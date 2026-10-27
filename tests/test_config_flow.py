"""Test the GUDE PDU config flow."""  # codespell:ignore gude

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gude_pdu.api import (
    GudeAuthError,
    GudeClient,
    GudeConnectionError,
)
from custom_components.gude_pdu.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_HOSTNAME, MOCK_MAC, MOCK_USERNAME


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_ENTRY_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOSTNAME
    assert result["data"] == MOCK_CONFIG_ENTRY_DATA
    assert result["result"].unique_id == MOCK_MAC
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        pytest.param(
            GudeConnectionError("Connection timeout"),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            GudeAuthError("Invalid credentials"),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            Exception("Unexpected error"),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_gude_pdu_client: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test user configuration flow error handling and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch.object(GudeClient, "authenticate", side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG_ENTRY_DATA,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    # Recover from error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_ENTRY_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOSTNAME
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when device is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_ENTRY_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test re-authentication flow succeeds."""
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "new_password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


@pytest.mark.usefixtures("mock_gude_pdu_client", "mock_setup_entry")
async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-authentication flow error when invalid credentials given."""
    result = await mock_config_entry.start_reauth_flow(hass)

    with patch.object(
        GudeClient,
        "authenticate",
        side_effect=GudeAuthError("Bad credentials"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.object(
        GudeClient,
        "authenticate",
        side_effect=GudeConnectionError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: "new_password",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch.object(
        GudeClient,
        "authenticate",
        side_effect=RuntimeError("Boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: "new_password",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "new_password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguration flow succeeds after error recovery."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    for exc, expected_error in (
        (GudeAuthError("Bad auth"), "invalid_auth"),
        (GudeConnectionError("Unreachable"), "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ):
        with patch.object(GudeClient, "authenticate", side_effect=exc):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    **MOCK_CONFIG_ENTRY_DATA,
                    CONF_HOST: "192.168.1.200",
                    CONF_PORT: 8080,
                },
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **MOCK_CONFIG_ENTRY_DATA,
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 8080,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.data[CONF_PORT] == 8080


async def test_reconfigure_flow_different_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    epc8291_fixture: dict[str, Any],
) -> None:
    """Test reconfiguration flow aborts if different device MAC is detected."""
    result = await mock_config_entry.start_reconfigure_flow(hass)

    # Return fixture of EPC 8291 which has a different MAC address
    with patch.object(GudeClient, "_request", return_value=epc8291_fixture):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **MOCK_CONFIG_ENTRY_DATA,
                CONF_HOST: "192.168.1.200",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"
