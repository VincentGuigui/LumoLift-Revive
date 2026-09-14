package com.lumolift.revive.device

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelUuid
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import java.util.UUID

internal val PRIMARY_SERVICE: UUID = UUID.fromString("af120101-31d4-48e8-a1f8-5c09c020ae42")
internal val SERVER_CONTROL: UUID = UUID.fromString("af120201-31d4-48e8-a1f8-5c09c020ae42")
internal val SERVER_DATA: UUID = UUID.fromString("af120202-31d4-48e8-a1f8-5c09c020ae42")
internal val CLIENT_CONTROL: UUID = UUID.fromString("af120203-31d4-48e8-a1f8-5c09c020ae42")
internal val CLIENT_DATA: UUID = UUID.fromString("af120204-31d4-48e8-a1f8-5c09c020ae42")
internal val MANUFACTURER: UUID = UUID.fromString("00002a29-0000-1000-8000-00805f9b34fb")
private val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

internal data class Notification(val uuid: UUID, val value: ByteArray)

@SuppressLint("MissingPermission")
internal class AndroidBleConnection(private val context: Context) {
    private val manager = context.getSystemService(BluetoothManager::class.java)
    private val adapter: BluetoothAdapter get() = manager.adapter ?: error("Bluetooth is unavailable")
    private val notificationsMutable = MutableSharedFlow<Notification>(
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val notifications: SharedFlow<Notification> = notificationsMutable

    private var connectionDeferred: CompletableDeferred<Unit>? = null
    private var discoveryDeferred: CompletableDeferred<Unit>? = null
    private var operationDeferred: CompletableDeferred<ByteArray>? = null
    private val operationMutex = Mutex()
    private var gatt: BluetoothGatt? = null

    private val callback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS && newState == BluetoothProfile.STATE_CONNECTED) {
                this@AndroidBleConnection.gatt = gatt
                connectionDeferred?.complete(Unit)
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                val error = IllegalStateException("Bluetooth disconnected (status $status)")
                connectionDeferred?.completeExceptionally(error)
                discoveryDeferred?.completeExceptionally(error)
                operationDeferred?.completeExceptionally(error)
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) discoveryDeferred?.complete(Unit)
            else discoveryDeferred?.completeExceptionally(IllegalStateException("Service discovery failed: $status"))
        }

        @Deprecated("Deprecated in API 33")
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            notificationsMutable.tryEmit(Notification(characteristic.uuid, characteristic.value.clone()))
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
        ) {
            notificationsMutable.tryEmit(Notification(characteristic.uuid, value.clone()))
        }

        override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            completeOperation(status, byteArrayOf())
        }

        override fun onDescriptorWrite(gatt: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            completeOperation(status, byteArrayOf())
        }

        @Deprecated("Deprecated in API 33")
        override fun onCharacteristicRead(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            completeOperation(status, characteristic.value.clone())
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
            status: Int,
        ) {
            completeOperation(status, value.clone())
        }
    }

    private fun completeOperation(status: Int, value: ByteArray) {
        val operation = operationDeferred ?: return
        if (status == BluetoothGatt.GATT_SUCCESS) operation.complete(value)
        else operation.completeExceptionally(IllegalStateException("GATT operation failed: $status"))
    }

    fun hasPermissions(): Boolean = if (Build.VERSION.SDK_INT >= 31) {
        ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
    } else {
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
    }

    suspend fun connect() {
        check(hasPermissions()) { "Bluetooth permissions are required" }
        check(adapter.isEnabled) { "Bluetooth is turned off" }
        val device = scan()
        connectionDeferred = CompletableDeferred()
        gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
        withTimeout(15_000) { connectionDeferred!!.await() }
        discoveryDeferred = CompletableDeferred()
        check(gatt!!.discoverServices()) { "Unable to start service discovery" }
        withTimeout(10_000) { discoveryDeferred!!.await() }
        requiredCharacteristic(SERVER_CONTROL)
        requiredCharacteristic(SERVER_DATA)
        requiredCharacteristic(CLIENT_CONTROL)
        requiredCharacteristic(CLIENT_DATA)
    }

    private suspend fun scan(): BluetoothDevice = withTimeout(20_000) {
        val result = CompletableDeferred<BluetoothDevice>()
        val scanner = adapter.bluetoothLeScanner ?: error("BLE scanner is unavailable")
        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, scanResult: ScanResult) {
                val name = scanResult.scanRecord?.deviceName ?: scanResult.device.name.orEmpty()
                val services = scanResult.scanRecord?.serviceUuids.orEmpty()
                if (name.startsWith("Lumo", ignoreCase = true) || services.contains(ParcelUuid(PRIMARY_SERVICE))) {
                    if (result.complete(scanResult.device)) scanner.stopScan(this)
                }
            }

            override fun onScanFailed(errorCode: Int) {
                result.completeExceptionally(IllegalStateException("BLE scan failed: $errorCode"))
            }
        }
        val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        scanner.startScan(listOf(ScanFilter.Builder().build()), settings, callback)
        try { result.await() } finally { scanner.stopScan(callback) }
    }

    private fun requiredCharacteristic(uuid: UUID): BluetoothGattCharacteristic =
        gatt?.services?.asSequence()?.flatMap { it.characteristics.asSequence() }
            ?.firstOrNull { it.uuid == uuid } ?: error("Required characteristic $uuid is missing")

    suspend fun enableNotifications(uuid: UUID, enabled: Boolean) = operationMutex.withLock {
        val localGatt = gatt ?: error("Not connected")
        val characteristic = requiredCharacteristic(uuid)
        check(localGatt.setCharacteristicNotification(characteristic, enabled)) { "Unable to configure notification $uuid" }
        val descriptor = characteristic.getDescriptor(CCCD) ?: error("CCCD missing for $uuid")
        operationDeferred = CompletableDeferred()
        val value = if (enabled) BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE else BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE
        val started = if (Build.VERSION.SDK_INT >= 33) {
            localGatt.writeDescriptor(descriptor, value) == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION")
            run { descriptor.value = value; localGatt.writeDescriptor(descriptor) }
        }
        check(started) { "Unable to write notification descriptor $uuid" }
        withTimeout(8_000) { operationDeferred!!.await() }
        operationDeferred = null
    }

    suspend fun write(uuid: UUID, value: ByteArray, response: Boolean) = operationMutex.withLock {
        val localGatt = gatt ?: error("Not connected")
        val characteristic = requiredCharacteristic(uuid)
        val writeType = if (response) BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT else BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
        operationDeferred = CompletableDeferred()
        val started = if (Build.VERSION.SDK_INT >= 33) {
            localGatt.writeCharacteristic(characteristic, value, writeType) == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION")
            run { characteristic.writeType = writeType; characteristic.value = value; localGatt.writeCharacteristic(characteristic) }
        }
        check(started) { "Unable to write characteristic $uuid" }
        withTimeout(8_000) { operationDeferred!!.await() }
        operationDeferred = null
    }

    suspend fun read(uuid: UUID): ByteArray = operationMutex.withLock {
        val localGatt = gatt ?: error("Not connected")
        operationDeferred = CompletableDeferred()
        check(localGatt.readCharacteristic(requiredCharacteristic(uuid))) { "Unable to read $uuid" }
        val result = withTimeout(8_000) { operationDeferred!!.await() }
        operationDeferred = null
        result
    }

    fun deviceName(): String = if (Build.VERSION.SDK_INT >= 31 && !hasPermissions()) "Lumo Lift" else gatt?.device?.name ?: "Lumo Lift"

    fun close() {
        gatt?.disconnect()
        gatt?.close()
        gatt = null
    }
}
