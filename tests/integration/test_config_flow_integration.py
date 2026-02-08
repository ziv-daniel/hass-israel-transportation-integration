"""Integration tests for Israel Transportation config flow covering all transport types."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.israel_transportation.api import (
    ApiTimeoutError,
)
from custom_components.israel_transportation.gov_api import (
    ApiConnectionError as GovApiConnectionError,
)
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
    ERROR_CANNOT_CONNECT,
    ERROR_STATION_NOT_FOUND,
    TRANSPORT_TYPE_BUS,
    TRANSPORT_TYPE_LIGHT_RAIL,
    TRANSPORT_TYPE_TRAIN,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def navigate_to_station_config(hass: HomeAssistant, transport_type: str):
    """Navigate through the config flow to the station config step.

    Args:
        hass: Home Assistant instance
        transport_type: Transport type to select

    Returns:
        Flow result after navigation
    """
    # Start config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select transport type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT_TYPE: transport_type},
    )

    # Select manual entry method
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selection_method": "manual"},
    )

    return result


async def navigate_to_train_config(hass: HomeAssistant):
    """Navigate through the config flow to the train config step.

    Args:
        hass: Home Assistant instance

    Returns:
        Flow result after navigation
    """
    # Start config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select train transport type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN},
    )

    # Select manual entry method
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selection_method": "manual"},
    )

    return result


# ============================================================================
# BUS STATION INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_bus_station_12664_validation(hass: HomeAssistant):
    """Test validation of bus station 12664 - the specific user-reported issue.

    This test ensures that station 12664 (a real bus station) validates
    correctly using the gov API.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        # Mock successful station lookup
        mock_client.return_value.get_station = AsyncMock(
            return_value={
                "Name": "Test Station 12664",
                "Makat": 12664,
                "Latitude": 32.0853,
                "Longitude": 34.7818,
            }
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        # Configure station 12664 - should succeed
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "12664"},
        )

        # Should proceed to bus lines selection
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bus_lines"

        # Verify get_station was called with correct station ID
        mock_client.return_value.get_station.assert_called_once_with("12664")


@pytest.mark.asyncio
async def test_bus_station_valid_common_stations(hass: HomeAssistant):
    """Test validation of common valid bus stations (24068, 24069).

    These are well-known Tel Aviv bus stations that should always validate.
    """
    test_stations = [
        {"id": "24068", "name": "Arlozorov Terminal"},
        {"id": "24069", "name": "Tel Aviv Central Bus Station"},
    ]

    for station_data in test_stations:
        with patch(
            "custom_components.israel_transportation.config_flow.GovApiClient"
        ) as mock_client:
            mock_client.return_value.get_station = AsyncMock(
                return_value={
                    "Name": station_data["name"],
                    "Makat": int(station_data["id"]),
                }
            )
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_client.return_value
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            # Navigate to station config
            result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

            # Configure station
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_STATION_ID: station_data["id"]},
            )

            # Should proceed to bus lines
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "bus_lines"

            # Complete the flow
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_BUS_LINES: "249, 40"},
            )

            # Should create entry successfully
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"][CONF_STATION_ID] == station_data["id"]
            assert result["data"][CONF_STATION_NAME] == station_data["name"]


@pytest.mark.asyncio
async def test_bus_station_invalid_rejected(hass: HomeAssistant):
    """Test that invalid bus station (99999999) is properly rejected.

    This tests the error handling when a station doesn't exist.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        # Mock station not found (Name is None, Makat is 0)
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": None, "Makat": 0}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        # Try to configure invalid station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "99999999"},
        )

        # Should show error and stay on same form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_config"
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}


@pytest.mark.asyncio
async def test_bus_station_api_timeout(hass: HomeAssistant):
    """Test graceful handling of API connection errors.

    Ensures that connection errors are caught and displayed as user-friendly errors.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        # Mock API connection error
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value.get_station = AsyncMock(
            side_effect=GovApiConnectionError("Connection failed")
        )

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        # Try to configure station (will fail with connection error)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Should show cannot connect error
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


@pytest.mark.asyncio
async def test_bus_station_empty_response(hass: HomeAssistant):
    """Test handling when API returns station not found.

    This covers the edge case where the API responds but station is invalid.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        # Mock station not found response (Name is None, Makat is 0)
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": None, "Makat": 0}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "12345"},
        )

        # Should show station not found error
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}


@pytest.mark.asyncio
async def test_bus_lines_selection(hass: HomeAssistant):
    """Test selection and configuration of multiple bus lines.

    Verifies that users can configure multiple lines separated by commas.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        # Configure station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Configure multiple bus lines with various spacing
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: "249, 40,  605,  18  ,  189"},
        )

        # Should create entry with properly parsed lines
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_BUS_LINES] == ["249", "40", "605", "18", "189"]


@pytest.mark.asyncio
async def test_bus_lines_validation_required(hass: HomeAssistant):
    """Test that at least one bus line is required.

    Empty or whitespace-only input should be rejected.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Test various empty inputs
        empty_inputs = ["", "   ", ",,,", "  ,  ,  "]

        for empty_input in empty_inputs:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_BUS_LINES: empty_input},
            )

            # Should show error and stay on form
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "bus_lines"
            assert result["errors"] == {"base": "no_lines"}


# ============================================================================
# TRAIN STATION INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_train_station_valid_routes(hass: HomeAssistant):
    """Test valid train routes like 3600→2800.

    These are common train station IDs that should validate properly.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock search for both stations
        def mock_search(station_id):
            stations = {
                "3600": [{"stop_id": "3600", "name": "Tel Aviv HaHagana"}],
                "2800": [{"stop_id": "2800", "name": "Jerusalem Biblical Zoo"}],
            }
            return AsyncMock(return_value=stations.get(station_id, []))()

        mock_client.return_value.search_station = mock_search

        # Mock train route API validation (called after search_station succeeds)
        mock_client.return_value.validate_train_route_api_response = AsyncMock(
            return_value=(True, "")
        )

        # Navigate to train config
        result = await navigate_to_train_config(hass)

        # Configure train route
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FROM_STATION: "3600", CONF_TO_STATION: "2800"},
        )

        # Should create entry
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_FROM_STATION] == "3600"
        assert result["data"][CONF_TO_STATION] == "2800"
        assert result["data"][CONF_TRANSPORT_TYPE] == TRANSPORT_TYPE_TRAIN


@pytest.mark.asyncio
async def test_train_station_invalid_rejected(hass: HomeAssistant):
    """Test that non-existent train stations are rejected.

    Invalid station IDs should fail validation.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock search returning empty for invalid stations
        mock_client.return_value.search_station = AsyncMock(return_value=[])

        # Navigate to train config
        result = await navigate_to_train_config(hass)

        # Try invalid stations
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FROM_STATION: "99999", CONF_TO_STATION: "88888"},
        )

        # Should show error
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "train_config"
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}


@pytest.mark.asyncio
async def test_train_api_timeout(hass: HomeAssistant):
    """Test graceful handling of API timeout during train station validation."""
    with patch(
        "custom_components.israel_transportation.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            side_effect=ApiTimeoutError("Request timed out")
        )

        # Navigate to train config
        result = await navigate_to_train_config(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FROM_STATION: "3600", CONF_TO_STATION: "2800"},
        )

        # Should show station not found error (caught by generic exception handler)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}


@pytest.mark.asyncio
async def test_train_arrival_data_format(hass: HomeAssistant):
    """Test that train entry has correct data structure and attributes."""
    with patch(
        "custom_components.israel_transportation.config_flow.BusNearbyApiClient"
    ) as mock_client:

        def mock_search(station_id):
            stations = {
                "3600": [{"stop_id": "3600", "name": "Tel Aviv HaHagana"}],
                "2800": [{"stop_id": "2800", "name": "Jerusalem Biblical Zoo"}],
            }
            return AsyncMock(return_value=stations.get(station_id, []))()

        mock_client.return_value.search_station = mock_search

        # Mock train route API validation (called after search_station succeeds)
        mock_client.return_value.validate_train_route_api_response = AsyncMock(
            return_value=(True, "")
        )

        # Navigate to train config
        result = await navigate_to_train_config(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FROM_STATION: "3600", CONF_TO_STATION: "2800"},
        )

        # Verify all required attributes are present
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert CONF_TRANSPORT_TYPE in result["data"]
        assert CONF_FROM_STATION in result["data"]
        assert CONF_TO_STATION in result["data"]
        assert CONF_FROM_STATION_NAME in result["data"]
        assert CONF_TO_STATION_NAME in result["data"]
        assert CONF_UPDATE_INTERVAL in result["data"]
        assert CONF_MAX_ARRIVALS in result["data"]

        # Verify default values
        assert (
            result["data"][CONF_UPDATE_INTERVAL]
            == DEFAULT_SCAN_INTERVAL.total_seconds()
        )
        assert result["data"][CONF_MAX_ARRIVALS] == DEFAULT_MAX_ARRIVALS


# ============================================================================
# LIGHT RAIL INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_lightrail_station_validation(hass: HomeAssistant):
    """Test validation of light rail stations (Jerusalem/Tel Aviv).

    Tests both Jerusalem light rail and Tel Aviv light rail stations.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Pisgat Ze'ev", "Makat": 30001}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config for light rail
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_LIGHT_RAIL)

        # Configure station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "30001"},
        )

        # Should proceed to line selection
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bus_lines"


@pytest.mark.asyncio
async def test_lightrail_line_selection(hass: HomeAssistant):
    """Test light rail line configuration.

    Light rail typically has fewer lines (e.g., 1, 2, 3 for Jerusalem).
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Pisgat Ze'ev", "Makat": 30001}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config for light rail
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_LIGHT_RAIL)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "30001"},
        )

        # Configure light rail lines
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: "1, 2"},
        )

        # Should create entry successfully
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_TRANSPORT_TYPE] == TRANSPORT_TYPE_LIGHT_RAIL
        assert result["data"][CONF_BUS_LINES] == ["1", "2"]
        assert result["data"][CONF_STATION_ID] == "30001"


@pytest.mark.asyncio
async def test_lightrail_api_response(hass: HomeAssistant):
    """Test that light rail configuration creates correct data structure."""
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={
                "Name": "City Hall",
                "Makat": 30010,
                "Latitude": 31.7833,
                "Longitude": 35.2167,
            }
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config for light rail
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_LIGHT_RAIL)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "30010"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: "1"},
        )

        # Verify data structure
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_TRANSPORT_TYPE] == TRANSPORT_TYPE_LIGHT_RAIL
        assert result["data"][CONF_STATION_ID] == "30010"
        assert result["data"][CONF_STATION_NAME] == "City Hall"
        assert result["data"][CONF_BUS_LINES] == ["1"]
        assert CONF_UPDATE_INTERVAL in result["data"]
        assert CONF_MAX_ARRIVALS in result["data"]


# ============================================================================
# COMMON FLOW INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_transport_type_selection_all_types_available(hass: HomeAssistant):
    """Test that all 3 transport types are available in initial selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Verify initial form shows transport type selection
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test each transport type leads to station_selection_method
    for transport_type in [
        TRANSPORT_TYPE_BUS,
        TRANSPORT_TYPE_TRAIN,
        TRANSPORT_TYPE_LIGHT_RAIL,
    ]:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: transport_type},
        )

        # Should proceed to station selection method
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_selection_method"

        # Restart flow for next iteration
        if transport_type != TRANSPORT_TYPE_LIGHT_RAIL:
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )


@pytest.mark.asyncio
async def test_already_configured_rejection(hass: HomeAssistant):
    """Test that duplicate configurations are prevented.

    Same station with same lines should not be configured twice.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Test Station",
            CONF_BUS_LINES: ["249", "40"],
        },
        unique_id="24068",
    )
    existing_entry.add_to_hass(hass)

    # Try to add same station again
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BUS_LINES: "249, 40"},
        )

        # Should abort due to duplicate
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_options_flow_update_lines(hass: HomeAssistant):
    """Test updating bus lines through options flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Import config_flow to register handler in HANDLERS registry
    import custom_components.israel_transportation.config_flow  # noqa: F401

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Test Station",
            CONF_BUS_LINES: ["249", "40"],
            CONF_UPDATE_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
            CONF_MAX_ARRIVALS: DEFAULT_MAX_ARRIVALS,
        },
    )
    entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Update lines
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_BUS_LINES: "249, 40, 605, 18",
            CONF_UPDATE_INTERVAL: 45,
            CONF_MAX_ARRIVALS: 5,
        },
    )

    # Should complete successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify data was updated
    assert entry.data[CONF_BUS_LINES] == ["249", "40", "605", "18"]
    assert entry.data[CONF_UPDATE_INTERVAL] == 45
    assert entry.data[CONF_MAX_ARRIVALS] == 5


@pytest.mark.asyncio
async def test_options_flow_update_interval(hass: HomeAssistant):
    """Test updating scan interval and max arrivals through options flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Import config_flow to register handler in HANDLERS registry
    import custom_components.israel_transportation.config_flow  # noqa: F401

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS,
            CONF_STATION_ID: "24068",
            CONF_STATION_NAME: "Test Station",
            CONF_BUS_LINES: ["249"],
            CONF_UPDATE_INTERVAL: 30,
            CONF_MAX_ARRIVALS: 3,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Update settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_BUS_LINES: "249",
            CONF_UPDATE_INTERVAL: 60,
            CONF_MAX_ARRIVALS: 8,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_UPDATE_INTERVAL] == 60
    assert entry.data[CONF_MAX_ARRIVALS] == 8


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_connection_error_handling(hass: HomeAssistant):
    """Test handling of various connection errors.

    GovApiConnectionError is caught and shown as cannot_connect error.
    """
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        # Test GovApiConnectionError
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value.get_station = AsyncMock(
            side_effect=GovApiConnectionError("Network error")
        )

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        assert result["type"] == FlowResultType.FORM
        # GovApiConnectionError is caught and shown as cannot_connect
        assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


@pytest.mark.asyncio
async def test_station_id_whitespace_handling(hass: HomeAssistant):
    """Test that station IDs with whitespace are properly trimmed."""
    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        mock_client.return_value.get_station = AsyncMock(
            return_value={"Name": "Test Station", "Makat": 24068}
        )
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        # Submit station ID with whitespace
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "  24068  "},
        )

        # Should proceed successfully (whitespace trimmed)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bus_lines"

        # Verify get_station was called with trimmed ID
        mock_client.return_value.get_station.assert_called_once_with("24068")


@pytest.mark.asyncio
async def test_generic_exception_handling(hass: HomeAssistant):
    """Test handling of unexpected exceptions."""
    from custom_components.israel_transportation.const import ERROR_UNKNOWN

    with patch(
        "custom_components.israel_transportation.config_flow.GovApiClient"
    ) as mock_client:
        # Simulate unexpected exception
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client.return_value
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value.get_station = AsyncMock(
            side_effect=ValueError("Unexpected error")
        )

        # Navigate to station config
        result = await navigate_to_station_config(hass, TRANSPORT_TYPE_BUS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Should show unknown error (caught by generic exception handler)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_UNKNOWN}
