"""The Zenkit api."""

import requests  # type: ignore
import asyncio
import logging

from .const import API_URL, ENTRIES_LIMIT, COMPLETED_COLOR
from .exceptions import CannotLoginException, UpdateFailedException

_LOGGER = logging.getLogger(__name__)

CATEGORIES_ELEMENT = 6


def _stage_element(elements: list[dict]) -> dict | None:
    """Get the status element of a list, see docs/zenkit/zenkit-todo.md."""
    for element in elements:
        if element.get("resourceRole") == "stage":
            return element
    # Fallback for lists without roles: categories element with a "done" colored option
    for element in elements:
        if element.get("elementcategory") == CATEGORIES_ELEMENT and any(
            option.get("colorHex") == COMPLETED_COLOR
            for option in _status_options(element)
        ):
            return element
    return None


def _status_options(element: dict) -> list[dict]:
    """Get the selectable options of a categories element."""
    return (element.get("elementData") or {}).get("predefinedCategories") or []


def _status_option(element: dict, completed: bool) -> dict | None:
    """Get the option for the completed or open status of a status element."""
    options = _status_options(element)
    role = "done" if completed else "todo"
    for option in options:
        if option.get("resourceRole") == role:
            return option
    if completed:
        for option in options:
            if option.get("colorHex") == COMPLETED_COLOR:
                return option
    return None


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

    async def login(self) -> dict:
        """Login to the Zenkit API."""
        # https://base.zenkit.com/docs/api/overview/authentication
        url = f"{API_URL}/auth/currentuser"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)

        if type(response.json()) is not dict or response.json().get("username") is None:
            raise CannotLoginException

        return response.json()

    async def get_lists(self) -> dict:
        """Get lists."""
        # https://base.zenkit.com/docs/api/workspaces/get-api-v1-users-me-workspaceswithlists
        url = f"{API_URL}/users/me/workspacesWithLists"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        workspaces = response.json()
        lists = []
        for workspace in workspaces:
            for list in workspace["lists"]:
                lists.append(list)
        return lists

    async def get_list_entries(self, list_short_id: str, count=0) -> dict:
        """Get list entries."""
        # https://base.zenkit.com/docs/api/entries/post-api-v1-lists-listshortid-entries-filter-list
        url = f"{API_URL}/lists/{list_short_id}/entries/filter/list"
        data = {
            "filter": {},
            "groupByElementId": 0,
            "limit": ENTRIES_LIMIT,
            "skip": count,
            "exclude": [],
            "allowDeprecated": False,
            "taskStyle": False,
        }
        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=data
        )

        if response.status_code != 200:
            _LOGGER.error(response.json())
            raise UpdateFailedException
        elif (
            response.json()["listEntries"] is None
            or response.json()["countData"]["filteredTotal"] == 0
        ):
            return []
        elif response.json()["countData"]["filteredTotal"] > count + ENTRIES_LIMIT:
            return response.json()["listEntries"] + await self.get_list_entries(
                list_short_id, count + ENTRIES_LIMIT
            )

        return response.json()["listEntries"]

    async def get_list_entry(self, list_any_id: str, entry_id: str) -> dict:
        """Get list entry."""
        # https://base.zenkit.com/docs/api/entries/get-api-v1-lists-listallid-entries-listentryallid
        url = f"{API_URL}/lists/{list_any_id}/entries/{entry_id}"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        if response.status_code != 200:
            _LOGGER.error(response.json())
            raise UpdateFailedException

        return response.json()

    async def create_entry(self, list_short_id: str, entry_id: str, **kwargs) -> None:
        """Add an entry to a list."""
        # https://base.zenkit.com/docs/api/entries/post-api-v1-lists-listid-entries
        url = f"{API_URL}/lists/{list_short_id}/entries"
        data = {
            "uuid": entry_id,
        }
        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=data
        )

        if response.status_code != 200:
            _LOGGER.error(response.json())
            raise Exception("Error creating list entry")

        # Add data like name to the entry
        try:
            response = await self.update_entry(list_short_id, entry_id, **kwargs)
        except Exception as error:
            raise UpdateFailedException(
                "Failed to add data to list entry: %s" % entry_id
            ) from error

    async def update_entry(self, list_short_id: str, entry_id: str, **kwargs) -> None:
        """Update an entry in a list."""
        try:
            entry = await self.get_list_entry(list_short_id, entry_id)
        except Exception as error:
            raise UpdateFailedException(
                "Failed to fetch list entry: %s" % entry_id
            ) from error

        unsupported = set(kwargs) - {"name", "completed"}
        if unsupported:
            # TODO implement description and due date (#9, #11)
            raise NotImplementedError(
                "Update of fields not implemented: %s" % ", ".join(sorted(unsupported))
            )

        update = {}
        if "name" in kwargs:
            for f, field in entry.items():
                if f.endswith("text") and (
                    field == entry["displayString"] or entry["displayString"] == None
                ):
                    update[f] = kwargs["name"]
                    break
        if "completed" in kwargs:
            update.update(await self._status_update(list_short_id, kwargs["completed"]))

        if not update:
            return None

        # https://base.zenkit.com/docs/api/entries/put-api-v1-lists-listid-entries-listentryid
        url = f"{API_URL}/lists/{list_short_id}/entries/{entry_id}"
        response = await asyncio.to_thread(
            requests.put, url, headers=self.headers, json=update
        )

        if response.status_code != 200:
            _LOGGER.error(response.json())
            raise Exception("Error updating list entry")

        return response.raise_for_status()

    async def get_list_elements(self, list_any_id: str) -> list[dict]:
        """Get the elements (fields) of a list."""
        # https://base.zenkit.com/docs/api/elements/get-api-v1-lists-listallid-elements
        url = f"{API_URL}/lists/{list_any_id}/elements"
        response = await asyncio.to_thread(requests.get, url, headers=self.headers)
        if response.status_code != 200:
            _LOGGER.error(response.json())
            raise UpdateFailedException

        return response.json()

    async def _status_update(self, list_short_id: str, completed: bool) -> dict:
        """Get the entry fields to set the completed or open status."""
        # Fetched on each status change, so renamed or added options are picked up
        elements = await self.get_list_elements(list_short_id)
        stage = _stage_element(elements)
        if stage is None:
            raise UpdateFailedException(
                "List %s has no status field to complete items" % list_short_id
            )

        option = _status_option(stage, completed)
        if option is None and completed:
            raise UpdateFailedException(
                "List %s has no done status option" % list_short_id
            )

        # Only `_categories` is writable, `_categories_sort` is ignored by Zenkit
        return {f"{stage['uuid']}_categories": [option["id"]] if option else []}

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
            _LOGGER.error(response.json())
            raise Exception("Error deleting list entries %s" % entriesIds)

        return response.raise_for_status()
