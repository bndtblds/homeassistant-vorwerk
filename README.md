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
- Fixed translation placeholders (`{docs_url}`) in the config flow
- General code cleanup and compatibility fixes for HA 2025.x

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

---

# Vorwerk integration for Home Assistant

Custom integration to control Vorwerk Kobold VR series vacuum cleaners.

The official Home Assistant Neato integration removed Vorwerk support due to changes in the Vorwerk App and its authentication system.  
This custom component restores functionality using the updated Vorwerk cloud login flow.

## Supported vacuum cleaners

- **VR200**
- **VR300** (map sensors not supported)

---

## Installation

### Via HACS (recommended)

1. In HACS: *Integrations → Custom Repositories*
2. Add:  
   `https://github.com/bndtblds/homeassistant-vorwerk`  
   Category: **Integration**
3. Install the integration.
4. Restart Home Assistant.
5. Add the integration via *Settings → Devices & Services → Add Integration → Vorwerk Kobold*.

### Manual installation

1. Download or clone this repository.
2. Copy all files into: <HA config directory>/custom_components/vorwerk
3. Restart Home Assistant.
4. Add the integration through the UI.

---

## Credits

- Original work by **@trunneml**
- Maintenance, compatibility updates and fixes by **@bndtblds**

---

License: Apache-2.0

