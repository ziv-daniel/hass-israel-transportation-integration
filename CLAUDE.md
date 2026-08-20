# Israel Transportation HA Integration

Custom Home Assistant integration for real-time Israeli public transportation (buses, trains, light rail).

## Testing

### Unit/Integration Tests (no Docker needed)
```bash
pip install -r requirements_test.txt
pytest tests/ --cov=custom_components.israel_transportation --cov-fail-under=70
```
Tests use `pytest-homeassistant-custom-component` which provides an in-process HA mock. No Docker container is needed.

`pytest-homeassistant-custom-component` requires **Python 3.14** from version 0.13.317 onward — CI runs on 3.14. `pytest`, `pytest-asyncio` and `pytest-cov` are deliberately left unpinned in `requirements_test.txt`: phcc pins them exactly, and giving them our own floors made the file unresolvable twice. Let phcc decide; they're on Dependabot's ignore list for the same reason.

### Live Integration Testing (ha-test container)

For testing against a real Home Assistant instance, a test container exists on the Proxmox host:

- **Location:** `/opt/homelab/ha-test/docker-compose.yml` on Proxmox (192.168.68.200)
- **Image:** `ghcr.io/home-assistant/home-assistant:stable`
- **Config mount:** `/opt/homelab/ha-test/config` -> `/config`
- **Port:** the compose file maps host port **8124** to container port 8123 — the instance is at `http://192.168.68.200:8124`, not 8123.
- **Restart policy:** `no` (does not auto-restart)
- **HACS is not installed** on this instance. Deploy by copying `custom_components/israel_transportation/` directly into the config's `custom_components/`; the HACS install/update path can't be exercised here.
- **DNS on that host is flaky** — roughly a quarter of lookups fail, for any hostname. Expect intermittent `unavailable` sensor states unrelated to integration bugs; don't chase these as regressions.

#### Lifecycle

1. **Start** the test container before live testing:
   ```bash
   # Via Docker API (from any machine on the network)
   curl -X POST http://192.168.68.200:2375/containers/ha-test/start

   # Or via SSH on Proxmox
   cd /opt/homelab/ha-test && docker compose up -d
   ```

   The container is frequently **absent**, not merely stopped — see Auto-Cleanup below — in which case `start` 404s. Recreate it via the Docker API from the compose spec:
   ```bash
   curl -X POST http://192.168.68.200:2375/containers/create?name=ha-test \
     -H "Content-Type: application/json" \
     -d '{
       "Image": "ghcr.io/home-assistant/home-assistant:stable",
       "Env": ["TZ=Asia/Jerusalem"],
       "HostConfig": {
         "Privileged": true,
         "Binds": ["/opt/homelab/ha-test/config:/config"],
         "PortBindings": {"8123/tcp": [{"HostPort": "8124"}]},
         "RestartPolicy": {"Name": "no"}
       },
       "ExposedPorts": {"8123/tcp": {}}
     }'
   curl -X POST http://192.168.68.200:2375/containers/ha-test/start
   ```
   The image is normally already cached on the host — registry pulls from it fail (broken IPv6 route), so recreating from the cached image works but a fresh pull won't.

2. **Sync code** to the test HA instance:
   ```powershell
   # From Windows - sync via Samba to ha-test config
   .\sync-to-homeassistant.ps1
   ```
   From a non-Windows machine without Samba access, upload via the Docker API instead: tar the `custom_components/israel_transportation` directory and `PUT` it to `/containers/ha-test/archive?path=/config/custom_components` (or via a helper container bind-mounted to `/opt/homelab`, then copy on the host filesystem directly).

3. **Stop** the test container when done:
   ```bash
   curl -X POST http://192.168.68.200:2375/containers/ha-test/stop

   # Or via SSH
   cd /opt/homelab/ha-test && docker compose down
   ```

#### Auto-Cleanup

The infrastructure cleanup cron (runs nightly at 03:00) will automatically:
- **Stop and remove** `ha-test` if it has been running for more than **2 hours**
- **Remove** `ha-test` if it is in exited state

This is a safety net. Tests take ~5 minutes, so always `docker compose down` when done.

## Project Structure

```
custom_components/israel_transportation/
  __init__.py          # Integration setup
  sensor.py            # Sensor platform
  config_flow.py       # Config flow UI
  coordinator.py       # Data update coordinator
  gov_api.py           # Bus/light-rail client (api.bus.gov.il, the MOT route planner's own API)
  api.py               # Legacy BusNearby client — train station search only; its arrivals endpoint is 403'd
  gtfs_loader.py        # Bundled GTFS station index (city/station browsing in the config flow)
  manifest.json         # Integration manifest
  brand/                # Local brand icon (icon.png, icon@2x.png) — HA 2026.3.0+ picks these up automatically
  translations/          # i18n (en, he)
tests/
  conftest.py          # Fixtures (mock API clients, config entries)
  unit/                # Unit tests
  integration/          # Integration tests
  e2e/                 # End-to-end tests
```

Bus/light-rail stops are addressed by **stop_code** (the number on the physical stop sign), not the GTFS `stop_id` bundled in `gtfs_loader.py`'s index — the two are different numbers in overlapping ranges. Train stations from `israelrailapi.stations.RAIL_STATIONS` (via `config_flow.get_train_stations_list()`) are the only source of truth for train station codes — there is no local fallback table; don't hand-maintain one, it will silently drift.

## Sync Scripts

- `sync-to-homeassistant.ps1` - Full sync via Samba (`robocopy /MIR`), supports `-Watch` for auto-sync
- `quick-sync.ps1` - Quick copy of `.py` files only
- `check_ha_logs.ps1` - Read HA logs filtered for this integration
