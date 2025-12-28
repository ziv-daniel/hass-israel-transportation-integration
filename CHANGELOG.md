# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- The domain name `silent_bus` remains unchanged to maintain compatibility with existing installations
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
  - `silent_bus.refresh_data`: Force immediate refresh of arrival times
  - `silent_bus.update_lines`: Dynamically update tracked bus lines
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
