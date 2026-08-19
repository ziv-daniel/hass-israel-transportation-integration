"""Fixtures for Israel Transportation tests."""

from __future__ import annotations

import socket as socket_module
import sys
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.israel_transportation.const import (
    CONF_BUS_LINES,
    CONF_MAX_ARRIVALS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TRANSPORT_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MAX_ARRIVALS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TRANSPORT_TYPE_BUS,
)

pytest_plugins = "pytest_homeassistant_custom_component"

# ---------------------------------------------------------------------------
# Windows socket workaround
# ---------------------------------------------------------------------------
# On Windows, asyncio event loops need socket.socketpair() for internal
# self-pipe communication. pytest-socket blocks socket.socket() but only
# allows Unix sockets (which don't exist on Windows). Fix: save the
# original socketpair (which uses the real socket internally) and replace
# the module-level function so it always works regardless of socket guard.
if sys.platform == "win32":
    _real_socket_class = socket_module.socket
    _original_socketpair = socket_module.socketpair

    def _unguarded_socketpair(
        family=socket_module.AF_INET, type=socket_module.SOCK_STREAM, proto=0
    ):
        """Create a socket pair bypassing pytest-socket guard."""
        saved = socket_module.socket
        try:
            socket_module.socket = _real_socket_class
            return _original_socketpair(family, type, proto)
        finally:
            socket_module.socket = saved

    socket_module.socketpair = _unguarded_socketpair


# ---------------------------------------------------------------------------
# Standard autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return


@pytest.fixture(autouse=True)
def mock_gtfs_functions():
    """Stop the direction fallback from reading GTFS files off disk in tests."""
    with patch(
        "custom_components.israel_transportation.coordinator.get_route_headsign",
        return_value=None,
    ):
        yield


# ---------------------------------------------------------------------------
# Mock API clients
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_api_client():
    """Mock BusNearbyApiClient for train tests."""
    with patch(
        "custom_components.israel_transportation.api.BusNearbyApiClient"
    ) as mock:
        client = mock.return_value
        client.validate_station = AsyncMock(return_value=True)
        client.search_station = AsyncMock(
            return_value=[
                {
                    "stop_id": "24068",
                    "name": "Arlozorov Terminal",
                    "city": "Tel Aviv",
                    "lat": 32.0853,
                    "lon": 34.7818,
                }
            ]
        )
        client.get_stop_times = AsyncMock(
            return_value=[
                {
                    "routeShortName": "249",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 1000,
                    "scheduledArrival": 1000,
                    "realtime": True,
                    "headsign": "Tel Aviv - Jerusalem",
                },
                {
                    "routeShortName": "40",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 2000,
                    "scheduledArrival": 2000,
                    "realtime": True,
                    "headsign": "Tel Aviv - Ramat Gan",
                },
            ]
        )
        client.close = AsyncMock()
        yield client


@pytest.fixture
def mock_gov_api_client():
    """Mock GovApiClient for bus/light rail tests."""
    with patch("custom_components.israel_transportation.gov_api.GovApiClient") as mock:
        client = mock.return_value
        client.validate_station = AsyncMock(return_value=True)
        client.get_station = AsyncMock(
            return_value={
                "Name": "Arlozorov Terminal",
                "Makat": 24068,
                "Latitude": 32.0853,
                "Longitude": 34.7818,
            }
        )
        client.get_arrivals = AsyncMock(
            return_value=[
                {
                    "line": "249",
                    "direction": "Tel Aviv - Jerusalem",
                    "operator": "Egged",
                    "route_desc": "10249-1-0",
                    "arrivals": [
                        {"minutes_until": 5, "is_realtime": True},
                        {"minutes_until": 15, "is_realtime": False},
                    ],
                },
                {
                    "line": "40",
                    "direction": "Tel Aviv - Ramat Gan",
                    "operator": "Dan",
                    "route_desc": "10040-1-0",
                    "arrivals": [
                        {"minutes_until": 8, "is_realtime": False},
                        {"minutes_until": 20, "is_realtime": False},
                    ],
                },
            ]
        )
        client.close = AsyncMock()
        yield client


# ---------------------------------------------------------------------------
# Mock config entries
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry():
    """Mock config entry for bus transport."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Arlozorov Terminal",
            CONF_BUS_LINES: ["249", "40", "605"],
            CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
            CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
        },
        options={},
    )


@pytest.fixture
def simple_mock_config_entry(hass):
    """Simple mock config entry for coordinator tests.

    Includes full bus config data so coordinator construction succeeds.
    Uses async_refresh() (not async_config_entry_first_refresh) so no
    special entry state is needed.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Arlozorov Terminal",
            CONF_BUS_LINES: ["249", "40"],
            CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
            CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
        },
    )
    entry.add_to_hass(hass)
    return entry


# ---------------------------------------------------------------------------
# Integration setup helper
# ---------------------------------------------------------------------------


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_config_entry, mock_gov_api_client
):
    """Set up the Israel Transportation integration for bus/light rail."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
