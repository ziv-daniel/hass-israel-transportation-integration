#!/usr/bin/env python3
"""Download and parse Israeli government GTFS data.

This script downloads the official Israeli Ministry of Transport GTFS feed,
extracts station information, parses city names, and generates a structured
index for use in the Home Assistant integration.

Data Source: https://gtfs.mot.gov.il
License: CDLA-Permissive-1.0
"""

import asyncio
import gzip
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Set
import sys

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)

# Import comprehensive city mappings
try:
    from israeli_cities import get_all_city_mappings, get_hebrew_name

    CITY_MAPPINGS = get_all_city_mappings()
except ImportError:
    # Fallback to basic mappings if israeli_cities.py not found
    CITY_MAPPINGS = {
        "תל אביב": "Tel Aviv",
        "ירושלים": "Jerusalem",
        "חיפה": "Haifa",
        "באר שבע": "Be'er Sheva",
    }

    def get_hebrew_name(english_city: str) -> str:
        """Fallback function if israeli_cities.py not found."""
        for he_city, en_city in CITY_MAPPINGS.items():
            if en_city == english_city:
                return he_city
        return ""


# Configuration
GTFS_URL = "https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip"
OUTPUT_DIR = Path("custom_components/israel_transportation/gtfs_data")
CITIES_INDEX_FILE = "cities_index.json"

# GTFS route_type codes (per the GTFS spec) relevant to filtering stations by
# transport mode. A station can be served by multiple route_types (e.g. both
# a bus route and a light rail route stopping at the same physical stop).
GTFS_ROUTE_TYPE_LIGHT_RAIL = 0
GTFS_ROUTE_TYPE_BUS = 3


def extract_city_from_name(stop_name: str) -> str:
    """Extract city name from stop name.

    The GTFS stop names often include city information in various formats:
    - "Station Name - City Name"
    - "Station Name / City Name"
    - "City Name - Station Name"

    Args:
        stop_name: The stop name from GTFS stops.txt

    Returns:
        Normalized English city name or "Other" if not found

    Examples:
        >>> extract_city_from_name("תחנה מרכזית - תל אביב")
        'Tel Aviv'
        >>> extract_city_from_name("Central Bus Station - Jerusalem")
        'Jerusalem'
    """
    # Remove extra whitespace
    stop_name = " ".join(stop_name.split())

    # Words to exclude from city matching (common words that aren't city names)
    # Note: "שדרות" removed - handled specially below as it's both a city name (Sderot) and boulevard
    EXCLUDE_WORDS = {"רחוב", "דרך", "כביש", "מרכז", "תחנה"}

    # Strategy 1: Try pattern-based extraction first (most reliable)
    # These patterns extract cities from structured formats like "Station - City"

    # Pattern 1: "Something - City" (after dash, before end or slash)
    # Matches Hebrew: "רחוב ראשי - תל אביב" → "תל אביב"
    # Matches English: "Main Street - Jerusalem" → "Jerusalem"
    match = re.search(r"[-–]\s*([א-ת][א-ת\s\-\']+?)(?:\s*$)", stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate not in EXCLUDE_WORDS and city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]

    # English variant
    match = re.search(r"[-–]\s*([A-Z][a-zA-Z\s\']+?)(?:\s*$)", stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]
        # Check against English city names
        for he_city, en_city in CITY_MAPPINGS.items():
            if city_candidate.lower() == en_city.lower():
                return en_city

    # Pattern 2: "City - Something" (at beginning, before dash)
    # Matches: "תל אביב - רחוב דיזנגוף" → "תל אביב"
    match = re.search(r"^([א-ת][א-ת\s\-\']+?)\s*[-–]", stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate not in EXCLUDE_WORDS and city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]

    # English variant
    match = re.search(r"^([A-Z][a-zA-Z\s\']+?)\s*[-–]", stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]

    # Pattern 3: "City / Something" or "Something / City" (with slashes)
    # Matches: "תל אביב/מרכז" → "תל אביב"
    for part in stop_name.split("/"):
        part = part.strip()
        if part in CITY_MAPPINGS and part not in EXCLUDE_WORDS:
            return CITY_MAPPINGS[part]
        # Check for English cities
        for he_city, en_city in CITY_MAPPINGS.items():
            if part.lower() == en_city.lower():
                return en_city

    # Strategy 2: Substring matching with word boundaries (more lenient, last resort)
    # Look for city names that appear as complete words, not substrings
    # This prevents "שדרות" (boulevard) from matching "Sderot"

    # Build a list of cities that appear as complete words (with word boundaries)
    matched_cities = []
    for he_city, en_city in CITY_MAPPINGS.items():
        # Skip common words that aren't actually cities in this context
        if he_city in EXCLUDE_WORDS:
            continue

        # Special handling for "שדרות" (Sderot) - both a city name and "boulevard"
        # Only match if it's NOT followed by a street name (which would indicate boulevard usage)
        if he_city == "שדרות":
            # Pattern: "שדרות" followed by another Hebrew word = boulevard (skip)
            # Pattern: "שדרות" standalone or with separators = city name (include)
            if re.search(r"שדרות\s+[א-ת]", stop_name):
                # Likely "שדרות <street name>" = boulevard, skip
                continue

        # Use word boundary matching - city must be surrounded by spaces, dashes, or string boundaries
        # This prevents "שדרות" in "שדרות ירושלים" from matching
        pattern = r"(?:^|\s|[-–/])" + re.escape(he_city) + r"(?:$|\s|[-–/])"
        if re.search(pattern, stop_name):
            matched_cities.append((len(he_city), en_city))

    if matched_cities:
        # Return the longest match (most specific)
        # E.g., "תל אביב יפו" beats "תל אביב"
        matched_cities.sort(reverse=True)
        return matched_cities[0][1]

    # Default: categorize as "Other"
    return "Other"


def extract_city_from_desc(stop_desc: str) -> Optional[str]:
    """Extract the official city name from a stop's stop_desc field.

    MOT's GTFS feed encodes structured address info in stop_desc as
    "רחוב: <street> עיר: <city> רציף: <platform> קומה: <floor>" — the
    עיר (city) segment is the ministry's own municipality assignment for
    the stop, keyed by its actual location. This is authoritative and
    unambiguous, unlike extract_city_from_name()'s text-heuristic (which
    false-positives whenever a city's name overlaps a common word or a
    person's name reused in street naming — e.g. a stop on "אריאל שרון"
    street, named after former PM Ariel Sharon, getting matched to the
    city "Ariel" no matter where in the country it actually is).

    Args:
        stop_desc: The stop_desc field from GTFS stops.txt

    Returns:
        The Hebrew city name, or None if stop_desc has no city field.

    Examples:
        >>> extract_city_from_desc("רחוב: אדמונית החורש 4 עיר: שדרות רציף:  קומה: ")
        'שדרות'
    """
    match = re.search(r"עיר:\s*([^:]*?)\s*רציף:", stop_desc)
    if match:
        city_he = match.group(1).strip()
        if city_he:
            return city_he
    return None


async def download_gtfs() -> Path:
    """Download GTFS zip file from Israeli Ministry of Transport.

    Returns:
        Path to the downloaded zip file

    Raises:
        aiohttp.ClientError: If download fails
    """
    print(f"Downloading GTFS data from {GTFS_URL}...")
    print("This may take a few minutes (~120 MB)...")

    async with aiohttp.ClientSession() as session:
        async with session.get(
            GTFS_URL, timeout=aiohttp.ClientTimeout(total=600)
        ) as response:
            response.raise_for_status()
            content = await response.read()

    # Save to disk
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / "israel-public-transportation.zip"
    zip_path.write_bytes(content)

    size_mb = len(content) / 1024 / 1024
    print(f"[OK] Downloaded {size_mb:.2f} MB")

    return zip_path


def parse_stops(zip_path: Path) -> Dict[str, Dict]:
    """Parse stops.txt from GTFS zip and build city-indexed station data.

    Args:
        zip_path: Path to the GTFS zip file

    Returns:
        Dictionary mapping city names to station lists

    Example output:
        {
            "Tel Aviv": {
                "name": "Tel Aviv",
                "name_he": "תל אביב",
                "stations": [
                    {
                        "id": "24068",
                        "name": "תחנה מרכזית ארלוזורוב / Arlozorov Terminal",
                        "lat": 32.0853,
                        "lon": 34.7818
                    },
                    ...
                ]
            },
            ...
        }
    """
    print("Parsing stops.txt...")

    cities_index = {}
    total_stops = 0
    skipped_stops = 0

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("stops.txt", "r") as f:
            # Read and decode file (handle UTF-8 BOM)
            lines = f.read().decode("utf-8-sig").splitlines()

            # Parse header
            header = lines[0].split(",")

            # Find required column indices
            try:
                stop_id_idx = header.index("stop_id")
                stop_name_idx = header.index("stop_name")
                stop_lat_idx = header.index("stop_lat")
                stop_lon_idx = header.index("stop_lon")
            except ValueError as e:
                print(f"Error: Required column not found in stops.txt header: {e}")
                raise

            # stop_code is the number printed on the stop sign (the "makat"), and
            # it is what bus.gov.il / api.bus.gov.il address stops by. It is NOT
            # stop_id, which is an internal GTFS surrogate key — the two are
            # different numbers for the same stop, in overlapping ranges, so
            # confusing them silently resolves to a different station.
            try:
                stop_code_idx = header.index("stop_code")
            except ValueError:
                stop_code_idx = None
                print("Warning: stops.txt has no stop_code column")

            # stop_desc carries MOT's own structured address, including the
            # official municipality ("עיר: <city>"). Prefer that over
            # extract_city_from_name()'s text-heuristic — see
            # extract_city_from_desc()'s docstring for why the heuristic
            # alone misfiles stops.
            try:
                stop_desc_idx = header.index("stop_desc")
            except ValueError:
                stop_desc_idx = None
                print("Warning: stops.txt has no stop_desc column")

            # Parse each stop
            for line_num, line in enumerate(lines[1:], start=2):
                # Handle CSV properly (quoted fields may contain commas)
                parts = line.split(",")

                if (
                    len(parts)
                    < max(stop_id_idx, stop_name_idx, stop_lat_idx, stop_lon_idx) + 1
                ):
                    skipped_stops += 1
                    continue

                try:
                    stop_id = parts[stop_id_idx].strip().strip('"')
                    stop_name = parts[stop_name_idx].strip().strip('"')
                    stop_lat = float(parts[stop_lat_idx].strip())
                    stop_lon = float(parts[stop_lon_idx].strip())
                    stop_code = ""
                    if stop_code_idx is not None and len(parts) > stop_code_idx:
                        stop_code = parts[stop_code_idx].strip().strip('"')
                    stop_desc = ""
                    if stop_desc_idx is not None and len(parts) > stop_desc_idx:
                        stop_desc = parts[stop_desc_idx].strip().strip('"')
                except (ValueError, IndexError):
                    # Skip malformed lines
                    skipped_stops += 1
                    continue

                # Skip empty stops
                if not stop_id or not stop_name:
                    skipped_stops += 1
                    continue

                # Extract city: official stop_desc field first (authoritative),
                # falling back to the name heuristic only for the small
                # minority of stops with no stop_desc (mostly rail stations,
                # which this bus/light-rail index doesn't surface anyway).
                city_he = extract_city_from_desc(stop_desc)
                if city_he:
                    city = CITY_MAPPINGS.get(city_he, city_he)
                else:
                    city = extract_city_from_name(stop_name)

                # Initialize city entry if needed
                if city not in cities_index:
                    # For a mapped English id, use the canonical Hebrew name
                    # from CITY_MAPPINGS (deterministic regardless of which
                    # spelling variant of the city was seen first). For an
                    # unmapped city, city itself IS the official Hebrew name.
                    city_name_he = get_hebrew_name(city) or (city_he or "")
                    cities_index[city] = {
                        "name": city,
                        "name_he": city_name_he,  # Populate Hebrew name
                        "stations": [],
                    }

                # Add station to city
                station = {
                    "id": stop_id,
                    "name": stop_name,
                    "lat": stop_lat,
                    "lon": stop_lon,
                }
                if stop_code:
                    station["code"] = stop_code
                cities_index[city]["stations"].append(station)

                total_stops += 1

    print(f"[OK] Parsed {total_stops:,} stops")
    print(f"[OK] Found {len(cities_index)} cities")
    if skipped_stops > 0:
        print(f"  (Skipped {skipped_stops} malformed entries)")

    # Sort stations within each city by name
    for city_data in cities_index.values():
        city_data["stations"].sort(key=lambda s: s["name"])

    return cities_index


def parse_routes(zip_path: Path) -> Dict[str, Dict]:
    """Parse routes.txt from GTFS zip.

    Args:
        zip_path: Path to the GTFS zip file

    Returns:
        Dictionary mapping route_id to route info

    Example output:
        {
            "7021": {
                "route_id": "7021",
                "route_short_name": "1",
                "route_long_name": "Jerusalem - Tel Aviv",
                "route_desc": "",
                "route_type": "3"
            },
            ...
        }
    """
    print("Parsing routes.txt...")

    routes = {}
    total_routes = 0

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("routes.txt", "r") as f:
            lines = f.read().decode("utf-8-sig").splitlines()
            header = lines[0].split(",")

            try:
                route_id_idx = header.index("route_id")
                route_short_name_idx = header.index("route_short_name")
                route_long_name_idx = (
                    header.index("route_long_name")
                    if "route_long_name" in header
                    else None
                )
                route_desc_idx = (
                    header.index("route_desc") if "route_desc" in header else None
                )
                route_type_idx = (
                    header.index("route_type") if "route_type" in header else None
                )
            except ValueError as e:
                print(f"Error: Required column not found in routes.txt: {e}")
                raise

            for line in lines[1:]:
                parts = line.split(",")
                if (
                    len(parts)
                    < max(
                        i for i in [route_id_idx, route_short_name_idx] if i is not None
                    )
                    + 1
                ):
                    continue

                try:
                    route_id = parts[route_id_idx].strip().strip('"')
                    route_short_name = parts[route_short_name_idx].strip().strip('"')
                    route_long_name = (
                        parts[route_long_name_idx].strip().strip('"')
                        if route_long_name_idx
                        else ""
                    )
                    route_desc = (
                        parts[route_desc_idx].strip().strip('"')
                        if route_desc_idx and len(parts) > route_desc_idx
                        else ""
                    )
                    route_type = (
                        parts[route_type_idx].strip().strip('"')
                        if route_type_idx and len(parts) > route_type_idx
                        else ""
                    )
                except (ValueError, IndexError):
                    continue

                routes[route_id] = {
                    "route_id": route_id,
                    "route_short_name": route_short_name,
                    "route_long_name": route_long_name,
                    "route_desc": route_desc,
                    "route_type": route_type,
                }
                total_routes += 1

    print(f"[OK] Parsed {total_routes:,} routes")
    return routes


def parse_trips(zip_path: Path) -> Dict[str, Dict]:
    """Parse trips.txt from GTFS zip.

    Args:
        zip_path: Path to the GTFS zip file

    Returns:
        Dictionary mapping trip_id to trip info

    Example output:
        {
            "123456": {
                "trip_id": "123456",
                "route_id": "7021",
                "trip_headsign": "Tel Aviv",
                "direction_id": "0"
            },
            ...
        }
    """
    print("Parsing trips.txt...")

    trips = {}
    total_trips = 0

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("trips.txt", "r") as f:
            lines = f.read().decode("utf-8-sig").splitlines()
            header = lines[0].split(",")

            try:
                trip_id_idx = header.index("trip_id")
                route_id_idx = header.index("route_id")
                trip_headsign_idx = (
                    header.index("trip_headsign") if "trip_headsign" in header else None
                )
                direction_id_idx = (
                    header.index("direction_id") if "direction_id" in header else None
                )
            except ValueError as e:
                print(f"Error: Required column not found in trips.txt: {e}")
                raise

            for line in lines[1:]:
                parts = line.split(",")
                if (
                    len(parts)
                    < max(i for i in [trip_id_idx, route_id_idx] if i is not None) + 1
                ):
                    continue

                try:
                    trip_id = parts[trip_id_idx].strip().strip('"')
                    route_id = parts[route_id_idx].strip().strip('"')
                    trip_headsign = (
                        parts[trip_headsign_idx].strip().strip('"')
                        if trip_headsign_idx and len(parts) > trip_headsign_idx
                        else ""
                    )
                    direction_id = (
                        parts[direction_id_idx].strip().strip('"')
                        if direction_id_idx and len(parts) > direction_id_idx
                        else ""
                    )
                except (ValueError, IndexError):
                    continue

                trips[trip_id] = {
                    "trip_id": trip_id,
                    "route_id": route_id,
                    "trip_headsign": trip_headsign,
                    "direction_id": direction_id,
                }
                total_trips += 1

    print(f"[OK] Parsed {total_trips:,} trips")
    return trips


def parse_stop_times(zip_path: Path) -> Dict[str, set]:
    """Parse stop_times.txt to get stop-to-trip mappings.

    Args:
        zip_path: Path to the GTFS zip file

    Returns:
        Dictionary mapping stop_id to set of trip_ids

    Note: This file is very large (~millions of rows), so we only store
    the mapping of stops to trips, not full schedule data.
    """
    print("Parsing stop_times.txt (this may take a while)...")

    stop_trips = defaultdict(set)
    total_stop_times = 0

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("stop_times.txt", "r") as f:
            lines = f.read().decode("utf-8-sig").splitlines()
            header = lines[0].split(",")

            try:
                trip_id_idx = header.index("trip_id")
                stop_id_idx = header.index("stop_id")
            except ValueError as e:
                print(f"Error: Required column not found in stop_times.txt: {e}")
                raise

            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) < max(trip_id_idx, stop_id_idx) + 1:
                    continue

                try:
                    trip_id = parts[trip_id_idx].strip().strip('"')
                    stop_id = parts[stop_id_idx].strip().strip('"')
                except (ValueError, IndexError):
                    continue

                stop_trips[stop_id].add(trip_id)
                total_stop_times += 1

    print(f"[OK] Parsed {total_stop_times:,} stop_times")
    print(f"[OK] Found {len(stop_trips):,} stops with trip associations")
    return stop_trips


def build_stop_route_types(
    routes: Dict[str, Dict], trips: Dict[str, Dict], stop_trips: Dict[str, set]
) -> Dict[str, Set[int]]:
    """Compute the set of GTFS route_types serving each stop.

    Joins stop_id -> trip_id (from stop_times.txt) -> route_id (from trips.txt)
    -> route_type (from routes.txt) to determine which transport mode(s) serve
    each stop. A stop can legitimately be served by more than one mode (e.g. a
    stop with both a bus route and a light rail route).

    Args:
        routes: Routes data from parse_routes (route_id -> route dict, incl. route_type)
        trips: Trips data from parse_trips (trip_id -> trip dict, incl. route_id)
        stop_trips: Stop-to-trip mappings from parse_stop_times

    Returns:
        Dictionary mapping stop_id to a set of route_type ints, e.g. {0, 3}
    """
    print("Building stop -> route_type index...")

    stop_route_types: Dict[str, Set[int]] = defaultdict(set)

    for stop_id, trip_ids in stop_trips.items():
        for trip_id in trip_ids:
            trip_data = trips.get(trip_id)
            if not trip_data:
                continue

            route_data = routes.get(trip_data["route_id"])
            if not route_data:
                continue

            route_type_raw = route_data.get("route_type", "")
            try:
                route_type = int(route_type_raw)
            except (ValueError, TypeError):
                continue

            stop_route_types[stop_id].add(route_type)

    print(f"[OK] Tagged route types for {len(stop_route_types):,} stops")
    return stop_route_types


def annotate_route_types(
    cities_index: Dict, stop_route_types: Dict[str, Set[int]]
) -> None:
    """Tag each station in cities_index with the route_types that serve it.

    Mutates cities_index in place, adding a sorted "route_types" list (e.g.
    [0, 3]) to each station dict. Stations with no known trips (not found in
    stop_times.txt, or whose trips/routes couldn't be resolved) get an empty
    list rather than being omitted, so consumers can distinguish "known to
    serve no tracked route" from "not yet tagged" (the field's mere presence).

    Args:
        cities_index: Cities index from parse_stops (mutated in place)
        stop_route_types: Stop-to-route_type mapping from build_stop_route_types
    """
    tagged = 0
    for city_data in cities_index.values():
        for station in city_data["stations"]:
            route_types = stop_route_types.get(station["id"], set())
            station["route_types"] = sorted(route_types)
            if route_types:
                tagged += 1

    print(f"[OK] Annotated route_types on stations ({tagged:,} stations have data)")


def build_routes_index(
    stops_data: Dict, routes: Dict, trips: Dict, stop_trips: Dict
) -> Dict:
    """Build routes index mapping stations to their routes and headsigns.

    Args:
        stops_data: Cities index from parse_stops
        routes: Routes data from parse_routes
        trips: Trips data from parse_trips
        stop_trips: Stop-to-trip mappings from parse_stop_times

    Returns:
        Dictionary mapping station_id to route information

    Example output:
        {
            "stations": {
                "12664": {
                    "name": "Station Name",
                    "routes": [
                        {
                            "route_id": "7021",
                            "route_short_name": "1",
                            "route_long_name": "City Center - Airport",
                            "trips": [
                                {"trip_headsign": "Airport", "direction_id": "0"},
                                {"trip_headsign": "City Center", "direction_id": "1"}
                            ]
                        }
                    ]
                }
            }
        }
    """
    print("Building routes index...")

    routes_index = {"stations": {}}
    total_stations_with_routes = 0

    # Iterate through all cities and stations
    for city_data in stops_data.values():
        for station in city_data["stations"]:
            station_id = station["id"]
            station_name = station["name"]

            # Get all trips for this station
            trip_ids = stop_trips.get(station_id, set())
            if not trip_ids:
                continue

            # Group trips by route
            routes_by_id = defaultdict(list)
            for trip_id in trip_ids:
                trip_data = trips.get(trip_id)
                if not trip_data:
                    continue

                route_id = trip_data["route_id"]
                trip_headsign = trip_data["trip_headsign"]
                direction_id = trip_data["direction_id"]

                # Add trip to route group
                routes_by_id[route_id].append(
                    {"trip_headsign": trip_headsign, "direction_id": direction_id}
                )

            if not routes_by_id:
                continue

            # Build route list for this station
            station_routes = []
            for route_id, trip_list in routes_by_id.items():
                route_data = routes.get(route_id)
                if not route_data:
                    continue

                # Deduplicate trip headsigns (keep unique headsigns per direction)
                unique_trips = {}
                for trip in trip_list:
                    key = (trip["trip_headsign"], trip["direction_id"])
                    if key not in unique_trips:
                        unique_trips[key] = trip

                station_routes.append(
                    {
                        "route_id": route_id,
                        "route_short_name": route_data["route_short_name"],
                        "route_long_name": route_data["route_long_name"],
                        "trips": list(unique_trips.values()),
                    }
                )

            # Add station to routes index
            routes_index["stations"][station_id] = {
                "name": station_name,
                "routes": station_routes,
            }
            total_stations_with_routes += 1

    print(f"[OK] Built routes index for {total_stations_with_routes:,} stations")
    return routes_index


def save_index(cities_index: Dict, output_path: Path):
    """Save cities index to JSON file.

    Args:
        cities_index: Dictionary of city data
        output_path: Path to save the JSON file
    """
    print(f"Saving index to {output_path}...")

    # Pretty print JSON for readability
    json_content = json.dumps(
        cities_index,
        ensure_ascii=False,  # Preserve Hebrew characters
        indent=2,
        sort_keys=True,
    )

    output_path.write_text(json_content, encoding="utf-8")

    size_kb = len(json_content) / 1024
    print(f"[OK] Saved {size_kb:.2f} KB")


def save_routes_index(routes_index: Dict, output_path: Path):
    """Save routes index to compressed JSON file.

    Args:
        routes_index: Dictionary of routes data
        output_path: Path to save the JSON.gz file
    """
    print(f"Saving routes index to {output_path}...")

    # Convert to JSON
    json_content = json.dumps(
        routes_index,
        ensure_ascii=False,  # Preserve Hebrew characters
        indent=None,  # Compact format for compression
        sort_keys=True,
    )

    # Compress with gzip
    compressed = gzip.compress(json_content.encode("utf-8"))

    # Write to file
    output_path.write_bytes(compressed)

    original_size_kb = len(json_content) / 1024
    compressed_size_kb = len(compressed) / 1024
    ratio = (1 - compressed_size_kb / original_size_kb) * 100
    print(
        f"[OK] Saved {compressed_size_kb:.2f} KB (compressed from {original_size_kb:.2f} KB, {ratio:.1f}% reduction)"
    )


def print_statistics(cities_index: Dict, routes_index: Dict = None):
    """Print statistics about the parsed data.

    Args:
        cities_index: Dictionary of city data
        routes_index: Optional dictionary of routes data
    """
    print("\n" + "=" * 60)
    print("GTFS Data Statistics")
    print("=" * 60)

    total_stations = sum(len(city["stations"]) for city in cities_index.values())

    print(f"Total Cities: {len(cities_index)}")
    print(f"Total Stations: {total_stations:,}")

    light_rail_stations = sum(
        1
        for city in cities_index.values()
        for station in city["stations"]
        if GTFS_ROUTE_TYPE_LIGHT_RAIL in station.get("route_types", [])
    )
    print(f"Total Light Rail Stations: {light_rail_stations:,}")

    print("\nTop 10 Cities by Station Count:")

    # Sort cities by station count
    sorted_cities = sorted(
        cities_index.items(), key=lambda x: len(x[1]["stations"]), reverse=True
    )

    for i, (city_name, city_data) in enumerate(sorted_cities[:10], 1):
        station_count = len(city_data["stations"])
        print(f"  {i:2d}. {city_name:20s} - {station_count:,} stations")

    if routes_index:
        total_routes = sum(
            len(station["routes"])
            for station in routes_index.get("stations", {}).values()
        )
        print(
            f"\nTotal Stations with Routes: {len(routes_index.get('stations', {})):,}"
        )
        print(f"Total Route Associations: {total_routes:,}")

    print("=" * 60 + "\n")


async def main():
    """Main update process."""
    print("Israeli Transit GTFS Data Updater")
    print("=" * 60 + "\n")

    try:
        # Step 1: Download GTFS data
        zip_path = await download_gtfs()

        # Step 2: Parse stops and build city index
        cities_index = parse_stops(zip_path)

        # Step 3: Parse routes, trips, and stop_times for routes index
        routes = parse_routes(zip_path)
        trips = parse_trips(zip_path)
        stop_trips = parse_stop_times(zip_path)

        # Step 3.5: Tag each station with the transport mode(s) (route_types)
        # that serve it, so the config flow can filter bus vs. light rail.
        stop_route_types = build_stop_route_types(routes, trips, stop_trips)
        annotate_route_types(cities_index, stop_route_types)

        # Step 4: Build routes index
        routes_index = build_routes_index(cities_index, routes, trips, stop_trips)

        # Step 5: Save cities index to JSON
        cities_output = OUTPUT_DIR / CITIES_INDEX_FILE
        save_index(cities_index, cities_output)

        # Step 6: Save routes index to compressed JSON
        routes_output = OUTPUT_DIR / "routes_index.json.gz"
        save_routes_index(routes_index, routes_output)

        # Step 7: Print statistics
        print_statistics(cities_index, routes_index)

        # Step 8: Cleanup zip file
        zip_path.unlink()
        print("[OK] Cleaned up temporary files")

        print("\n[SUCCESS] GTFS data update complete!")
        print(f"   Cities index: {cities_output}")
        print(f"   Routes index: {routes_output}")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
