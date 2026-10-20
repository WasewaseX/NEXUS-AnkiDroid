# v1.7 Evidence Benchmark — normal AnkiDroid (stock FSRS) vs NEXUS-TRIAD + real-data α-gate

Full report: [`benchmark_report_v1.7.md`](benchmark_report_v1.7.md).
Companion of `../v18_nexus_triad_benchmark` (the v1.8 APK scheduling package);
v1.7 is the **evidence layer**: (a) a two-arm paired-CRN scheduling simulation
with a bit-exact replication audit against the v1.6 confirmation block, and
(b) a REAL-learner-data gate (Duolingo HLR public release, md5-verified,
English learners, user-level held-out splits) that decides whether any
TRIAD-native memory-model component is justified. **Verdict: it is not —
the held-out CI crosses zero, α stays 0, FSRS-5 remains the memory model.**

Key numbers (simulation, paired, 96 careers/arm, seed 20261101):
ret@28 diff −0.0008 (no-harm PASS), DPI/hour +10.2% [CI +1.0, +10.8],
sessions −2.21 min, premature quits −9.7 pp; attribution: session-control
layer carries it, risk-ordering ≈ 0.

Key numbers (real data, 2,400 English-learner users, 558k events):
small real contextual residual (~2.2 pp relative decline across session
position and workload), but held-out log-loss gain +0.0007
[−0.0010, +0.0023] — crosses zero → gate closed.

Layout note: this directory is a curated copy; the runnable harness tree
(`sim17/`, `outputs/raw/`) lives in the local benchmark workspace alongside
the v1.4/v1.5/v1.6 packages it imports unmodified (`sim15`, `sim16`, `simlib`).
`scripts/` contains the real-data pipeline (download with md5 check,
preprocessing, FSRS-5 fit, frozen held-out evaluation, figures).
`tests17.py` — 8 mechanism tests (replication, due-core protection, risk
ordering, α-gate sanity, null-verdict guard, prereg floors).
