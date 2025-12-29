"""Fixtures for Israel Transportation tests."""

from __future__ import annotations

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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return


@pytest.fixture
def mock_api_client():
    """Mock BusNearbyApiClient for train tests."""
    with patch("custom_components.israel_transportation.api.BusNearbyApiClient") as mock:
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
                    "Shilut": "249",
                    "MinutesToArrival": 5,
                    "MinutesToArrivalList": [5, 15],
                    "Description": "Tel Aviv - Jerusalem",
                    "CompanyName": "Egged",
                    "BusstopHebrewName": "Arlozorov Terminal",
                    "ResponseSuccesed": True,
                },
                {
                    "Shilut": "40",
                    "MinutesToArrival": 8,
                    "MinutesToArrivalList": [8, 20],
                    "Description": "Tel Aviv - Ramat Gan",
                    "CompanyName": "Dan",
                    "BusstopHebrewName": "Arlozorov Terminal",
                    "ResponseSuccesed": True,
                },
            ]
        )
        client.close = AsyncMock()
        yield client


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
    """Simple mock config entry for coordinator tests."""
    from homeassistant.config_entries import ConfigEntryState

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)
    # Set entry state to SETUP_IN_PROGRESS to allow async_config_entry_first_refresh()
    entry._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, "")
    return entry


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_config_entry, mock_gov_api_client):
    """Set up the Silent Bus integration for bus/light rail."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
