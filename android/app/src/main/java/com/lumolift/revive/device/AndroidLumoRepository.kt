package com.lumolift.revive.device

import android.content.Context
import com.lumolift.revive.protocol.Frame
import com.lumolift.revive.protocol.LumoProtocol
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.roundToInt

class AndroidLumoRepository(private val context: Context) : LumoRepository {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val eventsMutable = MutableSharedFlow<DeviceEvent>(extraBufferCapacity = 128)
    override val events: SharedFlow<DeviceEvent> = eventsMutable
    private var connection: AndroidBleConnection? = null
    private var transport: LumoBulkTransport? = null
    private var monitoring: Job? = null
    private var originalFlags = 0

    override suspend fun connect(): DeviceInfo {
        if (connection != null) return refresh()
        val newConnection = AndroidBleConnection(context)
        newConnection.connect()
        val newTransport = LumoBulkTransport(newConnection)
        try {
            newTransport.start()
            connection = newConnection
            transport = newTransport
            scope.launch { newTransport.events.collect(::emitFrame) }
            originalFlags = readProperty(6).getOrNull(1)?.toInt()?.and(0xff) ?: 0
            val info = withActive { refreshActive() }
            withActive { sendJson("GET_LIVE") }
            return info
        } catch (error: Throwable) {
            runCatching { newTransport.close() }
            newConnection.close()
            connection = null
            transport = null
            throw error
        }
    }

    override suspend fun disconnect() {
        stopMonitoring()
        val currentTransport = transport
        val currentConnection = connection
        try {
            if (currentTransport != null) setCommunication(originalFlags)
        } finally {
            runCatching { currentTransport?.close() }
            currentConnection?.close()
            transport = null
            connection = null
        }
    }

    override suspend fun refresh(): DeviceInfo = withActive { refreshActive() }

    private suspend fun refreshActive(): DeviceInfo {
        val version = readProperty(1)
        val v = ByteBuffer.wrap(version, 1, 12).order(ByteOrder.BIG_ENDIAN)
        val major = v.short.toInt() and 0xffff
        val minor = v.short.toInt() and 0xffff
        val revision = v.int.toLong() and 0xffffffffL
        val capabilities = v.int.toLong() and 0xffffffffL
        val battery = parseBattery(readProperty(23))
        val coaching = queryJson("CHTOG").optString("val") == "1"
        val delay = queryJson("AL_LEN_GET").optInt("val", 15)
        val feedback = queryJson("BSE_GET")
        return DeviceInfo(
            name = connection?.deviceName() ?: "Lumo Lift",
            firmware = "$major.$minor",
            revision = revision,
            capabilities = capabilities,
            batteryPercent = (battery.charge * 100).roundToInt().coerceIn(0, 100),
            voltage = battery.voltage,
            temperature = battery.temperature,
            coaching = coaching,
            feedbackDelay = delay,
            feedbackActive = feedback.optLong("left") > 0,
            feedbackRemaining = feedback.optLong("left"),
        )
    }

    override suspend fun startMonitoring() {
        if (monitoring?.isActive == true) return
        setCommunication(0x06)
        monitoring = scope.launch {
            while (isActive) {
                runCatching { sendJson("GET_LIVE") }
                    .onFailure { eventsMutable.tryEmit(DeviceEvent("ERROR", mapOf("message" to (it.message ?: "Monitoring failed")), "")) }
                delay(5_000)
            }
        }
    }

    override suspend fun stopMonitoring() {
        monitoring?.cancel()
        monitoring = null
        if (transport != null) setCommunication(0x02)
    }

    override suspend fun setCoaching(enabled: Boolean): Boolean = withActive {
        sendJson("CHTOG", if (enabled) "1" else "0")
        delay(350)
        val actual = queryJson("CHTOG").optString("val") == "1"
        check(actual == enabled) { "Coaching read-back failed" }
        actual
    }

    override suspend fun setFeedbackDelay(seconds: Int): Int = withActive {
        require(seconds in listOf(3, 5, 10, 15, 30, 45, 60, 120)) { "Unsupported delay" }
        sendJson("ALERTLEN", seconds.toString())
        delay(350)
        val actual = queryJson("AL_LEN_GET").optInt("val")
        check(actual == seconds) { "Feedback delay read-back failed" }
        actual
    }

    override suspend fun setFeedbackActive(enabled: Boolean): Boolean = withActive {
        sendJson(if (enabled) "BSE_START" else "BSE_END")
        delay(350)
        queryJson("BSE_GET").optLong("left") > 0
    }

    override suspend fun buzz() = withActive { sendJson("BUZZ") }
    override suspend fun readOwner(): String = withActive { queryJson("OWNER_GET").optString("str") }

    override suspend fun setOwner(owner: String): String = withActive {
        require(owner.isNotBlank()) { "Owner is required" }
        sendJson("OWN", owner, "")
        delay(350)
        val actual = queryJson("OWNER_GET").optString("str")
        check(actual == owner) { "Owner read-back failed" }
        actual
    }

    override suspend fun setProfile(heightCm: Double, weightKg: Double, gender: String, age: Int) = withActive {
        require(heightCm in 1.0..300.0 && weightKg in 1.0..500.0)
        require(gender in listOf("m", "f") && age in 0..130)
        sendJson("USER_HEIGHT_CM", "%g".format(heightCm))
        sendJson("USER_WEIGHT_KG", "%g".format(weightKg))
        sendJson("USER_GENDER", gender)
        sendJson("USER_AGE", age.toString())
    }

    private suspend fun <T> withActive(block: suspend () -> T): T {
        val wasMonitoring = monitoring?.isActive == true
        if (!wasMonitoring) setCommunication(0x06)
        return try { block() } finally { if (!wasMonitoring && transport != null) setCommunication(0x02) }
    }

    private suspend fun setCommunication(flags: Int) {
        transport().send(LumoProtocol.encode(2, byteArrayOf(6, flags.toByte())))
        delay(200)
    }

    private suspend fun readProperty(id: Int): ByteArray {
        val frame = transport().exchange(LumoProtocol.encode(1, byteArrayOf(id.toByte()))) {
            it.type == 1 && it.payload.firstOrNull()?.toInt()?.and(0xff) == id
        }
        return frame.payload
    }

    private suspend fun queryJson(command: String): JSONObject {
        val frame = transport().exchange(LumoProtocol.jsonCommand(command)) {
            it.type == LumoProtocol.JSON_TYPE && parseJson(it).optString("type") == command
        }
        return parseJson(frame)
    }

    private suspend fun sendJson(command: String, vararg args: String) {
        transport().send(LumoProtocol.jsonCommand(command, *args))
    }

    private fun transport(): LumoBulkTransport = transport ?: error("Device is not connected")

    private fun emitFrame(frame: Frame) {
        if (frame.type != LumoProtocol.JSON_TYPE) return
        runCatching { parseJson(frame) }.onSuccess { json ->
            val values = json.keys().asSequence().associateWith { json.optString(it) }
            eventsMutable.tryEmit(DeviceEvent(json.optString("type", "JSON"), values, frame.raw.toHex()))
        }
    }

    private fun parseJson(frame: Frame): JSONObject {
        val payload = frame.payload.takeWhile { it != 0.toByte() }.toByteArray()
        return JSONObject(payload.toString(Charsets.UTF_8))
    }

    private data class Battery(val voltage: Double, val charge: Double, val temperature: Double)

    private fun parseBattery(payload: ByteArray): Battery {
        require(payload.size == 19 && payload[0] == 23.toByte()) { "Invalid battery response" }
        val voltage = half(payload, 1)
        val charge = ByteBuffer.wrap(payload, 9, 8).order(ByteOrder.BIG_ENDIAN).double
        val temperature = half(payload, 17)
        return Battery(voltage, charge, temperature)
    }

    private fun half(data: ByteArray, offset: Int): Double {
        val bits = ByteBuffer.wrap(data, offset, 2).order(ByteOrder.BIG_ENDIAN).short.toInt() and 0xffff
        val sign = if (bits and 0x8000 != 0) -1.0 else 1.0
        val exponent = bits shr 10 and 0x1f
        val fraction = bits and 0x3ff
        return when (exponent) {
            0 -> sign * Math.scalb(fraction.toDouble(), -24)
            31 -> if (fraction == 0) sign * Double.POSITIVE_INFINITY else Double.NaN
            else -> sign * Math.scalb((1024 + fraction).toDouble(), exponent - 25)
        }
    }

    private fun ByteArray.toHex() = joinToString("") { "%02x".format(it) }
}
