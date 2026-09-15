# Vorwerk Kobold for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://www.hacs.xyz/)

Control Vorwerk Kobold VR200 and VR300 robot vacuums from Home Assistant through the Vorwerk cloud account used by the MyKobold app.

## Requirements

- Home Assistant 2026.2.0 or newer
- HACS
- A MyKobold account with a VR200 or VR300
- Internet access from Home Assistant

Local-only control is not supported.

## Installation and setup

The integration is included in the default HACS store and does not need to be added as a custom repository.

> [!IMPORTANT]
> HACS can show two integrations named **Vorwerk Kobold**. Select the entry described as **Home Assistant cloud integration for Vorwerk Kobold VR200 and VR300 vacuums (domain: vorwerk)**. Its repository is `bndtblds/homeassistant-vorwerk`. The entry described only as **Home Assistant integration for Vorwerk Kobold robot vacuums** belongs to the separate `FReichelt/ha-vorwerk-kobold` project.

1. Open **HACS → Integrations**.
2. Search for **Vorwerk Kobold** and select the entry whose description explicitly mentions **VR200 and VR300**.
3. Select **Download** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Vorwerk Kobold**.
6. Enter the email address used by the MyKobold app.
7. Enter the one-time code sent by Vorwerk.

The login uses the MyKobold account, not a Vorwerk online-shop account. Home Assistant creates one device for each robot assigned to the account.

## Entities

| Entity | Purpose |
| --- | --- |
| Vacuum | Start or resume, pause, stop, return to base, locate, and spot clean |
| Battery sensor | Battery charge in percent |
| Schedule switch | Enable or disable the schedule stored on the robot |

## Vacuum states and status

| State | Meaning |
| --- | --- |
| `cleaning` | Actively cleaning or exploring a map |
| `paused` | Cleaning or exploration is paused or suspended |
| `returning` | Returning to the base |
| `docked` | Docked or charging |
| `idle` | Stopped and not docked or charging |
| `error` | Robot error |

The `status` attribute provides additional Vorwerk-specific details such as the cleaning mode, action, and zone. Examples include `Turbo Suspended Cleaning` and `Eco Map cleaning Kitchen`.

## Custom cleaning

The `vorwerk.custom_cleaning` action starts a cleaning run with explicit settings.

| Parameter | Values | Default |
| --- | --- | --- |
| `mode` | `1` Eco, `2` Turbo | `2` |
| `navigation` | `1` Normal, `2` Extra care, `3` Deep | `1` |
| `category` | `2` No persistent map, `4` Use persistent map | `4` |
| `zone` | Optional zone name or unique part of it | None |

```yaml
action: vorwerk.custom_cleaning
target:
  entity_id: vacuum.upstairs
data:
  mode: 2
  navigation: 1
  category: 4
  zone: Kitchen
```

Zone matching is case-insensitive. Named zones only work when the robot has a persistent map and the Vorwerk cloud returns its boundaries. Home Assistant reports the available zones when possible if a name cannot be resolved.

## Troubleshooting

### The integration is missing after download

Restart Home Assistant. If it is still missing under **Add integration**, redownload `bndtblds/homeassistant-vorwerk` in HACS and restart again.

### Login fails or no code arrives

Use the email address from the MyKobold app, check the spam folder, and request a new code. Only the most recent code may be valid.

To renew authentication, open the configured Vorwerk integration under **Settings → Devices & services**, select **Configure**, confirm **Renew Vorwerk authentication**, and enter the one-time code sent by Vorwerk. The configured email address cannot be changed in this flow; add a new integration to use another Vorwerk account.

Authentication renewal is started only by the user. Home Assistant does not automatically request one-time codes after API, polling, or timeout errors.

### The robot is unavailable

Check whether the robot is online in the MyKobold app and whether Home Assistant has internet access. The integration updates once per minute, so temporary cloud failures can clear on a later update. Relevant messages appear under **Settings → System → Logs** with logger `custom_components.vorwerk`.

### Named-zone cleaning fails

Verify that the map and named zone exist in the MyKobold app, use `category: 4`, and check the Home Assistant error for boundaries currently returned by the cloud. Zones that are not returned by the cloud cannot be used.

### Old entity names remain after an update

Home Assistant preserves entity registry customizations. Rename the entities on the device page, or remove and add the integration again to recreate the current default names.

## Limitations

- The integration depends on the unofficial Vorwerk cloud interface and the `pybotvac` library. Cloud changes or outages can interrupt operation.
- Map images and map sensor entities are not provided.
- A normal start can use the mode selected by the robot or cloud. Use `vorwerk.custom_cleaning` to select Eco or Turbo explicitly.

## Updates and support

Install updates through HACS and restart Home Assistant when requested. See the [changelog](./CHANGELOG.md) before updating.

Before opening a [GitHub issue](https://github.com/bndtblds/homeassistant-vorwerk/issues), search existing reports and include the robot model, Home Assistant version, integration version, relevant logs, and the action that failed. Never publish account credentials, one-time codes, or robot secrets.

## Credits and license

This integration is a maintained fork of [`trunneml/homeassistant-vorwerk`](https://github.com/trunneml/homeassistant-vorwerk) and is licensed under the [Apache License 2.0](./LICENSE).
