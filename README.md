# Zenkit Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/despokd/homeassistant-zenkit)](https://github.com/despokd/homeassistant-zenkit/releases)
[![HACS Validate](https://img.shields.io/github/actions/workflow/status/despokd/homeassistant-zenkit/hacs.yaml?branch=main&label=HACS%20Validate)](https://github.com/despokd/homeassistant-zenkit/actions/workflows/hacs.yaml)
[![CI (hassfest, tests, black)](https://img.shields.io/github/actions/workflow/status/despokd/homeassistant-zenkit/CI.yaml?branch=main&label=hassfest%20%26%20CI)](https://github.com/despokd/homeassistant-zenkit/actions/workflows/CI.yaml)

Bring your [Zenkit](https://zenkit.com) lists into Home Assistant as to-do lists, calendars and sensors.

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=despokd&repository=homeassistant-zenkit&category=integration)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/despokd/homeassistant-zenkit/main/custom_components/zenkit/brand/dark_logo.png">
    <img alt="Zenkit" src="https://raw.githubusercontent.com/despokd/homeassistant-zenkit/main/custom_components/zenkit/brand/logo.png">
  </picture>
</p>

## Features

- One **to-do entity per Zenkit list**: add, rename and complete items
- Item details: description, due date, sub-items, dependencies and checklists
- A read-only **calendar per list** with the due dates of open items
- **Count sensors per list**: open, overdue and due today
- **Account sensors**: unread notifications, number of lists, profile and organization data
- A **refresh button** to update all lists immediately
- English and German translations

## Installation

### Marketplace (recommended)

1. Open the Home Assistant Marketplace and search for **Zenkit**, or use the button above.
2. Install it and restart Home Assistant.

<details>
<summary>Manual installation</summary>

1. Download the latest zip from [GitHub Releases](https://github.com/despokd/homeassistant-zenkit/releases/latest).
2. Copy the folder `zenkit` from `custom_components` to `<config>/custom_components/`.
3. Restart Home Assistant.

Don't download the `main` branch directly, it can be in development.

</details>

## Setup

1. Create an API key in Zenkit under **Your Account → Integrations → API Key**.
2. Go to **Settings → Devices & services → Add integration**, search for **Zenkit** and enter the key, or use the button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zenkit)

Each Zenkit account can be added once. All entities belong to one device named after your Zenkit display name.

## Entities

| Entity | What it is |
| --- | --- |
| `todo.<list>` | One per list. State is the number of open items |
| `calendar.<account>_<list>` | Open items with a due date, for lists with a due date field |
| `sensor.zenkit_<list>_open_entries` | Open items |
| `sensor.zenkit_<list>_overdue_entries` | Open items due before now |
| `sensor.zenkit_<list>_entries_due_today` | Open items due today |
| `sensor.zenkit_unread_notifications` | Unread Zenkit notifications |
| `sensor.zenkit_lists` | Number of loaded lists |
| `button.zenkit_refresh` | Updates all lists now |

More account and organization sensors, and the attributes of the to-do entities, are described in the [configuration docs](https://github.com/despokd/homeassistant-zenkit/blob/main/docs/user/configuration.md).

## Examples

Notify when new Zenkit notifications arrive:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.zenkit_unread_notifications
    above: 0
```

Act on the due day of an item:

```yaml
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.jane_doe_groceries
```

## Good to know

- Data is polled every 60 seconds. Press the refresh button for an immediate update.
- New lists need a reload of the integration.
- Only the name and the completed state of items can be changed from Home Assistant.
- Lists without a status field show their items in a separate section with an indeterminate checkbox, and can't be completed.

## Documentation and help

- [User documentation](https://github.com/despokd/homeassistant-zenkit/tree/main/docs/user)
- [Full documentation](https://github.com/despokd/homeassistant-zenkit/tree/main/docs)
- [Report an issue](https://github.com/despokd/homeassistant-zenkit/issues)
