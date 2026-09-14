"""UI-independent async client for the verified Lumo Lift BLE protocol."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .ble_transport import LumoBulkTransport
from .protocol import (
    BatteryStateV2,
    DeviceVersion,
    PacketStreamDecoder,
    ProtocolError,
    decode_battery_property_v2,
    decode_json_payload,
    decode_packet,
    decode_version_property,
    encode_json_command,
    encode_packet,
)


LUMO_PRIMARY_SERVICE = "af120101-31d4-48e8-a1f8-5c09c020ae42"
MANUFACTURER_NAME_UUID = "00002a29-0000-1000-8000-00805f9b34fb"
VALID_FEEDBACK_DELAYS = (3, 5, 10, 15, 30, 45, 60, 120)


@dataclass(frozen=True, slots=True)
class DiscoveredLumo:
    name: str
    address: str
    rssi: int
    advertised_services: tuple[str, ...]
    device: BLEDevice = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class FeedbackSession:
    length_seconds: int
    remaining_seconds: int
    good_posture_seconds: int

    @property
    def active(self) -> bool:
        return self.remaining_seconds > 0


@dataclass(frozen=True, slots=True)
class DeviceSnapshot:
    name: str
    manufacturer: str
    version: DeviceVersion
    battery: BatteryStateV2
    coaching_enabled: bool
    feedback_delay_seconds: int
    feedback_session: FeedbackSession


@dataclass(frozen=True, slots=True)
class LumoEvent:
    packet_type: int
    kind: str
    values: dict[str, Any]
    raw_hex: str


class LumoLiftClient:
    """Reusable device API with no dependency on a particular user interface."""

    def __init__(self) -> None:
        self._client: BleakClient | None = None
        self._transport: LumoBulkTransport | None = None
        self._device: DiscoveredLumo | None = None
        self._original_communication: int | None = None
        self._operation_lock = asyncio.Lock()
        self._monitor_task: asyncio.Task | None = None
        self._event_handlers: list[Callable[[LumoEvent], None]] = []
        self._packet_stream = PacketStreamDecoder()

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    @property
    def device(self) -> DiscoveredLumo | None:
        return self._device

    def add_event_handler(self, handler: Callable[[LumoEvent], None]) -> None:
        if handler not in self._event_handlers:
            self._event_handlers.append(handler)

    def remove_event_handler(self, handler: Callable[[LumoEvent], None]) -> None:
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)

    @staticmethod
    async def discover(timeout: float = 10.0) -> list[DiscoveredLumo]:
        found = await BleakScanner.discover(timeout=timeout, return_adv=True)
        devices = []
        for device, advertisement in found.values():
            name = advertisement.local_name or device.name or ""
            services = tuple(service.lower() for service in advertisement.service_uuids)
            if name.lower().startswith("lumo") or LUMO_PRIMARY_SERVICE in services:
                devices.append(
                    DiscoveredLumo(
                        name=name or "Lumo",
                        address=device.address,
                        rssi=advertisement.rssi,
                        advertised_services=services,
                        device=device,
                    )
                )
        return sorted(devices, key=lambda candidate: candidate.rssi, reverse=True)

    async def connect(self, device: DiscoveredLumo | None = None) -> DeviceSnapshot:
        await self.stop_monitoring()
        if self.is_connected:
            return await self.refresh()
        if device is None:
            devices = await self.discover(timeout=15.0)
            if not devices:
                raise RuntimeError("No Lumo BLE device found")
            device = devices[0]

        client = BleakClient(device.device, timeout=20.0)
        await client.connect()
        transport = LumoBulkTransport(client, event_callback=self._handle_packet)
        try:
            await transport.start()
            self._client = client
            self._transport = transport
            self._device = device
            self._packet_stream.clear()
            self._original_communication = await self.get_communication_flags()
            await self._set_communication_flags(0x06)
            active_flags = await self.get_communication_flags()
            if active_flags != 0x06:
                raise RuntimeError(
                    f"Unable to activate Lumo session; flags are 0x{active_flags:02x}"
                )
            snapshot = await self.refresh()
            # One one-shot update populates live counters without enabling the
            # recurring monitoring task.
            await self.request_live_data()
            return snapshot
        except Exception:
            try:
                if self._original_communication is not None and client.is_connected:
                    try:
                        await self._set_communication_flags(self._original_communication)
                    except Exception:
                        pass
            finally:
                try:
                    await transport.close()
                finally:
                    await client.disconnect()
            self._client = None
            self._transport = None
            self._device = None
            self._original_communication = None
            self._packet_stream.clear()
            raise

    async def disconnect(self) -> None:
        await self.stop_monitoring()
        client = self._client
        transport = self._transport
        original_communication = self._original_communication
        try:
            if transport is not None and client is not None and client.is_connected:
                try:
                    if original_communication is not None:
                        await self._set_communication_flags(original_communication)
                        await asyncio.sleep(0.3)
                finally:
                    await transport.close()
        finally:
            if client is not None and client.is_connected:
                await client.disconnect()
            self._client = None
            self._transport = None
            self._device = None
            self._original_communication = None
            self._packet_stream.clear()

    def _require_transport(self) -> LumoBulkTransport:
        if not self.is_connected or self._transport is None:
            raise RuntimeError("Lumo device is not connected")
        return self._transport

    @staticmethod
    def _packet_filter(packet_type: int, predicate=None):
        def matches(packet: bytes) -> bool:
            actual_type, payload = decode_packet(packet)
            return actual_type == packet_type and (predicate is None or predicate(payload))

        return matches

    @staticmethod
    def _json_filter(expected_type: str):
        return LumoLiftClient._packet_filter(
            0x8000,
            lambda payload: decode_json_payload(payload).get("type") == expected_type,
        )

    async def _query_property(self, property_id: int) -> bytes:
        async with self._operation_lock:
            transport = self._require_transport()
            exchange = await transport.execute(
                encode_packet(1, bytes((property_id,))),
                response_filter=self._packet_filter(
                    1, lambda payload: bool(payload) and payload[0] == property_id
                ),
            )
        packet_type, payload = decode_packet(exchange.response_packet)
        if packet_type != 1:
            raise ProtocolError(f"Unexpected property packet type {packet_type}")
        return payload

    async def _query_json(self, command: str, timeout: float = 10.0) -> dict:
        async with self._operation_lock:
            exchange = await self._require_transport().execute(
                encode_json_command(command),
                timeout=timeout,
                response_filter=self._json_filter(command),
            )
        _, payload = decode_packet(exchange.response_packet)
        return decode_json_payload(payload)

    async def _set_json(self, command: str, *arguments: str) -> None:
        async with self._operation_lock:
            await self._require_transport().send_oneway(
                encode_json_command(command, *arguments)
            )
            await asyncio.sleep(0.35)

    async def _set_communication_flags(self, flags: int) -> None:
        async with self._operation_lock:
            await self._require_transport().send_oneway(
                encode_packet(2, bytes((6, flags)))
            )
            await asyncio.sleep(0.35)

    async def get_communication_flags(self) -> int:
        payload = await self._query_property(6)
        if len(payload) != 2:
            raise ProtocolError(f"Unexpected communication payload: {payload.hex()}")
        return payload[1]

    async def get_version(self) -> DeviceVersion:
        return decode_version_property(await self._query_property(1))

    async def get_battery(self) -> BatteryStateV2:
        return decode_battery_property_v2(await self._query_property(23))

    async def get_manufacturer(self) -> str:
        client = self._client
        if client is None or not client.is_connected:
            raise RuntimeError("Lumo device is not connected")
        raw = await client.read_gatt_char(MANUFACTURER_NAME_UUID)
        return bytes(raw).rstrip(b"\x00").decode("utf-8", errors="replace")

    async def get_coaching_enabled(self) -> bool:
        return str((await self._query_json("CHTOG"))["val"]) == "1"

    async def set_coaching_enabled(self, enabled: bool) -> bool:
        await self._set_json("CHTOG", "1" if enabled else "0")
        actual = await self.get_coaching_enabled()
        if actual != enabled:
            raise RuntimeError("Coaching setting failed read-back")
        return actual

    async def get_feedback_delay(self) -> int:
        return int((await self._query_json("AL_LEN_GET"))["val"])

    async def set_feedback_delay(self, seconds: int) -> int:
        if seconds not in VALID_FEEDBACK_DELAYS:
            raise ValueError(f"Delay must be one of {VALID_FEEDBACK_DELAYS}")
        await self._set_json("ALERTLEN", str(seconds))
        actual = await self.get_feedback_delay()
        if actual != seconds:
            raise RuntimeError(
                f"Feedback delay read-back is {actual}; expected {seconds}"
            )
        return actual

    async def get_feedback_session(self) -> FeedbackSession:
        message = await self._query_json("BSE_GET")
        return FeedbackSession(
            length_seconds=int(message.get("len", 0)),
            remaining_seconds=int(message.get("left", 0)),
            good_posture_seconds=int(message.get("tgood", 0)),
        )

    async def set_feedback_session_enabled(self, enabled: bool) -> FeedbackSession:
        await self._set_json("BSE_START" if enabled else "BSE_END")
        return await self.get_feedback_session()

    async def buzz(self) -> None:
        await self._set_json("BUZZ")

    async def refresh(self) -> DeviceSnapshot:
        if self._device is None:
            raise RuntimeError("Lumo device is not connected")
        version = await self.get_version()
        battery = await self.get_battery()
        coaching = await self.get_coaching_enabled()
        delay = await self.get_feedback_delay()
        feedback = await self.get_feedback_session()
        manufacturer = await self.get_manufacturer()
        return DeviceSnapshot(
            name=self._device.name,
            manufacturer=manufacturer,
            version=version,
            battery=battery,
            coaching_enabled=coaching,
            feedback_delay_seconds=delay,
            feedback_session=feedback,
        )

    async def request_live_data(self) -> None:
        async with self._operation_lock:
            await self._require_transport().send_oneway(encode_json_command("GET_LIVE"))

    async def start_monitoring(self, interval: float = 5.0) -> None:
        self._require_transport()
        if interval < 1.0:
            raise ValueError("Monitoring interval must be at least one second")
        if self._monitor_task and not self._monitor_task.done():
            return

        async def monitor() -> None:
            while self.is_connected:
                try:
                    await self.request_live_data()
                except Exception as error:
                    self._emit_event(
                        LumoEvent(-1, "monitor_error", {"error": str(error)}, "")
                    )
                await asyncio.sleep(interval)

        self._monitor_task = asyncio.create_task(monitor())

    async def stop_monitoring(self) -> None:
        task = self._monitor_task
        self._monitor_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _handle_packet(self, packet: bytes) -> None:
        try:
            for packet_type, payload, raw in self._packet_stream.feed(packet):
                if packet_type == 0x8000:
                    message = decode_json_payload(payload)
                    kind = str(message.get("type", "json"))
                    self._emit_event(LumoEvent(packet_type, kind, message, raw.hex()))
                else:
                    self._emit_event(
                        LumoEvent(
                            packet_type,
                            f"packet_{packet_type}",
                            {"payload_hex": payload.hex()},
                            raw.hex(),
                        )
                    )
        except Exception as error:
            self._emit_event(
                LumoEvent(-1, "decode_error", {"error": str(error)}, packet.hex())
            )

    def _emit_event(self, event: LumoEvent) -> None:
        for handler in tuple(self._event_handlers):
            try:
                handler(event)
            except Exception:
                pass
