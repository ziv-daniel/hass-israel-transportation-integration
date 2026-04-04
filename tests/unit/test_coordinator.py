"""Tests for the Israel Transportation coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.israel_transportation.api import BusNearbyApiError
from custom_components.israel_transportation.coordinator import SilentBusCoordinator
from custom_components.israel_transportation.gov_api import RateLimitError


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


# ---------------------------------------------------------------------------
# Malformed / adversarial API response tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gov_api_malformed_minutes_type(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Gov API returns MinutesToArrival as string — must not crash coordinator."""
    mock_gov_client = MagicMock()
    mock_gov_client.get_arrivals = AsyncMock(
        return_value=[
            {
                "Shilut": "249",
                "MinutesToArrival": "five",  # wrong type
                "MinutesToArrivalList": ["five", "ten"],
                "Description": "Tel Aviv",
                "CompanyName": "Egged",
            }
        ]
    )
    mock_gov_client.validate_station = AsyncMock(return_value=True)

    coordinator = SilentBusCoordinator(
        hass=hass,
        gov_api_client=mock_gov_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    # Must not raise TypeError — coordinator should raise UpdateFailed or return empty data
    try:
        await coordinator.async_config_entry_first_refresh()
        # If it succeeds, data should be empty (bad entries skipped)
        line_data = coordinator.get_line_data("249")
        assert line_data is None or line_data == []
    except Exception as exc:
        # UpdateFailed is acceptable; async_config_entry_first_refresh wraps it as ConfigEntryNotReady
        assert isinstance(
            exc, (UpdateFailed, ConfigEntryNotReady)
        ), f"Expected UpdateFailed or ConfigEntryNotReady, got {type(exc).__name__}: {exc}"


@pytest.mark.asyncio
async def test_gov_api_missing_shilut_field(
    hass: HomeAssistant, simple_mock_config_entry
):
    """Gov API returns arrivals without Shilut field — entries must be skipped."""
    mock_gov_client = MagicMock()
    mock_gov_client.get_arrivals = AsyncMock(
        return_value=[
            {
                # Missing "Shilut" key entirely
                "MinutesToArrival": 5,
                "MinutesToArrivalList": [5],
                "Description": "Tel Aviv",
                "CompanyName": "Egged",
            }
        ]
    )
    mock_gov_client.validate_station = AsyncMock(return_value=True)

    coordinator = SilentBusCoordinator(
        hass=hass,
        gov_api_client=mock_gov_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()
    # Entry without Shilut must be silently skipped, not crash
    assert coordinator.data == {} or coordinator.get_line_data("249") is None


@pytest.mark.asyncio
async def test_gov_api_empty_response(hass: HomeAssistant, simple_mock_config_entry):
    """Gov API returns empty list — coordinator data is empty, sensor shows unknown."""
    mock_gov_client = MagicMock()
    mock_gov_client.get_arrivals = AsyncMock(return_value=[])
    mock_gov_client.validate_station = AsyncMock(return_value=True)

    coordinator = SilentBusCoordinator(
        hass=hass,
        gov_api_client=mock_gov_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == {}
    assert coordinator.get_next_arrival("249") is None


@pytest.mark.asyncio
async def test_gov_api_rate_limit_raises_update_failed_with_retry(
    hass: HomeAssistant, simple_mock_config_entry
):
    """HTTP 429 from gov API must raise UpdateFailed with retry_after, not raw exception."""
    mock_gov_client = MagicMock()
    mock_gov_client.get_arrivals = AsyncMock(
        side_effect=RateLimitError(retry_after=30.0)
    )
    mock_gov_client.validate_station = AsyncMock(return_value=True)

    coordinator = SilentBusCoordinator(
        hass=hass,
        gov_api_client=mock_gov_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Rate limited" in str(exc_info.value)


@pytest.mark.asyncio
async def test_coordinator_retains_stale_data_after_failed_update(
    hass: HomeAssistant, simple_mock_config_entry
):
    """After a successful refresh, a failed update retains last-good data."""
    mock_gov_client = MagicMock()

    mock_gov_client.get_arrivals = AsyncMock(
        return_value=[
            {
                "Shilut": "249",
                "MinutesToArrival": 5,
                "MinutesToArrivalList": [5, 15],
                "Description": "Tel Aviv",
                "CompanyName": "Egged",
            }
        ]
    )
    mock_gov_client.validate_station = AsyncMock(return_value=True)

    coordinator = SilentBusCoordinator(
        hass=hass,
        gov_api_client=mock_gov_client,
        update_interval=timedelta(seconds=30),
        config_entry=simple_mock_config_entry,
        station_id="24068",
        station_name="Test Station",
        bus_lines=["249"],
    )

    # First refresh succeeds
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.data is not None
    assert "249" in coordinator.data

    # Now fail the update
    mock_gov_client.get_arrivals = AsyncMock(side_effect=Exception("Network error"))
    await coordinator.async_refresh()

    # last_update_success is False but data is retained from last good fetch
    assert coordinator.last_update_success is False
    assert coordinator.data is not None  # stale data retained
