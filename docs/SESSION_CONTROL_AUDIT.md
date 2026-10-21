# Session-Control Audit (audit-first refactor, TRIAD feature-flagged)

**Status:** audit complete; feature-flagged integration surface implemented and tested.
**Release policy:** `TriadFeatureFlags.TRIAD_INTERVAL_ADJUSTMENTS = false` (hard-off, no override).
**Evidence mandate:** TRIAD interval adjustments stay disabled until a new out-of-sample
validation PASS is recorded here.

---

## 1. Why this audit exists

The governing directive is evidence-gated: build toward a TRIAD-native memory model only when
evidence shows which aspect of human recall the FSRS-centered approach fails to capture, and
compare any candidate against FSRS on real, held-out outcomes. The v1.7 real-data alpha gate
(REAL learner data: Duolingo HLR public release, `settles.acl16.learning_traces.13m.csv.gz`,
doi:10.7910/DVN/N8XJME, md5-verified; user-level splits 1456 train / 479 calibration / 465
test; alpha selected on calibration users only; test users touched exactly once with frozen
artifacts) did **not** show a held-out predictive gain beyond FSRS-5:

| model (test users, n_binary = 7,732) | soft logloss | Brier (soft) | MAE | binary logloss | binary AUC |
|---|---|---|---|---|---|
| FSRS-5, fitted on train users (m0) | 0.32521 | 0.069802 | 0.18298 | 0.33631 | 0.5446 |
| FSRS-5 + TRIAD context, alpha*=0.75 (m1) | 0.32538 | 0.069882 | 0.18183 | 0.33684 | 0.5466 |

The calibration split showed a small optimum at alpha = 0.75 (cal logloss 0.33575 vs 0.33692
at alpha = 0), but it did not transfer to a test-split gain. Per the pre-registered one-shot
gate, **alpha stays 0**. Consequently the app must structurally guarantee that TRIAD cannot
adjust FSRS intervals. This document records the audit that establishes that guarantee and the
feature-flagged surface that enforces it.

Caveats carried from the gate itself: the dataset is English-learner practice on the Duolingo
app (2012–2013), aggregated per-lesson outcomes (`p_recall`), not per-exercise binary reviews;
it is predictive-accuracy evidence, not a scheduling A/B trial.

## 2. Scheduling-authority audit (line-referenced)

Files audited: `core/src/main/kotlin/io/github/wasewasex/nexus/{fsrs,session,budget,engine,
experiment,audit,skills,triad}`.

| # | Path | Finding |
|---|---|---|
| A1 | `fsrs/Fsrs.kt` | `Fsrs.review` is the ONLY entry point that mutates scheduling state (stability, difficulty, due, state). `intervalFor` derives intervals purely from FSRS-5 parameters (FACTOR = 19/81, desired retention). No external code writes these fields. |
| A2 | `session/SessionEngine.kt` | `recordReview` is the only caller of `Fsrs.review` (learner-initiated reviews only). `recordExercise` and `recordAssessment` never touch FSRS — the isolation guarantee tested by `IsolationTest`. |
| A3 | `session/SessionEngine.kt` (`nextIntervention`) | Enrichment selection is gated (reviews protected, backlog threshold, attendance gap, budget floor) and every skip is audited once per day with a reason. |
| A4 | `budget/Budget.kt` | `canEnrich` enforces reviews-first: zero enrichment while any review is due or the backlog exceeds the threshold. Enrichment never grows its own allowance (review-time base). |
| A5 | `experiment/Experiment.kt` | Counterbalanced arms + 10% held-out items; assessments are verification events, never scheduling events. |
| A6 | `audit/AuditLog.kt` | Append-only; nothing deletes entries; exports include the full log. |
| A7 | v1.8 code delta | The v1.7/v1.8 commits added ONLY `benchmarks/` and `docs/` — the TRIAD engine existed exclusively as simulation code (`sim18/triad.py`); the app contained **no** TRIAD interval pathway to disable. The refactor therefore ADDS the inert, flag-gated surface rather than removing a live one. |

**Audit conclusion:** FSRS-5 is the authoritative scheduler on every path. The only missing
piece was a defined, audited integration point where a future TRIAD-native model could ever
touch intervals — plus a hard guarantee that it cannot do so today.

## 3. The feature-flagged surface (what was added)

- `triad/TriadFeatureFlags.kt` — release-policy constants. `TRIAD_INTERVAL_ADJUSTMENTS = false`
  is a compile-time constant: no runtime, persisted, or build-variant override exists. Enabling
  it is a source change that requires both a new out-of-sample gate PASS and an evidence review
  recorded here. `TRIAD_OBSERVABILITY = true` allows read-only audit receipts.
- `triad/TriadGate.kt` — pure, stateless port of the v1.8 contextual-delta reference
  (`sim18/triad.py`): weights (acc 2.0, lat 0.8, workload 0.4, fatigue 0.5, absence 0.3),
  references (acc 0.85, workload 30, absence horizon 7 d), ±1.5-logit clip, the user's formula
  `P_hybrid = sigmoid(logit(P_eff) + alpha*delta)` with alpha = 0 identity, and a proposal
  function that refuses unless the flag AND a nonzero alpha AND a |delta| above the 0.05-logit
  action floor are all present. The candidate mapping `factor = exp(alpha*delta)` is labeled
  UNVALIDATED and has never been applied to any learner state.
- `session/SessionEngine.kt` — exactly one TRIAD consultation point, strictly AFTER FSRS has
  produced its authoritative result in `recordReview`. In this release it appends a
  `TRIAD_INTERVAL_GATE` audit receipt (decision `disabled_by_flag`, alpha, FSRS scheduled days)
  and mutates nothing. A future evidenced release that applies an adjustment would additionally
  emit `TRIAD_INTERVAL_ADJUSTED` — the absence of which is the per-review compliance proof.
- `AppState.triadAlpha` — evidence-mandated 0.0, persisted for forward compatibility; covered
  by the state round-trip test.

## 4. Test evidence (mechanics, never learning outcomes)

`TriadGateTest` (all passing): flag is hard-off; decision order is flag → alpha → enablement;
delta math matches the reference port (9 hand-checked cases incl. both clips); hybrid identity
at alpha = 0; proposal refusals under all partial enablements; hypothetical-enablement candidate
is directionally sane and explicitly unvalidated; **byte-identical FSRS scheduling** — a 24-item,
72-review, 4-rating mixed script through the full `SessionEngine` (with the gate live in
observability mode) reproduces an independent raw-`Fsrs` replay exactly on all 7 scheduling
fields; audit receipts written per review and zero `TRIAD_INTERVAL_ADJUSTED` entries;
`triadAlpha` survives the JSON round trip.

## 5. Activation protocol (for a future evidenced release)

1. New out-of-sample validation PASS on the declared gate: deterministic held-out split,
   ≥ 0.005 logloss improvement over FSRS-5, ≥ 40 events, test users never used for fitting or
   selection. Public datasets and pre-registered simulations are acceptable validation sources;
   claims must still be labeled as predictive-accuracy evidence, not scheduling A/B results.
2. Record the result and the decision in this file with a date and artifact path.
3. Flip `TRIAD_INTERVAL_ADJUSTMENTS` to `true` AND set a nonzero `triadAlpha` in the same
   evidenced release; both changes in one commit referencing step 2.
4. Keep the `TRIAD_INTERVAL_ADJUSTED` audit emission: from activation onward, every applied
   adjustment must be individually auditable.
