"""Run the native battery and coaching-state read-only queries."""

import asyncio

from bleak import BleakClient, BleakScanner

from lumolift.ble_transport import LumoBulkTransport
from lumolift.protocol import (
    decode_battery_property_v2,
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


def print_exchange(label, exchange) -> None:
    print(
        f"{label} request_id={exchange.request_control.identifier} "
        f"server_result={exchange.server_acknowledgement.result} "
        f"response_id={exchange.response_control.identifier} "
        f"response_length={exchange.response_control.length}"
    )


async def main() -> int:
    print("Scanning for a Lumo BLE device for 20 seconds...")
    found = await find_lumo()
    if found is None:
        print("No BLE device whose name starts with 'Lumo' was found.")
        return 2

    _, device, name = found
    print(f"Connecting to {name!r} for read-only native queries...")
    async with BleakClient(device, timeout=20.0) as client:
        transport = LumoBulkTransport(client)
        await transport.start()
        try:
            battery_exchange = await transport.execute(encode_packet(1, b"\x17"))
            print_exchange("battery", battery_exchange)
            packet_type, payload = decode_packet(battery_exchange.response_packet)
            if packet_type != 1:
                raise RuntimeError(f"unexpected battery packet type {packet_type}")
            battery = decode_battery_property_v2(payload)
            print(
                f"battery voltage={battery.voltage:.4f}V "
                f"usb_power={battery.has_usb_power} charging={battery.is_charging} "
                f"charge_current={battery.charge_current:.6f}A "
                f"system_current={battery.system_current:.6f}A "
                f"reported_charge={battery.reported_charge:.6f} "
                f"voltage_estimate={battery.voltage_charge_estimate:.3f} "
                f"temperature={battery.temperature:.3f}"
            )

            coach_exchange = await transport.execute(encode_json_command("CHTOG"))
            print_exchange("coach", coach_exchange)
            packet_type, payload = decode_packet(coach_exchange.response_packet)
            if packet_type != 0x8000:
                raise RuntimeError(f"unexpected coaching packet type {packet_type}")
            message = decode_json_payload(payload)
            print(f"coach response={message!r}")
        finally:
            await transport.close()

    print("Disconnected cleanly; no configuration command was sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
