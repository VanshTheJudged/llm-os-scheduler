"""Static figures (PNG) for the report and slides.

Styling follows one fixed scheme so every figure reads the same way:

* each policy keeps one colour in every figure: FCFS blue, SJF-heuristic orange,
  SJF-oracle (reference) aqua; other conditions use neutral ink with direct labels;
* 2 px lines, markers with a ring in the surface colour, hairline y-grid, no top/right
  spines, one y-axis per panel (two measures -> two panels, never a second y-scale);
* titles state what is plotted; axis labels carry units; every figure states that the
  data are simulated.

The three hues were checked with the dataviz palette validator (all-pairs CVD separation
passes; aqua is below 3:1 contrast on the light surface, so figures carry direct labels
and the report gives the numbers in tables).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

POLICY_COLORS: dict[str, str] = {
    "FCFS": "#2a78d6",
    "SJF-heuristic": "#eb6834",
    "SJF-oracle": "#1baf7a",
}
NEUTRAL = INK_2
SIM_NOTE = "Simulated single-slot M/G/1 model; not GPU measurements."


def color_for(label: str) -> str:
    return POLICY_COLORS.get(label, NEUTRAL)


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlecolor": INK,
            "axes.labelcolor": INK_2,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "lines.linewidth": 2.0,
            "lines.solid_capstyle": "round",
            "lines.solid_joinstyle": "round",
            "legend.frameon": False,
            "legend.labelcolor": INK_2,
        }
    )


def _finish(fig: plt.Figure, path: Path, note: str = SIM_NOTE) -> Path:
    fig.text(0.01, 0.005, note, fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _marker_kw(color: str) -> dict:
    return {"marker": "o", "markersize": 6, "markerfacecolor": color, "markeredgecolor": SURFACE, "markeredgewidth": 1.5}


def _end_label(ax: plt.Axes, x: float, y: float, text: str, dy: float = 0.0) -> None:
    ax.annotate(text, (x, y), xytext=(6, dy), textcoords="offset points", va="center", fontsize=9, color=INK_2)


def line_with_ci(
    agg: pd.DataFrame,
    x: str,
    y: str,
    lo: str,
    hi: str,
    series: str,
    order: Sequence[str],
    title: str,
    xlabel: str,
    ylabel: str,
    path: Path,
    logx: bool = False,
    label_offsets: Mapping[str, float] | None = None,
    hline: float | None = None,
    ylim: tuple[float, float] | None = None,
) -> Path:
    """One line per series with a 95 % CI band; end-of-line direct labels plus a legend."""
    apply_style()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    offsets = dict(label_offsets or {})
    for label in order:
        d = agg[agg[series] == label].sort_values(x)
        if d.empty:
            continue
        c = color_for(label)
        ax.fill_between(d[x], d[lo], d[hi], color=c, alpha=0.12, linewidth=0)
        ax.plot(d[x], d[y], color=c, label=label, **_marker_kw(c))
        _end_label(ax, d[x].iloc[-1], d[y].iloc[-1], label, offsets.get(label, 0.0))
    if hline is not None:
        ax.axhline(hline, color=AXIS, linewidth=1.0, zorder=1)
    if logx:
        ax.set_xscale("log")
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.margins(x=0.12)
    ax.legend(loc="upper left")
    return _finish(fig, path)


def grouped_bars(
    data: pd.DataFrame,
    group: str,
    series: str,
    value: str,
    err_lo: str | None,
    err_hi: str | None,
    group_order: Sequence[str],
    series_order: Sequence[str],
    title: str,
    ylabel: str,
    path: Path,
    value_fmt: str = "{:.1f}",
    ax: plt.Axes | None = None,
) -> Path | None:
    """Grouped bar chart with value labels at bar tips and optional CI whiskers."""
    own = ax is None
    if own:
        apply_style()
        fig, ax = plt.subplots(figsize=(7.0, 4.2))
    n = len(series_order)
    width = min(0.8 / n, 0.26)
    xs = np.arange(len(group_order))
    tops = []
    for i, s in enumerate(series_order):
        d = data[data[series] == s].set_index(group).reindex(group_order)
        pos = xs + (i - (n - 1) / 2) * width
        c = color_for(s)
        ax.bar(pos, d[value], width=width, color=c, edgecolor=SURFACE, linewidth=1.5, label=s, zorder=2)
        if err_lo and err_hi:
            yerr = np.vstack([d[value] - d[err_lo], d[err_hi] - d[value]])
            ax.errorbar(pos, d[value], yerr=yerr, fmt="none", ecolor=INK_2, elinewidth=1, capsize=2, zorder=3)
        for px, v, top in zip(pos, d[value], d[err_hi] if err_hi else d[value]):
            if pd.notna(v):
                tops.append(top)
                ax.annotate(value_fmt.format(v), (px, top), xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_xticks(xs, group_order)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)
    if tops and max(tops) > 0:
        ax.set_ylim(top=max(tops) * 1.28)  # headroom so the one-row legend never covers a bar
    ax.legend(loc="upper left", ncol=n, handlelength=1.0, columnspacing=1.0, fontsize=8)
    if own:
        return _finish(fig, path)
    return None


def small_multiple_bars(
    data: pd.DataFrame,
    facet: str,
    facet_order: Sequence[str],
    group: str,
    group_order: Sequence[str],
    series: str,
    series_order: Sequence[str],
    value: str,
    title: str,
    ylabel: str,
    path: Path,
    value_fmt: str = "{:.0f}",
    sharey: bool = False,
    log: bool = False,
) -> Path:
    apply_style()
    fig, axes = plt.subplots(1, len(facet_order), figsize=(4.0 * len(facet_order), 4.0), sharey=sharey)
    for ax, f in zip(np.atleast_1d(axes), facet_order):
        grouped_bars(data[data[facet] == f], group, series, value, None, None, group_order, series_order,
                     f, ylabel if f == facet_order[0] else "", path, value_fmt, ax=ax)
        if log:
            vals = data[data[facet] == f][value]
            ax.set_yscale("log")
            ax.set_ylim(vals[vals > 0].min() * 0.6, vals.max() * 6)  # headroom on a log axis for the legend row
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
            ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        if f != facet_order[0]:
            ax.get_legend().remove()
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    return _finish(fig, path)


def ecdf_small_multiples(
    requests: pd.DataFrame,
    facet: str,
    facet_order: Sequence[str],
    series: str,
    series_order: Sequence[str],
    value: str,
    title: str,
    xlabel: str,
    path: Path,
) -> Path:
    """Empirical CDF of ``value`` per series, one panel per facet, log x-axis."""
    apply_style()
    fig, axes = plt.subplots(1, len(facet_order), figsize=(4.0 * len(facet_order), 3.8), sharey=True)
    for ax, f in zip(np.atleast_1d(axes), facet_order):
        sub = requests[requests[facet] == f]
        for s in series_order:
            v = np.sort(sub.loc[sub[series] == s, value].to_numpy(dtype=float))
            if len(v) == 0:
                continue
            v = np.maximum(v, 1e-2)  # zero waits plotted at 0.01 s on the log axis
            ax.plot(v, np.arange(1, len(v) + 1) / len(v), color=color_for(s), label=s)
        ax.set_xscale("log")
        ax.set_title(f"{f} requests")
        ax.set_xlabel(xlabel)
        ax.grid(axis="x", visible=True)
    np.atleast_1d(axes)[0].set_ylabel("fraction of requests")
    np.atleast_1d(axes)[0].legend(loc="upper left")
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    return _finish(fig, path, SIM_NOTE + " Waits of 0 s are drawn at 0.01 s.")


def tradeoff_curve(
    panels: Iterable[tuple[str, pd.DataFrame]],
    x: str,
    y: str,
    label_col: str,
    endpoints: Mapping[str, str],
    title: str,
    xlabel: str,
    ylabel: str,
    path: Path,
    label_points: Iterable[str] | None = None,
    label_offsets: Mapping[str, tuple[float, float]] | None = None,
    note: str = "",
) -> Path:
    """Connected scatter: one point per configuration, endpoints coloured by policy.

    Only endpoints and ``label_points`` get a text label, so coincident points never stack labels.
    """
    apply_style()
    panels = list(panels)
    keep = set(label_points or []) | set(endpoints)
    offsets = dict(label_offsets or {})
    fig, axes = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 4.3))
    for ax, (name, d) in zip(np.atleast_1d(axes), panels):
        d = d.sort_values(x)
        ax.plot(d[x], d[y], color=NEUTRAL, linewidth=1.5, zorder=1)
        for _, row in d.iterrows():
            lab = row[label_col]
            c = color_for(endpoints.get(lab, lab))
            ax.plot([row[x]], [row[y]], **_marker_kw(c), zorder=4 if lab in endpoints else 3)
            if lab in keep:
                dx, dy = offsets.get(lab, (6, 4))
                ax.annotate(endpoints.get(lab, lab), (row[x], row[y]), xytext=(dx, dy), textcoords="offset points",
                            fontsize=8, color=INK_2, ha="right" if dx < 0 else "left")
        ax.set_title(name)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(axis="x", visible=True)
        ax.margins(0.12)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    return _finish(fig, path, (note + " " if note else "") + SIM_NOTE)


def parity_plot(df: pd.DataFrame, x: str, y: str, series: str, series_order: Sequence[str], title: str,
                xlabel: str, ylabel: str, path: Path) -> Path:
    """Simulated vs analytical values with the y = x reference line (log-log)."""
    apply_style()
    fig, ax = plt.subplots(figsize=(5.6, 5.0))
    lo = min(df[x].min(), df[y].min()) * 0.8
    hi = max(df[x].max(), df[y].max()) * 1.25
    ax.plot([lo, hi], [lo, hi], color=AXIS, linewidth=1.0, zorder=1)
    for s in series_order:
        d = df[df[series] == s]
        c = color_for(s)
        ax.plot(d[x], d[y], linestyle="none", label=s, **_marker_kw(c), alpha=0.9)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=True)
    ax.legend(loc="upper left")
    return _finish(fig, path, "Points on the grey line agree exactly. " + SIM_NOTE)


def scatter_labeled(df: pd.DataFrame, x: str, y: str, label: str, curve_mask: pd.Series, title: str, xlabel: str,
                    ylabel: str, path: Path, hlines: Mapping[str, float], label_offsets: Mapping[str, tuple] | None = None,
                    facet: str | None = None, facet_order: Sequence | None = None,
                    skip_labels: Iterable[str] = ()) -> Path:
    """Predictor-quality chart: noise-sweep points joined as a curve, others labelled points.

    Labels in ``skip_labels`` are not drawn (their points are), to avoid collisions on dense curves.
    """
    apply_style()
    facets = list(facet_order) if facet else [None]
    fig, axes = plt.subplots(1, len(facets), figsize=(5.6 * len(facets), 4.4), sharey=True)
    offsets = dict(label_offsets or {})
    skip = set(skip_labels)
    for ax, f in zip(np.atleast_1d(axes), facets):
        d = df if f is None else df[df[facet] == f]
        m = curve_mask.loc[d.index]
        curve = d[m].sort_values(x)
        ax.plot(curve[x], curve[y], color=color_for("SJF-oracle"), linewidth=1.5, zorder=1,
                label="SJF + oracle with synthetic noise (reference)")
        for idx, row in d.iterrows():
            is_curve = bool(m.loc[idx])
            c = color_for(row[label]) if row[label] in POLICY_COLORS else (color_for("SJF-oracle") if is_curve else NEUTRAL)
            ax.plot([row[x]], [row[y]], **_marker_kw(c), zorder=4 if row[label] in POLICY_COLORS else 3)
            if row[label] in skip:
                continue
            dx, dy = offsets.get(row[label], (6, 4))
            ax.annotate(row[label].replace("SJF-", ""), (row[x], row[y]), xytext=(dx, dy), textcoords="offset points",
                        fontsize=8, color=INK_2, ha="right" if dx < 0 else "left")
        for name, val in hlines.items():
            ax.axhline(val, color=color_for(name), linewidth=1.0, zorder=0)
            ax.annotate(name, (1.0, val), xycoords=("axes fraction", "data"), xytext=(-4, 4), textcoords="offset points",
                        fontsize=8, color=INK_2, ha="right")
        ax.set_title(title if f is None else f"load {f}")
        ax.set_xlabel(xlabel)
        ax.grid(axis="x", visible=True)
        ax.legend(loc="lower left", fontsize=8)
    np.atleast_1d(axes)[0].set_ylabel(ylabel)
    if facet:
        fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    return _finish(fig, path, "Unlabelled aqua points: sigma = 0.1, 0.25, 0.75. " + SIM_NOTE)
