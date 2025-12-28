# Design: Migrate Bus/Light Rail to bus.gov.il API

**Date:** 2025-12-28
**Status:** Approved
**Author:** Claude Code

## Problem Statement

Station 44592 fails at runtime with error: "Station 44592 is not accessible. Please check your configuration."

### Root Cause

The current BusNearby API requires a **stop_id** (internal ID like 44592), but users enter the **Makat/stop_code** (displayed on physical bus stop signs, like 12665). The config flow translates stop_code→stop_id during setup, but runtime validation uses `search_station()` which only works with stop_code, causing a mismatch.

### Solution

Replace BusNearby API with the official **bus.gov.il API** for buses and light rail. This API uses Makat directly, eliminating the translation problem entirely.

## API Discovery

### bus.gov.il Endpoints

```
Base URL: https://bus.gov.il/WebApi/api/passengerinfo

GET /GetBusStopByMakat/{makat}/{locale}/false
    → Returns station info (name, coordinates, makat)
    → Invalid station: Name=null, Makat=0

GET /GetRealtimeBusLineListByBustop/{makat}/{locale}/false
    → Returns array of real-time arrivals
    → No arrivals: empty array []
```

### Example Response: GetBusStopByMakat

```json
{
  "Id": 0,
  "Name": "אלי מויאל/דוד המלך",
  "Longitude": 34.596388999999995,
  "Latitude": 31.540779999999998,
  "Makat": 12665
}
```

### Example Response: GetRealtimeBusLineListByBustop

```json
[
  {
    "Shilut": "1א",
    "MinutesToArrival": 4,
    "MinutesToArrivalList": [4, 34],
    "Description": "שדרות,נאות הנביאים - אזור התעשיה",
    "CompanyName": "דן בדרום",
    "BusstopHebrewName": "אלי מויאל/דוד המלך",
    "ResponseSuccesed": true
  }
]
```

### Advantages Over BusNearby

| Feature | BusNearby | bus.gov.il |
|---------|-----------|------------|
| Uses Makat directly | No (needs translation) | Yes |
| Official source | No (third-party) | Yes (government) |
| Minutes pre-calculated | No (must calculate) | Yes |
| Multiple arrivals | Complex parsing | Simple array |

### Limitations

- **Trains not supported** - Train station IDs return null
- **No search endpoint** - Must know Makat in advance

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Israel Transportation                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐         ┌─────────────────┐       │
│  │  Bus / Light    │         │     Train       │       │
│  │     Rail        │         │                 │       │
│  └────────┬────────┘         └────────┬────────┘       │
│           │                           │                 │
│           ▼                           ▼                 │
│  ┌─────────────────┐         ┌─────────────────┐       │
│  │  bus.gov.il     │         │   BusNearby     │       │
│  │  API Client     │         │   API Client    │       │
│  │    (NEW)        │         │   (existing)    │       │
│  └─────────────────┘         └─────────────────┘       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. New API Client (`gov_api.py`)

```python
class GovApiClient:
    """API client for bus.gov.il service."""

    BASE_URL = "https://bus.gov.il/WebApi/api/passengerinfo"

    async def get_station(self, makat: str, locale: str = "he") -> dict:
        """Get station info by Makat."""
        url = f"{self.BASE_URL}/GetBusStopByMakat/{makat}/{locale}/false"
        return await self._make_request(url)

    async def get_arrivals(self, makat: str, locale: str = "he") -> list:
        """Get real-time arrivals for a station."""
        url = f"{self.BASE_URL}/GetRealtimeBusLineListByBustop/{makat}/{locale}/false"
        return await self._make_request(url)

    async def validate_station(self, makat: str) -> bool:
        """Check if station exists."""
        result = await self.get_station(makat)
        return result.get("Name") is not None and result.get("Makat", 0) > 0
```

### 2. Response Field Mapping

| bus.gov.il Field | Sensor Attribute |
|------------------|------------------|
| `Name` | `station_name` |
| `Makat` | `station_id` |
| `Shilut` | `line_number` |
| `MinutesToArrival` | sensor state |
| `MinutesToArrivalList` | `upcoming_arrivals` |
| `Description` | `direction` |
| `CompanyName` | `operator` (new) |

### 3. Config Flow Simplification

**Before (complex, buggy):**
```
User enters stop_code (12665)
       ↓
Search BusNearby API
       ↓
Extract stop_id from result (44592)  ← Bug source
       ↓
Validate with stoptimes API
       ↓
Store stop_id in config
```

**After (simple):**
```
User enters Makat (12665)
       ↓
Call GetBusStopByMakat(12665)
       ↓
Check: Name != null && Makat > 0
       ↓
Store Makat directly in config
```

### 4. Coordinator Routing

```python
async def _async_update_data(self) -> dict[str, Any]:
    if self.transport_type == TRANSPORT_TYPE_TRAIN:
        # Use existing BusNearby API
        return await self._fetch_train_data()
    else:
        # Use new bus.gov.il API
        return await self._fetch_bus_data()

async def _fetch_bus_data(self) -> dict[str, Any]:
    arrivals = await self.gov_api_client.get_arrivals(self.station_id)

    # Filter by tracked lines
    if self.bus_lines:
        arrivals = [a for a in arrivals if a["Shilut"] in self.bus_lines]

    # Transform to sensor format
    return self._process_gov_arrivals(arrivals)
```

### 5. Integration Setup

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    transport_type = entry.data.get(CONF_TRANSPORT_TYPE, TRANSPORT_TYPE_BUS)

    if transport_type == TRANSPORT_TYPE_TRAIN:
        api_client = BusNearbyApiClient(session)
        # ... existing train setup ...
    else:
        api_client = GovApiClient(session)

        station_id = entry.data[CONF_STATION_ID]  # Makat
        is_valid = await api_client.validate_station(station_id)
        if not is_valid:
            raise ConfigEntryNotReady(f"Station {station_id} not found")

        coordinator = SilentBusCoordinator(
            hass=hass,
            gov_api_client=api_client,
            transport_type=transport_type,
            station_id=station_id,
            ...
        )
```

## Files to Change

### Create

| File | Purpose |
|------|---------|
| `gov_api.py` | New bus.gov.il API client |

### Modify

| File | Changes |
|------|---------|
| `const.py` | Add GOV_API_BASE_URL, update ATTRIBUTION |
| `config_flow.py` | Remove stop_code→stop_id translation, use gov API |
| `coordinator.py` | Add gov_api_client parameter, route by transport type |
| `__init__.py` | Create correct API client based on transport type |
| `api.py` | Optional: remove unused bus methods, keep train only |

### Unchanged

| File | Reason |
|------|--------|
| `sensor.py` | Sensor format unchanged |
| `train_stations.py` | Train logic unchanged |

## Testing Checklist

- [ ] Bus station 12665 (original bug) works
- [ ] Bus station 24068 (Azrieli, high traffic) works
- [ ] Light rail station works
- [ ] Train routes still work with BusNearby
- [ ] Invalid station shows proper error message
- [ ] Station with no current service handled gracefully
- [ ] Hebrew line numbers (e.g., "1א") work correctly
- [ ] Multiple arrivals displayed correctly

## Migration

Not required - integration is not yet public.

## Rollback Plan

If issues arise, revert to BusNearby API by:
1. Reverting code changes
2. No data migration needed (config format compatible)
