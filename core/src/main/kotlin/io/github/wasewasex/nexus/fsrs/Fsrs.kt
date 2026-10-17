package io.github.wasewasex.nexus.fsrs

import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/** FSRS-5 rating, mirroring the open FSRS specification (AnkiDroid's default scheduler family). */
enum class Rating(val value: Int) {
    AGAIN(1), HARD(2), GOOD(3), EASY(4);

    companion object {
        fun from(value: Int): Rating = entries.first { it.value == value }
    }
}

enum class CardState { NEW, LEARNING, REVIEW, RELEARNING }

/**
 * Scheduling state of one item. Pure data. Only [Fsrs.review] mutates scheduling state;
 * NEXUS-SCOPE exercises and delayed assessments never touch this class.
 */
class FsrsCard(
    var id: String = "",
    var state: CardState = CardState.NEW,
    var stability: Double = 0.0,
    var difficulty: Double = 0.0,
    /** UTC epoch day when the card is next due. */
    var dueEpochDay: Long = 0,
    /** UTC epoch day of the last real FSRS review (0 = never reviewed). */
    var lastReviewEpochDay: Long = 0,
    var reps: Int = 0,
    var lapses: Int = 0,
) {
    val isNew: Boolean get() = state == CardState.NEW

    fun copy(): FsrsCard =
        FsrsCard(id, state, stability, difficulty, dueEpochDay, lastReviewEpochDay, reps, lapses)
}

/**
 * Immutable record of one real FSRS review. NEXUS exercises never produce these entries —
 * this is the isolation guarantee tested by IsolationTest.
 */
class FsrsReviewLog(
    var cardId: String = "",
    var rating: Rating = Rating.GOOD,
    var reviewedAtMillis: Long = 0,
    var dueBeforeEpochDay: Long = 0,
    var stateBefore: String = CardState.NEW.name,
    var elapsedDays: Long = 0,
    var scheduledDays: Long = 0,
)

class FsrsParameters(
    /** FSRS-5 published default weights (open-spaced-repetition, MIT-licensed reference ports). */
    var weights: DoubleArray = doubleArrayOf(
        0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046,
        1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315,
        2.9898, 0.51655, 0.6621,
    ),
    var desiredRetention: Double = 0.9,
    /** Single intra-day learning/relearning step in minutes (v0.1 simplification). */
    var learningStepMinutes: Int = 10,
) {
    companion object {
        const val DECAY: Double = -0.5
        const val FACTOR: Double = 19.0 / 81.0 // chosen so R(S) = 0.9 exactly
    }
}

class FsrsResult(val card: FsrsCard, val reviewLog: FsrsReviewLog)

/**
 * FSRS-5 scheduler, a faithful Kotlin port of the open algorithm
 * (open-spaced-repetition py-fsrs / ts-fsrs, both MIT). Deliberate v0.1 simplifications,
 * documented in docs/LIMITATIONS.md: UTC epoch-day interval resolution; a single 10-minute
 * intra-day learning step; no fuzz; no per-deck weight optimization UI.
 */
class Fsrs(var params: FsrsParameters = FsrsParameters()) {

    fun intervalFor(stability: Double): Long {
        val interval = (stability / FsrsParameters.FACTOR) *
            (params.desiredRetention.pow(1.0 / FsrsParameters.DECAY) - 1.0)
        return max(1L, Math.round(interval))
    }

    /** Estimated recall probability for a card at [atMillis]. NEW cards return 0.0. */
    fun retrievability(card: FsrsCard, atMillis: Long): Double {
        if (card.isNew || card.stability <= 0.0 || card.lastReviewEpochDay == 0L) return 0.0
        val elapsed = max(0L, epochDay(atMillis) - card.lastReviewEpochDay).toDouble()
        return (1.0 + FsrsParameters.FACTOR * elapsed / card.stability).pow(FsrsParameters.DECAY)
    }

    /** The ONLY entry point that mutates FSRS scheduling state. */
    fun review(cardIn: FsrsCard, rating: Rating, atMillis: Long): FsrsResult {
        val w = params.weights
        val card = cardIn.copy()
        val day = epochDay(atMillis)
        val lastReviewBefore = card.lastReviewEpochDay
        val log = FsrsReviewLog(
            cardId = card.id,
            rating = rating,
            reviewedAtMillis = atMillis,
            dueBeforeEpochDay = card.dueEpochDay,
            stateBefore = card.state.name,
        )
        val g = rating.value
        when (card.state) {
            CardState.NEW -> {
                card.stability = w[g - 1]
                card.difficulty = clampD(w[4] - (g - 3) * w[5])
                card.reps = 1
                card.state = CardState.LEARNING
                card.lastReviewEpochDay = day
                card.dueEpochDay = epochDay(atMillis + stepMillis())
            }
            CardState.LEARNING, CardState.RELEARNING -> {
                card.reps += 1
                val sameDay = day == card.lastReviewEpochDay
                if (sameDay || rating == Rating.AGAIN) {
                    // FSRS-5 short-term (intra-day) stability update
                    card.stability = card.stability * exp(w[17] * (g - 3 + w[18]))
                    card.lastReviewEpochDay = day
                    if (rating == Rating.AGAIN) {
                        card.state = CardState.LEARNING
                        card.dueEpochDay = epochDay(atMillis + stepMillis())
                    } else {
                        card.state = CardState.REVIEW
                        card.difficulty = clampD(nextDifficulty(card.difficulty, g, w))
                        card.dueEpochDay = day + intervalFor(card.stability)
                    }
                } else {
                    applyLongGapUpdate(card, rating, day, atMillis, w)
                }
            }
            CardState.REVIEW -> {
                card.reps += 1
                applyLongGapUpdate(card, rating, day, atMillis, w)
            }
        }
        log.elapsedDays = if (log.stateBefore == CardState.NEW.name) 0
        else max(0L, day - lastReviewBefore)
        log.scheduledDays = max(0L, card.dueEpochDay - day)
        return FsrsResult(card, log)
    }

    private fun applyLongGapUpdate(card: FsrsCard, rating: Rating, day: Long, atMillis: Long, w: DoubleArray) {
        val elapsed = max(0L, day - card.lastReviewEpochDay)
        val r = if (card.lastReviewEpochDay == 0L) params.desiredRetention
        else (1.0 + FsrsParameters.FACTOR * elapsed / card.stability).pow(FsrsParameters.DECAY)
        card.difficulty = clampD(nextDifficulty(card.difficulty, rating.value, w))
        card.stability = if (rating == Rating.AGAIN) {
            card.lapses += 1
            w[11] * card.difficulty.pow(-w[12]) *
                (Math.pow(card.stability + 1.0, w[13]) - 1.0) *
                exp(w[14] * (1.0 - r))
        } else {
            val hardPenalty = if (rating == Rating.HARD) w[15] else 1.0
            val easyBonus = if (rating == Rating.EASY) w[16] else 1.0
            card.stability * (1.0 + exp(w[8]) * (11.0 - card.difficulty) *
                card.stability.pow(-w[9]) * (exp(w[10] * (1.0 - r)) - 1.0) *
                hardPenalty * easyBonus)
        }
        card.lastReviewEpochDay = day
        if (rating == Rating.AGAIN) {
            card.state = CardState.RELEARNING
            card.dueEpochDay = epochDay(atMillis + stepMillis())
        } else {
            card.state = CardState.REVIEW
            card.dueEpochDay = day + intervalFor(card.stability)
        }
    }

    private fun nextDifficulty(d: Double, g: Int, w: DoubleArray): Double {
        val deltaD = -w[6] * (g - 3)
        val damped = d + deltaD * (10.0 - d) / 9.0
        val anchor = w[4] - w[5] // D0(EASY), the mean-reversion anchor used by FSRS-5
        return w[7] * anchor + (1.0 - w[7]) * damped
    }

    private fun stepMillis(): Long = params.learningStepMinutes * 60_000L

    private fun clampD(x: Double): Double = min(10.0, max(1.0, x))

    companion object {
        fun epochDay(millis: Long): Long = Math.floorDiv(millis, 86_400_000L)
    }
}
