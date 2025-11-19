# homeassistant-vorwerk (maintained fork)

> **Fork of [`trunneml/homeassistant-vorwerk`](https://github.com/trunneml/homeassistant-vorwerk)**  
> Updated to work with recent Home Assistant versions (2024.12 / 2025.x) and the current Vorwerk cloud authentication.

## Changes in this fork (0.9.7)

- Updated to Home Assistant 2024.12 / 2025.x API:
  - Replaced deprecated `async_forward_entry_setup` with `async_forward_entry_setups`
  - Updated `vacuum.py` to use `StateVacuumEntity`, `VacuumEntityFeature` and `VacuumActivity`
  - Converted vacuum services (`start`, `stop`, `return_to_base`, `locate`, `clean_spot`) to async methods
  - Fixed battery sensor (`SensorDeviceClass.BATTERY`, `native_value`, `SensorStateClass.MEASUREMENT`)
  - Switched schedule switch to `SwitchEntity` with async on/off
- Fixed config flow translation placeholders for `{docs_url}`

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

# homeassistant-vorwerk

Home assistant integration to control Vorwerk VR vacuum cleaners.

With the new Vorwerk App and authentication the Home Assistant Neato component dropped the vorwerk support. This integration is based on the neato component with the new Vorwerk authentication flow. 

## Supported vacuum cleaners
 
 - VR200
 - VR300 (without map sensors)

 ## Installation

 Use HACS or checkout this repository and copy the `custom_components/vorwerk` folder in your home assistant configuration under: `<HA config directory>/custom_components/<domain>`
