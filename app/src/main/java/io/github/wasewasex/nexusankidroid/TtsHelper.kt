package io.github.wasewasex.nexusankidroid

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * Thin wrapper around the on-device Android [TextToSpeech] engine.
 *
 * Privacy: the app holds no permissions and never selects a network TTS engine; whatever
 * offline engine the device provides is used as-is. Speech synthesis happens locally.
 *
 * Rates:
 *  - [NATURAL_RATE] (1.0x) is used by LISTENING_INPUT exercises (varied, but natural input).
 *  - [ASSESSMENT_RATE] (1.15x) is used by delayed listening ASSESSMENTS. The deck sentences
 *    are deliberately simple A2/B1 English, so assessment difficulty comes from speech speed
 *    rather than vocabulary; the slightly-faster-than-natural playback is the documented
 *    "unfamiliar audio" proxy that keeps assessments honest without recording real audio.
 */
class TtsHelper(context: Context) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = TextToSpeech(context.applicationContext, this)
    private var utteranceCounter: Int = 0

    var isReady: Boolean = false
        private set

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            isReady = false
            return
        }
        val result = tts?.setLanguage(Locale.US)
        isReady = result != null &&
            result != TextToSpeech.LANG_MISSING_DATA &&
            result != TextToSpeech.LANG_NOT_SUPPORTED
    }

    /** Speaks [text] at [rate] (defaults to natural 1.0x). No-op until init succeeded. */
    fun speak(text: String, rate: Float = NATURAL_RATE) {
        val engine = tts ?: return
        if (!isReady) return
        engine.setSpeechRate(rate)
        utteranceCounter += 1
        engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "nexus-$utteranceCounter")
    }

    fun stop() {
        tts?.stop()
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
    }

    companion object {
        const val NATURAL_RATE: Float = 1.0f
        const val ASSESSMENT_RATE: Float = 1.15f
    }
}
