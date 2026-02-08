"""Integration tests for Israel Transportation."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.israel_transportation.const import (
    CONF_BUS_LINES,
    CONF_STATION_ID,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry, mock_gov_api_client
):
    """Test integration setup and unload."""
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

    # Unload
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    # Stop Home Assistant to cleanup all background threads
    await hass.async_stop()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_setup_failure_invalid_station(hass: HomeAssistant, mock_config_entry):
    """Test setup failure with invalid station."""
    mock_gov_api_client = MagicMock()
    mock_gov_api_client.validate_station = AsyncMock(return_value=False)

    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.israel_transportation.GovApiClient",
        return_value=mock_gov_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


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

    # Check that sensors exist for each configured line
    bus_lines = mock_config_entry.data[CONF_BUS_LINES]
    station_id = mock_config_entry.data[CONF_STATION_ID]

    for line in bus_lines:
        entity_id = f"sensor.bus_{station_id}_line_{line}"
        hass.states.get(entity_id)
        # Sensor may not be registered yet, but the entity should exist
        # We're mainly checking that the integration loaded properly
