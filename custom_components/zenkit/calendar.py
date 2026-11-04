"""A calendar platform for Zenkit, one read-only calendar per list with due dates."""

import datetime
import logging
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.todo import TodoItemStatus
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DUE_DATE_FORMAT
from .coordinator import ZenkitDataUpdateCoordinator
from .elements import due_element
from .todo import _completion_status, _description, _list_icon

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a calendar for each Zenkit list with a due date field."""
    coordinator: ZenkitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # The first refresh fetched the fields, lists whose fields failed are skipped
    async_add_entities(
        ZenkitCalendarEntity(coordinator, zenkit_list)
        for zenkit_list in coordinator.lists
        if due_element(coordinator.zk.elements.get(zenkit_list["shortId"]) or [])
        is not None
    )


def _parse_date(
    value: str | None, has_time: bool
) -> datetime.date | datetime.datetime | None:
    """Parse a date value, which is in UTC if it has a time."""
    if not value:
        return None
    try:
        if has_time:
            return dt_util.as_local(datetime.datetime.fromisoformat(value))
        return datetime.datetime.strptime(value[:10], DUE_DATE_FORMAT).date()
    except ValueError:
        _LOGGER.warning("Unable to parse due date %s", value)
    return None


def _event(
    entry: dict[str, Any], due_uuid: str, elements: list[dict]
) -> CalendarEvent | None:
    """Get the event of an entry with a due date, see docs/zenkit/zenkit-todo.md."""
    has_time = bool(entry.get(f"{due_uuid}_hasTime"))
    start = _parse_date(entry.get(f"{due_uuid}_date"), has_time)
    if start is None:
        return None
    # A date range has an end date, which is inclusive for dates
    end = _parse_date(entry.get(f"{due_uuid}_endDate"), has_time)
    if end is None or end < start:
        end = start
    if not has_time:
        end += datetime.timedelta(days=1)
    return CalendarEvent(
        start=start,
        end=end,
        summary=entry["displayString"],
        description=_description(entry, elements),
        uid=entry["uuid"],
    )


def _local(value: datetime.date | datetime.datetime) -> datetime.datetime:
    """Get the local start of a date or a datetime as is, for comparisons."""
    if isinstance(value, datetime.datetime):
        return value
    return dt_util.start_of_local_day(value)


class ZenkitCalendarEntity(
    CoordinatorEntity[ZenkitDataUpdateCoordinator], CalendarEntity
):
    """The open entries with a due date of a Zenkit list."""

    _attr_has_entity_name = True
    _attr_translation_key = "list"

    def __init__(
        self, coordinator: ZenkitDataUpdateCoordinator, zenkit_list: dict[str, Any]
    ) -> None:
        """Initialize the calendar of a list."""
        super().__init__(coordinator=coordinator)
        self.list_short_id = zenkit_list["shortId"]
        self._attr_unique_id = zenkit_list["uuid"]
        self._attr_name = zenkit_list["name"]
        self._attr_icon = _list_icon(zenkit_list)
        self._attr_initial_color = zenkit_list.get("iconColor") or None
        self._attr_device_info = coordinator.device_info
        self._events: list[CalendarEvent] = []

    @property
    def available(self) -> bool:
        """Unavailable while only this list fails to load."""
        return (
            super().available
            and self.list_short_id not in self.coordinator.failed_lists
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the events of the open entries with a due date."""
        elements = self.coordinator.zk.elements.get(self.list_short_id) or []
        due = due_element(elements)
        events = []
        if due is not None:
            for entry in self.coordinator.data.get(self.list_short_id, []):
                if (
                    _completion_status(entry, elements) != TodoItemStatus.COMPLETED
                    and (event := _event(entry, due["uuid"], elements)) is not None
                ):
                    events.append(event)
        self._events = sorted(events, key=lambda event: _local(event.start))
        super()._handle_coordinator_update()

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next event."""
        now = dt_util.now()
        return next(
            (event for event in self._events if _local(event.end) > now),
            None,
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Get the events in a time range."""
        return [
            event
            for event in self._events
            if _local(event.start) < end_date
            and (
                _local(event.end) > start_date
                # Events at a point in time have no duration
                or _local(event.start) == _local(event.end) == start_date
            )
        ]

    async def async_added_to_hass(self) -> None:
        """Get the events from the existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
