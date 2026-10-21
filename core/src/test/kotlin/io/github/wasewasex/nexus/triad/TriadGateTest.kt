package io.github.wasewasex.nexus.triad

import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.fsrs.FsrsCard
import io.github.wasewasex.nexus.fsrs.Rating
import io.github.wasewasex.nexus.json.Json
import io.github.wasewasex.nexus.session.AppState
import io.github.wasewasex.nexus.session.SessionEngine
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * THE TRIAD gate suite: the feature flag must keep TRIAD interval adjustments structurally
 * disabled (FSRS-5 stays the authoritative scheduler, byte-identical to the stock algorithm),
 * the gate math must match the v1.8 reference port, and every gate consultation must leave an
 * audit receipt while no TRIAD_INTERVAL_ADJUSTED entry may ever appear in this release.
 */
class TriadGateTest {

    /** 2026-01-01T10:00 UTC — same fixed clock as the isolation and round-trip suites. */
    private val t0 = 1767261600000L
    private val day = 86_400_000L

    private fun obs(
        acc: Double = 0.85,
        slowdown: Double = 1.0,
        due: Int = 15,
        fatigue: Double = 0.0,
        gap: Double = 0.0,
    ) = TriadContextObservables(acc, slowdown, due, fatigue, gap)

    private fun freshEngine(nItems: Int = 24): Pair<SessionEngine, List<String>> {
        val state = AppState()
        val eng = SessionEngine(state)
        eng.ensureDay(Fsrs.epochDay(t0))
        val ids = (1..nItems).map { "t%03d".format(it) }
        eng.initializeDeck(ids, t0)
        return eng to ids
    }

    // ---------------------------------------------------------------- release policy

    @Test
    fun `interval adjustment flag is hard-disabled in this release`() {
        assertFalse(TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS)
        assertTrue(TriadFeatureFlags.TRIAD_OBSERVABILITY)
    }

    @Test
    fun `gate decision order is flag then alpha then enablement`() {
        assertEquals("disabled_by_flag", TriadGate.decisionFor(false, 0.75))
        assertEquals("alpha_zero", TriadGate.decisionFor(true, 0.0))
        assertEquals("enabled", TriadGate.decisionFor(true, 0.75))
    }

    // ---------------------------------------------------------------- reference math port

    @Test
    fun `delta formula matches the v18 reference port`() {
        val gate = TriadGate()
        // All-neutral observables -> exactly 0.
        assertEquals(0.0, gate.deltaContext(obs()), 1e-12)
        // Pure accuracy: 2.0 * (0.95 - 0.85).
        assertEquals(0.2, gate.deltaContext(obs(acc = 0.95)), 1e-12)
        // Pure latency: -0.8 * (1.5 - 1.0).
        assertEquals(-0.4, gate.deltaContext(obs(slowdown = 1.5)), 1e-12)
        // Pure workload: due=45 -> ratio 1.5 -> -0.4 * (1.5 - 0.5).
        assertEquals(-0.4, gate.deltaContext(obs(due = 45)), 1e-12)
        // Workload cap: due=200 -> ratio capped at 3.0 -> -0.4 * (3.0 - 0.5).
        assertEquals(-1.0, gate.deltaContext(obs(due = 200)), 1e-12)
        // Pure fatigue: -0.5 * 0.6.
        assertEquals(-0.3, gate.deltaContext(obs(fatigue = 0.6)), 1e-12)
        // Pure absence: -0.3 * min(3.5/7, 1).
        assertEquals(-0.15, gate.deltaContext(obs(gap = 3.5)), 1e-12)
        // Negative clip: slowdown 3.0 -> -1.6 -> clipped to -1.5.
        assertEquals(-1.5, gate.deltaContext(obs(slowdown = 3.0)), 1e-12)
        // Positive clip via a-priori-weight override: 12 * (1.0 - 0.85) = 1.8 -> clipped to 1.5.
        val custom = TriadGate(TriadWeights(acc = 12.0, lat = 0.0, workload = 0.0, fatigue = 0.0, absence = 0.0))
        assertEquals(1.5, custom.deltaContext(obs(acc = 1.0)), 1e-12)
    }

    @Test
    fun `hybrid with alpha zero is the identity on the clipped effective probability`() {
        val gate = TriadGate()
        assertEquals(0.9, gate.hybrid(0.9, delta = 5.0, alpha = 0.0), 1e-12)
        // Alpha > 0 direction: negative delta must lower the hybrid estimate.
        // logit(0.9)=2.1972245773; sigmoid(2.1972245773 - 1.0) = 0.7680306833...
        assertEquals(0.7680306833, gate.hybrid(0.9, delta = -1.0, alpha = 1.0), 1e-9)
        assertTrue(gate.hybrid(0.9, delta = -1.0, alpha = 1.0) < 0.9)
    }

    // ---------------------------------------------------------------- gate refusals

    @Test
    fun `propose refuses under release defaults and every partial enablement`() {
        val gate = TriadGate()
        val o = obs(slowdown = 3.0) // |delta| well above the action floor
        assertNull("release defaults (flag off, alpha 0)", gate.proposeIntervalAdjustment(o, 0.0, false))
        assertNull("flag dominates even with a nonzero alpha", gate.proposeIntervalAdjustment(o, 0.75, false))
        assertNull("alpha zero refuses even with the flag on", gate.proposeIntervalAdjustment(o, 0.0, true))
        val small = obs(acc = 0.86) // delta = 0.02, below the 0.05 action floor
        assertNull("below action floor", gate.proposeIntervalAdjustment(small, 0.75, true))
    }

    @Test
    fun `hypothetical enablement produces a sane unvalidated candidate only`() {
        val gate = TriadGate()
        val o = obs(slowdown = 3.0) // delta clipped to -1.5
        val p = gate.proposeIntervalAdjustment(o, 0.75, true)!!
        assertEquals(-1.5, p.deltaLogits, 1e-12)
        assertEquals(0.75, p.alpha, 1e-12)
        // Negative delta => factor < 1 => the (unvalidated) candidate would review sooner.
        assertEquals(kotlin.math.exp(0.75 * -1.5), p.candidateIntervalFactor, 1e-12)
        assertTrue(p.candidateIntervalFactor < 1.0)
        // And SessionEngine never reaches this branch in this release: the flag is a const.
    }

    // ---------------------------------------------------------------- the compliance proof

    @Test
    fun `session engine keeps FSRS-5 scheduling byte-identical to the stock scheduler`() {
        val (eng, ids) = freshEngine(24)
        // Varied, deterministic rating script per item.
        val script = ids.mapIndexed { i, id ->
            listOf(
                Triple(id, Rating.from((i % 4) + 1), t0 + i * 60_000L),
                Triple(id, Rating.GOOD, t0 + 15 * 60_000L + i * 30_000L),
                if (i % 2 == 0) {
                    Triple(id, if (i % 3 == 0) Rating.AGAIN else Rating.HARD, t0 + day + i * 60_000L)
                } else {
                    Triple(id, Rating.EASY, t0 + 3 * day + i * 60_000L)
                },
            )
        }.flatten()
        for ((id, rating, at) in script) eng.recordReview(id, rating, at, 9)

        // Independent raw-FSRS replay of the identical sequence on plain cards.
        // Fsrs.review returns a mutated COPY, so the map must be updated after every step,
        // exactly like SessionEngine.recordReview does with state.cards.
        val raw = Fsrs()
        val rawCards = HashMap<String, FsrsCard>()
        for (id in ids) rawCards[id] = FsrsCard(id = id, dueEpochDay = Fsrs.epochDay(t0))
        for ((id, rating, at) in script) {
            val res = raw.review(rawCards.getValue(id), rating, at)
            rawCards[id] = res.card
        }

        for (id in ids) {
            val viaEngine = eng.card(id)!!
            val viaRaw = rawCards.getValue(id)
            assertEquals("state $id", viaRaw.state, viaEngine.state)
            assertEquals("stability $id", viaRaw.stability, viaEngine.stability, 1e-12)
            assertEquals("difficulty $id", viaRaw.difficulty, viaEngine.difficulty, 1e-12)
            assertEquals("dueEpochDay $id", viaRaw.dueEpochDay, viaEngine.dueEpochDay)
            assertEquals("lastReviewEpochDay $id", viaRaw.lastReviewEpochDay, viaEngine.lastReviewEpochDay)
            assertEquals("reps $id", viaRaw.reps, viaEngine.reps)
            assertEquals("lapses $id", viaRaw.lapses, viaEngine.lapses)
        }
        assertEquals(ids.size * 3, eng.state.reviewLogs.size)
    }

    @Test
    fun `gate writes audit receipts and never an adjustment entry`() {
        val (eng, ids) = freshEngine(6)
        for ((i, id) in ids.withIndex()) eng.recordReview(id, Rating.GOOD, t0 + i * 60_000L, 8)

        val receipts = eng.state.audit.entries.filter { it.kind == "TRIAD_INTERVAL_GATE" }
        assertEquals(ids.size, receipts.size)
        assertTrue(receipts.all { it.payload["decision"] == "disabled_by_flag" })
        assertTrue(receipts.all { it.payload["intervalAdjustmentsEnabled"] == "false" })
        assertTrue(receipts.all { it.payload["alpha"] == "0.0" })
        assertEquals(
            0,
            eng.state.audit.entries.count { it.kind == "TRIAD_INTERVAL_ADJUSTED" },
        )
        // The receipt must always trail the authoritative FSRS record for the same review.
        val reviewEntries = eng.state.audit.entries.filter { it.kind == "FSRS_REVIEW" }
        assertEquals(ids.size, reviewEntries.size)
        for (r in receipts) {
            val idx = eng.state.audit.entries.indexOf(r)
            assertTrue(eng.state.audit.entries.subList(0, idx).any { it.kind == "FSRS_REVIEW" })
        }
    }

    @Test
    fun `triad alpha persists through the state round trip`() {
        val (eng, _) = freshEngine(2)
        val s1 = Json.toJson(eng.state)
        val restored = Json.fromJson<AppState>(s1)
        val s2 = Json.toJson(restored)
        assertEquals(s1, s2)
        assertEquals(0.0, restored.triadAlpha, 1e-12)
    }
}
