"""Tests for the Zenkit config entry setup."""

from unittest.mock import MagicMock

from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zenkit import (
    _register_devices,
    _set_unique_id,
    async_remove_config_entry_device,
)
from custom_components.zenkit.const import DOMAIN
from custom_components.zenkit.coordinator import ZenkitDataUpdateCoordinator


async def test_sets_unique_id_of_old_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)

    _set_unique_id(hass, entry, "906842")

    assert entry.unique_id == "906842"


async def test_keeps_existing_unique_id(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="1", version=2)
    entry.add_to_hass(hass)

    _set_unique_id(hass, entry, "906842")

    assert entry.unique_id == "1"


async def test_duplicate_account_keeps_no_unique_id(hass):
    MockConfigEntry(domain=DOMAIN, unique_id="906842", version=2).add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)

    _set_unique_id(hass, entry, "906842")

    assert entry.unique_id is None


def _coordinator(hass, entry_id, lists=()):
    coordinator = ZenkitDataUpdateCoordinator(
        hass, MagicMock(), {"id": 906842, "username": "u"}, entry_id
    )
    coordinator.user["organizationId"] = 560986
    coordinator.organization = {"name": "Org"}
    coordinator._lists = list(lists)
    return coordinator


def _device(hass, entry, identifier):
    return dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_{identifier}"), entry.entry_id
    )


async def test_registers_account_and_organization_devices(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    coordinator = _coordinator(hass, entry.entry_id)

    _register_devices(hass, entry, coordinator)

    account = _device(hass, entry, "account_906842")
    organization = _device(hass, entry, "organization_560986")
    assert account.name == "u"
    assert coordinator.account_device_id == account.id
    assert organization.name == "Org"
    assert organization.via_device_id == account.id


async def test_migrates_old_device_to_account_device(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    old = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "906842")}, name="u"
    )
    registry.async_update_device(old.id, area_id="office")

    _register_devices(hass, entry, _coordinator(hass, entry.entry_id))

    device = registry.async_get(old.id)
    assert device.identifiers == {(DOMAIN, f"{entry.entry_id}_account_906842")}
    assert device.area_id == "office"
    assert len(dr.async_entries_for_config_entry(registry, entry.entry_id)) == 2


async def test_account_configured_twice_gets_two_account_devices(hass):
    registry = dr.async_get(hass)
    entries = [MockConfigEntry(domain=DOMAIN, version=2) for _ in range(2)]
    for entry in entries:
        entry.add_to_hass(hass)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={(DOMAIN, "906842")}
        )

    for entry in entries:
        _register_devices(hass, entry, _coordinator(hass, entry.entry_id))

    for entry in entries:
        assert _device(hass, entry, "account_906842") is not None
        assert len(dr.async_entries_for_config_entry(registry, entry.entry_id)) == 2


async def test_old_device_removed_if_account_device_exists(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_account_906842")},
    )
    old = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "906842")}
    )

    _register_devices(hass, entry, _coordinator(hass, entry.entry_id))

    assert registry.async_get(old.id) is None


async def test_only_stale_devices_can_be_removed(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    coordinator = _coordinator(
        hass, entry.entry_id, [{"uuid": "u", "shortId": "a", "name": "A"}]
    )
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    registry = dr.async_get(hass)

    def device(identifier):
        return registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{identifier}")},
        )

    for identifier in ("account_906842", "organization_560986", "list_u"):
        assert not await async_remove_config_entry_device(
            hass, entry, device(identifier)
        )
    assert await async_remove_config_entry_device(hass, entry, device("list_gone"))
