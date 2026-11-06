package io.github.sirmeili.filamenttracker.nfc

/** Whether this phone can read Bambu tags right now, in the web app's words. */
object NfcState {
    /** Android's feature name for NXP MIFARE Classic support. */
    const val MIFARE_FEATURE = "com.nxp.mifare"

    fun of(hasNfc: Boolean, hasMifare: Boolean, enabled: Boolean): String =
        when {
            !hasNfc -> "no_nfc"
            !hasMifare -> "no_mifare"
            !enabled -> "nfc_off"
            else -> "ready"
        }
}
