# SarrisConnector

A fork of [SHIFTR](https://github.com/JuergenLeber/SHIFTR) adapted for a **Saris M2**
trainer and **MyWhoosh** on Windows.

Upstream already provides the hard parts: BLE ↔ FE-C bridging, FTMS emulation for apps
that don't speak FE-C, reverse-engineered Zwift virtual shifting, and a web config UI.
This fork adds:

1. Gradient/sim control for the M2 from MyWhoosh (ERG already works).
2. **App-driven virtual shifting with no Zwift Click/Play controller** — the app sets
   gears; the firmware exposes the shifting service and translates gear changes to
   resistance commands.
3. A small web UI extension for toggles and trainer connection settings.

## Status

Early development. [`TODO.md`](TODO.md) has the research, prototype results, and plan.
The upstream SHIFTR documentation is preserved in [`README.upstream.md`](README.upstream.md)
and [`VirtualShifting.md`](VirtualShifting.md).

## Repo layout

- `src/`, `include/`, `lib/`, `src-web/` — SHIFTR firmware and web UI (upstream structure)
- `tools/` — Python diagnostic scripts for BLE/protocol capture
- `docs/` — local protocol notes and capture guides
- `refs/` — read-only third-party reference clones (gitignored)
- `out/` — scratch captures and logs (gitignored)

## Firmware build

The firmware uses NimBLE-Arduino 2.x and builds for a generic ESP32, an ESP32-S3
DevKitC-1, and the upstream WT32-ETH01. All targets use the `min_spiffs.csv` partition
layout because NimBLE 2.x does not fit in the default 1.25 MB app partition.

```bash
pio run -e esp32dev              # generic ESP32 (default)
pio run -e esp32-s3-devkitc-1    # ESP32-S3 DevKitC-1
pio run -e wt32-eth01            # upstream board

pio run -e esp32dev -t upload    # flash
pio run -e esp32dev -t monitor   # serial console, 115200 baud
pio test -e native               # calculation unit tests
```

The web UI is at the device's IP (see serial output). It exposes gear up/down buttons
and a reconnect button on the status page, plus an **App-driven gears** toggle under
device settings.

## Diagnostic tools

Run these on the machine with the BLE radio next to the trainer (native Windows, not WSL):

```bash
pip install -r requirements.txt
python tools/scan_trainer.py --all --scan-seconds 15
```

Reports are written to `out/`. See [`docs/capture-guide.md`](docs/capture-guide.md)
for the man-in-the-middle capture steps.

## Upstream

Upstream repository: <https://github.com/JuergenLeber/SHIFTR> (GPL-3.0). This fork
keeps that license and upstream history; pull from `upstream/main` to stay current.
