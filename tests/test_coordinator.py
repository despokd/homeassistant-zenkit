"""Tests for the Zenkit coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.zenkit.const import DOMAIN
from custom_components.zenkit.coordinator import ZenkitDataUpdateCoordinator
from custom_components.zenkit.exceptions import UpdateFailedException

LISTS = [{"shortId": "a", "name": "A"}, {"shortId": "b", "name": "B"}]
USER = {
    "id": 906842,
    "username": "user",
    "displayname": "User Name",
    "organizationId": 560986,
}
ORGANIZATION = {"id": 560986, "name": "Org", "planId": "free"}


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
    zk.get_unread_notifications_count = AsyncMock(return_value=2)
    zk.login = AsyncMock(return_value=USER)
    zk.get_organization = AsyncMock(return_value=ORGANIZATION)
    zk.get_organization_members_count = AsyncMock(return_value=2)
    return ZenkitDataUpdateCoordinator(
        hass, zk, USER, MockConfigEntry(domain=DOMAIN, entry_id="entry")
    )


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


async def test_force_refresh_refetches_fields(coordinator):
    coordinator.zk.get_list_elements = AsyncMock()

    await coordinator.async_force_refresh()

    assert coordinator.zk.get_list_elements.await_count == 2
    assert coordinator.data == {"a": [{"uuid": "a1"}], "b": [{"uuid": "b1"}]}


async def test_update_fetches_unread_notifications(coordinator):
    await coordinator._async_update_data()

    assert coordinator.unread_notifications == 2


async def test_failing_notifications_do_not_fail_update(coordinator):
    coordinator.unread_notifications = 2
    coordinator.zk.get_unread_notifications_count.side_effect = UpdateFailedException(
        "down"
    )

    data = await coordinator._async_update_data()

    assert data == {"a": [{"uuid": "a1"}], "b": [{"uuid": "b1"}]}
    assert coordinator.unread_notifications is None


def test_device_info_is_the_account(coordinator):
    info = coordinator.device_info

    assert info["identifiers"] == {(DOMAIN, "entry_account_906842")}
    assert info["name"] == "User Name"
    assert info["model"] == "account"
    assert info["entry_type"] == DeviceEntryType.SERVICE


def test_device_models_are_translated(coordinator):
    coordinator.models = {"account": "Konto", "project": "Projekt", "list": "Liste"}
    project = {"uuid": "u", "shortId": "a", "name": "A", "resourceType": "project"}
    unknown = {"uuid": "u", "shortId": "a", "name": "A", "resourceType": "other"}

    assert coordinator.device_info["model"] == "Konto"
    assert coordinator.list_device_info(project)["model"] == "Projekt"
    assert coordinator.list_device_info(unknown)["model"] == "Liste"


def test_organization_device_info(coordinator):
    coordinator.account_device_id = "account-device"
    coordinator.organization = {"name": "Org"}
    info = coordinator.organization_device_info

    assert info["identifiers"] == {(DOMAIN, "entry_organization_560986")}
    assert info["name"] == "Org"
    assert info["translation_key"] is None
    assert info["via_device_id"] == "account-device"


def test_unknown_organization_has_translated_name(coordinator):
    info = coordinator.organization_device_info

    assert info["name"] is None
    assert info["translation_key"] == "organization"


def test_no_organization_device_without_organization(coordinator):
    coordinator.user = {"id": 1, "username": "user"}

    assert coordinator.organization_device_info is None


def test_list_device_info(coordinator):
    coordinator.account_device_id = "account-device"
    info = coordinator.list_device_info({"uuid": "u", "shortId": "a", "name": "A"})

    assert info["identifiers"] == {(DOMAIN, "entry_list_u")}
    assert info["name"] == "A"
    assert info["model"] == "list"
    # A device, the account and organization are services
    assert info["entry_type"] is None
    assert info["via_device_id"] == "account-device"


def test_device_identifiers_scoped_to_entry(hass, coordinator):
    coordinator._lists = [{"uuid": "u", "shortId": "a", "name": "A"}]
    other = ZenkitDataUpdateCoordinator(
        hass, coordinator.zk, USER, MockConfigEntry(domain=DOMAIN, entry_id="other")
    )
    other._lists = coordinator._lists

    assert coordinator.device_identifiers == {
        (DOMAIN, "entry_account_906842"),
        (DOMAIN, "entry_organization_560986"),
        (DOMAIN, "entry_list_u"),
    }
    assert not coordinator.device_identifiers & other.device_identifiers


def test_device_info_falls_back_to_username(coordinator):
    coordinator.user = {"id": 1, "username": "user", "displayname": ""}

    assert coordinator.device_info["name"] == "user"


def test_no_device_info_without_user(hass):
    assert ZenkitDataUpdateCoordinator(hass, MagicMock()).device_info is None


async def test_first_update_fetches_account_and_organization(coordinator):
    await coordinator._async_update_data()

    coordinator.zk.get_organization.assert_awaited_once_with(560986)
    coordinator.zk.get_organization_members_count.assert_awaited_once_with(560986)
    assert coordinator.organization == ORGANIZATION
    assert coordinator.organization_members == 2


async def test_account_is_not_refetched_within_interval(coordinator):
    await coordinator._async_update_data()
    coordinator.zk.login = AsyncMock(return_value={**USER, "username": "new"})

    await coordinator._async_update_data()

    coordinator.zk.login.assert_not_awaited()
    assert coordinator.user == USER


async def test_account_is_refetched_after_interval(coordinator, freezer):
    await coordinator._async_update_data()
    coordinator.zk.login = AsyncMock(return_value={**USER, "username": "new"})
    freezer.tick(3600)

    await coordinator._async_update_data()

    assert coordinator.user["username"] == "new"


async def test_failed_account_fetch_keeps_last_data(coordinator):
    coordinator.zk.get_organization.side_effect = UpdateFailedException("down")

    await coordinator._async_update_data()

    assert coordinator.user == USER
    assert coordinator.organization is None


async def test_force_refresh_refetches_account(coordinator):
    coordinator.zk.get_list_elements = AsyncMock()
    coordinator.zk.login = AsyncMock(return_value={**USER, "username": "new"})

    await coordinator.async_force_refresh()

    assert coordinator.user["username"] == "new"


def test_lists_before_fetch(hass):
    assert ZenkitDataUpdateCoordinator(hass, MagicMock()).lists == []


def test_no_link_before_account_device_is_registered(coordinator):
    info = coordinator.list_device_info({"uuid": "u", "shortId": "a", "name": "A"})

    assert "via_device_id" not in info


async def test_lists_are_not_refetched_within_interval(coordinator):
    await coordinator._async_update_data()

    await coordinator._async_update_data()

    coordinator.zk.get_lists.assert_awaited_once()


async def test_lists_are_refetched_after_interval(coordinator, entries, freezer):
    await coordinator._async_update_data()
    coordinator.zk.get_lists.return_value = [*LISTS, {"shortId": "c", "name": "C"}]
    entries["c"] = [{"uuid": "c1"}]
    coordinator.zk.elements["c"] = []
    freezer.tick(3600)

    data = await coordinator._async_update_data()

    assert [list["shortId"] for list in coordinator.lists] == ["a", "b", "c"]
    assert data["c"] == [{"uuid": "c1"}]


async def test_force_refresh_refetches_lists(coordinator):
    coordinator.zk.get_list_elements = AsyncMock()
    await coordinator._async_update_data()

    await coordinator.async_force_refresh()

    assert coordinator.zk.get_lists.await_count == 2


async def test_removed_list_is_forgotten(coordinator, entries, freezer):
    entries["b"] = UpdateFailedException("down")
    await coordinator._async_update_data()
    coordinator.zk.get_lists.return_value = LISTS[:1]
    freezer.tick(3600)

    data = await coordinator._async_update_data()

    assert data == {"a": [{"uuid": "a1"}]}
    assert coordinator.get_list("b") is None
    assert "b" not in coordinator.zk.elements
    assert coordinator.failed_lists == set()


async def test_failed_list_fetch_keeps_lists_and_retries(coordinator, freezer):
    await coordinator._async_update_data()
    coordinator.zk.get_lists.side_effect = UpdateFailedException("down")
    freezer.tick(3600)

    data = await coordinator._async_update_data()
    await coordinator._async_update_data()

    assert coordinator.lists == LISTS
    assert data == {"a": [{"uuid": "a1"}], "b": [{"uuid": "b1"}]}
    assert coordinator.zk.get_lists.await_count == 3


async def test_first_failed_list_fetch_fails_update(coordinator):
    coordinator.zk.get_lists.side_effect = UpdateFailedException("down")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


def test_get_list(coordinator):
    coordinator._lists = LISTS

    assert coordinator.get_list("b") == LISTS[1]
    assert coordinator.get_list("gone") is None
