# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2026-08-20

### Fixed
- Train sensors could show "Next Train: 0m" when a real train was actually minutes away. The Israel Rail API doesn't strictly filter to future departures and sometimes returns a train that has already left (observed up to 26 minutes in the past) ahead of the real upcoming ones; that negative time-to-departure was clamped to 0 and sorted ahead of the correct next train instead of being filtered out.

### Changed
- A stale, unused, hand-maintained train station list (`scripts/train_stations.py`) was removed. It was never read at runtime — the config flow already sources station data from the `israel-rail-api` library — and its codes were wrong.

## [1.1.1] - 2026-08-19

### Fixed
- Bus and light rail were completely broken: `bus.gov.il` removed the `/WebApi/api/passengerinfo` API this integration depended on, and every configured station failed setup with "Station is not accessible." Ported the client to the API the MOT's own [route planner](https://route.bus.gov.il) uses (`api.bus.gov.il`), which needs no authentication.
- Setup no longer validates a station against the live API. A single upstream outage used to leave already-working stations permanently stuck in `setup_retry` with no entities at all; entries now stay loaded and their sensors report `unavailable` until the API recovers.
- The bus stop-arrivals request used UTC to ask for "today's" service day. Between midnight and ~02:00–03:00 Israel time this asked the API for yesterday, which returns zero routes — every bus sensor would go blank overnight. Now uses Israel local time.
- An empty route list from the API was cached for a full hour, so a transient gap (including the UTC bug above) kept sensors blank long after service resumed. Empty results are no longer cached.
- A total API outage was silently recorded as a *successful* update with no arrivals, so sensors read "no bus" during an outage instead of `unavailable`, and a rate limit never reached the coordinator's backoff. Failures now propagate correctly.
- "Browse stations by city" failed with an unlogged HTTP 400 for both bus and light rail — a form field was misconfigured (a list of options passed where the UI expected a single autocomplete string). Replaced with the correct dropdown selector.
- The bundled station index is keyed by GTFS `stop_id`, while the live API addresses stops by `stop_code` — different identifiers that happen to share a numeric range, so a station picked from the city browser could silently resolve to the wrong stop. The config flow now resolves the correct code before saving.
- `gtfs_loader.py` performed synchronous file I/O from async functions, both blocking the event loop and (for the background refresh) risking a mid-write cancellation. All of it now runs off the event loop, and the refresh is a tracked background task instead of a bare fire-and-forget.
- Upstream failures are now distinguishable in the log: a non-JSON response is logged with its content type and the first bytes of the body instead of a generic connection error.

### Added
- A brand icon, shipped locally under `custom_components/israel_transportation/brand/` (requires Home Assistant 2026.3.0+ to render; earlier cores fall back to no icon).

### Changed
- `is_realtime` on each arrival now reflects what the API actually reports, instead of always being `true`.
- Requests for a stop's arrivals are limited to the lines you've configured and bounded in concurrency, so a busy interchange (Tel Aviv Savidor alone serves 50+ routes) doesn't fire a burst of requests every poll.
- README rewritten to match current behavior — it previously documented a different, no-longer-used data source.

## [1.1.0] - 2026-04-12

### Fixed
- Train coordinator: datetime timezone error (`can't subtract offset-naive and offset-aware datetimes`) when processing train departure/arrival times
- Config flow: HTTP 500 on manual station ID entry caused by non-serializable `vol.Match` validator — replaced with `TextSelector` + manual validation
- Config flow: train same-station error (`cannot_be_same`) was unreachable because FROM station was excluded from TO dropdown before validation
- Validation: Unicode/Arabic-Indic digits (e.g. `١٢٣٤٥`) now correctly rejected — added `.isascii()` guard alongside `.isdigit()`

### Changed
- GTFS station data decoupled from code releases — data now lives as assets on a fixed `gtfs-data-latest` GitHub Release and is downloaded/refreshed automatically by the integration (weekly). Code releases no longer bump version for data-only changes.
- GTFS loader refreshes data in the background every 7 days with no disruption to running sensors

### Added
- CI: coverage threshold (70%), mypy type checking, bandit security scan
- Security tests: fuzz/edge-case tests for station ID input (SQL injection, XSS, path traversal, Arabic-Indic digits, null bytes)

## [1.0.23] - 2026-04-10

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.22] - 2026-04-07

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.20] - 2026-04-04

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.18] - 2026-03-31

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.17] - 2026-03-28

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.16] - 2026-03-22

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.15] - 2026-03-19

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.14] - 2026-03-16

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.13] - 2026-03-13

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.12] - 2026-03-10

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.11] - 2026-03-07

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.10] - 2026-03-04

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.9] - 2026-03-01

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.8] - 2026-02-28

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.7] - 2026-02-25

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.6] - 2026-02-22

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.5] - 2026-02-19

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.4] - 2026-02-16

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.3] - 2026-02-13

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.2] - 2026-02-10

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.0.0] - 2026-02-08

### Changed
- Repository consolidation: single repo for all development and distribution
- Reset version to 1.0.0 for clean public release
- Removed release-to-public sync workflow (no longer needed)

### Fixed
- Fixed hassfest CI validation failure (removed inline URLs from translation strings)
- Added HACS validation workflow

### Added
- Full test suite included in repository
- Development configuration files (pytest.ini, requirements_test.txt)
- HACS validation workflow for automated HACS compatibility checks


## [0.0.18] - 2026-02-04

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.17] - 2026-02-01

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.16] - 2026-01-31

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.15] - 2026-01-28

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.14] - 2026-01-25

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.13] - 2026-01-22

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.12] - 2026-01-19

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.9] - 2026-01-16

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.8] - 2026-01-13

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.7] - 2026-01-10

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.6] - 2026-01-07

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.5] - 2026-01-04

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [0.0.4] - 2026-01-01

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [2.0.2] - 2025-12-31

### Changed
- Automated GTFS station data update
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities


## [1.3.3] - 2025-12-28

### Fixed
- **Train Station Dropdown**: Added dropdown selection for train stations (70+ Israeli Railways stations)
  - Users can now browse and select FROM/TO stations from a list
  - Bilingual display (English / Hebrew) for all train stations
  - Manual entry still available as fallback option
  - Validation prevents selecting same station for FROM and TO

- **City Extraction Improvements**: Better categorization of bus stations by city
  - Expanded city mappings from 25 to 100+ Israeli cities
  - Improved extraction logic with word-boundary matching
  - Prevents false matches (e.g., "שדרות" boulevard vs Sderot city)
  - Reduced "Other" category from 95% to 92% of stations
  - Now properly identifies 87 cities including all major urban areas

- **Bilingual City Names**: Added Hebrew translations to city dropdown
  - Cities now display as "English / עברית (station count)"
  - Example: "Tel Aviv / תל אביב (157 stations)"
  - Improves accessibility for Hebrew-speaking users

- **API Error Handling**: Fixed "missing 'times' key" error
  - Stations without scheduled service now handled gracefully
  - Returns empty arrival list instead of crashing
  - Better logging for debugging stations with no service

- **UI Branding Consistency**: Fixed integration display name
  - Updated hacs.json from "Silent Bus" to "Israel Transportation"
  - Ensures HACS shows correct integration name
  - Aligns with rebranding from v1.3.0

### Technical
- Added `scripts/israeli_cities.py` with comprehensive city mappings (100+ cities)
- Added `custom_components/israel_transportation/train_stations.py` with major train stations
- Enhanced `extract_city_from_name()` with 5 pattern-matching strategies
- Updated `get_cities_list()` to display bilingual names
- Improved error handling in `get_stop_times()` API method
- GTFS data regenerated with Hebrew city names populated

## [1.3.2] - 2025-12-28

### Fixed
- **Translation Files**: Updated English and Hebrew translations
  - Integration now displays as "Israel Transportation" instead of "Silent Bus"
  - Added translations for all new GTFS cascade dropdown steps
  - Fixed branding consistency across all UI elements
  - Hebrew translations updated for new multi-step flow

## [1.3.1] - 2025-12-28

### Added
- **GTFS-Based Station Selection**: Revolutionary new station discovery system
  - 🌍 Access to ALL ~35,000 Israeli transit stations (buses, trains, light rail)
  - 🏙️ City-based cascade dropdown for easy navigation
  - 📊 33 cities with automatic station categorization
  - 📥 Powered by official Israeli Ministry of Transport GTFS data
  - 🔄 Auto-updates every 3 days via GitHub Actions
  - 🔍 Manual entry fallback still available for any station
  - ⚡ Government-backed authoritative data source (gtfs.mot.gov.il)

- **Automated Data Management**
  - GitHub Actions workflow for automated GTFS updates
  - Runs every 3 days to download latest station data
  - Automatic version bumping and changelog updates
  - Automatic release creation when data changes
  - Self-maintaining infrastructure

### Fixed
- **Station Validation**: Improved validation using search endpoint
  - Fixes issue where valid stations (like 12664) were rejected
  - Single API call for faster validation and name retrieval
  - Better coverage aligned with official bus.gov.il database
  - Eliminates duplicate API calls during configuration

### Changed
- **Config Flow**: Enhanced multi-step configuration
  - New station selection method step (city dropdown vs manual entry)
  - New city selection step (choose from 33 cities)
  - New station selection step (filtered by city)
  - Graceful fallback to manual entry if GTFS data unavailable
  - Improved UX for discovering stations

### Technical
- Added `gtfs_loader.py` module for efficient GTFS data loading
- Added `scripts/update_gtfs_data.py` for automated data updates
- Added `scripts/get_version.py`, `bump_version.py`, `update_changelog.py`
- Created `gtfs_data/cities_index.json` with 34,860 stations
- Updated `config_flow.py` with cascade dropdown implementation
- Phase 1 validation fix applied to all config steps

## [1.3.0] - 2025-12-27

### Changed
- **Integration Name**: Renamed from "Silent Bus" to "Israel Transportation"
  - Better reflects support for all transportation types (buses, trains, light rail)
  - More discoverable and professional naming
  - Updated all UI strings and documentation
- **Repository URLs**: Updated to point to public repository
  - Documentation: https://github.com/ziv-daniel/hass-israel-transportation-integration
  - Issue Tracker: https://github.com/ziv-daniel/hass-israel-transportation-integration/issues

### Note
- The domain name `israel_transportation` remains unchanged to maintain compatibility with existing installations
- Existing users will see the updated name after upgrading

## [1.2.0] - 2025-12-25

### Added
- **Train Support**: Full integration for Israeli Railways train routes
  - Track departures between any two train stations
  - Dedicated train sensors with route information
  - Display journey duration and real-time train status
- **Light Rail Support**: Complete support for Jerusalem and Tel Aviv light rail (Kala)
  - Track light rail arrivals at stations
  - Automatic icon assignment (mdi:tram)
- **Custom Services**: Two new automation services
  - `israel_transportation.refresh_data`: Force immediate refresh of arrival times
  - `israel_transportation.update_lines`: Dynamically update tracked bus lines
- **Entity Enhancements**:
  - Added `SensorDeviceClass.DURATION` for proper time-based sensor UI
  - Added `SensorStateClass.MEASUREMENT` for long-term statistics support
  - Improved sensor attributes with comprehensive metadata
- **CI/CD Infrastructure**:
  - GitHub Actions workflows for hassfest, HACS, and testing
  - Pre-commit hooks with Ruff for code quality
  - Automated testing across Python 3.12/3.13 and multiple HA versions
  - Release Drafter for automated release notes
  - Dependabot for dependency management
- **Brand Assets**: Integration logo and icon files (icon@2x.png, logo@2x.png)

### Enhanced
- **Documentation**: Expanded README with 8+ automation examples
- **Services Documentation**: Comprehensive services.yaml with field selectors
- **Examples**: Added train and light rail configuration examples
- **Features List**: Updated to highlight multi-modal transportation support

### Fixed
- Improved error handling for all transport types
- Better sensor availability tracking during API errors

## [1.0.0] - 2025-12-24

### Added
- Initial release of Silent Bus Home Assistant integration
- Real-time bus arrival tracking for Israeli public transportation
- Support for multiple stations and bus lines
- UI-based configuration flow with station and line selection
- Dynamic update intervals based on bus proximity and time of day
- Comprehensive sensor entities with rich attributes
- Bilingual support (English and Hebrew)
- Automatic error handling and retry logic
- Options flow for reconfiguring existing integrations
- Full test coverage (unit and integration tests)
- HACS compatibility

### Features
- BusNearby API integration for real-time data
- DataUpdateCoordinator for efficient data management
- Smart update intervals (15-300 seconds based on context)
- Per-line sensor entities with unique IDs
- Device registry integration
- Sensor attributes including:
  - Next arrival time
  - Real-time vs scheduled data
  - Bus direction/destination
  - List of upcoming arrivals
  - Last update timestamp

### Documentation
- Comprehensive README with usage examples
- Detailed integration plan document
- Configuration guide
- Automation examples
- Troubleshooting section

### Testing
- Unit tests for API client
- Unit tests for coordinator
- Unit tests for config flow
- Unit tests for sensors
- Integration tests for setup/unload
- 90%+ code coverage

---

## Release Notes

### Version 1.2.0
This release adds comprehensive multi-modal transportation support, transforming Silent Bus into a complete Israeli public transportation integration. Now track buses, trains, and light rail all from one integration with powerful automation services.

### Version 1.0.0
This is the first production-ready release of the Silent Bus integration. The integration has been thoroughly tested and is ready for daily use.

### Known Limitations
- Relies on BusNearby API availability
- No offline mode (planned for future release)
- Israeli public transportation only

### Upgrade Path
- This is the initial release, no upgrade needed

### Breaking Changes
- None (initial release)
