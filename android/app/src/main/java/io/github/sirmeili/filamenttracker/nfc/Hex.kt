package io.github.sirmeili.filamenttracker.nfc

/** Upper-case hex, as the server and scanner write it. */
object Hex {
    private const val DIGITS = "0123456789ABCDEF"

    fun encode(bytes: ByteArray): String =
        buildString(bytes.size * 2) {
            for (b in bytes) {
                append(DIGITS[(b.toInt() shr 4) and 0xF])
                append(DIGITS[b.toInt() and 0xF])
            }
        }

    fun decode(text: String): ByteArray {
        require(text.length % 2 == 0) { "hex needs an even number of digits" }
        return ByteArray(text.length / 2) {
            val hi = Character.digit(text[it * 2], 16)
            val lo = Character.digit(text[it * 2 + 1], 16)
            require(hi >= 0 && lo >= 0) { "not hex" }
            ((hi shl 4) or lo).toByte()
        }
    }
}
