"""Test GUDE PDU integration initialization and unloading."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gude_pdu.api import (
    GudeAuthError,
    GudeClient,
    GudeConnectionError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup and unload of GUDE PDU config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator.data is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gude_pdu_client: AsyncMock,
) -> None:
    """Test setup failure due to connection error."""
    with patch.object(
        GudeClient,
        "_request",
        side_effect=GudeConnectionError("Network down"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gude_pdu_client: AsyncMock,
) -> None:
    """Test setup failure due to authentication error."""
    with patch.object(
        GudeClient,
        "_request",
        side_effect=GudeAuthError("Invalid credentials"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
