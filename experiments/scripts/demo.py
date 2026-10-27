"""Command-line demonstration for the project review.

Steps:
  1. generate one fixed workload (mixed, 2,000 requests, load 0.9, seed 42);
  2. run FCFS;
  3. run predictive SJF with the heuristic predictor on the *same* workload;
  4. print a side-by-side comparison;
  5. save per-request results and a summary to experiments/results/DEMO_<timestamp>/;
  6. regenerate one plot (mean waiting time by length category) into that directory.

Usage: python experiments/scripts/demo.py [--n 2000] [--load 0.9] [--seed 42]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_scheduler import plotting as P  # noqa: E402
from llm_scheduler.metrics import relative_reduction, request_records, summarize, summarize_by_category  # noqa: E402
from llm_scheduler.policies import FCFSPolicy, PredictiveSJFPolicy  # noqa: E402
from llm_scheduler.predictor import HeuristicPredictor  # noqa: E402
from llm_scheduler.service_model import ServiceModel  # noqa: E402
from llm_scheduler.simulator import Simulator  # noqa: E402
from llm_scheduler.workload import generate_workload  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--load", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    sm = ServiceModel()
    print(f"[1] generating workload: mix=mixed n={args.n} load={args.load} seed={args.seed}")
    wl = generate_workload("mixed", args.n, args.load, args.seed, sm)
    d = wl.describe(sm)
    print(f"    mean output {d['mean_output_tokens']:.0f} tokens, service CV {d['cv_service']:.2f}, "
          f"short/medium/long = {d['share_short']:.0%}/{d['share_medium']:.0%}/{d['share_long']:.0%}")

    sim = Simulator(sm)
    print("[2] running FCFS")
    fcfs = sim.run(wl, FCFSPolicy())
    print("[3] running predictive SJF (heuristic predictor) on the same workload")
    sjf = sim.run(wl, PredictiveSJFPolicy(), HeuristicPredictor())

    a, b = summarize(fcfs), summarize(sjf)
    rows = [("mean JCT (s)", "jct_mean"), ("median JCT (s)", "jct_median"), ("P95 JCT (s)", "jct_p95"),
            ("P99 JCT (s)", "jct_p99"), ("mean TTFT (s)", "ttft_mean"), ("mean wait (s)", "wait_mean"),
            ("max wait (s)", "wait_max"), ("throughput (req/s)", "throughput_rps")]
    print("[4] comparison (simulated; lower is better except throughput)")
    print(f"    {'metric':20s} {'FCFS':>10s} {'SJF':>10s} {'reduction':>10s}")
    for name, k in rows:
        red = relative_reduction(a[k], b[k])
        print(f"    {name:20s} {a[k]:10.3f} {b[k]:10.3f} {red:9.1f}%")
    print(f"    predictor: Spearman {b['pred_spearman']:.3f}, MAE {b['pred_mae']:.0f} tokens")

    out = ROOT / "experiments" / "results" / f"DEMO_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True)
    pd.DataFrame([{"condition": "FCFS", **a}, {"condition": "SJF-heuristic", **b}]).to_csv(out / "summary.csv", index=False)
    pd.DataFrame(request_records(fcfs)).to_csv(out / "requests_FCFS.csv", index=False)
    pd.DataFrame(request_records(sjf)).to_csv(out / "requests_SJF-heuristic.csv", index=False)
    cats = pd.DataFrame([{"condition": c, **row} for c, res in (("FCFS", fcfs), ("SJF-heuristic", sjf))
                         for row in summarize_by_category(res)])
    cats.to_csv(out / "by_category.csv", index=False)
    print(f"[5] saved results to {out.relative_to(ROOT)}")

    fig = P.grouped_bars(cats, "category", "condition", "wait_mean", None, None, ["short", "medium", "long"],
                         ["FCFS", "SJF-heuristic"], f"Demo: mean waiting time by length category (load {args.load:g})",
                         "mean waiting time (s)", out / "demo_wait_by_category.png")
    print(f"[6] plot written to {fig.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
