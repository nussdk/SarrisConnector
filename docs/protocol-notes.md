# Protocol cheat sheet

Working notes for Phase 1. Everything here must be confirmed against the actual M2
capture before being treated as fact for this trainer.

## BLE FTMS (Bluetooth Fitness Machine Service)

- Service UUID: **0x1826** (full: `00001826-0000-1000-8000-00805f9b34fb`)
- Cycling Power Service: **0x1818** (read-only power/cadence)
- Cycling Speed and Cadence Service: **0x1819**

Indoor-bike-relevant characteristics:

| Characteristic | UUID | Use |
| --- | --- | --- |
| Fitness Machine Feature | `0x2ACC` | Bitfields: what the machine can report and which targets it accepts |
| Indoor Bike Data | `0x2AD2` | Notify: speed, cadence, power |
| Supported Power Range | `0x2AD8` | Min/max/step for target power |
| Fitness Machine Control Point | `0x2AD9` | Write-with-indication: control commands |
| Fitness Machine Status | `0x2ADA` | Notify: machine status |

Control Point op codes (write `opcode + parameters` to `0x2AD9`):

| Op code | Command |
| --- | --- |
| `0x00` | Request Control |
| `0x04` | Set Target Resistance Level |
| `0x05` | Set Target Power (ERG) |
| `0x07` | Start or Resume |
| `0x08` | Stop or Pause |
| `0x11` | Set Indoor Bike Simulation Parameters (grade) |
| `0x80` | Response prefix, followed by result/request opcode + result code |

Response codes: `0x01` success, `0x02` not supported, `0x03` invalid parameter,
`0x04` operation failed, `0x05` control not permitted.

Simulation parameters payload (8 bytes): wind speed (uint16, 0.001 m/s), grade
(int16, 0.01%), rolling resistance coefficient (uint8, 0.0001), wind resistance
coefficient (uint8, 0.001), target power (uint16, W). A target-setting bitfield
selects which fields are valid.

Useful references:
- FTMS 1.0 spec: <https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/>
- Control point walkthrough: <https://cadexa.org/guides/bluetooth-ftms-explained>
- FTMS op code implementation notes: <https://github.com/openzigs/onyourleft/issues/43>

## ANT+ FE-C

- Garmin head units/watches control trainers with FE-C data pages over ANT+.
- This is the path already proven to change resistance on the M2, so it is the
  preferred trainer-side transport for the bridge.
- Need to capture exact page numbers/payloads from the Garmin → M2 link in Phase 1
  rather than assume them. Reference profile: ANT+ Device Profile — Fitness
  Equipment (FE), and open implementations in QZ / `openant`.

## Zwift virtual shifting

- Proprietary BLE service; FTMS has no gear concept.
- Reverse engineering and service details: `SHIFTR/VirtualShifting.md`
  (<https://github.com/JuergenLeber/SHIFTR>), `zwiftplay`
  (<https://github.com/ajchellew/zwiftplay>), QZ.
- Open question: whether MyWhoosh uses the identical service or a variant.

## Why a bridge rather than a MyWhoosh patch

MyWhoosh is a closed, signed, frequently updated client with competitive/anti-cheat
incentives. A client patch is brittle and could put the account at risk. A bridge only
emulates devices on standard/proprietary radio protocols and leaves the app untouched.
