"""Tests for the Zenkit todo entity."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.todo import TodoItem, TodoItemStatus

from custom_components.zenkit.todo import ZenkitTodoListEntity

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
    coordinator.async_refresh = AsyncMock()
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
    entity.coordinator.async_refresh.assert_awaited_once()


async def test_rename_item(entity):
    await entity.async_update_todo_item(_item(summary="Buy oat milk"))

    entity.coordinator.zk.update_entry.assert_awaited_once_with(
        "list", "entry-uuid", name="Buy oat milk"
    )


async def test_unchanged_item_is_not_written(entity):
    await entity.async_update_todo_item(_item())

    entity.coordinator.zk.update_entry.assert_not_awaited()
    entity.coordinator.async_refresh.assert_not_awaited()


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


async def test_create_item_with_fields(entity):
    await entity.async_create_todo_item(
        TodoItem(summary="Buy milk", status=TodoItemStatus.NEEDS_ACTION, **_kwargs())
    )

    _, _, kwargs = entity.coordinator.zk.create_entry.mock_calls[0]
    assert kwargs == {"name": "Buy milk", **_kwargs()}
    entity.coordinator.async_refresh.assert_awaited_once()


async def test_create_item_without_fields_sends_only_name(entity):
    await entity.async_create_todo_item(
        TodoItem(summary="Buy milk", status=TodoItemStatus.NEEDS_ACTION)
    )

    _, _, kwargs = entity.coordinator.zk.create_entry.mock_calls[0]
    assert kwargs == {"name": "Buy milk"}
