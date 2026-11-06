package io.github.sirmeili.filamenttracker

import android.os.Bundle
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        registerPlugin(FilamentTrackerPlugin::class.java)
        super.onCreate(savedInstanceState)
    }
}
