package io.github.wasewasex.nexus.triad

/**
 * TRIAD feature flags — release-policy constants, NOT user-facing settings.
 *
 * Evidence state (benchmarks/v17_evidence_benchmark/outputs/verdicts_real.json — REAL learner
 * data, Duolingo HLR public release, user-level splits, alpha selected on calibration users
 * only): the TRIAD-native contextual correction did NOT demonstrate a held-out predictive gain
 * beyond fitted FSRS-5 (test soft logloss 0.32538 vs baseline 0.32521 at the calibration-chosen
 * alpha*=0.75; binary AUC +0.002, MAE -0.001). Per the pre-registered one-shot gate, alpha
 * stays 0 and TRIAD interval adjustments stay OFF. Full rationale: docs/SESSION_CONTROL_AUDIT.md.
 */
object TriadFeatureFlags {
    /**
     * HARD-DISABLED in this release. There is no runtime, persisted, or build-variant override:
     * enabling TRIAD interval adjustments is a source-code change that requires BOTH
     *  (1) a new out-of-sample validation PASS on the declared gate (deterministic held-out
     *      split, >= 0.005 logloss improvement, >= 40 events), AND
     *  (2) an explicit evidence review recorded in docs/SESSION_CONTROL_AUDIT.md.
     */
    const val TRIAD_INTERVAL_ADJUSTMENTS: Boolean = false

    /**
     * Observability-only channel: TRIAD may READ FSRS state and append audit receipts.
     * It never writes FSRS scheduling state under any flag combination.
     */
    const val TRIAD_OBSERVABILITY: Boolean = true
}
