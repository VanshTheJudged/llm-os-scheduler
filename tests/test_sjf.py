import pytest

from llm_scheduler.policies import AgingSJFPolicy, FCFSPolicy, PredictiveSJFPolicy
from llm_scheduler.predictor import OraclePredictor, build_predictor
from llm_scheduler.request import PromptFeatures
from llm_scheduler.service_model import ServiceModel
from llm_scheduler.simulator import Simulator
from llm_scheduler.workload import generate_workload, workload_from_rows


class ConstantMapPredictor:
    """Test predictor returning fixed values by request id."""

    name = "fixed"
    uses_ground_truth = False

    def __init__(self, values):
        self.values = values

    def predict(self, features: PromptFeatures) -> int:
        return self.values[features.request_id]


def by_id(result):
    return {r.request_id: r for r in result.requests}


def test_sjf_hand_example_oracle(unit_service, hand_workload, hand_truth):
    res = Simulator(unit_service).run(hand_workload, PredictiveSJFPolicy(), OraclePredictor(hand_truth))
    r = by_id(res)
    # R0 runs alone; at t=5 the waiting set is {R1:3, R2:1, R3:2} -> R2, R3, R1.
    assert [r[i].start_time for i in range(4)] == [0, 8, 5, 6]
    assert [r[i].jct for i in range(4)] == [5, 10, 4, 5]
    assert [r[i].waiting_time for i in range(4)] == [0, 7, 3, 3]
    assert [r[i].ttft for i in range(4)] == [1, 8, 4, 4]


def test_sjf_picks_shortest_predicted_among_waiting():
    sm = ServiceModel()
    wl = generate_workload("mixed", 1500, 0.95, seed=5, service_model=sm)
    sim = Simulator(sm, record_trace=True)
    res = sim.run(wl, PredictiveSJFPolicy(), build_predictor({"type": "heuristic"}, {}, 5))
    reqs = by_id(res)
    for t, event, rid in res.trace:
        if event != "dispatch":
            continue
        waiting = [
            q for q in res.requests if q.arrival_time <= t and q.start_time is not None and q.start_time >= t
        ]
        chosen = reqs[rid]
        assert chosen.predicted_output_tokens == min(q.predicted_output_tokens for q in waiting)


def test_sjf_is_non_preemptive(unit_service):
    # A very short request arrives while a long one runs: it must wait.
    rows = [
        {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 10},
        {"arrival_time": 1.0, "prompt_tokens": 1, "output_tokens": 1},
    ]
    wl = workload_from_rows(rows)
    truth = {s.request_id: s.actual_output_tokens for s in wl.specs}
    r = by_id(Simulator(unit_service).run(wl, PredictiveSJFPolicy(), OraclePredictor(truth)))
    assert r[0].completion_time == 10
    assert r[1].start_time == 10


def test_sjf_tie_break_earlier_arrival_first(unit_service):
    rows = [
        {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 4},
        {"arrival_time": 1.0, "prompt_tokens": 1, "output_tokens": 2},
        {"arrival_time": 2.0, "prompt_tokens": 1, "output_tokens": 2},
    ]
    wl = workload_from_rows(rows)
    pred = ConstantMapPredictor({0: 4, 1: 2, 2: 2})
    r = by_id(Simulator(unit_service).run(wl, PredictiveSJFPolicy(), pred))
    assert r[1].start_time < r[2].start_time


def test_service_uses_actual_not_predicted(unit_service, hand_workload):
    wildly_wrong = ConstantMapPredictor({0: 1000, 1: 1, 2: 999, 3: 7})
    res = Simulator(unit_service).run(hand_workload, PredictiveSJFPolicy(), wildly_wrong)
    for r in res.requests:
        assert r.service_time == r.actual_output_tokens  # unit model: service = n seconds
        assert r.generated_tokens == r.actual_output_tokens


def test_sjf_requires_predictor(unit_service, hand_workload):
    with pytest.raises(ValueError):
        Simulator(unit_service).run(hand_workload, PredictiveSJFPolicy(), None)


def test_aging_zero_equals_sjf_and_large_equals_fcfs():
    sm = ServiceModel()
    wl = generate_workload("mixed", 1000, 0.9, seed=8, service_model=sm)
    pred = {"type": "heuristic"}
    sim = Simulator(sm)

    def starts(policy):
        res = sim.run(wl, policy, build_predictor(pred, {}, 8) if policy.requires_prediction else None)
        return [r.start_time for r in res.requests]

    assert starts(AgingSJFPolicy(0.0)) == starts(PredictiveSJFPolicy())
    assert starts(AgingSJFPolicy(1e12)) == starts(FCFSPolicy())


def test_aging_rejects_negative_rate():
    with pytest.raises(ValueError):
        AgingSJFPolicy(-1.0)
