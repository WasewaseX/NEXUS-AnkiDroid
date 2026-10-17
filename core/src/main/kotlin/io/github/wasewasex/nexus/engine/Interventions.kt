package io.github.wasewasex.nexus.engine

import io.github.wasewasex.nexus.skills.Skill
import io.github.wasewasex.nexus.skills.SkillProfile

/**
 * The five NEXUS-SCOPE Level-2 specialist interventions with their evidence-based costs.
 * Each targets exactly one Level-1 skill.
 */
enum class InterventionType(
    val skill: Skill,
    val costSeconds: Int,
    val cooldownDays: Long,
) {
    /** Varied audio, transcript hidden until after the attempt. */
    LISTENING_INPUT(Skill.LISTENING, 120, 1),

    /** Produce before seeing the answer. */
    PRODUCTION_FIRST(Skill.PRODUCTION, 180, 2),

    /** Contrastive correction + targeted repair. */
    GRAMMAR_REPAIR(Skill.GRAMMAR, 150, 2),

    /** Known expressions in unfamiliar contexts. */
    TRANSFER_TASK(Skill.TRANSFER, 120, 2),

    /** Confident mistake -> corrective feedback + independent retry. */
    PREDICTION_ERROR_REPAIR(Skill.MEANING_RECALL, 120, 1);

    companion object {
        fun from(name: String): InterventionType = entries.first { it.name == name }
    }
}

class SelectorConfig(
    var minEvidence: Int = 4,
    /** A skill is in deficit when its level is below this. */
    var deficitThreshold: Double = 0.55,
    var maxInterventionsPerDay: Int = 2,
    var maxPerTypePerDay: Int = 1,
    /** Repeated-ineffectiveness guard: after this many uses, the type is suspended if... */
    var ineffectiveWindow: Int = 3,
    /** ...the average level delta over the window is below this. */
    var ineffectiveMinAvgDelta: Double = 0.02,
    /** Attendance-gap tolerance: pause interventions after this many inactive days. */
    var attendanceGapPauseDays: Long = 3,
)

class SelectedIntervention(
    var type: InterventionType = InterventionType.LISTENING_INPUT,
    var itemId: String = "",
    var costSeconds: Int = 0,
    /** Human-auditable justification: deficit, evidence count, budget, cooldown. */
    var rationale: String = "",
)

/**
 * NEXUS-SCOPE intervention selection. Deterministic, rule-based and fully auditable.
 * It NEVER changes FSRS state; it only reads the skill profile and budget.
 */
class InterventionSelector(var config: SelectorConfig = SelectorConfig()) {

    /**
     * @param budgetRemainingSeconds enrichment seconds still available today
     * @param countsToday type -> number of interventions already done today
     * @param day current UTC epoch day
     * @param lastActiveEpochDay last day the learner studied (0 = never)
     * @param treatmentItemIds candidate item ids belonging to the treatment arm
     */
    fun select(
        profile: SkillProfile,
        budgetRemainingSeconds: Int,
        countsToday: Map<String, Int>,
        day: Long,
        lastActiveEpochDay: Long,
        treatmentItemIds: List<String>,
    ): SelectedIntervention? {
        if (treatmentItemIds.isEmpty()) return null
        if (lastActiveEpochDay > 0 && day - lastActiveEpochDay >= config.attendanceGapPauseDays) {
            return null
        }
        val totalToday = countsToday.values.sum()
        if (totalToday >= config.maxInterventionsPerDay) return null

        var bestType: InterventionType? = null
        var bestScore = Double.NEGATIVE_INFINITY
        var bestReason = ""
        for (type in InterventionType.entries) {
            if ((countsToday[type.name] ?: 0) >= config.maxPerTypePerDay) continue
            val cooldownEnd = profile.lastUsedDay(type.name) + type.cooldownDays
            if (day < cooldownEnd) continue
            val avgDelta = profile.recentAvgDelta(type.name, config.ineffectiveWindow)
            if (avgDelta != null && avgDelta < config.ineffectiveMinAvgDelta) continue
            val st = profile.state(type.skill)
            if (st.evidenceCount < config.minEvidence) continue
            val deficit = config.deficitThreshold - st.level
            if (deficit <= 0.0) continue
            if (type.costSeconds > budgetRemainingSeconds) continue
            val score = deficit * profile.confidence(type.skill)
            if (score > bestScore) {
                bestScore = score
                bestType = type
                bestReason = buildString {
                    append(type.skill.name).append(" level ")
                    append("%.2f".format(st.level))
                    append(" below threshold ")
                    append("%.2f".format(config.deficitThreshold))
                    append(" (deficit ")
                    append("%.2f".format(deficit))
                    append("), evidence n=").append(st.evidenceCount)
                    append(", confidence=").append("%.2f".format(profile.confidence(type.skill)))
                    append(", budget ").append(budgetRemainingSeconds).append("s remaining")
                    append(", cost ").append(type.costSeconds).append("s")
                    if (st.provisional) append(", level provisional until delayed verification")
                }
            }
        }
        bestType ?: return null
        return SelectedIntervention(
            type = bestType,
            itemId = treatmentItemIds.first(),
            costSeconds = bestType.costSeconds,
            rationale = bestReason,
        )
    }
}
