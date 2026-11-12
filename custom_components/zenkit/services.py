"""Actions of the Zenkit integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_CREATE_ENTRY = "create_entry"
SERVICE_UPDATE_ENTRY = "update_entry"

ATTR_NAME = "name"
ATTR_DESCRIPTION = "description"
ATTR_DUE_DATE = "due_date"
ATTR_DUE_DATETIME = "due_datetime"
ATTR_STATUS = "status"
ATTR_LABELS = "labels"
ATTR_ASSIGNEES = "assignees"
ATTR_CHECKLIST = "checklist"
ATTR_CHECKLIST_NAME = "checklist_name"
ATTR_ITEM = "item"
ATTR_RENAME = "rename"

CREATE_ENTRY_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional(ATTR_DESCRIPTION): cv.string,
            vol.Optional(ATTR_DUE_DATE): cv.date,
            vol.Optional(ATTR_DUE_DATETIME): cv.datetime,
            vol.Optional(ATTR_STATUS): cv.string,
            vol.Optional(ATTR_LABELS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ASSIGNEES): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_CHECKLIST): vol.All(
                cv.ensure_list, [vol.All(cv.string, vol.Length(min=1))]
            ),
            vol.Optional(ATTR_CHECKLIST_NAME): cv.string,
        }
    ),
    cv.has_at_most_one_key(ATTR_DUE_DATE, ATTR_DUE_DATETIME),
)

# Fields that are not given stay as they are, null or an empty list clears them
UPDATE_ENTRY_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Required(ATTR_ITEM): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional(ATTR_RENAME): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional(ATTR_DESCRIPTION): vol.Any(None, cv.string),
            vol.Optional(ATTR_DUE_DATE): vol.Any(None, cv.date),
            vol.Optional(ATTR_DUE_DATETIME): vol.Any(None, cv.datetime),
            vol.Optional(ATTR_STATUS): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional(ATTR_LABELS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ASSIGNEES): vol.All(cv.ensure_list, [cv.string]),
        }
    ),
    cv.has_at_most_one_key(ATTR_DUE_DATE, ATTR_DUE_DATETIME),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions, they target Zenkit todo entities."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CREATE_ENTRY,
        entity_domain=TODO_DOMAIN,
        schema=CREATE_ENTRY_SCHEMA,
        func="async_create_entry",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_ENTRY,
        entity_domain=TODO_DOMAIN,
        schema=UPDATE_ENTRY_SCHEMA,
        func="async_update_entry",
    )
