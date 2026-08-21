"""Unit tests for scripts/update_gtfs_data.py city assignment.

These tests cover the fix for the "Ariel shows as 1km from Sderot" bug:
extract_city_from_name() (a text heuristic that greps for a city's Hebrew
name anywhere in a stop's *name*) mis-files any stop whose name contains a
city's name as a substring of something else — e.g. a stop on "אריאל שרון"
street (named after former PM Ariel Sharon, common all over the country)
was being filed under the city "Ariel" no matter where it actually is,
including stops literally in Sderot.

extract_city_from_desc() fixes this by reading MOT's own authoritative
"עיר: <city>" field out of stop_desc instead of guessing from stop_name.
parse_stops() now prefers it, falling back to the name heuristic only for
the rare stop with no stop_desc at all (chiefly rail stations, which this
bus/light-rail index doesn't surface via the config flow anyway).
"""

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from update_gtfs_data import (  # noqa: E402
    extract_city_from_desc,
    extract_city_from_name,
    parse_stops,
)

STOPS_HEADER = "stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon"


def _stops_zip_bytes(rows: list[str]) -> bytes:
    """Build the bytes of a GTFS zip containing only a stops.txt.

    parse_stops() takes a Path and opens it with zipfile.ZipFile(zip_path),
    so the caller writes these bytes to a tmp_path file first.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stops.txt", "\n".join([STOPS_HEADER, *rows]))
    return buf.getvalue()


class TestExtractCityFromDesc:
    def test_extracts_city_from_official_field(self):
        desc = "רחוב: אדמונית החורש 4 עיר: שדרות רציף:  קומה: "
        assert extract_city_from_desc(desc) == "שדרות"

    def test_ariel_sharon_street_resolves_to_sderot_not_ariel(self):
        # This is the exact reported bug case: a stop named after "Ariel
        # Sharon" street sitting in Sderot, not the city of Ariel.
        desc = "רחוב: אדמונית החורש 4 עיר: שדרות רציף:  קומה: "
        assert extract_city_from_desc(desc) != "אריאל"
        assert extract_city_from_desc(desc) == "שדרות"

    def test_real_ariel_city_stop_still_resolves_to_ariel(self):
        desc = "רחוב: כביש 31 עיר: אריאל רציף:  קומה: "
        assert extract_city_from_desc(desc) == "אריאל"

    def test_empty_desc_returns_none(self):
        assert extract_city_from_desc("") is None

    def test_desc_with_no_city_field_returns_none(self):
        assert extract_city_from_desc("רחוב: מסילת ברזל רציף: 2 קומה: ") is None

    def test_desc_with_blank_city_value_returns_none(self):
        assert extract_city_from_desc("רחוב: X עיר:  רציף:  קומה: ") is None


class TestParseStops:
    def test_prefers_stop_desc_city_over_name_heuristic(self, tmp_path):
        # Same reported bug case, run through the full parse_stops() pipeline:
        # a stop literally named ".../אריאל שרון" must land under Sderot
        # (per its stop_desc), not under Ariel (what the old name-only
        # heuristic would have matched).
        rows = [
            '50958,14170,"אדמונית החורש/אריאל שרון",'
            '"רחוב: אדמונית החורש 4 עיר: שדרות רציף:  קומה: ",31.532263,34.601241',
        ]
        zip_path = tmp_path / "gtfs.zip"
        zip_path.write_bytes(_stops_zip_bytes(rows))

        cities_index = parse_stops(zip_path)

        assert "Sderot" in cities_index
        station_ids = {s["id"] for s in cities_index["Sderot"]["stations"]}
        assert "50958" in station_ids

        if "Ariel" in cities_index:
            ariel_ids = {s["id"] for s in cities_index["Ariel"]["stations"]}
            assert "50958" not in ariel_ids

    def test_real_ariel_stop_still_lands_under_ariel(self, tmp_path):
        rows = [
            '34503,99001,"אוניברסיטת אריאל/כביש 31",'
            '"רחוב: כביש 31 עיר: אריאל רציף:  קומה: ",32.105926,35.210692',
        ]
        zip_path = tmp_path / "gtfs.zip"
        zip_path.write_bytes(_stops_zip_bytes(rows))

        cities_index = parse_stops(zip_path)

        assert "Ariel" in cities_index
        station_ids = {s["id"] for s in cities_index["Ariel"]["stations"]}
        assert "34503" in station_ids

    def test_falls_back_to_name_heuristic_when_stop_desc_missing(self, tmp_path):
        # Rail stations in this feed have an empty stop_desc. The station
        # name itself is unambiguous here ("כפר סבא" = the city), so the
        # name-heuristic fallback still resolves it correctly.
        rows = ['99001,,"כפר סבא","",32.178889,34.907500']
        zip_path = tmp_path / "gtfs.zip"
        zip_path.write_bytes(_stops_zip_bytes(rows))

        cities_index = parse_stops(zip_path)

        assert extract_city_from_name("כפר סבא") == "Kfar Saba"
        assert "Kfar Saba" in cities_index
        station_ids = {s["id"] for s in cities_index["Kfar Saba"]["stations"]}
        assert "99001" in station_ids

    def test_unmapped_official_city_uses_hebrew_name_as_id(self, tmp_path):
        # A real, sizeable locality (Rosh HaAyin) that is not (yet) present
        # in CITY_MAPPINGS should still get its own correctly-separated
        # bucket, keyed by its Hebrew name, rather than being lumped into
        # "Other" or mis-matched onto an unrelated city.
        rows = [
            '11111,,"תחנה כלשהי","רחוב: X עיר: ראש העין רציף:  קומה: ",32.09,34.95',
        ]
        zip_path = tmp_path / "gtfs.zip"
        zip_path.write_bytes(_stops_zip_bytes(rows))

        cities_index = parse_stops(zip_path)

        assert "ראש העין" in cities_index
        assert cities_index["ראש העין"]["name_he"] == "ראש העין"
        station_ids = {s["id"] for s in cities_index["ראש העין"]["stations"]}
        assert "11111" in station_ids
