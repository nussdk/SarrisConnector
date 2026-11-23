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
| `protocol.py` | Done — FTMS op codes + ANT+ FE-C constants + FTMS Indoor Bike Data (0x2AD2) payload builder |
| `translator.py` | Done — FTMS → ANT+ FE-C intent (grade / target power / resistance), unit-tested |
| `virtual_shifting.py` | **Done** — gear ratio → ANT+ FE-C resistance/grade/power, ported from SHIFTR's `Calculations.cpp` (gravity + rolling + drag × relative gear ratio) |
| `ant_master.py` | Done — wraps `openant.devices.fitness_equipment.FitnessEquipment`; sends `set_target_power` / `set_basic_resistance` to the M2 via ANT+ stick. **Now also parses incoming ANT+ data pages** (power/cadence/speed) via `data_callback` and tracks `last_data_time` for ANT+ connectivity heartbeat (`ant_stale` property). Needs hardware to test. |
| `ble_server.py` | **Done (WinRT backend)** — hosts the FTMS GATT service and advertises as a BLE trainer peripheral via WinRT `GattServiceProvider` + `BluetoothLEAdvertisementPublisher`. Control-point writes from MyWhoosh flow to `handle_control_write` → translator → ANT+ master. **Gear ratio writes** on the Zwift custom service characteristic (0x00000002) flow to `handle_gear_ratio_write` → bridge → VirtualShifter → ANT+ master. `notify_indoor_bike_data` sends trainer data back to MyWhoosh; WinRT CCCD setup / characteristic lookup needs validation on the Windows host. |
| `bridge.py` | Done — wires BLE command → translator → ANT+ master **and** ANT+ trainer data → BLE notify to MyWhoosh **and** MyWhoosh gear ratio → VirtualShifter → ANT+ master |
| `__main__.py` | Done — `python -m sarris_connector` entry point |

## Data flow

```
Command path:  MyWhoosh (BLE FTMS writes: grade, target power)
                  -> bridge -> translator -> ANT+ FE-C -> M2
               MyWhoosh (BLE gear ratio on Zwift custom service 0x00000002)
                  -> bridge -> VirtualShifter -> ANT+ FE-C -> M2
Data path:     M2 (ANT+ data pages: power/cadence/speed)
                  -> ant_master data callback -> bridge -> BLE notify (0x2AD2) -> MyWhoosh
```

Gear signal: MyWhoosh writes a gear ratio (float, 0.75–5.49) to the BLE characteristic
`00000002-19CA-4651-86E5-FA29DCDD09D1` on service `00000001-19CA-4651-86E5-FA29DCDD09D1`.
The `BleTrainerServer.handle_gear_ratio_write()` dispatches it to
`TrainerBridge._on_gear_ratio()` → `VirtualShifter.set_gear_ratio()` → `AntMaster.apply()`.

Heartbeat: `AntMaster.last_data_time` is updated on every ANT+ data page; `ant_stale` is `True` if no data page has arrived for >5 seconds.

## Virtual shifting

MyWhoosh sends a selected gear ratio (0.75–5.49). The `VirtualShifter` calculates the total resistance force (gravity + rolling + drag) at the current grade/speed, applies the relative gear ratio (selected ÷ default 34/14), and outputs one of three ANT+ FE-C action types:

- `basic_resistance` → `set_basic_resistance` (0–100%)
- `track_resistance` → equivalent grade → `set_basic_resistance` placeholder
- `target_power` → calculated watts → `set_target_power`

Mode is configurable via `VirtualShifter(mode=...)`. Gear index (0–23) maps to the Zwift gear ratio table.



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
