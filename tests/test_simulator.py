import numpy as np
import pytest

from llm_scheduler.analytical import nonpreemptive_priority_mean_wait, pk_mean_wait
from llm_scheduler.metrics import request_records, summarize
from llm_scheduler.policies import FCFSPolicy, PredictiveSJFPolicy
from llm_scheduler.predictor import OraclePredictor, build_predictor
from llm_scheduler.request import RequestState
from llm_scheduler.service_model import ServiceModel
from llm_scheduler.simulator import Simulator
from llm_scheduler.workload import generate_workload, workload_from_rows


def test_single_request_timing():
    sm = ServiceModel(prefill_base_s=0.5, prefill_per_token_s=0.01, decode_per_token_s=0.1)
    wl = workload_from_rows([{"arrival_time": 2.0, "prompt_tokens": 50, "output_tokens": 11}])
    (r,) = Simulator(sm).run(wl, FCFSPolicy()).requests
    assert r.start_time == 2.0
    assert r.first_token_time == pytest.approx(2.0 + 0.5 + 0.5)
    assert r.completion_time == pytest.approx(3.0 + 10 * 0.1)
    assert r.waiting_time == 0.0


def test_idle_gap_between_arrivals(unit_service):
    rows = [
        {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 2},
        {"arrival_time": 10.0, "prompt_tokens": 1, "output_tokens": 3},
    ]
    res = Simulator(unit_service).run(workload_from_rows(rows), FCFSPolicy())
    r1 = res.requests[1]
    assert r1.start_time == 10.0 and r1.waiting_time == 0.0
    assert summarize(res)["utilization"] == pytest.approx(5 / 13)


def test_arrival_at_completion_instant_is_visible_to_dispatch(unit_service):
    # R0 finishes at t=5 exactly when a 1-token request arrives; SJF must pick it at t=5.
    rows = [
        {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 5},
        {"arrival_time": 1.0, "prompt_tokens": 1, "output_tokens": 3},
        {"arrival_time": 5.0, "prompt_tokens": 1, "output_tokens": 1},
    ]
    wl = workload_from_rows(rows)
    truth = {s.request_id: s.actual_output_tokens for s in wl.specs}
    res = Simulator(unit_service).run(wl, PredictiveSJFPolicy(), OraclePredictor(truth))
    r = {q.request_id: q for q in res.requests}
    assert r[2].start_time == 5.0 and r[1].start_time == 6.0


def test_one_token_request_first_token_equals_completion(unit_service):
    wl = workload_from_rows([{"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 1}])
    (r,) = Simulator(unit_service).run(wl, FCFSPolicy()).requests
    assert r.first_token_time == r.completion_time == 1.0


@pytest.mark.parametrize("policy_name", ["fcfs", "sjf"])
def test_invariants_on_generated_workload(policy_name):
    sm = ServiceModel()
    wl = generate_workload("long_heavy", 2000, 0.9, seed=3, service_model=sm)
    policy = FCFSPolicy() if policy_name == "fcfs" else PredictiveSJFPolicy()
    pred = build_predictor({"type": "heuristic"}, {}, 3) if policy_name == "sjf" else None
    res = Simulator(sm).run(wl, policy, pred)
    reqs = sorted(res.requests, key=lambda r: r.start_time)
    for r in reqs:
        assert r.state is RequestState.COMPLETED
        assert r.start_time >= r.arrival_time
        assert r.first_token_time >= r.start_time
        assert r.jct == pytest.approx(r.waiting_time + r.service_time)
        assert r.service_time == pytest.approx(sm.service_time(r.prompt_tokens, r.actual_output_tokens))
    # Single slot: service intervals never overlap.
    for a, b in zip(reqs, reqs[1:]):
        assert b.start_time >= a.completion_time - 1e-9
    assert res.n_decisions == len(reqs)


def test_same_seed_gives_identical_results():
    sm = ServiceModel()
    runs = []
    for _ in range(2):
        wl = generate_workload("mixed", 1000, 0.85, seed=21, service_model=sm)
        res = Simulator(sm).run(wl, PredictiveSJFPolicy(), build_predictor({"type": "heuristic"}, {}, 21))
        runs.append(request_records(res))
    assert runs[0] == runs[1]


def test_workload_is_not_mutated_between_runs():
    sm = ServiceModel()
    wl = generate_workload("mixed", 500, 0.8, seed=2, service_model=sm)
    sim = Simulator(sm)
    first = request_records(sim.run(wl, FCFSPolicy()))
    sim.run(wl, PredictiveSJFPolicy(), build_predictor({"type": "heuristic"}, {}, 2))
    assert request_records(sim.run(wl, FCFSPolicy())) == first


def test_work_conservation_same_makespan():
    sm = ServiceModel()
    wl = generate_workload("mixed", 1500, 0.9, seed=4, service_model=sm)
    sim = Simulator(sm)
    a = summarize(sim.run(wl, FCFSPolicy()))
    b = summarize(sim.run(wl, PredictiveSJFPolicy(), build_predictor({"type": "heuristic"}, {}, 4)))
    assert a["window_s"] == pytest.approx(b["window_s"])
    assert a["throughput_tps"] == pytest.approx(b["throughput_tps"])


def test_horizon_records_unfinished_requests(unit_service):
    rows = [
        {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 5},
        {"arrival_time": 1.0, "prompt_tokens": 1, "output_tokens": 3},
        {"arrival_time": 2.0, "prompt_tokens": 1, "output_tokens": 1},
        {"arrival_time": 50.0, "prompt_tokens": 1, "output_tokens": 1},
    ]
    res = Simulator(unit_service).run(workload_from_rows(rows), FCFSPolicy(), horizon=6.5)
    states = {r.request_id: r.state for r in res.requests}
    assert states == {0: RequestState.COMPLETED, 1: RequestState.RUNNING, 2: RequestState.WAITING, 3: RequestState.PENDING}
    r1 = res.requests[1]
    assert r1.generated_tokens == 1  # started at 5, first token at 6.0, second due at 7.0
    s = summarize(res)
    assert s["n_completed"] == 1 and s["n_incomplete"] == 2 and s["n_not_arrived"] == 1
    assert s["window_s"] == 6.5
    assert s["utilization"] == pytest.approx(6.5 / 6.5)
    assert s["throughput_tps"] == pytest.approx((5 + 1) / 6.5)


def test_scale_invariance_of_time_metrics():
    sm = ServiceModel()
    wl1 = generate_workload("mixed", 800, 0.8, seed=6, service_model=sm)
    wl2 = generate_workload("mixed", 800, 0.8, seed=6, service_model=sm.scaled(3.0))
    s1 = summarize(Simulator(sm).run(wl1, FCFSPolicy()))
    s2 = summarize(Simulator(sm.scaled(3.0)).run(wl2, FCFSPolicy()))
    for key in ("jct_mean", "wait_mean", "ttft_mean", "jct_p95"):
        assert s2[key] == pytest.approx(3.0 * s1[key], rel=1e-9)
    assert s2["slowdown_mean"] == pytest.approx(s1["slowdown_mean"], rel=1e-9)


def _sim_vs_formula(policy_factory, formula, seeds):
    sm = ServiceModel()
    sim_waits, model_waits = [], []
    for seed in seeds:
        wl = generate_workload("mixed", 20000, 0.6, seed=seed, service_model=sm)
        truth = {s.request_id: s.actual_output_tokens for s in wl.specs}
        res = Simulator(sm).run(wl, *policy_factory(truth))
        svc = np.array([sm.service_time(s.features.prompt_tokens, s.actual_output_tokens) for s in wl.specs])
        keys = np.array([s.actual_output_tokens for s in wl.specs])
        sim_waits.append(summarize(res)["wait_mean"])
        model_waits.append(formula(svc, keys, wl.arrival_rate))
    return np.mean(sim_waits), np.mean(model_waits)


def test_fcfs_matches_pollaczek_khinchine():
    sim, model = _sim_vs_formula(lambda t: (FCFSPolicy(), None), lambda s, k, lam: pk_mean_wait(s, lam), [1, 2, 3])
    assert sim == pytest.approx(model, rel=0.10)


def test_oracle_sjf_matches_cobham():
    sim, model = _sim_vs_formula(
        lambda t: (PredictiveSJFPolicy(), OraclePredictor(t)), nonpreemptive_priority_mean_wait, [1, 2, 3]
    )
    assert sim == pytest.approx(model, rel=0.10)
