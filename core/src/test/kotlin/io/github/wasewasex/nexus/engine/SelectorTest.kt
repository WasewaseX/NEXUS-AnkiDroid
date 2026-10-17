package io.github.wasewasex.nexus.engine

import io.github.wasewasex.nexus.skills.Skill
import io.github.wasewasex.nexus.skills.SkillProfile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Intervention selection: evidence gating, deficit detection, priority scoring, cooldowns,
 * daily caps, repeated-ineffectiveness guard, attendance-gap tolerance and budget respect.
 */
class SelectorTest {

    private val day = 1000L
    private val items = listOf("t1", "t2", "t3")

    private fun profileWith(skill: Skill, level: Double, evidence: Int): SkillProfile {
        val p = SkillProfile()
        repeat(evidence) { p.recordEvidence(skill, level, 1.0, day, provisional = false) }
        // recordEvidence nudges the level toward `level` with weight 1.0, so final == level
        return p
    }

    @Test
    fun `selects the deficient skill with sufficient evidence`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        val sel = InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items)
        assertNotNull(sel)
        assertEquals(InterventionType.LISTENING_INPUT, sel!!.type)
        assertEquals(Skill.LISTENING, sel.type.skill)
        assertTrue(sel.rationale.contains("LISTENING"))
        assertTrue(sel.rationale.contains("budget 600s"))
    }

    @Test
    fun `no selection without minimum evidence`() {
        val p = profileWith(Skill.PRODUCTION, 0.20, 3)
        assertNull(InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items))
    }

    @Test
    fun `no selection when no skill is in deficit`() {
        val p = profileWith(Skill.GRAMMAR, 0.80, 6)
        assertNull(InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items))
    }

    @Test
    fun `cooldown blocks immediate reuse`() {
        val p = profileWith(Skill.PRODUCTION, 0.20, 6)
        p.markUsed(InterventionType.PRODUCTION_FIRST.name, day)
        assertNull("same-day reuse must be blocked", InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items))
        val nextDay = InterventionSelector().select(p, 600, emptyMap(), day + 2, day + 1, items)
        assertNotNull("after cooldownDays the type must be available again", nextDay)
    }

    @Test
    fun `daily caps enforced`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        p.recordEvidence(Skill.PRODUCTION, 0.20, 1.0, day, false)
        p.recordEvidence(Skill.PRODUCTION, 0.20, 1.0, day, false)
        p.recordEvidence(Skill.PRODUCTION, 0.20, 1.0, day, false)
        p.recordEvidence(Skill.PRODUCTION, 0.20, 1.0, day, false)
        // per-type cap: listening already used once today
        val sel = InterventionSelector().select(p, 600, mapOf("LISTENING_INPUT" to 1), day, day - 1, items)
        assertEquals(InterventionType.PRODUCTION_FIRST, sel!!.type)
        // per-day cap
        assertNull(
            InterventionSelector().select(
                p, 600, mapOf("LISTENING_INPUT" to 1, "PRODUCTION_FIRST" to 1), day, day - 1, items,
            ),
        )
    }

    @Test
    fun `repeatedly ineffective intervention type is suspended`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        repeat(3) { p.recordInterventionDelta(InterventionType.LISTENING_INPUT.name, 0.0) }
        assertNull(InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items))
    }

    @Test
    fun `effective history keeps the type available`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        repeat(3) { p.recordInterventionDelta(InterventionType.LISTENING_INPUT.name, 0.05) }
        assertNotNull(InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items))
    }

    @Test
    fun `budget below cost blocks selection`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        assertNull(InterventionSelector().select(p, 60, emptyMap(), day, day - 1, items))
    }

    @Test
    fun `attendance gap pauses interventions`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        assertNull(
            InterventionSelector().select(
                p, 600, emptyMap(), day, lastActiveEpochDay = day - 3, treatmentItemIds = items,
            ),
        )
    }

    @Test
    fun `no treatment items means no selection`() {
        val p = profileWith(Skill.LISTENING, 0.30, 6)
        assertNull(InterventionSelector().select(p, 600, emptyMap(), day, day - 1, emptyList()))
    }

    @Test
    fun `higher deficit with same evidence wins`() {
        val p = SkillProfile()
        repeat(6) { p.recordEvidence(Skill.LISTENING, 0.30, 1.0, day, false) }
        repeat(6) { p.recordEvidence(Skill.PRODUCTION, 0.45, 1.0, day, false) }
        val sel = InterventionSelector().select(p, 600, emptyMap(), day, day - 1, items)
        assertEquals(InterventionType.LISTENING_INPUT, sel!!.type)
    }
}
