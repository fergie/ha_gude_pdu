"""Common fixtures for the GUDE PDU tests."""  # codespell:ignore gude

from collections.abc import Generator
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    load_json_object_fixture,
)

from custom_components.gude_pdu.api import GudeClient
from custom_components.gude_pdu.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_MAC


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable custom integrations in all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.gude_pdu.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock PDU config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        unique_id=MOCK_MAC,
        title="epc8041",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def epc8041_fixture() -> dict[str, Any]:
    """Load the EPC 8041 JSON fixture."""
    return cast("dict[str, Any]", load_json_object_fixture("status_epc8041.json"))


@pytest.fixture
def epc8291_fixture() -> dict[str, Any]:
    """Load the EPC 8291 JSON fixture."""
    return cast("dict[str, Any]", load_json_object_fixture("status_epc8291.json"))


@pytest.fixture
def mock_gude_pdu_client(epc8041_fixture: dict[str, Any]) -> Generator[AsyncMock]:
    """Mock GudeClient._request returning realistic fixture data."""
    with patch.object(
        GudeClient,
        "_request",
        return_value=epc8041_fixture,
    ) as mock_req:
        yield mock_req
