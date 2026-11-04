# Architecture

## Files

```
custom_components/zenkit/
├── __init__.py       # Entry setup: login, create coordinator, forward to BUTTON and TODO platforms; config entry migration
├── config_flow.py    # UI setup: asks for API key (CONF_TOKEN), validates via login, titles entry with username
├── api.py            # Zenkit REST client (sync `requests` wrapped in asyncio.to_thread), caches list elements
├── elements.py       # Finds the title/notes/due/status elements of a list by role, with fallbacks
├── coordinator.py    # DataUpdateCoordinator: polls every UPDATE_INTERVAL s, data = {list shortId: [entries]}, failed_lists; refresh of a single list; forced refresh
├── todo.py           # One TodoListEntity per Zenkit list; maps entries <-> TodoItem
├── button.py         # Refresh button per entry: drops cached list elements and refreshes all lists
├── const.py          # DOMAIN, API_URL, UPDATE_INTERVAL, ENTRIES_LIMIT, RETRY_DELAYS, DUE_DATE_FORMAT, DUE_DATETIME_FORMAT
├── exceptions.py     # ZenkitException > CannotConnectException, CannotLoginException, UpdateFailedException
├── manifest.json     # HA manifest (cloud_polling, requires `requests`)
├── strings.json      # Config flow strings
└── translations/     # en, de
```

