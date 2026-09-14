"""Temporarily subscribe to known Lumo notification characteristics."""

import asyncio
from datetime import datetime

from bleak import BleakClient, BleakScanner


RADAR_UUID = "af120301-31d4-48e8-a1f8-5c09c020ae42"
ACTIVITY_UUID = "af121001-31d4-48e8-a1f8-5c09c020ae42"
LISTEN_SECONDS = 30


def notification(sender, data: bytearray) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    print(f"{timestamp} uuid={sender.uuid} data={bytes(data).hex()}", flush=True)


async def main() -> int:
    print("Scanning for a Lumo BLE device for 20 seconds...")
    discovered = await BleakScanner.discover(timeout=20.0, return_adv=True)
    candidates = []
    for device, advertisement in discovered.values():
        name = advertisement.local_name or device.name or ""
        if name.lower().startswith("lumo"):
            candidates.append((advertisement.rssi, device, name))

    if not candidates:
        print("No BLE device whose name starts with 'Lumo' was found.")
        return 2

    _, device, name = max(candidates, key=lambda candidate: candidate[0])
    print(f"Connecting to {name!r} for a passive notification capture...")
    async with BleakClient(device, timeout=20.0) as client:
        subscribed = []
        for characteristic_uuid in (RADAR_UUID, ACTIVITY_UUID):
            await client.start_notify(characteristic_uuid, notification)
            subscribed.append(characteristic_uuid)
            print(f"subscribed={characteristic_uuid}")

        print(f"Listening for {LISTEN_SECONDS} seconds; no protocol commands sent...")
        await asyncio.sleep(LISTEN_SECONDS)

        for characteristic_uuid in reversed(subscribed):
            await client.stop_notify(characteristic_uuid)
            print(f"unsubscribed={characteristic_uuid}")

    print("Disconnected cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
