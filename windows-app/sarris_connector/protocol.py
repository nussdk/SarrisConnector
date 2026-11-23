"""Protocol constants for FTMS (BLE) and ANT+ FE-C.

FTMS: Bluetooth Fitness Machine Service — what MyWhoosh sends over BLE.
ANT+ FE-C: Fitness Equipment Control — what the Saris M2 accepts from Garmin.

FTMS values come from the official FTMS 1.0 spec.
ANT+ FE-C page numbers/payloads are placeholders pending Phase-1 capture
from a Garmin -> M2 link (see TODO.md).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# BLE FTMS (Bluetooth Fitness Machine Service)
# ---------------------------------------------------------------------------

FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
FTMS_CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"
FTMS_FEATURE_UUID = "00002acc-0000-1000-8000-00805f9b34fb"
FTMS_INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
FTMS_STATUS_UUID = "00002ada-0000-1000-8000-00805f9b34fb"

# Fitness Machine Control Point op codes (write to 0x2AD9)
FTMS_OP_REQUEST_CONTROL = 0x00
FTMS_OP_SET_TARGET_RESISTANCE = 0x04
FTMS_OP_SET_TARGET_POWER = 0x05
FTMS_OP_START_RESUME = 0x07
FTMS_OP_STOP_PAUSE = 0x08
FTMS_OP_SET_SIMULATION_PARAMS = 0x11
FTMS_OP_RESPONSE_PREFIX = 0x80

# Response codes
FTMS_RSP_SUCCESS = 0x01
FTMS_RSP_NOT_SUPPORTED = 0x02
FTMS_RSP_INVALID_PARAM = 0x03
FTMS_RSP_OP_FAILED = 0x04
FTMS_RSP_CONTROL_NOT_PERMITTED = 0x05

# FTMS "Set Indoor Bike Simulation Parameters" target-setting bitfield bits
FTMS_SIM_TARGET_WIND_SPEED = 0x01
FTMS_SIM_TARGET_GRADE = 0x02
FTMS_SIM_TARGET_CRR = 0x04
FTMS_SIM_TARGET_CWR = 0x08
FTMS_SIM_TARGET_POWER = 0x10

# ---------------------------------------------------------------------------
# ANT+ FE-C (Fitness Equipment Control)
# ---------------------------------------------------------------------------

# ANT+ network key (public, well-known)
ANT_NETWORK_KEY = bytes([0xB9, 0xA5, 0x21, 0xFB, 0xBD, 0x72, 0xC3, 0x45])

# ANT+ device type: 17 = Fitness Equipment (same device class as a Garmin watch)
ANT_DEVICE_TYPE_FITNESS_EQUIPMENT = 17
ANT_CHANNEL_PERIOD = 8192  # ~4 Hz
ANT_RF_FREQUENCY = 57  # ANT+ default RF frequency
