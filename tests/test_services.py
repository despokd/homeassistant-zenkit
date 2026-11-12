"""Tests for the Zenkit actions."""

import datetime

import pytest
import voluptuous as vol

from custom_components.zenkit.const import DOMAIN
from custom_components.zenkit.services import (
    CREATE_ENTRY_SCHEMA,
    SERVICE_CREATE_ENTRY,
    SERVICE_UPDATE_ENTRY,
    UPDATE_ENTRY_SCHEMA,
    async_setup_services,
)


async def test_create_entry_is_registered(hass):
    async_setup_services(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_ENTRY)
    assert hass.services.has_service(DOMAIN, SERVICE_UPDATE_ENTRY)


def test_create_entry_schema():
    data = CREATE_ENTRY_SCHEMA(
        {
            "entity_id": "todo.inbox",
            "name": "Buy milk",
            "due_date": "2026-11-03",
            "labels": "Important",
            "assignees": ["Jane Doe"],
            "checklist": "Passport",
        }
    )

    assert data["due_date"] == datetime.date(2026, 11, 3)
    assert data["labels"] == ["Important"]
    assert data["checklist"] == ["Passport"]


@pytest.mark.parametrize(
    "data",
    [
        {"entity_id": "todo.inbox"},
        {"entity_id": "todo.inbox", "name": ""},
        {"entity_id": "todo.inbox", "name": "Trip", "checklist": ["Passport", ""]},
        {
            "entity_id": "todo.inbox",
            "name": "Buy milk",
            "due_date": "2026-11-03",
            "due_datetime": "2026-11-03 18:00:00",
        },
    ],
)
def test_create_entry_schema_rejects(data):
    with pytest.raises(vol.Invalid):
        CREATE_ENTRY_SCHEMA(data)


def test_update_entry_schema():
    data = UPDATE_ENTRY_SCHEMA(
        {
            "entity_id": "todo.inbox",
            "item": "Buy milk",
            "due_date": "2026-11-03",
            "labels": "Important",
        }
    )

    assert data["due_date"] == datetime.date(2026, 11, 3)
    assert data["labels"] == ["Important"]


def test_update_entry_schema_clears():
    data = UPDATE_ENTRY_SCHEMA(
        {
            "entity_id": "todo.inbox",
            "item": "Buy milk",
            "description": None,
            "due_date": None,
            "labels": [],
            "assignees": None,
        }
    )

    assert data["description"] is None
    assert data["due_date"] is None
    assert data["labels"] == []
    assert data["assignees"] == []


@pytest.mark.parametrize(
    "data",
    [
        {"entity_id": "todo.inbox"},
        {"entity_id": "todo.inbox", "item": ""},
        {"entity_id": "todo.inbox", "item": "Buy milk", "rename": ""},
        {"entity_id": "todo.inbox", "item": "Buy milk", "status": ""},
        {"entity_id": "todo.inbox", "item": "Buy milk", "checklist": ["Passport"]},
        {
            "entity_id": "todo.inbox",
            "item": "Buy milk",
            "due_date": "2026-11-03",
            "due_datetime": "2026-11-03 18:00:00",
        },
    ],
)
def test_update_entry_schema_rejects(data):
    with pytest.raises(vol.Invalid):
        UPDATE_ENTRY_SCHEMA(data)
