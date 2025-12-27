"""Config flow for Silent Bus integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import (
    ApiConnectionError,
    BusNearbyApiClient,
)
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
            if self._transport_type == TRANSPORT_TYPE_TRAIN:
                return await self.async_step_train_config()
            else:
                # For bus and light rail, use station-based configuration
                return await self.async_step_station_config()

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

            # Validate station ID
            try:
                async with aiohttp.ClientSession() as session:
                    api_client = BusNearbyApiClient(session)

                    # Try to validate the station
                    is_valid = await api_client.validate_station(station_id)

                    if not is_valid:
                        errors["base"] = ERROR_STATION_NOT_FOUND
                    else:
                        # Try to get station name
                        try:
                            stations = await api_client.search_station(station_id)
                            if stations:
                                self._station_name = stations[0].get(
                                    "name", f"Station {station_id}"
                                )
                            else:
                                self._station_name = f"Station {station_id}"
                        except Exception:
                            self._station_name = f"Station {station_id}"

                        self._station_id = station_id

                        # Move to next step
                        return await self.async_step_bus_lines()

            except ApiConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
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

            # Validate stations
            try:
                async with aiohttp.ClientSession() as session:
                    api_client = BusNearbyApiClient(session)

                    # Validate both stations
                    from_valid = await api_client.validate_station(from_station)
                    to_valid = await api_client.validate_station(to_station)

                    if not from_valid or not to_valid:
                        errors["base"] = ERROR_STATION_NOT_FOUND
                    else:
                        # Get station names
                        try:
                            from_stations = await api_client.search_station(
                                from_station
                            )
                            if from_stations:
                                self._from_station_name = from_stations[0].get(
                                    "name", f"Station {from_station}"
                                )
                            else:
                                self._from_station_name = f"Station {from_station}"
                        except Exception:
                            self._from_station_name = f"Station {from_station}"

                        try:
                            to_stations = await api_client.search_station(to_station)
                            if to_stations:
                                self._to_station_name = to_stations[0].get(
                                    "name", f"Station {to_station}"
                                )
                            else:
                                self._to_station_name = f"Station {to_station}"
                        except Exception:
                            self._to_station_name = f"Station {to_station}"

                        self._from_station = from_station
                        self._to_station = to_station

                        # Create entry for train
                        await self.async_set_unique_id(f"{from_station}_{to_station}")
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
