package io.github.wasewasex.nexusankidroid

import android.os.Bundle
import android.os.SystemClock
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import io.github.wasewasex.nexus.engine.InterventionType
import io.github.wasewasex.nexus.engine.SelectedIntervention
import io.github.wasewasex.nexus.experiment.AssessmentKind
import io.github.wasewasex.nexus.experiment.Arm
import io.github.wasewasex.nexus.experiment.ItemAssignment
import io.github.wasewasex.nexus.fsrs.Fsrs
import io.github.wasewasex.nexus.fsrs.Rating
import io.github.wasewasex.nexus.session.SessionEngine
import io.github.wasewasex.nexus.skills.Skill

/**
 * The core study loop. Every step re-reads [SessionEngine.studyState] and renders the next
 * pending thing in priority order:
 *
 *  1. delayed assessments due (DAY7 before DAY30; three skills per item: meaning recall,
 *     listening, production — each skill is one recordAssessment call),
 *  2. FSRS due/new reviews (the ONLY place [SessionEngine.recordReview] is ever called),
 *  3. the selected NEXUS intervention (recorded with [SessionEngine.recordExercise]),
 *  4. otherwise the completion message ("FSRS protected — X reviews done; enrichment ...").
 *
 * Isolation guarantees honored here: exercises and assessments NEVER call recordReview;
 * state is saved after every record* call; every exercise shows and logs its rationale.
 */
class StudyActivity : AppCompatActivity() {

    private lateinit var container: LinearLayout
    private var tts: TtsHelper? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        StateStore.get(this)
        setContentView(R.layout.activity_study)
        container = findViewById(R.id.study_container)
        tts = TtsHelper(this)
        renderNext()
    }

    override fun onDestroy() {
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }

    private fun engine(): SessionEngine = SessionEngine(StateStore.state)

    // ------------------------------------------------------------------ step selection

    private fun renderNext() {
        val e = engine()
        e.ensureDay(Fsrs.epochDay(System.currentTimeMillis()))
        val ss = e.studyState()
        val intervention = ss.intervention
        container.removeAllViews()
        container.addView(
            nexusCaption(
                getString(
                    R.string.status_fmt,
                    ss.assessmentsDue.size,
                    ss.reviewsDueIds.size + ss.newDueIds.size,
                    ss.budgetRemainingSeconds,
                )
            )
        )
        when {
            ss.assessmentsDue.isNotEmpty() -> renderAssessment(ss.assessmentsDue.first())
            ss.reviewsDueIds.isNotEmpty() -> renderReview(ss.reviewsDueIds.first())
            ss.newDueIds.isNotEmpty() -> renderReview(ss.newDueIds.first())
            intervention != null -> renderIntervention(intervention)
            else -> renderDone()
        }
    }

    // ------------------------------------------------------------------ FSRS review

    private fun renderReview(itemId: String) {
        val e = engine()
        val item = StateStore.deckById[itemId]
        val shownAt = SystemClock.elapsedRealtime()

        container.addView(nexusCaption(getString(R.string.review_stage, e.cardStateName(itemId))))
        container.addView(nexusHeader(item?.front ?: itemId, large = true))

        val backView = nexusHeader(item?.back ?: "", large = false)
        backView.visibility = View.GONE

        val ratingsRow = nexusRow(vertical = false)
        ratingsRow.visibility = View.GONE

        val reveal = nexusButton(getString(R.string.show_answer)) {
            it.visibility = View.GONE
            backView.visibility = View.VISIBLE
            ratingsRow.visibility = View.VISIBLE
        }
        container.addView(reveal)
        container.addView(backView)
        container.addFull(ratingsRow)

        for (rating in Rating.entries) {
            val label = when (rating) {
                Rating.AGAIN -> getString(R.string.rating_again)
                Rating.HARD -> getString(R.string.rating_hard)
                Rating.GOOD -> getString(R.string.rating_good)
                Rating.EASY -> getString(R.string.rating_easy)
            }
            ratingsRow.addView(
                nexusButton(label) {
                    val seconds = elapsedSecondsSince(shownAt)
                    e.recordReview(itemId, rating, System.currentTimeMillis(), seconds)
                    StateStore.save(this@StudyActivity)
                    renderNext()
                },
                nexusRowParams(weight = 1f),
            )
        }
    }

    // ------------------------------------------------------------------ delayed assessments

    private fun assessmentKind(a: ItemAssignment): AssessmentKind {
        val day = StateStore.state.currentDay
        return if (!a.day7Done && a.day7Due in 1..day) AssessmentKind.DAY7 else AssessmentKind.DAY30
    }

    private fun renderAssessment(a: ItemAssignment) {
        val item = StateStore.deckById[a.itemId]
        if (item == null) {
            container.addView(nexusHeader(getString(R.string.assessment_missing, a.itemId), large = false))
            container.addView(nexusButton(getString(R.string.back_home)) { finish() })
            return
        }
        val kind = assessmentKind(a)
        container.addView(nexusCaption(getString(R.string.assessment_stage, kind.name, a.itemId)))
        renderAssessmentMeaning(item, kind)
    }

    /** Meaning recall: front shown, reveal back, self-grade 1.0 / 0.5 / 0.0. */
    private fun renderAssessmentMeaning(item: DeckItem, kind: AssessmentKind) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_meaning_recall)))
        container.addView(nexusHeader(item.front, large = true))

        val backView = nexusHeader(item.back, large = false)
        backView.visibility = View.GONE

        val gradeRow = nexusGradeRow { grade ->
            e.recordAssessment(
                item.id, Skill.MEANING_RECALL, kind, grade,
                System.currentTimeMillis(), elapsedSecondsSince(shownAt), ASSESSMENT_DETAILS,
            )
            StateStore.save(this@StudyActivity)
            renderAssessmentListening(item, kind)
        }
        gradeRow.visibility = View.GONE

        val reveal = nexusButton(getString(R.string.recall_meaning)) {
            it.visibility = View.GONE
            backView.visibility = View.VISIBLE
            gradeRow.visibility = View.VISIBLE
        }
        container.addView(reveal)
        container.addView(backView)
        container.addFull(gradeRow)
    }

    /**
     * Listening: sentence spoken at 1.15x (the documented "unfamiliar audio" proxy); the
     * transcript stays HIDDEN until after the attempt; outcome 1/0.
     */
    private fun renderAssessmentListening(item: DeckItem, kind: AssessmentKind) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_listening)))
        container.addView(nexusBody(getString(R.string.listening_hidden_note)))

        val play = nexusButton(getString(R.string.play_sentence)) {
            tts?.speak(item.listeningText, TtsHelper.ASSESSMENT_RATE)
        }
        container.addView(play)
        // Auto-play once on entry. TTS may still be initializing on the very first screen,
        // in which case the Play sentence button covers the attempt.
        tts?.speak(item.listeningText, TtsHelper.ASSESSMENT_RATE)

        val optionsRow = nexusRow(vertical = true)
        val feedback = nexusRow(vertical = true)
        feedback.visibility = View.GONE
        val continueBtn = nexusButton(getString(R.string.continue_label)) {
            renderAssessmentProduction(item, kind)
        }
        continueBtn.visibility = View.GONE

        item.listeningOptions.forEachIndexed { idx, option ->
            optionsRow.addView(
                nexusButton(option) {
                    val outcome = if (idx == item.listeningAnswer) 1.0 else 0.0
                    e.recordAssessment(
                        item.id, Skill.LISTENING, kind, outcome,
                        System.currentTimeMillis(), elapsedSecondsSince(shownAt), ASSESSMENT_DETAILS,
                    )
                    StateStore.save(this@StudyActivity)
                    optionsRow.visibility = View.GONE
                    play.visibility = View.GONE
                    feedback.addView(nexusBody(getString(R.string.transcript_fmt, item.listeningText)))
                    feedback.addView(nexusBody(getString(R.string.correct_answer_fmt, item.listeningCorrect())))
                    feedback.visibility = View.VISIBLE
                    continueBtn.visibility = View.VISIBLE
                }
            )
        }
        container.addView(optionsRow)
        container.addView(feedback)
        container.addView(continueBtn)
    }

    /** Production: type an answer BEFORE the model is revealed, then self-grade 1.0/0.5/0.0. */
    private fun renderAssessmentProduction(item: DeckItem, kind: AssessmentKind) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_production)))
        container.addView(nexusBody(getString(R.string.production_first_note)))
        container.addView(nexusHeader(item.productionPrompt, large = false))

        val input = EditText(this)
        input.hint = getString(R.string.production_hint)
        input.minLines = 2
        container.addView(input)

        val modelView = nexusHeader(item.productionModel, large = false)
        modelView.visibility = View.GONE

        val gradeRow = nexusGradeRow { grade ->
            e.recordAssessment(
                item.id, Skill.PRODUCTION, kind, grade,
                System.currentTimeMillis(), elapsedSecondsSince(shownAt), ASSESSMENT_DETAILS,
            )
            StateStore.save(this@StudyActivity)
            renderNext()
        }
        gradeRow.visibility = View.GONE

        val reveal = nexusButton(getString(R.string.reveal_model)) {
            if (input.text.isNullOrBlank()) {
                Toast.makeText(this@StudyActivity, R.string.type_first_toast, Toast.LENGTH_SHORT).show()
                return@nexusButton
            }
            it.isEnabled = false
            input.isEnabled = false
            modelView.visibility = View.VISIBLE
            gradeRow.visibility = View.VISIBLE
        }
        container.addView(reveal)
        container.addView(modelView)
        container.addFull(gradeRow)
    }

    // ------------------------------------------------------------------ NEXUS interventions

    private fun exerciseDetails(iv: SelectedIntervention, extra: String? = null): String =
        if (extra == null) "why=" + iv.rationale
        else "why=" + iv.rationale + "; " + extra

    private fun renderIntervention(iv: SelectedIntervention) {
        container.addView(nexusCaption(getString(R.string.intervention_stage, iv.type.name)))
        // Rationale FIRST: the reason for this exercise is always shown to the learner.
        container.addView(nexusBody(getString(R.string.why_this_exercise, iv.rationale)))
        val item = StateStore.deckById[iv.itemId]
        if (item == null) {
            container.addView(nexusHeader(getString(R.string.assessment_missing, iv.itemId), large = false))
            container.addView(nexusButton(getString(R.string.back_home)) { finish() })
            return
        }
        when (iv.type) {
            InterventionType.LISTENING_INPUT -> renderListeningInput(iv, item)
            InterventionType.PRODUCTION_FIRST -> renderProductionFirst(iv, item)
            InterventionType.GRAMMAR_REPAIR -> renderGrammarRepair(iv, item)
            InterventionType.TRANSFER_TASK -> renderTransferTask(iv, item)
            InterventionType.PREDICTION_ERROR_REPAIR -> renderPredictionErrorRepair(iv, item)
        }
    }

    /** Varied audio at natural rate, transcript hidden until after the attempt; outcome 1/0. */
    private fun renderListeningInput(iv: SelectedIntervention, item: DeckItem) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_listening)))
        container.addView(nexusBody(getString(R.string.listening_hidden_note)))

        val play = nexusButton(getString(R.string.play_sentence)) {
            tts?.speak(item.listeningText, TtsHelper.NATURAL_RATE)
        }
        container.addView(play)
        tts?.speak(item.listeningText, TtsHelper.NATURAL_RATE)

        val optionsRow = nexusRow(vertical = true)
        val feedback = nexusRow(vertical = true)
        feedback.visibility = View.GONE
        val continueBtn = nexusButton(getString(R.string.continue_label)) { renderNext() }
        continueBtn.visibility = View.GONE

        item.listeningOptions.forEachIndexed { idx, option ->
            optionsRow.addView(
                nexusButton(option) {
                    val outcome = if (idx == item.listeningAnswer) 1.0 else 0.0
                    e.recordExercise(
                        iv.type, iv.itemId, outcome,
                        System.currentTimeMillis(), elapsedSecondsSince(shownAt),
                        exerciseDetails(iv),
                    )
                    StateStore.save(this@StudyActivity)
                    optionsRow.visibility = View.GONE
                    play.visibility = View.GONE
                    feedback.addView(nexusBody(getString(R.string.transcript_fmt, item.listeningText)))
                    feedback.addView(nexusBody(getString(R.string.correct_answer_fmt, item.listeningCorrect())))
                    feedback.visibility = View.VISIBLE
                    continueBtn.visibility = View.VISIBLE
                }
            )
        }
        container.addView(optionsRow)
        container.addView(feedback)
        container.addView(continueBtn)
    }

    /** Produce before seeing the model answer; self-grade 1.0/0.5/0.0. */
    private fun renderProductionFirst(iv: SelectedIntervention, item: DeckItem) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_production)))
        container.addView(nexusBody(getString(R.string.production_first_note)))
        container.addView(nexusHeader(item.productionPrompt, large = false))

        val input = EditText(this)
        input.hint = getString(R.string.production_hint)
        input.minLines = 2
        container.addView(input)

        val modelView = nexusHeader(item.productionModel, large = false)
        modelView.visibility = View.GONE

        val gradeRow = nexusGradeRow { grade ->
            e.recordExercise(
                iv.type, iv.itemId, grade,
                System.currentTimeMillis(), elapsedSecondsSince(shownAt),
                exerciseDetails(iv),
            )
            StateStore.save(this@StudyActivity)
            renderNext()
        }
        gradeRow.visibility = View.GONE

        val reveal = nexusButton(getString(R.string.reveal_model)) {
            if (input.text.isNullOrBlank()) {
                Toast.makeText(this@StudyActivity, R.string.type_first_toast, Toast.LENGTH_SHORT).show()
                return@nexusButton
            }
            it.isEnabled = false
            input.isEnabled = false
            modelView.visibility = View.VISIBLE
            gradeRow.visibility = View.VISIBLE
        }
        container.addView(reveal)
        container.addView(modelView)
        container.addFull(gradeRow)
    }

    /** Contrastive correction: pick the correct version, then see the explanation; outcome 1/0. */
    private fun renderGrammarRepair(iv: SelectedIntervention, item: DeckItem) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_grammar)))
        container.addView(nexusBody(getString(R.string.grammar_repair_note)))
        container.addView(nexusHeader(item.grammarSentence, large = false))

        val optionsRow = nexusRow(vertical = true)
        val feedback = nexusRow(vertical = true)
        feedback.visibility = View.GONE
        val continueBtn = nexusButton(getString(R.string.continue_label)) { renderNext() }
        continueBtn.visibility = View.GONE

        item.grammarOptions.forEachIndexed { idx, option ->
            optionsRow.addView(
                nexusButton(option) {
                    val outcome = if (idx == item.grammarAnswer) 1.0 else 0.0
                    e.recordExercise(
                        iv.type, iv.itemId, outcome,
                        System.currentTimeMillis(), elapsedSecondsSince(shownAt),
                        exerciseDetails(iv),
                    )
                    StateStore.save(this@StudyActivity)
                    optionsRow.visibility = View.GONE
                    feedback.addView(nexusBody(getString(R.string.correct_answer_fmt, item.grammarCorrect())))
                    feedback.addView(nexusBody(item.grammarExplanation))
                    feedback.visibility = View.VISIBLE
                    continueBtn.visibility = View.VISIBLE
                }
            )
        }
        container.addView(optionsRow)
        container.addView(feedback)
        container.addView(continueBtn)
    }

    /** Known expression in an unfamiliar context; after the choice, outcome 1/0 + note. */
    private fun renderTransferTask(iv: SelectedIntervention, item: DeckItem) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        container.addView(nexusCaption(getString(R.string.skill_transfer)))
        container.addView(nexusHeader(item.transferContext, large = false))

        val optionsRow = nexusRow(vertical = true)
        val feedback = nexusRow(vertical = true)
        feedback.visibility = View.GONE
        val continueBtn = nexusButton(getString(R.string.continue_label)) { renderNext() }
        continueBtn.visibility = View.GONE

        item.transferOptions.forEachIndexed { idx, option ->
            optionsRow.addView(
                nexusButton(option) {
                    val outcome = if (idx == item.transferAnswer) 1.0 else 0.0
                    e.recordExercise(
                        iv.type, iv.itemId, outcome,
                        System.currentTimeMillis(), elapsedSecondsSince(shownAt),
                        exerciseDetails(iv),
                    )
                    StateStore.save(this@StudyActivity)
                    optionsRow.visibility = View.GONE
                    feedback.addView(nexusBody(getString(R.string.correct_answer_fmt, item.transferCorrect())))
                    feedback.addView(nexusBody(getString(R.string.transfer_note)))
                    feedback.visibility = View.VISIBLE
                    continueBtn.visibility = View.VISIBLE
                }
            )
        }
        container.addView(optionsRow)
        container.addView(feedback)
        container.addView(continueBtn)
    }

    /**
     * Confident-mistake repair: silent recall -> confidence self-report -> reveal -> verify.
     * outcome = correct ? 1 : 0. If the learner was sure AND wrong, corrective feedback is
     * shown and ONE independent retry (same exercise type, DIFFERENT treatment item) runs
     * immediately; the retry outcome is appended to the same details string as "retry=...".
     */
    private fun renderPredictionErrorRepair(iv: SelectedIntervention, item: DeckItem) {
        val e = engine()
        val shownAt = SystemClock.elapsedRealtime()
        var wasSure = false
        var correctMain = false
        var confidenceText = "unsure"
        var retryOutcome: Double? = null
        var retryItemId: String? = null

        container.addView(nexusCaption(getString(R.string.skill_meaning_recall)))
        container.addView(nexusBody(getString(R.string.per_note)))
        container.addView(nexusHeader(item.front, large = true))

        // Views are declared (and hidden) up front; listeners are attached afterwards so
        // every referenced view/local function is already initialized.
        val backView = nexusHeader(item.back, large = false)
        backView.visibility = View.GONE

        val retryNoteView = nexusBody(getString(R.string.retry_note))
        retryNoteView.visibility = View.GONE
        val retryFrontView = nexusHeader("", large = true)
        retryFrontView.visibility = View.GONE
        val retryBackView = nexusHeader("", large = false)
        retryBackView.visibility = View.GONE
        val retryConfidenceRow = nexusRow(vertical = false)
        retryConfidenceRow.visibility = View.GONE
        val retryVerifyRow = nexusRow(vertical = false)
        retryVerifyRow.visibility = View.GONE
        val verifyRow = nexusRow(vertical = false)
        verifyRow.visibility = View.GONE
        val confidenceRow = nexusRow(vertical = false)

        fun completeExercise() {
            val details = buildString {
                append("why=").append(iv.rationale)
                append("; confidence=").append(confidenceText)
                val rOut = retryOutcome
                val rItem = retryItemId
                if (rOut != null && rItem != null) {
                    append("; retry=").append("%.1f".format(rOut))
                        .append(" (item ").append(rItem).append(")")
                }
            }
            val outcome = if (correctMain) 1.0 else 0.0
            e.recordExercise(
                iv.type, iv.itemId, outcome,
                System.currentTimeMillis(), elapsedSecondsSince(shownAt), details,
            )
            StateStore.save(this@StudyActivity)
            renderNext()
        }

        fun startRetry() {
            val treatmentIds = StateStore.state.experiment.studyableIds(Arm.TREATMENT)
            val otherId = treatmentIds.firstOrNull { it != iv.itemId } ?: iv.itemId
            val retryItem = StateStore.deckById[otherId]
            if (retryItem == null) {
                completeExercise()
                return
            }
            retryItemId = retryItem.id
            retryFrontView.text = retryItem.front
            retryBackView.text = retryItem.back
            retryFrontView.visibility = View.VISIBLE
            retryConfidenceRow.visibility = View.VISIBLE
        }

        // Independent-retry confidence buttons (phase R1).
        val retrySureBtn = nexusButton(getString(R.string.i_was_sure)) {
            it.isEnabled = false
            retryBackView.visibility = View.VISIBLE
            retryVerifyRow.visibility = View.VISIBLE
        }
        val retryUnsureBtn = nexusButton(getString(R.string.i_was_unsure)) {
            it.isEnabled = false
            retryBackView.visibility = View.VISIBLE
            retryVerifyRow.visibility = View.VISIBLE
        }
        retryConfidenceRow.addView(retrySureBtn, nexusRowParams(weight = 1f))
        retryConfidenceRow.addView(retryUnsureBtn, nexusRowParams(weight = 1f))

        // Independent-retry verify buttons (phase R2) -> single recordExercise with retry=...
        val retryRightBtn = nexusButton(getString(R.string.recalled_right)) {
            retryOutcome = 1.0
            retryVerifyRow.visibility = View.GONE
            completeExercise()
        }
        val retryWrongBtn = nexusButton(getString(R.string.recalled_wrong)) {
            retryOutcome = 0.0
            retryVerifyRow.visibility = View.GONE
            completeExercise()
        }
        retryVerifyRow.addView(retryRightBtn, nexusRowParams(weight = 1f))
        retryVerifyRow.addView(retryWrongBtn, nexusRowParams(weight = 1f))

        // Main verify buttons (phase 2): self-check the silent recall against the back.
        val rightBtn = nexusButton(getString(R.string.recalled_right)) {
            correctMain = true
            it.isEnabled = false
            verifyRow.visibility = View.GONE
            if (wasSure) {
                container.addView(nexusBody(getString(R.string.confident_mistake, item.back)))
                startRetry()
            } else {
                completeExercise()
            }
        }
        val wrongBtn = nexusButton(getString(R.string.recalled_wrong)) {
            correctMain = false
            it.isEnabled = false
            verifyRow.visibility = View.GONE
            if (wasSure) {
                container.addView(nexusBody(getString(R.string.confident_mistake, item.back)))
                startRetry()
            } else {
                completeExercise()
            }
        }
        verifyRow.addView(rightBtn, nexusRowParams(weight = 1f))
        verifyRow.addView(wrongBtn, nexusRowParams(weight = 1f))

        // Main confidence buttons (phase 1).
        val sureBtn = nexusButton(getString(R.string.i_was_sure)) {
            wasSure = true
            confidenceText = "sure"
            it.isEnabled = false
            backView.visibility = View.VISIBLE
            verifyRow.visibility = View.VISIBLE
        }
        val unsureBtn = nexusButton(getString(R.string.i_was_unsure)) {
            wasSure = false
            confidenceText = "unsure"
            it.isEnabled = false
            backView.visibility = View.VISIBLE
            verifyRow.visibility = View.VISIBLE
        }
        confidenceRow.addView(sureBtn, nexusRowParams(weight = 1f))
        confidenceRow.addView(unsureBtn, nexusRowParams(weight = 1f))

        container.addView(backView)
        container.addFull(confidenceRow)
        container.addFull(verifyRow)
        container.addView(retryNoteView)
        container.addView(retryFrontView)
        container.addView(retryBackView)
        container.addFull(retryConfidenceRow)
        container.addFull(retryVerifyRow)
    }

    // ------------------------------------------------------------------ completion

    private fun renderDone() {
        val st = StateStore.state
        container.addView(nexusCaption(getString(R.string.all_caught_up)))
        container.addView(
            nexusHeader(
                getString(
                    R.string.done_msg,
                    st.reviewsDoneToday,
                    st.budget.enrichmentSecondsToday,
                    st.budget.allowedSeconds(),
                ),
                large = true,
            )
        )
        container.addView(nexusButton(getString(R.string.back_home)) { finish() })
    }

    companion object {
        /** Standard details tag for all delayed assessments logged from this app. */
        private const val ASSESSMENT_DETAILS = "delayed assessment in-app"
    }
}
