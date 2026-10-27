"""Post-hoc diagnostic for Experiment 1 (added after the first EXP1 run).

At load 0.9 the FCFS simulation deviated from Pollaczek-Khinchine by up to +/-14 % per seed.
This script recomputes the formula with the *realised* arrival rate of each sample
(n / last arrival time) instead of the nominal rate, to see how much of the deviation is
explained by sampling variation in the arrival process.

Usage: python experiments/scripts/exp1_bias_diagnostic.py <EXP1 results dir>
Writes <dir>/bias_diagnostic.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from llm_scheduler.analytical import pk_mean_wait  # noqa: E402
from llm_scheduler.service_model import ServiceModel  # noqa: E402
from llm_scheduler.workload import generate_workload  # noqa: E402

out_dir = Path(sys.argv[1])
df = pd.read_csv(out_dir / "analytical_check.csv")
sm = ServiceModel()
rows = []
for (mix, load, seed), g in df[df.condition == "FCFS"].groupby(["mix", "load", "seed"]):
    wl = generate_workload(mix, 50_000, load, int(seed), sm)
    svc = np.array([sm.service_time(s.features.prompt_tokens, s.actual_output_tokens) for s in wl.specs])
    lam_real = len(wl.specs) / wl.specs[-1].arrival_time
    sim, nominal = g.sim_wait_mean.item(), g.model_wait_mean.item()
    realised = pk_mean_wait(svc, lam_real)
    rows.append({"mix": mix, "load": load, "seed": seed, "rho_realised": lam_real * svc.mean(),
                 "rel_error_nominal_pct": (sim - nominal) / nominal * 100,
                 "rel_error_realised_pct": (sim - realised) / realised * 100})
res = pd.DataFrame(rows)
res.to_csv(out_dir / "bias_diagnostic.csv", index=False)
summary = res.groupby(["mix", "load"])[["rho_realised", "rel_error_nominal_pct", "rel_error_realised_pct"]].mean().round(3)
print(summary.to_string())
