"""figures18 — v1.8 confirmation figures (English labels only)."""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
for p in ("/home/z/my-project/download/v14_methods_benchmark",
          "/home/z/my-project/download/v15_nexus_mix_benchmark",
          "/home/z/my-project/download/v16_nexus_mix2_benchmark",
          HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

OUT = os.path.join(HERE, "outputs")
RAW = os.path.join(OUT, "raw")

plt.rcParams.update({"font.size": 9, "figure.dpi": 150})


def fig_arm_summary():
    c = pd.read_csv(os.path.join(OUT, "v18_arm_summary.csv"), index_col=0)
    c = c.sort_values("dpi", ascending=True)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), constrained_layout=True)
    short = {"fsrs_recall_only": "FSRS\nmeaning-only", "fsrs_multitype": "FSRS\nmulti-type",
             "nexus_scope20": "NEXUS\nSCOPE 2.0", "nexus_mix2": "NEXUS\nMIX 2.0",
             "nexus_triad": "NEXUS\nTRIAD v1.8", "rwkv_instant": "RWKV\ninstant",
             "sm20": "SM-20"}
    labels = [short.get(a, a) for a in c.index]
    colors = ["#4a90d9" if a != "nexus_triad" else "#e0563a" for a in c.index]
    axes[0].barh(labels, c.dpi, color=colors)
    axes[0].set_title("DPI per study hour")
    axes[1].barh(labels, c.ret28, color=colors)
    axes[1].set_title("Day-28 retention (probes)")
    axes[1].axvline(float(c.loc["fsrs_multitype", "ret28"]), ls="--", c="gray", lw=0.8)
    axes[2].barh(labels, c.quit_rate, color=colors)
    axes[2].set_title("Premature-quit rate")
    for ax in axes:
        ax.tick_params(axis="y", labelsize=7)
    fig.suptitle("NEXUS-TRIAD v1.8 confirmation block (simulation, not real learners)",
                 fontsize=10)
    fig.savefig(os.path.join(HERE, "fig1_arm_summary_v18.png"))
    plt.close(fig)


def fig_stress():
    v = json.load(open(os.path.join(OUT, "verdicts_v18.json")))
    rows = v["T6_stress"]["rows"]
    scen = [r["scenario"] for r in rows]
    dpi = [r["dpi_rel_gain_pct"] for r in rows]
    sess = [r["session_diff"] for r in rows]
    quit_r = [r["quit_rate_diff"] for r in rows]
    x = np.arange(len(scen))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2), constrained_layout=True)
    axes[0].bar(x, dpi, color="#e0563a")
    axes[0].axhline(5.0, ls="--", c="gray", lw=0.8)
    axes[0].set_title("DPI gain vs FSRS multi-type (%)")
    axes[0].set_ylim(min(0, min(dpi)) - 1, max(dpi) + 2)
    axes[1].bar(x, sess, color="#4a90d9")
    axes[1].axhline(-0.5, ls="--", c="gray", lw=0.8)
    axes[1].set_title("Session-minutes diff (min)")
    axes[2].bar(x, quit_r, color="#3a9e5f")
    axes[2].axhline(0, c="gray", lw=0.8)
    axes[2].set_title("Premature-quit-rate diff")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(scen, rotation=45, ha="right", fontsize=6.5)
    fig.suptitle("Behavior-model stress test: TRIAD edge per scenario (simulation)", fontsize=10)
    fig.savefig(os.path.join(HERE, "fig2_stress_v18.png"))
    plt.close(fig)


def fig_end_reasons():
    base = os.path.join(RAW, "v18_confirmation_base_triad_b_sessions.csv")
    s = pd.read_csv(base)
    order = ["nexus_triad", "nexus_mix2", "fsrs_multitype", "fsrs_recall_only"]
    reasons = ["premature_quit", "budget", "planned_goal", "work_complete"]
    colors = {"premature_quit": "#c0392b", "budget": "#7f8c8d",
              "planned_goal": "#3a9e5f", "work_complete": "#4a90d9"}
    fig, ax = plt.subplots(figsize=(7.2, 3.2), constrained_layout=True)
    left = np.zeros(len(order))
    for reason in reasons:
        vals = []
        for arm in order:
            sub = s[s.arm == arm]
            vals.append((sub.end_reason == reason).mean())
        ax.barh([a.replace("_", " ") for a in order], vals, left=left,
                color=colors[reason], label=reason.replace("_", " "))
        left += np.array(vals)
    ax.set_title("Session end reasons (planned stops separated from quits, v1.6 change carried)")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4)
    fig.savefig(os.path.join(HERE, "fig3_end_reasons_v18.png"), bbox_inches=None)
    plt.close(fig)


if __name__ == "__main__":
    fig_arm_summary()
    fig_stress()
    fig_end_reasons()
    print("figures written to", HERE)
