"""Constants for GUDE PDU tests."""  # codespell:ignore gude

from custom_components.gude_pdu.const import (
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MOCK_HOST = "192.168.1.100"
MOCK_MAC = "00:19:32:01:a3:3e"
MOCK_PRODUCT_NAME = "Expert Power Control 8041-1"
MOCK_HOSTNAME = "epc8041"
MOCK_USERNAME = "admin"
MOCK_PASSWORD = "secret_password"

MOCK_CONFIG_ENTRY_DATA = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}
