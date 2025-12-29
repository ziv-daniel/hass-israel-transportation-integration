# Israel Rail API Migration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace broken BusNearby train routing with official Israel Rail API via `israel-rail-api` library.

**Architecture:** Use `israel-rail-api` library directly (no wrapper class). Trains use this library, buses continue using `gov_api.py`. Delete `train_stations.py` - stations come from library.

**Tech Stack:** `israel-rail-api==0.1.4`, Home Assistant DataUpdateCoordinator

---

## Context

- BusNearby API `/directions/index/plan` endpoint returns 500/502 for all train routes
- Official HA `israel_rail` integration uses `israel-rail-api` library successfully
- Library wraps `https://rail-api.rail.co.il/rjpa/api/v1` (official Israel Railways API)
- Station IDs in current `train_stations.py` are wrong (e.g., Sderot is 9600, not 7300)

## Tasks

---

### Task 1: Add israel-rail-api dependency

**Files:**
- Modify: `custom_components/israel_transportation/manifest.json`

**Step 1: Update manifest.json**

Add the library to requirements:

```json
{
  "domain": "israel_transportation",
  "name": "Israel Transportation",
  "codeowners": ["@ziv-daniel"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/ziv-daniel/hass-israel-transportation-integration",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/ziv-daniel/hass-israel-transportation-integration/issues",
  "requirements": [
    "aiohttp>=3.9.0",
    "israel-rail-api==0.1.4"
  ],
  "version": "1.6.0"
}
```

**Step 2: Commit**

```bash
git add custom_components/israel_transportation/manifest.json
git commit -m "chore: add israel-rail-api dependency for trains"
```

---

### Task 2: Update config_flow.py to use library stations

**Files:**
- Modify: `custom_components/israel_transportation/config_flow.py`

**Step 1: Update imports**

Replace train_stations import with library import:

```python
# Remove this:
from .train_stations import TRAIN_STATIONS

# Add this:
from israelrailapi.train_station import station_name_to_id
```

**Step 2: Update _get_train_stations method**

```python
def _get_train_stations(self) -> list[tuple[str, str]]:
    """Get list of train stations from israel-rail-api library.

    Returns:
        List of (station_id, display_name) tuples sorted by name
    """
    stations = []
    for name, station_id in station_name_to_id.items():
        # Format: "Hebrew Name (ID)"
        stations.append((str(station_id), f"{name} ({station_id})"))

    # Sort by display name
    stations.sort(key=lambda x: x[1])
    return stations
```

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/config_flow.py
git commit -m "feat: use israel-rail-api station list in config flow"
```

---

### Task 3: Update coordinator.py for Israel Rail API

**Files:**
- Modify: `custom_components/israel_transportation/coordinator.py`

**Step 1: Add import**

```python
from israelrailapi import TrainSchedule
```

**Step 2: Update train data fetching in _async_update_data**

Replace the BusNearby train route fetching with Israel Rail API:

```python
if self.transport_type == TRANSPORT_TYPE_TRAIN:
    # Fetch train routes using Israel Rail API
    _LOGGER.debug(
        "Fetching train routes from %s to %s using Israel Rail API",
        self.from_station,
        self.to_station,
    )

    try:
        # Query Israel Rail API (synchronous library, run in executor)
        routes = await self.hass.async_add_executor_job(
            TrainSchedule.query,
            self.from_station,
            self.to_station,
        )

        # Process train routes
        processed_data = self._process_rail_routes(routes)

    except Exception as err:
        raise UpdateFailed(f"Error fetching train data from Israel Rail API: {err}") from err
```

**Step 3: Add new _process_rail_routes method**

```python
def _process_rail_routes(self, routes: list) -> dict[str, Any]:
    """Process train routes from Israel Rail API.

    Args:
        routes: List of Route objects from israelrailapi

    Returns:
        Dictionary with route key mapping to processed departure data
    """
    processed: dict[str, list[dict[str, Any]]] = {}
    now = datetime.now()
    route_key = "train_route"

    for idx, route in enumerate(routes[: self.max_arrivals]):
        # Get departure info from first train in route
        trains = route.trains if hasattr(route, 'trains') else []
        if not trains:
            continue

        first_train = trains[0]

        # Parse departure time
        dep_time_str = first_train.departure if hasattr(first_train, 'departure') else None
        if not dep_time_str:
            continue

        # Parse time (format: "HH:MM")
        try:
            dep_parts = dep_time_str.split(":")
            departure_time = now.replace(
                hour=int(dep_parts[0]),
                minute=int(dep_parts[1]),
                second=0,
                microsecond=0,
            )
            # If time is in the past, it's tomorrow
            if departure_time < now:
                departure_time = departure_time + timedelta(days=1)
        except (ValueError, IndexError):
            continue

        # Calculate minutes until departure
        time_delta = departure_time - now
        minutes_until = max(0, int(time_delta.total_seconds() / 60))

        # Get platform and train number
        platform = first_train.platform if hasattr(first_train, 'platform') else ""
        train_number = first_train.trainno if hasattr(first_train, 'trainno') else ""

        # Calculate total duration if multiple trains
        duration_minutes = 0
        if trains:
            last_train = trains[-1]
            arr_time_str = last_train.arrival if hasattr(last_train, 'arrival') else None
            if arr_time_str:
                try:
                    arr_parts = arr_time_str.split(":")
                    arrival_time = now.replace(
                        hour=int(arr_parts[0]),
                        minute=int(arr_parts[1]),
                        second=0,
                        microsecond=0,
                    )
                    if arrival_time < departure_time:
                        arrival_time = arrival_time + timedelta(days=1)
                    duration_minutes = int((arrival_time - departure_time).total_seconds() / 60)
                except (ValueError, IndexError):
                    pass

        # Build direction string
        stops = [t.destination if hasattr(t, 'destination') else "" for t in trains]
        direction = " → ".join(filter(None, stops)) or self.to_station_name

        processed_route = {
            "arrival_time": departure_time.isoformat(),
            "minutes_until": minutes_until,
            "duration_minutes": duration_minutes,
            "is_realtime": False,  # Israel Rail API doesn't provide real-time
            "direction": direction,
            "platform": platform,
            "train_number": train_number,
            "route_index": idx,
            "transfers": len(trains) - 1,
        }

        if route_key not in processed:
            processed[route_key] = []

        processed[route_key].append(processed_route)

    # Sort by departure time
    if route_key in processed:
        processed[route_key].sort(key=lambda x: x["minutes_until"])

    return processed
```

**Step 4: Remove api_client dependency for trains**

In __init__, trains no longer need `api_client` parameter. Update the coordinator initialization in `__init__.py` to not pass `api_client` for trains (Task 4 handles this).

**Step 5: Commit**

```bash
git add custom_components/israel_transportation/coordinator.py
git commit -m "feat: use Israel Rail API for train routes"
```

---

### Task 4: Update __init__.py for train setup

**Files:**
- Modify: `custom_components/israel_transportation/__init__.py`

**Step 1: Remove api_client from train coordinator initialization**

In `async_setup_entry`, for the train case, don't create or pass api_client:

```python
if transport_type == TRANSPORT_TYPE_TRAIN:
    # Train configuration - uses Israel Rail API directly
    from_station = entry.data[CONF_FROM_STATION]
    to_station = entry.data[CONF_TO_STATION]
    from_station_name = entry.data[CONF_FROM_STATION_NAME]
    to_station_name = entry.data[CONF_TO_STATION_NAME]

    # Create coordinator for train (no api_client needed - uses israelrailapi)
    coordinator = SilentBusCoordinator(
        hass=hass,
        update_interval=update_interval,
        config_entry=entry,
        transport_type=transport_type,
        from_station=from_station,
        to_station=to_station,
        from_station_name=from_station_name,
        to_station_name=to_station_name,
        max_arrivals=max_arrivals,
    )
```

**Step 2: Keep api_client creation only for buses (for potential fallback)**

Move the api_client creation inside the else block or keep it but don't pass to train coordinator.

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/__init__.py
git commit -m "refactor: train setup uses Israel Rail API directly"
```

---

### Task 5: Delete train_stations.py

**Files:**
- Delete: `custom_components/israel_transportation/train_stations.py`

**Step 1: Remove the file**

```bash
git rm custom_components/israel_transportation/train_stations.py
```

**Step 2: Remove any remaining imports**

Search for and remove any imports of `train_stations` in other files (should be none after Task 2).

**Step 3: Commit**

```bash
git commit -m "chore: remove train_stations.py (stations from library)"
```

---

### Task 6: Update sensor.py attribution for trains

**Files:**
- Modify: `custom_components/israel_transportation/sensor.py`

**Step 1: Add new attribution constant**

In `const.py`, add:

```python
ATTRIBUTION_RAIL = "Data provided by Israel Railways"
```

**Step 2: Update SilentBusTrainSensor attribution**

In `sensor.py`, import and use the new attribution:

```python
from .const import (
    ...
    ATTRIBUTION_RAIL,
    ...
)

# In SilentBusTrainSensor.extra_state_attributes:
attributes = {
    ...
    ATTR_ATTRIBUTION: ATTRIBUTION_RAIL,  # Changed from ATTRIBUTION_BUSNEARBY
    ...
}
```

**Step 3: Commit**

```bash
git add custom_components/israel_transportation/const.py custom_components/israel_transportation/sensor.py
git commit -m "fix: correct attribution for train data"
```

---

### Task 7: Test and verify

**Step 1: Run linting**

```bash
ruff check custom_components/israel_transportation/
ruff format custom_components/israel_transportation/
```

**Step 2: Test in Home Assistant**

1. Copy updated files to HA custom_components
2. Restart Home Assistant
3. Remove existing train entry
4. Add new train entry (Sderot → Tel Aviv-Savidor)
5. Verify sensor shows data

**Step 3: Create release**

```bash
git tag -a v1.6.0 -m "v1.6.0: Switch trains to Israel Rail API

## What's New

### Bug Fixes
- **Fixed train data not loading** - BusNearby API was returning 500/502 errors
- **Fixed station IDs** - Now uses correct Israel Railways station codes

### Changes
- Trains now use official Israel Railways API (same as HA israel_rail integration)
- Station list comes from israel-rail-api library (no manual maintenance)
- Added platform and train number to sensor attributes

### Breaking Changes
- Existing train configurations must be re-added (station IDs changed)"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add dependency | manifest.json |
| 2 | Use library stations | config_flow.py |
| 3 | Israel Rail API in coordinator | coordinator.py |
| 4 | Update train setup | __init__.py |
| 5 | Delete train_stations.py | train_stations.py |
| 6 | Fix attribution | const.py, sensor.py |
| 7 | Test and release | - |

**Total: 7 tasks, ~45 minutes of work**

## Notes

- The `israel-rail-api` library is synchronous, so we use `hass.async_add_executor_job()` to run queries
- Station IDs changed significantly (e.g., Sderot: 7300 → 9600) - users must re-add train entries
- Israel Rail API doesn't provide real-time delays (unlike bus.gov.il)
- Platform and train number now included in attributes
