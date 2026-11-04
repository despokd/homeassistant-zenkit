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

- `due` is a `date`, or a local `datetime` if `_hasTime` is set (Zenkit stores it in UTC).
- An empty description (`""`) is shown as none.
- Until the elements of a list are fetched (or if the fetch failed), reads use the old heuristics: status by the `#3ba744` color in any `*_categories_sort`, description by the first `*_text` that differs from `displayString`, due by the first set `*_date`.

Completed items are filtered out and not shown in HA.

## Lists without a status field

HA has no feature flag to disable completion only, dropping `UPDATE_TODO_ITEM` would also disable editing. Once the elements of a list are known and it has no status element with a done option, its items get `status=None`:

- The HA todo card shows them in a separate section with an indeterminate checkbox.
- Clicking that checkbox sends `needs_action`, which is ignored. The card keeps showing it ticked until reloaded, as the item does not change (Lit does not reset the checkbox). Setting `completed` raises a `ServiceValidationError` (`no_status_field`).
- The entity state only counts `needs_action` items, so it is `0` for such lists.
