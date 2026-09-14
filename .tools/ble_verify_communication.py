"""Verify the current Lumo communication flags without modifying them."""

import asyncio

from bleak import BleakClient, BleakScanner

from lumolift.ble_transport import LumoBulkTransport
from lumolift.protocol import decode_packet, encode_packet


def is_communication_property(packet: bytes) -> bool:
    packet_type, payload = decode_packet(packet)
    return packet_type == 1 and len(payload) == 2 and payload[0] == 6


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
    print(f"Connecting to {name!r} for communication-state verification...")
    async with BleakClient(device, timeout=20.0) as client:
        transport = LumoBulkTransport(client)
        await transport.start()
        try:
            exchange = await transport.execute(
                encode_packet(1, b"\x06"),
                response_filter=is_communication_property,
            )
            packet_type, payload = decode_packet(exchange.response_packet)
            print(f"packet_type={packet_type} communication_flags=0x{payload[1]:02x}")
        finally:
            await transport.close()

    print("Disconnected cleanly without changing communication flags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
