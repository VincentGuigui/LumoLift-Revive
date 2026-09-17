package com.lumolift.tools.bleprobeconfigqueries

import android.Manifest
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Reimplements .tools/ble_probe_config_queries.py as a standalone app so the probed
 * commands (BSE_GET, AL_LEN_GET, SBB_GET, SBF_GET) can be re-tested against a physical
 * device, plus an experimental round-trip write test for the two sitting-tolerance
 * queries (SBB/SBF) whose setter command is not documented anywhere in this project.
 *
 * The round-trip test only runs for a command whose original value was successfully
 * read back: without a known original there is nothing safe to restore to, so per this
 * project's safety rules (see PROTOCOL.md) the write attempt is skipped instead of
 * guessing a "safe" default. The "communication" mode is always restored to its
 * original value before disconnecting.
 */
private val PROBED_COMMANDS = listOf("BSE_GET", "AL_LEN_GET", "SBB_GET", "SBF_GET")

/** Base names of GET commands to also round-trip test. Setter names are not documented;
 * these are the only two conventions already seen in this protocol for other commands
 * (BSE_GET/BSE_SET, and AL_LEN_GET/AL_LEN), tried in order until one is acknowledged. */
private val ROUND_TRIP_BASES = listOf("SBB", "SBF")
private const val QUERY_TIMEOUT_MS = 20_000L

class MainActivity : ComponentActivity() {
    private lateinit var logView: TextView
    private lateinit var runButton: Button

    private val permissions = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (result.values.all { it }) runProbe() else log("Permissions Bluetooth refusées.")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        logView = findViewById(R.id.logView)
        runButton = findViewById(R.id.runButton)
        runButton.setOnClickListener { requestPermissionsAndRun() }
    }

    private fun requestPermissionsAndRun() {
        val requested = if (Build.VERSION.SDK_INT >= 31) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        permissions.launch(requested)
    }

    private fun runProbe() {
        runButton.isEnabled = false
        logView.text = ""
        lifecycleScope.launch {
            val connection = BleConnection(applicationContext)
            try {
                log("Recherche d'un appareil BLE nommé 'Lumo*'...")
                val name = connection.connect()
                log("Connecté à '$name', sondage des commandes de configuration...")
                val transport = BulkTransport(connection)
                transport.start()
                var originalCommunication: Int? = null
                try {
                    originalCommunication = readCommunication(transport)
                    log("communication original=0x%02x".format(originalCommunication))
                    setCommunication(transport, 0x06)

                    val originalValues = mutableMapOf<String, String>()
                    for (command in PROBED_COMMANDS) {
                        val json = queryCommand(transport, command)
                        if (json != null) {
                            log("$command=$json")
                            if (json.has("val")) originalValues[command] = json.optString("val")
                        } else {
                            log("$command=TIMEOUT")
                        }
                    }

                    log("--- Test aller-retour (expérimental, nom du setter non documenté) ---")
                    for (base in ROUND_TRIP_BASES) {
                        roundTripTest(transport, base, originalValues["${base}_GET"])
                    }
                } finally {
                    if (originalCommunication != null) {
                        setCommunication(transport, originalCommunication)
                        log("communication_restored=0x%02x".format(originalCommunication))
                    }
                    transport.close()
                }
                connection.close()
                log("Terminé.")
            } catch (error: Exception) {
                log("Erreur: ${error.message}")
                connection.close()
            } finally {
                runButton.isEnabled = true
            }
        }
    }

    private fun isCommunicationProperty(frame: Frame): Boolean =
        frame.type == 1 && frame.payload.size == 2 && frame.payload[0] == 6.toByte()

    private suspend fun readCommunication(transport: BulkTransport): Int {
        val frame = transport.exchange(Protocol.encode(1, byteArrayOf(6)), timeoutMs = QUERY_TIMEOUT_MS, filter = ::isCommunicationProperty)
        return frame.payload[1].toInt() and 0xff
    }

    private suspend fun setCommunication(transport: BulkTransport, flags: Int) {
        transport.sendOneway(Protocol.encode(2, byteArrayOf(6, flags.toByte())))
    }

    /** Sends a JSON query and returns its decoded reply, or null on timeout. */
    private suspend fun queryCommand(transport: BulkTransport, command: String): JSONObject? = try {
        val frame = transport.exchange(
            Protocol.jsonCommand(command),
            timeoutMs = QUERY_TIMEOUT_MS,
        ) { candidate ->
            candidate.type == Protocol.JSON_TYPE &&
                runCatching { Protocol.decodeJsonPayload(candidate.payload).optString("type") }.getOrNull() == command
        }
        Protocol.decodeJsonPayload(frame.payload)
    } catch (timeout: TimeoutCancellationException) {
        null
    }

    /** Tries a setter command and returns true if the sensor acknowledged it. */
    private suspend fun trySend(transport: BulkTransport, command: String, value: String): Boolean = try {
        transport.sendOneway(Protocol.jsonCommand(command, value))
        true
    } catch (rejected: Exception) {
        false
    }

    /**
     * Reads [base]_GET, writes a nearby test value through the first setter candidate the
     * sensor acknowledges, reads back to verify, then restores the original value through the
     * same candidate. Skipped entirely if [originalValue] is unknown (GET timed out), since
     * there would be nothing safe to restore to.
     */
    private suspend fun roundTripTest(transport: BulkTransport, base: String, originalValue: String?) {
        val getCommand = "${base}_GET"
        if (originalValue == null) {
            log("$base: ignoré (valeur d'origine inconnue, $getCommand a timeout — restauration impossible)")
            return
        }
        val originalInt = originalValue.toIntOrNull()
        if (originalInt == null) {
            log("$base: ignoré (valeur d'origine non numérique: $originalValue)")
            return
        }
        val testValue = if (originalInt >= 1) originalInt - 1 else originalInt + 1
        log("$base original=$originalInt, valeur de test=$testValue")

        var workingCandidate: String? = null
        for (candidate in listOf("${base}_SET", base)) {
            if (trySend(transport, candidate, testValue.toString())) {
                workingCandidate = candidate
                log("$base: setter '$candidate' accepté (ack)")
                break
            }
            log("$base: setter '$candidate' rejeté")
        }
        if (workingCandidate == null) {
            log("$base: aucun setter candidat accepté, aucune écriture effectuée")
            return
        }

        try {
            val verified = queryCommand(transport, getCommand)
            log("$base verified=${verified?.toString() ?: "TIMEOUT"}")
        } finally {
            trySend(transport, workingCandidate, originalValue)
            log("$base restored=$originalValue")
            val restored = queryCommand(transport, getCommand)
            log("$base restore_verified=${restored?.toString() ?: "TIMEOUT"}")
        }
    }

    private fun log(line: String) {
        logView.append(line + "\n")
    }
}
