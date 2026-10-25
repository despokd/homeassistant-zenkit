# Entry → TodoItem mapping

Zenkit lists have user-defined fields, keyed `<elementUuid>_<type>`. The integration maps them heuristically:

| TodoItem      | Zenkit source                                                               |
| ------------- | --------------------------------------------------------------------------- |
| `uid`         | `uuid`                                                                      |
| `summary`     | `displayString`                                                             |
| `status`      | `COMPLETED` if any `*_categories_sort` category has `colorHex == "#3ba744"` |
| `description` | first `*_text` field that differs from `displayString`                      |
| `due`         | first non-null `*_date` field, parsed with `DUE_DATE_FORMAT`                |
| entity icon   | list `iconClassNames` (Font Awesome) converted to `mdi:*`                   |

Completed items are filtered out and not shown in HA.

Writing `status` uses element roles instead of the color, see [Data flow](data-flow.md).