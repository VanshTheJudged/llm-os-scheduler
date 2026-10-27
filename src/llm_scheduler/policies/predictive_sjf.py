"""Non-preemptive predictive Shortest-Job-First, and its aging variant."""

from __future__ import annotations

from typing import Any

from ..request import Request
from .base import StaticPriorityPolicy


class PredictiveSJFPolicy(StaticPriorityPolicy):
    """Non-preemptive SJF on *predicted* output length.

    When the slot is free, the waiting request with the smallest
    ``predicted_output_tokens`` is started and runs to completion; a shorter request that
    arrives later does not interrupt it. Ties: earlier arrival first, then lower
    ``request_id``.
    """

    name = "sjf"
    requires_prediction = True

    def priority_key(self, request: Request) -> tuple:
        return (request.predicted_output_tokens, request.arrival_time)


class AgingSJFPolicy(StaticPriorityPolicy):
    """EXTENSION (Experiment 7): predictive SJF with linear aging.

    Effective priority of a waiting request at time ``t`` is
    ``predicted_output_tokens - aging_rate * (t - arrival_time)``; the smallest runs next.
    Because the ``aging_rate * t`` term is common to every waiting request, the ordering at
    any ``t`` equals the ordering by the static key
    ``predicted_output_tokens + aging_rate * arrival_time``. The policy is therefore exact
    with a heap.

    ``aging_rate`` is in tokens per second of waiting. ``aging_rate = 0`` is plain SJF; as
    ``aging_rate`` grows, the order approaches FCFS. Non-preemptive.
    """

    name = "sjf_aging"
    requires_prediction = True

    def __init__(self, aging_rate: float) -> None:
        super().__init__()
        if aging_rate < 0:
            raise ValueError("aging_rate must be non-negative")
        self.aging_rate = aging_rate

    def priority_key(self, request: Request) -> tuple:
        return (request.predicted_output_tokens + self.aging_rate * request.arrival_time, request.arrival_time)

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "aging_rate": self.aging_rate}
