package com.lumolift.revive

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LumoApp(viewModel: MainViewModel, requestConnect: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    var tab by remember { mutableIntStateOf(0) }
    LaunchedEffect(state.error) {
        state.error?.let { snackbar.showSnackbar(it); viewModel.consumeError() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Column { Text("Lumo Lift"); Text(if (state.connected) "Connected" else "Offline", style = MaterialTheme.typography.labelSmall) } },
                actions = {
                    if (state.busy) CircularProgressIndicator(Modifier.padding(12.dp).width(24.dp))
                    if (state.connected) TextButton(onClick = viewModel::disconnect, enabled = !state.busy) { Text("Disconnect") }
                    else Button(onClick = requestConnect, enabled = !state.busy, modifier = Modifier.padding(end = 12.dp)) { Text("Scan & connect") }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(selected = tab == 0, onClick = { tab = 0 }, icon = {}, label = { Text("Dashboard") })
                NavigationBarItem(selected = tab == 1, onClick = { tab = 1 }, icon = {}, label = { Text("User profile") })
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (tab == 0) Dashboard(state, viewModel, padding)
        else ProfileScreen(state, viewModel, padding)
    }
}

@Composable
private fun Dashboard(state: MainUiState, vm: MainViewModel, padding: PaddingValues) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(padding),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { DeviceCard(state) }
        item { ConfigurationCard(state, vm) }
        item {
            BoxWithConstraints(Modifier.fillMaxWidth()) {
                if (maxWidth >= 720.dp) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MonitoringCard(state, vm, Modifier.weight(1f))
                        StepsCard(state, vm, Modifier.weight(1f))
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        MonitoringCard(state, vm, Modifier.fillMaxWidth())
                        StepsCard(state, vm, Modifier.fillMaxWidth())
                    }
                }
            }
        }
        item { Text("Recent events", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
        items(state.events) { Text(it, style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable
private fun DeviceCard(state: MainUiState) = SurfaceCard("Device") {
    val info = state.info
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Metric("Firmware", if (info.revision == 0L) "—" else "${info.firmware} r${info.revision}")
        Metric("Battery", if (state.connected) formatBatteryLabel(info.batteryPercent, info.voltage) else "—")
        Metric("Temperature", if (state.connected) "%.1f °C".format(info.temperature) else "—")
    }
}

@Composable
private fun ConfigurationCard(state: MainUiState, vm: MainViewModel) = SurfaceCard("Device configuration") {
    var delayOpen by remember { mutableStateOf(false) }
    var confirmFeedback by remember { mutableStateOf<Boolean?>(null) }
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Column { Text("Coaching vibration", fontWeight = FontWeight.Medium); Text("Persistent sensor setting", style = MaterialTheme.typography.bodySmall) }
        Switch(checked = state.info.coaching, onCheckedChange = vm::setCoaching, enabled = state.connected && !state.busy)
    }
    HorizontalDivider(Modifier.padding(vertical = 10.dp))
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Column { Text("Feedback delay", fontWeight = FontWeight.Medium); Text("${state.info.feedbackDelay} seconds", style = MaterialTheme.typography.bodySmall) }
        Column {
            OutlinedButton(onClick = { delayOpen = true }, enabled = state.connected && !state.busy) { Text("Change") }
            DropdownMenu(expanded = delayOpen, onDismissRequest = { delayOpen = false }) {
                listOf(3, 5, 10, 15, 30, 45, 60, 120).forEach { value ->
                    DropdownMenuItem(text = { Text("$value seconds") }, onClick = { delayOpen = false; vm.setDelay(value) })
                }
            }
        }
    }
    HorizontalDivider(Modifier.padding(vertical = 10.dp))
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Column { Text("Feedback session", fontWeight = FontWeight.Medium); Text(if (state.info.feedbackActive) "Active · ${state.info.feedbackRemaining}s left" else "Stopped", style = MaterialTheme.typography.bodySmall) }
        Button(onClick = { confirmFeedback = !state.info.feedbackActive }, enabled = state.connected && !state.busy) {
            Text(if (state.info.feedbackActive) "Stop" else "Start")
        }
    }
    Spacer(Modifier.height(10.dp))
    OutlinedButton(onClick = vm::buzz, enabled = state.connected && !state.busy) { Text("Test vibration") }
    confirmFeedback?.let { enabled ->
        AlertDialog(
            onDismissRequest = { confirmFeedback = null },
            title = { Text(if (enabled) "Start feedback?" else "Stop feedback?") },
            text = { Text("This changes the feedback session on the sensor.") },
            confirmButton = { TextButton(onClick = { confirmFeedback = null; vm.setFeedback(enabled) }) { Text("Confirm") } },
            dismissButton = { TextButton(onClick = { confirmFeedback = null }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun MonitoringCard(state: MainUiState, vm: MainViewModel, modifier: Modifier) = SurfaceCard("Monitoring", modifier) {
    val m = state.metrics
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Metric("Activity", m.activity)
        Metric("Angle", m.angle?.let { "%.1f°".format(it) } ?: "—")
        Metric("Posture", posture(m.activity, m.angle))
    }
    Spacer(Modifier.height(14.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { vm.setMonitoring(!state.monitoring) }, enabled = state.connected && !state.busy) {
            Text(if (state.monitoring) "Stop monitoring" else "Start monitoring")
        }
        OutlinedButton(onClick = vm::refresh, enabled = state.connected && !state.busy) { Text("Refresh") }
    }
    Text(
        if (state.monitoring) "Live request every 5 seconds" else "Off · active telemetry disabled",
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier.padding(top = 8.dp),
    )
}

@Composable
private fun StepsCard(state: MainUiState, vm: MainViewModel, modifier: Modifier) = SurfaceCard("Steps", modifier) {
    var goalText by remember(state.stepsGoal) { mutableStateOf(state.stepsGoal.toString()) }
    StepProgress("Daily STEPS", state.metrics.steps, state.stepsGoal)
    Spacer(Modifier.height(12.dp))
    StepProgress("STEPSH baseline", state.metrics.stepsH, state.stepsGoal)
    Spacer(Modifier.height(14.dp))
    OutlinedTextField(
        value = goalText,
        onValueChange = { goalText = it.filter(Char::isDigit) },
        label = { Text("Local steps goal") },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    Button(onClick = { goalText.toLongOrNull()?.let(vm::saveGoal) }, modifier = Modifier.padding(top = 8.dp)) { Text("Apply goal") }
    Text("Goal is local; the device has no recovered goal command.", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun ProfileScreen(state: MainUiState, vm: MainViewModel, padding: PaddingValues) {
    var owner by remember(state.owner) { mutableStateOf(state.owner) }
    var height by remember { mutableStateOf("175") }
    var weight by remember { mutableStateOf("70") }
    var gender by remember { mutableStateOf("m") }
    var age by remember { mutableStateOf("30") }
    var confirmOwner by remember { mutableStateOf(false) }
    var confirmProfile by remember { mutableStateOf(false) }
    Column(
        Modifier.fillMaxSize().padding(padding).padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SurfaceCard("Owner") {
            OutlinedTextField(owner, { owner = it }, label = { Text("Owner") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = vm::readOwner, enabled = state.connected && !state.busy) { Text("Read owner") }
                Button(onClick = { confirmOwner = true }, enabled = state.connected && !state.busy) { Text("Apply owner") }
            }
        }
        SurfaceCard("User profile") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(height, { height = it }, label = { Text("Height cm") }, modifier = Modifier.weight(1f), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                OutlinedTextField(weight, { weight = it }, label = { Text("Weight kg") }, modifier = Modifier.weight(1f), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
            }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = gender == "m", onClick = { gender = "m" }, label = { Text("Male") })
                FilterChip(selected = gender == "f", onClick = { gender = "f" }, label = { Text("Female") })
                OutlinedTextField(age, { age = it.filter(Char::isDigit) }, label = { Text("Age") }, modifier = Modifier.width(120.dp), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            }
            Button(onClick = { confirmProfile = true }, enabled = state.connected && !state.busy, modifier = Modifier.padding(top = 10.dp)) { Text("Apply user profile") }
            Text("These fields have no confirmed device read-back.", style = MaterialTheme.typography.bodySmall)
        }
    }
    if (confirmOwner) AlertDialog(
        onDismissRequest = { confirmOwner = false }, title = { Text("Apply owner?") },
        text = { Text("The app sends OWN(owner, empty password) and verifies with OWNER_GET.") },
        confirmButton = { TextButton(onClick = { confirmOwner = false; vm.setOwner(owner) }) { Text("Apply") } },
        dismissButton = { TextButton(onClick = { confirmOwner = false }) { Text("Cancel") } },
    )
    if (confirmProfile) AlertDialog(
        onDismissRequest = { confirmProfile = false }, title = { Text("Apply user profile?") },
        text = { Text("Height, weight, gender, and age will be written directly to the sensor.") },
        confirmButton = { TextButton(onClick = {
            confirmProfile = false
            val h = height.toDoubleOrNull(); val w = weight.toDoubleOrNull(); val a = age.toIntOrNull()
            if (h != null && w != null && a != null) vm.setProfile(h, w, gender, a)
        }) { Text("Apply") } },
        dismissButton = { TextButton(onClick = { confirmProfile = false }) { Text("Cancel") } },
    )
}

@Composable
private fun SurfaceCard(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}

@Composable private fun Metric(label: String, value: String) = Column {
    Text(label, style = MaterialTheme.typography.labelMedium)
    Text(value, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
}

@Composable private fun StepProgress(label: String, value: Long, goal: Long) {
    val progress = (value.toFloat() / goal.coerceAtLeast(1)).coerceIn(0f, 1f)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(label); Text("$value / $goal") }
    LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth().padding(top = 5.dp))
}

private fun posture(activity: String, angle: Double?): String = when {
    activity in listOf("—", "inactive", "not_worn") || angle == null -> "Not worn"
    angle < 85 -> "Forward"
    angle > 95 -> "Back"
    else -> "Good"
}

internal fun formatBatteryLabel(percent: Int, voltage: Double): String =
    "$percent% · ${String.format(Locale.US, "%.2f", voltage)} V"
