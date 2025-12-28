"""GTFS data loader for Israeli transit stations.

This module loads the pre-processed GTFS cities index and provides
functions to access station data for the config flow.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# Cache for loaded GTFS data
_CITIES_INDEX_CACHE: Optional[Dict] = None


def get_gtfs_data_path() -> Path:
    """Get the path to the GTFS data directory.

    Returns:
        Path to gtfs_data directory
    """
    return Path(__file__).parent / "gtfs_data"


def load_cities_index() -> Dict:
    """Load the cities index from JSON file.

    Returns:
        Dictionary mapping city names to station data

    Raises:
        FileNotFoundError: If cities_index.json doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    global _CITIES_INDEX_CACHE

    # Return cached data if available
    if _CITIES_INDEX_CACHE is not None:
        return _CITIES_INDEX_CACHE

    # Load from file
    index_path = get_gtfs_data_path() / "cities_index.json"

    if not index_path.exists():
        _LOGGER.error(
            f"GTFS data not found at {index_path}. "
            "Run scripts/update_gtfs_data.py to download station data."
        )
        raise FileNotFoundError(
            "GTFS station data not found. Please update GTFS data first."
        )

    _LOGGER.info(f"Loading GTFS cities index from {index_path}")

    with open(index_path, "r", encoding="utf-8") as f:
        _CITIES_INDEX_CACHE = json.load(f)

    _LOGGER.info(
        f"Loaded {len(_CITIES_INDEX_CACHE)} cities with "
        f"{sum(len(c['stations']) for c in _CITIES_INDEX_CACHE.values())} total stations"
    )

    return _CITIES_INDEX_CACHE


async def async_load_cities_index() -> Dict:
    """Load the cities index asynchronously (non-blocking).

    This runs the file I/O in a thread pool to avoid blocking the event loop.
    Should be called once during config flow setup to pre-load the cache.

    Returns:
        Dictionary mapping city names to station data

    Raises:
        FileNotFoundError: If cities_index.json doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    global _CITIES_INDEX_CACHE

    # Return cached data if available (no I/O needed)
    if _CITIES_INDEX_CACHE is not None:
        return _CITIES_INDEX_CACHE

    # Run the blocking I/O in a thread pool
    return await asyncio.to_thread(load_cities_index)


def get_cities_list(
    min_stations: int = 50,
    max_cities: int = 50,
    top_cities_count: int = 3,
) -> List[Dict[str, str]]:
    """Get list of cities with transit stations, filtered and sorted.

    Cities are filtered to only include those with a minimum number of stations,
    sorted with the largest cities first, then alphabetically by Hebrew name (א-ת).

    Args:
        min_stations: Minimum number of stations required (default: 50)
        max_cities: Maximum number of cities to return (default: 50)
        top_cities_count: Number of largest cities to show first (default: 3)

    Returns:
        List of dictionaries with 'id', 'name', 'name_he', and 'station_count' keys

    Example:
        [
            {'id': 'Jerusalem', 'name': 'Jerusalem / ירושלים (464 stations)',
             'name_he': 'ירושלים', 'station_count': 464},
            ...
        ]
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        _LOGGER.warning("GTFS data not available, returning empty cities list")
        return []

    cities = []
    for city_id, city_data in cities_index.items():
        station_count = len(city_data["stations"])

        # Skip "Other" category in main list (can be accessed via manual entry)
        if city_id == "Other":
            continue

        # Filter by minimum station count
        if station_count < min_stations:
            continue

        # Build bilingual city name if Hebrew name is available
        city_name_he = city_data.get("name_he", "")
        if city_name_he:
            display_name = f"{city_id} / {city_name_he} ({station_count} stations)"
        else:
            display_name = f"{city_id} ({station_count} stations)"

        cities.append(
            {
                "id": city_id,
                "name": display_name,
                "name_he": city_name_he or city_id,
                "station_count": station_count,
            }
        )

    # Sort all cities by Hebrew name (א-ת)
    cities.sort(key=lambda c: c["name_he"])

    # Extract top N cities by station count
    top_cities = sorted(cities, key=lambda c: c["station_count"], reverse=True)[
        :top_cities_count
    ]
    top_city_ids = {c["id"] for c in top_cities}

    # Get remaining cities (excluding top cities), already sorted by Hebrew name
    remaining_cities = [c for c in cities if c["id"] not in top_city_ids]

    # Combine: top cities first (sorted by size), then remaining (sorted by Hebrew)
    top_cities.sort(key=lambda c: c["station_count"], reverse=True)
    result = top_cities + remaining_cities

    # Limit to max_cities
    return result[:max_cities]


def get_all_cities_list() -> List[Dict[str, str]]:
    """Get list of ALL cities with transit stations (no filtering).

    This is used when user wants to see more cities beyond the default filtered list.

    Returns:
        List of dictionaries with city info, sorted by Hebrew name
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        _LOGGER.warning("GTFS data not available, returning empty cities list")
        return []

    cities = []
    for city_id, city_data in cities_index.items():
        station_count = len(city_data["stations"])

        # Skip "Other" category
        if city_id == "Other":
            continue

        city_name_he = city_data.get("name_he", "")
        if city_name_he:
            display_name = f"{city_id} / {city_name_he} ({station_count} stations)"
        else:
            display_name = f"{city_id} ({station_count} stations)"

        cities.append(
            {
                "id": city_id,
                "name": display_name,
                "name_he": city_name_he or city_id,
                "station_count": station_count,
            }
        )

    # Sort by Hebrew name
    cities.sort(key=lambda c: c["name_he"])
    return cities


def get_stations_for_city(city_id: str) -> List[Dict[str, str]]:
    """Get all stations for a specific city.

    Args:
        city_id: City identifier (e.g., "Tel Aviv", "Jerusalem")

    Returns:
        List of dictionaries with station info, sorted by name

    Example:
        [
            {
                'id': '24068',
                'name': 'תחנה מרכזית ארלוזורוב / Arlozorov Terminal',
                'lat': 32.0853,
                'lon': 34.7818
            },
            ...
        ]
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        _LOGGER.warning(
            f"GTFS data not available, returning empty stations list for {city_id}"
        )
        return []

    if city_id not in cities_index:
        _LOGGER.warning(f"City '{city_id}' not found in GTFS index")
        return []

    return cities_index[city_id]["stations"]


def search_station_by_id(station_id: str) -> Optional[Dict]:
    """Search for a station by its ID across all cities.

    Args:
        station_id: Station ID to search for

    Returns:
        Station dictionary if found, None otherwise
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        return None

    # Search through all cities
    for city_data in cities_index.values():
        for station in city_data["stations"]:
            if station["id"] == station_id:
                return station

    return None


def get_station_display_name(station_id: str) -> str:
    """Get a human-readable display name for a station.

    Searches GTFS data and returns a formatted string with city, station name, and ID.

    Args:
        station_id: Station ID to look up

    Returns:
        Formatted string like "Jerusalem - שם התחנה (12345)" or just "12345" if not found
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        return station_id

    # Search through all cities
    for city_id, city_data in cities_index.items():
        for station in city_data["stations"]:
            if station["id"] == station_id:
                city_name = city_data.get("name_he", city_id)
                station_name = station.get("name", "Unknown")
                return f"{city_id} ({city_name}) - {station_name} [{station_id}]"

    return f"Unknown station [{station_id}]"


def is_gtfs_data_available() -> bool:
    """Check if GTFS data is available.

    Returns:
        True if cities_index.json exists and is valid, False otherwise
    """
    try:
        load_cities_index()
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate approximate distance between two coordinates in km.

    Uses the Haversine formula for distance calculation.

    Args:
        lat1, lon1: First coordinate (latitude, longitude)
        lat2, lon2: Second coordinate (latitude, longitude)

    Returns:
        Distance in kilometers
    """
    import math

    # Earth's radius in kilometers
    R = 6371.0

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def get_nearest_city(home_lat: float, home_lon: float) -> Optional[Dict[str, str]]:
    """Find the nearest city to the given coordinates.

    Calculates the average distance to all stations in each city and
    returns the city with the smallest average distance.

    Args:
        home_lat: Home latitude
        home_lon: Home longitude

    Returns:
        City dictionary with 'id', 'name', 'distance_km' keys, or None if no data
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        return None

    nearest_city = None
    min_distance = float("inf")

    for city_id, city_data in cities_index.items():
        if city_id == "Other":
            continue

        stations = city_data.get("stations", [])
        if not stations:
            continue

        # Calculate average distance to all stations in this city
        total_distance = 0.0
        valid_stations = 0

        for station in stations:
            lat = station.get("lat")
            lon = station.get("lon")
            if lat is not None and lon is not None:
                total_distance += _calculate_distance(home_lat, home_lon, lat, lon)
                valid_stations += 1

        if valid_stations == 0:
            continue

        avg_distance = total_distance / valid_stations

        if avg_distance < min_distance:
            min_distance = avg_distance
            city_name_he = city_data.get("name_he", "")
            station_count = len(stations)

            if city_name_he:
                display_name = f"{city_id} / {city_name_he} ({station_count} stations)"
            else:
                display_name = f"{city_id} ({station_count} stations)"

            nearest_city = {
                "id": city_id,
                "name": display_name,
                "name_he": city_name_he or city_id,
                "station_count": station_count,
                "distance_km": round(avg_distance, 1),
            }

    return nearest_city


def get_cities_near_location(
    home_lat: float,
    home_lon: float,
    max_distance_km: float = 30.0,
    max_cities: int = 10,
) -> List[Dict[str, str]]:
    """Get cities within a certain distance from the given coordinates.

    Args:
        home_lat: Home latitude
        home_lon: Home longitude
        max_distance_km: Maximum distance in kilometers (default: 30km)
        max_cities: Maximum number of cities to return (default: 10)

    Returns:
        List of city dictionaries sorted by distance, closest first
    """
    try:
        cities_index = load_cities_index()
    except FileNotFoundError:
        return []

    cities_with_distance = []

    for city_id, city_data in cities_index.items():
        if city_id == "Other":
            continue

        stations = city_data.get("stations", [])
        if not stations:
            continue

        # Calculate minimum distance to any station in this city
        min_station_distance = float("inf")

        for station in stations:
            lat = station.get("lat")
            lon = station.get("lon")
            if lat is not None and lon is not None:
                distance = _calculate_distance(home_lat, home_lon, lat, lon)
                if distance < min_station_distance:
                    min_station_distance = distance

        if min_station_distance <= max_distance_km:
            city_name_he = city_data.get("name_he", "")
            station_count = len(stations)

            if city_name_he:
                display_name = f"{city_id} / {city_name_he} ({station_count} stations)"
            else:
                display_name = f"{city_id} ({station_count} stations)"

            cities_with_distance.append(
                {
                    "id": city_id,
                    "name": display_name,
                    "name_he": city_name_he or city_id,
                    "station_count": station_count,
                    "distance_km": round(min_station_distance, 1),
                }
            )

    # Sort by distance, closest first
    cities_with_distance.sort(key=lambda c: c["distance_km"])

    return cities_with_distance[:max_cities]
