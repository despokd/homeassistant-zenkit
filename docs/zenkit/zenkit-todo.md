# Zenkit Todo

## Element roles

`GET /api/v1/lists/{listAllId}/elements` returns a list's elements (fields). Each element has an undocumented `resourceRole` that says what it means, independent of its user-visible (localized) name:

| `resourceRole` | `elementcategory` | Example name | Entry key |
| --- | --- | --- | --- |
| `title` | 1 (text) | Titel | `<uuid>_text` |
| `stage` | 6 (categories) | Phase | `<uuid>_categories`, `<uuid>_categories_sort` |
| `notes` | 1 (text) | Notizen | `<uuid>_text` |
| `dueDate` | 4 (date) | Fälligkeitsdatum | `<uuid>_date` |
| `assignments` | 14 (persons) | Zugewiesen an | `<uuid>_persons`, `<uuid>_persons_sort` |
| `files` | 15 | Anhänge | |
| `tags` | 6 (categories) | Tags | `<uuid>_categories`, `<uuid>_categories_sort` |
| `subtasks` | 18 (subentries) | Subitems | `<uuid>_references`, `_parents`, `_path`, … (see [Sub-items](#sub-items-dependencies-and-checklists)) |
| `dependencies` | 19 (dependencies) | Abhängigkeiten | `<uuid>_references`, `_tags`, `_milestone` |

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

Labels and assignees, verified against a `taskList` and a `project` (2026-11-05):

- Labels (`tags`, `elementData.multiple: true`) are written like the status: `{"<uuid>_categories": [optionId, ...]}`. Options are `elementData.predefinedCategories` with `resourceRole: null`.
- New options can't be created through the API: `POST /lists/{listAllId}/elements/{elementAllId}/categories` (and variants with numeric ids or `predefinedcategories`) return `404`. Labels have to be added in Zenkit first.
- `taskList`s have no `tags` element, `project`s have one.
- Assignees (`assignments`, category 14): `{"<uuid>_persons": [userId, ...]}` with numeric user ids. Zenkit returns `<uuid>_persons_sort` with `id`, `displayname`, `username`, `initials` and the image fields.
- The members of a list come from `GET /lists/{listAllId}/users` (not in the docs): users with `id`, `displayname`, `fullname`, `username` and `roleId` (e.g. `listOwner`), but no email.

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

## Sub-items, dependencies and checklists

Observed 2026-11-05 on a `project` list ("testproj") with a Subitems and a Dependencies element, by setting and then clearing relations, and read-only on 15 `taskList`s. The keys are also listed in `GET /api/v1/elementcategories` (public, `businessDataDefinition`).

Subentries (category 18, `resourceRole: "subtasks"`, `singleton: true`), per entry:

| Key | Example | Meaning |
| --- | --- | --- |
| `<uuid>_references` | `["<child uuid>"]` | uuids of the direct sub-items (children) |
| `<uuid>_references_sort` | `[{"uuid", "displayString", …}]` | the children as entry objects |
| `<uuid>_parents` | `["<root uuid>", "<parent uuid>"]` | all ancestors from the root, the last is the direct parent |
| `<uuid>_path` | `"00000001.00000001"` | ltree path, one segment per level |
| `<uuid>_sortOrder` | `3` | position among siblings, `null` for a sub-item |
| `<uuid>_connected` | `true` | element `businessData.connected` is `true` too |

- Set sub-items on the parent: `PUT` `{"<uuid>_references": [childUuid]}`. Zenkit then sets the child's `_parents` and `_path`; `[]` clears it.
- Changing the tree renumbers the top-level `_path` segments of other entries (their `_sortOrder` stays), so clearing relations again does not restore the previous path order.

Dependencies (category 19, `resourceRole: "dependencies"`, `singleton: true`), per entry: `<uuid>_references` (uuids of the linked entries), `<uuid>_references_sort` (as entry objects), `<uuid>_tags` (`{}`) and `<uuid>_milestone` (`false`). A dependency is only stored on the entry it was written to, not mirrored on the referenced entry. Which side the Zenkit UI shows as the predecessor was not checked.

Hierarchy (category 17) was on none of the lists. Its category definition has a single text value (`businessDataDefinition.value`, `sortKey: "value"`, filter key `level`), so the entry key is assumed to be `<uuid>_value`.

Checklists are not an element: every entry has a top-level `checklists` array (also `[]` on lists without any):

```json
"checklists": [
  {
    "name": "Checklist",
    "uuid": "0341d82b-…",
    "items": [{"text": "…", "checked": false}],
    "shouldCheckedItemsBeHidden": false
  }
]
```

Checklist items have no uuid. Writing checklists is untested.
