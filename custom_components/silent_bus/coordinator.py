"""DataUpdateCoordinator for Silent Bus integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BusNearbyApiClient, BusNearbyApiError
from .gov_api import GovApiClient
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
from .gtfs_loader import get_station_display_name

_LOGGER = logging.getLogger(__name__)


class SilentBusCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Silent Bus data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api_client: BusNearbyApiClient | None = None,  # Keep for trains
        gov_api_client: GovApiClient | None = None,  # New for bus/light_rail
        update_interval: timedelta,
        config_entry=None,
        max_arrivals: int = DEFAULT_MAX_ARRIVALS,
        transport_type: str = TRANSPORT_TYPE_BUS,
        # Bus/Light Rail parameters
        station_id: str | None = None,
        station_name: str | None = None,
        bus_lines: list[str] | None = None,
        # Train parameters
        from_station: str | None = None,
        to_station: str | None = None,
        from_station_name: str | None = None,
        to_station_name: str | None = None,
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

        # Generate display name for logging (includes city, station name, and ID)
        if station_id:
            self._station_display = get_station_display_name(station_id)
        else:
            self._station_display = None

        # Generate unique coordinator name
        if transport_type == TRANSPORT_TYPE_TRAIN:
            coordinator_name = f"{DOMAIN}_{from_station}_{to_station}"
        else:
            coordinator_name = f"{DOMAIN}_{station_id}"

        super().__init__(
            hass,
            _LOGGER,
            name=coordinator_name,
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Dictionary mapping line numbers/routes to arrival data

        Raises:
            UpdateFailed: If update fails
        """
        try:
            if self.transport_type == TRANSPORT_TYPE_TRAIN:
                # Fetch train routes
                _LOGGER.debug(
                    "Fetching train routes from %s to %s",
                    self.from_station,
                    self.to_station,
                )

                itineraries = await self.api_client.get_train_routes(
                    self.from_station,
                    self.to_station,
                    number_of_routes=self.max_arrivals,
                )

                # Process train routes
                processed_data = self._process_train_routes(itineraries)

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
        now = datetime.now()

        for arrival in arrivals:
            line_number = arrival.get("routeShortName")
            if not line_number:
                continue

            # Calculate arrival time
            service_day = arrival.get("serviceDay", 0)
            realtime_arrival = arrival.get(
                "realtimeArrival", arrival.get("scheduledArrival", 0)
            )

            # Convert to datetime
            arrival_timestamp = service_day + realtime_arrival
            arrival_time = datetime.fromtimestamp(arrival_timestamp)

            # Calculate minutes until arrival
            time_delta = arrival_time - now
            minutes_until = max(0, int(time_delta.total_seconds() / 60))

            # Check if this is real-time data
            is_realtime = arrival.get("realtime", False)

            # Get direction/headsign
            direction = arrival.get("headsign", arrival.get("tripHeadsign", "Unknown"))

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

    def _process_train_routes(
        self, itineraries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Process train route itineraries into structured format.

        Args:
            itineraries: Raw itinerary data from API

        Returns:
            Dictionary with route key mapping to processed departure data
        """
        processed: dict[str, list[dict[str, Any]]] = {}
        now = datetime.now()

        route_key = "train_route"  # Single key for train routes

        for idx, itinerary in enumerate(itineraries):
            # Get departure time
            start_time = itinerary.get("startTime")
            if not start_time:
                continue

            # Convert to datetime (milliseconds timestamp)
            departure_time = datetime.fromtimestamp(start_time / 1000)

            # Calculate minutes until departure
            time_delta = departure_time - now
            minutes_until = max(0, int(time_delta.total_seconds() / 60))

            # Get duration
            duration_seconds = itinerary.get("duration", 0)
            duration_minutes = int(duration_seconds / 60)

            # Extract route details (legs)
            legs = itinerary.get("legs", [])
            route_description = " → ".join(
                [
                    leg.get("to", {}).get("name", "Unknown")
                    for leg in legs
                    if leg.get("mode") == "RAIL"
                ]
            )

            # Create processed route entry
            processed_route = {
                "arrival_time": departure_time.isoformat(),
                "minutes_until": minutes_until,
                "duration_minutes": duration_minutes,
                "is_realtime": itinerary.get("realtime", False),
                "direction": route_description or f"{self.to_station_name}",
                "route_index": idx,
            }

            # Add to routes list
            if route_key not in processed:
                processed[route_key] = []

            processed[route_key].append(processed_route)

        # Sort routes by departure time
        if route_key in processed:
            processed[route_key].sort(key=lambda x: x["minutes_until"])

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
            line_number = arrival.get("Shilut")
            if not line_number:
                continue

            minutes_list = arrival.get("MinutesToArrivalList", [])
            if not minutes_list:
                # Fallback to single value
                single_min = arrival.get("MinutesToArrival")
                if single_min is not None:
                    minutes_list = [single_min]

            direction = arrival.get("Description", "")
            operator = arrival.get("CompanyName", "")

            # Create arrival entries for each upcoming arrival
            now = datetime.now()
            line_arrivals = []
            for minutes in minutes_list:
                # Calculate arrival time from minutes
                arrival_time = now + timedelta(minutes=minutes)
                line_arrivals.append(
                    {
                        "arrival_time": arrival_time.isoformat(),
                        "minutes_until": minutes,
                        "is_realtime": True,  # Gov API always returns real-time
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
        current_hour = datetime.now().hour

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

    def get_line_data(self, line_number: str) -> list[dict[str, Any]] | None:
        """Get arrival data for a specific line.

        Args:
            line_number: Bus line number

        Returns:
            List of arrivals for the line, or None if no data
        """
        if not self.data:
            return None
        return self.data.get(line_number)

    def get_next_arrival(self, line_number: str) -> dict[str, Any] | None:
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
