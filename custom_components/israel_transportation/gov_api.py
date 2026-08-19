"""API client for the Israel Ministry of Transportation bus API.

The public bus.gov.il portal was rebuilt and its old ``/WebApi/api/passengerinfo``
endpoints were removed — every path under it now serves the site's SPA shell as
HTML. This client targets the API the current MOT route planner
(``route.bus.gov.il``) actually calls, which is anonymous and needs no API key.

Stops are addressed by their *stop code* (makat) — the number printed on the stop
sign. Note this is NOT the GTFS ``stop_id``; the API exposes both and they differ.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

import aiohttp
from aiohttp import ClientTimeout

from .const import (
    GOV_API_TIMEOUT,
    MOT_API_BASE_URL,
    MOT_API_LOCALE,
    MOT_MAX_CONCURRENT_REQUESTS,
    MOT_MAX_ROUTES_PER_POLL,
    MOT_PLANNER_BASE_URL,
    MOT_ROUTES_CACHE_TTL,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

# Service days are defined in Israeli local time regardless of where HA runs.
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class GovApiError(Exception):
    """Base exception for MOT API errors."""


class StationNotFoundError(GovApiError):
    """Exception raised when station is not found."""


class ApiConnectionError(GovApiError):
    """Exception raised when connection to API fails."""


class ApiTimeoutError(ApiConnectionError):
    """Exception raised when API request times out.

    Subclasses ApiConnectionError so callers that handle "could not reach the
    API" catch timeouts too — the config flow reports them as cannot_connect
    rather than as an unknown error.
    """


class InvalidMakatError(GovApiError):
    """Exception raised when makat is not a valid numeric station code."""


class InvalidResponseError(GovApiError):
    """Exception raised when the API returns something that is not its JSON.

    This is the signature of upstream breakage (an endpoint being removed and the
    request falling through to a web page) as opposed to a network failure, so it
    is deliberately distinct from ApiConnectionError.
    """


class RateLimitError(GovApiError):
    """Exception raised when API returns HTTP 429 Too Many Requests."""

    def __init__(self, retry_after: float = 60.0) -> None:
        """Initialize with retry_after seconds."""
        super().__init__(f"Rate limited. Retry after {retry_after}s.")
        self.retry_after = retry_after


def validate_makat(makat: str) -> str:
    """Validate that makat is a non-empty numeric string.

    Args:
        makat: Station makat (stop code) to validate.

    Returns:
        The validated makat string.

    Raises:
        InvalidMakatError: If makat is not a valid numeric string.
    """
    makat = str(makat).strip()
    if not makat or not makat.isascii() or not makat.isdigit():
        raise InvalidMakatError(
            f"Invalid makat {makat!r}: must be a non-empty numeric string."
        )
    return str(makat).strip()


class GovApiClient:
    """API client for the MOT bus API (api.bus.gov.il)."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        """Initialize the API client.

        Args:
            session: Optional aiohttp ClientSession. If not provided, a new one will be created.
        """
        self._session = session
        self._own_session = session is None
        self._headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://route.bus.gov.il/",
            "Origin": "https://route.bus.gov.il",
        }
        # Which routes serve a stop changes rarely, but arrival times need the
        # route descriptors from it on every poll — so cache it per stop.
        self._routes_cache: dict[
            tuple[str, str], tuple[float, list[dict[str, Any]]]
        ] = {}

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

    async def _make_request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        base_url: str = MOT_API_BASE_URL,
        locale: str = MOT_API_LOCALE,
    ) -> Any:
        """Make a GET request to the MOT API and return the unwrapped ``data`` payload.

        Args:
            path: Endpoint path, e.g. ``Stops/GetStopByCode``.
            params: Query string parameters.
            base_url: Which MOT service to talk to.
            locale: Language segment of the URL (``he``/``en``/``ar``).

        Returns:
            The value of the response's ``data`` key.

        Raises:
            RateLimitError: On HTTP 429.
            InvalidResponseError: If the response is not the API's JSON.
            ApiConnectionError: If the request fails at the network level.
        """
        if not self._session:
            raise ApiConnectionError("Session not initialized")

        url = f"{base_url}/{locale}/{path}"

        try:
            timeout = ClientTimeout(total=GOV_API_TIMEOUT)
            async with self._session.get(
                url,
                params=params,
                headers=self._headers,
                timeout=timeout,
            ) as response:
                if response.status == 429:
                    retry_after = float(response.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after=retry_after)
                response.raise_for_status()

                # An endpoint that has been removed upstream typically still
                # answers 200 — with a web page. Say so explicitly rather than
                # letting the JSON decode fail as a generic connection error.
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    body = (await response.text())[:200]
                    _LOGGER.warning(
                        "MOT API %s returned non-JSON content-type %r. "
                        "The endpoint may have been changed or removed upstream. "
                        "First bytes of body: %r",
                        url,
                        content_type,
                        body,
                    )
                    raise InvalidResponseError(
                        f"Expected JSON from {url}, got content-type {content_type!r}"
                    )

                payload = await response.json()

        except (RateLimitError, InvalidResponseError):
            raise
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout contacting {url}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Failed to connect to API: {err}") from err
        except Exception as err:  # pylint: disable=broad-except
            raise ApiConnectionError(f"Unexpected error: {err}") from err

        if not isinstance(payload, dict):
            raise InvalidResponseError(
                f"Unexpected response shape from {url}: {type(payload).__name__}"
            )

        if payload.get("success") is False:
            message = payload.get("message") or "no message"
            raise InvalidResponseError(f"API reported failure for {url}: {message}")

        return payload.get("data")

    async def get_station(
        self, makat: str, locale: str = MOT_API_LOCALE
    ) -> dict[str, Any]:
        """Get station information by makat (stop code).

        The returned mapping keeps the ``Name``/``Makat`` keys the rest of the
        integration already checks, so callers need no changes.

        Args:
            makat: Station stop code.
            locale: Language for the station name.

        Returns:
            Dict with at least ``Name`` and ``Makat``. ``Name`` is None and
            ``Makat`` is 0 when the stop does not exist.
        """
        makat = validate_makat(makat)
        _LOGGER.debug("Getting station info for makat %s", makat)

        data = await self._make_request(
            "Stops/GetStopByCode", {"stopcode": makat}, locale=locale
        )

        if not isinstance(data, dict):
            return {"Name": None, "Makat": 0}

        name = data.get("name") or {}
        # Only the requested locale is usually populated; fall back across them.
        display_name = (
            name.get(locale) or name.get("he") or name.get("en") or name.get("ar")
        )

        return {
            "Name": display_name,
            "Makat": data.get("stopcode") or 0,
            "StopId": data.get("stopid"),
            "CityName": data.get("cityName"),
            "StreetName": data.get("streetName"),
            "Latitude": data.get("lat"),
            "Longitude": data.get("lng"),
        }

    async def validate_station(self, makat: str) -> bool:
        """Validate that a station exists.

        Args:
            makat: Station makat to validate

        Returns:
            True if station exists and is valid, False otherwise
        """
        try:
            result = await self.get_station(makat)
            return result.get("Name") is not None and result.get("Makat", 0) > 0
        except GovApiError:
            return False

    async def search_stations(
        self, search_term: str, locale: str = MOT_API_LOCALE
    ) -> list[dict[str, Any]]:
        """Search for stops by name, returning their stop codes.

        Used by the config flow so users can pick a stop without needing to know
        its number, and without relying on the bundled GTFS index (which is keyed
        by GTFS ``stop_id``, a different identifier).

        Args:
            search_term: Free-text station name.
            locale: Language for results.

        Returns:
            List of dicts with ``makat``, ``name``, ``city``, ``lat``, ``lon``.
        """
        if not search_term or not search_term.strip():
            return []

        data = await self._make_request(
            "AutoComplete/SearchStations",
            {"searchTerm": search_term.strip()},
            base_url=MOT_PLANNER_BASE_URL,
            locale=locale,
        )

        if not isinstance(data, list):
            return []

        results: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            stopcode = item.get("stopcode")
            if not stopcode:
                continue
            results.append(
                {
                    "makat": str(stopcode),
                    "name": item.get("name") or "",
                    "city": item.get("cityName") or "",
                    "lat": item.get("lat"),
                    "lon": item.get("lng"),
                }
            )
        return results

    async def _get_routes_at_stop(
        self, makat: str, locale: str = MOT_API_LOCALE
    ) -> list[dict[str, Any]]:
        """Get the routes serving a stop, with their descriptors and headsigns.

        Cached for MOT_ROUTES_CACHE_TTL — this is reference data, but every
        arrivals poll needs the route descriptors it returns.
        """
        cache_key = (makat, locale)
        cached = self._routes_cache.get(cache_key)
        if cached and (time.monotonic() - cached[0]) < MOT_ROUTES_CACHE_TTL:
            return cached[1]

        # The service day must be Israel-local. Asking for a past date returns
        # zero routes, so using UTC would blank every stop between midnight and
        # 02:00/03:00 local, when the UTC date is still yesterday.
        day = datetime.now(ISRAEL_TZ).replace(tzinfo=None).isoformat()
        data = await self._make_request(
            "Stops/RefreshStopTimesAtStop",
            {"stopCode": makat, "day": day},
            locale=locale,
        )

        routes: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for route in data.get("routesInStop") or []:
                if not isinstance(route, dict):
                    continue
                route_desc = route.get("routeDesc")
                line = route.get("routeName")
                if not route_desc or not line:
                    continue
                headsign = route.get("headsign") or {}
                if isinstance(headsign, dict):
                    direction = (
                        headsign.get(locale)
                        or headsign.get("he")
                        or headsign.get("en")
                        or ""
                    )
                else:
                    direction = str(headsign or "")
                routes.append(
                    {
                        "line": str(line),
                        "route_desc": route_desc,
                        "direction": direction,
                        "operator": route.get("agencyName") or "",
                    }
                )

        # Only cache a non-empty result. An empty list is usually transient — a
        # night-time gap or an upstream hiccup — and pinning it for the full TTL
        # would keep the stop blank for an hour after service resumed.
        if routes:
            self._routes_cache[cache_key] = (time.monotonic(), routes)
        return routes

    async def get_arrivals(
        self,
        makat: str,
        locale: str = MOT_API_LOCALE,
        lines: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get upcoming arrivals for a station.

        Args:
            makat: Station stop code.
            locale: Language for direction/operator text.
            lines: Optional list of line numbers to restrict the query to. Applied
                before fetching times, since times cost one request per route.

        Returns:
            List of dicts, one per route serving the stop::

                {
                    "line": "1א",
                    "direction": "אזור תעשייה",
                    "operator": "דן בדרום",
                    "route_desc": "39001-1-1",
                    "arrivals": [{"minutes_until": 4, "is_realtime": False}, ...],
                }
        """
        makat = validate_makat(makat)

        routes = await self._get_routes_at_stop(makat, locale=locale)
        if lines:
            wanted = {str(line).strip() for line in lines}
            available = {route["line"] for route in routes}
            routes = [route for route in routes if route["line"] in wanted]
            if available and not routes:
                # Line numbers are matched verbatim against upstream, and Hebrew
                # suffixes make near-misses easy ("1" vs "1א"). Without this the
                # user just gets permanently empty sensors and no explanation.
                _LOGGER.warning(
                    "None of the configured lines %s serve stop %s. "
                    "Lines available at this stop: %s",
                    sorted(wanted),
                    makat,
                    sorted(available),
                )

        _LOGGER.debug(
            "Fetching times for %d route(s) at makat %s (lines filter: %s)",
            len(routes),
            makat,
            lines,
        )

        if not routes:
            return []

        if not lines:
            # Busy interchanges serve dozens of routes (Tel Aviv Savidor has 53),
            # and times cost one request each. Without a line filter, cap the work
            # rather than firing a request storm at the API on every poll.
            if len(routes) > MOT_MAX_ROUTES_PER_POLL:
                _LOGGER.warning(
                    "Stop %s serves %d routes and no line filter is configured; "
                    "only the first %d will be polled. Configure the lines you "
                    "care about to see all of them.",
                    makat,
                    len(routes),
                    MOT_MAX_ROUTES_PER_POLL,
                )
                routes = routes[:MOT_MAX_ROUTES_PER_POLL]

        semaphore = asyncio.Semaphore(MOT_MAX_CONCURRENT_REQUESTS)

        async def fetch(route: dict[str, Any]) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._get_route_times(makat, route, locale)

        results = await asyncio.gather(
            *(fetch(route) for route in routes),
            return_exceptions=True,
        )

        arrivals: list[dict[str, Any]] = []
        failures: list[BaseException] = []
        for route, result in zip(routes, results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                failures.append(result)
                _LOGGER.debug(
                    "Failed to fetch times for line %s at makat %s: %s",
                    route["line"],
                    makat,
                    result,
                )
                continue
            if not result:
                continue
            arrivals.append({**route, "arrivals": result})

        # A rate limit must reach the coordinator so it can back off, rather than
        # being smoothed into "no buses" while we keep hammering the API.
        for failure in failures:
            if isinstance(failure, RateLimitError):
                raise failure

        # If every route failed, the stop does not have "no arrivals" — we simply
        # do not know. Report it, so the entity goes unavailable and the reason is
        # visible, instead of silently rendering an outage as an empty timetable.
        if failures and len(failures) == len(routes):
            _LOGGER.warning(
                "All %d route time lookups failed for makat %s; reporting the "
                "update as failed. First error: %s",
                len(routes),
                makat,
                failures[0],
            )
            raise failures[0]

        if failures:
            _LOGGER.warning(
                "%d of %d route time lookups failed for makat %s; "
                "returning partial results. First error: %s",
                len(failures),
                len(routes),
                makat,
                failures[0],
            )

        return arrivals

    async def _get_route_times(
        self, makat: str, route: dict[str, Any], locale: str
    ) -> list[dict[str, Any]]:
        """Get upcoming times for one route at one stop."""
        data = await self._make_request(
            "Calendar/GetRouteCalendarAtStopsByStopCodes",
            {"stopCodes": makat, "routeDesc": route["route_desc"]},
            locale=locale,
        )

        if not isinstance(data, dict):
            return []

        stop_data = data.get(str(makat))
        if not isinstance(stop_data, dict):
            return []

        times: list[dict[str, Any]] = []
        for stop_time in stop_data.get("stopTimes") or []:
            if not isinstance(stop_time, dict):
                continue
            minutes = stop_time.get("minutesToArrival")
            if minutes is None:
                continue
            try:
                minutes_until = int(round(float(minutes)))
            except (TypeError, ValueError):
                continue
            if minutes_until < 0:
                continue
            times.append(
                {
                    "minutes_until": minutes_until,
                    "is_realtime": bool(stop_time.get("isRealTime")),
                }
            )

        return times
