"""Constants for the GUDE PDU integration."""  # codespell:ignore gude

import logging
from typing import Final

DOMAIN: Final = "gude_pdu"
LOGGER: Final = logging.getLogger(__package__)

DEFAULT_NAME: Final = "GUDE PDU"  # codespell:ignore gude
DEFAULT_PORT: Final = 80
DEFAULT_SSL_PORT: Final = 443
DEFAULT_SSL: Final = False
DEFAULT_VERIFY_SSL: Final = False

DEFAULT_SCAN_INTERVAL: Final = 30
# Bitmask: outputs (1) + ethernet (8) + misc (16)
# + sensor_values (16384) + sensor_descr (65536) + extended (8388608)
COMPONENTS_ALL: Final = 8470553
