# Multi-agent worklog

---
Task ID: 2
Agent: main (Super Z)
Task: Build, validate and execute the full simulation benchmark

Work Log:
- Wrote config.json: full parameter table (costs, memory, mechanisms with 4 regimes, methods, MC design, evidence labels)
- Built scripts/simulation.py (~2,500 lines): Env/item bank (600 items, 24 contexts, confusable clusters), 8 learner profiles,
  official FSRS wrapper + SM-2/HLR/Leitner/cram alt-schedulers, two-layer memory model (FSRS cards per (item,skill) trace +
  latent skill gains + context-tagged generalization + confusion + fatigue + adherence), 6 method policies + restudy/placebo variants,
  probes (day-7/day-30, model-based retention lags), prediction metrics (logloss/Brier/ECE/AUC), DIP composite (pre-registered equal weights),
  seed-cluster bootstrap CIs, paired CRN diffs, experiments V/A/B/D/E/E1/F/G/CALIB, per-experiment persistence + resume, figures
- Fixed during shakedown: py-fsrs requires tz-aware UTC; config dict-valued params (pv()); RAVEL stage progression; NEXUS phase budgets;
  listening training must be independent FSRS reviews to have any effect; monotony evaluated on daily dominant task; workload thresholds 80;
  graduated-memory calibration (R itself is the recall probability for >=2-rep traces; capability shapes encoding); per-learner stability multiplier
- Validation (V): ALL 4 CHECKS PASS - spacing > cram, retrieval >> restudy (0.846 vs 0.224), +40% costs reduce learning, placebo never wins/min
- Ran 10,168 runs: V 320, A 1,440, B 1,440, D 792, E 2,304, E1 1,296, F 768, G 2,048 (2 workers, ~25 min total)
- Final aggregation + 5 figures; copied simulation.py to deliverables

Stage Summary:
- KEY RESULTS (see benchmark_report.md): FSRS baseline wins pre-registered DIP-per-minute composite in every profile & all 4 regimes
  (0.174/100min neutral); PULSE closest alternative (0.111; indistinguishable for overconfident profile) and BEST under equal exposure (0.308);
  NEXUS buys transfer (+0.11-0.17) & fixes weak listening but most time-hungry and most regime-sensitive; FORGE most consistent listening gains
  but worst under backlog/short budgets; RAVEL most production-ready items but worst absolute composite; ablation: skill_diagnosis helps,
  gamification costs, others negligible; task-repetition mechanism nearly inert (flagged); Experiment F: scheduler choice barely moves learning
  (SM-2 most review-efficient, FSRS best calibrated ECE 0.07, HLR degenerates overconfident); robustness: FSRS most stress-resistant,
  PULSE most resilient alternative, NEXUS shines in weak-modalities scenario
- Deliverables in /home/z/my-project/download/english_methods_benchmark/ (9 requested files + 7 supporting: paired diffs, per-run rows,
  runs_*.csv batches, scheduler/robustness/validation CSVs, 4 extra figures)

---
Task ID: 1
Agent: main (Super Z)
Task: Read method specifications, verify environment, plan benchmark

Work Log:
- Read /home/z/my-project/upload/Pasted Content_1792010591516.txt = NEXUS-English v1.2 full spec (831 lines)
- SCENE-FORGE English ("Method 2 of 3") and PULSE-English ("Method 3 of 3") specs pasted in user message
- RAVEL has NO full spec anywhere -> will formalize from 3 bullet characterizations in PULSE doc, all assumptions labeled
- Verified python3.12 venv (numpy 2.1.3, pandas 2.2.3, scipy 1.14.1, matplotlib 3.9.2)
- Installed official `fsrs` 6.3.2 (open-spaced-repetition py-fsrs) into venv; verified API:
  Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False), review_card->(card,log),
  get_card_retrievability(card, dt); day-scale intervals; immutable cards; FSRS-6 default weights
- SM-20 / RWKV-Instant have no public implementation spec -> excluded from fabricated simulation per user's
  integrity rules; Experiment F instead tests FSRS vs SM-2 vs HLR vs Leitner (all public algorithms), tested from scratch
- Loaded charts skill for figure standards

Stage Summary:
- Methods to implement: FSRS baseline, NEXUS (full spec), RAVEL (assumption-labeled), PULSE (full spec),
  FORGE = SCENE-FORGE (full spec), FORGE-Combined (FORGE + skill diagnosis + confidence; subject of ablation D)
- Deliverables to /home/z/my-project/download/english_methods_benchmark/

---
Task ID: 3 (v2 phase)
Agent: main (Super Z)
Task: MASTER PROMPT V2.0 — forensic audit of v1 + rebuild + re-run rigorous benchmark

Work Log:
- Inventoried artifacts: v1 benchmark EXISTS (download/english_methods_benchmark/, 10k+ runs, code+config+report+CSVs);
  NEXUS v1.2 full spec = upload/Pasted Content_1792010591516.txt (831 lines, fully read);
  V2 master prompt = upload/Pasted Content_1792044514711.txt (627 lines, fully read)
- Verified venv /home/z/.venv (py3.12.15, numpy/scipy/matplotlib/pandas OK); installed fsrs (official py-fsrs, 21-param FSRS-6) into venv
- Extracted exact FSRS-6 equations from installed source (R=(1+F*t/S)^DECAY, DECAY=-w20=0.1542-based; init/next stability+difficulty formulas) for the tuned-FSRS fitter
- Audit evidence gathered (see audit_v1.md): success_prob() in v1 uses FSRS card retrievability AS the simulated ground truth (circularity, prompt 2.3);
  add_dip() z-scores components across methods (prompt 2.1); Exp A used only 3 seeds (prompt 2.4); minutes_used spread 328-436 in "equal-time" A (prompt 2.2);
  run-count discrepancy: report headline 10,168 vs CSV sum 10,172 vs report section-11 breakdown 10,432 (runs_B.csv=1200 but report claims 1,440) (prompt 2.7)

Stage Summary:
- Proceeding to write audit_v1.md, config_v2.json, method_registry.md, then simulation_v2.py (decoupled 4-world memory core), tests, full run

---
Task ID: 3 (v2 build complete)
Agent: main (Super Z)
Task: simulation_v2.py built, tested; launching full run

Work Log:
- Built download/english_sim_v2/simulation_v2.py (~2,900 lines): 4 decoupled worlds (W1 power-law,
  W2 Weibull, W3 context-specific, W4 skill-transfer matrix); official py-fsrs as SCHEDULER ONLY;
  15 arms (4 FSRS baselines incl. per-world tuned via validated numpy FSRS-6 replay + L-BFGS-B;
  nexus/ravel_prov/scene_forge/pulse/forge_combined; 5 pre-registered hybrids; validation arms);
  experiments A/B/C/D/E/F/G/H/I + V + SW sweeps; seed-level bootstrap CIs, BH-FDR, adaptive seed
  extension; fail-loud reconciliation (run_audit) + fairness gates
- tests_v2.py: 24 checks ALL PASS, including: T-fit replay==py-fsrs (<1e-9); T2 full-pool denominators;
  T3 world/scheduler decoupling (card poisoning changes nothing); T3b Weibull world miscalibrates
  FSRS-default (ECE 0.30); T6 all triggers fire; T11 spacing effect; T12 testing effect; T15 world
  structure sensitivity; T5 fairness gates; T8 reproducibility
- Bugs found & fixed during shakedown (each caught by a test): replay update order (stability uses
  current difficulty); Card() default due = real-now (2026-10) > simulated dates => new cards never
  due -> due pinned to course start; lifetime-vs-daily budget confusion froze phase policies after
  ~day 8 -> per-day spend accounting; PULSE missing new-item intro; W4 transfer-matrix key parsing;
  arm_flags ablation parsing; restudy compounding (multiplicative gains -> additive-saturating +
  spacing-dependent gain factor + restudy must be processable); reps count successes not attempts
- Perf: 130->60-95 ms/run (np.percentile elimination, ctx-sim matrix). 2 cores.

Stage Summary:
- Launching full pipeline: fit -> B,C,F,G,H,I,V,SW -> A (100 seeds x 9 arms x 4 worlds x 4 regimes
  x 8 learners = 115,200 runs) -> adaptive extension -> aggregate. Est. 2.5-3 h background.

---
Task ID: 4 (v1.1 completion)
Agent: main (Super Z)
Task: Complete interrupted v2 pipeline, fix discovered bugs, re-run affected arms, deliver tagged v1.1 package

Work Log:
- Verified prior progress: A/B/C complete at 100 seeds; F-I/V/SW missing (background run died with session)
- Ran remaining experiments foreground in chunks (background execution unreliable in sandbox)
- Discovered phase-budget bug (critical): NEXUS/SCENE-FORGE/PULSE skipped every phase after the largest
  (PULSE: 0 reconstructions, 0 verifications in 115k rows). Fixed to cumulative session targets
- Fixed: KIND_COST missing 'verify' (crash), HLR first-review None crash, H arm->fsrs_mean shell mapping,
  extras (cost_mult/slow_pct) not recorded in rows, --only char-splitting, T4/T5 gate mis-specifications
- Re-ran all affected arms: 51,200 A rows + B/C affected arms + all F + I cells + V + SW (~78k rows)
- Repaired post-run schema shift in A/B/C tail columns (name-based realignment, 0 violations verified)
- Aggregated: gates pass, 166,559 runs reconciled, 9 result CSVs + 8 figures generated
- Wrote benchmark_report_v1.1.md (18 sections, English), README_v1.1.md
- Delivered 25 files to /home/z/my-project/download/english_benchmark_v1.1/ (all tagged _v1.1)

Stage Summary:
- HEADLINE (Exp A, equal offered opportunity, 100 seeds, W1 neutral): fsrs_mean 0.379 best absolute;
  ravel_prov 0.371 (paired -0.008) with fewest active minutes (efficiency leader); heavyweights far below
  (forge_combined 0.264, pulse 0.248, scene_forge 0.246, nexus 0.228). Ordering stable across 4 worlds,
  4 regimes, 8 profiles; heavyweights fail first under 10-min budgets and starting backlogs
- Ablation: skill_diagnosis helps (-0.018 if removed); workload_adaptation hurts (+0.038 if removed);
  12/14 components null. Hybrids: only H2 (FSRS+diagnosis) non-inferior; repair hybrids cost -0.023..-0.059
- Scheduler-only: SM-2 best learning outcome (0.403 vs FSRS 0.377); tuned FSRS best calibration (ECE 0.031)
  but worst outcomes among FSRS variants - prediction/outcome dissociation
- Deliverables: /home/z/my-project/download/english_benchmark_v1.1/ (25 files, all tagged v1.1)

---
Task ID: 5 (v1.2)
Agent: main (Super Z)
Task: Address user feedback: test SM-20 + RWKV-Instant, de-rig the FSRS-centered benchmark, implement corrected NEXUS-SCOPE 2.0, deliver tagged new results

Work Log:
- Reinstalled official py-fsrs 6.3.2 (session reset had wiped the venv); verified Scheduler/Card/Rating API
- Extended the validated v2 engine (scripts/simulation_v2_v12.py, fork of simulation_v2.py):
  * NEXUS-SCOPE 2.0 arm 'scope2': protected FSRS reviews within (1-budget) share, Level-1 skill profile
    (per-skill EMA), Level-2 selective specialist training (auditory/production/prediction-repair/variation),
    review-level diagnosis probes (30% audio / 20% production on due meaning cards), budget 0/10/20/30 tested,
    earn-extension +5pp to 30% cap, simplify-or-remove implemented as trigger retirement, delayed verification,
    confidence sampled 25%, backlog guard
  * Self-implemented SM-20 (SM-2 core + 20-point quality remap + fine-scale modifier) and RWKV-Instant
    (RWKV-style gated multiplicative delta rule on per-item half-life) — both DECLARED stand-ins (no public
    spec), self-tuned on training learners only (rwkv eta=0.3 by logloss; sm20 variants tied, conservative chosen)
  * New stress scenarios: accent_storm, attendance_gaps, combined_real_world
  * J-experiments J1-J5 + v1.2 aggregation/figures/report writer (main_v12)
- Debugging loop caught by trigger forensics: (a) cross-skill EMA triggers inverted by probe-timing confound ->
  added absolute weakness floor; (b) specialists starved by review overflow -> 80/20 budget contract; (c)
  simplify rule froze whole session -> retired only the stagnating trigger; (d) verified HLR/RWKV row-identity
  is genuine behavioral convergence to daily review (not a wiring bug) and SM-20 vs SM-2 differences come from
  the q5 remap (3.75 vs 4.0 on Good)
- tests_v12.py: 30 checks ALL PASS (budget contract, b0 purity, scheduler sanity, scenario wiring, CRN pairing,
  all 12 arm variants smoke)
- Executed: tuning + J1 25,600 + J2 2,400 + J3 16,000 + J4 6,400 + J5 7,200 = 57,600 primary runs (~109k raw
  executions incl. deterministic re-runs), 0 errors; aggregated, figures, 12-section report, README
- Delivered 28 files to /home/z/my-project/download/english_benchmark_v1.2/ (all tagged v1.2)

Stage Summary:
- HEADLINE (J1, W1 neutral, 50 seeds, equal offered time, pre-registered full-pool PC30):
  fsrs_mean 0.3789 > fsrs_bidi 0.2716 > scope2 0.2473 > nexus 0.2278
- Selectivity confirmed: scope2 > Full-NEXUS +0.0195 paired (p<1e-4); budget_control is the load-bearing
  component (ablation -0.0427); selective_diagnosis -0.0085; enrichment itself does not pay on the full-pool
  composite (budget sweep monotone down 0.2496 -> 0.2441) — honest cost of targeted instruction at 30 days
- Scheduler tournament: sm2 0.4044 > fsrs 0.3789 > sm20 0.3632 > leitner 0.3628 > hlr=rwkv_instant 0.2943
  (degenerate daily review, explained) > fsrs_tuned 0.2941 (best ECE 0.031, worst outcome — dissociation replicates)
- De-rigging verified: method ordering (scope2 > nexus) survives scheduler swap (scope2 under sm2 0.2879,
  under rwkv 0.2372); ground truth owned by 4 non-FSRS worlds; probes independent
- Deliverables: /home/z/my-project/download/english_benchmark_v1.2/

---
Task ID: S5
Agent: benchmark-runner-builder
Task: Build the neutral evaluator + stress conditions + experiment runner/CLI + DPI endpoint for the v1.3 benchmark, with full test coverage

Work Log:
- Read worklog.md, then simlib/spec.py, env.py, memory.py, primitives.py, methods/baseline.py, config.json, tests/test_core.py in order; verified tests/test_core.py 7/7 PASS before starting; no shared file modified
- Wrote simlib/benchmark/stress.py: stress_condition / stress_day_active / stress_budget; ALL values read from cfg["stress"] at call time (nothing hardcoded); missed_sessions draws unconditionally per learner-day (constant rng consumption); stress_condition is rng-free so session+probe override derivation for the same day is exactly reproducible
- Wrote simlib/benchmark/evaluator.py: NeutralEvaluator with 9 learn=False probe sets (trained_retention <=30 known trainable items; novel_meaning/listening/production/grammar/transfer = 6 reserve items each; transfer_shift = 3 reserve transfer items re-placed via bank.replace to an unseen context, bank never mutated; listening_noise = noise_mult 1.5; accent_shift = all accents remapped to regional_2), one row per set (day, t_min, learner_id, archetype, probe, value=mean p_correct, n), plus up to 40 scheduler-prediction diagnostic rows (item_id, pred_R, truth_R, day, learner_id). Probes call truth.sample_practice(..., 0.0, {**overrides, "learn": False}) only: zero state change, zero minutes, zero scheduler logging
- Wrote simlib/experiments/runner.py: ArmSpec; build_condition (regime params + durations/n_contexts/new_card_cap + stress overrides); run_career (truth seed path pool.spawn("truth", rep, learner_id) IDENTICAL across arms = CRN at career start; truth.on_day_boundary(day) first; per-day rng pool.spawn("day", rep, learner_id, day); BudgetExhausted -> warning counted; probes run on cfg probe days even when the session day is skipped); run_experiment (per rep: bank + population built ONCE, shared across arms; careers/probes/diag pandas CSVs; one progress line per rep-learner); compute_dpi (0.40*trained_retention + 0.40*mean(five novel_*) + 0.20*plain transfer, divided by study hours); main() CLI (--experiment/--arms/--regime/--stress/--pilot plus --n-reps/--n-per-arch/--out-dir) resolving arms via simlib.registry inside main() only, SystemExit "simlib.registry not yet written by the main agent"
- Wrote tests/test_benchmark.py (15 tests): DummyScheduler (fixed 2-day interval, predicted_retrievability returns a value so diag rows exist) and DummyMethod (2 due reviews, 1 listening drill on known-or-new listening item, <=4 new meaning cards), monkeypatched into schedulers.FACTORIES["dummy"] (tests only, auto-reverted); no dependency on simlib.registry
- Iterated on failures: (1) DPI initially looked for a bare "transfer" probe, but the 9-probe set has none -> the plain transfer probe is novel_transfer (never transfer_shift); test now asserts DPI is EXACTLY unchanged when transfer_shift rows are dropped and changes when novel_transfer is dropped. (2) During the run, agent S1's simlib.schedulers landed mid-edit (transient NameError in sm20.py) - retried after their write completed, no action needed on my side
- Verified: probes leave truth.S/last_t/n_enc/contexts/accent_exposure/total_minutes and learner.ability bit-identical; run_career twice -> identical probe rows (exact float equality) and identical study_minutes; tiny run_experiment (n_reps=1, n_per_arch=1) -> 8 career rows, 3 CSVs, all 9 probe names on each probe day, diag rows present; all 7 stress names run 4 days clean; feedback_errors yields grade != grade_true records; backlog skip days honored and probes still fire on skipped days; experiment-level smoke (2 arms x 8 learners x 28 days, real config) produces byte-identical CSVs across two runs; integration smoke with S1's real "fsrs" factory + FlashcardMethod runs clean (DPI computed)

Stage Summary:
- Artifacts: simlib/benchmark/__init__.py, simlib/benchmark/stress.py, simlib/benchmark/evaluator.py, simlib/experiments/__init__.py, simlib/experiments/runner.py, tests/test_benchmark.py — tests/test_benchmark.py 15/15 PASS, full suite 22/22 PASS
- Interface concerns / deviations (all documented in code ASSUMPTION labels):
  1) Task sheet expected "careers row count == 1" for n_per_arch=1, but shared build_population always enumerates all 8 archetypes -> 8 rows per arm-rep; test asserts 8
  2) Runner probe call uses evaluator kwarg t_min (the sheet wrote "t_end="); probe time = session start + 120 min
  3) Probe-specific controlled overrides (noise 1.5 / accent remap) win over ambient stress overrides inside their own probe sets; all other probes inherit the day's stress overrides
  4) compute_dpi: novel composite = mean of the FIVE novel_* probes (incl. novel_transfer) and the transfer component re-uses novel_transfer -> transfer-flavored probes carry 0.28 total weight under the 0.40/0.40/0.20 weights; pre-registered formula, flagged for the report writer
  5) run_career takes an extra optional kwarg experiment="" (filled by run_experiment); career rows include experiment
  6) Expected registry interface: simlib.registry.build_arms(names: list[str], cfg: dict) -> list[ArmSpec]; runner imports it only inside main(). Scheduler factories are cfg -> SchedulerBase; S1's live set: fsrs, leitner, random, rwkv_instant, sm20 (FlashcardMethod from methods/baseline.py pairs with them)
  7) BudgetExhausted from a method counts 1 warning and the day still calls method.on_day_end; partial session work is kept
  8) compute_dpi returns NaN for zero probe rows or zero study minutes (e.g. all sessions missed) - aggregation must skipna
- Next actions for main agent: write simlib/registry.build_arms; wire experiment names to run_experiment/main(); aggregation should read {name}_careers.csv, {name}_probes.csv, {name}_diag.csv and call compute_dpi per career row

---
Task ID: S1
Agent: schedulers-builder
Task: Build the v1.3 scheduler suite (FSRS-4.5-style, SM-20, RWKV-Inspired Instant, Leitner, Random) with factories and tests
Work Log:
- Read worklog.md, then simlib/spec.py, simlib/env.py, simlib/memory.py, simlib/primitives.py, simlib/methods/baseline.py, config.json, tests/test_core.py; verified tests/test_core.py passes (7 passed) before starting; no file outside my ownership was modified.
- simlib/schedulers/fsrs.py: class FSRS (FSRS-4.5-style). Published 17-param default weight vector used verbatim (ASSUMPTION: no refitting on simulated data). Per-item plain dicts S/D/last_t/due_t. First graded review initializes S0(G)=w[G-1], D0(G)=clamp(w[4]-(G-3)w[5]); later reviews: difficulty linear update + mean reversion to D0(4), success S' with hard/easy modifiers (w[15]/w[16]), lapse S' with min(S',S); clamps S in [0.1,36500] d, D in [1,10]. Interval = S/FACTOR*(R_d**(-1/DECAY)-1) with R_d=0.9 from config; add_new = 10-min learning step (ASSUMPTION). predicted_retrievability + stability_estimate implemented; due() most-overdue-first with limit. Never reads the truth model (grep-verified).
- simlib/schedulers/sm20.py: class SM20. Ease quantized to a 20-level grid spanning exactly 1.30..2.90 (step ~0.0842); grade map Again/Hard/Good/Easy -> q=1/3/4/5 (declared); EF' = EF + (0.1-(5-q)(0.08+(5-q)0.02)) snapped to the nearest grid level, clamp >= 1.3, applied on EVERY review incl. failures (declared literal-order interpretation; classic SM-2 freezes EF on q<3). q<3: reps reset to 0 + 10-min relearn step; else n+=1 with intervals 1 / 6 / round(prev*EF) days capped 365. Initial EF 2.5 snapped to nearest grid level (declared). Heuristic R = (1+FACTOR*t/I)**(-0.5) with I = current interval (declared heuristic).
- simlib/schedulers/rwkv_instant.py: class RWKVInstant. Docstring declares it as our own design: an online single-pass scheduler inspired by RWKV-style state updates; NOT the RWKV language model, no external benchmark data. Per-item log_S (init log 1.5) and decay D (init 0.5) plus global prior EMA with 20% prior / 80% item-state shrinkage (prior EMA rate 0.05, declared). Targets y={1:0.10,2:0.60,3:0.85,4:0.97}; log-space gradient step lr=0.08 clipped +/-0.35 using the TRUE positive derivative dR/dlogS = R*D*u/(1+u); decay D += 0.01*(R_hat-y) clipped [0.3,0.8] (sign note declared in docstring); next due t_days = S*(R_d**(-1/D)-1)/0.234568 clamped [0.02,365] d; add_new = 10-min step.
- simlib/schedulers/baselines.py: class Leitner (7 boxes, intervals [1,2,4,8,16,32,64] days declared, grade>=2 promotes capped at 7, fail -> box 1, new items box 1 due t+10min, FSRS-family R heuristic on the box interval) and class RandomSched (next_due = t + U(1..6) days; deterministic seed = cfg["master_seed"] + item_id*31 + int(t); due() returns due seen items in an order seeded by master_seed + int(t) + 1, so identical event sequences reproduce identical schedules).
- Wired simlib/schedulers/__init__.py: kept the register decorator; module imports trigger @register; explicit FACTORIES mapping {"fsrs","sm20","rwkv_instant","leitner","random"} (classes as cfg-taking callables) plus class re-exports.
- tests/test_schedulers.py: 24 tests, ALL PASS. Factory + isinstance(SchedulerBase) checks; 40-item x 30-day random-grade add_new/review/due roundtrip for all 5 schedulers (limit respected, ids are ints, prediction/stability hooks raise nothing and stay sane); determinism of identical event sequences for all 5; FSRS: stability grows over 2-day-spaced Goods, shrinks after a lapse, R in (0,1], interval identity interval==S at defaults, Good-streak due > Again due, most-overdue-first ordering; SM20: exact 20-level grid membership over 80 random reviews + failure resets reps with 10-min relearn; RWKV: R rises 0.784 -> 0.871 across 150 spaced y=0.97 events (crosses 0.85), D/S/prior stay in bounds, predictions in (0,1]; Leitner box progression 1->7 and demotion; Random per-item seed variation + deterministic order.
- python3 -m pytest tests/test_core.py tests/test_schedulers.py -q -> 31 passed. py_compile clean on all new files.
Stage Summary:
- Artifacts: simlib/schedulers/fsrs.py, simlib/schedulers/sm20.py, simlib/schedulers/rwkv_instant.py, simlib/schedulers/baselines.py, simlib/schedulers/__init__.py (FACTORIES wiring only), tests/test_schedulers.py (24 passing tests). No core files touched; full benchmark not run.
- Interface concerns (adapted without changing any shared interface): (1) The task's FSRS interval formula "S/FACTOR*(R_d**(1/DECAY)-1)" is negative for any DECAY>0; implemented the standard inverted exponent (R_d**(-1/DECAY)-1), which reproduces interval==S exactly at FACTOR=19/81, DECAY=0.5, R_d=0.9 (test-pinned). (2) The task's RWKV dR/dlogS definition carries a sign error (true derivative is positive; the given form would drive S away from the target) and its two decay-update fragments contradict each other (one degenerates into a monotone ratchet that only increases D); implemented the mathematically consistent gradient and symmetric decay rules at the specified magnitudes, documented in the module docstring. (3) SM-20 has no public spec; implemented strictly from the task rule sheet as SM-2 with 20-level ease quantization. (4) add_new for every scheduler = 10-minute first learning step; learnable state (S/D/EF/log_S) initializes at the first graded review, matching FSRS's first-rating convention (primitives call add_new without a grade). Every assumption is labeled ASSUMPTION: in the module docstrings.
- Downstream contract: FACTORIES[name](cfg) returns a SchedulerBase; due(t_min, limit), add_new(item_id, t_min), review(item_id, t_min, grade 1..4), predicted_retrievability(item_id, t_min) (None/0.0 conventions documented), stability_estimate(item_id).

---
Task ID: S3
Agent: ravel-pulse-builder
Task: Implement RAVEL (variation-first) and PULSE (repair-centric) methods with pre-implementation per-skill optimization mappings and a full test suite.

Work Log:
- Read /home/z/my-project/worklog.md, then simlib/spec.py, simlib/env.py, simlib/memory.py, simlib/primitives.py, simlib/methods/baseline.py, config.json, tests/test_core.py; verified python3 -m pytest tests/test_core.py -q = 7 passed BEFORE starting. No shared file modified.
- Embedded the per-skill optimization mappings (produced BEFORE implementation, per user instruction; exclusions NEXUS/FSRS/RWKV-Instant/SM-20 acknowledged; "SBD" is an undefined acronym, not a method) as exported module-level dicts RAVEL_SKILL_OPTIMIZATION and PULSE_SKILL_OPTIMIZATION (exact strings), and used them in dispatch decisions: RAVEL — listening->modality rotation (listening-skill items get rotation priority), transfer->top-5 novelty + unseen context, meaning/grammar/production->context rotation; PULSE — perception->HVPT drill, production->forced production + spaced verification, meaning/grammar/transfer->new-context re-presentation.
- simlib/methods/ravel.py (Ravel(MethodBase), name="ravel"): due reviews FIRST via context_review(new_context=True, log_sched=True) — the review itself happens in a novel context; cross-modality rotation for audio items practiced >=2x in the same modality (context_review new_context=False, modality rotated, log_sched=False); ONE new-context re-encode per failed item per session, never re-logged to the scheduler; RAVEL_REENCODE_CAP=0.15 of session budget shared by rotation+re-encodes (new-card failures re-encoded in a final pass within the same cap); transfer practice bounded by declared RAVEL_TRANSFER_SHARE=0.20 with top-5 novelty selection and own-history unseen context; new intake on the meaning pool with new_card_cap minus already-new-this-session (transfer first-encounters counted against it), union of reserve_ids excluded; per-item modality/context counts tracked from the method's OWN history (truth internals never read).
- simlib/methods/pulse.py (Pulse(MethodBase), name="pulse"): classify_quadrant from Outcome.error_type, else latency heuristic (latency_s>8 -> consolidation_failure else retrieval_competition); weak_trace declared -> deferred like consolidation_failure. Due reviews via review_card (normal logging); ONE repair per failure under PULSE_REPAIR_CAP=0.25: perception->listening_drill(same iid, hvpt=True), drill-fail -> stop touching item today + queue (day+2, "listening"); meaning_gap/retrieval_competition -> context_review(new_context=True, log_sched=False); consolidation_failure -> NO same-day retry, queue (day+2, "meaning"); production-skill failures -> production_task (+queue on fail). Spaced rechecks via delayed_verification; verified outcomes logged to the main scheduler (declared: FSRS timing learns from them) using the learner-reported grade (= truth grade when feedback_flip_rate=0); failed rechecks requeue at +3 days, max 2 requeues then drop. Repairs/variation never log to the scheduler; accum.repair_events counts executed same-day repairs only; new intake meaning pool cap 8/day, reserve excluded.
- tests/test_ravel_pulse.py: counting stub scheduler (records (iid,t,grade) review/add calls; rotating due list with grade-dependent intervals 1/2/4/7 days), Runner day driver (condition = {"durations": cfg.session.durations_min, "n_contexts": 12, "new_card_cap": 8} merged with cfg.regimes.neutral; truth.on_day_boundary before each session; per-day budget assert). All 8 required tests implemented: (1) context diversity grows (history pairs + truth.contexts_seen cross-check), (2) re-encode cap 15% per session, (3) exactly one scheduler log per due review served (+ add_new == new cards), (4) repairs only after same-item failed reviews (ledger), (5) no identical (item,kind,context) triple per session, (6) repair minutes <= 25% per session, (7) scheduler.review only for scheduled reviews + verified rechecks (exact-triple match), (8) 14-day runs on balanced_novice/weak_listener/struggling_all x both methods, budget and reserve never violated. Plus mapping-export, quadrant/dispatch unit tests, and a modality-rotation dispatch test (injected method history).
- Verification: python3 -m pytest tests/test_ravel_pulse.py -q = 17 passed (3 consecutive deterministic runs); full tests/ suite = 72 passed; 28-day probe on 3 archetypes: both methods inside budget (RAVEL 447-475 of 532-588 min; PULSE 381-389), repairs fire (110-139), rechecks 54-69 with 38-43 verified outcomes logged back to the scheduler.

Stage Summary:
- Artifacts (only files owned/touched): simlib/methods/ravel.py, simlib/methods/pulse.py, tests/test_ravel_pulse.py. Exported: RAVEL_SKILL_OPTIMIZATION, RAVEL_REENCODE_CAP=0.15, RAVEL_TRANSFER_SHARE=0.20, RAVEL_TRANSFER_TOP_K=5; PULSE_SKILL_OPTIMIZATION, PULSE_REPAIR_CAP=0.25, PULSE_REQUEUE_MAX=2, REPAIR_KINDS, classify_quadrant, plan_repair.
- Declared assumptions/deviations (in module docstrings): RAVEL is fully assumption-labeled (concept-level spec only); "listening items" implemented as audio-modality items (covers all listening-skill items); transfer share 0.20 and new-card-accounting for transfer first-encounters are our choices; PULSE grammar mapping (different-item re-drill) NOT implemented — Item schema has no pattern tag and repairs must stay attributable to the failed item (test 4); grammar failures get the same-item new-context re-presentation; weak_trace deferred like consolidation_failure; repairs skipped by cap/budget are silently skipped (no queue push).
- Interface concerns for the runner agent (S5): (1) simlib/methods/__init__.py is shared and NOT modified — register/import arms directly: from simlib.methods.ravel import Ravel; from simlib.methods.pulse import Pulse. (2) RAVEL's scheduled reviews are kind="variation" records (context_review with log_sched=True) — evaluators must not treat kind=="variation" as automatically unscheduled; distinguish via scheduler call counts or the method's logged_flags. (3) PULSE verified-recheck scheduler logging uses the learner-reported grade (identical to Outcome.grade when feedback_flip_rate=0). (4) simlib/schedulers was an empty registry stub at build time; tests use a local StubScheduler and do not depend on S1's factories. Worklog copy saved as worklog_s3.md in the project root.

---
Task ID: 4 (v1.4 increment)
Agent: main (Super Z)
Task: User verdict on v1.3 received; request: optimize structure further knowing exact results, "very very cautious", document exactly how v1.3 works, build v1.4

Work Log:
- Re-grounded in the v1.3 package (read nexus_scope.py, runner.py, registry.py, memory.py, evaluator.py, env.py, spec.py, primitives.py, rwkv_instant.py, config.json, benchmark_report.md, analyze_v13.py)
- Built download/v14_methods_benchmark/ (copy of v1.3 code; v1.3 files untouched)
- Wrote pre-registration BEFORE running: config.json v14_changes (C1 diagnosis unlock / C2 stagnation timescale 5d-0.01 / C3 intake soft quota 3 cards) + v14_preregistration (H1-H5, seed_blocks calibration=20260116 confirmation=20261101, 0.0012 resolution floor, drop rules)
- nexus_scope.py: 2 new optional params (stagnation_window_days, intake_quota_cards) defaulting to EXACT v1.3 behavior; fixed quota to bound the intake loop (entry-gate alone was insufficient)
- runner.py: persist method self-report stats per career (diagnosis only); registry: nexus14_20/nostag/nointake/sweep arms
- Test hardening found real v1.3 defects: session rng seeded with id(self.method) (memory address = never reproducible) -> stable tags; 2 seed-lucky single-item assertions made seed-robust; documented in test files
- Ran: pilot, calibration block (9 arms x 96, seed 20260116, 106s), confirmation block + horizon56 + sched28 + 2 stress cells (seed 20261101, ~4 min); 85 tests pass 4x consecutive
- Analysis: scripts/v14/analyze_v14.py (career_dpi replicates v1.3 formula exactly; stratified cluster-bootstrap CIs n=2000; paired CRN diffs; method-blind flagged-skill mapping); figures_v14.py (6 PNGs); scripts copied into package/analysis/
- Caught and discarded an invalid intermediate read: verdicts accidentally computed on leftover pilot-sized v14_conf files; re-ran everything on the real confirmation block

Stage Summary:
- CONFIRMED (both seed blocks, CIs exclude 0): NEXUS-SCOPE pooled DPI edge over fsrs_meaning is small but real (+0.0007..+0.0012, +1.5-2.6%) and the +5% pre-registered rule FAILS (max +4.45% stratified) - v1.3 verdict replicated on fresh seeds
- C1 unlock generalizes: production/grammar training 0 -> ~7 events/career; flagged-strata probes: exam_crammer production 0.078 -> 0.115-0.120, weak-listener listening 0.103 -> 0.148-0.152 (v1.3: 0.088 -> 0.150)
- C2 outcome-neutral (halvings 3.31 -> 2.29/career); C3 costs ~0.0005 DPI on BOTH blocks for +9 items coverage -> DPI-optimal config = C1(+C2) without C3 (nexus14_nointake +2.95% on calibration)
- NEXUS variant ordering flips across seed blocks (plus leads cal, scope_20 leads conf; diff within +/-0.0005) - further diagnosis-parameter tuning would be seed-overfitting
- H5 confirmed: RWKV stand-in advantage shrinks 28d -> 56d (+0.00701 -> +0.00632), coverage frozen at 109 items while FSRS 336 -> 376, NEXUS -> 510
- Verdicts: H1 FAIL / H2 PASS / H3 PARTIAL (6/8, parity) / H4 FAIL / H5 PASS - all reported as-is
- Deliverables: download/v14_methods_benchmark/{benchmark_report_v1.4.md (12 sections incl. "how v1.3 works exactly"), README_v1.4.md, config.json, simulation.py, simlib/, tests/ (85 pass), 6 figs, outputs/ CSVs + verdicts_v14.json, analysis/ scripts}

---
Task ID: 2-b
Agent: general-purpose (docs + CI)
Task: Write README, docs, and AnkiDroid-style CI workflow

Work Log:
- Read worklog.md, then grounded docs in actual repo code: SessionEngine.kt (isolation guarantees, skip reasons, audit events), Budget.kt (review-time base, 0/10/20/30 levels, backlog guard), Experiment.kt (deterministic counterbalancing, held-out reserve, DAY7/DAY30, offline aggregate()), Interventions.kt (five types with costs/cooldowns); verified test names FsrsTest/BudgetTest/SelectorTest/IsolationTest/ExperimentTest/JsonRoundTripTest exist; used v14_methods_benchmark/README_v1.4.md for the simulation numbers (v1.3 README for the anchor)
- Created .github/workflows/ci.yml — byte-exact copy of the specified AnkiDroid-style pipeline (unit-tests -> build -> release -> ci-token-layer-check); validated with pyyaml (4 jobs parse) and diffed against the task text (byte-identical)
- Created README.md (root): badge, purpose paragraph, bold SCIENTIFIC INTEGRITY box, v1.4 simulation-reference section (0.04831 vs 0.04956 +2.56% DPI/h, ret d28 0.6926 vs 0.6756 within 0.02, strata gains replicated, pooled +5% rule FAILED, labeled design-references-not-predictions, v1.3 untouched anchor), architecture (core/app modules + 7 guarantee bullets), privacy (zero permissions, consent gate, local-only), CI/Release (incl. NEXUS_CI_TOKEN as Actions-secret-only + plaintext-chat PAT rotation warning), build (JDK 17, SDK 34, debug-signed tradeoff), license (MIT 2026 WasewaseX, FSRS-5 open-spaced-repetition attribution, not an AnkiDroid fork in v0.1)
- Created docs/SETUP.md: requirements (Android 8.0+/API 26+, TTS voice), install from GitHub Releases (unknown-sources steps, debug-signed note), first run (consent, budget choice, deck init), how studying works (FSRS first, interventions only in leftover time, retries never FSRS reviews, delayed assessments, attendance-gap pause), export (consent-gated anonymized JSON), delete = clear app data
- Created docs/EXPERIMENT_PROTOCOL.md: arms (deterministic counterbalance + held-out reserve, items never re-studied across arms), logging spec (reviews/interventions/budget/assessments; DPI ingredients logged, DPI computed OFFLINE), delayed assessments (+7/+30 auto-due, optional held-out novel checks, TTS 1.15 proxy limitation), pre-registered analysis rules carried from simulation (primary = delayed independent performance per active minute; success = >=5% pooled DPI with <=0.02 retention loss; per-skill strata; coverage beside rate endpoints; no post hoc changes), honest interpretation guidance (absence-of-gain verdict; per-skill targeted use labeled exploratory)
- Created docs/LIMITATIONS.md: not-an-AnkiDroid-fork (no .apkg/AnkiWeb/history migration; exact blocker named: fork build infeasible in this environment's time/size budget while keeping a reliable tested CI-buildable deliverable), FSRS simplifications (UTC epoch-day, single 10-min learning step, no fuzz, default weights), TTS 1.15 proxy, self-graded production, single learner / within-deck counterbalance, v1.4 primary + v1.3 anchor + SBD never defined/never invented, no hardcoded outcomes (tests check mechanics only)
- Created docs/SPEC_COMPLIANCE.md: 7-part spec table with implemented/partially/future status and one-line evidence each (5 implemented, 1 partially = privacy implemented + friend testing future; evidence cites core classes and all six test names)
- Secret scan of all created files: no tokens/keys/secrets (only ${{ secrets.NEXUS_CI_TOKEN }} / ${{ github.token }} references in ci.yml)

Stage Summary:
- Files created: .github/workflows/ci.yml, README.md, docs/SETUP.md, docs/EXPERIMENT_PROTOCOL.md, docs/LIMITATIONS.md, docs/SPEC_COMPLIANCE.md — nothing else in the repo touched
- ci.yml verified byte-exact vs task spec + pyyaml-valid (jobs: unit-tests, build, release, ci-token-layer-check); docs consistently carry the scientific-integrity line: no human-established superiority, simulation numbers are design references, all app outcomes from logged data only
- YAML risks for the owner: no gradle wrapper committed yet (CI uses ./gradlew — needs gradlew + gradle-wrapper.jar in repo or CI will fail); app module sources/build files were not present at write time (parallel agents) so :app:testDebugUnitTest and assembleDebug/assembleRelease depend on them landing; release job pins tag v0.1.0-alpha and falls back to gh release upload --clobber; ci-token-layer-check fails the pipeline if the NEXUS_CI_TOKEN secret is unset/invalid (by design); permissions: contents:write is only used by the release job
- Reminder propagated in README: PAT shared in plaintext chat — rotate/revoke after the NEXUS_CI_TOKEN check passes

---
Task ID: 4 (GitHub publication + APK release)
Agent: main (Super Z)
Task: Publish NEXUS-AnkiDroid to GitHub under WasewaseX, AnkiDroid-style CI, APK release

Work Log:
- Verified PAT -> account WasewaseX (id 321686523); token stored only in /home/z/my-project/.gh-token (chmod 600, outside repo), never in any tracked file
- Built full project at /home/z/my-project/NEXUS-AnkiDroid: core module (FSRS-5 port, SkillProfile, InterventionSelector, BudgetController, ExperimentManager, AuditLog, SessionEngine isolation boundary, Gson state) + 45 unit tests; app module (review flow, 5 intervention exercise types with TTS, delayed assessments 7/30d, dashboard, consent-gated export, zero permissions, 24-item original demo deck) written by parallel agent 2-a; docs+CI by agent 2-b (v1.4 = primary simulation reference, v1.3 = anchor; no superiority claims anywhere)
- Gradle 8.7 wrapper fetched from official gradle/gradle v8.7.0 tag
- Created repo WasewaseX/NEXUS-AnkiDroid via API (201); added NEXUS_CI_TOKEN Actions secret via libsodium sealed-box (201) — the "CI layer"; value file deleted after upload
- 3 commits, ALL authored+committed WasewaseX <WasewaseX@users.noreply.github.com>; git grep token scan clean; pushed via inline credential helper (token never in argv)
- CI debug loop (3 rounds, logs fetched via redirect-safe job-log fetcher): R1 compilation failure = Kotlin JVM signature clash (property budgetPct setter vs fun setBudgetPct) -> renamed fun to changeBudget + 5 call sites; R2 3 test failures = wrong test expectations (elapsed-days semantics, activeSeconds includes assessments, gap simulation ordering) -> fixed; R3 GREEN
- Verified: 45 tests / 0 failures; jobs unit-tests/build/release/ci-token-layer-check all success; Release v0.1.0-alpha created by CI with app-debug.apk; manually attached app-release.apk (debug-signed, installable) via API

Stage Summary:
- LIVE: repo https://github.com/WasewaseX/NEXUS-AnkiDroid ; release https://github.com/WasewaseX/NEXUS-AnkiDroid/releases/tag/v0.1.0-alpha (app-debug.apk 5.8MB + app-release.apk 4.7MB)
- CI: .github/workflows/ci.yml (tests -> assembleDebug/assembleRelease -> GitHub Release -> NEXUS_CI_TOKEN layer check) — every main push rebuilds and re-attaches
- HONEST SCOPE: standalone instrument implementing FSRS-5 + NEXUS-SCOPE 2.0, NOT yet a code fork of AnkiDroid (no .apkg import / AnkiWeb sync — named in docs/LIMITATIONS.md); FSRS simplifications documented; no hardcoded outcomes anywhere (tests check mechanics only)
- SECURITY: PAT was shared in plaintext chat; local copy deleted; user must rotate/revoke it (noted in README too)

---
Task ID: 5 (post-restore verification + honest re-baseline)
Agent: main (Super Z)
Task: Continue from context-restore: deliver FSRS vs NEXUS-SCOPE comparison in chat, verify real repo/CI/release state, correct stale claims

Work Log:
- Context restore carried a STALE summary (claimed /workspace/ankidroid-ci, user id 245568344, repo id 998244731, mid-push) — all wrong. Real state: project at /home/z/my-project/NEXUS-AnkiDroid, user WasewaseX id 321686523, repo id 1423146906, push long complete. Did NOT re-run repo creation
- Delivered the requested FSRS vs NEXUS-SCOPE comparison in plain text in chat, grounded line-by-line in core/ (Fsrs.kt: DSR model, R=(1+F*t/S)^-0.5, 19 FSRS-5 weights, damped+mean-reverted difficulty, post-lapse/recall/short-term stability recurrences, I=(S/F)*(Rt^(1/D)-1); Skills.kt: 5-skill confidence-weighted EMA, n/12 confidence, provisional flags; Interventions.kt: 5 types, gate sequence, deficit*confidence scoring; Budget.kt: review-time base 0/10/20/30%, reviews-first + backlog<=20; SessionEngine.kt: isolation guarantees, audited skip reasons; Experiment.kt: counterbalanced arms + 10% held-out, day7/day30) + v1.4 benchmark verdicts (FAIL on pre-registered +5% rule, +2.5% pooled DPI, targeted strata gains replicate)
- Accepted user correction: NOT an AnkiDroid fork. Verified docs already say this honestly (README line 86, docs/LIMITATIONS.md "Not yet an AnkiDroid fork" + exact blocker); GitHub repo description clean (no fork claim) — nothing to fix
- Verified live state via API: CI run on HEAD 823d449 = success (823d449 == remote main); release v0.1.0-alpha carries app-debug.apk + app-release.apk; Actions secret NEXUS_CI_TOKEN present
- Cleaned working tree: 46 files were mode-only diffs (644->755) from container copy -> set git config core.fileMode false; restored ci.yml (same mode noise) and gradle-wrapper.jar (binary refetch, 43453->43453 bytes, identical size) to HEAD; tree now 0 changes, local HEAD == remote
- Token used transiently in env vars only; no secrets written to any tracked file; token not stored anywhere on disk this session

Stage Summary:
- PUBLICATION TASK IS COMPLETE (was already complete before the stale summary): repo https://github.com/WasewaseX/NEXUS-AnkiDroid, CI green, release v0.1.0-alpha with both APKs, CI secret layer intact
- The only real gap between user expectation ("real AnkiDroid fork") and reality (standalone instrument) is documented in docs/LIMITATIONS.md and was communicated honestly in chat with the full FSRS-vs-NEXUS mechanics comparison
- OPEN ACTION FOR USER: the PAT (github_pat_11CMWI...) was shared in plaintext chat and is STILL LIVE — user should revoke/rotate it at github.com/settings/tokens; CI no longer depends on it once NEXUS_CI_TOKEN secret is confirmed (it is set and the layer-check job passes)

---
Task ID: 6 (v1.5 NEXUS-MIX benchmark)
Agent: main (Super Z)
Task: Fact-check user's FSRS/NEXUS-SCOPE article; design + build + run the mixed multi-type FSRS benchmark with fatigue/quit/return metrics (user's "less tiring" goal)

Work Log:
- Fact-checked the pasted article against core/ code: TRUE on all load-bearing claims (EMA math 0.7*0.70+0.3*0.30=0.58 correct, budget 20min*20%=4min correct, gates/isolation/numbers correct); noted the app v0.1 has no optimizer UI (default weights) and the article carried decorative AI-generated citations
- Designed NEXUS-MIX per user brief: multi-type cards (meaning/listening/production/grammar-rule) on the SAME unmodified v1.4 FSRS wrapper; bio-inspired behavior TRUTH layer: two-process fatigue (K_FAT 0.024, kind costs 1.0-1.6, tau 0.9d), quit hazard (H0*(t/15)^0.7 * fatigue * monotony * valence), morning return model (base 0.94, gap/valence/habit terms); grammar-rule round-robin (rules of 20) = "grammar unique"; goal-stop pacing at 75% budget; dishabituation interleave (streak cap 3); diagnosis-weighted ordering (EMA 0.3, deficit 0.55, mult 1.5)
- Built download/v15_nexus_mix_benchmark/: config15.json (preregistration BEFORE runs), sim15/{behavior,mix}.py, runner15.py (return gate + QuitAwareSessionContext spend() hook + career-wide Accumulators), tests15.py (14 tests, all pass), analyze15.py (paired CRN diffs, cluster bootstrap n=2000 on learner), figures15.py (2 figs), README_v1.5.md
- Bugfixes during build: MemoryTruthFatigue penalty must hit _p_correct (learn=True only, probes exempt); valence auto-fed from truth.sample_practice (methods cannot skip it); context-owned skill-streak counter; career-wide Accumulators (per-session would zero study_minutes/DPI)
- Pilot: calibrated H0 0.020 -> 0.017 to put multitype quit at 0.327 in declared band [0.25,0.35], FROZEN; recall_only structural 97% quit (single-modality monotony) kept and documented as honest consequence
- Ran calibration (20260116) + confirmation (20261101) blocks: 288 careers each, 11520 probe rows each, ~6s/block; analysis + verdicts + 2 figures

Stage Summary:
- H2 (user's goal, PRIMARY): PASS - sessions -3.02 min (CI [-3.22,-2.80]), gap -0.103d (CI [-0.161,-0.044]), quit 0.257 vs 0.376, open rate 0.619 vs 0.569
- H1: FAIL on the letter: DPI +13.2% (CI [+5.3,+14.0]) clears +5% BUT ret28 -0.0225 breaches 0.02 tolerance by 0.0025; H3 FAIL (same); H4 FAIL (per-session throughput ratio 0.768)
- H5 exploratory: naive multi-type FSRS = -48.7% DPI/hour vs recall-only (content diversity WITHOUT session intelligence is a trap under fatigue dynamics); mix recovers ~half and buys engagement
- Cross-seed replication: calibration signs identical (+15.4%, -2.97min, -0.113d, quit 0.23 vs 0.38)
- Deliverables: download/v15_nexus_mix_benchmark/ (config+code+tests+outputs+verdicts+figs+README_v1.5.md)

---
Task ID: 7 (v1.6 NEXUS-MIX 2.0: review fixes + retention-guarded pacing)
Agent: main (Super Z)
Task: Address the external review of v1.5: (1) separate planned stops from premature quits, (2) stress-test the behavior model, (3) tune the stopping policy until retention is back inside the 0.02 margin while keeping engagement wins

Work Log:
- Wrote config16.json BEFORE any run: 7-policy grid (goal fraction x due-core protection), declared selection rule (calibration block, max ret28 diff among eligible), 8 stress scenarios + hard_skeptical, hypotheses K1-K8, floors carried from v1.5
- Built download/v16_nexus_mix2_benchmark/: sim16/behavior_ext.py (BehaviorState16 frustration switch + apply_scenario deep-copy patching), sim16/policy.py (_InstrumentedBase counters + NexusMix2 with due_core_protect: goal line never truncates due reviews, only gates new intake), runner16.py (end reasons premature_quit/budget/planned_goal/work_complete + per-session rows + exposure-adjusted quit metrics + due_completion), run16.py stage driver, analyze16.py, figures16.py, tests16.py
- Bugfix during build: intake must be planned BEFORE the due drain (v1.5 order) or diagnosis state diverges -> v15_replica now reproduces v1.5 EXACTLY (16/16 tests pass, incl. bit-exact replication test)
- Ran calibration grid (7 policies x 3 arms x 96 careers); ALL eligible; rule froze p075_prot (goal 0.75 + due-core protection; the only cell with POSITIVE calibration ret28 diff +0.015)
- Ran confirmation ONCE: base + 8 scenarios + goal100 ablation (10 cells x 288 careers); analysis + verdicts + 3 figures + README_v1.6.md

Stage Summary:
- K1 LEARNING PASS: DPI/hour +11.2% (CI [+2.4,+11.4]) AND ret28 diff -0.0001 (v1.5's -0.0225 breach eliminated); K2 ENGAGEMENT PASS: sessions -2.31 min (CI [-2.55,-2.07]), gap -0.117 d; K3 PASS; K4 PASS on protection (due completion +0.029 vs multitype; enc/session ratio 0.825 reported, no pass/fail)
- K5 PASS: premature quit -9.5pp AND exposure-adjusted quit intensity -0.30/100min (the honest metric); K6: quit reduction survives ALL 9 scenarios incl. no_monotony and both skeptical cells; session shortening is MECHANICAL pacing (hard_skeptical floor -2.41 min >= base -2.31) and is labeled as such
- K7 ablation: without the goal line, retention STILL breaches (-0.0265) and quitting does not drop -> pacing+protection is the load-bearing component; K8: per ENROLLED day, mix2 and multitype beat recall-only (recall-only's DPI/hour win inverts on calendar time)
- Replication audit EXACT (multitype/recall arms reproduce v1.5 confirmation to all decimals)
- Deliverables: download/v16_nexus_mix2_benchmark/ (config+code+tests+outputs+verdicts+3 figs+README_v1.6.md)

---
Task ID: 17
Agent: main (Super Z)
Task: v1.7 — two-arm memory benchmark (normal AnkiDroid vs NEXUS-TRIAD scheduling) + real-data evidence gate for a TRIAD-native memory model

Work Log:
- Executed user directives: "now same memory benchmarks but simulate using of normal anki droid and nexus triad ones no hukkucination or guesses evidence based result" + "build toward a TRIAD-native memory model only when you have evidence showing which aspect of human recall the current FSRS-centered approach fails to capture. Then compare the new model against FSRS using real, held-out outcomes."
- Built download/v17_nexus_triad_benchmark on top of the UNMODIFIED v1.4/v1.5/v1.6 harness: Arm A fsrs_multitype (normal AnkiDroid, verbatim sim16), Arm B nexus_triad (TRIAD owns ordering/pacing/cold-start; FSRS-4.5 wrapper stays the interval authority, alpha=0 by construction; knobs FROZEN from v1.6 frozen policy p075_prot — no v1.7 tuning).
- Transparent logging scheduler proxy injected via FACTORIES patch (log-then-delegate, zero RNG) -> per-review event rows (r_before, s_before, grade, context).
- Ran 7 cells (base + 2 ablations + 4 stress scenarios) x 3 reps x 32 learners x 2 arms = 1,344 careers; analyze17.py produced verdicts_v17.json.
- REPLICATION AUDIT: v17 fsrs_multitype careers bit-identical to v16 confirmation base (dpi 0.12799==0.12799, ret 0.58187==0.58187, exact=true). Fixed a glob bug that had read only reps 1-2 (rep-0 chunk writes untagged files).
- RESULTS (sim): P1 no-harm PASS (ret28 diff -0.0008); P2 DPI/h +10.2% [CI +0.97,+10.8]; P4 due completion +0.0275 [+0.0125,+0.0431], quits -9.67pp, intensity -0.33/100min, sessions -2.21min, gap -0.117d; P3 attribution: risk-ordering layer ~0 (DPI -0.9% [CI -3.3,+2.7]), pacing carries the effect; P6 stress: quit reduction survives all 5 scenarios, session reduction is mechanical pacing (hard_skeptical -2.40 ~= base -2.21), all ret diffs within +-0.02 (worst -0.0187 under no_fatigue_quit).
- REAL DATA: downloaded the public Duolingo HLR learning-traces dataset (Settles & Meeder ACL 2016, Harvard Dataverse doi:10.7910/DVN/N8XJME, 379,004,009 bytes) via parallel ranged download after two stall failures; md5 VERIFIED 0a1cae5eb7ad4b0bd9c0de91d74fcced.
- prep_real.py (declared preprocessing): learning_language=='en', >=40 rows, hash-subsample 2,400 users -> 558,148 events over 2,516... (2,512) lexemes; sessions = 30-min gaps; grade mapping p_recall -> 1..4 declared; user-level splits train 1,456 / cal 479 / test 465 (seed 20261101).
- fit_real.py: exact FSRS-5 (py-fsrs 5.1.3 formulas, 19 params) ported to torch with per-user BPTT, Adam 4 epochs on train users; M0 global logit calibration (a,b) on train; dContext = logistic contextual correction (session position, elapsed session min, same-day workload, absence gap) fitted on train only; alpha selected on CAL users only -> alpha*=0.75 (cal log-loss 0.33575 vs 0.33692 at alpha=0).
- eval_real.py: ONE frozen evaluation on test users. RESULT: held-out paired per-user log-loss gain +0.0007, 95% CI [-0.0010,+0.0023] CROSSES ZERO for both fitted and default FSRS-5 weights -> GATE CLOSED: no TRIAD-native memory model justified; alpha=0 stands.
- STRATA EVIDENCE (real, held-out): small monotone residual decline across session position (+0.0444 -> +0.0239) and same-day workload (+0.0446 -> +0.0225) — the real fatigue/workload signature TRIAD targets; absence adds no signal beyond FSRS's own interval input.
- figures17.py -> fig1 (two-arm), fig2 (attribution CIs), fig3 (real strata), fig4 (alpha gate); benchmark_report_v1.7.md written with full honesty labels; tests17.py 8/8 pass.
- Repo: fast-forwarded local NEXUS-AnkiDroid to origin/main (507dd51, the v1.8 pivot pushed by the release pipeline); added benchmarks/v17_evidence_benchmark/ (report, README, code, config, verdicts, figures, real-data scripts); committed.

Stage Summary:
- Two-arm answer (evidence-based, simulation): TRIAD-owned scheduling is retention-clean (-0.0008) and more efficient (+10.2% DPI/h, fewer quits) BUT the benefit is entirely session control (pacing + due-core protection); context-risk ordering adds nothing measurable.
- Real-data answer (evidence-based): a small real fatigue/workload residual signature exists in FSRS-centered prediction (~2.2 pp relative each), but a TRIAD-native memory correction does NOT beat FSRS-5 on held-out real outcomes (CI crosses 0) -> per the user's own gate, DO NOT build a TRIAD-native memory model on current evidence; alpha=0; FSRS-5 remains the memory model.
- Refactor scope justified by evidence: fix the four integration defects + wire session control/ordering behind a feature flag; do NOT touch interval math.
- Token handled as runtime secret only (env var + git credential helper at push time); never written to any file.
