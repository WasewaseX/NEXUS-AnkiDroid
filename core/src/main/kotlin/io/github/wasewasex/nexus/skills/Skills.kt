package io.github.wasewasex.nexus.skills

/**
 * The five NEXUS-SCOPE Level-1 skills. Evidence comes from real reviews, exercises and
 * delayed assessments; no level is ever assumed or fabricated.
 */
enum class Skill {
    MEANING_RECALL,
    LISTENING,
    PRODUCTION,
    GRAMMAR,
    TRANSFER;

    companion object {
        fun from(name: String): Skill = entries.first { it.name == name }
    }
}

/** One skill's evidence state. Level in 0..1. */
class SkillState(
    var level: Double = 0.5,
    var evidenceCount: Int = 0,
    /** True while the level rests on unverified exercise evidence; cleared by delayed assessments. */
    var provisional: Boolean = false,
    var lastEvidenceEpochDay: Long = 0,
) {
    fun copy(): SkillState = SkillState(level, evidenceCount, provisional, lastEvidenceEpochDay)
}

/**
 * Five-skill profile (NEXUS-SCOPE Level 1). Updates are exponential moving averages weighted
 * by evidence confidence; every update is recorded by the caller in the audit log.
 * All map keys are Strings so Gson round-trips cleanly.
 */
class SkillProfile {
    var states: LinkedHashMap<String, SkillState> = LinkedHashMap()
    /** Last intervention outcome deltas per InterventionType (repeated-ineffectiveness guard). */
    var typeDeltas: LinkedHashMap<String, ArrayList<Double>> = LinkedHashMap()
    /** Last day each intervention type was used (cooldown enforcement). */
    var typeLastUsedDay: LinkedHashMap<String, Long> = LinkedHashMap()

    fun state(skill: Skill): SkillState = states.getOrPut(skill.name) { SkillState() }

    fun level(skill: Skill): Double = state(skill).level

    /**
     * Record one piece of evidence. [weight] in 0..1 is the evidence confidence;
     * [provisional] marks unverified exercise evidence.
     */
    fun recordEvidence(skill: Skill, outcome: Double, weight: Double, epochDay: Long, provisional: Boolean) {
        val s = state(skill)
        val clamped = outcome.coerceIn(0.0, 1.0)
        val a = weight.coerceIn(0.0, 1.0)
        s.level = ((1.0 - a) * s.level + a * clamped).coerceIn(0.0, 1.0)
        s.evidenceCount += 1
        s.lastEvidenceEpochDay = epochDay
        s.provisional = provisional || s.provisional
    }

    fun recordInterventionDelta(type: String, delta: Double) {
        val list = typeDeltas.getOrPut(type) { ArrayList() }
        list.add(delta)
        while (list.size > 5) list.removeAt(0)
    }

    fun lastUsedDay(type: String): Long = typeLastUsedDay[type] ?: -1L

    fun markUsed(type: String, epochDay: Long) {
        typeLastUsedDay[type] = epochDay
    }

    /** Average of the last [window] deltas for a type, or null if not enough history. */
    fun recentAvgDelta(type: String, window: Int): Double? {
        val list = typeDeltas[type] ?: return null
        if (list.size < window) return null
        return list.takeLast(window).average()
    }

    /** Evidence confidence in 0..1, saturating at 12 independent observations. */
    fun confidence(skill: Skill): Double {
        val n = state(skill).evidenceCount
        if (n <= 0) return 0.0
        val v = n / 12.0
        return if (v > 1.0) 1.0 else v
    }
}
