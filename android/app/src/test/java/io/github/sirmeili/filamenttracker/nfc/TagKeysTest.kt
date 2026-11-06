package io.github.sirmeili.filamenttracker.nfc

import org.junit.Assert.assertEquals
import org.junit.Test

class TagKeysTest {
    // Computed with the server's decoder.keys.sector_keys for UID 01020304 and a made-up
    // salt 000102...0F, so the phone and the server derive the same keys.
    private val serverKeys =
        listOf(
            "AF3520B7BDB2", "A7B4B2859655", "436D18FEC2CA", "06657ED4A196",
            "8710781551CC", "47488F9AC880", "CFE971244EBC", "696B9207F49C",
            "9B76003F6D41", "F7D3B36D9EB5", "C19E933142E2", "3E5DD8361E86",
            "8047B6F898CE", "246B14907B3A", "76F6872BF8C5", "DDD41D0B2621",
        )

    @Test
    fun derivesTheSameKeysAsTheServer() {
        val keys = TagKeys.sectorKeys(Hex.decode("01020304"), ByteArray(16) { it.toByte() })
        assertEquals(serverKeys, keys.map(Hex::encode))
    }

    @Test
    fun matchesRfc5869TestCase1() {
        val okm =
            TagKeys.hkdfSha256(
                ByteArray(22) { 0x0b },
                Hex.decode("000102030405060708090A0B0C"),
                Hex.decode("F0F1F2F3F4F5F6F7F8F9"),
                42,
            )
        assertEquals(
            "3CB25F25FAACD57A90434F64D0362F2A2D2D0A90CF1A5A4C5DB02D56ECC4C5BF34007208D5B887185865",
            Hex.encode(okm),
        )
    }

    @Test
    fun treatsAnEmptySaltAsZeros() {
        // RFC 5869 test case 3: no salt, no info.
        val okm = TagKeys.hkdfSha256(ByteArray(22) { 0x0b }, ByteArray(0), ByteArray(0), 42)
        assertEquals(
            "8DA4E775A563C18F715F802A063C5A31B8A11F5C5EE1879EC3454E5F3C738D2D9D201395FAA4B61A96C8",
            Hex.encode(okm),
        )
    }
}
