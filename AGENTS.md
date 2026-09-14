# LumoLift Revival agent context

Start with [README.md](README.md) for the project goal and current scope. Read
[STRATEGY.md](STRATEGY.md) before making implementation decisions, and use
[PROTOCOL.md](PROTOCOL.md) as the authoritative protocol record. Application
architecture and usage are documented in [APP.md](APP.md).
Native Android architecture and build instructions are in
[ANDROID.md](ANDROID.md).

Current investigation inputs:

- Original app APK: `Lumo-Bodytech/com-lumobodytech-lumolift.apk` (private;
  preserve unchanged)
- Private decompilation output: `Lumo-Bodytech/decompiled/`
- Physical sensor: BLE connection verified; advertises as `LUMO:`

Do not send unidentified state-changing Bluetooth commands, reset the sensor,
or alter/remove the original APK or related app data.
