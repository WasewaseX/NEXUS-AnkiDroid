package io.github.wasewasex.nexus.json

import io.github.wasewasex.nexus.engine.InterventionType
import io.github.wasewasex.nexus.experiment.Arm
import io.github.wasewasex.nexus.experiment.AssessmentKind
import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.fsrs.Rating
import io.github.wasewasex.nexus.session.AppState
import io.github.wasewasex.nexus.session.SessionEngine
import io.github.wasewasex.nexus.skills.Skill
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Full-state persistence integrity: serialize -> deserialize -> serialize must be identical. */
class JsonRoundTripTest {

    private val t0 = 1767261600000L

    @Test
    fun `app state round trips exactly`() {
        val state = AppState()
        val eng = SessionEngine(state)
        eng.ensureDay(Fsrs.epochDay(t0))
        val ids = (1..30).map { "j%03d".format(it) }
        eng.initializeDeck(ids, t0)
        for (id in ids) eng.recordReview(id, Rating.GOOD, t0, 9)
        for (id in ids) eng.recordReview(id, Rating.GOOD, t0 + 15 * 60_000, 7)
        state.profile.recordEvidence(Skill.LISTENING, 0.4, 0.5, state.currentDay, true)
        state.profile.recordInterventionDelta(InterventionType.LISTENING_INPUT.name, 0.03)
        val treatment = state.experiment.studyableIds(Arm.TREATMENT)
        eng.recordExercise(InterventionType.LISTENING_INPUT, treatment[0], 0.7, t0 + 30 * 60_000, 120, "rt")
        eng.recordAssessment(treatment[0], Skill.PRODUCTION, AssessmentKind.DAY7, 0.6, t0 + 31 * 60_000, 90, "rt")
        state.budget.changeBudget(30)

        val s1 = Json.toJson(state)
        val restored = Json.fromJson<AppState>(s1)
        val s2 = Json.toJson(restored)
        assertEquals(s1, s2)

        // spot checks on restored content
        assertEquals(state.cards.size, restored.cards.size)
        assertEquals(state.reviewLogs.size, restored.reviewLogs.size)
        assertEquals(state.experiment.studyableIds(Arm.TREATMENT), restored.experiment.studyableIds(Arm.TREATMENT))
        assertEquals(state.profile.state(Skill.LISTENING).level, restored.profile.state(Skill.LISTENING).level, 1e-12)
        assertEquals(30, restored.budget.budgetPct)
        assertTrue(restored.audit.entries.size >= 3)
        assertEquals(state.experiment.aggregate(), restored.experiment.aggregate())
    }

    @Test
    fun `empty state round trips`() {
        val s1 = Json.toJson(AppState())
        val restored = Json.fromJson<AppState>(s1)
        assertEquals(s1, Json.toJson(restored))
    }
}
