"""Collect every number shown on the slides from the saved analysis outputs.

Writes presentation/deck_data.json, which build_deck.js reads. Nothing on the slides is
typed in by hand: re-run `python experiments/scripts/analyze.py`, then this script, then
`node presentation/build_deck.js` to refresh the deck.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "experiments" / "results" / "analysis"


def r(x, d=1):
    return None if pd.isna(x) else round(float(x), d)


def main() -> None:
    src = json.loads((A / "sources.json").read_text())
    out: dict = {"sources": src["runs"]}

    # EXP1
    an = pd.read_csv(A / "EXP1_analytical_summary.csv")
    lind = pd.read_csv(A / "EXP1_lindley_summary.csv")
    exp1_dir = ROOT / "experiments" / "results" / src["runs"]["EXP1"]
    meta = json.loads((exp1_dir / "run_meta.json").read_text())
    pytest_last = (exp1_dir / "pytest_output.txt").read_text(encoding="utf-8").strip().splitlines()[-1]
    out["exp1"] = {
        "mean_abs_err_pct": r(an["mean"].abs().mean(), 1),
        "n_cells": int(len(an)),
        "lindley_max_diff_s": float(lind["max_abs_diff_vs_lindley_s"].max()),
        "pk_fresh_err_range": [r(lind["mean"].min(), 1), r(lind["mean"].max(), 1)],
        "pytest": pytest_last.strip("= "),
        "deterministic": bool(meta["deterministic"]),
        "hand_match": bool(meta["hand_example_match"]),
    }

    # EXP2A
    p = pd.read_csv(A / "EXP2A_paired.csv")
    jm = p[p.metric == "jct_mean"]
    loads = sorted(jm.load.unique())
    out["exp2a"] = {
        "loads": [float(x) for x in loads],
        "mean_jct": {c: [r(jm[(jm.condition == c) & (jm.load == l)].value_mean.item()) for l in loads]
                     for c in ["FCFS", "SJF-heuristic", "SJF-oracle"]},
        "reduction_heur": [r(jm[(jm.condition == "SJF-heuristic") & (jm.load == l)].rel_mean.item()) for l in loads],
    }
    at = p[(p.load == 0.8)]

    def g(metric, cond, col="value_mean", d=1):
        return r(at[(at.metric == metric) & (at.condition == cond)][col].item(), d)

    out["exp2a"]["at08"] = {m: {"fcfs": g(m, "FCFS", d=3 if "through" in m else 1), "heur": g(m, "SJF-heuristic", d=3 if "through" in m else 1),
                               "heur_rel": g(m, "SJF-heuristic", "rel_mean"), "heur_lo": g(m, "SJF-heuristic", "rel_lo"),
                               "heur_hi": g(m, "SJF-heuristic", "rel_hi"), "oracle_rel": g(m, "SJF-oracle", "rel_mean"),
                               "better": int(at[(at.metric == m) & (at.condition == "SJF-heuristic")].n_better.item())}
                            for m in ["jct_mean", "jct_p95", "jct_p99", "ttft_mean", "wait_max", "throughput_tps", "throughput_rps"]}
    p99 = p[(p.metric == "jct_p99") & (p.condition == "SJF-heuristic")]
    out["exp2a"]["p99_heur"] = {f"{l:g}": r(p99[p99.load == l].rel_mean.item()) for l in loads}

    # EXP2B
    b = pd.read_csv(A / "EXP2B_paired.csv")
    nb = b[(b.metric == "n_completed") & (b.condition == "SJF-heuristic")]
    tb = b[(b.metric == "throughput_tps") & (b.condition == "SJF-heuristic")]
    out["exp2b"] = {"completed_gain": {f"{l:g}": r(nb[nb.load == l].rel_mean.item()) for l in nb.load},
                    "tokens_change": {f"{l:g}": r(tb[tb.load == l].rel_mean.item(), 2) for l in tb.load}}

    # EXP3
    e3 = pd.read_csv(A / "EXP3_paired.csv")
    e3 = e3[(e3.metric == "jct_mean") & (e3.load == 0.8)]
    wl = pd.read_csv(A / "EXP3_workload_stats.csv").set_index("mix")
    mixes = ["short_heavy", "mixed", "long_heavy"]
    out["exp3"] = {"mixes": mixes,
                   "heur": [r(e3[(e3.mix == m) & (e3.condition == "SJF-heuristic")].rel_mean.item()) for m in mixes],
                   "oracle": [r(e3[(e3.mix == m) & (e3.condition == "SJF-oracle")].rel_mean.item()) for m in mixes],
                   "cv": [r(wl.loc[m, "wl_cv_service"], 2) for m in mixes]}

    # EXP4
    e4 = pd.read_csv(A / "EXP4_predictor_table.csv")
    e4 = e4[(e4.load == 0.8) & (e4.condition != "FCFS")]
    keep = ["SJF-oracle", "SJF-noise0.5", "SJF-heuristic", "SJF-noise1.0", "SJF-noise2.0", "SJF-noise3.0",
            "SJF-max_tokens", "SJF-random", "SJF-prompt_length"]
    rows = []
    for c in keep:
        row = e4[e4.condition == c].iloc[0]
        rows.append({"condition": c, "spearman": r(row.pred_spearman, 2), "reduction": r(row.jct_reduction_pct),
                     "gain_captured": r(row.gain_captured_pct, 0), "reference": bool(row.predictor_is_reference)})
    out["exp4"] = rows
    e4_09 = pd.read_csv(A / "EXP4_predictor_table.csv")
    out["exp4_prompt_len_09"] = r(e4_09[(e4_09.load == 0.9) & (e4_09.condition == "SJF-prompt_length")].jct_reduction_pct.item())

    # EXP5
    e5 = pd.read_csv(A / "EXP5_by_category.csv")
    m5 = e5[e5.mix == "mixed"]
    conds = ["FCFS", "SJF-heuristic", "SJF-oracle"]
    cats = ["short", "medium", "long"]
    out["exp5"] = {"cats": cats,
                   "wait_mean": {c: [r(m5[(m5.condition == c) & (m5.category == k)].wait_mean.item()) for k in cats] for c in conds},
                   "long_max": {c: r(m5[(m5.condition == c) & (m5.category == "long")].wait_max_mean.item(), 0) for c in conds},
                   "short_slowdown": {c: r(m5[(m5.condition == c) & (m5.category == "short")].slowdown_mean.item()) for c in conds}}
    st = pd.read_csv(A / "EXP5_starvation_summary.csv")
    sm = st[st.mix == "mixed"].set_index("condition")
    out["exp5"]["n_over"] = {c: r(sm.loc[c, "n_over_mean"]) for c in conds}
    out["exp5"]["n_over_medium_heur"] = r(sm.loc["SJF-heuristic", "n_over_medium_mean"])
    # worst-case ratio range across mixes (per-seed max wait, any category) vs FCFS
    ratios = []
    for mix in mixes:
        sub = e5[e5.mix == mix]
        f = sub[sub.condition == "FCFS"].wait_max_mean.max()
        for c in ["SJF-heuristic", "SJF-oracle"]:
            ratios.append(sub[sub.condition == c].wait_max_mean.max() / f)
    out["exp5"]["max_ratio_range"] = [r(min(ratios)), r(max(ratios))]
    tail = pd.read_csv(A / "EXP5_tail_composition.csv")
    th = tail[tail.condition == "SJF-heuristic"]
    out["exp5"]["tail_pred_ge1024"] = r(th.tail_share_pred_ge_1024.mean() * 100, 0)
    out["exp5"]["all_pred_ge1024"] = r(th.all_share_pred_ge_1024.mean() * 100, 1)

    # EXP6
    e6 = pd.read_csv(A / "EXP6_paired.csv")
    e6 = e6[(e6.metric == "jct_mean") & (e6.condition == "SJF-heuristic")]
    rt = pd.read_csv(A / "EXP6_runtime.csv")
    out["exp6"] = {"reduction_range": [r(e6.rel_mean.min()), r(e6.rel_mean.max())],
                   "sd_small": r(e6.sort_values("n_requests_cfg").rel_sd.iloc[0]),
                   "sd_large": r(e6.sort_values("n_requests_cfg").rel_sd.iloc[-1], 2),
                   "sched_us": r(rt[rt.n_requests_cfg == 5000].sched_us_per_decision.mean(), 1),
                   "predict_us": r(rt[(rt.n_requests_cfg == 5000) & (rt.condition == "SJF-heuristic")].predict_us_per_request.item(), 1)}

    # EXP7
    e7 = pd.read_csv(A / "EXP7_tradeoff.csv")
    m7 = e7[e7.mix == "mixed"].sort_values("aging_rate")
    show = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0, 100.0, float("inf")]
    m7 = m7[m7.aging_rate.isin(show)]
    out["exp7"] = {"labels": ["SJF (a=0)" if a == 0 else ("FCFS" if a == float("inf") else f"a={a:g}") for a in m7.aging_rate],
                   "gain": [r(v) for v in m7.impr_jct_mean], "max_wait": [r(v, 0) for v in m7.wait_max],
                   "jct_mean": [r(v) for v in m7.jct_mean]}

    # Demo run (latest DEMO_* directory written by experiments/scripts/demo.py)
    demos = sorted((ROOT / "experiments" / "results").glob("DEMO_*"))
    if demos:
        d = pd.read_csv(demos[-1] / "summary.csv").set_index("condition")
        out["demo"] = {"run": demos[-1].name, "n": int(d.loc["FCFS", "n_requests"]),
                       "fcfs_jct": r(d.loc["FCFS", "jct_mean"]), "sjf_jct": r(d.loc["SJF-heuristic", "jct_mean"]),
                       "reduction": r((d.loc["FCFS", "jct_mean"] - d.loc["SJF-heuristic", "jct_mean"]) / d.loc["FCFS", "jct_mean"] * 100)}

    (ROOT / "presentation" / "deck_data.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1)[:3000])


if __name__ == "__main__":
    main()
