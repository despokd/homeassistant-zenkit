# Data flow

```
HA config entry (API key)
  └─> Zenkit api client ──HTTPS──> https://zenkit.com/api/v1  (header: Zenkit-API-Key)
        └─> ZenkitDataUpdateCoordinator (stored in hass.data[DOMAIN][entry_id])
              └─> ZenkitTodoListEntity × N  (one per list, unique_id = list uuid)
```

- **Setup**: `async_setup_entry` calls `login()` (`/auth/currentuser`). Network errors raise `ConfigEntryNotReady`; bad key returns `False`.
- **Polling**: the coordinator fetches lists once (`/users/me/workspacesWithLists`, flattened across workspaces and cached), then every interval fetches each list's entries via `/lists/{shortId}/entries/filter/list`, paginating recursively in pages of `ENTRIES_LIMIT`.
- **Writes**: entity create/update/delete call the api client, then `coordinator.async_refresh()`.
  - Create: `POST /lists/{shortId}/entries` with a new uuid, then `update_entry` to set the name.
  - Update: fetches the entry, finds the matching field, `PUT`s it. Only `name` is implemented; `description`, `completed`, `due_date` raise `NotImplementedError`.
  - Delete: resolves uuids to numeric ids, then deprecates them (`/entries/delete/filter`); Zenkit soft-deletes.