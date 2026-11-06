package io.github.sirmeili.filamenttracker.nfc

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class HexTest {
    @Test
    fun encodesUpperCase() {
        assertEquals("00FF7F80", Hex.encode(byteArrayOf(0, -1, 0x7f, -128)))
    }

    @Test
    fun decodesEitherCase() {
        assertArrayEquals(byteArrayOf(0x0a, -1), Hex.decode("0aFF"))
        assertArrayEquals(ByteArray(0), Hex.decode(""))
    }

    @Test
    fun refusesWhatIsNotHex() {
        assertThrows(IllegalArgumentException::class.java) { Hex.decode("ABC") }
        assertThrows(IllegalArgumentException::class.java) { Hex.decode("G0") }
        assertThrows(IllegalArgumentException::class.java) { Hex.decode("0G") }
    }
}
