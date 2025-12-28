"""GTFS data loader for Israeli transit stations.

This module loads the pre-processed GTFS cities index and provides
functions to access station data for the config flow.
"""

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

    with open(index_path, 'r', encoding='utf-8') as f:
        _CITIES_INDEX_CACHE = json.load(f)

    _LOGGER.info(
        f"Loaded {len(_CITIES_INDEX_CACHE)} cities with "
        f"{sum(len(c['stations']) for c in _CITIES_INDEX_CACHE.values())} total stations"
    )

    return _CITIES_INDEX_CACHE


def get_cities_list() -> List[Dict[str, str]]:
    """Get list of all cities with transit stations.

    Returns:
        List of dictionaries with 'id' and 'name' keys, sorted alphabetically

    Example:
        [
            {'id': 'Jerusalem', 'name': 'Jerusalem / ירושלים (464 stations)'},
            {'id': 'Tel Aviv', 'name': 'Tel Aviv / תל אביב (157 stations)'},
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
        station_count = len(city_data['stations'])

        # Skip "Other" category in main list (can be accessed via manual entry)
        if city_id == "Other":
            continue

        # Build bilingual city name if Hebrew name is available
        city_name_he = city_data.get('name_he', '')
        if city_name_he:
            display_name = f"{city_id} / {city_name_he} ({station_count} stations)"
        else:
            display_name = f"{city_id} ({station_count} stations)"

        cities.append({
            'id': city_id,
            'name': display_name
        })

    # Sort alphabetically by city name
    cities.sort(key=lambda c: c['id'])

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
        _LOGGER.warning(f"GTFS data not available, returning empty stations list for {city_id}")
        return []

    if city_id not in cities_index:
        _LOGGER.warning(f"City '{city_id}' not found in GTFS index")
        return []

    return cities_index[city_id]['stations']


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
        for station in city_data['stations']:
            if station['id'] == station_id:
                return station

    return None


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
