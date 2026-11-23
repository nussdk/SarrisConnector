"""Unit tests for the virtual shifting engine."""

from __future__ import annotations

from sarris_connector.translator import TranslationAction
from sarris_connector.virtual_shifting import (
    DEFAULT_GEAR_RATIO,
    VirtualShifter,
    VirtualShiftingMode,
    ZWIFT_GEAR_RATIOS,
)


def test_default_gear_ratio():
    assert abs(DEFAULT_GEAR_RATIO - (34.0 / 14.0)) < 0.0001


def test_gear_ratios_sorted():
    assert ZWIFT_GEAR_RATIOS == sorted(ZWIFT_GEAR_RATIOS)
    assert len(ZWIFT_GEAR_RATIOS) == 24


def test_gear_index_mapping():
    shifter = VirtualShifter()
    assert shifter.gear_for_index(0) == 0.75
    assert shifter.gear_for_index(11) == 2.40
    assert shifter.gear_for_index(23) == 5.49
    assert shifter.gear_for_index(-1) is None
    assert shifter.gear_for_index(100) is None


def test_basic_resistance_grade_5pct():
    shifter = VirtualShifter(mode=VirtualShiftingMode.BASIC_RESISTANCE)
    shifter.update_grade(5.0)
    shifter.update_cadence(80.0)
    actions = shifter.set_gear_ratio(2.40)
    assert len(actions) == 1
    assert actions[0].kind == "resistance"
    assert 0.0 <= actions[0].value <= 100.0


def test_track_resistance_mode():
    shifter = VirtualShifter(mode=VirtualShiftingMode.TRACK_RESISTANCE)
    shifter.update_grade(5.0)
    shifter.update_cadence(80.0)
    actions = shifter.set_gear_ratio(2.40)
    assert len(actions) == 1
    assert actions[0].kind == "grade"


def test_target_power_mode():
    shifter = VirtualShifter(mode=VirtualShiftingMode.TARGET_POWER)
    shifter.update_grade(5.0)
    shifter.update_cadence(80.0)
    actions = shifter.set_gear_ratio(2.40)
    assert len(actions) == 1
    assert actions[0].kind == "target_power"
    assert actions[0].value >= 0.0


def test_negative_force_clamps_to_zero_resistance():
    # Downhill (-10% grade) should clamp resistance to 0%
    shifter = VirtualShifter(mode=VirtualShiftingMode.BASIC_RESISTANCE)
    shifter.update_grade(-10.0)
    shifter.update_cadence(80.0)
    actions = shifter.set_gear_ratio(2.40)
    assert actions[0].kind == "resistance"
    assert actions[0].value == 0.0
