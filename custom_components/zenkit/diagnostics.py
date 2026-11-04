"""Diagnostics for the Zenkit integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# The user payload contains the API key in plain text and personal data
TO_REDACT = {
    CONF_TOKEN,
    "title",
    "api_key",
    "tokens",
    "emails",
    "username",
    "displayname",
    "fullname",
    "initials",
    "imageLink",
    "recentListShortIds",
    "recentListEntries",
    "recentGlobalSearchQueries",
}

LIST_FIELDS = ("id", "shortId", "uuid", "workspaceId", "resourceType", "appType")
ELEMENT_FIELDS = ("uuid", "name", "resourceRole", "elementcategory", "isPrimary")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    lists = []
    for list in await coordinator.async_get_lists() or []:
        short_id = list["shortId"]
        elements = coordinator.zk.elements.get(short_id)
        entries = (coordinator.data or {}).get(short_id)
        lists.append(
            {
                **{field: list.get(field) for field in LIST_FIELDS},
                "elements": (
                    [
                        {field: element.get(field) for field in ELEMENT_FIELDS}
                        for element in elements
                    ]
                    if elements is not None
                    else None
                ),
                "entries": len(entries) if entries is not None else None,
                "failed": short_id in coordinator.failed_lists,
            }
        )

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "user": async_redact_data(coordinator.user, TO_REDACT),
        "organization": async_redact_data(
            coordinator.organization, TO_REDACT | {"name", "description"}
        ),
        "organization_members": coordinator.organization_members,
        "unread_notifications": coordinator.unread_notifications,
        "lists": lists,
    }
