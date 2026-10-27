"""Config flow for the GUDE PDU integration."""  # codespell:ignore gude

from collections.abc import Mapping
import logging
from typing import Any, override

from probatio import Optional, Port, Required, Schema

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import GudeAuthError, GudeClient, GudeConnectionError
from .const import DEFAULT_PORT, DEFAULT_SSL, DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = Schema(
    {
        Required(CONF_HOST): str,
        Optional(CONF_PORT, default=DEFAULT_PORT): Port(),
        Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        Optional(CONF_USERNAME): str,
        Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class GudeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            client = GudeClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                ssl=user_input.get(CONF_SSL, DEFAULT_SSL),
                verify_ssl=verify_ssl,
                session=async_get_clientsession(self.hass, verify_ssl=verify_ssl),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )
            try:
                device_info = await client.authenticate()
            except GudeAuthError:
                errors["base"] = "invalid_auth"
            except GudeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during PDU setup")
                errors["base"] = "unknown"
            else:
                formatted_mac = dr.format_mac(device_info.mac)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_info.hostname or device_info.product_name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with PDU."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with PDU."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            verify_ssl = reauth_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            client = GudeClient(
                host=reauth_entry.data[CONF_HOST],
                port=reauth_entry.data.get(CONF_PORT, DEFAULT_PORT),
                ssl=reauth_entry.data.get(CONF_SSL, DEFAULT_SSL),
                verify_ssl=verify_ssl,
                session=async_get_clientsession(self.hass, verify_ssl=verify_ssl),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )
            try:
                await client.authenticate()
            except GudeAuthError:
                errors["base"] = "invalid_auth"
            except GudeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during PDU re-auth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=Schema(
                {
                    Optional(
                        CONF_USERNAME,
                        default=reauth_entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    Optional(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of PDU device."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            client = GudeClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                ssl=user_input.get(CONF_SSL, DEFAULT_SSL),
                verify_ssl=verify_ssl,
                session=async_get_clientsession(self.hass, verify_ssl=verify_ssl),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )
            try:
                device_info = await client.authenticate()
            except GudeAuthError:
                errors["base"] = "invalid_auth"
            except GudeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                formatted_mac = dr.format_mac(device_info.mac)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_mismatch(reason="different_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=Schema(
                {
                    Required(
                        CONF_HOST,
                        default=reconfigure_entry.data.get(CONF_HOST, ""),
                    ): str,
                    Optional(
                        CONF_PORT,
                        default=reconfigure_entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): Port(),
                    Optional(
                        CONF_SSL,
                        default=reconfigure_entry.data.get(CONF_SSL, DEFAULT_SSL),
                    ): bool,
                    Optional(
                        CONF_VERIFY_SSL,
                        default=reconfigure_entry.data.get(
                            CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                        ),
                    ): bool,
                    Optional(
                        CONF_USERNAME,
                        default=reconfigure_entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    Optional(
                        CONF_PASSWORD,
                        default=reconfigure_entry.data.get(CONF_PASSWORD, ""),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                }
            ),
            errors=errors,
        )
