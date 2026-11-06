package io.github.sirmeili.filamenttracker.storage

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

/** The app's AES key in the Android Keystore, created on first use. */
object KeystoreKey {
    private const val STORE = "AndroidKeyStore"
    private const val ALIAS = "filament-tracker-storage"

    fun get(): SecretKey {
        val store = KeyStore.getInstance(STORE).apply { load(null) }
        (store.getKey(ALIAS, null) as SecretKey?)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, STORE)
        generator.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }
}

/** Encrypted values in a private SharedPreferences file. */
class PrefsValues(context: Context) : KeyValues {
    private val prefs = context.getSharedPreferences("secure-store", Context.MODE_PRIVATE)

    override fun get(name: String): String? = prefs.getString(name, null)

    override fun put(name: String, value: String) {
        prefs.edit().putString(name, value).apply()
    }

    override fun remove(name: String) {
        prefs.edit().remove(name).apply()
    }
}
