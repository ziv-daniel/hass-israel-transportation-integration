"""Tests for the Israel MOT bus API client (api.bus.gov.il)."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.israel_transportation.gov_api import (
    GovApiClient,
    InvalidMakatError,
    InvalidResponseError,
)

# Shapes below mirror real api.bus.gov.il responses (the `data` payload, which is
# what _make_request returns after unwrapping the {data, success, message} envelope).

STOP_BY_CODE_RESPONSE = {
    "stopid": 44592,
    "stopcode": 12665,
    "name": {"he": "אלי מויאל/דוד המלך", "en": None, "ar": None},
    "cityName": "שדרות",
    "streetName": "אלי מויאל",
    "lat": 31.540695,
    "lng": 34.596276,
}

ROUTES_AT_STOP_RESPONSE = {
    "routesInStop": [
        {
            "routeId": 20393,
            "routeName": "1א",
            "routeDesc": "39001-1-1",
            "agencyName": "דן בדרום",
            "headsign": {"he": "אזור תעשייה", "en": "Industrial Zone", "ar": None},
        },
        {
            "routeId": 29092,
            "routeName": "5",
            "routeDesc": "96005-1-#",
            "agencyName": "דן בדרום",
            "headsign": {"he": "תחנת הרכבת", "en": "The Train Station", "ar": None},
        },
    ]
}


def _times_response(makat, minutes_and_realtime):
    """Build a Calendar/GetRouteCalendarAtStopsByStopCodes payload."""
    return {
        str(makat): {
            "routeId": 1,
            "stopCode": int(makat),
            "stopTimes": [
                {
                    "arrivalTime": "2026-08-19T19:10:59",
                    "arrivalTimeString": "19:10",
                    "minutesToArrival": minutes,
                    "isRealTime": realtime,
                    "isLate": False,
                }
                for minutes, realtime in minutes_and_realtime
            ],
        }
    }


class TestGovApiClientInit:
    """Test GovApiClient initialization."""

    def test_init_with_session(self):
        """Test client initializes with provided session."""
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        client = GovApiClient(mock_session)
        assert client._session == mock_session
        assert client._own_session is False

    def test_init_without_session(self):
        """Test client initializes without session."""
        client = GovApiClient()
        assert client._session is None
        assert client._own_session is True


class TestGetStation:
    """Test get_station method."""

    @pytest.mark.asyncio
    async def test_get_station_valid(self):
        """A known stop code resolves to its name and makat."""
        with patch.object(
            GovApiClient, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = STOP_BY_CODE_RESPONSE
            async with GovApiClient() as client:
                result = await client.get_station("12665")

            assert result["Name"] == "אלי מויאל/דוד המלך"
            assert result["Makat"] == 12665
            # The API exposes the GTFS stop_id too; it is a different identifier.
            assert result["StopId"] == 44592
            assert result["CityName"] == "שדרות"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_station_unknown_returns_null_values(self):
        """An unknown stop code yields the null shape callers check for."""
        with patch.object(
            GovApiClient, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = None
            async with GovApiClient() as client:
                result = await client.get_station("99999")

            assert result["Name"] is None
            assert result["Makat"] == 0

    @pytest.mark.asyncio
    async def test_get_station_falls_back_across_locales(self):
        """A name missing in the requested locale falls back to another."""
        with patch.object(
            GovApiClient, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "stopcode": 12665,
                "name": {"he": None, "en": "Eli Moyal/David HaMelech", "ar": None},
            }
            async with GovApiClient() as client:
                result = await client.get_station("12665")

            assert result["Name"] == "Eli Moyal/David HaMelech"

    @pytest.mark.asyncio
    async def test_get_station_rejects_non_numeric_makat(self):
        """Non-numeric input is rejected before any request is made."""
        async with GovApiClient() as client:
            with pytest.raises(InvalidMakatError):
                await client.get_station("not-a-code")


class TestValidateStation:
    """Test validate_station method."""

    @pytest.mark.asyncio
    async def test_validate_station_valid(self):
        """Test validating a valid station returns True."""
        with patch.object(
            GovApiClient, "get_station", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"Name": "אלי מויאל/דוד המלך", "Makat": 12665}
            async with GovApiClient() as client:
                assert await client.validate_station("12665") is True

    @pytest.mark.asyncio
    async def test_validate_station_invalid_null_name(self):
        """Test validating station with null name returns False."""
        with patch.object(
            GovApiClient, "get_station", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"Name": None, "Makat": 0}
            async with GovApiClient() as client:
                assert await client.validate_station("99999") is False

    @pytest.mark.asyncio
    async def test_validate_station_invalid_zero_makat(self):
        """Test validating station with zero makat returns False."""
        with patch.object(
            GovApiClient, "get_station", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"Name": "Some Name", "Makat": 0}
            async with GovApiClient() as client:
                assert await client.validate_station("99999") is False

    @pytest.mark.asyncio
    async def test_validate_station_swallows_api_errors(self):
        """Upstream breakage reports 'not valid' rather than propagating."""
        with patch.object(
            GovApiClient, "get_station", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = InvalidResponseError("served HTML")
            async with GovApiClient() as client:
                assert await client.validate_station("12665") is False


class TestGetArrivals:
    """Test get_arrivals method."""

    @pytest.mark.asyncio
    async def test_get_arrivals_with_data(self):
        """Routes at the stop are joined with their upcoming times."""

        async def fake_request(path, params=None, base_url=None, locale="he"):
            if path == "Stops/RefreshStopTimesAtStop":
                return ROUTES_AT_STOP_RESPONSE
            if params["routeDesc"] == "39001-1-1":
                return _times_response("12665", [(4, True), (34, False)])
            return _times_response("12665", [(8, False)])

        with patch.object(GovApiClient, "_make_request", side_effect=fake_request):
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665")

        assert len(result) == 2

        first = result[0]
        assert first["line"] == "1א"
        assert first["direction"] == "אזור תעשייה"
        assert first["operator"] == "דן בדרום"
        assert [a["minutes_until"] for a in first["arrivals"]] == [4, 34]
        # is_realtime reflects what the API actually reports.
        assert [a["is_realtime"] for a in first["arrivals"]] == [True, False]

        assert result[1]["line"] == "5"
        assert result[1]["arrivals"] == [{"minutes_until": 8, "is_realtime": False}]

    @pytest.mark.asyncio
    async def test_get_arrivals_empty(self):
        """A stop with no routes yields no arrivals."""
        with patch.object(
            GovApiClient, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"routesInStop": []}
            async with GovApiClient() as client:
                assert await client.get_arrivals("12665") == []

    @pytest.mark.asyncio
    async def test_get_arrivals_filtered_by_lines(self):
        """Line filtering happens before times are fetched, one request per route."""
        times_calls = []

        async def fake_request(path, params=None, base_url=None, locale="he"):
            if path == "Stops/RefreshStopTimesAtStop":
                return ROUTES_AT_STOP_RESPONSE
            times_calls.append(params["routeDesc"])
            return _times_response("12665", [(4, False)])

        with patch.object(GovApiClient, "_make_request", side_effect=fake_request):
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665", lines=["5"])

        assert [entry["line"] for entry in result] == ["5"]
        # The filtered-out route must not cost a request.
        assert times_calls == ["96005-1-#"]

    @pytest.mark.asyncio
    async def test_get_arrivals_skips_routes_without_times(self):
        """Routes with no upcoming departures are omitted, not reported empty."""

        async def fake_request(path, params=None, base_url=None, locale="he"):
            if path == "Stops/RefreshStopTimesAtStop":
                return ROUTES_AT_STOP_RESPONSE
            if params["routeDesc"] == "39001-1-1":
                return {"12665": None}
            return _times_response("12665", [(8, False)])

        with patch.object(GovApiClient, "_make_request", side_effect=fake_request):
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665")

        assert [entry["line"] for entry in result] == ["5"]

    @pytest.mark.asyncio
    async def test_get_arrivals_tolerates_one_route_failing(self):
        """One route's times failing must not lose the other routes."""

        async def fake_request(path, params=None, base_url=None, locale="he"):
            if path == "Stops/RefreshStopTimesAtStop":
                return ROUTES_AT_STOP_RESPONSE
            if params["routeDesc"] == "39001-1-1":
                raise InvalidResponseError("upstream hiccup")
            return _times_response("12665", [(8, False)])

        with patch.object(GovApiClient, "_make_request", side_effect=fake_request):
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665")

        assert [entry["line"] for entry in result] == ["5"]

    @pytest.mark.asyncio
    async def test_routes_at_stop_are_cached(self):
        """The route list is reference data and must not be refetched per poll."""
        route_calls = 0

        async def fake_request(path, params=None, base_url=None, locale="he"):
            nonlocal route_calls
            if path == "Stops/RefreshStopTimesAtStop":
                route_calls += 1
                return ROUTES_AT_STOP_RESPONSE
            return _times_response("12665", [(4, False)])

        with patch.object(GovApiClient, "_make_request", side_effect=fake_request):
            async with GovApiClient() as client:
                await client.get_arrivals("12665")
                await client.get_arrivals("12665")

        assert route_calls == 1


class TestSearchStations:
    """Test search_stations method."""

    @pytest.mark.asyncio
    async def test_search_returns_stop_codes(self):
        """Search yields stop codes, which is what the rest of the flow needs."""
        with patch.object(
            GovApiClient, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = [
                {
                    "stopid": 35749,
                    "stopcode": 47444,
                    "name": "יוספטל (47444)",
                    "cityName": "קרית אתא",
                    "lat": 32.818022,
                    "lng": 35.11283,
                },
                {"stopid": 1, "name": "no stopcode", "cityName": "x"},
            ]
            async with GovApiClient() as client:
                results = await client.search_stations("יוספטל")

        assert len(results) == 1
        assert results[0]["makat"] == "47444"
        assert results[0]["city"] == "קרית אתא"

    @pytest.mark.asyncio
    async def test_search_empty_term_makes_no_request(self):
        """Blank searches short-circuit."""
        with patch.object(
            GovApiClient, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            async with GovApiClient() as client:
                assert await client.search_stations("   ") == []
            mock_request.assert_not_called()
