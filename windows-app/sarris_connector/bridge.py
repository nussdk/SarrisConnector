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
from .translator import FtmsCommand, FtmsToAntTranslator

logger = logging.getLogger("sarris_connector.bridge")


class TrainerBridge:
    """Orchestrates BLE <-> ANT+ translation for the Saris M2."""

    def __init__(self) -> None:
        self._translator = FtmsToAntTranslator()
        self._ble = BleTrainerServer(on_command=self._on_ftms_command)
        self._ant = AntMaster()
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
