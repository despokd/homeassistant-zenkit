# Configuration

Go to Configuration -> Integrations and click on "add integration". Then search for "Zenkit".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zenkit)

### Configuration Variables

- __token__: Your API Key from Your Account > Integrations > API Key

### Refresh button

Data is polled every 60 seconds. Press the __Refresh Zenkit data__ button (`button.zenkit_refresh`) to update all lists immediately, e.g. after changing list fields in Zenkit. It can also be pressed from automations with the `button.press` action. New lists still require a reload of the integration.

### Account device

The integration adds one device per Zenkit account, named after your Zenkit display name. All lists, the refresh button, the account sensors and the profile image belong to it. With the device, list names shown in Home Assistant get the device name as prefix, e.g. "Jane Doe Groceries". Entity ids of existing lists stay the same.

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

### Diagnostics

Settings > Devices & services > Zenkit > ⋮ > Download diagnostics. The file has your list ids, field roles and errors, but not your API key, emails, names or list names.
