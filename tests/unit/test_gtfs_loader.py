"""Unit tests for gtfs_loader city/station transport-type filtering.

These tests cover the fix for #36: the "Browse stations by city" config flow
was showing every city/station regardless of transport type, because
gtfs_loader had no way to filter by mode. See build_stop_route_types /
annotate_route_types in scripts/update_gtfs_data.py for how the "route_types"
tag on each station is produced, and _station_matches_transport_type in
gtfs_loader.py for how it's consumed.
"""

from unittest.mock import patch

import pytest

from custom_components.israel_transportation import gtfs_loader
from custom_components.israel_transportation.const import (
    TRANSPORT_TYPE_BUS,
    TRANSPORT_TYPE_LIGHT_RAIL,
)

# A fixture city with a bus-only station, a light-rail-only station, a mixed
# (both modes) station, and an untagged/legacy station with no "route_types"
# key at all (simulating data produced before this tagging existed — which
# must still behave as "matches everything" for backward compatibility).
FIXTURE_CITIES_INDEX = {
    "Testville": {
        "name": "Testville",
        "name_he": "טסטוויל",
        "stations": [
            {
                "id": "1",
                "name": "Bus Only Station",
                "lat": 32.0,
                "lon": 34.0,
                "route_types": [3],
            },
            {
                "id": "2",
                "name": "Light Rail Only Station",
                "lat": 32.01,
                "lon": 34.01,
                "route_types": [0],
            },
            {
                "id": "3",
                "name": "Mixed Station",
                "lat": 32.02,
                "lon": 34.02,
                "route_types": [0, 3],
            },
            {
                "id": "4",
                "name": "Legacy Untagged Station",
                "lat": 32.03,
                "lon": 34.03,
                # No "route_types" key — simulates data from before this fix.
            },
        ],
    },
    "OtherCity": {
        "name": "OtherCity",
        "name_he": "עיר אחרת",
        "stations": [
            {
                "id": "5",
                "name": "Only Bus Station",
                "lat": 33.0,
                "lon": 35.0,
                "route_types": [3],
            },
        ],
    },
}


@pytest.fixture(autouse=True)
def _reset_gtfs_cache():
    """Ensure gtfs_loader's module-level cache doesn't leak between tests."""
    gtfs_loader._CITIES_INDEX_CACHE = None
    yield
    gtfs_loader._CITIES_INDEX_CACHE = None


@pytest.fixture
def mock_cities_index():
    """Patch load_cities_index() to return the fixture data above."""
    with patch.object(
        gtfs_loader, "load_cities_index", return_value=FIXTURE_CITIES_INDEX
    ):
        yield


class TestStationMatchesTransportType:
    """Unit tests for the _station_matches_transport_type helper."""

    def test_no_filter_matches_everything(self):
        station = {"route_types": [3]}
        assert gtfs_loader._station_matches_transport_type(station, None) is True

    def test_untagged_station_matches_everything(self):
        station = {"name": "legacy"}
        assert (
            gtfs_loader._station_matches_transport_type(
                station, TRANSPORT_TYPE_LIGHT_RAIL
            )
            is True
        )
        assert (
            gtfs_loader._station_matches_transport_type(station, TRANSPORT_TYPE_BUS)
            is True
        )

    def test_bus_only_station_excluded_from_light_rail(self):
        station = {"route_types": [3]}
        assert (
            gtfs_loader._station_matches_transport_type(
                station, TRANSPORT_TYPE_LIGHT_RAIL
            )
            is False
        )

    def test_light_rail_only_station_matches_light_rail(self):
        station = {"route_types": [0]}
        assert (
            gtfs_loader._station_matches_transport_type(
                station, TRANSPORT_TYPE_LIGHT_RAIL
            )
            is True
        )

    def test_mixed_station_matches_both(self):
        station = {"route_types": [0, 3]}
        assert (
            gtfs_loader._station_matches_transport_type(
                station, TRANSPORT_TYPE_LIGHT_RAIL
            )
            is True
        )
        assert (
            gtfs_loader._station_matches_transport_type(station, TRANSPORT_TYPE_BUS)
            is True
        )


class TestGetStationsForCity:
    """Unit tests for get_stations_for_city transport_type filtering."""

    def test_no_filter_returns_all_stations(self, mock_cities_index):
        stations = gtfs_loader.get_stations_for_city("Testville")
        assert len(stations) == 4

    def test_light_rail_filter_returns_only_matching_stations(self, mock_cities_index):
        stations = gtfs_loader.get_stations_for_city(
            "Testville", transport_type=TRANSPORT_TYPE_LIGHT_RAIL
        )
        station_ids = {s["id"] for s in stations}
        # Light-rail-only (2), mixed (3), and the untagged legacy station (4)
        # all match; the bus-only station (1) must not.
        assert station_ids == {"2", "3", "4"}

    def test_bus_filter_excludes_light_rail_only_station(self, mock_cities_index):
        stations = gtfs_loader.get_stations_for_city(
            "Testville", transport_type=TRANSPORT_TYPE_BUS
        )
        station_ids = {s["id"] for s in stations}
        assert "2" not in station_ids  # light-rail-only station excluded
        assert "1" in station_ids  # bus-only station included
        assert "3" in station_ids  # mixed station included
        assert "4" in station_ids  # untagged station included (back-compat)


class TestGetAllCitiesList:
    """Unit tests for get_all_cities_list transport_type filtering."""

    def test_no_filter_returns_all_cities(self, mock_cities_index):
        cities = gtfs_loader.get_all_cities_list()
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville", "OtherCity"}

    def test_light_rail_filter_excludes_bus_only_city(self, mock_cities_index):
        """A city whose only station is bus-only must disappear entirely
        when filtering for light rail — this is the core bug from #36."""
        cities = gtfs_loader.get_all_cities_list(
            transport_type=TRANSPORT_TYPE_LIGHT_RAIL
        )
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville"}
        assert "OtherCity" not in city_ids

    def test_light_rail_filter_station_count_reflects_filtered_stations(
        self, mock_cities_index
    ):
        cities = gtfs_loader.get_all_cities_list(
            transport_type=TRANSPORT_TYPE_LIGHT_RAIL
        )
        testville = next(c for c in cities if c["id"] == "Testville")
        # Only stations 2, 3, 4 match light rail (see test above).
        assert testville["station_count"] == 3


class TestGetCitiesList:
    """Unit tests for get_cities_list transport_type filtering."""

    def test_no_filter_returns_all_cities(self, mock_cities_index):
        cities = gtfs_loader.get_cities_list()
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville", "OtherCity"}

    def test_light_rail_filter_excludes_bus_only_city(self, mock_cities_index):
        cities = gtfs_loader.get_cities_list(transport_type=TRANSPORT_TYPE_LIGHT_RAIL)
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville"}

    def test_light_rail_filter_with_home_location(self, mock_cities_index):
        """When home coordinates are set, get_cities_list also consults
        get_cities_near_location internally — that path must respect the
        transport_type filter too, or bus-only cities would leak back in
        via the "nearby cities" (📍) section."""
        cities = gtfs_loader.get_cities_list(
            home_lat=32.0,
            home_lon=34.0,
            transport_type=TRANSPORT_TYPE_LIGHT_RAIL,
        )
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville"}
        assert "OtherCity" not in city_ids


class TestGetCitiesNearLocation:
    """Unit tests for get_cities_near_location transport_type filtering."""

    def test_light_rail_filter_excludes_bus_only_city(self, mock_cities_index):
        cities = gtfs_loader.get_cities_near_location(
            32.0, 34.0, max_distance_km=9999, transport_type=TRANSPORT_TYPE_LIGHT_RAIL
        )
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville"}
        assert "OtherCity" not in city_ids

    def test_no_filter_returns_all_cities(self, mock_cities_index):
        cities = gtfs_loader.get_cities_near_location(32.0, 34.0, max_distance_km=9999)
        city_ids = {c["id"] for c in cities}
        assert city_ids == {"Testville", "OtherCity"}
