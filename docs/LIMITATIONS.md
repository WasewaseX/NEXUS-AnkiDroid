# Limitations (v0.1) — the honest list

## Not yet an AnkiDroid fork

v0.1 is a **standalone app** implementing the FSRS-5 algorithm and the established NEXUS-SCOPE 2.0 design. It is **NOT yet a code fork of the AnkiDroid APK**:

- no `.apkg` import
- no AnkiWeb sync
- no migration of existing review histories

True AnkiDroid integration is the designated next milestone. The exact blocker, stated honestly: **a full AnkiDroid fork build could not be completed inside this environment's time/size budget while preserving a reliable, tested, CI-buildable deliverable.** The standalone path was chosen to still deliver a working, installable instrument.

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
