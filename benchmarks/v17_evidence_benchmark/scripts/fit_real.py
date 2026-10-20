"""fit_real.py — REAL-data fitting stage (train + calibration users ONLY).

Evidence pipeline for the user's directive: 'build toward a TRIAD-native
memory model only when you have evidence showing which aspect of human recall
the current FSRS-centered approach fails to capture. Then compare the new
model against FSRS using real, held-out outcomes.'

STAGE 1 (this script) touches train + calibration users ONLY:
  1. FSRS-5 (exact py-fsrs 5.1.3 formulas, 19 params) fitted by Adam on
     train users' soft outcomes (BCE), full BPTT per user. Declared epoch
     budget; checkpoints saved.
  2. M0 baseline: P = sigmoid(a*logit(R)+b) with a,b fitted on train users
     (identical treatment for every arm).
  3. TRIAD-native contextual correction: dContext(x) = beta*ctx(x) fitted on
     train users from the residual of y on logit(R); ctx features are
     session-position, elapsed-session-minutes, same-day workload, and
     absence gap — the context channels TRIAD's predictor models.
  4. alpha selected on CALIBRATION users by soft log-loss over a declared
     grid; frozen to outputs/real_frozen.json.
STAGE 2 (eval_real.py) touches the TEST users exactly once with the frozen
artifacts and is the only source of final numbers.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd
import torch

torch.manual_seed(20261101)

DATA = "/home/z/my-project/data/real_events.parquet"
OUT_DIR = "/home/z/my-project/download/v17_nexus_triad_benchmark/outputs"
CKPT = os.path.join(OUT_DIR, "real_fsrs5_ckpt.pt")
FROZEN = os.path.join(OUT_DIR, "real_frozen.json")

DECAY = -0.5
FACTOR = 0.9 ** (1.0 / DECAY) - 1.0        # 19/81
W_DEFAULT = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604,
             0.0046, 1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605,
             2.2698, 0.2315, 2.9898, 0.51655, 0.6621]
S_MIN, S_MAX = 0.1, 36500.0
D_MIN, D_MAX = 1.0, 10.0
EPOCHS = 4
LR = 0.02
CTX_FEATURES = ["position_in_session", "elapsed_session_min",
                "events_so_far_today", "absence_gap_capped"]
ALPHA_GRID = [0.0, 0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]


# ---------------------------------------------------------------- FSRS-5 torch
class FSRS5Torch:
    """Exact FSRS-5 update rules (py-fsrs 5.1.3) on torch scalars."""

    def __init__(self, w: torch.Tensor):
        self.w = w

    def _clamp_d(self, d):
        return torch.clamp(d, D_MIN, D_MAX)

    def initial_state(self, g):
        w = self.w
        gi = int(g)
        s = torch.clamp(w[gi - 1], min=S_MIN)
        d = self._clamp_d(w[4] - torch.exp(w[5] * (gi - 1.0)) + 1.0)
        return s, d

    def next_difficulty(self, d, g):
        w = self.w
        d0_easy = self._clamp_d(w[4] - torch.exp(w[5] * 3.0) + 1.0)  # G=4
        delta = -(w[6] * (g - 3.0))
        damped = (10.0 - d) * delta / 9.0
        d2 = w[7] * d0_easy + (1.0 - w[7]) * (d + damped)
        return self._clamp_d(d2)

    def r_curve(self, dt_days, s):
        return (1.0 + FACTOR * dt_days / s) ** DECAY

    def short_term_s(self, s, g):
        w = self.w
        return s * torch.exp(w[17] * (g - 3.0 + w[18]))

    def recall_s(self, s, d, r, g):
        w = self.w
        hard = torch.where(g == 2, w[15], torch.ones((), dtype=w.dtype))
        easy = torch.where(g == 4, w[16], torch.ones((), dtype=w.dtype))
        return s * (1.0 + torch.exp(w[8]) * (11.0 - d)
                    * (s ** (-w[9]))
                    * (torch.exp((1.0 - r) * w[10]) - 1.0) * hard * easy)

    def forget_s(self, s, d, r):
        w = self.w
        long_t = (w[11] * (d ** (-w[12]))
                  * (((s + 1.0) ** w[13]) - 1.0)
                  * torch.exp((1.0 - r) * w[14]))
        short_t = s / torch.exp(w[17] * w[18])
        return torch.minimum(long_t, short_t)


# ------------------------------------------------------------------ data prep
def load_and_scan(df_users: pd.DataFrame, w: torch.Tensor, collect_grad: bool):
    """Sequential FSRS-5 scan over each user's events (time-ordered).

    Returns rows for evaluated events (seq_idx>=1, dt>=1 day):
    user key, y, r_pred, ctx features. When collect_grad, builds a torch
    graph per user and backprops the soft BCE through the state trajectory.
    """
    w_ = w.detach().clone().requires_grad_(collect_grad)
    model = FSRS5Torch(w_)
    losses = []
    out_rows = []
    for _, gdf in df_users.groupby("user_id", sort=False):
        gdf = gdf.sort_values(["lexeme_id", "timestamp"])
        # per-lexeme state
        S: dict = {}
        D: dict = {}
        last: dict = {}
        loss_terms = []
        rows = []
        for idx, rec in zip(gdf.index, gdf.itertuples(index=False)):
            key = rec.lexeme_id
            g = float(rec.grade)
            t = float(rec.timestamp)
            if key not in S:
                s, d = model.initial_state(g)
                if collect_grad:
                    S[key], D[key] = s, d
                else:
                    S[key], D[key] = s.detach(), d.detach()
                last[key] = t
                continue
            dt_days = max(0.0, (t - last[key]) / 86400.0)
            s, d = S[key], D[key]
            if collect_grad:
                r = model.r_curve(torch.tensor(dt_days, dtype=torch.float64), s)
            else:
                with torch.no_grad():
                    r = model.r_curve(torch.tensor(dt_days, dtype=torch.float64), s)
            gten = torch.tensor(g, dtype=torch.float64)
            if collect_grad:
                if dt_days < 1.0:
                    s2 = model.short_term_s(s, gten)
                    d2 = model.next_difficulty(d, gten)
                else:
                    if g == 1.0:
                        s2 = model.forget_s(s, d, r)
                    else:
                        s2 = model.recall_s(s, d, r, gten)
                    d2 = model.next_difficulty(d, gten)
                s2 = torch.clamp(s2, S_MIN, S_MAX)
                S[key], D[key] = s2, d2
            else:
                with torch.no_grad():
                    if dt_days < 1.0:
                        s2 = model.short_term_s(s, gten)
                        d2 = model.next_difficulty(d, gten)
                    else:
                        if g == 1.0:
                            s2 = model.forget_s(s, d, r)
                        else:
                            s2 = model.recall_s(s, d, r, gten)
                        d2 = model.next_difficulty(d, gten)
                    s2 = torch.clamp(s2, S_MIN, S_MAX)
                    S[key], D[key] = s2.detach(), d2.detach()
            last[key] = t
            if dt_days >= 1.0:  # evaluation-eligible (srs-benchmark convention)
                y = float(rec.y)
                ctx = [float(rec.position_in_session),
                       float(rec.elapsed_session_min),
                       float(rec.events_so_far_today),
                       min(float(rec.days_since_prev_session)
                           if not math.isnan(rec.days_since_prev_session) else 0.0,
                           30.0)]
                rows.append((y, float(r.detach()), ctx, int(idx)))
                if collect_grad:
                    p = torch.clamp(r, 1e-6, 1 - 1e-6)
                    loss_terms.append(-(y * torch.log(p)
                                        + (1.0 - y) * torch.log(1.0 - p)))
        if collect_grad and loss_terms:
            loss = torch.stack(loss_terms).mean()
            loss.backward()
            losses.append(float(loss.detach()))
        out_rows.extend(rows)
    grad = w_.grad.detach().clone() if collect_grad else None
    return out_rows, grad, (float(np.mean(losses)) if losses else float("nan"))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_parquet(DATA)
    df = df[df.seq_idx >= 0].copy()
    df["absence_gap_capped"] = df.days_since_prev_session.fillna(0.0).clip(0, 30)
    train = df[df.split == "train"]
    cal = df[df.split == "cal"]
    print(f"train users {train.user_id.nunique()}, rows {len(train)}; "
          f"cal users {cal.user_id.nunique()}, rows {len(cal)}", flush=True)

    # sort once: groupby user, then lexeme+time inside the scan
    train = train.sort_values(["user_id", "timestamp"])

    # ---- 1. FSRS-5 fit on train users (Adam on 19 weights, BPTT per user)
    w = torch.tensor(W_DEFAULT, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.Adam([w], lr=LR)
    n_users = train.user_id.nunique()
    for ep in range(EPOCHS):
        opt.zero_grad()
        # shuffle user order per epoch
        users = train.user_id.unique()
        perm = torch.randperm(len(users)).numpy()
        users_shuf = users[perm]
        sub = train[train.user_id.isin(users_shuf)]
        _, grad, avg_loss = load_and_scan(sub, w, collect_grad=True)
        w.grad = grad
        opt.step()
        w.data = torch.clamp(w.data, min=torch.tensor(
            [0.1, 0.1, 0.1, 0.1, 1.0, 0.001, 0.001, 0.001, 0.0, 0.0,
             0.001, 0.001, 0.001, 0.001, 0.0, 0.0, 1.0, 0.0, 0.0],
            dtype=torch.float64))
        print(f"epoch {ep+1}/{EPOCHS} train BCE {avg_loss:.5f} "
              f"({n_users} users)", flush=True)
        torch.save({"w": w.detach(), "epoch": ep}, CKPT)

    w_fit = w.detach().clone()

    # ---- 2. forward pass (no grad) for train + cal users with fitted w
    rows_tr, _, _ = load_and_scan(train, w_fit, collect_grad=False)
    rows_cal, _, _ = load_and_scan(cal, w_fit, collect_grad=False)
    tr = pd.DataFrame(rows_tr, columns=["y", "r", "ctx", "src_idx"])
    ca = pd.DataFrame(rows_cal, columns=["y", "r", "ctx", "src_idx"])
    tr["logit_r"] = np.log(np.clip(tr.r, 1e-6, 1 - 1e-6)
                           / np.clip(1 - tr.r, 1e-6, 1 - 1e-6))
    ca["logit_r"] = np.log(np.clip(ca.r, 1e-6, 1 - 1e-6)
                           / np.clip(1 - ca.r, 1e-6, 1 - 1e-6))
    CTX = np.array(tr.ctx.tolist())
    mu, sd = CTX.mean(0), CTX.std(0) + 1e-12
    tr_z = (CTX - mu) / sd
    ca_z = (np.array(ca.ctx.tolist()) - mu) / sd

    def bce(p, y):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    # ---- 3. M0 calibration (a,b) on train
    X0 = np.column_stack([np.ones(len(tr)), tr.logit_r.values])
    y0 = tr.y.values
    theta0 = None  # proper logistic fit via GD below (soft targets)
    a, b = 1.0, 0.0
    for _ in range(3000):
        p = 1 / (1 + np.exp(-(a * tr.logit_r.values + b)))
        ga = np.mean((p - y0) * tr.logit_r.values)
        gb = np.mean(p - y0)
        a -= 0.5 * ga
        b -= 0.5 * gb
    m0_cal_loss = bce(1 / (1 + np.exp(-(a * ca.logit_r.values + b))), ca.y.values)

    # ---- 4. dContext: logistic regression of y on [logit_r | z-ctx] (train)
    X1 = np.column_stack([np.ones(len(tr)), tr.logit_r.values, tr_z])
    y1 = tr.y.values
    theta = np.zeros(X1.shape[1])
    lr = 0.25
    for _ in range(6000):
        p = 1 / (1 + np.exp(-np.clip(X1 @ theta, -30, 30)))
        theta -= lr * (X1.T @ (p - y1)) / len(y1)
    beta_ctx = theta[2:]
    # centered dContext: offset from TRAIN users (declared; no cal leakage)
    dc_offset = float((tr_z @ beta_ctx).mean())
    dc_cal = ca_z @ beta_ctx - dc_offset

    # ---- 5. alpha selection on CAL users (declared grid)
    base = a * ca.logit_r.values + b
    best = None
    grid_out = []
    for al in ALPHA_GRID:
        p = 1 / (1 + np.exp(-np.clip(base + al * dc_cal, -30, 30)))
        L = bce(p, ca.y.values)
        grid_out.append(dict(alpha=al, cal_logloss=L))
        if best is None or L < best[1]:
            best = (al, L)
    alpha_star = best[0]

    frozen = dict(
        w_fit=w_fit.tolist(), w_default=W_DEFAULT,
        m0_a=float(a), m0_b=float(b),
        ctx_mu=mu.tolist(), ctx_sd=sd.tolist(),
        beta_ctx=beta_ctx.tolist(), alpha_star=float(alpha_star),
        alpha_grid=grid_out,
        cal_logloss_m0=m0_cal_loss,
        ctx_features=CTX_FEATURES,
        note="fitted on TRAIN users only; alpha selected on CAL users; "
             "TEST users untouched (eval_real.py consumes this file once)",
    )
    with open(FROZEN, "w") as f:
        json.dump(frozen, f, indent=2)
    print(json.dumps({k: frozen[k] for k in
                      ("alpha_star", "cal_logloss_m0", "ctx_features")}, indent=2))
    print("alpha grid:", json.dumps(grid_out, indent=1))
    print("beta_ctx (z-units):", beta_ctx.tolist())


if __name__ == "__main__":
    main()
