package com.lumolift.revive.protocol

import java.nio.ByteBuffer
import java.nio.ByteOrder

object LumoProtocol {
    const val JSON_TYPE = 0x8000
    const val MAX_PAYLOAD = 500
    const val BULK_CHUNK = 20
    const val MAX_BULK = 280
    private val magic = byteArrayOf(0x5a, 0x4f)

    fun crc16(data: ByteArray): Int {
        var crc = 0xffff
        data.forEach { value ->
            val byte = value.toInt() and 0xff
            repeat(8) { bit ->
                val inputBit = (byte shr (7 - bit)) and 1
                val topBit = (crc shr 15) and 1
                crc = (crc shl 1) and 0xffff
                if ((topBit xor inputBit) != 0) crc = crc xor 0x1021
            }
        }
        return crc and 0xffff
    }

    fun encode(type: Int, payload: ByteArray = byteArrayOf()): ByteArray {
        require(type in 0..0xffff) { "Packet type must fit in 16 bits" }
        require(payload.size <= MAX_PAYLOAD) { "Payload exceeds $MAX_PAYLOAD bytes" }
        val body = ByteBuffer.allocate(6 + payload.size).order(ByteOrder.BIG_ENDIAN)
            .put(magic).putShort(type.toShort()).putShort(payload.size.toShort())
            .put(payload).array()
        return body + ByteBuffer.allocate(2).order(ByteOrder.BIG_ENDIAN)
            .putShort(crc16(body).toShort()).array()
    }

    fun decode(packet: ByteArray): Frame {
        require(packet.size >= 8) { "Packet is shorter than 8 bytes" }
        require(packet[0] == magic[0] && packet[1] == magic[1]) { "Invalid ZO magic" }
        val header = ByteBuffer.wrap(packet).order(ByteOrder.BIG_ENDIAN)
        header.position(2)
        val type = header.short.toInt() and 0xffff
        val length = header.short.toInt() and 0xffff
        require(length <= MAX_PAYLOAD) { "Payload exceeds $MAX_PAYLOAD bytes" }
        require(packet.size == length + 8) { "Packet length mismatch" }
        val expected = crc16(packet.copyOf(packet.size - 2))
        val received = ByteBuffer.wrap(packet, packet.size - 2, 2)
            .order(ByteOrder.BIG_ENDIAN).short.toInt() and 0xffff
        require(received == expected) { "CRC mismatch" }
        return Frame(type, packet.copyOfRange(6, 6 + length), packet)
    }

    fun jsonCommand(command: String, vararg arguments: String): ByteArray {
        require(command.matches(Regex("[A-Z0-9_]+"))) { "Invalid command token" }
        require(arguments.none { it.contains(',') || it.contains('"') || it.contains(' ') }) {
            "Invalid command argument"
        }
        val value = if (arguments.isEmpty()) command else "$command:${arguments.joinToString(",")}" 
        val text = " {\"CMD\":\"$value\"}"
        require(text.length <= 100) { "Command exceeds 100 characters" }
        return encode(JSON_TYPE, text.toByteArray(Charsets.UTF_8) + 0)
    }

    fun chunks(data: ByteArray): List<ByteArray> {
        require(data.size <= MAX_BULK) { "Bulk payload exceeds $MAX_BULK bytes" }
        return data.asList().chunked(BULK_CHUNK).map { part ->
            ByteArray(BULK_CHUNK).also { chunk -> part.forEachIndexed { i, b -> chunk[i] = b } }
        }
    }
}

data class Frame(val type: Int, val payload: ByteArray, val raw: ByteArray)

class FrameStreamDecoder {
    private var buffer = byteArrayOf()

    fun clear() { buffer = byteArrayOf() }

    fun feed(bytes: ByteArray): List<Frame> {
        buffer += bytes
        val result = mutableListOf<Frame>()
        while (true) {
            val start = buffer.indices.firstOrNull {
                it + 1 < buffer.size && buffer[it] == 0x5a.toByte() && buffer[it + 1] == 0x4f.toByte()
            } ?: run {
                buffer = if (buffer.lastOrNull() == 0x5a.toByte()) byteArrayOf(0x5a) else byteArrayOf()
                return result
            }
            if (start > 0) buffer = buffer.copyOfRange(start, buffer.size)
            if (buffer.size < 6) return result
            val length = ByteBuffer.wrap(buffer, 4, 2).order(ByteOrder.BIG_ENDIAN).short.toInt() and 0xffff
            if (length > LumoProtocol.MAX_PAYLOAD) {
                buffer = buffer.copyOfRange(1, buffer.size)
                continue
            }
            val total = length + 8
            if (buffer.size < total) return result
            val raw = buffer.copyOfRange(0, total)
            buffer = buffer.copyOfRange(total, buffer.size)
            result += LumoProtocol.decode(raw)
        }
    }
}

data class BulkControl(
    val command: Int,
    val action: Int = 0,
    val result: Int = 0,
    val identifier: Int = 0,
    val length: Int = 0,
    val crc: Int = 0,
    val address: Long = 0,
) {
    fun encode(): ByteArray = ByteBuffer.allocate(12).order(ByteOrder.LITTLE_ENDIAN)
        .put(command.toByte()).put(action.toByte()).put(result.toByte()).put(identifier.toByte())
        .putShort(length.toShort()).putShort(crc.toShort()).putInt(address.toInt()).array()

    companion object {
        fun decode(data: ByteArray): BulkControl {
            require(data.size == 12) { "Bulk control must be 12 bytes" }
            val b = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
            return BulkControl(
                b.get().toInt() and 0xff, b.get().toInt() and 0xff,
                b.get().toInt() and 0xff, b.get().toInt() and 0xff,
                b.short.toInt() and 0xffff, b.short.toInt() and 0xffff,
                b.int.toLong() and 0xffffffffL,
            )
        }
    }
}
