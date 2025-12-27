"""DataUpdateCoordinator for Silent Bus integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BusNearbyApiClient, BusNearbyApiError
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
    """Class to manage fetching Silent Bus data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BusNearbyApiClient,
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
            api_client: BusNearby API client
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
                # Fetch bus/light rail arrivals
                _LOGGER.debug(
                    "Fetching data for station %s, lines: %s",
                    self.station_id,
                    self.bus_lines,
                )

                arrivals = await self.api_client.get_stop_times(
                    self.station_id,
                    self.bus_lines,
                    number_of_departures=self.max_arrivals,
                )

                # Process arrivals into structured data
                processed_data = self._process_arrivals(arrivals)

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
