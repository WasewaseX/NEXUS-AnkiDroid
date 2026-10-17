package io.github.wasewasex.nexus.experiment

import io.github.wasewasex.nexus.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Counterbalancing, held-out integrity, delayed-assessment scheduling, export round-trip. */
class ExperimentTest {

    @Test
    fun `counterbalanced split is exact and disjoint`() {
        val em = ExperimentManager()
        val ids = (1..40).map { "item-%03d".format(it) }
        em.assignItems(ids)
        val control = em.studyableIds(Arm.CONTROL)
        val treatment = em.studyableIds(Arm.TREATMENT)
        val hold = em.heldOutIds()
        // 40 items, 10% held out -> 36 studyable -> 18/18
        assertEquals(18, control.size)
        assertEquals(18, treatment.size)
        assertEquals(4, hold.size)
        assertEquals(40, (control + treatment + hold).size)
        assertTrue((control intersect treatment).isEmpty())
        assertTrue((hold intersect control).isEmpty())
        assertTrue((hold intersect treatment).isEmpty())
    }

    @Test
    fun `odd sized deck still balances studyable arms`() {
        val em = ExperimentManager()
        val ids = (1..41).map { "item-%03d".format(it) }
        em.assignItems(ids)
        assertEquals(18, em.studyableIds(Arm.CONTROL).size)
        assertEquals(18, em.studyableIds(Arm.TREATMENT).size)
        assertEquals(5, em.heldOutIds().size)
    }

    @Test
    fun `deterministic assignment for the same input`() {
        val ids = (1..40).map { "item-%03d".format(it) }
        val a = ExperimentManager().apply { assignItems(ids) }
        val b = ExperimentManager().apply { assignItems(ids) }
        for (id in ids) assertEquals(a.armOf(id), b.armOf(id))
    }

    @Test
    fun `delayed assessments scheduled at first seen plus 7 and 30 days`() {
        val em = ExperimentManager()
        val ids = (1..40).map { "item-%03d".format(it) }
        em.assignItems(ids)
        val id = em.studyableIds(Arm.TREATMENT)[0]
        em.markSeen(id, 100)
        assertEquals(107, em.assignments[id]!!.day7Due)
        assertEquals(130, em.assignments[id]!!.day30Due)
        assertTrue(em.assessmentsDue(106).isEmpty())
        assertEquals(listOf(id), em.assessmentsDue(107).map { it.itemId })
        em.markAssessed(id, AssessmentKind.DAY7)
        assertTrue("day7 done must disappear from due list", em.assessmentsDue(107).isEmpty())
        assertEquals(listOf(id), em.assessmentsDue(130).map { it.itemId })
    }

    @Test
    fun `held out items are never studyable in either arm`() {
        val em = ExperimentManager()
        val ids = (1..40).map { "item-%03d".format(it) }
        em.assignItems(ids)
        val hold = em.heldOutIds()
        assertTrue(hold.isNotEmpty())
        for (id in hold) {
            assertFalse(em.studyableIds(Arm.CONTROL).contains(id))
            assertFalse(em.studyableIds(Arm.TREATMENT).contains(id))
        }
    }

    @Test
    fun `aggregate computes DPI ingredients from real events only`() {
        val em = ExperimentManager()
        em.recordEvent(1L, "CONTROL", "REVIEW", "a", "MEANING_RECALL", 1.0, 60, "")
        em.recordEvent(2L, "CONTROL", "REVIEW", "b", "MEANING_RECALL", 1.0, 60, "")
        em.recordEvent(3L, "CONTROL", "ASSESSMENT_DAY7", "a", "PRODUCTION", 0.5, 90, "")
        em.recordEvent(4L, "TREATMENT", "REVIEW", "c", "MEANING_RECALL", 1.0, 60, "")
        em.recordEvent(5L, "TREATMENT", "EXERCISE", "c", "LISTENING", 0.8, 120, "")
        em.recordEvent(6L, "TREATMENT", "ASSESSMENT_DAY7", "c", "PRODUCTION", 1.0, 90, "")
        val agg = em.aggregate()
        assertEquals(120.0, agg["control.activeSeconds"]!!, 1e-9)
        assertEquals(270.0, agg["treatment.activeSeconds"]!!, 1e-9)
        assertEquals(2.0, agg["control.nReviews"]!!, 1e-9)
        assertEquals(1.0, agg["treatment.nExercises"]!!, 1e-9)
        assertEquals(0.5, agg["control.ASSESSMENT_DAY7.PRODUCTION.mean"]!!, 1e-9)
        assertEquals(1.0, agg["treatment.ASSESSMENT_DAY7.PRODUCTION.mean"]!!, 1e-9)
        assertTrue(agg["control.ASSESSMENT_DAY30.PRODUCTION.mean"]!!.isNaN())
    }

    @Test
    fun `gson round trip preserves assignment and events`() {
        val em = ExperimentManager()
        val ids = (1..20).map { "item-%02d".format(it) }
        em.assignItems(ids)
        em.markSeen(ids[0], 50)
        em.recordEvent(9L, "CONTROL", "REVIEW", ids[0], "MEANING_RECALL", 0.75, 30, "roundtrip")
        val s1 = Json.toJson(em)
        val em2 = Json.fromJson<ExperimentManager>(s1)
        val s2 = Json.toJson(em2)
        assertEquals(s1, s2)
        assertEquals(em.armOf(ids[0]), em2.armOf(ids[0]))
        assertEquals(1, em2.events.size)
        assertEquals(0.75, em2.events[0].outcome, 0.0)
    }
}
