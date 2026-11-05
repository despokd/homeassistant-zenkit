"""Tests for the entry count sensors of Zenkit lists."""

import datetime
from unittest.mock import MagicMock

import pytest

from homeassistant.util import dt as dt_util

from custom_components.zenkit.sensor import (
    LIST_SENSORS,
    ZenkitListSensor,
    async_setup_entry,
)

STAGE = "stage-uuid"
DUE = "due-uuid"
STAGE_ELEMENT = {
    "uuid": STAGE,
    "elementcategory": 6,
    "resourceRole": "stage",
    "elementData": {
        "predefinedCategories": [
            {"id": 1, "resourceRole": "todo", "colorHex": "#0089d1"},
            {"id": 2, "resourceRole": "done", "colorHex": "#3ba744"},
        ]
    },
}
TITLE_ELEMENT = {"uuid": "title-uuid", "elementcategory": 1, "resourceRole": "title"}
DUE_ELEMENT = {"uuid": DUE, "elementcategory": 4, "resourceRole": "dueDate"}
ELEMENTS = [TITLE_ELEMENT, DUE_ELEMENT, STAGE_ELEMENT]
LIST = {"shortId": "list", "uuid": "list-uuid", "name": "Groceries"}
NOW = datetime.datetime(2026, 11, 5, 12, 0, tzinfo=datetime.UTC)


def _entry(status=1, date=None, has_time=False):
    entry = {"uuid": "e", "displayString": "x", f"{STAGE}_categories": [status]}
    if date is not None:
        entry[f"{DUE}_date"] = date
        entry[f"{DUE}_hasTime"] = has_time
    return entry


ENTRIES = [
    _entry(),  # open, no due date
    _entry(date="2026-11-04"),  # overdue
    _entry(date="2026-11-05"),  # due today, not overdue
    _entry(date="2026-11-05T09:00:00.000Z", has_time=True),  # today and overdue
    _entry(date="2026-11-05T15:00:00.000Z", has_time=True),  # today
    _entry(date="2026-11-06"),  # tomorrow
    _entry(status=2, date="2026-11-01"),  # completed
]


@pytest.fixture(autouse=True)
def now(monkeypatch):
    monkeypatch.setattr(dt_util, "now", lambda time_zone=None: NOW)


def _coordinator(entries=ENTRIES, elements=ELEMENTS):
    coordinator = MagicMock(
        entry_id="entry",
        data={"list": list(entries)},
        failed_lists=set(),
        last_update_success=True,
        lists=[LIST],
    )
    coordinator.zk.elements = {} if elements is None else {"list": elements}
    return coordinator


def _sensor(key, coordinator=None):
    description = next(d for d in LIST_SENSORS if d.key == key)
    return ZenkitListSensor(coordinator or _coordinator(), LIST, description)


@pytest.mark.parametrize(
    ("key", "value"),
    [("open_entries", 6), ("overdue_entries", 2), ("entries_due_today", 3)],
)
def test_counts(key, value):
    assert _sensor(key).native_value == value


def test_counts_without_known_fields():
    """Status and due date fall back to the heuristics of the todo entity."""
    entries = [
        {"uuid": "e", "displayString": "x", "d_date": "2026-11-04"},
        {
            "uuid": "f",
            "displayString": "y",
            "s_categories_sort": [{"colorHex": "#3ba744"}],
        },
    ]
    coordinator = _coordinator(entries, elements=None)
    assert _sensor("open_entries", coordinator).native_value == 1
    assert _sensor("overdue_entries", coordinator).native_value == 1


def test_list_without_status_counts_all_entries():
    coordinator = _coordinator(
        [_entry(), _entry(status=2)], elements=[TITLE_ELEMENT, DUE_ELEMENT]
    )
    assert _sensor("open_entries", coordinator).native_value == 2


def test_failed_list_is_unavailable():
    coordinator = _coordinator()
    coordinator.failed_lists.add("list")
    assert not _sensor("open_entries", coordinator).available


def test_list_without_data_is_unavailable():
    coordinator = _coordinator()
    coordinator.data = {}
    sensor = _sensor("open_entries", coordinator)
    assert not sensor.available
    assert sensor.native_value is None


def test_ids_and_name():
    sensor = _sensor("overdue_entries")
    assert sensor.unique_id == "entry_list-uuid_overdue_entries"
    assert sensor.entity_id == "sensor.zenkit_groceries_overdue_entries"
    assert sensor.translation_key == "overdue_entries"
    assert sensor.device_info is sensor.coordinator.list_device_info.return_value
    sensor.coordinator.list_device_info.assert_called_with(LIST)


async def _keys(coordinator):
    hass = MagicMock()
    added = []
    await async_setup_entry(
        hass, MagicMock(entry_id="entry", runtime_data=coordinator), added.extend
    )
    return {e.entity_description.key for e in added if isinstance(e, ZenkitListSensor)}


async def test_setup_adds_all_counts_for_lists_with_due_date():
    assert await _keys(_coordinator()) == {
        "open_entries",
        "overdue_entries",
        "entries_due_today",
    }


async def test_setup_adds_only_open_count_without_due_date():
    coordinator = _coordinator(elements=[TITLE_ELEMENT, STAGE_ELEMENT])
    assert await _keys(coordinator) == {"open_entries"}
