"""Verified Lumo Lift bulk-transfer transport over a connected Bleak client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from bleak import BleakClient

from .protocol import BulkControl, chunk_bulk_payload, crc16_ccitt


SERVER_CONTROL_UUID = "af120201-31d4-48e8-a1f8-5c09c020ae42"
SERVER_DATA_UUID = "af120202-31d4-48e8-a1f8-5c09c020ae42"
CLIENT_CONTROL_UUID = "af120203-31d4-48e8-a1f8-5c09c020ae42"
CLIENT_DATA_UUID = "af120204-31d4-48e8-a1f8-5c09c020ae42"


@dataclass(frozen=True, slots=True)
class BulkExchange:
    request_control: BulkControl
    server_acknowledgement: BulkControl
    response_control: BulkControl
    response_packet: bytes


@dataclass(frozen=True, slots=True)
class BulkWriteAcknowledgement:
    request_control: BulkControl
    server_acknowledgement: BulkControl


class LumoBulkTransport:
    """Serialize request/response exchanges over the four bulk characteristics."""

    def __init__(
        self,
        client: BleakClient,
        event_callback: Callable[[bytes], None] | None = None,
    ):
        self.client = client
        self.event_callback = event_callback
        self._identifier = 0
        self._server_future = None
        self._response_future = None
        self._response_control = None
        self._response_data = bytearray()
        self._response_filter = None
        self._unsolicited_callback = None
        self._client_data_lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.client.start_notify(SERVER_CONTROL_UUID, self._on_server_control)
        await self.client.start_notify(CLIENT_CONTROL_UUID, self._on_client_control)
        await self.client.start_notify(CLIENT_DATA_UUID, self._on_client_data)
        self._started = True

    async def close(self) -> None:
        if not self._started:
            return
        await self.client.stop_notify(CLIENT_DATA_UUID)
        await self.client.stop_notify(CLIENT_CONTROL_UUID)
        await self.client.stop_notify(SERVER_CONTROL_UUID)
        self._started = False

    def _fail_response(self, error: Exception) -> None:
        if self._response_future and not self._response_future.done():
            self._response_future.set_exception(error)

    def _on_server_control(self, _sender, data: bytearray) -> None:
        try:
            control = BulkControl.decode(bytes(data))
            if (
                self._server_future
                and not self._server_future.done()
                and control.command == 2
                and control.identifier == self._identifier
            ):
                self._server_future.set_result(control)
        except Exception as error:
            if self._server_future and not self._server_future.done():
                self._server_future.set_exception(error)

    def _on_client_control(self, _sender, data: bytearray) -> None:
        try:
            control = BulkControl.decode(bytes(data))
            if control.command == 1:
                self._response_control = control
                self._response_data.clear()
        except Exception as error:
            self._fail_response(error)

    async def _on_client_data(self, _sender, data: bytearray) -> None:
        async with self._client_data_lock:
            await self._handle_client_data(data)

    async def _handle_client_data(self, data: bytearray) -> None:
        if self._response_control is None:
            # A previous one-way command can leave a late padded/unsolicited
            # data notification. It has no control metadata, so it cannot be
            # validated or acknowledged and must not satisfy the active query.
            return

        self._response_data.extend(data)
        if len(self._response_data) < self._response_control.length:
            return

        content = bytes(self._response_data[: self._response_control.length])
        result = 1 if crc16_ccitt(content) == self._response_control.crc else 2
        acknowledgement = BulkControl(
            command=self._response_control.command,
            action=self._response_control.action,
            result=result,
            identifier=self._response_control.identifier,
            length=self._response_control.length,
            crc=self._response_control.crc,
            address=self._response_control.address,
        )
        await self.client.write_gatt_char(
            CLIENT_CONTROL_UUID, acknowledgement.encode(), response=False
        )
        if result != 1:
            self._fail_response(RuntimeError("response bulk CRC mismatch"))
        elif self._response_future and not self._response_future.done():
            try:
                matches = self._response_filter is None or self._response_filter(content)
            except Exception as error:
                self._fail_response(error)
                matches = False
            if matches:
                self._response_future.set_result((self._response_control, content))
            elif self._unsolicited_callback is not None:
                self._unsolicited_callback(content)
            elif self.event_callback is not None:
                self.event_callback(content)
        elif result == 1 and self.event_callback is not None:
            self.event_callback(content)
        self._response_control = None
        self._response_data.clear()

    async def execute(
        self,
        application_packet: bytes,
        timeout: float = 10.0,
        response_filter: Callable[[bytes], bool] | None = None,
        unsolicited_callback: Callable[[bytes], None] | None = None,
    ) -> BulkExchange:
        if not self._started:
            raise RuntimeError("bulk transport is not started")
        if self._server_future is not None:
            raise RuntimeError("another bulk exchange is already active")

        loop = asyncio.get_running_loop()
        self._identifier = (self._identifier + 1) & 0xFF
        self._server_future = loop.create_future()
        self._response_future = loop.create_future()
        self._response_control = None
        self._response_data.clear()
        self._response_filter = response_filter
        self._unsolicited_callback = unsolicited_callback
        request_control = BulkControl(
            command=2,
            action=0,
            result=0,
            identifier=self._identifier,
            length=len(application_packet),
            crc=crc16_ccitt(application_packet),
            address=0,
        )

        try:
            await self.client.write_gatt_char(
                SERVER_CONTROL_UUID, request_control.encode(), response=False
            )
            for chunk in chunk_bulk_payload(application_packet):
                await self.client.write_gatt_char(SERVER_DATA_UUID, chunk, response=True)

            server_ack = await asyncio.wait_for(self._server_future, timeout)
            if server_ack.result != 1:
                raise RuntimeError(f"server rejected bulk request: {server_ack}")
            response_control, response_packet = await asyncio.wait_for(
                self._response_future, timeout
            )
            return BulkExchange(
                request_control, server_ack, response_control, response_packet
            )
        finally:
            self._server_future = None
            self._response_future = None
            self._response_control = None
            self._response_data.clear()
            self._response_filter = None
            self._unsolicited_callback = None

    async def send_oneway(
        self, application_packet: bytes, timeout: float = 10.0
    ) -> BulkWriteAcknowledgement:
        """Send an application packet that returns only a server acknowledgement."""

        if not self._started:
            raise RuntimeError("bulk transport is not started")
        if self._server_future is not None:
            raise RuntimeError("another bulk exchange is already active")

        loop = asyncio.get_running_loop()
        self._identifier = (self._identifier + 1) & 0xFF
        self._server_future = loop.create_future()
        request_control = BulkControl(
            command=2,
            action=0,
            result=0,
            identifier=self._identifier,
            length=len(application_packet),
            crc=crc16_ccitt(application_packet),
            address=0,
        )
        try:
            await self.client.write_gatt_char(
                SERVER_CONTROL_UUID, request_control.encode(), response=False
            )
            for chunk in chunk_bulk_payload(application_packet):
                await self.client.write_gatt_char(SERVER_DATA_UUID, chunk, response=True)
            server_ack = await asyncio.wait_for(self._server_future, timeout)
            if server_ack.result != 1:
                raise RuntimeError(f"server rejected bulk request: {server_ack}")
            return BulkWriteAcknowledgement(request_control, server_ack)
        finally:
            self._server_future = None
