"""The Zenkit integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

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

    coordinator = ZenkitDataUpdateCoordinator(hass, zk, user, entry.entry_id)
    await coordinator.async_config_entry_first_refresh()
    _register_devices(hass, entry, coordinator)

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


def _register_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: ZenkitDataUpdateCoordinator
) -> None:
    """Register the account and organization devices, list devices link to them."""
    registry = dr.async_get(hass)
    _migrate_account_device(registry, entry, coordinator)
    account = registry.async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    )
    coordinator.account_device_id = account.id
    if (organization := coordinator.organization_device_info) is not None:
        registry.async_get_or_create(config_entry_id=entry.entry_id, **organization)


def _migrate_account_device(
    registry: dr.DeviceRegistry,
    entry: ConfigEntry,
    coordinator: ZenkitDataUpdateCoordinator,
) -> None:
    """Keep the single device of older versions as account device.

    It was identified by the user id only, so its area and name survive.
    """
    old = _entry_device(registry, entry, (DOMAIN, str(coordinator.user["id"])))
    if old is None:
        return
    if _entry_device(registry, entry, coordinator.account_identifier) is not None:
        # E.g. after a downgrade and upgrade, the account device exists already
        _remove_entry_device(registry, entry, old)
        return
    _LOGGER.debug("Migrating device %s to the account device", old.id)
    registry.async_update_device(
        old.id, new_identifiers={coordinator.account_identifier}
    )
    if not hasattr(old, "config_entry_id"):
        # Before HA 2026.8 an account configured twice shared the device
        for other in old.config_entries - {entry.entry_id}:
            registry.async_update_device(old.id, remove_config_entry_id=other)


def _entry_device(
    registry: dr.DeviceRegistry, entry: ConfigEntry, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """The device of the config entry with the identifier."""
    if hasattr(registry, "async_get_device_by_identifier"):
        return registry.async_get_device_by_identifier(identifier, entry.entry_id)
    # Before HA 2026.8 devices were shared by config entries
    device = registry.async_get_device(identifiers={identifier})
    if device is None or entry.entry_id not in device.config_entries:
        return None
    return device


def _remove_entry_device(
    registry: dr.DeviceRegistry, entry: ConfigEntry, device: dr.DeviceEntry
) -> None:
    """Remove the device from the config entry."""
    if hasattr(device, "config_entry_id"):
        registry.async_remove_device(device.id)
    else:
        registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow removing devices of lists that no longer exist."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return not device.identifiers & coordinator.device_identifiers


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
