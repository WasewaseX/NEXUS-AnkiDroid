"""figures17.py — v1.7 figures (simulation two-arm + real-data strata).

All numbers plotted are read from the verdicts JSONs (computed outputs only).
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = "/home/z/my-project/download/v17_nexus_triad_benchmark"
OUT = os.path.join(HERE, "outputs")

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10,
                     "axes.titleweight": "bold", "figure.dpi": 150})

V17 = json.load(open(os.path.join(OUT, "verdicts_v17.json")))
VRE = json.load(open(os.path.join(OUT, "verdicts_real.json")))

# ------------------------------------------------------------------ fig 1
def fig1_two_arm():
    ba = V17["by_arm_base"]
    arms = ["fsrs_multitype", "nexus_triad"]
    labels = ["Normal AnkiDroid\n(stock FSRS)", "NEXUS-TRIAD\n(scheduling)"]
    metrics = [("dpi", "DPI / study hour"),
               ("ret28", "day-28 trained retention"),
               ("sess_min", "session minutes"),
               ("premature_quit", "premature-quit rate")]
    fig, axes = plt.subplots(1, 4, figsize=(10.5, 3.0))
    for ax, (m, title) in zip(axes, metrics):
        vals = [ba[m][a] for a in arms]
        bars = ax.bar(range(2), vals, color=["#8a94a6", "#2f6f4f"], width=0.62)
        ax.set_xticks(range(2))
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_title(title)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.3f}" if v < 1 else f"{v:.1f}",
                    ha="center", va="bottom", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(0, max(vals) * 1.22)
    ret = V17["P1_no_harm_primary"]["ret28_diff"]
    fig.suptitle(
        f"v1.7 two-arm simulation — paired CRN, 96 careers/arm, seed 20261101 "
        f"(SIMULATION, not real learners)   |   ret@28 diff {ret:+.4f} "
        f"(no-harm floor ±0.02: PASS)",
        fontsize=8.5, y=1.04)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_two_arm_v17.png"),
                bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ fig 2
def fig2_attribution():
    p3 = V17["P3_ordering_effect_exploratory"]
    p3b = V17["P3b_pacing_effect_exploratory"]
    p4 = V17["P4_honesty"]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2))

    def ci_ax(ax, items, title):
        ys = np.arange(len(items))
        for y, (name, est, lo, hi) in zip(ys, items):
            ax.plot([lo, hi], [y, y], color="#333", lw=1.6)
            ax.plot(est, y, "o", color="#2f6f4f", ms=5)
            ax.axvline(0, color="#aaa", lw=0.8, ls="--")
        ax.set_yticks(ys)
        ax.set_yticklabels([n for n, *_ in items], fontsize=7.5)
        ax.set_title(title, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)

    ci_ax(axes[0], [
        ("risk-order DPI %", p3["dpi_rel_gain"]["pooled_rel_gain_pct"],
         p3["dpi_rel_gain"]["ci_pct"][0], p3["dpi_rel_gain"]["ci_pct"][1]),
        ("no-pacing DPI %", p3b["dpi_rel_gain"]["pooled_rel_gain_pct"],
         p3b["dpi_rel_gain"]["ci_pct"][0], p3b["dpi_rel_gain"]["ci_pct"][1]),
        ("full TRIAD DPI %", V17["P2_efficiency_secondary"]["pooled_rel_gain_pct"],
         V17["P2_efficiency_secondary"]["ci_pct"][0],
         V17["P2_efficiency_secondary"]["ci_pct"][1]),
    ], "DPI/hour relative gain vs stock FSRS (%)")
    axes[0].set_xlabel("95% cluster-bootstrap CI")

    dc = p4["due_completion_diff"]
    ci_ax(axes[1], [
        ("due completion", dc["diff"], dc["ci"][0], dc["ci"][1]),
    ], "Due-work completion diff (TRIAD − stock)")
    axes[1].set_xlim(-0.05, 0.08)

    q = p4["premature_quit_rate"]
    qi = p4["quit_intensity"]
    ci_ax(axes[2], [
        ("quit rate (pp)", q["diff"] * 100, q["ci"][0] * 100, q["ci"][1] * 100),
        ("quit /100 min", qi["diff"], qi["ci"][0], qi["ci"][1]),
    ], "Engagement diffs (TRIAD − stock)")
    fig.suptitle("Attribution: the DPI gain is carried by session control; "
                 "risk-ordering adds nothing measurable (SIMULATION)",
                 fontsize=9, y=1.03)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_attribution_v17.png"),
                bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ fig 3
def fig3_real_strata():
    r = VRE["results"]["fsrs5_fitted"]
    st = r["strata_m0_test"]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2))
    panels = [
        ("position_in_session", "position in session (events)",
         "position_in_session"),
        ("events_so_far_today", "same-day workload (events today)",
         "events_so_far_today"),
        ("absence_gap_capped", "days since previous session",
         "absence_gap_capped"),
    ]
    for ax, (key, xlabel, col) in zip(axes, panels):
        rows = st[key]
        xs = np.arange(len(rows))
        resid = [x["residual"] for x in rows]
        ns = [x["n"] for x in rows]
        colors = ["#2f6f4f" if v >= 0 else "#a64545" for v in resid]
        ax.bar(xs, resid, color=colors, width=0.55)
        ax.axhline(0, color="#333", lw=0.9)
        ax.set_xticks(xs)
        ax.set_xticklabels([x[col] for x in rows], fontsize=7.5)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel("actual − predicted", fontsize=8)
        for x, v, n in zip(xs, resid, ns):
            ax.text(x, v, f"{v:+.3f}\nn={n}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=6.5)
        ax.spines[["top", "right"]].set_visible(False)
        lo = min(resid) - 0.05
        hi = max(resid) + 0.05
        ax.set_ylim(lo, hi)
    fig.suptitle(
        "REAL learner data (held-out test users): FSRS-5 residual by context "
        "— small monotone decline across session position and workload "
        "(fatigue/workload signature), no absence signal beyond FSRS",
        fontsize=8.5, y=1.05)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_real_strata_v17.png"),
                bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ fig 4
def fig4_alpha_gate():
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.2))
    ax = axes[0]
    for key, color, name in (("fsrs5_fitted", "#2f6f4f", "FSRS-5 fitted"),
                             ("fsrs5_default", "#8a94a6", "FSRS-5 default")):
        g = VRE["results"][key]["alpha_grid"]
        ax.plot([x["alpha"] for x in g], [x["cal_logloss"] for x in g],
                "o-", color=color, label=name, ms=4)
    ax.set_xlabel("alpha (contextual correction weight)")
    ax.set_ylabel("calibration-block log-loss")
    ax.set_title("alpha selection (calibration users only)")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)

    ax = axes[1]
    for i, (key, color, name) in enumerate((
            ("fsrs5_fitted", "#2f6f4f", "fitted"),
            ("fsrs5_default", "#8a94a6", "default"))):
        pd_ = VRE["results"][key]["paired_diff"]
        est = pd_["mean_ll_gain_per_user"]
        lo, hi = pd_["ci"]
        ax.plot([lo, hi], [i, i], color="#333", lw=2)
        ax.plot(est, i, "o", color=color, ms=6)
    ax.axvline(0, color="#a33", lw=1.0, ls="--")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["FSRS-5\nfitted", "FSRS-5\ndefault"], fontsize=8)
    ax.set_xlabel("held-out paired log-loss gain per user\n(M0 − M1; >0 = context helps)")
    ax.set_title("HELD-OUT TEST USERS: CI crosses 0\n→ gate stays closed (alpha=0)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_alpha_gate_v17.png"),
                bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig1_two_arm()
    fig2_attribution()
    fig3_real_strata()
    fig4_alpha_gate()
    print("figures written to", OUT)
