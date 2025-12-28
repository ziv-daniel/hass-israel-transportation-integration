"""Tests for bus.gov.il API client."""

from unittest.mock import MagicMock

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
