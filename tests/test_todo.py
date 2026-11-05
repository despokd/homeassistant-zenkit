"""Tests for the Zenkit todo entity."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.todo import TodoItem, TodoItemStatus
from homeassistant.exceptions import ServiceValidationError

from custom_components.zenkit.todo import (
    ITEM_DETAILS,
    ZenkitTodoListEntity,
    _item_details,
    _list_attributes,
)

STAGE = "stage-uuid"
NOTES = "notes-uuid"
DUE = "due-uuid"
ELEMENTS = [
    {"uuid": "title-uuid", "elementcategory": 1, "resourceRole": "title"},
    {"uuid": NOTES, "elementcategory": 1, "resourceRole": "notes"},
    {"uuid": DUE, "elementcategory": 4, "resourceRole": "dueDate"},
    {
        "uuid": STAGE,
        "elementcategory": 6,
        "resourceRole": "stage",
        "elementData": {
            "predefinedCategories": [
                {"id": 1, "resourceRole": "todo", "colorHex": "#0089d1"},
                {"id": 2, "resourceRole": "done", "colorHex": "#3ba744"},
            ]
        },
    },
]
DONE = {"id": 2, "uuid": "done-uuid", "name": "Erledigt", "colorHex": "#3ba744"}
OPEN = {"id": 1, "uuid": "todo-uuid", "name": "Zu bearbeiten", "colorHex": "#0089d1"}


@pytest.fixture
def entity():
    """Todo entity with one open entry in the coordinator data."""
    coordinator = MagicMock()
    coordinator.data = {
        "list": [
            {
                "uuid": "entry-uuid",
                "displayString": "Buy milk",
                f"{STAGE}_categories_sort": [OPEN],
            }
        ]
    }
    coordinator.zk.elements = {}
    coordinator.zk.update_entry = AsyncMock()
    coordinator.zk.create_entry = AsyncMock()
    coordinator.async_refresh_list = AsyncMock()
    coordinator.failed_lists = set()
    return ZenkitTodoListEntity(coordinator, "1", "list", "list-uuid", "List")


def _item(summary="Buy milk", status=TodoItemStatus.NEEDS_ACTION, **kwargs):
    return TodoItem(uid="entry-uuid", summary=summary, status=status, **kwargs)


@pytest.fixture
def entity_with_fields(entity):
    """Todo entity whose list fields are known."""
    entity.coordinator.zk.elements = {"list": ELEMENTS}
    entity.coordinator.data["list"][0].update(
        {
            f"{STAGE}_categories": [1],
            f"{NOTES}_text": "2 liters",
            f"{DUE}_date": "2026-11-03",
            f"{DUE}_hasTime": False,
        }
    )
    return entity


def _kwargs(**kwargs):
    return {"description": "2 liters", "due": datetime.date(2026, 11, 3), **kwargs}


async def test_complete_item(entity):
    await entity.async_update_todo_item(_item(status=TodoItemStatus.COMPLETED))

    entity.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", completed=True
    )
    entity.coordinator.async_refresh_list.assert_awaited_once_with("list")


async def test_rename_item(entity):
    await entity.async_update_todo_item(_item(summary="Buy oat milk"))

    entity.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", name="Buy oat milk"
    )


async def test_unchanged_item_is_not_written(entity):
    await entity.async_update_todo_item(_item())

    entity.coordinator.zk.update_entry.assert_not_awaited()
    entity.coordinator.async_refresh_list.assert_not_awaited()


async def test_reopen_item(entity):
    entity.coordinator.data["list"][0][f"{STAGE}_categories_sort"] = [DONE]

    await entity.async_update_todo_item(_item())

    entity.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", completed=False
    )


async def test_change_description(entity_with_fields):
    await entity_with_fields.async_update_todo_item(
        _item(**_kwargs(description="3 liters"))
    )

    entity_with_fields.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", description="3 liters"
    )


async def test_clear_description(entity_with_fields):
    await entity_with_fields.async_update_todo_item(_item(**_kwargs(description=None)))

    entity_with_fields.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", description=None
    )


async def test_empty_description_equals_none(entity):
    await entity.async_update_todo_item(_item(description=""))

    entity.coordinator.zk.update_entry.assert_not_awaited()


async def test_change_due(entity_with_fields):
    due = datetime.datetime(2026, 11, 3, 14, 30, tzinfo=datetime.timezone.utc)

    await entity_with_fields.async_update_todo_item(_item(**_kwargs(due=due)))

    entity_with_fields.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", due=due
    )


async def test_unchanged_item_with_fields_is_not_written(entity_with_fields):
    await entity_with_fields.async_update_todo_item(_item(**_kwargs()))

    entity_with_fields.coordinator.zk.update_entry.assert_not_awaited()


async def test_due_with_time_is_read_as_datetime(entity_with_fields):
    entry = entity_with_fields.coordinator.data["list"][0]
    entry[f"{DUE}_date"] = "2026-11-03T14:30:00.000Z"
    entry[f"{DUE}_hasTime"] = True
    due = datetime.datetime(2026, 11, 3, 14, 30, tzinfo=datetime.timezone.utc)

    await entity_with_fields.async_update_todo_item(_item(**_kwargs(due=due)))

    entity_with_fields.coordinator.zk.update_entry.assert_not_awaited()


async def test_status_is_read_by_role(entity_with_fields):
    # A done colored option without the done role is not completed
    entry = entity_with_fields.coordinator.data["list"][0]
    entry[f"{STAGE}_categories_sort"] = [DONE]

    await entity_with_fields.async_update_todo_item(_item(**_kwargs()))

    entity_with_fields.coordinator.zk.update_entry.assert_not_awaited()


@pytest.fixture
def entity_without_status(entity):
    """Todo entity whose list has no status field."""
    entity.coordinator.zk.elements = {"list": ELEMENTS[:3]}
    return entity


def _items(entity):
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    return entity.todo_items


def test_items_without_status_field_have_no_status(entity_without_status):
    assert [item.status for item in _items(entity_without_status)] == [None]


def test_items_without_done_option_have_no_status(entity):
    stage = {**ELEMENTS[3], "elementData": {"predefinedCategories": [{"id": 1}]}}
    entity.coordinator.zk.elements = {"list": [*ELEMENTS[:3], stage]}

    assert [item.status for item in _items(entity)] == [None]


def test_items_with_status_field_have_status(entity_with_fields):
    assert [item.status for item in _items(entity_with_fields)] == [
        TodoItemStatus.NEEDS_ACTION
    ]


async def test_unchanged_item_without_status_field_is_not_written(
    entity_without_status,
):
    await entity_without_status.async_update_todo_item(_item(status=None))

    entity_without_status.coordinator.zk.update_entry.assert_not_awaited()


async def test_open_item_without_status_field_is_not_written(entity_without_status):
    # The indeterminate checkbox of an item without status sends needs_action
    await entity_without_status.async_update_todo_item(_item())

    entity_without_status.coordinator.zk.update_entry.assert_not_awaited()


async def test_complete_item_without_status_field_fails(entity_without_status):
    with pytest.raises(ServiceValidationError):
        await entity_without_status.async_update_todo_item(
            _item(status=TodoItemStatus.COMPLETED)
        )

    entity_without_status.coordinator.zk.update_entry.assert_not_awaited()


async def test_rename_item_without_status_field(entity_without_status):
    await entity_without_status.async_update_todo_item(
        _item(summary="Buy oat milk", status=None)
    )

    entity_without_status.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", name="Buy oat milk"
    )


async def test_create_item_with_fields(entity):
    await entity.async_create_todo_item(
        TodoItem(summary="Buy milk", status=TodoItemStatus.NEEDS_ACTION, **_kwargs())
    )

    _, _, kwargs = entity.coordinator.zk.create_entry.mock_calls[0]
    assert kwargs == {"name": "Buy milk", **_kwargs()}
    entity.coordinator.async_refresh_list.assert_awaited_once_with("list")


async def test_create_item_without_fields_sends_only_name(entity):
    await entity.async_create_todo_item(
        TodoItem(summary="Buy milk", status=TodoItemStatus.NEEDS_ACTION)
    )

    _, _, kwargs = entity.coordinator.zk.create_entry.mock_calls[0]
    assert kwargs == {"name": "Buy milk"}


def test_available_while_list_loads(entity):
    assert entity.available


def test_unavailable_when_only_this_list_failed(entity):
    entity.coordinator.failed_lists = {"list"}

    assert not entity.available


def test_entity_belongs_to_list_device(entity):
    assert entity.name is None
    assert entity.device_info is entity.coordinator.list_device_info.return_value
    entity.coordinator.list_device_info.assert_called_with(
        {"uuid": "list-uuid", "shortId": "list", "name": "List"}
    )


def test_attributes():
    attributes = {
        "workspace": "Home",
        "folder": "Beds",
        "folder_id": 3,
        "folder_path": ["Garden", "Beds"],
        "icon_color": "#ff0000",
    }

    entity = ZenkitTodoListEntity(
        MagicMock(), "1", "list", "list-uuid", "List", attributes=attributes
    )

    assert entity.extra_state_attributes == attributes


def test_list_attributes():
    list = {
        "description": "Weekly shopping",
        "iconClassNames": "fa-shopping-cart",
        "iconColor": "#ffffff",
        "iconBackgroundColor": "#3ba744",
        "imageId": 123,
        "coverImageId": 456,
        "backgroundId": "bg1",
    }

    assert _list_attributes(list) == {
        "description": "Weekly shopping",
        "icon_class": "fa-shopping-cart",
        "icon_color": "#ffffff",
        "icon_background_color": "#3ba744",
        "image_id": 123,
        "cover_image_id": 456,
        "background_id": "bg1",
    }


def test_list_attributes_unset():
    list = {"description": "", "iconColor": None, "imageId": 0, "coverImageId": 0}

    assert set(_list_attributes(list).values()) == {None}


def test_no_folder_attributes_without_folder(entity):
    assert entity.extra_state_attributes == {}


SUBITEMS = "subitems-uuid"
DEPENDENCIES = "dependencies-uuid"
RELATION_ELEMENTS = [
    {"uuid": SUBITEMS, "elementcategory": 18, "resourceRole": "subtasks"},
    {"uuid": DEPENDENCIES, "elementcategory": 19, "resourceRole": "dependencies"},
    {"uuid": "hierarchy-uuid", "elementcategory": 17, "resourceRole": None},
]


def test_item_details():
    item = {
        f"{SUBITEMS}_parents": ["root-uuid", "parent-uuid"],
        f"{SUBITEMS}_references": ["child-uuid"],
        f"{DEPENDENCIES}_references": ["other-uuid"],
        "hierarchy-uuid_value": "1.2",
        "checklists": [
            {
                "name": "Packing",
                "uuid": "checklist-uuid",
                "items": [
                    {"text": "Tent", "checked": True},
                    {"text": "Stove", "checked": False},
                ],
                "shouldCheckedItemsBeHidden": False,
            }
        ],
    }

    assert _item_details(item, RELATION_ELEMENTS) == {
        "parent": "parent-uuid",
        "children": ["child-uuid"],
        "dependencies": ["other-uuid"],
        "hierarchy": "1.2",
        "checklists": [{"name": "Packing", "checked": 1, "total": 2}],
    }


def test_item_details_empty():
    item = {
        f"{SUBITEMS}_parents": [],
        f"{SUBITEMS}_references": [],
        f"{DEPENDENCIES}_references": [],
        "checklists": [],
    }

    assert _item_details(item, RELATION_ELEMENTS) == {}


def test_item_details_without_elements_has_checklists():
    item = {
        f"{SUBITEMS}_references": ["child-uuid"],
        "checklists": [{"name": "Checklist", "items": None}],
    }

    assert _item_details(item) == {
        "checklists": [{"name": "Checklist", "checked": 0, "total": 0}]
    }


def test_item_details_attribute(entity):
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    entity.coordinator.zk.elements = {"list": RELATION_ELEMENTS}
    entry = entity.coordinator.data["list"][0]
    entry[f"{DEPENDENCIES}_references"] = ["other-uuid"]

    entity._handle_coordinator_update()
    assert entity.extra_state_attributes == {
        ITEM_DETAILS: {"entry-uuid": {"dependencies": ["other-uuid"]}}
    }

    entry[f"{DEPENDENCIES}_references"] = []
    entity._handle_coordinator_update()
    assert entity.extra_state_attributes == {}
