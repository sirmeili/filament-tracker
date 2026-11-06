package io.github.sirmeili.filamenttracker.nfc

import java.io.IOException

/** A MIFARE Classic 1K in memory: 64 blocks, with key A for each sector. */
class FakeTag(
    override val uid: ByteArray,
    salt: ByteArray,
    override val sectorCount: Int = 16,
) : MifareLike {
    val memory = Array(64) { block -> ByteArray(16) { (block + it).toByte() } }
    val keys = TagKeys.sectorKeys(uid, salt).toMutableList()
    var connected = false
    var closed = false
    var loseAtBlock = -1
    var shortBlock = -1
    private var authenticated = -1

    override fun connect() {
        connected = true
    }

    override fun authenticateSectorWithKeyA(sector: Int, key: ByteArray): Boolean {
        check(connected) { "not connected" }
        authenticated = if (key.contentEquals(keys[sector])) sector else -1
        return authenticated == sector
    }

    override fun readBlock(block: Int): ByteArray {
        if (block == loseAtBlock) throw IOException("tag lost")
        check(block / 4 == authenticated) { "sector not authenticated" }
        check(block % 4 != 3) { "read a trailer" }
        return if (block == shortBlock) ByteArray(4) else memory[block].copyOf()
    }

    override fun close() {
        closed = true
    }
}
