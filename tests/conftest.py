"""Shared fixtures: the hand-calculated example used throughout the docs.

Service model: prefill = 1 s, decode = 1 s/token, so a request with n output tokens has
service time exactly n seconds and its first token 1 s after it starts.

| id | arrival | output tokens |
|----|---------|---------------|
| 0  | 0       | 5             |
| 1  | 1       | 3             |
| 2  | 2       | 1             |
| 3  | 3       | 2             |
"""

import pytest

from llm_scheduler.service_model import ServiceModel
from llm_scheduler.workload import workload_from_rows

HAND_ROWS = [
    {"arrival_time": 0.0, "prompt_tokens": 1, "output_tokens": 5},
    {"arrival_time": 1.0, "prompt_tokens": 1, "output_tokens": 3},
    {"arrival_time": 2.0, "prompt_tokens": 1, "output_tokens": 1},
    {"arrival_time": 3.0, "prompt_tokens": 1, "output_tokens": 2},
]


@pytest.fixture
def unit_service() -> ServiceModel:
    return ServiceModel(prefill_base_s=1.0, prefill_per_token_s=0.0, decode_per_token_s=1.0)


@pytest.fixture
def hand_workload():
    return workload_from_rows(HAND_ROWS)


@pytest.fixture
def hand_truth(hand_workload):
    return {s.request_id: s.actual_output_tokens for s in hand_workload.specs}
