# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
