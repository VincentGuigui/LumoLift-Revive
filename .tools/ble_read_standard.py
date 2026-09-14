"""Read only the standard Manufacturer Name and Battery Level values."""

import asyncio

from bleak import BleakClient, BleakScanner


MANUFACTURER_NAME_UUID = "00002a29-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


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
    print(f"Connecting to {name!r} for standard read-only queries...")
    async with BleakClient(device, timeout=20.0) as client:
        manufacturer_raw = await client.read_gatt_char(MANUFACTURER_NAME_UUID)
        battery_raw = await client.read_gatt_char(BATTERY_LEVEL_UUID)
        manufacturer = bytes(manufacturer_raw).rstrip(b"\x00").decode(
            "utf-8", errors="replace"
        )
        battery = battery_raw[0] if len(battery_raw) == 1 else None
        print(f"manufacturer={manufacturer!r}")
        print(f"battery_raw={bytes(battery_raw).hex()}")
        print(f"battery_percent={battery!r}")

    print("Disconnected cleanly without subscriptions or writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
