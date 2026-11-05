# Data flow

```
HA config entry (API key)
  └─> Zenkit api client ──HTTPS──> https://zenkit.com/api/v1  (header: Zenkit-API-Key)
        └─> ZenkitDataUpdateCoordinator (stored in hass.data[DOMAIN][entry_id])
              ├─> account device (service, identifier = <entry_id>_account_<user id>)
              │     ├─> ZenkitRefreshButton
              │     ├─> ZenkitSensor × 17  (account, see sensor.SENSORS)
              │     └─> ZenkitProfileImage
              ├─> organization device (service, <entry_id>_organization_<organization id>, via account)
              │     └─> ZenkitSensor × 4  (organization_*, device_fn)
              └─> list device × N  (device, <entry_id>_list_<list uuid>, via account)
                    ├─> ZenkitTodoListEntity  (unique_id = list uuid)
                    ├─> ZenkitCalendarEntity  (lists with a due date field)
                    └─> ZenkitListSensor × 1–3  (see sensor.LIST_SENSORS)
```

- **Setup**: `async_setup_entry` calls `login()` (`/auth/currentuser`) and keeps the returned user on the coordinator for the account device and diagnostics. Network and server errors (`CannotConnectException`) raise `ConfigEntryNotReady`; a bad key (HTTP 401) returns `False`. Older entries get the user id as `unique_id`, unless another entry already has it. Then the account and organization devices are registered before the platforms, so list devices can link to the account device by `via_device_id`, see [Devices](#devices).
- **Polling**: the coordinator fetches the lists on the first poll, then every `USER_UPDATE_INTERVAL` s (1 h) and on a forced refresh (`/users/me/workspacesWithLists`, flattened across workspaces; a failure keeps the known lists and retries on the next poll; each list gets its workspace and folder path from the same response, see [Workspaces and folders](../zenkit/workspaces.md)), and each list's elements once (`/lists/{shortId}/elements`, cached in `Zenkit.elements`, retried on the next poll if it failed). Then every interval it fetches each list's entries via `/lists/{shortId}/entries/filter/list`, page by page in pages of `ENTRIES_LIMIT`. A failed page (5xx, 429, non-JSON body, connection error) is retried after `RETRY_DELAYS` seconds; other errors are not retried.
- **Account**: the first poll, then every `USER_UPDATE_INTERVAL` s (1 h) and a forced refresh fetch the user (`login()`), its organization (`/users/me/organizations`) and the organization's member count (`/organizations/{id}/users`). A failure keeps the last known data.
- **Notifications**: after the lists, each poll fetches `/users/me/notifications?limit=1` for `newNotificationsCount`. A failure only sets `coordinator.unread_notifications` to `None` (sensor unavailable).
- **Failures**: lists are fetched independently. A list whose entries can't be fetched is left out of the data and added to `coordinator.failed_lists`, so only its entity is unavailable; it is removed again on its next successful fetch. The update only fails (all entities unavailable) if every list fails.
- **Writes**: entity create/update/delete call the api client, then `coordinator.async_refresh_list(shortId)`, which re-fetches only that list's entries. If that fetch fails, only that list goes unavailable until the next poll.
  - Every write fetches `/lists/{shortId}/elements` first, which also refreshes the cache, so renamed or added fields and options are picked up. Fields are picked as in [Entry → TodoItem mapping](todoitem-mapping.md).
  - Create: `POST /lists/{shortId}/entries` with a new uuid and the fields (name, and description/due if set) in one request. The `zenkit.create_entry` action also passes `status`, `labels` and `assignees` by name; they are resolved to option ids of the `stage`/`tags` elements and to user ids from `/lists/{shortId}/users` (fetched only when assignees are given). A name that matches nothing, or a missing element, raises `InvalidValueException` before anything is written.
  - Update: the entity compares the HA item with the coordinator data and passes only changed fields (`name`, `completed`, `description`, `due`). `update_entry` `PUT`s all changes in one request. See [Zenkit Todo](../zenkit/zenkit-todo.md#writing-entries).
  - Delete: resolves uuids to numeric ids, then deprecates them (`/entries/delete/filter`); Zenkit soft-deletes.

## Devices

- Lists are refetched as in **Polling**, see [List changes](#list-changes).
- Device models are translated by `_async_device_models` from the `device` strings in `hass.config.language` at setup.
- The single device of versions before #51 (identifier = user id) gets the account identifier, keeping its area and name. If an account device exists already, the old one is removed.
- `async_remove_config_entry_device` allows removing devices that aren't in `coordinator.device_identifiers`, e.g. of deleted lists.

## List changes

When the lists are refetched (#36):

- **Added**: each platform sets up its list entities with `entity.async_add_list_entities`, which listens to the coordinator and adds entities whose unique id is new. This also adds a calendar or due date sensors once the fields of a list are known.
- **Removed**: the coordinator drops the list's cached fields and failure. `_update_list_devices` in `__init__.py` (a coordinator listener) removes the config entry from list devices not in `coordinator.device_identifiers`; HA then deletes the device and its entities from the registries.
- **Renamed or moved**: `_update_list_devices` updates the name and model of the list device (`name_by_user` is kept), the entity names follow it. The todo entity takes name, icon, folder and appearance attributes, the calendar its icon, from `coordinator.get_list` on every update. Entity ids are not changed.
