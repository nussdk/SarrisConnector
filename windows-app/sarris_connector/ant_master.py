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

Data path (M2 -> MyWhoosh):

  * openant parses ANT+ data pages (0x19 power, 0x1A torque, 0x10 general FE)
    into :class:`PowerData` / :class:`FitnessEquipmentData` objects.
  * A data callback forwards those to the BLE layer, which notifies MyWhoosh
    on the FTMS Indoor Bike Data characteristic (0x2AD2).
  * ``last_data_time`` tracks the most recent ANT+ data page for connectivity
    heartbeat / stale-channel detection.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from openant.easy.node import Node
from openant.devices.fitness_equipment import FitnessEquipment
from openant.devices.common import DeviceData

from .protocol import ANT_NETWORK_KEY
from .translator import TranslationAction

logger = logging.getLogger("sarris_connector.ant")


class AntFitnessEquipment(FitnessEquipment):
    """FitnessEquipment that forwards parsed ANT+ data pages to a callback."""

    def __init__(self, node: Node, device_id: int, data_callback: Callable) -> None:
        super().__init__(node, device_id=device_id)
        self._data_callback = data_callback

    def on_device_data(self, page: int, page_name: str, data: DeviceData) -> None:
        """openant calls this for every parsed ANT+ data page."""
        try:
            self._data_callback(page, page_name, data)
        except Exception as exc:  # noqa: BLE001
            logger.error("ANT+ data callback failed: %s", exc)
        super().on_device_data(page, page_name, data)


class AntMaster:
    """Send ANT+ FE-C control to a paired trainer.

    Wraps ``openant.devices.fitness_equipment.FitnessEquipment``. The ANT+
    node runs on its own thread; action application is serialized with a lock.

    :param data_callback: invoked with ``(page, page_name, data)`` for each
        parsed ANT+ data page received from the trainer (power/cadence/speed).
    """

    def __init__(self, data_callback: Optional[Callable] = None) -> None:
        self._node: Optional[Node] = None
        self._fe: Optional[AntFitnessEquipment] = None
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._lock = threading.Lock()
        self._data_callback = data_callback
        # Heartbeat: wall-clock time of the last ANT+ data page received.
        self.last_data_time: Optional[float] = None

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
        self._fe = AntFitnessEquipment(
            self._node, device_id=0, data_callback=self._on_ant_data
        )

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
    # ANT+ data handling (trainer data -> connector)
    # ------------------------------------------------------------------

    def _on_ant_data(self, page: int, page_name: str, data: DeviceData) -> None:
        """Internal handler for parsed ANT+ data pages from the M2."""
        self.last_data_time = time.time()

        # Extract the most useful telemetry for MyWhoosh.
        power_w: Optional[float] = None
        cadence_rpm: Optional[float] = None
        speed_kmh: Optional[float] = None

        if hasattr(data, "instantaneous_power"):
            power_w = float(data.instantaneous_power)
        if hasattr(data, "cadence"):
            cadence_rpm = float(data.cadence)
        if hasattr(data, "speed"):
            speed_kmh = float(data.speed)

        if self._data_callback is not None:
            try:
                self._data_callback(
                    page=page,
                    page_name=page_name,
                    power_w=power_w,
                    cadence_rpm=cadence_rpm,
                    speed_kmh=speed_kmh,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("User data callback failed: %s", exc)

        logger.debug(
            "ANT+ page %s (%s): power=%s W cadence=%s rpm speed=%s km/h",
            page,
            page_name,
            power_w,
            cadence_rpm,
            speed_kmh,
        )

    @property
    def ant_stale(self) -> bool:
        """True if no ANT+ data page has been received for >5 seconds."""
        if self.last_data_time is None:
            return True
        return (time.time() - self.last_data_time) > 5.0

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
