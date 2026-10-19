"""analyze18 — v1.8 confirmation-block analysis + verdicts (T1-T8).

Confirmation block ONLY (calibration was selection-only). All numbers are
properties of the declared simulation, not measurements of real learners.
"""
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analyze16 import cluster_boot_ci, diff_with_ci, rel_gain_with_ci  # noqa: E402
from sim18.triad import brier, logloss  # noqa: E402
import runner18  # noqa: E402

RAW = os.path.join(HERE, "outputs", "raw")
OUT = os.path.join(HERE, "outputs")
TRIAD = "nexus_triad"
MUL = "fsrs_multitype"


def load(name: str) -> dict:
    base = os.path.join(RAW, name)
    out = {}
    for s in ("careers", "probes", "sessions", "predictions"):
        try:
            out[s] = pd.read_csv(base + f"_{s}.csv")
        except pd.errors.EmptyDataError:
            out[s] = pd.DataFrame()
    return out


def attach(careers: pd.DataFrame, probes: pd.DataFrame, horizon: int):
    from analyze16 import attach_endpoints
    return attach_endpoints(careers, probes, horizon)


def arm_table(c) -> pd.DataFrame:
    g = c.groupby("arm").agg(
        dpi=("dpi", "mean"), dpi_ci_lo=("dpi", lambda x: 0), ret28=("ret28", "mean"),
        sessions=("session_minutes_mean", "mean"), gap=("mean_gap_days", "mean"),
        open_rate=("opened_rate", "mean"),
        quit_rate=("premature_quit_rate", "mean"),
        planned_rate=("planned_stop_rate", "mean"),
        work_complete_rate=("work_complete_rate", "mean"),
        quit_intensity=("quit_intensity_per100min", "mean"),
        due_completion=("due_completion_rate", "mean"),
        encounters=("encounters", "mean"),
        study_minutes=("study_minutes", "mean"),
        alpha_final=("triad_alpha_final", "mean"),
        scope_events=("scope_events", "mean"),
    )
    g["dpi_per_enrolled_day"] = g["dpi"] * (c.groupby("arm")["study_minutes"].mean()
                                            / 60.0) / 28.0
    return g.sort_values("dpi", ascending=False)


def paired_ci(d: pd.DataFrame, a: str, b: str, metric: str) -> dict:
    return diff_with_ci(d, a, b, metric)


def main() -> None:
    cfg18, cfg14, cfg15 = runner18.load_cfgs(HERE)
    horizon = int(cfg14["horizon_days"])
    frozen = json.load(open(os.path.join(OUT, "frozen_triad_policy.json")))
    cell = frozen["cell"]

    base = load(f"v18_confirmation_base_{cell}")
    d = attach(base["careers"], base["probes"], horizon)

    # ---------------------------------------------------------- arm table
    table = arm_table(d)
    table.to_csv(os.path.join(OUT, "v18_arm_summary.csv"))

    # ------------------------------------------------------------- verdicts
    V: dict = {"cell": cell, "honesty": cfg18["honesty"]["simulation_not_humans"]}

    # T1 learning primary
    rel = rel_gain_with_ci(d, TRIAD, MUL)
    ret_diff = paired_ci(d, TRIAD, MUL, "ret28")
    V["T1_learning"] = dict(
        dpi_rel_gain_pct=rel["pooled_rel_gain_pct"], dpi_ci_pct=rel["ci_pct"],
        ret28_diff=ret_diff["diff"], ret28_ci=ret_diff["ci"],
        pass_=bool(rel["ci_pct"][0] > 0 and rel["pooled_rel_gain_pct"] >= 5.0
                   and ret_diff["diff"] >= -0.02))

    # T2 engagement
    sess = paired_ci(d, TRIAD, MUL, "session_minutes_mean")
    gap = paired_ci(d, TRIAD, MUL, "mean_gap_days")
    V["T2_engagement"] = dict(
        session_minutes_diff=sess["diff"], session_ci=sess["ci"],
        gap_days_diff=gap["diff"], gap_ci=gap["ci"],
        pass_=bool(sess["ci"][1] < -0.5 and gap["ci"][1] < -0.02))

    # T3 no harm
    V["T3_no_harm"] = dict(ret28_diff=ret_diff["diff"], ret28_ci=ret_diff["ci"],
                           pass_=bool(abs(ret_diff["diff"]) <= 0.02))

    # T4 prediction gating (on the frozen cell's TRIAD predictions)
    P = base["predictions"]
    if len(P):
        last = P.sort_values("seq").groupby(["rep", "learner_id"]).tail(1)
        frac_alpha = float((last["alpha"] > 0).mean())
        mean_alpha = float(last.loc[last.alpha > 0, "alpha"].mean()) if (last.alpha > 0).any() else 0.0
        b_eff = brier(list(zip(P.p_eff, P["correct"])))
        l_eff = logloss(list(zip(P.p_eff, P["correct"])))
        b_h = brier(list(zip(P.p_hybrid, P["correct"])))
        l_h = logloss(list(zip(P.p_hybrid, P["correct"])))
        V["T4_prediction"] = dict(
            n_predictions=int(len(P)), frac_careers_alpha_gt0=frac_alpha,
            mean_alpha_given_gt0=mean_alpha,
            brier_p_eff=b_eff, brier_p_hybrid=b_h,
            logloss_p_eff=l_eff, logloss_p_hybrid=l_h)
    else:
        V["T4_prediction"] = dict(n_predictions=0)

    # T5 SCOPE (descriptive)
    scope_dpi = float(d[d.arm == "nexus_scope20"].dpi.mean())
    mul_dpi = float(d[d.arm == MUL].dpi.mean())
    scope_ret = paired_ci(d, "nexus_scope20", MUL, "ret28")
    V["T5_scope"] = dict(
        scope_dpi=scope_dpi, multitype_dpi=mul_dpi,
        scope_dpi_rel_pct=(scope_dpi - mul_dpi) / abs(mul_dpi) * 100.0,
        ret28_diff=scope_ret["diff"], ret28_ci=scope_ret["ci"])

    # T6 stress (frozen cell TRIAD vs multitype per scenario)
    stress = []
    scens = ("no_monotony", "double_monotony", "no_fatigue_quit",
             "no_valence_quit", "no_return_valence", "slow_recovery",
             "skeptical", "hard_skeptical")
    for scen in (["base"] + list(scens)):
        if scen == "base":
            dd = d
        else:
            cellbase = load(f"v18_confirmation_{scen}_{cell}")
            dd = attach(cellbase["careers"], cellbase["probes"], horizon)
        sd = paired_ci(dd, TRIAD, MUL, "session_minutes_mean")
        qd = paired_ci(dd, TRIAD, MUL, "premature_quit_rate")
        rd = rel_gain_with_ci(dd, TRIAD, MUL)
        stress.append(dict(scenario=scen, dpi_rel_gain_pct=rd["pooled_rel_gain_pct"],
                           session_diff=sd["diff"], session_ci=sd["ci"],
                           quit_rate_diff=qd["diff"], quit_ci=qd["ci"]))
    V["T6_stress"] = dict(
        rows=stress,
        mechanical_floor_session_diff=next(r["session_diff"] for r in stress
                                           if r["scenario"] == "hard_skeptical"),
        base_session_diff=next(r["session_diff"] for r in stress
                               if r["scenario"] == "base"))

    # T7 ablations (alpha gate off = triad_d; intake gate off = triad_c)
    abl = {}
    for name, other in (("alpha_gate_off", "v18_confirmation_base_triad_d"),
                        ("intake_gate_off", "v18_confirmation_base_triad_c")):
        try:
            db = load(other)
            da = attach(db["careers"], db["probes"], horizon)
            tri_other = da[da.arm == TRIAD].set_index(["rep", "learner_id"])
            tri_frozen = d[d.arm == TRIAD].set_index(["rep", "learner_id"])
            j = pd.concat([tri_frozen[["dpi", "ret28", "session_minutes_mean"]],
                           tri_other[["dpi", "ret28", "session_minutes_mean"]]],
                          axis=1, keys=["frozen", "other"]).dropna()
            abl[name] = dict(
                dpi_diff_frozen_minus_other=float(
                    (j[("frozen", "dpi")] - j[("other", "dpi")]).mean()),
                ret28_diff=float((j[("frozen", "ret28")]
                                  - j[("other", "ret28")]).mean()),
                session_diff=float((j[("frozen", "session_minutes_mean")]
                                    - j[("other", "session_minutes_mean")]).mean()))
        except FileNotFoundError:
            abl[name] = dict(error="missing run")
    V["T7_ablations"] = abl

    # T8 alt schedulers (descriptive)
    t8 = {}
    for arm in ("rwkv_instant", "sm20", "fsrs_recall_only", "nexus_mix2",
                "nexus_scope20"):
        sub = d[d.arm == arm]
        if len(sub):
            t8[arm] = dict(dpi=float(sub.dpi.mean()),
                           ret28=float(sub.ret28.mean()))
    t8[MUL] = dict(dpi=float(d[d.arm == MUL].dpi.mean()),
                   ret28=float(d[d.arm == MUL].ret28.mean()))
    V["T8_scheduler_arms"] = t8

    with open(os.path.join(OUT, "verdicts_v18.json"), "w") as f:
        json.dump(V, f, indent=1, default=float)

    # ------------------------------------------------------------ printout
    print("=== v1.8 CONFIRMATION (frozen cell", cell, ") ===")
    print(table[["dpi", "ret28", "sessions", "gap", "quit_rate",
                 "planned_rate", "due_completion"]].round(4).to_string())
    print("\nT1 DPI gain %+0.2f%% CI [%+0.2f, %+0.2f] | ret28 diff %+0.4f CI [%+0.4f, %+0.4f] -> %s"
          % (rel["pooled_rel_gain_pct"], rel["ci_pct"][0], rel["ci_pct"][1],
             ret_diff["diff"], ret_diff["ci"][0], ret_diff["ci"][1],
             "PASS" if V["T1_learning"]["pass_"] else "FAIL"))
    print("T2 session diff %+.2f min CI [%+.2f, %+.2f] | gap diff %+.3f d -> %s"
          % (sess["diff"], sess["ci"][0], sess["ci"][1], gap["diff"],
             "PASS" if V["T2_engagement"]["pass_"] else "FAIL"))
    print("T3 no-harm |ret28 diff| = %+.4f -> %s"
          % (ret_diff["diff"], "PASS" if V["T3_no_harm"]["pass_"] else "FAIL"))
    if V["T4_prediction"].get("n_predictions"):
        t4 = V["T4_prediction"]
        print("T4 predictions n=%d | alpha>0 in %.1f%% careers (mean %.2f) | "
              "Brier %.4f -> %.4f | logloss %.4f -> %.4f"
              % (t4["n_predictions"], 100 * t4["frac_careers_alpha_gt0"],
                 t4["mean_alpha_given_gt0"], t4["brier_p_eff"],
                 t4["brier_p_hybrid"], t4["logloss_p_eff"], t4["logloss_p_hybrid"]))
    print("\nStress table:")
    print(pd.DataFrame(V["T6_stress"]["rows"]).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
