"""Test the GUDE PDU data update coordinator."""  # codespell:ignore gude

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.gude_pdu.api import (
    GudeAuthError,
    GudeClient,
    GudeConnectionError,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util.dt import utcnow


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_coordinator_update_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator updates data successfully."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True

    # Advance time to trigger next scheduled update
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_coordinator_update_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator handles connection failure during update."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    with patch.object(
        GudeClient,
        "_request",
        side_effect=GudeConnectionError("Connection lost"),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=35))
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_coordinator_auth_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    with (
        patch.object(
            GudeClient,
            "_request",
            side_effect=GudeAuthError("Unauthorized"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()
