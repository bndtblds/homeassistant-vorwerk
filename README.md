# homeassistant-vorwerk (maintained fork)

> **Fork of [`trunneml/homeassistant-vorwerk`](https://github.com/trunneml/homeassistant-vorwerk)**  
> Updated to work with recent Home Assistant versions (2024.12 / 2025.x / 2026.x) and the current Vorwerk cloud authentication.

This repository contains a maintained fork of the original Vorwerk Kobold integration for Home Assistant.

All changes and technical details can be found in the  
➡️ **[CHANGELOG.md](./CHANGELOG.md)**

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
2. Copy all files into: /config/custom_components/vorwerk
3. Restart Home Assistant.
4. Add the integration through the UI.

---

## Credits

- Original work by **@trunneml**
- Maintenance, compatibility updates and fixes by **@bndtblds**

---

License: Apache-2.0
