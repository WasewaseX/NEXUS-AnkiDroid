#!/bin/bash
# run17.sh — execute all v1.7 cells in foreground waves (2 workers per wave),
# then analyze. Chunks are per-rep (rep_offset) so RNG paths are identical to
# a single unchunked run (pool.spawn depends on (rep, learner_id) labels only).
set -u
HERE="/home/z/my-project/download/v17_nexus_triad_benchmark"
cd "$HERE"
mkdir -p outputs/raw outputs/logs

cell3() {
  local sc="$1"; local var="$2"
  for r in 0 1 2; do
    python3 runner17.py --scenario "$sc" --variant "$var" --n-reps 1 --rep-offset $r \
        >> "outputs/logs/${sc}_${var}.log" 2>&1
  done
  echo "done: $sc / $var"
}

wave() { cell3 "$1" "$2" & cell3 "$3" "$4" & wait; }

wave base nexus_triad base triad_no_risk_order
wave base triad_no_pacing no_fatigue_quit nexus_triad
wave double_monotony nexus_triad skeptical nexus_triad
cell3 hard_skeptical nexus_triad

echo "=== analyzing ==="
python3 analyze17.py
echo "=== run17 complete ==="
