"""Config-driven experiment runner.

Usage::

    python -m llm_scheduler.experiment_runner --config experiments/configs/exp2_fcfs_vs_sjf.yaml

For every combination of mix x load x size x seed the runner generates **one** workload and
replays it under every condition (policy + predictor), so all comparisons are paired.

Each invocation writes a new directory ``experiments/results/<ID>[_<tag>]_<timestamp>/``
(never overwriting earlier runs) containing:

* ``config.yaml``      - the resolved configuration;
* ``summary.csv``      - one row per (workload, condition) run;
* ``by_category.csv``  - one row per run and output-length category;
* ``requests/*.csv.gz`` - per-request records for the workloads listed in ``save_requests``;
* ``run_meta.json``    - command, timing, code hash, platform and package versions.

A log is written to ``experiments/logs/<same name>.log``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import logging
import platform
import sys
import time
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

from .metrics import request_records, summarize, summarize_by_category
from .policies import build_policy
from .predictor import build_predictor
from .service_model import ServiceModel
from .simulator import Simulator
from .workload import generate_workload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"
log = logging.getLogger("llm_scheduler")


def code_hash() -> str:
    """SHA-256 (first 12 hex chars) of the package source; stands in for a git commit."""
    h = hashlib.sha256()
    for path in sorted((PROJECT_ROOT / "src" / "llm_scheduler").rglob("*.py")):
        h.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def load_config(path: Path, defaults_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Experiment config merged over ``config/default.yaml`` (experiment keys win)."""
    with open(defaults_path, encoding="utf-8") as fh:
        cfg: dict[str, Any] = yaml.safe_load(fh) or {}
    with open(path, encoding="utf-8") as fh:
        exp = yaml.safe_load(fh) or {}
    for key, value in exp.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg[key], **value}
        else:
            cfg[key] = value
    for key in ("experiment_id", "conditions"):
        if key not in cfg:
            raise KeyError(f"config {path} is missing {key!r}")
    labels = [c["label"] for c in cfg["conditions"]]
    if len(labels) != len(set(labels)):
        raise ValueError("condition labels must be unique")
    return cfg


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _resolve_horizon(spec: Any, workload) -> float | None:
    if spec is None:
        return None
    if spec == "last_arrival":
        return workload.specs[-1].arrival_time
    return float(spec)


def _should_save(cfg: Mapping[str, Any], mix: str, load: float, n: int, seed: int) -> bool:
    """Whether to write per-request records; filters may name mix, load, n_requests, seeds."""
    rule = cfg.get("save_requests")
    if rule == "all":
        return True
    for entry in rule or []:
        if (
            entry.get("mix", mix) == mix
            and float(entry.get("load", load)) == float(load)
            and int(entry.get("n_requests", n)) == int(n)
            and seed in entry.get("seeds", [seed])
        ):
            return True
    return False


def _package_versions() -> dict[str, str]:
    out = {}
    for pkg in ("numpy", "pandas", "scipy", "matplotlib", "PyYAML"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = "not installed"
    return out


def run_experiment(cfg: dict[str, Any], out_dir: Path) -> pd.DataFrame:
    """Run every workload x condition in ``cfg``; write outputs into ``out_dir``."""
    sm = ServiceModel(**cfg["service_model"])
    sim = Simulator(sm)
    mixes = _as_list(cfg["mixes"])
    loads = [float(x) for x in _as_list(cfg["loads"])]
    sizes = [int(x) for x in _as_list(cfg["n_requests"])]
    seeds = [int(x) for x in _as_list(cfg["seeds"])]
    conditions = cfg["conditions"]
    req_dir = out_dir / "requests"

    summary_rows: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []
    combos = list(itertools.product(mixes, loads, sizes, seeds))
    log.info("%d workloads x %d conditions = %d runs", len(combos), len(conditions), len(combos) * len(conditions))

    for idx, (mix, load, n, seed) in enumerate(combos, 1):
        t0 = time.perf_counter()
        wl = generate_workload(mix, n, load, seed, sm)
        wl_info = {f"wl_{k}": v for k, v in wl.describe(sm).items()}
        truth = {s.request_id: s.actual_output_tokens for s in wl.specs}
        horizon = _resolve_horizon(cfg.get("horizon"), wl)
        save = _should_save(cfg, mix, load, n, seed)
        for cond in conditions:
            policy = build_policy(cond)
            predictor = build_predictor(cond.get("predictor"), truth, seed)
            result = sim.run(wl, policy, predictor, horizon=horizon)
            keys = {
                "experiment_id": cfg["experiment_id"],
                "mix": mix,
                "load": load,
                "n_requests_cfg": n,
                "seed": seed,
                "condition": cond["label"],
                "aging_rate": cond.get("aging_rate"),
                "horizon_s": horizon,
            }
            summary_rows.append({**keys, **summarize(result), **wl_info})
            for row in summarize_by_category(result):
                category_rows.append({**keys, "policy": result.policy, "predictor": result.predictor, **row})
            if save:
                req_dir.mkdir(parents=True, exist_ok=True)
                name = f"{mix}_load{load:g}_n{n}_seed{seed}_{cond['label']}.csv.gz"
                pd.DataFrame(request_records(result)).to_csv(req_dir / name, index=False, compression="gzip")
        log.info(
            "[%d/%d] mix=%s load=%g n=%d seed=%d done in %.2fs",
            idx, len(combos), mix, load, n, seed, time.perf_counter() - t0,
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(category_rows).to_csv(out_dir / "by_category.csv", index=False)
    return summary


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path, help="experiment YAML")
    parser.add_argument("--results-root", type=Path, default=PROJECT_ROOT / "experiments" / "results")
    parser.add_argument("--logs-root", type=Path, default=PROJECT_ROOT / "experiments" / "logs")
    parser.add_argument("--seeds", type=int, nargs="+", help="override seeds (e.g. development seeds)")
    parser.add_argument("--tag", default="", help="label added to the run directory name, e.g. 'dev'")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.seeds:
        cfg["seeds"] = args.seeds
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_name = f"{cfg['experiment_id']}{'_' + args.tag if args.tag else ''}_{stamp}"
    out_dir = args.results_root / run_name
    out_dir.mkdir(parents=True, exist_ok=False)
    args.logs_root.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        logging.FileHandler(args.logs_root / f"{run_name}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)

    with open(out_dir / "config.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(copy.deepcopy(cfg), fh, sort_keys=False)
    meta: dict[str, Any] = {
        "run_name": run_name,
        "experiment_id": cfg["experiment_id"],
        "command": " ".join([Path(sys.executable).name, "-m", "llm_scheduler.experiment_runner", *sys.argv[1:]]),
        "config_file": args.config.as_posix(),
        "code_hash": code_hash(),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": _package_versions(),
        "simulated": True,
        "status": "RUNNING",
    }
    log.info("run %s (code %s) config %s", run_name, meta["code_hash"], args.config)
    t0 = time.perf_counter()
    try:
        summary = run_experiment(cfg, out_dir)
        meta["status"] = "COMPLETED"
        meta["n_runs"] = int(len(summary))
    except Exception as exc:  # record the failure, then re-raise
        meta["status"] = "FAILED"
        meta["error"] = repr(exc)
        log.exception("experiment failed")
        raise
    finally:
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        meta["wall_time_s"] = round(time.perf_counter() - t0, 3)
        with open(out_dir / "run_meta.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
    log.info("finished in %.1fs -> %s", meta["wall_time_s"], out_dir)
    return out_dir


if __name__ == "__main__":
    main()
