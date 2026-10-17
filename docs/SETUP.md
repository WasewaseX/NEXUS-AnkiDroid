# Setup & User Guide

NEXUS-AnkiDroid is a single-learner, local-only app. Everything happens on your device; the app requests zero permissions (it does not even declare `INTERNET`).

## Requirements

- **Android 8.0+ (API 26+)**
- **A TTS voice installed** (e.g., Google Text-to-Speech with an English voice) — required for listening items and listening assessments.
- Free storage for one local JSON state file (small; grows with your review history).

## Install the APK

1. Go to the [GitHub Releases page](https://github.com/WasewaseX/NEXUS-AnkiDroid/releases) and download the release APK (asset of the `NEXUS-AnkiDroid-release` artifact, e.g. `app-release.apk`).
2. Android blocks installs from outside the Play Store by default. When prompted, allow **"Install unknown apps"** for the app you used to download/open the APK (browser or file manager): *Settings → Apps → Special access → Install unknown apps*.
3. Open the APK and tap **Install**.

Notes:

- The release APK is **debug-signed** so it is directly installable; this is a documented tradeoff (see the README and [LIMITATIONS.md](LIMITATIONS.md)).
- The app requests **no permissions** during or after install.

## First run

1. **Consent gate.** Before any experiment activity or export, the app asks for your consent. Nothing is exported without it.
2. **Choose the enrichment budget.** This is the NEXUS-SCOPE share of your FSRS review time: **0 / 10 / 20 / 30 %** (the pre-registered levels). `0%` means pure FSRS — the NEXUS layer never fires.
3. **Initialize the deck** with your item list. Items are deterministically split into CONTROL (pure FSRS), TREATMENT (FSRS + NEXUS), and a held-out reserve (see [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)).

## How studying works

- **Scheduled FSRS reviews always come first.** Rate each item (Again / Hard / Good / Easy). Every review is logged with its rating, FSRS state before the review, scheduled days, and seconds spent.
- **NEXUS interventions only fill leftover time**, and only when *no* reviews are due, the backlog is within its threshold, and the enrichment budget is not exhausted. At most 2 interventions per day (max 1 per type): listening input (TTS, transcript hidden until after your attempt), production-first, grammar repair, transfer task, prediction-error repair. Each offered intervention shows its rationale.
- **Retries and exercises never become FSRS reviews** — they cannot change your schedule. This is enforced in code and pinned by unit tests.
- **Delayed assessments become due automatically** at first encounter +7 days and +30 days. They are short checks and are part of the experiment evidence.
- **After 3 inactive days**, interventions pause (attendance-gap tolerance) until you resume.

## How to export

1. Open the dashboard and tap **Export JSON** (available only after the consent gate).
2. The export is a single anonymized JSON file written via the system share/save sheet. No network is involved — the app has no `INTERNET` permission.

The export contains everything needed to recompute the experiment endpoints offline: reviews, interventions, budget accounting, assessments, and the audit log.

## How to delete all data

All data lives in one local JSON document. To delete everything: *Android Settings → Apps → NEXUS-AnkiDroid → Clear data* (or simply uninstall the app). There is no cloud copy.
