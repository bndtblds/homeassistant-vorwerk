# homeassistant-vorwerk

Maintained fork of [`trunneml/homeassistant-vorwerk`](https://github.com/trunneml/homeassistant-vorwerk) for current Home Assistant versions and the Vorwerk cloud login flow used by the MyKobold app.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Open your Home Assistant instance and open the HACS repository dialog with a specific repository pre-filled.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bndtblds&repository=homeassistant-vorwerk&category=integration)

This custom integration restores Vorwerk Kobold support that is no longer available in Home Assistant's official Neato integration.

## Compatibility

- Integration version: `0.9.10`
- Targeted at current Home Assistant `2026.x` releases
- Currently pinned to `pybotvac==0.0.28`

## Breaking Changes

- `0.9.10` is focused on Home Assistant `2026.x` and no longer claims compatibility with older `2024.x` or `2025.x` releases.
- Legacy YAML configuration is no longer supported; setup is handled exclusively through the UI config flow.

## Upgrade Notes

- Existing installations may keep older entity display names from the Home Assistant entity registry even after upgrading to `0.9.10`.
- In particular, schedule and battery entities may continue to show the robot name instead of translated defaults such as `Zeitplan` or `Batterie`.
- If that happens, remove the integration, restart Home Assistant, and set it up again so the current default entity names can be created cleanly.

## Supported devices

- Vorwerk Kobold VR200
- Vorwerk Kobold VR300

Map-based zone cleaning depends on robot capabilities and available boundaries in the Vorwerk cloud. The VR300 supports named zones; map sensors are not provided by this integration.

## What the integration provides

- `vacuum` entity with start, pause, stop, return-to-base, locate and spot-clean commands
- `sensor` entity for battery level (`..._battery`)
- `switch` entity for schedule on/off (`..._schedule`)
- Config flow with email OTP login against the Vorwerk cloud
- Custom service `vorwerk.custom_cleaning` for zone or parameterized cleaning
- UI translations in English, German and French
- Runtime-data/coordinator based structure aligned with current Home Assistant development guidance

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

## Notes

- The login uses the Vorwerk cloud account from the MyKobold app, not the Vorwerk shop account.
- Battery and schedule entities use translated names such as `Batterie` and `Zeitplan` on a clean setup.
- If zone cleaning is unavailable, verify that persistent maps and named boundaries exist in the Vorwerk app and that the robot exposes them through the cloud API.
- If Home Assistant reports the integration as unavailable after an upgrade, reinstalling through HACS and restarting Home Assistant usually refreshes the custom component metadata.

## Changelog

Release history is maintained in [CHANGELOG.md](./CHANGELOG.md).

## Credits

- Original integration by **@trunneml**
- Maintenance and compatibility updates by **@bndtblds**

## License

Apache-2.0
