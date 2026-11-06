package io.github.sirmeili.filamenttracker

import android.app.Activity
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.MifareClassic
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import io.github.sirmeili.filamenttracker.nfc.AndroidMifare
import io.github.sirmeili.filamenttracker.nfc.Hex
import io.github.sirmeili.filamenttracker.nfc.NfcState
import io.github.sirmeili.filamenttracker.nfc.TagReader
import io.github.sirmeili.filamenttracker.storage.KeystoreKey
import io.github.sirmeili.filamenttracker.storage.PrefsValues
import io.github.sirmeili.filamenttracker.storage.SecureStore

/**
 * The phone app's native side: NFC tag reads, QR scanning and encrypted storage.
 *
 * Derived keys stay in [TagReader]; only the UID, data blocks and `readOk` reach the web view.
 * Nothing here logs tag contents, the salt or stored values.
 */
@CapacitorPlugin(name = "FilamentTracker")
class FilamentTrackerPlugin : Plugin() {
    private val store by lazy { SecureStore(KeystoreKey::get, PrefsValues(context)) }
    private var pending: PluginCall? = null
    private var salt: ByteArray? = null

    @PluginMethod
    fun appInfo(call: PluginCall) {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        call.resolve(JSObject().put("version", info.versionName ?: "unknown"))
    }

    @PluginMethod
    fun nfcStatus(call: PluginCall) {
        call.resolve(JSObject().put("status", status()))
    }

    private fun status(): String {
        val adapter = NfcAdapter.getDefaultAdapter(context)
        val mifare = context.packageManager.hasSystemFeature(NfcState.MIFARE_FEATURE)
        return NfcState.of(adapter != null, mifare, adapter?.isEnabled == true)
    }

    /** Wait for the next tag. Only one read waits at a time; a newer one replaces it. */
    @PluginMethod(returnType = PluginMethod.RETURN_PROMISE)
    fun readTag(call: PluginCall) {
        val saltBytes =
            runCatching { Hex.decode(call.getString("salt").orEmpty()) }.getOrNull()
                ?.takeIf { it.isNotEmpty() }
                ?: return call.reject("salt must be hex")
        synchronized(this) {
            pending?.reject("replaced by a newer read")
            call.setKeepAlive(true)
            pending = call
            salt = saltBytes
        }
        activity.runOnUiThread { startReader(activity) }
    }

    @PluginMethod
    fun cancelRead(call: PluginCall) {
        finish()?.reject("cancelled")
        call.resolve()
    }

    private fun startReader(activity: Activity) {
        val adapter = NfcAdapter.getDefaultAdapter(activity)
        if (adapter == null) {
            finish()?.reject("no NFC")
            return
        }
        adapter.enableReaderMode(
            activity,
            ::onTag,
            NfcAdapter.FLAG_READER_NFC_A or NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK,
            null,
        )
    }

    private fun onTag(tag: Tag) {
        val key = synchronized(this) { salt } ?: return
        val result =
            runCatching {
                val mifare = MifareClassic.get(tag) ?: error("not a MIFARE Classic tag")
                TagReader.read(AndroidMifare(mifare), key)
            }
        // A failed read (tag pulled away, wrong tag) rejects; the Scan page asks again.
        val call = finish() ?: return
        result.fold(
            onSuccess = { read ->
                call.resolve(
                    JSObject()
                        .put("tagUid", read.tagUid)
                        .put("blocks", JSArray(read.blocks))
                        .put("readOk", read.readOk),
                )
            },
            onFailure = { call.reject("tag read failed") },
        )
    }

    /** Take the waiting call, if any, and stop listening for tags. */
    private fun finish(): PluginCall? {
        val call =
            synchronized(this) {
                val current = pending
                pending = null
                salt = null
                current
            }
        activity?.let { a ->
            a.runOnUiThread { NfcAdapter.getDefaultAdapter(a)?.disableReaderMode(a) }
        }
        call?.setKeepAlive(false)
        return call
    }

    override fun handleOnResume() {
        super.handleOnResume()
        if (synchronized(this) { pending } != null) startReader(activity)
    }

    override fun handleOnPause() {
        NfcAdapter.getDefaultAdapter(activity)?.disableReaderMode(activity)
        super.handleOnPause()
    }

    @PluginMethod
    fun scanQr(call: PluginCall) {
        val options = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        GmsBarcodeScanning.getClient(activity, options)
            .startScan()
            .addOnSuccessListener { code -> call.resolve(JSObject().put("value", code.rawValue)) }
            .addOnCanceledListener { call.resolve(JSObject().put("value", null)) }
            .addOnFailureListener { call.reject("camera unavailable") }
    }

    @PluginMethod
    fun secureGet(call: PluginCall) {
        val name = call.getString("key") ?: return call.reject("key required")
        call.resolve(JSObject().put("value", store.get(name)))
    }

    @PluginMethod
    fun secureSet(call: PluginCall) {
        val name = call.getString("key") ?: return call.reject("key required")
        val value = call.getString("value") ?: return call.reject("value required")
        store.set(name, value)
        call.resolve()
    }

    @PluginMethod
    fun secureRemove(call: PluginCall) {
        val name = call.getString("key") ?: return call.reject("key required")
        store.remove(name)
        call.resolve()
    }
}
