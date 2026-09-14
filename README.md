# Lumofit Revival

## Main goal

Restore useful configuration and posture-alert functionality for the owner's
Bluetooth posture sensor without relying on its discontinued mobile app.

The first successful outcome is deliberately small:

> An independent client connects to the identified sensor, performs one useful
> reversible configuration operation, verifies the result, reconnects
> successfully, and determines whether posture alerts work without a phone.

The project will begin with a Windows/Python diagnostic tool. An Android
replacement will be chosen and built only after the device protocol and its
operating model have been verified.

## Documentation

| File | Purpose |
| --- | --- |
| [README.md](README.md) | Main goal, current state, scope, and documentation index. |
| [STRATEGY.md](STRATEGY.md) | Detailed research and development strategy. |
| [PROTOCOL.md](PROTOCOL.md) | Authoritative BLE, packet, command, and evidence record. |
| [COMMANDS.md](COMMANDS.md) | Complete recovered BLE command, event, packet-type, and property inventory. |
| [BLE_PROBE.md](BLE_PROBE.md) | How the read-only Windows BLE probe works, how to run it, and its observed output. |
| [APP.md](APP.md) | Python application setup, features, evidence status, architecture, and reusable API. |
| [AGENTS.md](AGENTS.md) | Short repository instructions and pointers for coding agents. |
| [CODEX.md](CODEX.md) | Redirect to the shared agent instructions. |

This index tracks the project-authored Markdown files. Third-party documentation
inside downloaded tools and private generated APK output is not part of the
project documentation set.

## Current context

- The hardware and supplied APK are now identified as **Lumo Lift**. The APK is
  package `com.lumobodytech.lumolift`, version `2.0.7`.
- The original Android app no longer launches. Its untouched APK and private
  decompilation output are kept under `Lumo-Bodytech/`.
- A Windows BLE scan found the sensor advertising as `LUMO:`. A read-only
  connection and GATT service enumeration succeeded; no values or commands
  were written.
- Static analysis confirms that the live sensor and APK use the same
  proprietary `af12…` UUID family. The recovered bulk-transfer transport and a
  read-only version-property query are now verified on hardware.
- The device reports manufacturer `zero2one`, firmware `0.1`, revision `102424`,
  and capabilities `0x0001007f`. Its native telemetry reported about `3.846 V`
  and `50%` charge; the standard Battery Level characteristic's raw `00` is not
  a valid charge estimate for this device.
- Coaching control is verified: `CHTOG` changed from `1` to `0`, survived a
  reconnect, was restored to `1`, and survived a second reconnect.
- A minimalist Python/Tkinter configuration and monitoring app is available via
  `run_lumolift.ps1`. Its BLE client, transport, codecs, and posture classifier
  are reusable without the UI; see `APP.md`.
- The app displays daily `STEPS` and `STEPSH` gauges. The steps goal is a local
  gauge target only: APK analysis found no device-side goal command.
- Existing open-source posture-sensor projects may provide investigation
  methods or interface architecture, but do not demonstrate compatibility with
  this sensor.

## Project approach

1. **Preserve and identify.** Keep untouched private copies of the APK and
   existing app data. Record the hardware label/model, APK package and version,
   Bluetooth adapter, and discovered transport.
2. **Investigate APK and hardware together.** Inspect the APK for discovery,
   service UUIDs, packet construction, response parsing, settings, and any
   initialization or authorization requirements. Independently inventory the
   sensor's Bluetooth services and characteristics.
3. **Prove one safe operation in Python.** If the device uses BLE, build a
   small Bleak-based command-line diagnostic client. Start with reads and known
   notifications; only write commands supported by evidence.
4. **Test the operating model.** After a verified configuration change,
   disconnect and test alert behavior, persistence, calibration, and power-cycle
   behavior.
5. **Build the Android MVP.** Choose native Kotlin or an adapted application
   architecture only after the required protocol and lifecycle are understood.

## Next work package

Test whether enabled coaching produces posture alerts after the client fully
disconnects, and determine the calibration lifecycle. Capture controlled
activity/radar notifications while wearing and moving the sensor. Keep the
verified coaching state and communication-state restoration checks in every
experiment.

Preserve raw payloads with timestamps and keep interpretations tentative until
hardware tests confirm them.

## Evidence gates

| Gate | Requirement |
| --- | --- |
| G1 — Identity and discovery | **Complete:** hardware/app identity, transport, and discovery results are documented. |
| G2 — Protocol foothold | **Complete:** bulk transport and the read-only version-property request are hardware-verified. |
| G3 — Independent control | **Complete:** coaching was changed, read back, persisted across reconnect, and restored. |
| G4 — Operating model | Offline alerts, persistence, and calibration lifecycle are tested. |
| G5 — Android MVP | Required functions work on the target phone, including permission and lifecycle cases. |

## Safety and scope

Do not uninstall the original app, delete its data, clear Bluetooth bonds, or
factory-reset the sensor during investigation. Do not send arbitrary writes,
probe firmware/bootloader/reset endpoints, or attempt firmware replacement.

State-changing commands must be explicitly understood, allowlisted, serialized,
and verified by read-back, response, or observed physical behavior. A successful
Bluetooth write alone does not prove that a setting took effect.

Keep original APKs, unsanitized captures, device identifiers, and credentials
private. Share only sanitized evidence and independently implemented code.

## Planned project contents

```text
README.md       Project goal, scope, and setup context
STRATEGY.md     Detailed research and development strategy
PROTOCOL.md     Authoritative device protocol findings and unknowns
COMMANDS.md     Recovered BLE command and property inventory
BLE_PROBE.md    Read-only BLE probe usage and observed service inventory
APP.md          Python app setup, capabilities, and reusable architecture
AGENTS.md       Agent entry point and safety instructions
CODEX.md        Redirect to AGENTS.md
python/         Windows diagnostic client and packet codecs
android/        Mobile implementation, after the protocol is proven
tests/          Sanitized packet fixtures and regression tests
evidence/       Device maps and selected sanitized captures
run_lumolift.ps1 Windows launcher for the Python application
pyproject.toml   Installable Python package metadata
```

`STRATEGY.md` is the detailed decision record. `PROTOCOL.md` will become the
single source of truth for device-specific findings, using these evidence states:
**unknown**, **inferred from code**, **observed in traffic**, and **verified on
hardware**.

## Explicit non-goals for the first milestone

The first milestone does not attempt to recreate the vendor account system,
cloud synchronization, dashboards, firmware updating, broad historical
statistics, or a polished desktop interface. It also does not promise settings
such as sensitivity, vibration intensity, or alert delay until the recovered
protocol proves that they are supported.
