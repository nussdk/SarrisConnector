#!/usr/bin/env python3
"""Enumerate BLE services/characteristics of the Saris M2 trainer.

Run this on the machine with the BLE radio next to the trainer. It scans for devices,
connects to anything matching the name filter (or a fixed --address), dumps the GATT
service tree and readable values, and writes a timestamped JSON report to out/.

Usage:
    python tools/scan_trainer.py
    python tools/scan_trainer.py --address AA:BB:CC:DD:EE:FF
    python tools/scan_trainer.py --all --scan-seconds 15
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("bleak is required: pip install -r requirements.txt")

DEFAULT_NAME_PARTS = ("saris", "m2", "cycleops", "smart trainer")


def _jsonable(value):
    """Turn advertisement metadata into JSON-serialisable values."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def advertisement_info(device) -> dict:
    info: dict = {}
    metadata = getattr(device, "metadata", None)
    if isinstance(metadata, dict):
        info["metadata"] = _jsonable(metadata)
    details = getattr(device, "details", None)
    if details is not None:
        info["details"] = _jsonable(getattr(details, "props", details))
    return info


async def dump_device(device, out_dir: Path, connect_timeout: float) -> dict:
    report: dict = {
        "address": device.address,
        "name": device.name,
        "advertisement": advertisement_info(device),
    }
    try:
        async with BleakClient(device, timeout=connect_timeout) as client:
            services = client.services
            dump = []
            for service in services:
                chars = []
                for char in service.characteristics:
                    entry = {
                        "uuid": str(char.uuid),
                        "properties": sorted(str(p) for p in char.properties),
                        "descriptors": [str(d.uuid) for d in char.descriptors],
                    }
                    if "read" in char.properties:
                        try:
                            value = await client.read_gatt_char(char)
                            entry["value_hex"] = value.hex()
                        except Exception as exc:  # pairing/permissions vary by OS
                            entry["read_error"] = f"{type(exc).__name__}: {exc}"
                    chars.append(entry)
                dump.append({"uuid": str(service.uuid), "characteristics": chars})
            report["services"] = dump
    except Exception as exc:
        report["connect_error"] = f"{type(exc).__name__}: {exc}"

    target = out_dir / f"ble_{device.address.replace(':', '-')}.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["_report_path"] = str(target)
    return report


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", help="connect directly to this BLE address")
    parser.add_argument("--all", action="store_true", help="dump every discovered device")
    parser.add_argument("--scan-seconds", type=float, default=10.0)
    parser.add_argument("--connect-timeout", type=float, default=15.0)
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    if args.address:
        print(f"Looking for {args.address} ...")
        device = await BleakScanner.find_device_by_address(
            args.address, timeout=args.scan_seconds
        )
        if device is None:
            sys.exit(f"Device {args.address} not found")
        devices = [device]
    else:
        print(f"Scanning for {args.scan_seconds:g}s ...")
        devices = await BleakScanner.discover(timeout=args.scan_seconds)
        print(f"Found {len(devices)} device(s)")
        if not args.all:
            devices = [
                d
                for d in devices
                if any(part in (d.name or "").lower() for part in DEFAULT_NAME_PARTS)
            ]
            print(f"Filtered to {len(devices)} likely trainer(s)")

    if not devices:
        sys.exit("No matching devices; try --all or --address")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    combined = {"captured_at": stamp, "devices": []}
    for device in devices:
        print(f"\nDumping {device.address} ({device.name}) ...")
        report = await dump_device(device, args.out, args.connect_timeout)
        if "connect_error" in report:
            print(f"  connect failed: {report['connect_error']}")
            continue
        for service in report.get("services", []):
            print(f"  {service['uuid']}")
            for char in service["characteristics"]:
                print(f"    {char['uuid']} {','.join(char['properties'])}")
        combined["devices"].append(report)
        print(f"  saved: {report['_report_path']}")

    combined_path = args.out / f"ble_scan_{stamp}.json"
    combined_path.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    print(f"\nCombined report: {combined_path}")


if __name__ == "__main__":
    asyncio.run(main())
