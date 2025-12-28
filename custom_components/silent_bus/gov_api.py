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

    async def _make_request(self, url: str) -> dict[str, Any] | list[Any]:
        """Make HTTP request to bus.gov.il API."""
        if not self._session:
            raise ApiConnectionError("Session not initialized")

        try:
            timeout = ClientTimeout(total=GOV_API_TIMEOUT)
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Failed to connect to API: {err}") from err
        except Exception as err:
            raise ApiConnectionError(f"Unexpected error: {err}") from err

    async def get_station(self, makat: str, locale: str = "he") -> dict[str, Any]:
        """Get station information by Makat."""
        url = f"{GOV_API_BASE_URL}/GetBusStopByMakat/{makat}/{locale}/false"
        _LOGGER.debug("Getting station info for Makat %s", makat)

        result = await self._make_request(url)
        if not isinstance(result, dict):
            return {"Name": None, "Makat": 0}

        return result

    async def validate_station(self, makat: str) -> bool:
        """Validate that a station exists.

        Args:
            makat: Station Makat to validate

        Returns:
            True if station exists and is valid, False otherwise
        """
        try:
            result = await self.get_station(makat)
            return result.get("Name") is not None and result.get("Makat", 0) > 0
        except GovApiError:
            return False
