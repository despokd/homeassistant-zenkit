"""Config flow for Zenkit integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import Zenkit
from .const import CONF_LIST_TYPES, CONF_SHOPPING_LIST, DOMAIN, OPTIONAL_LIST_TYPES
from .coordinator import ZenkitConfigEntry
from .exceptions import CannotConnectException, CannotLoginException

_LOGGER = logging.getLogger(__name__)


def _list_types_field(current: list[str]) -> dict:
    """Choose the list types synced besides to-do lists."""
    return {
        vol.Optional(CONF_LIST_TYPES, default=current): SelectSelector(
            SelectSelectorConfig(
                options=OPTIONAL_LIST_TYPES,
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_LIST_TYPES,
            )
        ),
    }


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
        **_list_types_field(OPTIONAL_LIST_TYPES),
    }
)


class ZenkitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zenkit."""

    VERSION = 2
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ZenkitConfigEntry) -> ZenkitOptionsFlow:
        """Options of a Zenkit account."""
        return ZenkitOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            zk = Zenkit(async_get_clientsession(self.hass), user_input[CONF_TOKEN])
            try:
                user = await zk.login()
            except (TimeoutError, CannotConnectException):
                errors["base"] = "cannot_connect"
            except CannotLoginException:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # One entry per Zenkit account
                await self.async_set_unique_id(str(user["id"]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.get("username", "Zenkit"),
                    data={CONF_TOKEN: user_input[CONF_TOKEN]},
                    options={
                        CONF_LIST_TYPES: user_input.get(
                            CONF_LIST_TYPES, OPTIONAL_LIST_TYPES
                        )
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class ZenkitOptionsFlow(OptionsFlowWithReload):
    """Choose the synced list types and the list for Assist, see assist.py."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the lists of the account."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry: ZenkitConfigEntry = self.config_entry
        coordinator = getattr(entry, "runtime_data", None)
        lists = coordinator.lists if coordinator is not None else []
        options = [
            SelectOptionDict(value=zenkit_list["uuid"], label=zenkit_list["name"])
            for zenkit_list in sorted(lists, key=lambda item: item["name"].casefold())
        ]
        current = entry.options.get(CONF_SHOPPING_LIST)
        schema = vol.Schema(
            {
                **_list_types_field(
                    entry.options.get(CONF_LIST_TYPES, OPTIONAL_LIST_TYPES)
                ),
                vol.Optional(
                    CONF_SHOPPING_LIST,
                    description={"suggested_value": current} if current else None,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
