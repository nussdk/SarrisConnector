"""Translation layer: FTMS control-point commands -> ANT+ FE-C intents.

MyWhoosh sends FTMS control-point writes over BLE to what it thinks is a
trainer. This module translates those into semantic ANT+ FE-C intents that the
:class:`AntMaster` sends to the real Saris M2 (proven working via Garmin watch).

Each intent is a :class:`TranslationAction` describing *what* to do, not the
raw ANT+ byte layout. Page payload layouts vary by trainer/firmware and are
handled by :mod:`openant`'s ``FitnessEquipment`` device.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .protocol import (
    FTMS_OP_SET_SIMULATION_PARAMS,
    FTMS_OP_SET_TARGET_POWER,
    FTMS_OP_SET_TARGET_RESISTANCE,
    FTMS_SIM_TARGET_GRADE,
    FTMS_SIM_TARGET_POWER,
)


@dataclass
class TranslationAction:
    """A single ANT+ FE-C action to apply to the real trainer."""

    kind: str  # "grade" | "target_power" | "resistance"
    value: float


class TranslationError(Exception):
    """Raised when an FTMS command cannot be translated."""


@dataclass
class FtmsCommand:
    """A parsed FTMS control-point command from MyWhoosh."""

    op_code: int
    params: bytes


class FtmsToAntTranslator:
    """Translates FTMS control-point commands into ANT+ FE-C intents."""

    def __init__(self) -> None:
        self._last_grade_pct: Optional[float] = None
        self._last_target_power_w: Optional[float] = None
        self._last_resistance_pct: Optional[float] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate(self, command: FtmsCommand) -> list[TranslationAction]:
        """Translate one FTMS command into zero or more ANT+ FE-C actions."""
        op = command.op_code
        params = command.params

        if op == FTMS_OP_SET_SIMULATION_PARAMS:
            return self._translate_simulation(params)
        if op == FTMS_OP_SET_TARGET_POWER:
            return self._translate_target_power(params)
        if op == FTMS_OP_SET_TARGET_RESISTANCE:
            return self._translate_target_resistance(params)

        # Request control, start/stop, etc. — acknowledged at the BLE layer,
        # no ANT+ action needed for now.
        return []

    # ------------------------------------------------------------------
    # FTMS op code -> ANT+ FE-C intent
    # ------------------------------------------------------------------

    def _translate_simulation(self, params: bytes) -> list[TranslationAction]:
        """Set Indoor Bike Simulation Parameters (FTMS op 0x11).

        FTMS payload layout:
          [0] target-setting bitfield
          [1:3] wind speed uint16 (0.001 m/s)
          [3:5] grade int16 (0.01%)
          [5] C_rr uint8 (0.0001)
          [6] C_wr uint8 (0.001)
          [7:9] target power uint16 (W)  — present only if bit 4 set
        """
        if len(params) < 5:
            raise TranslationError(
                f"simulation params too short: {len(params)} bytes"
            )

        bitfield = params[0]
        actions: list[TranslationAction] = []

        if bitfield & FTMS_SIM_TARGET_GRADE:
            grade_raw = int.from_bytes(params[3:5], "little", signed=True)
            grade_pct = grade_raw / 100.0
            self._last_grade_pct = grade_pct
            actions.append(TranslationAction(kind="grade", value=grade_pct))

        if bitfield & FTMS_SIM_TARGET_POWER and len(params) >= 9:
            power_w = float(int.from_bytes(params[7:9], "little"))
            self._last_target_power_w = power_w
            actions.append(TranslationAction(kind="target_power", value=power_w))

        return actions

    def _translate_target_power(self, params: bytes) -> list[TranslationAction]:
        """Set Target Power (FTMS op 0x05).

        FTMS payload: target power uint16 (W), 2 bytes little-endian.
        """
        if len(params) < 2:
            raise TranslationError(
                f"target power params too short: {len(params)} bytes"
            )
        power_w = float(int.from_bytes(params[0:2], "little"))
        self._last_target_power_w = power_w
        return [TranslationAction(kind="target_power", value=power_w)]

    def _translate_target_resistance(self, params: bytes) -> list[TranslationAction]:
        """Set Target Resistance Level (FTMS op 0x04).

        FTMS payload: resistance level uint16 (0.5% units, 0-200), 2 bytes.
        """
        if len(params) < 2:
            raise TranslationError(
                f"target resistance params too short: {len(params)} bytes"
            )
        level = int.from_bytes(params[0:2], "little")
        pct = level / 2.0  # 0-200 -> 0-100 %
        self._last_resistance_pct = pct
        return [TranslationAction(kind="resistance", value=pct)]
