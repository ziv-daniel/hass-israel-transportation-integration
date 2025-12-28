"""Tests for the Silent Bus config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.silent_bus.api import ApiConnectionError
from custom_components.silent_bus.gov_api import ApiConnectionError as GovApiConnectionError
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
        "custom_components.silent_bus.config_flow.GovApiClient"
    ) as mock_client:
        # Mock station not found (Name is None, Makat is 0)
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": None, "Makat": 0}
        )
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

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
    """Test connection error is caught and shown as cannot_connect error."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
        ERROR_CANNOT_CONNECT,
    )

    with patch(
        "custom_components.silent_bus.config_flow.GovApiClient"
    ) as mock_client:
        # GovApiConnectionError is caught and shown as cannot_connect
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value.get_station = AsyncMock(
            side_effect=GovApiConnectionError("Test error")
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

        # Then configure station (connection error caught)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        assert result["type"] == FlowResultType.FORM
        # GovApiConnectionError is caught and shown as cannot_connect
        assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


@pytest.mark.asyncio
async def test_user_form_success(hass: HomeAssistant):
    """Test successful station validation."""
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.GovApiClient"
    ) as mock_client:
        # Mock valid station (Name is set, Makat is non-zero)
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

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
        "custom_components.silent_bus.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

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
        "custom_components.silent_bus.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

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


@pytest.mark.asyncio
async def test_station_makat_used_directly(hass: HomeAssistant):
    """Test that user-entered makat is used directly with gov API.

    With the gov API, users enter the makat (stop code displayed on bus stop signs)
    and the gov API accepts this directly without translation.
    """
    from custom_components.silent_bus.const import (
        CONF_TRANSPORT_TYPE,
        TRANSPORT_TYPE_BUS,
    )

    with patch(
        "custom_components.silent_bus.config_flow.GovApiClient"
    ) as mock_client:
        # Gov API returns station info directly using makat
        mock_client.return_value.get_station = AsyncMock(
            return_value={
                "Name": "אלי מויאל/דוד המלך",
                "Makat": 12665,
                "Latitude": 31.54078,
                "Longitude": 34.596389,
            }
        )
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Configure transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Select manual entry method
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selection_method": "manual"},
        )

        # Enter makat "12665" (what user sees on bus stop sign)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "12665"},
        )

        # Configure bus lines
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: "1, 5, 1א"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # With gov API, the makat is stored directly as entered
        assert result["data"][CONF_STATION_ID] == "12665"
        assert result["data"][CONF_BUS_LINES] == ["1", "5", "1א"]
