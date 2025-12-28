"""Config flow for Silent Bus integration."""

from __future__ import annotations

import logging
from typing import Any

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
from .gov_api import GovApiClient, ApiConnectionError as GovApiConnectionError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .gtfs_loader import (
    async_load_cities_index,
    get_all_cities_list,
    get_cities_list,
    get_cities_near_location,
    get_stations_for_city,
    is_gtfs_data_available,
)
from .train_stations import get_train_stations_list
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


class SilentBusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Silent Bus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._station_id: str | None = None
        self._station_name: str | None = None
        self._transport_type: str | None = None
        self._from_station: str | None = None
        self._to_station: str | None = None
        self._from_station_name: str | None = None
        self._to_station_name: str | None = None
        self._selected_city: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
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
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle station selection method choice.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        # Pre-load GTFS data asynchronously to avoid blocking I/O warnings
        try:
            await async_load_cities_index()
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
        self, user_input: dict[str, Any] | None = None
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

        if user_input is not None:
            city_id = user_input["city_id"]

            # Handle special options
            if city_id == "manual":
                return await self.async_step_station_config()
            if city_id == "show_all":
                return await self.async_step_select_city_all()

            # Save selected city and move to station selection
            self._selected_city = city_id
            return await self.async_step_select_station()

        # Try to get home location for nearby city suggestions
        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude
        nearby_cities = []
        suggested_city = None

        if home_lat and home_lon:
            # Get cities near home location (within 30km)
            nearby_cities = get_cities_near_location(
                home_lat, home_lon, max_distance_km=30.0, max_cities=5
            )
            if nearby_cities:
                suggested_city = nearby_cities[0]
                _LOGGER.debug(
                    "Found %d nearby cities. Closest: %s (%.1f km)",
                    len(nearby_cities),
                    suggested_city["id"],
                    suggested_city["distance_km"],
                )

        # Get filtered cities (>50 stations, top 3 biggest first, then Hebrew sorted)
        cities = get_cities_list(min_stations=50, max_cities=50, top_cities_count=3)

        if not cities:
            # No GTFS data available, fall back to manual entry
            return await self.async_step_station_config()

        # Build city options list for SelectSelector
        city_options: list[SelectOptionDict] = []

        # Add nearby cities section first (if any)
        nearby_city_ids = {c["id"] for c in nearby_cities}
        if nearby_cities:
            for city in nearby_cities:
                city_options.append(
                    SelectOptionDict(
                        value=city["id"],
                        label=f"📍 {city['name']} (~{city['distance_km']} km)",
                    )
                )

        # Add remaining cities (excluding already added nearby cities)
        for city in cities:
            if city["id"] not in nearby_city_ids:
                city_options.append(
                    SelectOptionDict(
                        value=city["id"],
                        label=city["name"],
                    )
                )

        # Add special options at the end
        city_options.append(
            SelectOptionDict(
                value="show_all",
                label="📋 Show all cities...",
            )
        )
        city_options.append(
            SelectOptionDict(
                value="manual",
                label="🔍 Enter station ID manually...",
            )
        )

        # Use SelectSelector with dropdown mode for searchable list
        data_schema = vol.Schema(
            {
                vol.Required(
                    "city_id",
                    default=suggested_city["id"] if suggested_city else None,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=city_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=False,
                        sort=False,  # We already sorted it ourselves
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
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle selection from ALL cities (no filtering).

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            city_id = user_input["city_id"]

            if city_id == "manual":
                return await self.async_step_station_config()

            self._selected_city = city_id
            return await self.async_step_select_station()

        # Get ALL cities (no minimum station filter)
        cities = get_all_cities_list()

        if not cities:
            return await self.async_step_station_config()

        # Build options list
        city_options: list[SelectOptionDict] = []
        for city in cities:
            city_options.append(
                SelectOptionDict(
                    value=city["id"],
                    label=city["name"],
                )
            )

        # Add manual entry option
        city_options.append(
            SelectOptionDict(
                value="manual",
                label="🔍 Enter station ID manually...",
            )
        )

        data_schema = vol.Schema(
            {
                vol.Required("city_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=city_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=False,
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
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle station selection from chosen city.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input["station_id"]

            # Handle manual entry fallback
            if station_id == "manual":
                return await self.async_step_station_config()

            # Get station details from GTFS data
            stations = get_stations_for_city(self._selected_city)
            selected_station = next(
                (s for s in stations if s["id"] == station_id), None
            )

            if selected_station:
                self._station_name = selected_station["name"]

                # Validate and resolve actual stop_id via API
                # GTFS data may use stop_code (shown on signs) instead of stop_id
                try:
                    async with aiohttp.ClientSession() as session:
                        api_client = BusNearbyApiClient(session)

                        # Try to find the station via API to get correct stop_id
                        try:
                            api_stations = await api_client.search_station(station_id)
                            if api_stations:
                                # Use stop_id from API result
                                actual_stop_id = api_stations[0].get(
                                    "stop_id", api_stations[0].get("id", station_id)
                                )
                                _LOGGER.debug(
                                    "GTFS station lookup: gtfs_id=%s -> stop_id=%s",
                                    station_id,
                                    actual_stop_id,
                                )
                            else:
                                # Fallback to GTFS ID if API search fails
                                actual_stop_id = station_id
                        except Exception:
                            actual_stop_id = station_id

                        self._station_id = actual_stop_id

                        # Validate API response format
                        (
                            is_valid,
                            error_msg,
                        ) = await api_client.validate_station_api_response(
                            actual_stop_id
                        )
                        if not is_valid:
                            _LOGGER.error(
                                "Station %s (gtfs: %s) failed API validation: %s",
                                actual_stop_id,
                                station_id,
                                error_msg,
                            )
                            errors["base"] = ERROR_INVALID_STATION_RESPONSE
                        else:
                            # Move to bus lines selection
                            return await self.async_step_bus_lines()
                except ApiConnectionError:
                    errors["base"] = ERROR_CANNOT_CONNECT
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during API validation")
                    errors["base"] = ERROR_UNKNOWN
            else:
                errors["base"] = ERROR_STATION_NOT_FOUND

        # Get stations for selected city
        stations = get_stations_for_city(self._selected_city or "Other")

        if not stations:
            # No stations found, fall back to manual entry
            return await self.async_step_station_config()

        # Build station options with SelectSelector
        # Sort by name and take first 100 stations
        sorted_stations = sorted(stations, key=lambda s: s["name"])[:100]

        station_options: list[SelectOptionDict] = []
        for station in sorted_stations:
            station_options.append(
                SelectOptionDict(
                    value=station["id"],
                    label=f"{station['name']} ({station['id']})",
                )
            )

        # Add manual entry fallback
        station_options.append(
            SelectOptionDict(
                value="manual",
                label="🔍 Enter station ID manually...",
            )
        )

        data_schema = vol.Schema(
            {
                vol.Required("station_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=station_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=False,
                        sort=False,  # Already sorted alphabetically
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

    async def async_step_station_config(
        self, user_input: dict[str, Any] | None = None
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

            # Validate station directly with gov API (no translation needed)
            try:
                async with GovApiClient(
                    async_get_clientsession(self.hass)
                ) as gov_client:
                    # Validate station directly with gov API
                    station_info = await gov_client.get_station(station_id)

                    if station_info.get("Name") is None or station_info.get("Makat", 0) == 0:
                        errors["base"] = ERROR_STATION_NOT_FOUND
                    else:
                        # Station is valid - use Makat directly
                        self._station_id = station_id
                        self._station_name = station_info.get("Name", f"Station {station_id}")

                        _LOGGER.info(
                            "Station validated: makat=%s, name=%s",
                            self._station_id,
                            self._station_name,
                        )

                        # Move to next step
                        return await self.async_step_bus_lines()

            except GovApiConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during station validation")
                errors["base"] = ERROR_UNKNOWN

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): str,
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
        self, user_input: dict[str, Any] | None = None
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

                # Resolve Israel Railways code to BusNearby stop_id by searching
                # by Hebrew station name (more reliable than using rail codes)
                try:
                    async with aiohttp.ClientSession() as session:
                        api_client = BusNearbyApiClient(session)
                        # Search by Hebrew name to find BusNearby stop_id
                        search_results = await api_client.search_station(
                            station["name_he"]
                        )
                        if search_results:
                            # Use the BusNearby stop_id for API calls
                            self._from_station = search_results[0].get(
                                "stop_id", station_id
                            )
                            _LOGGER.debug(
                                "Train FROM station: rail_code=%s -> stop_id=%s (name: %s)",
                                station_id,
                                self._from_station,
                                station["name_he"],
                            )
                        else:
                            # Fallback to rail code if search fails
                            self._from_station = station_id
                            _LOGGER.warning(
                                "Could not resolve BusNearby ID for train station %s (%s)",
                                station_id,
                                station["name_he"],
                            )
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to resolve train station %s: %s", station_id, err
                    )
                    self._from_station = station_id

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
        self, user_input: dict[str, Any] | None = None
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

                # Resolve Israel Railways code to BusNearby stop_id
                try:
                    async with aiohttp.ClientSession() as session:
                        api_client = BusNearbyApiClient(session)
                        # Search by Hebrew name to find BusNearby stop_id
                        search_results = await api_client.search_station(
                            station["name_he"]
                        )
                        if search_results:
                            self._to_station = search_results[0].get(
                                "stop_id", station_id
                            )
                            _LOGGER.debug(
                                "Train TO station: rail_code=%s -> stop_id=%s (name: %s)",
                                station_id,
                                self._to_station,
                                station["name_he"],
                            )
                        else:
                            self._to_station = station_id
                            _LOGGER.warning(
                                "Could not resolve BusNearby ID for train station %s (%s)",
                                station_id,
                                station["name_he"],
                            )

                        # Validate: FROM and TO must be different
                        if self._from_station == self._to_station:
                            errors["to_station"] = "cannot_be_same"
                        else:
                            # Validate train route API response before creating entry
                            (
                                is_valid,
                                error_msg,
                            ) = await api_client.validate_train_route_api_response(
                                self._from_station, self._to_station
                            )
                            if not is_valid:
                                _LOGGER.error(
                                    "Train route %s -> %s failed validation: %s",
                                    self._from_station,
                                    self._to_station,
                                    error_msg,
                                )
                                errors["base"] = ERROR_INVALID_STATION_RESPONSE
                            else:
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
                except ApiConnectionError:
                    errors["base"] = ERROR_CANNOT_CONNECT
                except Exception as err:
                    _LOGGER.exception("Failed to validate train route: %s", err)
                    errors["base"] = ERROR_UNKNOWN

        # Get train stations list (exclude the FROM station)
        stations_list = get_train_stations_list()
        station_options = {
            s["id"]: s["name"]
            for s in stations_list
            if s["id"] != self._from_station  # Exclude FROM station
        }

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
                "train_help": f"Select the destination (TO) train station from {self._from_station_name}",
            },
        )

    async def async_step_train_config(
        self, user_input: dict[str, Any] | None = None
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
        self, user_input: dict[str, Any] | None = None
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
        return SilentBusOptionsFlow()


class SilentBusOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Silent Bus."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
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
