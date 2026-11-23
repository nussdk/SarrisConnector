# Phase 1 capture guide

Goal: answer two questions with real captures.

1. What BLE services/characteristics does the M2 actually expose?
2. Does MyWhoosh send **any** resistance/grade command, and if so, in what encoding?

## 1. BLE service scan (Windows, native — not WSL)

```powershell
pip install -r requirements.txt
python tools\scan_trainer.py --all --scan-seconds 15
```

Copy `out\ble_scan_*.json` into the repo `out/` on this machine (or paste it to me).
Look for service `0x1826` (FTMS) and its Control Point `0x2AD9`. If it is missing,
the trainer may be using a proprietary/legacy control service instead.

## 2. ESP32 man-in-the-middle log (Simcline-V2)

Reference clone is already in `refs/simcline-v2` (read-only). Do not edit it in place.

1. Install **Arduino IDE 2**, the **ESP32 board package**, and **NimBLE-Arduino 2.x**.
2. Install Simcline-V2 as a library: copy `refs/simcline-v2` to
   `~/Documents/Arduino/libraries/Simcline-V2` (or the Windows equivalent), then
   restart Arduino IDE. Edit the **copy**, not `refs/`.
3. In the copied library's `src/config/`:
   - `configBoard.h`: select `YOUR_ESP32_BOARD` (or your actual board)
   - `configDisplay.h`: `NODISPLAY` is fine
   - `configNimBLE.h`: keep `ENABLE_FTMS` and `ENABLE_CSC` enabled (defaults)
   - `configDebug.h`: `GLOBAL_DEBUG` is already enabled
4. Open `File > Examples > Simcline-V2 > Smart_MITM`, select your ESP32 board and
   port, and upload. Open Serial Monitor at **115200** baud.
5. Power on the M2. The ESP32 should scan, find the trainer, and connect. It advertises
   itself as **`SIM32`**.
6. Start MyWhoosh **after** the ESP32 has connected to the trainer. In MyWhoosh's
   pairing screen, pair `SIM32` as power / resistance / cadence.
7. Ride a route with a clear climb and descent. Keep the Serial Monitor visible and
   save the full log to `out/esp32_mitm.log`.
8. Note the grade values shown in MyWhoosh versus the grade logged by the ESP32.

If the ESP32 cannot connect using FTMS mode, stop and report that — the next thing to
try is the legacy FE-C-over-BLE mode (`ENABLE_TACXFEC` in `configNimBLE.h`), but only
after we see the BLE scan.

## 3. MyWhoosh pairing details to record

Please record these regardless of the capture result:

- MyWhoosh version and OS build
- Whether the M2 appears as **controllable trainer / resistance** or only as
  **power/cadence source**, over both BLE and ANT+
- Exact names of the pairing options shown
- Gradient Feel slider value during the test

## Why this matters

Phase 0 showed that ANT+ control in MyWhoosh does not move the trainer, even though
the Garmin does. Two possibilities remain:

- MyWhoosh sends a command but in a dialect the M2 ignores → the MITM log shows writes
  we can translate.
- MyWhoosh never opens a control channel → no grade command reaches the radio at all,
  and the bridge must get grade elsewhere (app telemetry/network/UI) instead of
  translating a radio command.
