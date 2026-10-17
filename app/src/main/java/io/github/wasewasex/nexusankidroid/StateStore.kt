package io.github.wasewasex.nexusankidroid

import android.content.Context
import io.github.wasewasex.nexus.json.Json
import io.github.wasewasex.nexus.session.AppState
import io.github.wasewasex.nexus.session.SessionEngine
import org.json.JSONObject
import java.io.File

/**
 * Singleton holder of the persistent [AppState] (local-only, filesDir/state.json) and of the
 * in-memory demo deck. The app owns no scheduling logic — it loads, renders and re-persists
 * core's state document.
 *
 * Usage: call [get] once per Activity in onCreate, then read [state] / [deck] / [deckById].
 * Call [save] after EVERY record* call so a crash never loses logged evidence.
 */
object StateStore {

    const val APP_NAME = "NEXUS-AnkiDroid"
    const val APP_VERSION = "0.1.0-alpha"
    private const val STATE_FILE = "state.json"

    var state: AppState = AppState()
        private set

    var deck: List<DeckItem> = emptyList()
        private set

    var deckById: Map<String, DeckItem> = emptyMap()
        private set

    private var loaded = false

    /**
     * Lazily loads (or creates) the persistent state and the demo deck. Idempotent.
     * On first run (state has no cards) the deck is initialized through
     * [SessionEngine.initializeDeck], which creates FSRS cards and the counterbalanced
     * CONTROL/TREATMENT/held-out experiment assignment, audited as DECK_INITIALIZED.
     */
    fun get(context: Context) {
        if (loaded) return
        val file = File(context.filesDir, STATE_FILE)
        state = if (file.exists()) {
            try {
                Json.fromJson<AppState>(file.readText())
            } catch (e: Exception) {
                // Corrupt local file: start fresh rather than crash; nothing was shared.
                AppState()
            }
        } else {
            AppState()
        }
        deck = DeckItem.parseDemoDeck(context)
        deckById = deck.associateBy { it.id }
        if (state.cards.isEmpty()) {
            SessionEngine(state).initializeDeck(deck.map { it.id }, System.currentTimeMillis())
            save(context)
        }
        loaded = true
    }

    /** Writes the full state (pretty JSON) to filesDir/state.json. */
    fun save(context: Context) {
        val file = File(context.filesDir, STATE_FILE)
        file.writeText(Json.toJson(state))
    }

    /**
     * Full export payload: the per-arm aggregate (real logged data only) plus the complete
     * raw state, wrapped with app metadata. Nothing is uploaded anywhere by this call —
     * the caller shares the returned text through the system share sheet.
     */
    fun exportJson(context: Context): String {
        get(context)
        val aggregate = JSONObject(Json.toJson(state.experiment.aggregate()))
        val stateJson = JSONObject(Json.toJson(state))
        return JSONObject()
            .put("app", APP_NAME)
            .put("version", APP_VERSION)
            .put("exportedAt", System.currentTimeMillis())
            .put("aggregate", aggregate)
            .put("state", stateJson)
            .toString(2)
    }
}
