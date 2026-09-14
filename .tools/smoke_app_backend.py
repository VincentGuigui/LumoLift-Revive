"""Hardware smoke test for the reusable client with delay restoration."""

import asyncio

from lumolift.client import LumoLiftClient


def describe(snapshot) -> str:
    return (
        f"name={snapshot.name!r} firmware={snapshot.version.major}."
        f"{snapshot.version.minor}r{snapshot.version.revision} "
        f"battery={snapshot.battery.reported_charge * 100:.1f}% "
        f"coaching={snapshot.coaching_enabled} "
        f"delay={snapshot.feedback_delay_seconds}s "
        f"feedback_active={snapshot.feedback_session.active}"
    )


async def main() -> int:
    client = LumoLiftClient()
    events = []
    client.add_event_handler(events.append)
    original_delay = None
    restored = False
    try:
        snapshot = await client.connect()
        print(f"initial {describe(snapshot)}")
        original_delay = snapshot.feedback_delay_seconds
        test_delay = 10 if original_delay != 10 else 15

        await client.start_monitoring(interval=2.0)
        await asyncio.sleep(5.0)
        await client.stop_monitoring()
        print(f"monitor_events={len(events)} kinds={[event.kind for event in events]}")

        actual = await client.set_feedback_delay(test_delay)
        print(f"delay_set={actual}")
        await client.disconnect()

        persisted = await client.connect()
        print(f"after_test_reconnect delay={persisted.feedback_delay_seconds}")
        if persisted.feedback_delay_seconds != test_delay:
            raise RuntimeError("test feedback delay did not persist")

        restored_value = await client.set_feedback_delay(original_delay)
        print(f"delay_restored={restored_value}")
        await client.disconnect()

        final = await client.connect()
        print(f"after_restore_reconnect delay={final.feedback_delay_seconds}")
        if final.feedback_delay_seconds != original_delay:
            raise RuntimeError("original feedback delay did not persist after restoration")
        restored = True
        return 0
    finally:
        if client.is_connected:
            await client.disconnect()
        if original_delay is not None and not restored:
            print(f"safety_restore delay={original_delay}")
            await client.connect()
            await client.set_feedback_delay(original_delay)
            await client.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
