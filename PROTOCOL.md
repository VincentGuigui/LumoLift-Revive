# Lumo Lift protocol draft

This is the authoritative record for device-specific findings. It intentionally
separates static-code inference from live hardware verification.

## Evidence states

- **Unknown** — not yet established.
- **Inferred from code** — recovered from the supplied APK, not exercised.
- **Observed in traffic** — captured from a real device exchange.
- **Verified on hardware** — repeated with the expected response or behavior.

## Inputs

| Input | Details |
| --- | --- |
| APK | `Lumo-Bodytech/com-lumobodytech-lumolift.apk` |
| APK SHA-256 | `CCBC7BFE312A7B574717925FF0E7E0B66AE37F9C052DE9BCE57DA918337A6A25` |
| Package | `com.lumobodytech.lumolift` |
| App version | `2.0.7` (`versionCode` 1803261115) |
| Device | Advertises as `LUMO:`; BLE connection and service discovery verified on 2026-09-14 |
| Device firmware | Version `0.1`, revision `102424`, capabilities `0x0001007f` |
| Native battery | `3.8457 V`, not charging, approximately 49–50%, `23.578°C` |

The APK and full JADX output are private inputs and must remain unchanged or
unpublished.

## Identity and UUID scheme

**Verified on hardware:** the sensor advertises primary service
`af120101-31d4-48e8-a1f8-5c09c020ae42`, and a Windows BLE client connects and
enumerates its GATT database successfully.

The discovery session saw the local name `LUMO:`, RSSI `-50 dBm`, and advertised
service `af120101-31d4-48e8-a1f8-5c09c020ae42`. The device address is deliberately
omitted from project documentation. See [BLE_PROBE.md](BLE_PROBE.md) for the
probe procedure and complete exposed-service inventory.

**Inferred from code and matched on hardware:** proprietary UUIDs use:

```text
af12NNNN-31d4-48e8-a1f8-5c09c020ae42
```

where `NNNN` is a four-digit lowercase hexadecimal identifier. The Android app
selects `NNNN = 0101` as its primary Lumo service.

## Observed GATT map

**Verified on hardware:** the connected device exposed the standard Generic
Access (`1800`), Generic Attribute (`1801`), Device Information (`180a`), and
Battery (`180f`) services, plus proprietary services `af120002…`, `af120003…`,
and `af120101…`.

| Service | Characteristic | Properties | Code interpretation | State |
| --- | --- | --- | --- | --- |
| `0101` | `1001` | Notify | Activity | Observed; name inferred |
| `0101` | `1002` | Write without response | Options | Observed; name inferred |
| `0002` | `0201` | Notify, write without response | Server control | Observed; role inferred |
| `0002` | `0202` | Write | Server data | Observed; role inferred |
| `0002` | `0203` | Notify, write without response | Client control | Observed; role inferred |
| `0002` | `0204` | Notify | Client data | Observed; role inferred |
| `0003` | `0301` | Read, notify, write without response | Radar/ping | Observed; role inferred |
| Bluetooth Device Information | Manufacturer Name | Read | Standard GATT | Verified: `zero2one` |
| Bluetooth Battery | Battery Level | Read | Standard GATT | Verified raw value: `00` (reported 0%) |

All shortened proprietary IDs use the UUID base above. The app also supports
later service variants `0012`/`0013`, with radar characteristic `0311`.

## Application packet framing

**Inferred from code:** logical application packets are big-endian and have
this layout:

```text
offset  size  field
0       2     magic bytes 5A 4F (ASCII "ZO")
2       2     packet type, big-endian
4       2     payload length, big-endian
6       N     payload
6+N     2     CRC-16, big-endian
```

The CRC starts at `0xffff`, processes bits most-significant first, and uses
polynomial `0x1021` over the header and payload. The maximum decoded payload
accepted by the app is 500 bytes.

JSON commands use packet type `0x8000`. The payload is a UTF-8, null-terminated
string formatted by the app as:

```text
 {"CMD":"COMMAND"}
 {"CMD":"COMMAND:arg1,arg2"}
```

The leading space is present in the original builder. The app limits the JSON
command string to 100 characters.

## Bulk-transfer transport

**Inferred from code:** application packets are carried through service `0002`.
The 12-byte control record uses little-endian multibyte fields:

```text
u8 command, u8 action, u8 result, u8 identifier,
u16 length, u16 CRC, u32 address
```

For client-to-sensor execution, the app writes command `2`, action `0`, then
writes data to `0202` in 20-byte padded chunks. It waits for a matching control
notification on `0201` with result `1`. Maximum queued application data is
14 chunks (280 bytes). Sensor-to-client data uses `0203` control and `0204`
chunks, followed by a result acknowledgement written to `0203`.

**Verified on hardware:** the replacement client successfully sent a read-only
property request through this transport and received both the server
acknowledgement and a CRC-valid response. Because each application packet
already ends in its own CRC, the bulk CRC over the complete packet had the
expected zero residue.

The verified version exchange was:

```text
request application packet: 5a4f000100010112a0
request meaning:             packet type 1, property 1 (device version)
server acknowledgement:      command 2, result 1, identifier 1
response bulk control:        command 1, length 21, CRC 0000, identifier 2
response application type:    1
response payload:             0100000001000190180001007f
decoded:                      version 0.1, revision 102424,
                              capabilities 0x0001007f
```

The client acknowledged the response with result `1`, disabled notifications,
and disconnected cleanly. No configuration command was sent.

## Initialization sequence

**Inferred from code:** after enabling the required notifications, the original
client performs a four-step hello sequence:

1. Disable upload/plugin/active communication flags and request properties
   `1, 5, 16, 2, 3, 14, 15, 11`.
2. Based on reported capabilities, request battery property `7` or `23` and
   update metadata property `9` or `22`.
3. Set the device real-time clock.
4. Enable upload/plugin/active flags and read communication property `6`.

The replacement has not run this sequence. Clock and communication writes must
remain disabled until the response transport and packet fixtures are tested.

## Useful commands recovered from the APK

These are **inferred from code** and are not yet hardware-verified:

| Command | Arguments | Meaning |
| --- | --- | --- |
| `CHTOG` | none | Query coaching vibration state; verified reply includes `val`. |
| `CHTOG` | `0` or `1` | Disable or enable coaching vibrations; hardware-verified. |
| `ALERTLEN` | seconds | Set the persistent posture-feedback delay. |
| `AL_LEN` | seconds | Set the delay used by the onboarding try-out flow. |
| `BUZZ` | none | Request a test buzz. |
| `BUZZSTR` | `255` | Enable the vibration strength/mask used by the app. |
| `GET_LIVE` | none | Request current live values. |
| `STARTUP_RSP` | none | Response sent when the sensor emits `STARTUP`. |

The app exposes feedback-delay values `3, 5, 10, 15, 30, 45, 60, 120` seconds,
defaulting to 15 seconds. `CALIB_START` is handled as an incoming sensor event;
the current code evidence does not justify sending it as a calibration command.

### Additional verified queries

With communication flags `0x06`, the following query results were observed:

```text
BSE_GET     {type: BSE_GET, len: 32000, left: 24792, tgood: 96}
AL_LEN_GET  {type: AL_LEN_GET, val: 15}
SBB_GET     timeout
SBF_GET     timeout
```

`BSE_GET` confirms that feedback session state and its timer can be monitored.
`AL_LEN_GET` confirms a 15-second configured alert delay. Backward and forward
tolerance queries did not reply on firmware revision 102424; their setters are
unknown and must not be guessed.

### Verified coaching exchange

**Verified on hardware:** JSON commands require communication flags `plugin`
and `active` (`0x02 | 0x04 = 0x06`). With flags `0x00`, the transport accepts a
`CHTOG` query but does not return an application response. Enabling all flags as
the original app does (`0x07`) also starts historical packet-type-4 uploads;
the diagnostic therefore uses `0x06` to leave upload disabled.

The current coaching value was the JSON string `"1"`. Set operations return a
successful bulk-transfer acknowledgement but no dedicated application reply, so
the client must reconcile them with a separate no-argument `CHTOG` query.

The verified persistence experiment was:

```text
baseline:                 coaching 1, communication 00
set test value:           coaching 0, query read-back 0
after disconnect/reconnect: coaching 0
restore original:         coaching 1, query read-back 1
after disconnect/reconnect: coaching 1
final communication state: 00
```

This satisfies independent-control Gate G3. It does not yet prove that coaching
vibrations occur autonomously after disconnection.

## Steps and goal boundary

**Inferred from APK:** the sensor reports daily steps with JSON type `STEPS` and
an hour-boundary counter with type `STEPSH`. The original app requests live data
with `GET_LIVE`, stores the daily value, and uses a progress bar against a local
goal. `STEPSH` is used to derive current-hour activity (`STEPS - STEPSH`); it is
not itself a device-configurable goal.

The original goal screen accepts a minimum of 100 steps (default 10,000) and
saves `STEP_GOAL` to app preferences. `LKGoalsManager` stores/synchronizes goals
through the cloud goals database. No BLE command or packet builder sets a steps
goal on the physical sensor.

The Python application consequently exposes two live gauges and a local goal
target, but deliberately does not send a fabricated “set steps goal” command to
the device.

### Goal-model follow-up

A broader APK pass found `LKGoal`, a cloud/database model with defaults of
`steps = 10000` and `posture = 14400` seconds (four hours). `LKGoalsManager`
can store and synchronize those records with the discontinued cloud service.
However, the visible `StepsActivity` does not create or upload an `LKGoal`; it
only saves `STEP_GOAL` in Android preferences. No caller in the app source was
found that sends either goal to the sensor through BLE.

The protocol boundary is therefore unchanged: steps and posture goals are
app/cloud concepts, not recovered device configuration.

## Feature inventory from the APK

| Feature | Evidence | Replacement position |
| --- | --- | --- |
| Daily steps, hour-boundary steps, distance, calories, and good-posture time | `STEPS`, `STEPSH`, `CALS`, `TGOOD` live messages | Monitor and display; no arbitrary counter writes |
| Posture feedback session | `BSE_GET`, `BSE_START`, `BSE_END`, `BSE_SET` | Read session state; user-confirmed start/stop only |
| Coaching vibration | `CHTOG` | Read/write verified with read-back and reconnect test |
| Alert delay | `AL_LEN_GET`, `ALERTLEN`, `AL_LEN` | Read current delay; constrained user-settable values |
| Test vibration | `BUZZ`, `BUZZSTR` | Expose only as a user-requested physical test |
| Target-posture calibration | Incoming `CALIB_START`; onboarding instructions use physical interaction | No outgoing calibration command exposed |
| Angle/tolerance values | `REC` carries angle; `SBB_GET`/`SBF_GET` time out on this firmware | Local display classifier only; no guessed setters |
| User height/weight/gender/age | Sent during ownership onboarding | Editable with explicit confirmation; no confirmed local read-back |
| Firmware/update/reset/ownership/minting | APK contains flows | Explicitly excluded from the replacement |
| Steps/posture goals and units | Android preferences and cloud/database paths | Local UI preferences only, not sensor configuration |

## Multi-frame event handling

**Observed during live use:** a bulk-transfer response can contain multiple
concatenated application frames. Treating its full payload as one frame produced
the reported error `packet length is 124 bytes; expected 27` after valid `STEPS`
events.

The reusable `PacketStreamDecoder` now buffers and splits each bulk payload at
the `ZO` frame boundary, validates every frame independently, and emits all
contained events. Connection performs one `GET_LIVE` request after its initial
configuration refresh, but recurring monitoring remains off until explicitly
started in the UI. Stopping monitoring both cancels client polling and changes
communication flags from active/plugin (`0x06`) to idle/plugin (`0x02`) so the
sensor is not left in its active telemetry mode.

## Why STEPS and STEPSH can appear to reset on reconnect

The sensor messages provide raw counters. In the original APK, `STEPS` and
`STEPSH` are not displayed directly: the app reads locally persisted
`deltaSteps`/`deltaStepsTillHr` values and calculates `raw counter + delta`.
It recomputes those deltas from the app's activity database and resets them at
day/hour boundaries. This preserves the dashboard total when a raw device
counter restarts, rolls over, or reports a new session baseline.

The replacement now persists a small local state record containing each last raw
value and displayed total. On a same-day raw-counter decrease, it preserves the
previous displayed total and adds the new raw baseline; on an app restart, it
loads the saved totals. The record resets at the next local calendar day. This
avoids the apparent reconnect reset without using any cloud service.

## Ownership and cloud boundary

**Inferred from code:** the original high-level onboarding flow queries
`OWNER_GET` and can send account credentials through `OWN`. It may mint a new
sensor ID when taking ownership. These operations are outside the replacement
client and must not be reproduced.

Low-level BLE connection and service discovery work without login. Whether the
hello sequence and local configuration commands require an owned state remains
**unknown**.

## Replacement implementation status

**Verified locally:** `python/lumolift/protocol.py` implements the application
CRC, application frame encode/decode, APK-style JSON command encoding,
bulk-control records, and 20-byte data chunking. Protocol-focused tests cover
the standard CRC vector, round trips, invalid data, byte order, padding, and
size limits.

The complete suite now has 20 passing tests, including battery/JSON response
decoding and UI-independent posture classification. The Tkinter interface also
passes an off-screen construction/close smoke test.

**Verified on hardware:** `.tools/ble_query_version.py` uses those codecs for
the version-property exchange described above.

Additional read-only observations:

- `.tools/ble_read_standard.py` read Manufacturer Name as `zero2one`.
- The standard Battery Level value was one byte `00`; native property `23`
  instead reported `3.8457 V`, no USB power, not charging, charge current
  `0 A`, system current `0.005852 A`, raw charge `0.503153`, voltage-derived
  estimate `0.491`, and temperature `23.578°C`.
- `.tools/ble_listen_readonly.py` subscribed to radar `0301` and activity
  `1001` for 30 seconds. No notification payload arrived while the sensor was
  idle. Both subscriptions were disabled before disconnecting.
- `.tools/ble_query_readonly.py` verifies native battery and query-only coaching
  operations.
- `.tools/ble_verify_coach_persistence.py` performs the reversible Gate G3
  disconnect/reconnect experiment and restores the original state.
- The app's daily and `STEPSH` gauges consume `STEPS`/`STEPSH` JSON events;
  the adjustable goal is local because the APK has no device-goal endpoint.

## Hardware write allowlist

Only these operations are currently allowlisted:

| Operation | Constraints |
| --- | --- |
| Communication property `6` | May temporarily change `0x00` to `0x06`; must restore the original value and verify it on a fresh connection. Keep upload bit `0x01` disabled. |
| `CHTOG:0` / `CHTOG:1` | Record the original value, query after each write, restore it in a safety path, and verify persistence after reconnect. |
| Bulk client acknowledgement | Result must reflect the validated response CRC and reuse the sensor's control identifier. |
| `ALERTLEN:<seconds>` | User-initiated only; value must be one of `3, 5, 10, 15, 30, 45, 60, 120` and must be reconciled with `AL_LEN_GET`. APK-supported; live write verification pending. |
| `BSE_START` / `BSE_END` | User-initiated only and confirmation required; reconcile with `BSE_GET`. APK-supported; live start/stop verification pending. |
| `BUZZ` | User-initiated test only. APK-supported; physical confirmation pending. |
| `USER_HEIGHT_CM`, `USER_WEIGHT_KG`, `USER_GENDER`, `USER_AGE` | Explicit Profile-tab confirmation only; values are range-validated and sent directly to the sensor. No confirmed read-back exists. |
| `OWN` | Explicit User-profile-tab confirmation only; sends the owner with an empty second argument and verifies with `OWNER_GET`. |

Ownership, minting, RTC changes, tolerance setters, firmware operations, resets,
and arbitrary console commands remain disallowed.

## Next verification steps

1. With coaching confirmed enabled, disconnect fully and test whether posture
   alerts operate autonomously.
2. Record timestamped radar/activity bytes during controlled wear, posture, and
   button actions.
3. Determine calibration behavior without treating incoming `CALIB_START` as a
   command.
4. Investigate `AL_LEN_GET` as the likely query for current alert delay before
   considering a reversible delay-setting experiment.
