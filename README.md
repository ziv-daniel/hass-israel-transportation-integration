# Israel Transportation — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/ziv-daniel/hass-israel-transportation-integration.svg?style=for-the-badge&color=blue)](https://github.com/ziv-daniel/hass-israel-transportation-integration/releases)
[![License](https://img.shields.io/github/license/ziv-daniel/hass-israel-transportation-integration.svg?style=for-the-badge&color=blue)](LICENSE)

[![hassfest](https://img.shields.io/github/actions/workflow/status/ziv-daniel/hass-israel-transportation-integration/hassfest.yaml?branch=main&label=hassfest&style=flat-square)](https://github.com/ziv-daniel/hass-israel-transportation-integration/actions/workflows/hassfest.yaml)
[![HACS](https://img.shields.io/github/actions/workflow/status/ziv-daniel/hass-israel-transportation-integration/hacs.yaml?branch=main&label=HACS&style=flat-square)](https://github.com/ziv-daniel/hass-israel-transportation-integration/actions/workflows/hacs.yaml)
[![Tests](https://img.shields.io/github/actions/workflow/status/ziv-daniel/hass-israel-transportation-integration/test.yaml?branch=main&label=tests&style=flat-square)](https://github.com/ziv-daniel/hass-israel-transportation-integration/actions/workflows/test.yaml)

Track Israeli buses, trains and light rail in Home Assistant. Each tracked line becomes a sensor whose state is the number of minutes until the next arrival, with the following departures, direction and operator as attributes — ready for dashboards and automations.

## Features

- 🚌 **Buses and 🚊 light rail** — departures for any stop, filtered to the lines you care about
- 🚆 **Trains** — next departure for a route, with platform, train number and journey time
- 🎯 **Multiple stations** — add as many stops and routes as you like
- 🔄 **Adaptive polling** — checks more often when a bus is close, backs off overnight
- 🌍 **Hebrew and English** — station and direction names come through in Hebrew
- 📊 **Rich attributes** — `upcoming_arrivals`, `direction`, `real_time`, `operator`
- ⚙️ **UI setup** — browse stops by city, or type a stop code directly
- 🛠️ **Services** — force a refresh, or change tracked lines without re-adding the entry

## Requirements

- Home Assistant **2025.11.0** or newer
- Outbound internet access to `api.bus.gov.il` (bus, light rail) and `rail.co.il` (trains)

No API key, account or registration is needed for either service.

## Installation

### HACS

If the repository is not in your HACS yet:

1. HACS → ⋮ (top right) → **Custom repositories**
2. URL: `https://github.com/ziv-daniel/hass-israel-transportation-integration`
3. Category: **Integration** → **Add**

Then:

1. HACS → search for **Israel Transportation** → open it
2. **Download**, pick the version, and **Restart Home Assistant**

#### Installing a beta

Beta builds are published as pre-releases. In the download dialog, turn on
**Show beta versions** — betas are hidden without it — then pick the
`x.y.z-beta.n` build.

### Manual

```bash
cd /config/custom_components
curl -sL https://github.com/ziv-daniel/hass-israel-transportation-integration/archive/refs/tags/vX.Y.Z.tar.gz | tar -xz
mv hass-israel-transportation-integration-X.Y.Z/custom_components/israel_transportation .
rm -rf hass-israel-transportation-integration-X.Y.Z
```

Restart Home Assistant afterwards.

## Configuration

### Adding a station or route

**Settings** → **Devices & Services** → **Add Integration** → **Israel Transportation**.

1. **Transport type** — Bus, Train or Light Rail.
2. **How to find the station**:
   - *Browse stations by city* — pick a city, then a stop from the list. Recommended; you don't need to know any numbers.
   - *Enter station ID manually* — type the stop code if you already know it.
3. **Bus / light rail**: enter the line numbers to track, comma separated (e.g. `249, 40, 605`). Only these lines get sensors.
   **Trains**: pick the origin and destination stations from the dropdowns.

Repeat to add more stops or routes — each becomes its own entry.

### Finding a stop code

The **stop code** (מק"ט) is the number printed on the physical stop sign, and
it is what this integration expects. You can find it on the
[MOT route planner](https://route.bus.gov.il) by searching for the stop, or
simply use *Browse stations by city* during setup and skip the lookup entirely.

> **Note** — a stop code is not the same as a GTFS `stop_id`. They are both
> short numbers in overlapping ranges, so it is easy to mistake one for the
> other, and a `stop_id` used as a stop code will silently resolve to a
> completely different station. If a stop resolves to an unexpected name,
> this is usually why.

Train stations are chosen from a built-in dropdown, so no lookup is needed.

### Options

Click **Configure** on an entry to change:

| Option | Range | Default |
|---|---|---|
| Bus lines | comma-separated | — |
| Update interval | 15–600 s | 30 s |
| Maximum arrivals | 1–10 | 3 |

Tracking fewer lines is meaningfully cheaper: departure times are fetched
per route, so a stop with many lines and no filter costs many requests per poll.

## Sensors

### Bus and light rail

One sensor per tracked line: `sensor.bus_station_{station}_line_{line}`
(light rail uses `light_rail_station_…`).

**State** — minutes until the next arrival, e.g. `7`. The state is `unknown`
when no upcoming departures are known (outside service hours, or the line does
not currently serve the stop), and `unavailable` when the last update failed.

**Attributes**

```yaml
line_number: "249"
station_id: "24068"
station_name: "ת. רכבת תל אביב - סבידור/דרך נמיר"
direction: "כפר סבא_תחנה מרכזית"
real_time: false
next_arrival: "2026-08-19T21:12:00+03:00"
last_update: "2026-08-19T21:00:24+03:00"
upcoming_arrivals:
  - arrival_time: "2026-08-19T21:12:00+03:00"
    minutes_until: 12
    is_realtime: false
    direction: "כפר סבא_תחנה מרכזית"
    operator: "מטרופולין"
```

`real_time` reflects what the MOT API reports for that departure. Much of the
data is timetable-based, so `false` is common and simply means the time is
scheduled rather than live-tracked.

### Trains

One sensor per route: `sensor.train_route_{from}_{to}_next_train`

**State** — minutes until the next departure, or `unknown` when no departures
are known and `unavailable` after a failed update.

**Attributes**

```yaml
from_station: "3600"
to_station: "7320"
from_station_name: "Tel Aviv-University"
to_station_name: "Be'er Sheva-Center"
direction: "Be'er Sheva-Center"
duration_minutes: 105
real_time: false
next_arrival: "2026-08-19T21:05:00+03:00"
upcoming_arrivals:
  - arrival_time: "2026-08-19T21:05:00+03:00"
    minutes_until: 164
    duration_minutes: 105
    is_realtime: false
    direction: "Be'er Sheva-Center"
    platform: 2
    train_number: "43"
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
          {% set times = lines | reject('in', ['unknown', 'unavailable']) | map('int') | list %}
          {% if times | length > 0 %}
            {{ times | min }}
          {% else %}
            unknown
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
      - service: israel_transportation.refresh_data
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
      - service: israel_transportation.update_lines
        data:
          entity_id: sensor.bus_station_azrieli_center_line_249
          lines: "249, 40, 189"  # Morning express lines

  - alias: "Update Bus Lines for Evening Commute"
    trigger:
      - platform: time
        at: "17:00:00"
    action:
      - service: israel_transportation.update_lines
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
      - service: israel_transportation.refresh_data
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

### `israel_transportation.refresh_data`

Force an immediate refresh, for when you want current times before deciding something.

| Parameter | Required | Meaning |
|---|---|---|
| `entity_id` | no | Entity to refresh; omit to refresh every entity |

```yaml
action: israel_transportation.refresh_data
data:
  entity_id: sensor.bus_station_azrieli_center_line_249
```

### `israel_transportation.update_lines`

Change which lines a stop tracks, without removing and re-adding the entry.
Bus and light rail only.

| Parameter | Required | Meaning |
|---|---|---|
| `entity_id` | yes | Entity to update |
| `lines` | yes | Comma-separated line numbers |

```yaml
action: israel_transportation.update_lines
data:
  entity_id: sensor.bus_station_azrieli_center_line_249
  lines: "249, 40, 605"
```

## Behaviour

### Polling

The update interval adapts to how soon your ride arrives:

| Situation | Interval |
|---|---|
| Next arrival under 10 min | 15 s |
| Normal hours (06:00–22:00) | 30 s (configurable) |
| Night (22:00–06:00) | 5 min |
| Nothing due for over an hour | 5 min |

### When the upstream API is unavailable

Entries stay **loaded** and their sensors report `unavailable`; they recover on
their own once the API responds again. Setup deliberately does not verify the
station against the live API, so an upstream outage cannot leave a
previously-working station permanently unconfigurable.

Failures are logged with enough detail to tell apart a network problem, a rate
limit, and an endpoint that has changed shape upstream.

## Data sources

| Transport | Source |
|---|---|
| Bus, light rail | `api.bus.gov.il` — the API behind the Ministry of Transport's own [route planner](https://route.bus.gov.il) |
| Trains | Israel Railways, via the [`israel-rail-api`](https://pypi.org/project/israel-rail-api/) package |
| Station lists | MOT GTFS feed, rebuilt every 3 days and shipped as a release asset |

Neither API requires authentication.

## Troubleshooting

Enable debug logging to see exactly what the integration is doing:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.israel_transportation: debug
```

**A sensor is `unknown`** — no upcoming departures are known for that line right
now. Check the line actually serves that stop, and that it runs at this hour;
many lines stop in the evening and Shabbat timetables differ. The log names the
lines the stop does serve when your filter matches nothing.

**A sensor is `unavailable`** — the last update failed. The log will say why.

**The station resolves to the wrong name** — you have probably entered a GTFS
`stop_id` rather than the stop code from the sign. See
[Finding a stop code](#finding-a-stop-code).

**Setup fails with "cannot connect"** — the MOT API was unreachable or returned
something unexpected. The log records the response content type and the first
bytes of the body, which distinguishes an outage from an endpoint that has moved.

**No icon in Settings → Devices & Services** — requires Home Assistant
2026.3.0 or newer. Earlier cores don't read local brand images and always
show the placeholder; this is cosmetic and does not affect functionality.

## Development

```bash
git clone https://github.com/ziv-daniel/hass-israel-transportation-integration.git
cd hass-israel-transportation-integration
pip install -r requirements_test.txt
pre-commit install
```

**Python 3.14 is required** for the test suite —
`pytest-homeassistant-custom-component` requires it from 0.13.317 onward.

```bash
pytest tests/ --cov=custom_components.israel_transportation --cov-fail-under=70
pre-commit run --all-files
mypy custom_components/israel_transportation --ignore-missing-imports
bandit -r custom_components/israel_transportation -ll --exclude custom_components/israel_transportation/gtfs_data
```

`pytest`, `pytest-asyncio` and `pytest-cov` are intentionally left unpinned in
`requirements_test.txt`: `pytest-homeassistant-custom-component` pins them
exactly, and adding our own floors has twice made the file unresolvable. They
are on Dependabot's ignore list for the same reason.

Tests must not reach the network — the shared fixtures stub the GTFS download,
and the Home Assistant test harness fails any test that opens a socket.

### CI

| Workflow | Purpose |
|---|---|
| Tests | pytest on Python 3.14, 70% coverage floor |
| Quality checks | mypy and bandit |
| Pre-commit | Ruff lint and format, codespell |
| Hassfest / HACS | Home Assistant and HACS structure validation |
| Auto Beta Version | Bumps the version and publishes a pre-release on every merge to `main` |
| Update GTFS Data | Rebuilds the station index every 3 days |

### Contributing

1. Fork and branch (`git checkout -b fix/thing`)
2. Make the change, with a test that fails without it
3. `pre-commit run --all-files` and `pytest tests/`
4. Open a pull request

## License

MIT — see [LICENSE](LICENSE).

## Credits

- Integration by [@ziv-daniel](https://github.com/ziv-daniel)
- Bus and light rail data from the Israeli Ministry of Transport
- Train data via [`israel-rail-api`](https://pypi.org/project/israel-rail-api/)
- Inspired by the original [silent-bus](https://github.com/silentbil/silent-bus) Lovelace card

## Support

- 🐛 [Report a bug](https://github.com/ziv-daniel/hass-israel-transportation-integration/issues)
- 💬 [Discussions](https://github.com/ziv-daniel/hass-israel-transportation-integration/discussions)
- 📝 [Changelog](CHANGELOG.md)

---

**Disclaimer** — unofficial integration, not affiliated with or endorsed by the
Israeli Ministry of Transport or Israel Railways. It reads the same public
endpoints their own website uses; those may change without notice.
