package com.lumolift.revive

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.lumolift.revive.device.AndroidLumoRepository
import com.lumolift.revive.device.DeviceInfo
import com.lumolift.revive.device.LiveMetrics
import com.lumolift.revive.device.LumoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate

data class MainUiState(
    val connected: Boolean = false,
    val busy: Boolean = false,
    val monitoring: Boolean = false,
    val info: DeviceInfo = DeviceInfo(),
    val metrics: LiveMetrics = LiveMetrics(),
    val stepsGoal: Long = 10_000,
    val owner: String = "",
    val events: List<String> = emptyList(),
    val error: String? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository: LumoRepository = AndroidLumoRepository(application)
    private val preferences = application.getSharedPreferences("local_state", 0)
    private val _state = MutableStateFlow(
        MainUiState(
            stepsGoal = preferences.getLong("steps_goal", 10_000),
            metrics = LiveMetrics(
                steps = preferences.getLong("steps_displayed", 0),
                stepsH = preferences.getLong("stepsh_displayed", 0),
            ),
        )
    )
    val state: StateFlow<MainUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.events.collect { event ->
                _state.update { current ->
                    val metrics = when (event.type) {
                        "STEPS" -> current.metrics.copy(steps = continuous("steps", event.values["val"]?.toLongOrNull() ?: 0))
                        "STEPSH" -> current.metrics.copy(stepsH = continuous("stepsh", event.values["val"]?.toLongOrNull() ?: 0))
                        "CALS" -> current.metrics.copy(calories = event.values["val"]?.toLongOrNull() ?: current.metrics.calories)
                        "TGOOD" -> current.metrics.copy(goodPostureSeconds = event.values["val"]?.toLongOrNull() ?: current.metrics.goodPostureSeconds)
                        "REC" -> current.metrics.copy(
                            activity = event.values["act1"] ?: current.metrics.activity,
                            angle = event.values["angle"]?.toDoubleOrNull() ?: current.metrics.angle,
                        )
                        else -> current.metrics
                    }
                    current.copy(
                        metrics = metrics,
                        events = (listOf("${event.type}: ${event.values}") + current.events).take(30),
                    )
                }
            }
        }
    }

    fun connect() = runAction {
        val info = repository.connect()
        _state.update { it.copy(connected = true, info = info) }
    }

    fun disconnect() = runAction {
        repository.disconnect()
        _state.update { it.copy(connected = false, monitoring = false) }
    }

    fun refresh() = runAction {
        _state.update { it.copy(info = repository.refresh()) }
    }

    fun setMonitoring(enabled: Boolean) = runAction {
        if (enabled) repository.startMonitoring() else repository.stopMonitoring()
        _state.update { it.copy(monitoring = enabled) }
    }

    fun setCoaching(enabled: Boolean) = runAction {
        val actual = repository.setCoaching(enabled)
        _state.update { it.copy(info = it.info.copy(coaching = actual)) }
    }

    fun setDelay(seconds: Int) = runAction {
        val actual = repository.setFeedbackDelay(seconds)
        _state.update { it.copy(info = it.info.copy(feedbackDelay = actual)) }
    }

    fun setFeedback(enabled: Boolean) = runAction {
        val actual = repository.setFeedbackActive(enabled)
        _state.update { it.copy(info = it.info.copy(feedbackActive = actual)) }
    }

    fun buzz() = runAction { repository.buzz() }

    fun saveGoal(goal: Long) {
        if (goal < 100) {
            _state.update { it.copy(error = "Steps goal must be at least 100") }
            return
        }
        preferences.edit().putLong("steps_goal", goal).apply()
        _state.update { it.copy(stepsGoal = goal) }
    }

    fun readOwner() = runAction {
        val owner = repository.readOwner()
        _state.update { it.copy(owner = owner) }
    }

    fun setOwner(owner: String) = runAction {
        val actual = repository.setOwner(owner)
        _state.update { it.copy(owner = actual) }
    }

    fun setProfile(height: Double, weight: Double, gender: String, age: Int) = runAction {
        repository.setProfile(height, weight, gender, age)
    }

    fun consumeError() = _state.update { it.copy(error = null) }

    private fun runAction(block: suspend () -> Unit) {
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null) }
            try { block() } catch (error: Throwable) {
                _state.update { it.copy(error = error.message ?: "Unexpected error") }
            } finally { _state.update { it.copy(busy = false) } }
        }
    }

    private fun continuous(prefix: String, raw: Long): Long {
        val today = LocalDate.now().toString()
        val storedDay = preferences.getString("counter_day", today)
        if (storedDay != today) {
            preferences.edit().clear().putString("counter_day", today)
                .putLong("steps_goal", _state.value.stepsGoal).apply()
        }
        val oldRaw = preferences.getLong("${prefix}_raw", 0)
        val oldDisplayed = preferences.getLong("${prefix}_displayed", 0)
        val displayed = oldDisplayed + if (raw >= oldRaw) raw - oldRaw else raw
        preferences.edit().putString("counter_day", today)
            .putLong("${prefix}_raw", raw).putLong("${prefix}_displayed", displayed).apply()
        return displayed
    }

    override fun onCleared() {
        viewModelScope.launch { runCatching { repository.disconnect() } }
        super.onCleared()
    }
}
