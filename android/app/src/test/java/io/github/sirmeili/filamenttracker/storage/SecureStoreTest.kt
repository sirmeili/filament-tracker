package io.github.sirmeili.filamenttracker.storage

import io.github.sirmeili.filamenttracker.nfc.Hex
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

class SecureStoreTest {
    private class MemoryValues : KeyValues {
        val map = mutableMapOf<String, String>()

        override fun get(name: String) = map[name]

        override fun put(name: String, value: String) {
            map[name] = value
        }

        override fun remove(name: String) {
            map.remove(name)
        }
    }

    private fun newKey(): SecretKey = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()

    private val key = newKey()
    private val values = MemoryValues()
    private val store = SecureStore({ key }, values)

    @Test
    fun keepsValuesEncrypted() {
        store.set("pairing", "ftd_secret-token")

        assertEquals("ftd_secret-token", store.get("pairing"))
        val stored = values.map.getValue("pairing")
        assertFalse(stored.contains("secret"))
        assertFalse(stored.contains(Hex.encode("ftd_secret-token".toByteArray())))
    }

    @Test
    fun usesAFreshIvEachTime() {
        store.set("a", "same")
        val first = values.map.getValue("a")
        store.set("a", "same")
        assertNotEquals(first, values.map.getValue("a"))
    }

    @Test
    fun missingAndRemovedValuesReadAsNull() {
        assertNull(store.get("nothing"))
        store.set("queue", "[]")
        store.remove("queue")
        assertNull(store.get("queue"))
    }

    @Test
    fun aValueMovedToAnotherNameDoesNotDecrypt() {
        store.set("kdf_salt", "AABB")
        values.map["pairing"] = values.map.getValue("kdf_salt")

        assertNull(store.get("pairing"))
        assertFalse(values.map.containsKey("pairing"))
        assertEquals("AABB", store.get("kdf_salt"))
    }

    @Test
    fun damagedValuesOrALostKeyAreDropped() {
        store.set("pairing", "x")
        assertNull(SecureStore({ newKey() }, values).get("pairing"))
        assertTrue(values.map.isEmpty())

        values.map["a"] = "not hex"
        values.map["b"] = "00FF"
        assertNull(store.get("a"))
        assertNull(store.get("b"))
        assertTrue(values.map.isEmpty())
    }
}
