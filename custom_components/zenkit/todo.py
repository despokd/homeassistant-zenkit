"""A todo platform for Zenkit."""

import logging
import datetime
import uuid

from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DUE_DATE_FORMAT, COMPLETED_COLOR
from .coordinator import ZenkitDataUpdateCoordinator
from .elements import due_element, notes_element, stage_element, status_option

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up the Zenkit todo platform config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    lists = await coordinator.zk.get_lists()
    if lists is None:
        _LOGGER.warning("No lists found")
        return False

    listEntities = []
    for list in lists:
        listId = list["id"]
        listShortId = list["shortId"]

        listEntities.append(
            ZenkitTodoListEntity(
                coordinator,
                listId,
                listShortId,
                list["uuid"],
                list["name"],
                _list_icon(list),
            )
        )

    async_add_entities(listEntities)

    if not listEntities:
        _LOGGER.warning("No lists added")
        return False

    return True


def _list_icon(list: dict[str, Any]) -> str | None:
    """Get the icon of by icon class field. (Font Awesome)"""
    if "iconClassNames" not in list:
        return None

    class_name = list["iconClassNames"]
    if class_name is None:
        return None
    if "plane" in class_name:
        return "mdi:airplane"
    if "tree" in class_name:
        return "mdi:pine-tree"
    if "graduation-cap" in class_name:
        return "mdi:school"

    # try to remove font awesome prefixes
    class_name = (
        class_name.replace("fa-", "")
        .replace("fas-", "")
        .replace("far-", "")
        .replace("fal-", "")
        .replace("fab-", "")
    )
    class_name = (
        class_name.replace("fa ", "")
        .replace("fas ", "")
        .replace("far ", "")
        .replace("fal ", "")
        .replace("fab ", "")
    )

    # TODO test if icon exists

    return f"mdi:{class_name}"


def _completion_status(
    item: dict[str, Any], elements: list[dict] | None = None
) -> TodoItemStatus:
    """Get the state of an entry by its status field."""
    stage = stage_element(elements) if elements else None
    done = status_option(stage, True) if stage else None
    if done is not None and f"{stage['uuid']}_categories" in item:
        if done["id"] in (item[f"{stage['uuid']}_categories"] or []):
            return TodoItemStatus.COMPLETED
        return TodoItemStatus.NEEDS_ACTION

    # Fallback without known fields: "done" colored option in any status field
    """
    Example completion status field, name is translated
    "fd3bb8c3-07a5-424f-9bb0-82ab022f2e24_categories_sort": [
        {
            "id": 12691260,
            "uuid": "9b30d1a2-6951-4e83-ab5f-46626ee8d53e",
            "name": "Completed",
            "colorHex": "#3ba744"
        }
    ],
    """
    for f, field in item.items():
        if f.endswith("_categories_sort"):
            for category in field:
                if category["colorHex"] == COMPLETED_COLOR:
                    return TodoItemStatus.COMPLETED
    return TodoItemStatus.NEEDS_ACTION


def _description(
    item: dict[str, Any], elements: list[dict] | None = None
) -> str | None:
    """Get the description of an entry by its notes field."""
    notes = notes_element(elements) if elements else None
    if notes is not None:
        # Zenkit returns "" for a cleared text
        return item.get(f"{notes['uuid']}_text") or None

    # Fallback without known fields: first text field which is not the summary
    for f, field in item.items():
        if f.endswith("_text") and field != item["displayString"]:
            return field
    return None


def _due_date(
    item: dict[str, Any], elements: list[dict] | None = None
) -> datetime.date | datetime.datetime | None:
    """Get the due date of an entry by its due date field."""
    due = due_element(elements) if elements else None
    if due is not None:
        return _parse_due(item, due["uuid"])

    # Fallback without known fields: first date field which is set
    for f, field in item.items():
        if f.endswith("_date") and field is not None:
            parsed = _parse_due(item, f.removesuffix("_date"))
            if parsed is not None:
                return parsed
    return None


def _parse_due(
    item: dict[str, Any], uuid: str
) -> datetime.date | datetime.datetime | None:
    """Parse a date field, which has a time in UTC if `_hasTime` is set."""
    value = item.get(f"{uuid}_date")
    if value is None:
        return None
    try:
        if item.get(f"{uuid}_hasTime"):
            return dt_util.as_local(datetime.datetime.fromisoformat(value))
        return datetime.datetime.strptime(value[:10], DUE_DATE_FORMAT).date()
    except ValueError:
        _LOGGER.warning("Unable to parse due date %s", value)
    return None


class ZenkitTodoListEntity(
    CoordinatorEntity[ZenkitDataUpdateCoordinator], TodoListEntity
):
    """An Zenkit TodoListEntity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        coordinator: ZenkitDataUpdateCoordinator,
        list_id: str,
        list_short_id: str,
        list_uuid: str,
        list_name: str,
        icon: str | None = None,
    ) -> None:
        """Initialize TodoistTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self.list_id = list_id
        self.list_short_id = list_short_id
        self.list_uuid = list_uuid

        self._attr_unique_id = list_uuid
        self._attr_name = list_name
        self._attr_todo_items = None
        self._attr_icon = icon

        _LOGGER.debug("Created list %s (%s)", list_short_id, list_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        items = []
        elements = self._elements
        list_entries = self.coordinator.data.get(self.list_short_id, [])
        for entry in list_entries:
            status = _completion_status(entry, elements)
            # skip completed items
            if status == TodoItemStatus.COMPLETED:
                continue

            items.append(
                TodoItem(
                    uid=entry["uuid"],
                    summary=entry["displayString"],
                    status=status,
                    description=_description(entry, elements),
                    due=_due_date(entry, elements),
                )
            )
        self._attr_todo_items = list(items)

        super()._handle_coordinator_update()
        _LOGGER.debug(
            "Updated list %s (%s) with %s items",
            self.list_short_id,
            self.name,
            len(self._attr_todo_items),
        )

    @property
    def _elements(self) -> list[dict] | None:
        """Fields of the list, None until fetched."""
        return self.coordinator.zk.elements.get(self.list_short_id)

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        uid = str(uuid.uuid4())
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        fields = {"name": item.summary}
        # Only send what is set, lists may lack a description or due date field
        if item.description:
            fields["description"] = item.description
        if item.due is not None:
            fields["due"] = item.due
        await self.coordinator.zk.create_entry(self.list_short_id, uid, **fields)
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        # HA passes the whole item, so only send fields which changed
        entry = next(
            (
                entry
                for entry in self.coordinator.data.get(self.list_short_id, [])
                if entry["uuid"] == item.uid
            ),
            None,
        )
        elements = self._elements
        changes = {}
        if entry is None or item.summary != entry["displayString"]:
            changes["name"] = item.summary
        if entry is None or item.status != _completion_status(entry, elements):
            changes["completed"] = item.status == TodoItemStatus.COMPLETED
        description = _description(entry, elements) if entry else None
        if (item.description or None) != description:
            changes["description"] = item.description
        due = _due_date(entry, elements) if entry else None
        if item.due != due:
            changes["due"] = item.due
        if not changes:
            return

        try:
            await self.coordinator.zk.update_entry(
                self.list_short_id, item.uid, **changes
            )
        except Exception as error:
            _LOGGER.error("Error updating todo item: %s", item.uid, exc_info=error)
            raise error

        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item. Which is a deprecation at zenkit before complete deletion."""
        try:
            await self.coordinator.zk.deprecate_entries(self.list_id, uids)
        except Exception as error:
            _LOGGER.error("Error deleting todo items: %s", uids, exc_info=error)
            raise error
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
