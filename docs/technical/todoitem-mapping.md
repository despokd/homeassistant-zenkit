# Entry → TodoItem mapping

Zenkit lists have user-defined fields, keyed `<elementUuid>_<type>`. Fields are found by the element's `resourceRole` (see [Zenkit Todo](../zenkit/zenkit-todo.md#element-roles)), using the elements cached per list in `Zenkit.elements`:

| TodoItem      | Element (`resourceRole`)       | Fallback without the role                       | Entry key                    |
| ------------- | ------------------------------ | ----------------------------------------------- | ---------------------------- |
| `uid`         |                                |                                                 | `uuid`                       |
| `summary`     | `title` (read: `displayString`) | `isPrimary` element                            | `<uuid>_text`                |
| `status`      | `stage`, option role `done`    | categories element with a `#3ba744` option      | `<uuid>_categories`          |
| `description` | `notes`                        | first text element without role, not the title | `<uuid>_text`                |
| `due`         | `dueDate`                      | first date element without role                 | `<uuid>_date`, `_hasTime`    |
| entity icon   | list `iconClassNames` (Font Awesome) converted to `mdi:*` |                      |                              |

- `due` is a `date`, or a local `datetime` if `_hasTime` is set (Zenkit stores it in UTC).
- An empty description (`""`) is shown as none.
- Until the elements of a list are fetched (or if the fetch failed), reads use the old heuristics: status by the `#3ba744` color in any `*_categories_sort`, description by the first `*_text` that differs from `displayString`, due by the first set `*_date`.

Completed items are filtered out and not shown in HA.
