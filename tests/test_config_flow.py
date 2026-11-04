"""Tests for the Zenkit config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import FlowResultType

from custom_components.zenkit.const import DOMAIN
from custom_components.zenkit.exceptions import (
    CannotConnectException,
    CannotLoginException,
)

USER = {"id": 906842, "username": "user"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def login():
    with (
        patch("custom_components.zenkit.config_flow.Zenkit.login") as login,
        patch("custom_components.zenkit.async_setup_entry", return_value=True),
    ):
        login.return_value = USER
        yield login


async def _submit(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "key"}
    )


async def test_creates_entry_for_account(hass, login):
    result = await _submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user"
    assert result["data"] == {CONF_TOKEN: "key"}


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
