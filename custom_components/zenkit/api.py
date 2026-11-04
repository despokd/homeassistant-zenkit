"""The Zenkit api."""

import requests  # type: ignore
import asyncio
import datetime
import logging

from requests.exceptions import RequestException  # type: ignore

from .const import (
    API_URL,
    ENTRIES_LIMIT,
    DUE_DATE_FORMAT,
    DUE_DATETIME_FORMAT,
    RETRY_DELAYS,
)
from .elements import (
    due_element,
    notes_element,
    stage_element,
    status_option,
    title_element,
)
from .exceptions import (
    CannotConnectException,
    CannotLoginException,
    UpdateFailedException,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FIELDS = {"name", "completed", "description", "due"}


def _log_error(response, message: str, *args) -> None:
    """Log a failed response, its body may not be JSON (e.g. a proxy error page)."""
    _LOGGER.error(
        message + ": HTTP %s %s: %s",
        *args,
        response.status_code,
        response.reason,
        response.text[:500],
    )


def user_image_url(user: dict, size: int) -> str | None:
    """Get the URL of a user's profile image, it needs no API key."""
    if not user.get("isImagePreferred") or not user.get("imageLink"):
        return None
    return f"{API_URL}/files/{user['imageLink']}/convert?w={size}&h={size}"


def _is_retryable(response) -> bool:
    """Whether a failed request may succeed when sent again."""
    return response.status_code == 429 or response.status_code >= 500


def _entry_fields(elements: list[dict], list_short_id: str, **kwargs) -> dict:
    """Get the entry fields to write the given values."""
    unsupported = set(kwargs) - SUPPORTED_FIELDS
    if unsupported:
        raise NotImplementedError(
            "Update of fields not implemented: %s" % ", ".join(sorted(unsupported))
        )

    def require(element: dict | None, name: str) -> str:
        if element is None:
            raise UpdateFailedException(
                "List %s has no %s field" % (list_short_id, name)
            )
        return element["uuid"]

    fields = {}
    if "name" in kwargs:
        fields[f"{require(title_element(elements), 'title')}_text"] = kwargs["name"]
    if "description" in kwargs:
        # null clears the text, Zenkit then returns ""
        uuid = require(notes_element(elements), "description")
        fields[f"{uuid}_text"] = kwargs["description"] or None
    if "due" in kwargs:
        uuid = require(due_element(elements), "due date")
        fields.update(_due_fields(uuid, kwargs["due"]))
    if "completed" in kwargs:
        stage = stage_element(elements)
        if stage is None:
            raise UpdateFailedException(
                "List %s has no status field to complete items" % list_short_id
            )
        option = status_option(stage, kwargs["completed"])
        if option is None and kwargs["completed"]:
            raise UpdateFailedException(
                "List %s has no done status option" % list_short_id
            )
        # Only `_categories` is writable, `_categories_sort` is ignored by Zenkit
        fields[f"{stage['uuid']}_categories"] = [option["id"]] if option else []
    return fields


def _due_fields(uuid: str, due: datetime.date | None) -> dict:
    """Get the date element fields for a due date, date-time or none."""
    if isinstance(due, datetime.datetime):
        value = due.astimezone(datetime.timezone.utc).strftime(DUE_DATETIME_FORMAT)
        return {f"{uuid}_date": value, f"{uuid}_hasTime": True}
    # An empty string is rejected, null clears the date
    value = due.strftime(DUE_DATE_FORMAT) if due is not None else None
    return {f"{uuid}_date": value, f"{uuid}_hasTime": False}


def _folder(workspace: dict, workspaces: list[dict]) -> dict:
    """Get the top-level workspace and folder path of the lists in a workspace."""
    # Folders are nested workspaces, top-level ones are of type "folder" too,
    # so only `parentWorkspaceId` tells them apart (docs/zenkit/workspaces.md)
    by_id = {w["id"]: w for w in workspaces}
    path = [workspace]
    while (
        parent := by_id.get(path[0].get("parentWorkspaceId"))
    ) and parent not in path:
        path.insert(0, parent)
    folders = path[1:]
    return {
        "workspace": path[0]["name"],
        "folder": folders[-1]["name"] if folders else None,
        "folder_id": folders[-1]["id"] if folders else None,
        "folder_path": [folder["name"] for folder in folders],
    }


class Zenkit:
    """Class to manage fetching Zenkit data with API key authentication."""

    def __init__(self, api_key: str) -> None:
        """Initialize with the provided API key."""
        # https://base.zenkit.com/docs/api/overview/introduction
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Zenkit-API-Key": self.api_key,
        }
        self.elements: dict[str, list[dict]] = {}

    async def login(self) -> dict:
        """Login to the Zenkit API, returns the current user."""
        # https://base.zenkit.com/docs/api/overview/authentication
        url = f"{API_URL}/auth/currentuser"
        try:
            response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        except RequestException as error:
            raise CannotConnectException from error

        if response.status_code == 401:
            raise CannotLoginException
        if response.status_code != 200:
            _log_error(response, "Failed to login")
            raise CannotConnectException
        try:
            user = response.json()
        except ValueError as error:
            raise CannotConnectException from error
        if type(user) is not dict or user.get("username") is None:
            raise CannotLoginException

        return user

    async def get_organization(self, organization_id: int) -> dict | None:
        """Get an organization of the current user, None if it is not one of them."""
        # Not in the docs, /organizations/{id} is no endpoint
        url = f"{API_URL}/users/me/organizations"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        if response.status_code != 200:
            _log_error(response, "Failed to fetch organizations")
            raise UpdateFailedException("Failed to fetch organizations")

        return next(
            (
                organization
                for organization in response.json()["organizations"]
                if organization["id"] == organization_id
            ),
            None,
        )

    async def get_organization_members_count(self, organization_id: int) -> int:
        """Get the number of users of an organization."""
        # Not in the docs, also returns the users with their emails
        url = f"{API_URL}/organizations/{organization_id}/users"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        if response.status_code != 200:
            _log_error(response, "Failed to fetch organization users")
            raise UpdateFailedException("Failed to fetch organization users")

        return response.json()["filteredTotal"]

    async def get_unread_notifications_count(self) -> int:
        """Get the number of new notifications."""
        # https://base.zenkit.com/docs/api/notifications/get-api-v1-users-me-notifications
        url = f"{API_URL}/users/me/notifications"
        response = await asyncio.to_thread(
            requests.get, url, headers=self.headers, params={"limit": 1}
        )
        if response.status_code != 200:
            _log_error(response, "Failed to fetch notifications")
            raise UpdateFailedException("Failed to fetch notifications")

        return response.json()["newNotificationsCount"]

    async def get_lists(self) -> dict:
        """Get lists."""
        # https://base.zenkit.com/docs/api/workspaces/get-api-v1-users-me-workspaceswithlists
        url = f"{API_URL}/users/me/workspacesWithLists"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        workspaces = response.json()
        lists = []
        for workspace in workspaces:
            folder = _folder(workspace, workspaces)
            for list in workspace["lists"]:
                lists.append({**list, "_folder": folder})
        return lists

    async def get_list_entries(self, list_short_id: str) -> list[dict]:
        """Get all list entries, page by page."""
        entries = []
        while True:
            page = await self._get_list_entries_page(list_short_id, len(entries))
            if page["listEntries"] is None:
                return entries
            entries += page["listEntries"]
            # Stop on an empty page too, in case the total changes while paging
            if not page["listEntries"] or page["countData"]["filteredTotal"] <= len(
                entries
            ):
                return entries

    async def _get_list_entries_page(self, list_short_id: str, skip: int) -> dict:
        """Get one page of list entries, retrying transient errors."""
        # https://base.zenkit.com/docs/api/entries/post-api-v1-lists-listshortid-entries-filter-list
        url = f"{API_URL}/lists/{list_short_id}/entries/filter/list"
        data = {
            "filter": {},
            "groupByElementId": 0,
            "limit": ENTRIES_LIMIT,
            "skip": skip,
            "exclude": [],
            "allowDeprecated": False,
            "taskStyle": False,
        }
        for delay in (*RETRY_DELAYS, None):
            try:
                response = await asyncio.to_thread(
                    requests.post, url, headers=self.headers, json=data
                )
            except RequestException as error:
                _LOGGER.warning(
                    "Failed to fetch entries of list %s at %s: %s",
                    list_short_id,
                    skip,
                    error,
                )
                retry = True
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError:
                        pass
                _log_error(
                    response,
                    "Failed to fetch entries of list %s at %s",
                    list_short_id,
                    skip,
                )
                retry = response.status_code == 200 or _is_retryable(response)
            if delay is None or not retry:
                break
            await asyncio.sleep(delay)

        raise UpdateFailedException(
            "Failed to fetch entries of list %s at %s" % (list_short_id, skip)
        )

    async def get_list_entry(self, list_any_id: str, entry_id: str) -> dict:
        """Get list entry."""
        # https://base.zenkit.com/docs/api/entries/get-api-v1-lists-listallid-entries-listentryallid
        url = f"{API_URL}/lists/{list_any_id}/entries/{entry_id}"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        if response.status_code != 200:
            _log_error(response, "Failed to fetch entry %s", entry_id)
            raise UpdateFailedException("Failed to fetch entry %s" % entry_id)

        return response.json()

    async def create_entry(self, list_short_id: str, entry_id: str, **kwargs) -> None:
        """Add an entry with its fields to a list."""
        elements = await self.get_list_elements(list_short_id)
        # https://base.zenkit.com/docs/api/entries/post-api-v1-lists-listid-entries
        url = f"{API_URL}/lists/{list_short_id}/entries"
        data = {
            "uuid": entry_id,
            **_entry_fields(elements, list_short_id, **kwargs),
        }
        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=data
        )

        if response.status_code != 200:
            _log_error(response, "Failed to create entry in list %s", list_short_id)
            raise Exception("Error creating list entry")

    async def update_entry(self, list_short_id: str, entry_id: str, **kwargs) -> None:
        """Update an entry in a list."""
        if not kwargs:
            return None

        # Fetched on each write, so renamed or added fields and options are picked up
        elements = await self.get_list_elements(list_short_id)
        update = _entry_fields(elements, list_short_id, **kwargs)

        # https://base.zenkit.com/docs/api/entries/put-api-v1-lists-listid-entries-listentryid
        url = f"{API_URL}/lists/{list_short_id}/entries/{entry_id}"
        response = await asyncio.to_thread(
            requests.put, url, headers=self.headers, json=update
        )

        if response.status_code != 200:
            _log_error(response, "Failed to update entry %s", entry_id)
            raise Exception("Error updating list entry")

        return response.raise_for_status()

    async def get_list_elements(self, list_any_id: str) -> list[dict]:
        """Get the elements (fields) of a list."""
        # https://base.zenkit.com/docs/api/elements/get-api-v1-lists-listallid-elements
        url = f"{API_URL}/lists/{list_any_id}/elements"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        if response.status_code != 200:
            _log_error(response, "Failed to fetch fields of list %s", list_any_id)
            raise UpdateFailedException(
                "Failed to fetch fields of list %s" % list_any_id
            )

        # Cached for reading entries, refreshed on each write
        self.elements[list_any_id] = response.json()
        return self.elements[list_any_id]

    async def deprecate_entries(self, list_id: str, entriesIds: list[str]) -> None:
        # https://base.zenkit.com/docs/api/entries/post-api-v1-lists-listid-entries-delete-filter
        url = f"{API_URL}/lists/{list_id}/entries/delete/filter"
        listEntryIds = []

        for id in entriesIds:
            try:
                entry = await self.get_list_entry(list_id, id)
            except Exception as error:
                _LOGGER.error("Failed to fetch list entry: %s", id)
                continue
            listEntryIds.append(entry["id"])

        data = {
            "listEntryIds": listEntryIds,
        }
        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=data
        )

        if response.status_code != 200:
            _log_error(response, "Failed to delete entries in list %s", list_id)
            raise Exception("Error deleting list entries %s" % entriesIds)

        return response.raise_for_status()
