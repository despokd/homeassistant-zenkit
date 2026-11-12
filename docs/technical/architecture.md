# Architecture

## Files

```
custom_components/zenkit/
├── __init__.py       # Registers the actions (services.py) in async_setup. Entry setup: login, create coordinator, forward to BUTTON, CALENDAR, IMAGE, SENSOR and TODO platforms; backfills unique_id; registers the account and organization devices, migrates the single device of older versions to the account device; allows removing stale devices; config entry migration
├── config_flow.py    # UI setup: asks for API key (CONF_TOKEN), validates via login, unique_id = Zenkit user id (one entry per account), titles entry with username. Options flow (reloads the entry): the list for Assist's shopping list sentences (CONF_SHOPPING_LIST)
├── assist.py         # Registers Assist's shopping list sentences as conversation sentence triggers for the list chosen in the options, see assist.md
├── api.py            # Zenkit REST client on HA's shared aiohttp session (`async_get_clientsession`), 30 s timeout per request, caches list elements
├── elements.py       # Finds the title/notes/due/status/labels/assignees elements of a list by role, with fallbacks; options by name
├── services.py       # zenkit.create_entry / zenkit.update_entry: entity actions on the Zenkit todo entities (ZenkitTodoListEntity.async_create_entry / async_update_entry), fields in services.yaml
├── coordinator.py    # DataUpdateCoordinator: polls every UPDATE_INTERVAL s, data = {list shortId: [entries]}, failed_lists; unread_notifications; user; device info of the account, organization and each list (identifiers scoped to the entry id, linked to the account device by `via_device_id`, so HA 2026.8+ is required; account and organization are services, lists are devices with their `resourceType` as model, translated via the `device` strings since HA translates only device names); lists refetched every USER_UPDATE_INTERVAL s; refresh of a single list; forced refresh
├── entity.py         # async_add_list_entities: adds the entities of each list, and of lists added later
├── todo.py           # One TodoListEntity per Zenkit list; maps entries <-> TodoItem
├── calendar.py     # Read-only CalendarEntity per list with a due date field; events are the open entries with a due date, from coordinator data
├── button.py         # Refresh button per entry: refetches the lists, their elements and entries
├── sensor.py         # Account and organization sensors per entry (SENSORS); open/overdue/due today counts per list (LIST_SENSORS) from coordinator data, using the todo.py status and due date
├── image.py          # Profile image of the account (public URL, no API key)
├── diagnostics.py    # Config entry diagnostics: redacted user, lists with element roles, failures
├── const.py          # CONF_SHOPPING_LIST, DOMAIN, ZENKIT_URL, API_URL, UPDATE_INTERVAL, USER_UPDATE_INTERVAL, ENTRIES_LIMIT, RETRY_DELAYS, REQUEST_TIMEOUT, DUE_DATE_FORMAT, DUE_DATETIME_FORMAT
├── exceptions.py     # ZenkitException > CannotConnectException, CannotLoginException, UpdateFailedException, InvalidValueException (a ServiceValidationError with a translated message)
├── manifest.json     # HA manifest (integration_type `hub`, cloud_polling, after_dependencies `conversation`, no requirements: `aiohttp` ships with HA)
├── services.yaml     # Fields of the actions
├── icons.json        # Action icons
├── strings.json      # Config flow, options, entity, action and error strings
└── translations/     # en, de
```

