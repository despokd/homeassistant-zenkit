"""The Zenkit coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_INTERVAL, USER_UPDATE_INTERVAL, ZENKIT_URL
from .api import Zenkit

_LOGGER = logging.getLogger(__name__)
# Device model translation keys by list resourceType, others are "list"
LIST_MODELS = {"taskList": "task_list", "project": "project", "database": "database"}


class ZenkitDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Zenkit data."""

    def __init__(
        self,
        hass: HomeAssistant,
        zk: Zenkit,
        user: dict | None = None,
        entry_id: str = "",
    ) -> None:
        """Initialize global Zenkit data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=True,
        )
        self.zk = zk
        # Scopes the device identifiers, two accounts may share a list (#33)
        self.entry_id = entry_id
        # Registered at setup, before the devices linked to it
        self.account_device_id: str | None = None
        # Translated device models by translation key, loaded at setup
        self.models: dict[str, str] = {}
        self._lists: dict = None
        # Short ids of lists whose last fetch failed, their entities are unavailable
        self.failed_lists: set[str] = set()
        # The account of the API key and its organization, from login, refreshed
        # every USER_UPDATE_INTERVAL, the first update fetches the organization
        self.user = user
        self.organization: dict | None = None
        self.organization_members: int | None = None
        self._account_updated: datetime | None = None
        # None while the count could not be fetched
        self.unread_notifications: int | None = None

    async def _async_update_data(self) -> dict:
        """Fetch items from Zenkit."""

        if self._lists is None:
            try:
                await self.async_get_lists()
            except Exception as error:
                raise UpdateFailed("Failed to fetch lists") from error
            _LOGGER.debug("Lists were empty, fetched lists: %s", self._lists)

        lists_entries = dict()
        if self._lists is not None:
            for list in self._lists:
                list_shortId = list["shortId"]
                if list_shortId not in self.zk.elements:
                    # Entities fall back to heuristics until the fields are known
                    try:
                        await self.zk.get_list_elements(list_shortId)
                    except Exception:
                        _LOGGER.warning(
                            "Failed to fetch fields for list %s (%s)",
                            list["name"],
                            list_shortId,
                        )
                # A failing list only makes its own entity unavailable
                entries = await self._async_fetch_entries(list_shortId, list["name"])
                if entries is not None:
                    lists_entries[list_shortId] = entries

            if self._lists and not lists_entries:
                raise UpdateFailed("Failed to fetch entries of all lists")

        if (
            self._account_updated is None
            or dt_util.utcnow() - self._account_updated
            >= (timedelta(seconds=USER_UPDATE_INTERVAL))
        ):
            await self._async_fetch_account()
        await self._async_fetch_unread_notifications()
        return lists_entries

    async def _async_fetch_account(self) -> None:
        """Fetch the account and organization, keeps the last known data on error."""
        try:
            self.user = await self.zk.login()
            organization_id = self.user["organizationId"]
            self.organization = await self.zk.get_organization(organization_id)
            self.organization_members = await self.zk.get_organization_members_count(
                organization_id
            )
        except Exception as error:
            _LOGGER.warning("Failed to fetch account data: %s", error)
            return
        self._account_updated = dt_util.utcnow()

    @property
    def lists(self) -> list[dict]:
        """The lists fetched at setup."""
        return self._lists or []

    async def _async_fetch_unread_notifications(self) -> None:
        """Fetch the unread notification count, None on error."""
        try:
            self.unread_notifications = await self.zk.get_unread_notifications_count()
        except Exception as error:
            _LOGGER.warning("Failed to fetch notifications: %s", error)
            self.unread_notifications = None

    @property
    def account_identifier(self) -> tuple[str, str] | None:
        """Device identifier of the account, None without user."""
        if self.user is None:
            return None
        return (DOMAIN, f"{self.entry_id}_account_{self.user['id']}")

    @property
    def device_info(self) -> DeviceInfo | None:
        """The Zenkit account as a service device with the account entities."""
        if self.user is None:
            return None
        return DeviceInfo(
            identifiers={self.account_identifier},
            name=self.user.get("displayname") or self.user["username"],
            manufacturer="Zenkit",
            model=self._model("account"),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=ZENKIT_URL,
        )

    @property
    def organization_device_info(self) -> DeviceInfo | None:
        """The organization of the account, None if the account has none."""
        organization_id = (self.user or {}).get("organizationId")
        if organization_id is None:
            return None
        name = (self.organization or {}).get("name")
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_organization_{organization_id}")},
            # The organization may be unknown if its fetch failed at setup
            name=name or None,
            translation_key=None if name else "organization",
            manufacturer="Zenkit",
            model=self._model("organization"),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=ZENKIT_URL,
            **self._via_account(),
        )

    def list_device_info(self, zenkit_list: dict) -> DeviceInfo:
        """A Zenkit list with its todo, calendar and sensor entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_list_{zenkit_list['uuid']}")},
            name=zenkit_list["name"],
            manufacturer="Zenkit",
            model=self._model(LIST_MODELS.get(zenkit_list.get("resourceType"), "list")),
            configuration_url=ZENKIT_URL,
            **self._via_account(),
        )

    def _model(self, key: str) -> str:
        """The translated device model, the key before translations are loaded."""
        return self.models.get(key, key)

    def _via_account(self) -> DeviceInfo:
        """Link a device to the account device, once it is registered."""
        if self.account_device_id is None:
            return DeviceInfo()
        return DeviceInfo(via_device_id=self.account_device_id)

    @property
    def device_identifiers(self) -> set[tuple[str, str]]:
        """Identifiers of all current devices, others are stale."""
        devices = [self.device_info, self.organization_device_info]
        devices += [self.list_device_info(list) for list in self.lists]
        return {
            identifier
            for device in devices
            if device is not None
            for identifier in device["identifiers"]
        }

    async def async_refresh_list(self, list_short_id: str) -> None:
        """Fetch the entries of one list, e.g. after a write to it."""
        name = next(
            (
                list["name"]
                for list in self._lists or []
                if list["shortId"] == list_short_id
            ),
            list_short_id,
        )
        entries = await self._async_fetch_entries(list_short_id, name)
        data = {
            short_id: list_entries
            for short_id, list_entries in (self.data or {}).items()
            if short_id != list_short_id
        }
        if entries is not None:
            data[list_short_id] = entries
        self.async_set_updated_data(data)

    async def async_force_refresh(self) -> None:
        """Fetch all list fields and entries and the account now, bypassing caches."""
        self.zk.elements.clear()
        self._account_updated = None
        await self.async_refresh()

    async def _async_fetch_entries(
        self, list_short_id: str, name: str
    ) -> list[dict] | None:
        """Fetch the entries of a list, None and marked as failed on error."""
        try:
            entries = await self.zk.get_list_entries(list_short_id)
        except Exception as error:
            _LOGGER.warning(
                "Failed to fetch entries for list %s (%s): %s",
                name,
                list_short_id,
                error,
            )
            self.failed_lists.add(list_short_id)
            return None
        self.failed_lists.discard(list_short_id)
        _LOGGER.debug(
            "Fetched %s entries for list %s (%s)", len(entries), name, list_short_id
        )
        return entries

    async def async_get_lists(self) -> dict:
        """Return lists from Zenkit fetched at most once."""
        if self._lists is None:
            self._lists = await self.zk.get_lists()
        return self._lists
