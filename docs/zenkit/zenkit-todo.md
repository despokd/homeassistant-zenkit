# Zenkit Todo

## Element roles

`GET /api/v1/lists/{listAllId}/elements` returns a list's elements (fields). Each element has an undocumented `resourceRole` that says what it means, independent of its user-visible (localized) name:

| `resourceRole` | `elementcategory` | Example name | Entry key |
| --- | --- | --- | --- |
| `title` | 1 (text) | Titel | `<uuid>_text` |
| `stage` | 6 (categories) | Phase | `<uuid>_categories`, `<uuid>_categories_sort` |
| `notes` | 1 (text) | Notizen | `<uuid>_text` |
| `dueDate` | 4 (date) | Fälligkeitsdatum | `<uuid>_date` |
| `assignments` | 14 | Zugewiesen an | |
| `files` | 15 | Anhänge | |
| `tags` | 6 (categories) | Tags | |

- Lists of type `database` (e.g. created empty) only have `title`; elements without a role return `resourceRole: null`.
- `isPrimary: true` marks the title element on every list, including `database` lists.
- `GET /api/v1/lists/{listAllId}` has `resourceType` (`taskList`, `project`, `database`) and `appType` (`todos`, `base`).

## Status

- Status is the element with `resourceRole: "stage"` (single-select categories, `elementData.multiple: false`).
- Its options are `elementData.predefinedCategories`. Each has an `id`, a `uuid` and a `resourceRole`:
  - `todo`: open (e.g. "Zu bearbeiten", `#0089d1`)
  - `done`: completed (e.g. "Erledigt", `#3ba744`)
  - user-added options (e.g. "In Bearbeitung") have `resourceRole: null`
- Option names are localized and user-editable, so match on `resourceRole`, not on `name` or `colorHex`.
- `businessData.categories` on the element holds the default option ids for new entries (may be `[]`).
- An entry stores the status twice: `<uuid>_categories` is a list of option ids, `<uuid>_categories_sort` is a list of option objects (`id`, `uuid`, `name`, `colorHex`).

## Writing entries

Verified against a `taskList` (2026-10-25):

- Set status: `PUT /lists/{listAllId}/entries/{entryAllId}` with `{"<uuid>_categories": [optionId]}`. `_categories_sort` is updated by Zenkit.
- Writing `_categories_sort` returns `200` but is **silently ignored**.
- `{"<uuid>_categories": []}` clears the status.
- One PUT can set several fields, e.g. `{"<titleUuid>_text": "...", "<stageUuid>_categories": [optionId]}`.
- `POST /lists/{listAllId}/entries` accepts field values next to `uuid`, so an entry can be created with title, notes, due date and status in one request.
- `POST /lists/{listId}/entries/delete/filter` with `{"listEntryIds": [id]}` deprecates entries: a GET by uuid still returns them with `deprecated_at` set, but the filter endpoint with `allowDeprecated: false` no longer lists them.

Text and date fields, verified against a `taskList` (2026-10-25):

- Text (`notes`): `{"<uuid>_text": "..."}`. Stored as plain text (`<uuid>_textType: "plain"`), line breaks and Markdown characters are kept as is. Zenkit also returns `<uuid>_searchText`.
- Clear a text with `null`; it is then returned as `""`.
- Date (`dueDate`): an entry has `<uuid>_date`, `<uuid>_hasTime`, `<uuid>_endDate` and `<uuid>_duration`.
  - Date only: `{"<uuid>_date": "2026-11-03", "<uuid>_hasTime": false}`.
  - With time: `{"<uuid>_date": "2026-11-03T14:30:00.000Z", "<uuid>_hasTime": true}`, stored and returned in UTC.
  - The integration always writes `_hasTime` together with `_date`.
  - Clear with `{"<uuid>_date": null}`; `""` is rejected with `400` (`C21`, "not a valid ISO date string").

## Reading entries

`POST /lists/{shortId}/entries/filter/list` returns at most `limit` entries (the integration uses 100) plus `countData.filteredTotal`; page with `skip`. An empty list returns `listEntries: null`.

Observed 2026-10-25 on a list with 1383 entries (14 pages): 42 pages fetched back to back all returned 200 in 0.12–0.25 s, with no rate-limit or `Retry-After` headers. A page occasionally fails with a body that isn't JSON (seen once in HA, not reproducible), so error bodies must not be parsed as JSON. The rate limits themselves are undocumented in a readable form (#6).
