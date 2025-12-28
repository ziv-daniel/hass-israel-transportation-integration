"""API client for BusNearby."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout

from .const import (
    API_BASE_URL,
    API_SEARCH_URL,
    API_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class BusNearbyApiError(Exception):
    """Base exception for BusNearby API errors."""


class StationNotFoundError(BusNearbyApiError):
    """Exception raised when station is not found."""


class ApiConnectionError(BusNearbyApiError):
    """Exception raised when connection to API fails."""


class ApiTimeoutError(BusNearbyApiError):
    """Exception raised when API request times out."""


class InvalidResponseError(BusNearbyApiError):
    """Exception raised when API returns invalid response."""


class BusNearbyApiClient:
    """API client for BusNearby service."""

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
            "Referer": "https://app.busnearby.co.il",
        }

    async def __aenter__(self) -> BusNearbyApiClient:
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

    async def _make_request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic.

        Args:
            url: URL to request
            params: Query parameters
            retry_count: Current retry attempt

        Returns:
            JSON response as dictionary

        Raises:
            ApiConnectionError: If connection fails
            ApiTimeoutError: If request times out
            InvalidResponseError: If response is invalid
        """
        if not self._session:
            raise ApiConnectionError("Session not initialized")

        try:
            timeout = ClientTimeout(total=API_TIMEOUT)
            async with self._session.get(
                url,
                params=params,
                headers=self._headers,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data

        except asyncio.TimeoutError as err:
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY * (2**retry_count)
                _LOGGER.warning(
                    "Request timeout, retrying in %s seconds (attempt %s/%s)",
                    delay,
                    retry_count + 1,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                return await self._make_request(url, params, retry_count + 1)
            raise ApiTimeoutError(
                f"Request timed out after {MAX_RETRIES} retries"
            ) from err

        except ClientError as err:
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY * (2**retry_count)
                _LOGGER.warning(
                    "Connection error, retrying in %s seconds (attempt %s/%s)",
                    delay,
                    retry_count + 1,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                return await self._make_request(url, params, retry_count + 1)
            raise ApiConnectionError(f"Failed to connect to API: {err}") from err

        except Exception as err:
            raise InvalidResponseError(f"Invalid response from API: {err}") from err

    def _normalize_pattern_response(
        self, data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize pattern-based API response to standard format.

        The API sometimes returns data in a pattern-based format:
        [{"pattern": {"route": {...}}, "stoptimes": [...]}, ...]

        This normalizes it to the expected format:
        [{"routeShortName": "249", "serviceDay": ..., "realtimeArrival": ...}, ...]

        Args:
            data: List of pattern objects from API

        Returns:
            List of normalized arrival dictionaries
        """
        normalized: list[dict[str, Any]] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            # Extract route info from pattern
            pattern = item.get("pattern", {})
            route = pattern.get("route", {})
            route_short_name = route.get("shortName", "")

            # Get stoptimes from the item
            stoptimes = item.get("stoptimes", [])
            if not stoptimes and "times" in item:
                stoptimes = item.get("times", [])

            # If no stoptimes found, try to extract from item directly
            # (sometimes the item itself contains the arrival info)
            if not stoptimes:
                # Check if item has arrival time fields directly
                if "realtimeArrival" in item or "scheduledArrival" in item:
                    stoptimes = [item]

            for stoptime in stoptimes:
                if not isinstance(stoptime, dict):
                    continue

                arrival_entry = {
                    "routeShortName": route_short_name
                    or stoptime.get("routeShortName", ""),
                    "serviceDay": stoptime.get("serviceDay", 0),
                    "realtimeArrival": stoptime.get("realtimeArrival", 0),
                    "scheduledArrival": stoptime.get("scheduledArrival", 0),
                    "realtime": stoptime.get("realtime", False),
                    "headsign": stoptime.get("headsign", "")
                    or stoptime.get("tripHeadsign", "")
                    or pattern.get("headsign", ""),
                }

                # Only add if we have a valid route name
                if arrival_entry["routeShortName"]:
                    normalized.append(arrival_entry)

        _LOGGER.debug("Normalized %d arrivals from pattern response", len(normalized))
        return normalized

    async def search_station(
        self, query: str, locale: str = "he"
    ) -> list[dict[str, Any]]:
        """Search for a station by name or ID.

        Args:
            query: Station name or ID to search for
            locale: Language locale (default: "he")

        Returns:
            List of station dictionaries containing:
                - stop_id: Station ID
                - name: Station name
                - city: City name (optional)
                - lat: Latitude (optional)
                - lon: Longitude (optional)

        Raises:
            StationNotFoundError: If no stations found
            ApiConnectionError: If connection fails
        """
        _LOGGER.debug("Searching for station: %s", query)

        params = {
            "query": query,
            "locale": locale,
        }

        try:
            data = await self._make_request(API_SEARCH_URL, params)

            if not isinstance(data, list):
                raise InvalidResponseError("Expected list response from search")

            if not data:
                raise StationNotFoundError(f"No stations found for query: {query}")

            _LOGGER.debug("Found %s stations", len(data))
            return data

        except BusNearbyApiError:
            raise
        except Exception as err:
            raise InvalidResponseError(
                f"Failed to parse search results: {err}"
            ) from err

    async def get_stop_times(
        self,
        stop_id: str,
        bus_lines: list[str] | None = None,
        number_of_departures: int = 1,
        time_range: int = 86400,
    ) -> list[dict[str, Any]]:
        """Get real-time bus arrival times for a station.

        Args:
            stop_id: Station ID
            bus_lines: Optional list of bus line numbers to filter
            number_of_departures: Number of departures to return per line
            time_range: Time range in seconds (default: 86400 = 24 hours)

        Returns:
            List of arrival dictionaries containing:
                - routeShortName: Bus line number
                - serviceDay: Service day timestamp
                - realtimeArrival: Real-time arrival timestamp
                - scheduledArrival: Scheduled arrival timestamp
                - realtime: Boolean indicating if data is real-time
                - headsign: Bus direction/destination (optional)

        Raises:
            ApiConnectionError: If connection fails
            InvalidResponseError: If response format is invalid
        """
        _LOGGER.debug(
            "Getting stop times for station %s, lines: %s", stop_id, bus_lines
        )

        # Ensure stop_id has the correct format (prefix with "1:" if not present)
        if not stop_id.startswith("1:"):
            formatted_stop_id = f"1:{stop_id}"
        else:
            formatted_stop_id = stop_id

        url = f"{API_BASE_URL}/directions/index/stops/{formatted_stop_id}/stoptimes"

        params = {
            "numberOfDepartures": number_of_departures,
            "timeRange": time_range,
            "currentTime": int(datetime.now().timestamp()),
        }

        try:
            data = await self._make_request(url, params)

            _LOGGER.debug(
                "Raw API response for station %s: type=%s, data=%s",
                stop_id,
                type(data).__name__,
                str(data)[:500] if data else "None",
            )

            # Handle both response formats:
            # 1. Dictionary with "times" key: {"times": [...]}
            # 2. Direct list of pattern/stoptimes: [{pattern: {...}, stoptimes: [...]}, ...]
            if isinstance(data, list):
                # API returned pattern-based list format
                _LOGGER.debug(
                    "Station %s returned direct list format with %d items",
                    stop_id,
                    len(data),
                )
                arrivals = self._normalize_pattern_response(data)
                _LOGGER.debug(
                    "Normalized arrivals for station %s: %d items, lines: %s",
                    stop_id,
                    len(arrivals),
                    list(set(a.get("routeShortName", "") for a in arrivals)),
                )
            elif isinstance(data, dict):
                # API returned dictionary format
                if "times" not in data:
                    _LOGGER.debug(
                        "Station %s has no scheduled times (no service or no routes). Keys in response: %s",
                        stop_id,
                        list(data.keys()) if data else "None",
                    )
                    return []
                arrivals = data["times"]
                if not isinstance(arrivals, list):
                    raise InvalidResponseError(
                        "Invalid response format: 'times' is not a list"
                    )
                _LOGGER.debug(
                    "Dict format arrivals for station %s: %d items, lines: %s",
                    stop_id,
                    len(arrivals),
                    list(set(a.get("routeShortName", "") for a in arrivals if isinstance(a, dict))),
                )
            else:
                response_preview = str(data)[:200] if data else "empty/null"
                _LOGGER.error(
                    "Invalid API response for station %s: expected dict or list, got %s. Response: %s",
                    stop_id,
                    type(data).__name__,
                    response_preview,
                )
                raise InvalidResponseError(
                    f"Invalid response format: expected dictionary or list, got {type(data).__name__}"
                )

            # Filter by bus lines if specified
            if bus_lines:
                arrivals = [
                    arrival
                    for arrival in arrivals
                    if arrival.get("routeShortName") in bus_lines
                ]
                _LOGGER.debug(
                    "Filtered to %s arrivals for lines %s", len(arrivals), bus_lines
                )

            _LOGGER.debug("Retrieved %s arrivals", len(arrivals))
            return arrivals

        except BusNearbyApiError:
            raise
        except Exception as err:
            raise InvalidResponseError(f"Failed to parse stop times: {err}") from err

    async def validate_station(self, station_id: str) -> bool:
        """Validate that a station ID exists and is accessible.

        Args:
            station_id: Station ID to validate

        Returns:
            True if station is valid and accessible
        """
        try:
            # Use search endpoint for validation (better coverage)
            result = await self.search_station(station_id)
            return result is not None and len(result) > 0
        except BusNearbyApiError:
            return False

    async def validate_station_api_response(
        self, station_id: str
    ) -> tuple[bool, str]:
        """Validate that station returns valid API response format.

        This method tests the actual stop times endpoint to ensure the station
        returns data in the expected format. Use this during setup to fail early
        if a station has API compatibility issues.

        Args:
            station_id: Station ID to validate

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        try:
            await self.get_stop_times(station_id, number_of_departures=1)
            return True, ""
        except InvalidResponseError as err:
            return False, str(err)
        except BusNearbyApiError as err:
            return False, str(err)

    async def validate_train_route_api_response(
        self, from_station: str, to_station: str
    ) -> tuple[bool, str]:
        """Validate that train route returns valid API response format.

        This method tests the train routes endpoint to ensure the stations
        return data in the expected format. Use this during setup to fail early
        if a route has API compatibility issues.

        Args:
            from_station: Origin station ID
            to_station: Destination station ID

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        try:
            await self.get_train_routes(from_station, to_station, number_of_routes=1)
            return True, ""
        except InvalidResponseError as err:
            return False, str(err)
        except BusNearbyApiError as err:
            return False, str(err)

    async def get_train_routes(
        self,
        from_station: str,
        to_station: str,
        number_of_routes: int = 3,
    ) -> list[dict[str, Any]]:
        """Get train routes between two stations.

        Args:
            from_station: Origin station ID
            to_station: Destination station ID
            number_of_routes: Number of route options to return

        Returns:
            List of route dictionaries containing departure times and details

        Raises:
            ApiConnectionError: If connection fails
            InvalidResponseError: If response format is invalid
        """
        _LOGGER.debug("Getting train routes from %s to %s", from_station, to_station)

        # Format station IDs
        if not from_station.startswith("1:"):
            from_station = f"1:{from_station}"
        if not to_station.startswith("1:"):
            to_station = f"1:{to_station}"

        # Use the plan endpoint for routes
        url = f"{API_BASE_URL}/directions/index/plan"

        params = {
            "fromPlace": from_station,
            "toPlace": to_station,
            "numItineraries": number_of_routes,
            "mode": "TRANSIT,WALK",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "arriveBy": "false",
        }

        try:
            data = await self._make_request(url, params)

            if not isinstance(data, dict):
                raise InvalidResponseError("Invalid response format: expected dict")

            # Extract itineraries
            plan = data.get("plan", {})
            itineraries = plan.get("itineraries", [])

            if not isinstance(itineraries, list):
                raise InvalidResponseError(
                    "Invalid response format: 'itineraries' is not a list"
                )

            _LOGGER.debug("Retrieved %s train routes", len(itineraries))
            return itineraries

        except BusNearbyApiError:
            raise
        except Exception as err:
            raise InvalidResponseError(f"Failed to parse train routes: {err}") from err
