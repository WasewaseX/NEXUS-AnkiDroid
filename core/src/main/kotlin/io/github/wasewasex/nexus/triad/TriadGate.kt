package io.github.wasewasex.nexus.triad

import kotlin.math.exp
import kotlin.math.ln

/**
 * Context observables for the TRIAD contextual recall predictor. Every value is an
 * observable app-side quantity; none are derived from FSRS internals (TRIAD only READS
 * `predicted_retrievability`; see the v1.8 spec). Session-scope values are recomputed
 * fresh per session and are NEVER persisted.
 *
 * Mirrors benchmarks/v18_nexus_triad_benchmark/sim18/triad.py `ContextState.delta`.
 */
class TriadContextObservables(
    /** Recent accuracy EMA over due-review events, in [0, 1]. */
    val recentAccuracyEma: Double,
    /** Per-kind recent-latency EMA / per-kind career-latency EMA (kind-controlled). */
    val latencySlowdown: Double,
    /** Current due review count (FSRS due + new intake). */
    val dueCount: Int,
    /** Session-scope fatigue proxy = sessionEvents/40 + elapsedMinutes/budget. */
    val sessionFatigueProxy: Double,
    /** Days since the learner was last active. */
    val absenceGapDays: Double,
)

/**
 * A-priori constants from benchmarks/v18_nexus_triad_benchmark/config18.json
 * (`triad_constants.context_features`). Declared BEFORE any run in the benchmark program;
 * never tuned on any outcome data (no circular tuning).
 */
class TriadWeights(
    val acc: Double = 2.0,
    val lat: Double = 0.8,
    val workload: Double = 0.4,
    val fatigue: Double = 0.5,
    val absence: Double = 0.3,
    /** Accuracy reference point in the delta formula. */
    val accReference: Double = 0.85,
    /** Workload reference due-count (formula uses due/30 - 0.5). */
    val workloadReference: Double = 30.0,
    /** Absence horizon in days (formula uses min(gap/7, 1)). */
    val absenceHorizonDays: Double = 7.0,
    /** Logit clip applied to the contextual delta. */
    val clipLogits: Double = 1.5,
)

/**
 * One TRIAD interval-adjustment proposal, produced ONLY when the gate would act.
 * The scheduling mapping below is UNVALIDATED and exists so that a future evidenced
 * release has a concrete, reviewable candidate — it has never been applied to any
 * learner state and never will be while [TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS]
 * is false.
 */
class TriadProposal(
    val deltaLogits: Double,
    val alpha: Double,
    /** Candidate multiplicative factor on the FSRS interval: exp(alpha*delta). UNVALIDATED. */
    val candidateIntervalFactor: Double,
)

/**
 * The feature-flagged TRIAD session-control gate.
 *
 * Pure math + pure decisions: this class NEVER mutates state. [SessionEngine] consults it
 * at exactly one hook (after a real FSRS review) and, in this release, only to append an
 * audit receipt — because [TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS] is hard-off.
 */
class TriadGate(private val w: TriadWeights = TriadWeights()) {

    /**
     * Contextual delta in logits — the v1.8 reference formula, ported verbatim:
     *   delta = w_acc*(recent_acc - 0.85) - w_lat*max(0, slowdown-1)
     *           - w_wl*max(0, due/30 - 0.5) - w_fat*fatigue - w_abs*min(gap/7, 1)
     * clipped to +/- 1.5 logits.
     */
    fun deltaContext(o: TriadContextObservables): Double {
        val accTerm = w.acc * (o.recentAccuracyEma - w.accReference)
        val latTerm = -w.lat * maxOf(0.0, o.latencySlowdown - 1.0)
        val wlRatio = minOf(o.dueCount.toDouble(), 3.0 * w.workloadReference) / w.workloadReference
        val wlTerm = -w.workload * maxOf(0.0, wlRatio - 0.5)
        val fatTerm = -w.fatigue * o.sessionFatigueProxy
        val absTerm = -w.absence * minOf(o.absenceGapDays / w.absenceHorizonDays, 1.0)
        return clip(accTerm + latTerm + wlTerm + fatTerm + absTerm, -w.clipLogits, w.clipLogits)
    }

    /**
     * The user's formula, verbatim: P_hybrid = sigmoid(logit(P_eff) + alpha*delta).
     * With alpha = 0 (the current, evidence-mandated value) this is the identity on
     * [P_eff] clipped to [1e-4, 1 - 1e-4], matching the reference implementation.
     */
    fun hybrid(pEff: Double, delta: Double, alpha: Double): Double {
        val p = pEff.coerceIn(1e-4, 1.0 - 1e-4)
        if (alpha == 0.0) return p
        val logit = ln(p / (1.0 - p))
        val z = logit + alpha * delta
        return (1.0 / (1.0 + exp(-z))).coerceIn(1e-4, 1.0 - 1e-4)
    }

    /**
     * What TRIAD WOULD propose if it were enabled: keep the learner's intended review
     * difficulty by scaling the FSRS interval by exp(alpha*delta) — negative delta
     * (context says recall will be WORSE than the model predicts) shortens the interval.
     * Returns null when the gate refuses to act.
     */
    fun proposeIntervalAdjustment(o: TriadContextObservables, alpha: Double, flagEnabled: Boolean): TriadProposal? {
        if (!flagEnabled) return null
        if (alpha == 0.0) return null
        val d = deltaContext(o)
        if (kotlin.math.abs(d) < ACTION_FLOOR_LOGITS) return null
        return TriadProposal(deltaLogits = d, alpha = alpha, candidateIntervalFactor = exp(alpha * d))
    }

    companion object {
        /** Minimum |delta| (logits) for a proposal to be considered at all. */
        const val ACTION_FLOOR_LOGITS: Double = 0.05

        /**
         * The audit decision string for the current release configuration. Refusal order is
         * deliberate: the flag dominates, then alpha, then enablement.
         */
        fun decisionFor(flagEnabled: Boolean, alpha: Double): String = when {
            !flagEnabled -> "disabled_by_flag"
            alpha == 0.0 -> "alpha_zero"
            else -> "enabled"
        }
    }

    private fun clip(x: Double, lo: Double, hi: Double): Double = minOf(hi, maxOf(lo, x))
}
