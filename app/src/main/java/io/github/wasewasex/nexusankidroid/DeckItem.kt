package io.github.wasewasex.nexusankidroid

import android.content.Context
import org.json.JSONArray

/**
 * One demo-deck item. Field names mirror assets/demo_deck.json exactly.
 * All content is original, simple CEFR A2/B1 English (no copyrighted material).
 */
data class DeckItem(
    val id: String,
    val front: String,
    val back: String,
    val listeningText: String,
    val listeningOptions: List<String>,
    val listeningAnswer: Int,
    val productionPrompt: String,
    val productionModel: String,
    val grammarSentence: String,
    val grammarOptions: List<String>,
    val grammarAnswer: Int,
    val grammarExplanation: String,
    val transferContext: String,
    val transferOptions: List<String>,
    val transferAnswer: Int,
) {
    fun listeningCorrect(): String = listeningOptions[listeningAnswer]
    fun grammarCorrect(): String = grammarOptions[grammarAnswer]
    fun transferCorrect(): String = transferOptions[transferAnswer]

    companion object {
        /**
         * Parses assets/demo_deck.json with org.json (kept deliberately simple and
         * independent of Gson, which is reserved for core state round-trips).
         */
        fun parseDemoDeck(context: Context): List<DeckItem> {
            val text = context.assets.open("demo_deck.json").bufferedReader().use { it.readText() }
            val arr = JSONArray(text)
            val items = ArrayList<DeckItem>(arr.length())
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                items.add(
                    DeckItem(
                        id = o.getString("id"),
                        front = o.getString("front"),
                        back = o.getString("back"),
                        listeningText = o.getString("listeningText"),
                        listeningOptions = o.getJSONArray("listeningOptions").let { a ->
                            List(a.length()) { a.getString(it) }
                        },
                        listeningAnswer = o.getInt("listeningAnswer"),
                        productionPrompt = o.getString("productionPrompt"),
                        productionModel = o.getString("productionModel"),
                        grammarSentence = o.getString("grammarSentence"),
                        grammarOptions = o.getJSONArray("grammarOptions").let { a ->
                            List(a.length()) { a.getString(it) }
                        },
                        grammarAnswer = o.getInt("grammarAnswer"),
                        grammarExplanation = o.getString("grammarExplanation"),
                        transferContext = o.getString("transferContext"),
                        transferOptions = o.getJSONArray("transferOptions").let { a ->
                            List(a.length()) { a.getString(it) }
                        },
                        transferAnswer = o.getInt("transferAnswer"),
                    )
                )
            }
            return items
        }
    }
}
