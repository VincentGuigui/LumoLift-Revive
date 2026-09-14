"""Verify coaching state across reconnects and restore the original value."""

import asyncio

from bleak import BleakClient

from lumolift.ble_transport import LumoBulkTransport
from ble_verify_coach_toggle import (
    find_lumo,
    query_coach,
    read_communication,
    set_coach,
    set_communication,
)


async def session(label: str, set_value: str | None = None) -> str:
    found = await find_lumo()
    if found is None:
        raise RuntimeError("no Lumo BLE device found")
    _, device, name = found
    print(f"{label}: connecting to {name!r}...")
    async with BleakClient(device, timeout=20.0) as client:
        transport = LumoBulkTransport(client)
        await transport.start()
        original_communication = None
        try:
            original_communication = await read_communication(transport)
            await set_communication(transport, 0x06)
            before = await query_coach(transport)
            print(f"{label}: coach_before={before}")
            if set_value is not None:
                await set_coach(transport, set_value)
                after = await query_coach(transport)
                print(f"{label}: coach_after={after}")
                if after != set_value:
                    raise RuntimeError(
                        f"{label}: read-back {after!r} did not match {set_value!r}"
                    )
                return after
            return before
        finally:
            try:
                if original_communication is not None:
                    await set_communication(transport, original_communication)
                    print(
                        f"{label}: communication_restored="
                        f"0x{original_communication:02x}"
                    )
            finally:
                await transport.close()


async def main() -> int:
    print("Each discovery scan can take up to 20 seconds.")
    original = await session("baseline")
    test_value = "0" if original == "1" else "1"
    restore_needed = True
    try:
        await session("set-test", test_value)
        persisted_test = await session("verify-test-reconnect")
        if persisted_test != test_value:
            raise RuntimeError(
                f"test value did not persist: {persisted_test!r} != {test_value!r}"
            )
        print(f"persistence verified for test value {test_value}")

        await session("restore-original", original)
        persisted_original = await session("verify-restore-reconnect")
        if persisted_original != original:
            raise RuntimeError(
                f"restored value did not persist: {persisted_original!r} != {original!r}"
            )
        restore_needed = False
        print(f"restoration verified for original value {original}")
    finally:
        if restore_needed:
            print(f"safety restore: setting coaching back to {original}")
            await session("safety-restore", original)

    print("Persistence test complete; original coaching state restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
