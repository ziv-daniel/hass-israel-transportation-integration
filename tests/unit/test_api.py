"""Tests for the BusNearby API client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.silent_bus.api import (
    ApiConnectionError,
    ApiTimeoutError,
    BusNearbyApiClient,
    InvalidResponseError,
    StationNotFoundError,
)


@pytest.mark.asyncio
async def test_api_client_context_manager():
    """Test API client as context manager."""
    async with BusNearbyApiClient() as client:
        assert client._session is not None
        assert client._own_session is True


@pytest.mark.asyncio
async def test_api_client_with_session():
    """Test API client with provided session."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = BusNearbyApiClient(session=mock_session)

    assert client._session == mock_session
    assert client._own_session is False


@pytest.mark.asyncio
async def test_search_station_success():
    """Test successful station search."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[
            {
                "stop_id": "24068",
                "name": "Arlozorov Terminal",
                "city": "Tel Aviv",
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

    assert len(result) == 1
    assert result[0]["stop_id"] == "24068"
    assert result[0]["name"] == "Arlozorov Terminal"


@pytest.mark.asyncio
async def test_search_station_not_found():
    """Test station search with no results."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=[])
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    with pytest.raises(StationNotFoundError):
        await client.search_station("99999")


@pytest.mark.asyncio
async def test_get_stop_times_success():
    """Test successful stop times retrieval."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value={
            "times": [
                {
                    "routeShortName": "249",
                    "serviceDay": 1640000000,
                    "realtimeArrival": 1000,
                    "realtime": True,
                }
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

    assert len(result) == 1
    assert result[0]["routeShortName"] == "249"


@pytest.mark.asyncio
async def test_get_stop_times_with_filter():
    """Test stop times retrieval with line filter."""
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
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)
    result = await client.get_stop_times("24068", bus_lines=["249"])

    assert len(result) == 1
    assert result[0]["routeShortName"] == "249"


@pytest.mark.asyncio
async def test_get_stop_times_invalid_response():
    """Test stop times with invalid response format."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"invalid": "data"})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    )

    client = BusNearbyApiClient(session=mock_session)

    with pytest.raises(InvalidResponseError):
        await client.get_stop_times("24068")


@pytest.mark.asyncio
async def test_api_timeout_with_retry():
    """Test API timeout with retry logic."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

    client = BusNearbyApiClient(session=mock_session)

    with pytest.raises(ApiTimeoutError):
        await client.get_stop_times("24068")


@pytest.mark.asyncio
async def test_api_connection_error():
    """Test API connection error."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError())

    client = BusNearbyApiClient(session=mock_session)

    with pytest.raises(ApiConnectionError):
        await client.get_stop_times("24068")


@pytest.mark.asyncio
async def test_validate_station_success():
    """Test successful station validation."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value=[
            {
                "stop_id": "24068",
                "name": "Arlozorov Terminal",
                "city": "Tel Aviv",
            }
        ]
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
async def test_validate_station_failure():
    """Test failed station validation."""
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
async def test_stop_id_formatting():
    """Test that stop_id is properly formatted with '1:' prefix."""
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"times": []})
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_get = AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
    mock_session.get = MagicMock(return_value=mock_get)

    client = BusNearbyApiClient(session=mock_session)
    await client.get_stop_times("24068")

    # Check that the URL contains the formatted stop_id
    call_args = mock_session.get.call_args
    assert "1:24068" in call_args[0][0]
