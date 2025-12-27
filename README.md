# Silent Bus - Israeli Public Transportation Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/ziv-daniel/hass-israel-transportation-integration.svg)](https://github.com/ziv-daniel/hass-israel-transportation-integration/releases)
[![License](https://img.shields.io/github/license/ziv-daniel/hass-israel-transportation-integration.svg)](LICENSE)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ziv-daniel&repository=hass-israel-transportation-integration&category=integration)

Track Israeli buses, trains, and light rail in real-time with Home Assistant.

## Features

- **Real-time tracking** - Live arrival times for buses, trains, and light rail
- **Multi-station support** - Monitor multiple stations and routes simultaneously
- **Smart polling** - Dynamic update intervals based on arrival proximity and time of day
- **Rich sensor data** - Detailed attributes including upcoming arrivals, real-time status, and directions
- **Bilingual support** - Full English and Hebrew translations
- **Custom services** - Automation-friendly services for refreshing data and updating lines
- **Easy HACS installation** - One-click installation through HACS

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. In Home Assistant, go to **HACS** → **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add repository URL: `https://github.com/ziv-daniel/hass-israel-transportation-integration`
5. Category: **Integration**
6. Click **Add**
7. Search for "**Silent Bus**" in HACS and click **Download**
8. Restart Home Assistant
9. Go to **Settings** → **Devices & Services** → **Add Integration**
10. Search for "**Silent Bus**" and follow the configuration steps

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/ziv-daniel/hass-israel-transportation-integration/releases)
2. Extract the `custom_components/silent_bus` folder
3. Copy to your Home Assistant `config/custom_components/` directory
4. Restart Home Assistant
5. Add the integration through **Settings** → **Devices & Services**

## Quick Start

### Setup

1. Navigate to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "**Silent Bus**"
3. Select your transport type:
   - **Bus** - Track bus arrivals at stations
   - **Train** - Plan routes between train stations
   - **Light Rail** - Track Jerusalem/Tel Aviv light rail arrivals
4. Enter station details (station ID for buses/light rail, or origin/destination for trains)
5. Configure which lines to track (for buses and light rail)
6. Optionally adjust update interval and maximum arrivals shown

### Finding Station IDs

**Buses & Light Rail:**
- Visit [bus.co.il](https://www.bus.co.il) - Official bus information
- Or use [BusNearby app](https://app.busnearby.co.il) - Real-time tracking

**Trains:**
- Visit [rail.co.il](https://www.rail.co.il) - Israel Railways

**Common train station IDs:**
- Tel Aviv Center (Savidor): `3600`
- Jerusalem Yitzhak Navon: `680`
- Haifa Center (HaShmona): `2800`
- Beer Sheva Center: `5800`
- Ben Gurion Airport: `8600`

## Sensors

### Bus/Light Rail Sensors

**Entity ID format:** `sensor.{type}_station_{station_name}_line_{line_number}`

**Example:** `sensor.bus_station_azrieli_center_line_249`

**State:** Minutes until next arrival
- `5` - Arriving in 5 minutes
- `Arrived` - At station now
- `No data` - No upcoming arrivals
- `Unavailable` - API error or station not found

**Attributes:**
```yaml
line_number: "249"
station_name: "Azrieli Center"
station_id: "24068"
next_arrival: "2025-12-26T14:35:00+02:00"
real_time: true
direction: "Tel Aviv - Jerusalem"
upcoming_arrivals:
  - arrival_time: "2025-12-26T14:35:00+02:00"
    minutes_until: 5
    real_time: true
  - arrival_time: "2025-12-26T14:50:00+02:00"
    minutes_until: 20
    real_time: false
last_update: "2025-12-26T14:30:15+02:00"
```

### Train Sensors

**Entity ID format:** `sensor.train_route_{from_station}_{to_station}_next_train`

**Example:** `sensor.train_route_tel_aviv_center_haifa_center_next_train`

**State:** Minutes until next departure

**Attributes:**
```yaml
from_station: "3600"
from_station_name: "Tel Aviv Center"
to_station: "2800"
to_station_name: "Haifa Center"
next_arrival: "2025-12-26T14:45:00+02:00"
duration_minutes: 65
upcoming_arrivals:
  - departure_time: "2025-12-26T14:45:00+02:00"
    arrival_time: "2025-12-26T15:50:00+02:00"
    minutes_until: 15
    duration_minutes: 65
```

## Automation Examples

### Notify When Bus Approaching

```yaml
automation:
  - alias: "Bus 249 Approaching Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.bus_station_azrieli_center_line_249
      below: 10
    action:
      service: notify.mobile_app_phone
      data:
        message: "Bus 249 arrives in {{ states('sensor.bus_station_azrieli_center_line_249') }} minutes!"
        title: "Bus Alert"
```

### Turn On Lights When Leaving for Work

```yaml
automation:
  - alias: "Prepare to Leave for Work"
    trigger:
      platform: numeric_state
      entity_id: sensor.bus_station_home_line_40
      below: 5
    condition:
      - condition: time
        after: "06:00:00"
        before: "09:00:00"
      - condition: state
        entity_id: person.me
        state: "home"
    action:
      - service: light.turn_on
        target:
          entity_id: light.hallway
      - service: notify.mobile_app_phone
        data:
          message: "Time to leave! Bus in {{ states('sensor.bus_station_home_line_40') }} minutes"
```

## Services

### `silent_bus.refresh_data`

Force immediate data refresh for sensors.

```yaml
service: silent_bus.refresh_data
data:
  entity_id: sensor.bus_station_azrieli_center_line_249
```

*Omit `entity_id` to refresh all Silent Bus sensors.*

### `silent_bus.update_lines`

Dynamically update which bus lines are tracked (bus/light rail only).

```yaml
service: silent_bus.update_lines
data:
  entity_id: sensor.bus_station_azrieli_center_line_249
  lines: "249, 40, 605"
```

## Configuration Options

Adjust these settings via **Configure** in the integration settings:

- **Update Interval**: 15-600 seconds (default: 30)
- **Maximum Arrivals**: 1-10 per line (default: 3)

## Smart Features

### Dynamic Polling

The integration automatically adjusts update frequency:
- **Bus approaching** (<10 min): Every 15 seconds
- **Normal hours** (6:00-22:00): Every 30 seconds
- **Night hours** (22:00-6:00): Every 5 minutes
- **No upcoming buses** (>60 min): Every 5 minutes

### Error Handling

- Automatic retries with exponential backoff
- Graceful handling of API failures
- Clear error messages in sensor attributes

## Troubleshooting

**Sensors not updating?**
1. Check your internet connection
2. Verify station ID is correct at [bus.co.il](https://www.bus.co.il)
3. Check Home Assistant logs for error messages

**Station not found error?**
1. Verify the station number has no prefix (use only digits)
2. Some small stations may not be available in the API
3. Try searching for nearby stations

**No data for specific line?**
1. Verify the line serves this station
2. Check if the line is currently operating (time/day restrictions)
3. Some lines may not provide real-time data

## Support

- **Report bugs**: [GitHub Issues](https://github.com/ziv-daniel/hass-israel-transportation-integration/issues)
- **Ask questions**: [GitHub Discussions](https://github.com/ziv-daniel/hass-israel-transportation-integration/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- Developed by [@ziv-daniel](https://github.com/ziv-daniel)
- Data provided by [BusNearby](https://app.busnearby.co.il)
- Icon and branding by Silent Bus community

---

**Disclaimer**: This is an unofficial integration and is not affiliated with the Israeli Ministry of Transportation, BusNearby, or any public transportation operator.
