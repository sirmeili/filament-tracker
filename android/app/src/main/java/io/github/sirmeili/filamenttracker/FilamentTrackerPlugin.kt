package io.github.sirmeili.filamenttracker

import android.app.Activity
import android.media.AudioManager
import android.media.ToneGenerator
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

    private companion object {
        const val TONE_VOLUME = 80
        const val TONE_MS = 150
    }

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
        if (NfcAdapter.getDefaultAdapter(context) == null) return call.reject("no NFC")
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
        take()?.reject("cancelled")
        call.resolve()
    }

    /**
     * Reader mode stays on while the app is in front, and tags that arrive while no read is
     * waiting are ignored. Android reports a tag once when it comes near, so a spool left on
     * the phone is not read again; it has to be lifted and tapped. Reader mode also keeps
     * Android's own tag handling away, and its "tag found" sound is off: that sound plays
     * before the read is done, so the app beeps only once the whole tag has been read.
     */
    private fun startReader(activity: Activity) {
        NfcAdapter.getDefaultAdapter(activity)?.enableReaderMode(
            activity,
            ::onTag,
            NfcAdapter.FLAG_READER_NFC_A or
                NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK or
                NfcAdapter.FLAG_READER_NO_PLATFORM_SOUNDS,
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
        val call = take() ?: return
        result.fold(
            onSuccess = { read ->
                beep(ToneGenerator.TONE_PROP_ACK)
                call.resolve(
                    JSObject()
                        .put("tagUid", read.tagUid)
                        .put("blocks", JSArray(read.blocks))
                        .put("readOk", read.readOk),
                )
            },
            onFailure = {
                beep(ToneGenerator.TONE_PROP_NACK)
                call.reject("tag read failed")
            },
        )
    }

    private var tones: ToneGenerator? = null

    private fun beep(tone: Int) {
        runCatching {
            val generator = tones ?: ToneGenerator(AudioManager.STREAM_NOTIFICATION, TONE_VOLUME).also { tones = it }
            generator.startTone(tone, TONE_MS)
        }
    }

    /** Take the waiting call, if any. Reader mode stays on. */
    private fun take(): PluginCall? {
        val call =
            synchronized(this) {
                val current = pending
                pending = null
                salt = null
                current
            }
        call?.setKeepAlive(false)
        return call
    }

    override fun handleOnResume() {
        super.handleOnResume()
        startReader(activity)
    }

    override fun handleOnPause() {
        NfcAdapter.getDefaultAdapter(activity)?.disableReaderMode(activity)
        super.handleOnPause()
    }

    override fun handleOnDestroy() {
        tones?.release()
        tones = null
        super.handleOnDestroy()
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
