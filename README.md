# NEXUS-AnkiDroid

![CI](https://github.com/WasewaseX/NEXUS-AnkiDroid/actions/workflows/ci.yml/badge.svg)

NEXUS-AnkiDroid is a local-first Android experiment app that keeps pure FSRS-5 scheduling intact and adds the established NEXUS-SCOPE 2.0 adaptive English-learning layer as an optional, budget-controlled module, to collect real-world evidence on whether the layer's gains justify its extra time — Control (FSRS only) vs Treatment (FSRS + NEXUS) within the same app via counterbalanced item assignment.

> **SCIENTIFIC INTEGRITY — read this first.**
> NEXUS-SCOPE's superiority over plain FSRS has **NOT** been established in humans. The simulation results below are **model-based, not proof**. This app is an evidence-collection instrument: it contains **no hardcoded expected improvements**, and it computes outcomes **only from logged data**.

## Simulation reference (benchmark v1.4 — design inputs, not predictions)

The app's design is informed by an executed, reproducible Monte Carlo benchmark: the **English-Learning Methods Benchmark v1.4**, a cautious structural optimization of v1.3 under a calibration/confirmation seed split. v1.3 remains untouched as the prior anchor. Headline confirmation-block results (96 careers/arm, paired CRN):

| Arm | Pooled DPI/hour | vs fsrs_meaning | Retention d28 |
| --- | --- | --- | --- |
| fsrs_meaning (FSRS baseline) | 0.04831 | — | 0.6926 |
| nexus_scope_20 (NEXUS-SCOPE 2.0 @ 20% budget) | 0.04956 | +2.56% | 0.6756 |

- Retention d28: 0.6926 vs 0.6756 — **within the pre-registered 0.02 tolerance**.
- Targeted probe gains on flagged strata **did replicate**: production **+19–48%** relative, grammar **+16–17%**, weak-listener listening **+47%** (measured on held-out reserve items).
- The pre-registered pooled success rule (**+5% DPI with retention within tolerance**) **FAILED** on a fresh confirmation seed — replicated from v1.3.

**These numbers are simulation outputs used as design references, NOT predictions for the app experiment.** No benchmark number is built into the app; every app-side outcome is computed only from logged data (see [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md)).

## Architecture

Two Gradle modules:

- **`core`** — pure Kotlin (no Android dependencies), fully unit-tested:
  - FSRS-5 port (`fsrs/Fsrs.kt`, verified by `FsrsTest`)
  - five-skill NEXUS profile (`skills/SkillProfile`)
  - intervention selector (`engine/InterventionSelector`, verified by `SelectorTest`)
  - budget controller (`budget/BudgetController`, verified by `BudgetTest`)
  - experiment manager (`experiment/ExperimentManager`, verified by `ExperimentTest`)
  - audit log (`audit/AuditLog`)
  - session engine (`session/SessionEngine`, isolation verified by `IsolationTest`; state persistence verified by `JsonRoundTripTest`)
- **`app`** — Android shell: review UI, the five NEXUS intervention exercise types with TTS listening, dashboard, JSON export.

Key guarantees (enforced in code and unit-tested):

- **FSRS owns all scheduling.** Only real, learner-initiated reviews touch FSRS state — `SessionEngine.recordReview` is the single scheduling path (enforced and unit-tested in `IsolationTest`).
- **Retries and exercises never become FSRS reviews.** `recordExercise` / `recordAssessment` never call `Fsrs.review`: no review-log entry, no stability/difficulty/due change.
- **Scheduled reviews are protected from enrichment.** No intervention is selected while any FSRS review is still due.
- **Backlog guard.** Enrichment is blocked while overdue items exceed the threshold (default 20).
- **Attendance-gap tolerance.** Interventions pause after 3 inactive days.
- **Budget: 0 / 10 / 20 / 30 %** (the pre-registered levels). The daily enrichment allowance is a percentage of the time actually spent on real FSRS reviews; enrichment consumes but never grows the allowance, so the loop always terminates (`BudgetTest`).
- **Every decision is audited** (`AuditLog`): FSRS reviews, interventions, skipped enrichment with the exact reason, delayed assessments.

## Privacy

- **Zero permissions** — the app does not declare the `INTERNET` permission at all.
- **Local-only storage** — the entire state is one JSON document on the device.
- **Consent gate before export** — export is locked until the learner consents.
- **Anonymized JSON export.**
- **Deletion = clear app data** (or uninstall). No cloud backend in v1.

## CI / Release

The GitHub Actions workflow (`.github/workflows/ci.yml`, AnkiDroid-style Gradle pipeline) runs:

1. **Unit tests (JVM)** — `:core:test` and `:app:testDebugUnitTest`; test results uploaded as artifacts.
2. **Build** — `assembleDebug assembleRelease` on JDK 17 (Temurin); debug and release APKs uploaded as artifacts.
3. **Release** — on pushes to `main`, a GitHub Release `v0.1.0-alpha` is created (or updated) with the APKs attached; the release APK is **debug-signed**, so it is directly installable.
4. **NEXUS_CI_TOKEN layer check** — verifies that the PAT-based repository secret can read the repo (expects HTTP 200).

The `NEXUS_CI_TOKEN` repository secret is the PAT-based CI layer. It is stored only as an Actions secret — never in code, never in any file of this repository.

> **WARNING — rotate/revoke the PAT.** The PAT used to set up this repository was shared in plaintext chat. After confirming the `NEXUS_CI_TOKEN` layer check passes, **rotate or revoke it** and replace the secret with a freshly generated fine-grained token with the minimum required scopes.

## Build

Requirements: JDK 17, Android SDK 34.

```bash
./gradlew assembleDebug       # debug APK
./gradlew assembleRelease     # release APK (debug-signed; see below)
./gradlew :core:test          # core unit tests
```

The release APK is **debug-signed** so it is directly installable without any signing setup. This is a documented tradeoff for a research instrument: installable everywhere, but not a Play-Store-style signed release.

## License

MIT — Copyright (c) 2026 WasewaseX. FSRS-5 algorithm attribution: the open-spaced-repetition reference ports (MIT-licensed).

**v0.2 update:** a **real AnkiDroid fork now exists** — [WasewaseX/Anki-Android](https://github.com/WasewaseX/Anki-Android) — with **NEXUS-TRIAD v1.8 replacing the bare FSRS review entry** (merged via in-fork PRs #1-#4 as the release gate; real APK published on the fork's Releases). FSRS remains the authoritative memory engine *inside* TRIAD, per the TRIAD spec. The v1.8 benchmark (7 distinct arms incl. RWKV-instant and SM-20; TRIAD +11.41% DPI/h, retention +0.0054, sessions -2.72 min, quits 26.2% vs 37.6%) lives in [benchmarks/v18_nexus_triad_benchmark/](benchmarks/v18_nexus_triad_benchmark/README_v1.8.md) — **simulation evidence, not real-learner evidence**. This standalone app remains the instrument repo; see [docs/LIMITATIONS.md](docs/LIMITATIONS.md).
