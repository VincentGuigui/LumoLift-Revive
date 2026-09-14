# Minimal Python application

## Run

On the current Windows/Codex host, put the Lumo Lift into pairing mode and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lumolift.ps1
```

For a portable Python installation:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m lumolift
```

Python 3.10 or newer and a Bluetooth LE adapter are required. The app is
offline-first and does not use the discontinued Lumo account or cloud service.

## Application features

| Area | Capability | Evidence/status |
| --- | --- | --- |
| Connection | Discover `Lumo*`, connect, initialize plugin/active communication, perform one refresh/`GET_LIVE` request, restore original flags on disconnect | Hardware-verified transport; app-level smoke test pending device advertising |
| Device | Manufacturer, firmware revision/capabilities, native voltage/charge/temperature | Hardware-verified |
| Coaching | Read, enable, disable, and verify by read-back | Hardware-verified, including reconnect persistence |
| Feedback delay | Read current delay; set one of 3, 5, 10, 15, 30, 45, 60, or 120 seconds with read-back | Read verified; write recovered from APK, pending live app verification |
| Feedback session | Read total/remaining/good-posture time; start or stop with confirmation | Read verified; start/stop recovered from APK, not yet live-tested |
| Vibration | Request the APK's `BUZZ` test | Recovered from APK, not yet physically confirmed |
| Monitoring | Poll `GET_LIVE`, display JSON events, activity, angle, steps, and posture | Off by default; connection makes one one-shot live request, then polling starts only when selected |
| Step gauges | Progress bars for daily `STEPS` and `STEPSH` (hour-boundary baseline) | UI implemented; updated from live events |
| Steps goal | Validate and Apply a local goal (minimum 100, default 10,000) used by both gauges | Local-only; no device BLE goal command exists in the APK |
| Device profile | Read hardware/software IDs and owner; edit owner, height, weight, gender, and age | Direct device actions with confirmation; user-field read-back remains unconfirmed |
| Local thresholds | Classify forward/good/back with adjustable display thresholds | UI-independent local calculation; does not modify sensor firmware |

The APK's default display thresholds are forward below 85°, good from 85°
through 95°, and back above 95°. These are used only to interpret live `REC`
events. The device commands `SBB_GET` and `SBF_GET` time out on firmware revision
102424, and no supported setters were found, so the app does not invent device
angle/tolerance controls.

The original APK's steps goal screen validates a minimum of 100 steps and saves
the selected value as `STEP_GOAL` in app preferences. Goals are represented in
the cloud goals database; no `sendCommand`/BLE packet applies a steps goal to
the sensor. The Python app therefore labels its Apply action “local gauge” and
does not claim to write the goal to the device.

The APK also contains a cloud `LKGoal` model with defaults of 10,000 steps and
14,400 good-posture seconds (four hours). That is a cloud/app objective model,
not evidence of an additional sensor configuration endpoint.

Target-posture calibration remains a physical-device operation. The APK handles
`CALIB_START` as an incoming event and does not establish it as a safe outgoing
command.

## Architecture

The UI contains no BLE framing or device policy:

| Module | Responsibility |
| --- | --- |
| `python/lumolift/protocol.py` | Pure packet, CRC, JSON, bulk-control, property, and telemetry codecs |
| `python/lumolift/ble_transport.py` | Serialized GATT bulk-transfer request/response transport and unsolicited events |
| `python/lumolift/client.py` | UI-independent discovery, lifecycle, configuration, read-back, and monitoring API |
| `python/lumolift/monitoring.py` | Pure posture classification with replaceable local thresholds |
| `python/lumolift/steps.py` | Pure step-goal validation and progress calculations |
| `python/lumolift/gui.py` | Minimal Tkinter presentation and background-event-loop bridge |
| `python/lumolift/__main__.py` | `python -m lumolift` entry point |

Another UI, command-line client, Android bridge, or automated test harness can
reuse `LumoLiftClient` without importing Tkinter.

The **Profile & investigation** tab shows the APK's recovered formats for
height, weight, gender, and age. Its probe button sends those command names with
no argument, one at a time, after confirmation. The editable fields send direct
sensor commands only. Owner application requires a password because the
recovered command is `OWN(owner, password)` and is verified using `OWNER_GET`.
The APK sources that password from the original Lumo account login; it is not a
new device-specific password.

## Reusable API example

```python
import asyncio
from lumolift.client import LumoLiftClient


async def inspect():
    client = LumoLiftClient()
    try:
        snapshot = await client.connect()
        print(snapshot.version, snapshot.battery)
        print("coaching:", await client.get_coaching_enabled())
        print("delay:", await client.get_feedback_delay())
    finally:
        await client.disconnect()


asyncio.run(inspect())
```

Configuration methods validate inputs and read settings back where a query is
available. `disconnect()` stops monitoring and restores the communication flags
that were present before connection.

## Tests

Run the UI-independent suite from the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path '.\python').Path
python -m unittest discover -s tests -v
```

The suite currently covers protocol framing, CRCs, bulk-control byte order,
limits, telemetry decoding, JSON decoding, and posture classification. Hardware
smoke tests are kept under `.tools/` and preserve or restore original settings.
