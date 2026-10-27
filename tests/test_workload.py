import numpy as np
import pytest

from llm_scheduler.service_model import ServiceModel
from llm_scheduler.workload import (
    WORKLOAD_MIXES,
    generate_workload,
    length_category,
)


def test_generation_is_deterministic():
    sm = ServiceModel()
    a = generate_workload("mixed", 300, 0.8, seed=1, service_model=sm)
    b = generate_workload("mixed", 300, 0.8, seed=1, service_model=sm)
    c = generate_workload("mixed", 300, 0.8, seed=2, service_model=sm)
    assert a.specs == b.specs
    assert a.specs != c.specs


def test_sizes_identical_across_loads_only_arrivals_rescale():
    sm = ServiceModel()
    lo = generate_workload("mixed", 300, 0.5, seed=1, service_model=sm)
    hi = generate_workload("mixed", 300, 0.9, seed=1, service_model=sm)
    assert [s.features for s in lo.specs] == [s.features for s in hi.specs]
    assert [s.actual_output_tokens for s in lo.specs] == [s.actual_output_tokens for s in hi.specs]
    ratio = np.array([h.arrival_time / l.arrival_time for l, h in zip(lo.specs, hi.specs)])
    assert np.allclose(ratio, 0.5 / 0.9)


def test_arrival_rate_calibrated_to_target_load():
    sm = ServiceModel()
    wl = generate_workload("long_heavy", 2000, 0.75, seed=4, service_model=sm)
    assert wl.arrival_rate * wl.describe(sm)["mean_service_s"] == pytest.approx(0.75)


@pytest.mark.parametrize("mix", list(WORKLOAD_MIXES))
def test_mix_properties(mix):
    sm = ServiceModel()
    wl = generate_workload(mix, 3000, 0.8, seed=0, service_model=sm)
    arrivals = [s.arrival_time for s in wl.specs]
    assert arrivals == sorted(arrivals)
    assert [s.request_id for s in wl.specs] == list(range(3000))
    for s in wl.specs:
        assert 1 <= s.actual_output_tokens <= s.features.max_tokens


def test_mix_ordering_by_mean_length():
    sm = ServiceModel()
    means = {m: generate_workload(m, 4000, 0.8, seed=0, service_model=sm).describe(sm)["mean_output_tokens"] for m in WORKLOAD_MIXES}
    assert means["short_heavy"] < means["mixed"] < means["long_heavy"]


def test_length_category_thresholds():
    assert [length_category(n) for n in (1, 128, 129, 512, 513)] == ["short", "short", "medium", "medium", "long"]


def test_bad_arguments():
    sm = ServiceModel()
    with pytest.raises(KeyError):
        generate_workload("nope", 10, 0.5, 0, sm)
    with pytest.raises(ValueError):
        generate_workload("mixed", 0, 0.5, 0, sm)
    with pytest.raises(ValueError):
        generate_workload("mixed", 10, 0.0, 0, sm)
