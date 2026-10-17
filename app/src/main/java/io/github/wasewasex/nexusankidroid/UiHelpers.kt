package io.github.wasewasex.nexusankidroid

import android.app.Activity
import android.os.SystemClock
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Small shared helpers for the classic-View UI (NO Compose — per architecture requirements).
 * Implemented as Activity extensions so call sites stay terse.
 */

internal fun Activity.nexusDp(x: Int): Int = (x * resources.displayMetrics.density).toInt()

/** Small grey-ish stage/step caption. Note: parameters are named `label` because inside
 *  the `apply` block the TextView's own `text` property would shadow a `text` parameter. */
internal fun Activity.nexusCaption(label: String): TextView = TextView(this).apply {
    text = label
    textSize = 13f
    setPadding(0, nexusDp(10), 0, nexusDp(4))
}

/** Normal body text. */
internal fun Activity.nexusBody(label: String): TextView = TextView(this).apply {
    text = label
    textSize = 16f
    setPadding(0, nexusDp(4), 0, nexusDp(4))
}

/** Headline; [large] for card fronts/backs. */
internal fun Activity.nexusHeader(label: String, large: Boolean): TextView = TextView(this).apply {
    text = label
    textSize = if (large) 28f else 20f
    setPadding(0, nexusDp(8), 0, nexusDp(8))
}

internal fun Activity.nexusButton(label: String, onClick: (View) -> Unit): Button =
    Button(this).apply {
        text = label
        setOnClickListener(onClick)
    }

internal fun Activity.nexusRow(vertical: Boolean = false): LinearLayout =
    LinearLayout(this).apply {
        orientation = if (vertical) LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
    }

/** Margined params; positive [weight] gives an equal-share column (used for button rows). */
internal fun Activity.nexusRowParams(weight: Float = 0f): LinearLayout.LayoutParams {
    val width = if (weight == 0f) LinearLayout.LayoutParams.WRAP_CONTENT else 0
    return LinearLayout.LayoutParams(width, LinearLayout.LayoutParams.WRAP_CONTENT, weight).apply {
        setMargins(nexusDp(2), 0, nexusDp(2), 0)
    }
}

/** Correct / Partial / Wrong self-grade row (1.0 / 0.5 / 0.0). */
internal fun Activity.nexusGradeRow(onGrade: (Double) -> Unit): LinearLayout {
    val row = nexusRow(vertical = false)
    val options = listOf(
        getString(R.string.grade_correct) to 1.0,
        getString(R.string.grade_partial) to 0.5,
        getString(R.string.grade_wrong) to 0.0,
    )
    for ((label, grade) in options) {
        row.addView(nexusButton(label) { onGrade(grade) }, nexusRowParams(weight = 1f))
    }
    return row
}

/** Whole seconds elapsed since [fromMs] (a SystemClock.elapsedRealtime() snapshot). */
internal fun Activity.elapsedSecondsSince(fromMs: Long): Int =
    ((SystemClock.elapsedRealtime() - fromMs) / 1000L).toInt()

/** Adds [view] with MATCH_PARENT width so weighted button rows spread across the screen. */
internal fun LinearLayout.addFull(view: View) {
    addView(
        view,
        LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ),
    )
}
