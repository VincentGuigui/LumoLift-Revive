"""Request only the Lumo device-version property through bulk transfer."""

import asyncio
import struct

from bleak import BleakClient, BleakScanner

from lumolift.protocol import (
    BulkControl,
    chunk_bulk_payload,
    crc16_ccitt,
    decode_packet,
    encode_packet,
)


SERVER_CONTROL_UUID = "af120201-31d4-48e8-a1f8-5c09c020ae42"
SERVER_DATA_UUID = "af120202-31d4-48e8-a1f8-5c09c020ae42"
CLIENT_CONTROL_UUID = "af120203-31d4-48e8-a1f8-5c09c020ae42"
CLIENT_DATA_UUID = "af120204-31d4-48e8-a1f8-5c09c020ae42"


async def find_lumo():
    discovered = await BleakScanner.discover(timeout=20.0, return_adv=True)
    candidates = []
    for device, advertisement in discovered.values():
        name = advertisement.local_name or device.name or ""
        if name.lower().startswith("lumo"):
            candidates.append((advertisement.rssi, device, name))
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate[0])


def parse_version_property(payload: bytes) -> str:
    if len(payload) != 13 or payload[0] != 1:
        return f"unexpected_property_payload={payload.hex()}"
    major, minor, revision, capabilities = struct.unpack(">HHII", payload[1:])
    return (
        f"version={major}.{minor} revision={revision} "
        f"capabilities=0x{capabilities:08x}"
    )


async def main() -> int:
    print("Scanning for a Lumo BLE device for 20 seconds...")
    found = await find_lumo()
    if found is None:
        print("No BLE device whose name starts with 'Lumo' was found.")
        return 2

    _, device, name = found
    server_ack = asyncio.Event()
    response_complete = asyncio.Event()
    response_control = None
    response_data = bytearray()
    response_packet = None
    response_error = None

    print(f"Connecting to {name!r} for a version-property query...")
    async with BleakClient(device, timeout=20.0) as client:

        def on_server_control(_sender, data: bytearray) -> None:
            nonlocal response_error
            try:
                control = BulkControl.decode(bytes(data))
                print(
                    "server_control "
                    f"command={control.command} result={control.result} "
                    f"identifier={control.identifier}"
                )
                if control.command == 2 and control.identifier == 1:
                    if control.result != 1:
                        response_error = f"server rejected transfer: {control}"
                    server_ack.set()
            except Exception as error:  # Preserve diagnostics from device input.
                response_error = f"invalid server control: {error}"
                server_ack.set()

        def on_client_control(_sender, data: bytearray) -> None:
            nonlocal response_control, response_error
            try:
                control = BulkControl.decode(bytes(data))
                print(
                    "client_control "
                    f"command={control.command} length={control.length} "
                    f"crc=0x{control.crc:04x} identifier={control.identifier}"
                )
                if control.command == 1:
                    response_control = control
            except Exception as error:
                response_error = f"invalid client control: {error}"
                response_complete.set()

        async def on_client_data(_sender, data: bytearray) -> None:
            nonlocal response_packet, response_error
            if response_control is None:
                response_error = "client data arrived before client control"
                response_complete.set()
                return

            response_data.extend(data)
            if len(response_data) < response_control.length:
                return

            content = bytes(response_data[: response_control.length])
            result = 1 if crc16_ccitt(content) == response_control.crc else 2
            acknowledgement = BulkControl(
                command=response_control.command,
                action=response_control.action,
                result=result,
                identifier=response_control.identifier,
                length=response_control.length,
                crc=response_control.crc,
                address=response_control.address,
            )
            await client.write_gatt_char(
                CLIENT_CONTROL_UUID, acknowledgement.encode(), response=False
            )
            if result != 1:
                response_error = "response bulk CRC mismatch"
            else:
                response_packet = content
            response_complete.set()

        await client.start_notify(SERVER_CONTROL_UUID, on_server_control)
        await client.start_notify(CLIENT_CONTROL_UUID, on_client_control)
        await client.start_notify(CLIENT_DATA_UUID, on_client_data)

        # Packet type 1 requests the listed property IDs; property 1 is version.
        request = encode_packet(1, b"\x01")
        control = BulkControl(
            command=2,
            action=0,
            result=0,
            identifier=1,
            length=len(request),
            crc=crc16_ccitt(request),
            address=0,
        )
        print(
            f"request packet={request.hex()} bulk_crc=0x{control.crc:04x} "
            "property=1"
        )
        await client.write_gatt_char(
            SERVER_CONTROL_UUID, control.encode(), response=False
        )
        for chunk in chunk_bulk_payload(request):
            await client.write_gatt_char(SERVER_DATA_UUID, chunk, response=True)

        await asyncio.wait_for(server_ack.wait(), timeout=10.0)
        if response_error:
            raise RuntimeError(response_error)
        await asyncio.wait_for(response_complete.wait(), timeout=10.0)
        if response_error:
            raise RuntimeError(response_error)
        if response_packet is None:
            raise RuntimeError("response completed without packet data")

        packet_type, payload = decode_packet(response_packet)
        print(f"response packet_type={packet_type} payload={payload.hex()}")
        if packet_type != 1:
            raise RuntimeError(f"unexpected response packet type {packet_type}")
        print(parse_version_property(payload))

        await client.stop_notify(CLIENT_DATA_UUID)
        await client.stop_notify(CLIENT_CONTROL_UUID)
        await client.stop_notify(SERVER_CONTROL_UUID)

    print("Disconnected cleanly; no configuration command was sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
