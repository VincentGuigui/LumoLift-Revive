"""Probe APK-documented configuration queries without changing settings."""

import asyncio

from bleak import BleakClient

from lumolift.ble_transport import LumoBulkTransport
from lumolift.protocol import decode_json_payload, decode_packet, encode_json_command
from ble_verify_coach_toggle import (
    find_lumo,
    read_communication,
    set_communication,
)


def response_filter(expected_type: str):
    def matches(packet: bytes) -> bool:
        packet_type, payload = decode_packet(packet)
        return (
            packet_type == 0x8000
            and decode_json_payload(payload).get("type") == expected_type
        )

    return matches


async def main() -> int:
    found = await find_lumo()
    if found is None:
        print("No Lumo BLE device found.")
        return 2
    _, device, name = found
    print(f"Connecting to {name!r} for configuration queries...")
    async with BleakClient(device, timeout=20.0) as client:
        transport = LumoBulkTransport(client)
        await transport.start()
        original_communication = None
        try:
            original_communication = await read_communication(transport)
            await set_communication(transport, 0x06)
            for command in ("BSE_GET", "AL_LEN_GET", "SBB_GET", "SBF_GET"):
                try:
                    exchange = await transport.execute(
                        encode_json_command(command),
                        response_filter=response_filter(command),
                        timeout=6.0,
                    )
                    _, payload = decode_packet(exchange.response_packet)
                    print(f"{command}={decode_json_payload(payload)!r}")
                except TimeoutError:
                    print(f"{command}=TIMEOUT")
        finally:
            try:
                if original_communication is not None:
                    await set_communication(transport, original_communication)
                    print(f"communication_restored=0x{original_communication:02x}")
            finally:
                await transport.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
