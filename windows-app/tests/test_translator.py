"""Unit tests for the FTMS -> ANT+ FE-C translator."""

from __future__ import annotations

import struct

from sarris_connector.protocol import (
    FTMS_OP_SET_SIMULATION_PARAMS,
    FTMS_OP_SET_TARGET_POWER,
    FTMS_OP_SET_TARGET_RESISTANCE,
    FTMS_SIM_TARGET_GRADE,
    FTMS_SIM_TARGET_POWER,
)
from sarris_connector.translator import FtmsCommand, FtmsToAntTranslator


def _sim_params(bitfield: int, grade_raw: int, power_w: int) -> bytes:
    return (
        bytes([bitfield])
        + struct.pack("<H", 0)  # wind speed
        + struct.pack("<h", grade_raw)  # grade
        + b"\x00\x00"  # crr, cwr
        + struct.pack("<H", power_w)  # target power
    )


def _actions_by_kind(actions):
    return {a.kind: a.value for a in actions}


def test_translate_grade_only():
    t = FtmsToAntTranslator()
    actions = t.translate(
        FtmsCommand(
            FTMS_OP_SET_SIMULATION_PARAMS,
            _sim_params(FTMS_SIM_TARGET_GRADE, 500, 0),
        )
    )
    assert _actions_by_kind(actions) == {"grade": 5.0}


def test_translate_power_only():
    t = FtmsToAntTranslator()
    actions = t.translate(FtmsCommand(FTMS_OP_SET_TARGET_POWER, struct.pack("<H", 200)))
    assert _actions_by_kind(actions) == {"target_power": 200.0}


def test_translate_grade_and_power():
    t = FtmsToAntTranslator()
    actions = t.translate(
        FtmsCommand(
            FTMS_OP_SET_SIMULATION_PARAMS,
            _sim_params(FTMS_SIM_TARGET_GRADE | FTMS_SIM_TARGET_POWER, -300, 250),
        )
    )
    assert _actions_by_kind(actions) == {"grade": -3.0, "target_power": 250.0}


def test_translate_unsupported_op_returns_empty():
    t = FtmsToAntTranslator()
    assert t.translate(FtmsCommand(0x00, b"")) == []  # request control


def test_translate_target_resistance():
    t = FtmsToAntTranslator()
    actions = t.translate(
        FtmsCommand(FTMS_OP_SET_TARGET_RESISTANCE, struct.pack("<H", 100))
    )
    assert _actions_by_kind(actions) == {"resistance": 50.0}
