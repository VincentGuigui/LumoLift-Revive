# Lumofit Revival: Revised Development Strategy

**Prepared:** September 14, 2026  
**Objective:** Restore configuration and posture-alert functionality without depending on the discontinued mobile app.  
**Preferred sequence:** Hardware identification -> APK and Bluetooth investigation -> Windows/Python proof of concept -> Android app.

> **Recommendation:** Recover and validate the device protocol before building the application. Reuse relevant open-source work, but do not mistake a similar posture sensor for a compatible one.

## 1. What is known, and what is not

The owner describes a Bluetooth posture-monitoring device named **lumofit**, whose original mobile app no longer launches. The owner has the Android APK and would like to start with a Windows/Python diagnostic application before moving to Android.

**The exact hardware identity is not established.** In particular, this document does not assume that "lumofit" means Lumo Lift, LUMOback, or Upright GO 1. Confirm the manufacturer, model, app package name, and Bluetooth identifiers before selecting any device-specific code.

The APK has not been supplied or inspected for this document, and no physical Bluetooth tests have been performed. Repository features below are reported by their maintainers, not independently hardware-tested here.

The reviewed resources did **not establish a ready-to-use Bluetooth implementation compatible with this particular sensor**. That is a bounded research finding, not proof that no implementation exists.

## 2. What the existing-code search changes

The original Python-first approach remains appropriate. The revision is to distinguish three kinds of resources: device-protocol evidence, reusable application architecture, and irrelevant cloud-only integrations.

### 2.1 LUMOKit-Public: an older Lumo sensor SDK lead

**Repository:** `talmaco/LUMOKit-Public`

Indexed documentation describes an Objective-C iOS framework for communicating with **LUMOback**, receiving posture/activity updates approximately once per second. The indexed repository includes a framework and sample application, uses CoreBluetooth, and documents a vendor-issued application ID. It does not establish Lumo Lift compatibility or availability of the framework's underlying protocol source. [S1]

During this review, direct repository retrieval returned a 404, while search-indexed documentation remained available. Treat download availability, buildability, and application-ID enforcement as **unverified**, not as solved prerequisites.

**Decision:** Keep this as a secondary research lead. Examine recoverable headers, samples, or framework contents for useful clues, but do not make project progress depend on it.

### 2.2 `samuelmr/lumolift`: a cloud API client, not a Bluetooth driver

This Node.js package is an unofficial Lumo Lift API client for authentication, activities, and user information. GitHub identifies it as archived on March 28, 2023. Its configuration points to vendor HTTPS/OAuth endpoints and requests activity/profile-reading scopes. [S2], [S3]

**Decision:** Do not use it as the implementation foundation. Accessing account data is a different problem from connecting to and configuring the physical sensor. Its existence does not demonstrate a recovered Bluetooth protocol.

### 2.3 Open Posture Companion: a possible application foundation

**Repository:** `niltonheck/open-posture-companion`

This MIT-licensed React Native/Expo project targets **Upright GO 1**. Its README describes calibration, training/tracking modes, test vibration, live status, reconnection, and local history. It separates device logic into `src/device/` above `react-native-ble-plx`. The documented validated platform is iOS; Android on-device verification remains pending. Native BLE requires a custom development build rather than Expo Go. [S4]

**Decision:** Evaluate its architecture after identifying the sensor. For a different model, adaptation means implementing that model's initialization, packet formats, state transitions, and capabilities; changing the advertised name or UUIDs alone is not a compatibility strategy.

### 2.4 Upright GO 1 reverse engineering: a useful Python-first precedent

**Repository:** `niltonheck/upright-go-1-reverse-engineering`

This project provides Python/Bleak examples and `PROTOCOL.md`. Its July 2026 update reports a hardware-characterized Upright GO 1 protocol, including calibration, posture states, pause mode, battery, and telemetry. These findings apply to the author's documented Upright hardware, not automatically to another sensor. [S5]

The author also reports apparently corrupting a device while experimenting with arbitrary writes, and subsequently adopting read-first exploration. [S5]

**Decision:** Reuse the investigation method and documentation structure. Do not run its device-specific commands against unidentified hardware. Prefer its maintained protocol reference over blindly copying an older example.

### Practical conclusion

The **APK remains the strongest candidate source for the exact device's commands**. Existing projects may reduce the work needed for diagnostics, documentation, or the eventual interface, but do not yet remove the need to recover and validate this sensor's protocol.

## 3. Define the smallest useful outcome

The initial goal is not to reproduce the original product, account system, or dashboards. It is to demonstrate:

> An independent client connects, performs a useful and reversible configuration operation, verifies the result, reconnects successfully, and establishes whether posture alerts work without a connected phone.

Candidate features are status/battery, calibration, coaching on/off, and alert delay or sensitivity **only where supported by the recovered protocol**. Do not promise adjustable thresholds, vibration intensity, or historical data until evidence supports them.

Accounts, cloud synchronization, firmware updates, extensive statistics, and a polished desktop interface are outside the first milestone.

The investigation must distinguish these possibilities:

| Architecture hypothesis | Consequence for the replacement |
| --- | --- |
| The sensor detects posture and alerts independently. | Build a small connect/configure/disconnect utility. |
| The phone interprets measurements or triggers alerts. | Recover the data format and processing logic; maintain a live connection. |
| The app requires login, but local device control does not. | An offline client may avoid the obsolete login workflow. |
| The device itself requires vendor-generated authorization. | Investigate that dependency before assuming offline initialization is possible. |

These are alternatives to test, not descriptions of the actual device.

## 4. Phase A: Preserve and identify

Keep an untouched private copy of the APK, record its SHA-256 hash and version, and retain any existing installation and app data. Do not begin by uninstalling the old app, deleting its data, clearing Bluetooth bonds, or factory-resetting the sensor.

Record the label/model, charger and button layout, current behavior, app package name, phone/Android version, Windows version, and Bluetooth adapter. Determine whether "lumofit" is the printed product name, app name, or advertised Bluetooth name.

Use a BLE inspection tool such as nRF Connect for Android to record advertisements and, where a connection is possible, services, characteristics, and their properties. Nordic documents scanning, service discovery, reads/writes, notifications, and logging in this tool. [S6]

Begin with discovery and understood reads. Do not indiscriminately interact with firmware, bootloader, reset, or undocumented control endpoints.

**Checkpoint:** Identify the probable model and transport, or document precisely what remains unknown. A failed Windows scan is not enough to declare the hardware unsupported; compare with Android and investigate discovery state, adapter behavior, permissions, and existing connections.

Bleak is a BLE/GATT client, not a general Bluetooth Classic client. If the APK or hardware evidence points to Bluetooth Classic, revise the transport choice rather than forcing a BLE solution. [S7]

## 5. Phase B: Inspect the APK and hardware in parallel

### APK investigation

Start with JADX for decompiled code and resources. Its maintainers explicitly warn that decompilation may be incomplete. Use Apktool when decoded resources, smali-level inspection, or a controlled rebuild is necessary. Neither tool guarantees that every relevant implementation will be readable. [S8], [S9]

Trace a small number of paths instead of reading the entire application:

| Area | Questions to answer |
| --- | --- |
| Manifest, resources, model references | Which product and app generation does this APK support? |
| Bluetooth discovery and connection | What filters, transport, pairing, and connection sequence are used? |
| Service/characteristic identifiers | Which endpoints carry commands, responses, and telemetry? |
| Settings handlers and packet builders | Which bytes implement calibration, coaching, or a setting change? |
| Incoming-message parsers | How are status, acknowledgments, errors, and measurements represented? |
| Initialization and authentication | Are time setup, session negotiation, account data, or device credentials required? |

Useful search targets include `BluetoothGatt`, `connectGatt`, `writeCharacteristic`, `onCharacteristicChanged`, `UUID`, and strings from the configuration screens. Also inspect bundled libraries and native-code boundaries when the Java/Kotlin layer delegates the important work.

For each candidate operation, record the service and characteristic, packet framing, byte order, length, parameter range, checksum if present, prerequisites, response, timeout, and expected physical effect. Leave unknown fields explicitly unknown.

Distinguish ordinary pairing/bonding from proprietary authorization. Bleak supports pairing workflows on supported platforms; encountering a protected characteristic does not by itself demonstrate a vendor-server dependency. [S10]

### Hardware investigation

Compare the discovered service map with APK identifiers. Read identified information and subscribe to understood status streams. Record controlled physical actions with timestamps: stationary, tilted, restored orientation, and a known non-destructive button action.

Preserve raw bytes alongside tentative interpretations. A value that changes during movement is evidence of correlation, not yet proof of its units or meaning.

**Checkpoint:** Produce a device-specific protocol draft and at least one well-supported, low-risk command candidate. Do not populate it with Upright or LUMOback constants merely because the products have similar purposes.

## 6. Phase C: Build a Windows/Python diagnostic client

Assuming BLE is confirmed, use Python with Bleak. Its documented capabilities cover discovery, connections, characteristic reads/writes, and notifications on Windows and other platforms. [S7], [S10]

Build a command-line tool first. Separate Bluetooth transport, device-session handling, packet encoding/decoding, and the command interface. Keep unknown-device command writes disabled by default.

The following describes a **proposed interface, not existing working commands**:

```text
sensor scan              Discover nearby candidate devices
sensor inspect           Export the service/characteristic map
sensor status            Read identified status values
sensor listen            Record selected notification streams
sensor config read       Read configuration where supported
sensor config set ...    Execute an explicitly supported setting change
sensor calibrate         Calibrate after its protocol is verified
```

Include timestamped logs, operation direction, endpoint identifiers, raw payloads, connection state, errors, and a session/model/firmware identifier where available. Keep personal identifiers and credentials out of shareable logs.

### Verification experiment

Choose one reversible setting supported by the APK evidence. Establish its original value, send the documented command, confirm an application response or read-back, observe the expected behavior, and restore the original value.

Specify Bleak's write response mode explicitly according to the device protocol. Writes with and without responses have different behavior; a completed transport operation is not sufficient proof that the intended setting took effect. [S10]

Serialize state-changing commands and use bounded timeouts. After a timeout, reconcile device state before retrying; do not automatically replay an operation that may already have succeeded. Treat calibration especially carefully because repeating it may establish a different reference posture.

**Checkpoint:** Independently control one useful feature with repeatable evidence. Reading battery status alone is not proof that configuration can be restored.

## 7. Phase D: Resolve gaps with the old app only when needed

Do not make repairing the original application the main project. Use it as a reference when static inspection leaves an important ambiguity.

First collect its startup failure through ADB/logcat, which provides application and system log output. Determine whether the failure occurs before Bluetooth initialization, during login, or elsewhere. A compatible spare phone or a narrowly modified local test copy may help, depending on the actual failure. Preserve the original installation and APK. [S11]

When the app can perform a relevant operation, capture one action at a time using Android Bluetooth HCI snoop logging. Android documents enabling the setting in Developer options and restarting Bluetooth; its documentation also describes extracting snoop data through bug reports. [S12]

Compare a baseline connection with a single setting change, then repeat with a different value. Separate initialization messages from feature commands and compare captures with the APK's packet-building logic.

A capture cannot reveal a command the app never reaches. If the app remains unusable, continue from static evidence and controlled hardware tests rather than assuming packet capture solves the problem.

Reserve deeper runtime/native-code investigation and external radio capture for specific unresolved questions. Do not brute-force unknown writes or attempt firmware replacement as a shortcut.

## 8. Phase E: Determine whether the sensor works autonomously

After configuration is verified, disconnect the Bluetooth client completely and test alerts. Repeat after a normal power cycle only when the model's power controls and effects are understood. Separately record which settings persist and whether recalibration is required.

| Observation | Design decision |
| --- | --- |
| Alerts continue with no phone connection. | Prefer a configuration-only app; disconnect after each task. |
| Alerts work until a restart or recalibration event. | Make that lifecycle visible and support the required recovery operation. |
| Alerts require the phone connection. | Recover the necessary processing or commands and design continuous operation. |
| Behavior is inconsistent. | Investigate mode, calibration, wear detection, timing, or initialization before expanding the interface. |

**Checkpoint:** Document both offline behavior and persistence. Do not inherit another sensor's calibration or restart semantics.

## 9. Phase F: Choose the Android implementation

The revised recommendation is **not an unconditional commitment to Kotlin**, and not an automatic fork of a superficially similar app. Choose after the protocol and required lifecycle are understood.

### Option A: Native Kotlin

Prefer a small Kotlin application for an Android-only configuration utility or where explicit native lifecycle control is the priority. Evaluate Nordic's Android BLE Library for queued operations, initialization, timeouts, and error handling. Its documentation notes that scanning is separate, so account for that in the design. [S13]

This remains the default recommendation for a narrowly scoped Android-only replacement unless reuse demonstrably reduces the work.

### Option B: Adapt Open Posture Companion

Evaluate this route when its interface and structure substantially match the recovered requirements, or cross-platform support has value. The project and its platform limitations are described in Section 2.3. [S4]

Before committing, build an Android development version, review the device-layer contract, and estimate what must change. Implement a separate model-specific adapter; remove or hide unsupported features. Treat Android reliability as work to validate, not something inherited from successful iOS operation.

### Keep the architecture portable

```text
User interface
      |
Device functions and capabilities
      |
Connection/session state + packet codec
      |
Bluetooth transport
      |
Actual sensor
```

Reuse the **protocol specification, evidence, packet fixtures, and tests** across implementations. Port packet codecs and session behavior as needed; do not make embedding the Python runtime in Android a requirement.

### Android requirements

Handle permissions according to both OS and target SDK, including `BLUETOOTH_SCAN` and `BLUETOOTH_CONNECT` where applicable. Request only the capabilities the app needs. [S14]

If continuous communication is necessary, choose a documented background BLE approach, such as an appropriately started `connectedDevice` foreground service or companion-device service. Follow launch restrictions and test on physical hardware; do not assume that keeping a JavaScript or Kotlin loop alive guarantees background operation. [S15]

Test permission denial, Bluetooth toggling, unexpected disconnects, screen locking, application restarts, sensor sleep/wake, and sensor power cycling. Make unavailable, uncalibrated, and disconnected states explicit in the interface.

## 10. Evidence, safeguards, and project outputs

### Evidence discipline

Use four statuses in the protocol notes: **unknown**, **inferred from code**, **observed in traffic**, and **verified on hardware**. Include the relevant model, firmware, APK version, source location, and capture/test identifier.

Do not promote an inferred command to verified merely because a BLE write returned successfully. Before calling the minimum implementation reliable, demonstrate repeated command behavior and successful reconnection using the intended platform.

### Safeguards

Keep firmware updates, bootloader operations, undocumented resets, and arbitrary write sweeps outside this project. Require an explicit allowlist of understood state-changing operations and reject unsupported models. The reported Upright corruption is a cautionary precedent, not evidence that this sensor has the same vulnerability. [S5]

Keep raw APKs, private captures, identifiers, and any recovered credentials private by default. Before redistributing reused code or assets, inspect the actual license terms and notices. Prefer publishing the independent implementation, protocol notes, and sanitized test fixtures rather than repackaging proprietary application contents.

### Minimal outputs

Avoid a collection of overlapping planning documents. Maintain this strategy and one authoritative protocol reference, supported by machine-readable evidence and tests:

```text
project/
  README.md                 Setup, supported hardware, limitations
  PROTOCOL.md               Verified protocol and remaining unknowns
  python/                   Diagnostic client and packet codecs
  android/                  Created after choosing the mobile approach
  tests/                    Sanitized packet fixtures and regression tests
  evidence/                 Device maps and selected sanitized captures
```

Keep original APKs and unsanitized captures separately in private storage. These are proposed outputs; no client, Android build, or protocol implementation accompanies this strategy document.

## 11. Acceptance gates and immediate next action

| Gate | Evidence required before advancing |
| --- | --- |
| G1: Identity and discovery | Hardware/app identity and transport documented; discovery results recorded. |
| G2: Protocol foothold | Relevant endpoints and at least one low-risk command supported by evidence. |
| G3: Independent control | A useful setting or action works, is verified, and survives a reconnect as expected. |
| G4: Operating model | Standalone alerts, persistence, and calibration lifecycle tested. |
| G5: Android MVP | Required functions work on the target phone, including applicable permission and lifecycle tests. |

The immediate next work package is **APK analysis plus a BLE inventory from the physical sensor**. The APK supplies candidate behavior; the hardware validates it. Repository reuse should follow that evidence, not precede it.

**Bottom line:** Keep Windows/Python as the feasibility stage. Use existing projects selectively, keep the solution offline-first where the protocol permits it, and choose the Android implementation only after one useful configuration operation and the device's standalone behavior have been verified.

## Sources

Sources were reviewed on September 14, 2026. Repository statements describe the retrieved documentation, not an independent audit or guarantee of compatibility. S1 was available through indexed documentation only; direct retrieval failed during the review.

| Reference | Primary source |
| --- | --- |
| S1 | [LUMOKit-Public: indexed SDK documentation and repository lead][S1] |
| S2 | [samuelmr/lumolift: package purpose and archive status][S2] |
| S3 | [samuelmr/lumolift: HTTPS/OAuth configuration][S3] |
| S4 | [Open Posture Companion: features, architecture, license, and platform status][S4] |
| S5 | [Upright GO 1 reverse engineering: protocol reference, examples, and caution][S5] |
| S6 | [Nordic: nRF Connect for Android documentation][S6] |
| S7 | [Bleak documentation][S7] |
| S8 | [JADX: capabilities and decompilation limitations][S8] |
| S9 | [Apktool: Android package reverse-engineering tool][S9] |
| S10 | [BleakClient: pairing, reads, writes, and notifications][S10] |
| S11 | [Android Developers: logcat][S11] |
| S12 | [Android Open Source Project: Bluetooth verification and debugging][S12] |
| S13 | [Nordic: Android BLE Library][S13] |
| S14 | [Android Developers: Bluetooth permissions][S14] |
| S15 | [Android Developers: background BLE communication][S15] |

[S1]: https://github.com/talmaco/LUMOKit-Public
[S2]: https://github.com/samuelmr/lumolift
[S3]: https://github.com/samuelmr/lumolift/blob/master/config.js
[S4]: https://github.com/niltonheck/open-posture-companion
[S5]: https://github.com/niltonheck/upright-go-1-reverse-engineering
[S6]: https://github.com/nordicsemi/Android-nRF-Connect
[S7]: https://bleak.readthedocs.io/en/latest/
[S8]: https://github.com/skylot/jadx
[S9]: https://github.com/iBotPeaches/Apktool
[S10]: https://bleak.readthedocs.io/en/latest/api/client.html
[S11]: https://developer.android.com/tools/logcat
[S12]: https://source.android.com/docs/core/connect/bluetooth/verifying_debugging
[S13]: https://github.com/nordicsemi/Android-BLE-Library
[S14]: https://developer.android.com/develop/connectivity/bluetooth/bt-permissions
[S15]: https://developer.android.com/develop/connectivity/bluetooth/ble/background
