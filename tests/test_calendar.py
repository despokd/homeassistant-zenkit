"""Tests for the Zenkit calendar entity."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.util import dt as dt_util

from custom_components.zenkit.calendar import ZenkitCalendarEntity, async_setup_entry
from custom_components.zenkit.const import DOMAIN

STAGE = "stage-uuid"
NOTES = "notes-uuid"
DUE = "due-uuid"
ELEMENTS = [
    {"uuid": "title-uuid", "elementcategory": 1, "resourceRole": "title"},
    {"uuid": NOTES, "elementcategory": 1, "resourceRole": "notes"},
    {"uuid": DUE, "elementcategory": 4, "resourceRole": "dueDate"},
    {
        "uuid": STAGE,
        "elementcategory": 6,
        "resourceRole": "stage",
        "elementData": {
            "predefinedCategories": [
                {"id": 1, "resourceRole": "todo", "colorHex": "#0089d1"},
                {"id": 2, "resourceRole": "done", "colorHex": "#3ba744"},
            ]
        },
    },
]
LIST = {"shortId": "list", "uuid": "list-uuid", "name": "List", "iconColor": "#ff0000"}
UTC = datetime.timezone.utc


def _entry(uuid, due=None, has_time=False, status=1, end=None, **fields):
    return {
        "uuid": uuid,
        "displayString": uuid.title(),
        f"{STAGE}_categories": [status],
        f"{DUE}_date": due,
        f"{DUE}_hasTime": has_time,
        f"{DUE}_endDate": end,
        **fields,
    }


@pytest.fixture(autouse=True)
def utc_time_zone():
    """Local time is UTC."""
    default = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(UTC)
    yield
    dt_util.set_default_time_zone(default)


@pytest.fixture
def coordinator():
    """Coordinator with known fields of the list."""
    coordinator = MagicMock(entry_id="entry")
    coordinator.lists = [LIST]
    coordinator.get_list.return_value = LIST
    coordinator.zk.elements = {"list": ELEMENTS}
    coordinator.failed_lists = set()
    coordinator.data = {
        "list": [
            _entry("timed", "2026-11-04T14:30:00.000Z", has_time=True),
            _entry("dated", "2026-11-03", **{f"{NOTES}_text": "2 liters"}),
            _entry("done", "2026-11-03", status=2),
            _entry("undated"),
            _entry("range", "2026-11-05", end="2026-11-07"),
        ]
    }
    return coordinator


@pytest.fixture
def entity(coordinator):
    entity = ZenkitCalendarEntity(coordinator, LIST)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    return entity


def _range(start, end):
    return (
        datetime.datetime(*start, tzinfo=UTC),
        datetime.datetime(*end, tzinfo=UTC),
    )


async def test_events_of_open_entries_with_due_date(entity):
    events = await entity.async_get_events(None, *_range((2026, 11, 1), (2026, 12, 1)))

    assert [event.uid for event in events] == ["dated", "timed", "range"]
    dated, timed, range = events
    assert dated.start == datetime.date(2026, 11, 3)
    assert dated.end == datetime.date(2026, 11, 4)
    assert dated.all_day
    assert dated.summary == "Dated"
    assert dated.description == "2 liters"
    assert (
        timed.start == timed.end == datetime.datetime(2026, 11, 4, 14, 30, tzinfo=UTC)
    )
    assert not timed.all_day
    # The end date of a range is inclusive
    assert range.end == datetime.date(2026, 11, 8)


async def test_events_in_range(entity):
    events = await entity.async_get_events(None, *_range((2026, 11, 4), (2026, 11, 5)))

    assert [event.uid for event in events] == ["timed"]


async def test_timed_event_at_range_start(entity):
    events = await entity.async_get_events(
        None, *_range((2026, 11, 4, 14, 30), (2026, 11, 4, 15))
    )

    assert [event.uid for event in events] == ["timed"]


def test_next_event(entity):
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime.datetime(2026, 11, 3, 12, tzinfo=UTC),
    ):
        assert entity.event.uid == "dated"
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime.datetime(2026, 11, 4, 0, tzinfo=UTC),
    ):
        assert entity.event.uid == "timed"
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime.datetime(2026, 12, 1, tzinfo=UTC),
    ):
        assert entity.event is None


def test_appearance(entity):
    assert entity.unique_id == "entry_list-uuid"
    # Named after the list device
    assert entity.name is None
    assert entity.device_info is entity.coordinator.list_device_info.return_value
    entity.coordinator.list_device_info.assert_called_with(LIST)
    assert entity.initial_color == "#ff0000"


def test_unavailable_when_list_fails(entity, coordinator):
    coordinator.failed_lists.add("list")

    assert not entity.available


async def test_invalid_date_is_skipped(entity, coordinator):
    coordinator.data["list"] = [_entry("bad", "not a date")]
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()

    assert entity._events == []


async def test_only_lists_with_due_date_field(coordinator):
    coordinator.lists = [
        LIST,
        {"shortId": "no-due", "uuid": "u2", "name": "No due"},
        {"shortId": "no-fields", "uuid": "u3", "name": "No fields"},
    ]
    coordinator.zk.elements["no-due"] = ELEMENTS[:2]
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coordinator}}
    added = []

    await async_setup_entry(hass, MagicMock(entry_id="entry"), added.extend)

    assert [entity.unique_id for entity in added] == ["entry_list-uuid"]


async def test_calendar_added_once_fields_are_known(coordinator):
    coordinator.zk.elements = {}
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coordinator}}
    added = []
    await async_setup_entry(hass, MagicMock(entry_id="entry"), added.extend)
    coordinator.zk.elements = {"list": ELEMENTS}

    coordinator.async_add_listener.call_args.args[0]()

    assert [entity.unique_id for entity in added] == ["entry_list-uuid"]


async def test_icon_follows_list(entity, coordinator):
    coordinator.get_list.return_value = {**LIST, "iconClassNames": "fa-tree"}
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()

    assert entity.icon == "mdi:pine-tree"
