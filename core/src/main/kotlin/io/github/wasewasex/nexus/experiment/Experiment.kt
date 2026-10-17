package io.github.wasewasex.nexus.experiment

/**
 * Within-app randomized experiment: the same deck is split into a CONTROL arm (pure FSRS)
 * and a TREATMENT arm (FSRS + NEXUS-SCOPE). Each item belongs to exactly one arm and is
 * never re-studied in the other condition. Held-out items are never studied at all and are
 * reserved for delayed assessments (novel-item transfer / unfamiliar listening).
 */
enum class Arm { CONTROL, TREATMENT }

enum class AssessmentKind { DAY7, DAY30 }

class ExperimentConfig(
    var treatmentBudgetPct: Int = 20,
    /** Delayed assessment days after first encounter. */
    var assessmentDays: ArrayList<Int> = arrayListOf(7, 30),
    /** Fraction of the deck reserved as held-out assessment items. */
    var heldOutFraction: Double = 0.1,
    var salt: String = "nexus-v0.1",
)

class ItemAssignment(
    var itemId: String = "",
    var arm: Arm = Arm.CONTROL,
    var heldOut: Boolean = false,
    var firstSeenEpochDay: Long = 0,
    var day7Due: Long = 0,
    var day30Due: Long = 0,
    var day7Done: Boolean = false,
    var day30Done: Boolean = false,
)

/**
 * One logged experiment event. Together with the audit log this is the raw evidence stream;
 * DPI-equivalent endpoints are computed OFFLINE from exports — nothing here hardcodes or
 * predicts any improvement.
 */
class ExperimentEvent(
    var millis: Long = 0,
    var arm: String = "",
    var kind: String = "", // REVIEW | EXERCISE | ASSESSMENT_DAY7 | ASSESSMENT_DAY30
    var itemId: String = "",
    var skill: String = "",
    var outcome: Double = 0.0,
    var durationSeconds: Int = 0,
    var details: String = "",
)

class ExperimentManager(var config: ExperimentConfig = ExperimentConfig()) {
    var assignments: LinkedHashMap<String, ItemAssignment> = LinkedHashMap()
    var events: ArrayList<ExperimentEvent> = ArrayList()

    /**
     * Counterbalanced assignment. Items are sorted (deterministic), the last ceil(n*fraction)
     * become held-out assessment items, the rest are paired; within each pair one item goes to
     * CONTROL and one to TREATMENT, alternating order across pairs to cancel position effects.
     */
    fun assignItems(itemIds: List<String>) {
        val sorted = itemIds.sorted()
        val nHold = Math.ceil(sorted.size * config.heldOutFraction).toInt()
            .coerceIn(0, sorted.size - 2) // always keep at least 2 studyable items
        val hold = if (nHold > 0) sorted.takeLast(nHold) else emptyList()
        val study = sorted.dropLast(nHold)
        study.chunked(2).forEachIndexed { i, pair ->
            if (pair.size == 2) {
                val (a, b) = pair
                if (i % 2 == 0) {
                    put(a, Arm.CONTROL); put(b, Arm.TREATMENT)
                } else {
                    put(a, Arm.TREATMENT); put(b, Arm.CONTROL)
                }
            } else {
                put(pair[0], if (i % 2 == 0) Arm.CONTROL else Arm.TREATMENT)
            }
        }
        hold.forEach { id -> assignments[id] = ItemAssignment(itemId = id, arm = Arm.CONTROL, heldOut = true) }
    }

    private fun put(id: String, arm: Arm) {
        assignments[id] = ItemAssignment(itemId = id, arm = arm)
    }

    fun armOf(itemId: String): Arm? = assignments[itemId]?.arm

    fun studyableIds(arm: Arm): List<String> =
        assignments.values.filter { !it.heldOut && it.arm == arm }.map { it.itemId }

    fun heldOutIds(): List<String> = assignments.values.filter { it.heldOut }.map { it.itemId }

    fun markSeen(itemId: String, epochDay: Long) {
        val a = assignments[itemId] ?: return
        if (a.firstSeenEpochDay == 0L) {
            a.firstSeenEpochDay = epochDay
            a.day7Due = epochDay + (config.assessmentDays.getOrNull(0) ?: 7)
            a.day30Due = epochDay + (config.assessmentDays.getOrNull(1) ?: 30)
        }
    }

    fun assessmentsDue(epochDay: Long): List<ItemAssignment> = assignments.values.filter { a ->
        a.firstSeenEpochDay > 0 && (
            (!a.day7Done && a.day7Due in 1..epochDay) ||
                (!a.day30Done && a.day30Due in 1..epochDay)
            )
    }

    fun markAssessed(itemId: String, kind: AssessmentKind) {
        val a = assignments[itemId] ?: return
        when (kind) {
            AssessmentKind.DAY7 -> a.day7Done = true
            AssessmentKind.DAY30 -> a.day30Done = true
        }
    }

    fun recordEvent(
        millis: Long, arm: String, kind: String, itemId: String,
        skill: String, outcome: Double, durationSeconds: Int, details: String,
    ) {
        events.add(ExperimentEvent(millis, arm, kind, itemId, skill, outcome, durationSeconds, details))
    }

    /**
     * Aggregates the raw DPI ingredients per arm, computed only from real logged events:
     * active study seconds (reviews + exercises), delayed assessment outcomes at day 7/30
     * (overall and per skill). No target, threshold or prediction is applied here.
     */
    fun aggregate(): LinkedHashMap<String, Double> {
        val out = LinkedHashMap<String, Double>()
        for (arm in listOf("CONTROL", "TREATMENT")) {
            val armEvents = events.filter { it.arm == arm }
            val reviews = armEvents.filter { it.kind == "REVIEW" }
            val exercises = armEvents.filter { it.kind == "EXERCISE" }
            val activeSeconds = armEvents.sumOf { it.durationSeconds.toDouble() }
            out["${arm.lowercase()}.nReviews"] = reviews.size.toDouble()
            out["${arm.lowercase()}.nExercises"] = exercises.size.toDouble()
            out["${arm.lowercase()}.activeSeconds"] = activeSeconds
            for (kind in listOf("ASSESSMENT_DAY7", "ASSESSMENT_DAY30")) {
                val subset = armEvents.filter { it.kind == kind }
                out["${arm.lowercase()}.$kind.mean"] =
                    if (subset.isEmpty()) Double.NaN else subset.map { it.outcome }.average()
                for (skill in listOf("MEANING_RECALL", "PRODUCTION", "LISTENING", "GRAMMAR", "TRANSFER")) {
                    val bySkill = subset.filter { it.skill == skill }
                    out["${arm.lowercase()}.$kind.$skill.mean"] =
                        if (bySkill.isEmpty()) Double.NaN else bySkill.map { it.outcome }.average()
                }
            }
        }
        return out
    }
}
