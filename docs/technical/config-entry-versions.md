# Config entry versions

`ConfigFlow.VERSION` is 2, `MINOR_VERSION` 2. `async_migrate_entry` migrates older entries to 2.2 and refuses versions above 2:

- 1.1: renames `api_key` → `token`.
- 1.x and 2.1: unique ids of list entities (todo, calendar, list sensors) get the prefix `<entry_id>_` in the entity registry (#33), so entity ids and history stay. They were the list uuid, which is the same for all accounts sharing a workspace, so a second account's entity was rejected as duplicate. Account entities already started with the entry id and are skipped.

`unique_id` is the Zenkit user id (`str(user["id"])`), set by the config flow. Older entries without it get it in `async_setup_entry`; a second entry for the same account keeps `None`. Setting it needs no version bump.
The device migration of #51 (single device → account device) runs in `async_setup_entry` and needs no version bump either, see [Data flow](data-flow.md#devices).
