# Configuration

Go to Configuration -> Integrations and click on "add integration". Then search for "Zenkit".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zenkit)

### Configuration Variables

- __token__: Your API Key from Your Account > Integrations > API Key

### Assist shopping list

Assist sends sentences without a list name, like "add milk to my shopping list" or "füge Milch zur Einkaufsliste hinzu", to Home Assistant's Shopping List integration. This happens even when Shopping List is not set up, and then the sentence fails. To send them to a Zenkit list instead, choose it in Settings > Devices & services > Zenkit > ⚙ (Configure) > __Shopping list for Assist__.

The list then gets these sentences in English and German (English for other Home Assistant languages):

| Sentence | Does |
| --- | --- |
| "add milk to my shopping list", "put milk on the list" | Adds the item. An open item with the same name (ignoring case) is not added twice |
| "check off milk from my shopping list", "remove milk from the list" | Completes the open item with that name, or answers that it's not on the list |
| "füge Milch zur Einkaufsliste hinzu", "setze Milch auf die Liste", "Milch zum Einkauf hinzufügen" | Adds the item |
| "streiche Milch von der Einkaufsliste", "nimm Milch aus der Liste raus", "hake Milch auf der Liste ab" | Completes the item |

A preposition is needed right before the list ("zur Liste", not "Liste"), so sentences with another list name, like "füge Putzen zur Haushaltsliste hinzu", still go to that list. Like sentence triggers of automations, they are handled before the conversation agent of a voice assistant, LLM agents included. They are not shared with the Shopping List integration: while a Zenkit list is chosen, Shopping List doesn't get them. Clear the option to undo this. If more than one Zenkit account chooses a list, each one gets the item.

### List attributes

Each todo entity has attributes for where its list is in Zenkit:

- __workspace__: name of the top-level workspace
- __folder__: name of the folder the list is directly in, `null` if it is directly in the workspace
- __folder_id__: Zenkit id of that folder, `null` if none
- __folder_path__: folder names from the workspace down to the list, e.g. `["Garden", "Beds"]`, `[]` if none

How the list looks in Zenkit, each `null` if unset:

- __description__: list description
- __icon_class__: Font Awesome class of the list icon, e.g. `fa fa-plane`. The entity icon is an MDI icon guessed from it
- __icon_color__ / __icon_background_color__: hex colors of the icon and behind it, e.g. `#3ba744`
- __image_id__ / __cover_image_id__: Zenkit file id of the list image and cover image. The images themselves need your API key, so Home Assistant can't show them yet
- __background_id__: Zenkit id of the list background

Example template: `{{ state_attr('todo.groceries', 'folder_path') | join(' / ') }}`. Renamed or moved lists and folders are picked up within an hour, or right away with the [refresh button](#refresh-button).

### Completed items

Completing an item sets the list's done status in Zenkit, and the item disappears from Home Assistant. Completed items aren't loaded at all, so lists with many done items poll as fast as short ones. To reopen an item, change its status in Zenkit; it shows up again with the next poll.

### Item order

Items are shown in their Zenkit order. Drag an item in the to-do card to move it; the new position is saved in Zenkit, where only the moved item changes. New items appear at the top, as in Zenkit.

### Lists without status

Items are completed by the list's status field. Lists without one (or without a done status) show their items in a separate section with an indeterminate checkbox (neither checked nor unchecked). Clicking it changes nothing in Zenkit, but the card shows it ticked until the page is reloaded. Completing an item through an action shows an error. The entity state counts only open items, so it is `0` for these lists.

### Create entry action

`zenkit.create_entry` adds an item to the targeted Zenkit to-do lists, with fields `todo.add_item` doesn't have:

| Field | Value |
| --- | --- |
| `name` | Title of the item (required) |
| `description` | Text for the notes field |
| `due_date` / `due_datetime` | Due date, or date and time. A time without time zone is in the time zone of Home Assistant |
| `status` | Name of a status option, e.g. `In progress` |
| `labels` | Names of tag options |
| `assignees` | Display names or usernames of list members |
| `checklist` | Items of a new checklist, unchecked. Any list can have checklists |
| `checklist_name` | Name of that checklist, `Checklist` if not set |

Names are matched as shown in Zenkit, ignoring case. The options must exist in the list already, new labels can't be created. A name that matches no option or member, or a field the list doesn't have, fails with a message listing what is available. Lists of type to-do have no tags field, projects do.

With `response_variable`, the action returns the `uid` of the new item per entity:

```yaml
actions:
  - action: zenkit.create_entry
    target:
      entity_id: todo.groceries
    data:
      name: Buy milk
      status: In progress
      labels: [Important]
      assignees: [Jane Doe]
      checklist: [Passport, Charger]
      checklist_name: Packing list
    response_variable: created
```

### Update entry action

`zenkit.update_entry` changes an item of the targeted Zenkit to-do lists, also the fields `todo.update_item` doesn't have. Only the given fields are written, the others stay as they are.

| Field | Value |
| --- | --- |
| `item` | Title or uid of the item (required) |
| `rename` | New title |
| `description` | Text for the notes field, empty or `null` to clear it |
| `due_date` / `due_datetime` | Due date, or date and time, `null` to clear it. A time without time zone is in the time zone of Home Assistant |
| `status` | Name of a status option |
| `labels` | Names of tag options. Replaces the labels of the item, `[]` removes them all |
| `assignees` | Display names or usernames of list members. Replaces the assignees of the item, `[]` removes them all |

Names are matched as in `zenkit.create_entry`. A title matches open items only, the first one if several have it. Completed items can be changed by their uid, e.g. the one `zenkit.create_entry` returns. Checklists can't be changed.

```yaml
actions:
  - action: zenkit.update_entry
    target:
      entity_id: todo.groceries
    data:
      item: Buy milk
      rename: Buy oat milk
      status: In progress
      labels: [Important, Weekly]
      assignees: []
```

### Calendars

Each list with a due date field also gets a read-only calendar entity, e.g. `calendar.groceries` (calendars added before the list devices keep their id, e.g. `calendar.jane_doe_groceries`). Its events are the open items with a due date:

- Items with a date only are all-day events, items with a time are events at that point in time (Zenkit stores the time in UTC, Home Assistant shows it in its time zone).
- Items with a date range span from the start to the end date.
- Completed items, items without due date and deleted items are not shown.
- The event description is the item description. The calendar color starts as the icon color of the list.

The calendar is `on` while an event is ongoing, which for all-day items is the whole due day. Use it in calendar triggers, e.g. for a notification on the due day:

```yaml
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.groceries
```

Lists whose fields could not be loaded yet get their calendar once they are.

### Refresh button

Data is polled every 60 seconds. Press the __Refresh Zenkit data__ button (`button.zenkit_refresh`) to update all lists immediately, e.g. after changing list fields in Zenkit. It can also be pressed from automations with the `button.press` action. It also picks up added, removed, renamed and moved lists, which are otherwise checked every hour.

### Devices

The integration groups its entities into devices:

| Device | Name | Model | Entities |
| --- | --- | --- | --- |
| Account (service) | Your Zenkit display name | Account | Account sensors, unread notifications, profile image, refresh button |
| Organization (service) | Organization name | Organization | Organization, plan, members and quotas sensors |
| One device per Zenkit list | List name | Its Zenkit type: To-do list, Project or Database | The todo list, its calendar and its count sensors |

The integration page shows the account and organization under services and the lists under devices. List and organization devices are linked to the account device ("Connected via"). Models are in the language of Home Assistant at setup. The todo list and calendar are named after their list device, the count sensors are e.g. "Groceries Open entries".

Installs from before the grouping keep their device, with its area and name, as the account device. Entity ids stay the same. Lists are checked every hour and on the refresh button: new lists and projects get their device and entities, devices of lists deleted in Zenkit are removed with their entities, and renamed lists rename their device. A name you gave the device in Home Assistant is kept.

Each Zenkit account can only be added once.

### Account sensors

| Entity | Value |
| --- | --- |
| `sensor.zenkit_unread_notifications` | Number of unread Zenkit notifications, updated with each poll |
| `sensor.zenkit_lists` | Number of lists loaded as todo entities |
| `sensor.zenkit_username` | Zenkit username |
| `sensor.zenkit_display_name` | Display name, with your profile image as entity picture |
| `sensor.zenkit_full_name` | Full name |
| `sensor.zenkit_initials` | Initials |
| `sensor.zenkit_email` | Primary email address, attribute `emails` lists all with `primary` and `verified` |
| `sensor.zenkit_apps` | Number of Zenkit apps (e.g. To Do, Base), attribute `apps` lists them |
| `sensor.zenkit_super_admin` | `yes` or `no` |
| `sensor.zenkit_two_factor_authentication` | `enabled` or `disabled` |
| `sensor.zenkit_timezone` | Time zone set in Zenkit, e.g. `Europe/Berlin` |
| `sensor.zenkit_language` | Language set in Zenkit, e.g. `de` |
| `sensor.zenkit_date_format` / `sensor.zenkit_time_format` | e.g. `DD.MM.YYYY` / `HH:mm` |
| `sensor.zenkit_start_of_week` | e.g. `Mon` |
| `sensor.zenkit_registered` | When the account was registered |
| `sensor.zenkit_last_login` | Last sign-in to Zenkit (API requests don't count) |
| `sensor.zenkit_organization` | Organization name, attributes `id` and `description` |
| `sensor.zenkit_organization_plan` | Zenkit plan, e.g. `free` |
| `sensor.zenkit_organization_members` | Number of users in the organization |
| `sensor.zenkit_organization_quotas_exceeded` | `yes` or `no` |
| `image.zenkit_profile_image` | Your Zenkit profile image, unavailable if Zenkit shows your initials instead |

All but the notifications sensor are diagnostic entities. The account and organization data are fetched hourly and when the refresh button is pressed.

Example automation trigger:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.zenkit_unread_notifications
    above: 0
```

### List sensors

Each list gets sensors counting its open items, with the same status and due date as the todo entity:

| Entity | Value |
| --- | --- |
| `sensor.zenkit_<list>_open_entries` | Open items, all items for lists without status |
| `sensor.zenkit_<list>_overdue_entries` | Open items due before now. Items with only a date are overdue from the next day |
| `sensor.zenkit_<list>_entries_due_today` | Open items due today, including ones due earlier today |

Lists without a due date field only get the open count. The counts update with each poll, and a list that fails to load makes its sensors unavailable. They belong to the device of their list.

### Diagnostics

Settings > Devices & services > Zenkit > ⋮ > Download diagnostics. The file has your list ids, field roles, the number of loaded (open) items per list and errors, but not your API key, emails, names or list names.
