package com.lumolift.revive.device

import com.lumolift.revive.protocol.BulkControl
import com.lumolift.revive.protocol.Frame
import com.lumolift.revive.protocol.FrameStreamDecoder
import com.lumolift.revive.protocol.LumoProtocol
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout

internal class LumoBulkTransport(private val connection: AndroidBleConnection) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val exchangeMutex = Mutex()
    private val clientDataMutex = Mutex()
    private val decoder = FrameStreamDecoder()
    private val eventsMutable = MutableSharedFlow<Frame>(extraBufferCapacity = 64)
    val events: SharedFlow<Frame> = eventsMutable

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
        val valid = LumoProtocol.crc16(content) == control.crc
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
            if (expected) response?.complete(frame) else eventsMutable.tryEmit(frame)
        }
    }

    suspend fun exchange(packet: ByteArray, filter: (Frame) -> Boolean): Frame = exchangeMutex.withLock {
        identifier = (identifier + 1) and 0xff
        serverAck = CompletableDeferred()
        response = CompletableDeferred()
        responseFilter = filter
        try {
            writePacket(packet)
            val ack = withTimeout(10_000) { serverAck!!.await() }
            check(ack.result == 1) { "Sensor rejected request" }
            withTimeout(10_000) { response!!.await() }
        } finally {
            serverAck = null
            response = null
            responseFilter = null
        }
    }

    suspend fun send(packet: ByteArray) = exchangeMutex.withLock {
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
            crc = LumoProtocol.crc16(packet),
        )
        connection.write(SERVER_CONTROL, control.encode(), response = false)
        LumoProtocol.chunks(packet).forEach { connection.write(SERVER_DATA, it, response = true) }
    }
}
