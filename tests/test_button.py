"""Tests for the Zenkit refresh button."""

from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant.common import MockEntityPlatform

from custom_components.zenkit.button import ZenkitRefreshButton


async def test_press_forces_refresh():
    coordinator = MagicMock()
    coordinator.async_force_refresh = AsyncMock()
    button = ZenkitRefreshButton(coordinator, "entry")

    await button.async_press()

    coordinator.async_force_refresh.assert_awaited_once()
    assert button.unique_id == "entry_refresh"
    assert button.entity_id == "button.zenkit_refresh"


async def test_entity_id_independent_of_language(hass):
    hass.config.language = "de"
    platform = MockEntityPlatform(hass, domain="button", platform_name="zenkit")

    await platform.async_add_entities([ZenkitRefreshButton(MagicMock(), "entry")])

    assert hass.states.get("button.zenkit_refresh") is not None
