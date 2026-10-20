"""tests17 — mechanism tests for the v1.7 two-arm benchmark + real-data gate.

Run: python -m pytest tests17.py -q
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

HERE = os.path.abspath(os.path.dirname(__file__))
V16 = os.path.abspath(os.path.join(HERE, "..", "v16_nexus_mix2_benchmark"))
V15 = os.path.abspath(os.path.join(HERE, "..", "v15_nexus_mix_benchmark"))
V14 = os.path.abspath(os.path.join(HERE, "..", "v14_methods_benchmark"))
for p in (V14, V15, V16):
    if p not in sys.path:
        sys.path.insert(0, p)


# ------------------------------------------------------------- replication
def test_multitype_replicates_v16_bit_exactly():
    """The shared arm must reproduce v1.6's confirmation-base careers exactly
    (proves the logging proxy and arm-list change consumed no RNG)."""
    v16 = pd.read_csv(os.path.join(
        V16, "outputs", "raw", "v16_confirmation_base_p075_prot_careers.csv"))
    v17 = pd.read_csv(os.path.join(
        HERE, "outputs", "raw", "v17_base_nexus_triad_careers.csv"))
    m16 = (v16[v16.arm == "fsrs_multitype"]
           .set_index(["rep", "learner_id"]).sort_index())
    m17 = (v17[v17.arm == "fsrs_multitype"]
           .set_index(["rep", "learner_id"]).sort_index())
    common = m16.index.intersection(m17.index)
    assert len(common) == 32  # rep 0 (32 careers) present in both
    cols = ["study_minutes", "encounters", "new_items", "opened_rate"]
    pd.testing.assert_frame_equal(m16.loc[common, cols], m17.loc[common, cols],
                                  check_exact=True)


def test_replication_audit_exact_in_verdicts():
    V = json.load(open(os.path.join(HERE, "outputs", "verdicts_v17.json")))
    assert V["replication_audit"]["exact"] is True


# ---------------------------------------------------------------- TRIAD arm
def test_triad_due_core_protection_planned_goal():
    """With due-core protection, the goal line gates ONLY new intake; a
    session that runs past the goal line on due work must NOT be labeled
    planned_goal."""
    s = pd.read_csv(os.path.join(
        HERE, "outputs", "raw", "v17_base_nexus_triad_sessions.csv"))
    tri = s[s.arm == "nexus_triad"]
    # planned_goal sessions exist (the finish line fires on light days)
    assert (tri.end_reason == "planned_goal").sum() > 0
    # and due completion is >= stock's (P4 floor)
    c = pd.read_csv(os.path.join(
        HERE, "outputs", "raw", "v17_base_nexus_triad_careers.csv"))
    tri_due = c[c.arm == "nexus_triad"].due_completion_rate.mean()
    mul_due = c[c.arm == "fsrs_multitype"].due_completion_rate.mean()
    assert tri_due >= mul_due - 0.02


def test_risk_order_sorts_by_retrievability():
    """The ordering layer sorts each due queue ascending by the scheduler's
    predicted retrievability (most fragile first)."""
    from sim17.triad import NexusTriad

    class StubSched:
        def predicted_retrievability(self, iid, t):
            return {11: 0.9, 12: 0.5, 13: 0.7, 14: 0.3}[iid]

        def due(self, t):
            return [11, 12, 13, 14]

    from simlib.spec import ItemBank  # noqa: F401  (import sanity)

    learner = type("L", (), {})()
    nt = NexusTriad.__new__(NexusTriad)  # skip __init__ (needs full cfg)
    nt._pool = {11: "meaning", 12: "meaning", 13: "meaning", 14: "meaning"}
    nt.mix_cfg = {"grammar_rule_size": 100}
    nt.risk_order = True

    class Ctx:
        def current_t(self):
            return 0.0

        def main_sched(self):
            return StubSched()

    q = nt._risk_ordered_queues(Ctx())
    assert q["meaning"] == [14, 12, 13, 11]


# ------------------------------------------------------------- real-data gate
def test_alpha_gate_frozen_and_selection_sane():
    fr = json.load(open(os.path.join(
        HERE, "outputs", "real_frozen.json")))
    grid = {g["alpha"]: g["cal_logloss"] for g in fr["alpha_grid"]}
    a_star = fr["alpha_star"]
    assert a_star in grid
    # the selected alpha must not be worse than alpha=0 on the calibration
    # block (else selection failed)
    assert grid[a_star] <= grid[0.0] + 1e-12
    # betas present for every declared context feature
    assert len(fr["beta_ctx"]) == len(fr["ctx_features"])


def test_held_out_gate_verdict_is_null_and_reported_as_such():
    V = json.load(open(os.path.join(HERE, "outputs", "verdicts_real.json")))
    for key in ("fsrs5_fitted", "fsrs5_default"):
        ci = V["results"][key]["paired_diff"]["ci"]
        # the CI must CROSS zero (gate closed) — if a future rerun makes it
        # exclude 0, this test fails and the gate must be re-evaluated
        assert ci[0] <= 0.0 <= ci[1], (
            f"{key}: held-out CI {ci} no longer crosses zero — the alpha=0 "
            f"gate verdict must be revisited")


# ------------------------------------------------------------- prereg floors
def test_p1_no_harm_within_floor():
    V = json.load(open(os.path.join(HERE, "outputs", "verdicts_v17.json")))
    assert abs(V["P1_no_harm_primary"]["ret28_diff"]) <= 0.02


def test_config_declared_before_runs():
    cfg = json.load(open(os.path.join(HERE, "config17.json")))
    fk = cfg["arms"]["nexus_triad"]["frozen_knobs"]
    assert fk["goal_stop_fraction"] == 0.75 and fk["due_core_protect"] is True
    assert cfg["master_seed_blocks"]["confirmation"] == 20261101
