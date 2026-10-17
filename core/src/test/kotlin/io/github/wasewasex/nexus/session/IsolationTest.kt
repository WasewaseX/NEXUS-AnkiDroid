package io.github.wasewasex.nexus.session

import io.github.wasewasex.nexus.engine.InterventionType
import io.github.wasewasex.nexus.experiment.Arm
import io.github.wasewasex.nexus.experiment.AssessmentKind
import io.github.wasewasex.nexus.fsrs.CardState
import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.fsrs.Rating
import io.github.wasewasex.nexus.skills.Skill
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * THE critical safety suite: NEXUS-SCOPE exercises and delayed assessments must never
 * contaminate FSRS scheduling, and FSRS reviews must always be protected from enrichment.
 */
class IsolationTest {

    /** 2026-01-01T10:00 UTC. */
    private val t0 = 1767261600000L

    private fun freshEngine(nItems: Int = 40): Pair<SessionEngine, List<String>> {
        val state = AppState()
        val eng = SessionEngine(state)
        eng.ensureDay(Fsrs.epochDay(t0))
        val ids = (1..nItems).map { "i%03d".format(it) }
        eng.initializeDeck(ids, t0)
        return eng to ids
    }

    private fun runFullReviewQueue(eng: SessionEngine, ids: List<String>) {
        // first encounter (learning step)
        for (id in ids) eng.recordReview(id, Rating.GOOD, t0, 10)
        // same-day graduation
        for (id in ids) eng.recordReview(id, Rating.GOOD, t0 + 15 * 60_000, 8)
    }

    @Test
    fun `exercises never produce review log entries or schedule changes`() {
        val (eng, ids) = freshEngine()
        runFullReviewQueue(eng, ids)
        val state = eng.state
        val logsAfterReviews = state.reviewLogs.size
        assertEquals(ids.size * 2, logsAfterReviews)

        val treatment = state.experiment.studyableIds(Arm.TREATMENT)
        assertTrue(treatment.isNotEmpty())
        val cardBefore = eng.card(treatment[0])!!.copy()

        eng.recordExercise(
            InterventionType.LISTENING_INPUT, treatment[0], outcome = 0.8,
            atMillis = t0 + 30 * 60_000, secondsSpent = 120, details = "unit test",
        )
        eng.recordExercise(
            InterventionType.PREDICTION_ERROR_REPAIR, treatment[1], outcome = 0.6,
            atMillis = t0 + 32 * 60_000, secondsSpent = 120, details = "unit test",
        )
        // delayed assessment also must not touch FSRS
        eng.recordAssessment(
            treatment[0], Skill.MEANING_RECALL, AssessmentKind.DAY7, outcome = 0.7,
            atMillis = t0 + 33 * 60_000, secondsSpent = 60, details = "unit test",
        )

        assertEquals("review log count must not change", logsAfterReviews, state.reviewLogs.size)
        val cardAfter = eng.card(treatment[0])!!
        assertEquals(cardBefore.state, cardAfter.state)
        assertEquals(cardBefore.stability, cardAfter.stability, 0.0)
        assertEquals(cardBefore.difficulty, cardAfter.difficulty, 0.0)
        assertEquals(cardBefore.dueEpochDay, cardAfter.dueEpochDay)
        assertEquals(0, cardAfter.lapses)
    }

    @Test
    fun `scheduled reviews are protected from enrichment and skip is audited`() {
        val (eng, ids) = freshEngine()
        val state = eng.state
        // set a deficit profile with plenty of evidence so selection would otherwise fire
        for (i in 0 until 6) {
            state.profile.recordEvidence(Skill.LISTENING, 0.30, 1.0, state.currentDay, false)
        }
        // reviews still due (nothing studied yet)
        val sel = eng.nextIntervention()
        assertNull("no intervention while FSRS reviews are due", sel)
        val skip = state.audit.entries.lastOrNull { it.kind == "ENRICHMENT_SKIPPED" }
        assertNotNull(skip)
        assertEquals("fsrs_reviews_protected", skip!!.payload["reason"])
        assertEquals(ids.size, eng.dueReviewIds().size + eng.newDueIds().size)
    }

    @Test
    fun `enrichment only after the full review queue is done and within budget`() {
        val (eng, ids) = freshEngine()
        val state = eng.state
        for (i in 0 until 6) {
            state.profile.recordEvidence(Skill.LISTENING, 0.30, 1.0, state.currentDay, false)
        }
        runFullReviewQueue(eng, ids)
        // 40 items * (10s + 8s) = 720s review time; 20% -> 144s allowance
        assertEquals(720, state.budget.reviewSecondsToday)
        assertEquals(144, state.budget.allowedSeconds())
        val sel = eng.nextIntervention()
        assertNotNull("intervention should be selectable after reviews are done", sel)
        assertEquals(Arm.TREATMENT.name, "TREATMENT")
        val item = sel!!.itemId
        assertTrue(state.experiment.studyableIds(Arm.TREATMENT).contains(item))
        assertTrue(item in state.experiment.studyableIds(Arm.TREATMENT))
        // the OTHER arm must never receive interventions
        val controlIds = state.experiment.studyableIds(Arm.CONTROL)
        assertTrue(!controlIds.contains(item))
    }

    @Test
    fun `zero budget disables interventions even after reviews`() {
        val (eng, ids) = freshEngine()
        val state = eng.state
        state.budget.changeBudget(0)
        for (i in 0 until 6) {
            state.profile.recordEvidence(Skill.LISTENING, 0.30, 1.0, state.currentDay, false)
        }
        runFullReviewQueue(eng, ids)
        assertNull(eng.nextIntervention())
        val skip = state.audit.entries.lastOrNull { it.kind == "ENRICHMENT_SKIPPED" }
        assertEquals("budget_0_percent", skip!!.payload["reason"])
    }

    @Test
    fun `exercises consume budget but reviews never do`() {
        val (eng, ids) = freshEngine()
        val state = eng.state
        runFullReviewQueue(eng, ids)
        assertEquals(720, state.budget.reviewSecondsToday)
        assertEquals(0, state.budget.enrichmentSecondsToday)
        val treatment = state.experiment.studyableIds(Arm.TREATMENT)
        eng.recordExercise(
            InterventionType.TRANSFER_TASK, treatment[0], 0.5,
            t0 + 40 * 60_000, 120, "unit test",
        )
        assertEquals(120, state.budget.enrichmentSecondsToday)
        assertEquals(720, state.budget.reviewSecondsToday)
    }

    @Test
    fun `every intervention is auditable with before and after levels`() {
        val (eng, ids) = freshEngine()
        val state = eng.state
        for (i in 0 until 6) {
            state.profile.recordEvidence(Skill.LISTENING, 0.30, 1.0, state.currentDay, false)
        }
        runFullReviewQueue(eng, ids)
        val sel = eng.nextIntervention()!!
        eng.recordExercise(
            sel.type, sel.itemId, outcome = 0.8,
            atMillis = t0 + 50 * 60_000, secondsSpent = sel.costSeconds, details = sel.rationale,
        )
        val entry = state.audit.entries.last { it.kind == "NEXUS_INTERVENTION" }
        assertEquals(sel.type.name, entry.payload["type"])
        assertNotNull(entry.payload["levelBefore"])
        assertNotNull(entry.payload["levelAfter"])
        assertEquals(sel.rationale, entry.payload["details"])
        assertTrue(entry.payload["levelAfter"]!!.toDouble() > entry.payload["levelBefore"]!!.toDouble())
    }

    @Test
    fun `long attendance gap pauses interventions with audit trail`() {
        val (eng, ids) = freshEngine()
        val state = eng.state
        for (i in 0 until 6) {
            state.profile.recordEvidence(Skill.LISTENING, 0.30, 1.0, state.currentDay, false)
        }
        runFullReviewQueue(eng, ids)
        // 12 days of absence; the queue is cleared for the new day first, then the stale
        // activity record is restored to simulate the gap (reviews would otherwise mark
        // the learner active today and defeat the very rule under test).
        val gapDay = state.currentDay + 12
        eng.ensureDay(gapDay)
        for (id in eng.dueReviewIds()) eng.recordReview(id, Rating.GOOD, gapDay * 86_400_000L + 10 * 3_600_000, 10)
        state.lastActiveEpochDay = gapDay - 12
        val sel = eng.nextIntervention()
        assertNull("attendance gap must pause enrichment", sel)
        val skip = state.audit.entries.lastOrNull { it.kind == "ENRICHMENT_SKIPPED" }
        assertEquals("attendance_gap_pause", skip!!.payload["reason"])
    }
}
