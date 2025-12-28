"""Tests for the Silent Bus config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.silent_bus.api import ApiConnectionError
from custom_components.silent_bus.const import (
    CONF_BUS_LINES,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    ERROR_STATION_NOT_FOUND,
)


@pytest.mark.asyncio
async def test_user_form_display(hass: HomeAssistant):
    """Test that user form is displayed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    # First step shows transport type selection, no errors expected
    assert result.get("errors") is None or result.get("errors") == {}


@pytest.mark.asyncio
async def test_user_form_station_not_found(hass: HomeAssistant):
    """Test station not found error."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(return_value=[])

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First configure transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Select manual entry method
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selection_method": "manual"},
        )

        # Then configure station (should fail validation)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "99999"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}


@pytest.mark.asyncio
async def test_user_form_cannot_connect(hass: HomeAssistant):
    """Test connection error is caught and shown as station not found."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # ApiConnectionError is caught by generic exception handler in config flow
        mock_client.return_value.search_station = AsyncMock(
            side_effect=ApiConnectionError("Test error")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First configure transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Select manual entry method
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selection_method": "manual"},
        )

        # Then configure station (connection error caught as station not found)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        assert result["type"] == FlowResultType.FORM
        # Note: ApiConnectionError is caught by generic handler, shown as station_not_found
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}


@pytest.mark.asyncio
async def test_user_form_success(hass: HomeAssistant):
    """Test successful station validation."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"name": "Test Station", "stop_id": "24068"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First configure transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Select manual entry method
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selection_method": "manual"},
        )

        # Then configure station (should succeed)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bus_lines"


@pytest.mark.asyncio
async def test_bus_lines_form_no_lines(hass: HomeAssistant):
    """Test bus lines form with no lines entered."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"name": "Test Station", "stop_id": "24068"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First configure transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Select manual entry method
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selection_method": "manual"},
        )

        # Then configure station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Then configure bus lines (empty - should fail)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: ""},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_lines"}


@pytest.mark.asyncio
async def test_full_flow_success(hass: HomeAssistant):
    """Test complete successful flow."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"name": "Test Station", "stop_id": "24068"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First configure transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Select manual entry method
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selection_method": "manual"},
        )

        # Then configure station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Then configure bus lines
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: "249, 40, 605"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Station"
        assert result["data"][CONF_STATION_ID] == "24068"
        assert result["data"][CONF_BUS_LINES] == ["249", "40", "605"]


@pytest.mark.asyncio
async def test_options_flow(hass: HomeAssistant):
    """Test options flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Test Station",
            CONF_BUS_LINES: ["249", "40"],
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_options_flow_update(hass: HomeAssistant):
    """Test options flow with updates."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Test Station",
            CONF_BUS_LINES: ["249", "40"],
        },
    )

    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_update_entry"):
        result = await hass.config_entries.options.async_init(entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_BUS_LINES: "249, 40, 605",
                "update_interval": 60,
                "max_arrivals": 5,
            },
        )

        # Options flow completes successfully
        assert result["type"] == FlowResultType.CREATE_ENTRY
