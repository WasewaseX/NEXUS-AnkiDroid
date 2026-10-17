package io.github.wasewasex.nexusankidroid

import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import io.github.wasewasex.nexus.experiment.Arm
import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.session.SessionEngine

/**
 * Home screen: deck/arm stats, today's workload, the pre-registered enrichment budget
 * selector, the privacy consent switch and the three entry points (study, dashboard, export).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var deckStats: LinearLayout
    private lateinit var todayStats: LinearLayout
    private lateinit var notice: TextView
    private lateinit var budgetGroup: RadioGroup
    private lateinit var consentCheck: CheckBox
    private lateinit var exportButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        StateStore.get(this)
        engine().ensureDay(Fsrs.epochDay(System.currentTimeMillis()))
        StateStore.save(this) // persist possible day rollover / once-per-day skip audit
        setContentView(R.layout.activity_main)

        deckStats = findViewById(R.id.container_deck_stats)
        todayStats = findViewById(R.id.container_today)
        notice = findViewById(R.id.text_notice)
        budgetGroup = findViewById(R.id.budget_group)
        consentCheck = findViewById(R.id.consent_check)
        exportButton = findViewById(R.id.button_export)

        setupBudget()
        setupConsent()
        setupButtons()
        refreshStats()
    }

    override fun onResume() {
        super.onResume()
        if (::deckStats.isInitialized) refreshStats()
    }

    private fun engine(): SessionEngine = SessionEngine(StateStore.state)

    private fun refreshStats() {
        val e = engine()
        e.ensureDay(Fsrs.epochDay(System.currentTimeMillis()))
        val st = StateStore.state

        deckStats.removeAllViews()
        addStat(
            deckStats,
            getString(
                R.string.deck_stats_fmt,
                st.cards.size,
                st.experiment.studyableIds(Arm.CONTROL).size,
                st.experiment.studyableIds(Arm.TREATMENT).size,
                st.experiment.heldOutIds().size,
            ),
        )

        todayStats.removeAllViews()
        val dueNow = e.dueReviewIds().size + e.newDueIds().size
        addStat(
            todayStats,
            getString(R.string.today_fmt, dueNow, e.overdueCount(), st.reviewsDoneToday),
        )

        val nAssess = e.studyState().assessmentsDue.size
        if (nAssess > 0) {
            notice.text = getString(R.string.notice_assessments_due, nAssess)
            notice.setTypeface(null, Typeface.BOLD)
            notice.visibility = View.VISIBLE
        } else {
            notice.visibility = View.GONE
        }
    }

    private fun addStat(parent: LinearLayout, text: String) {
        val tv = TextView(this)
        tv.text = text
        tv.textSize = 15f
        tv.setPadding(0, nexusDp(2), 0, nexusDp(2))
        parent.addView(tv)
    }

    /**
     * The four pre-registered budget options. The current value is checked BEFORE the
     * listener is attached, so programmatic init never writes a spurious BUDGET_CHANGED.
     */
    private fun setupBudget() {
        when (StateStore.state.budget.budgetPct) {
            0 -> budgetGroup.check(R.id.rb_budget_0)
            10 -> budgetGroup.check(R.id.rb_budget_10)
            30 -> budgetGroup.check(R.id.rb_budget_30)
            else -> budgetGroup.check(R.id.rb_budget_20)
        }
        budgetGroup.setOnCheckedChangeListener { _, checkedId ->
            val pct = when (checkedId) {
                R.id.rb_budget_0 -> 0
                R.id.rb_budget_10 -> 10
                R.id.rb_budget_30 -> 30
                else -> 20
            }
            val old = StateStore.state.budget.budgetPct
            if (pct != old) {
                StateStore.state.budget.changeBudget(pct)
                StateStore.state.audit.add(
                    "BUDGET_CHANGED",
                    "from" to old.toString(),
                    "to" to pct.toString(),
                )
                StateStore.save(this)
            }
        }
    }

    private fun setupConsent() {
        consentCheck.isChecked = StateStore.state.learnerConsent
        exportButton.isEnabled = StateStore.state.learnerConsent
        consentCheck.setOnCheckedChangeListener { _, checked ->
            StateStore.state.learnerConsent = checked
            StateStore.state.audit.add(
                if (checked) "CONSENT_GRANTED" else "CONSENT_WITHDRAWN",
                "exportEnabled" to checked.toString(),
            )
            StateStore.save(this)
            exportButton.isEnabled = checked
        }
    }

    private fun setupButtons() {
        findViewById<Button>(R.id.button_study).setOnClickListener {
            startActivity(Intent(this, StudyActivity::class.java))
        }
        findViewById<Button>(R.id.button_dashboard).setOnClickListener {
            startActivity(Intent(this, DashboardActivity::class.java))
        }
        exportButton.setOnClickListener { shareExport() }
    }

    /** Local-only privacy: export is a user-initiated share of the JSON text. */
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
