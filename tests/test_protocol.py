import unittest
import struct

from lumolift.protocol import (
    BulkControl,
    ProtocolError,
    chunk_bulk_payload,
    crc16_ccitt,
    decode_battery_property_v2,
    decode_json_payload,
    decode_packet,
    decode_version_property,
    encode_json_command,
    encode_packet,
)


class CrcTests(unittest.TestCase):
    def test_standard_ccitt_false_vector(self):
        self.assertEqual(crc16_ccitt(b"123456789"), 0x29B1)


class PacketTests(unittest.TestCase):
    def test_round_trip(self):
        packet = encode_packet(0x1234, b"payload")
        self.assertEqual(decode_packet(packet), (0x1234, b"payload"))

    def test_json_command_preserves_apk_format(self):
        packet = encode_json_command("CHTOG", "1")
        packet_type, payload = decode_packet(packet)
        self.assertEqual(packet_type, 0x8000)
        self.assertEqual(payload, b' {"CMD":"CHTOG:1"}\x00')

    def test_bad_crc_is_rejected(self):
        packet = bytearray(encode_packet(1, b"x"))
        packet[-1] ^= 1
        with self.assertRaisesRegex(ProtocolError, "CRC mismatch"):
            decode_packet(bytes(packet))

    def test_trailing_data_is_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "packet length"):
            decode_packet(encode_packet(1) + b"\x00")

    def test_oversized_payload_is_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "exceeds 500"):
            encode_packet(1, bytes(501))


class BulkControlTests(unittest.TestCase):
    def test_known_little_endian_layout(self):
        control = BulkControl(
            command=2,
            action=1,
            result=0,
            identifier=7,
            length=0x1234,
            crc=0x5678,
            address=0x90ABCDEF,
        )
        encoded = control.encode()
        self.assertEqual(encoded.hex(), "0201000734127856efcdab90")
        self.assertEqual(BulkControl.decode(encoded), control)

    def test_record_length_is_validated(self):
        with self.assertRaisesRegex(ProtocolError, "exactly 12"):
            BulkControl.decode(bytes(11))

    def test_field_range_is_validated(self):
        with self.assertRaisesRegex(ProtocolError, "unsigned range"):
            BulkControl(command=256).encode()


class ChunkTests(unittest.TestCase):
    def test_chunks_are_twenty_bytes_and_zero_padded(self):
        chunks = chunk_bulk_payload(bytes(range(21)))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], bytes(range(20)))
        self.assertEqual(chunks[1], b"\x14" + bytes(19))

    def test_exact_chunk_has_no_extra_chunk(self):
        self.assertEqual(chunk_bulk_payload(bytes(20)), [bytes(20)])

    def test_empty_payload_has_no_data_chunks(self):
        self.assertEqual(chunk_bulk_payload(b""), [])

    def test_maximum_is_enforced(self):
        self.assertEqual(len(chunk_bulk_payload(bytes(280))), 14)
        with self.assertRaisesRegex(ProtocolError, "exceeds 280"):
            chunk_bulk_payload(bytes(281))


class ResponseDecoderTests(unittest.TestCase):
    def test_version_property(self):
        payload = b"\x01" + struct.pack(">HHII", 0, 1, 102424, 0x0001007F)
        version = decode_version_property(payload)
        self.assertEqual((version.major, version.minor), (0, 1))
        self.assertEqual(version.revision, 102424)
        self.assertEqual(version.capabilities, 0x0001007F)

    def test_battery_property_v2(self):
        payload = (
            b"\x17"
            + struct.pack(">e??eed e".replace(" ", ""), 3.85, True, False, 0.05, -0.02, 0.5, 24.0)
        )
        battery = decode_battery_property_v2(payload)
        self.assertAlmostEqual(battery.voltage, 3.85, places=2)
        self.assertTrue(battery.has_usb_power)
        self.assertFalse(battery.is_charging)
        self.assertAlmostEqual(battery.reported_charge, 0.5)
        self.assertAlmostEqual(battery.voltage_charge_estimate, 0.5, places=2)

    def test_json_payload(self):
        self.assertEqual(
            decode_json_payload(b'{"type":"CHTOG","val":1}\x00'),
            {"type": "CHTOG", "val": 1},
        )


if __name__ == "__main__":
    unittest.main()
