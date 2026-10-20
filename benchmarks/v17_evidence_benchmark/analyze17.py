"""analyze17 — pre-registered analysis for v1.7 (P1-P6 + replication audit).

Reuses v1.6's analysis helpers UNMODIFIED (attach_endpoints, paired diffs,
cluster bootstrap). The confirmation block is the ONLY evidence. The shared
arm (fsrs_multitype) must reproduce the v1.6 confirmation-base numbers
bit-exactly — any drift is a bug, not noise.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.abspath(os.path.dirname(__file__))
V16 = os.path.abspath(os.path.join(HERE, "..", "v16_nexus_mix2_benchmark"))
V15 = os.path.abspath(os.path.join(HERE, "..", "v15_nexus_mix_benchmark"))
for p in (HERE, V16, V15):
    if p not in sys.path:
        sys.path.insert(0, p)

from analyze16 import (BOOT_N, attach_endpoints, cluster_boot_ci,  # noqa: E402
                       diff_with_ci, paired, rel_gain_with_ci)


def run_name(scenario: str, variant: str) -> str:
    return f"v17_{scenario}_{variant}"


def load_raw(scenario: str, variant: str) -> tuple:
    import glob as _glob
    base = os.path.join(HERE, "outputs", "raw", run_name(scenario, variant))
    out = []
    for suffix in ("careers", "probes", "sessions", "events"):
        paths = sorted(_glob.glob(base + f"_r[0-9]*_{suffix}.csv"))
        if not paths:
            paths = [base + f"_{suffix}.csv"]
        else:
            untagged = base + f"_{suffix}.csv"
            if os.path.exists(untagged):  # rep 0 chunk writes untagged files
                paths.append(untagged)
                paths = sorted(paths)
        out.append(pd.concat([pd.read_csv(p) for p in paths],
                             ignore_index=True))
    c, p, s, e = out
    return c, p, s, e


# ---------------------------------------------------------------- diagnostics
def _session_gap_map(sessions: pd.DataFrame) -> dict:
    """(arm, rep, learner_id) -> {day: gap_days_since_prev_session}."""
    out = {}
    for (arm, rep, lid), g in sessions.groupby(["arm", "rep", "learner_id"]):
        days = sorted(g["day"].tolist())
        prev = None
        m = {}
        for d in days:
            m[d] = (d - prev) if prev is not None else 0
            prev = d
        out[(arm, rep, lid)] = m
    return out


def event_diagnostics(events: pd.DataFrame, sessions: pd.DataFrame) -> dict:
    """P5: FSRS calibration residuals by context strata (descriptive only).

    residual(stratum) = mean(success) - mean(r_before)  over graded reviews
    with r_before > 0 (initialized scheduler state). r_before is the
    scheduler's OWN prediction made BEFORE the grade; success is the truth
    outcome. In-simulation residuals are properties of the DECLARED truth
    model (its fatigue/workload/absence channels), not of real humans.
    """
    ev = events[(events.is_new == False) & (events.grade > 0) &
                (events.r_before > 0)].copy()
    gaps = _session_gap_map(sessions)
    ev["gap_days"] = [gaps.get((a, r, l), {}).get(d, np.nan)
                      for a, r, l, d in zip(ev.arm, ev.rep, ev.learner_id, ev.day)]

    # per-(arm,rep,learner,day) event index within the day's session
    ev = ev.sort_values(["arm", "rep", "learner_id", "day", "t_min"])
    ev["evt_idx"] = ev.groupby(["arm", "rep", "learner_id", "day"]).cumcount()
    ev["pos_frac"] = ev["evt_idx"] / 12.0  # approximate session length scale

    def residual_table(df: pd.DataFrame, key: str, bins, labels) -> pd.DataFrame:
        df = df.copy()
        df["stratum"] = pd.cut(df[key], bins=bins, labels=labels)
        g = df.groupby("stratum", observed=True).agg(
            n=("success", "size"),
            mean_r=("r_before", "mean"),
            mean_success=("success", "mean"),
        )
        g["residual"] = g["mean_success"] - g["mean_r"]
        g[key] = g.index.astype(str)
        return g.reset_index()[[key, "n", "mean_r", "mean_success", "residual"]]

    out = {
        "overall": dict(
            n=int(len(ev)),
            mean_r=float(ev.r_before.mean()),
            mean_success=float(ev.success.mean()),
            residual=float(ev.success.mean() - ev.r_before.mean()),
        ),
        "position_in_session": residual_table(
            ev, "evt_idx", bins=[-0.5, 3.5, 7.5, 11.5, 17.5, 999],
            labels=["0-3", "4-7", "8-11", "12-17", "18+"]).to_dict("records"),
        "elapsed_min": residual_table(
            ev, "t_min", bins=[1080, 1085, 1090, 1095, 1100, 1120, 1e9],
            labels=["0-5", "5-10", "10-15", "15-20", "20-40", "40+"]).to_dict("records"),
        "gap_days": residual_table(
            ev, "gap_days", bins=[-0.5, 0.5, 1.5, 2.5, 6.5, 100],
            labels=["same/next", "1d", "2d", "3-6d", "7d+"]).to_dict("records"),
        "r_before_bins": residual_table(
            ev, "r_before", bins=[0, 0.5, 0.7, 0.8, 0.87, 0.925, 1.0],
            labels=["<0.5", "0.5-0.7", "0.7-0.8", "0.8-0.87", "0.87-0.925", ">0.925"]
        ).to_dict("records"),
    }
    # absolute-time control (t_min is absolute sim time; elapsed within session)
    ev["elapsed_min"] = ev["t_min"] - ((ev["day"] - 1) * 1440.0 + 1080.0)
    out["elapsed_in_session"] = residual_table(
        ev, "elapsed_min", bins=[-0.1, 5, 10, 15, 20, 40, 1e9],
        labels=["0-5", "5-10", "10-15", "15-20", "20-40", "40+"]).to_dict("records")
    return out


# ------------------------------------------------------------------ verdicts
def verdicts(cfg17: dict) -> dict:
    floors = cfg17["v17_preregistration"]["floors"]
    V = {"note": "confirmation block only; TRIAD knobs frozen ex ante from "
                 "the v1.6 frozen policy (p075_prot); floors: " + json.dumps(floors),
         "floors": floors}

    c, p, s, e = load_raw("base", "nexus_triad")
    base = attach_endpoints(c, p)
    by_arm = base.groupby("arm").agg(
        dpi=("dpi", "mean"), ret28=("ret28", "mean"),
        dpi_per_day=("dpi_per_day", "mean"),
        sess_min=("session_minutes_mean", "mean"), gap=("mean_gap_days", "mean"),
        premature_quit=("premature_quit_rate", "mean"),
        planned_stop=("planned_stop_rate", "mean"),
        work_complete=("work_complete_rate", "mean"),
        budget_end=("budget_rate", "mean"),
        quit_intensity=("quit_intensity_per100min", "mean"),
        open_rate=("opened_rate", "mean"),
        encounters=("encounters", "mean"), enc_per_session=("enc_per_session", "mean"),
        due_completion=("due_completion_rate", "mean"),
        study_min=("study_minutes", "mean"),
    )
    by_arm.to_csv(os.path.join(HERE, "outputs", "v17_base_by_arm.csv"))
    V["by_arm_base"] = json.loads(by_arm.round(5).to_json())

    # P1 no-harm (primary) + P2 efficiency + P4 honesty
    ret_diff = float(base[base.arm == "nexus_triad"].ret28.mean()
                     - base[base.arm == "fsrs_multitype"].ret28.mean())
    V["P1_no_harm_primary"] = dict(
        ret28_diff=ret_diff, ok=bool(abs(ret_diff) <= floors["retention_tolerance"]))
    V["P2_efficiency_secondary"] = dict(
        **rel_gain_with_ci(base, "nexus_triad", "fsrs_multitype"),
        ok_claim_only_if_ci_excludes_0=True)
    V["P4_honesty"] = dict(
        due_completion_diff=diff_with_ci(base, "nexus_triad", "fsrs_multitype",
                                         "due_completion_rate"),
        premature_quit_rate=diff_with_ci(base, "nexus_triad", "fsrs_multitype",
                                         "premature_quit_rate"),
        quit_intensity=diff_with_ci(base, "nexus_triad", "fsrs_multitype",
                                    "quit_intensity_per100min"),
        session_minutes=diff_with_ci(base, "nexus_triad", "fsrs_multitype",
                                     "session_minutes_mean"),
        gap_days=diff_with_ci(base, "nexus_triad", "fsrs_multitype",
                              "mean_gap_days"),
        dpi_per_day=diff_with_ci(base, "nexus_triad", "fsrs_multitype",
                                 "dpi_per_day"))

    # P3 ordering attribution (triad vs its no-risk-order ablation)
    c2, p2, _, _ = load_raw("base", "triad_no_risk_order")
    ab1 = attach_endpoints(c2, p2)
    both = pd.concat([base, ab1], ignore_index=True)
    V["P3_ordering_effect_exploratory"] = dict(
        dpi_rel_gain=rel_gain_with_ci(both, "nexus_triad", "triad_no_risk_order"),
        ret28_diff=float(both[both.arm == "nexus_triad"].ret28.mean()
                         - both[both.arm == "triad_no_risk_order"].ret28.mean()))

    # pacing attribution (triad vs no-pacing ablation)
    c3, p3, _, _ = load_raw("base", "triad_no_pacing")
    ab2 = attach_endpoints(c3, p3)
    both2 = pd.concat([base, ab2], ignore_index=True)
    V["P3b_pacing_effect_exploratory"] = dict(
        dpi_rel_gain=rel_gain_with_ci(both2, "nexus_triad", "triad_no_pacing"),
        ret28_diff=float(both2[both2.arm == "nexus_triad"].ret28.mean()
                         - both2[both2.arm == "triad_no_pacing"].ret28.mean()),
        session_diff=diff_with_ci(both2, "nexus_triad", "triad_no_pacing",
                                  "session_minutes_mean"))

    # P5 diagnostics per arm
    V["P5_event_diagnostics"] = dict(
        fsrs_multitype=event_diagnostics(e[e.arm == "fsrs_multitype"],
                                         s[s.arm == "fsrs_multitype"]),
        nexus_triad=event_diagnostics(e[e.arm == "nexus_triad"],
                                      s[s.arm == "nexus_triad"]))

    # P6 stress scenarios
    srows = []
    for sc in ("no_fatigue_quit", "double_monotony", "skeptical", "hard_skeptical"):
        cs, ps, _, _ = load_raw(sc, "nexus_triad")
        st = attach_endpoints(cs, ps)
        srows.append(dict(
            scenario=sc,
            session_diff=diff_with_ci(st, "nexus_triad", "fsrs_multitype",
                                      "session_minutes_mean"),
            quit_diff=diff_with_ci(st, "nexus_triad", "fsrs_multitype",
                                   "premature_quit_rate"),
            ret28_diff=float(st[st.arm == "nexus_triad"].ret28.mean()
                             - st[st.arm == "fsrs_multitype"].ret28.mean())))
    V["P6_stress"] = srows

    # replication audit vs v1.6 confirmation base (bit-exact expectation)
    v16 = json.load(open(os.path.join(V16, "outputs", "verdicts_v16.json")))
    ba16 = v16["by_arm_confirmation"]
    ba17 = V["by_arm_base"]
    V["replication_audit"] = dict(
        multitype_dpi_v17=ba17["dpi"]["fsrs_multitype"],
        multitype_dpi_v16=ba16["dpi"]["fsrs_multitype"],
        multitype_ret_v17=ba17["ret28"]["fsrs_multitype"],
        multitype_ret_v16=ba16["ret28"]["fsrs_multitype"],
        exact=bool(abs(ba17["dpi"]["fsrs_multitype"] - ba16["dpi"]["fsrs_multitype"]) < 1e-9
                   and abs(ba17["ret28"]["fsrs_multitype"] - ba16["ret28"]["fsrs_multitype"]) < 1e-9))
    return V


def main() -> None:
    with open(os.path.join(HERE, "config17.json")) as f:
        cfg17 = json.load(f)
    V = verdicts(cfg17)
    with open(os.path.join(HERE, "outputs", "verdicts_v17.json"), "w") as f:
        json.dump(V, f, indent=2)
    show = ("P1_no_harm_primary", "P2_efficiency_secondary", "P3_ordering_effect_exploratory",
            "P3b_pacing_effect_exploratory", "P4_honesty", "P6_stress", "replication_audit")
    print(json.dumps({k: V[k] for k in show}, indent=2)[:5000])
    print("\nP5 diagnostics (multitype overall):",
          json.dumps(V["P5_event_diagnostics"]["fsrs_multitype"]["overall"]))
    print("P5 position strata (multitype):")
    for r in V["P5_event_diagnostics"]["fsrs_multitype"]["position_in_session"]:
        print("  ", r)


if __name__ == "__main__":
    main()
