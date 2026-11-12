"""Tests for the Zenkit config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.zenkit.const import (
    CONF_LIST_TYPES,
    CONF_SHOPPING_LIST,
    DOMAIN,
)
from custom_components.zenkit.exceptions import (
    CannotConnectException,
    CannotLoginException,
)

USER = {"id": 906842, "username": "user"}


@pytest.fixture
def login():
    with (
        patch("custom_components.zenkit.config_flow.Zenkit.login") as login,
        patch("custom_components.zenkit.async_setup_entry", return_value=True),
    ):
        login.return_value = USER
        yield login


async def _submit(hass, **user_input):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "key", **user_input}
    )


async def test_creates_entry_for_account(hass, login):
    result = await _submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user"
    assert result["data"] == {CONF_TOKEN: "key"}
    assert result["options"] == {CONF_LIST_TYPES: ["project", "database"]}
    assert result["result"].unique_id == "906842"


async def test_setup_chooses_list_types(hass, login):
    result = await _submit(hass, **{CONF_LIST_TYPES: ["database"]})

    assert result["data"] == {CONF_TOKEN: "key"}
    assert result["options"] == {CONF_LIST_TYPES: ["database"]}


async def test_same_account_aborts(hass, login):
    MockConfigEntry(domain=DOMAIN, unique_id="906842", version=2).add_to_hass(hass)

    result = await _submit(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (CannotLoginException, "invalid_auth"),
        (CannotConnectException, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_errors(hass, login, error, reason):
    login.side_effect = error

    result = await _submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}


async def test_options_choose_shopping_list(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="906842", version=2)
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        lists=[
            {"uuid": "b-uuid", "name": "groceries"},
            {"uuid": "a-uuid", "name": "Chores"},
        ]
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    field = result["data_schema"].schema[CONF_SHOPPING_LIST]
    assert [option["label"] for option in field.config["options"]] == [
        "Chores",
        "groceries",
    ]

    with patch("custom_components.zenkit.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_SHOPPING_LIST: "b-uuid", CONF_LIST_TYPES: ["project"]},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SHOPPING_LIST: "b-uuid", CONF_LIST_TYPES: ["project"]}


async def test_options_of_unloaded_entry_have_no_lists(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="906842", version=2)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    field = result["data_schema"].schema[CONF_SHOPPING_LIST]
    assert field.config["options"] == []


async def test_options_list_types_default_to_all(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="906842", version=2)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch("custom_components.zenkit.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )

    assert entry.options == {CONF_LIST_TYPES: ["project", "database"]}
