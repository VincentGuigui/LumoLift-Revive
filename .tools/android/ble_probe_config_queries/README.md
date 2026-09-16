# BLE Probe Config Queries (Android)

## Purpose

Standalone Android port of `.tools/ble_probe_config_queries.py`, to re-run the
same probe directly from a phone instead of a Windows/Bleak setup.

It connects to the nearest BLE advertiser named `Lumo*`, reads and enables
communication mode `0x06`, then queries `BSE_GET`, `AL_LEN_GET`, `SBB_GET`, and
`SBF_GET` in order, logging each reply or `TIMEOUT`. The original communication
mode is restored before disconnecting. No setter command is ever sent, and no
setting is changed on the device.

This app is independent of the main `android/` project (own Gradle root, own
package `com.lumolift.tools.bleprobeconfigqueries`) so it can be built and
installed without touching the main app.

## Build

From this directory, with JDK 17 and the Android SDK configured:

```powershell
.\gradlew.bat assembleDebug
```

```bash
./gradlew assembleDebug
```

The output APK is:

```text
app/build/outputs/apk/debug/ble_probe_config_queries.apk
```

## Install and run

Enable USB debugging, connect the target phone, then run:

```bash
adb install -r app/build/outputs/apk/debug/ble_probe_config_queries.apk
```

Put the Lumo Lift in pairing/advertising mode, launch the app, grant the
requested Bluetooth permissions, and tap **Lancer le sondage**. Results are
logged on screen line by line, e.g.:

```text
communication original=0x00
BSE_GET={"type":"BSE_GET","len":32000,"left":24792,"tgood":96}
AL_LEN_GET={"type":"AL_LEN_GET","val":15}
SBB_GET=TIMEOUT
SBF_GET=TIMEOUT
communication_restored=0x00
Terminé.
```

A `SBB_GET`/`SBF_GET` timeout reproduces what was already observed with the
Python probe on firmware revision `102424` (see `PROTOCOL.md` and
`COMMANDS.md` at the repository root); a non-timeout reply here would mean a
different firmware answers these queries.

## Source layout

| File | Purpose |
| --- | --- |
| `Protocol.kt` | Packet framing, CRC16, JSON command encode/decode — ported from `LumoProtocol.kt` / `python/lumolift/protocol.py`. |
| `BleConnection.kt` | GATT scan/connect/notify/write — ported from `AndroidBleConnection.kt`. |
| `BulkTransport.kt` | Request/response bulk-transfer exchange — ported from `LumoBulkTransport.kt`. |
| `MainActivity.kt` | Reproduces the exact probe sequence from `ble_probe_config_queries.py`. |
