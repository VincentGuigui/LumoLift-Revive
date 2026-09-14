package com.lumolift.revive.device

data class DeviceInfo(
    val name: String = "Lumo Lift",
    val firmware: String = "—",
    val revision: Long = 0,
    val capabilities: Long = 0,
    val batteryPercent: Int = 0,
    val voltage: Double = 0.0,
    val temperature: Double = 0.0,
    val coaching: Boolean = false,
    val feedbackDelay: Int = 15,
    val feedbackActive: Boolean = false,
    val feedbackRemaining: Long = 0,
)

data class LiveMetrics(
    val steps: Long = 0,
    val stepsH: Long = 0,
    val calories: Long = 0,
    val goodPostureSeconds: Long = 0,
    val activity: String = "—",
    val angle: Double? = null,
)

data class DeviceEvent(val type: String, val values: Map<String, String>, val raw: String)

interface LumoRepository {
    val events: kotlinx.coroutines.flow.SharedFlow<DeviceEvent>
    suspend fun connect(): DeviceInfo
    suspend fun disconnect()
    suspend fun refresh(): DeviceInfo
    suspend fun startMonitoring()
    suspend fun stopMonitoring()
    suspend fun setCoaching(enabled: Boolean): Boolean
    suspend fun setFeedbackDelay(seconds: Int): Int
    suspend fun setFeedbackActive(enabled: Boolean): Boolean
    suspend fun buzz()
    suspend fun readOwner(): String
    suspend fun setOwner(owner: String): String
    suspend fun setProfile(heightCm: Double, weightKg: Double, gender: String, age: Int)
}
