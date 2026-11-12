# Zenkit Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/despokd/homeassistant-zenkit)](https://github.com/despokd/homeassistant-zenkit/releases)
[![HACS Validate](https://img.shields.io/github/actions/workflow/status/despokd/homeassistant-zenkit/hacs.yaml?branch=main&label=HACS%20Validate)](https://github.com/despokd/homeassistant-zenkit/actions/workflows/hacs.yaml)
[![CI (hassfest, tests, black)](https://img.shields.io/github/actions/workflow/status/despokd/homeassistant-zenkit/CI.yaml?branch=main&label=hassfest%20%26%20CI)](https://github.com/despokd/homeassistant-zenkit/actions/workflows/CI.yaml)

Bring your [Zenkit](https://zenkit.com) lists into Home Assistant as to-do lists, calendars and sensors.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/despokd/homeassistant-zenkit/main/custom_components/zenkit/brand/dark_logo.png">
    <img alt="Zenkit" src="https://raw.githubusercontent.com/despokd/homeassistant-zenkit/main/custom_components/zenkit/brand/logo.png">
  </picture>
</p>

## Features

- One **to-do entity per Zenkit list**: add, edit, complete and delete items
- **`zenkit.create_entry` and `zenkit.update_entry` actions** to add and change items with status, labels, assignees and a checklist
- Item details: description, due date, sub-items, dependencies and checklists
- A read-only **calendar per list** with the due dates of open items
- **Count sensors per list**: open, overdue and due today
- **Account sensors**: unread notifications, number of lists, profile and organization data
- Added, removed and renamed lists are picked up without a reload
- A **refresh button** to update all lists immediately
- **Assist shopping list**: "add milk to my shopping list" goes to a Zenkit list of your choice
- English and German translations

## Installation

### Marketplace (recommended)

1. Open the Home Assistant Marketplace and search for **Zenkit**, or use the button below.
2. Install it and restart Home Assistant.

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=despokd&repository=homeassistant-zenkit&category=integration)

<details>
<summary>Manual installation</summary>

1. Download `Source code (zip)` of the latest [GitHub Release](https://github.com/despokd/homeassistant-zenkit/releases/latest).
2. Copy the folder `zenkit` from `custom_components` to `<config>/custom_components/`.
3. Restart Home Assistant.

Don't download the `main` branch directly, it can be in development.

</details>

## Setup

1. Create an API key in Zenkit under **Your Account → Integrations → API Key**.
2. Go to **Settings → Devices & services → Add integration**, search for **Zenkit** and enter the key, or use the button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zenkit)

Each Zenkit account can be added once. Each list gets a device with its to-do list, calendar and count sensors; account and organization entities are on their own devices.

## Entities

| Entity | What it is |
| --- | --- |
| `todo.<list>` | One per list. State is the number of open items |
| `calendar.<list>` | Open items with a due date, for lists with a due date field |
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
    entity_id: calendar.groceries
```

Add an item with more fields than `todo.add_item` has:

```yaml
actions:
  - action: zenkit.create_entry
    target:
      entity_id: todo.groceries
    data:
      name: Buy milk
      due_date: "2026-11-30"
      status: In progress
      labels: [Important]
      assignees: [Jane Doe]
      checklist: [Passport, Charger]
```

Change these fields later, by title or uid:

```yaml
actions:
  - action: zenkit.update_entry
    target:
      entity_id: todo.groceries
    data:
      item: Buy milk
      status: Done
      labels: []
```

## Good to know

- Data is polled every 60 seconds, the lists themselves every hour. Press the refresh button for an immediate update.
- Name, completed state, description and due date of items can be changed from the to-do entity. Status, labels and assignees can be changed with `zenkit.update_entry`. Checklists can only be set when creating an item with `zenkit.create_entry`.
- Completed items aren't shown in Home Assistant or loaded from Zenkit. Reopen them in Zenkit.
- Lists without a status field show their items in a separate section with an indeterminate checkbox, and can't be completed.

## Documentation and help

- [User documentation](https://github.com/despokd/homeassistant-zenkit/tree/main/docs/user)
- [Full documentation](https://github.com/despokd/homeassistant-zenkit/tree/main/docs)
- [Report an issue](https://github.com/despokd/homeassistant-zenkit/issues)
