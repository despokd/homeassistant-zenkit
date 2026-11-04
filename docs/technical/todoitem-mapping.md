# Entry → TodoItem mapping

Zenkit lists have user-defined fields, keyed `<elementUuid>_<type>`. Fields are found by the element's `resourceRole` (see [Zenkit Todo](../zenkit/zenkit-todo.md#element-roles)), using the elements cached per list in `Zenkit.elements`:

| TodoItem      | Element (`resourceRole`)       | Fallback without the role                       | Entry key                    |
| ------------- | ------------------------------ | ----------------------------------------------- | ---------------------------- |
| `uid`         |                                |                                                 | `uuid`                       |
| `summary`     | `title` (read: `displayString`) | `isPrimary` element                            | `<uuid>_text`                |
| `status`      | `stage`, option role `done`    | categories element with a `#3ba744` option; none → `None` | `<uuid>_categories` |
| `description` | `notes`                        | first text element without role, not the title | `<uuid>_text`                |
| `due`         | `dueDate`                      | first date element without role                 | `<uuid>_date`, `_hasTime`    |
| entity icon   | list `iconClassNames` (Font Awesome) converted to `mdi:*` |                      |                              |
| entity attributes | list `workspaceId`, workspaces' `parentWorkspaceId` ([Workspaces and folders](../zenkit/workspaces.md)) |  | `workspace`, `folder`, `folder_id`, `folder_path` |
| entity attributes | list `description`, `iconClassNames`, `iconColor`, `iconBackgroundColor`, `imageId`, `coverImageId`, `backgroundId` ([Lists](../zenkit/lists.md)) |  | `description`, `icon_class`, `icon_color`, `icon_background_color`, `image_id`, `cover_image_id`, `background_id` |
| entity attribute `item_details` | `subtasks` (18), `dependencies` (19), hierarchy (17), entry `checklists` ([Sub-items](../zenkit/zenkit-todo.md#sub-items-dependencies-and-checklists)) | element by category | `<uuid>_parents` (last), `<uuid>_references`, `<uuid>_value`, `checklists` |

- `due` is a `date`, or a local `datetime` if `_hasTime` is set (Zenkit stores it in UTC).
- An empty description (`""`) is shown as none.
- Until the elements of a list are fetched (or if the fetch failed), reads use the old heuristics: status by the `#3ba744` color in any `*_categories_sort`, description by the first `*_text` that differs from `displayString`, due by the first set `*_date`.

Completed items are filtered out and not shown in HA.

## Lists without a status field

HA has no feature flag to disable completion only, dropping `UPDATE_TODO_ITEM` would also disable editing. Once the elements of a list are known and it has no status element with a done option, its items get `status=None`:

- The HA todo card shows them in a separate section with an indeterminate checkbox.
- Clicking that checkbox sends `needs_action`, which is ignored. The card keeps showing it ticked until reloaded, as the item does not change (Lit does not reset the checkbox). Setting `completed` raises a `ServiceValidationError` (`no_status_field`).
- The entity state only counts `needs_action` items, so it is `0` for such lists.

## Item details

HA todo items have no sub-tasks (#43), so the entity has a read-only `item_details` attribute. It maps the uid of each shown (open) item to what it has, empty values and items without any are left out; the attribute is missing if no item has details:

```yaml
item_details:
  57fd3671-56b2-4bb6-8dc9-9b2e95e6178c:
    parent: <uid>             # Subitems <uuid>_parents, last
    children: [<uid>]         # Subitems <uuid>_references
    dependencies: [<uid>]     # Dependencies <uuid>_references
    hierarchy: "1.2"          # Hierarchy <uuid>_value
    checklists:
      - {name: Checklist, checked: 1, total: 4}
```

Referenced uids may be completed items, which are not in the todo list.
