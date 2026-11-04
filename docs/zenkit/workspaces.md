# Workspaces and folders

The API docs don't describe folders. The following comes from the Zenkit web app bundle (`base.zenkit.com/assets/index-*.js`) and was checked against real `GET /users/me/workspacesWithLists` responses on 2026-11-04, from an account with the chain workspace > folder > folder, with lists at each level.

## Folders are workspaces

- Every workspace, top-level or nested, has a `resourceType`. Seen values: `"folder"`, `"document"`, `"viewContainer"`, `"portfolio"`. The bundle also lists `agency`, `notebook`, `groupChat`, `privateChat`, `process`.
- **Top-level workspaces have `resourceType: "folder"` too**, not `null` (a top-level `"portfolio"` was also seen). So `resourceType` does not tell a folder from a workspace; `parentWorkspaceId` does.
- `parentWorkspaceId` is the numeric `id` of the parent workspace, `null` for a top-level workspace.
- A folder inside a workspace is a nested workspace with `resourceType: "folder"`. Nested workspaces aren't always folders: `"document"` and `"viewContainer"` children (with no lists) were seen too. Only folders were seen holding lists.
- `sortOrder` is `null` on top-level workspaces and an int on nested ones. The web app sorts siblings by `sortOrder`, then `id`.
- Folders nest: a folder's parent may be a workspace or another folder (both verified). A folder in a folder looks the same: `resourceType: "folder"`, `parentWorkspaceId` = the outer folder's `id`, int `sortOrder`.
- A list has `workspaceId`, the id of the workspace or folder it is directly in. Verified for lists in a top-level workspace, a folder and a folder in a folder. Moving a list into a folder changes its `workspaceId` to the folder's `id`.

## `GET /users/me/workspacesWithLists`

- Returns a **flat** array of all workspaces the user can access, nested ones included, each with its own `lists`. Verified: nested workspaces appear as their own array entries next to their parent, and no list appears twice.
- A folder's lists are in the folder's `lists`, not in its parent's (verified).
- So a list's folder path is resolved without extra requests: find the workspace whose `id` is the list's `workspaceId`, then follow `parentWorkspaceId` up to a workspace without a parent. Don't filter on `resourceType` when doing this.
- Other endpoints: `GET /workspaces/{id}` and `GET /workspaces/{id}/lists`.

### Shape (sanitized)

```json
[
  {
    "id": 1000,
    "shortId": "abc123",
    "name": "Home",
    "resourceType": "folder",
    "parentWorkspaceId": null,
    "sortOrder": null,
    "appType": "todos",
    "isDefault": false,
    "lists": [
      {
        "id": 2000,
        "shortId": "def456",
        "name": "Groceries",
        "workspaceId": 1000,
        "resourceType": "taskList",
        "appType": "todos",
        "sortOrder": 0
      }
    ]
  },
  {
    "id": 1001,
    "name": "Notes",
    "resourceType": "document",
    "parentWorkspaceId": 1000,
    "sortOrder": 1,
    "appType": "base",
    "lists": []
  }
]
```

Other workspace fields: `uuid`, `description`, `organizationId`, `visibility`, `settings`, `tags`, `resourceTags`, icon/image fields, `created_at`/`updated_at`/`deprecated_at`, `created_by`. Lists also carry their own `resourceType` (seen: `taskList`, `database`, `project`) and `appType` (`todos`, `base`).
