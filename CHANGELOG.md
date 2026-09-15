# Changelog

All notable changes to this project are documented in this file.

This project follows a simplified version of the guidelines from
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Added a user-initiated flow to renew authentication for the configured Vorwerk account using an email one-time code.

## [2026.9.1] - 2026-09-14

### Changed
- Reworked the README as concise user documentation with installation from the default HACS store, setup and operation guidance, troubleshooting, and a clear distinction from the similarly named Kobold integration.

### Fixed
- Corrected the historical mapping of suspended vacuum actions. Suspended Cleaning and Suspended Exploration are now reported to Home Assistant as `paused` instead of active cleaning, based on the action value supplied by the Vorwerk cloud.
- Preserved detailed Vorwerk status information such as `Turbo Suspended Cleaning` for suspended operations.

## [2026.9.0] - 2026-09-11

### Added
- Added automated integration tests for config entry setup and unloading, config flow, coordinator updates, robot commands, custom cleaning, entity registry migrations, vacuum state, and battery and schedule entities.
- Added a test workflow for pull requests and pushes to `main` with a minimum coverage requirement of 95%.
- Added an automated release workflow that verifies tag and manifest versions, runs the test suite, HACS validation, and Hassfest before publishing a GitHub release.

### Changed
- Moved map boundary loading for zone cleaning into Home Assistant's executor to avoid blocking the event loop.
- Let the data update coordinator handle robot update failures through `UpdateFailed` so entity availability follows Home Assistant coordinator state.
- Documented the polling interval and known integration limitations.
- Moved the schedule switch icon to Home Assistant icon translations and normalized device manufacturer metadata.
- Clarified the `pybotvac` pinning rationale and reorganized the README into a more standard user-facing structure.
- Activated calendar versioning in the format `YYYY.M.N`, where `N` is the release sequence within the month.

### Fixed
- Removed the legacy vacuum `state` override so Home Assistant derives the state from `VacuumActivity` as required by Home Assistant 2026.9.
- Associated each data update coordinator with its config entry so initial refreshes use the current Home Assistant lifecycle API.
- Prevented delayed executor failures after an update timeout from producing an unconsumed shielded-future exception.
- Raised translated Home Assistant service errors when custom cleaning cannot load boundaries, cannot find a requested zone, or a robot command fails.

### Compatibility
- Validated the integration against Home Assistant `2026.2.0` and `2026.9.1`.
- Kept the minimum supported Home Assistant version at `2026.2.0`.
- Kept `pybotvac==0.0.28` deliberately pinned and added the compatible Setuptools runtime needed by its deprecated `pkg_resources` import to the test environments.

### Testing
- Added 76 automated tests with 99% measured integration coverage.
- Added regression coverage for all supported vacuum activities, blocking executor calls, timeouts, late failures, entity targeting, named zones, OTP handling, and legacy registry entries.

## [0.9.10] - 2026-03-27

### Breaking Changes
- `0.9.10` is now explicitly targeted at Home Assistant `2026.x`.
- Compatibility with older Home Assistant `2024.x` and `2025.x` releases is no longer claimed for this release line.
- Legacy YAML import/setup support has been removed; configuration now requires the UI config flow.
- Existing installations may retain older entity display names from the Home Assistant entity registry after upgrade and may require removing and re-adding the integration.

### Added
- Added a dedicated `coordinator.py` and shared `entity.py` to align the integration structure with current Home Assistant development guidance.
- Added service translations for `vorwerk.custom_cleaning` in English, German, and French.
- Added richer service metadata with selectors and proper entity targeting in `services.yaml`.
- Added a calendar icon for the schedule switch.

### Changed
- Switched runtime storage from `hass.data` bookkeeping to typed `ConfigEntry.runtime_data`, following current Home Assistant recommendations.
- Refactored the vacuum, sensor, switch, and config flow modules for clearer typing, naming, and readability.
- Updated entity naming to better fit modern Home Assistant device/entity naming conventions.
- Bumped the integration version to `0.9.10`.
- Updated README to document the 2026-oriented integration structure and UI-only setup path.

### Fixed
- Fixed a duplicate unique ID issue on the schedule switch by giving it its own unique suffix.
- Fixed the custom cleaning service registration to use Home Assistant's platform entity service registration from `async_setup`.
- Fixed the OTP flow so the code email is only sent when entering the code step instead of on every retry.
- Fixed multiple translation issues and wording inconsistencies across config flow texts.
- Added migration logic for legacy schedule switch entity IDs so existing installations can move toward the `_schedule` naming scheme.
- Fixed battery and schedule entity naming so Home Assistant exposes translated names such as `Batterie` and `Zeitplan` instead of only the robot name.
- Fixed zone cleaning lookups to lazily load map boundaries from the robot before resolving a named zone.

## [0.9.9] - 2026-03-19

### Added
- Added a brand icon under `custom_components/vorwerk/brand/icon.png` for HACS validation and better integration metadata.

### Changed
- Bumped the integration version to `0.9.9`.

### Fixed
- Removed the deprecated `battery_level` vacuum property to stay compatible with newer Home Assistant vacuum APIs.

## [0.9.8] - 2026-02-12

### Added
- Added French translation for the config flow.
- Updated README with current Home Assistant compatibility information.

### Changed
- Pinned `pybotvac` to `0.0.28` so installs remain reproducible and future dependency updates can be validated explicitly before adoption.
- Bumped the integration version to `0.9.8`.

### Fixed
- Restored compatibility with Home Assistant 2026.2 vacuum API changes.
- Fixed vacuum activity/state handling.
- Triggered state refreshes after vacuum commands.
- Switched away from `pkg_resources`-dependent behavior relied on during `pybotvac` imports.
- Fixed indentation in `__init__.py`.
- Corrected a typo in the config flow strings.

## [0.9.7] - 2025-11-18

### Added
- Full compatibility with Home Assistant 2024.12 / 2025.x.
- Updated the vacuum entity to the modern Home Assistant API with `StateVacuumEntity`, `VacuumEntityFeature` flags, `VacuumActivity` reporting, and fully asynchronous command handlers.
- Modernized the battery sensor with `SensorDeviceClass.BATTERY`, `native_value`, `native_unit_of_measurement`, and `SensorStateClass.MEASUREMENT`.
- Updated the schedule switch by migrating from deprecated `ToggleEntity` to `SwitchEntity` and async `turn_on` / `turn_off`.
- Added HACS metadata and repository structure required for HACS default repository compliance.
- Added HACS and Hassfest GitHub workflows.

### Fixed
- Replaced deprecated `async_forward_entry_setup` with `async_forward_entry_setups`.
- Corrected config flow translation placeholders (`{docs_url}`) to restore proper UI rendering.
- Improved compatibility and error handling for recent Home Assistant releases.
- Corrected `hacs.json` metadata.
- Sorted manifest keys for Hassfest validation.

### Changed
- General code cleanup and modernization.
- Removed deprecated constants (`SUPPORT_*`).
- Updated internal logic and imports for consistency and future HA compatibility.
- Documentation updated to reflect the maintained fork.
- Moved the changelog content out of `README.md` into `CHANGELOG.md`.

## [0.9.6] - 2021-12-01

### Original release
- Original version of the Vorwerk integration by [`@trunneml`](https://github.com/trunneml/homeassistant-vorwerk).
