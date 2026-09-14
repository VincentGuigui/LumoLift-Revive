"""Query coaching state while temporarily enabling session communication."""

import asyncio

from bleak import BleakClient, BleakScanner

from lumolift.ble_transport import LumoBulkTransport
from lumolift.protocol import (
    decode_json_payload,
    decode_packet,
    encode_json_command,
    encode_packet,
)


async def find_lumo():
    discovered = await BleakScanner.discover(timeout=20.0, return_adv=True)
    candidates = []
    for device, advertisement in discovered.values():
        name = advertisement.local_name or device.name or ""
        if name.lower().startswith("lumo"):
            candidates.append((advertisement.rssi, device, name))
    return max(candidates, key=lambda candidate: candidate[0]) if candidates else None


async def read_communication_flags(transport: LumoBulkTransport) -> int:
    def is_communication_property(packet: bytes) -> bool:
        packet_type, payload = decode_packet(packet)
        return packet_type == 1 and len(payload) == 2 and payload[0] == 6

    exchange = await transport.execute(
        encode_packet(1, b"\x06"),
        response_filter=is_communication_property,
        unsolicited_callback=log_unsolicited,
    )
    packet_type, payload = decode_packet(exchange.response_packet)
    if packet_type != 1 or len(payload) != 2 or payload[0] != 6:
        raise RuntimeError(
            f"unexpected communication property response: type={packet_type} "
            f"payload={payload.hex()}"
        )
    return payload[1]


def log_unsolicited(packet: bytes) -> None:
    try:
        packet_type, payload = decode_packet(packet)
        print(f"unsolicited packet_type={packet_type} payload_length={len(payload)}")
    except Exception as error:
        print(f"unsolicited invalid_packet={error}")


def is_coach_response(packet: bytes) -> bool:
    packet_type, payload = decode_packet(packet)
    if packet_type != 0x8000:
        return False
    return decode_json_payload(payload).get("type") == "CHTOG"


async def set_communication_flags(transport: LumoBulkTransport, flags: int) -> None:
    acknowledgement = await transport.send_oneway(
        encode_packet(2, bytes((6, flags)))
    )
    print(
        f"communication set=0x{flags:02x} "
        f"request_id={acknowledgement.request_control.identifier} "
        f"server_result={acknowledgement.server_acknowledgement.result}"
    )


async def main() -> int:
    print("Scanning for a Lumo BLE device for 20 seconds...")
    found = await find_lumo()
    if found is None:
        print("No BLE device whose name starts with 'Lumo' was found.")
        return 2

    _, device, name = found
    print(f"Connecting to {name!r} for an active-session coaching query...")
    async with BleakClient(device, timeout=20.0) as client:
        transport = LumoBulkTransport(client)
        await transport.start()
        original_flags = None
        try:
            original_flags = await read_communication_flags(transport)
            print(f"communication original=0x{original_flags:02x}")
            # Plugin + active. Keep upload disabled to avoid historical type-4 traffic.
            await set_communication_flags(transport, 0x06)
            active_flags = await read_communication_flags(transport)
            print(f"communication verified_active=0x{active_flags:02x}")
            if active_flags != 0x06:
                raise RuntimeError("device did not report the requested active flags")

            exchange = await transport.execute(
                encode_json_command("CHTOG"),
                response_filter=is_coach_response,
                unsolicited_callback=log_unsolicited,
            )
            packet_type, payload = decode_packet(exchange.response_packet)
            if packet_type != 0x8000:
                raise RuntimeError(f"unexpected coaching packet type {packet_type}")
            print(f"coach response={decode_json_payload(payload)!r}")
        finally:
            try:
                if original_flags is not None:
                    await set_communication_flags(transport, original_flags)
                    print(
                        f"communication restore_acknowledged=0x{original_flags:02x}"
                    )
            finally:
                await transport.close()

    print("Disconnected cleanly; original communication flags restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
