"""Tests for bus.gov.il API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.silent_bus.gov_api import GovApiClient


class TestGovApiClientInit:
    """Test GovApiClient initialization."""

    def test_init_with_session(self):
        """Test client initializes with provided session."""
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        client = GovApiClient(mock_session)
        assert client._session == mock_session
        assert client._own_session is False

    def test_init_without_session(self):
        """Test client initializes without session."""
        client = GovApiClient()
        assert client._session is None
        assert client._own_session is True


class TestGetStation:
    """Test get_station method."""

    @pytest.mark.asyncio
    async def test_get_station_valid(self):
        """Test getting a valid station."""
        mock_response = {
            "Id": 0,
            "Name": "אלי מויאל/דוד המלך",
            "Longitude": 34.596388999999995,
            "Latitude": 31.540779999999998,
            "Makat": 12665,
        }

        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.get_station("12665")

            assert result["Name"] == "אלי מויאל/דוד המלך"
            assert result["Makat"] == 12665
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_station_invalid(self):
        """Test getting an invalid station returns null values."""
        mock_response = {
            "Id": 0,
            "Name": None,
            "Longitude": 0.0,
            "Latitude": 0.0,
            "Makat": 0,
        }

        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.get_station("99999")

            assert result["Name"] is None
            assert result["Makat"] == 0


class TestValidateStation:
    """Test validate_station method."""

    @pytest.mark.asyncio
    async def test_validate_station_valid(self):
        """Test validating a valid station returns True."""
        mock_response = {
            "Name": "אלי מויאל/דוד המלך",
            "Makat": 12665,
        }

        with patch.object(GovApiClient, "get_station", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.validate_station("12665")

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_station_invalid_null_name(self):
        """Test validating station with null name returns False."""
        mock_response = {
            "Name": None,
            "Makat": 0,
        }

        with patch.object(GovApiClient, "get_station", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.validate_station("99999")

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_station_invalid_zero_makat(self):
        """Test validating station with zero makat returns False."""
        mock_response = {
            "Name": "Some Name",
            "Makat": 0,
        }

        with patch.object(GovApiClient, "get_station", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.validate_station("99999")

            assert result is False
