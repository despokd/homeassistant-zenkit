"""The Zenkit coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from custom_components.zenkit.exceptions import UpdateFailedException
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL
from .api import Zenkit

_LOGGER = logging.getLogger(__name__)


class ZenkitDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Zenkit data."""

    def __init__(self, hass: HomeAssistant, zk: Zenkit) -> None:
        """Initialize global Zenkit data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=True,
        )
        self.zk = zk
        self._lists: dict = None

    async def _async_update_data(self) -> dict:
        """Fetch items from Zenkit."""

        if self._lists is None:
            try:
                await self.async_get_lists()
            except Exception as error:
                raise UpdateFailedException("Failed to fetch lists") from error
            _LOGGER.debug("Lists were empty, fetched lists: %s", self._lists)

        lists_entries = dict()
        if self._lists is not None:
            for list in self._lists:
                list_shortId = list["shortId"]
                try:
                    list_entries = await self.zk.get_list_entries(list_shortId)
                except Exception as error:
                    raise UpdateFailedException(
                        "Failed to fetch list entities for list %s (%s)",
                        list["name"],
                        list_shortId,
                    ) from error
                lists_entries[list_shortId] = list_entries
        return lists_entries

    async def async_get_lists(self) -> dict:
        """Return lists from Zenkit fetched at most once."""
        if self._lists is None:
            self._lists = await self.zk.get_lists()
        return self._lists
