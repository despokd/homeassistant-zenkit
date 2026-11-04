# Architecture

## Files

```
custom_components/zenkit/
├── __init__.py       # Entry setup: login, create coordinator, forward to BUTTON, IMAGE, SENSOR and TODO platforms; backfills unique_id; config entry migration
├── config_flow.py    # UI setup: asks for API key (CONF_TOKEN), validates via login, unique_id = Zenkit user id (one entry per account), titles entry with username
├── api.py            # Zenkit REST client (sync `requests` wrapped in asyncio.to_thread), caches list elements
├── elements.py       # Finds the title/notes/due/status elements of a list by role, with fallbacks
├── coordinator.py    # DataUpdateCoordinator: polls every UPDATE_INTERVAL s, data = {list shortId: [entries]}, failed_lists; unread_notifications; user + account device_info; refresh of a single list; forced refresh
├── todo.py           # One TodoListEntity per Zenkit list; maps entries <-> TodoItem
├── button.py         # Refresh button per entry: drops cached list elements and refreshes all lists
├── sensor.py         # Account and organization sensors per entry, described by SENSORS
├── image.py          # Profile image of the account (public URL, no API key)
├── diagnostics.py    # Config entry diagnostics: redacted user, lists with element roles, failures
├── const.py          # DOMAIN, ZENKIT_URL, API_URL, UPDATE_INTERVAL, USER_UPDATE_INTERVAL, ENTRIES_LIMIT, RETRY_DELAYS, DUE_DATE_FORMAT, DUE_DATETIME_FORMAT
├── exceptions.py     # ZenkitException > CannotConnectException, CannotLoginException, UpdateFailedException
├── manifest.json     # HA manifest (integration_type `service`, cloud_polling, requires `requests`)
├── strings.json      # Config flow strings
└── translations/     # en, de
```

