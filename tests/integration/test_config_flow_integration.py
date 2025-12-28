"""Integration tests for Silent Bus config flow covering all transport types."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.silent_bus.api import (
    ApiConnectionError,
    ApiTimeoutError,
    StationNotFoundError,
)
from custom_components.silent_bus.const import (
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
# BUS STATION INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_bus_station_12664_validation(hass: HomeAssistant):
    """Test validation of bus station 12664 - the specific user-reported issue.

    This test ensures that station 12664 (a real bus station) validates
    correctly using the search endpoint.
    """
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock successful search for station 12664
        mock_client.return_value.search_station = AsyncMock(
            return_value=[
                {
                    "stop_id": "12664",
                    "name": "Test Station 12664",
                    "city": "Tel Aviv",
                    "lat": 32.0853,
                    "lon": 34.7818,
                }
            ]
        )

        # Start config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Select bus transport type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Configure station 12664 - should succeed
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "12664"},
        )

        # Should proceed to bus lines selection
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bus_lines"

        # Verify search_station was called with correct station ID
        mock_client.return_value.search_station.assert_called_once_with("12664")


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
            "custom_components.silent_bus.config_flow.BusNearbyApiClient"
        ) as mock_client:
            mock_client.return_value.search_station = AsyncMock(
                return_value=[
                    {
                        "stop_id": station_data["id"],
                        "name": station_data["name"],
                        "city": "Tel Aviv",
                    }
                ]
            )

            # Start fresh flow for each station
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            # Select bus type
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
            )

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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock search returning empty list (station not found)
        mock_client.return_value.search_station = AsyncMock(return_value=[])

        # Start config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Select bus type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

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
    """Test graceful handling of API timeout errors.

    Ensures that network timeouts are caught and displayed as user-friendly errors.
    """
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock API timeout
        mock_client.return_value.search_station = AsyncMock(
            side_effect=ApiTimeoutError("Request timed out")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Select bus type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Try to configure station (will timeout)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Should show connection error
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


@pytest.mark.asyncio
async def test_bus_station_empty_response(hass: HomeAssistant):
    """Test handling when API returns empty response.

    This covers the edge case where the API responds but has no data.
    """
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock empty response
        mock_client.return_value.search_station = AsyncMock(return_value=[])

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[
                {"stop_id": "24068", "name": "Test Station", "city": "Tel Aviv"}
            ]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Select bus type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"stop_id": "24068", "name": "Test Station"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

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
    """Test valid train routes like 3600→2800, 680→8600.

    These are common train station IDs that should validate properly.
    """
    test_routes = [
        {
            "from": "3600",
            "to": "2800",
            "from_name": "Tel Aviv HaHagana",
            "to_name": "Jerusalem Biblical Zoo",
        },
        {
            "from": "680",
            "to": "8600",
            "from_name": "Tel Aviv Savidor Center",
            "to_name": "Haifa HaShmona",
        },
    ]

    for route in test_routes:
        with patch(
            "custom_components.silent_bus.config_flow.BusNearbyApiClient"
        ) as mock_client:
            # Mock search for both stations
            def mock_search(station_id):
                if station_id == route["from"]:
                    return AsyncMock(
                        return_value=[
                            {"stop_id": route["from"], "name": route["from_name"]}
                        ]
                    )()
                elif station_id == route["to"]:
                    return AsyncMock(
                        return_value=[
                            {"stop_id": route["to"], "name": route["to_name"]}
                        ]
                    )()
                return AsyncMock(return_value=[])()

            mock_client.return_value.search_station = mock_search

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            # Select train type
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN},
            )

            # Configure train route
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_FROM_STATION: route["from"], CONF_TO_STATION: route["to"]},
            )

            # Should create entry
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"][CONF_FROM_STATION] == route["from"]
            assert result["data"][CONF_TO_STATION] == route["to"]
            assert result["data"][CONF_FROM_STATION_NAME] == route["from_name"]
            assert result["data"][CONF_TO_STATION_NAME] == route["to_name"]
            assert result["data"][CONF_TRANSPORT_TYPE] == TRANSPORT_TYPE_TRAIN


@pytest.mark.asyncio
async def test_train_station_same_origin_destination(hass: HomeAssistant):
    """Test that same origin and destination stations are handled.

    While the API might accept this, it's logically invalid for route planning.
    Note: Current implementation doesn't validate this - documenting behavior.
    """
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"stop_id": "3600", "name": "Tel Aviv HaHagana"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN},
        )

        # Configure with same station for both
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FROM_STATION: "3600", CONF_TO_STATION: "3600"},
        )

        # Current behavior: accepts same station (may want to add validation)
        assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_train_station_invalid_rejected(hass: HomeAssistant):
    """Test that non-existent train stations are rejected.

    Invalid station IDs should fail validation.
    """
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Mock search returning empty for invalid stations
        mock_client.return_value.search_station = AsyncMock(return_value=[])

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN},
        )

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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            side_effect=ApiTimeoutError("Request timed out")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FROM_STATION: "3600", CONF_TO_STATION: "2800"},
        )

        # Should show connection error
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


@pytest.mark.asyncio
async def test_train_arrival_data_format(hass: HomeAssistant):
    """Test that train entry has correct data structure and attributes."""
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:

        def mock_search(station_id):
            stations = {
                "3600": [{"stop_id": "3600", "name": "Tel Aviv HaHagana"}],
                "2800": [{"stop_id": "2800", "name": "Jerusalem Biblical Zoo"}],
            }
            return AsyncMock(return_value=stations.get(station_id, []))()

        mock_client.return_value.search_station = mock_search

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_TRAIN},
        )

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
        assert result["data"][CONF_UPDATE_INTERVAL] == DEFAULT_SCAN_INTERVAL.total_seconds()
        assert result["data"][CONF_MAX_ARRIVALS] == DEFAULT_MAX_ARRIVALS


# ============================================================================
# LIGHT RAIL INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_lightrail_station_validation(hass: HomeAssistant):
    """Test validation of light rail stations (Jerusalem/Tel Aviv).

    Tests both Jerusalem light rail and Tel Aviv light rail stations.
    """
    test_stations = [
        {"id": "30001", "name": "Pisgat Ze'ev", "city": "Jerusalem"},
        {"id": "30010", "name": "City Hall", "city": "Jerusalem"},
        {"id": "40001", "name": "Bat Yam", "city": "Tel Aviv"},
    ]

    for station_data in test_stations:
        with patch(
            "custom_components.silent_bus.config_flow.BusNearbyApiClient"
        ) as mock_client:
            mock_client.return_value.search_station = AsyncMock(
                return_value=[
                    {
                        "stop_id": station_data["id"],
                        "name": station_data["name"],
                        "city": station_data["city"],
                    }
                ]
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            # Select light rail type
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_LIGHT_RAIL},
            )

            # Configure station
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_STATION_ID: station_data["id"]},
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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[
                {"stop_id": "30001", "name": "Pisgat Ze'ev", "city": "Jerusalem"}
            ]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_LIGHT_RAIL},
        )

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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[
                {
                    "stop_id": "30010",
                    "name": "City Hall",
                    "city": "Jerusalem",
                    "lat": 31.7833,
                    "lon": 35.2167,
                }
            ]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_LIGHT_RAIL},
        )

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

    # Verify all three types can be selected
    # (We can't directly inspect the schema, but we can test each type)
    for transport_type in [
        TRANSPORT_TYPE_BUS,
        TRANSPORT_TYPE_TRAIN,
        TRANSPORT_TYPE_LIGHT_RAIL,
    ]:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: transport_type},
        )

        # Should proceed to appropriate config step
        assert result["type"] == FlowResultType.FORM
        expected_step = (
            "train_config" if transport_type == TRANSPORT_TYPE_TRAIN else "station_config"
        )
        assert result["step_id"] == expected_step

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
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"stop_id": "24068", "name": "Test Station"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

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
    """Test handling of various connection errors."""
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Test ApiConnectionError
        mock_client.return_value.search_station = AsyncMock(
            side_effect=ApiConnectionError("Network error")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


@pytest.mark.asyncio
async def test_station_id_whitespace_handling(hass: HomeAssistant):
    """Test that station IDs with whitespace are properly trimmed."""
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"stop_id": "24068", "name": "Test Station"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        # Submit station ID with whitespace
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "  24068  "},
        )

        # Should proceed successfully (whitespace trimmed)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bus_lines"

        # Verify search was called with trimmed ID
        mock_client.return_value.search_station.assert_called_once_with("24068")


@pytest.mark.asyncio
async def test_generic_exception_handling(hass: HomeAssistant):
    """Test handling of unexpected exceptions."""
    with patch(
        "custom_components.silent_bus.config_flow.BusNearbyApiClient"
    ) as mock_client:
        # Simulate unexpected exception
        mock_client.return_value.search_station = AsyncMock(
            side_effect=ValueError("Unexpected error")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "24068"},
        )

        # Should show station not found error (caught by generic exception handler)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": ERROR_STATION_NOT_FOUND}
