package io.github.sirmeili.filamenttracker.nfc

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class TagReaderTest {
    private val uid = Hex.decode("A1B2C3D4")
    private val salt = ByteArray(16) { (it * 7).toByte() }

    @Test
    fun readsEveryDataBlockAndNoTrailers() {
        val tag = FakeTag(uid, salt)

        val read = TagReader.read(tag, salt)

        assertTrue(read.readOk)
        assertEquals("A1B2C3D4", read.tagUid)
        assertEquals(48, read.blocks.size)
        assertEquals(Hex.encode(tag.memory[0]), read.blocks[0])
        assertEquals(Hex.encode(tag.memory[4]), read.blocks[3])
        assertEquals(Hex.encode(tag.memory[62]), read.blocks[47])
        assertTrue(tag.closed)
    }

    @Test
    fun aRefusedKeyGivesTheUidOnly() {
        val tag = FakeTag(uid, salt)
        tag.keys[5] = ByteArray(6)

        val read = TagReader.read(tag, salt)

        assertFalse(read.readOk)
        assertEquals("A1B2C3D4", read.tagUid)
        assertEquals(emptyList<String>(), read.blocks)
        assertTrue(tag.closed)
    }

    @Test
    fun theWrongSaltFailsToAuthenticate() {
        assertFalse(TagReader.read(FakeTag(uid, salt), ByteArray(16)).readOk)
    }

    @Test
    fun aTagPulledAwayThrowsAndIsClosed() {
        val lost = FakeTag(uid, salt).apply { loseAtBlock = 20 }
        assertThrows(IOException::class.java) { TagReader.read(lost, salt) }
        assertTrue(lost.closed)

        val short = FakeTag(uid, salt).apply { shortBlock = 1 }
        assertThrows(IOException::class.java) { TagReader.read(short, salt) }
    }

    @Test
    fun refusesTagsThatAreNotBambuShaped() {
        assertThrows(UnsupportedTagException::class.java) {
            TagReader.read(FakeTag(ByteArray(7), salt), salt)
        }
        val mini = FakeTag(uid, salt, sectorCount = 5)
        assertThrows(UnsupportedTagException::class.java) { TagReader.read(mini, salt) }
        assertFalse(mini.connected)
    }
}
