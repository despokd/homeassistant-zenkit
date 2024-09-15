"""Config flow for Zenkit integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY

from .api import Zenkit
from .const import DOMAIN
from .exceptions import CannotLoginException

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class ZenkitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zenkit."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            zk = Zenkit(user_input[CONF_API_KEY])
            try:
                user = await zk.login()
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except CannotLoginException:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user.get("username", "Zenkit"),
                    data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )