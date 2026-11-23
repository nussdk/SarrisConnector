"""Unit tests for the gear signal path (BLE gear ratio -> VirtualShifter)."""

from __future__ import annotations

from sarris_connector.ble_server import BleTrainerServer
from sarris_connector.bridge import TrainerBridge
from sarris_connector.translator import TranslationAction
from sarris_connector.virtual_shifting import VirtualShiftingMode


def test_ble_server_gear_ratio_callback():
    """BleTrainerServer.handle_gear_ratio_write invokes on_gear_ratio callback."""
    received = []

    def cb(ratio: float) -> None:
        received.append(ratio)

    server = BleTrainerServer(on_gear_ratio=cb)
    server.handle_gear_ratio_write(2.40)
    assert received == [2.40]


def test_ble_server_gear_ratio_no_callback():
    """No crash when on_gear_ratio is not set."""
    server = BleTrainerServer()
    server.handle_gear_ratio_write(2.40)  # should not raise


def test_bridge_on_gear_ratio_calls_shifter():
    """TrainerBridge._on_gear_ratio delegates to set_gear_ratio."""
    bridge = TrainerBridge()
    # Replace shifter with one in basic resistance mode for deterministic output
    bridge._shifter.mode = VirtualShiftingMode.BASIC_RESISTANCE
    bridge._shifter.update_grade(0.0)
    bridge._shifter.update_cadence(0.0)

    # Capture actions applied to AntMaster
    applied = []
    orig_apply = bridge._ant.apply
    bridge._ant.apply = lambda action: applied.append(action)  # type: ignore

    bridge._on_gear_ratio(2.40)
    assert len(applied) == 1
    assert applied[0].kind == "resistance"

    bridge._ant.apply = orig_apply


def test_bridge_set_gear_ratio_via_callback():
    """End-to-end: gear ratio callback -> resistance action on AntMaster."""
    bridge = TrainerBridge()
    bridge._shifter.mode = VirtualShiftingMode.BASIC_RESISTANCE
    bridge._shifter.update_grade(5.0)
    bridge._shifter.update_cadence(80.0)

    applied = []
    orig_apply = bridge._ant.apply
    bridge._ant.apply = lambda action: applied.append(action)  # type: ignore

    bridge._on_gear_ratio(2.40)

    assert len(applied) == 1
    assert applied[0].kind == "resistance"
    assert 0.0 <= applied[0].value <= 100.0

    bridge._ant.apply = orig_apply


def test_bridge_set_gear_index_via_callback():
    """Gear index callback maps to a valid ratio and applies resistance."""
    bridge = TrainerBridge()
    bridge._shifter.mode = VirtualShiftingMode.BASIC_RESISTANCE
    bridge._shifter.update_grade(0.0)
    bridge._shifter.update_cadence(0.0)

    applied = []
    orig_apply = bridge._ant.apply
    bridge._ant.apply = lambda action: applied.append(action)  # type: ignore

    bridge.set_gear_index(11)  # ratio 2.40

    assert len(applied) == 1
    assert applied[0].kind == "resistance"

    bridge._ant.apply = orig_apply
