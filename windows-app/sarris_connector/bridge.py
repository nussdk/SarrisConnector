"""Bridge: connects the BLE trainer server to the ANT+ master via the translator.

Flow:

    MyWhoosh (BLE FTMS writes)
        -> BleTrainerServer.on_command
        -> FtmsToAntTranslator.translate
        -> AntMaster.apply (ANT+ FE-C to the real M2)

Trainer data (ANT+) flows back:
    (not yet wired) AntMaster data callback
        -> BleTrainerServer.notify_indoor_bike_data (BLE notify to MyWhoosh)
"""

from __future__ import annotations

import asyncio
import logging

from .ant_master import AntMaster
from .ble_server import BleTrainerServer
from .protocol import build_indoor_bike_data
from .translator import FtmsCommand, FtmsToAntTranslator
from .virtual_shifting import VirtualShifter, VirtualShiftingMode

logger = logging.getLogger("sarris_connector.bridge")


class TrainerBridge:
    """Orchestrates BLE <-> ANT+ translation for the Saris M2.

    Command path (MyWhoosh -> M2):

        MyWhoosh (BLE FTMS writes: grade, target power)
            -> BleTrainerServer.on_command
            -> FtmsToAntTranslator.translate
            -> AntMaster.apply (ANT+ FE-C to the real M2)

        MyWhoosh (virtual shifting: gear ratio selection)
            -> TrainerBridge.set_gear_ratio
            -> VirtualShifter.set_gear_ratio
            -> AntMaster.apply (ANT+ FE-C to the real M2)

    Data path (M2 -> MyWhoosh):

        M2 (ANT+ data pages)
            -> AntMaster data callback
            -> TrainerBridge._on_ant_data
            -> BleTrainerServer.notify_indoor_bike_data (BLE notify)
            -> TrainerBridge updates VirtualShifter telemetry
    """

    def __init__(self) -> None:
        self._translator = FtmsToAntTranslator()
        self._shifter = VirtualShifter(mode=VirtualShiftingMode.BASIC_RESISTANCE)
        self._ble = BleTrainerServer(
            on_command=self._on_ftms_command,
            on_gear_ratio=self._on_gear_ratio,
        )
        self._ant = AntMaster(data_callback=self._on_ant_data)
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._ant.start()
        await self._ble.start()
        self._ble.build_services()
        self._running = True
        logger.info("Trainer bridge started")

    async def stop(self) -> None:
        if not self._running:
            return
        await self._ble.stop()
        self._ant.stop()
        self._running = False
        logger.info("Trainer bridge stopped")

    # ------------------------------------------------------------------
    # Command path: BLE FTMS -> ANT+ FE-C
    # ------------------------------------------------------------------

    def _on_ftms_command(self, command) -> None:  # noqa: ANN001
        """Handle a FTMS command from MyWhoosh: translate and apply over ANT+."""
        fc = FtmsCommand(op_code=command.op_code, params=bytes(command.params))

        try:
            actions = self._translator.translate(fc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Translation failed for op %#04x: %s", fc.op_code, exc)
            return

        for action in actions:
            self._ant.apply(action)
            logger.info(
                "Translated FTMS op %#04x -> ANT+ action %s=%s",
                fc.op_code,
                action.kind,
                action.value,
            )

        # Feed FTMS simulation grade into the virtual shifter's telemetry.
        from .protocol import FTMS_OP_SET_SIMULATION_PARAMS, FTMS_SIM_TARGET_GRADE

        if fc.op_code == FTMS_OP_SET_SIMULATION_PARAMS and len(fc.params) >= 5:
            bitfield = fc.params[0]
            if bitfield & FTMS_SIM_TARGET_GRADE:
                grade_raw = int.from_bytes(fc.params[3:5], "little", signed=True)
                self._shifter.update_grade(grade_raw / 100.0)

    # ------------------------------------------------------------------
    # Virtual shifting: MyWhoosh gear selection -> ANT+ FE-C
    # ------------------------------------------------------------------

    def set_gear_ratio(self, gear_ratio: float) -> None:
        """MyWhoosh selected a gear ratio. Translate and apply over ANT+."""
        try:
            actions = self._shifter.set_gear_ratio(gear_ratio)
        except Exception as exc:  # noqa: BLE001
            logger.error("Virtual shifting failed for ratio %s: %s", gear_ratio, exc)
            return

        for action in actions:
            self._ant.apply(action)
            logger.info(
                "Virtual shift ratio=%.4f -> ANT+ action %s=%s",
                gear_ratio,
                action.kind,
                action.value,
            )

    def set_gear_index(self, gear_index: int) -> None:
        """MyWhoosh selected a zero-based gear index. Translate and apply over ANT+."""
        ratio = self._shifter.gear_for_index(gear_index)
        if ratio is None:
            logger.warning("Invalid gear index: %d", gear_index)
            return
        self.set_gear_ratio(ratio)

    def _on_gear_ratio(self, gear_ratio: float) -> None:
        """Callback invoked by the BLE server when MyWhoosh writes a gear ratio."""
        self.set_gear_ratio(gear_ratio)

    # ------------------------------------------------------------------
    # Data path: ANT+ trainer data -> BLE notify to MyWhoosh
    # ------------------------------------------------------------------

    def _on_ant_data(
        self,
        *,
        page: int,
        page_name: str,
        power_w,
        cadence_rpm,
        speed_kmh,
    ) -> None:
        """Forward ANT+ trainer telemetry to MyWhoosh over BLE notify."""
        # Only notify when we have usable telemetry.
        if power_w is None and cadence_rpm is None and speed_kmh is None:
            return

        # Feed live telemetry to the virtual shifter.
        if speed_kmh is not None:
            self._shifter.update_speed(speed_kmh / 3.6)  # km/h -> m/s
        if cadence_rpm is not None:
            self._shifter.update_cadence(cadence_rpm)

        payload = build_indoor_bike_data(
            power_w=power_w if power_w is not None else 0,
            cadence_rpm=cadence_rpm if cadence_rpm is not None else 0,
        )
        self._ble.notify_indoor_bike_data(payload)
        logger.debug(
            "ANT+ -> BLE notify: page=%s (%s) power=%s W cadence=%s rpm speed=%s km/h",
            page,
            page_name,
            power_w,
            cadence_rpm,
            speed_kmh,
        )
