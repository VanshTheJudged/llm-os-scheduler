"""Experiment 1: simulator validation.

Writes ``experiments/results/EXP1_<timestamp>/`` with:

* ``pytest_output.txt``   - full unit-test output;
* ``hand_example.csv``     - per-request timings of the 4-request worked example under
  FCFS and SJF-oracle, next to the hand-calculated values;
* ``analytical_check.csv`` - simulated mean waiting time vs. closed-form M/G/1 results
  (Pollaczek-Khinchine for FCFS; Cobham's non-preemptive priority formula for SJF);
* ``determinism.json``     - SHA-256 of per-request records from two identical runs;
* ``run_meta.json``.

Usage: ``python experiments/scripts/exp1_validate.py``
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_scheduler.analytical import nonpreemptive_priority_mean_wait, pk_mean_wait  # noqa: E402
from llm_scheduler.experiment_runner import code_hash  # noqa: E402
from llm_scheduler.metrics import request_records, summarize  # noqa: E402
from llm_scheduler.policies import FCFSPolicy, PredictiveSJFPolicy  # noqa: E402
from llm_scheduler.predictor import HeuristicPredictor, OraclePredictor  # noqa: E402
from llm_scheduler.service_model import ServiceModel  # noqa: E402
from llm_scheduler.simulator import Simulator  # noqa: E402
from llm_scheduler.workload import generate_workload, workload_from_rows  # noqa: E402

HAND_ROWS = [
    {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 5},
    {"arrival_time": 1.0, "prompt_tokens": 1, "output_tokens": 3},
    {"arrival_time": 2.0, "prompt_tokens": 1, "output_tokens": 1},
    {"arrival_time": 3.0, "prompt_tokens": 1, "output_tokens": 2},
]
# Hand-calculated (prefill 1 s, decode 1 s/token => service = n s):
HAND_EXPECTED = {
    "FCFS": {"start": [0, 5, 8, 9], "ttft": [1, 5, 7, 7], "jct": [5, 7, 7, 8], "wait": [0, 4, 6, 6]},
    "SJF-oracle": {"start": [0, 8, 5, 6], "ttft": [1, 8, 4, 4], "jct": [5, 10, 4, 5], "wait": [0, 7, 3, 3]},
}

ANALYTIC_MIXES = ["short_heavy", "mixed", "long_heavy"]
ANALYTIC_LOADS = [0.5, 0.7, 0.9]
ANALYTIC_SEEDS = [0, 1, 2, 3, 4]
ANALYTIC_N = 50_000


def run_pytest(out_dir: Path) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (out_dir / "pytest_output.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return proc.returncode


def hand_example(out_dir: Path) -> bool:
    sm = ServiceModel(prefill_base_s=1.0, prefill_per_token_s=0.0, decode_per_token_s=1.0)
    wl = workload_from_rows(HAND_ROWS)
    truth = {s.request_id: s.actual_output_tokens for s in wl.specs}
    sim = Simulator(sm)
    rows, ok = [], True
    for label, policy, pred in [("FCFS", FCFSPolicy(), None), ("SJF-oracle", PredictiveSJFPolicy(), OraclePredictor(truth))]:
        res = sim.run(wl, policy, pred)
        s = summarize(res)
        for r in sorted(res.requests, key=lambda q: q.request_id):
            i = r.request_id
            exp = HAND_EXPECTED[label]
            row = {
                "policy": label, "request_id": i, "arrival": r.arrival_time, "output_tokens": r.actual_output_tokens,
                "start_sim": r.start_time, "start_hand": exp["start"][i],
                "ttft_sim": r.ttft, "ttft_hand": exp["ttft"][i],
                "jct_sim": r.jct, "jct_hand": exp["jct"][i],
                "wait_sim": r.waiting_time, "wait_hand": exp["wait"][i],
            }
            row["match"] = all(row[f"{k}_sim"] == row[f"{k}_hand"] for k in ("start", "ttft", "jct", "wait"))
            ok &= row["match"]
            rows.append(row)
        rows.append({"policy": label, "request_id": "mean", "jct_sim": s["jct_mean"], "jct_hand": float(np.mean(exp["jct"])),
                     "wait_sim": s["wait_mean"], "wait_hand": float(np.mean(exp["wait"])),
                     "ttft_sim": s["ttft_mean"], "ttft_hand": float(np.mean(exp["ttft"]))})
    pd.DataFrame(rows).to_csv(out_dir / "hand_example.csv", index=False)
    return ok


def analytical_check(out_dir: Path) -> pd.DataFrame:
    sm = ServiceModel()
    sim = Simulator(sm)
    heur = HeuristicPredictor()
    rows = []
    for mix in ANALYTIC_MIXES:
        for load in ANALYTIC_LOADS:
            for seed in ANALYTIC_SEEDS:
                wl = generate_workload(mix, ANALYTIC_N, load, seed, sm)
                svc = np.array([sm.service_time(s.features.prompt_tokens, s.actual_output_tokens) for s in wl.specs])
                truth = {s.request_id: s.actual_output_tokens for s in wl.specs}
                cases = [
                    ("FCFS", FCFSPolicy(), None, pk_mean_wait(svc, wl.arrival_rate), "Pollaczek-Khinchine"),
                    ("SJF-oracle", PredictiveSJFPolicy(), OraclePredictor(truth),
                     nonpreemptive_priority_mean_wait(svc, [s.actual_output_tokens for s in wl.specs], wl.arrival_rate), "Cobham"),
                    ("SJF-heuristic", PredictiveSJFPolicy(), heur,
                     nonpreemptive_priority_mean_wait(svc, [heur.predict(s.features) for s in wl.specs], wl.arrival_rate), "Cobham"),
                ]
                for label, policy, pred, model_wait, formula in cases:
                    sim_wait = summarize(sim.run(wl, policy, pred))["wait_mean"]
                    rows.append({"mix": mix, "load": load, "seed": seed, "condition": label, "formula": formula,
                                 "sim_wait_mean": sim_wait, "model_wait_mean": model_wait,
                                 "rel_error_pct": (sim_wait - model_wait) / model_wait * 100})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "analytical_check.csv", index=False)
    return df


def lindley_check(out_dir: Path) -> pd.DataFrame:
    """FCFS simulator vs. an independent Lindley recursion, plus P-K on fresh seeds.

    Seeds 1000-1019 are used only here, so this check is independent of ``ANALYTIC_SEEDS``.
    """
    sm = ServiceModel()
    rows = []
    for mix in ANALYTIC_MIXES:
        for seed in range(1000, 1020):
            wl = generate_workload(mix, ANALYTIC_N, 0.5, seed, sm)
            a = np.array([s.arrival_time for s in wl.specs])
            svc = np.array([sm.service_time(s.features.prompt_tokens, s.actual_output_tokens) for s in wl.specs])
            w = np.zeros(len(a))
            for i in range(1, len(a)):
                w[i] = max(0.0, w[i - 1] + svc[i - 1] - (a[i] - a[i - 1]))
            sim_w = np.array([r.waiting_time for r in Simulator(sm).run(wl, FCFSPolicy()).requests])
            pk = pk_mean_wait(svc, wl.arrival_rate)
            rows.append({"mix": mix, "load": 0.5, "seed": seed, "max_abs_diff_s": float(np.abs(sim_w - w).max()),
                         "sim_wait_mean": float(sim_w.mean()), "pk_wait_mean": pk,
                         "rel_error_pct": (sim_w.mean() - pk) / pk * 100})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "lindley_check.csv", index=False)
    return df


def determinism(out_dir: Path) -> bool:
    sm = ServiceModel()
    digests = []
    for _ in range(2):
        wl = generate_workload("mixed", 5000, 0.9, 0, sm)
        res = Simulator(sm).run(wl, PredictiveSJFPolicy(), HeuristicPredictor())
        payload = json.dumps(request_records(res), sort_keys=True, default=str).encode()
        digests.append(hashlib.sha256(payload).hexdigest())
    same = digests[0] == digests[1]
    (out_dir / "determinism.json").write_text(json.dumps({"sha256_run1": digests[0], "sha256_run2": digests[1], "identical": same}, indent=2))
    return same


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "experiments" / "results" / f"EXP1_{stamp}"
    out_dir.mkdir(parents=True)
    t0 = time.perf_counter()
    meta = {"experiment_id": "EXP1", "run_name": out_dir.name, "code_hash": code_hash(),
            "command": "python experiments/scripts/exp1_validate.py", "started_at": datetime.now().isoformat(timespec="seconds"),
            "python": sys.version.split()[0], "simulated": True}

    rc = run_pytest(out_dir)
    print(f"pytest exit code {rc}")
    hand_ok = hand_example(out_dir)
    print(f"hand example matches: {hand_ok}")
    det_ok = determinism(out_dir)
    print(f"deterministic: {det_ok}")
    df = analytical_check(out_dir)
    agg = df.groupby(["condition", "mix", "load"])["rel_error_pct"].agg(["mean", "min", "max"]).round(2)
    print(agg.to_string())
    lind = lindley_check(out_dir)
    lind_max = float(lind["max_abs_diff_s"].max())
    print(f"max |simulator - Lindley| = {lind_max:.2e} s")
    print(lind.groupby("mix")["rel_error_pct"].agg(["mean", "std", "count"]).round(2).to_string())

    meta.update({"pytest_returncode": rc, "hand_example_match": hand_ok, "deterministic": det_ok,
                 "lindley_max_abs_diff_s": lind_max,
                 "analytic_mean_abs_rel_error_pct": float(df.groupby(["condition", "mix", "load"])["rel_error_pct"].mean().abs().mean()),
                 "wall_time_s": round(time.perf_counter() - t0, 2),
                 "status": "COMPLETED" if (rc == 0 and hand_ok and det_ok and lind_max < 1e-6) else "FAILED"})
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"-> {out_dir} ({meta['status']})")


if __name__ == "__main__":
    main()
