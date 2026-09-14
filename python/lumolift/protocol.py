"""Pure codecs inferred from the Lumo Lift 2.0.7 Android APK.

This module performs no Bluetooth operations. In particular, importing or
calling it cannot communicate with a physical sensor.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import struct


MAGIC = b"ZO"
JSON_PACKET_TYPE = 0x8000
MAX_PACKET_PAYLOAD = 500
BULK_CHUNK_SIZE = 20
MAX_BULK_CHUNKS = 14
MAX_BULK_PAYLOAD = BULK_CHUNK_SIZE * MAX_BULK_CHUNKS


class ProtocolError(ValueError):
    """Raised when encoded or received protocol data is invalid."""


def crc16_ccitt(data: bytes) -> int:
    """Return the APK's CRC-16/CCITT-FALSE value for *data*."""

    crc = 0xFFFF
    for byte in data:
        for bit_index in range(8):
            input_bit = (byte >> (7 - bit_index)) & 1
            top_bit = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if top_bit ^ input_bit:
                crc ^= 0x1021
    return crc


def encode_packet(packet_type: int, payload: bytes = b"") -> bytes:
    """Encode one big-endian Lumo application packet."""

    if not 0 <= packet_type <= 0xFFFF:
        raise ProtocolError("packet type must fit in an unsigned 16-bit field")
    if len(payload) > MAX_PACKET_PAYLOAD:
        raise ProtocolError(f"payload exceeds {MAX_PACKET_PAYLOAD} bytes")

    body = MAGIC + struct.pack(">HH", packet_type, len(payload)) + payload
    return body + struct.pack(">H", crc16_ccitt(body))


def decode_packet(packet: bytes) -> tuple[int, bytes]:
    """Validate and decode exactly one Lumo application packet."""

    if len(packet) < 8:
        raise ProtocolError("packet is shorter than the 8-byte minimum")
    if packet[:2] != MAGIC:
        raise ProtocolError("packet does not start with the ZO magic bytes")

    packet_type, payload_length = struct.unpack(">HH", packet[2:6])
    if payload_length > MAX_PACKET_PAYLOAD:
        raise ProtocolError(f"payload exceeds {MAX_PACKET_PAYLOAD} bytes")
    expected_length = 6 + payload_length + 2
    if len(packet) != expected_length:
        raise ProtocolError(
            f"packet length is {len(packet)} bytes; expected {expected_length}"
        )

    received_crc = struct.unpack(">H", packet[-2:])[0]
    expected_crc = crc16_ccitt(packet[:-2])
    if received_crc != expected_crc:
        raise ProtocolError(
            f"CRC mismatch: received 0x{received_crc:04x}, "
            f"expected 0x{expected_crc:04x}"
        )
    return packet_type, packet[6:-2]


def encode_json_command(command: str, *arguments: str) -> bytes:
    """Encode the APK's packet type 0x8000 JSON-command representation."""

    if not command or any(character in command for character in '\" :,'):
        raise ProtocolError("command must be a non-empty protocol token")

    values = [str(argument) for argument in arguments]
    if any(any(character in value for character in '\" ,') for value in values):
        raise ProtocolError("arguments may not contain quotes, spaces, or commas")

    command_value = command
    if values:
        command_value += ":" + ",".join(values)
    json_text = f' {{"CMD":"{command_value}"}}'
    if len(json_text) > 100:
        raise ProtocolError("JSON command exceeds the APK's 100-character limit")
    return encode_packet(JSON_PACKET_TYPE, json_text.encode("utf-8") + b"\x00")


@dataclass(frozen=True, slots=True)
class BulkControl:
    """The 12-byte little-endian bulk-transfer control record."""

    command: int
    action: int = 0
    result: int = 0
    identifier: int = 0
    length: int = 0
    crc: int = 0
    address: int = 0

    _STRUCT = struct.Struct("<BBBBHHI")

    def encode(self) -> bytes:
        values = (
            self.command,
            self.action,
            self.result,
            self.identifier,
            self.length,
            self.crc,
            self.address,
        )
        limits = (0xFF, 0xFF, 0xFF, 0xFF, 0xFFFF, 0xFFFF, 0xFFFFFFFF)
        if any(not 0 <= value <= limit for value, limit in zip(values, limits)):
            raise ProtocolError("bulk-control field is outside its unsigned range")
        return self._STRUCT.pack(*values)

    @classmethod
    def decode(cls, data: bytes) -> BulkControl:
        if len(data) != cls._STRUCT.size:
            raise ProtocolError("bulk-control record must be exactly 12 bytes")
        return cls(*cls._STRUCT.unpack(data))


def chunk_bulk_payload(payload: bytes) -> list[bytes]:
    """Split and zero-pad an application packet into 20-byte GATT writes."""

    if len(payload) > MAX_BULK_PAYLOAD:
        raise ProtocolError(f"bulk payload exceeds {MAX_BULK_PAYLOAD} bytes")
    return [
        payload[offset : offset + BULK_CHUNK_SIZE].ljust(BULK_CHUNK_SIZE, b"\x00")
        for offset in range(0, len(payload), BULK_CHUNK_SIZE)
    ]


@dataclass(frozen=True, slots=True)
class DeviceVersion:
    major: int
    minor: int
    revision: int
    capabilities: int


def decode_version_property(payload: bytes) -> DeviceVersion:
    """Decode the payload of a property-1 response."""

    if len(payload) != 13 or payload[0] != 1:
        raise ProtocolError("version response must be property 1 with 12 data bytes")
    return DeviceVersion(*struct.unpack(">HHII", payload[1:]))


@dataclass(frozen=True, slots=True)
class BatteryStateV2:
    voltage: float
    has_usb_power: bool
    is_charging: bool
    charge_current: float
    system_current: float
    reported_charge: float
    temperature: float

    @property
    def voltage_charge_estimate(self) -> float:
        """Return the APK's initial non-charging voltage-based charge estimate."""

        return min(1.0, max(0.0, (self.voltage - 3.6) / 0.5))


def decode_battery_property_v2(payload: bytes) -> BatteryStateV2:
    """Decode the payload of a property-23 battery response."""

    if len(payload) != 19 or payload[0] != 23:
        raise ProtocolError("battery response must be property 23 with 18 data bytes")
    voltage = struct.unpack(">e", payload[1:3])[0]
    has_usb_power = bool(payload[3])
    is_charging = bool(payload[4])
    charge_current = struct.unpack(">e", payload[5:7])[0]
    system_current = struct.unpack(">e", payload[7:9])[0]
    reported_charge = struct.unpack(">d", payload[9:17])[0]
    temperature = struct.unpack(">e", payload[17:19])[0]
    return BatteryStateV2(
        voltage,
        has_usb_power,
        is_charging,
        charge_current,
        system_current,
        reported_charge,
        temperature,
    )


def decode_json_payload(payload: bytes) -> dict:
    """Decode one null-terminated JSON response payload."""

    terminator = payload.find(b"\x00")
    if terminator < 0:
        raise ProtocolError("JSON response is not null-terminated")
    if any(payload[terminator + 1 :]):
        raise ProtocolError("JSON response has non-zero data after its terminator")
    try:
        value = json.loads(payload[:terminator].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"invalid JSON response: {error}") from error
    if not isinstance(value, dict):
        raise ProtocolError("JSON response root must be an object")
    return value
