# Data flow

```
HA config entry (API key)
  └─> Zenkit api client ──HTTPS──> https://zenkit.com/api/v1  (header: Zenkit-API-Key)
        └─> ZenkitDataUpdateCoordinator (stored in hass.data[DOMAIN][entry_id])
              └─> account device (service, identifier = Zenkit user id)
                    ├─> ZenkitTodoListEntity × N  (one per list, unique_id = list uuid)
                    ├─> ZenkitRefreshButton
                    ├─> ZenkitSensor × 21  (account and organization, see sensor.SENSORS)
                    └─> ZenkitProfileImage
```

- **Setup**: `async_setup_entry` calls `login()` (`/auth/currentuser`) and keeps the returned user on the coordinator for the account device and diagnostics. Network and server errors (`CannotConnectException`) raise `ConfigEntryNotReady`; a bad key (HTTP 401) returns `False`. Older entries get the user id as `unique_id`, unless another entry already has it.
- **Polling**: the coordinator fetches lists once (`/users/me/workspacesWithLists`, flattened across workspaces and cached; each list gets its workspace and folder path from the same response, see [Workspaces and folders](../zenkit/workspaces.md)), and each list's elements once (`/lists/{shortId}/elements`, cached in `Zenkit.elements`, retried on the next poll if it failed). Then every interval it fetches each list's entries via `/lists/{shortId}/entries/filter/list`, page by page in pages of `ENTRIES_LIMIT`. A failed page (5xx, 429, non-JSON body, connection error) is retried after `RETRY_DELAYS` seconds; other errors are not retried.
- **Account**: the first poll, then every `USER_UPDATE_INTERVAL` s (1 h) and a forced refresh fetch the user (`login()`), its organization (`/users/me/organizations`) and the organization's member count (`/organizations/{id}/users`). A failure keeps the last known data.
- **Notifications**: after the lists, each poll fetches `/users/me/notifications?limit=1` for `newNotificationsCount`. A failure only sets `coordinator.unread_notifications` to `None` (sensor unavailable).
- **Failures**: lists are fetched independently. A list whose entries can't be fetched is left out of the data and added to `coordinator.failed_lists`, so only its entity is unavailable; it is removed again on its next successful fetch. The update only fails (all entities unavailable) if every list fails.
- **Writes**: entity create/update/delete call the api client, then `coordinator.async_refresh_list(shortId)`, which re-fetches only that list's entries. If that fetch fails, only that list goes unavailable until the next poll.
  - Every write fetches `/lists/{shortId}/elements` first, which also refreshes the cache, so renamed or added fields and options are picked up. Fields are picked as in [Entry → TodoItem mapping](todoitem-mapping.md).
  - Create: `POST /lists/{shortId}/entries` with a new uuid and the fields (name, and description/due if set) in one request.
  - Update: the entity compares the HA item with the coordinator data and passes only changed fields (`name`, `completed`, `description`, `due`). `update_entry` `PUT`s all changes in one request. See [Zenkit Todo](../zenkit/zenkit-todo.md#writing-entries).
  - Delete: resolves uuids to numeric ids, then deprecates them (`/entries/delete/filter`); Zenkit soft-deletes.