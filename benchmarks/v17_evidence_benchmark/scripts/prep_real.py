"""prep_real.py — prepare the Duolingo HLR real-learner dataset (v1.7 real-data arm).

SOURCE (real, public): Settles & Meeder 2016 learning-traces release, Harvard
Dataverse doi:10.7910/DVN/N8XJME, file settles.acl16.learning_traces.13m.csv.gz
(md5-verified 0a1cae5eb7ad4b0bd9c0de91d74fcced). 13M rows of REAL spaced
repetition practice. Each row: one (user, lexeme, lesson) practice event with
p_recall = fraction of exercises recalled correctly in that lesson.

DECLARED PREPROCESSING (written before any outcome analysis):
1. Filter learning_language == 'en'  -> learners STUDYING ENGLISH (the
   benchmark's "identical English material" requirement, on real data).
2. Keep users with >= 40 practice rows (enough events for per-user context).
3. Deterministic subsample of at most 2400 users: sha1(user_id) mod 10000
   bucketing with a declared seed; users assigned to splits by the same hash:
   train 60% / calibration 20% / test 20% (user-level split — the test users
   are NEVER used for fitting or alpha selection).
4. Sessions: consecutive events of a user with timestamp gap > 1800 s (30
   min) start a new session (declared).
5. Per-event context features (computed from the log ONLY):
   - position_in_session  (0-based index within the session)
   - elapsed_session_min  (t - session_start) / 60
   - events_so_far_today  (rows already logged by this user this UTC day)
   - days_since_prev_session (calendar-day gap to the previous session)
   - session_idx_that_day
   - delta_days = delta / 86400 (FSRS input)
   - history_seen, history_correct (FSRS input / cold-start priors)
6. Grade mapping for FSRS-5 state (declared BEFORE fitting):
   G=4 if p_recall == 1.0; G=3 if >= 0.8; G=2 if >= 0.6; else G=1.
7. Prediction targets start at the SECOND event of each (user, lexeme)
   sequence (the first event initializes the FSRS state), matching the
   srs-benchmark convention.

Output: data/real_events.parquet (+ a small JSON audit).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

GZ = "/home/z/my-project/data/settles.acl16.learning_traces.13m.csv.gz"
OUT_DIR = "/home/z/my-project/data"
OUT_PARQUET = os.path.join(OUT_DIR, "real_events.parquet")
AUDIT = os.path.join(OUT_DIR, "real_prep_audit.json")

LANG = "en"          # learners studying English
MIN_ROWS = 40        # min practice rows per user
MAX_USERS = 2400     # deterministic subsample cap
SEED = 20261101      # declared seed for the hash subsample
SESSION_GAP = 1800   # seconds; > this starts a new session


def split_of(user_id: str) -> str:
    h = int(hashlib.sha1((str(SEED) + "|" + user_id).encode()).hexdigest(), 16)
    b = h % 10000
    if b < 6000:
        return "train"
    if b < 8000:
        return "cal"
    return "test"


def main() -> None:
    t0 = time.time()
    keep_users: dict[str, int] = {}
    # pass 1: count rows per user (en learners only)
    for chunk in pd.read_csv(GZ, compression="gzip", usecols=["user_id",
                                                             "learning_language"],
                             chunksize=2_000_000):
        sub = chunk[chunk.learning_language == LANG]
        vc = sub.user_id.value_counts()
        for u, n in vc.items():
            keep_users[u] = keep_users.get(u, 0) + int(n)
    elig = {u: n for u, n in keep_users.items() if n >= MIN_ROWS}
    print(f"pass1 done in {time.time()-t0:.0f}s: {len(keep_users)} en users, "
          f"{len(elig)} eligible (>= {MIN_ROWS} rows)", flush=True)

    # deterministic subsample: order by hash, take first MAX_USERS
    order = sorted(elig.keys(), key=lambda u: hashlib.sha1(
        (str(SEED) + "|order|" + u).encode()).hexdigest())
    picked = order[:MAX_USERS]
    picked_set = set(picked)
    splits = {u: split_of(u) for u in picked}

    # pass 2: collect rows of picked users
    cols = ["p_recall", "timestamp", "delta", "user_id", "learning_language",
            "ui_language", "lexeme_id", "history_seen", "history_correct",
            "session_seen", "session_correct"]
    frames = []
    for chunk in pd.read_csv(GZ, compression="gzip", usecols=cols,
                             chunksize=2_000_000):
        frames.append(chunk[chunk.user_id.isin(picked_set)])
    df = pd.concat(frames, ignore_index=True)
    del frames
    df = df[df.learning_language == LANG].copy()
    print(f"pass2 done in {time.time()-t0:.0f}s: {len(df)} en rows for "
          f"{df.user_id.nunique()} users", flush=True)

    # session/context features per user
    df = df.sort_values(["user_id", "timestamp", "lexeme_id"]).reset_index(drop=True)
    ts = df.timestamp.values
    uid = df.user_id.values
    day = (ts // 86400).astype(np.int64)
    session_id = np.zeros(len(df), dtype=np.int64)
    prev_ts = {}
    session_counter = {}
    last_session_day = {}
    pos_in_sess = np.zeros(len(df), dtype=np.int64)
    sess_start = np.zeros(len(df), dtype=np.int64)
    events_today = np.zeros(len(df), dtype=np.int64)
    day_count = {}
    lex_count_in_sess = {}

    uid_key = pd.factorize(uid)[0]
    prev_pos = {}
    prev_sess_start = {}
    for i in range(len(df)):
        k = uid_key[i]
        t = int(ts[i])
        d = int(day[i])
        p = prev_ts.get(k)
        if p is None or (t - p) > SESSION_GAP:
            session_counter[k] = session_counter.get(k, 0) + 1
            pos_in_sess[i] = 0
            sess_start[i] = t
            last_session_day[k] = d
        else:
            pos_in_sess[i] = prev_pos[k] + 1
            sess_start[i] = prev_sess_start[k]
        prev_pos[k] = pos_in_sess[i]
        prev_sess_start[k] = sess_start[i]
        session_id[i] = session_counter[k]
        prev_ts[k] = t
        cnt = day_count.get((k, d), 0)
        events_today[i] = cnt
        day_count[(k, d)] = cnt + 1
    df["session_id"] = session_id
    df["position_in_session"] = pos_in_sess
    df["elapsed_session_min"] = (ts - sess_start) / 60.0
    df["events_so_far_today"] = events_today

    # days since previous session (calendar-day gap)
    prev_session_day = {}
    gap = np.full(len(df), np.nan)
    for i in range(len(df)):
        k = uid_key[i]
        d = int(day[i])
        if pos_in_sess[i] == 0:
            gap[i] = d - prev_session_day[k] if k in prev_session_day else 0.0
            prev_session_day[k] = d
        else:
            gap[i] = 0.0
    df["days_since_prev_session"] = gap
    df["split"] = [splits[u] for u in df.user_id]
    df["y"] = df["p_recall"].astype(float)
    df["n_ex"] = df["session_seen"].astype(int)

    # grade mapping (declared)
    pr = df.y.values
    grade = np.ones(len(df), dtype=np.int64)
    grade[pr >= 0.6] = 2
    grade[pr >= 0.8] = 3
    grade[pr == 1.0] = 4
    df["grade"] = grade

    keep = ["user_id", "lexeme_id", "timestamp", "delta", "y", "n_ex", "grade",
            "history_seen", "history_correct", "session_seen", "session_correct",
            "position_in_session", "elapsed_session_min", "events_so_far_today",
            "days_since_prev_session", "session_id", "split"]
    out = df[keep].reset_index(drop=True)

    # mark first event per (user, lexeme): init row (no prediction)
    out = out.sort_values(["user_id", "lexeme_id", "timestamp"]).reset_index(drop=True)
    out["seq_idx"] = out.groupby(["user_id", "lexeme_id"]).cumcount()
    out.to_parquet(OUT_PARQUET, index=False)

    audit = dict(
        source=os.path.basename(GZ), md5="0a1cae5eb7ad4b0bd9c0de91d74fcced",
        learning_language=LANG, min_rows=MIN_ROWS, max_users=MAX_USERS,
        n_users_total_en=int(len(keep_users)), n_users_eligible=int(len(elig)),
        n_users_picked=int(out.user_id.nunique()),
        n_rows=int(len(out)),
        rows_by_split=out.groupby("split").size().to_dict(),
        users_by_split=out.groupby("split").user_id.nunique().to_dict(),
        n_lexemes=int(out.lexeme_id.nunique()),
        session_gap_s=SESSION_GAP, seed=SEED,
        wall_seconds=round(time.time() - t0, 1),
        note="real learner data; rows = practice events; prediction targets "
             "are events with seq_idx >= 1",
    )
    with open(AUDIT, "w") as f:
        json.dump(audit, f, indent=2)
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__":
    main()
