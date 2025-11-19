# Changelog

All notable changes to this project are documented in this file.

This project follows a simplified version of the guidelines from  
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.9.7] – 2025-11-18

### Added
- Full compatibility with Home Assistant 2024.12 / 2025.x.
- Updated vacuum entity to the modern API:
  - Migrated to `StateVacuumEntity`
  - Implemented `VacuumEntityFeature` flags
  - Implemented `VacuumActivity` reporting
  - Introduced fully asynchronous vacuum commands:
    - `async_start`
    - `async_stop`
    - `async_pause`
    - `async_return_to_base`
    - `async_clean_spot`
    - `async_locate`
- Modernized battery sensor:
  - Now using `SensorDeviceClass.BATTERY`
  - Updated to `native_value` and `native_unit_of_measurement`
  - Added `SensorStateClass.MEASUREMENT`
- Updated schedule switch:
  - Migrated from deprecated `ToggleEntity` to `SwitchEntity`
  - Updated to async `turn_on` / `turn_off`

### Fixed
- Replaced deprecated `async_forward_entry_setup` with `async_forward_entry_setups`
- Corrected config flow translation placeholders (`{docs_url}`) to restore proper UI rendering
- Improved compatibility and error handling for recent Home Assistant releases

### Changed
- General code cleanup and modernization
- Removed deprecated constants (`SUPPORT_*`)
- Updated internal logic and imports for consistency and future HA compatibility
- Documentation updated to reflect maintained-fork status

---

## [0.9.6] – 2021-12-01

### Original release
- Original version of the Vorwerk integration by [`@trunneml`](https://github.com/trunneml/homeassistant-vorwerk)
