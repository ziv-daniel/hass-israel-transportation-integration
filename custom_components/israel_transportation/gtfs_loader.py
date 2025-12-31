"""GTFS data loader for Israeli transit stations.

This module loads the pre-processed GTFS cities index and provides
functions to access station data for the config flow.

If the GTFS data file is missing (e.g., not downloaded by HACS), this module
will automatically download it from the latest GitHub release.
"""

import asyncio
import gzip
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None  # Will be available in Home Assistant environment

_LOGGER = logging.getLogger(__name__)

# Cache for loaded GTFS data
_CITIES_INDEX_CACHE: Optional[Dict] = None
_ROUTES_INDEX_CACHE: Optional[Dict] = None

# GitHub repository for downloading GTFS data
GITHUB_REPO = "ziv-daniel/hass-israel-transportation-integration"
GTFS_ASSET_NAME = "cities_index.json.gz"
ROUTES_ASSET_NAME = "routes_index.json.gz"


def get_gtfs_data_path() -> Path:
    """Get the path to the GTFS data directory.

    Returns:
        Path to gtfs_data directory
    """
    return Path(__file__).parent / "gtfs_data"


async def download_gtfs_data_from_release() -> bool:
    """Download GTFS data from the latest GitHub release.

    Returns:
        True if download successful, False otherwise
    """
    if aiohttp is None:
        _LOGGER.error("aiohttp not available, cannot download GTFS data")
        return False

    try:
        _LOGGER.info("Attempting to download GTFS data from GitHub releases...")

        # Get latest release info
        async with aiohttp.ClientSession() as session:
            release_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

            async with session.get(release_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to get latest release info: HTTP {response.status}")
                    return False

                release_data = await response.json()

                # Find the GTFS data asset
                gtfs_asset = None
                for asset in release_data.get("assets", []):
                    if asset["name"] == GTFS_ASSET_NAME:
                        gtfs_asset = asset
                        break

                if not gtfs_asset:
                    _LOGGER.error(f"GTFS data asset '{GTFS_ASSET_NAME}' not found in release")
                    return False

                download_url = gtfs_asset["browser_download_url"]
                _LOGGER.info(f"Downloading GTFS data from: {download_url}")

                # Download the compressed file
                async with session.get(download_url, timeout=aiohttp.ClientTimeout(total=120)) as download_response:
                    if download_response.status != 200:
                        _LOGGER.error(f"Failed to download GTFS data: HTTP {download_response.status}")
                        return False

                    compressed_data = await download_response.read()
                    _LOGGER.info(f"Downloaded {len(compressed_data)} bytes (compressed)")

        # Decompress the data
        try:
            decompressed_data = gzip.decompress(compressed_data)
            _LOGGER.info(f"Decompressed to {len(decompressed_data)} bytes")
        except Exception as e:
            _LOGGER.error(f"Failed to decompress GTFS data: {e}")
            return False

        # Ensure gtfs_data directory exists
        gtfs_dir = get_gtfs_data_path()
        gtfs_dir.mkdir(parents=True, exist_ok=True)

        # Save the decompressed file
        output_path = gtfs_dir / "cities_index.json"
        output_path.write_bytes(decompressed_data)
        _LOGGER.info(f"GTFS data saved to: {output_path}")

        # Validate the downloaded data
        try:
            cities_data = json.loads(decompressed_data)
            city_count = len(cities_data)
            station_count = sum(len(city["stations"]) for city in cities_data.values())
            _LOGGER.info(f"Successfully downloaded GTFS data: {city_count} cities, {station_count} stations")
            return True
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Downloaded GTFS data is not valid JSON: {e}")
            # Delete the invalid file
            output_path.unlink(missing_ok=True)
            return False

    except asyncio.TimeoutError:
        _LOGGER.error("Timeout while downloading GTFS data")
        return False
    except Exception as e:
        _LOGGER.error(f"Unexpected error downloading GTFS data: {e}")
        return False


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


def load_routes_index() -> Dict:
    """Load the routes index from compressed JSON file.

    Returns:
        Dictionary mapping station IDs to route data

    Raises:
        FileNotFoundError: If routes_index.json.gz doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    global _ROUTES_INDEX_CACHE

    # Return cached data if available
    if _ROUTES_INDEX_CACHE is not None:
        return _ROUTES_INDEX_CACHE

    # Load from file
    index_path = get_gtfs_data_path() / "routes_index.json.gz"

    if not index_path.exists():
        _LOGGER.debug(
            f"Routes index not found at {index_path}. "
            "GTFS route data fallback will not be available."
        )
        raise FileNotFoundError("Routes index not found")

    _LOGGER.info(f"Loading GTFS routes index from {index_path}")

    try:
        # Read and decompress gzip file
        with gzip.open(index_path, "rt", encoding="utf-8") as f:
            _ROUTES_INDEX_CACHE = json.load(f)

        station_count = len(_ROUTES_INDEX_CACHE.get("stations", {}))
        _LOGGER.info(f"Loaded routes data for {station_count:,} stations")

        return _ROUTES_INDEX_CACHE
    except Exception as e:
        _LOGGER.error(f"Failed to load routes index: {e}")
        raise


def get_route_headsign(station_id: str, route_number: str) -> Optional[str]:
    """Get route headsign from GTFS data for a specific station and route.

    This provides a fallback when the real-time API doesn't return direction/headsign data.

    Args:
        station_id: Station ID (e.g., "12664")
        route_number: Route/line number (e.g., "1", "5")

    Returns:
        Headsign/direction string or None if not found

    Example:
        >>> get_route_headsign("12664", "1")
        "Tel Aviv Central Station"
    """
    try:
        routes_data = load_routes_index()
    except FileNotFoundError:
        _LOGGER.debug("Routes index not available, cannot provide GTFS fallback")
        return None

    # Get station routes
    station_data = routes_data.get("stations", {}).get(station_id)
    if not station_data:
        return None

    # Find matching route by route_short_name
    for route in station_data.get("routes", []):
        if route.get("route_short_name") == route_number:
            # Prefer trip_headsign, fallback to route_long_name
            trips = route.get("trips", [])
            if trips:
                # Get the first trip's headsign (most common)
                trip_headsign = trips[0].get("trip_headsign", "").strip()
                if trip_headsign:
                    return trip_headsign

            # Fallback to route long name
            route_long_name = route.get("route_long_name", "").strip()
            if route_long_name:
                return route_long_name

    return None


async def async_load_cities_index() -> Dict:
    """Load the cities index asynchronously (non-blocking).

    This runs the file I/O in a thread pool to avoid blocking the event loop.
    Should be called once during config flow setup to pre-load the cache.

    If the GTFS data file is not found (e.g., not downloaded by HACS),
    this function will attempt to download it from the latest GitHub release.

    Returns:
        Dictionary mapping city names to station data

    Raises:
        FileNotFoundError: If cities_index.json doesn't exist and download fails
        json.JSONDecodeError: If JSON is malformed
    """
    global _CITIES_INDEX_CACHE

    # Return cached data if available (no I/O needed)
    if _CITIES_INDEX_CACHE is not None:
        return _CITIES_INDEX_CACHE

    # Check if GTFS data file exists
    index_path = get_gtfs_data_path() / "cities_index.json"

    if not index_path.exists():
        _LOGGER.warning(
            "GTFS data file not found. This may happen if HACS didn't download it. "
            "Attempting to download from GitHub releases..."
        )

        # Attempt to download from GitHub releases
        download_success = await download_gtfs_data_from_release()

        if not download_success:
            _LOGGER.error(
                "Failed to download GTFS data. Please ensure you have an internet connection, "
                "or manually download cities_index.json from the GitHub releases."
            )
            raise FileNotFoundError(
                "GTFS station data not found and could not be downloaded automatically. "
                "Please check your internet connection or download manually from "
                f"https://github.com/{GITHUB_REPO}/releases/latest"
            )

        _LOGGER.info("GTFS data downloaded successfully!")

    # Run the blocking I/O in a thread pool
    return await asyncio.to_thread(load_cities_index)


def get_cities_list(
    home_lat: float | None = None,
    home_lon: float | None = None,
    min_stations: int = 1,
    max_cities: int = 9999,
    top_cities_count: int = 3,
) -> List[Dict[str, str]]:
    """Get list of cities with transit stations, filtered and sorted.

    If home coordinates are provided, shows the 3 closest cities first,
    then all remaining cities sorted alphabetically by Hebrew name (א-ת).
    If no coordinates, shows all cities sorted alphabetically.

    Args:
        home_lat: Home latitude for proximity sorting (optional)
        home_lon: Home longitude for proximity sorting (optional)
        min_stations: Minimum number of stations required (default: 1)
        max_cities: Maximum number of cities to return (default: 9999 = all)
        top_cities_count: Number of closest cities to show first (default: 3)

    Returns:
        List of dictionaries with 'id', 'name', 'name_he', and 'station_count' keys

    Example:
        [
            {'id': 'Sderot', 'name': 'Sderot / שדרות (~2 km)',
             'name_he': 'שדרות', 'station_count': 15},
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

    # If home coordinates provided, show closest cities first
    if home_lat is not None and home_lon is not None:
        # Get closest cities by location
        nearby_cities = get_cities_near_location(
            home_lat, home_lon, max_distance_km=9999, max_cities=top_cities_count
        )
        nearby_city_ids = {c["id"] for c in nearby_cities}

        # Update display names for nearby cities to show distance
        for city in nearby_cities:
            city_id = city["id"]
            station_count = city.get("station_count", 0)
            distance_km = city.get("distance_km", 0)
            city_name_he = city.get("name_he", city_id)

            # Format with distance indicator
            if city_name_he and city_name_he != city_id:
                city["name"] = f"📍 {city_id} / {city_name_he} (~{distance_km:.0f} km)"
            else:
                city["name"] = f"📍 {city_id} (~{distance_km:.0f} km)"

        # Get remaining cities (excluding nearby ones), sort alphabetically by Hebrew
        remaining_cities = [c for c in cities if c["id"] not in nearby_city_ids]
        remaining_cities.sort(key=lambda c: c["name_he"])

        # Combine: nearby cities first, then all others alphabetically
        result = nearby_cities + remaining_cities
    else:
        # No coordinates provided - just sort alphabetically by Hebrew name
        cities.sort(key=lambda c: c["name_he"])
        result = cities

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
