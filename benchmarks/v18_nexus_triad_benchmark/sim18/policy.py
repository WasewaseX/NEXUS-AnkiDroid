"""sim18.policy — the v1.8 arms (all subclasses of the v1.6 instrumented base).

Arm list (user's 8 requested arms; (2) and (6) coincide -> 7 implementations):
  fsrs_recall_only  (v1.6, unchanged)          = arm 1
  fsrs_multitype    (v1.6, unchanged)          = arms 2 and 6 (duplication noted)
  nexus_scope20     (NEW: SCOPE 2.0 layer)     = arm 3
  nexus_mix2        (v1.6 frozen p075_prot)    = arm 4
  nexus_triad       (NEW: NEXUS-TRIAD v1.8)    = arm 5
  rwkv_instant      (NEW arm class, v1.4 RWKVInstant scheduler) = arm 7
  sm20              (NEW arm class, v1.4 SM20 scheduler)        = arm 8

NEUTRALITY (carried from v1.5/v1.6, still in force): methods never read the
truth model, the behavior state, or any learner truth. TRIAD reads only the
scheduler's own predicted_retrievability, the item bank's public tags, and
the outcomes of events it initiated. FSRS remains the AUTHORITATIVE memory
engine in every arm: TRIAD never calls scheduler mutation methods beyond
what route_event already does for every arm (identical code path).
"""
from __future__ import annotations

from collections import OrderedDict

from sim15.mix import (
    SKILL_EFFORT, SKILL_KIND, SKILL_ORDER, build_interleave_order, route_event,
)
from sim16.policy import (
    FsrsMultiType16, FsrsRecallOnly16, NexusMix2, _InstrumentedBase,
)
from simlib.spec import SessionContext

from sim18.triad import AlphaGate, ContextState, SkillPriors, hybrid

SCOPE_FRACTION_OF_DUE_MINUTES = 0.20   # NEXUS-SCOPE default budget level (20%)
SCOPE_MIN_EVIDENCE = 4                 # evidence gate (core spec: evidence < 4 -> skip)
SCOPE_CONFIDENCE_CAP = 12              # confidence = min(n, 12) / 12 (core spec)


# ------------------------------------------------------- arm 3: SCOPE 2.0
class ScopeInterventions20(_InstrumentedBase):
    """FSRS due-first + NEXUS-SCOPE 2.0 intervention layer.

    Session plan:
      1. DUE reviews first, scheduler's own order, never truncated (grinds
         to budget like every baseline arm);
      2. SCOPE reserve = SCOPE_FRACTION * real due-drain minutes; if the
         deficit x confidence - targeted weakest NON-MEANING skill has
         evidence >= SCOPE_MIN_EVIDENCE, run ONE intervention block: extra
         type-matched events on already-seen items of that skill until the
         reserve is spent (adaptive stop at event boundary);
      3. new-card intake with the remaining budget (grinds).

    Adaptation note (declared): in the standalone app, interventions are
    logged separately and never touch FSRS state (isolation guarantee). In
    this career simulation every event is real, so interventions are extra
    events of the targeted kind; meaning is excluded as a target because an
    'extra meaning event' would simply be an unscheduled FSRS review, which
    is not an intervention."
    """

    name = "nexus_scope20"

    def __init__(self, learner, cfg15: dict):
        super().__init__(learner, cfg15, SKILL_ORDER)
        self.scope_events = 0

    def run_session(self, ctx: SessionContext):
        self.goal_stop = False
        due = self._due_ids_naive(ctx)
        self.due_scheduled = len(due)
        due_start = float(ctx.elapsed_min)
        self._drain(ctx, due, label="due")
        due_minutes = float(ctx.elapsed_min) - due_start

        # ---- SCOPE intervention block (one per day, weakest-skill targeted)
        reserve = SCOPE_FRACTION_OF_DUE_MINUTES * due_minutes
        target = self._scope_target()
        if reserve > 1e-9 and target is not None:
            cands = [iid for iid, s in self._pool.items()
                     if s == target and iid in self._seen]
            while cands and reserve > 1e-9:
                iid = cands.pop(0)
                t0 = float(ctx.elapsed_min)
                rec, oc = route_event(ctx, ctx.bank.get(iid))
                self.diag.update(target, bool(oc.correct))
                self.events += 1
                self.scope_events += 1
                reserve -= float(ctx.elapsed_min) - t0

        n_new = self._intake_estimate(ctx, mean_min=0.80)
        self._drain(ctx, self._intake_ids(n_new), label="new")
        return []

    def _scope_target(self):
        """deficit x confidence targeting over non-meaning skills (gates:
        evidence >= 4; one block per day is structural - called once)."""
        best, best_score = None, -1.0
        for s in SKILL_ORDER:
            if s == "meaning" or self.diag.n[s] < SCOPE_MIN_EVIDENCE:
                continue
            deficit = 1.0 - float(self.diag.level[s])
            confidence = min(self.diag.n[s], SCOPE_CONFIDENCE_CAP) / SCOPE_CONFIDENCE_CAP
            score = deficit * confidence
            if score > best_score:
                best, best_score = s, score
        return best


# --------------------------------------------- arms 7/8: alt schedulers
class _AltSchedulerArm(_InstrumentedBase):
    """Naive multi-type session policy over a DIFFERENT scheduler (the arm's
    intelligence lives in the scheduler alone - same shape as fsrs_multitype,
    so differences are attributable to the scheduler)."""

    def __init__(self, learner, cfg15: dict):
        super().__init__(learner, cfg15, SKILL_ORDER)

    def run_session(self, ctx: SessionContext):
        self.goal_stop = False
        due = self._due_ids_naive(ctx)
        self.due_scheduled = len(due)
        self._drain(ctx, due, label="due")
        n_new = self._intake_estimate(ctx, mean_min=0.80)
        self._drain(ctx, self._intake_ids(n_new), label="new")
        return []


class RwkvInstantArm(_AltSchedulerArm):
    name = "rwkv_instant"


class Sm20Arm(_AltSchedulerArm):
    name = "sm20"


# ------------------------------------------------------ arm 5: TRIAD v1.8
class TriadFull(_InstrumentedBase):
    """NEXUS-TRIAD v1.8: the v1.6 mix2 controller + the three TRIAD layers.

    Session plan:
      1. start-of-session context update (due count, budget, absence gap);
      2. alpha gate check (fits ONCE on gate day, out-of-sample, else 0);
      3. DUE reviews in dishabituation-interleave order with PRIOR-SHRUNK
         diagnosis priorities (cold-start layer) - NEVER truncated by the
         goal line (due_core_protect, v1.6 frozen mechanism);
         every due event logs a (P_eff, delta, outcome) prediction row:
         P_eff = cold-start-shrunk scheduler retrievability,
         P_hybrid = sigmoid(logit(P_eff) + alpha*delta) via the gate;
      4. intake decision: if the SESSION-SCOPE fatigue proxy is above the
         declared threshold (and the session is long enough to matter),
         new-card intake is SKIPPED - a planned stop (goal_stop=True);
         DUE reviews are never skipped. Otherwise intake (weak-skill + prior
         aware) drains to the goal line, which EXTENDS to 0.85*budget on
         high-accuracy days (recent_acc >= 0.85) - a DPI lever within budget.
      5. end-of-session absence bookkeeping.

    FSRS is the authoritative memory engine: this method NEVER mutates
    scheduler state beyond route_event's shared logging path.
    """

    name = "nexus_triad"

    def __init__(self, learner, cfg15: dict, cfg18: dict, cell: dict):
        super().__init__(learner, cfg15, SKILL_ORDER)
        consts = cfg18["triad_constants"]
        self.cell = dict(cell)
        self.priors = SkillPriors(
            consts["cold_start"]["prior_shrink_k_skill"],
            consts["cold_start"]["prior_shrink_k_card"])
        self.cx = ContextState(consts)
        self.gate = (AlphaGate(consts) if cell.get("alpha_gating", True)
                     else None)
        ctrl = consts["controller"]
        ig, ge = ctrl["intake_gate"], ctrl["goal_extend"]
        self.fatigue_threshold = float(ig["fatigue_proxy_threshold"])
        self.gate_min_events = int(ig["min_session_events"])
        self.extend_acc_min = float(ge["recent_acc_min"])
        self.extend_goal_fraction = float(ge["extended_goal_fraction"])

    # ------------------------------------------------------------- helpers
    def _shrunk_priority(self, weak_threshold: float, mult: float) -> dict:
        out = {}
        for s in SKILL_ORDER:
            lvl = self.priors.shrunk_level(s, float(self.diag.level[s]),
                                           int(self.diag.n[s]))
            out[s] = float(mult) if (self.diag.n[s] >= self.diag.n_min
                                     and lvl < weak_threshold) else 1.0
        return out

    def _triad_weakest(self):
        """Weakest skill by PRIOR-SHRUNK level (cold-start: with little
        evidence the shared prior decides; evidence takes over later)."""
        cands = [s for s in SKILL_ORDER
                 if self.priors.shrunk_level(s, self.diag.level[s],
                                             self.diag.n[s]) is not None]
        return min(cands, key=lambda s: self.priors.shrunk_level(
            s, self.diag.level[s], self.diag.n[s]))

    def _drain_triad(self, ctx: SessionContext, ids, label: str,
                     stop_at_min=None) -> None:
        """Per-event instrumented drain: predict BEFORE observing, then
        update priors/context/diagnosis. QuitSession/BudgetExhausted
        propagate; completed events counted (v1.6 instrumentation)."""
        for iid in ids:
            if stop_at_min is not None and ctx.elapsed_min >= stop_at_min:
                self.goal_stop = True
                return
            skill = self._pool[iid]
            item = ctx.bank.get(iid)
            # ---- predict BEFORE the event (no truth access, no RNG)
            p_sched = float(ctx.main_sched().predicted_retrievability(
                iid, ctx.current_t()))
            card_n = self.cx.card_reviews(iid)
            p_eff = self.priors.shrunk_p(skill, p_sched, card_n)
            delta = self.cx.delta()
            alpha = self.gate.alpha if self.gate is not None else 0.0
            p_hybrid = hybrid(p_eff, delta, alpha)
            # ---- event (shared code path with every other arm)
            t0 = float(ctx.elapsed_min)
            rec, oc = route_event(ctx, item)
            dt = float(ctx.elapsed_min) - t0
            self._seen.add(iid)
            correct = bool(oc.correct)
            # ---- observe AFTER the event
            if label == "due":
                self.enc_due += 1
                if self.gate is not None:
                    self.gate.log(ctx.day, p_eff, delta, correct)
            else:
                self.enc_new += 1
            self.diag.update(skill, correct)
            self.priors.update(skill, correct)
            self.cx.observe_card(iid)
            self.cx.observe_event(SKILL_KIND[skill], dt, skill, correct)
            self.cx.session_elapsed = float(ctx.elapsed_min)
            self.events += 1
        if stop_at_min is not None and ctx.elapsed_min >= stop_at_min:
            self.goal_stop = True

    # -------------------------------------------------------------- session
    def run_session(self, ctx: SessionContext):
        self.goal_stop = False
        budget = float(ctx.budget_min)

        queues = self._partition_due(ctx)
        priority = self._shrunk_priority(
            float(self.mix_cfg["weak_skill_threshold"]),
            float(self.mix_cfg["weak_skill_priority_mult"]))
        order = build_interleave_order(queues, self.mix_cfg, priority)
        self.due_scheduled = len(order)

        self.cx.start_session(ctx.day, len(order), budget)

        if self.gate is not None:
            self.gate.maybe_fit(ctx.day)

        goal_frac = float(self.cell["goal_stop_fraction"])
        if (self.cell.get("goal_extend", True)
                and self.cx.recent_acc() >= self.extend_acc_min):
            goal_frac = max(goal_frac, self.extend_goal_fraction)
        goal_min = budget * min(goal_frac, 1.0)

        # DUE drain - due_core_protect: NO goal-line truncation, ever
        self._drain_triad(ctx, order, label="due")

        # intake (optional enrichment; fatigue-gated = planned stop)
        quota = int(budget * float(self.mix_cfg["new_quota_fraction_of_budget"]) / 0.45)
        weak = self._triad_weakest()
        intake = self._intake_ids(
            min(int(ctx.condition["new_card_cap"]), quota), prefer_skill=weak)
        if (self.cell.get("intake_gate", True)
                and self.cx.fatigue_proxy() >= self.fatigue_threshold
                and self.cx.session_events >= self.gate_min_events
                and intake):
            self.goal_stop = True        # planned stop (intake skipped)
        else:
            self._drain_triad(ctx, intake, label="new", stop_at_min=goal_min)

        self.cx.end_session(ctx.day)
        return []

    def prediction_log(self):
        if self.gate is None:
            return []
        return self.gate.rows


# ---------------------------------------------------------------- registry
def build_arm_specs18(cell_id: str, cfg18: dict, mix2_policy: str = "p075_prot"):
    """ArmSpec list for run_experiment18 (7 distinct implementations of the
    user's 8 requested arms; see config18.v18_arms for the mapping)."""
    from simlib.experiments.runner import ArmSpec
    cells = cfg18["v18_policy_grid"]["policies"]
    if cell_id not in cells:
        raise KeyError(f"unknown triad cell {cell_id}; known: {sorted(cells)}")
    cell = cells[cell_id]
    p16 = _P16_POLICIES[mix2_policy]
    return [
        ArmSpec("fsrs_recall_only", "fsrs",
                lambda learner, cfg: FsrsRecallOnly16(learner, cfg)),
        ArmSpec("fsrs_multitype", "fsrs",
                lambda learner, cfg: FsrsMultiType16(learner, cfg)),
        ArmSpec("nexus_scope20", "fsrs",
                lambda learner, cfg: ScopeInterventions20(learner, cfg)),
        ArmSpec("nexus_mix2", "fsrs",
                lambda learner, cfg: NexusMix2(
                    learner, cfg,
                    goal_stop_fraction=p16["goal_stop_fraction"],
                    due_core_protect=p16["due_core_protect"])),
        ArmSpec("nexus_triad", "fsrs",
                lambda learner, cfg: TriadFull(learner, cfg, cfg18, cell)),
        ArmSpec("rwkv_instant", "rwkv_instant",
                lambda learner, cfg: RwkvInstantArm(learner, cfg)),
        ArmSpec("sm20", "sm20",
                lambda learner, cfg: Sm20Arm(learner, cfg)),
    ]


# small alias table so the mix2 arm uses the v1.6 frozen policy without
# importing runner16 (which would re-import pandas etc. harmlessly anyway)
from sim16.policy import POLICIES as _P16_POLICIES  # noqa: E402
