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
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DUE_DATE_FORMAT, COMPLETED_COLOR
from .coordinator import ZenkitConfigEntry, ZenkitDataUpdateCoordinator
from .entity import async_add_list_entities
from .elements import (
    dependencies_element,
    due_element,
    hierarchy_element,
    notes_element,
    stage_element,
    status_option,
    subentries_element,
)

_LOGGER = logging.getLogger(__name__)

# Sub-items, dependencies and checklists per item uid, see _item_details
ITEM_DETAILS = "item_details"
# Name of a checklist created by zenkit.create_entry, as Zenkit names new ones
DEFAULT_CHECKLIST_NAME = "Checklist"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZenkitConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zenkit todo platform config entry."""
    coordinator = entry.runtime_data
    async_add_list_entities(
        coordinator,
        entry,
        async_add_entities,
        lambda zenkit_list: [
            ZenkitTodoListEntity(
                coordinator,
                zenkit_list["id"],
                zenkit_list["shortId"],
                zenkit_list["uuid"],
                zenkit_list["name"],
                _list_icon(zenkit_list),
                _all_list_attributes(zenkit_list),
                resource_type=zenkit_list.get("resourceType"),
            )
        ],
    )


def _all_list_attributes(zenkit_list: dict[str, Any]) -> dict[str, Any]:
    """Get the folder path and appearance of a list."""
    return {**(zenkit_list.get("_folder") or {}), **_list_attributes(zenkit_list)}


def _list_attributes(list: dict[str, Any]) -> dict[str, Any]:
    """Get the appearance of a list in Zenkit, see docs/zenkit/lists.md."""
    return {
        # Zenkit returns "" for a cleared text
        "description": list.get("description") or None,
        "icon_class": list.get("iconClassNames") or None,
        "icon_color": list.get("iconColor") or None,
        "icon_background_color": list.get("iconBackgroundColor") or None,
        # File ids, the files need the API key (docs/zenkit/lists.md#images)
        "image_id": list.get("imageId") or None,
        "cover_image_id": list.get("coverImageId") or None,
        "background_id": list.get("backgroundId") or None,
    }


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


def _supports_completion(elements: list[dict] | None) -> bool:
    """Whether a list has a status field with a done option, assumed until fetched."""
    if elements is None:
        return True
    stage = stage_element(elements)
    return stage is not None and status_option(stage, True) is not None


def _completion_status(
    item: dict[str, Any], elements: list[dict] | None = None
) -> TodoItemStatus | None:
    """Get the state of an entry by its status field, None if the list has none."""
    if not _supports_completion(elements):
        return None
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


def _item_details(
    item: dict[str, Any], elements: list[dict] | None = None
) -> dict[str, Any]:
    """Get what a TodoItem can't hold, see docs/zenkit/zenkit-todo.md#sub-items."""
    details: dict[str, Any] = {}
    subentries = subentries_element(elements) if elements else None
    if subentries is not None:
        # Ancestors from the root, the last is the direct parent
        if parents := item.get(f"{subentries['uuid']}_parents"):
            details["parent"] = parents[-1]
        if children := item.get(f"{subentries['uuid']}_references"):
            details["children"] = children
    dependencies = dependencies_element(elements) if elements else None
    if dependencies is not None:
        if references := item.get(f"{dependencies['uuid']}_references"):
            details["dependencies"] = references
    hierarchy = hierarchy_element(elements) if elements else None
    if hierarchy is not None:
        if value := item.get(f"{hierarchy['uuid']}_value"):
            details["hierarchy"] = value
    checklists = [
        {
            "name": checklist.get("name"),
            "checked": sum(1 for i in checklist.get("items") or [] if i.get("checked")),
            "total": len(checklist.get("items") or []),
        }
        for checklist in item.get("checklists") or []
    ]
    if checklists:
        details["checklists"] = checklists
    return details


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
    # Only for the attribute names, the name is the device name
    _attr_translation_key = "list"
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
        attributes: dict[str, Any] | None = None,
        resource_type: str | None = None,
    ) -> None:
        """Initialize TodoistTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self.list_id = list_id
        self.list_short_id = list_short_id
        self.list_uuid = list_uuid
        self.list_name = list_name

        # Scoped to the entry, accounts sharing a workspace see the same list uuid
        self._attr_unique_id = f"{coordinator.entry_id}_{list_uuid}"
        # The main entity of the list device, named after it
        self._attr_name = None
        self._attr_todo_items = None
        self._attr_icon = icon
        self._attr_device_info = coordinator.list_device_info(
            {
                "uuid": list_uuid,
                "shortId": list_short_id,
                "name": list_name,
                "resourceType": resource_type,
            }
        )
        # Folder path and appearance, see docs/user/configuration.md
        self._attr_extra_state_attributes = dict(attributes or {})

        _LOGGER.debug("Created list %s (%s)", list_short_id, list_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if (zenkit_list := self.coordinator.get_list(self.list_short_id)) is not None:
            # Renamed or moved in Zenkit, the device is renamed in __init__.py
            self.list_name = zenkit_list["name"]
            self._attr_icon = _list_icon(zenkit_list)
            self._attr_extra_state_attributes = _all_list_attributes(zenkit_list)

        items = []
        details = {}
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
            if item_details := _item_details(entry, elements):
                details[entry["uuid"]] = item_details
        self._attr_todo_items = list(items)
        if details:
            self._attr_extra_state_attributes[ITEM_DETAILS] = details
        else:
            self._attr_extra_state_attributes.pop(ITEM_DETAILS, None)

        super()._handle_coordinator_update()
        _LOGGER.debug(
            "Updated list %s (%s) with %s items",
            self.list_short_id,
            self.list_name,
            len(self._attr_todo_items),
        )

    @property
    def available(self) -> bool:
        """Unavailable while only this list fails to load."""
        return (
            super().available
            and self.list_short_id not in self.coordinator.failed_lists
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
        await self.coordinator.async_refresh_list(self.list_short_id)

    async def async_create_entry(
        self,
        name: str,
        description: str | None = None,
        due_date: datetime.date | None = None,
        due_datetime: datetime.datetime | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
        checklist: list[str] | None = None,
        checklist_name: str | None = None,
    ) -> ServiceResponse:
        """Create an entry with more fields than a To-do item has (zenkit.create_entry)."""
        uid = str(uuid.uuid4())
        fields: dict[str, Any] = {"name": name}
        # Only send what is set, lists may lack these fields
        if description:
            fields["description"] = description
        if due_datetime is not None:
            # Without a time zone, the time is in the time zone of HA
            fields["due"] = dt_util.as_local(due_datetime)
        elif due_date is not None:
            fields["due"] = due_date
        if status:
            fields["status"] = status
        if labels:
            fields["labels"] = labels
        if assignees:
            fields["assignees"] = assignees
        if checklist:
            fields["checklist"] = {
                "name": checklist_name or DEFAULT_CHECKLIST_NAME,
                "items": checklist,
            }
        await self.coordinator.zk.create_entry(self.list_short_id, uid, **fields)
        await self.coordinator.async_refresh_list(self.list_short_id)
        return {"uid": uid}

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
            if _supports_completion(elements):
                changes["completed"] = item.status == TodoItemStatus.COMPLETED
            elif item.status == TodoItemStatus.COMPLETED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="no_status_field",
                    translation_placeholders={"list": self.list_name},
                )
            # Open on a list without status field, as the indeterminate checkbox sends
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

        await self.coordinator.async_refresh_list(self.list_short_id)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item. Which is a deprecation at zenkit before complete deletion."""
        try:
            await self.coordinator.zk.deprecate_entries(self.list_id, uids)
        except Exception as error:
            _LOGGER.error("Error deleting todo items: %s", uids, exc_info=error)
            raise error
        await self.coordinator.async_refresh_list(self.list_short_id)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
