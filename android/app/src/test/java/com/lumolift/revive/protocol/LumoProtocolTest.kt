package com.lumolift.revive.protocol

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LumoProtocolTest {
    @Test fun crcKnownVector() = assertEquals(0x29b1, LumoProtocol.crc16("123456789".toByteArray()))

    @Test fun packetRoundTrip() {
        val packet = LumoProtocol.encode(0x1234, "payload".toByteArray())
        val frame = LumoProtocol.decode(packet)
        assertEquals(0x1234, frame.type)
        assertArrayEquals("payload".toByteArray(), frame.payload)
    }

    @Test fun splitsConcatenatedFrames() {
        val first = LumoProtocol.encode(1, byteArrayOf(1))
        val second = LumoProtocol.encode(2, byteArrayOf(2))
        val decoder = FrameStreamDecoder()
        assertTrue(decoder.feed(first.copyOfRange(0, 3)).isEmpty())
        val result = decoder.feed(first.copyOfRange(3, first.size) + second)
        assertEquals(listOf(1, 2), result.map { it.type })
    }

    @Test fun bulkControlIsLittleEndian() {
        val encoded = BulkControl(2, 1, 0, 7, 0x1234, 0x5678, 0x90abcdef).encode()
        assertEquals("0201000734127856efcdab90", encoded.joinToString("") { "%02x".format(it) })
        assertEquals(0x90abcdef, BulkControl.decode(encoded).address)
    }
}
