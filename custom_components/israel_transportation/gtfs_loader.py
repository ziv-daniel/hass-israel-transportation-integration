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
import time
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
# Fixed tag that always holds the latest GTFS assets — never changes URL
GTFS_DATA_TAG = "gtfs-data-latest"
GTFS_ASSET_NAME = "cities_index.json"
ROUTES_ASSET_NAME = "routes_index.json.gz"

# Refresh interval: re-download assets if older than 7 days
GTFS_REFRESH_INTERVAL_SECONDS = 7 * 24 * 3600


def get_gtfs_data_path() -> Path:
    """Get the path to the GTFS data directory.

    Returns:
        Path to gtfs_data directory
    """
    return Path(__file__).parent / "gtfs_data"


def _get_timestamp_path() -> Path:
    """Path to the file storing the last GTFS download timestamp."""
    return get_gtfs_data_path() / ".gtfs_updated_at"


def _gtfs_is_stale() -> bool:
    """Return True if GTFS data is missing or older than GTFS_REFRESH_INTERVAL_SECONDS."""
    ts_path = _get_timestamp_path()
    if not ts_path.exists():
        return True
    try:
        last_updated = float(ts_path.read_text().strip())
        return (time.time() - last_updated) > GTFS_REFRESH_INTERVAL_SECONDS
    except (ValueError, OSError):
        return True


def _mark_gtfs_updated() -> None:
    """Write current timestamp to the GTFS update marker file."""
    try:
        _get_timestamp_path().write_text(str(time.time()))
    except OSError as e:
        _LOGGER.warning(f"Could not write GTFS timestamp: {e}")


async def _download_asset(
    session: "aiohttp.ClientSession", filename: str, dest: Path
) -> bool:
    """Download a single asset from the gtfs-data-latest release.

    Uses a direct download URL that never changes:
    https://github.com/<repo>/releases/download/gtfs-data-latest/<filename>

    Returns True on success, False on failure.
    """
    url = (
        f"https://github.com/{GITHUB_REPO}/releases/download/{GTFS_DATA_TAG}/{filename}"
    )
    _LOGGER.info(f"Downloading GTFS asset: {url}")
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                _LOGGER.error(f"Failed to download {filename}: HTTP {resp.status}")
                return False
            data = await resp.read()
    except asyncio.TimeoutError:
        _LOGGER.error(f"Timeout downloading {filename}")
        return False

    # Run the write in a thread: this is called from the event loop and HA
    # flags synchronous file I/O there as a blocking call.
    await asyncio.to_thread(dest.write_bytes, data)
    _LOGGER.info(f"Saved {filename} ({len(data):,} bytes) → {dest}")
    return True


async def download_gtfs_data_from_release() -> bool:
    """Download both GTFS assets from the fixed gtfs-data-latest release.

    Assets are always at a predictable URL so no GitHub API call is needed.
    Returns True if both assets downloaded and cities_index validated successfully.
    """
    if aiohttp is None:
        _LOGGER.error("aiohttp not available, cannot download GTFS data")
        return False

    gtfs_dir = get_gtfs_data_path()
    await asyncio.to_thread(gtfs_dir.mkdir, parents=True, exist_ok=True)

    cities_path = gtfs_dir / GTFS_ASSET_NAME
    routes_path = gtfs_dir / ROUTES_ASSET_NAME

    try:
        async with aiohttp.ClientSession() as session:
            cities_ok = await _download_asset(session, GTFS_ASSET_NAME, cities_path)
            routes_ok = await _download_asset(session, ROUTES_ASSET_NAME, routes_path)
    except Exception as e:
        _LOGGER.error(f"Unexpected error downloading GTFS data: {e}")
        return False

    if not cities_ok:
        return False

    # Validate cities_index.json
    try:
        raw = await asyncio.to_thread(cities_path.read_bytes)
        cities_data = json.loads(raw)
        city_count = len(cities_data)
        station_count = sum(len(c["stations"]) for c in cities_data.values())
        _LOGGER.info(
            f"GTFS download complete: {city_count} cities, {station_count} stations"
        )
    except (json.JSONDecodeError, KeyError) as e:
        _LOGGER.error(f"Downloaded cities_index.json is invalid: {e}")
        await asyncio.to_thread(cities_path.unlink, missing_ok=True)
        return False

    if not routes_ok:
        _LOGGER.warning(
            "routes_index.json.gz download failed — headsign fallback unavailable"
        )

    # Invalidate in-memory caches so next load reads fresh data
    global _CITIES_INDEX_CACHE, _ROUTES_INDEX_CACHE
    _CITIES_INDEX_CACHE = None
    _ROUTES_INDEX_CACHE = None

    await asyncio.to_thread(_mark_gtfs_updated)
    return True


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


async def async_load_cities_index(hass=None) -> Dict:
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

    index_path = get_gtfs_data_path() / GTFS_ASSET_NAME

    if not await asyncio.to_thread(index_path.exists):
        # First install or HACS didn't bundle the file — download now (blocking)
        _LOGGER.warning(
            "GTFS data not found locally. Downloading from gtfs-data-latest release..."
        )
        success = await download_gtfs_data_from_release()
        if not success:
            raise FileNotFoundError(
                "GTFS station data not found and could not be downloaded. "
                "Check your internet connection or visit "
                f"https://github.com/{GITHUB_REPO}/releases/tag/{GTFS_DATA_TAG}"
            )
        _LOGGER.info("GTFS data downloaded successfully.")
    elif await asyncio.to_thread(_gtfs_is_stale):
        # Data exists but is >7 days old — refresh in background, serve stale for now.
        # Hand the task to HA so it is tracked and cancelled cleanly on shutdown
        # rather than being an unowned fire-and-forget that can be killed mid-write.
        _LOGGER.info("GTFS data is stale (>7 days). Refreshing in background...")
        if hass is not None:
            hass.async_create_background_task(
                download_gtfs_data_from_release(),
                "israel_transportation_gtfs_refresh",
            )
        else:
            _LOGGER.debug("No hass reference; skipping background GTFS refresh")

    # Run the blocking I/O in a thread pool
    return await asyncio.to_thread(load_cities_index)


def get_cities_list(
    home_lat: Optional[float] = None,
    home_lon: Optional[float] = None,
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
