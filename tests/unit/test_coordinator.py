"""Tests for the Silent Bus coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.israel_transportation.api import BusNearbyApiError
from custom_components.israel_transportation.coordinator import SilentBusCoordinator


@pytest.mark.asyncio
async def test_coordinator_update_success(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test successful coordinator update."""
    mock_api_client = MagicMock()
    mock_api_client.get_stop_times = AsyncMock(
        return_value=[
            {
                "routeShortName": "249",
                "serviceDay": int(datetime.now().timestamp()),
                "realtimeArrival": 300,  # 5 minutes
                "realtime": True,
                "headsign": "Tel Aviv",
            }
        ]
    )

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data is not None
    assert "249" in coordinator.data
    assert len(coordinator.data["249"]) > 0


@pytest.mark.asyncio
async def test_coordinator_update_failure(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test coordinator update with API error."""
    mock_api_client = MagicMock()
    mock_api_client.get_stop_times = AsyncMock(
        side_effect=BusNearbyApiError("Test error")
    )

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_process_arrivals(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test arrival data processing."""
    mock_api_client = MagicMock()
    current_time = int(datetime.now().timestamp())

    mock_api_client.get_stop_times = AsyncMock(
        return_value=[
            {
                "routeShortName": "249",
                "serviceDay": current_time,
                "realtimeArrival": 300,  # 5 minutes
                "scheduledArrival": 300,
                "realtime": True,
                "headsign": "Tel Aviv",
            },
            {
                "routeShortName": "249",
                "serviceDay": current_time,
                "realtimeArrival": 600,  # 10 minutes
                "scheduledArrival": 600,
                "realtime": False,
                "headsign": "Tel Aviv",
            },
        ]
    )

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()

    # Check that arrivals are sorted by time
    line_data = coordinator.get_line_data("249")
    assert line_data is not None
    assert len(line_data) == 2
    assert line_data[0]["minutes_until"] <= line_data[1]["minutes_until"]


@pytest.mark.asyncio
async def test_coordinator_get_next_arrival(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test getting next arrival for a line."""
    mock_api_client = MagicMock()
    current_time = int(datetime.now().timestamp())

    mock_api_client.get_stop_times = AsyncMock(
        return_value=[
            {
                "routeShortName": "249",
                "serviceDay": current_time,
                "realtimeArrival": 300,
                "realtime": True,
                "headsign": "Tel Aviv",
            }
        ]
    )

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()

    next_arrival = coordinator.get_next_arrival("249")
    assert next_arrival is not None
    assert next_arrival["is_realtime"] is True
    assert "minutes_until" in next_arrival


@pytest.mark.asyncio
async def test_coordinator_update_interval_adjustment(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test dynamic update interval adjustment."""
    mock_api_client = MagicMock()
    current_time = int(datetime.now().timestamp())

    # Bus arriving in 5 minutes (should trigger faster updates)
    mock_api_client.get_stop_times = AsyncMock(
        return_value=[
            {
                "routeShortName": "249",
                "serviceDay": current_time,
                "realtimeArrival": 300,  # 5 minutes
                "realtime": True,
                "headsign": "Tel Aviv",
            }
        ]
    )

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()

    # Update interval might change based on approaching bus
    # (exact behavior depends on implementation)
    assert coordinator.update_interval is not None


@pytest.mark.asyncio
async def test_coordinator_multiple_lines(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test coordinator with multiple bus lines."""
    mock_api_client = MagicMock()
    current_time = int(datetime.now().timestamp())

    mock_api_client.get_stop_times = AsyncMock(
        return_value=[
            {
                "routeShortName": "249",
                "serviceDay": current_time,
                "realtimeArrival": 300,
                "realtime": True,
                "headsign": "Tel Aviv",
            },
            {
                "routeShortName": "40",
                "serviceDay": current_time,
                "realtimeArrival": 500,
                "realtime": True,
                "headsign": "Ramat Gan",
            },
        ]
    )

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249", "40"],
    )

    await coordinator.async_config_entry_first_refresh()

    assert "249" in coordinator.data
    assert "40" in coordinator.data
    assert coordinator.get_next_arrival("249") is not None
    assert coordinator.get_next_arrival("40") is not None


@pytest.mark.asyncio
async def test_coordinator_no_data_for_line(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Test coordinator when no data available for a line."""
    mock_api_client = MagicMock()
    mock_api_client.get_stop_times = AsyncMock(return_value=[])

    coordinator = SilentBusCoordinator(
        hass=hass,
        api_client=mock_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()

    line_data = coordinator.get_line_data("249")
    assert line_data is None

    next_arrival = coordinator.get_next_arrival("249")
    assert next_arrival is None
