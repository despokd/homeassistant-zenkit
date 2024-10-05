"""The Zenkit api."""

import requests  # type: ignore
import asyncio
import logging
from datetime import date

from .const import API_URL, ENTRIES_LIMIT, DUE_DATE_FORMAT
from .exceptions import CannotLoginException, UpdateFailedException

_LOGGER = logging.getLogger(__name__)


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

        update = {}
        if "name" in kwargs:
            for f, field in entry.items():
                if f.endswith("text") and (
                    field == entry["displayString"] or entry["displayString"] == None
                ):
                    update[f] = kwargs["name"]
                    break
        elif "description" in kwargs:
            # TODO implement
            raise NotImplementedError("Update description field not implemented")
            text_field_count = 0
            for f, field in entry.items():
                if f.endswith("_text"):
                    if text_field_count == 1:
                        update[f] = kwargs["description"]
                        break
                    text_field_count += 1
        elif "completed" in kwargs:
            # TODO implement
            raise NotImplementedError("Update completed field not implemented")
            pass
        elif "due_date" in kwargs:
            # TODO implement
            raise NotImplementedError("Update due date field not implemented")
            for f, field in entry.items():
                if f.endswith("_date") in f:
                    due_date = kwargs["due_date"]
                    if due_date == None:
                        break
                    update[f] = date.strftime(due_date, DUE_DATE_FORMAT)
                    break
        else:
            raise ValueError("Invalid update field")

        # https://base.zenkit.com/docs/api/entries/put-api-v1-lists-listid-entries-listentryid
        url = f"{API_URL}/lists/{list_short_id}/entries/{entry_id}"
        response = await asyncio.to_thread(
            requests.put, url, headers=self.headers, json=update
        )

        if response.status_code != 200:
            _LOGGER.error(response.json())
            raise Exception("Error updating list entry")

        return response.raise_for_status()

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
