"""Config flow for Israel Transportation integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ApiConnectionError,
    BusNearbyApiClient,
    InvalidResponseError,
)
from .gov_api import (
    ApiConnectionError as GovApiConnectionError,
    GovApiClient,
    InvalidMakatError,
    InvalidResponseError as GovInvalidResponseError,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .gtfs_loader import (
    async_load_cities_index,
    get_all_cities_list,
    get_cities_list,
    get_stations_for_city,
    is_gtfs_data_available,
)
from israelrailapi.train_station import STATIONS as RAIL_STATIONS
from .const import (
    CONF_BUS_LINES,
    CONF_FROM_STATION,
    CONF_FROM_STATION_NAME,
    CONF_MAX_ARRIVALS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TO_STATION,
    CONF_TO_STATION_NAME,
    CONF_TRANSPORT_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MAX_ARRIVALS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_STATION_RESPONSE,
    ERROR_STATION_NOT_FOUND,
    ERROR_UNKNOWN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TRANSPORT_TYPE_BUS,
    TRANSPORT_TYPE_LABELS,
    TRANSPORT_TYPE_LIGHT_RAIL,
    TRANSPORT_TYPE_TRAIN,
)

_LOGGER = logging.getLogger(__name__)


def get_train_stations_list() -> list[dict[str, str]]:
    """Get train stations from israel-rail-api library.

    Returns:
        List of station dicts with id, name, and name_en keys
    """
    stations = []
    for station_id, names in RAIL_STATIONS.items():
        hebrew_name = names.get("Heb", "")
        english_name = names.get("Eng", hebrew_name)
        stations.append(
            {
                "id": str(station_id),
                "name": f"{hebrew_name} - {english_name} ({station_id})",
                "name_en": english_name,
            }
        )
    # Sort by Hebrew name
    stations.sort(key=lambda x: x["name"])
    return stations


class SilentBusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Israel Transportation."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._station_id: Optional[str] = None
        self._station_name: Optional[str] = None
        self._transport_type: Optional[str] = None
        self._from_station: Optional[str] = None
        self._to_station: Optional[str] = None
        self._from_station_name: Optional[str] = None
        self._to_station_name: Optional[str] = None
        self._selected_city: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step - transport type selection.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        if user_input is not None:
            self._transport_type = user_input[CONF_TRANSPORT_TYPE]

            # Route to appropriate configuration step
            # For all transport types, ask how they want to select station
            return await self.async_step_station_selection_method()

        # Show transport type selection
        data_schema = vol.Schema(
            {
                vol.Required(CONF_TRANSPORT_TYPE, default=TRANSPORT_TYPE_BUS): vol.In(
                    {
                        TRANSPORT_TYPE_BUS: TRANSPORT_TYPE_LABELS[TRANSPORT_TYPE_BUS],
                        TRANSPORT_TYPE_TRAIN: TRANSPORT_TYPE_LABELS[
                            TRANSPORT_TYPE_TRAIN
                        ],
                        TRANSPORT_TYPE_LIGHT_RAIL: TRANSPORT_TYPE_LABELS[
                            TRANSPORT_TYPE_LIGHT_RAIL
                        ],
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={
                "type_help": "Select the type of public transportation you want to track"
            },
        )

    async def async_step_station_selection_method(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle station selection method choice.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        # Pre-load GTFS data asynchronously to avoid blocking I/O warnings
        try:
            await async_load_cities_index(self.hass)
        except FileNotFoundError:
            pass  # Will be handled by is_gtfs_data_available() check below

        if user_input is not None:
            selection_method = user_input["selection_method"]

            if selection_method == "city_dropdown":
                # Bus/Light Rail: use city-based dropdown
                return await self.async_step_select_city()
            elif selection_method == "train_dropdown":
                # Train: use train station dropdown
                return await self.async_step_train_select_from()
            else:
                # Manual entry
                if self._transport_type == TRANSPORT_TYPE_TRAIN:
                    return await self.async_step_train_config()
                else:
                    return await self.async_step_station_config()

        # Check if GTFS data is available
        gtfs_available = is_gtfs_data_available()

        # Build selection options based on transport type
        if self._transport_type == TRANSPORT_TYPE_TRAIN:
            # Train: offer train station dropdown or manual
            options = {
                "train_dropdown": "Select from train stations list (recommended)",
                "manual": "Enter station ID manually",
            }
            default_method = "train_dropdown"
        elif gtfs_available:
            # Bus/Light Rail: offer city dropdown or manual
            options = {
                "city_dropdown": "Browse stations by city (recommended)",
                "manual": "Enter station ID manually",
            }
            default_method = "city_dropdown"
        else:
            # GTFS data not available, only offer manual entry
            options = {
                "manual": "Enter station ID manually",
            }
            default_method = "manual"

        data_schema = vol.Schema(
            {
                vol.Required("selection_method", default=default_method): vol.In(
                    options
                ),
            }
        )

        return self.async_show_form(
            step_id="station_selection_method",
            data_schema=data_schema,
            description_placeholders={
                "transport_type": TRANSPORT_TYPE_LABELS.get(
                    self._transport_type, "transportation"
                ).lower(),
            },
        )

    async def async_step_select_city(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle city selection from GTFS data.

        Shows cities filtered and sorted:
        - Nearby cities first (based on Home Assistant home location)
        - Then top 3 largest cities
        - Then remaining cities sorted א-ת (Hebrew alphabetical)
        - Only cities with 50+ stations are shown

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        _LOGGER.debug("user_input=%s", user_input)
        _LOGGER.debug("user_input type=%s", type(user_input))

        if user_input is not None:
            try:
                city_input = user_input.get("city_id", "").strip()
                _LOGGER.debug(
                    "Received city_input: %r (type: %s, len: %d)",
                    city_input,
                    type(city_input),
                    len(city_input) if city_input else 0,
                )

                # Extract city_id from formatted string like "City Name [city_id]"
                import re

                match = re.search(r"\[([^\]]+)\]$", city_input)
                if match:
                    city_id = match.group(1)
                    _LOGGER.debug("Extracted city_id: %r from input", city_id)
                else:
                    # Fallback: use input directly (might be manual entry)
                    city_id = city_input
                    _LOGGER.debug("Using raw input as city_id: %r", city_id)

                # Handle special options
                if city_id == "manual" or "manual" in city_input.lower():
                    _LOGGER.debug("Manual entry selected")
                    return await self.async_step_station_config()
                if city_id == "show_all" or "show all" in city_input.lower():
                    _LOGGER.debug("Show all cities selected")
                    return await self.async_step_select_city_all()

                # Save selected city and move to station selection
                _LOGGER.debug("Setting _selected_city to: %r", city_id)
                self._selected_city = city_id
                _LOGGER.debug("Calling async_step_select_station()")
                return await self.async_step_select_station()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception while selecting a city")
                errors["base"] = ERROR_UNKNOWN

        # Get home location for proximity sorting
        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude

        # Get cities list - shows 3 closest first (if coordinates available), then all others alphabetically
        # No filtering by min_stations - shows ALL cities (matching self._transport_type,
        # e.g. only light-rail-served cities when configuring a light rail sensor)
        cities = get_cities_list(
            home_lat=home_lat, home_lon=home_lon, transport_type=self._transport_type
        )

        if not cities:
            # No GTFS data available, fall back to manual entry
            return await self.async_step_station_config()

        # Cities are already sorted: nearby first (with 📍), then alphabetical.
        options = [
            SelectOptionDict(value=city["id"], label=city["name"]) for city in cities
        ]
        options.append(
            SelectOptionDict(value="show_all", label="📋 Show all cities...")
        )
        options.append(
            SelectOptionDict(value="manual", label="🔍 Enter station ID manually...")
        )

        _LOGGER.debug("Built city dropdown with %d options", len(options))

        data_schema = vol.Schema(
            {
                vol.Required("city_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_city",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "transport_type": TRANSPORT_TYPE_LABELS.get(
                    self._transport_type, "transportation"
                ).lower(),
            },
        )

    async def async_step_select_city_all(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle selection from ALL cities (no filtering).

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            import re

            city_input = user_input.get("city_id", "").strip()

            # Extract city_id from formatted string like "City Name [city_id]"
            match = re.search(r"\[([^\]]+)\]$", city_input)
            if match:
                city_id = match.group(1)
            else:
                city_id = city_input

            if city_id == "manual" or "manual" in city_input.lower():
                return await self.async_step_station_config()

            self._selected_city = city_id
            return await self.async_step_select_station()

        # Get ALL cities (no minimum station filter), still restricted to the
        # transport type being configured so bus/light-rail don't leak into
        # each other's pickers.
        cities = get_all_cities_list(transport_type=self._transport_type)

        if not cities:
            return await self.async_step_station_config()

        options = [
            SelectOptionDict(value=city["id"], label=city["name"]) for city in cities
        ]
        options.append(
            SelectOptionDict(value="manual", label="🔍 Enter station ID manually...")
        )

        data_schema = vol.Schema(
            {
                vol.Required("city_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_city_all",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "transport_type": TRANSPORT_TYPE_LABELS.get(
                    self._transport_type, "transportation"
                ).lower(),
            },
        )

    async def async_step_select_station(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle station selection from chosen city.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        _LOGGER.debug("user_input=%s", user_input)
        _LOGGER.debug("_selected_city=%s", self._selected_city)
        errors: dict[str, str] = {}

        if user_input is not None:
            station_input = user_input["station_id"].strip()

            # Handle manual entry fallback
            if station_input.lower() == "manual" or "manual" in station_input.lower():
                return await self.async_step_station_config()

            # Get station details from GTFS data and match user input
            stations = get_stations_for_city(
                self._selected_city, transport_type=self._transport_type
            )
            selected_station = self._find_station_by_input(stations, station_input)

            if selected_station:
                self._station_name = selected_station["name"]

                # The bundled GTFS index is keyed by GTFS stop_id, but the MOT API
                # addresses stops by stop_code (makat) — different identifiers that
                # happen to share a numeric range, so passing the stop_id through
                # silently resolves to a *different* station. Translate first.
                try:
                    async with GovApiClient(
                        async_get_clientsession(self.hass)
                    ) as gov_client:
                        makat = await self._resolve_makat(gov_client, selected_station)

                        if makat is None:
                            errors["base"] = ERROR_STATION_NOT_FOUND
                        else:
                            station_info = await gov_client.get_station(makat)

                            if (
                                station_info.get("Name") is None
                                or station_info.get("Makat", 0) == 0
                            ):
                                _LOGGER.error(
                                    "Station %s failed MOT API validation: %s",
                                    makat,
                                    station_info,
                                )
                                errors["base"] = ERROR_STATION_NOT_FOUND
                            else:
                                # Store the makat — this is what the API expects at runtime
                                self._station_id = makat
                                self._station_name = station_info.get(
                                    "Name", self._station_name
                                )
                                _LOGGER.debug(
                                    "Station resolved: gtfs_stop_id=%s -> makat=%s (%s)",
                                    selected_station["id"],
                                    makat,
                                    self._station_name,
                                )
                                return await self.async_step_bus_lines()

                except GovApiConnectionError:
                    errors["base"] = ERROR_CANNOT_CONNECT
                except GovInvalidResponseError:
                    # Upstream answered, but not with its API — surface it as a
                    # connection problem rather than a mystery "unknown error".
                    _LOGGER.exception("MOT API returned an unexpected response")
                    errors["base"] = ERROR_CANNOT_CONNECT
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during MOT API validation")
                    errors["base"] = ERROR_UNKNOWN
            else:
                errors["base"] = ERROR_STATION_NOT_FOUND

        # Get stations for selected city
        try:
            _LOGGER.debug(
                "Fetching stations for city: %r", self._selected_city or "Other"
            )
            stations = get_stations_for_city(
                self._selected_city or "Other", transport_type=self._transport_type
            )
            _LOGGER.debug(
                "Found %d stations for city %r", len(stations), self._selected_city
            )
        except Exception as e:
            _LOGGER.error(
                "Error getting stations for city %r: %s",
                self._selected_city,
                str(e),
                exc_info=True,
            )
            errors["base"] = "unknown"
            stations = []

        if not stations:
            # No stations found, fall back to manual entry
            _LOGGER.warning(
                "No stations found for city %r, falling back to manual entry",
                self._selected_city,
            )
            return await self.async_step_station_config()

        sorted_stations = sorted(stations, key=lambda s: s["name"])

        options = [
            SelectOptionDict(
                value=station["id"], label=f"{station['name']} ({station['id']})"
            )
            for station in sorted_stations
        ]
        options.append(
            SelectOptionDict(value="manual", label="🔍 Enter station ID manually...")
        )

        data_schema = vol.Schema(
            {
                vol.Required("station_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_station",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "city_name": self._selected_city or "Unknown",
                "station_count": str(len(stations)),
            },
        )

    async def _resolve_makat(
        self, gov_client: GovApiClient, gtfs_station: dict
    ) -> Optional[str]:
        """Translate a bundled-GTFS station into the MOT API's stop code.

        The GTFS index stores GTFS ``stop_id``; the API addresses stops by
        ``stop_code`` (the number on the stop sign). Both are small integers, so a
        stop_id passed to the API usually resolves to a real but *different*
        station. Resolve by searching the station's name and matching on position.

        Args:
            gov_client: Client to search with.
            gtfs_station: Station dict from the GTFS index (``name``/``lat``/``lon``).

        Returns:
            The matching stop code, or None if it could not be resolved.
        """
        # Newer GTFS index builds carry the stop_code directly; use it and skip
        # the search entirely. Older bundled data predates that field, hence the
        # name-and-coordinates fallback below.
        code = str(gtfs_station.get("code") or "").strip()
        if code.isascii() and code.isdigit():
            return code

        name = gtfs_station.get("name") or ""
        lat = gtfs_station.get("lat")
        lon = gtfs_station.get("lon")

        candidates = await gov_client.search_stations(name)
        if not candidates:
            _LOGGER.warning("No MOT API match for GTFS station %r", name)
            return None

        if lat is None or lon is None:
            # Without coordinates we can only trust an unambiguous name match.
            return candidates[0]["makat"] if len(candidates) == 1 else None

        # ~0.002 degrees is roughly 200m — close enough to be the same stop,
        # tight enough to not pick the one across the street.
        best = None
        best_distance = 0.002
        for candidate in candidates:
            c_lat, c_lon = candidate.get("lat"), candidate.get("lon")
            if c_lat is None or c_lon is None:
                continue
            distance = max(abs(c_lat - lat), abs(c_lon - lon))
            if distance < best_distance:
                best_distance = distance
                best = candidate

        if best is None:
            _LOGGER.warning(
                "Found %d MOT API candidates for %r but none within range of the "
                "GTFS coordinates; ask the user for the stop code instead",
                len(candidates),
                name,
            )
            return None

        return best["makat"]

    def _find_station_by_input(
        self, stations: list[dict], user_input: str
    ) -> Optional[dict]:
        """Find station by ID or name from user input.

        Args:
            stations: List of station dictionaries
            user_input: User's text input (could be ID, name, or formatted string)

        Returns:
            Matching station dict or None

        Examples:
            >>> _find_station_by_input(stations, "Station Name (12345)")
            {'id': '12345', 'name': 'Station Name', ...}

            >>> _find_station_by_input(stations, "12345")
            {'id': '12345', 'name': 'Station Name', ...}
        """
        import re

        user_input = user_input.strip()

        # Check for manual entry option
        if user_input.lower() == "manual" or "manual" in user_input.lower():
            return None

        # Extract ID from formatted string like "Station Name (12345)"
        id_match = re.search(r"\((\d+)\)$", user_input)
        if id_match:
            station_id = id_match.group(1)
        else:
            # Try using input directly as ID
            station_id = user_input

        # Try exact ID match first
        for station in stations:
            if station["id"] == station_id:
                return station

        # Fallback: fuzzy name matching
        user_lower = user_input.lower()
        for station in stations:
            if user_lower in station["name"].lower():
                return station

        return None

    async def async_step_station_config(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle station configuration for bus and light rail.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID].strip()

            # ASCII digits only — isdigit() alone also accepts Arabic-Indic/Unicode digits
            if not station_id or not station_id.isascii() or not station_id.isdigit():
                errors[CONF_STATION_ID] = "invalid_station_id"
            else:
                # Validate station directly with gov API (no translation needed)
                try:
                    async with GovApiClient(
                        async_get_clientsession(self.hass)
                    ) as gov_client:
                        station_info = await gov_client.get_station(station_id)

                        if (
                            station_info.get("Name") is None
                            or station_info.get("Makat", 0) == 0
                        ):
                            errors["base"] = ERROR_STATION_NOT_FOUND
                        else:
                            self._station_id = station_id
                            self._station_name = station_info.get(
                                "Name", f"Station {station_id}"
                            )
                            _LOGGER.info(
                                "Station validated: makat=%s, name=%s",
                                self._station_id,
                                self._station_name,
                            )
                            return await self.async_step_bus_lines()

                except InvalidMakatError:
                    errors["base"] = ERROR_STATION_NOT_FOUND
                except GovApiConnectionError:
                    _LOGGER.warning("Could not reach the MOT API", exc_info=True)
                    errors["base"] = ERROR_CANNOT_CONNECT
                except GovInvalidResponseError:
                    _LOGGER.exception("MOT API returned an unexpected response")
                    errors["base"] = ERROR_CANNOT_CONNECT
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during station validation")
                    errors["base"] = ERROR_UNKNOWN

        # Use TextSelector — vol.Match is not serializable by voluptuous_serialize
        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )

        transport_label = TRANSPORT_TYPE_LABELS.get(self._transport_type, "Station")

        return self.async_show_form(
            step_id="station_config",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_help": f"Enter the {transport_label.lower()} station number (e.g., 24068). "
                "You can find station numbers at https://www.bus.co.il"
            },
        )

    async def async_step_train_select_from(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle FROM train station selection from dropdown.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        if user_input is not None:
            station_id = user_input["from_station"]

            # Check if user chose manual entry
            if station_id == "manual":
                return await self.async_step_train_config()

            # Get station names from train stations list
            stations_list = get_train_stations_list()
            station = next((s for s in stations_list if s["id"] == station_id), None)

            if station:
                self._from_station_name = station["name_en"]
                # Use rail station code directly - the train API expects rail codes
                self._from_station = station_id
                _LOGGER.debug(
                    "Train FROM station: rail_code=%s, name=%s",
                    station_id,
                    station["name_en"],
                )

                # Move to TO station selection
                return await self.async_step_train_select_to()
            else:
                # Fallback to manual if station not found
                return await self.async_step_train_config()

        # Get train stations list
        stations_list = get_train_stations_list()
        station_options = {s["id"]: s["name"] for s in stations_list}

        # Add manual entry option
        station_options["manual"] = "🔍 Enter station ID manually..."

        data_schema = vol.Schema(
            {
                vol.Required("from_station"): vol.In(station_options),
            }
        )

        return self.async_show_form(
            step_id="train_select_from",
            data_schema=data_schema,
            description_placeholders={
                "train_help": "Select the origin (FROM) train station"
            },
        )

    async def async_step_train_select_to(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle TO train station selection from dropdown.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input["to_station"]

            # Check if user chose manual entry
            if station_id == "manual":
                return await self.async_step_train_config()

            # Get station names from train stations list
            stations_list = get_train_stations_list()
            station = next((s for s in stations_list if s["id"] == station_id), None)

            if station:
                self._to_station_name = station["name_en"]
                # Use rail station code directly - the train API expects rail codes
                self._to_station = station_id
                _LOGGER.debug(
                    "Train TO station: rail_code=%s, name=%s",
                    station_id,
                    station["name_en"],
                )

                # Validate: FROM and TO must be different
                if self._from_station == self._to_station:
                    errors["to_station"] = "cannot_be_same"
                else:
                    # Skip BusNearby API validation for dropdown selections
                    # The dropdown contains known-valid Israel Railways station codes
                    # BusNearby API doesn't understand rail codes (7300, 3600, etc.)
                    # Validation is only needed for manual entry
                    _LOGGER.debug(
                        "Creating train route from dropdown: %s (%s) -> %s (%s)",
                        self._from_station,
                        self._from_station_name,
                        self._to_station,
                        self._to_station_name,
                    )

                    # Create entry for train
                    await self.async_set_unique_id(
                        f"{self._from_station}_{self._to_station}"
                    )
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"{self._from_station_name} → {self._to_station_name}",
                        data={
                            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN,
                            CONF_FROM_STATION: self._from_station,
                            CONF_TO_STATION: self._to_station,
                            CONF_FROM_STATION_NAME: self._from_station_name,
                            CONF_TO_STATION_NAME: self._to_station_name,
                            CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
                            CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
                        },
                    )

        # Get train stations list (include all stations — cannot_be_same error handles duplicates)
        stations_list = get_train_stations_list()
        station_options = {s["id"]: s["name"] for s in stations_list}

        # Add manual entry option
        station_options["manual"] = "🔍 Enter station ID manually..."

        data_schema = vol.Schema(
            {
                vol.Required("to_station"): vol.In(station_options),
            }
        )

        return self.async_show_form(
            step_id="train_select_to",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "from_station": self._from_station_name,
                "train_help": f"Select the destination (TO) train station from {self._from_station_name}",  # nosec B608
            },
        )

    async def async_step_train_config(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle train configuration (from/to stations).

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            from_station = user_input[CONF_FROM_STATION].strip()
            to_station = user_input[CONF_TO_STATION].strip()

            # Validate and get station info in one call per station (Phase 1 fix)
            try:
                async with aiohttp.ClientSession() as session:
                    api_client = BusNearbyApiClient(session)

                    # Validate and get station names using search endpoint
                    try:
                        from_stations = await api_client.search_station(from_station)
                        to_stations = await api_client.search_station(to_station)

                        if not from_stations or not to_stations:
                            errors["base"] = ERROR_STATION_NOT_FOUND
                        else:
                            # Get station names from search results
                            self._from_station_name = from_stations[0].get(
                                "name", f"Station {from_station}"
                            )
                            self._to_station_name = to_stations[0].get(
                                "name", f"Station {to_station}"
                            )
                            self._from_station = from_station
                            self._to_station = to_station

                            # Validate API response format before proceeding
                            (
                                is_valid,
                                error_msg,
                            ) = await api_client.validate_train_route_api_response(
                                from_station, to_station
                            )
                            if not is_valid:
                                _LOGGER.error(
                                    "Train route %s → %s failed API validation: %s",
                                    from_station,
                                    to_station,
                                    error_msg,
                                )
                                errors["base"] = ERROR_INVALID_STATION_RESPONSE
                            else:
                                # Create entry for train
                                await self.async_set_unique_id(
                                    f"{from_station}_{to_station}"
                                )
                                self._abort_if_unique_id_configured()

                                return self.async_create_entry(
                                    title=f"{self._from_station_name} → {self._to_station_name}",
                                    data={
                                        CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN,
                                        CONF_FROM_STATION: self._from_station,
                                        CONF_TO_STATION: self._to_station,
                                        CONF_FROM_STATION_NAME: self._from_station_name,
                                        CONF_TO_STATION_NAME: self._to_station_name,
                                        CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
                                        CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
                                    },
                                )
                    except InvalidResponseError as err:
                        _LOGGER.error(
                            "Train route %s → %s has invalid API response: %s",
                            from_station,
                            to_station,
                            err,
                        )
                        errors["base"] = ERROR_INVALID_STATION_RESPONSE
                    except Exception:
                        errors["base"] = ERROR_STATION_NOT_FOUND

            except ApiConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = ERROR_UNKNOWN

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_FROM_STATION): str,
                vol.Required(CONF_TO_STATION): str,
            }
        )

        return self.async_show_form(
            step_id="train_config",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "train_help": "Enter origin and destination train station numbers (e.g., 3600 for Tel Aviv). "
                "You can find station numbers at https://www.rail.co.il"
            },
        )

    async def async_step_bus_lines(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle bus lines selection step.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            bus_lines_input = user_input[CONF_BUS_LINES].strip()

            # Parse bus lines (comma-separated)
            bus_lines = [
                line.strip() for line in bus_lines_input.split(",") if line.strip()
            ]

            if not bus_lines:
                errors["base"] = "no_lines"
            else:
                # Create the config entry
                await self.async_set_unique_id(f"{self._station_id}")
                self._abort_if_unique_id_configured()

                transport_type = self._transport_type or TRANSPORT_TYPE_BUS

                return self.async_create_entry(
                    title=f"{self._station_name}",
                    data={
                        CONF_TRANSPORT_TYPE: transport_type,
                        CONF_STATION_ID: self._station_id,
                        CONF_STATION_NAME: self._station_name,
                        CONF_BUS_LINES: bus_lines,
                        CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
                        CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
                    },
                )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_BUS_LINES): str,
            }
        )

        transport_label = TRANSPORT_TYPE_LABELS.get(self._transport_type, "Bus")
        lines_example = (
            "1, 3"
            if self._transport_type == TRANSPORT_TYPE_LIGHT_RAIL
            else "249, 40, 605"
        )

        return self.async_show_form(
            step_id="bus_lines",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_name": self._station_name or "Unknown",
                "lines_help": f"Enter {transport_label.lower()} line numbers separated by commas (e.g., {lines_example})",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SilentBusOptionsFlow:
        """Get the options flow for this handler.

        Args:
            config_entry: Config entry

        Returns:
            Options flow handler
        """
        return SilentBusOptionsFlow(config_entry)


class SilentBusOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Israel Transportation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        return self._config_entry

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse bus lines
            bus_lines_input = user_input[CONF_BUS_LINES].strip()
            bus_lines = [
                line.strip() for line in bus_lines_input.split(",") if line.strip()
            ]

            if not bus_lines:
                errors["base"] = "no_lines"
            else:
                # Update the config entry
                new_data = {
                    **self.config_entry.data,
                    CONF_BUS_LINES: bus_lines,
                    CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                    CONF_MAX_ARRIVALS: user_input[CONF_MAX_ARRIVALS],
                }

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

                return self.async_create_entry(title="", data={})

        # Get current values
        current_lines = self.config_entry.data.get(CONF_BUS_LINES, [])
        current_interval = self.config_entry.data.get(
            CONF_UPDATE_INTERVAL,
            DEFAULT_SCAN_INTERVAL.total_seconds(),
        )
        current_max_arrivals = self.config_entry.data.get(
            CONF_MAX_ARRIVALS,
            DEFAULT_MAX_ARRIVALS,
        )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_BUS_LINES,
                    default=", ".join(current_lines),
                ): str,
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=current_interval,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_SCAN_INTERVAL.total_seconds(),
                        max=MAX_SCAN_INTERVAL.total_seconds(),
                    ),
                ),
                vol.Required(
                    CONF_MAX_ARRIVALS,
                    default=current_max_arrivals,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_name": self.config_entry.data.get(
                    CONF_STATION_NAME, "Unknown"
                ),
            },
        )
