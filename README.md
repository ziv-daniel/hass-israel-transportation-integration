# Silent Bus - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/ziv-daniel/Silent-bus-integration.svg?style=for-the-badge)](https://github.com/ziv-daniel/Silent-bus-integration/releases)
[![License](https://img.shields.io/github/license/ziv-daniel/Silent-bus-integration.svg?style=for-the-badge)](LICENSE)

[![hassfest](https://img.shields.io/github/actions/workflow/status/ziv-daniel/Silent-bus-integration/hassfest.yaml?branch=main&label=hassfest&style=flat-square)](https://github.com/ziv-daniel/Silent-bus-integration/actions/workflows/hassfest.yaml)
[![HACS](https://img.shields.io/github/actions/workflow/status/ziv-daniel/Silent-bus-integration/hacs.yaml?branch=main&label=HACS&style=flat-square)](https://github.com/ziv-daniel/Silent-bus-integration/actions/workflows/hacs.yaml)
[![Tests](https://img.shields.io/github/actions/workflow/status/ziv-daniel/Silent-bus-integration/test.yaml?branch=main&label=tests&style=flat-square)](https://github.com/ziv-daniel/Silent-bus-integration/actions/workflows/test.yaml)

A comprehensive Home Assistant integration for monitoring Israeli public transportation in real-time. Track buses, trains, and light rail with live arrival times and get notified when your ride is approaching.

## Features

- 🚌 **Real-time Bus Tracking** - Get live arrival times for Israeli buses
- 🚆 **Train Route Support** - Monitor train departures between stations
- 🚊 **Light Rail (Kala) Support** - Track Jerusalem and Tel Aviv light rail
- 🎯 **Multi-Station Support** - Monitor multiple stations and routes simultaneously
- 🔄 **Automatic Updates** - Smart polling with dynamic update intervals
- 🌍 **Bilingual** - Full support for Hebrew and English
- 📊 **Rich Sensor Data** - Detailed attributes including direction, real-time status, and upcoming arrivals
- ⚙️ **Easy Configuration** - User-friendly UI configuration flow for all transport types
- 🔔 **Automation Ready** - Perfect for creating arrival notifications and automations
- 🛠️ **Custom Services** - Force refresh and dynamically update tracked lines
- 📈 **Long-term Statistics** - Sensor data compatible with Home Assistant history and statistics
- ⚡ **Device Class Support** - Proper duration device class for time-based sensors

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/ziv-daniel/Silent-bus-integration`
6. Select category: "Integration"
7. Click "Add"
8. Find "Silent Bus" in the integrations list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/ziv-daniel/Silent-bus-integration/releases)
2. Extract the `custom_components/silent_bus` folder
3. Copy it to your Home Assistant `custom_components` directory
4. Restart Home Assistant

## Configuration

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Silent Bus**
4. Follow the configuration steps:
   - **Step 1**: Select transport type (Bus, Train, or Light Rail)
   - **For Buses/Light Rail**:
     - **Step 2**: Enter station number (e.g., `24068`)
     - **Step 3**: Enter line numbers separated by commas (e.g., `249, 40, 605`)
   - **For Trains**:
     - **Step 2**: Enter origin station (e.g., `3600` for Tel Aviv Center)
     - **Step 2**: Enter destination station (e.g., `2800` for Haifa Center)

### Finding Station Numbers

#### Buses and Light Rail
- [bus.co.il](https://www.bus.co.il) - Official Israeli bus information site
- [BusNearby](https://app.busnearby.co.il) - Real-time bus tracking app

#### Trains
- [rail.co.il](https://www.rail.co.il) - Israel Railways official site

Common train station IDs:
- Tel Aviv - Savidor Center: `3600`
- Tel Aviv - HaShalom: `3700`
- Jerusalem - Yitzhak Navon: `680`
- Haifa Center - HaShmona: `2800`
- Beer Sheva Center: `5800`
- Ben Gurion Airport: `8600`

### Configuration Options

After setup, you can modify settings by clicking **Configure** on the integration:

- **Bus Lines**: Comma-separated list of bus line numbers to track
- **Update Interval**: How often to fetch data (15-600 seconds, default: 30)
- **Maximum Arrivals**: Number of upcoming arrivals to track per line (1-10, default: 3)

## Sensors

### Bus and Light Rail Sensors

The integration creates one sensor per line:

**Entity ID**: `sensor.{type}_station_{station_name}_line_{line_number}`

**Example**:
- Bus: `sensor.bus_station_azrieli_center_line_249`
- Light Rail: `sensor.light_rail_station_central_station_line_1`

#### Sensor State

Shows minutes until the next arrival:
- `5` - Arriving in 5 minutes
- `Arrived` - Currently at the station
- `No data` - No upcoming arrivals
- `Unavailable` - API connection error

#### Bus/Light Rail Sensor Attributes

```yaml
line_number: "249"
station_id: "24068"
station_name: "Azrieli Center"
next_arrival: "2025-12-25T14:35:00+02:00"
real_time: true
direction: "Tel Aviv - Jerusalem"
upcoming_arrivals:
  - arrival_time: "2025-12-25T14:35:00+02:00"
    minutes_until: 5
    is_realtime: true
    direction: "Tel Aviv - Jerusalem"
```

### Train Sensors

One sensor per route:

**Entity ID**: `sensor.train_route_{from}_{to}_next_train`

**Example**: `sensor.train_route_tel_aviv_center_haifa_center_next_train`

#### Train Sensor State

Shows minutes until next departure:
- `15` - Departing in 15 minutes
- `Departing` - Train is departing now
- `No data` - No upcoming trains

#### Train Sensor Attributes

```yaml
from_station: "3600"
to_station: "2800"
from_station_name: "Tel Aviv - Savidor Center"
to_station_name: "Haifa Center - HaShmona"
next_arrival: "2025-12-25T14:45:00+02:00"
duration_minutes: 65
real_time: true
direction: "Haifa Center - HaShmona"
upcoming_arrivals:
  - arrival_time: "2025-12-25T14:45:00+02:00"
    minutes_until: 15
    duration_minutes: 65
    is_realtime: true
```

## Usage Examples

### Dashboard Card

Display public transport times using the built-in entities card:

```yaml
type: entities
title: Public Transport
entities:
  - entity: sensor.bus_station_azrieli_center_line_249
    name: Bus 249
  - entity: sensor.light_rail_station_central_station_line_1
    name: Light Rail 1
  - entity: sensor.train_route_tel_aviv_center_haifa_center_next_train
    name: Train to Haifa
```

Icons are automatically set based on transport type:
- 🚌 Bus: `mdi:bus`
- 🚊 Light Rail: `mdi:tram`
- 🚆 Train: `mdi:train`

### Automation: Notify When Bus Approaching

Get notified when your bus is 10 minutes away:

```yaml
automation:
  - alias: "Bus 249 Approaching"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bus_station_azrieli_center_line_249
        below: 10
    condition:
      - condition: numeric_state
        entity_id: sensor.bus_station_azrieli_center_line_249
        above: 0
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Bus 249 Approaching"
          message: "Bus arrives in {{ states('sensor.bus_station_azrieli_center_line_249') }} minutes"
```

### Automation: Train Departure Notification

Get notified when your train is departing soon:

```yaml
automation:
  - alias: "Train to Haifa Departing Soon"
    trigger:
      - platform: numeric_state
        entity_id: sensor.train_route_tel_aviv_center_haifa_center_next_train
        below: 15
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Train Departing Soon"
          message: >
            Train to {{ state_attr('sensor.train_route_tel_aviv_center_haifa_center_next_train', 'to_station_name') }}
            departs in {{ states('sensor.train_route_tel_aviv_center_haifa_center_next_train') }} minutes.
            Journey time: {{ state_attr('sensor.train_route_tel_aviv_center_haifa_center_next_train', 'duration_minutes') }} min
```

### Automation: Turn On Lights When Bus is Near

Prepare to leave when bus is 5 minutes away:

```yaml
automation:
  - alias: "Prepare to Leave - Bus Approaching"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bus_station_azrieli_center_line_249
        below: 5
    action:
      - service: light.turn_on
        target:
          entity_id: light.hallway
      - service: notify.mobile_app_your_phone
        data:
          message: "Time to leave! Bus 249 in {{ states('sensor.bus_station_azrieli_center_line_249') }} min"
```

### Template Sensor: Next Bus Across Multiple Lines

Create a sensor showing the soonest bus from multiple lines:

```yaml
template:
  - sensor:
      - name: "Next Bus Home"
        state: >
          {% set lines = [
            states('sensor.bus_station_azrieli_center_line_249'),
            states('sensor.bus_station_azrieli_center_line_40'),
            states('sensor.bus_station_azrieli_center_line_605')
          ] %}
          {% set times = lines | reject('in', ['No data', 'Arrived', 'unavailable']) | map('int') | list %}
          {% if times | length > 0 %}
            {{ times | min }}
          {% else %}
            No data
          {% endif %}
        unit_of_measurement: "min"
        icon: mdi:bus-clock
```

### Automation: Force Refresh Before Leaving

Refresh arrival times when you're getting ready to leave:

```yaml
automation:
  - alias: "Refresh Bus Times When Leaving"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: silent_bus.refresh_data
        data:
          entity_id: sensor.bus_station_azrieli_center_line_249
```

### Automation: Dynamic Line Updates

Update tracked lines based on time of day:

```yaml
automation:
  - alias: "Update Bus Lines for Morning Commute"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: silent_bus.update_lines
        data:
          entity_id: sensor.bus_station_azrieli_center_line_249
          lines: "249, 40, 189"  # Morning express lines

  - alias: "Update Bus Lines for Evening Commute"
    trigger:
      - platform: time
        at: "17:00:00"
    action:
      - service: silent_bus.update_lines
        data:
          entity_id: sensor.bus_station_azrieli_center_line_249
          lines: "249, 40, 605"  # Evening lines
```

### Script: Check Next Bus and Decide

Create a script to check if you need to hurry:

```yaml
script:
  check_bus_status:
    sequence:
      - service: silent_bus.refresh_data
      - delay:
          seconds: 2
      - choose:
          - conditions:
              - condition: numeric_state
                entity_id: sensor.bus_station_azrieli_center_line_249
                below: 5
            sequence:
              - service: notify.mobile_app_your_phone
                data:
                  title: "Hurry!"
                  message: "Bus arrives in {{ states('sensor.bus_station_azrieli_center_line_249') }} minutes!"
                  data:
                    priority: high
          - conditions:
              - condition: numeric_state
                entity_id: sensor.bus_station_azrieli_center_line_249
                above: 15
            sequence:
              - service: notify.mobile_app_your_phone
                data:
                  message: "You have {{ states('sensor.bus_station_azrieli_center_line_249') }} minutes. No rush!"
```

For more examples including train and light rail configurations, see [examples/configuration_examples.yaml](examples/configuration_examples.yaml).

## Services

The integration provides custom services for advanced automation scenarios:

### `silent_bus.refresh_data`

Force an immediate refresh of arrival times data. Useful when you want the latest information before making a decision.

**Parameters:**
- `entity_id` (optional): Specific entity to refresh. If not provided, all Silent Bus integrations will be refreshed.

**Example:**
```yaml
service: silent_bus.refresh_data
data:
  entity_id: sensor.bus_station_azrieli_center_line_249
```

### `silent_bus.update_lines`

Dynamically update the bus lines being tracked for a station. Perfect for adjusting monitored routes based on time of day or other conditions. Only works for bus and light rail sensors, not trains.

**Parameters:**
- `entity_id` (required): The Silent Bus entity to update
- `lines` (required): Comma-separated list of bus line numbers

**Example:**
```yaml
service: silent_bus.update_lines
data:
  entity_id: sensor.bus_station_azrieli_center_line_249
  lines: "249, 40, 605"
```

## Smart Features

### Dynamic Update Intervals

The integration automatically adjusts update frequency based on context:

- **Bus approaching** (<10 min): Updates every 15 seconds
- **Normal hours** (6:00-22:00): Updates every 30 seconds (default)
- **Night hours** (22:00-6:00): Updates every 5 minutes
- **No upcoming buses** (>60 min): Updates every 5 minutes

This optimizes API usage while ensuring timely updates when you need them most.

### Error Handling

The integration includes robust error handling:

- **Automatic retries** with exponential backoff for network errors
- **Graceful degradation** when API is unavailable
- **Clear error messages** in the UI
- **Sensor availability tracking** - sensors marked unavailable during errors

## Data Source

This integration uses the [BusNearby API](https://app.busnearby.co.il), which provides real-time Israeli public transportation data. The API does not require authentication and is free to use.

## Troubleshooting

### Sensors Not Updating

1. Check your internet connection
2. Verify the station ID is correct
3. Ensure the bus lines serve that station
4. Check Home Assistant logs for errors: `Configuration` → `Logs`

### Station Not Found During Setup

- Double-check the station number at [bus.co.il](https://www.bus.co.il)
- Try entering the station number without any prefix
- Some stations may not be available in the API

### No Data for Specific Line

- Verify the line number is correct
- Check if the line serves this station
- The line may not be operating at the current time

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/ziv-daniel/Silent-bus-integration.git
cd Silent-bus-integration

# Install development dependencies
pip install -r requirements_test.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=custom_components.silent_bus --cov-report=html

# Run specific test file
pytest tests/unit/test_api.py

# Run pre-commit checks manually
pre-commit run --all-files
```

### CI/CD Pipeline

This integration uses GitHub Actions for automated testing and validation:

- **Hassfest**: Validates integration structure and Home Assistant compatibility
- **HACS Validation**: Ensures HACS repository standards compliance
- **Tests**: Runs pytest across Python 3.12/3.13 and multiple HA versions
- **Pre-commit**: Automated code formatting and linting with Ruff
- **Release Drafter**: Automatically generates release notes from PRs
- **Dependabot**: Keeps dependencies and actions up to date

All workflows run automatically on push and pull requests.

### Code Quality

This project uses:
- **Ruff** for fast Python linting and formatting
- **pytest** with coverage reporting via Codecov
- **Pre-commit hooks** for automated code quality checks

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and ensure tests pass
4. Run pre-commit checks: `pre-commit run --all-files`
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

All PRs are automatically validated by CI/CD workflows.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- Integration developed by [@ziv-daniel](https://github.com/ziv-daniel)
- Data provided by [BusNearby](https://app.busnearby.co.il)
- Inspired by the original [silent-bus](https://github.com/silentbil/silent-bus) Lovelace card

## Support

- 🐛 **Report bugs**: [GitHub Issues](https://github.com/ziv-daniel/Silent-bus-integration/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/ziv-daniel/Silent-bus-integration/discussions)
- 📖 **Documentation**: [Integration Plan](INTEGRATION_PLAN.md)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

**Disclaimer**: This is an unofficial integration and is not affiliated with or endorsed by the Israeli Ministry of Transportation or BusNearby.
