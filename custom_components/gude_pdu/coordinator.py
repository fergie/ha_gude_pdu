"""DataUpdateCoordinator for the GUDE PDU integration."""  # codespell:ignore gude

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GudeAuthError,
    GudeClient,
    GudeConnectionError,
    GudeError,
    GudeStatus,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


@dataclass
class GudeData:
    """Runtime data stored in the config entry."""

    coordinator: GudeDataUpdateCoordinator
    client: GudeClient


type GudeConfigEntry = ConfigEntry[GudeData]


class GudeDataUpdateCoordinator(DataUpdateCoordinator[GudeStatus]):
    """Class to manage fetching PDU data from the device."""

    config_entry: GudeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GudeConfigEntry,
        client: GudeClient,
    ) -> None:
        """Initialise the coordinator."""
        self.client = client
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @override
    async def _async_update_data(self) -> GudeStatus:
        """Fetch status data from the device."""
        try:
            return await self.client.get_status()
        except GudeAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except (GudeConnectionError, GudeError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
