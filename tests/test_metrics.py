import math

import pytest

from llm_scheduler.metrics import (
    jain_index,
    mean_ci,
    percentile,
    prediction_error,
    relative_increase,
    relative_reduction,
    summarize,
    summarize_by_category,
)
from llm_scheduler.policies import FCFSPolicy, PredictiveSJFPolicy
from llm_scheduler.predictor import OraclePredictor
from llm_scheduler.simulator import Simulator


def test_hand_example_metrics(unit_service, hand_workload, hand_truth):
    sim = Simulator(unit_service)
    fcfs = summarize(sim.run(hand_workload, FCFSPolicy()))
    sjf = summarize(sim.run(hand_workload, PredictiveSJFPolicy(), OraclePredictor(hand_truth)))

    assert fcfs["jct_mean"] == pytest.approx(27 / 4)
    assert fcfs["wait_mean"] == pytest.approx(16 / 4)
    assert fcfs["ttft_mean"] == pytest.approx(20 / 4)
    assert fcfs["jct_median"] == pytest.approx(7.0)
    assert sjf["jct_mean"] == pytest.approx(24 / 4)
    assert sjf["wait_mean"] == pytest.approx(13 / 4)
    assert sjf["ttft_mean"] == pytest.approx(17 / 4)
    assert sjf["jct_max"] == 10

    for s in (fcfs, sjf):  # same work, same makespan
        assert s["window_s"] == 11
        assert s["throughput_rps"] == pytest.approx(4 / 11)
        assert s["throughput_tps"] == pytest.approx(11 / 11)
        assert s["utilization"] == pytest.approx(1.0)
        assert s["n_completed"] == 4 and s["n_incomplete"] == 0
        assert math.isnan(s["jct_p95"])  # too few observations
    assert sjf["pred_mae"] == 0 and sjf["pred_spearman"] == pytest.approx(1.0)
    assert math.isnan(fcfs["pred_mae"])
    # Relative reduction formula from the methodology.
    assert relative_reduction(fcfs["jct_mean"], sjf["jct_mean"]) == pytest.approx((6.75 - 6.0) / 6.75 * 100)


def test_percentile_minimum_sample_rule():
    assert math.isnan(percentile(list(range(199)), 95))
    assert percentile(list(range(200)), 95) == pytest.approx(189.05)
    assert math.isnan(percentile(list(range(999)), 99))
    assert not math.isnan(percentile(list(range(1000)), 99))
    assert math.isnan(percentile([], 50))


def test_relative_formulas():
    assert relative_reduction(10.0, 7.5) == pytest.approx(25.0)
    assert relative_increase(10.0, 12.0) == pytest.approx(20.0)
    assert math.isnan(relative_reduction(0.0, 1.0))


def test_mean_ci():
    m, lo, hi = mean_ci([1.0, 2.0, 3.0, 4.0, 5.0])
    assert m == 3.0
    # t_{0.975,4} = 2.7764; s = 1.5811; half = 2.7764 * 1.5811 / sqrt(5) = 1.9632
    assert hi - m == pytest.approx(1.9632, abs=1e-3)
    assert m - lo == pytest.approx(hi - m)
    assert math.isnan(mean_ci([2.0])[1])


def test_prediction_error_values():
    class R:
        def __init__(self, p, a):
            self.predicted_output_tokens, self.actual_output_tokens = p, a

    e = prediction_error([R(10, 20), R(30, 20), R(20, 40)])
    assert e["pred_mae"] == pytest.approx((10 + 10 + 20) / 3)
    assert e["pred_bias"] == pytest.approx((-10 + 10 - 20) / 3)
    assert e["pred_mdape"] == pytest.approx(50.0)


def test_by_category_counts(unit_service, hand_workload):
    rows = summarize_by_category(Simulator(unit_service).run(hand_workload, FCFSPolicy()))
    by_cat = {r["category"]: r for r in rows}
    assert by_cat["short"]["n_requests"] == 4  # all outputs <= 128 tokens
    assert by_cat["short"]["completion_rate"] == 1.0
    assert by_cat["long"]["n_requests"] == 0 and math.isnan(by_cat["long"]["jct_mean"])


def test_jain_index():
    assert jain_index([1, 1, 1]) == pytest.approx(1.0)
    assert jain_index([1, 0, 0]) == pytest.approx(1 / 3)
