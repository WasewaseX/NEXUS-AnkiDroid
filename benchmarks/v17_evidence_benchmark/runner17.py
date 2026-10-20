"""runner17 — v1.7 day loop: v1.6 flow + per-review event diagnostics.

Design: runner16.run_career16 is used VERBATIM (no code duplication) so the
shared arm is bit-identical to v1.6 by construction. Logging is injected by
temporarily patching simlib's FSRS factory with a TRANSPARENT PROXY that
records (r_before, s_before, grade, t) for every graded review BEFORE
delegating the update. The proxy consumes NO RNG and reads only scheduler
state + bank tags, so behavior cannot change — the replication audit
(analyze17) verifies this against the v1.6 confirmation-base numbers.

Outputs per cell: {name}_{careers,probes,diag,sessions,events}.csv
"""
from __future__ import annotations

import contextvars
import json
import os
import sys
from typing import List

import pandas as pd

HERE = os.path.abspath(os.path.dirname(__file__))
V16 = os.path.abspath(os.path.join(HERE, "..", "v16_nexus_mix2_benchmark"))
V15 = os.path.abspath(os.path.join(HERE, "..", "v15_nexus_mix_benchmark"))
V14 = os.path.abspath(os.path.join(HERE, "..", "v14_methods_benchmark"))
for p in (V14, V15, V16):
    if p not in sys.path:
        sys.path.insert(0, p)

import runner16  # noqa: E402  (v16 runner, used verbatim)
from runner16 import SESSION_START_MIN, MINUTES_PER_DAY, resolve_end_reason  # noqa: E402,F401
from simlib.schedulers import FACTORIES  # noqa: E402
from sim16.behavior_ext import apply_scenario  # noqa: E402
from sim17.triad import build_arm_specs17  # noqa: E402

# ------------------------------------------------------------------ logging
_event_rows: List[dict] = []
_log_ctx: contextvars.ContextVar = contextvars.ContextVar("triad_log_ctx",
                                                          default=None)


def _skill_of(bank, item_id: int) -> str:
    try:
        return str(bank.get(int(item_id)).skill)
    except Exception:
        return "?"


class LoggingFSRSProxy:
    """Transparent wrapper: log-then-delegate. No RNG, no behavior change."""

    def __init__(self, inner):
        self._inner = inner

    # -- scheduler interface ------------------------------------------------
    def add_new(self, item_id: int, t_min: float) -> None:
        c = _log_ctx.get()
        if c is not None:
            day = int(float(t_min) // MINUTES_PER_DAY) + 1
            _event_rows.append(dict(
                arm=c["arm"], rep=c["rep"], learner_id=c["learner_id"],
                day=day, t_min=float(t_min), skill=_skill_of(c["bank"], item_id),
                item_id=int(item_id), grade=0, success=False,
                r_before=0.0, s_before=None, is_new=True))
        return self._inner.add_new(item_id, t_min)

    def review(self, item_id: int, t_min: float, grade: int) -> None:
        c = _log_ctx.get()
        if c is not None:
            r_before = self._inner.predicted_retrievability(item_id, float(t_min))
            s_before = self._inner.stability_estimate(item_id)
            day = int(float(t_min) // MINUTES_PER_DAY) + 1
            _event_rows.append(dict(
                arm=c["arm"], rep=c["rep"], learner_id=c["learner_id"],
                day=day, t_min=float(t_min), skill=_skill_of(c["bank"], item_id),
                item_id=int(item_id), grade=int(grade),
                success=bool(int(grade) >= 2), r_before=float(r_before),
                s_before=(float(s_before) if s_before is not None else None),
                is_new=False))
        return self._inner.review(item_id, t_min, grade)

    def due(self, t_min: float, limit: int | None = None) -> list:
        return self._inner.due(t_min, limit)

    def predicted_retrievability(self, item_id: int, t_min: float):
        return self._inner.predicted_retrievability(item_id, t_min)

    def stability_estimate(self, item_id: int):
        return self._inner.stability_estimate(item_id)

    def __getattr__(self, name):  # delegate everything else verbatim
        return getattr(self._inner, name)


# ------------------------------------------------------------------ runner
def run_experiment17(name: str, cfg14: dict, cfg15_eff: dict, variant: str,
                     frustration: bool, master_seed: int, n_reps=None,
                     n_per_arch=None, out_dir: str = "outputs/raw",
                     rep_offset: int = 0) -> List[str]:
    """reps x population x [fsrs_multitype, <variant arm>]; proxy-patched.

    rep_offset: run only reps [rep_offset, rep_offset+n_reps) and write
    rep-chunk files {name}_r{rep_offset}_{suffix}.csv — lets a long cell be
    executed in foreground chunks (tool-call timeout) without changing the
    RNG: pool.spawn paths depend on (rep, learner_id) labels only."""
    global _event_rows
    if n_reps is None:
        n_reps = int(cfg15_eff["population"]["n_reps"])
    if n_per_arch is None:
        n_per_arch = int(cfg15_eff["population"]["n_learners_per_archetype"])
    cfg_local = dict(cfg14)
    cfg_local["master_seed"] = int(master_seed)
    cfg_local["population"] = {**cfg14["population"],
                               "n_learners_per_archetype": int(n_per_arch)}

    from simlib.env import RNGPool, build_bank, build_population
    from simlib.schedulers.fsrs import FSRS

    arms = build_arm_specs17(variant)

    def proxy_factory(cfg):
        return LoggingFSRSProxy(FSRS(cfg))

    original = FACTORIES.get("fsrs")
    FACTORIES["fsrs"] = proxy_factory
    pool = RNGPool(int(master_seed))
    career_rows: list = []
    probe_rows: list = []
    diag_rows: list = []
    session_rows: list = []
    try:
        for rep in range(int(rep_offset), int(rep_offset) + int(n_reps)):
            bank = build_bank(cfg_local, pool, rep)
            population = build_population(cfg_local, pool, rep)
            for learner in population:
                for arm in arms:
                    _log_ctx.set(dict(arm=arm.name, rep=rep,
                                      learner_id=learner.learner_id, bank=bank))
                    career, prows, drows, srows = runner16.run_career16(
                        arm, learner, bank, rep, cfg_local, cfg15_eff,
                        frustration=frustration, experiment=name)
                    career_rows.append(career)
                    probe_rows.extend(prows)
                    diag_rows.extend(drows)
                    session_rows.extend(srows)
            _log_ctx.set(None)
            print(f"[run_experiment17:{name}] rep {rep + 1}/{n_reps} done "
                  f"({len(population)} learners x 2 arms)")
    finally:
        _log_ctx.set(None)
        if original is not None:
            FACTORIES["fsrs"] = original
        else:
            FACTORIES.pop("fsrs", None)

    os.makedirs(out_dir, exist_ok=True)
    paths = []
    tag = f"_r{int(rep_offset)}" if rep_offset else ""
    for df, suffix in ((pd.DataFrame(career_rows), "careers"),
                       (pd.DataFrame(probe_rows), "probes"),
                       (pd.DataFrame(diag_rows), "diag"),
                       (pd.DataFrame(session_rows), "sessions"),
                       (pd.DataFrame(_event_rows), "events")):
        path = os.path.join(out_dir, f"{name}{tag}_{suffix}.csv")
        df.to_csv(path, index=False)
        paths.append(path)
    _event_rows.clear()
    return paths


def load_cfgs17(here: str):
    here = os.path.abspath(here)
    with open(os.path.join(here, "config17.json")) as f:
        cfg17 = json.load(f)
    with open(os.path.join(V14, "config.json")) as f:
        cfg14 = json.load(f)
    with open(os.path.join(V15, "config15.json")) as f:
        cfg15 = json.load(f)
    return cfg17, cfg14, cfg15


def run_cell17(scenario: str, variant: str, here: str, n_reps=None,
               n_per_arch=None, out_dir=None, rep_offset: int = 0) -> List[str]:
    """One (scenario, variant) run chunk. Name convention:
    v17_{scenario}_{variant} (chunk tag _r{rep_offset} when chunked)."""
    cfg17, cfg14, cfg15 = load_cfgs17(here)
    spec = cfg17["scenarios_run"][scenario]
    cfg_eff, frustration = apply_scenario(cfg15, spec)
    seed = int(cfg17["master_seed_blocks"]["confirmation"])
    name = f"v17_{scenario}_{variant}"
    out = out_dir or os.path.join(HERE, "outputs", "raw")
    return run_experiment17(name, cfg14, cfg_eff, variant, frustration,
                            master_seed=seed, n_reps=n_reps,
                            n_per_arch=n_per_arch, out_dir=out,
                            rep_offset=rep_offset)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="v1.7 NEXUS-TRIAD two-arm runner")
    ap.add_argument("--scenario", default="base")
    ap.add_argument("--variant", default="nexus_triad",
                    choices=["nexus_triad", "triad_no_risk_order",
                             "triad_no_pacing"])
    ap.add_argument("--n-reps", type=int, default=None)
    ap.add_argument("--n-per-arch", type=int, default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--rep-offset", type=int, default=0)
    args = ap.parse_args(argv)
    paths = run_cell17(args.scenario, args.variant, HERE,
                       n_reps=args.n_reps, n_per_arch=args.n_per_arch,
                       out_dir=args.out_dir, rep_offset=args.rep_offset)
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
