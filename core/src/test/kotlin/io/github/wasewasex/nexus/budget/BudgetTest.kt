package io.github.wasewasex.nexus.budget

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Budget limits: exact percentages, FSRS review protection, backlog guard, day reset. */
class BudgetTest {

    @Test
    fun `zero budget never allows enrichment`() {
        val b = BudgetController(budgetPct = 0)
        b.recordReviewTime(600)
        assertFalse(b.canEnrich(reviewsDue = 0, overdue = 0, costSeconds = 10))
        assertEquals(0, b.allowedSeconds())
    }

    @Test
    fun `twenty percent of review time is the allowance`() {
        val b = BudgetController(budgetPct = 20)
        b.recordReviewTime(600)
        assertEquals(120, b.allowedSeconds())
        assertEquals(120, b.remainingSeconds())
        b.recordEnrichment(100)
        assertEquals(20, b.remainingSeconds())
        assertFalse(b.canEnrich(reviewsDue = 0, overdue = 0, costSeconds = 30))
        assertTrue(b.canEnrich(reviewsDue = 0, overdue = 0, costSeconds = 20))
    }

    @Test
    fun `enrichment never grows its own allowance`() {
        val b = BudgetController(budgetPct = 30)
        b.recordReviewTime(300)
        assertEquals(90, b.allowedSeconds())
        b.recordEnrichment(90)
        b.recordReviewTime(0)
        assertEquals(90, b.allowedSeconds())
        assertEquals(0, b.remainingSeconds())
    }

    @Test
    fun `scheduled reviews are protected until done`() {
        val b = BudgetController(budgetPct = 20)
        b.recordReviewTime(600)
        assertFalse(b.canEnrich(reviewsDue = 1, overdue = 0, costSeconds = 10))
        assertTrue(b.canEnrich(reviewsDue = 0, overdue = 0, costSeconds = 10))
    }

    @Test
    fun `backlog above threshold blocks enrichment`() {
        val b = BudgetController(budgetPct = 20)
        b.recordReviewTime(600)
        assertFalse(b.canEnrich(reviewsDue = 0, overdue = 21, costSeconds = 10))
        assertTrue(b.canEnrich(reviewsDue = 0, overdue = 20, costSeconds = 10))
    }

    @Test
    fun `new day resets counters`() {
        val b = BudgetController(budgetPct = 20)
        b.newDayIfNeeded(100)
        b.recordReviewTime(600)
        b.recordEnrichment(50)
        b.newDayIfNeeded(100) // same day: no reset
        assertEquals(120, b.allowedSeconds())
        b.newDayIfNeeded(101)
        assertEquals(0, b.reviewSecondsToday)
        assertEquals(0, b.enrichmentSecondsToday)
        assertEquals(0, b.remainingSeconds())
    }

    @Test(expected = IllegalArgumentException::class)
    fun `invalid budget percent rejected`() {
        BudgetController().changeBudget(15)
    }

    @Test
    fun `all pre-registered budget levels accepted`() {
        for (p in intArrayOf(0, 10, 20, 30)) {
            val b = BudgetController()
            b.changeBudget(p)
            assertEquals(p, b.budgetPct)
        }
    }
}
