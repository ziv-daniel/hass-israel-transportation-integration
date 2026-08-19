"""Integration tests validating the full data flow.

Config entry → async_setup_entry → coordinator fetches Gov API → sensor state.

These are the most critical integration tests - they prove the production
path works end-to-end within Home Assistant's framework.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.israel_transportation.const import (
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

# ---------------------------------------------------------------------------
# Mock Gov API responses
# ---------------------------------------------------------------------------

GOV_ARRIVALS_TWO_LINES = [
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


def _make_bus_config_entry(
    bus_lines: list[str] | None = None,
) -> MockConfigEntry:
    """Create a bus config entry with realistic data."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Arlozorov Terminal",
            CONF_BUS_LINES: bus_lines or ["249", "40"],
            CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
            CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
        },
    )


def _make_gov_client_mock(arrivals=None) -> MagicMock:
    """Create a mock GovApiClient."""
    client = MagicMock()
    client.validate_station = AsyncMock(return_value=True)
    client.get_arrivals = AsyncMock(
        return_value=arrivals if arrivals is not None else GOV_ARRIVALS_TWO_LINES
    )
    client.get_station = AsyncMock(
        return_value={"Name": "Arlozorov Terminal", "Makat": 24068}
    )
    return client


# ---------------------------------------------------------------------------
# Bus data flow tests
# ---------------------------------------------------------------------------


class TestBusDataFlow:
    """Test bus: config entry → coordinator → sensor state."""

    async def test_bus_setup_to_sensor_state(self, hass: HomeAssistant):
        """Full flow: setup entry → coordinator fetches gov API → sensor shows minutes."""
        entry = _make_bus_config_entry()
        entry.add_to_hass(hass)
        mock_client = _make_gov_client_mock()

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

        # Verify coordinator has data from Gov API
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.data is not None
        assert "249" in coordinator.data
        assert coordinator.data["249"][0]["minutes_until"] == 5

    async def test_bus_sensor_attributes(self, hass: HomeAssistant):
        """Sensor attributes include direction, real_time, upcoming_arrivals."""
        entry = _make_bus_config_entry()
        entry.add_to_hass(hass)
        mock_client = _make_gov_client_mock()

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        # Verify arrival data has expected Gov API format fields
        arrival = coordinator.get_next_arrival("249")
        assert arrival is not None
        assert arrival["direction"] == "Tel Aviv - Jerusalem"
        assert arrival["is_realtime"] is True
        assert arrival["operator"] == "Egged"
        assert "arrival_time" in arrival

    async def test_bus_multiple_lines_create_data(self, hass: HomeAssistant):
        """Three configured lines → coordinator has data for lines present in API."""
        entry = _make_bus_config_entry(bus_lines=["249", "40", "605"])
        entry.add_to_hass(hass)
        mock_client = _make_gov_client_mock()

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        # API returns data for 249 and 40 (not 605)
        assert "249" in coordinator.data
        assert "40" in coordinator.data
        # 605 not in API response → not in data
        assert coordinator.get_next_arrival("605") is None

    async def test_bus_api_returns_empty(self, hass: HomeAssistant):
        """Gov API returns [] → coordinator data is empty, sensors have None state."""
        entry = _make_bus_config_entry()
        entry.add_to_hass(hass)
        mock_client = _make_gov_client_mock(arrivals=[])

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.data == {}
        assert coordinator.get_next_arrival("249") is None

    async def test_bus_api_error_still_loads_entry(self, hass: HomeAssistant):
        """An API outage must degrade to unavailable entities, not kill the entry.

        Regression test: the integration used to raise ConfigEntryNotReady when the
        first fetch failed, which left every configured station in setup_retry with
        no entities at all whenever the upstream API had a bad day.
        """
        entry = _make_bus_config_entry()
        entry.add_to_hass(hass)

        mock_client = MagicMock()
        mock_client.validate_station = AsyncMock(return_value=True)
        mock_client.get_arrivals = AsyncMock(side_effect=Exception("API is down"))

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.last_update_success is False
        assert coordinator.get_next_arrival("249") is None

    async def test_coordinator_uses_gov_api_not_busnearby(self, hass: HomeAssistant):
        """Bus setup creates coordinator with gov_api_client, NOT api_client."""
        entry = _make_bus_config_entry()
        entry.add_to_hass(hass)
        mock_client = _make_gov_client_mock()

        with patch(
            "custom_components.israel_transportation.GovApiClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.gov_api_client is mock_client
        assert coordinator.api_client is None


# ---------------------------------------------------------------------------
# Train data flow tests
# ---------------------------------------------------------------------------


class TestTrainDataFlow:
    """Test train: config entry → coordinator → sensor state."""

    async def test_train_setup_to_coordinator(self, hass: HomeAssistant):
        """Train setup creates coordinator without gov_api_client."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN,
                CONF_FROM_STATION: "9600",
                CONF_TO_STATION: "3700",
                CONF_FROM_STATION_NAME: "Sderot",
                CONF_TO_STATION_NAME: "Tel Aviv Savidor",
                CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
                CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
            },
        )
        entry.add_to_hass(hass)

        # Train coordinator calls _query_rail_api which uses israelrailapi
        # Mock the executor job to avoid real API calls
        mock_routes = []

        with patch(
            "custom_components.israel_transportation.coordinator.SilentBusCoordinator._query_rail_api",
            return_value=mock_routes,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.transport_type == TRANSPORT_TYPE_TRAIN
        assert coordinator.gov_api_client is None
        assert coordinator.from_station == "9600"
        assert coordinator.to_station == "3700"
