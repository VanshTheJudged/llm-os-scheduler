"""Analyse saved experiment outputs: paired statistics, tables and figures.

Usage::

    python experiments/scripts/analyze.py            # latest COMPLETED evaluation run of each experiment
    python experiments/scripts/analyze.py --run EXP2A=EXP2A_20261028-001500 ...

Reads only files under ``experiments/results/`` (never re-simulates). Writes:

* ``experiments/results/analysis/*.csv`` and ``tables.md`` - derived tables;
* ``experiments/figures/*.png`` - figures;
* ``experiments/results/analysis/sources.json`` - which run directory fed each output.

Statistics: the unit of analysis is one workload seed. For every seed the condition is
compared with FCFS on the *same* workload; the per-seed relative changes are summarised by
their mean and a two-sided 95 % Student-t interval across seeds, plus the number of seeds
on which the condition was better. Derived outputs are regenerated on every call; raw run
directories are never modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_scheduler import plotting as P  # noqa: E402
from llm_scheduler.metrics import jain_index, mean_ci  # noqa: E402

RESULTS = ROOT / "experiments" / "results"
FIG = ROOT / "experiments" / "figures"
OUT = RESULTS / "analysis"
EXPERIMENTS = ["EXP1", "EXP2A", "EXP2B", "EXP3", "EXP4", "EXP5", "EXP6", "EXP7"]
MAIN3 = ["FCFS", "SJF-heuristic", "SJF-oracle"]
MIXES = ["short_heavy", "mixed", "long_heavy"]
CATS = ["short", "medium", "long"]
KEYS = ["mix", "load", "n_requests_cfg"]

tables_md: list[str] = []
sources: dict[str, str] = {}


# ----------------------------------------------------------------------------- helpers
def latest_run(exp_id: str) -> Path:
    """Most recent untagged run directory of ``exp_id`` whose status is COMPLETED."""
    cands = sorted(p for p in RESULTS.glob(f"{exp_id}_2*") if p.is_dir())
    for p in reversed(cands):
        meta = p / "run_meta.json"
        if meta.exists() and json.loads(meta.read_text()).get("status") == "COMPLETED":
            return p
    raise FileNotFoundError(f"no completed run for {exp_id}")


def fmt_ci(m: float, lo: float, hi: float, digits: int = 1) -> str:
    if pd.isna(m):
        return "n/a"
    if pd.isna(lo):
        return f"{m:.{digits}f}"
    return f"{m:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def paired(summary: pd.DataFrame, metric: str, higher_better: bool = False, baseline: str = "FCFS",
           keys: list[str] = KEYS) -> pd.DataFrame:
    """Per-condition value and per-seed paired relative change vs ``baseline``.

    ``rel_*`` is the relative *improvement* in percent: (base - x) / base x 100 for
    lower-is-better metrics and (x - base) / base x 100 for higher-is-better ones.
    """
    base = summary[summary.condition == baseline].set_index(keys + ["seed"])[metric]
    rows = []
    for k, g in summary.groupby(keys + ["condition"], sort=False):
        g = g.set_index(keys + ["seed"])
        b = base.loc[g.index]
        x = g[metric]
        rel = (x - b) / b * 100 if higher_better else (b - x) / b * 100
        vm, vlo, vhi = mean_ci(list(x))
        rm, rlo, rhi = mean_ci(list(rel))
        rows.append({**dict(zip(keys + ["condition"], k)), "metric": metric, "value_mean": vm, "value_lo": vlo,
                     "value_hi": vhi, "rel_mean": rm, "rel_lo": rlo, "rel_hi": rhi, "rel_sd": float(np.std(rel, ddof=1)),
                     "n_seeds": len(g), "n_better": int((rel > 1e-9).sum()), "n_worse": int((rel < -1e-9).sum())})
    return pd.DataFrame(rows)


def _cell(v) -> str:
    if isinstance(v, float):
        return "n/a" if np.isnan(v) else (f"{v:.4g}" if abs(v) < 1e-2 and v != 0 else f"{v:,.3f}".rstrip("0").rstrip("."))
    return str(v)


def md_table(df: pd.DataFrame, title: str, note: str = "") -> None:
    tables_md.append(f"### {title}\n")
    if note:
        tables_md.append(note + "\n")
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    tables_md.append("\n".join(lines) + "\n")


def save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUT / name, index=False)


def cond_order(labels) -> list[str]:
    present = list(dict.fromkeys(labels))
    return [c for c in MAIN3 if c in present] + [c for c in present if c not in MAIN3]


# ----------------------------------------------------------------------------- EXP1
def exp1(run: Path) -> None:
    hand = pd.read_csv(run / "hand_example.csv")
    hand_tbl = hand[hand.request_id != "mean"][["policy", "request_id", "arrival", "output_tokens", "start_sim", "ttft_sim",
                                                "jct_sim", "wait_sim", "jct_hand", "wait_hand", "match"]]
    md_table(hand_tbl, "EXP1 - hand-calculated example (prefill 1 s, decode 1 s/token)")
    means = hand[hand.request_id == "mean"][["policy", "jct_sim", "jct_hand", "wait_sim", "wait_hand", "ttft_sim", "ttft_hand"]]
    md_table(means, "EXP1 - hand example means")
    an = pd.read_csv(run / "analytical_check.csv")
    agg = an.groupby(["condition", "formula", "mix", "load"], sort=False)["rel_error_pct"].agg(["mean", "min", "max"]).reset_index()
    agg = agg.round(2)
    save(agg, "EXP1_analytical_summary.csv")
    md_table(agg, "EXP1 - simulated vs analytical mean waiting time, relative error % (5 seeds x 50,000 requests)",
             "rel_error = (simulated - formula) / formula x 100. FCFS vs Pollaczek-Khinchine; SJF vs Cobham.")
    P.parity_plot(an, "model_wait_mean", "sim_wait_mean", "condition", MAIN3,
                  "Simulator vs queueing theory: mean waiting time", "analytical mean wait (s, log)",
                  "simulated mean wait (s, log)", FIG / "fig01_exp1_parity.png")
    lind = run / "lindley_check.csv"
    if lind.exists():
        ld = pd.read_csv(lind)
        lt = ld.groupby("mix")["rel_error_pct"].agg(["mean", "std", "count"]).reset_index()
        lt["se"] = lt["std"] / np.sqrt(lt["count"])
        lt["max_abs_diff_vs_lindley_s"] = ld.groupby("mix")["max_abs_diff_s"].max().values
        save(lt, "EXP1_lindley_summary.csv")
        shown = lt.round({"mean": 3, "std": 3, "se": 3})
        shown["max_abs_diff_vs_lindley_s"] = shown["max_abs_diff_vs_lindley_s"].map(lambda v: f"{v:.1e}")
        md_table(shown, "EXP1 - FCFS simulator vs Lindley recursion and P-K on fresh seeds 1000-1019 (load 0.5)",
                 "mean/std/se: relative error of simulated mean wait vs Pollaczek-Khinchine, %.")
    sources["fig01_exp1_parity.png"] = run.name


# ----------------------------------------------------------------------------- EXP2A
def exp2a(run: Path) -> None:
    s = pd.read_csv(run / "summary.csv")
    metrics = [("jct_mean", False), ("jct_median", False), ("jct_p95", False), ("jct_p99", False), ("wait_mean", False),
               ("ttft_mean", False), ("wait_max", False), ("throughput_rps", True), ("throughput_tps", True)]
    allp = pd.concat([paired(s, m, hb) for m, hb in metrics])
    save(allp, "EXP2A_paired.csv")
    at = allp[(allp.load == 0.8)]
    tbl = at.assign(value=[fmt_ci(a, b, c, 2) for a, b, c in zip(at.value_mean, at.value_lo, at.value_hi)],
                    change=[fmt_ci(a, b, c) if cnd != "FCFS" else "-" for a, b, c, cnd in zip(at.rel_mean, at.rel_lo, at.rel_hi, at.condition)],
                    better=[f"{b}/{n}" if cnd != "FCFS" else "-" for b, n, cnd in zip(at.n_better, at.n_seeds, at.condition)])
    md_table(tbl[["metric", "condition", "value", "change", "better"]],
             "EXP2A - mixed workload, load 0.8, 10 seeds x 5,000 requests",
             "value: mean across seeds [95% t-CI] (seconds; throughput in req/s or tokens/s). "
             "change: paired relative improvement vs FCFS in % (positive = better). better: seeds on which the condition beat FCFS.")
    red = allp[allp.metric.isin(["jct_mean", "jct_p95", "jct_p99", "wait_max"]) & (allp.condition != "FCFS")]
    red_tbl = red.assign(improvement=[fmt_ci(a, b, c) for a, b, c in zip(red.rel_mean, red.rel_lo, red.rel_hi)],
                         better=[f"{b}/{n}" for b, n in zip(red.n_better, red.n_seeds)])
    red_tbl = red_tbl.pivot_table(index=["metric", "condition"], columns="load", values="improvement", aggfunc="first").reset_index()
    md_table(red_tbl, "EXP2A - relative improvement vs FCFS (%) by load, mean [95% CI] over 10 seeds",
             "Negative = worse than FCFS.")
    for metric, fname, title in [("jct_mean", "fig02_exp2a_mean_jct_vs_load.png", "Mean job completion time vs offered load"),
                                 ("jct_p95", "fig03_exp2a_p95_jct_vs_load.png", "P95 job completion time vs offered load")]:
        d = allp[allp.metric == metric]
        P.line_with_ci(d, "load", "value_mean", "value_lo", "value_hi", "condition", MAIN3, title + " (mixed workload)",
                       "offered load rho (utilisation of the single slot)", f"{'mean' if metric == 'jct_mean' else 'P95'} JCT (s)",
                       FIG / fname, label_offsets={"SJF-heuristic": 4, "SJF-oracle": -6})
        sources[fname] = run.name
    d = allp[(allp.metric == "jct_mean") & (allp.condition != "FCFS")]
    P.line_with_ci(d, "load", "rel_mean", "rel_lo", "rel_hi", "condition", MAIN3,
                   "Reduction in mean JCT vs FCFS, by offered load (mixed workload)", "offered load rho",
                   "mean-JCT reduction vs FCFS (%)", FIG / "fig04_exp2a_reduction_vs_load.png", hline=0.0)
    sources["fig04_exp2a_reduction_vs_load.png"] = run.name
    bars = allp[(allp.load == 0.8) & allp.metric.isin(["jct_mean", "jct_median", "jct_p95", "jct_p99"])].copy()
    bars["metric"] = bars.metric.map({"jct_mean": "mean", "jct_median": "median", "jct_p95": "P95", "jct_p99": "P99"})
    P.grouped_bars(bars, "metric", "condition", "value_mean", "value_lo", "value_hi", ["median", "mean", "P95", "P99"], MAIN3,
                   "Job completion time at load 0.8 (mixed workload, 10 seeds)", "JCT (s)", FIG / "fig05_exp2a_jct_summary_load08.png",
                   "{:.0f}")
    sources["fig05_exp2a_jct_summary_load08.png"] = run.name


# ----------------------------------------------------------------------------- EXP2B
def exp2b(run: Path, run2a: Path | None) -> None:
    s = pd.read_csv(run / "summary.csv")
    rows = []
    for m, hb in [("n_completed", True), ("n_incomplete", False), ("throughput_rps", True), ("throughput_tps", True),
                  ("jct_mean", False), ("utilization", True)]:
        rows.append(paired(s, m, hb))
    p = pd.concat(rows)
    save(p, "EXP2B_paired.csv")
    tbl = p.assign(value=[fmt_ci(a, b, c, 3 if "throughput" in m or m == "utilization" else 1)
                          for a, b, c, m in zip(p.value_mean, p.value_lo, p.value_hi, p.metric)],
                   change=[fmt_ci(a, b, c, 2) if cnd != "FCFS" else "-" for a, b, c, cnd in zip(p.rel_mean, p.rel_lo, p.rel_hi, p.condition)])
    md_table(tbl[["load", "metric", "condition", "value", "change"]],
             "EXP2B - overload, horizon = last arrival, 10 seeds x 5,000 requests",
             "jct_mean covers completed requests only (biased toward short requests under SJF). change: % improvement vs FCFS.")
    P.apply_style()
    fig, axes = P.plt.subplots(1, 2, figsize=(10.5, 4.2))
    labels = ["FCFS", "SJF-heuristic"]
    frames = []
    if run2a is not None:
        s2 = pd.read_csv(run2a / "summary.csv")
        s2 = s2[(s2.load.isin([0.8, 0.95])) & s2.condition.isin(labels)]
        frames.append(s2)
    frames.append(s)
    allr = pd.concat(frames)
    allr["load_label"] = allr.load.map(lambda x: f"rho={x:g}")
    order = [f"rho={x:g}" for x in sorted(allr.load.unique())]
    for ax, (metric, ylabel, fmt) in zip(axes, [("throughput_rps", "completed requests per second", "{:.3f}"),
                                                ("throughput_tps", "generated tokens per second", "{:.1f}")]):
        agg = allr.groupby(["load_label", "condition"])[metric].mean().reset_index()
        P.grouped_bars(agg, "load_label", "condition", metric, None, None, order, labels, ylabel.capitalize(), ylabel, Path(), fmt, ax=ax)
    fig.suptitle("Throughput: identical below capacity, diverges only under overload with a finite horizon",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=P.INK)
    P._finish(fig, FIG / "fig06_exp2b_throughput.png",
              P.SIM_NOTE + " rho<1 from EXP2A (all requests complete); rho>1 from EXP2B (horizon = last arrival).")
    sources["fig06_exp2b_throughput.png"] = f"{run.name} + {run2a.name if run2a else ''}"


# ----------------------------------------------------------------------------- EXP3
def exp3(run: Path) -> None:
    s = pd.read_csv(run / "summary.csv")
    c = pd.read_csv(run / "by_category.csv")
    p = pd.concat([paired(s, m) for m in ["jct_mean", "jct_p95", "wait_mean"]])
    save(p, "EXP3_paired.csv")
    wl = s[s.condition == "FCFS"].groupby(["mix"])[["wl_mean_output_tokens", "wl_median_output_tokens", "wl_cv_service",
                                                    "wl_share_short", "wl_share_medium", "wl_share_long", "wl_mean_service_s"]].mean()
    wl = wl.reindex(MIXES).reset_index().round(3)
    save(wl, "EXP3_workload_stats.csv")
    md_table(wl, "EXP3 - workload statistics (mean over 10 seeds, 5,000 requests each)")
    q = p[p.condition != "FCFS"]
    t = q.assign(improvement=[fmt_ci(a, b, cc) for a, b, cc in zip(q.rel_mean, q.rel_lo, q.rel_hi)],
                 better=[f"{b}/{n}" for b, n in zip(q.n_better, q.n_seeds)])
    md_table(t[["mix", "load", "metric", "condition", "improvement", "better"]],
             "EXP3 - relative improvement vs FCFS (%) by workload mix, mean [95% CI] over 10 seeds")
    cat = c.groupby(["mix", "load", "condition", "category"], sort=False)[["n_requests", "wait_mean", "wait_p95", "wait_max", "jct_mean", "slowdown_mean"]].mean().reset_index()
    save(cat.round(3), "EXP3_by_category.csv")
    for load in sorted(cat.load.unique()):
        ct = cat[cat.load == load].pivot_table(index=["mix", "category"], columns="condition", values="wait_mean").reindex(columns=MAIN3)
        ct = ct.reindex(pd.MultiIndex.from_product([MIXES, CATS])).reset_index().rename(columns={"level_0": "mix", "level_1": "category"})
        md_table(ct.round(1), f"EXP3 - mean waiting time (s) by actual-length category, load {load:g}")
    d = p[(p.metric == "jct_mean") & (p.condition != "FCFS")].copy()
    P.apply_style()
    fig, axes = P.plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for ax, load in zip(axes, sorted(d.load.unique())):
        P.grouped_bars(d[d.load == load], "mix", "condition", "rel_mean", "rel_lo", "rel_hi", MIXES, ["SJF-heuristic", "SJF-oracle"],
                       f"load {load:g}", "mean-JCT reduction vs FCFS (%)" if load == min(d.load) else "", Path(), "{:.0f}%", ax=ax)
    fig.suptitle("Mean-JCT reduction vs FCFS by workload composition", x=0.01, ha="left", fontsize=12, fontweight="bold", color=P.INK)
    P._finish(fig, FIG / "fig07_exp3_reduction_by_mix.png")
    sources["fig07_exp3_reduction_by_mix.png"] = run.name
    P.small_multiple_bars(cat[cat.load == 0.8], "mix", MIXES, "category", CATS, "condition", MAIN3, "wait_mean",
                          "Mean waiting time by actual output-length category (load 0.8)", "mean waiting time (s)",
                          FIG / "fig08_exp3_wait_by_category.png")
    sources["fig08_exp3_wait_by_category.png"] = run.name


# ----------------------------------------------------------------------------- EXP4
def exp4(run: Path) -> None:
    s = pd.read_csv(run / "summary.csv")
    p = pd.concat([paired(s, "jct_mean"), paired(s, "jct_p95"), paired(s, "wait_max")])
    save(p, "EXP4_paired.csv")
    acc = s.groupby(["load", "condition"], sort=False)[["pred_spearman", "pred_kendall", "pred_mae", "pred_mdape", "pred_bias", "predictor_is_reference"]].mean().reset_index()
    jm = p[p.metric == "jct_mean"].set_index(["load", "condition"])
    j95 = p[p.metric == "jct_p95"].set_index(["load", "condition"])
    acc = acc.set_index(["load", "condition"])
    acc["jct_mean"] = jm.value_mean
    acc["jct_reduction_pct"] = jm.rel_mean
    acc["jct_reduction_ci"] = [fmt_ci(a, b, c) for a, b, c in zip(jm.rel_mean, jm.rel_lo, jm.rel_hi)]
    acc["p95_reduction_pct"] = j95.rel_mean
    acc = acc.reset_index()
    for load in acc.load.unique():
        f = acc[(acc.load == load) & (acc.condition == "FCFS")].jct_mean.item()
        o = acc[(acc.load == load) & (acc.condition == "SJF-oracle")].jct_mean.item()
        acc.loc[acc.load == load, "gain_captured_pct"] = (f - acc.loc[acc.load == load, "jct_mean"]) / (f - o) * 100
    save(acc.round(4), "EXP4_predictor_table.csv")
    show = acc[["load", "condition", "predictor_is_reference", "pred_spearman", "pred_mae", "pred_mdape", "jct_mean",
                "jct_reduction_ci", "p95_reduction_pct", "gain_captured_pct"]].round(3)
    md_table(show, "EXP4 - predictor quality vs scheduling outcome (mixed workload, 10 seeds)",
             "gain_captured = (FCFS - x) / (FCFS - oracle) x 100, using seed-averaged mean JCT. "
             "Reference conditions (oracle, noisy oracle) read the actual length and are not deployable.")
    a = acc[acc.condition != "FCFS"].copy()
    a["rel_to_fcfs"] = 1 - a.jct_reduction_pct / 100
    curve = a.condition.str.startswith("SJF-noise") | (a.condition == "SJF-oracle")
    P.scatter_labeled(a, "pred_spearman", "rel_to_fcfs", "condition", curve,
                      "Scheduling quality tracks rank correlation of predictions", "Spearman rank correlation (predicted vs actual length)",
                      "mean JCT relative to FCFS (1.0 = FCFS)", FIG / "fig09_exp4_rank_vs_jct.png", {"FCFS": 1.0},
                      label_offsets={"SJF-heuristic": (8, 12), "SJF-oracle": (-6, -12), "SJF-noise0.5": (4, 8),
                                     "SJF-noise1.0": (4, -14), "SJF-random": (6, 6), "SJF-max_tokens": (6, -12)},
                      facet="load", facet_order=sorted(a.load.unique()),
                      skip_labels={"SJF-noise0.1", "SJF-noise0.25", "SJF-noise0.75"})
    sources["fig09_exp4_rank_vs_jct.png"] = run.name
    noise = p[(p.metric == "jct_mean") & (p.condition.str.startswith("SJF-noise") | (p.condition == "SJF-oracle"))].copy()
    noise["sigma"] = noise.condition.map(lambda c: 0.0 if c == "SJF-oracle" else float(c.replace("SJF-noise", "")))
    noise["series"] = noise.load.map(lambda x: f"noisy oracle, load {x:g}")
    P.apply_style()
    fig, ax = P.plt.subplots(figsize=(7.0, 4.2))
    shades = {0.8: P.color_for("SJF-oracle"), 0.9: P.INK_2}
    for load, d in noise.groupby("load"):
        d = d.sort_values("sigma")
        ax.fill_between(d.sigma, d.value_lo, d.value_hi, color=shades[load], alpha=0.12, linewidth=0)
        ax.plot(d.sigma, d.value_mean, color=shades[load], label=f"SJF + noisy oracle, load {load:g}", **P._marker_kw(shades[load]))
        f = p[(p.metric == "jct_mean") & (p.condition == "FCFS") & (p.load == load)].value_mean.item()
        h = p[(p.metric == "jct_mean") & (p.condition == "SJF-heuristic") & (p.load == load)].value_mean.item()
        ax.axhline(f, color=P.color_for("FCFS"), linewidth=1.0)
        ax.annotate(f"FCFS, load {load:g}", (3.0, f), xytext=(-4, 4), textcoords="offset points", ha="right", fontsize=8, color=P.INK_2)
        ax.axhline(h, color=P.color_for("SJF-heuristic"), linewidth=1.0)
        ax.annotate(f"SJF-heuristic, load {load:g}", (3.0, h), xytext=(-4, 4), textcoords="offset points", ha="right", fontsize=8, color=P.INK_2)
    ax.set_title("Mean JCT vs synthetic prediction noise (mixed workload)")
    ax.set_xlabel("noise level sigma (prediction = actual x exp(sigma z), z ~ N(0,1))")
    ax.set_ylabel("mean JCT (s)")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=8)
    P._finish(fig, FIG / "fig10_exp4_noise_sweep.png")
    sources["fig10_exp4_noise_sweep.png"] = run.name


# ----------------------------------------------------------------------------- EXP5
def exp5(run: Path) -> None:
    c = pd.read_csv(run / "by_category.csv")
    s = pd.read_csv(run / "summary.csv")
    rows = []
    for (mix, cond, cat), g in c.groupby(["mix", "condition", "category"], sort=False):
        wm = mean_ci(list(g.wait_mean))
        rows.append({"mix": mix, "condition": cond, "category": cat, "n_per_seed": g.n_requests.mean(),
                     "wait_mean": wm[0], "wait_mean_ci": fmt_ci(*wm), "wait_p95": g.wait_p95.mean(),
                     "wait_max_mean": g.wait_max.mean(), "wait_max_overall": g.wait_max.max(),
                     "slowdown_mean": g.slowdown_mean.mean(), "completion_rate": g.completion_rate.mean()})
    cat = pd.DataFrame(rows)
    save(cat.round(3), "EXP5_by_category.csv")
    md_table(cat[["mix", "condition", "category", "n_per_seed", "wait_mean_ci", "wait_p95", "wait_max_mean", "wait_max_overall",
                  "slowdown_mean", "completion_rate"]].round(2),
             "EXP5 - waiting time by actual-length category, load 0.9, 10 seeds x 5,000 requests",
             "wait_p95: mean of per-seed P95 (NaN when a category has < 200 requests in a seed). wait_max_mean: mean of per-seed maxima.")
    # Starvation indicator: requests whose wait exceeds the largest FCFS wait on the same workload.
    req_dir = run / "requests"
    starv, frames = [], []
    for mix in MIXES:
        for seed in sorted(s.seed.unique()):
            per = {cnd: pd.read_csv(req_dir / f"{mix}_load0.9_n5000_seed{seed}_{cnd}.csv.gz") for cnd in MAIN3}
            fmax = per["FCFS"].waiting_time.max()
            for cnd, df in per.items():
                over = df[df.waiting_time > fmax]
                sd = (df.jct / (df.jct - df.waiting_time))
                row = {"mix": mix, "seed": seed, "condition": cnd, "fcfs_max_wait": fmax, "n_over": len(over),
                       "jain_slowdown": jain_index(sd.to_numpy())}
                for ct in CATS:
                    row[f"n_over_{ct}"] = int((over.category == ct).sum())
                starv.append(row)
                if mix == "mixed":
                    frames.append(df.assign(condition=cnd, seed=seed)[["condition", "seed", "category", "waiting_time"]])
    st = pd.DataFrame(starv)
    save(st, "EXP5_starvation_per_seed.csv")
    sa = st.groupby(["mix", "condition"], sort=False)[["n_over", "n_over_short", "n_over_medium", "n_over_long", "jain_slowdown"]].agg(["mean", "max"]).round(3)
    sa.columns = [f"{a}_{b}" for a, b in sa.columns]
    sa = sa.reset_index()
    save(sa, "EXP5_starvation_summary.csv")
    md_table(sa, "EXP5 - requests waiting longer than the maximum FCFS wait on the same workload (per seed; mean and max over 10 seeds)",
             "Jain index computed over per-request slowdown (JCT / service time) within one run: 1 = all equal.")
    allreq = pd.concat(frames)
    P.ecdf_small_multiples(allreq, "category", CATS, "condition", MAIN3, "waiting_time",
                           "Waiting-time distribution by actual output length (mixed workload, load 0.9, 10 seeds pooled)",
                           "waiting time (s, log scale)", FIG / "fig11_exp5_wait_ecdf.png")
    sources["fig11_exp5_wait_ecdf.png"] = run.name
    P.small_multiple_bars(cat.rename(columns={"wait_max_mean": "wmax"}), "mix", MIXES, "category", CATS, "condition", MAIN3, "wmax",
                          "Maximum waiting time per seed by length category (load 0.9, mean of 10 seeds)", "max waiting time (s)",
                          FIG / "fig12_exp5_max_wait.png")
    sources["fig12_exp5_max_wait.png"] = run.name
    P.small_multiple_bars(cat, "mix", MIXES, "category", CATS, "condition", MAIN3, "slowdown_mean",
                          "Mean slowdown (JCT / service time) by length category (load 0.9)", "mean slowdown (log)",
                          FIG / "fig13_exp5_slowdown.png", "{:.1f}", log=True)
    sources["fig13_exp5_slowdown.png"] = run.name


# ----------------------------------------------------------------------------- EXP6
def exp6(run: Path) -> None:
    s = pd.read_csv(run / "summary.csv")
    p = pd.concat([paired(s, "jct_mean"), paired(s, "jct_p95")])
    save(p, "EXP6_paired.csv")
    q = p[p.condition != "FCFS"]
    perf = s.groupby(["n_requests_cfg", "condition"])[["sim_wall_s", "sched_us_per_decision", "predict_us_per_request"]].mean().reset_index()
    save(perf.round(4), "EXP6_runtime.csv")
    t = q.pivot_table(index="n_requests_cfg", columns="metric", values=["rel_mean", "rel_lo", "rel_hi", "rel_sd"]).round(2)
    t.columns = [f"{a}_{b}" for a, b in t.columns]
    t = t.reset_index()
    wall = perf.pivot_table(index="n_requests_cfg", columns="condition", values="sim_wall_s").round(3).add_prefix("wall_s_").reset_index()
    us = perf.pivot_table(index="n_requests_cfg", columns="condition", values="sched_us_per_decision").round(2).add_prefix("sched_us_").reset_index()
    t = t.merge(wall, on="n_requests_cfg").merge(us, on="n_requests_cfg")
    md_table(t, "EXP6 - SJF-heuristic vs FCFS by workload size (mixed, load 0.8, 10 seeds)",
             "rel_* = % improvement vs FCFS; rel_sd = standard deviation across seeds. wall_s = simulated run wall-clock seconds (this laptop, Python). "
             "sched_us = measured Python time in admit+select per dispatched request (microseconds).")
    d = q[q.metric == "jct_mean"]
    P.line_with_ci(d, "n_requests_cfg", "rel_mean", "rel_lo", "rel_hi", "condition", ["SJF-heuristic"],
                   "Mean-JCT reduction of SJF-heuristic vs FCFS by workload size", "requests per workload (log scale)",
                   "mean-JCT reduction vs FCFS (%)", FIG / "fig14_exp6_size.png", logx=True, ylim=(0, 60))
    sources["fig14_exp6_size.png"] = run.name


# ----------------------------------------------------------------------------- EXP7
def exp7(run: Path) -> None:
    s = pd.read_csv(run / "summary.csv")
    c = pd.read_csv(run / "by_category.csv")
    p = pd.concat([paired(s, m) for m in ["jct_mean", "jct_p95", "wait_max", "wait_p99"]])
    save(p, "EXP7_paired.csv")
    long = c[c.category == "long"].groupby(["mix", "condition"], sort=False)[["wait_mean", "wait_p95", "wait_max"]].mean().add_prefix("long_")
    v = p.pivot_table(index=["mix", "condition"], columns="metric", values="value_mean")
    r = p.pivot_table(index=["mix", "condition"], columns="metric", values="rel_mean").add_prefix("impr_")
    t = v.join(r).join(long).reset_index()
    t["aging_rate"] = t.condition.map(lambda x: 0.0 if x == "SJF-heuristic" else (np.inf if x == "FCFS" else float(x.split("-")[1])))
    t = t.sort_values(["mix", "aging_rate"])
    save(t.round(3), "EXP7_tradeoff.csv")
    md_table(t[["mix", "condition", "aging_rate", "jct_mean", "impr_jct_mean", "jct_p95", "wait_max", "impr_wait_max",
                "long_wait_mean", "long_wait_p95", "long_wait_max"]].round(1),
             "EXP7 (extension) - linear aging sweep, load 0.9, 10 seeds",
             "aging_rate in tokens of priority per second waited (0 = SJF, inf = FCFS). impr_* = % improvement vs FCFS (negative = worse).")
    panels = []
    for mix in ["mixed", "long_heavy"]:
        d = t[t.mix == mix].copy()
        d["pt"] = d.condition.map(lambda x: x if x in ("FCFS", "SJF-heuristic") else "a=" + x.split("-")[1])
        panels.append((f"{mix} workload", d))
    P.tradeoff_curve(panels, "jct_mean", "wait_max", "pt", {"FCFS": "FCFS", "SJF-heuristic": "SJF-heuristic (a=0)"},
                     "Aging trades mean JCT for worst-case waiting (load 0.9; a = aging rate, tokens/s)",
                     "mean JCT (s)", "maximum waiting time per seed (s, mean of 10)", FIG / "fig15_exp7_aging_tradeoff.png",
                     label_points=["a=0.5", "a=1", "a=2", "a=3", "a=5", "a=10"],
                     label_offsets={"SJF-heuristic": (8, -2), "FCFS": (-4, -14)},
                     note="Unlabelled: a=0.1 and 0.3 coincide with SJF; a=30 and 100 lie next to FCFS.")
    sources["fig15_exp7_aging_tradeoff.png"] = run.name


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", nargs="*", default=[], help="override run directory, e.g. EXP2A=EXP2A_20261028-001500")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    override = dict(item.split("=", 1) for item in args.run)
    runs: dict[str, Path | None] = {}
    for e in EXPERIMENTS:
        try:
            runs[e] = RESULTS / override[e] if e in override else latest_run(e)
        except FileNotFoundError as exc:
            print(f"skip {e}: {exc}")
            runs[e] = None
    tables_md.append("# Derived tables\n\nGenerated by `experiments/scripts/analyze.py` from these runs:\n")
    for e, r in runs.items():
        tables_md.append(f"- {e}: `{r.name if r else 'MISSING'}`")
    tables_md.append("")
    steps = {"EXP1": exp1, "EXP2A": exp2a, "EXP3": exp3, "EXP4": exp4, "EXP5": exp5, "EXP6": exp6, "EXP7": exp7}
    for e, fn in steps.items():
        if runs[e] is not None:
            print(f"analysing {e} <- {runs[e].name}")
            fn(runs[e])
            if e == "EXP2A" and runs["EXP2B"] is not None:
                print(f"analysing EXP2B <- {runs['EXP2B'].name}")
                exp2b(runs["EXP2B"], runs["EXP2A"])
    (OUT / "tables.md").write_text("\n".join(tables_md), encoding="utf-8")
    (OUT / "sources.json").write_text(json.dumps({"runs": {k: (v.name if v else None) for k, v in runs.items()}, "figures": sources}, indent=2))
    print(f"wrote {OUT / 'tables.md'} and {len(sources)} figures")


if __name__ == "__main__":
    main()
