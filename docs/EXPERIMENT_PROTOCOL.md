# Real-World Experiment Protocol (v0.1)

This is the protocol for the real-world evidence collection performed by this app. The analysis rules at the bottom are **carried from the simulation benchmark (v1.4)** and must **NOT be moved after data collection**.

## Arms

Within-app counterbalanced design. The same deck is split **deterministically** (`ExperimentManager.assignItems`: items sorted, held-out reserve removed, remaining items paired, CONTROL/TREATMENT alternating across pairs to cancel position effects) into:

- **CONTROL** — pure FSRS. No NEXUS activity ever touches these items.
- **TREATMENT** — FSRS + NEXUS-SCOPE at the chosen budget (0/10/20/30%).
- **Held-out reserve** — never studied at all; reserved for novel-item delayed checks (transfer / unfamiliar listening).

Each item belongs to exactly one arm and is **never re-studied in the other condition**.

## Logging (exportable JSON)

Every event needed to recompute the endpoints offline is logged:

- **Every FSRS review**: rating, FSRS state before the review, elapsed/scheduled days, seconds spent.
- **Every NEXUS intervention**: type, rationale, duration, outcome.
- **Budget accounting**: review seconds (the budget base), enrichment seconds, remaining allowance.
- **Delayed assessments**: kind (DAY7 / DAY30), skill, outcome, seconds.
- **Audit log**: every decision, including skipped enrichment with its exact reason.

The DPI-equivalent ingredients — delayed independent performance (including production and listening) at day 7/30, and active seconds per arm — are logged. **DPI itself is computed OFFLINE from exports.** Nothing in the app hardcodes, targets, or predicts any improvement.

## Delayed assessments

- Automatically due at **first-encounter +7 days** and **+30 days** (`ExperimentConfig.assessmentDays`).
- **Held-out novel-item checks are optional** extras: short checks on never-studied reserve items, measuring transfer and unfamiliar listening.
- **Listening assessments use TTS at rate 1.15** as an unfamiliar-audio proxy. This is a weak manipulation and a known limitation ([LIMITATIONS.md](LIMITATIONS.md)).

## Pre-registered analysis rules (carried from the simulation — do NOT move after data collection)

- **Primary comparison**: delayed independent English performance per active minute (DPI ingredients), CONTROL vs TREATMENT.
- **Pre-registered success rule**: pooled DPI improvement **≥ 5%** with absolute delayed retention loss **≤ 0.02**.
- Report **per-skill strata** (especially weak listeners) alongside pooled results.
- Report **coverage beside any rate-based endpoint**.
- **No post hoc threshold changes.**

## Honest interpretation guidance

- **Absence of a significant gain with present overhead means the layer is not justified at that budget.** That is a publishable result, not a failure of the app.
- Per-skill gains (e.g., listening for weak listeners) may justify **targeted** use even when pooled DPI fails the pre-registered rule — but such claims must be labeled **exploratory**.
