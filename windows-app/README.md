# SarrisConnector — Windows Translation App

Windows application that bridges MyWhoosh (BLE) to the Saris M2 trainer (ANT+ FE-C).

## Architecture

```
MyWhoosh (Windows PC)
    │ BLE (FTMS control point: grade, target power)
    ▼
Windows app — BLE GATT server (virtual trainer peripheral)   [STUB — see below]
    │ translate: FTMS op codes → ANT+ FE-C
    ▼
ANT+ USB stick → Saris M2 (FE-C gradient/resistance control)

Trainer data (power/cadence/speed) flows back over ANT+ → app → BLE → MyWhoosh
```

## Why Windows app instead of ESP32

- MyWhoosh runs on the Windows PC, which already has BLE + ANT+ radios.
- The M2 responds to ANT+ FE-C commands from a Garmin watch — proven working.
- MyWhoosh's own BLE commands don't drive gradient on the M2.
- A Windows app can sit between them: present a virtual BLE trainer to MyWhoosh,
  translate its commands into ANT+ FE-C, and send to the real M2 via an ANT+ stick.

## Current state

| Module | Status |
|--------|--------|
| `protocol.py` | Done — FTMS op codes + ANT+ FE-C constants |
| `translator.py` | Done — FTMS → ANT+ FE-C intent (grade / target power / resistance), unit-tested |
| `ant_master.py` | Done — wraps `openant.devices.fitness_equipment.FitnessEquipment`; sends `set_target_power` / `set_basic_resistance` to the M2 via ANT+ stick (needs hardware to test) |
| `ble_server.py` | **Done (WinRT backend)** — hosts the FTMS GATT service and advertises as a BLE trainer peripheral via WinRT `GattServiceProvider` + `BluetoothLEAdvertisementPublisher`. Control-point writes from MyWhoosh flow to `handle_control_write` → translator → ANT+ master. Written against the `winrt` API; **validate on the Windows host** (characteristic registration / notify path not testable on this Linux box). |
| `bridge.py` | Done — wires BLE command → translator → ANT+ master |
| `__main__.py` | Done — `python -m sarris_connector` entry point |

Running the app starts the ANT+ node and hosts the FTMS BLE service via the
WinRT backend. The BLE-server path is implemented but **untested on Windows**
(written on Linux, where `winrt` is unavailable); validate it on the Windows
host with the M2 hardware before relying on end-to-end control.

## Run

```bash
cd windows-app
# runtime deps
python -m venv .venv
.venv/bin/pip install -r requirements.txt
# run (will hit the BLE-server stub until implemented)
python -m sarris_connector
```

### Tests

```bash
.venv/bin/pip install pytest   # dev dep
.venv/bin/python -m pytest
```

## Requirements

- Runtime: `bleak`, `openant`, `pyusb`
- Dev: `pytest`

## Notes

- ANT+ FE-C page payload layouts (grade page 0x11, etc.) are placeholders
  pending Phase-1 capture from a Garmin → M2 link. `openant`'s
  `FitnessEquipment.set_target_power` (page 0x31) and `set_basic_resistance`
  (page 0x30) are used directly and are the proven-working commands.
- The ESP32 NimBLE 2.x firmware migration is paused on a stash (`git stash
  list`) and the work lives on the `feature/windows-connector` branch, to be
  merged to `main` when complete.
