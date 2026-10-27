"""Diagnostic: which requests form the slowest 1 % (JCT >= per-seed P99) under each policy?

Reads per-request records of the latest EXP5 run (mixed workload, load 0.9) and writes
experiments/results/analysis/EXP5_tail_composition.csv. Added after EXP2A showed that
SJF-heuristic's P99 JCT is worse than FCFS at load >= 0.9, to explain that result.

Usage: python experiments/scripts/diag_tail.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "scripts"))
from analyze import latest_run  # noqa: E402

run = latest_run("EXP5")
rows = []
for cond in ["FCFS", "SJF-heuristic", "SJF-oracle"]:
    for seed in range(10):
        df = pd.read_csv(run / "requests" / f"mixed_load0.9_n5000_seed{seed}_{cond}.csv.gz")
        tail = df[df.jct >= df.jct.quantile(0.99)]
        rows.append({
            "condition": cond, "seed": seed, "n_tail": len(tail),
            "tail_share_short": (tail.category == "short").mean(),
            "tail_share_medium": (tail.category == "medium").mean(),
            "tail_share_long": (tail.category == "long").mean(),
            "tail_mean_actual_tokens": tail.actual_output_tokens.mean(),
            "tail_mean_wait_s": tail.waiting_time.mean(),
            "tail_mean_service_s": (tail.jct - tail.waiting_time).mean(),
            "tail_share_pred_ge_1024": (tail.predicted_output_tokens >= 1024).mean() if cond != "FCFS" else float("nan"),
            "all_share_pred_ge_1024": (df.predicted_output_tokens >= 1024).mean() if cond != "FCFS" else float("nan"),
            "n_distinct_predictions": df.predicted_output_tokens.nunique() if cond != "FCFS" else float("nan"),
        })
out = pd.DataFrame(rows)
agg = out.groupby("condition", sort=False).mean(numeric_only=True).drop(columns="seed").round(3)
out.to_csv(ROOT / "experiments" / "results" / "analysis" / "EXP5_tail_composition.csv", index=False)
print(f"source: {run.name}")
print(agg.to_string())
