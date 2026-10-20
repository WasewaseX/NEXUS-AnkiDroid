"""sim17.triad — the NEXUS-TRIAD scheduling arm (v1.7).

Everything SUBCLASSES sim16.policy classes (imported unmodified). TRIAD owns
scheduling through the declared layers; FSRS stays the authoritative per-card
memory engine — interval math is NEVER touched (alpha=0 gate):

1. REVIEW PRIORITIZATION (the layer under test): per-skill due queues are
   sorted by ASCENDING scheduler-predicted retrievability (most fragile
   first) before the v1.5 dishabituation interleave. Inputs: the scheduler's
   OWN estimates (allowed per sim15 NEUTRALITY: methods see the scheduler's
   estimates) and the item bank's public tags. No truth access.
2. SESSION CONTROL: goal line at 75% of budget + due-core protection —
   knobs FROZEN from the v1.6 frozen policy (p075_prot), not re-tuned.
3. COLD-START PRIORS: weakest-skill-biased intake quota (v1.5 mix rule).

Ablation variants (declared in config17.json):
- risk_order=False  -> queues in scheduler-native order (most-overdue first)
- goal_stop_fraction=1.0 -> no goal line (grinds to budget)
"""
from __future__ import annotations

from collections import OrderedDict

from sim16.policy import _InstrumentedBase
from sim15.mix import SKILL_ORDER, build_interleave_order, grammar_round_robin
from simlib.spec import SessionContext


class NexusTriad(_InstrumentedBase):
    """TRIAD-owns-scheduling arm: risk-ordered due queue + v1.5 interleave
    + frozen pacing (goal 0.75 + due-core protection) + cold-start priors."""

    name = "nexus_triad"

    def __init__(self, learner, cfg15: dict, goal_stop_fraction: float = 0.75,
                 due_core_protect: bool = True, risk_order: bool = True):
        super().__init__(learner, cfg15, SKILL_ORDER)
        self.goal_fraction = float(goal_stop_fraction)
        self.due_protect = bool(due_core_protect)
        self.risk_order = bool(risk_order)

    # ------------------------------------------------------------ TRIAD layer
    def _risk_ordered_queues(self, ctx: SessionContext) -> "OrderedDict[str, list]":
        """Per-skill due queues; with risk_order=True each queue is sorted by
        ascending predicted retrievability (most fragile first). Grammar
        round-robin rotation is applied AFTER risk sorting so rule diversity
        is preserved (rotation preserves within-queue relative fragility
        order inside each rule bucket: stable sort by rule index only)."""
        t_now = ctx.current_t()
        sched = ctx.main_sched()
        queues: "OrderedDict[str, list]" = OrderedDict()
        for iid in self._due_ids_naive(ctx):
            queues.setdefault(self._pool[iid], []).append(iid)
        for skill in list(queues.keys()):
            ids = queues[skill]
            if self.risk_order:
                # stable sort: ascending predicted R = most fragile first
                ids.sort(key=lambda iid: (
                    sched.predicted_retrievability(iid, t_now), iid))
            if skill == "grammar":
                ids = grammar_round_robin(
                    ids, int(self.mix_cfg["grammar_rule_size"]))
            queues[skill] = ids
        return queues

    # ------------------------------------------------------------ session plan
    def run_session(self, ctx: SessionContext):
        self.goal_stop = False
        budget = float(ctx.budget_min)
        goal_min = budget * self.goal_fraction

        queues = self._risk_ordered_queues(ctx)
        priority = self.diag.priority(
            float(self.mix_cfg["weak_skill_threshold"]),
            float(self.mix_cfg["weak_skill_priority_mult"]))
        order = build_interleave_order(queues, self.mix_cfg, priority)
        self.due_scheduled = len(order)

        # cold-start intake: quota + weakest-skill bias (v1.5 rule, frozen)
        quota = int(budget * float(self.mix_cfg["new_quota_fraction_of_budget"]) / 0.45)
        weak = self._weakest_skill()
        intake = self._intake_ids(
            min(int(ctx.condition["new_card_cap"]), quota), prefer_skill=weak)

        # due core: truncated ONLY by budget/quit when due_protect=True
        self._drain(ctx, order, label="due",
                    stop_at_min=None if self.due_protect else goal_min)

        # optional new intake gated by the goal line (planned stop)
        if not self.goal_stop:
            self._drain(ctx, intake, label="new", stop_at_min=goal_min)
        return []

    def _weakest_skill(self):
        cands = [s for s in SKILL_ORDER
                 if self.diag.n[s] >= int(self.mix_cfg["diagnosis_min_evidence"])]
        if not cands:
            return None
        return min(cands, key=lambda s: self.diag.level[s])


def build_arm_specs17(variant: str = "nexus_triad"):
    """ArmSpec list for runner17.

    variant 'nexus_triad'       -> [fsrs_multitype, nexus_triad]
    variant 'triad_no_risk_order' -> [fsrs_multitype, triad_no_risk_order]
    variant 'triad_no_pacing'     -> [fsrs_multitype, triad_no_pacing]
    """
    from simlib.experiments.runner import ArmSpec
    from sim16.policy import FsrsMultiType16

    if variant == "nexus_triad":
        triad = lambda learner, cfg: NexusTriad(learner, cfg)  # noqa: E731
        name = "nexus_triad"
    elif variant == "triad_no_risk_order":
        triad = lambda learner, cfg: NexusTriad(  # noqa: E731
            learner, cfg, risk_order=False)
        name = "triad_no_risk_order"
    elif variant == "triad_no_pacing":
        triad = lambda learner, cfg: NexusTriad(  # noqa: E731
            learner, cfg, goal_stop_fraction=1.0, due_core_protect=False)
        name = "triad_no_pacing"
    else:
        raise KeyError(f"unknown variant {variant}")

    return [
        ArmSpec("fsrs_multitype", "fsrs",
                lambda learner, cfg: FsrsMultiType16(learner, cfg)),
        ArmSpec(name, "fsrs", triad),
    ]
