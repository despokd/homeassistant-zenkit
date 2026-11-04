"""The Zenkit integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .api import Zenkit
from .exceptions import CannotConnectException, CannotLoginException
from .coordinator import ZenkitDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.IMAGE,
    Platform.SENSOR,
    Platform.TODO,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zenkit from a config entry."""

    api_key = entry.data[CONF_TOKEN]
    zk = Zenkit(api_key)

    try:
        user = await zk.login()
    except (TimeoutError, CannotConnectException) as error:
        _LOGGER.error("Error connecting to Zenkit api")
        raise ConfigEntryNotReady from error
    except CannotLoginException as error:
        _LOGGER.error("Authentication error connecting to Zenkit api")
        return False
    except Exception as error:
        _LOGGER.error("Unexpected error connecting to Zenkit api")
        raise ConfigEntryNotReady from error

    _set_unique_id(hass, entry, str(user["id"]))

    coordinator = ZenkitDataUpdateCoordinator(hass, zk, user)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _set_unique_id(hass: HomeAssistant, entry: ConfigEntry, user_id: str) -> None:
    """Set the Zenkit user id on entries created before it was stored."""
    if entry.unique_id is not None:
        return
    if any(
        other.unique_id == user_id
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    ):
        _LOGGER.warning("Zenkit account %s is configured more than once", user_id)
        return
    hass.config_entries.async_update_entry(entry, unique_id=user_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:

        new_data = {**config_entry.data}
        if config_entry.minor_version < 2:
            new_data["token"] = new_data.pop("api_key")

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=3, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
