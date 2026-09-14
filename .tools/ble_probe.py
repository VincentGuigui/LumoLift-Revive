"""Read-only BLE discovery and GATT inventory for the Lumo investigation."""

import asyncio
import sys

from bleak import BleakClient, BleakScanner


async def main() -> int:
    print("Scanning for BLE advertisements for 20 seconds...")
    discovered = await BleakScanner.discover(timeout=20.0, return_adv=True)
    candidates = []

    for device, advertisement in discovered.values():
        name = advertisement.local_name or device.name or ""
        print(
            f"seen name={name!r} address={device.address} "
            f"rssi={advertisement.rssi} services={advertisement.service_uuids}"
        )
        if name.lower().startswith("lumo"):
            candidates.append((device, advertisement, name))

    if not candidates:
        print("No BLE device whose name starts with 'Lumo' was found.")
        return 2

    candidates.sort(key=lambda item: item[1].rssi, reverse=True)
    device, advertisement, name = candidates[0]
    print(f"Connecting read-only to {name!r} ({device.address})...")

    async with BleakClient(device, timeout=20.0) as client:
        print(f"connected={client.is_connected}")
        for service in client.services:
            print(f"service {service.uuid} {service.description}")
            for characteristic in service.characteristics:
                properties = ",".join(characteristic.properties)
                print(
                    f"  characteristic {characteristic.uuid} "
                    f"properties={properties} description={characteristic.description}"
                )
                for descriptor in characteristic.descriptors:
                    print(
                        f"    descriptor {descriptor.uuid} "
                        f"description={descriptor.description}"
                    )

    print("Disconnected cleanly without reads, subscriptions, or writes.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
