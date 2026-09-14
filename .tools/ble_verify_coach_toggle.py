"""Reversibly toggle coaching off and restore its original state."""

import asyncio

from bleak import BleakClient, BleakScanner

from lumolift.ble_transport import LumoBulkTransport
from lumolift.protocol import decode_json_payload, decode_packet, encode_json_command, encode_packet


def is_communication_property(packet: bytes) -> bool:
    packet_type, payload = decode_packet(packet)
    return packet_type == 1 and len(payload) == 2 and payload[0] == 6


def is_coach_response(packet: bytes) -> bool:
    packet_type, payload = decode_packet(packet)
    return packet_type == 0x8000 and decode_json_payload(payload).get("type") == "CHTOG"


async def find_lumo():
    discovered = await BleakScanner.discover(timeout=20.0, return_adv=True)
    candidates = []
    for device, advertisement in discovered.values():
        name = advertisement.local_name or device.name or ""
        if name.lower().startswith("lumo"):
            candidates.append((advertisement.rssi, device, name))
    return max(candidates, key=lambda candidate: candidate[0]) if candidates else None


async def set_communication(transport: LumoBulkTransport, flags: int) -> None:
    result = await transport.send_oneway(encode_packet(2, bytes((6, flags))))
    if result.server_acknowledgement.result != 1:
        raise RuntimeError("communication write was not acknowledged")
    await asyncio.sleep(0.5)


async def read_communication(transport: LumoBulkTransport) -> int:
    exchange = await transport.execute(
        encode_packet(1, b"\x06"), response_filter=is_communication_property
    )
    _, payload = decode_packet(exchange.response_packet)
    return payload[1]


async def query_coach(transport: LumoBulkTransport) -> str:
    exchange = await transport.execute(
        encode_json_command("CHTOG"), response_filter=is_coach_response
    )
    _, payload = decode_packet(exchange.response_packet)
    return str(decode_json_payload(payload)["val"])


async def set_coach(transport: LumoBulkTransport, value: str) -> None:
    acknowledgement = await transport.send_oneway(encode_json_command("CHTOG", value))
    if acknowledgement.server_acknowledgement.result != 1:
        raise RuntimeError("coaching write was not acknowledged")
    await asyncio.sleep(0.5)


async def main() -> int:
    print("Scanning for a Lumo BLE device for 20 seconds...")
    found = await find_lumo()
    if found is None:
        print("No BLE device whose name starts with 'Lumo' was found.")
        return 2

    _, device, name = found
    print(f"Connecting to {name!r} for a reversible coaching-state test...")
    async with BleakClient(device, timeout=20.0) as client:
        transport = LumoBulkTransport(client)
        await transport.start()
        original_communication = None
        original_coach = None
        try:
            original_communication = await read_communication(transport)
            print(f"communication original=0x{original_communication:02x}")
            await set_communication(transport, 0x06)
            print(f"communication active=0x{await read_communication(transport):02x}")

            original_coach = await query_coach(transport)
            print(f"coach original={original_coach}")
            test_value = "0" if original_coach == "1" else "1"
            await set_coach(transport, test_value)
            print(f"coach set={test_value}")
            verified_test = await query_coach(transport)
            print(f"coach verified_test={verified_test}")
            if verified_test != test_value:
                raise RuntimeError("coaching test value failed read-back")

            await set_coach(transport, original_coach)
            print(f"coach restored={original_coach}")
            verified_restore = await query_coach(transport)
            print(f"coach verified_restore={verified_restore}")
            if verified_restore != original_coach:
                raise RuntimeError("coaching original value failed read-back")
        finally:
            try:
                try:
                    if original_coach is not None:
                        current = await query_coach(transport)
                        print(f"coach final_check={current}")
                        if current != original_coach:
                            await set_coach(transport, original_coach)
                            print(f"coach emergency_restore={original_coach}")
                finally:
                    if original_communication is not None:
                        await set_communication(transport, original_communication)
                        print(f"communication restored=0x{original_communication:02x}")
            finally:
                await transport.close()

    print("Disconnected cleanly with original coaching and communication states restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
