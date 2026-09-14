# Recovered BLE command inventory

This is the complete command-name enum recovered from Lumo Lift APK 2.0.7,
plus the direct packet operations used by its device library. It is an inventory
of what the APK knows about, not a promise that every command works on firmware
revision 102424 or is safe to send.

Use [PROTOCOL.md](PROTOCOL.md) for GATT transport/framing details and current
hardware evidence.

## Status key

- **Verified** — exercised against this device.
- **APK** — command/path recovered from code only.
- **Event** — sensor-to-client message; not a command to send.
- **Blocked** — deliberately excluded from the replacement app.
- **Unknown** — name is present, but purpose or safe parameters were not
  established.

## JSON command envelope

The APK sends command names in a packet of type `0x8000`, whose null-terminated
UTF-8 payload has this form:

```text
 {"CMD":"COMMAND"}
 {"CMD":"COMMAND:arg1,arg2"}
```

The leading space is part of the original builder. Commands are transported via
the bulk-control/data characteristics described in `PROTOCOL.md`.

## Sensor/session commands

| Name | Direction | Purpose | Status |
| --- | --- | --- | --- |
| `ECHO` | Host → sensor | Diagnostic echo with a value. | APK |
| `BUZZ` | Host → sensor | Request a test vibration. | APK; user-initiated only |
| `REVISION` | Host → sensor | Query plugin/firmware revision. | APK |
| `CALIB_START` | Sensor → host | Calibration/target-posture event. | Event |
| `STARTUP` | Sensor → host | Startup event. | Event |
| `STARTUP_RSP` | Host → sensor | Response to `STARTUP`. | APK |
| `MIDNIGHT` | Host → sensor | Notify/reset daily boundary. | APK |
| `GET_LIVE` | Host → sensor | Request current live telemetry. | Verified transport; live events observed |
| `FLASH_EMPTY` | Sensor → host | Device flash-empty event. | Event |
| `LOGGING_OFF` | Host → sensor | Disable device logging. | Blocked/ownership setup only |

## Telemetry and activity messages

| Name | Direction | Meaning in APK | Status |
| --- | --- | --- | --- |
| `TGOOD` | Sensor → host | Good-posture duration; may include hours/current-hour seconds. | Event |
| `STEPS` | Sensor → host | Daily steps and distance fields. | Event; live `STEPS` observed |
| `STEPSH` | Sensor → host | Steps-at-hour-boundary counter. | Event |
| `CALS` | Sensor → host | Calories counter. | Event |
| `REC` | Sensor → host | Real-time activity and posture angle. | Event |
| `CACT` | Sensor → host | Compressed activity-history transfer. | Event; ownership/data-sync dependent |
| `ACT` | Host → sensor | Acknowledge activity-history transfer pages. | APK; automatic protocol acknowledgement only |
| `BS` | Unknown | Enum name only; no application use located. | Unknown |
| `BE` | Unknown | Enum name only; no application use located. | Unknown |

## Feedback, coaching, and alert commands

| Name | Direction | Purpose | Status |
| --- | --- | --- | --- |
| `BSE_START` | Host → sensor / event | Start posture-feedback session. | APK; UI action requires confirmation |
| `BSE_END` | Host → sensor / event | Stop/end posture-feedback session. | APK; UI action requires confirmation |
| `BSE_GET` | Host ↔ sensor | Read feedback session `len`, `left`, and `tgood`. | Verified |
| `BSE_SET` | Host → sensor | Set feedback-session length; APK ownership setup uses `32000`. | APK; not exposed as arbitrary control |
| `BSE_KILL` | Host → sensor | Likely terminate feedback session. | Unknown; blocked |
| `CHTOG` | Host ↔ sensor | Read/set coaching vibration enabled (`0`/`1`). | Verified, including reconnect persistence |
| `CSLEN` | Unknown | Enum name only; no application use located. | Unknown |
| `AL_LEN` | Host → sensor | Set onboarding/try-out feedback delay. | APK |
| `AL_LEN_GET` | Host ↔ sensor | Read current feedback delay. | Verified |
| `ALERTLEN` | Host → sensor | Set persistent alert delay. | APK; constrained to documented UI values |
| `AL_OFF` | Host → sensor | Disable an alert mode during ownership setup. | Blocked |
| `ALERT` | Unknown | Enum name only; no application use located. | Unknown |
| `BUZZSTR` | Host → sensor | Set vibration-strength/mask; app sends `255`. | APK; physical test only |
| `COACHCALIB` | Host → sensor | Configure coaching calibration; setup uses `0`. | Blocked/unknown lifecycle |
| `BPSM` | Host → sensor | Configure posture-sensor mode; setup uses `1`. | Blocked/unknown lifecycle |
| `SBB_GET` | Host ↔ sensor | Query backward sitting tolerance. | APK; timed out on this firmware |
| `SBF_GET` | Host ↔ sensor | Query forward sitting tolerance. | APK; timed out on this firmware |

## Ownership and user-data commands

| Name | Direction | Purpose | Status |
| --- | --- | --- | --- |
| `OWNER_GET` | Host ↔ sensor | Read owner identifier. | APK; not used by replacement |
| `NOT_OWNED` | Sensor → host | Ownership-state reply. | Event |
| `OWN` | Host → sensor | Send account credentials to claim device. | Blocked |
| `OWN_OK` | Sensor → host | Ownership accepted. | Event |
| `OWN_NOTOK` | Sensor → host | Ownership rejected. | Event |
| `USER_HEIGHT_CM` | Host → sensor | Set user height during ownership setup. | Editable with confirmation; no-argument read probe available; no confirmed read-back |
| `USER_WEIGHT_KG` | Host → sensor | Set user weight during ownership setup. | Editable with confirmation; no-argument read probe available; no confirmed read-back |
| `USER_GENDER` | Host → sensor | Set user gender during ownership setup. | Editable with confirmation; no-argument read probe available; no confirmed read-back |
| `USER_AGE` | Host → sensor | Set user age during ownership setup. | Editable with confirmation; no-argument read probe available; no confirmed read-back |

## Direct application-packet operations

These use the `ZO` binary frame and are separate from JSON command names.

| Packet type | Operation | Status |
| --- | --- | --- |
| `1` | Read properties; used for version, RTC, quiet mode, hardware ID, communication flags, battery, metadata, settings, IDs, button, and echo. | Verified for version, communication, and battery |
| `2` | Set property; APK uses it for RTC and communication flags. | Communication flags verified; RTC blocked |
| `3` | Mint/reassign software ID. | Blocked |
| `4` | Acknowledge uploaded data page. | Automatic protocol acknowledgement only |
| `6` | Turn indicator LED on with duration/style/RGB/current. | APK; not exposed |
| `7` | Erase firmware-update area. | Blocked |
| `8` | Commit firmware update metadata. | Blocked |
| `11` | Property response packet accepted by APK; no host request builder located. | Unknown |
| `12` | Restart device (`reset` payload). | Blocked |
| `13` | Graceful protocol disconnect. | APK |
| `0x8000` | JSON command envelope above. | Verified transport |

## Property identifiers accepted by the APK

| ID | Meaning |
| --- | --- |
| `1` | Firmware/base version and capability flags |
| `2` | Real-time clock |
| `3` | Quiet state |
| `5` | Hardware ID |
| `6` | Communication flags: upload `0x01`, plugin `0x02`, active `0x04` |
| `7` | Legacy battery state |
| `9` | Legacy firmware-update metadata |
| `10` | Firmware-update CRCs |
| `11` | Touch settings |
| `14` | Plugin inactive flags |
| `15` | Touch inactive flags |
| `16` | Software ID |
| `20` | Mode settings |
| `22` | Version-2 firmware-update metadata |
| `23` | Version-2 battery state |
| `29` | Button event/state |
| `30` | Echo response |

Other property IDs in the APK's switch are explicitly unrecognized. Firmware,
ownership, reset, arbitrary console, and unexplained write operations are not
part of the replacement application's allowlist.
