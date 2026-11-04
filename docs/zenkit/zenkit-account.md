# Zenkit Account

Observed with an API key (`Zenkit-API-Key` header) in November 2026.

## Current user

`GET /api/v1/auth/currentuser` and `GET /api/v1/users/me` return the same payload. Only `/users/me` is listed in the docs sidebar.

| Field | Example / type | Notes |
| --- | --- | --- |
| `id` | `906842` (int) | Stable, use as unique id of the account |
| `shortId`, `uuid` | str | Also stable |
| `organizationId` | int | |
| `username`, `displayname`, `fullname`, `initials` | str | `username` is the current config entry title |
| `timezone` | `Europe/Berlin` | |
| `settings.language` | `de` | Also the language of API error names (see below) |
| `settings.dateFormat`, `timeFormat`, `startOfTheWeek` | `DD.MM.YYYY`, `HH:mm`, `Mon` | |
| `imageLink` | `10959895` | File id of the profile image, see [Profile image](#profile-image) |
| `isTwoFactorAuthenticationEnabled` | bool | |
| `created_at`, `registered_at`, `last_login`, `last_seen` | ISO str | `last_login` is the last sign-in to the web/app, API requests don't change it. `last_seen` changes on every request, not useful as a state |
| `appInstances` | `[{uuid, appType, created_at}]` | `appType` e.g. `todos`, `base` |
| `api_key` | str | **The API key used for the request, in plain text** |
| `emails` | `[{email, isPrimary, isVerified, ...}]` | Personal data |
| `settings.recentListShortIds`, `recentListEntries`, `recentGlobalSearchQueries` | | Usage history |
| `settings.sortedWorkspaceIds` | `[1187910, ...]` | Workspace order in the sidebar; missing in an earlier response of the same account |
| `isSuperAdmin`, `isPasswordGenerated` | bool | `isSuperAdmin` is likely a Zenkit platform flag, not the organization role (that is `roleId` in [accesses](#access-and-notifications)) |
| `isImagePreferred` | bool | See [Profile image](#profile-image) |
| `privacy_policy_accepted_at`, `terms_accepted_at` | ISO str | |
| `blocked_at`, `blocked_by_organization_at` | ISO str or `null` | `null` for an active account |
| `providers` | `[]` | Presumably external sign-in providers; empty for an email/password account |
| `tokens` | | Sensitive |
| `abTests`, `backgroundId` | `null` | |
| `settings.notificationSettings` | `{general, activities, comments, mentions, reminders, reactions}` | Each `{email, toast, notification, desktopNotification, pushNotification}` |
| `settings.notificationSettingsPerList`, `notificationSettingsPerWorkspace` | dict | |
| `settings.decimalFormat` | `0` (int) | |
| `settings.defaultSortOrderForNewEntries` | `lowest` | |
| `settings.listActivityFilter`, `listEntryActivityFilter`, `userActivityFilter`, `workspaceActivityFilter` | int | |
| `settings.recentListsSettings`, `userFilesSettings` | dict | |
| `settings.assignmentsViewSettings`, `userCalendarSettings`, `userTagsSettings` | dict or `null` | |
| `settings.soundEnabled`, `useDockedChats` | bool | |
| `settings.releaseNotesWatermark` | ISO str | |
| `settings.listElementSettingsInfoDismissed`, `textfieldInfoDismissed`, `themeOnboardingDismissed`, `userAssignmentsInfoDismissed`, `userTagsInfoDismissed` | bool | Web app hints dismissed |

There is no separate first name or last name field; `fullname` is whatever the user entered as name.

Redact `api_key`, `emails`, `tokens` and the `recent*` settings before logging or adding the payload to diagnostics.

## Workspaces

See [Workspaces and folders](workspaces.md). In addition:

- `GET /api/v1/users/me/workspaces` (not in the docs) returns the same workspaces as `workspacesWithLists`, without `lists`.
- Zenkit Base workspaces (`appType: base`, `resourceType: document`) have `lists: []`.
- `GET /api/v1/workspaces/{workspaceId}/users` returns members: `id`, `username`, `displayname`, `fullname`, `initials`, `imageLink`, `emailCount`, `roleId` (e.g. `workspaceOwner`). No emails.

## Access and notifications

- `GET /api/v1/users/me/accesses` returns one access per shared resource: `accessType` (`List`, `Workspace`, `Organization`) and `roleId` (`listOwner`, `listAdmin`, `workspaceOwner`, `organizationOwner`, ...).
- `GET /api/v1/users/me/notifications?limit=1` returns `{newNotificationsCount: int, thereAreMoreResults, notifications}`; `newNotificationsCount` is the unread count.
- `GET /api/v1/users/me/new-notifications-in-minimal-format` returns `[]` when there are no new notifications.

## Organization

- `GET /api/v1/users/me/organizations` (not in the docs) returns `{myOrganizationId, organizations: [...]}`. Each organization has `id`, `name`, `description`, `planId` (e.g. `free`), `quotasExceeded`, `isOverdue`, `escalationLevel`, `subscription_valid_until`, `canUsers*` permission flags, and `volumeDetails` (`workspaceIds`, `listIds`, `userIds`).
- `GET /api/v1/organizations/{id}` and `/organizations` are not endpoints (404, code `C2`).
- `GET /api/v1/organizations/{id}/users` returns `{filteredTotal, users}`. Users include `roleId` (`organizationOwner`, `organizationAdmin`, ...) and the **emails of other members**.
- `volumeDetails.userIds` can be shorter than the organization's users (1 vs. 2 seen), use `filteredTotal`.

## Profile image

- The web app builds the URL from `imageLink`: `GET /api/v1/files/{imageLink}` (original, JPEG) or `/api/v1/files/{imageLink}/convert?w={px}&h={px}` (scaled).
- **No API key is needed**, the URL is public.
- Show it only if `isImagePreferred` is true, else Zenkit shows `initials`.

## Errors

- An invalid API key returns HTTP 401 `{"error": {"code": "UNAUTHENTICATED", "statusCode": 401, ...}}`.
- `error.name` is localized to the user's language (e.g. `Ressource nicht gefunden`), match on `code` or `statusCode`.
- `GET /api/v1/organizations/{id}` is not an endpoint (404, code `C2`); organization data is only available as `organizationId`.
- Responses carry no rate-limit headers.
