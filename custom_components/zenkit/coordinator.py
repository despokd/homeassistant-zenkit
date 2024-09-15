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
        self.zk = zk
        self.lists: list[dict] = []
        self._list_entries: dict[str, list[dict]] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=True
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Zenkit."""
        try:
            lists = await self.zk.get_lists()
        except Exception as error:
            raise UpdateFailedException("Failed to fetch lists") from error

        self.lists = lists
        return {"lists": lists}

    async def async_get_list_entities(self, list_shortId) -> list[dict]:
        """Get list entities."""
        listEntities = []
        try:
            listEntities = await self.zk.get_list_entries(list_shortId)
        except Exception as error:
            raise UpdateFailedException(
                "Failed to fetch list entities for list: %s" % list_shortId
            ) from error
        return listEntities
