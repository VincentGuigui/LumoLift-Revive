# BLE Probe Config Queries (Android)

## Purpose

Standalone Android port of `.tools/ble_probe_config_queries.py`, to re-run the
same probe directly from a phone instead of a Windows/Bleak setup.

It connects to the nearest BLE advertiser named `Lumo*`, reads and enables
communication mode `0x06`, then queries `BSE_GET`, `AL_LEN_GET`, `SBB_GET`, and
`SBF_GET` in order (20 s timeout each), logging each reply or `TIMEOUT`.

It then runs an **experimental round-trip write test** for `SBB` and `SBF`:
write a value one unit away from the value just read, read it back to verify,
then restore the original value. This only runs for a command whose original
value was actually read (not `TIMEOUT`) — without a known original there is
nothing safe to restore to, so the test is skipped instead of guessing. No
setter command name for `SBB`/`SBF` is documented anywhere in this project
(see `PROTOCOL.md`/`COMMANDS.md`); the test tries `<NAME>_SET` then bare
`<NAME>` — the only two setter-naming conventions already seen in this
protocol for sibling commands (`BSE_GET`/`BSE_SET`, `AL_LEN_GET`/`AL_LEN`) —
and skips the write entirely if the sensor acknowledges neither.

The original communication mode is always restored before disconnecting.

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
SBF_GET={"type":"SBF_GET","val":"5"}
--- Test aller-retour (expérimental, nom du setter non documenté) ---
SBB: ignoré (valeur d'origine inconnue, SBB_GET a timeout — restauration impossible)
SBF original=5, valeur de test=4
SBF: setter 'SBF_SET' rejeté
SBF: setter 'SBF' rejeté
SBF: aucun setter candidat accepté, aucune écriture effectuée
communication_restored=0x00
Terminé.
```

A `SBB_GET` timeout reproduces what was already observed with the Python
probe on firmware revision `102424` (see `PROTOCOL.md` and `COMMANDS.md` at
the repository root); a non-timeout `SBF_GET` reply, as seen above, means
this firmware answers that query even though the earlier Python run did not
— worth re-running the Python probe too to confirm this isn't intermittent.
If both setter candidates are rejected, the actual setter name (if any) is
still undocumented.

## Source layout

| File | Purpose |
| --- | --- |
| `Protocol.kt` | Packet framing, CRC16, JSON command encode/decode — ported from `LumoProtocol.kt` / `python/lumolift/protocol.py`. |
| `BleConnection.kt` | GATT scan/connect/notify/write — ported from `AndroidBleConnection.kt`. |
| `BulkTransport.kt` | Request/response bulk-transfer exchange — ported from `LumoBulkTransport.kt`. |
| `MainActivity.kt` | Reproduces the exact probe sequence from `ble_probe_config_queries.py`. |
