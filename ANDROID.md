# Android application

The native Android client lives in `android/`. It uses Kotlin, Jetpack Compose,
Material 3, and the recovered offline BLE protocol; it has no Lumo cloud or
account-service dependency.

## Current status

- Debug APK builds successfully.
- JVM protocol tests pass.
- Android lint passes with no errors.
- Physical-phone BLE behavior remains to be verified.
- Android Studio is optional; the checked-in Gradle wrapper is sufficient when
  JDK 17 and Android SDK 37 are installed.

Debug APK:

```text
android/app/build/outputs/apk/debug/lumolift-revive.apk
```

## Features

- Runtime Bluetooth permission flow for old and current Android versions.
- Scan by `Lumo*` name or the verified primary service UUID.
- Serialized GATT writes, descriptor configuration, timeouts, and error
  propagation.
- Verified `ZO` framing, CRC-16, bulk-transfer acknowledgements, and concatenated
  frame decoding.
- One initial refresh/live request with monitoring off by default.
- Explicit Start/Stop monitoring; Stop disables the sensor active flag.
- Firmware, native battery, coaching, alert-delay, feedback-session, posture,
  activity, step, calorie, and good-posture displays.
- Material 3 dashboard with adaptive Monitoring/Steps layout.
- Locally persisted step continuity and goal.
- User-confirmed coaching, alert-delay, feedback-session, vibration, owner, and
  user-profile actions.
- User profile commands remain direct-to-device and owner uses an empty second
  `OWN` argument as requested.

Firmware, reset, arbitrary console commands, minting, and unknown tolerance
writes are not exposed.

## Architecture

| Package/file | Responsibility |
| --- | --- |
| `protocol/LumoProtocol.kt` | UI-independent frames, CRC, stream decoder, chunks, and bulk control |
| `device/AndroidBleConnection.kt` | BLE scan, GATT connection, permissions, reads/writes, and notifications |
| `device/LumoBulkTransport.kt` | Serialized bulk exchanges, acknowledgements, response filtering, and events |
| `device/AndroidLumoRepository.kt` | UI-independent device features, lifecycle, read-back, and monitoring |
| `device/Models.kt` | Repository interface and immutable domain models |
| `MainViewModel.kt` | Lifecycle state, persistent counters/goal, and error handling |
| `LumoApp.kt` | Adaptive Material 3 Compose screens |
| `MainActivity.kt` | Permission launcher and Compose host |

The UI depends only on `LumoRepository`; device/protocol logic can be tested or
reused independently.

## Build

From `android/`, with JDK 17 and the Android SDK configured:

```powershell
.\gradlew.bat test lintDebug assembleDebug
```

This workspace also contains an ignored local toolchain under
`android/.toolchain/`. Android Studio was not installed because the command-line
toolchain built and linted the application successfully.

## Install on a connected phone

Enable USB debugging, connect the target phone, then run:

```powershell
adb install -r .\app\build\outputs\apk\debug\lumolift-revive.apk
```

Put the Lumo Lift in pairing mode before selecting **Scan & connect**. Grant the
Bluetooth permissions requested by Android. The first physical test should
verify connection, refresh, monitoring stop, coaching read-back, and clean
disconnect before testing profile or feedback writes.
