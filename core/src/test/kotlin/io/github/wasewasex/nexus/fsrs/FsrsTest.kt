package io.github.wasewasex.nexus.fsrs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * Verifies the FSRS-5 port: retrievability math, stability dynamics, difficulty dynamics,
 * interval ordering, determinism and review-log integrity.
 */
class FsrsTest {

    private val fsrs = Fsrs()
    /** 2026-01-01T10:00:00 UTC. */
    private val t0 = 1767261600000L
    private val day0 = Fsrs.epochDay(t0)

    private fun millisAt(day: Long, hour: Int = 10) = day * 86_400_000L + hour * 3_600_000L

    @Test
    fun `retrievability at one stability equals 0_9`() {
        val c = FsrsCard(id = "x", state = CardState.REVIEW, stability = 10.0, lastReviewEpochDay = day0)
        val at = millisAt(day0 + 10)
        assertEquals(0.9, fsrs.retrievability(c, at), 1e-6)
    }

    @Test
    fun `retrievability decays monotonically and is bounded`() {
        val c = FsrsCard(id = "x", state = CardState.REVIEW, stability = 5.0, lastReviewEpochDay = day0)
        var prev = 1.0
        for (d in 1L..30L) {
            val r = fsrs.retrievability(c, millisAt(day0 + d))
            assertTrue(r < prev && r > 0.0)
            prev = r
        }
    }

    @Test
    fun `new card enters learning step then graduates to review`() {
        val c = FsrsCard(id = "c1")
        val r1 = fsrs.review(c, Rating.GOOD, t0)
        assertEquals(CardState.LEARNING, r1.card.state)
        assertEquals(Fsrs.epochDay(t0 + 10 * 60_000), r1.card.dueEpochDay)
        // same-day graduation
        val r2 = fsrs.review(r1.card, Rating.GOOD, t0 + 15 * 60_000)
        assertEquals(CardState.REVIEW, r2.card.state)
        assertTrue(r2.card.dueEpochDay > day0)
        assertTrue(r2.card.stability > 0.0)
    }

    @Test
    fun `stability grows across successful spaced reviews`() {
        var card = FsrsCard(id = "g")
        card = fsrs.review(card, Rating.GOOD, t0).card
        card = fsrs.review(card, Rating.GOOD, t0 + 15 * 60_000).card
        val s1 = card.stability
        val due1 = card.dueEpochDay
        card = fsrs.review(card, Rating.GOOD, millisAt(due1)).card
        val s2 = card.stability
        val due2 = card.dueEpochDay
        card = fsrs.review(card, Rating.GOOD, millisAt(due2)).card
        val s3 = card.stability
        assertTrue("s2 $s2 should exceed s1 $s1", s2 > s1)
        assertTrue("s3 $s3 should exceed s2 $s2", s3 > s2)
        assertTrue(due2 - due1 >= 1)
    }

    @Test
    fun `lapse drops stability and moves to relearning`() {
        var card = FsrsCard(id = "l")
        card = fsrs.review(card, Rating.GOOD, t0).card
        card = fsrs.review(card, Rating.GOOD, t0 + 15 * 60_000).card
        val sBefore = card.stability
        // review far in the future, then fail
        card = fsrs.review(card, Rating.GOOD, millisAt(card.dueEpochDay)).card
        val r = fsrs.review(card, Rating.AGAIN, millisAt(card.dueEpochDay))
        assertEquals(CardState.RELEARNING, r.card.state)
        assertTrue("stability after lapse ${r.card.stability} should drop below $sBefore", r.card.stability < sBefore)
        assertEquals(1, r.card.lapses)
    }

    @Test
    fun `difficulty moves toward easier after easy and harder after again`() {
        var a = FsrsCard(id = "a")
        var b = FsrsCard(id = "b")
        a = fsrs.review(a, Rating.GOOD, t0).card
        b = fsrs.review(b, Rating.GOOD, t0).card
        a = fsrs.review(a, Rating.GOOD, t0 + 15 * 60_000).card
        b = fsrs.review(b, Rating.GOOD, t0 + 15 * 60_000).card
        assertEquals(a.difficulty, b.difficulty, 1e-9)
        a = fsrs.review(a, Rating.EASY, millisAt(a.dueEpochDay)).card
        b = fsrs.review(b, Rating.AGAIN, millisAt(b.dueEpochDay)).card
        assertTrue("easy difficulty ${a.difficulty} should be lower", a.difficulty < b.difficulty)
        assertTrue(a.difficulty in 1.0..10.0)
        assertTrue(b.difficulty in 1.0..10.0)
    }

    @Test
    fun `easy interval geq good geq hard for same history`() {
        fun rated(r: Rating): FsrsCard {
            var c = FsrsCard(id = r.name)
            c = fsrs.review(c, Rating.GOOD, t0).card
            c = fsrs.review(c, Rating.GOOD, t0 + 15 * 60_000).card
            return fsrs.review(c, r, millisAt(c.dueEpochDay)).card
        }
        val easy = rated(Rating.EASY).dueEpochDay
        val good = rated(Rating.GOOD).dueEpochDay
        val hard = rated(Rating.HARD).dueEpochDay
        assertTrue(easy >= good)
        assertTrue(good >= hard)
    }

    @Test
    fun `late review logs correct elapsed days and still schedules`() {
        var c = FsrsCard(id = "late")
        c = fsrs.review(c, Rating.GOOD, t0).card
        c = fsrs.review(c, Rating.GOOD, t0 + 15 * 60_000).card
        val scheduled = c.dueEpochDay
        val r = fsrs.review(c, Rating.GOOD, millisAt(scheduled + 3)) // 3 days late
        assertEquals(3L, r.reviewLog.elapsedDays)
        assertTrue(r.card.dueEpochDay > Fsrs.epochDay(millisAt(scheduled + 3)))
    }

    @Test
    fun `deterministic same inputs same outputs`() {
        fun run(): FsrsResult {
            var c = FsrsCard(id = "d")
            c = fsrs.review(c, Rating.GOOD, t0).card
            c = fsrs.review(c, Rating.GOOD, t0 + 15 * 60_000).card
            return fsrs.review(c, Rating.GOOD, millisAt(c.dueEpochDay))
        }
        val a = run()
        val b = run()
        assertEquals(a.card.stability, b.card.stability, 0.0)
        assertEquals(a.card.difficulty, b.card.difficulty, 0.0)
        assertEquals(a.card.dueEpochDay, b.card.dueEpochDay)
    }

    @Test
    fun `interval matches desired retention semantics`() {
        // intervalFor(S) at 0.9 retention must equal S (FACTOR chosen so R(S)=0.9)
        assertEquals(10L, fsrs.intervalFor(10.0))
        assertEquals(1L, fsrs.intervalFor(0.5)) // floor of 1 day
        assertTrue(abs(fsrs.intervalFor(33.3) - 33L) <= 1L)
    }
}
