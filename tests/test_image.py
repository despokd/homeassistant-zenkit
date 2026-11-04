"""Tests for the Zenkit profile image."""

from unittest.mock import MagicMock

from custom_components.zenkit.image import ZenkitProfileImage

USER = {"id": 1, "imageLink": "123", "isImagePreferred": True}
URL = "https://zenkit.com/api/v1/files/123/convert?w=256&h=256"


def _image(hass, user=USER):
    coordinator = MagicMock(user=user, last_update_success=True)
    return ZenkitProfileImage(hass, coordinator, "entry")


async def test_image_url(hass):
    image = _image(hass)

    assert image.image_url == URL
    assert image.available
    assert image.unique_id == "entry_profile_image"
    assert image.entity_id == "image.zenkit_profile_image"


async def test_unavailable_when_initials_are_preferred(hass):
    assert not _image(hass, {**USER, "isImagePreferred": False}).available


async def test_changed_image_updates_url_and_time(hass):
    image = _image(hass)
    first_updated = image.image_last_updated
    image.async_write_ha_state = MagicMock()
    image.coordinator.user = {**USER, "imageLink": "456"}

    image._handle_coordinator_update()

    assert image.image_url.startswith("https://zenkit.com/api/v1/files/456/")
    assert image.image_last_updated >= first_updated


async def test_unchanged_image_keeps_time(hass):
    image = _image(hass)
    first_updated = image.image_last_updated
    image.async_write_ha_state = MagicMock()

    image._handle_coordinator_update()

    assert image.image_last_updated == first_updated
