# API overview

What the [Zenkit API](https://base.zenkit.com/docs/api/overview/structure) offers beyond the endpoints the integration uses, checked on 2026-11-05 for [#2](https://github.com/despokd/homeassistant-zenkit/issues/2). For which of these the integration will use, see the decisions in #2.

The API docs render client-side: a plain HTTP fetch returns only an HTML shell, so read them in a browser. Most endpoint pages list only the path and the response codes, without a request body.

Zenkit has no separate calendar, board or timeline resources. Calendar, Kanban and Gantt are views of a list's entries and elements.

## Element categories

`GET /api/v1/elementcategories` returns all element (field) types. **It needs no API key.**

| `id` | `name` | | `id` | `name` |
| --- | --- | --- | --- | --- |
| 1 | Textfield | | 11 | Created_by |
| 2 | Number | | 12 | Updated_by |
| 3 | Link | | 13 | Deprecated_by |
| 4 | Date | | 14 | Persons |
| 5 | Checkbox | | 15 | Files |
| 6 | Categories | | 16 | References |
| 7 | Formula | | 17 | Hierarchy |
| 8 | Created_at | | 18 | Subentries |
| 9 | Updated_at | | 19 | Dependencies |
| 10 | Deprecated_at | | | |

All have `group: "Control"`. An element's `elementcategory` is one of these ids, see [Element roles](zenkit-todo.md#element-roles).

The [Checklist type](https://base.zenkit.com/docs/api/type/checklist) is `{uuid, name, items, shouldCheckedItemsBeHidden}`; checklists are written with `PUT /lists/{listAllId}/entries/{entryAllId}/checklists`.

## Webhooks

- `POST /api/v1/webhooks` creates a webhook, `DELETE /api/v1/webhooks/{webhookId}` removes it. The docs don't show the request body.
- [Webhook](https://base.zenkit.com/docs/api/type/webhook) fields: `triggerType`, `url`, `workspaceId`, `listId`, `listEntryId` (scope), `userId`, `provider`, `locale`.
- `triggerType` ([WebhookTriggerType](https://base.zenkit.com/docs/api/type/webhooktriggertype)): `0` Entry, `1` Activity, `2` Notification, `3` System Message, `4` Comment.
- Zenkit has to reach the webhook URL, so a Home Assistant instance would need a public URL.

## Notifications

[NotificationType](https://base.zenkit.com/docs/api/type/notificationtype): `personAdded`, `listShare`, `workspaceShare`, `subscription`, `reminder`, `mention`. For the endpoints see [Access and notifications](zenkit-account.md#access-and-notifications).

## Activities

- [ActivityType](https://base.zenkit.com/docs/api/type/activitytype): `0` comment, `1` created, `2` updated, `3` deprecated, `4` imported, `5` copied, `6` restored, `7` bulk operation in list, `8` deleted.
- Activities can be searched per user, workspace, list and entry (`GET .../activities?limit&skip&filter`). `POST /lists/{listAllId}/activities/sync` returns list activities after a watermark.

## Watermark sync

`POST /lists/{listShortId}/entries/sync` returns the most recently updated entries of a list. The first call sends no watermark; later calls send the watermark of the previous response. `excludeDeprecatedBefore` (the time of the first call) skips entries deprecated before the sync started. Not tried yet.

## Calendar synchronization

The Calendar Synchronization endpoints connect a list or workspace to an external calendar provider via OAuth (`GET /users/me/oauth/calendars/{provider}`, `POST /lists/{listAllId}/connections/calendar`, `POST /workspaces/{workspaceAllId}/connections/calendar`). The API docs show no ICS feed, so these endpoints are no source for an HA calendar; use the entries' due dates instead.

## Kanban sort

`PUT /lists/{listAllId}/elements/{elementAllId}/kanbanSort` reorders the columns (category options) of a Kanban view. It only writes view order.
