"""DataUpdateCoordinator for Israel Transportation integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from israelrailapi.api import GetRoutesApi

from .api import BusNearbyApiClient, BusNearbyApiError
from .gov_api import GovApiClient, RateLimitError
from .gtfs_loader import get_route_headsign
from .const import (
    APPROACHING_THRESHOLD,
    DEFAULT_MAX_ARRIVALS,
    DOMAIN,
    FAR_AWAY_THRESHOLD,
    MIN_SCAN_INTERVAL,
    NIGHT_HOUR_END,
    NIGHT_HOUR_START,
    TRANSPORT_TYPE_BUS,
    TRANSPORT_TYPE_TRAIN,
)

_LOGGER = logging.getLogger(__name__)


class SilentBusCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Israel Transportation data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api_client: Optional[BusNearbyApiClient] = None,  # Keep for trains
        gov_api_client: Optional[GovApiClient] = None,  # New for bus/light_rail
        update_interval: timedelta,
        config_entry=None,
        max_arrivals: int = DEFAULT_MAX_ARRIVALS,
        transport_type: str = TRANSPORT_TYPE_BUS,
        # Bus/Light Rail parameters
        station_id: Optional[str] = None,
        station_name: Optional[str] = None,
        bus_lines: Optional[list[str]] = None,
        # Train parameters
        from_station: Optional[str] = None,
        to_station: Optional[str] = None,
        from_station_name: Optional[str] = None,
        to_station_name: Optional[str] = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            api_client: BusNearby API client (for trains)
            gov_api_client: Government API client (for bus/light rail)
            update_interval: How often to update data
            config_entry: Config entry (optional, required for async_config_entry_first_refresh)
            max_arrivals: Maximum number of arrivals to track per line
            transport_type: Type of transport (bus, train, light_rail)
            station_id: Station ID to monitor (for bus/light rail)
            station_name: Station name for display (for bus/light rail)
            bus_lines: List of bus line numbers to track (for bus/light rail)
            from_station: Origin station ID (for trains)
            to_station: Destination station ID (for trains)
            from_station_name: Origin station name (for trains)
            to_station_name: Destination station name (for trains)
        """
        self.api_client = api_client
        self.gov_api_client = gov_api_client
        self.transport_type = transport_type
        self.max_arrivals = max_arrivals
        self._base_update_interval = update_interval

        # Bus/Light Rail attributes
        self.station_id = station_id
        self.station_name = station_name
        self.bus_lines = bus_lines

        # Train attributes
        self.from_station = from_station
        self.to_station = to_station
        self.from_station_name = from_station_name
        self.to_station_name = to_station_name

        # Display label for logging. Built from the config entry rather than
        # looked up in the GTFS index: that lookup read a ~5MB JSON file
        # synchronously on the event loop (HA flags it as a blocking call), and
        # it keyed on GTFS stop_id while station_id here is a stop_code, so it
        # rarely matched anyway.
        if station_id:
            self._station_display = (
                f"{station_name} [{station_id}]" if station_name else str(station_id)
            )
        else:
            self._station_display = None

        # GTFS direction cache for fallback when API doesn't provide direction
        self._gtfs_direction_cache: dict[tuple[str, str], Optional[str]] = {}

        # Generate unique coordinator name
        if transport_type == TRANSPORT_TYPE_TRAIN:
            coordinator_name = f"{DOMAIN}_{from_station}_{to_station}"
        else:
            coordinator_name = f"{DOMAIN}_{station_id}"

        # Build kwargs for super().__init__ - config_entry is only supported
        # in HA 2023.7+ (DataUpdateCoordinator gained the parameter later)
        init_kwargs: dict[str, Any] = {
            "name": coordinator_name,
            "update_interval": update_interval,
        }
        try:
            super().__init__(
                hass,
                _LOGGER,
                config_entry=config_entry,
                **init_kwargs,
            )
        except TypeError:
            # Older HA version without config_entry support
            super().__init__(
                hass,
                _LOGGER,
                **init_kwargs,
            )
            self.config_entry = config_entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Dictionary mapping line numbers/routes to arrival data

        Raises:
            UpdateFailed: If update fails
        """
        try:
            if self.transport_type == TRANSPORT_TYPE_TRAIN:
                # Fetch train routes using Israel Rail API
                _LOGGER.debug(
                    "Fetching train routes from %s to %s using Israel Rail API",
                    self.from_station,
                    self.to_station,
                )

                try:
                    # Query Israel Rail API directly (bypass buggy translate_station)
                    routes = await self.hass.async_add_executor_job(
                        self._query_rail_api,
                        self.from_station,
                        self.to_station,
                    )

                    # Process train routes
                    processed_data = self._process_rail_routes(routes)

                except Exception as err:
                    raise UpdateFailed(
                        f"Error fetching train data from Israel Rail API: {err}"
                    ) from err

            else:
                # Bus/Light Rail - use gov API if available, else BusNearby
                if self.gov_api_client:
                    processed_data = await self._fetch_gov_arrivals()
                else:
                    # Fallback to BusNearby (legacy)
                    _LOGGER.debug(
                        "Fetching data for %s, lines: %s",
                        self._station_display,
                        self.bus_lines,
                    )

                    arrivals = await self.api_client.get_stop_times(
                        self.station_id,
                        self.bus_lines,
                        number_of_departures=self.max_arrivals,
                    )

                    _LOGGER.debug(
                        "Received %d arrivals from API for %s",
                        len(arrivals) if arrivals else 0,
                        self._station_display,
                    )

                    processed_data = self._process_arrivals(arrivals)

                    _LOGGER.debug(
                        "Processed data for %s: lines found=%s, tracking lines=%s",
                        self._station_display,
                        list(processed_data.keys()) if processed_data else [],
                        self.bus_lines,
                    )

                    if not processed_data and arrivals:
                        _LOGGER.warning(
                            "%s: API returned %d arrivals but none matched tracked lines %s. "
                            "Available lines in response: %s",
                            self._station_display,
                            len(arrivals),
                            self.bus_lines,
                            list(set(a.get("routeShortName", "?") for a in arrivals)),
                        )
                    elif not processed_data and not arrivals:
                        _LOGGER.info(
                            "%s: No arrivals returned by API (station may have no service at this time)",
                            self._station_display,
                        )

            # Adjust update interval based on data
            self._adjust_update_interval(processed_data)

            _LOGGER.debug(
                "Successfully fetched data for %s items",
                len(processed_data),
            )

            return processed_data

        except RateLimitError as err:
            raise UpdateFailed(
                f"Rate limited by gov API. Retrying in {err.retry_after}s.",
            ) from err
        except BusNearbyApiError as err:
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching data: {err}") from err

    def _process_arrivals(self, arrivals: list[dict[str, Any]]) -> dict[str, Any]:
        """Process raw arrival data into structured format.

        Args:
            arrivals: Raw arrival data from API

        Returns:
            Dictionary mapping line numbers to processed arrival data
        """
        processed: dict[str, list[dict[str, Any]]] = {}
        now = dt_util.now()

        for arrival in arrivals:
            line_number = arrival.get("routeShortName")
            if not line_number:
                continue

            # Calculate arrival time
            service_day = arrival.get("serviceDay", 0)
            realtime_arrival = arrival.get(
                "realtimeArrival", arrival.get("scheduledArrival", 0)
            )

            # Convert to timezone-aware datetime
            arrival_timestamp = service_day + realtime_arrival
            arrival_time = dt_util.utc_from_timestamp(arrival_timestamp)
            arrival_time = dt_util.as_local(arrival_time)

            # Calculate minutes until arrival
            time_delta = arrival_time - now
            minutes_until = max(0, int(time_delta.total_seconds() / 60))

            # Check if this is real-time data
            is_realtime = arrival.get("realtime", False)

            # Get direction/headsign with GTFS fallback
            headsign = arrival.get("headsign", "").strip()
            trip_headsign = arrival.get("tripHeadsign", "").strip()
            direction = headsign or trip_headsign

            # Fallback chain: API → GTFS → Line number
            if not direction:
                cache_key = (self.station_id, line_number)
                if cache_key in self._gtfs_direction_cache:
                    direction = (
                        self._gtfs_direction_cache[cache_key] or f"Line {line_number}"
                    )
                else:
                    gtfs_direction = get_route_headsign(self.station_id, line_number)
                    self._gtfs_direction_cache[cache_key] = gtfs_direction
                    direction = gtfs_direction or f"Line {line_number}"

                    if gtfs_direction:
                        _LOGGER.debug(
                            "Station %s, line %s: Using GTFS fallback direction: %s",
                            self.station_id,
                            line_number,
                            direction,
                        )

            # Create processed arrival entry
            processed_arrival = {
                "arrival_time": arrival_time.isoformat(),
                "minutes_until": minutes_until,
                "is_realtime": is_realtime,
                "direction": direction,
            }

            # Add to line's arrival list
            if line_number not in processed:
                processed[line_number] = []

            processed[line_number].append(processed_arrival)

        # Sort arrivals by time for each line
        for line_number in processed:
            processed[line_number].sort(key=lambda x: x["minutes_until"])

        return processed

    def _query_rail_api(self, from_station: str, to_station: str) -> list:
        """Query Israel Rail API directly with station IDs.

        This bypasses the buggy translate_station function in israelrailapi.

        Args:
            from_station: Origin station ID (e.g., '9600' for Sderot)
            to_station: Destination station ID (e.g., '3700' for Tel Aviv Savidor)

        Returns:
            List of TrainRoute objects
        """
        import time

        api = GetRoutesApi()
        today = time.strftime("%Y-%m-%d")
        current_hour = time.strftime("%H:%M")

        return api.request(
            fromStation=from_station,
            toStation=to_station,
            date=today,
            hour=current_hour,
        )

    def _process_rail_routes(self, routes: list) -> dict[str, Any]:
        """Process train routes from Israel Rail API.

        Args:
            routes: List of TrainRoute objects from israelrailapi

        Returns:
            Dictionary with route key mapping to processed departure data
        """
        processed: dict[str, list[dict[str, Any]]] = {}
        now = dt_util.now()
        route_key = "train_route"

        # Iterate every returned route, not just the first max_arrivals: the
        # API can put an already-departed train ahead of the real upcoming
        # ones (see the skip below), so slicing before filtering could drop
        # a genuine future train in its place. Truncate after filtering.
        for idx, route in enumerate(routes):
            # Get trains from route
            trains = route.trains if hasattr(route, "trains") else []
            if not trains:
                continue

            first_train = trains[0]

            # Parse departure time (ISO format with timezone: "2025-12-29T16:12:00+02:00")
            dep_time_str = (
                first_train.departure if hasattr(first_train, "departure") else None
            )
            if not dep_time_str:
                continue

            try:
                # Parse ISO datetime string with timezone awareness
                departure_time = dt_util.parse_datetime(dep_time_str)
                if departure_time is None:
                    # Fallback for non-standard formats
                    departure_time = datetime.fromisoformat(dep_time_str)
                if departure_time.tzinfo is None:
                    departure_time = dt_util.as_local(departure_time)
            except (ValueError, TypeError):
                continue

            # Calculate minutes until departure. The Rail API's searchTrain
            # sometimes returns a train that has already left alongside the
            # upcoming ones — observed up to 26 minutes in the past — rather
            # than strictly filtering to future departures. Clamping that to
            # 0 made an already-departed train sort as "next" ahead of the
            # real next train, so skip it instead of keeping a false 0m.
            time_delta = departure_time - now
            if time_delta.total_seconds() < 0:
                continue
            minutes_until = int(time_delta.total_seconds() / 60)

            # Get platform and train number from raw data
            platform = first_train.platform if hasattr(first_train, "platform") else ""
            train_number = (
                first_train.data.get("trainNumber", "")
                if hasattr(first_train, "data")
                else ""
            )

            # Calculate total duration
            duration_minutes = 0
            last_train = trains[-1]
            arr_time_str = (
                last_train.arrival if hasattr(last_train, "arrival") else None
            )
            if arr_time_str:
                try:
                    # Parse arrival time with timezone awareness
                    arrival_time = dt_util.parse_datetime(arr_time_str)
                    if arrival_time is None:
                        # Fallback for non-standard formats
                        arrival_time = datetime.fromisoformat(arr_time_str)
                    if arrival_time.tzinfo is None:
                        arrival_time = dt_util.as_local(arrival_time)

                    duration_minutes = int(
                        (arrival_time - departure_time).total_seconds() / 60
                    )
                except (ValueError, TypeError):
                    pass

            # Build direction string from destination station IDs
            # Note: dst contains station ID, not name
            direction = self.to_station_name or ""

            processed_route = {
                "arrival_time": departure_time.isoformat(),
                "minutes_until": minutes_until,
                "duration_minutes": duration_minutes,
                "is_realtime": False,  # Israel Rail API doesn't provide real-time
                "direction": direction,
                "platform": platform,
                "train_number": str(train_number),
                "route_index": idx,
                "transfers": len(trains) - 1,
            }

            if route_key not in processed:
                processed[route_key] = []

            processed[route_key].append(processed_route)

        # Sort by departure time and cap at the configured number of arrivals
        if route_key in processed:
            processed[route_key].sort(key=lambda x: x["minutes_until"])
            processed[route_key] = processed[route_key][: self.max_arrivals]

        return processed

    async def _fetch_gov_arrivals(self) -> dict[str, Any]:
        """Fetch arrivals from bus.gov.il API.

        Returns:
            Dictionary mapping line numbers to processed arrival data
        """
        if not self.gov_api_client:
            raise UpdateFailed("Gov API client not initialized")

        _LOGGER.debug(
            "Fetching gov API data for %s, lines: %s",
            self._station_display,
            self.bus_lines,
        )

        arrivals = await self.gov_api_client.get_arrivals(
            self.station_id,
            lines=self.bus_lines,
        )

        _LOGGER.debug(
            "Received %d arrivals from gov API for %s",
            len(arrivals) if arrivals else 0,
            self._station_display,
        )

        return self._process_gov_arrivals(arrivals)

    def _process_gov_arrivals(self, arrivals: list[dict[str, Any]]) -> dict[str, Any]:
        """Process arrivals from bus.gov.il into sensor format.

        Args:
            arrivals: Raw arrivals from gov API

        Returns:
            Dictionary mapping line numbers to processed arrival data
        """
        processed: dict[str, list[dict[str, Any]]] = {}

        for arrival in arrivals:
            line_number = arrival.get("line")
            if not line_number:
                continue

            line_times = arrival.get("arrivals") or []

            direction = (arrival.get("direction") or "").strip()
            operator = arrival.get("operator") or ""

            # Fallback chain: API → GTFS → Line number
            if not direction:
                # Check cache first
                cache_key = (self.station_id, line_number)
                if cache_key in self._gtfs_direction_cache:
                    direction = (
                        self._gtfs_direction_cache[cache_key] or f"Line {line_number}"
                    )
                else:
                    # Try GTFS fallback
                    gtfs_direction = get_route_headsign(self.station_id, line_number)
                    self._gtfs_direction_cache[cache_key] = gtfs_direction

                    if gtfs_direction:
                        direction = gtfs_direction
                        _LOGGER.debug(
                            "Station %s, line %s: Using GTFS fallback direction: %s",
                            self.station_id,
                            line_number,
                            direction,
                        )
                    else:
                        direction = f"Line {line_number}"
                        _LOGGER.debug(
                            "Station %s, line %s: No GTFS data, using line number fallback",
                            self.station_id,
                            line_number,
                        )

            # Create arrival entries for each upcoming arrival
            now = dt_util.now()
            line_arrivals = []
            for stop_time in line_times:
                try:
                    minutes = int(stop_time["minutes_until"])
                except (KeyError, TypeError, ValueError):
                    # Upstream occasionally returns nulls or non-numeric values;
                    # drop the entry rather than failing the whole update.
                    continue
                # Derive the timestamp locally so it is always timezone-aware —
                # the API reports a naive local time.
                arrival_time = now + timedelta(minutes=minutes)
                line_arrivals.append(
                    {
                        "arrival_time": arrival_time.isoformat(),
                        "minutes_until": minutes,
                        "is_realtime": bool(stop_time.get("is_realtime")),
                        "direction": direction,
                        "operator": operator,
                    }
                )

            if line_number not in processed:
                processed[line_number] = []

            processed[line_number].extend(line_arrivals)

        # Sort arrivals by time for each line
        for line_number in processed:
            processed[line_number].sort(key=lambda x: x["minutes_until"])
            # Limit to max_arrivals
            processed[line_number] = processed[line_number][: self.max_arrivals]

        return processed

    def _adjust_update_interval(self, data: dict[str, Any]) -> None:
        """Dynamically adjust update interval based on data.

        Adjusts update frequency based on:
        - Time of day (night hours = slower updates)
        - Proximity of next bus (approaching = faster updates)
        - Presence of data (no upcoming buses = slower updates)

        Args:
            data: Processed arrival data
        """
        current_hour = dt_util.now().hour

        # Check if it's night time
        is_night = NIGHT_HOUR_START <= current_hour or current_hour < NIGHT_HOUR_END

        # Find the soonest arriving bus
        min_minutes = float("inf")
        for line_data in data.values():
            if line_data:
                min_minutes = min(min_minutes, line_data[0]["minutes_until"])

        # Determine appropriate interval
        if min_minutes == float("inf"):
            # No upcoming buses
            new_interval = timedelta(minutes=5)
        elif min_minutes < APPROACHING_THRESHOLD:
            # Bus is approaching, update more frequently
            new_interval = MIN_SCAN_INTERVAL
        elif min_minutes > FAR_AWAY_THRESHOLD:
            # Bus is far away
            new_interval = timedelta(minutes=5) if is_night else timedelta(minutes=2)
        else:
            # Normal interval
            new_interval = self._base_update_interval

        # Only update if interval changed significantly (avoid constant changes)
        if abs((new_interval - self.update_interval).total_seconds()) > 5:
            _LOGGER.debug(
                "Adjusting update interval from %s to %s (next bus in %s min)",
                self.update_interval,
                new_interval,
                min_minutes if min_minutes != float("inf") else "N/A",
            )
            self.update_interval = new_interval

    def get_line_data(self, line_number: str) -> Optional[list[dict[str, Any]]]:
        """Get arrival data for a specific line.

        Args:
            line_number: Bus line number

        Returns:
            List of arrivals for the line, or None if no data
        """
        if not self.data:
            return None
        return self.data.get(line_number)

    def get_next_arrival(self, line_number: str) -> Optional[dict[str, Any]]:
        """Get next arrival for a specific line.

        Args:
            line_number: Bus line number

        Returns:
            Next arrival data, or None if no upcoming arrivals
        """
        line_data = self.get_line_data(line_number)
        if line_data:
            return line_data[0]
        return None
