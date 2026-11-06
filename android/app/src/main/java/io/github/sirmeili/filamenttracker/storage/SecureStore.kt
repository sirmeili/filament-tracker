package io.github.sirmeili.filamenttracker.storage

import io.github.sirmeili.filamenttracker.nfc.Hex
import java.security.GeneralSecurityException
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Where encrypted values are kept (SharedPreferences in the app, a map in tests). */
interface KeyValues {
    fun get(name: String): String?

    fun put(name: String, value: String)

    fun remove(name: String)
}

/**
 * Values encrypted with AES-GCM under a key that never leaves the Android Keystore.
 *
 * Each value is stored as hex of IV + ciphertext, with its name as associated data, so a
 * value cannot be moved to another name. A value that no longer decrypts (for example after
 * the Keystore key was lost) is removed and reads as missing, so the phone simply re-pairs.
 */
class SecureStore(private val key: () -> SecretKey, private val values: KeyValues) {
    fun get(name: String): String? {
        val stored = values.get(name) ?: return null
        return try {
            val bytes = Hex.decode(stored)
            require(bytes.size > IV_SIZE) { "too short" }
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(TAG_BITS, bytes, 0, IV_SIZE))
            cipher.updateAAD(name.toByteArray(Charsets.UTF_8))
            String(cipher.doFinal(bytes, IV_SIZE, bytes.size - IV_SIZE), Charsets.UTF_8)
        } catch (e: GeneralSecurityException) {
            values.remove(name)
            null
        } catch (e: IllegalArgumentException) {
            values.remove(name)
            null
        }
    }

    fun set(name: String, value: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        // The Keystore picks the IV: it refuses caller-chosen IVs for encryption.
        cipher.init(Cipher.ENCRYPT_MODE, key())
        cipher.updateAAD(name.toByteArray(Charsets.UTF_8))
        val sealed = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        values.put(name, Hex.encode(cipher.iv + sealed))
    }

    fun remove(name: String) = values.remove(name)

    companion object {
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_SIZE = 12
        const val TAG_BITS = 128
    }
}
