package io.github.wasewasex.nexus.session

import io.github.wasewasex.nexus.audit.AuditLog
import io.github.wasewasex.nexus.budget.BudgetController
import io.github.wasewasex.nexus.engine.InterventionSelector
import io.github.wasewasex.nexus.engine.SelectorConfig
import io.github.wasewasex.nexus.engine.SelectedIntervention
import io.github.wasewasex.nexus.experiment.Arm
import io.github.wasewasex.nexus.experiment.AssessmentKind
import io.github.wasewasex.nexus.experiment.ExperimentManager
import io.github.wasewasex.nexus.experiment.ItemAssignment
import io.github.wasewasex.nexus.fsrs.CardState
import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.fsrs.FsrsCard
import io.github.wasewasex.nexus.fsrs.FsrsParameters
import io.github.wasewasex.nexus.fsrs.FsrsReviewLog
import io.github.wasewasex.nexus.fsrs.Rating
import io.github.wasewasex.nexus.skills.Skill
import io.github.wasewasex.nexus.skills.SkillProfile
import io.github.wasewasex.nexus.triad.TriadFeatureFlags
import io.github.wasewasex.nexus.triad.TriadGate

/**
 * Full persistent application state. One JSON document; local-only storage.
 * The app owns no scheduling logic of its own — it persists and renders this state.
 */
class AppState(
    var schemaVersion: Int = 1,
    var fsrsParams: FsrsParameters = FsrsParameters(),
    /**
     * TRIAD contextual-correction strength. Evidence-mandated to 0.0 (v1.7 real-data alpha
     * gate failed to show a held-out gain; see docs/SESSION_CONTROL_AUDIT.md). Only an
     * evidenced release may change this, together with the hard-off feature flag.
     */
    var triadAlpha: Double = 0.0,
    var cards: LinkedHashMap<String, FsrsCard> = LinkedHashMap(),
    var reviewLogs: ArrayList<FsrsReviewLog> = ArrayList(),
    var profile: SkillProfile = SkillProfile(),
    var budget: BudgetController = BudgetController(),
    var selectorConfig: SelectorConfig = SelectorConfig(),
    var experiment: ExperimentManager = ExperimentManager(),
    var audit: AuditLog = AuditLog(),
    var currentDay: Long = 0,
    var lastActiveEpochDay: Long = 0,
    var reviewsDoneToday: Int = 0,
    var exercisesDoneToday: LinkedHashMap<String, Int> = LinkedHashMap(),
    var treatmentCursor: Int = 0,
    var lastSkipAuditDay: Long = 0,
    var learnerConsent: Boolean = false,
)

class StudyState(
    var reviewsDueIds: ArrayList<String> = ArrayList(),
    var newDueIds: ArrayList<String> = ArrayList(),
    var overdueCount: Int = 0,
    var assessmentsDue: ArrayList<ItemAssignment> = ArrayList(),
    var intervention: SelectedIntervention? = null,
    var reviewsDoneToday: Int = 0,
    var budgetRemainingSeconds: Int = 0,
    var budgetPct: Int = 0,
    var notice: String = "",
)

/**
 * The session boundary between FSRS and NEXUS-SCOPE.
 *
 * Isolation guarantees (tested in IsolationTest):
 *  1. [recordExercise] and [recordAssessment] NEVER call Fsrs.review — no review log entry,
 *     no stability/difficulty/due change, no state change.
 *  2. Only [recordReview] (a real, learner-initiated FSRS review) produces FsrsReviewLog entries.
 *  3. Enrichment time is accounted separately from review time; enrichment never extends the
 *     enrichment allowance (the base is review time only).
 */
class SessionEngine(val state: AppState) {

    private val fsrs = Fsrs(state.fsrsParams)

    fun ensureDay(epochDay: Long) {
        state.budget.newDayIfNeeded(epochDay)
        if (state.currentDay != epochDay) {
            state.currentDay = epochDay
            state.reviewsDoneToday = 0
            state.exercisesDoneToday.clear()
        }
    }

    fun dueReviewIds(): List<String> =
        state.cards.values.filter { !it.isNew && it.dueEpochDay <= state.currentDay }.map { it.id }

    fun overdueCount(): Int =
        state.cards.values.count { !it.isNew && it.dueEpochDay < state.currentDay }

    fun newDueIds(): List<String> =
        state.cards.values.filter { it.isNew && it.dueEpochDay <= state.currentDay }.map { it.id }

    fun studyState(): StudyState {
        val due = ArrayList(dueReviewIds())
        val news = ArrayList(newDueIds())
        val assessments = ArrayList(state.experiment.assessmentsDue(state.currentDay))
        val intervention = if (assessments.isEmpty()) nextIntervention() else null
        return StudyState(
            reviewsDueIds = due,
            newDueIds = news,
            overdueCount = overdueCount(),
            assessmentsDue = assessments,
            intervention = intervention,
            reviewsDoneToday = state.reviewsDoneToday,
            budgetRemainingSeconds = state.budget.remainingSeconds(),
            budgetPct = state.budget.budgetPct,
            notice = "",
        )
    }

    /**
     * Select the next NEXUS intervention, or null. Selection is skipped (and audited once
     * per day) while FSRS reviews are due, while the backlog exceeds the threshold, when the
     * attendance gap is too large, or when the enrichment budget is exhausted.
     */
    fun nextIntervention(): SelectedIntervention? {
        val day = state.currentDay
        val treatmentIds = rotatingTreatmentIds()
        val reviewsDue = dueReviewIds().size + newDueIds().size
        val overdue = overdueCount()
        val remaining = state.budget.remainingSeconds()

        val selected = state.budget.takeIf { it.budgetPct > 0 }?.let {
            io.github.wasewasex.nexus.engine.InterventionSelector(state.selectorConfig).select(
                profile = state.profile,
                budgetRemainingSeconds = remaining,
                countsToday = state.exercisesDoneToday,
                day = day,
                lastActiveEpochDay = state.lastActiveEpochDay,
                treatmentItemIds = treatmentIds,
            )
        }
        if (selected == null && state.lastSkipAuditDay != day && treatmentIds.isNotEmpty()) {
            state.lastSkipAuditDay = day
            val reason = when {
                state.budget.budgetPct == 0 -> "budget_0_percent"
                reviewsDue > 0 -> "fsrs_reviews_protected"
                overdue > state.budget.backlogThreshold -> "backlog_threshold"
                state.lastActiveEpochDay > 0 &&
                    day - state.lastActiveEpochDay >= state.selectorConfig.attendanceGapPauseDays ->
                    "attendance_gap_pause"
                state.budget.remainingSeconds() < cheapestCost() -> "budget_exhausted"
                else -> "no_skill_in_deficit_with_sufficient_evidence"
            }
            state.audit.add(
                "ENRICHMENT_SKIPPED",
                "reason" to reason,
                "reviewsDue" to reviewsDue.toString(),
                "overdue" to overdue.toString(),
                "budgetRemainingSeconds" to remaining.toString(),
            )
        }
        return selected
    }

    private fun cheapestCost(): Int =
        io.github.wasewasex.nexus.engine.InterventionType.entries.minOf { it.costSeconds }

    private fun rotatingTreatmentIds(): List<String> {
        val ids = state.experiment.studyableIds(Arm.TREATMENT)
        if (ids.isEmpty()) return ids
        val start = state.treatmentCursor % ids.size
        return ids.subList(start, ids.size) + ids.subList(0, start)
    }

    /** Initialize deck once: creates FSRS cards and the counterbalanced experiment assignment. */
    fun initializeDeck(itemIds: List<String>, todayMillis: Long) {
        val day = Fsrs.epochDay(todayMillis)
        ensureDay(day)
        for (id in itemIds) {
            if (!state.cards.containsKey(id)) {
                state.cards[id] = FsrsCard(id = id, dueEpochDay = day)
            }
        }
        state.experiment.assignItems(itemIds)
        state.audit.add(
            "DECK_INITIALIZED",
            "items" to itemIds.size.toString(),
            "control" to state.experiment.studyableIds(Arm.CONTROL).size.toString(),
            "treatment" to state.experiment.studyableIds(Arm.TREATMENT).size.toString(),
            "heldOut" to state.experiment.heldOutIds().size.toString(),
        )
    }

    /** A real, learner-initiated FSRS review. The ONLY path that touches FSRS scheduling. */
    fun recordReview(itemId: String, rating: Rating, atMillis: Long, secondsSpent: Int): FsrsReviewLog? {
        val day = Fsrs.epochDay(atMillis)
        ensureDay(day)
        var card = state.cards[itemId] ?: return null
        val result = fsrs.review(card, rating, atMillis)
        state.cards[itemId] = result.card
        state.reviewLogs.add(result.reviewLog)
        state.budget.recordReviewTime(secondsSpent)
        state.experiment.markSeen(itemId, day)
        val arm = state.experiment.armOf(itemId)
        state.experiment.recordEvent(
            millis = atMillis,
            arm = arm?.name ?: "UNASSIGNED",
            kind = "REVIEW",
            itemId = itemId,
            skill = Skill.MEANING_RECALL.name,
            outcome = (rating.value - 1) / 3.0,
            durationSeconds = secondsSpent,
            details = "rating=${rating.name} stateBefore=${result.reviewLog.stateBefore} " +
                "elapsedDays=${result.reviewLog.elapsedDays} scheduledDays=${result.reviewLog.scheduledDays}",
        )
        state.reviewsDoneToday += 1
        state.lastActiveEpochDay = day
        state.audit.add(
            "FSRS_REVIEW",
            "itemId" to itemId,
            "rating" to rating.name,
            "stateBefore" to result.reviewLog.stateBefore,
            "scheduledDays" to result.reviewLog.scheduledDays.toString(),
            "reviewSeconds" to secondsSpent.toString(),
        )
        // TRIAD session-control hook (audit-first, feature-flagged). Exactly one consultation
        // point, strictly AFTER FSRS has produced its authoritative result. In this release
        // TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS is hard-off: the gate NEVER mutates
        // scheduling state, and this entry is the per-review audit receipt. If a future
        // evidenced release enables the flag, an applied adjustment would additionally emit a
        // TRIAD_INTERVAL_ADJUSTED entry — its absence is itself the compliance proof.
        // See docs/SESSION_CONTROL_AUDIT.md and TriadGateTest.
        if (TriadFeatureFlags.TRIAD_OBSERVABILITY) {
            state.audit.add(
                "TRIAD_INTERVAL_GATE",
                "itemId" to itemId,
                "intervalAdjustmentsEnabled" to TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS.toString(),
                "alpha" to state.triadAlpha.toString(),
                "decision" to TriadGate.decisionFor(
                    TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS,
                    state.triadAlpha,
                ),
                "fsrsScheduledDays" to result.reviewLog.scheduledDays.toString(),
            )
        }
        return result.reviewLog
    }

    /**
     * A NEXUS-SCOPE intervention exercise. Updates the skill profile (provisional) and the
     * enrichment budget ONLY. Never touches FSRS scheduling state.
     */
    fun recordExercise(
        type: io.github.wasewasex.nexus.engine.InterventionType,
        itemId: String,
        outcome: Double,
        atMillis: Long,
        secondsSpent: Int,
        details: String,
    ) {
        val day = Fsrs.epochDay(atMillis)
        ensureDay(day)
        val skill = type.skill
        val levelBefore = state.profile.level(skill)
        state.profile.recordEvidence(skill, outcome, weight = 0.3, epochDay = day, provisional = true)
        val levelAfter = state.profile.level(skill)
        state.profile.recordInterventionDelta(type.name, levelAfter - levelBefore)
        state.profile.markUsed(type.name, day)
        state.budget.recordEnrichment(secondsSpent)
        state.exercisesDoneToday[type.name] = (state.exercisesDoneToday[type.name] ?: 0) + 1
        state.experiment.recordEvent(
            millis = atMillis,
            arm = Arm.TREATMENT.name,
            kind = "EXERCISE",
            itemId = itemId,
            skill = skill.name,
            outcome = outcome,
            durationSeconds = secondsSpent,
            details = details,
        )
        state.audit.add(
            "NEXUS_INTERVENTION",
            "type" to type.name,
            "itemId" to itemId,
            "skill" to skill.name,
            "levelBefore" to "%.3f".format(levelBefore),
            "levelAfter" to "%.3f".format(levelAfter),
            "durationSeconds" to secondsSpent.toString(),
            "budgetRemainingSeconds" to state.budget.remainingSeconds().toString(),
            "details" to details,
        )
        state.lastActiveEpochDay = day
    }

    /**
     * A delayed assessment (day 7 / day 30). Verifies skill evidence (clears the provisional
     * flag), logs the DPI ingredient (delayed independent performance), and NEVER schedules
     * or modifies an FSRS review.
     */
    fun recordAssessment(
        itemId: String,
        skill: Skill,
        kind: AssessmentKind,
        outcome: Double,
        atMillis: Long,
        secondsSpent: Int,
        details: String,
    ) {
        val day = Fsrs.epochDay(atMillis)
        ensureDay(day)
        state.experiment.markAssessed(itemId, kind)
        state.profile.recordEvidence(skill, outcome, weight = 0.5, epochDay = day, provisional = false)
        val arm = state.experiment.armOf(itemId)
        state.experiment.recordEvent(
            millis = atMillis,
            arm = arm?.name ?: "HELD_OUT",
            kind = "ASSESSMENT_${kind.name}",
            itemId = itemId,
            skill = skill.name,
            outcome = outcome,
            durationSeconds = secondsSpent,
            details = details,
        )
        state.audit.add(
            "DELAYED_ASSESSMENT",
            "kind" to kind.name,
            "itemId" to itemId,
            "skill" to skill.name,
            "outcome" to "%.2f".format(outcome),
            "durationSeconds" to secondsSpent.toString(),
            "details" to details,
        )
    }

    fun card(itemId: String): FsrsCard? = state.cards[itemId]

    fun cardStateName(itemId: String): String = state.cards[itemId]?.state?.name ?: CardState.NEW.name
}
