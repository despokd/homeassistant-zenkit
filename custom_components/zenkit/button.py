"""A button platform for Zenkit."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZenkitDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Zenkit button platform config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZenkitRefreshButton(coordinator, entry.entry_id)])


class ZenkitRefreshButton(ButtonEntity):
    """Button to force an update of all Zenkit data."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: ZenkitDataUpdateCoordinator, entry_id: str) -> None:
        """Initialize ZenkitRefreshButton."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_refresh"

    async def async_press(self) -> None:
        """Refresh all lists now."""
        await self.coordinator.async_force_refresh()
