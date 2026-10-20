"""eval_real.py — STAGE 2: one frozen evaluation on REAL held-out test users.

Consumes outputs/real_frozen.json (fitted weights, calibration, context
betas, alpha selected on calibration users) and evaluates EXACTLY TWO
systems on the never-touched TEST users:

  M0  "FSRS-centered"  : FSRS-5 (py-fsrs 5.1.3 formulas) fitted on train
                          users + global logit calibration (a,b) from train.
  M1  "FSRS + TRIAD-native contextual correction":
                          M0 + alpha* * dContext(x), dContext fitted on train
                          users only (session position, elapsed session
                          minutes, same-day workload, absence gap).

Secondary (default-weights) comparison: FSRS-5 out-of-box default weights
(what a normal AnkiDroid user has without running the optimizer), same
protocol (calibration + dContext refit for that memory model on train,
alpha on cal) — everything below is computed for BOTH memory models.

Metrics (test users): soft log-loss (primary; y = p_recall as fractional
target), binary log-loss / AUC on session_seen==1 rows, Brier (soft), MAE.
Uncertainty: cluster bootstrap over test users (2,000 resamples) on paired
per-user log-loss differences. Descriptive strata tables (residuals by
context) on TEST and TRAIN.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import torch

HERE = "/home/z/my-project/scripts/v17"
sys.path.insert(0, HERE)
from fit_real import (ALPHA_GRID, CTX_FEATURES, FSRS5Torch,  # noqa: E402
                      W_DEFAULT, load_and_scan)

DATA = "/home/z/my-project/data/real_events.parquet"
OUT_DIR = "/home/z/my-project/download/v17_nexus_triad_benchmark/outputs"
FROZEN = os.path.join(OUT_DIR, "real_frozen.json")
VERDICTS = os.path.join(OUT_DIR, "verdicts_real.json")
SEED = 20261101


def bce(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p))


def fit_cal_and_ctx(tr: pd.DataFrame):
    """(a, b, beta_ctx, mu, sd, dc_offset) fitted on TRAIN rows given r."""
    tr = tr.copy()
    tr["logit_r"] = np.log(np.clip(tr.r, 1e-6, 1 - 1e-6)
                           / np.clip(1 - tr.r, 1e-6, 1 - 1e-6))
    y0 = tr.y.values
    a, b = 1.0, 0.0
    for _ in range(3000):
        p = 1 / (1 + np.exp(-(a * tr.logit_r.values + b)))
        a -= 0.5 * np.mean((p - y0) * tr.logit_r.values)
        b -= 0.5 * np.mean(p - y0)
    CTX = np.array(tr.ctx.tolist())
    mu, sd = CTX.mean(0), CTX.std(0) + 1e-12
    tr_z = (CTX - mu) / sd
    X1 = np.column_stack([np.ones(len(tr)), tr.logit_r.values, tr_z])
    theta = np.zeros(X1.shape[1])
    for _ in range(6000):
        p = 1 / (1 + np.exp(-np.clip(X1 @ theta, -30, 30)))
        theta -= 0.25 * (X1.T @ (p - y0)) / len(y0)
    beta_ctx = theta[2:]
    dc_offset = float((tr_z @ beta_ctx).mean())
    return a, b, beta_ctx, mu, sd, dc_offset


def predict(fr, df, a, b, beta_ctx, mu, sd, dc_offset, alpha):
    """df has r, ctx, y -> P(M0), P(M1), dContext."""
    z = (np.array(df.ctx.tolist()) - mu) / sd
    dc = z @ beta_ctx - dc_offset
    base = a * df.logit_r.values + b
    p0 = 1 / (1 + np.exp(-np.clip(base, -30, 30)))
    p1 = 1 / (1 + np.exp(-np.clip(base + alpha * dc, -30, 30)))
    return p0, p1, dc


def pick_alpha(ca: pd.DataFrame, a, b, beta_ctx, mu, sd, dc_offset):
    rows = []
    best = None
    for al in ALPHA_GRID:
        _, p1, _ = predict(None, ca, a, b, beta_ctx, mu, sd, dc_offset, al)
        L = bce(p1, ca.y.values)
        rows.append(dict(alpha=al, cal_logloss=L))
        if best is None or L < best[1]:
            best = (al, L)
    return best[0], rows


def strata_table(df: pd.DataFrame, p: np.ndarray, key: str, bins, labels):
    d = df.copy()
    d["p"] = p
    d["stratum"] = pd.cut(d[key], bins=bins, labels=labels)
    g = d.groupby("stratum", observed=True).agg(
        n=("y", "size"), mean_p=("p", "mean"), mean_y=("y", "mean"))
    g["residual"] = g.mean_y - g.mean_p
    g[key] = g.index.astype(str)
    return g.reset_index()[[key, "n", "mean_p", "mean_y", "residual"]]


def cluster_boot_ci_paired(diff_by_user: np.ndarray, n_boot=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(diff_by_user)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n, n)
        means[i] = diff_by_user[pick].mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def evaluate_arm_bundle(df_train, df_cal, df_test, w_vec, label):
    """Full protocol for one memory model (fitted or default weights).
    df_* MUST carry column src_idx-able default RangeIndex aligned with the
    parquet rows of that split (they do: sorted views of the same frame)."""
    w = torch.tensor(w_vec, dtype=torch.float64)
    rows_tr, _, _ = load_and_scan(df_train, w, collect_grad=False)
    rows_cal, _, _ = load_and_scan(df_cal, w, collect_grad=False)
    rows_te, _, _ = load_and_scan(df_test, w, collect_grad=False)
    tr = pd.DataFrame(rows_tr, columns=["y", "r", "ctx", "src_idx"])
    ca = pd.DataFrame(rows_cal, columns=["y", "r", "ctx", "src_idx"])
    te = pd.DataFrame(rows_te, columns=["y", "r", "ctx", "src_idx"])
    for d in (tr, ca, te):
        d["logit_r"] = np.log(np.clip(d.r, 1e-6, 1 - 1e-6)
                              / np.clip(1 - d.r, 1e-6, 1 - 1e-6))
    a, b, beta_ctx, mu, sd, off = fit_cal_and_ctx(tr)
    alpha_star, grid = pick_alpha(ca, a, b, beta_ctx, mu, sd, off)

    p0, p1, dc = predict(None, te, a, b, beta_ctx, mu, sd, off, alpha_star)
    y = te.y.values
    meta = df_test.loc[te.src_idx.values, [
        "user_id", "n_ex", "position_in_session", "elapsed_session_min",
        "events_so_far_today", "absence_gap_capped"]].reset_index(drop=True)
    te_ext = pd.concat([te.reset_index(drop=True), meta], axis=1)

    def metrics(p):
        out = dict(
            logloss_soft=bce(p, y),
            brier_soft=float(np.mean((p - y) ** 2)),
            mae=float(np.mean(np.abs(p - y))),
        )
        m = (te_ext.n_ex.values == 1)
        if m.sum() > 100:
            out["logloss_binary"] = bce(p[m], y[m])
            out["auc_binary"] = auc(y[m], p[m])
            out["n_binary"] = int(m.sum())
        return out

    m0, m1 = metrics(p0), metrics(p1)
    # paired per-user log-loss diff (M0 - M1; positive = context helps)
    te_ext["ll0"] = -(y * np.log(np.clip(p0, 1e-6, 1 - 1e-6))
                      + (1 - y) * np.log(np.clip(1 - p0, 1e-6, 1 - 1e-6)))
    te_ext["ll1"] = -(y * np.log(np.clip(p1, 1e-6, 1 - 1e-6))
                      + (1 - y) * np.log(np.clip(1 - p1, 1e-6, 1 - 1e-6)))
    per_user = te_ext.groupby("user_id")[["ll0", "ll1"]].mean()
    diff = (per_user.ll0 - per_user.ll1).values  # >0: M1 better
    lo, hi = cluster_boot_ci_paired(diff)
    rel = float(diff.mean() / per_user.ll0.mean() * 100.0)

    # strata (test, descriptive) + the context columns come via src_idx merge
    dte = te_ext.copy()
    strata = {
        "position_in_session": strata_table(
            dte, p0, "position_in_session", [-0.5, 2.5, 5.5, 8.5, 12.5, 1000],
            ["0-2", "3-5", "6-8", "9-12", "13+"]).to_dict("records"),
        "elapsed_session_min": strata_table(
            dte, p0, "elapsed_session_min",
            [-0.1, 5, 10, 20, 40, 1e9], ["0-5", "5-10", "10-20", "20-40", "40+"]
        ).to_dict("records"),
        "events_so_far_today": strata_table(
            dte, p0, "events_so_far_today",
            [-0.5, 4.5, 9.5, 14.5, 24.5, 1e6],
            ["0-4", "5-9", "10-14", "15-24", "25+"]).to_dict("records"),
        "absence_gap_capped": strata_table(
            dte, p0, "absence_gap_capped", [-0.5, 0.5, 1.5, 2.5, 6.5, 100],
            ["0", "1", "2", "3-6", "7+"]).to_dict("records"),
    }
    return dict(
        label=label, m0=m0, m1=m1, alpha_star=alpha_star, alpha_grid=grid,
        paired_diff=dict(
            mean_ll_gain_per_user=float(diff.mean()), ci=[lo, hi],
            rel_gain_pct=rel, n_users=int(len(diff))),
        strata_m0_test=strata,
        beta_ctx=dict(zip(CTX_FEATURES, [float(x) for x in beta_ctx])),
        m0_a=float(a), m0_b=float(b),
    )


def main() -> None:
    fr = json.load(open(FROZEN))
    df = pd.read_parquet(DATA)
    df["absence_gap_capped"] = df.days_since_prev_session.fillna(0.0).clip(0, 30)
    df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    # split-level frames; seq_idx>=0 (first events initialize state)
    splits = {}
    for sp in ("train", "cal", "test"):
        d = df[df.split == sp]
        splits[sp] = d
        print(f"{sp}: users {d.user_id.nunique()}, rows {len(d)}", flush=True)

    global df_test_sorted
    df_test_sorted = splits["test"]  # kept for provenance reporting only

    results = {}
    # primary: FSRS-5 fitted on train users
    results["fsrs5_fitted"] = evaluate_arm_bundle(
        splits["train"], splits["cal"], splits["test"],
        fr["w_fit"], "FSRS-5 (fitted on train users)")
    # secondary: FSRS-5 out-of-box defaults (normal AnkiDroid, no optimizer)
    results["fsrs5_default"] = evaluate_arm_bundle(
        splits["train"], splits["cal"], splits["test"],
        W_DEFAULT, "FSRS-5 (out-of-box default weights)")

    verdict = dict(
        note="REAL learner data (Duolingo HLR public release, English "
             "learners); user-level splits; test users touched exactly once "
             "with frozen artifacts; simulation-free",
        data=dict(source="settles.acl16.learning_traces.13m.csv.gz "
                         "(doi:10.7910/DVN/N8XJME), md5-verified",
                  n_train_users=int(splits['train'].user_id.nunique()),
                  n_cal_users=int(splits['cal'].user_id.nunique()),
                  n_test_users=int(splits['test'].user_id.nunique())),
        primary_question="Does a TRIAD-native contextual correction add "
                         "held-out predictive accuracy beyond FSRS-5 on "
                         "real recall outcomes?",
        results=results,
        honesty=dict(
            real_data=True,
            alpha_gate="alpha selected on calibration users only; test users "
                       "never used for any fitting or selection",
            caveat="English-learner practice on the Duolingo app, 2012-2013 "
                   "release; aggregated per-lesson outcomes (p_recall), not "
                   "per-exercise binary reviews; grade mapping declared in "
                   "prep_real.py; results are predictive-accuracy evidence, "
                   "not a scheduling A/B trial",
        ),
    )
    with open(VERDICTS, "w") as f:
        json.dump(verdict, f, indent=2)
    for k, r in results.items():
        print(f"\n=== {k}: {r['label']} ===")
        print("  M0 :", json.dumps(r["m0"], indent=None))
        print("  M1 :", json.dumps(r["m1"], indent=None))
        print("  paired log-loss gain per user:",
              json.dumps(r["paired_diff"], indent=None))
        print("  alpha*:", r["alpha_star"])
    print("\nverdicts ->", VERDICTS)


if __name__ == "__main__":
    main()
