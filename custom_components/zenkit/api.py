"""The Zenkit api."""

import requests  # type: ignore
import asyncio
import datetime
import logging

from .const import API_URL, ENTRIES_LIMIT, DUE_DATE_FORMAT, DUE_DATETIME_FORMAT
from .elements import (
    due_element,
    notes_element,
    stage_element,
    status_option,
    title_element,
)
from .exceptions import CannotLoginException, UpdateFailedException

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FIELDS = {"name", "completed", "description", "due"}


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
            _LOGGER.error(response.json())
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
            _LOGGER.error(response.json())
            raise Exception("Error deleting list entries %s" % entriesIds)

        return response.raise_for_status()
