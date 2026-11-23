"""ANT+ master: send FE-C control to the Saris M2 via an ANT+ USB stick.

Uses :mod:`openant`'s ``FitnessEquipment`` device, which is the same FE-C
device type a Garmin watch uses to control the M2. That path is proven to
drive gradient/resistance on this trainer.

Actions:

  * ``target_power`` W  -> ``FitnessEquipment.set_target_power`` (ANT+ page 0x31)
  * ``resistance`` %    -> ``FitnessEquipment.set_basic_resistance`` (page 0x30)
  * ``grade`` %         -> logged; openant's FitnessEquipment doesn't expose a
    dedicated grade page, so grade is translated to an equivalent resistance
    placeholder until a raw page 0x11 can be sent (Phase-1 capture pending).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from openant.easy.node import Node
from openant.devices.fitness_equipment import FitnessEquipment

from .protocol import ANT_NETWORK_KEY
from .translator import TranslationAction

logger = logging.getLogger("sarris_connector.ant")


class AntMaster:
    """Send ANT+ FE-C control to a paired trainer.

    Wraps ``openant.devices.fitness_equipment.FitnessEquipment``. The ANT+
    node runs on its own thread; action application is serialized with a lock.
    """

    def __init__(self) -> None:
        self._node: Optional[Node] = None
        self._fe: Optional[FitnessEquipment] = None
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise the ANT+ node and open a Fitness Equipment channel."""
        if self._started:
            return
        self._node = Node()
        self._node.set_network_key(0x00, ANT_NETWORK_KEY)

        # Device type 17 = Fitness Equipment (same as a Garmin watch).
        self._fe = FitnessEquipment(self._node, device_id=0)

        self._thread = threading.Thread(target=self._node.start, daemon=True)
        self._thread.start()
        self._started = True
        logger.info("ANT+ node started (Fitness Equipment master)")

    def stop(self) -> None:
        """Stop the ANT+ node and release the channel."""
        if not self._started:
            return
        try:
            if self._node is not None:
                self._node.stop()
        finally:
            self._started = False
            self._node = None
            self._fe = None
            self._thread = None
            logger.info("ANT+ node stopped")

    # ------------------------------------------------------------------
    # Applying translated actions
    # ------------------------------------------------------------------

    def apply(self, action: TranslationAction) -> None:
        """Apply one translated ANT+ FE-C action to the trainer."""
        if not self._started or self._fe is None:
            logger.warning("ANT+ not started; dropping action %s", action.kind)
            return

        kind = action.kind
        value = action.value

        with self._lock:
            try:
                if kind == "target_power":
                    watts = max(0, min(4000, int(value)))
                    self._fe.set_target_power(watts)
                    logger.info("ANT+ set_target_power %d W", watts)
                elif kind == "resistance":
                    pct = max(0.0, min(100.0, float(value)))
                    self._fe.set_basic_resistance(pct)
                    logger.info("ANT+ set_basic_resistance %.1f%%", pct)
                elif kind == "grade":
                    # Placeholder: openant FE exposes power/resistance, not
                    # grade directly. Map grade to an approximate resistance
                    # until raw page 0x11 can be sent (Phase-1 capture).
                    approx_pct = max(0.0, min(100.0, abs(float(value)) * 4.0))
                    self._fe.set_basic_resistance(approx_pct)
                    logger.info(
                        "ANT+ grade %.2f%% -> approx resistance %.1f%% (placeholder)",
                        float(value),
                        approx_pct,
                    )
                else:
                    logger.warning("Unknown ANT+ action kind: %s", kind)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to apply ANT+ action %s: %s", kind, exc)
