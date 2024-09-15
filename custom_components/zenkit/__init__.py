"""The Zenkit integration."""

from __future__ import annotations

import logging
from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .api import Zenkit
from .exceptions import CannotLoginException
from .coordinator import ZenkitDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zenkit from a config entry."""

    api_key = entry.data[CONF_API_KEY]
    zk = Zenkit(api_key)

    try:
        await zk.login()
    except (TimeoutError, ClientError) as error:
        _LOGGER.error("Error connecting to Zenkit api")
        raise ConfigEntryNotReady from error
    except CannotLoginException as error:
        _LOGGER.error("Authentication error connecting to Zenkit api")
        return False
    except Exception as error:
        _LOGGER.error("Unexpected error connecting to Zenkit api")
        raise ConfigEntryNotReady from error

    coordinator = ZenkitDataUpdateCoordinator(hass, zk)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
