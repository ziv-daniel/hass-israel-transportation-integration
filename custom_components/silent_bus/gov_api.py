"""API client for bus.gov.il (Israel Ministry of Transportation)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import ClientTimeout

from .const import GOV_API_BASE_URL, GOV_API_TIMEOUT, USER_AGENT

_LOGGER = logging.getLogger(__name__)


class GovApiError(Exception):
    """Base exception for bus.gov.il API errors."""


class StationNotFoundError(GovApiError):
    """Exception raised when station is not found."""


class ApiConnectionError(GovApiError):
    """Exception raised when connection to API fails."""


class ApiTimeoutError(GovApiError):
    """Exception raised when API request times out."""


class GovApiClient:
    """API client for bus.gov.il service."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the API client.

        Args:
            session: Optional aiohttp ClientSession. If not provided, a new one will be created.
        """
        self._session = session
        self._own_session = session is None
        self._headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://bus.gov.il/",
        }

    async def __aenter__(self) -> GovApiClient:
        """Async context manager entry."""
        if self._own_session:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self._own_session and self._session:
            await self._session.close()

    async def close(self) -> None:
        """Close the client session."""
        if self._own_session and self._session:
            await self._session.close()
