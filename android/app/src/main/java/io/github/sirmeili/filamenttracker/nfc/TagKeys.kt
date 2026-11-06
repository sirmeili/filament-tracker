package io.github.sirmeili.filamenttracker.nfc

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Bambu tag sector keys, as on the server (`decoder/keys.py`).
 *
 * Each of the 16 key A values comes from the tag's 4-byte UID with HKDF-SHA256, using the
 * key-derivation constant from the server as the salt and "RFID-A\0" as the info. The keys
 * stay inside the plugin: they are never returned to the web view or logged.
 */
object TagKeys {
    const val SECTORS = 16
    const val KEY_SIZE = 6
    private val INFO_KEY_A = "RFID-A\u0000".toByteArray(Charsets.US_ASCII)

    fun sectorKeys(uid: ByteArray, salt: ByteArray): List<ByteArray> {
        val material = hkdfSha256(uid, salt, INFO_KEY_A, SECTORS * KEY_SIZE)
        return List(SECTORS) { material.copyOfRange(it * KEY_SIZE, (it + 1) * KEY_SIZE) }
    }

    /** HKDF (RFC 5869) with SHA-256. */
    fun hkdfSha256(ikm: ByteArray, salt: ByteArray, info: ByteArray, length: Int): ByteArray {
        val prk = hmac(salt, ikm)
        val out = java.io.ByteArrayOutputStream()
        var block = ByteArray(0)
        var counter = 1
        while (out.size() < length) {
            block = hmac(prk, block + info + byteArrayOf(counter.toByte()))
            out.write(block)
            counter += 1
        }
        return out.toByteArray().copyOf(length)
    }

    private fun hmac(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        // An empty salt means a zero key in RFC 5869; the JCE refuses empty keys.
        mac.init(SecretKeySpec(if (key.isEmpty()) ByteArray(32) else key, "HmacSHA256"))
        return mac.doFinal(data)
    }
}
