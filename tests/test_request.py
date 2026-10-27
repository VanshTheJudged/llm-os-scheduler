import pytest

from llm_scheduler.request import InvalidTransition, PromptFeatures, Request, RequestSpec, RequestState


def make_spec(arrival=1.0, out=4, rid=0):
    return RequestSpec(PromptFeatures(rid, 10, "chat", False, 4096), arrival, out)


def test_valid_lifecycle_and_derived_timings():
    r = Request(make_spec(arrival=1.0, out=4))
    assert r.state is RequestState.PENDING and r.jct is None
    r.mark_arrived(1.0)
    r.mark_started(3.0)
    r.mark_first_token(3.5)
    r.mark_completed(6.0)
    assert r.state is RequestState.COMPLETED
    assert r.waiting_time == 2.0
    assert r.ttft == 2.5
    assert r.jct == 5.0  # completion - arrival, not the absolute completion time
    assert r.service_time == 3.0
    assert r.generated_tokens == 4
    assert r.preemption_count == 0


def test_cannot_complete_twice():
    r = Request(make_spec())
    r.mark_arrived(1.0)
    r.mark_started(1.0)
    r.mark_first_token(2.0)
    r.mark_completed(3.0)
    with pytest.raises(InvalidTransition):
        r.mark_completed(4.0)


def test_completed_request_cannot_be_started_again():
    r = Request(make_spec())
    r.mark_arrived(1.0)
    r.mark_started(1.0)
    r.mark_first_token(2.0)
    r.mark_completed(3.0)
    with pytest.raises(InvalidTransition):
        r.mark_started(5.0)


def test_cannot_start_before_arrival_or_without_arriving():
    r = Request(make_spec(arrival=5.0))
    with pytest.raises(InvalidTransition):
        r.mark_started(6.0)  # never arrived
    with pytest.raises(InvalidTransition):
        r.mark_arrived(4.0)  # earlier than its arrival time


def test_cannot_complete_before_first_token():
    r = Request(make_spec())
    r.mark_arrived(1.0)
    r.mark_started(1.0)
    with pytest.raises(InvalidTransition):
        r.mark_completed(2.0)


@pytest.mark.parametrize("arrival,out", [(-1.0, 3), (0.0, 0)])
def test_spec_validation(arrival, out):
    with pytest.raises(ValueError):
        make_spec(arrival=arrival, out=out)


def test_features_do_not_contain_actual_length():
    fields = set(PromptFeatures.__dataclass_fields__)
    assert "actual_output_tokens" not in fields
    assert "output_tokens" not in fields
