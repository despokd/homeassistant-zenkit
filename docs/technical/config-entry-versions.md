# Config entry versions

`async_migrate_entry` handles v1 entries: minor < 2 renames `api_key` → `token`. `ConfigFlow.VERSION` is 2.
`unique_id` is the Zenkit user id (`str(user["id"])`), set by the config flow. Older entries without it get it in `async_setup_entry`; a second entry for the same account keeps `None`. Setting it needs no version bump.
The device migration of #51 (single device → account device) runs in `async_setup_entry` and needs no version bump either, see [Data flow](data-flow.md#devices).
