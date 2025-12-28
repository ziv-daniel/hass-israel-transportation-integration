#!/usr/bin/env python3
"""Download and parse Israeli government GTFS data.

This script downloads the official Israeli Ministry of Transport GTFS feed,
extracts station information, parses city names, and generates a structured
index for use in the Home Assistant integration.

Data Source: https://gtfs.mot.gov.il
License: CDLA-Permissive-1.0
"""

import asyncio
import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List
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
OUTPUT_DIR = Path("custom_components/silent_bus/gtfs_data")
CITIES_INDEX_FILE = "cities_index.json"


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
    # "שדרות" = boulevard/avenue (also a city name, but more commonly a street type)
    EXCLUDE_WORDS = {"שדרות", "רחוב", "דרך", "כביש", "מרכז", "תחנה"}

    # Strategy 1: Try pattern-based extraction first (most reliable)
    # These patterns extract cities from structured formats like "Station - City"

    # Pattern 1: "Something - City" (after dash, before end or slash)
    # Matches Hebrew: "רחוב ראשי - תל אביב" → "תל אביב"
    # Matches English: "Main Street - Jerusalem" → "Jerusalem"
    match = re.search(r'[-–]\s*([א-ת][א-ת\s\-\']+?)(?:\s*$)', stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate not in EXCLUDE_WORDS and city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]

    # English variant
    match = re.search(r'[-–]\s*([A-Z][a-zA-Z\s\']+?)(?:\s*$)', stop_name)
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
    match = re.search(r'^([א-ת][א-ת\s\-\']+?)\s*[-–]', stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate not in EXCLUDE_WORDS and city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]

    # English variant
    match = re.search(r'^([A-Z][a-zA-Z\s\']+?)\s*[-–]', stop_name)
    if match:
        city_candidate = match.group(1).strip()
        if city_candidate in CITY_MAPPINGS:
            return CITY_MAPPINGS[city_candidate]

    # Pattern 3: "City / Something" or "Something / City" (with slashes)
    # Matches: "תל אביב/מרכז" → "תל אביב"
    for part in stop_name.split('/'):
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

        # Use word boundary matching - city must be surrounded by spaces, dashes, or string boundaries
        # This prevents "שדרות" in "שדרות ירושלים" from matching
        pattern = r'(?:^|\s|[-–/])' + re.escape(he_city) + r'(?:$|\s|[-–/])'
        if re.search(pattern, stop_name):
            matched_cities.append((len(he_city), en_city))

    if matched_cities:
        # Return the longest match (most specific)
        # E.g., "תל אביב יפו" beats "תל אביב"
        matched_cities.sort(reverse=True)
        return matched_cities[0][1]

    # Default: categorize as "Other"
    return "Other"


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
        async with session.get(GTFS_URL, timeout=aiohttp.ClientTimeout(total=600)) as response:
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
        with zf.open('stops.txt', 'r') as f:
            # Read and decode file (handle UTF-8 BOM)
            lines = f.read().decode('utf-8-sig').splitlines()

            # Parse header
            header = lines[0].split(',')

            # Find required column indices
            try:
                stop_id_idx = header.index('stop_id')
                stop_name_idx = header.index('stop_name')
                stop_lat_idx = header.index('stop_lat')
                stop_lon_idx = header.index('stop_lon')
            except ValueError as e:
                print(f"Error: Required column not found in stops.txt header: {e}")
                raise

            # Parse each stop
            for line_num, line in enumerate(lines[1:], start=2):
                # Handle CSV properly (quoted fields may contain commas)
                parts = line.split(',')

                if len(parts) < max(stop_id_idx, stop_name_idx, stop_lat_idx, stop_lon_idx) + 1:
                    skipped_stops += 1
                    continue

                try:
                    stop_id = parts[stop_id_idx].strip().strip('"')
                    stop_name = parts[stop_name_idx].strip().strip('"')
                    stop_lat = float(parts[stop_lat_idx].strip())
                    stop_lon = float(parts[stop_lon_idx].strip())
                except (ValueError, IndexError) as e:
                    # Skip malformed lines
                    skipped_stops += 1
                    continue

                # Skip empty stops
                if not stop_id or not stop_name:
                    skipped_stops += 1
                    continue

                # Extract city
                city = extract_city_from_name(stop_name)

                # Initialize city entry if needed
                if city not in cities_index:
                    cities_index[city] = {
                        'name': city,
                        'name_he': get_hebrew_name(city),  # Populate Hebrew name
                        'stations': []
                    }

                # Add station to city
                cities_index[city]['stations'].append({
                    'id': stop_id,
                    'name': stop_name,
                    'lat': stop_lat,
                    'lon': stop_lon
                })

                total_stops += 1

    print(f"[OK] Parsed {total_stops:,} stops")
    print(f"[OK] Found {len(cities_index)} cities")
    if skipped_stops > 0:
        print(f"  (Skipped {skipped_stops} malformed entries)")

    # Sort stations within each city by name
    for city_data in cities_index.values():
        city_data['stations'].sort(key=lambda s: s['name'])

    return cities_index


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
        sort_keys=True
    )

    output_path.write_text(json_content, encoding='utf-8')

    size_kb = len(json_content) / 1024
    print(f"[OK] Saved {size_kb:.2f} KB")


def print_statistics(cities_index: Dict):
    """Print statistics about the parsed data.

    Args:
        cities_index: Dictionary of city data
    """
    print("\n" + "="*60)
    print("GTFS Data Statistics")
    print("="*60)

    total_stations = sum(len(city['stations']) for city in cities_index.values())

    print(f"Total Cities: {len(cities_index)}")
    print(f"Total Stations: {total_stations:,}")
    print(f"\nTop 10 Cities by Station Count:")

    # Sort cities by station count
    sorted_cities = sorted(
        cities_index.items(),
        key=lambda x: len(x[1]['stations']),
        reverse=True
    )

    for i, (city_name, city_data) in enumerate(sorted_cities[:10], 1):
        station_count = len(city_data['stations'])
        print(f"  {i:2d}. {city_name:20s} - {station_count:,} stations")

    print("="*60 + "\n")


async def main():
    """Main update process."""
    print("Israeli Transit GTFS Data Updater")
    print("="*60 + "\n")

    try:
        # Step 1: Download GTFS data
        zip_path = await download_gtfs()

        # Step 2: Parse stops and build city index
        cities_index = parse_stops(zip_path)

        # Step 3: Save index to JSON
        output_path = OUTPUT_DIR / CITIES_INDEX_FILE
        save_index(cities_index, output_path)

        # Step 4: Print statistics
        print_statistics(cities_index)

        # Step 5: Cleanup zip file
        zip_path.unlink()
        print("[OK] Cleaned up temporary files")

        print("\n[SUCCESS] GTFS data update complete!")
        print(f"   Index file: {output_path}")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
