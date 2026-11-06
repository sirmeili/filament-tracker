package io.github.sirmeili.filamenttracker.nfc

import org.junit.Assert.assertEquals
import org.junit.Test

class NfcStateTest {
    @Test
    fun saysWhatStopsAScan() {
        assertEquals("no_nfc", NfcState.of(hasNfc = false, hasMifare = false, enabled = false))
        assertEquals("no_mifare", NfcState.of(hasNfc = true, hasMifare = false, enabled = true))
        assertEquals("nfc_off", NfcState.of(hasNfc = true, hasMifare = true, enabled = false))
        assertEquals("ready", NfcState.of(hasNfc = true, hasMifare = true, enabled = true))
    }
}
