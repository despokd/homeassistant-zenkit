"""Tests for the Zenkit diagnostics."""

import json
from unittest.mock import MagicMock

from homeassistant.const import CONF_TOKEN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zenkit.const import DOMAIN
from custom_components.zenkit.diagnostics import async_get_config_entry_diagnostics

USER = {
    "id": 906842,
    "username": "user",
    "displayname": "User Name",
    "api_key": "secret-key",
    "emails": [{"email": "user@example.com", "isPrimary": True}],
    "timezone": "Europe/Berlin",
    "settings": {"language": "de", "recentListShortIds": ["a"]},
}
LISTS = [
    {"id": 1, "shortId": "a", "name": "Private list", "workspaceId": 7},
    {"id": 2, "shortId": "b", "name": "Failing list", "workspaceId": 7},
]


async def test_diagnostics_redacts_secrets(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="user", data={CONF_TOKEN: "secret-key"}, version=2
    )
    entry.add_to_hass(hass)
    coordinator = MagicMock(
        user=USER,
        organization={"id": 560986, "name": "Private org", "planId": "free"},
        organization_members=2,
        unread_notifications=2,
        data={"a": [{"uuid": "e1"}, {"uuid": "e2"}]},
        failed_lists={"b"},
    )
    coordinator.lists = LISTS
    coordinator.zk.elements = {
        "a": [{"uuid": "t", "name": "Titel", "resourceRole": "title", "x": 1}]
    }
    entry.runtime_data = coordinator

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    dumped = json.dumps(diagnostics)
    for secret in (
        "secret-key",
        "user@example.com",
        "User Name",
        "Private list",
        "Private org",
    ):
        assert secret not in dumped
    assert diagnostics["user"]["id"] == 906842
    assert diagnostics["user"]["settings"]["language"] == "de"
    assert diagnostics["unread_notifications"] == 2
    assert diagnostics["organization"]["planId"] == "free"
    assert diagnostics["organization_members"] == 2
    assert diagnostics["lists"][0]["entries"] == 2
    assert diagnostics["lists"][0]["elements"] == [
        {
            "uuid": "t",
            "name": "Titel",
            "resourceRole": "title",
            "elementcategory": None,
            "isPrimary": None,
        }
    ]
    assert diagnostics["lists"][1] | {"id": None} == {
        "id": None,
        "shortId": "b",
        "uuid": None,
        "workspaceId": 7,
        "resourceType": None,
        "appType": None,
        "elements": None,
        "entries": None,
        "failed": True,
    }
