package io.github.wasewasex.nexusankidroid

import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.os.SystemClock
import android.view.View
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.card.MaterialCardView
import io.github.wasewasex.nexus.experiment.AssessmentKind
import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.session.SessionEngine
import io.github.wasewasex.nexus.skills.Skill
import kotlin.random.Random

/**
 * Read-only dashboard over the local state: skill profile bars, budget/review counters,
 * the last audit entries, and the REAL per-arm experiment aggregates (no fabricated numbers;
 * em-dash when a mean is NaN). Also hosts the held-out novel-item check and the export.
 */
class DashboardActivity : AppCompatActivity() {

    private lateinit var container: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        StateStore.get(this)
        engine().ensureDay(Fsrs.epochDay(System.currentTimeMillis()))
        setContentView(R.layout.activity_dashboard)
        container = findViewById(R.id.dashboard_container)
        renderAll()
    }

    private fun engine(): SessionEngine = SessionEngine(StateStore.state)

    private fun renderAll() {
        container.removeAllViews()
        renderSkillBars()
        renderBudget()
        renderReviews()
        renderAudit()
        renderExperiment()
        renderButtons()
    }

    // ------------------------------------------------------------------ cards

    private fun card(title: String): LinearLayout {
        val cardView = MaterialCardView(this)
        cardView.radius = nexusDp(12).toFloat()
        cardView.cardElevation = nexusDp(2).toFloat()
        cardView.setContentPadding(nexusDp(12), nexusDp(12), nexusDp(12), nexusDp(12))
        val inner = nexusRow(vertical = true)
        cardView.addView(inner)
        val titleView = TextView(this)
        titleView.text = title
        titleView.textSize = 16f
        titleView.setTypeface(null, Typeface.BOLD)
        titleView.setPadding(0, 0, 0, nexusDp(6))
        inner.addView(titleView)
        container.addView(
            cardView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { setMargins(0, nexusDp(8), 0, nexusDp(8)) },
        )
        return inner
    }

    private fun line(parent: LinearLayout, text: String) {
        val tv = TextView(this)
        tv.text = text
        tv.textSize = 14f
        tv.setPadding(0, nexusDp(2), 0, nexusDp(2))
        parent.addView(tv)
    }

    // ------------------------------------------------------------------ sections

    private fun renderSkillBars() {
        val c = card(getString(R.string.card_skills))
        for (skill in Skill.entries) {
            val st = StateStore.state.profile.state(skill)
            val provisionalSuffix = if (st.provisional) getString(R.string.provisional_suffix) else ""
            val label = TextView(this)
            label.text = getString(
                R.string.skill_line_fmt,
                skill.name,
                "%.2f".format(st.level),
                st.evidenceCount,
                provisionalSuffix,
            )
            label.textSize = 14f
            label.setPadding(0, nexusDp(6), 0, nexusDp(2))
            val bar = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal)
            bar.max = 100
            bar.progress = (st.level * 100).toInt().coerceIn(0, 100)
            c.addView(label)
            c.addView(bar)
        }
    }

    private fun renderBudget() {
        val c = card(getString(R.string.card_budget))
        val b = StateStore.state.budget
        line(c, getString(R.string.budget_allowed_fmt, b.allowedSeconds()))
        line(c, getString(R.string.budget_enrichment_fmt, b.enrichmentSecondsToday))
        line(c, getString(R.string.budget_review_fmt, b.reviewSecondsToday))
        line(c, getString(R.string.budget_remaining_fmt, b.remainingSeconds()))
    }

    private fun renderReviews() {
        val c = card(getString(R.string.card_reviews))
        val e = engine()
        line(c, getString(R.string.reviews_done_fmt, StateStore.state.reviewsDoneToday))
        line(c, getString(R.string.reviews_due_fmt, e.dueReviewIds().size + e.newDueIds().size))
        line(c, getString(R.string.reviews_overdue_fmt, e.overdueCount()))
    }

    private fun renderAudit() {
        val c = card(getString(R.string.card_audit))
        val entries = StateStore.state.audit.last(10)
        if (entries.isEmpty()) {
            line(c, getString(R.string.audit_empty))
            return
        }
        for (entry in entries) {
            val payload = entry.payload.entries.joinToString(" ") { it.key + "=" + it.value }
            line(c, getString(R.string.audit_entry_fmt, entry.kind, payload))
        }
    }

    private fun renderExperiment() {
        val c = card(getString(R.string.card_experiment))
        val agg = StateStore.state.experiment.aggregate()
        for (arm in listOf("CONTROL", "TREATMENT")) {
            val prefix = arm.lowercase() + "."
            line(c, getString(R.string.arm_header_fmt, arm))
            line(c, getString(R.string.metric_fmt, getString(R.string.metric_reviews), fmtCount(agg[prefix + "nReviews"])))
            line(c, getString(R.string.metric_fmt, getString(R.string.metric_exercises), fmtCount(agg[prefix + "nExercises"])))
            line(c, getString(R.string.metric_fmt, getString(R.string.metric_active_seconds), fmtCount(agg[prefix + "activeSeconds"])))
            line(c, getString(R.string.metric_fmt, "DAY7", fmtMean(agg[prefix + "ASSESSMENT_DAY7.mean"])))
            line(c, getString(R.string.metric_fmt, "DAY30", fmtMean(agg[prefix + "ASSESSMENT_DAY30.mean"])))
            for (skill in Skill.entries) {
                val v7 = agg[prefix + "ASSESSMENT_DAY7." + skill.name + ".mean"] ?: Double.NaN
                val v30 = agg[prefix + "ASSESSMENT_DAY30." + skill.name + ".mean"] ?: Double.NaN
                if (!v7.isNaN()) {
                    line(c, "  " + getString(R.string.metric_fmt, "DAY7 · " + skill.name, fmtMean(v7)))
                }
                if (!v30.isNaN()) {
                    line(c, "  " + getString(R.string.metric_fmt, "DAY30 · " + skill.name, fmtMean(v30)))
                }
            }
        }
        line(c, getString(R.string.experiment_caption))
    }

    private fun fmtCount(v: Double?): String = if (v == null || v.isNaN()) "—" else "%.0f".format(v)

    private fun fmtMean(v: Double?): String = if (v == null || v.isNaN()) "—" else "%.2f".format(v)

    private fun renderButtons() {
        val c = card(getString(R.string.card_tools))
        c.addView(nexusButton(getString(R.string.novel_check)) { startNovelCheck() })
        val export = nexusButton(getString(R.string.export_json)) { shareExport() }
        export.isEnabled = StateStore.state.learnerConsent
        c.addView(export)
    }

    // ------------------------------------------------------------------ novel-item check

    private fun startNovelCheck() {
        val ids = StateStore.state.experiment.heldOutIds()
        if (ids.isEmpty()) {
            Toast.makeText(this, R.string.novel_check_none, Toast.LENGTH_SHORT).show()
            return
        }
        val realId = ids[Random.nextInt(ids.size)]
        val item = StateStore.deckById[realId]
        if (item == null) {
            Toast.makeText(this, R.string.novel_check_none, Toast.LENGTH_SHORT).show()
            return
        }
        renderNovelCheck(item)
    }

    /** Same assessment UI flow as delayed meaning-recall, for a never-studied held-out item. */
    private fun renderNovelCheck(item: DeckItem) {
        container.removeAllViews()
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.novel_check_stage, item.id)))
        container.addView(nexusBody(getString(R.string.novel_check_note)))
        container.addView(nexusHeader(item.front, large = true))

        val backView = nexusHeader(item.back, large = false)
        backView.visibility = View.GONE

        val gradeRow = nexusGradeRow { grade ->
            // Arm logging: held-out ids are stored in the assignments map with arm=CONTROL
            // (core's assignItems), so passing the raw id would file the event under CONTROL
            // and contaminate the CONTROL assessment means. recordAssessment labels the arm
            // HELD_OUT exactly when armOf() returns null, so we log under a "heldout:"-prefixed
            // id; the real item id is preserved after the prefix and repeated in details.
            val loggedId = "heldout:" + item.id
            e.recordAssessment(
                loggedId, Skill.MEANING_RECALL, AssessmentKind.DAY7, grade,
                System.currentTimeMillis(), elapsedSecondsSince(shownAt),
                "held-out novel-item check (MEANING_RECALL), in-app; heldOutItem=" + item.id,
            )
            StateStore.save(this)
            renderNovelCheckDone(grade)
        }
        gradeRow.visibility = View.GONE

        val reveal = nexusButton(getString(R.string.recall_meaning)) {
            it.isEnabled = false
            backView.visibility = View.VISIBLE
            gradeRow.visibility = View.VISIBLE
        }
        container.addView(reveal)
        container.addView(backView)
        container.addFull(gradeRow)
    }

    private fun renderNovelCheckDone(grade: Double) {
        container.removeAllViews()
        container.addView(nexusBody(getString(R.string.novel_check_done, "%.2f".format(grade))))
        container.addView(nexusButton(getString(R.string.back_to_dashboard)) { renderAll() })
    }

    // ------------------------------------------------------------------ export

    private fun shareExport() {
        if (!StateStore.state.learnerConsent) {
            Toast.makeText(this, R.string.export_requires_consent, Toast.LENGTH_LONG).show()
            return
        }
        val json = StateStore.exportJson(this)
        val send = Intent(Intent.ACTION_SEND)
        send.type = "text/plain"
        send.putExtra(Intent.EXTRA_SUBJECT, getString(R.string.export_subject))
        send.putExtra(Intent.EXTRA_TEXT, json)
        startActivity(Intent.createChooser(send, getString(R.string.export_chooser_title)))
    }
}
