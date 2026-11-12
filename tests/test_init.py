"""Tests for the Zenkit config entry setup."""

from unittest.mock import MagicMock

from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.zenkit import (
    _async_device_models,
    _register_devices,
    _set_unique_id,
    _update_list_devices,
    async_migrate_entry,
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


def _coordinator(hass, entry, lists=()):
    coordinator = ZenkitDataUpdateCoordinator(
        hass, MagicMock(), {"id": 906842, "username": "u"}, entry
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
    coordinator = _coordinator(hass, entry)

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

    _register_devices(hass, entry, _coordinator(hass, entry))

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
        _register_devices(hass, entry, _coordinator(hass, entry))

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

    _register_devices(hass, entry, _coordinator(hass, entry))

    assert registry.async_get(old.id) is None


async def test_only_stale_devices_can_be_removed(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    coordinator = _coordinator(
        hass, entry, [{"uuid": "u", "shortId": "a", "name": "A"}]
    )
    entry.runtime_data = coordinator
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


async def test_device_models_in_ha_language(hass):
    hass.config.language = "de"

    models = await _async_device_models(hass)

    assert models["account"] == "Konto"
    assert models["task_list"] == "Aufgabenliste"


async def test_device_of_removed_list_is_removed_with_entities(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    kept = {"uuid": "u", "shortId": "a", "name": "A"}
    gone = {"uuid": "gone", "shortId": "b", "name": "B"}
    coordinator = _coordinator(hass, entry, [kept, gone])
    _register_devices(hass, entry, coordinator)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    for zenkit_list in (kept, gone):
        device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            **coordinator.list_device_info(zenkit_list),
        )
        entities.async_get_or_create(
            "todo",
            DOMAIN,
            zenkit_list["uuid"],
            config_entry=entry,
            device_id=device.id,
        )
    coordinator._lists = [kept]

    _update_list_devices(hass, entry, coordinator)
    await hass.async_block_till_done()

    assert _device(hass, entry, "list_u") is not None
    assert _device(hass, entry, "list_gone") is None
    assert _device(hass, entry, "account_906842") is not None
    assert _device(hass, entry, "organization_560986") is not None
    assert entities.async_get_entity_id("todo", DOMAIN, "u") is not None
    assert entities.async_get_entity_id("todo", DOMAIN, "gone") is None


async def test_device_of_renamed_list_is_renamed(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    zenkit_list = {"uuid": "u", "shortId": "a", "name": "A"}
    coordinator = _coordinator(hass, entry, [zenkit_list])
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.list_device_info(zenkit_list)
    )
    devices.async_update_device(device.id, name_by_user="Mine")
    coordinator._lists = [
        {**zenkit_list, "name": "Groceries", "resourceType": "project"}
    ]

    _update_list_devices(hass, entry, coordinator)

    device = devices.async_get(device.id)
    assert device.name == "Groceries"
    assert device.model == "project"
    assert device.name_by_user == "Mine"


async def _migrate(hass, entry, entities):
    """Register entities of the entry with their old unique ids and migrate."""
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for platform, unique_id in entities:
        registry.async_get_or_create(
            platform,
            DOMAIN,
            unique_id,
            config_entry=entry,
            suggested_object_id=unique_id,
        )
    assert await async_migrate_entry(hass, entry)
    return registry


async def test_migrates_list_unique_ids(hass):
    entry = MockConfigEntry(domain=DOMAIN, entry_id="entry", version=2)
    entities = [
        ("todo", "list-uuid"),
        ("calendar", "list-uuid"),
        ("sensor", "list-uuid_open_entries"),
        ("sensor", "entry_username"),
        ("button", "entry_refresh"),
    ]

    registry = await _migrate(hass, entry, entities)

    assert {
        (e.domain, e.entity_id.split(".")[1], e.unique_id)
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    } == {
        ("todo", "list_uuid", "entry_list-uuid"),
        ("calendar", "list_uuid", "entry_list-uuid"),
        ("sensor", "list_uuid_open_entries", "entry_list-uuid_open_entries"),
        ("sensor", "entry_username", "entry_username"),
        ("button", "entry_refresh", "entry_refresh"),
    }
    assert (entry.version, entry.minor_version) == (2, 2)


async def test_migrates_version_1_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry",
        version=1,
        minor_version=1,
        data={"api_key": "key"},
    )

    registry = await _migrate(hass, entry, [("todo", "list-uuid")])

    assert entry.data == {"token": "key"}
    assert (entry.version, entry.minor_version) == (2, 2)
    assert registry.async_get_entity_id("todo", DOMAIN, "entry_list-uuid")


async def test_does_not_migrate_future_version(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=3)
    entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, entry)
