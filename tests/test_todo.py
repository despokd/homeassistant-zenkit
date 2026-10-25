"""Tests for the Zenkit todo entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.todo import TodoItem, TodoItemStatus

from custom_components.zenkit.todo import ZenkitTodoListEntity

STAGE = "stage-uuid"
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
    coordinator.zk.update_entry = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    return ZenkitTodoListEntity(coordinator, "1", "list", "list-uuid", "List")


def _item(summary="Buy milk", status=TodoItemStatus.NEEDS_ACTION):
    return TodoItem(uid="entry-uuid", summary=summary, status=status)


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
