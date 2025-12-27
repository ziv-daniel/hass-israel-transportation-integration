"""Sensor platform for Silent Bus integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ATTRIBUTION,
    ATTR_DIRECTION,
    ATTR_LAST_UPDATE,
    ATTR_LINE_NUMBER,
    ATTR_NEXT_ARRIVAL,
    ATTR_REAL_TIME,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    ATTR_UPCOMING_ARRIVALS,
    ATTRIBUTION,
    CONF_BUS_LINES,
    CONF_FROM_STATION,
    CONF_FROM_STATION_NAME,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TO_STATION,
    CONF_TO_STATION_NAME,
    CONF_TRANSPORT_TYPE,
    DOMAIN,
    TRANSPORT_TYPE_BUS,
    TRANSPORT_TYPE_ICONS,
    TRANSPORT_TYPE_LABELS,
    TRANSPORT_TYPE_TRAIN,
)
from .coordinator import SilentBusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Silent Bus sensors based on a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    coordinator: SilentBusCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    transport_type = entry.data.get(CONF_TRANSPORT_TYPE, TRANSPORT_TYPE_BUS)

    entities = []

    if transport_type == TRANSPORT_TYPE_TRAIN:
        # Create a single sensor for the train route
        from_station = entry.data[CONF_FROM_STATION]
        to_station = entry.data[CONF_TO_STATION]
        from_station_name = entry.data[CONF_FROM_STATION_NAME]
        to_station_name = entry.data[CONF_TO_STATION_NAME]

        entities = [
            SilentBusTrainSensor(
                coordinator,
                from_station,
                to_station,
                from_station_name,
                to_station_name,
            )
        ]
    else:
        # Create a sensor for each bus/light rail line
        station_id = entry.data[CONF_STATION_ID]
        station_name = entry.data[CONF_STATION_NAME]
        bus_lines = entry.data[CONF_BUS_LINES]

        entities = [
            SilentBusSensor(
                coordinator,
                station_id,
                station_name,
                line_number,
                transport_type,
            )
            for line_number in bus_lines
        ]

    async_add_entities(entities, True)

    _LOGGER.info(
        "Set up %s Silent Bus sensors",
        len(entities),
    )


class SilentBusSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Silent Bus sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SilentBusCoordinator,
        station_id: str,
        station_name: str,
        line_number: str,
        transport_type: str = TRANSPORT_TYPE_BUS,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data update coordinator
            station_id: Station ID
            station_name: Station name
            line_number: Bus/Light Rail line number
            transport_type: Type of transport (bus/light_rail)
        """
        super().__init__(coordinator)

        self._station_id = station_id
        self._station_name = station_name
        self._line_number = line_number
        self._transport_type = transport_type

        # Set icon based on transport type
        self._attr_icon = TRANSPORT_TYPE_ICONS.get(transport_type, "mdi:bus")

        # Set unique ID
        self._attr_unique_id = f"{DOMAIN}_{station_id}_{line_number}"

        # Set device info
        transport_label = TRANSPORT_TYPE_LABELS.get(transport_type, "Bus")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{station_id}")},
            "name": f"{transport_label} Station {station_name}",
            "manufacturer": "Silent Bus",
            "model": f"{transport_label} Stop",
        }

        # Set entity name
        self._attr_name = f"Line {line_number}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor.

        Returns:
            Minutes until next arrival, or None if no data
        """
        next_arrival = self.coordinator.get_next_arrival(self._line_number)

        if next_arrival is None:
            return None

        return next_arrival["minutes_until"]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement.

        Returns:
            Unit string
        """
        return "min"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dictionary of attributes
        """
        next_arrival = self.coordinator.get_next_arrival(self._line_number)
        all_arrivals = self.coordinator.get_line_data(self._line_number)

        attributes = {
            ATTR_LINE_NUMBER: self._line_number,
            ATTR_STATION_ID: self._station_id,
            ATTR_STATION_NAME: self._station_name,
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: datetime.now().isoformat(),
        }

        if next_arrival:
            attributes[ATTR_NEXT_ARRIVAL] = next_arrival["arrival_time"]
            attributes[ATTR_REAL_TIME] = next_arrival["is_realtime"]
            attributes[ATTR_DIRECTION] = next_arrival["direction"]

        if all_arrivals:
            attributes[ATTR_UPCOMING_ARRIVALS] = all_arrivals

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            True if coordinator has data
        """
        # Entity is available if coordinator is available
        return self.coordinator.last_update_success

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity should be enabled by default.

        Returns:
            True to enable by default
        """
        return True


class SilentBusTrainSensor(CoordinatorEntity, SensorEntity):
    """Representation of a train route sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:train"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SilentBusCoordinator,
        from_station: str,
        to_station: str,
        from_station_name: str,
        to_station_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data update coordinator
            from_station: Origin station ID
            to_station: Destination station ID
            from_station_name: Origin station name
            to_station_name: Destination station name
        """
        super().__init__(coordinator)

        self._from_station = from_station
        self._to_station = to_station
        self._from_station_name = from_station_name
        self._to_station_name = to_station_name

        # Set unique ID
        self._attr_unique_id = f"{DOMAIN}_train_{from_station}_{to_station}"

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"train_{from_station}_{to_station}")},
            "name": f"Train Route {from_station_name} → {to_station_name}",
            "manufacturer": "Silent Bus",
            "model": "Train Route",
        }

        # Set entity name
        self._attr_name = "Next Train"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor.

        Returns:
            Minutes until next departure, or None if no data
        """
        next_departure = self.coordinator.get_next_arrival("train_route")

        if next_departure is None:
            return None

        return next_departure["minutes_until"]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement.

        Returns:
            Unit string
        """
        return "min"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dictionary of attributes
        """
        next_departure = self.coordinator.get_next_arrival("train_route")
        all_departures = self.coordinator.get_line_data("train_route")

        attributes = {
            "from_station": self._from_station,
            "to_station": self._to_station,
            "from_station_name": self._from_station_name,
            "to_station_name": self._to_station_name,
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: datetime.now().isoformat(),
        }

        if next_departure:
            attributes[ATTR_NEXT_ARRIVAL] = next_departure["arrival_time"]
            attributes[ATTR_REAL_TIME] = next_departure["is_realtime"]
            attributes[ATTR_DIRECTION] = next_departure["direction"]
            attributes["duration_minutes"] = next_departure.get("duration_minutes")

        if all_departures:
            attributes[ATTR_UPCOMING_ARRIVALS] = all_departures

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            True if coordinator has data
        """
        return self.coordinator.last_update_success

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity should be enabled by default.

        Returns:
            True to enable by default
        """
        return True
