# Read-only BLE probe

## Purpose

`.tools/ble_probe.py` is the first Windows diagnostic for this project. It finds
nearby BLE advertisers whose local name starts with `Lumo`, connects to the
strongest matching device, prints its GATT services, characteristics, and
descriptors, then disconnects.

The probe is intentionally non-invasive. It does not pair, read characteristic
values, enable notifications, or write commands. GATT service discovery happens
as part of establishing the connection.

## Requirements

- Windows with a working Bluetooth LE adapter
- Python 3.12 or another version supported by the installed Bleak release
- Bleak, installed locally under `.tools/pydeps`

Install the dependency locally from PowerShell:

```powershell
python -m pip install --target .tools\pydeps bleak
```

On this Codex host, Python is supplied by the bundled workspace runtime rather
than the system `PATH`. Its current executable is:

```text
C:\Users\vince\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

## Run

Put the Lumo Lift into advertising/pairing mode, keep it near the computer, and
run from the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path '.tools\pydeps').Path
python .tools\ble_probe.py
```

When using this workspace's bundled runtime, replace `python` with the full
executable path shown above. The scan lasts 20 seconds. Exit code `2` means that
no device with a name beginning with `Lumo` was found.

## Verified discovery result

The probe ran successfully on September 14, 2026:

| Observation | Result |
| --- | --- |
| Advertised name | `LUMO:` |
| Signal during scan | `-50 dBm` |
| Advertised service | `af120101-31d4-48e8-a1f8-5c09c020ae42` |
| Connection | Successful |
| Disconnection | Clean |
| Reads, subscriptions, or writes | None |

The Bluetooth address is treated as a private device identifier and is not
recorded here.

## Exposed services and characteristics

| Service UUID | Characteristic UUID | Properties |
| --- | --- | --- |
| `00001800-0000-1000-8000-00805f9b34fb` | `00002a00-0000-1000-8000-00805f9b34fb` | Read, write, write without response |
| `00001800-0000-1000-8000-00805f9b34fb` | `00002a01-0000-1000-8000-00805f9b34fb` | Read |
| `00001800-0000-1000-8000-00805f9b34fb` | `00002a04-0000-1000-8000-00805f9b34fb` | Read |
| `00001801-0000-1000-8000-00805f9b34fb` | — | No characteristic printed by Bleak |
| `af120002-31d4-48e8-a1f8-5c09c020ae42` | `af120201-31d4-48e8-a1f8-5c09c020ae42` | Notify, write without response |
| `af120002-31d4-48e8-a1f8-5c09c020ae42` | `af120202-31d4-48e8-a1f8-5c09c020ae42` | Write |
| `af120002-31d4-48e8-a1f8-5c09c020ae42` | `af120203-31d4-48e8-a1f8-5c09c020ae42` | Notify, write without response |
| `af120002-31d4-48e8-a1f8-5c09c020ae42` | `af120204-31d4-48e8-a1f8-5c09c020ae42` | Notify |
| `af120003-31d4-48e8-a1f8-5c09c020ae42` | `af120301-31d4-48e8-a1f8-5c09c020ae42` | Read, notify, write without response |
| `af120101-31d4-48e8-a1f8-5c09c020ae42` | `af121001-31d4-48e8-a1f8-5c09c020ae42` | Notify |
| `af120101-31d4-48e8-a1f8-5c09c020ae42` | `af121002-31d4-48e8-a1f8-5c09c020ae42` | Write without response |
| `0000180a-0000-1000-8000-00805f9b34fb` | `00002a29-0000-1000-8000-00805f9b34fb` | Read |
| `0000180f-0000-1000-8000-00805f9b34fb` | `00002a19-0000-1000-8000-00805f9b34fb` | Read |

Every notifying characteristic exposed the standard Client Characteristic
Configuration descriptor `00002902-0000-1000-8000-00805f9b34fb`. The standard
Manufacturer Name and Battery Level characteristics exposed presentation-format
descriptor `00002904-0000-1000-8000-00805f9b34fb`.

The proprietary roles inferred from APK analysis are documented separately in
[PROTOCOL.md](PROTOCOL.md). The probe reports the GATT surface only and must stay
free of protocol writes.

## Companion read-only diagnostics

The following scripts extend discovery without sending a configuration command:

| Script | Action | Verified result |
| --- | --- | --- |
| `.tools/ble_read_standard.py` | Reads standard Manufacturer Name and Battery Level. | Manufacturer `zero2one`; battery raw `00`. |
| `.tools/ble_listen_readonly.py` | Temporarily enables radar `0301` and activity `1001` notifications for 30 seconds. | No idle payloads; subscriptions disabled cleanly. |
| `.tools/ble_query_version.py` | Uses the recovered bulk protocol to request property `1`. | Firmware `0.1`, revision `102424`, capabilities `0x0001007f`. |
| `.tools/ble_query_readonly.py` | Queries native battery property `23` and coaching state. | About 50% charge; coaching `1`. |
| `.tools/ble_query_coach_active.py` | Temporarily enables plugin/active communication and queries `CHTOG`. | Query succeeds; communication restoration acknowledged. |
| `.tools/ble_verify_communication.py` | Reads communication property `6` on a fresh connection. | Restored value `0x00`. |
| `.tools/ble_verify_coach_toggle.py` | Toggles coaching and restores it in one connection. | Verified `1 → 0 → 1`. |
| `.tools/ble_verify_coach_persistence.py` | Verifies test and restored values across separate connections. | `0` and restored `1` both persisted. |
| `.tools/ble_probe_config_queries.py` | Queries feedback session, alert delay, and tolerance commands. | Session and delay replied; tolerance queries timed out. |
| `.tools/smoke_app_backend.py` | Exercises the reusable high-level client and restores delay after testing. | Pending: sensor was not advertising during the attempted run. |
| `.tools/smoke_gui.py` | Constructs and closes the Tkinter UI without Bluetooth access. | Passed; requested layout `692×678`. |

The notification listener performs only the standard, reversible Client
Characteristic Configuration descriptor writes needed to enable and disable
notifications. The version query writes an APK-documented read request and the
required response acknowledgement; it does not send a JSON command or alter a
setting.

Run the version query with both dependency roots on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = (Resolve-Path '.\python').Path + ';' + `
    (Resolve-Path '.tools\pydeps').Path
python .tools\ble_query_version.py
```

The packet and bulk-transfer implementation is in
`python/lumolift/protocol.py`; the serialized live transport is in
`python/lumolift/ble_transport.py`. Run the tests with:

```powershell
$env:PYTHONPATH = (Resolve-Path '.\python').Path
python -m unittest discover -s tests -v
```

## Expected console flow

```text
Scanning for BLE advertisements for 20 seconds...
seen name='LUMO:' ...
Connecting read-only to 'LUMO:' (...)
connected=True
service ...
  characteristic ...
Disconnected cleanly without reads, subscriptions, or writes.
```

Addresses are printed locally for diagnostics but should be removed from shared
logs and documentation.
