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

/**
 * Reimplements .tools/ble_probe_config_queries.py as a standalone app so the probed
 * commands (BSE_GET, AL_LEN_GET, SBB_GET, SBF_GET) can be re-tested against a physical
 * device. Read-only: the "communication" mode is restored to its original value before
 * disconnecting, and no setter command is ever sent.
 */
private val PROBED_COMMANDS = listOf("BSE_GET", "AL_LEN_GET", "SBB_GET", "SBF_GET")

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

                    for (command in PROBED_COMMANDS) {
                        try {
                            val frame = transport.exchange(
                                Protocol.jsonCommand(command),
                                timeoutMs = 6_000,
                            ) { candidate ->
                                candidate.type == Protocol.JSON_TYPE &&
                                    runCatching { Protocol.decodeJsonPayload(candidate.payload).optString("type") }
                                        .getOrNull() == command
                            }
                            val json = Protocol.decodeJsonPayload(frame.payload)
                            log("$command=$json")
                        } catch (timeout: TimeoutCancellationException) {
                            log("$command=TIMEOUT")
                        }
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
        val frame = transport.exchange(Protocol.encode(1, byteArrayOf(6)), timeoutMs = 10_000, filter = ::isCommunicationProperty)
        return frame.payload[1].toInt() and 0xff
    }

    private suspend fun setCommunication(transport: BulkTransport, flags: Int) {
        transport.sendOneway(Protocol.encode(2, byteArrayOf(6, flags.toByte())))
    }

    private fun log(line: String) {
        logView.append(line + "\n")
    }
}
