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

from .const import DOMAIN, DUE_DATE_FORMAT
from .coordinator import ZenkitDataUpdateCoordinator

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


def _completion_status(item: dict[str, Any]) -> TodoItemStatus:
    """Get the state of by sort field item."""
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
                if category["colorHex"] == "#3ba744":
                    return TodoItemStatus.COMPLETED
    return TodoItemStatus.NEEDS_ACTION


def _description(item: dict[str, Any]) -> str | None:
    """Get the description of by text field."""
    # Zenkit does not have a description field, so we use the first text field ending with _text as key
    for f, field in item.items():
        if f.endswith("_text") and field != item["displayString"]:
            return field
    return None


def _due_date(item: dict[str, Any]) -> str | None:
    """Get the due date of by date field."""
    # Zenkit does not have a due date field, so we use the first date field ending with _date as key
    for f, field in item.items():
        if f.endswith("_date") and field is not None:
            try:
                due_datetime = datetime.datetime.strptime(field, DUE_DATE_FORMAT)
                return due_datetime.date()
            except ValueError:
                _LOGGER.warning("Unable to parse due date %s", field)
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
        list_entries = self.coordinator.data.get(self.list_short_id, [])
        for entry in list_entries:
            status = _completion_status(entry)
            # skip completed items
            if status == TodoItemStatus.COMPLETED:
                continue

            items.append(
                TodoItem(
                    uid=entry["uuid"],
                    summary=entry["displayString"],
                    status=status,
                    description=_description(entry),
                    due=_due_date(entry),
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

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        uid = str(uuid.uuid4())
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        await self.coordinator.zk.create_entry(
            self.list_short_id,
            uid,
            name=item.summary,
            description=item.description,
            completed=item.due,
        )
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        try:
            await self.coordinator.zk.update_entry(
                self.list_short_id,
                item.uid,
                name=item.summary,
                description=item.description,
                completed=item.status == TodoItemStatus.COMPLETED,
                due_date=item.due,
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
