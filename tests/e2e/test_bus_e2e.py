"""End-to-end tests: complete user journey from setup to working sensors.

These tests validate the full lifecycle including recovery from failures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
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

GOV_ARRIVALS_FULL = [
    {
        "Shilut": "249",
        "MinutesToArrival": 5,
        "MinutesToArrivalList": [5, 15, 25],
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
    {
        "Shilut": "605",
        "MinutesToArrival": 12,
        "MinutesToArrivalList": [12, 42],
        "Description": "Tel Aviv - Kfar Saba",
        "CompanyName": "Kavim",
        "BusstopHebrewName": "Arlozorov Terminal",
        "ResponseSuccesed": True,
    },
]


class TestCompleteBusFlow:
    """E2E: config entry → integration loads → coordinator fetches → sensors show data."""

    async def test_complete_bus_setup_flow(self, hass: HomeAssistant):
        """Complete flow: create config → setup → verify coordinator data → verify sensors."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
                CONF_STATION_ID: "24068",
                CONF_STATION_NAME: "Arlozorov Terminal",
                CONF_BUS_LINES: ["249", "40", "605"],
                CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
                CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
            },
        )
        entry.add_to_hass(hass)

        mock_client = MagicMock()
        mock_client.validate_station = AsyncMock(return_value=True)
        mock_client.get_arrivals = AsyncMock(return_value=GOV_ARRIVALS_FULL)

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        # 1. Entry loaded successfully
        assert entry.state == ConfigEntryState.LOADED

        # 2. Coordinator has data
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.data is not None

        # 3. All three lines have data
        assert "249" in coordinator.data
        assert "40" in coordinator.data
        assert "605" in coordinator.data

        # 4. Data matches Gov API response format
        arrival_249 = coordinator.get_next_arrival("249")
        assert arrival_249["minutes_until"] == 5
        assert arrival_249["direction"] == "Tel Aviv - Jerusalem"
        assert arrival_249["operator"] == "Egged"
        assert arrival_249["is_realtime"] is True

        # 5. Multiple arrivals per line
        line_249 = coordinator.get_line_data("249")
        assert len(line_249) == 3  # [5, 15, 25] minutes
        assert line_249[0]["minutes_until"] == 5
        assert line_249[1]["minutes_until"] == 15
        assert line_249[2]["minutes_until"] == 25

        # 6. Gov API was called with correct parameters
        mock_client.validate_station.assert_awaited_once_with("24068")
        mock_client.get_arrivals.assert_awaited_with(
            "24068", lines=["249", "40", "605"]
        )

    async def test_sensor_recovers_after_api_failure(
        self, hass: HomeAssistant
    ):
        """API fails → coordinator retries → eventually succeeds."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
                CONF_STATION_ID: "24068",
                CONF_STATION_NAME: "Arlozorov Terminal",
                CONF_BUS_LINES: ["249"],
                CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
                CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
            },
        )
        entry.add_to_hass(hass)

        # First setup succeeds with good data
        mock_client = MagicMock()
        mock_client.validate_station = AsyncMock(return_value=True)
        mock_client.get_arrivals = AsyncMock(
            return_value=[
                {
                    "Shilut": "249",
                    "MinutesToArrival": 5,
                    "MinutesToArrivalList": [5],
                    "Description": "Tel Aviv",
                    "CompanyName": "Egged",
                },
            ]
        )

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.data is not None
        assert coordinator.get_next_arrival("249")["minutes_until"] == 5

        # Simulate API failure on next update
        mock_client.get_arrivals = AsyncMock(
            side_effect=Exception("API down")
        )

        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Coordinator marks update as failed
        assert coordinator.last_update_success is False

        # Simulate API recovery
        mock_client.get_arrivals = AsyncMock(
            return_value=[
                {
                    "Shilut": "249",
                    "MinutesToArrival": 3,
                    "MinutesToArrivalList": [3],
                    "Description": "Tel Aviv",
                    "CompanyName": "Egged",
                },
            ]
        )

        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Coordinator recovers
        assert coordinator.last_update_success is True
        assert coordinator.get_next_arrival("249")["minutes_until"] == 3
