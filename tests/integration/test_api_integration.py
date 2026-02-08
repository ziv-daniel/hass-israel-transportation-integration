"""Integration tests for Israel Transportation API endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.israel_transportation.api import (
    ApiConnectionError,
    ApiTimeoutError,
    BusNearbyApiClient,
    InvalidResponseError,
    StationNotFoundError,
)


# ============================================================================
# SEARCH STATION ENDPOINT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_search_station_endpoint_basic(hass):
    """Test basic search station endpoint functionality.

    Verifies that the search endpoint returns expected data structure.
    """
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
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
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.search_station("24068")

    # Verify response structure
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["stop_id"] == "24068"
    assert result[0]["name"] == "Arlozorov Terminal"
    assert result[0]["city"] == "Tel Aviv"
    assert "lat" in result[0]
    assert "lon" in result[0]


@pytest.mark.asyncio
async def test_search_station_12664_specific(hass):
    """Test search for station 12664 - the specific user-reported issue.

    This is the critical test case that validates the fix for the reported bug.
    Station 12664 should be found and validated correctly.
    """
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[
            {
                "stop_id": "12664",
                "name": "Station 12664",
                "city": "Test City",
                "lat": 32.0,
                "lon": 34.0,
            }
        ]
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    # Test search
    result = await client.search_station("12664")
    assert len(result) == 1
    assert result[0]["stop_id"] == "12664"

    # Test validation (uses search endpoint internally)
    is_valid = await client.validate_station("12664")
    assert is_valid is True


@pytest.mark.asyncio
async def test_search_station_response_format(hass):
    """Test that search station returns data in expected format.

    Verifies all expected fields are present in the response.
    """
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[
            {
                "stop_id": "24068",
                "name": "Arlozorov Terminal",
                "city": "Tel Aviv",
                "lat": 32.0853,
                "lon": 34.7818,
            },
            {
                "stop_id": "24069",
                "name": "Tel Aviv Central",
                "city": "Tel Aviv",
                "lat": 32.0544,
                "lon": 34.7801,
            },
        ]
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    results = await client.search_station("Tel Aviv")

    # Verify list structure
    assert isinstance(results, list)
    assert len(results) == 2

    # Verify each result has required fields
    for result in results:
        assert "stop_id" in result
        assert "name" in result
        assert isinstance(result["stop_id"], str)
        assert isinstance(result["name"], str)

        # Optional fields
        if "city" in result:
            assert isinstance(result["city"], str)
        if "lat" in result:
            assert isinstance(result["lat"], (int, float))
        if "lon" in result:
            assert isinstance(result["lon"], (int, float))


@pytest.mark.asyncio
async def test_search_station_error_handling_not_found(hass):
    """Test search station error handling when station not found."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=[])
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    # Should raise StationNotFoundError
    with pytest.raises(StationNotFoundError) as exc_info:
        await client.search_station("99999999")

    assert "No stations found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_station_error_handling_invalid_response(hass):
    """Test search station error handling with invalid response format."""
    mock_response = MagicMock()
    # Return dict instead of list
    mock_response.json = AsyncMock(return_value={"error": "Invalid format"})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    # Should raise InvalidResponseError
    with pytest.raises(InvalidResponseError) as exc_info:
        await client.search_station("24068")

    assert "Expected list response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_station_error_handling_network_error(hass):
    """Test search station with network connection error."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Network error"))

    client = BusNearbyApiClient(session=mock_session)

    # Should raise ApiConnectionError after retries
    with pytest.raises(ApiConnectionError) as exc_info:
        await client.search_station("24068")

    assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_station_error_handling_timeout(hass):
    """Test search station with timeout error and retry logic."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

    client = BusNearbyApiClient(session=mock_session)

    # Should raise ApiTimeoutError after retries
    with pytest.raises(ApiTimeoutError) as exc_info:
        await client.search_station("24068")

    assert "timed out" in str(exc_info.value).lower()


# ============================================================================
# GET STOP TIMES ENDPOINT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_stop_times_endpoint_basic(hass):
    """Test basic get stop times endpoint functionality."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value={
            "times": [
                {
                    "routeShortName": "249",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 1000,
                    "scheduledArrival": 1000,
                    "realtime": True,
                    "headsign": "Jerusalem",
                },
                {
                    "routeShortName": "40",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 2000,
                    "scheduledArrival": 2000,
                    "realtime": False,
                    "headsign": "Ramat Gan",
                },
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.get_stop_times("24068")

    # Verify response structure
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["routeShortName"] == "249"
    assert result[1]["routeShortName"] == "40"


@pytest.mark.asyncio
async def test_get_stop_times_with_line_filter(hass):
    """Test get stop times with bus line filtering."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value={
            "times": [
                {
                    "routeShortName": "249",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 1000,
                },
                {
                    "routeShortName": "40",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 2000,
                },
                {
                    "routeShortName": "605",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 3000,
                },
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.get_stop_times("24068", bus_lines=["249", "605"])

    # Should only return filtered lines
    assert len(result) == 2
    assert result[0]["routeShortName"] == "249"
    assert result[1]["routeShortName"] == "605"


@pytest.mark.asyncio
async def test_get_stop_times_stop_id_formatting(hass):
    """Test that stop IDs are properly formatted with '1:' prefix."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"times": []})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_get = AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    mock_session.get = MagicMock(return_value=mock_get)

    client = BusNearbyApiClient(session=mock_session)

    # Test with station ID without prefix
    await client.get_stop_times("24068")
    call_args = mock_session.get.call_args
    assert "1:24068" in call_args[0][0]

    # Reset mock
    mock_session.get.reset_mock()

    # Test with station ID that already has prefix
    await client.get_stop_times("1:24068")
    call_args = mock_session.get.call_args
    # Should not double-prefix
    assert "1:24068" in call_args[0][0]
    assert "1:1:24068" not in call_args[0][0]


@pytest.mark.asyncio
async def test_get_stop_times_missing_times_returns_empty(hass):
    """Test handling of response missing 'times' key returns empty list.

    When the API returns a dict without 'times', it means the station has no
    scheduled service. This should return an empty list, not raise an exception.
    """
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"invalid": "data"})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    # Should return empty list instead of raising exception
    result = await client.get_stop_times("24068")
    assert result == []


@pytest.mark.asyncio
async def test_get_stop_times_invalid_response_not_list(hass):
    """Test handling of invalid response where 'times' is not a list."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"times": "invalid"})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    with pytest.raises(InvalidResponseError) as exc_info:
        await client.get_stop_times("24068")

    assert "not a list" in str(exc_info.value)


# ============================================================================
# VALIDATE STATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_validate_station_success(hass):
    """Test successful station validation."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[{"stop_id": "24068", "name": "Arlozorov Terminal"}]
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.validate_station("24068")

    assert result is True


@pytest.mark.asyncio
async def test_validate_station_failure_not_found(hass):
    """Test station validation failure when station not found."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=[])
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.validate_station("99999")

    assert result is False


@pytest.mark.asyncio
async def test_validate_station_failure_api_error(hass):
    """Test station validation failure when API error occurs."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError())

    client = BusNearbyApiClient(session=mock_session)
    result = await client.validate_station("24068")

    # Should return False instead of raising exception
    assert result is False


@pytest.mark.asyncio
async def test_validate_station_12664_specific(hass):
    """Test validation of specific station 12664 from user report.

    This is the regression test for the reported bug.
    """
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[
            {
                "stop_id": "12664",
                "name": "Station 12664",
                "city": "Test City",
            }
        ]
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.validate_station("12664")

    assert result is True


# ============================================================================
# TRAIN ROUTES ENDPOINT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_train_routes_basic(hass):
    """Test basic train routes endpoint functionality."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value={
            "plan": {
                "itineraries": [
                    {
                        "duration": 3600,
                        "startTime": 1640000000000,
                        "endTime": 1640003600000,
                        "legs": [
                            {
                                "mode": "RAIL",
                                "route": "Tel Aviv - Jerusalem",
                                "from": {"name": "Tel Aviv HaHagana"},
                                "to": {"name": "Jerusalem Biblical Zoo"},
                            }
                        ],
                    }
                ]
            }
        }
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.get_train_routes("3600", "2800")

    assert isinstance(result, list)
    assert len(result) == 1
    assert "duration" in result[0]
    assert "legs" in result[0]


@pytest.mark.asyncio
async def test_get_train_routes_station_formatting(hass):
    """Test that train station IDs are properly formatted."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"plan": {"itineraries": []}})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    await client.get_train_routes("3600", "2800")

    # Verify URL was called with formatted station IDs
    call_args = mock_session.get.call_args
    params = call_args[1]["params"]
    assert params["fromPlace"] == "1:3600"
    assert params["toPlace"] == "1:2800"


@pytest.mark.asyncio
async def test_get_train_routes_invalid_response(hass):
    """Test handling of invalid train routes response."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"error": "Invalid"})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    # Should handle missing 'plan' gracefully
    result = await client.get_train_routes("3600", "2800")
    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================================
# CLIENT LIFECYCLE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_api_client_context_manager(hass):
    """Test API client as async context manager."""
    async with BusNearbyApiClient() as client:
        assert client._session is not None
        assert client._own_session is True


@pytest.mark.asyncio
async def test_api_client_with_provided_session(hass):
    """Test API client with externally provided session."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = BusNearbyApiClient(session=mock_session)

    assert client._session == mock_session
    assert client._own_session is False


@pytest.mark.asyncio
async def test_api_client_close(hass):
    """Test API client close method."""
    client = BusNearbyApiClient()
    await client.__aenter__()

    assert client._session is not None

    await client.close()
    # Session should be closed (we can't easily verify, but no exception should occur)


# ============================================================================
# RETRY LOGIC TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_retry_logic_timeout(hass):
    """Test retry logic with timeout errors."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # Fail first 2 times, succeed on 3rd
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise asyncio.TimeoutError()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[{"stop_id": "24068", "name": "Test"}]
        )
        mock_response.raise_for_status = MagicMock()
        # Return an async context manager mock (don't call it with ())
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_response)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    mock_session.get = MagicMock(side_effect=side_effect)

    client = BusNearbyApiClient(session=mock_session)
    result = await client.search_station("24068")

    # Should succeed after retries
    assert len(result) == 1
    assert call_count == 3  # Retried twice


@pytest.mark.asyncio
async def test_retry_logic_max_retries_exceeded(hass):
    """Test that max retries are respected."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

    client = BusNearbyApiClient(session=mock_session)

    # Should raise after max retries
    with pytest.raises(ApiTimeoutError):
        await client.search_station("24068")

    # Verify it tried MAX_RETRIES + 1 times (initial + retries)
    # MAX_RETRIES = 3, so should be called 4 times total
    assert mock_session.get.call_count == 4


@pytest.mark.asyncio
async def test_retry_logic_connection_error(hass):
    """Test retry logic with connection errors."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # Fail first time, succeed second time
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise aiohttp.ClientError("Connection failed")

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[{"stop_id": "24068", "name": "Test"}]
        )
        mock_response.raise_for_status = MagicMock()
        # Return an async context manager mock (don't call it with ())
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_response)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    mock_session.get = MagicMock(side_effect=side_effect)

    client = BusNearbyApiClient(session=mock_session)
    result = await client.search_station("24068")

    # Should succeed after retry
    assert len(result) == 1
    assert call_count == 2  # Retried once


# ============================================================================
# LOCALE AND PARAMETER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_search_station_locale_parameter(hass):
    """Test that locale parameter is passed correctly."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[{"stop_id": "24068", "name": "ארלוזורוב"}]
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    await client.search_station("24068", locale="he")

    # Verify locale was passed in params
    call_args = mock_session.get.call_args
    assert call_args[1]["params"]["locale"] == "he"


@pytest.mark.asyncio
async def test_get_stop_times_parameters(hass):
    """Test that all parameters are passed correctly to get_stop_times."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"times": []})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    await client.get_stop_times("24068", number_of_departures=5, time_range=7200)

    # Verify parameters
    call_args = mock_session.get.call_args
    params = call_args[1]["params"]
    assert params["numberOfDepartures"] == 5
    assert params["timeRange"] == 7200
    assert "currentTime" in params
