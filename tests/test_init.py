"""Tests for the Zenkit config entry setup."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zenkit import _set_unique_id
from custom_components.zenkit.const import DOMAIN


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
