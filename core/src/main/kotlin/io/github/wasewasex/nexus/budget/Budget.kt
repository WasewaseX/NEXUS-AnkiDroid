package io.github.wasewasex.nexus.budget

/**
 * Enrichment budget controller (NEXUS-SCOPE workload safeguard).
 *
 * Semantics: the enrichment allowance for a day is [budgetPct] percent of the time actually
 * spent on real FSRS reviews that day. Using review time (not total time) as the base keeps
 * the controller monotone: enrichment consumes the allowance but never grows it, so the loop
 * always terminates. Scheduled FSRS reviews are protected unconditionally: no enrichment is
 * allowed while any review is still due, or while the backlog exceeds [backlogThreshold].
 */
class BudgetController(
    /** Allowed values: 0, 10, 20, 30 (percent). */
    var budgetPct: Int = 20,
    var day: Long = 0,
    var reviewSecondsToday: Int = 0,
    var enrichmentSecondsToday: Int = 0,
    var backlogThreshold: Int = 20,
) {
    fun setBudgetPct(pct: Int) {
        require(pct == 0 || pct == 10 || pct == 20 || pct == 30) {
            "budgetPct must be one of 0, 10, 20, 30 (got $pct)"
        }
        budgetPct = pct
    }

    fun newDayIfNeeded(epochDay: Long) {
        if (epochDay != day) {
            day = epochDay
            reviewSecondsToday = 0
            enrichmentSecondsToday = 0
        }
    }

    fun recordReviewTime(seconds: Int) {
        if (seconds > 0) reviewSecondsToday += seconds
    }

    fun recordEnrichment(seconds: Int) {
        if (seconds > 0) enrichmentSecondsToday += seconds
    }

    fun allowedSeconds(): Int = reviewSecondsToday * budgetPct / 100

    fun remainingSeconds(): Int = maxOf(0, allowedSeconds() - enrichmentSecondsToday)

    /**
     * Whether a NEXUS intervention of [costSeconds] may start now.
     * FSRS reviews always come first; this is the core workload safeguard.
     */
    fun canEnrich(reviewsDue: Int, overdue: Int, costSeconds: Int): Boolean =
        budgetPct > 0 &&
            reviewsDue == 0 &&
            overdue <= backlogThreshold &&
            remainingSeconds() >= costSeconds
}
