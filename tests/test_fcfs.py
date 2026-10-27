import pytest

from llm_scheduler.policies import FCFSPolicy
from llm_scheduler.service_model import ServiceModel
from llm_scheduler.simulator import Simulator
from llm_scheduler.workload import generate_workload, workload_from_rows


def by_id(result):
    return {r.request_id: r for r in result.requests}


def test_fcfs_hand_example(unit_service, hand_workload):
    res = Simulator(unit_service).run(hand_workload, FCFSPolicy())
    r = by_id(res)
    assert [r[i].start_time for i in range(4)] == [0, 5, 8, 9]
    assert [r[i].completion_time for i in range(4)] == [5, 8, 9, 11]
    assert [r[i].jct for i in range(4)] == [5, 7, 7, 8]
    assert [r[i].waiting_time for i in range(4)] == [0, 4, 6, 6]
    assert [r[i].ttft for i in range(4)] == [1, 5, 7, 7]


def test_fcfs_preserves_arrival_order():
    sm = ServiceModel()
    wl = generate_workload("mixed", 800, 0.9, seed=11, service_model=sm)
    res = Simulator(sm).run(wl, FCFSPolicy())
    started = sorted(res.requests, key=lambda r: r.start_time)
    arrivals = [r.arrival_time for r in started]
    assert arrivals == sorted(arrivals)


def test_fcfs_matches_lindley_recursion():
    # Independent FCFS implementation: W[i] = max(0, W[i-1] + S[i-1] - (a[i] - a[i-1])).
    sm = ServiceModel()
    wl = generate_workload("long_heavy", 3000, 0.9, seed=13, service_model=sm)
    a = [s.arrival_time for s in wl.specs]
    s = [sm.service_time(x.features.prompt_tokens, x.actual_output_tokens) for x in wl.specs]
    w = [0.0]
    for i in range(1, len(a)):
        w.append(max(0.0, w[-1] + s[i - 1] - (a[i] - a[i - 1])))
    res = Simulator(sm).run(wl, FCFSPolicy())
    assert [r.waiting_time for r in res.requests] == pytest.approx(w, abs=1e-6)


def test_fcfs_tie_break_by_request_id(unit_service):
    rows = [{"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": n} for n in (4, 1, 3)]
    res = Simulator(unit_service).run(workload_from_rows(rows), FCFSPolicy())
    order = [r.request_id for r in sorted(res.requests, key=lambda r: r.start_time)]
    assert order == [0, 1, 2]


def test_fcfs_does_not_need_predictor(unit_service, hand_workload):
    res = Simulator(unit_service).run(hand_workload, FCFSPolicy(), predictor=None)
    assert all(r.predicted_output_tokens is None for r in res.requests)
    assert res.predictor == "none"


def test_policy_queue_basics():
    p = FCFSPolicy()
    assert len(p) == 0 and p.select_next(0.0) is None
    assert p.preemptive is False


def test_simulator_rejects_reused_policy(unit_service, hand_workload):
    from llm_scheduler.request import Request

    p = FCFSPolicy()
    req = Request(hand_workload.specs[0])
    p.admit(req, 0.0)
    with pytest.raises(ValueError):
        Simulator(unit_service).run(hand_workload, p)
