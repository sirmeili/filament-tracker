package io.github.sirmeili.filamenttracker.nfc

import java.io.IOException

/** The parts of Android's `MifareClassic` the reader uses, so tests can use a fake tag. */
interface MifareLike {
    val uid: ByteArray
    val sectorCount: Int

    @Throws(IOException::class)
    fun connect()

    @Throws(IOException::class)
    fun authenticateSectorWithKeyA(sector: Int, key: ByteArray): Boolean

    @Throws(IOException::class)
    fun readBlock(block: Int): ByteArray

    fun close()
}

/** One read, as a scanner sends it: the UID and the 48 data blocks, without trailers. */
data class TagRead(val tagUid: String, val blocks: List<String>, val readOk: Boolean)

/** A tag this app cannot read: not a 4-byte-UID MIFARE Classic 1K, as Bambu tags are. */
class UnsupportedTagException(message: String) : Exception(message)

object TagReader {
    const val UID_SIZE = 4
    const val BLOCKS_PER_SECTOR = 4
    const val BLOCK_SIZE = 16

    /**
     * Read every data block with keys derived from the salt. A sector that refuses its key
     * gives `readOk = false` and no blocks: the server then stores the UID only. Losing the
     * tag mid-read throws `IOException`.
     */
    @Throws(IOException::class, UnsupportedTagException::class)
    fun read(tag: MifareLike, salt: ByteArray): TagRead {
        val uid = tag.uid
        if (uid.size != UID_SIZE) throw UnsupportedTagException("not a 4-byte UID")
        if (tag.sectorCount < TagKeys.SECTORS) throw UnsupportedTagException("not a 1K tag")
        val tagUid = Hex.encode(uid)
        val keys = TagKeys.sectorKeys(uid, salt)
        tag.connect()
        try {
            val blocks = ArrayList<String>(TagKeys.SECTORS * (BLOCKS_PER_SECTOR - 1))
            for (sector in 0 until TagKeys.SECTORS) {
                if (!tag.authenticateSectorWithKeyA(sector, keys[sector])) {
                    return TagRead(tagUid, emptyList(), readOk = false)
                }
                for (offset in 0 until BLOCKS_PER_SECTOR - 1) {
                    val data = tag.readBlock(sector * BLOCKS_PER_SECTOR + offset)
                    if (data.size != BLOCK_SIZE) throw IOException("short block")
                    blocks.add(Hex.encode(data))
                }
            }
            return TagRead(tagUid, blocks, readOk = true)
        } finally {
            tag.close()
        }
    }
}
