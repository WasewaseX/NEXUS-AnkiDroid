"""tests18 — v1.8 mechanics tests (no outcome expectations anywhere).

Run:  python3 tests18.py
Covers: hybrid formula identity, shrinkage math, delta clip, session-scope
fatigue reset, alpha-gate acceptance rules, no-due-skipping, prediction-row
integrity, SCOPE gates, alt-scheduler arms, end reasons, determinism.
"""
from __future__ import annotations

import copy
import math
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
from sim18.triad import (AlphaGate, ContextState, SkillPriors, brier,  # noqa: E402
                         hybrid, logit, logloss, sigmoid)
from sim18.policy import TriadFull, build_arm_specs18  # noqa: E402


def _cfgs():
    return runner18.load_cfgs(HERE)


# ------------------------------------------------------------ pure math
def test_hybrid_formula():
    # alpha=0 -> exactly P_eff (user's rule: contextual term starts at zero)
    assert abs(hybrid(0.9, 0.7, 0.0) - 0.9) < 1e-12
    # formula check against manual computation
    p, d, a = 0.85, 0.4, 0.5
    expect = 1.0 / (1.0 + math.exp(-(math.log(p / (1 - p)) + a * d)))
    assert abs(hybrid(p, d, a) - expect) < 1e-12
    # bounds
    assert 0.0 < hybrid(0.5, 1.5, 1.0) < 1.0
    assert 0.0 < hybrid(0.5, -1.5, 1.0) < 1.0


def test_logit_sigmoid_roundtrip():
    for p in (0.01, 0.3, 0.5, 0.77, 0.99):
        assert abs(sigmoid(logit(p)) - p) < 1e-9


def test_metrics():
    assert abs(brier([(0.8, 1.0), (0.2, 0.0)]) - 0.04) < 1e-12
    ll = logloss([(0.999, 1.0), (0.001, 0.0)])
    assert ll < 1e-2


# ------------------------------------------------------------ priors
def test_priors_shrinkage_math():
    sp = SkillPriors(k_skill=8.0, k_card=3.0)
    # n=0 -> exactly the prior mean (Beta(1,1) -> 0.5)
    assert abs(sp.mean("meaning") - 0.5) < 1e-12
    assert abs(sp.shrunk_level("meaning", 0.9, 0) - 0.5) < 1e-12
    # shrunk_level = (n*lvl + k*mean)/(n+k)
    sp.update("meaning", True)
    sp.update("meaning", True)
    sp.update("meaning", False)
    mean = (1.0 + 2) / (2.0 + 3)          # (alpha=3, beta=2)
    assert abs(sp.mean("meaning") - mean) < 1e-12
    got = sp.shrunk_level("meaning", 0.9, 4)
    assert abs(got - (4 * 0.9 + 8 * mean) / 12) < 1e-12
    # card shrinkage: n >= k_card -> exactly p_sched
    assert sp.shrunk_p("meaning", 0.83, 3) == 0.83
    got = sp.shrunk_p("meaning", 0.83, 1)
    assert abs(got - (1 * 0.83 + 3 * mean) / 4) < 1e-12


# ------------------------------------------------------------ context
def _ctx_state():
    cfg18, _, _ = _cfgs()
    return ContextState(cfg18["triad_constants"])


def test_delta_neutral_start_and_clip():
    cs = _ctx_state()
    cs.start_session(day=2, due_count=15, budget_min=20.0)
    # neutral: acc at reference, no slowdown, workload 0.5, no fatigue, no gap
    assert abs(cs.delta()) < 1e-9
    # extreme gap + workload + fatigue pushes negative but stays clipped
    cs.gap_days = 30
    cs.due_count = 90
    cs.session_events = 100
    cs.session_elapsed = 100.0
    d = cs.delta()
    assert d >= -1.5 - 1e-12 and d < 0


def test_fatigue_proxy_session_scope_only():
    cs = _ctx_state()
    cs.start_session(2, 10, 20.0)
    cs.session_events = 30
    cs.session_elapsed = 10.0
    assert abs(cs.fatigue_proxy() - (30 / 40 + 10 / 20)) < 1e-12
    # NEW session: reset (never persists)
    cs.end_session(2)
    cs.start_session(3, 5, 20.0)
    assert cs.fatigue_proxy() == 0.0
    assert cs.gap_days == 1


def test_slowdown_kind_controlled():
    cs = _ctx_state()
    cs.start_session(2, 10, 20.0)
    for _ in range(6):
        cs.observe_event("review", 0.35, "meaning", True)
    assert abs(cs.slowdown() - 1.0) < 1e-9
    for _ in range(6):
        cs.observe_event("review", 0.70, "meaning", True)
    assert cs.slowdown() > 1.0


# ------------------------------------------------------------ alpha gate
def _gate():
    cfg18, _, _ = _cfgs()
    return AlphaGate(cfg18["triad_constants"])


def test_gate_requires_gate_day_and_events():
    g = _gate()
    for day in range(1, 14):
        g.log(day, 0.9, 0.5, 1.0)
    g.maybe_fit(13)
    assert g.alpha == 0.0 and not g.fitted
    g.maybe_fit(14)
    assert g.fitted and g.alpha == 0.0            # 13 events < min_events
    assert g.fit_summary["reason"] == "insufficient_events"


def test_gate_accepts_only_real_improvement():
    g = _gate()
    # strongly informative delta: correct when delta>0, wrong when delta<0
    day = 1
    for i in range(60):
        d = 1.2 if i % 2 == 0 else -1.2
        g.log(day, 0.5, d, 1.0 if d > 0 else 0.0)
    g.maybe_fit(14)
    assert g.alpha > 0.0
    assert g.fit_summary["reason"] == "accepted"
    assert g.fit_summary["improvement"] >= g.min_improvement
    # rows count preserved; val split deterministic
    n_val = sum(1 for r in g.rows if r[4] % 10 < 3)
    assert n_val >= 1


def test_gate_rejects_noise():
    g = _gate()
    day = 1
    for i in range(60):
        g.log(day, 0.5, 0.0, 1.0 if i % 2 == 0 else 0.0)
    g.maybe_fit(14)
    assert g.alpha == 0.0


def test_gate_deterministic():
    a, b = _gate(), _gate()
    for i in range(60):
        d = 1.0 if i % 3 else -0.5
        for g in (a, b):
            g.log(1, 0.5, d, 1.0 if d > 0 else 0.0)
    a.maybe_fit(14)
    b.maybe_fit(14)
    assert a.alpha == b.alpha
    assert a.fit_summary == b.fit_summary


# ------------------------------------------------------------ end reasons
def test_resolve_end_reason_total():
    r = runner18.resolve_end_reason
    assert r("quit", False, 5.0) == "premature_quit"
    assert r("budget", False, 0.0) == "budget"
    assert r("none", True, 3.0) == "planned_goal"
    assert r("none", False, 0.0) == "budget"
    assert r("none", False, 9.0) == "work_complete"


# ---------------------------------------------------------- tiny e2e runs
def _tiny_cfg14(cfg14):
    c = copy.deepcopy(cfg14)
    c["horizon_days"] = 7
    c["probe_days"] = [7]
    return c


def test_all_arms_run_end_to_end():
    cfg18, cfg14, cfg15 = _cfgs()
    cfg14t = _tiny_cfg14(cfg14)
    out = os.path.join(HERE, "outputs", "test_smoke")
    paths = runner18.run_experiment18(
        "v18_test_e2e", cfg14t, cfg15, cfg18, "triad_a", True,
        master_seed=12345, n_reps=1, n_per_arch=1, out_dir=out)
    for p in paths:
        assert os.path.exists(p), p
    import pandas as pd
    careers = pd.read_csv(paths[0])
    arms = set(careers["arm"])
    assert arms == {"fsrs_recall_only", "fsrs_multitype", "nexus_scope20",
                    "nexus_mix2", "nexus_triad", "rwkv_instant", "sm20"}
    preds = pd.read_csv(paths[4])
    if len(preds):
        assert set(preds["arm"]) == {"nexus_triad"}
        assert preds["p_eff"].between(0.0, 1.0).all()
        assert preds["p_hybrid"].between(0.0, 1.0).all()
        # alpha in the declared grid only
        assert set(preds["alpha"]).issubset({0.0, 0.25, 0.5, 0.75, 1.0})


def test_triad_never_skips_due():
    cfg18, cfg14, cfg15 = _cfgs()
    cfg14t = _tiny_cfg14(cfg14)
    out = os.path.join(HERE, "outputs", "test_due")
    paths = runner18.run_experiment18(
        "v18_test_due", cfg14t, cfg15, cfg18, "triad_a", True,
        master_seed=777, n_reps=1, n_per_arch=2, out_dir=out,
        arm_filter={"nexus_triad"})
    import pandas as pd
    sess = pd.read_csv(paths[3])
    ok = sess[sess["end_reason"] != "premature_quit"]
    # every non-quit session completed ALL scheduled due reviews
    assert (ok["due_done"] >= ok["due_scheduled"]).all()


def test_determinism_same_seed():
    cfg18, cfg14, cfg15 = _cfgs()
    cfg14t = _tiny_cfg14(cfg14)
    out = os.path.join(HERE, "outputs", "test_det")
    p1 = runner18.run_experiment18(
        "v18_test_det", cfg14t, cfg15, cfg18, "triad_a", True,
        master_seed=999, n_reps=1, n_per_arch=1, out_dir=out,
        arm_filter={"nexus_triad", "fsrs_multitype"})
    c1 = open(p1[0]).read()
    p2 = runner18.run_experiment18(
        "v18_test_det", cfg14t, cfg15, cfg18, "triad_a", True,
        master_seed=999, n_reps=1, n_per_arch=1, out_dir=out,
        arm_filter={"nexus_triad", "fsrs_multitype"})
    c2 = open(p2[0]).read()
    assert c1 == c2


def test_arm_registry_shape():
    cfg18, _, _ = _cfgs()
    specs = build_arm_specs18("triad_a", cfg18)
    names = [s.name for s in specs]
    scheds = {s.name: s.scheduler_name for s in specs}
    assert names == ["fsrs_recall_only", "fsrs_multitype", "nexus_scope20",
                     "nexus_mix2", "nexus_triad", "rwkv_instant", "sm20"]
    assert scheds["rwkv_instant"] == "rwkv_instant"
    assert scheds["sm20"] == "sm20"
    assert scheds["nexus_triad"] == "fsrs"      # FSRS authoritative in TRIAD


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} tests pass")
    sys.exit(1 if failed else 0)
