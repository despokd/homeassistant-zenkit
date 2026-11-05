"""The Zenkit integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.translation import async_get_translations

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
    coordinator.models = await _async_device_models(hass)
    await coordinator.async_config_entry_first_refresh()
    _register_devices(hass, entry, coordinator)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def update_list_devices() -> None:
        _update_list_devices(hass, entry, coordinator)

    update_list_devices()
    entry.async_on_unload(coordinator.async_add_listener(update_list_devices))

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


async def _async_device_models(hass: HomeAssistant) -> dict[str, str]:
    """Device models in the language of HA, HA translates only device names."""
    translations = await async_get_translations(
        hass, hass.config.language, "device", {DOMAIN}
    )
    prefix = f"component.{DOMAIN}.device."
    return {
        key.removeprefix(prefix).removesuffix(".name"): name
        for key, name in translations.items()
        if key.startswith(prefix) and key.endswith(".name")
    }


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
    old = registry.async_get_device_by_identifier(
        (DOMAIN, str(coordinator.user["id"])), entry.entry_id
    )
    if old is None:
        return
    if registry.async_get_device_by_identifier(
        coordinator.account_identifier, entry.entry_id
    ):
        # E.g. after a downgrade and upgrade, the account device exists already
        registry.async_remove_device(old.id)
        return
    _LOGGER.debug("Migrating device %s to the account device", old.id)
    registry.async_update_device(
        old.id, new_identifiers={coordinator.account_identifier}
    )


@callback
def _update_list_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: ZenkitDataUpdateCoordinator
) -> None:
    """Follow renamed and removed lists, new lists get devices with their entities.

    Removing a device removes its entities from the entity registry.
    """
    registry = dr.async_get(hass)
    current = coordinator.device_identifiers
    list_prefix = f"{entry.entry_id}_list_"
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        is_list = any(
            domain == DOMAIN and identifier.startswith(list_prefix)
            for domain, identifier in device.identifiers
        )
        if is_list and not device.identifiers & current:
            _LOGGER.debug("Removing device %s of a removed list", device.name)
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
    for zenkit_list in coordinator.lists:
        info = coordinator.list_device_info(zenkit_list)
        device = registry.async_get_device(identifiers=info["identifiers"])
        if device is not None and (
            device.name != info["name"] or device.model != info["model"]
        ):
            # A name given in HA (name_by_user) is kept
            registry.async_update_device(
                device.id, name=info["name"], model=info["model"]
            )


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
