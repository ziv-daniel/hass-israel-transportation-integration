"""Tests for the Israel Transportation sensor platform."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.israel_transportation.sensor import SilentBusSensor


@pytest.mark.asyncio
async def test_sensor_state_with_arrival(hass: HomeAssistant):
    """Test sensor state with upcoming arrival."""
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


@pytest.mark.asyncio
async def test_sensor_state_no_data(hass: HomeAssistant):
    """Test sensor state with no data."""
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


@pytest.mark.asyncio
async def test_sensor_state_arrived(hass: HomeAssistant):
    """Test sensor state when bus has arrived."""
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


@pytest.mark.asyncio
async def test_sensor_attributes(hass: HomeAssistant):
    """Test sensor attributes."""
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


@pytest.mark.asyncio
async def test_sensor_unique_id(hass: HomeAssistant):
    """Test sensor unique ID."""
    mock_coordinator = MagicMock()

    sensor = SilentBusSensor(
        coordinator=mock_coordinator,
        station_id="24068",
        station_name="Test Station",
        line_number="249",
    )

    assert sensor.unique_id == "israel_transportation_24068_249"


@pytest.mark.asyncio
async def test_sensor_device_info(hass: HomeAssistant):
    """Test sensor device info."""
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


@pytest.mark.asyncio
async def test_sensor_unavailable(hass: HomeAssistant):
    """Test sensor unavailable state."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False

    sensor = SilentBusSensor(
        coordinator=mock_coordinator,
        station_id="24068",
        station_name="Test Station",
        line_number="249",
    )

    assert sensor.available is False
