"""Integration tests for Israel Transportation setup/unload."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.israel_transportation import (
    SERVICE_REFRESH_DATA,
    SERVICE_UPDATE_LINES,
)
from custom_components.israel_transportation.api import ApiConnectionError
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


@pytest.mark.asyncio
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry, mock_gov_api_client
):
    """Test integration setup and unload lifecycle."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # Verify coordinator is stored
    entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert "coordinator" in entry_data
    coordinator = entry_data["coordinator"]
    assert coordinator.gov_api_client is mock_gov_api_client

    # Unload
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    await hass.async_stop()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_setup_does_not_validate_station(hass: HomeAssistant, mock_config_entry):
    """Setup must not gate on a live validation call.

    Validating at setup meant one upstream outage put every configured station
    into setup_retry with no entities. Validation belongs in the config flow;
    here, a failing fetch should only make entities unavailable.
    """
    mock_gov_api_client = MagicMock()
    mock_gov_api_client.validate_station = AsyncMock(return_value=False)
    mock_gov_api_client.get_arrivals = AsyncMock(return_value=[])

    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    mock_gov_api_client.validate_station.assert_not_awaited()


@pytest.mark.asyncio
async def test_reload_entry(
    hass: HomeAssistant, mock_config_entry, mock_gov_api_client
):
    """Test reloading the config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED

        # Reload
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED


@pytest.mark.asyncio
async def test_sensors_created(
    hass: HomeAssistant, mock_config_entry, mock_gov_api_client
):
    """Test that sensors are created for each bus line."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Verify coordinator was created with correct lines
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
    bus_lines = mock_config_entry.data[CONF_BUS_LINES]
    assert coordinator.bus_lines == bus_lines


@pytest.mark.asyncio
async def test_setup_raises_config_entry_not_ready_on_api_connection_error(
    hass: HomeAssistant, mock_config_entry
):
    """A connection error during coordinator setup should retry, not hard-fail."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        side_effect=ApiConnectionError("boom"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_options_update_triggers_reload(hass: HomeAssistant, setup_integration):
    """Updating a config entry's options should reload it via the update listener."""
    entry = setup_integration
    assert entry.state == ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(entry, options={"changed": True})
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED


async def _setup_station(
    hass: HomeAssistant, gov_client, station_id: str, station_name: str
) -> MockConfigEntry:
    """Set up one bus station entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: station_id,
            CONF_STATION_NAME: station_name,
            CONF_BUS_LINES: ["249", "40"],
            CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
            CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
        },
        unique_id=station_id,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=gov_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_ids(hass: HomeAssistant, entry: MockConfigEntry) -> list[str]:
    """Sensor entity ids registered for a config entry."""
    registry = er.async_get(hass)
    return [
        e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    ]


def _coordinator(hass: HomeAssistant, entry: MockConfigEntry):
    return hass.data[DOMAIN][entry.entry_id]["coordinator"]


@pytest.fixture
async def two_stations(hass: HomeAssistant, mock_gov_api_client):
    """Two configured bus stations (hacs/default#10146 item 3)."""
    station_a = await _setup_station(hass, mock_gov_api_client, "24068", "Station A")
    station_b = await _setup_station(hass, mock_gov_api_client, "12664", "Station B")
    assert _entity_ids(hass, station_a) and _entity_ids(hass, station_b)
    return station_a, station_b


@pytest.mark.asyncio
async def test_refresh_data_without_target_refreshes_every_station(
    hass: HomeAssistant, two_stations
):
    """refresh_data with no entity_id refreshes every coordinator once."""
    station_a, station_b = two_stations
    with (
        patch.object(_coordinator(hass, station_a), "async_request_refresh") as a,
        patch.object(_coordinator(hass, station_b), "async_request_refresh") as b,
    ):
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_DATA, {}, blocking=True)

    a.assert_awaited_once()
    b.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_data_refreshes_only_the_targeted_station(
    hass: HomeAssistant, two_stations
):
    """Targeting station B's sensors refreshes B once and leaves A alone."""
    station_a, station_b = two_stations
    with (
        patch.object(_coordinator(hass, station_a), "async_request_refresh") as a,
        patch.object(_coordinator(hass, station_b), "async_request_refresh") as b,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_DATA,
            {ATTR_ENTITY_ID: _entity_ids(hass, station_b)},
            blocking=True,
        )

    a.assert_not_awaited()
    b.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_data_rejects_unknown_entity(hass: HomeAssistant, two_stations):
    """An entity that is not ours raises a translated validation error."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_DATA,
            {ATTR_ENTITY_ID: ["sensor.not_ours"]},
            blocking=True,
        )
    assert err.value.translation_key == "unknown_entity"


@pytest.mark.asyncio
async def test_update_lines_changes_only_the_targeted_station(
    hass: HomeAssistant, two_stations
):
    """update_lines on station B rewrites B's lines and leaves A untouched."""
    station_a, station_b = two_stations
    lines_a = list(station_a.data[CONF_BUS_LINES])

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_LINES,
        {ATTR_ENTITY_ID: _entity_ids(hass, station_b)[0], "lines": "101, 102 ,103"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(station_b.entry_id).data[
        CONF_BUS_LINES
    ] == ["101", "102", "103"]
    assert _coordinator(hass, station_b).bus_lines == ["101", "102", "103"]
    assert (
        hass.config_entries.async_get_entry(station_a.entry_id).data[CONF_BUS_LINES]
        == lines_a
    )
    assert _coordinator(hass, station_a).bus_lines == lines_a


@pytest.mark.asyncio
async def test_update_lines_rejects_unknown_entity(hass: HomeAssistant, two_stations):
    """update_lines with an entity that is not ours raises and changes nothing."""
    station_a, _ = two_stations
    lines_a = list(station_a.data[CONF_BUS_LINES])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_LINES,
            {ATTR_ENTITY_ID: "sensor.not_ours", "lines": "1"},
            blocking=True,
        )

    assert _coordinator(hass, station_a).bus_lines == lines_a


@pytest.mark.asyncio
async def test_update_lines_service_ignores_blank_lines(
    hass: HomeAssistant, two_stations, caplog
):
    """update_lines with no valid line numbers should warn and leave state unchanged."""
    station_a, _ = two_stations
    original_lines = list(_coordinator(hass, station_a).bus_lines)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_LINES,
        {ATTR_ENTITY_ID: _entity_ids(hass, station_a)[0], "lines": " , , "},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _coordinator(hass, station_a).bus_lines == original_lines
    assert "No valid lines provided" in caplog.text


@pytest.mark.asyncio
async def test_update_lines_service_rejects_train_entity(hass: HomeAssistant, caplog):
    """update_lines is bus/light-rail only; a train entity is left unchanged."""
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

    with patch(
        "custom_components.israel_transportation.coordinator.SilentBusCoordinator._query_rail_api",
        return_value=[],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_LINES,
        {ATTR_ENTITY_ID: _entity_ids(hass, entry)[0], "lines": "101"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Cannot update lines for train routes" in caplog.text
    assert (
        CONF_BUS_LINES not in hass.config_entries.async_get_entry(entry.entry_id).data
    )
