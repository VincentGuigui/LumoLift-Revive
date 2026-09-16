package com.lumolift.tools.bleprobeconfigqueries

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout

/** Port of the app's LumoBulkTransport, trimmed to the request/response exchange this probe needs. */
internal class BulkTransport(private val connection: BleConnection) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val exchangeMutex = Mutex()
    private val clientDataMutex = Mutex()
    private val decoder = FrameStreamDecoder()

    private var identifier = 0
    private var serverAck: CompletableDeferred<BulkControl>? = null
    private var response: CompletableDeferred<Frame>? = null
    private var responseFilter: ((Frame) -> Boolean)? = null
    private var responseControl: BulkControl? = null
    private var responseBytes = byteArrayOf()

    suspend fun start() {
        connection.enableNotifications(SERVER_CONTROL, true)
        connection.enableNotifications(CLIENT_CONTROL, true)
        connection.enableNotifications(CLIENT_DATA, true)
        scope.launch { connection.notifications.collect(::onNotification) }
    }

    suspend fun close() {
        runCatching { connection.enableNotifications(CLIENT_DATA, false) }
        runCatching { connection.enableNotifications(CLIENT_CONTROL, false) }
        runCatching { connection.enableNotifications(SERVER_CONTROL, false) }
        scope.cancel()
        decoder.clear()
    }

    private fun onNotification(notification: Notification) {
        when (notification.uuid) {
            SERVER_CONTROL -> runCatching { BulkControl.decode(notification.value) }
                .onSuccess { control ->
                    if (control.command == 2 && control.identifier == identifier) serverAck?.complete(control)
                }.onFailure { serverAck?.completeExceptionally(it) }
            CLIENT_CONTROL -> runCatching { BulkControl.decode(notification.value) }
                .onSuccess { control ->
                    if (control.command == 1) {
                        responseControl = control
                        responseBytes = byteArrayOf()
                    }
                }.onFailure { response?.completeExceptionally(it) }
            CLIENT_DATA -> scope.launch { consumeClientData(notification.value) }
        }
    }

    private suspend fun consumeClientData(value: ByteArray) = clientDataMutex.withLock {
        val control = responseControl ?: return
        responseBytes += value
        if (responseBytes.size < control.length) return
        val content = responseBytes.copyOfRange(0, control.length)
        val valid = Protocol.crc16(content) == control.crc
        connection.write(
            CLIENT_CONTROL,
            control.copy(result = if (valid) 1 else 2).encode(),
            response = false,
        )
        responseControl = null
        responseBytes = byteArrayOf()
        if (!valid) {
            response?.completeExceptionally(IllegalArgumentException("Bulk response CRC mismatch"))
            return@withLock
        }
        decoder.feed(content).forEach { frame ->
            val expected = responseFilter?.invoke(frame) == true && response?.isCompleted == false
            if (expected) response?.complete(frame)
        }
    }

    /** Send a request and wait for both the sensor's ack and a matching response frame. */
    suspend fun exchange(packet: ByteArray, timeoutMs: Long, filter: (Frame) -> Boolean): Frame =
        exchangeMutex.withLock {
            identifier = (identifier + 1) and 0xff
            serverAck = CompletableDeferred()
            response = CompletableDeferred()
            responseFilter = filter
            try {
                writePacket(packet)
                val ack = withTimeout(10_000) { serverAck!!.await() }
                check(ack.result == 1) { "Sensor rejected request" }
                withTimeout(timeoutMs) { response!!.await() }
            } finally {
                serverAck = null
                response = null
                responseFilter = null
            }
        }

    /** Send a request and wait only for the sensor's ack, without expecting a data response. */
    suspend fun sendOneway(packet: ByteArray) = exchangeMutex.withLock {
        identifier = (identifier + 1) and 0xff
        serverAck = CompletableDeferred()
        try {
            writePacket(packet)
            val ack = withTimeout(10_000) { serverAck!!.await() }
            check(ack.result == 1) { "Sensor rejected command" }
        } finally {
            serverAck = null
        }
    }

    private suspend fun writePacket(packet: ByteArray) {
        val control = BulkControl(
            command = 2,
            identifier = identifier,
            length = packet.size,
            crc = Protocol.crc16(packet),
        )
        connection.write(SERVER_CONTROL, control.encode(), response = false)
        Protocol.chunks(packet).forEach { connection.write(SERVER_DATA, it, response = true) }
    }
}
