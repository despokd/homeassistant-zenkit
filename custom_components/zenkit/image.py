"""An image platform for Zenkit."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import user_image_url
from .const import DOMAIN
from .coordinator import ZenkitConfigEntry, ZenkitDataUpdateCoordinator

# Pixels of the profile image, Zenkit scales it on request
IMAGE_SIZE = 256


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZenkitConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zenkit image platform config entry."""
    coordinator = entry.runtime_data
    async_add_entities([ZenkitProfileImage(hass, coordinator, entry.entry_id)])


class ZenkitProfileImage(CoordinatorEntity[ZenkitDataUpdateCoordinator], ImageEntity):
    """The profile image of the Zenkit account."""

    _attr_has_entity_name = True
    _attr_translation_key = "profile_image"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ZenkitDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize ZenkitProfileImage."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{entry_id}_profile_image"
        self._attr_device_info = coordinator.device_info
        # Suggested id, else it is derived from the name in the HA language
        self.entity_id = f"image.{DOMAIN}_profile_image"
        self._update_image_url()

    def _update_image_url(self) -> None:
        """Take the image URL of the account, a new URL is a new image."""
        url = user_image_url(self.coordinator.user or {}, IMAGE_SIZE)
        if url != self._attr_image_url:
            self._attr_image_url = url
            self._attr_image_last_updated = dt_util.utcnow()
            self._cached_image = None

    @property
    def available(self) -> bool:
        """Unavailable without a profile image, e.g. initials are preferred."""
        return super().available and self._attr_image_url is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Pick up a changed profile image."""
        self._update_image_url()
        super()._handle_coordinator_update()
