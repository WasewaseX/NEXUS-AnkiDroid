"""runner18 — v1.8 day loop: v1.6 instrumentation + TRIAD prediction capture.

Inherited UNCHANGED from runner16 (which stays untouched):
  end reasons (premature_quit | budget | planned_goal | work_complete),
  per-session rows, exposure-adjusted quit metrics, scenarios via
  apply_scenario, CRN/seeds/truth/FSRS wrapper/evaluator/DPI endpoint.

v1.8 additions:
  1. ARMS: build_arm_specs18 (7 distinct implementations of the user's 8
     requested arms, including the rwkv_instant and sm20 schedulers).
  2. PREDICTION ROWS: TRIAD logs (P_eff, delta, alpha, P_hybrid, outcome)
     for every DUE-review event; the runner persists them as
     <run>_predictions.csv for the T4 gating analysis.
"""
from __future__ import annotations

import json
import os
import statistics
from typing import List

import pandas as pd

from sim15.behavior import QuitSession  # noqa: F401  (re-exported)
from sim16.behavior_ext import BehaviorState16, apply_scenario
from sim18.policy import build_arm_specs18
from simlib.benchmark.evaluator import NeutralEvaluator
from simlib.env import RNGPool, build_bank, build_population
from simlib.experiments.runner import (
    ArmSpec, MINUTES_PER_DAY, PROBE_OFFSET_MIN, SESSION_START_MIN,
    build_condition, compute_dpi,
)
from simlib.spec import Accumulators, BudgetExhausted

EPS = 1e-6


def resolve_end_reason(exc: str, goal_stop: bool, remaining: float) -> str:
    if exc == "quit":
        return "premature_quit"
    if exc == "budget":
        return "budget"
    if goal_stop:
        return "planned_goal"
    if remaining <= EPS:
        return "budget"
    return "work_complete"


def run_career18(arm: ArmSpec, learner, bank, rep: int, cfg14: dict,
                 cfg15_eff: dict, cfg18: dict, frustration: bool = True,
                 regime: str = "neutral", experiment: str = ""):
    """One learner-career for one arm; returns career + rows incl. TRIAD
    prediction rows."""
    import copy as _copy
    learner = _copy.deepcopy(learner)
    pool = RNGPool(cfg14["master_seed"])
    params = dict(cfg14["regimes"][regime])

    behavior = BehaviorState16(
        cfg15_eff, pool.spawn("behavior-base", rep, learner.learner_id),
        frustration=frustration)
    from sim15.behavior import fatigue_penalized_truth
    truth = fatigue_penalized_truth(
        learner, params, pool.spawn("truth", rep, learner.learner_id), behavior)

    from simlib.schedulers import FACTORIES
    sched = FACTORIES[arm.scheduler_name](cfg14)

    method = arm.method_builder(learner, cfg15_eff)
    method.bind_bank(bank)
    evaluator = NeutralEvaluator(cfg14)
    accum = Accumulators()
    probe_days = set(int(d) for d in cfg14["probe_days"])

    session_rows: List[dict] = []
    prediction_rows: List[dict] = []
    warnings = 0
    probe_rows: list = []
    diag_rows: list = []
    horizon = int(cfg14["horizon_days"])

    for day in range(1, horizon + 1):
        truth.on_day_boundary(day)
        behavior.morning(day)

        rng_ret = pool.spawn("behavior-return", rep, learner.learner_id, day)
        u_open = float(rng_ret.random())
        opens = (day == 1) or (u_open < behavior.p_open(day, is_day1=(day == 1)))

        if opens:
            rng_day = pool.spawn("day", rep, learner.learner_id, day)
            condition = build_condition(cfg14, params, "none", day, rng_day)
            from sim15.behavior import QuitAwareSessionContext
            ctx = QuitAwareSessionContext(
                learner=learner, bank=bank, truth=truth, rng=rng_day,
                sched={"main": sched}, condition=condition, accum=accum,
                t_min=(day - 1) * MINUTES_PER_DAY + SESSION_START_MIN,
                day=day, budget_min=float(learner.daily_minutes),
                behavior=behavior,
                rng_quit=pool.spawn("behavior-quit", rep, learner.learner_id, day),
            )
            snap = (getattr(method, "due_scheduled", 0), getattr(method, "enc_due", 0),
                    getattr(method, "enc_new", 0), getattr(method, "events", 0))
            exc = "none"
            try:
                method.run_session(ctx)
            except QuitSession:
                exc = "quit"
            except BudgetExhausted:
                exc = "budget"
                warnings += 1
            reason = resolve_end_reason(exc, bool(getattr(method, "goal_stop", False)),
                                        ctx.remaining())
            behavior.close_session(day, ended_by_quit=(reason == "premature_quit"))
            due_done = getattr(method, "enc_due", 0) - snap[1]
            new_done = getattr(method, "enc_new", 0) - snap[2]
            session_rows.append(dict(
                arm=arm.name, rep=rep, learner_id=learner.learner_id, day=day,
                minutes=float(ctx.elapsed_min), end_reason=reason,
                due_scheduled=int(getattr(method, "due_scheduled", 0)),
                due_done=int(due_done), n_new=int(new_done),
                events=int(getattr(method, "events", 0) - snap[3]),
            ))

        if day in probe_days:
            prows, drows = evaluator.run_probes(
                truth, learner, bank,
                t_min=(day - 1) * MINUTES_PER_DAY + SESSION_START_MIN + PROBE_OFFSET_MIN,
                day=day, sched=sched,
                rng=pool.spawn("probe", rep, learner.learner_id, day),
                condition_overrides={})
            for row in prows:
                row.update(arm=arm.name, regime=regime, stress="none",
                           rep=rep, experiment=experiment)
            for row in drows:
                row.update(arm=arm.name, regime=regime, stress="none",
                           rep=rep, experiment=experiment)
            probe_rows.extend(prows)
            diag_rows.extend(drows)

    # TRIAD prediction rows (after the full career: alpha final everywhere)
    gate = getattr(method, "gate", None)
    if gate is not None and hasattr(gate, "prediction_rows"):
        prediction_rows.extend(
            gate.prediction_rows(arm.name, rep, learner.learner_id))

    # ------------------------------------------------------- career metrics
    acc = accum.as_dict()
    n_sess = len(session_rows)
    minutes_all = [r["minutes"] for r in session_rows]
    gaps, prev_open = [], None
    for r in session_rows:
        if prev_open is not None:
            gaps.append(r["day"] - prev_open)
        prev_open = r["day"]

    def rate(reason: str) -> float:
        return (sum(1 for r in session_rows if r["end_reason"] == reason) / n_sess
                if n_sess else 0.0)

    def mean_min(reason: str) -> float:
        vals = [r["minutes"] for r in session_rows if r["end_reason"] == reason]
        return float(statistics.mean(vals)) if vals else 0.0

    n_pq = sum(1 for r in session_rows if r["end_reason"] == "premature_quit")
    total_min = float(sum(minutes_all))
    quit_mins = [r["minutes"] for r in session_rows
                 if r["end_reason"] == "premature_quit"]
    due_sched_total = sum(r["due_scheduled"] for r in session_rows)
    due_done_total = sum(r["due_done"] for r in session_rows)

    career = dict(
        arm=arm.name, experiment=experiment, scenario=experiment, regime=regime,
        rep=rep, archetype=learner.archetype, learner_id=learner.learner_id,
        study_minutes=float(acc.get("study_minutes", 0.0)),
        encounters=int(acc.get("encounters", 0)),
        new_items=int(acc.get("new_items", 0)),
        n_days=horizon, n_sessions=n_sess,
        opened_rate=n_sess / horizon if horizon else 0.0,
        session_minutes_mean=float(statistics.mean(minutes_all)) if minutes_all else 0.0,
        session_minutes_median=float(statistics.median(minutes_all)) if minutes_all else 0.0,
        mean_gap_days=float(statistics.mean(gaps)) if gaps else float(horizon),
        total_active_minutes=total_min,
        premature_quit_rate=rate("premature_quit"),
        planned_stop_rate=rate("planned_goal"),
        work_complete_rate=rate("work_complete"),
        budget_rate=rate("budget"),
        min_premature_quit=mean_min("premature_quit"),
        min_planned_goal=mean_min("planned_goal"),
        min_work_complete=mean_min("work_complete"),
        min_budget=mean_min("budget"),
        time_to_quit_mean=float(statistics.mean(quit_mins)) if quit_mins else 0.0,
        quit_intensity_per100min=(100.0 * n_pq / total_min) if total_min > EPS else 0.0,
        due_sched_total=int(due_sched_total),
        due_done_total=int(due_done_total),
        due_completion_rate=(due_done_total / due_sched_total) if due_sched_total > 0 else 1.0,
        enc_per_session=(acc.get("encounters", 0) / n_sess) if n_sess else float("nan"),
        fatigue_end=float(behavior.F),
        valence_end=float(behavior.valence),
        # ---- v1.8 TRIAD diagnostics (0 for non-TRIAD arms)
        triad_alpha_final=float(getattr(gate, "alpha", 0.0) or 0.0) if gate is not None else 0.0,
        triad_fit_reason=(gate.fit_summary.get("reason", "n/a") if gate is not None and gate.fit_summary else
                          ("off" if gate is None else "not_fitted")),
        scope_events=int(getattr(method, "scope_events", 0)),
    )
    return career, probe_rows, diag_rows, session_rows, prediction_rows


def run_experiment18(name: str, cfg14: dict, cfg15_eff: dict, cfg18: dict,
                     cell_id: str, frustration: bool, master_seed: int,
                     n_reps=None, n_per_arch=None, out_dir: str = "outputs/raw",
                     arm_filter=None) -> List[str]:
    """reps x population x arms; bank/population shared across arms per rep."""
    if n_reps is None:
        n_reps = int(cfg15_eff["population"]["n_reps"])
    if n_per_arch is None:
        n_per_arch = int(cfg15_eff["population"]["n_learners_per_archetype"])
    cfg_local = dict(cfg14)
    cfg_local["master_seed"] = int(master_seed)
    cfg_local["population"] = {**cfg14["population"],
                               "n_learners_per_archetype": int(n_per_arch)}

    pool = RNGPool(int(master_seed))
    career_rows: list = []
    probe_rows: list = []
    diag_rows: list = []
    session_rows: list = []
    prediction_rows: list = []

    specs = [s for s in build_arm_specs18(cell_id, cfg18)
             if arm_filter is None or s.name in arm_filter]

    for rep in range(int(n_reps)):
        bank = build_bank(cfg_local, pool, rep)
        population = build_population(cfg_local, pool, rep)
        for learner in population:
            for arm in specs:
                career, prows, drows, srows, predr = run_career18(
                    arm, learner, bank, rep, cfg_local, cfg15_eff, cfg18,
                    frustration=frustration, experiment=name)
                career_rows.append(career)
                probe_rows.extend(prows)
                diag_rows.extend(drows)
                session_rows.extend(srows)
                prediction_rows.extend(predr)
        print(f"[run_experiment18:{name}] rep {rep + 1}/{n_reps} done "
              f"({len(population)} learners x {len(specs)} arms)", flush=True)

    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for df, suffix in ((pd.DataFrame(career_rows), "careers"),
                       (pd.DataFrame(probe_rows), "probes"),
                       (pd.DataFrame(diag_rows), "diag"),
                       (pd.DataFrame(session_rows), "sessions"),
                       (pd.DataFrame(prediction_rows), "predictions")):
        path = os.path.join(out_dir, f"{name}_{suffix}.csv")
        df.to_csv(path, index=False)
        paths.append(path)
    return paths


def load_cfgs(here: str):
    with open(os.path.join(here, "config18.json")) as f:
        cfg18 = json.load(f)
    with open(os.path.join(here, "..", "v14_methods_benchmark", "config.json")) as f:
        cfg14 = json.load(f)
    with open(os.path.join(here, "..", "v15_nexus_mix_benchmark", "config15.json")) as f:
        cfg15 = json.load(f)
    return cfg18, cfg14, cfg15


def run_cell(block: str, scenario: str, cell_id: str, here: str,
             n_reps=None, n_per_arch=None, out_dir=None,
             arm_filter=None) -> List[str]:
    """One (block, scenario, cell) run. Name convention:
    v18_{block}_{scenario}_{cell}."""
    cfg18, cfg14, cfg15 = load_cfgs(here)
    spec = cfg18["v18_scenarios"][scenario]
    cfg_eff, frustration = apply_scenario(cfg15, spec)
    seed = int(cfg18["master_seed_blocks"][block])
    name = f"v18_{block}_{scenario}_{cell_id}"
    out = out_dir or os.path.join(here, "outputs", "raw")
    return run_experiment18(name, cfg14, cfg_eff, cfg18, cell_id, frustration,
                            master_seed=seed, n_reps=n_reps,
                            n_per_arch=n_per_arch, out_dir=out,
                            arm_filter=arm_filter)


def main(argv=None) -> None:
    import argparse
    here = os.path.abspath(os.path.dirname(__file__))
    ap = argparse.ArgumentParser(description="v1.8 NEXUS-TRIAD runner")
    ap.add_argument("--block", required=True,
                    choices=["calibration", "confirmation"])
    ap.add_argument("--scenario", default="base")
    ap.add_argument("--cell", default="triad_a")
    ap.add_argument("--arms", default=None,
                    help="comma-separated arm filter (default: all 7)")
    ap.add_argument("--n-reps", type=int, default=None)
    ap.add_argument("--n-per-arch", type=int, default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)
    arm_filter = (set(args.arms.split(",")) if args.arms else None)
    paths = run_cell(args.block, args.scenario, args.cell, here,
                     n_reps=args.n_reps, n_per_arch=args.n_per_arch,
                     out_dir=args.out_dir, arm_filter=arm_filter)
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
