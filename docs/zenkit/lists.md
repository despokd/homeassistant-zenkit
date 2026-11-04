# Lists

Appearance fields of a list, from the [List type](https://base.zenkit.com/docs/api/type/list) of the API docs. `GET /users/me/workspacesWithLists` returns them with each list, so no extra requests are needed.

Checked on 2026-11-05 against a real account: `description`, `iconClassNames`, `iconColor`, `iconBackgroundColor` and `imageId` are returned as below. No list there had a cover image or background, so those are only documented, not seen. A list with an icon image still has `iconColor` and `iconBackgroundColor` set.

| Field | Type | Meaning |
| --- | --- | --- |
| `description` | str | List description, may be `""` or `null` |
| `iconClassNames` | str | Font Awesome class of the list icon, e.g. `fa fa-plane`. Not in the API docs |
| `iconColor` | str | Hex color of the icon, `null` if unset |
| `iconBackgroundColor` | str | Hex color behind the icon, `null` if unset |
| `imageId` | int | File id of the list image, `0` if none |
| `coverImageId` | int | File id of the cover image, `0` if none |
| `backgroundId` | str | Id of the list background, `null` if none |

## Images

- The web app loads a list image from `GET /api/v1/files/{imageId}`, scaled with `/convert?w={px}&h={px}`, the same URL as the profile image ([Profile image](zenkit-account.md#profile-image)). It also knows the form `/api/v1/lists/{listId}/files/{fileId}`.
- **Unlike the profile image, a list image is not public**: without a session or API key the URL returns HTTP 403 (error code `A5`, verified 2026-11-05). So the URL can't be given to a browser as is; it has to be fetched with the API key, e.g. by an HA image entity.
- The API docs have no endpoint to get a file by id.

## Background

- `backgroundId` refers to a Background (`GET /api/v1/backgrounds/{backgroundId}`), with `colorHex`, `fileId` (ShortID of the image), `previewFileShortId`, `theme`, `style`, `description` and `link`. Resolving it needs one request per list, so it isn't done.
