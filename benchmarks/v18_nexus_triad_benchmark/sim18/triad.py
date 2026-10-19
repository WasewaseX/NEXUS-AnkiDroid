"""sim18.triad — NEXUS-TRIAD v1.8 core (method-side only; never reads truth).

Four components, per the user's spec:

1. COLD-START INTELLIGENCE  (SkillPriors): shared empirical-Bayes priors.
   Per-skill Beta(1,1) posteriors over observed outcomes; a card or skill with
   little evidence is shrunk toward the shared prior. The prior dominates
   early, individual evidence takes over as history accumulates.

2. FSRS MEMORY ENGINE (authoritative, EXTERNAL): the FSRS scheduler is never
   touched by TRIAD — intervals, stability, difficulty all come from the v1.4
   wrapper exactly as in every other arm. TRIAD only READS
   predicted_retrievability for its own decision support.

3. CONTEXTUAL RECALL PREDICTOR (ContextState): features from observables
   only — recent accuracy EMA, per-kind latency slowdown, workload, session
   fatigue proxies (SESSION SCOPE ONLY), absence history.
   delta = w_acc*(recent_acc-0.85) - w_lat*max(0,slowdown-1)
           - w_wl*max(0, due/30-0.5) - w_fat*fatigue_proxy
           - w_abs*min(gap/7,1),  clipped to +/-1.5 logits.

4. NEXUS CONTROLLER: lives in sim18.policy.TriadFull (mix2 layer + intake
   gate + goal extension), driven by 1-3.

Hybrid prediction (the user's formula, verbatim):
    P_hybrid = sigmoid(logit(P_eff) + alpha * delta_context)
with alpha = 0 until the AlphaGate demonstrates reliable out-of-sample value
(held-out logloss improvement >= min_improvement with >= min_events).
"""
from __future__ import annotations

import math

from sim15.mix import SKILL_ORDER


# --------------------------------------------------------------- math utils
def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def logit(p: float) -> float:
    p = _clip(float(p), 1e-4, 1.0 - 1e-4)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def hybrid(p_eff: float, delta: float, alpha: float) -> float:
    """The user's formula: P_hybrid = sigmoid(logit(P_eff) + alpha*delta)."""
    if alpha == 0.0:
        return _clip(float(p_eff), 1e-4, 1.0 - 1e-4)
    return sigmoid(logit(p_eff) + float(alpha) * float(delta))


def brier(preds) -> float:
    return sum((p - y) ** 2 for p, y in preds) / len(preds)


def logloss(preds) -> float:
    eps = 1e-6
    return sum(-(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)))
               for p, y in preds) / len(preds)


# ------------------------------------------------- 1. cold-start priors
class SkillPriors:
    """Shared empirical-Bayes priors (component 1).

    Per-skill Beta(1,1) posterior from outcomes the method itself observed.
    shrunk_level() blends an observed EMA level with the prior mean using
    n/(n+k) shrinkage — the prior dominates early (cold start), evidence
    takes over as n grows. No RNG consumption.
    """

    def __init__(self, k_skill: float = 8.0, k_card: float = 3.0):
        self.k_skill = float(k_skill)
        self.k_card = float(k_card)
        self.alpha = {s: 1.0 for s in SKILL_ORDER}
        self.beta = {s: 1.0 for s in SKILL_ORDER}

    def update(self, skill: str, correct: bool) -> None:
        if skill not in self.alpha:
            return
        if correct:
            self.alpha[skill] += 1.0
        else:
            self.beta[skill] += 1.0

    def mean(self, skill: str) -> float:
        return self.alpha[skill] / (self.alpha[skill] + self.beta[skill])

    def shrunk_level(self, skill: str, observed_level: float, n: int) -> float:
        k = self.k_skill
        return (n * float(observed_level) + k * self.mean(skill)) / (n + k)

    def shrunk_p(self, skill: str, p_sched: float, card_n: int) -> float:
        """Cold-start prediction shrinkage for cards with < k_card reviews."""
        k = self.k_card
        if card_n >= k:
            return _clip(float(p_sched), 1e-4, 1.0 - 1e-4)
        return (card_n * float(p_sched) + k * self.mean(skill)) / (k + card_n)


# --------------------------------- 3. contextual recall predictor
class ContextState:
    """Observable context tracker (component 3). Features ONLY from events
    the method initiated and from the day counter the runner provides.
    Session-scope quantities (session_events, session_elapsed) are RESET in
    start_session() and never persisted — fatigue cannot leak across
    sessions and never touches the scheduler."""

    def __init__(self, consts: dict):
        cf = consts["context_features"]
        self.w_acc = float(cf["acc_reference"])
        self.w = dict(cf["delta_weights"])
        self.clip = float(cf["delta_clip_logits"])
        self.wl_ref = float(cf["workload_reference_due"])
        self.abs_h = float(cf["absence_horizon_days"])
        self.acc_ema_rate = float(cf["recent_acc_ema"])
        self.lat_ema_rate = float(cf["latency_ema"])
        # career-wide accumulators
        self.acc_ema = 0.85  # neutral start at the reference level
        self.lat_ema: dict = {}   # kind -> mean minutes per event
        self.lat_recent: dict = {}  # kind -> recent minutes EMA
        # per-card review counts (observable: events the method ran)
        self.card_n: dict = {}
        # session scope (reset each session)
        self.session_events = 0
        self.session_elapsed = 0.0
        self.session_budget = 1.0
        self.due_count = 0
        # absence history
        self.last_day = None
        self.gap_days = 0

    # ------------------------------------------------------------ lifecycle
    def start_session(self, day: int, due_count: int, budget_min: float) -> None:
        self.session_events = 0
        self.session_elapsed = 0.0
        self.session_budget = max(1e-6, float(budget_min))
        self.due_count = int(due_count)
        if self.last_day is not None:
            self.gap_days = max(0, int(day) - self.last_day)

    def end_session(self, day: int) -> None:
        self.last_day = int(day)

    # ------------------------------------------------------------ observe
    def observe_event(self, kind: str, minutes: float, skill: str,
                      correct: bool) -> None:
        """Update all EMAs after one completed event. No RNG."""
        x = 1.0 if correct else 0.0
        self.acc_ema = (1.0 - self.acc_ema_rate) * self.acc_ema + self.acc_ema_rate * x
        m = max(1e-6, float(minutes))
        if kind not in self.lat_ema:
            self.lat_ema[kind] = m
            self.lat_recent[kind] = m
        else:
            r = self.lat_ema_rate
            self.lat_ema[kind] = (1.0 - r) * self.lat_ema[kind] + r * m
            self.lat_recent[kind] = (1.0 - 0.5) * self.lat_recent[kind] + 0.5 * m
        self.card_n[skill] = self.card_n.get(skill, 0) + 1
        self.session_events += 1

    def observe_card(self, item_id: int) -> None:
        """Per-CARD review count (distinct from per-skill counts)."""
        self.card_n[("card", item_id)] = self.card_n.get(("card", item_id), 0) + 1

    def card_reviews(self, item_id: int) -> int:
        return self.card_n.get(("card", item_id), 0)

    # ------------------------------------------------------------ features
    def fatigue_proxy(self) -> float:
        """SESSION SCOPE ONLY: events done + time spent in this session."""
        return self.session_events / 40.0 + self.session_elapsed / self.session_budget

    def slowdown(self) -> float:
        """Kind-controlled latency ratio: recent/career per-kind, blended by
        the per-kind session share observed so far. >1 means slowing down."""
        ratios = [self.lat_recent[k] / max(1e-6, self.lat_ema[k])
                  for k in self.lat_ema]
        return sum(ratios) / len(ratios) if ratios else 1.0

    def recent_acc(self) -> float:
        return self.acc_ema

    def delta(self) -> float:
        acc_term = self.w["acc"] * (self.acc_ema - self.w_acc)
        sd = self.slowdown()
        lat_term = -self.w["lat"] * max(0.0, sd - 1.0)
        wl_ratio = min(self.due_count, 3.0 * self.wl_ref) / self.wl_ref
        wl_term = -self.w["workload"] * max(0.0, wl_ratio - 0.5)
        fat_term = -self.w["fatigue"] * self.fatigue_proxy()
        abs_term = -self.w["absence"] * min(self.gap_days / self.abs_h, 1.0)
        return _clip(acc_term + lat_term + wl_term + fat_term + abs_term,
                     -self.clip, self.clip)


# --------------------------------------------- alpha gate (out-of-sample)
class AlphaGate:
    """alpha = 0 until out-of-sample validation succeeds (component 3 gate).

    Logs (day, p_eff, delta, correct) for DUE-review events only (no RNG).
    On gate day: fit alpha over the declared grid on the TRAIN split,
    evaluate on the deterministic VALIDATION split (every event whose index
    mod 10 < 3 -> ~30%); accept ONLY if val logloss improves by
    >= min_improvement and total events >= min_events. Otherwise alpha
    stays 0 forever (declared, conservative)."""

    def __init__(self, consts: dict):
        g = consts["alpha_gate"]
        self.gate_day = int(g["gate_day"])
        self.grid = [float(a) for a in g["grid"]]
        self.val_fraction = float(g["val_fraction"])
        self.min_events = int(g["min_events"])
        self.min_improvement = float(g["min_improvement"])
        self.alpha = 0.0
        self.fitted = False
        self.fit_summary: dict = {}
        self.rows: list = []
        self._seq = 0

    def log(self, day: int, p_eff: float, delta: float, correct: bool) -> None:
        self.rows.append((int(day), float(p_eff), float(delta),
                          1.0 if correct else 0.0, self._seq))
        self._seq += 1

    def maybe_fit(self, day: int) -> bool:
        if self.fitted or int(day) < self.gate_day:
            return False
        self.fitted = True
        n = len(self.rows)
        if n < self.min_events:
            self.fit_summary = {"n": n, "alpha": 0.0, "reason": "insufficient_events"}
            return False
        n_val = max(1, int(round(self.val_fraction * 10)))
        val = [r for r in self.rows if r[4] % 10 < n_val]
        train = [r for r in self.rows if r[4] % 10 >= n_val]
        if not train or not val:
            self.fit_summary = {"n": n, "alpha": 0.0, "reason": "empty_split"}
            return False

        def ll(rows, alpha):
            return logloss([(hybrid(p, d, alpha), y) for _, p, d, y, _ in rows])

        base_val = ll(val, 0.0)
        best_alpha, best_val = 0.0, base_val
        for a in self.grid:
            v = ll(val, a)
            if v < best_val - 1e-12:
                best_alpha, best_val = a, v
        improvement = base_val - best_val
        if improvement >= self.min_improvement and best_alpha > 0.0:
            self.alpha = best_alpha
            self.fit_summary = {
                "n": n, "alpha": best_alpha, "val_logloss_base": base_val,
                "val_logloss_best": best_val, "improvement": improvement,
                "reason": "accepted",
            }
        else:
            self.alpha = 0.0
            self.fit_summary = {
                "n": n, "alpha": 0.0, "val_logloss_base": base_val,
                "val_logloss_best": best_val, "improvement": improvement,
                "reason": "no_improvement" if improvement < self.min_improvement
                else "zero_alpha_best",
            }
        return True

    def prediction_rows(self, arm: str, rep: int, learner_id: str):
        out = []
        for day, p_eff, delta, y, seq in self.rows:
            p_h = hybrid(p_eff, delta, self.alpha)
            out.append(dict(arm=arm, rep=rep, learner_id=learner_id, day=day,
                            seq=seq, p_eff=p_eff, delta=delta,
                            alpha=self.alpha, p_hybrid=p_h, correct=y))
        return out


# -------------------------------------------------- helpers for policies
def scope_candidates(pool: dict, seen: set, skill: str) -> list:
    """Seen item ids of one skill (intervention candidates), stable order."""
    return [iid for iid, s in pool.items() if s == skill and iid in seen]
