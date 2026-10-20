# v1.7 — Two-Arm Memory Benchmark + Real-Data Evidence Gate for a TRIAD-Native Memory Model

**Date**: 2026-10-20 · **Lineage**: v1.3 → v1.4 → v1.5 → v1.6 → **v1.7**
**Directives executed**: "now same memory benchmarks but simulate using of normal anki droid and nexus triad ones no hukkucination or guesses evidence based result" + "build toward a TRIAD-native memory model only when you have evidence showing which aspect of human recall the current FSRS-centered approach fails to capture. Then compare the new model against FSRS using real, held-out outcomes."

---

## 0. Executive verdict (read this first)

1. **Two-arm scheduling simulation** (identical material, paired seeds, 96 careers/arm): NEXUS-TRIAD-owned scheduling is **retention-clean vs normal AnkiDroid** (day-28 retention diff **−0.0008**, no-harm floor ±0.02) and **more efficient per study hour** (DPI/hour **+10.2%**, 95% CI **[+1.0%, +10.8%]** — excludes 0), with shorter sessions (−2.21 min), earlier returns (−0.12 d), and fewer premature quits (−9.7 pp; exposure-adjusted intensity −0.33/100 min). **Attribution**: the gain is carried by the **session-control layer** (goal line + due-core protection, frozen from v1.6); the new **context-risk ordering layer adds nothing measurable** (DPI −0.9%, CI [−3.3%, +2.7%]).
2. **Real-data evidence gate** (the new, decisive part): on **real learner data** (Duolingo HLR public release, 13M traces, md5-verified; 2,400 English-learner users; user-level train/calibration/test splits; FSRS-5 fitted on train users), a **small, monotone, real residual signature exists exactly where TRIAD's contextual predictor targets**: FSRS-5's prediction error declines by ~2.2 pp (relative) across session position and ~2.2 pp across same-day workload — late-session and high-workload reviews are recalled **worse than FSRS predicts**. Absence gaps add **no** signal beyond FSRS's own interval input.
3. **But the same held-out data closes the gate**: a TRIAD-native contextual memory correction (Δ_context, α selected on calibration users only) **does not improve held-out log-loss on test users** (paired gain +0.0007, 95% CI **[−0.0010, +0.0023]** — crosses 0, for both fitted and default FSRS-5 weights). Per the pre-declared rule ("build only when evidence shows a failure; compare on real held-out outcomes"), **the TRIAD-native memory-model component is NOT justified by current evidence; α stays 0**. FSRS-5 remains the authoritative memory model.
4. Consequence for the genuine-scheduler refactor: the evidence supports wiring **session control** (pacing, due-core protection) and **correct tracker plumbing** into the scheduler path — **not** replacing FSRS interval math, and **not** claiming a better memory model. This report gives the exact, testable scope.

**Honesty labels**: Part A is a simulation of a declared behavioral model — every number is a property of that model, not a measurement of humans. Part B uses real learner outcomes for **predictive accuracy** only — it is not a scheduling A/B trial. Nothing here claims superiority of NEXUS-TRIAD over FSRS as a memory model; the evidence says the opposite (no demonstrable predictive gap worth exploiting).

---

## 1. Part A — Two-arm simulation: normal AnkiDroid vs NEXUS-TRIAD scheduling

### 1.1 Design (declared before runs; `config17.json`)

- **Arm A `fsrs_multitype`** — verbatim sim16 arm: stock FSRS scheduling, scheduler's own due order, grinds to budget. This is the scheduling behavior of the released v1.8 APK (whose TRIAD layer is a passive tracker that never modifies scheduling).
- **Arm B `nexus_triad`** — TRIAD owns scheduling; FSRS remains the authoritative per-card memory engine (intervals never modified — the α=0 gate is respected *by construction*):
  1. *Review prioritization*: per-skill due queues sorted by ascending scheduler-predicted retrievability (most fragile first) before the v1.5 dishabituation interleave;
  2. *Session control*: goal line at 75% of budget + due-core protection — **frozen from the v1.6 frozen policy (p075_prot), not re-tuned** (anti-circularity);
  3. *Cold-start priors*: weakest-skill-biased intake quota (v1.5 rule, unchanged).
- Identical 600-item English bank, 5 card types, 8 learner archetypes; 3 reps × 32 learners = **96 paired careers/arm**; confirmation seed 20261101 (same as v1.6); truth constants = v1.5/v1.6 constants untouched.
- **Replication audit**: the shared arm reproduces v1.6's confirmation-base numbers **bit-exactly** (DPI 0.12799 = 0.12799; ret@28 0.58187 = 0.58187; `exact: true`) — the harness injected logging without changing behavior.
- Ablations: `triad_no_risk_order` (ordering off), `triad_no_pacing` (goal line off). Stress subset: `no_fatigue_quit`, `double_monotony`, `skeptical`, `hard_skeptical` (the full 9-scenario grid for the pacing knobs already exists in v1.6).

### 1.2 Results (confirmation block only; paired CRN; cluster bootstrap over learners, n=2000)

| Arm | DPI/hour | ret@28 | session min | gap (d) | premature quit | planned stop | due completion |
|---|---|---|---|---|---|---|---|
| fsrs_multitype (normal AnkiDroid) | 0.12799 | 0.58187 | 17.81 | 2.133 | 0.376 | 0.000 | 0.831 |
| **nexus_triad** | **0.14105** | **0.58105** | **15.60** | **2.016** | **0.280** | 0.565 | **0.859** |

| Pre-registered check | Result | Verdict |
|---|---|---|
| **P1 no-harm (primary)** | ret@28 diff **−0.0008** (floor ±0.02) | **PASS** |
| **P2 efficiency (v1.6 rule)** | DPI/h **+10.2%**, CI **[+0.97%, +10.8%]** (excludes 0; CI lower bound below the +5% point bar — reported as-is) | **PASS with CI caveat** |
| **P4 honesty (due work)** | due completion diff **+0.0275** [+0.0125, +0.0431] | **PASS** |
| **P4 engagement** | quits −9.67 pp [−12.03, −7.62]; quit intensity −0.33/100 min [−0.48, −0.20]; sessions −2.21 min; gap −0.117 d | **PASS (directional)** |

**Attribution (the important part)**:

| Comparison | DPI/h rel gain | ret@28 diff | session diff | Reading |
|---|---|---|---|---|
| full TRIAD vs stock | **+10.2%** [0.97, 10.8] | −0.0008 | −2.21 min | total effect |
| **risk-ordering layer** (full vs no-risk-order) | **−0.9%** [−3.3, +2.7] | −0.0007 | — | **no measurable effect** |
| **pacing layer** (full vs no-pacing) | −2.2% [−4.5, +3.7] | **+0.0191** | −1.55 min | pacing buys retention + shorter sessions, costs nothing significant |

The ordering layer — the piece that "uses context to front-load fragile cards" — does nothing measurable in this truth model. The retention/engagement benefit is the session controller. This is consistent with v1.6's K7 and is now confirmed under the TRIAD banner with a frozen policy.

**Stress subset** (session diff / quit diff / ret diff vs stock, CIs in outputs): the session reduction is **mechanical pacing** (hard_skeptical −2.40 min ≈ base −2.21); the quit-rate reduction survives every scenario including `no_fatigue_quit` (−5.4 pp [−7.5, −3.3]) and `skeptical` (−4.3 pp [−5.7, −3.0]); all ret diffs stay inside ±0.02 (worst: −0.0187 under `no_fatigue_quit`, inside the floor).

### 1.3 Simulation event diagnostics (descriptive only)

Per-review logging (scheduler-predicted retrievability before each grade) shows the FSRS wrapper is **absolutely overconfident** against this truth model (overall residual −0.449) — a known property of the declared truth, not a new finding — with a small additional decline later in sessions (residual −0.432 at events 0-3 → −0.463 at 12-17). Because the truth model injects exactly these channels, this pattern is an **assumption echo**, not evidence about humans. The real-data analysis below is the evidence layer.

---

## 2. Part B — Real-data evidence gate for a TRIAD-native memory model

### 2.1 Data (real, public, verified)

- **Source**: Settles & Meeder (ACL 2016) learning-traces release, Harvard Dataverse **doi:10.7910/DVN/N8XJME**, file `settles.acl16.learning_traces.13m.csv.gz`, **md5-verified** `0a1cae5eb7ad4b0bd9c0de91d74fcced`. 13M practice events from real learners.
- **Material**: filtered to `learning_language == 'en'` — learners **studying English** (the benchmark's identical-English-material requirement, on real data).
- **Sample**: users with ≥40 events; deterministic hash subsample of **2,400 users → 558,148 practice events** over 2,512 English lexemes.
- **Splits (user-level, hash-seeded 20261101)**: train 1,456 users / 345,135 rows; calibration 479 / 113,409; **test 465 / 99,604 — touched exactly once, by the frozen evaluation**.
- **FSRS-5 memory model**: exact py-fsrs 5.1.3 formulas (19 params, DECAY −0.5, FACTOR 19/81, exponential D₀, short-term branch, damped mean reversion), grades mapped from p_recall (declared: 4 if p=1.0, 3 if ≥0.8, 2 if ≥0.6, else 1), same-day events handled by FSRS-5's short-term rule and **excluded from evaluation** (srs-benchmark convention).

### 2.2 Step 1 — the requested evidence: where does the FSRS-centered approach fail?

On **held-out test users**, FSRS-5 (fitted on train users) + global calibration leaves residuals (actual − predicted recall) with a **small, monotone, contextual gradient**:

| Context stratum | residual (actual − predicted) |
|---|---|
| Session position 0-2 | **+0.0444** |
| 3-5 / 6-8 / 9-12 | +0.0419 / +0.0378 / +0.0338 |
| 13+ (late session) | **+0.0239** |
| Workload 0-4 events today | **+0.0446** |
| 25+ events today | **+0.0225** |
| Absence 1 d / 2 d / 3-6 d / 7+ | +0.076 / +0.014 / +0.059 / +0.064 (n=139/100/81/16 — noisy, **no pattern**) |

**Reading**: relative to its own predictions, recall declines ~**2.2 pp** from early to late session and ~**2.2 pp** from low to high same-day workload. This is the **first real-data (non-simulated) demonstration in this project** of the exact channels TRIAD's contextual predictor targets (session fatigue proxies, workload). It is small and it does **not** appear for absence gaps beyond what FSRS's interval already encodes.

### 2.3 Step 2 — the gate: does a TRIAD-native correction beat FSRS on held-out outcomes?

Protocol (pre-declared): Δ_context = linear contextual correction on [session position, elapsed session minutes, same-day workload, absence gap], fitted **on train users only**; α ∈ {0, 0.125, …, 2.0} selected **on calibration users only** (α* = 0.75, cal log-loss 0.33575 vs 0.33692 at α=0 — a clean concave minimum); test users evaluated **once**, frozen.

| Memory model | M0 = FSRS-5 (test log-loss) | M1 = M0 + α*·Δ_context | paired per-user gain (95% CI) |
|---|---|---|---|
| FSRS-5 **fitted** on train users | 0.32521 | 0.32538 | **+0.0007 [−0.0010, +0.0023]** — crosses 0 |
| FSRS-5 **default** (out-of-box AnkiDroid) | 0.32534 | 0.32557 | **+0.0007 [−0.0011, +0.0024]** — crosses 0 |

Secondary metrics agree the effect is negligible: MAE improves microscopically (0.18298 → 0.18183 fitted), AUC on binary single-exercise rows 0.5446 → 0.5466 (n=7,732), Brier unchanged. 289 of 465 test users have ≥1 evaluation-eligible (non-same-day) review.

**Verdict: the gate CLOSES.** The contextual channel is real but far too weak to convert into held-out predictive accuracy. Under the user's own rule — *build toward a TRIAD-native memory model only when evidence shows which aspect of recall FSRS fails to capture; then compare on real held-out outcomes* — the evidence shows **a small fatigue/workload signature that does not survive validation as a predictive advantage**. A TRIAD-native memory model replacing or modifying FSRS-5 is **not justified** by current evidence; α stays 0 in any scheduling path that touches intervals.

### 2.4 Why the calibration-block gain did not generalize

The calibration block showed a consistent improvement (−0.0012 log-loss at α=0.75), but its magnitude is at the noise scale for held-out users: the contextual features are sparse per user (median evaluated rows per test user is small) and correlated with each other (position/elapsed) and with FSRS's own inputs (workload correlates with practice volume and spacing). This is precisely why the split protocol exists — and it worked: a genuine-looking calibration gain was caught before it could be sold as a scheduling claim.

---

## 3. What this means for the genuine-scheduler refactor

The combined evidence defines the smallest correct, testable scope:

1. **Justified by evidence**: fixing the four integration defects; routing **session control** (pacing + due-core protection) and **review presentation order** through the backend scheduling path behind a feature flag (TRIAD owns ordering/pacing; FSRS owns intervals — exactly the α=0 architecture). Expected effects, sized by this simulation: ret-neutral, ~+10% DPI/hour, shorter sessions, fewer premature quits — **within the declared simulation only**.
2. **Not justified by evidence**: any TRIAD-native memory model replacing or modifying FSRS interval math (α>0). The real-data gate says the missed signal is ~2 pp and does not generalize; building it would be exactly the "interesting architecture, not a demonstrated upgrade" failure mode the user identified in the v1.8 review.
3. **Also not justified**: the context-risk ordering layer — measurable ≈ 0 in simulation; keep it out of the first refactor increment (smallest correct changes).
4. Remaining real-data levers worth one more iteration (declared, not built): per-user Δ (learner-specific context sensitivity), richer features (time-of-day in local tz, per-lexeme difficulty priors), and longer-horizon scheduling outcomes. These require pre-registration before the next test-set touch.

---

## 4. Assumptions and limitations (full disclosure)

- **Part A** is a simulation: behavioral truth (fatigue → performance penalty, quit/return hazards) is a *declared model*; the stress scenarios bound but do not validate it. Absolute FSRS-vs-truth miscalibration in the simulator is large and known; only relative, paired, pre-registered comparisons are interpreted. TRIAD knobs were frozen ex ante (no v1.7 tuning); the replication audit proves logging injected no behavior change.
- **Part B** uses real outcomes for **prediction accuracy only**: Duolingo 2012-2013 aggregates (p_recall per lesson, not per-exercise binary reviews), a declared grade mapping, sessions defined by a 30-minute gap, English-learner population, 2,400-user sample. A low absolute AUC (~0.55 on binary rows) reflects the aggregated targets and state model; the paired, user-level comparison is the interpretable quantity, and it is null. This is not a scheduling trial: no learner was scheduled by TRIAD.
- **The released v1.8 APK's TRIAD is a passive tracker**; Arm A reproduces its scheduling behavior; Arm B evaluates the TRIAD scheduling design. No claim in this report is about the shipped APK.
- The token used for repository operations is a runtime secret only (never stored in repo files); rotation remains the owner's call.

---

## 5. Reproduce

```bash
# Part A (simulation; ~2 min)
cd download/v17_nexus_triad_benchmark
python3 runner17.py --scenario base --variant nexus_triad --n-reps 3          # etc. for ablations/scenarios (see run17.sh)
python3 analyze17.py                 # verdicts_v17.json (P1-P6 + replication audit)

# Part B (real data; dataset from doi:10.7910/DVN/N8XJME, md5 0a1cae5e...)
python3 scripts/v17/prep_real.py     # declared preprocessing -> data/real_events.parquet
python3 scripts/v17/fit_real.py     # FSRS-5 fit + dContext + alpha (train/cal only)
python3 scripts/v17/eval_real.py    # ONE frozen evaluation on test users
python3 scripts/v17/figures17.py    # figs 1-4
```

Artifacts: `outputs/verdicts_v17.json`, `outputs/verdicts_real.json`, `outputs/v17_base_by_arm.csv`, `outputs/fig1..fig4`, raw CSVs under `outputs/raw/`, frozen model `outputs/real_frozen.json`.

## 6. Verdict table (single glance)

| Question (user directive) | Evidence | Answer |
|---|---|---|
| Normal AnkiDroid vs NEXUS-TRIAD scheduling, no hallucination | Part A, paired CRN, replication-audited | ret-clean (−0.0008), DPI/h +10.2% [1.0, 10.8], sessions −2.21 min, quits −9.7 pp — **pacing carries it**; ordering ≈ 0 |
| Which aspect of recall does the FSRS-centered approach miss? (real evidence) | Part B step 1, held-out strata | small real fatigue/workload signature (~2.2 pp relative decline each); absence: nothing beyond FSRS |
| Build a TRIAD-native memory model? | Part B step 2, frozen held-out test | **No** — CI crosses 0; α=0 stands; FSRS-5 stays the memory model |
