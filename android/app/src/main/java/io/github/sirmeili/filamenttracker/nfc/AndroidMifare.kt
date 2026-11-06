package io.github.sirmeili.filamenttracker.nfc

import android.nfc.tech.MifareClassic

/** Android's `MifareClassic` behind the reader's interface. */
class AndroidMifare(private val tag: MifareClassic) : MifareLike {
    override val uid: ByteArray get() = tag.tag.id
    override val sectorCount: Int get() = tag.sectorCount

    override fun connect() = tag.connect()

    override fun authenticateSectorWithKeyA(sector: Int, key: ByteArray): Boolean =
        tag.authenticateSectorWithKeyA(sector, key)

    override fun readBlock(block: Int): ByteArray = tag.readBlock(block)

    override fun close() = runCatching { tag.close() }.let { }
}
