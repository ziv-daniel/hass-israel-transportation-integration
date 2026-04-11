"""Tests for the Israel Transportation sensor platform."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.israel_transportation.sensor import (
    SilentBusSensor,
    SilentBusTrainSensor,
)


# ---------------------------------------------------------------------------
# SilentBusSensor (bus / light rail)
# ---------------------------------------------------------------------------


class TestSilentBusSensor:
    """Tests for SilentBusSensor."""

    async def test_state_with_arrival(self, hass: HomeAssistant):
        """Sensor native_value returns minutes_until from next arrival."""
        mock_coordinator = MagicMock()
        mock_coordinator.get_next_arrival = MagicMock(
            return_value={
                "minutes_until": 5,
                "arrival_time": datetime.now().isoformat(),
                "is_realtime": True,
                "direction": "Tel Aviv",
            }
        )
        mock_coordinator.get_line_data = MagicMock(
            return_value=[
                {
                    "minutes_until": 5,
                    "arrival_time": datetime.now().isoformat(),
                    "is_realtime": True,
                    "direction": "Tel Aviv",
                }
            ]
        )
        mock_coordinator.last_update_success = True

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        assert sensor.native_value == 5
        assert sensor.native_unit_of_measurement == "min"
        assert sensor.available is True

    async def test_state_no_data(self, hass: HomeAssistant):
        """Sensor returns None when no arrival data."""
        mock_coordinator = MagicMock()
        mock_coordinator.get_next_arrival = MagicMock(return_value=None)
        mock_coordinator.get_line_data = MagicMock(return_value=None)
        mock_coordinator.last_update_success = True

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        assert sensor.native_value is None
        assert sensor.native_unit_of_measurement == "min"

    async def test_state_arrived(self, hass: HomeAssistant):
        """Sensor shows 0 when bus has arrived."""
        mock_coordinator = MagicMock()
        mock_coordinator.get_next_arrival = MagicMock(
            return_value={
                "minutes_until": 0,
                "arrival_time": datetime.now().isoformat(),
                "is_realtime": True,
                "direction": "Tel Aviv",
            }
        )
        mock_coordinator.last_update_success = True

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        assert sensor.native_value == 0

    async def test_attributes(self, hass: HomeAssistant):
        """Extra state attributes contain expected keys."""
        mock_coordinator = MagicMock()
        arrival_time = datetime.now()
        mock_coordinator.get_next_arrival = MagicMock(
            return_value={
                "minutes_until": 5,
                "arrival_time": arrival_time.isoformat(),
                "is_realtime": True,
                "direction": "Tel Aviv",
            }
        )
        mock_coordinator.get_line_data = MagicMock(
            return_value=[
                {
                    "minutes_until": 5,
                    "arrival_time": arrival_time.isoformat(),
                    "is_realtime": True,
                    "direction": "Tel Aviv",
                }
            ]
        )
        mock_coordinator.last_update_success = True

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        attributes = sensor.extra_state_attributes

        assert attributes["line_number"] == "249"
        assert attributes["station_id"] == "24068"
        assert attributes["station_name"] == "Test Station"
        assert attributes["next_arrival"] == arrival_time.isoformat()
        assert attributes["real_time"] is True
        assert attributes["direction"] == "Tel Aviv"
        assert "upcoming_arrivals" in attributes

    async def test_unique_id(self, hass: HomeAssistant):
        """Unique ID follows domain_stationid_linenumber pattern."""
        mock_coordinator = MagicMock()

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        assert sensor.unique_id == "israel_transportation_24068_249"

    async def test_device_info(self, hass: HomeAssistant):
        """Device info identifies the station."""
        mock_coordinator = MagicMock()

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        device_info = sensor.device_info

        assert device_info["name"] == "Bus Station Test Station"
        assert ("israel_transportation", "24068") in device_info["identifiers"]

    async def test_unavailable(self, hass: HomeAssistant):
        """Sensor reports unavailable when coordinator update fails."""
        mock_coordinator = MagicMock()
        mock_coordinator.last_update_success = False

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Test Station",
            line_number="249",
        )

        assert sensor.available is False

    async def test_with_gov_arrival_format(self, hass: HomeAssistant):
        """Sensor works with Gov API arrival format (includes 'operator' key)."""
        mock_coordinator = MagicMock()
        gov_arrival = {
            "minutes_until": 5,
            "arrival_time": datetime.now().isoformat(),
            "is_realtime": True,
            "direction": "Tel Aviv - Jerusalem",
            "operator": "Egged",
        }
        mock_coordinator.get_next_arrival = MagicMock(return_value=gov_arrival)
        mock_coordinator.get_line_data = MagicMock(return_value=[gov_arrival])
        mock_coordinator.last_update_success = True

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="24068",
            station_name="Arlozorov Terminal",
            line_number="249",
        )

        assert sensor.native_value == 5
        attrs = sensor.extra_state_attributes
        assert attrs["direction"] == "Tel Aviv - Jerusalem"
        assert attrs["real_time"] is True

    async def test_light_rail_transport_type(self, hass: HomeAssistant):
        """Sensor uses tram icon for light rail transport type."""
        mock_coordinator = MagicMock()

        sensor = SilentBusSensor(
            coordinator=mock_coordinator,
            station_id="50000",
            station_name="Light Rail Station",
            line_number="1",
            transport_type="light_rail",
        )

        assert sensor.icon == "mdi:tram"


# ---------------------------------------------------------------------------
# SilentBusTrainSensor
# ---------------------------------------------------------------------------


class TestSilentBusTrainSensor:
    """Tests for the train route sensor."""

    async def test_train_sensor_state(self, hass: HomeAssistant):
        """Train sensor returns minutes_until from 'train_route' key."""
        mock_coordinator = MagicMock()
        mock_coordinator.get_next_arrival = MagicMock(
            return_value={
                "minutes_until": 12,
                "arrival_time": datetime.now().isoformat(),
                "is_realtime": False,
                "direction": "Tel Aviv Savidor",
                "duration_minutes": 45,
                "platform": "3",
                "train_number": "1234",
            }
        )
        mock_coordinator.get_line_data = MagicMock(return_value=None)
        mock_coordinator.last_update_success = True

        sensor = SilentBusTrainSensor(
            coordinator=mock_coordinator,
            from_station="9600",
            to_station="3700",
            from_station_name="Sderot",
            to_station_name="Tel Aviv Savidor",
        )

        assert sensor.native_value == 12
        assert sensor.native_unit_of_measurement == "min"
        assert sensor.icon == "mdi:train"

    async def test_train_sensor_no_data(self, hass: HomeAssistant):
        """Train sensor returns None when no route data."""
        mock_coordinator = MagicMock()
        mock_coordinator.get_next_arrival = MagicMock(return_value=None)
        mock_coordinator.get_line_data = MagicMock(return_value=None)
        mock_coordinator.last_update_success = True

        sensor = SilentBusTrainSensor(
            coordinator=mock_coordinator,
            from_station="9600",
            to_station="3700",
            from_station_name="Sderot",
            to_station_name="Tel Aviv Savidor",
        )

        assert sensor.native_value is None

    async def test_train_sensor_unique_id(self, hass: HomeAssistant):
        """Train sensor unique ID uses from/to station IDs."""
        mock_coordinator = MagicMock()

        sensor = SilentBusTrainSensor(
            coordinator=mock_coordinator,
            from_station="9600",
            to_station="3700",
            from_station_name="Sderot",
            to_station_name="Tel Aviv Savidor",
        )

        assert sensor.unique_id == "israel_transportation_train_9600_3700"

    async def test_train_sensor_attributes(self, hass: HomeAssistant):
        """Train sensor attributes include from/to station info."""
        mock_coordinator = MagicMock()
        arrival_time = datetime.now()
        mock_coordinator.get_next_arrival = MagicMock(
            return_value={
                "minutes_until": 12,
                "arrival_time": arrival_time.isoformat(),
                "is_realtime": False,
                "direction": "Tel Aviv Savidor",
                "duration_minutes": 45,
            }
        )
        mock_coordinator.get_line_data = MagicMock(
            return_value=[
                {
                    "minutes_until": 12,
                    "arrival_time": arrival_time.isoformat(),
                    "is_realtime": False,
                    "direction": "Tel Aviv Savidor",
                    "duration_minutes": 45,
                }
            ]
        )
        mock_coordinator.last_update_success = True

        sensor = SilentBusTrainSensor(
            coordinator=mock_coordinator,
            from_station="9600",
            to_station="3700",
            from_station_name="Sderot",
            to_station_name="Tel Aviv Savidor",
        )

        attrs = sensor.extra_state_attributes

        assert attrs["from_station"] == "9600"
        assert attrs["to_station"] == "3700"
        assert attrs["from_station_name"] == "Sderot"
        assert attrs["to_station_name"] == "Tel Aviv Savidor"
        assert attrs["next_arrival"] == arrival_time.isoformat()
        assert attrs["duration_minutes"] == 45
        assert "upcoming_arrivals" in attrs

    async def test_train_sensor_device_info(self, hass: HomeAssistant):
        """Train sensor device info identifies the route."""
        mock_coordinator = MagicMock()

        sensor = SilentBusTrainSensor(
            coordinator=mock_coordinator,
            from_station="9600",
            to_station="3700",
            from_station_name="Sderot",
            to_station_name="Tel Aviv Savidor",
        )

        device_info = sensor.device_info
        assert "Train Route" in device_info["name"]
        assert (
            "israel_transportation",
            "train_9600_3700",
        ) in device_info["identifiers"]

    async def test_train_sensor_unavailable(self, hass: HomeAssistant):
        """Train sensor reports unavailable when update fails."""
        mock_coordinator = MagicMock()
        mock_coordinator.last_update_success = False

        sensor = SilentBusTrainSensor(
            coordinator=mock_coordinator,
            from_station="9600",
            to_station="3700",
            from_station_name="Sderot",
            to_station_name="Tel Aviv Savidor",
        )

        assert sensor.available is False
