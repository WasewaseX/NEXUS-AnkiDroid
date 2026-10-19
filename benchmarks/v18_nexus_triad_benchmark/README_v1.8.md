# NEXUS-TRIAD v1.8 — benchmark (8 requested arms)

**Simulation study. Every number below is a property of the declared simulation, NOT a measurement of real learners.**

NEXUS-TRIAD v1.8 = the four-component engine per the spec:

1. **Cold-start intelligence** — shared empirical-Bayes Beta(1,1) priors per skill; `n/(n+k)` shrinkage; the shared prior dominates early, individual evidence takes over as history accumulates.
2. **FSRS memory engine (authoritative)** — the FSRS wrapper is never modified by TRIAD; intervals, stability, difficulty all come from FSRS exactly as in every other arm. TRIAD only READS `predicted_retrievability`.
3. **Contextual recall predictor** — observables only: recent accuracy EMA, per-kind latency slowdown, workload, session-scope fatigue proxies, absence history.
   `delta = w_acc*(recent_acc-0.85) - w_lat*max(0,slowdown-1) - w_wl*max(0,due/30-0.5) - w_fat*fatigue - w_abs*min(gap/7,1)`, clipped to ±1.5 logits.
4. **NEXUS session controller** — v1.6 frozen mechanism (dishabituation interleave, due-core protection) + cold-start-aware ordering + fatigue-gated intake (planned stop) + accuracy-conditioned goal extension.

**Hybrid prediction (the user's formula, verbatim):** `P_hybrid = sigmoid(logit(P_eff) + α·Δ_context)` with **α = 0 until out-of-sample validation** succeeds (deterministic 30% held-out split, ≥ 0.005 logloss improvement, ≥ 40 events).

## Hard constraints honored

- Retention tolerance ≤ 0.02 (preregistered floor) — see T1/T3 below.
- α = 0 until validated (the gate is one-shot and conservative; rejected α stays 0 forever).
- Fatigue is SESSION-SCOPE ONLY: recomputed fresh each session, never persisted, never touches FSRS stability.
- No silent due-review skipping in ANY arm; TRIAD's fatigue gate acts only on OPTIONAL new-card intake.
- No circular tuning: truth constants inherited from v1.5/v1.6 unchanged; TRIAD constants are a-priori; only declared policy cells were selected on the calibration block.

## The 8 requested arms

| # | Requested | Implementation |
|---|-----------|----------------|
| 1 | FSRS meaning-only | `fsrs_recall_only` (status-quo anchor) |
| 2 | FSRS multi-type | `fsrs_multitype` |
| 3 | NEXUS-SCOPE 2.0 | `nexus_scope20` (due-first + 20% intervention reserve, deficit×confidence targeting, evidence ≥ 4 gate) |
| 4 | NEXUS-MIX 2.0 | `nexus_mix2` (v1.6 frozen policy p075_prot, unchanged) |
| 5 | NEXUS-TRIAD full | `nexus_triad` (v1.8) |
| 6 | FSRS | **duplicate of (2) in this framework** — reported once, never fabricated into a difference |
| 7 | RWKV-instant | `rwkv_instant` (v1.4 RWKVInstant scheduler, naive session policy) |
| 8 | SM-20 | `sm20` (v1.4 SM20 scheduler: SM-2 with 20-level ease grid, naive session policy) |

## Design (preregistered in config18.json BEFORE any run)

- Seeds: calibration block 20260116 (cell selection ONLY), confirmation block 20261101 (frozen cell `triad_b`, run ONCE — the only evidence below).
- Population: 3 reps × 4 archetypes × 4 learners = 48 learner-careers per arm, 28-day horizon, probes at days 7/14/21/28.
- Analysis: paired CRN diffs per (rep, learner_id); 95% cluster bootstrap (cluster = learner_id, n=2000).
- Policy grid (calibration only): triad_a goal 0.75 / triad_b goal 0.85 / triad_c no intake gate / triad_d α gating off. Frozen by the v1.6 selection rule → **triad_b**.

## Confirmation results (28-day careers, 7 distinct arms)

| arm | DPI/hour | ret28 | session min | gap d | quit rate | planned stop | due completion |
|---|---|---|---|---|---|---|---|
| fsrs_recall_only | 0.2495 | 0.5420 | 10.39 | 2.11 | 0.9866 | 0.000 | 0.8196 |
| **nexus_triad (v1.8)** | **0.1426** | **0.5872** | 15.09 | 2.04 | **0.2615** | 0.583 | 0.8533 |
| nexus_mix2 | 0.1424 | 0.5818 | 15.50 | 2.02 | 0.2813 | 0.574 | 0.8604 |
| nexus_scope20 | 0.1344 | 0.5846 | 17.88 | 2.26 | 0.3820 | 0.000 | 0.8947 |
| sm20 | 0.1281 | 0.6129 | 17.93 | 2.22 | 0.3614 | 0.000 | 0.8206 |
| fsrs_multitype | 0.1280 | 0.5819 | 17.81 | 2.13 | 0.3762 | 0.000 | 0.8313 |
| rwkv_instant | 0.1224 | 0.4985 | 17.90 | 2.16 | 0.3844 | 0.000 | 0.7734 |

**Replication audit:** `fsrs_multitype` reproduces the v1.5/v1.6 confirmation numbers exactly (DPI 0.1280, ret28 0.5819, sessions 17.81, quit 0.3762; mix2 vs multitype ret diff −0.0001 as in v1.6). Any drift would have been a bug, not noise.

## Verdicts (confirmation block only)

- **T1 learning (PRIMARY): PASS** — TRIAD DPI/hour **+11.41%** vs FSRS multi-type, 95% CI **[+4.12%, +14.54%]** (excludes 0; point ≥ +5% floor), ret28 diff **+0.0054** (CI [−0.0131, +0.0253]) — inside the ±0.02 tolerance and POSITIVE.
- **T2 engagement: PASS** — sessions **−2.72 min** (CI [−2.97, −2.47]), inter-session gap **−0.095 d**.
- **T3 no-harm: PASS** — |ret28 diff| = 0.0054 ≤ 0.02.
- **T4 prediction gating** — 18,182 logged due-review predictions; α > 0 accepted in **84.0%** of careers (mean α 0.92); Brier **0.3725 → 0.2546**, logloss **0.9958 → 0.7147** (P_eff = FSRS + cold-start shrinkage vs P_hybrid with gated α). The gate GUARANTEES non-worsening on its own validation split by construction.
- **T5 SCOPE (descriptive)** — +4.98% DPI vs multitype, ret28 +0.0027 (CI [−0.0164, +0.0226]).
- **T6 stress robustness** — DPI gain survives ALL 8 stress scenarios (+4.7% under slow_recovery … +19.9% under hard_skeptical); premature-quit diff < 0 in every scenario (CIs exclude 0); mechanical pacing floor under hard_skeptical = −3.23 min vs base −2.72 min (the engagement win is mostly MECHANICAL, not behavior-model-amplified — the honest direction).
- **T7 ablations** — α gating ON/OFF: no behavioral difference (by design: under the gate, α enters P_hybrid as decision support; the controller keys on observables directly). Intake gate ON: trades −0.0032 DPI for +0.0090 retention and −0.46 min sessions.
- **T8 scheduler arms (descriptive)** — SM-20 achieves the highest raw retention (0.6129) at the cost of the longest sessions; RWKV-instant is weakest overall (ret28 0.4985). Both use naive session policies; differences are attributable to the schedulers alone.

## Honest disclosures

- **Selection did not fully replicate:** triad_b showed +20.4% DPI on the calibration block but +11.4% on confirmation (seed-block flip, consistent with v1.4's variant-ordering flips). The frozen cell still cleared every floor.
- **recall-only's DPI/hour crown is a trap** (v1.6 K8 carried): per ENROLLED day, the multi-type arms beat it; its 98.7% premature-quit rate and 0.5420 retention make it a poor anchor for real use.
- **Prediction improvement ≠ scheduling improvement:** v1.8's α-gated P_hybrid improves out-of-sample prediction accuracy but is deliberately NOT yet allowed to alter scheduling; that step requires real-learner validation (per the user's α=0 rule).
- **Simulation ≠ real learners.** The behavior model is the DECLARED v1.5/v1.6 truth, stress-tested in T6, not validated against humans.

## Files

- `config18.json` — preregistration (written before any run)
- `sim18/triad.py`, `sim18/policy.py` — engine + arms (sim15/sim16 imported UNMODIFIED)
- `runner18.py`, `run18.py` — runner + stage driver (calibration → freeze → confirmation)
- `tests18.py` — 16 mechanics tests, all pass
- `analyze18.py`, `figures18.py` — analysis + 3 figures
- `outputs/` — raw CSVs, frozen policy, verdicts_v18.json, arm summary
- `fig1..3_*.png` — figures
