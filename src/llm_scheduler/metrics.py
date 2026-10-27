"""Metrics computed from a :class:`~llm_scheduler.simulator.SimulationResult`.

Definitions (all in simulated seconds unless stated):

* **waiting time** = start of service - arrival (queueing delay; the implemented policies
  are non-preemptive, so this is the total time spent waiting).
* **TTFT** = first-token time - arrival = waiting time + prefill time.
* **JCT** (job completion time) = completion time - arrival. *Not* the absolute
  completion timestamp.
* **service time** = completion - start = prefill + (n - 1) x decode time.
* **slowdown** = JCT / service time (>= 1; 1 means no waiting).
* **observation window** = [first arrival, end], where end is the last completion if
  every request finished, otherwise the horizon.
* **request throughput** = completed requests / window length.
* **token throughput** = output tokens generated inside the window / window length
  (includes the partial output of a request running at the horizon).
* **utilisation** = busy time of the slot inside the window / window length.
* **prediction error**: MAE = mean |predicted - actual| tokens; bias = mean
  (predicted - actual); MdAPE = median |predicted - actual| / actual x 100; Spearman and
  Kendall rank correlations between predicted and actual length (ordering quality is what
  SJF uses).

Percentiles are reported only with enough observations to be meaningful: P95 needs at
least ``MIN_N_P95`` values and P99 at least ``MIN_N_P99`` (about ten observations in the
tail); otherwise the value is NaN. JCT/TTFT statistics use completed requests only.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np
from scipy import stats

from .request import Request, RequestState
from .simulator import SimulationResult
from .workload import LENGTH_CATEGORIES, length_category

MIN_N_P95 = 200
MIN_N_P99 = 1000


def percentile(values: Sequence[float], q: float) -> float:
    """``q``-th percentile (linear interpolation), or NaN if too few observations."""
    n = len(values)
    if n == 0:
        return math.nan
    if q >= 99 and n < MIN_N_P99:
        return math.nan
    if 95 <= q < 99 and n < MIN_N_P95:
        return math.nan
    return float(np.percentile(np.asarray(values, dtype=float), q))


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else math.nan


def _median(values: Sequence[float]) -> float:
    return float(np.median(values)) if len(values) else math.nan


def _max(values: Sequence[float]) -> float:
    return float(np.max(values)) if len(values) else math.nan


def _dist(prefix: str, values: Sequence[float]) -> dict[str, float]:
    return {
        f"{prefix}_mean": _mean(values),
        f"{prefix}_median": _median(values),
        f"{prefix}_p95": percentile(values, 95),
        f"{prefix}_p99": percentile(values, 99),
        f"{prefix}_max": _max(values),
    }


def prediction_error(requests: Iterable[Request]) -> dict[str, float]:
    """Prediction error over requests that received a prediction."""
    pairs = [(r.predicted_output_tokens, r.actual_output_tokens) for r in requests if r.predicted_output_tokens is not None]
    if not pairs:
        return {k: math.nan for k in ("pred_mae", "pred_bias", "pred_mdape", "pred_spearman", "pred_kendall")}
    pred = np.array([p for p, _ in pairs], dtype=float)
    act = np.array([a for _, a in pairs], dtype=float)
    err = pred - act
    if len(pairs) > 1 and np.ptp(pred) > 0 and np.ptp(act) > 0:
        spearman = float(stats.spearmanr(pred, act).statistic)
        kendall = float(stats.kendalltau(pred, act).statistic)
    else:
        spearman = kendall = math.nan
    return {
        "pred_mae": float(np.mean(np.abs(err))),
        "pred_bias": float(np.mean(err)),
        "pred_mdape": float(np.median(np.abs(err) / act) * 100.0),
        "pred_spearman": spearman,
        "pred_kendall": kendall,
    }


def _timing_lists(requests: Iterable[Request]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {"jct": [], "wait": [], "ttft": [], "slowdown": []}
    for r in requests:
        if r.state is RequestState.COMPLETED:
            jct = r.jct
            svc = r.service_time
            out["jct"].append(jct)  # type: ignore[arg-type]
            out["ttft"].append(r.ttft)  # type: ignore[arg-type]
            out["slowdown"].append(jct / svc if svc else math.nan)  # type: ignore[operator]
        if r.start_time is not None:
            out["wait"].append(r.waiting_time)  # type: ignore[arg-type]
    return out


def summarize(result: SimulationResult) -> dict[str, Any]:
    """One row of run-level metrics."""
    reqs = result.requests
    n_completed = sum(r.state is RequestState.COMPLETED for r in reqs)
    n_waiting = sum(r.state is RequestState.WAITING for r in reqs)
    n_running = sum(r.state is RequestState.RUNNING for r in reqs)
    n_pending = sum(r.state is RequestState.PENDING for r in reqs)
    window = result.end_time - result.first_arrival
    tokens = sum(r.generated_tokens for r in reqs)
    lists = _timing_lists(reqs)

    row: dict[str, Any] = {
        "policy": result.policy,
        "predictor": result.predictor,
        "predictor_is_reference": result.predictor_uses_ground_truth,
        "n_requests": len(reqs),
        "n_completed": n_completed,
        "n_incomplete": n_waiting + n_running,
        "n_not_arrived": n_pending,
        "window_s": window,
        "throughput_rps": n_completed / window if window > 0 else math.nan,
        "throughput_tps": tokens / window if window > 0 else math.nan,
        "utilization": result.busy_time / window if window > 0 else math.nan,
        "n_preemptions": sum(r.preemption_count for r in reqs),
    }
    row.update(_dist("jct", lists["jct"]))
    row.update(_dist("wait", lists["wait"]))
    row.update(_dist("ttft", lists["ttft"]))
    row["slowdown_mean"] = _mean(lists["slowdown"])
    row["slowdown_p95"] = percentile(lists["slowdown"], 95)
    row.update(prediction_error(reqs))
    row["sim_wall_s"] = result.wall_time_s
    row["sched_us_per_decision"] = (
        result.scheduler_wall_s / max(result.n_decisions, 1) * 1e6
    )  # admit + select time per dispatched request
    row["predict_us_per_request"] = result.predictor_wall_s / max(len(reqs) - n_pending, 1) * 1e6
    return row


def summarize_by_category(result: SimulationResult) -> list[dict[str, Any]]:
    """Per output-length-category metrics (category from the *actual* output length)."""
    groups: dict[str, list[Request]] = {c: [] for c in LENGTH_CATEGORIES}
    for r in result.requests:
        groups[length_category(r.actual_output_tokens)].append(r)
    rows = []
    for cat in LENGTH_CATEGORIES:
        reqs = groups[cat]
        arrived = [r for r in reqs if r.state is not RequestState.PENDING]
        n_completed = sum(r.state is RequestState.COMPLETED for r in reqs)
        lists = _timing_lists(reqs)
        row: dict[str, Any] = {
            "category": cat,
            "n_requests": len(reqs),
            "n_arrived": len(arrived),
            "n_completed": n_completed,
            "completion_rate": n_completed / len(arrived) if arrived else math.nan,
        }
        row.update(_dist("jct", lists["jct"]))
        row.update(_dist("wait", lists["wait"]))
        row["ttft_mean"] = _mean(lists["ttft"])
        row["slowdown_mean"] = _mean(lists["slowdown"])
        row["slowdown_p95"] = percentile(lists["slowdown"], 95)
        rows.append(row)
    return rows


def request_records(result: SimulationResult) -> list[dict[str, Any]]:
    """Per-request rows (workload fields + outcome), for CSV export."""
    rows = []
    for r in result.requests:
        f = r.spec.features
        rows.append(
            {
                "request_id": r.request_id,
                "arrival_time": r.arrival_time,
                "task_type": f.task_type,
                "prompt_tokens": f.prompt_tokens,
                "detail_requested": f.detail_requested,
                "max_tokens": f.max_tokens,
                "actual_output_tokens": r.actual_output_tokens,
                "predicted_output_tokens": r.predicted_output_tokens,
                "category": length_category(r.actual_output_tokens),
                "state": r.state.value,
                "start_time": r.start_time,
                "first_token_time": r.first_token_time,
                "completion_time": r.completion_time,
                "waiting_time": r.waiting_time,
                "ttft": r.ttft,
                "jct": r.jct,
                "generated_tokens": r.generated_tokens,
                "preemption_count": r.preemption_count,
            }
        )
    return rows


def relative_reduction(baseline: float, value: float) -> float:
    """``(baseline - value) / baseline x 100`` - for lower-is-better metrics."""
    return (baseline - value) / baseline * 100.0 if baseline else math.nan


def relative_increase(baseline: float, value: float) -> float:
    """``(value - baseline) / baseline x 100`` - for higher-is-better metrics."""
    return (value - baseline) / baseline * 100.0 if baseline else math.nan


def mean_ci(values: Sequence[float], confidence: float = 0.95) -> tuple[float, float, float]:
    """Mean and two-sided Student-t confidence interval ``(mean, low, high)``.

    The unit of analysis is one value per independent workload seed.
    """
    arr = np.asarray([v for v in values if not math.isnan(v)], dtype=float)
    n = len(arr)
    if n == 0:
        return (math.nan, math.nan, math.nan)
    m = float(arr.mean())
    if n == 1:
        return (m, math.nan, math.nan)
    half = float(stats.t.ppf(0.5 + confidence / 2, n - 1) * arr.std(ddof=1) / math.sqrt(n))
    return (m, m - half, m + half)


def jain_index(values: Sequence[float]) -> float:
    """Jain's fairness index ``(sum x)^2 / (n * sum x^2)``, in (0, 1]; 1 = all equal."""
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0 or not np.any(arr):
        return math.nan
    return float(arr.sum() ** 2 / (len(arr) * np.square(arr).sum()))
