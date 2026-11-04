"""Tests for the Zenkit refresh button."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.zenkit.button import ZenkitRefreshButton


async def test_press_forces_refresh():
    coordinator = MagicMock()
    coordinator.async_force_refresh = AsyncMock()
    button = ZenkitRefreshButton(coordinator, "entry")

    await button.async_press()

    coordinator.async_force_refresh.assert_awaited_once()
    assert button.unique_id == "entry_refresh"
