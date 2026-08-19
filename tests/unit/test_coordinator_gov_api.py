"""Tests for SilentBusCoordinator with Gov API (production bus/light rail path).

These tests validate the PRODUCTION code path: bus.gov.il Gov API →
_process_gov_arrivals() → sensor data. The existing test_coordinator.py
tests the legacy BusNearby path (api_client=), which is only used for
trains now.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.israel_transportation.const import (
    DEFAULT_MAX_ARRIVALS,
    MIN_SCAN_INTERVAL,
)
from custom_components.israel_transportation.coordinator import (
    SilentBusCoordinator,
)

# ---------------------------------------------------------------------------
# Mock data matching the normalized shape GovApiClient.get_arrivals returns
# ---------------------------------------------------------------------------


def _times(*pairs):
    """Build an arrivals list from (minutes, is_realtime) pairs."""
    return [
        {"minutes_until": minutes, "is_realtime": realtime}
        for minutes, realtime in pairs
    ]


GOV_ARRIVALS_STANDARD = [
    {
        "line": "249",
        "direction": "Tel Aviv - Jerusalem",
        "operator": "Egged",
        "route_desc": "10249-1-0",
        "arrivals": _times((5, True), (15, False), (25, False)),
    },
    {
        "line": "40",
        "direction": "Tel Aviv - Ramat Gan",
        "operator": "Dan",
        "route_desc": "10040-1-0",
        "arrivals": _times((8, False), (20, False)),
    },
]

GOV_ARRIVALS_SINGLE = [
    {
        "line": "5",
        "direction": "Sderot - Train Station",
        "operator": "Dan BaDarom",
        "route_desc": "96005-1-#",
        "arrivals": _times((8, False)),
    },
]

GOV_ARRIVALS_BAD_LINE = [
    {
        "line": "",
        "direction": "Should be skipped",
        "operator": "",
        "arrivals": _times((3, False)),
    },
]

GOV_ARRIVALS_NO_DIRECTION = [
    {
        "line": "7",
        "direction": "",
        "operator": "Kavim",
        "route_desc": "10007-1-0",
        "arrivals": _times((10, False)),
    },
]

GOV_ARRIVALS_MANY = [
    {
        "line": "100",
        "direction": "Long Route",
        "operator": "Egged",
        "route_desc": "10100-1-0",
        "arrivals": _times(
            (2, False), (12, False), (22, False), (32, False), (42, False)
        ),
    },
]

GOV_ARRIVALS_UNSORTED = [
    {
        "line": "50",
        "direction": "Test Route",
        "operator": "Dan",
        "route_desc": "10050-1-0",
        "arrivals": _times((20, False), (5, False), (35, False), (10, False)),
    },
]


# ---------------------------------------------------------------------------
# Helper to create a coordinator with Gov API client
# ---------------------------------------------------------------------------


def _make_gov_coordinator(
    hass: HomeAssistant,
    config_entry,
    gov_api_client: MagicMock,
    bus_lines: list[str] | None = None,
    max_arrivals: int = DEFAULT_MAX_ARRIVALS,
) -> SilentBusCoordinator:
    """Create a SilentBusCoordinator configured for Gov API."""
    return SilentBusCoordinator(
        hass=hass,
        gov_api_client=gov_api_client,
        update_interval=timedelta(seconds=30),
        config_entry=config_entry,
        station_id="24068",
        station_name="Arlozorov Terminal",
        bus_lines=bus_lines or ["249", "40"],
        max_arrivals=max_arrivals,
    )


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestGovCoordinatorInit:
    """Test coordinator initialization with Gov API client."""

    async def test_gov_coordinator_init(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Constructor stores gov_api_client and leaves api_client as None."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        assert coordinator.gov_api_client is mock_gov
        assert coordinator.api_client is None
        assert coordinator.station_id == "24068"
        assert coordinator.bus_lines == ["249", "40"]

    async def test_gov_coordinator_name(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Coordinator name is based on domain + station_id."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        assert coordinator.name == "israel_transportation_24068"


# ---------------------------------------------------------------------------
# _process_gov_arrivals tests (pure logic, no async needed)
# ---------------------------------------------------------------------------


class TestProcessGovArrivals:
    """Test _process_gov_arrivals processing logic."""

    async def test_basic_processing(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Standard gov response → correct line grouping and arrival count."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_STANDARD)

        assert "249" in result
        assert "40" in result
        assert len(result["249"]) == 3  # MinutesToArrivalList has 3 entries
        assert len(result["40"]) == 2

    async def test_arrival_fields(self, hass: HomeAssistant, simple_mock_config_entry):
        """Each arrival dict has the expected keys and values."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_STANDARD)

        first_arrival = result["249"][0]
        assert first_arrival["minutes_until"] == 5
        assert first_arrival["direction"] == "Tel Aviv - Jerusalem"
        assert first_arrival["operator"] == "Egged"
        assert first_arrival["is_realtime"] is True
        assert "arrival_time" in first_arrival

    async def test_single_minute_fallback(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """When MinutesToArrivalList is missing, falls back to MinutesToArrival."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(
            hass, simple_mock_config_entry, mock_gov, bus_lines=["5"]
        )

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_SINGLE)

        assert "5" in result
        assert len(result["5"]) == 1
        assert result["5"][0]["minutes_until"] == 8

    async def test_empty_shilut_skipped(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Entries with empty Shilut are skipped."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_BAD_LINE)

        assert result == {}

    async def test_direction_fallback_to_line_number(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Empty Description + GTFS returns None → falls back to 'Line X'."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(
            hass, simple_mock_config_entry, mock_gov, bus_lines=["7"]
        )

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_NO_DIRECTION)

        assert "7" in result
        assert result["7"][0]["direction"] == "Line 7"

    async def test_max_arrivals_limits_output(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Output is capped at max_arrivals per line."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(
            hass,
            simple_mock_config_entry,
            mock_gov,
            bus_lines=["100"],
            max_arrivals=3,
        )

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_MANY)

        assert len(result["100"]) == 3

    async def test_sorts_by_minutes(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Arrivals are sorted ascending by minutes_until."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(
            hass, simple_mock_config_entry, mock_gov, bus_lines=["50"]
        )

        result = coordinator._process_gov_arrivals(GOV_ARRIVALS_UNSORTED)

        minutes = [a["minutes_until"] for a in result["50"]]
        assert minutes == sorted(minutes)
        assert minutes[0] == 5

    async def test_empty_response(self, hass: HomeAssistant, simple_mock_config_entry):
        """Empty API response produces empty dict."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        result = coordinator._process_gov_arrivals([])

        assert result == {}

    async def test_no_minutes_at_all(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """A route present at the stop but with no upcoming times → empty list for line."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        arrivals = [{"line": "99", "direction": "Ghost bus", "arrivals": []}]
        result = coordinator._process_gov_arrivals(arrivals)

        # Line exists in result but has no arrivals (empty minutes_list)
        assert result == {"99": []}


# ---------------------------------------------------------------------------
# _fetch_gov_arrivals / _async_update_data integration
# ---------------------------------------------------------------------------


class TestGovUpdateData:
    """Test full update cycle using Gov API."""

    async def test_update_data_success(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Successful update fetches gov API and returns processed data."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(return_value=GOV_ARRIVALS_STANDARD)

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        await coordinator.async_refresh()

        assert coordinator.data is not None
        assert "249" in coordinator.data
        assert "40" in coordinator.data
        assert len(coordinator.data["249"]) == 3

        mock_gov.get_arrivals.assert_awaited_once_with("24068", lines=["249", "40"])

    async def test_update_empty_response(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Empty gov API response → coordinator.data is empty dict."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(return_value=[])

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        await coordinator.async_refresh()

        assert coordinator.data == {}

    async def test_update_api_error(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Gov API raising exception → UpdateFailed."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(side_effect=Exception("Connection refused"))

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_fetch_gov_no_client_raises(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """_fetch_gov_arrivals raises UpdateFailed when gov_api_client is None."""
        coordinator = SilentBusCoordinator(
            hass=hass,
            gov_api_client=None,
            update_interval=timedelta(seconds=30),
            config_entry=simple_mock_config_entry,
            station_id="24068",
            station_name="Test",
            bus_lines=["1"],
        )
        # Force the gov path by setting gov_api_client back to None after init
        coordinator.gov_api_client = None

        with pytest.raises(UpdateFailed, match="Gov API client not initialized"):
            await coordinator._fetch_gov_arrivals()


# ---------------------------------------------------------------------------
# get_next_arrival / get_line_data after Gov API update
# ---------------------------------------------------------------------------


class TestGovDataAccess:
    """Test data access methods after a Gov API update."""

    async def test_get_next_arrival(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """get_next_arrival returns the first (soonest) arrival."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(return_value=GOV_ARRIVALS_STANDARD)

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        await coordinator.async_refresh()

        next_249 = coordinator.get_next_arrival("249")
        assert next_249 is not None
        assert next_249["minutes_until"] == 5
        assert next_249["direction"] == "Tel Aviv - Jerusalem"
        assert next_249["operator"] == "Egged"

    async def test_get_line_data(self, hass: HomeAssistant, simple_mock_config_entry):
        """get_line_data returns sorted list of all arrivals for a line."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(return_value=GOV_ARRIVALS_STANDARD)

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        await coordinator.async_refresh()

        line_data = coordinator.get_line_data("249")
        assert line_data is not None
        assert len(line_data) == 3
        assert line_data[0]["minutes_until"] <= line_data[1]["minutes_until"]

    async def test_get_next_arrival_missing_line(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """get_next_arrival for a line not in data returns None."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(return_value=GOV_ARRIVALS_STANDARD)

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        await coordinator.async_refresh()

        assert coordinator.get_next_arrival("999") is None

    async def test_get_line_data_no_data(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """get_line_data returns None when coordinator has no data."""
        mock_gov = MagicMock()
        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        # Don't refresh - data is None
        assert coordinator.get_line_data("249") is None


# ---------------------------------------------------------------------------
# Interval adjustment tests with Gov API data
# ---------------------------------------------------------------------------


class TestGovIntervalAdjustment:
    """Test _adjust_update_interval with Gov API data."""

    async def test_interval_approaching_bus(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Bus arriving in <10 minutes → MIN_SCAN_INTERVAL (15s)."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(
            return_value=[
                {
                    "line": "249",
                    "direction": "Test",
                    "operator": "Test",
                    "route_desc": "10249-1-0",
                    "arrivals": [{"minutes_until": 5, "is_realtime": True}],
                },
            ]
        )

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        await coordinator.async_refresh()

        assert coordinator.update_interval == MIN_SCAN_INTERVAL

    async def test_interval_no_data(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """No upcoming buses → 5 minute interval."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(return_value=[])

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        await coordinator.async_refresh()

        assert coordinator.update_interval == timedelta(minutes=5)

    async def test_interval_far_away_bus(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Bus arriving in >60 minutes → 2min (day) or 5min (night)."""
        mock_gov = MagicMock()
        mock_gov.get_arrivals = AsyncMock(
            return_value=[
                {
                    "Shilut": "249",
                    "MinutesToArrival": 90,
                    "MinutesToArrivalList": [90],
                    "Description": "Test",
                    "CompanyName": "Test",
                },
            ]
        )

        coordinator = _make_gov_coordinator(hass, simple_mock_config_entry, mock_gov)
        await coordinator.async_refresh()

        # Either 2min (day) or 5min (night) depending on test execution time
        assert coordinator.update_interval in (
            timedelta(minutes=2),
            timedelta(minutes=5),
        )
