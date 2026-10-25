"""Tests for the Zenkit coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.zenkit.coordinator import ZenkitDataUpdateCoordinator
from custom_components.zenkit.exceptions import UpdateFailedException

LISTS = [{"shortId": "a", "name": "A"}, {"shortId": "b", "name": "B"}]


@pytest.fixture
def entries():
    """Entries per list, an exception makes that list fail."""
    return {"a": [{"uuid": "a1"}], "b": [{"uuid": "b1"}]}


@pytest.fixture
def coordinator(hass, entries):
    """Coordinator with two lists whose fields are known."""

    async def get_list_entries(short_id):
        if isinstance(entries[short_id], Exception):
            raise entries[short_id]
        return entries[short_id]

    zk = MagicMock()
    zk.elements = {"a": [], "b": []}
    zk.get_lists = AsyncMock(return_value=LISTS)
    zk.get_list_entries = AsyncMock(side_effect=get_list_entries)
    return ZenkitDataUpdateCoordinator(hass, zk)


async def test_update_fetches_all_lists(coordinator):
    data = await coordinator._async_update_data()

    assert data == {"a": [{"uuid": "a1"}], "b": [{"uuid": "b1"}]}
    assert coordinator.failed_lists == set()


async def test_failing_list_does_not_fail_others(coordinator, entries):
    entries["a"] = UpdateFailedException("page 8")

    data = await coordinator._async_update_data()

    assert data == {"b": [{"uuid": "b1"}]}
    assert coordinator.failed_lists == {"a"}


async def test_failed_list_recovers(coordinator, entries):
    entries["a"] = UpdateFailedException("page 8")
    await coordinator._async_update_data()
    entries["a"] = [{"uuid": "a2"}]

    data = await coordinator._async_update_data()

    assert data["a"] == [{"uuid": "a2"}]
    assert coordinator.failed_lists == set()


async def test_all_lists_failing_fails_update(coordinator, entries):
    entries["a"] = entries["b"] = UpdateFailedException("down")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.failed_lists == {"a", "b"}


async def test_refresh_list_fetches_only_that_list(coordinator, entries):
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    coordinator.zk.get_list_entries.reset_mock()
    entries["a"] = [{"uuid": "a2"}]
    entries["b"] = [{"uuid": "b2"}]

    await coordinator.async_refresh_list("a")

    coordinator.zk.get_list_entries.assert_awaited_once_with("a")
    assert coordinator.data == {"a": [{"uuid": "a2"}], "b": [{"uuid": "b1"}]}


async def test_refresh_list_failure_marks_only_that_list(coordinator, entries):
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    entries["a"] = UpdateFailedException("page 8")

    await coordinator.async_refresh_list("a")

    assert coordinator.data == {"b": [{"uuid": "b1"}]}
    assert coordinator.failed_lists == {"a"}
    assert coordinator.last_update_success
