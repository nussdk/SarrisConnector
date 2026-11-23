# Sarris M2 connector — project detail

## Problem

Saris M2 trainer works in ERG mode with MyWhoosh on Windows, but ignores gradient/sim
commands and Zwift-style virtual shifting. A Garmin watch *can* change resistance on the
same trainer, so the hardware supports gradient control — the PC side just isn't speaking
a dialect the trainer understands.

Goal: gradient/sim control **and** Zwift-style virtual shifting in MyWhoosh, without
replacing the trainer.

## Confirmed facts

- Trainer is a **Saris M2** (wheel-on, ~1500 W, 15% simulated grade). Official spec:
  **dual ANT+ FE-C and BLE FTMS**. Source: <https://saris.com/products/m2-smart-trainer>
- Garmin watch controls gradient over **ANT+ FE-C** (Fitness Equipment Control).
  This path is proven to work with this trainer.
- MyWhoosh on PC pairs over BLE and/or ANT+. Community reports say switching trainer
  control to **ANT+** restores gradient feedback on some trainers:
  <https://www.reddit.com/r/mywhoosh/comments/1aucs2s/i_dont_get_any_gradient_feedback_on_my_smart/>
- Saris BLE implementations have known resistance-control quirks in Zwift (long forum
  thread): <https://forums.zwift.com/t/when-paired-via-bluetooth-saris-trainers-cannot-complete-spindown-through-zwift-report-resistance-issues/63992>
- Patching MyWhoosh directly is a bad idea: closed client, signed binaries, anti-cheat,
  account-ban risk, and every update can break the patch. **Rejected.**
- Prior art worth reading:
  - **SHIFTR** — ESP32 BLE↔Direct Connect bridge, reverse-engineered Zwift virtual
    shifting, plus FTMS emulation for MyWhoosh:
    <https://github.com/JuergenLeber/SHIFTR> (see also `VirtualShifting.md` in that repo)
  - **Simcline-V2** — ESP32/NimBLE BLE man-in-the-middle bridge that passes and inspects
    FTMS/CPS/CSC traffic between trainer and app, including Saris trainers:
    <https://github.com/Berg0162/Simcline-V2> (`examples/Smart-MITM`)
  - **QZ (qdomyos-zwift)** — large open source bridge, reverse engineered Zwift/DirCon
    and virtual shifting: <https://github.com/cagnulein/qdomyos-zwift>
  - **BikeControl** — closed-source core but useful reference for virtual shifting in
    MyWhoosh via trainer emulation: <https://github.com/OpenBikeControl/bikecontrol>
  - **zwiftplay** — Zwift Play BLE service/characteristic IDs:
    <https://github.com/ajchellew/zwiftplay>

## Environment / constraints

- MyWhoosh runs on **Windows PC**. PC has **both ANT+ and BLE** radios.
- **ESP32 boards available** for sniffing/prototyping.
- Local dev environment is Linux; keep code cross-platform (Python + `bleak`,
  optional `openant`) so it can be run on the Windows machine.

## Working hypothesis

MyWhoosh's trainer-control implementation (both BLE and ANT+ paths on PC) does not
issue commands the M2 acts on, while the Garmin watch issues valid ANT+ FE-C commands
to the same hardware. Either MyWhoosh uses a different/incomplete control dialect, or
it never opens a control channel at all and only pairs the trainer as a power source.
A bridge that presents a *virtual trainer* to MyWhoosh and translates its control
commands into known-good ANT+ FE-C (or valid FTMS) commands to the real trainer should
unlock gradient. Virtual shifting additionally needs a Zwift shift-controller/service
emulation toward MyWhoosh, with gear changes translated to resistance commands.

Phase 0's failure raises a question for Phase 1: does MyWhoosh send a control command
that the M2 ignores, or no usable command at all? The MITM capture will tell us. If it
sends malformed/unsupported commands, the bridge translates them; if it sends nothing
usable, grade must be derived from another source (app telemetry/UI/network).

## Decisions

- **Build a connector**, not a MyWhoosh patch.
- Firmware track (this branch, `feature/esp32-modern-build`): base the work on
  **SHIFTR** (<https://github.com/JuergenLeber/SHIFTR>) running on ESP32 hardware.
  It already implements BLE↔FE-C bridging, FTMS emulation, reverse-engineered Zwift
  virtual shifting, and a web config UI.
- Additional goals on top of SHIFTR:
  1. **Virtual shifting with no Zwift Click/Play controller** — expose the shifting
     service and let the app/web UI supply gears.
  2. **Quick web UI** to toggle features, change gears, reconnect the trainer, and
     connect/select the trainer.
- A separate Windows translation-app experiment lives on `feature/windows-connector`;
  it is a parallel option, not a replacement for this firmware work.
- Reference clones: `refs/shiftr` (primary), `refs/simcline-v2` (MITM capture),
  both read-only. Any modifications live in this repo, not in `refs/`.
- PC-side Python tools for protocol capture live in `tools/`.

## SHIFTR adaptation — scope questions

- **No-controller mode = app-driven gears only.** Enable the virtual shifting service
  toward the app without requiring a Zwift Click/Play; the app supplies gear changes.
  No fixed gear, web shifting, or auto-shift needed for now.
- **MyWhoosh first**, keep upstream Zwift behaviour working where practical.
- Available hardware: **ESP32-S3 and generic ESP32 dev boards** (no WT32-ETH01 confirmed).
  SHIFTR targets WT32-ETH01; portability to BLE-only ESP32/S3 needs checking.
- Does a fork need to stay compatible with upstream updates, or is a one-off fork fine?

## Phases

### Phase 0 — no-code check — DONE, FAILED

- [x] In MyWhoosh pairing, select the **ANT+** trainer/controllable option instead of BLE.
  **Result: still no gradient control.** The M2 *is* listed as a controllable/resistance
  trainer in MyWhoosh (both BLE and ANT+), and selecting it has no effect on gradient.
  So MyWhoosh recognises it as controllable but the commands it sends don't drive the
  trainer — unlike the Garmin's ANT+ FE-C commands on the same hardware.
- [ ] Record the exact MyWhoosh version, OS build, pairing options, and what appears in
      the device list. Put raw observations in `out/` (gitignored). Useful for deciding
      whether MyWhoosh ANT+ control is even implemented on PC.

### Phase 1 — protocol discovery

Detailed steps: [`docs/capture-guide.md`](docs/capture-guide.md).
Reference clones (read-only): `refs/simcline-v2`, `refs/shiftr`.

- [ ] Run `tools/scan_trainer.py` on the Windows machine: enumerate M2 BLE services,
      characteristics, and advertisement data. Save JSON to `out/`.
  - [ ] Determine whether it exposes standard FTMS (`0x1826`) with Fitness Machine
        Control Point (`0x2AD9`) and Indoor Bike Simulation parameters, legacy FE-C
        over BLE, or both.
- [ ] Use an ESP32 as BLE man-in-the-middle (Simcline-V2 `Smart-MITM` example) between
      MyWhoosh and the M2, and log the control writes MyWhoosh sends during a climb:
      op codes, target grade, target power, resistance level.
- [ ] Optional: log ANT+ FE-C pages from the Garmin watch → M2 for comparison
      (`openant` + USB stick) to learn the exact command profile the trainer accepts.
- [ ] Write up findings in `docs/protocol-notes.md` with concrete byte examples.

### Phase 2 — gradient bridge prototype

- [ ] ESP32 connector receives a grade/ERG command from the virtual trainer interface.
- [ ] Translate to ANT+ FE-C simulation / target-power pages and send to the M2.
- [ ] Relay CPS/CSC/power data back so MyWhoosh sees a normal trainer.
- [ ] End-to-end test: MyWhoosh shows a climb → resistance rises on the M2.

### Phase 2.5 — ESP32 port / NimBLE 2.x migration

- [x] Migrate to NimBLE-Arduino 2.x: scan callbacks, `getServices()` /
      `getCharacteristics()` return-by-reference, and explicit 128-bit UUID byte order.
- [x] Add `esp32dev` and `esp32-s3-devkitc-1` build envs alongside `wt32-eth01`;
      switch to `min_spiffs.csv` so NimBLE 2.x fits in flash.
- [x] Add app-driven-gear setting, `/gear` and `/connect` web endpoints, and web UI
      controls for gear shifting and trainer reconnect.
- [x] Builds pass for `esp32dev`, `esp32-s3-devkitc-1`, and `wt32-eth01`;
      `pio test -e native` passes.
- [ ] Flash to a real ESP32/S3, join the configured Wi-Fi, and check scan/connect,
      web UI, and FE-C writes against the M2.
- [ ] Verify app-driven virtual shifting with MyWhoosh (gear changes affect resistance).

### Phase 3 — virtual shifting

- [x] Firmware support for app-driven gears without Click/Play (config toggle,
      `/gear` endpoint, and virtual-shifting mode forced on a climb).
- [ ] Capture what MyWhoosh expects from a Zwift virtual-shifting-capable trainer
      (service UUIDs, gear index writes) using SHIFTR's reverse engineering as reference.
- [ ] Emulate that service toward MyWhoosh; map gear index to FE-C/FTMS resistance.
- [ ] Support Zwift Click / shifters as the input device.
- [ ] Decide whether this replaces or complements MyWhoosh's own virtual shifting UI.

## Open questions

- Does MyWhoosh's **ANT+** control already solve gradient with this trainer? (Phase 0)
- Does the M2's BLE FTMS implementation support Indoor Bike Simulation, or only
  target-power/ERG? (Phase 1)
- Does MyWhoosh virtual shifting use the same BLE service as Zwift, or its own?
- Is a second radio required for the virtual-trainer side, or can ANT+ do both directions?

## References

- FTMS spec (Bluetooth SIG):
  <https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/>
- MyWhoosh supported equipment list (M2 is not on it):
  <https://mywhoosh.com/docs/which-smart-equipment-works-with-mywhoosh/>
- MyWhoosh gradient feel explanation:
  <https://mywhooshinfo.com/blog/gradient-feel-trainer-difficulty>
