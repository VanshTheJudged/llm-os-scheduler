"""Run Experiment 1 and every evaluation config, in order, with the current interpreter.

Usage: ``python experiments/scripts/run_all.py``

Each experiment writes its own timestamped result directory and log; nothing is
overwritten. Stops at the first failure.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = [
    "exp2a_fcfs_vs_sjf_load.yaml",
    "exp2b_overload_horizon.yaml",
    "exp3_workload_composition.yaml",
    "exp4_predictor_quality.yaml",
    "exp5_fairness.yaml",
    "exp6_workload_size.yaml",
    "exp7_aging_extension.yaml",
]


def run(cmd: list[str]) -> None:
    print(">>", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    run([sys.executable, "experiments/scripts/exp1_validate.py"])
    for cfg in CONFIGS:
        run([sys.executable, "-m", "llm_scheduler.experiment_runner", "--config", f"experiments/configs/{cfg}"])


if __name__ == "__main__":
    main()
