# Limitations (v0.2) — the honest list

## The real AnkiDroid fork now EXISTS — with these caveats

As of v0.2, the project maintains a **real fork of AnkiDroid** ([WasewaseX/Anki-Android](https://github.com/WasewaseX/Anki-Android)) in which **NEXUS-TRIAD v1.8 replaces the bare FSRS review entry** (PRs #1–#4 merged inside the fork as the release gate; APK built by CI and published at the fork's Releases). Honest caveats about that fork build:

- **FSRS remains the authoritative memory engine inside TRIAD** — this is the NEXUS-TRIAD spec itself (component 2): the Rust/Anki backend schedules intervals exactly as before; TRIAD adds cold-start priors, the contextual recall predictor `P_hybrid = sigmoid(logit(P_FSRS) + alpha*delta)` (alpha gated at zero until out-of-sample validation), and session-controller state.
- The fork's engine is a **pure-Kotlin port** of the v1.8 simulation engine in `benchmarks/v18_nexus_triad_benchmark/`; the per-card P_FSRS input currently falls back to the engine's shared-prior estimate until backend retrievability wiring lands.
- The released APK is **debug-signed** (installable, but not Play-Release-signed).

## The standalone app (this repo, v0.1)

The standalone app in `app/` remains available and is **NOT a code fork of the AnkiDroid APK**:

- no `.apkg` import
- no AnkiWeb sync
- no migration of existing review histories

## FSRS simplifications

- **UTC epoch-day resolution** — scheduling granularity is whole days in UTC; no intra-day timestamps drive scheduling.
- **Single 10-minute intra-day learning step** — no multi-step learning schedules.
- **No fuzz** — intervals are deterministic.
- **Default FSRS-5 weights** — there is no per-user parameter optimization UI.

## Measurement proxies

- **TTS-based listening is a proxy for real varied audio**; the rate-1.15 setting is a weak "unfamiliar voice" manipulation.
- **Production scoring is self-graded** (Correct / Partial / Wrong) against a model answer; there is no automated rubric.

## Experimental scope

- **Single learner per install.**
- Counterbalancing is **within-deck, not within-population**; the sample size is one per device.
- Real-world conclusions from a single-device run are case studies, not population-level evidence.

## Benchmark lineage

- **v1.4 exists and is the primary simulation reference**; **v1.3 remains untouched as the prior anchor**.
- **"SBD" was never defined by the user and was never invented** — it appears nowhere as a method and is excluded everywhere.

## No hardcoded outcomes anywhere

There are no hardcoded learning outcomes in the app or its tests. Assertions in the test suite check **mechanics** — FSRS isolation (`IsolationTest`), budget semantics (`BudgetTest`), experiment assignment (`ExperimentTest`), selector rules (`SelectorTest`), FSRS-5 behavior (`FsrsTest`), state round-tripping (`JsonRoundTripTest`) — **never learning effects**. All reported outcomes are computed only from logged data.
