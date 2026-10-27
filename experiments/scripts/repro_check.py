"""Reproduction check: re-run one experiment from scratch and compare with a recorded run.

The re-run goes to experiments/results/_reproduction/ (so analyze.py never picks it up).
Simulated outputs must match exactly; wall-clock columns are machine-dependent and excluded.

Usage: python experiments/scripts/repro_check.py --config experiments/configs/exp2a_fcfs_vs_sjf_load.yaml \
           --original EXP2A_20261028-001549
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_scheduler.experiment_runner import main as run_experiment  # noqa: E402

WALL_CLOCK = ["sim_wall_s", "sched_us_per_decision", "predict_us_per_request"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--original", required=True, help="run directory name under experiments/results/")
    args = ap.parse_args()

    orig = ROOT / "experiments" / "results" / args.original
    new = run_experiment(["--config", str(args.config), "--results-root", str(ROOT / "experiments" / "results" / "_reproduction"), "--tag", "repro"])

    a = pd.read_csv(orig / "summary.csv").drop(columns=WALL_CLOCK)
    b = pd.read_csv(new / "summary.csv").drop(columns=WALL_CLOCK)
    summary_equal = a.shape == b.shape and a.equals(b)
    req_files = sorted(p.name for p in (orig / "requests").glob("*.csv.gz")) if (orig / "requests").exists() else []
    mismatched = [f for f in req_files if not pd.read_csv(orig / "requests" / f).equals(pd.read_csv(new / "requests" / f))]
    report = {"original": orig.name, "reproduction": str(new.relative_to(ROOT)), "summary_rows": int(len(a)),
              "summary_identical_excluding_wall_clock": bool(summary_equal), "request_files_compared": len(req_files),
              "request_files_mismatched": mismatched}
    (new / "repro_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
