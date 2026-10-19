"""run18 — v1.8 stage driver (calibration grid -> freeze -> confirmation).

Stages (in declared order, per config18.json):
  1. calibration grid: 4 TRIAD cells x {fsrs_multitype, nexus_triad}
  2. freeze: select cell on calibration (v1.6 rule) -> outputs/frozen_triad_policy.json
  3. confirmation base: frozen cell x ALL 7 arms (the only evidence)
  4. confirmation ablations: triad_d (alpha off), triad_c (intake gate off)
  5. confirmation stress: base + 9 scenarios x {fsrs_multitype, nexus_triad}
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

import runner18  # noqa: E402

RAW = os.path.join(HERE, "outputs", "raw")


def stage_calib() -> None:
    for cell in ("triad_a", "triad_b", "triad_c", "triad_d"):
        paths = runner18.run_cell(
            "calibration", "base", cell, HERE,
            arm_filter={"fsrs_multitype", "nexus_triad"}, out_dir=RAW)
        print("[calib]", cell, "->", len(paths), "files", flush=True)


def stage_freeze() -> dict:
    import pandas as pd
    from analyze16 import attach_endpoints, rel_gain_with_ci  # noqa: E402
    cfg18, cfg14, cfg15 = runner18.load_cfgs(HERE)
    horizon = int(cfg14["horizon_days"])
    floors = cfg18["v18_preregistration"]["floors"]
    rows = []
    for cell in ("triad_a", "triad_b", "triad_c", "triad_d"):
        base = os.path.join(RAW, f"v18_calibration_base_{cell}")
        careers = pd.read_csv(base + "_careers.csv")
        probes = pd.read_csv(base + "_probes.csv")
        c = attach_endpoints(careers, probes, horizon)
        mul = c[c.arm == "fsrs_multitype"].set_index(["rep", "learner_id"])
        tri = c[c.arm == "nexus_triad"].set_index(["rep", "learner_id"])
        j = pd.concat([tri[["dpi", "ret28", "session_minutes_mean",
                            "mean_gap_days"]],
                       mul[["dpi", "ret28", "session_minutes_mean",
                            "mean_gap_days"]]],
                      axis=1, keys=["t", "m"]).dropna()
        rel = rel_gain_with_ci(c, "nexus_triad", "fsrs_multitype")
        row = dict(
            cell=cell,
            dpi_rel_gain_pct=rel["pooled_rel_gain_pct"],
            ret28_diff=float((j[("t", "ret28")] - j[("m", "ret28")]).mean()),
            session_diff=float((j[("t", "session_minutes_mean")]
                                - j[("m", "session_minutes_mean")]).mean()),
            gap_diff=float((j[("t", "mean_gap_days")]
                            - j[("m", "mean_gap_days")]).mean()),
        )

        def margin(r):
            return min(r["ret28_diff"] + floors["retention_tolerance"],
                       r["dpi_rel_gain_pct"] - floors["dpi_relative_gain_pct"],
                       -(r["session_diff"] + floors["session_minutes"]),
                       -(r["gap_diff"] + floors["gap_days"]))
        row["margin"] = margin(row)
        rows.append(row)
    g = pd.DataFrame(rows)
    ok = g[(g.ret28_diff >= -floors["retention_tolerance"])
           & (g.dpi_rel_gain_pct >= floors["dpi_relative_gain_pct"])
           & (g.session_diff <= -floors["session_minutes"])
           & (g.gap_diff <= -floors["gap_days"])]
    if len(ok):
        best = ok.sort_values(["ret28_diff", "dpi_rel_gain_pct", "session_diff"],
                              ascending=[False, False, True]).iloc[0]
        rule = "eligible_max_ret28_diff"
    else:
        best = g.sort_values(["margin", "dpi_rel_gain_pct", "session_diff"],
                             ascending=[False, False, True]).iloc[0]
        rule = "fallback_max_worst_margin"
    frozen = dict(cell=str(best["cell"]), rule=rule,
                  grid=g.to_dict(orient="records"))
    os.makedirs(os.path.join(HERE, "outputs"), exist_ok=True)
    with open(os.path.join(HERE, "outputs", "frozen_triad_policy.json"), "w") as f:
        json.dump(frozen, f, indent=1)
    print("[freeze] cell =", frozen["cell"], "rule =", rule, flush=True)
    print(g.to_string(index=False), flush=True)
    return frozen


def stage_confirmation(frozen: dict) -> None:
    cell = frozen["cell"]
    runner18.run_cell("confirmation", "base", cell, HERE, out_dir=RAW)  # all 7 arms
    for abl in ("triad_c", "triad_d"):
        runner18.run_cell("confirmation", "base", abl, HERE,
                          arm_filter={"nexus_triad"}, out_dir=RAW)
    for scen in ("no_monotony", "double_monotony", "no_fatigue_quit",
                 "no_valence_quit", "no_return_valence", "slow_recovery",
                 "skeptical", "hard_skeptical"):
        runner18.run_cell("confirmation", scen, cell, HERE,
                          arm_filter={"fsrs_multitype", "nexus_triad"},
                          out_dir=RAW)
    print("[confirmation] done", flush=True)


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("calib", "all"):
        stage_calib()
    if which in ("freeze", "all"):
        frozen = stage_freeze()
    else:
        frozen = None
    if which in ("confirm", "all"):
        if frozen is None:
            with open(os.path.join(HERE, "outputs", "frozen_triad_policy.json")) as f:
                frozen = json.load(f)
        stage_confirmation(frozen)


if __name__ == "__main__":
    main()
