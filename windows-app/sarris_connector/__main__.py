"""CLI entry point: ``python -m sarris_connector``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from .bridge import TrainerBridge
from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sarris_connector",
        description=(
            "SarrisConnector Windows translation app: bridges MyWhoosh (BLE FTMS) "
            "to the Saris M2 trainer (ANT+ FE-C)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging level (default: INFO)",
    )
    parser.add_argument(
        "--device-name",
        default="SarrisConnector",
        help="BLE device name advertised to MyWhoosh (default: SarrisConnector)",
    )
    return parser


async def _run(bridge: TrainerBridge) -> None:
    await bridge.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows: add_signal_handler not supported on all loops; rely on
            # KeyboardInterrupt below.
            pass

    try:
        await stop_event.wait()
    finally:
        await bridge.stop()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bridge = TrainerBridge()

    try:
        asyncio.run(_run(bridge))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
