# homeassistant-vorwerk

Maintained fork of [`trunneml/homeassistant-vorwerk`](https://github.com/trunneml/homeassistant-vorwerk) for current Home Assistant versions and the Vorwerk cloud login flow used by the MyKobold app.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Open your Home Assistant instance and open the HACS repository dialog with a specific repository pre-filled.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bndtblds&repository=homeassistant-vorwerk&category=integration)

This custom integration restores Vorwerk Kobold support that is no longer available in Home Assistant's official Neato integration.

## Status

- Community-maintained custom integration for Home Assistant
- Supports Vorwerk Kobold VR200 and VR300
- Uses the Vorwerk cloud account from the MyKobold app
- Relies on the unofficial `pybotvac` client library and Vorwerk cloud behavior, which may change without notice

## Compatibility

- Integration version: `0.9.10`
- Targeted at current Home Assistant `2026.x` releases
- Currently pinned to `pybotvac==0.0.28` so installs stay reproducible and future `pybotvac` releases are only adopted after explicit verification

## Versioning

- The project is preparing to use calendar versioning in the format `YYYY.M.N`.
- `YYYY` is the release year, `M` is the release month, and `N` is the release sequence within that month.
- `N` is not a semantic-versioning patch number.
- Example: `2026.4.0` is the first release in April 2026, while `2026.4.1` is the second release in April 2026.

## Supported devices

- Vorwerk Kobold VR200
- Vorwerk Kobold VR300

Map-based zone cleaning depends on robot capabilities and available boundaries in the Vorwerk cloud. The VR300 supports named zones; map sensors are not provided by this integration.

## Features

- `vacuum` entity with start, pause, stop, return-to-base, locate and spot-clean commands
- `sensor` entity for battery level (`..._battery`)
- `switch` entity for schedule on/off (`..._schedule`)
- Config flow with email OTP login against the Vorwerk cloud
- Custom service `vorwerk.custom_cleaning` for zone or parameterized cleaning
- UI translations in English, German and French
- Runtime-data/coordinator based structure aligned with current Home Assistant development guidance

## Known limitations

- The integration depends on the synchronous `pybotvac` library. Blocking library calls are run through Home Assistant's executor, but the dependency itself is not async-native.
- `pybotvac` is pinned to the currently validated version so dependency changes remain under control until they have been tested against the Vorwerk login flow and robot commands used by this integration.
- Zone cleaning depends on the robot exposing map boundaries through the Vorwerk cloud API. Persistent maps or named zones that only exist in the MyKobold app may not always be available to Home Assistant.
- Reauthentication is not triggered automatically when the Vorwerk cloud rejects stored robot credentials. Remove and re-add the integration if the account or robot credentials change.

## Installation

### HACS

1. Open HACS and go to `Integrations`.
2. Open the menu for custom repositories.
3. Add `https://github.com/bndtblds/homeassistant-vorwerk` as category `Integration`.
4. Install `Vorwerk Kobold`.
5. Restart Home Assistant.
6. Add the integration under `Settings -> Devices & Services -> Add Integration`.

### Manual

1. Download or clone this repository.
2. Copy `custom_components/vorwerk` to `/config/custom_components/vorwerk`.
3. Restart Home Assistant.
4. Add the integration under `Settings -> Devices & Services`.

## Configuration

1. Start the `Vorwerk Kobold` config flow in Home Assistant.
2. Enter the email address used in the MyKobold app.
3. Enter the one-time code sent by Vorwerk via email.
4. Home Assistant will discover the robots linked to that account and create the entities automatically.

## Operation

- The integration polls the Vorwerk cloud once per minute by default.
- Polling is coordinated per robot through Home Assistant's `DataUpdateCoordinator`.
- Command calls request a refresh after the command has been sent.

## Service: `vorwerk.custom_cleaning`

This service can be called on a vacuum entity to start a cleaning run with explicit parameters.

Supported service fields:

- `mode`: cleaning mode, `1` = eco, `2` = turbo
- `navigation`: navigation mode, `1` = normal, `2` = extra care, `3` = deep
- `category`: map usage, `2` = no map, `4` = map
- `zone`: optional named zone, supported when the robot exposes map boundaries to the API

Example:

```yaml
service: vorwerk.custom_cleaning
target:
  entity_id: vacuum.vr300
data:
  mode: 2
  navigation: 1
  category: 4
  zone: Kitchen
```

## Troubleshooting

- The login uses the Vorwerk cloud account from the MyKobold app, not the Vorwerk shop account.
- Existing installations upgraded to `0.9.10` may keep older entity display names from the Home Assistant entity registry.
- Battery and schedule entities use translated names such as `Batterie` and `Zeitplan` on a clean setup.
- If older entity names persist after upgrading, remove the integration, restart Home Assistant, and set it up again so the current default entity names can be created cleanly.
- If zone cleaning is unavailable, verify that persistent maps and named boundaries exist in the Vorwerk app and that the robot exposes them through the cloud API.
- If Home Assistant reports the integration as unavailable after an upgrade, reinstalling through HACS and restarting Home Assistant usually refreshes the custom component metadata.

## Support policy

- `0.9.10` is focused on Home Assistant `2026.x` and no longer claims compatibility with older `2024.x` or `2025.x` releases.
- Legacy YAML configuration is no longer supported; setup is handled exclusively through the UI config flow.

## Changelog

Release history is maintained in [CHANGELOG.md](./CHANGELOG.md).

## Credits

- Original integration by **@trunneml**

## License

Apache-2.0
