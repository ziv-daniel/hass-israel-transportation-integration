# Silent Bus - Home Assistant Integration Plan

## Executive Summary

This document outlines a comprehensive plan to build a **Home Assistant custom integration** for Israeli public transportation (buses and trains). The integration will allow users to configure specific bus lines and stations through the UI, and receive real-time arrival information as sensor entities.

---

## 1. Background Research & Current State (2025)

### 1.1 Home Assistant Integration Best Practices (2025)

Based on current Home Assistant development standards:

- **Config Flow**: All modern integrations use UI-based configuration through `ConfigFlow` class
- **DataUpdateCoordinator**: Centralized data fetching and update management with automatic retry logic
- **Entity Platform**: Sensor entities that update automatically based on coordinator data
- **HACS Support**: Integration should be installable through Home Assistant Community Store
- **Async/Await**: All I/O operations must be asynchronous to prevent blocking the Home Assistant event loop
- **Unique IDs**: Each entity must have a stable unique identifier for proper entity registry management

**Key References:**
- [Config Flow Documentation](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [2025 Integration Blueprint](https://github.com/jpawlowski/hacs.integration_blueprint)
- [Home Assistant Developer Guides](https://thehomesmarthome.com/home-assistant-custom-integrations-developers-guide/)

### 1.2 Israeli Public Transportation Data Sources

After researching existing projects, I found several viable API options:

#### Option A: BusNearby API (Recommended)
**Project Reference**: [bus-times-ha by UriaKesarii](https://github.com/UriaKesarii/bus-times-ha)

**Endpoints:**
- Station Search: `https://app.busnearby.co.il/stopSearch?query={station}&locale=he`
- Real-time Arrivals: `https://api.busnearby.co.il/directions/index/stops/1:{stop_id}/stoptimes`

**Advantages:**
- ✅ Reliable and actively maintained
- ✅ No authentication required
- ✅ Good response format
- ✅ Includes real-time data
- ✅ Covers all Israeli bus lines

**Request Parameters:**
```json
{
  "numberOfDepartures": 1,
  "timeRange": 86400,
  "currentTime": 1234567890
}
```

**Response Structure:**
```json
{
  "times": [
    {
      "routeShortName": "249",
      "serviceDay": 1234567890,
      "realtimeArrival": 1234567890
    }
  ]
}
```

#### Option B: SIRI API (Official Government)
**Project Reference**: [israel-public-transport-api](https://github.com/benyaming/israel-public-transport-api)

**Advantages:**
- ✅ Official Ministry of Transport data
- ✅ GTFS standard compliant

**Disadvantages:**
- ❌ More complex implementation
- ❌ May require API key
- ❌ Heavier payload

#### Option C: Open Bus API
**Reference**: [Open Bus Stride API](https://open-bus-stride-api.hasadna.org.il/docs)

**Status**: Community-driven project with comprehensive data

**Decision**: We'll use **BusNearby API (Option A)** as the primary data source due to simplicity and reliability.

### 1.3 Analysis of Silent-Bus Project

The original [silent-bus project](https://github.com/silentbil/silent-bus) is a **Lovelace custom card** (frontend only), not a full integration. Key findings:

- **Type**: Custom Lovelace card (JavaScript/Angular)
- **Configuration**: YAML-based card configuration
- **Data Source**: Uses Israeli transit APIs (exact endpoint not visible in minified code)
- **Functionality**: Displays bus/train times on dashboard

**Configuration Example:**
```yaml
type: custom:silent-bus
station: 24068
busLines:
  - 249
  - 40
  - 605
```

**Key Insight**: Our integration will be **backend-focused** (sensors/entities) rather than a frontend card. This provides more flexibility and allows users to use any Lovelace card to display the data.

---

## 2. Integration Architecture

### 2.1 File Structure

```
custom_components/israel_transportation/
├── __init__.py              # Integration setup and entry point
├── manifest.json            # Integration metadata
├── config_flow.py          # UI configuration flow
├── const.py                # Constants and configuration keys
├── coordinator.py          # DataUpdateCoordinator for API calls
├── sensor.py               # Sensor platform implementation
├── api.py                  # API client for BusNearby
├── strings.json            # UI translations (Hebrew + English)
├── translations/
│   ├── en.json            # English translations
│   └── he.json            # Hebrew translations
└── README.md              # Documentation
```

### 2.2 Component Overview

#### 2.2.1 `manifest.json`
Defines integration metadata for Home Assistant:

```json
{
  "domain": "israel_transportation",
  "name": "Silent Bus",
  "codeowners": ["@yourusername"],
  "config_flow": true,
  "documentation": "https://github.com/yourusername/silent-bus-integration",
  "issue_tracker": "https://github.com/yourusername/silent-bus-integration/issues",
  "requirements": ["aiohttp>=3.9.0"],
  "dependencies": [],
  "version": "1.0.0",
  "iot_class": "cloud_polling"
}
```

**Key Fields:**
- `config_flow: true` - Enables UI configuration
- `iot_class: "cloud_polling"` - Indicates we poll external API
- `requirements` - Python dependencies (aiohttp for async HTTP)

#### 2.2.2 `api.py` - API Client
Handles all communication with BusNearby API:

**Core Methods:**
- `async def search_station(query: str) -> list[dict]` - Search for stations by name/number
- `async def get_stop_times(stop_id: str, bus_lines: list[str]) -> dict` - Get real-time arrivals

**Features:**
- Proper error handling (network errors, timeouts, invalid responses)
- User-Agent headers to mimic browser requests
- Rate limiting to prevent API abuse
- Response caching (optional)

**Example Implementation Flow:**
```python
async def get_stop_times(self, stop_id: str, bus_lines: list[str] = None):
    """Get real-time bus arrivals for a station."""
    url = f"https://api.busnearby.co.il/directions/index/stops/1:{stop_id}/stoptimes"
    params = {
        "numberOfDepartures": 1,
        "timeRange": 86400,
        "currentTime": int(datetime.now().timestamp())
    }

    # Make request
    async with self.session.get(url, params=params) as resp:
        data = await resp.json()

    # Filter by requested bus lines if specified
    if bus_lines:
        filtered = [bus for bus in data['times']
                   if bus['routeShortName'] in bus_lines]
        return filtered

    return data['times']
```

#### 2.2.3 `coordinator.py` - Data Update Coordinator
Manages periodic updates and data distribution to sensors:

**Responsibilities:**
- Fetch data from API every 30 seconds (configurable)
- Handle errors and retries automatically
- Distribute data to all listening sensors
- Manage update intervals based on time of day (more frequent during rush hour)

**Key Features:**
- Uses `DataUpdateCoordinator` base class from Home Assistant
- Automatic retry with exponential backoff
- Error state management
- Data validation before distribution

**Update Logic:**
```python
class SilentBusCoordinator(DataUpdateCoordinator):
    """Coordinate data updates for all Silent Bus sensors."""

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Get arrivals for configured station and lines
            data = await self.api.get_stop_times(
                self.stop_id,
                self.bus_lines
            )
            return self._process_arrivals(data)
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")
```

#### 2.2.4 `sensor.py` - Sensor Entities
Creates sensor entities for each bus line:

**Sensor Types:**
1. **Per-Line Sensors**: One sensor per bus line showing next arrival
2. **Station Summary Sensor**: Shows all lines at the station

**Sensor Attributes:**
- **State**: Minutes until next bus arrival (e.g., "5")
- **Unit of measurement**: "min"
- **Device class**: `timestamp` or custom
- **Attributes**:
  - `line_number`: Bus line number
  - `station_id`: Station ID
  - `station_name`: Station name
  - `next_arrival_time`: Exact timestamp
  - `real_time`: Boolean (is this real-time data or scheduled?)
  - `direction`: Bus direction/destination
  - `next_arrivals`: List of next 3-5 arrivals

**Unique ID Format:**
```
israel_transportation_{station_id}_{line_number}
```

Example: `israel_transportation_24068_249`

**Entity Naming:**
- Entity ID: `sensor.bus_24068_line_249`
- Friendly Name: "Bus 249 at Station 24068"
- Can be customized by user

#### 2.2.5 `config_flow.py` - Configuration UI
Multi-step configuration flow:

**Step 1: Station Selection**
- User enters station number OR searches by name
- Validation: Check if station exists using API
- Display station name for confirmation

**Step 2: Bus Lines Selection**
- User enters comma-separated list of bus lines (e.g., "249,40,605")
- OR: Auto-discover all lines at station and let user select
- Validation: Check if lines serve this station

**Step 3: Options (Optional)**
- Update interval (default: 30 seconds)
- Number of upcoming arrivals to track (default: 3)
- Enable/disable notifications for delays

**Step 4: Confirmation**
- Show summary of configuration
- Create config entry

**Options Flow:**
- Allow users to modify configuration after setup
- Add/remove bus lines
- Change update interval
- Change station

**User Experience:**
```
┌─────────────────────────────────────┐
│  Silent Bus Integration Setup       │
├─────────────────────────────────────┤
│  Station Number: [24068     ]       │
│                   or                │
│  Search Station: [Tel Aviv__]       │
│                                     │
│  [Next]                             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Select Bus Lines                   │
├─────────────────────────────────────┤
│  Station: Arlozorov Terminal        │
│                                     │
│  Enter lines (comma-separated):     │
│  [249, 40, 605              ]       │
│                                     │
│  [Back]  [Next]                     │
└─────────────────────────────────────┘
```

---

## 3. Data Flow & Update Mechanism

### 3.1 Initialization Flow

```
User adds integration via UI
    ↓
ConfigFlow collects station + bus lines
    ↓
__init__.py creates API client
    ↓
__init__.py creates DataUpdateCoordinator
    ↓
sensor.py creates entities for each line
    ↓
Coordinator starts polling API (every 30s)
    ↓
Sensors update their state automatically
```

### 3.2 Update Cycle

```
[Timer: 30 seconds]
    ↓
Coordinator._async_update_data() called
    ↓
API.get_stop_times(station_id, bus_lines)
    ↓
Parse response and calculate arrival times
    ↓
Update coordinator.data
    ↓
All sensors receive update notification
    ↓
Each sensor updates its state + attributes
    ↓
Home Assistant UI refreshes
    ↓
[Wait 30 seconds, repeat]
```

### 3.3 Error Handling

**Network Errors:**
- Retry up to 3 times with exponential backoff
- If all retries fail, mark sensors as "unavailable"
- Log error for debugging
- Resume normal operation when connection restored

**Invalid Data:**
- Validate API response structure
- Handle missing fields gracefully
- Use previous valid data if available
- Log warning for investigation

**API Rate Limiting:**
- Respect API limits (if any)
- Implement client-side throttling
- Increase update interval if rate-limited

---

## 4. Configuration & User Experience

### 4.1 Configuration Storage

Configuration is stored in Home Assistant's config entry:

```python
{
    "station_id": "24068",
    "station_name": "Arlozorov Terminal",
    "bus_lines": ["249", "40", "605"],
    "update_interval": 30,
    "max_arrivals": 3
}
```

### 4.2 Multiple Stations Support

Users can add multiple integration instances for different stations:

- Each instance = one station
- Each instance can monitor multiple bus lines
- All instances share the same API client (connection pooling)
- Each instance has its own coordinator (independent updates)

**Example Setup:**
- Instance 1: Home station (24068) - Lines 249, 40
- Instance 2: Work station (37201) - Lines 18, 25, 189
- Instance 3: School station (43156) - Line 61

### 4.3 Entity Naming Strategy

**Format:** `sensor.bus_{station_id}_line_{line_number}`

**Examples:**
- `sensor.bus_24068_line_249`
- `sensor.bus_24068_line_40`
- `sensor.bus_37201_line_18`

**Friendly Names (Customizable):**
- "Bus 249 at Arlozorov"
- "Line 40 - Home Station"
- "Work Bus 18"

### 4.4 Sensor State & Attributes

**State Value:**
- Number of minutes until next arrival (e.g., "5")
- "Arrived" if bus is at station
- "No data" if no upcoming arrivals
- "Unavailable" if API error

**Attributes:**
```json
{
  "line_number": "249",
  "station_id": "24068",
  "station_name": "Arlozorov Terminal",
  "next_arrival": "2025-12-24T14:35:00+02:00",
  "real_time": true,
  "direction": "Tel Aviv - Jerusalem",
  "upcoming_arrivals": [
    {
      "time": "2025-12-24T14:35:00+02:00",
      "minutes": 5,
      "real_time": true
    },
    {
      "time": "2025-12-24T14:50:00+02:00",
      "minutes": 20,
      "real_time": false
    }
  ],
  "last_update": "2025-12-24T14:30:15+02:00",
  "attribution": "Data provided by BusNearby"
}
```

---

## 5. Advanced Features

### 5.1 Smart Update Intervals

Adjust update frequency based on context:

- **Active hours** (6:00-22:00): Update every 30 seconds
- **Night hours** (22:00-6:00): Update every 5 minutes
- **When bus is approaching** (<10 min): Update every 15 seconds
- **When no upcoming buses** (>60 min): Update every 5 minutes

### 5.2 Notifications & Automations

Users can create automations based on sensor data:

**Example 1: Alert when bus is 10 minutes away**
```yaml
automation:
  - alias: "Bus 249 approaching"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bus_24068_line_249
        below: 10
    action:
      - service: notify.mobile_app
        data:
          message: "Bus 249 arrives in {{ states('sensor.bus_24068_line_249') }} minutes"
```

**Example 2: Turn on lights when bus is near**
```yaml
automation:
  - alias: "Prepare to leave - bus approaching"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bus_24068_line_249
        below: 5
    action:
      - service: light.turn_on
        target:
          entity_id: light.hallway
```

### 5.3 Lovelace Card Integration

While our integration creates sensors, users can display them using:

**Built-in Cards:**
- **Entity Card**: Simple display of state
- **Entities Card**: List multiple bus lines
- **Glance Card**: Quick overview

**Custom Cards:**
- **Template Card**: Fully customizable display
- **Button Card**: Interactive triggers
- Users can still use original `custom:silent-bus` card if they prefer

**Example Lovelace Configuration:**
```yaml
type: entities
title: Bus Times - Home
entities:
  - entity: sensor.bus_24068_line_249
    name: Line 249
    icon: mdi:bus
  - entity: sensor.bus_24068_line_40
    name: Line 40
    icon: mdi:bus
  - entity: sensor.bus_24068_line_605
    name: Line 605
    icon: mdi:bus
```

### 5.4 Historical Data & Statistics

Integration with Home Assistant's history and statistics:

- Long-term statistics for arrival patterns
- Average wait times per line
- Delay frequency analysis
- Rush hour identification

---

## 6. Implementation Roadmap

### Phase 1: Core Foundation (Week 1)
- [x] Research & planning
- [ ] Create basic file structure
- [ ] Implement `manifest.json`
- [ ] Implement `const.py` with all constants
- [ ] Implement `api.py` with BusNearby client
- [ ] Write unit tests for API client

### Phase 2: Data Management (Week 1-2)
- [ ] Implement `coordinator.py`
- [ ] Test coordinator with real API
- [ ] Implement error handling and retries
- [ ] Add logging and debugging

### Phase 3: Sensor Platform (Week 2)
- [ ] Implement `sensor.py`
- [ ] Create sensor entities with proper attributes
- [ ] Test sensor updates
- [ ] Implement unique ID generation

### Phase 4: Configuration UI (Week 2-3)
- [ ] Implement `config_flow.py`
- [ ] Create station selection step
- [ ] Create bus lines selection step
- [ ] Implement validation
- [ ] Create options flow for reconfiguration
- [ ] Add translations (English + Hebrew)

### Phase 5: Integration Setup (Week 3)
- [ ] Implement `__init__.py`
- [ ] Handle integration load/unload
- [ ] Test multi-instance support
- [ ] Implement device registry

### Phase 6: Testing & Refinement (Week 3-4)
- [ ] Integration testing with real Home Assistant
- [ ] Test error scenarios
- [ ] Test multiple stations
- [ ] Performance optimization
- [ ] Memory leak testing

### Phase 7: Documentation & Release (Week 4)
- [ ] Write comprehensive README
- [ ] Create installation instructions
- [ ] Document configuration options
- [ ] Create example automations
- [ ] Submit to HACS
- [ ] Create GitHub release

---

## 7. Technical Specifications

### 7.1 API Client Specifications

**Base URL:** `https://api.busnearby.co.il`

**Endpoints:**

1. **Search Station**
   - URL: `https://app.busnearby.co.il/stopSearch`
   - Method: GET
   - Parameters:
     - `query`: Station number or name
     - `locale`: "he" or "en"
   - Response: Array of station objects

2. **Get Stop Times**
   - URL: `/directions/index/stops/1:{stop_id}/stoptimes`
   - Method: GET
   - Parameters:
     - `numberOfDepartures`: Integer (default: 1)
     - `timeRange`: Seconds (default: 86400)
     - `currentTime`: Unix timestamp
   - Response: Object with `times` array

**Headers:**
```python
{
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://app.busnearby.co.il"
}
```

### 7.2 Data Models

**Station Object:**
```python
@dataclass
class Station:
    stop_id: str
    name: str
    city: str | None
    lat: float | None
    lon: float | None
```

**Bus Arrival Object:**
```python
@dataclass
class BusArrival:
    line_number: str
    arrival_time: datetime
    is_real_time: bool
    direction: str | None
    service_day: int
    realtime_arrival: int

    @property
    def minutes_until_arrival(self) -> int:
        """Calculate minutes until bus arrives."""
        delta = self.arrival_time - datetime.now()
        return max(0, int(delta.total_seconds() / 60))
```

### 7.3 Configuration Constants

```python
# Update intervals
DEFAULT_SCAN_INTERVAL = 30  # seconds
NIGHT_SCAN_INTERVAL = 300   # 5 minutes
APPROACHING_SCAN_INTERVAL = 15  # 15 seconds

# API settings
API_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Sensor settings
MAX_ARRIVALS_TO_TRACK = 5
DEFAULT_ARRIVALS_DISPLAY = 3

# Time thresholds
APPROACHING_THRESHOLD = 10  # minutes
FAR_AWAY_THRESHOLD = 60     # minutes
```

### 7.4 Error Codes & Messages

```python
ERROR_STATION_NOT_FOUND = "station_not_found"
ERROR_NO_LINES_CONFIGURED = "no_lines_configured"
ERROR_API_UNAVAILABLE = "api_unavailable"
ERROR_INVALID_RESPONSE = "invalid_response"
ERROR_NETWORK_ERROR = "network_error"
ERROR_TIMEOUT = "timeout"
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**api.py Tests:**
- Test station search with valid query
- Test station search with invalid query
- Test stop times retrieval
- Test error handling (network errors, timeouts)
- Test response parsing

**coordinator.py Tests:**
- Test update cycle
- Test error recovery
- Test data distribution to sensors

**sensor.py Tests:**
- Test sensor state calculation
- Test attribute population
- Test unique ID generation

### 8.2 Integration Tests

- Test complete setup flow
- Test with real API (in development environment)
- Test multiple instances
- Test reconfiguration
- Test unload/reload

### 8.3 Manual Testing Checklist

- [ ] Install via HACS
- [ ] Add integration through UI
- [ ] Configure with valid station
- [ ] Verify sensors are created
- [ ] Check sensor updates every 30 seconds
- [ ] Test with invalid station (error handling)
- [ ] Add second instance (different station)
- [ ] Reconfigure existing instance
- [ ] Remove integration
- [ ] Check for memory leaks (long-term test)

---

## 9. Security & Privacy

### 9.1 Data Privacy

- **No personal data collected**: Only station IDs and line numbers
- **No authentication**: Public API, no credentials stored
- **Local processing**: All data processing happens locally
- **No tracking**: No analytics or telemetry

### 9.2 API Security

- Use HTTPS for all API calls
- Validate all API responses
- Sanitize user input (station IDs, line numbers)
- Rate limiting to prevent abuse
- Proper error messages (no sensitive data leakage)

### 9.3 Home Assistant Security

- Follow Home Assistant security guidelines
- Use config entry storage (encrypted)
- No hardcoded credentials
- Proper input validation in config flow

---

## 10. Future Enhancements

### 10.1 Short-term (v1.1)

- [ ] Add support for train stations
- [ ] Implement station auto-discovery based on GPS
- [ ] Add support for favorite stations
- [ ] Create custom Lovelace card (optional)

### 10.2 Medium-term (v1.2-1.3)

- [ ] Support for alternative APIs (SIRI, Open Bus)
- [ ] Offline mode with cached schedules
- [ ] Predictive arrival times using ML
- [ ] Integration with calendar (add bus times to events)

### 10.3 Long-term (v2.0)

- [ ] Multi-modal trip planning
- [ ] Integration with navigation apps
- [ ] Community-driven route optimization
- [ ] Real-time alerts for service disruptions

---

## 11. Alignment Verification

### 11.1 Requirements Checklist

Let's verify we're aligned on all requirements:

✅ **User can add integration via UI** - Config flow implemented
✅ **User can select bus lines** - Multi-line selection in config flow
✅ **Real-time arrival data** - BusNearby API provides real-time data
✅ **Station-based tracking** - User specifies station ID
✅ **Sensor per line** - Each line gets its own sensor entity
✅ **Unique sensor names** - Format: `sensor.bus_{station}_{line}`
✅ **Display arrival times** - State = minutes until arrival
✅ **Additional attributes** - Next arrivals, real-time status, direction
✅ **Automatic updates** - Coordinator polls API every 30 seconds
✅ **Multiple stations** - Support for multiple integration instances
✅ **English interface** - All code, docs, and UI in English (with Hebrew translation support)

### 11.2 Clarification Questions

Before implementation, please confirm:

1. **Station Input Method**: Should users enter station ID directly, or should we provide a search interface? (I've planned for both)

2. **Line Selection**: Should we auto-discover available lines at the station and let users select, or require manual entry? (I've planned for manual with optional auto-discovery)

3. **Sensor Granularity**: Do you want:
   - One sensor per line (recommended) ✓
   - One sensor per station with all lines in attributes
   - Both options

4. **Update Frequency**: Is 30 seconds acceptable, or do you prefer a different default?

5. **Train Support**: Should we include train stations in v1.0, or defer to v1.1?

6. **API Choice**: Are you comfortable with BusNearby API, or would you prefer the official SIRI API?

---

## 12. Summary & Next Steps

### 12.1 What We're Building

A **professional-grade Home Assistant integration** that:
- Provides real-time Israeli bus arrival information
- Uses modern Home Assistant patterns (Config Flow, Coordinator, Entities)
- Supports multiple stations and bus lines
- Updates automatically every 30 seconds
- Integrates seamlessly with Home Assistant UI
- Can be installed via HACS
- Follows all 2025 best practices

### 12.2 Technical Approach

- **API**: BusNearby (reliable, no auth, good data)
- **Architecture**: Config Flow + DataUpdateCoordinator + Sensor Platform
- **Language**: Python 3.11+ with async/await
- **Testing**: Unit tests + integration tests
- **Documentation**: Comprehensive README + inline comments

### 12.3 Immediate Next Steps

Once you confirm the plan above:

1. **Create file structure** - Set up all files and folders
2. **Implement API client** - Build and test BusNearby integration
3. **Create manifest & constants** - Define integration metadata
4. **Implement coordinator** - Build data update mechanism
5. **Create sensors** - Implement sensor platform
6. **Build config flow** - Create UI configuration
7. **Test & refine** - Integration testing
8. **Document & release** - README, HACS submission

**Estimated Timeline:** 3-4 weeks for full implementation and testing

---

## Questions?

Please review this plan carefully and let me know:

1. Are we aligned on the approach?
2. Any changes or additions needed?
3. Any preferences on the clarification questions above?
4. Should I proceed with implementation?

I've made this plan very detailed to ensure we're on the same page. Please provide feedback, and I'll adjust before we start coding!

---

## References

- [Silent Bus Original Project](https://github.com/silentbil/silent-bus)
- [bus-times-ha Integration](https://github.com/UriaKesarii/bus-times-ha)
- [Open Bus Project](https://github.com/hasadna/open-bus)
- [Israel Public Transport API](https://github.com/benyaming/israel-public-transport-api)
- [Home Assistant Config Flow Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [2025 Integration Blueprint](https://github.com/jpawlowski/hacs.integration_blueprint)
- [Home Assistant Developer Guide](https://thehomesmarthome.com/home-assistant-custom-integrations-developers-guide/)
- [BusNearby Website](https://www.bus.co.il/)
