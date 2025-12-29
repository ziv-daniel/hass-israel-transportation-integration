# bus.gov.il API Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace BusNearby API with bus.gov.il API for buses and light rail to fix the Station 44592 bug.

**Architecture:** Create a new `GovApiClient` for bus.gov.il endpoints. Route bus/light_rail traffic to new client while trains continue using existing `BusNearbyApiClient`. Simplify config flow by removing stop_code→stop_id translation.

**Tech Stack:** Python 3.12+, aiohttp, Home Assistant custom component

**Design Doc:** `docs/plans/2025-12-28-bus-gov-il-api-migration-design.md`

---

## Task 1: Add bus.gov.il Constants

**Files:**
- Modify: `custom_components/israel_transportation/const.py`

**Step 1: Add new constants**

Add after line 48 (after existing API_SEARCH_URL):

```python
# bus.gov.il API configuration (for buses and light rail)
GOV_API_BASE_URL: Final = "https://bus.gov.il/WebApi/api/passengerinfo"
GOV_API_TIMEOUT: Final = 15
```

**Step 2: Update attribution**

Change line 71 from:
```python
ATTRIBUTION: Final = "Data provided by BusNearby"
```

To:
```python
ATTRIBUTION_BUSNEARBY: Final = "Data provided by BusNearby"
ATTRIBUTION_GOV: Final = "Data provided by Israel Ministry of Transportation"
```

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/const.py
git commit -m "feat: add bus.gov.il API constants"
```

---

## Task 2: Create GovApiClient - Basic Structure

**Files:**
- Create: `custom_components/israel_transportation/gov_api.py`
- Create: `tests/unit/test_gov_api.py`

**Step 1: Write failing test for client initialization**

Create `tests/unit/test_gov_api.py`:

```python
"""Tests for bus.gov.il API client."""

import pytest
from aiohttp import ClientSession

from custom_components.israel_transportation.gov_api import GovApiClient


class TestGovApiClientInit:
    """Test GovApiClient initialization."""

    def test_init_with_session(self):
        """Test client initializes with provided session."""
        session = ClientSession()
        client = GovApiClient(session)
        assert client._session == session
        assert client._own_session is False

    def test_init_without_session(self):
        """Test client initializes without session."""
        client = GovApiClient()
        assert client._session is None
        assert client._own_session is True
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_gov_api.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'custom_components.israel_transportation.gov_api'"

**Step 3: Write minimal implementation**

Create `custom_components/israel_transportation/gov_api.py`:

```python
"""API client for bus.gov.il (Israel Ministry of Transportation)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import ClientTimeout

from .const import GOV_API_BASE_URL, GOV_API_TIMEOUT, USER_AGENT

_LOGGER = logging.getLogger(__name__)


class GovApiError(Exception):
    """Base exception for bus.gov.il API errors."""


class StationNotFoundError(GovApiError):
    """Exception raised when station is not found."""


class ApiConnectionError(GovApiError):
    """Exception raised when connection to API fails."""


class ApiTimeoutError(GovApiError):
    """Exception raised when API request times out."""


class GovApiClient:
    """API client for bus.gov.il service."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the API client.

        Args:
            session: Optional aiohttp ClientSession. If not provided, a new one will be created.
        """
        self._session = session
        self._own_session = session is None
        self._headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://bus.gov.il/",
        }

    async def __aenter__(self) -> GovApiClient:
        """Async context manager entry."""
        if self._own_session:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self._own_session and self._session:
            await self._session.close()

    async def close(self) -> None:
        """Close the client session."""
        if self._own_session and self._session:
            await self._session.close()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_gov_api.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/israel_transportation/gov_api.py tests/unit/test_gov_api.py
git commit -m "feat: add GovApiClient basic structure"
```

---

## Task 3: Implement get_station Method

**Files:**
- Modify: `custom_components/israel_transportation/gov_api.py`
- Modify: `tests/unit/test_gov_api.py`

**Step 1: Write failing test for get_station**

Add to `tests/unit/test_gov_api.py`:

```python
import aiohttp
from aiohttp import web
from unittest.mock import AsyncMock, patch


class TestGetStation:
    """Test get_station method."""

    @pytest.mark.asyncio
    async def test_get_station_valid(self):
        """Test getting a valid station."""
        mock_response = {
            "Id": 0,
            "Name": "אלי מויאל/דוד המלך",
            "Longitude": 34.596388999999995,
            "Latitude": 31.540779999999998,
            "Makat": 12665,
        }

        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.get_station("12665")

            assert result["Name"] == "אלי מויאל/דוד המלך"
            assert result["Makat"] == 12665
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_station_invalid(self):
        """Test getting an invalid station returns null values."""
        mock_response = {
            "Id": 0,
            "Name": None,
            "Longitude": 0.0,
            "Latitude": 0.0,
            "Makat": 0,
        }

        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.get_station("99999")

            assert result["Name"] is None
            assert result["Makat"] == 0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_gov_api.py::TestGetStation -v
```

Expected: FAIL with "AttributeError: 'GovApiClient' object has no attribute '_make_request'" or "'get_station'"

**Step 3: Write implementation**

Add to `custom_components/israel_transportation/gov_api.py` after `close()` method:

```python
    async def _make_request(self, url: str) -> dict[str, Any] | list[Any]:
        """Make HTTP request to bus.gov.il API.

        Args:
            url: Full URL to request

        Returns:
            JSON response as dictionary or list

        Raises:
            ApiConnectionError: If connection fails
            ApiTimeoutError: If request times out
        """
        if not self._session:
            raise ApiConnectionError("Session not initialized")

        try:
            timeout = ClientTimeout(total=GOV_API_TIMEOUT)
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Failed to connect to API: {err}") from err
        except Exception as err:
            raise ApiConnectionError(f"Unexpected error: {err}") from err

    async def get_station(self, makat: str, locale: str = "he") -> dict[str, Any]:
        """Get station information by Makat.

        Args:
            makat: Station Makat (the number displayed on physical bus stop signs)
            locale: Language locale (default: "he")

        Returns:
            Station dictionary containing:
                - Name: Station name (None if not found)
                - Makat: Station Makat (0 if not found)
                - Longitude: Station longitude
                - Latitude: Station latitude
        """
        url = f"{GOV_API_BASE_URL}/GetBusStopByMakat/{makat}/{locale}/false"
        _LOGGER.debug("Getting station info for Makat %s", makat)

        result = await self._make_request(url)
        if not isinstance(result, dict):
            return {"Name": None, "Makat": 0}

        return result
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_gov_api.py::TestGetStation -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/israel_transportation/gov_api.py tests/unit/test_gov_api.py
git commit -m "feat: add get_station method to GovApiClient"
```

---

## Task 4: Implement validate_station Method

**Files:**
- Modify: `custom_components/israel_transportation/gov_api.py`
- Modify: `tests/unit/test_gov_api.py`

**Step 1: Write failing test for validate_station**

Add to `tests/unit/test_gov_api.py`:

```python
class TestValidateStation:
    """Test validate_station method."""

    @pytest.mark.asyncio
    async def test_validate_station_valid(self):
        """Test validating a valid station returns True."""
        mock_response = {
            "Name": "אלי מויאל/דוד המלך",
            "Makat": 12665,
        }

        with patch.object(GovApiClient, "get_station", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.validate_station("12665")

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_station_invalid_null_name(self):
        """Test validating station with null name returns False."""
        mock_response = {
            "Name": None,
            "Makat": 0,
        }

        with patch.object(GovApiClient, "get_station", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.validate_station("99999")

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_station_invalid_zero_makat(self):
        """Test validating station with zero makat returns False."""
        mock_response = {
            "Name": "Some Name",
            "Makat": 0,
        }

        with patch.object(GovApiClient, "get_station", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.validate_station("99999")

            assert result is False
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_gov_api.py::TestValidateStation -v
```

Expected: FAIL with "AttributeError: 'GovApiClient' object has no attribute 'validate_station'"

**Step 3: Write implementation**

Add to `custom_components/israel_transportation/gov_api.py` after `get_station()` method:

```python
    async def validate_station(self, makat: str) -> bool:
        """Validate that a station exists.

        Args:
            makat: Station Makat to validate

        Returns:
            True if station exists and is valid, False otherwise
        """
        try:
            result = await self.get_station(makat)
            return result.get("Name") is not None and result.get("Makat", 0) > 0
        except GovApiError:
            return False
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_gov_api.py::TestValidateStation -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/israel_transportation/gov_api.py tests/unit/test_gov_api.py
git commit -m "feat: add validate_station method to GovApiClient"
```

---

## Task 5: Implement get_arrivals Method

**Files:**
- Modify: `custom_components/israel_transportation/gov_api.py`
- Modify: `tests/unit/test_gov_api.py`

**Step 1: Write failing test for get_arrivals**

Add to `tests/unit/test_gov_api.py`:

```python
class TestGetArrivals:
    """Test get_arrivals method."""

    @pytest.mark.asyncio
    async def test_get_arrivals_with_data(self):
        """Test getting arrivals for station with buses."""
        mock_response = [
            {
                "Shilut": "1א",
                "MinutesToArrival": 4,
                "MinutesToArrivalList": [4, 34],
                "Description": "שדרות,נאות הנביאים - אזור התעשיה",
                "CompanyName": "דן בדרום",
                "BusstopHebrewName": "אלי מויאל/דוד המלך",
                "ResponseSuccesed": True,
            },
            {
                "Shilut": "5",
                "MinutesToArrival": 8,
                "MinutesToArrivalList": [8, 25],
                "Description": "שדרות - תחנת רכבת",
                "CompanyName": "דן בדרום",
                "BusstopHebrewName": "אלי מויאל/דוד המלך",
                "ResponseSuccesed": True,
            },
        ]

        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665")

            assert len(result) == 2
            assert result[0]["Shilut"] == "1א"
            assert result[0]["MinutesToArrival"] == 4
            assert result[1]["Shilut"] == "5"

    @pytest.mark.asyncio
    async def test_get_arrivals_empty(self):
        """Test getting arrivals for station with no buses."""
        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = []
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665")

            assert result == []

    @pytest.mark.asyncio
    async def test_get_arrivals_filtered_by_lines(self):
        """Test filtering arrivals by specific lines."""
        mock_response = [
            {"Shilut": "1א", "MinutesToArrival": 4, "MinutesToArrivalList": [4, 34]},
            {"Shilut": "5", "MinutesToArrival": 8, "MinutesToArrivalList": [8, 25]},
            {"Shilut": "10", "MinutesToArrival": 12, "MinutesToArrivalList": [12]},
        ]

        with patch.object(GovApiClient, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            async with GovApiClient() as client:
                result = await client.get_arrivals("12665", lines=["1א", "10"])

            assert len(result) == 2
            assert result[0]["Shilut"] == "1א"
            assert result[1]["Shilut"] == "10"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_gov_api.py::TestGetArrivals -v
```

Expected: FAIL with "AttributeError: 'GovApiClient' object has no attribute 'get_arrivals'"

**Step 3: Write implementation**

Add to `custom_components/israel_transportation/gov_api.py` after `validate_station()` method:

```python
    async def get_arrivals(
        self,
        makat: str,
        locale: str = "he",
        lines: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get real-time bus arrivals for a station.

        Args:
            makat: Station Makat
            locale: Language locale (default: "he")
            lines: Optional list of line numbers to filter by

        Returns:
            List of arrival dictionaries containing:
                - Shilut: Line number/name
                - MinutesToArrival: Minutes until next arrival
                - MinutesToArrivalList: List of all upcoming arrival times in minutes
                - Description: Route description
                - CompanyName: Bus company name
                - BusstopHebrewName: Station name in Hebrew
        """
        url = f"{GOV_API_BASE_URL}/GetRealtimeBusLineListByBustop/{makat}/{locale}/false"
        _LOGGER.debug("Getting arrivals for Makat %s, lines filter: %s", makat, lines)

        result = await self._make_request(url)

        if not isinstance(result, list):
            _LOGGER.warning("Unexpected response type for arrivals: %s", type(result))
            return []

        # Filter by lines if specified
        if lines:
            result = [arr for arr in result if arr.get("Shilut") in lines]
            _LOGGER.debug("Filtered to %d arrivals for lines %s", len(result), lines)

        return result
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_gov_api.py::TestGetArrivals -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/israel_transportation/gov_api.py tests/unit/test_gov_api.py
git commit -m "feat: add get_arrivals method to GovApiClient"
```

---

## Task 6: Update Coordinator to Support Both APIs

**Files:**
- Modify: `custom_components/israel_transportation/coordinator.py`

**Step 1: Add import and new parameter**

At the top of `coordinator.py`, add import:

```python
from .gov_api import GovApiClient
```

**Step 2: Update __init__ to accept gov_api_client**

Modify the `__init__` method signature (around line 32) to add:

```python
    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BusNearbyApiClient | None = None,  # Keep for trains
        gov_api_client: GovApiClient | None = None,    # New for bus/light_rail
        update_interval: timedelta,
        # ... rest of parameters unchanged
    ) -> None:
```

And add to the body after `self.api_client = api_client`:

```python
        self.gov_api_client = gov_api_client
```

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/coordinator.py
git commit -m "feat: add gov_api_client parameter to coordinator"
```

---

## Task 7: Implement _fetch_gov_arrivals Method in Coordinator

**Files:**
- Modify: `custom_components/israel_transportation/coordinator.py`

**Step 1: Add new method for fetching from gov API**

Add after the `_process_train_routes` method:

```python
    async def _fetch_gov_arrivals(self) -> dict[str, Any]:
        """Fetch arrivals from bus.gov.il API.

        Returns:
            Dictionary mapping line numbers to processed arrival data
        """
        if not self.gov_api_client:
            raise UpdateFailed("Gov API client not initialized")

        _LOGGER.debug(
            "Fetching gov API data for %s, lines: %s",
            self._station_display,
            self.bus_lines,
        )

        arrivals = await self.gov_api_client.get_arrivals(
            self.station_id,
            lines=self.bus_lines,
        )

        _LOGGER.debug(
            "Received %d arrivals from gov API for %s",
            len(arrivals) if arrivals else 0,
            self._station_display,
        )

        return self._process_gov_arrivals(arrivals)

    def _process_gov_arrivals(self, arrivals: list[dict[str, Any]]) -> dict[str, Any]:
        """Process arrivals from bus.gov.il into sensor format.

        Args:
            arrivals: Raw arrivals from gov API

        Returns:
            Dictionary mapping line numbers to processed arrival data
        """
        processed: dict[str, list[dict[str, Any]]] = {}

        for arrival in arrivals:
            line_number = arrival.get("Shilut")
            if not line_number:
                continue

            minutes_list = arrival.get("MinutesToArrivalList", [])
            if not minutes_list:
                # Fallback to single value
                single_min = arrival.get("MinutesToArrival")
                if single_min is not None:
                    minutes_list = [single_min]

            direction = arrival.get("Description", "")
            operator = arrival.get("CompanyName", "")

            # Create arrival entries for each upcoming arrival
            line_arrivals = []
            for minutes in minutes_list:
                line_arrivals.append({
                    "minutes_until": minutes,
                    "is_realtime": True,  # Gov API always returns real-time
                    "direction": direction,
                    "operator": operator,
                })

            if line_number not in processed:
                processed[line_number] = []

            processed[line_number].extend(line_arrivals)

        # Sort arrivals by time for each line
        for line_number in processed:
            processed[line_number].sort(key=lambda x: x["minutes_until"])
            # Limit to max_arrivals
            processed[line_number] = processed[line_number][: self.max_arrivals]

        return processed
```

**Step 2: Update _async_update_data to route correctly**

Modify the `_async_update_data` method. Replace the bus/light_rail section (the `else` block around line 130):

```python
            else:
                # Bus/Light Rail - use gov API if available, else BusNearby
                if self.gov_api_client:
                    processed_data = await self._fetch_gov_arrivals()
                else:
                    # Fallback to BusNearby (legacy)
                    _LOGGER.debug(
                        "Fetching data for %s, lines: %s",
                        self._station_display,
                        self.bus_lines,
                    )

                    arrivals = await self.api_client.get_stop_times(
                        self.station_id,
                        self.bus_lines,
                        number_of_departures=self.max_arrivals,
                    )

                    _LOGGER.debug(
                        "Received %d arrivals from API for %s",
                        len(arrivals) if arrivals else 0,
                        self._station_display,
                    )

                    processed_data = self._process_arrivals(arrivals)

                    _LOGGER.debug(
                        "Processed data for %s: lines found=%s, tracking lines=%s",
                        self._station_display,
                        list(processed_data.keys()) if processed_data else [],
                        self.bus_lines,
                    )

                    if not processed_data and arrivals:
                        _LOGGER.warning(
                            "%s: API returned %d arrivals but none matched tracked lines %s. "
                            "Available lines in response: %s",
                            self._station_display,
                            len(arrivals),
                            self.bus_lines,
                            list(set(a.get("routeShortName", "?") for a in arrivals)),
                        )
                    elif not processed_data and not arrivals:
                        _LOGGER.info(
                            "%s: No arrivals returned by API (station may have no service at this time)",
                            self._station_display,
                        )
```

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/coordinator.py
git commit -m "feat: add gov API fetch and processing to coordinator"
```

---

## Task 8: Update Integration Setup

**Files:**
- Modify: `custom_components/israel_transportation/__init__.py`

**Step 1: Add import**

Add at top with other imports:

```python
from .gov_api import GovApiClient
```

**Step 2: Update async_setup_entry**

Replace the bus/light_rail setup section (the `else` block starting around line 122):

```python
        else:
            # Bus/Light Rail configuration - use gov API
            station_id = entry.data[CONF_STATION_ID]
            station_name = entry.data[CONF_STATION_NAME]
            bus_lines = entry.data[CONF_BUS_LINES]

            # Create gov API client
            gov_api_client = GovApiClient(session)

            # Validate station with gov API
            is_valid = await gov_api_client.validate_station(station_id)
            if not is_valid:
                raise ConfigEntryNotReady(
                    f"Station {station_id} is not accessible. Please check your configuration."
                )

            # Create coordinator for bus/light rail with gov API
            coordinator = SilentBusCoordinator(
                hass=hass,
                gov_api_client=gov_api_client,
                update_interval=update_interval,
                config_entry=entry,
                transport_type=transport_type,
                station_id=station_id,
                station_name=station_name,
                bus_lines=bus_lines,
                max_arrivals=max_arrivals,
            )
```

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/__init__.py
git commit -m "feat: use GovApiClient for bus/light_rail setup"
```

---

## Task 9: Simplify Config Flow - Remove Translation Logic

**Files:**
- Modify: `custom_components/israel_transportation/config_flow.py`

**Step 1: Add import**

Add at top with other imports:

```python
from .gov_api import GovApiClient
```

**Step 2: Replace station validation logic**

Find the station validation section in `async_step_station` (around lines 550-620). Replace the entire try block that searches and translates with:

```python
            try:
                async with GovApiClient(
                    async_get_clientsession(self.hass)
                ) as gov_client:
                    # Validate station directly with gov API
                    station_info = await gov_client.get_station(station_id)

                    if station_info.get("Name") is None or station_info.get("Makat", 0) == 0:
                        errors["base"] = ERROR_STATION_NOT_FOUND
                    else:
                        # Station is valid - use Makat directly
                        self._station_id = station_id
                        self._station_name = station_info.get("Name", f"Station {station_id}")

                        _LOGGER.info(
                            "Station validated: makat=%s, name=%s",
                            self._station_id,
                            self._station_name,
                        )

                        # Move to next step
                        return await self.async_step_bus_lines()

            except ApiConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during station validation")
                errors["base"] = ERROR_UNKNOWN
```

**Step 3: Remove old imports no longer needed**

Remove these imports from config_flow.py if they become unused:
- `InvalidResponseError` from api (check if still used elsewhere)

**Step 4: Commit**

```bash
git add custom_components/israel_transportation/config_flow.py
git commit -m "feat: simplify config flow to use gov API directly"
```

---

## Task 10: Update Tests

**Files:**
- Modify: `tests/unit/test_config_flow.py` (if exists)
- Modify: `tests/integration/test_init.py` (if exists)

**Step 1: Update existing tests to mock gov API**

For any tests that create bus/light_rail entries, mock `GovApiClient` instead of `BusNearbyApiClient`:

```python
from unittest.mock import patch, AsyncMock
from custom_components.israel_transportation.gov_api import GovApiClient

# In test setup or individual tests:
with patch.object(GovApiClient, "validate_station", new_callable=AsyncMock) as mock_validate:
    mock_validate.return_value = True
    # ... test code ...

with patch.object(GovApiClient, "get_arrivals", new_callable=AsyncMock) as mock_arrivals:
    mock_arrivals.return_value = [
        {"Shilut": "1", "MinutesToArrival": 5, "MinutesToArrivalList": [5, 15]},
    ]
    # ... test code ...
```

**Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: update tests to use gov API mocks"
```

---

## Task 11: Update Sensor Attribution

**Files:**
- Modify: `custom_components/israel_transportation/sensor.py`

**Step 1: Update attribution based on transport type**

Find where `ATTRIBUTION` is used and update to use the correct one:

```python
from .const import ATTRIBUTION_BUSNEARBY, ATTRIBUTION_GOV, TRANSPORT_TYPE_TRAIN

# In the sensor class, update extra_state_attributes or similar:
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Return additional state attributes."""
    attrs = {
        # ... existing attributes ...
    }

    # Set correct attribution
    if self.coordinator.transport_type == TRANSPORT_TYPE_TRAIN:
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION_BUSNEARBY
    else:
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION_GOV

    return attrs
```

**Step 2: Commit**

```bash
git add custom_components/israel_transportation/sensor.py
git commit -m "feat: update attribution based on transport type"
```

---

## Task 12: Final Integration Test

**Step 1: Run all tests**

```bash
pytest tests/ -v --cov=custom_components.israel_transportation
```

Expected: All tests pass with good coverage

**Step 2: Run linting**

```bash
ruff check custom_components/israel_transportation/
ruff format custom_components/israel_transportation/
```

**Step 3: Test in Home Assistant**

1. Install the integration in a test Home Assistant instance
2. Add a bus station using Makat 12665 (the original bug station)
3. Verify station validates successfully
4. Verify real-time arrivals appear
5. Verify trains still work with BusNearby API

**Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete bus.gov.il API migration for buses and light rail"
```

---

## Summary

This plan migrates buses and light rail from BusNearby to bus.gov.il API while keeping trains on BusNearby. The key changes are:

1. **New `GovApiClient`** - Clean client for bus.gov.il endpoints
2. **Simplified config flow** - No more stop_code→stop_id translation
3. **Updated coordinator** - Routes to correct API based on transport type
4. **Updated setup** - Creates appropriate client for each transport type

Total tasks: 12
Estimated commits: 12
