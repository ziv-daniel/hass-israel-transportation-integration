"""The Silent Bus integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ApiConnectionError, BusNearbyApiClient
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
    TRANSPORT_TYPE_BUS,
    TRANSPORT_TYPE_TRAIN,
)
from .coordinator import SilentBusCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service names
SERVICE_REFRESH_DATA = "refresh_data"
SERVICE_UPDATE_LINES = "update_lines"

# Service schemas
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SERVICE_UPDATE_LINES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required("lines"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Silent Bus from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if setup was successful

    Raises:
        ConfigEntryNotReady: If setup should be retried
    """
    _LOGGER.debug("Setting up Silent Bus integration for entry %s", entry.entry_id)

    # Get common configuration
    transport_type = entry.data.get(CONF_TRANSPORT_TYPE, TRANSPORT_TYPE_BUS)
    update_interval_seconds = entry.data.get(
        CONF_UPDATE_INTERVAL,
        DEFAULT_SCAN_INTERVAL.total_seconds(),
    )
    max_arrivals = entry.data.get(CONF_MAX_ARRIVALS, DEFAULT_MAX_ARRIVALS)

    # Convert update interval to timedelta
    update_interval = timedelta(seconds=update_interval_seconds)

    # Create API client
    session = async_get_clientsession(hass)
    api_client = BusNearbyApiClient(session)

    # Validate connection and create coordinator based on transport type
    try:
        if transport_type == TRANSPORT_TYPE_TRAIN:
            # Train configuration
            from_station = entry.data[CONF_FROM_STATION]
            to_station = entry.data[CONF_TO_STATION]
            from_station_name = entry.data[CONF_FROM_STATION_NAME]
            to_station_name = entry.data[CONF_TO_STATION_NAME]

            # Validate stations
            from_valid = await api_client.validate_station(from_station)
            to_valid = await api_client.validate_station(to_station)

            if not from_valid or not to_valid:
                raise ConfigEntryNotReady(
                    f"Train stations {from_station} or {to_station} are not accessible."
                )

            # Create coordinator for train
            coordinator = SilentBusCoordinator(
                hass=hass,
                api_client=api_client,
                update_interval=update_interval,
                config_entry=entry,
                transport_type=transport_type,
                from_station=from_station,
                to_station=to_station,
                from_station_name=from_station_name,
                to_station_name=to_station_name,
                max_arrivals=max_arrivals,
            )

        else:
            # Bus/Light Rail configuration
            station_id = entry.data[CONF_STATION_ID]
            station_name = entry.data[CONF_STATION_NAME]
            bus_lines = entry.data[CONF_BUS_LINES]

            # Validate station
            is_valid = await api_client.validate_station(station_id)
            if not is_valid:
                raise ConfigEntryNotReady(
                    f"Station {station_id} is not accessible. Please check your configuration."
                )

            # Create coordinator for bus/light rail
            coordinator = SilentBusCoordinator(
                hass=hass,
                api_client=api_client,
                update_interval=update_interval,
                config_entry=entry,
                transport_type=transport_type,
                station_id=station_id,
                station_name=station_name,
                bus_lines=bus_lines,
                max_arrivals=max_arrivals,
            )

    except ApiConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to connect to BusNearby API: {err}") from err

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services (only once, for the first entry)
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_DATA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_DATA,
            async_handle_refresh_data,
            schema=SERVICE_REFRESH_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_LINES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_LINES,
            async_handle_update_lines,
            schema=SERVICE_UPDATE_LINES_SCHEMA,
        )

    # Log success message
    if transport_type == TRANSPORT_TYPE_TRAIN:
        _LOGGER.info(
            "Successfully set up Silent Bus integration for train route %s → %s",
            entry.data.get(CONF_FROM_STATION_NAME, ""),
            entry.data.get(CONF_TO_STATION_NAME, ""),
        )
    else:
        _LOGGER.info(
            "Successfully set up Silent Bus integration for station %s (%s)",
            entry.data.get(CONF_STATION_NAME, ""),
            entry.data.get(CONF_STATION_ID, ""),
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if unload was successful
    """
    _LOGGER.debug("Unloading Silent Bus integration for entry %s", entry.entry_id)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up stored data
        hass.data[DOMAIN].pop(entry.entry_id)

        # Close API client if it owns the session
        # Note: We're using the shared session from async_get_clientsession,
        # so we don't close it here

        _LOGGER.info("Successfully unloaded Silent Bus integration")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    _LOGGER.debug("Reloading Silent Bus integration for entry %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_handle_refresh_data(call: ServiceCall) -> None:
    """Handle the refresh_data service call.

    Args:
        call: Service call data
    """
    hass = call.hass
    entity_ids = call.data.get(ATTR_ENTITY_ID)

    # If no entity IDs specified, refresh all coordinators
    if not entity_ids:
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            coordinator = entry_data.get("coordinator")
            if coordinator:
                _LOGGER.info("Refreshing data for coordinator %s", entry_id)
                await coordinator.async_request_refresh()
        return

    # Refresh specific entities
    for entity_id in entity_ids:
        # Find the coordinator for this entity
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            coordinator = entry_data.get("coordinator")
            if coordinator:
                _LOGGER.info("Refreshing data for entity %s", entity_id)
                await coordinator.async_request_refresh()
                break


async def async_handle_update_lines(call: ServiceCall) -> None:
    """Handle the update_lines service call.

    Args:
        call: Service call data
    """
    hass = call.hass
    entity_id = call.data[ATTR_ENTITY_ID]
    lines_str = call.data["lines"]

    # Parse lines (comma-separated)
    new_lines = [line.strip() for line in lines_str.split(",") if line.strip()]

    if not new_lines:
        _LOGGER.warning("No valid lines provided for update_lines service")
        return

    # Find the config entry for this entity
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        coordinator: SilentBusCoordinator = entry_data.get("coordinator")
        if not coordinator:
            continue

        # Only update for bus/light rail (not trains)
        if coordinator.transport_type == TRANSPORT_TYPE_TRAIN:
            _LOGGER.warning("Cannot update lines for train routes")
            continue

        # Update the coordinator's bus_lines
        coordinator.bus_lines = new_lines

        # Get the config entry and update it
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry:
            # Create new data dict with updated lines
            new_data = dict(entry.data)
            new_data[CONF_BUS_LINES] = new_lines

            # Update the config entry
            hass.config_entries.async_update_entry(entry, data=new_data)

            _LOGGER.info(
                "Updated lines for entity %s to: %s",
                entity_id,
                new_lines,
            )

            # Trigger a refresh to get new data
            await coordinator.async_request_refresh()
            break
