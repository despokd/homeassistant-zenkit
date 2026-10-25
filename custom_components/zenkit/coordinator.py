"""The Zenkit coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
        # Short ids of lists whose last fetch failed, their entities are unavailable
        self.failed_lists: set[str] = set()

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
        return lists_entries

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
