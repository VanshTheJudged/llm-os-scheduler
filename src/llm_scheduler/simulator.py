"""Discrete-event simulator of one non-preemptive LLM execution slot.

Events
------
``ARRIVAL``      request enters the system; the predictor is called (admission-time
                 prediction) and the request joins the policy's waiting queue.
``FIRST_TOKEN``  prefill finished and the first output token is emitted.
``COMPLETION``   the last output token is emitted; the slot becomes free.

A *scheduling decision* (dispatch) is made after **all** events that share a timestamp
have been processed, whenever the slot is free and the queue is non-empty. So a request
that arrives at exactly the moment another completes is visible to that decision.

Ordering of events with equal timestamps: ``FIRST_TOKEN`` < ``COMPLETION`` < ``ARRIVAL``,
then insertion order. Arrivals are inserted in ``(arrival_time, request_id)`` order.
This makes every run fully deterministic.

Service progress uses the request's **actual** output length; the prediction is used only
by the policy to order the queue.
"""

from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field
from enum import IntEnum

from .policies.base import SchedulingPolicy
from .predictor import LengthPredictor
from .request import Request, RequestState
from .service_model import ServiceModel
from .workload import Workload


class EventType(IntEnum):
    FIRST_TOKEN = 0
    COMPLETION = 1
    ARRIVAL = 2


@dataclass
class SimulationResult:
    """Everything a run produced. Times are simulated seconds unless noted."""

    requests: list[Request]
    policy: str
    predictor: str
    predictor_uses_ground_truth: bool
    first_arrival: float
    end_time: float
    horizon: float | None
    busy_time: float
    n_decisions: int
    # Wall-clock measurements of this Python implementation (real seconds, not simulated).
    wall_time_s: float
    scheduler_wall_s: float
    predictor_wall_s: float
    trace: list[tuple[float, str, int]] | None = field(default=None, repr=False)


class Simulator:
    """Replays a workload under a policy on a single execution slot."""

    def __init__(self, service_model: ServiceModel, record_trace: bool = False) -> None:
        self.service_model = service_model
        self.record_trace = record_trace

    def run(
        self,
        workload: Workload,
        policy: SchedulingPolicy,
        predictor: LengthPredictor | None = None,
        horizon: float | None = None,
    ) -> SimulationResult:
        """Simulate ``workload`` under ``policy``.

        Args:
            workload: Requests to replay. Not modified.
            policy: A *fresh* policy instance (its queue must be empty).
            predictor: Called once per request at arrival. Required if the policy needs
                predictions.
            horizon: Optional end of simulated time. Events after it are not processed;
                requests still waiting or running are kept and reported as incomplete.
        """
        if len(policy) != 0:
            raise ValueError("policy queue must be empty at the start of a run")
        if policy.requires_prediction and predictor is None:
            raise ValueError(f"policy {policy.name!r} requires a predictor")
        if not workload.specs:
            raise ValueError("workload is empty")

        sm = self.service_model
        requests = [Request(spec) for spec in workload.specs]
        seq = itertools.count()
        events: list[tuple[float, int, int, Request]] = []
        for r in sorted(requests, key=lambda q: (q.arrival_time, q.request_id)):
            events.append((r.arrival_time, EventType.ARRIVAL, next(seq), r))
        heapq.heapify(events)

        trace: list[tuple[float, str, int]] | None = [] if self.record_trace else None
        running: Request | None = None
        busy_time = 0.0
        n_decisions = 0
        sched_wall = 0.0
        pred_wall = 0.0
        now = 0.0
        wall_start = time.perf_counter()

        while events:
            if horizon is not None and events[0][0] > horizon:
                break
            now, etype, _, req = heapq.heappop(events)

            if etype == EventType.ARRIVAL:
                req.mark_arrived(now)
                if predictor is not None:
                    t0 = time.perf_counter()
                    req.predicted_output_tokens = predictor.predict(req.spec.features)
                    pred_wall += time.perf_counter() - t0
                t0 = time.perf_counter()
                policy.admit(req, now)
                sched_wall += time.perf_counter() - t0
            elif etype == EventType.FIRST_TOKEN:
                req.mark_first_token(now)
            else:  # COMPLETION
                if req is not running:
                    raise RuntimeError(f"completion of request {req.request_id} that is not running")
                req.mark_completed(now)
                running = None
            if trace is not None:
                trace.append((now, etype.name.lower(), req.request_id))

            # Dispatch once all events at this timestamp are processed.
            if running is None and len(policy) > 0 and (not events or events[0][0] > now):
                t0 = time.perf_counter()
                nxt = policy.select_next(now)
                sched_wall += time.perf_counter() - t0
                n_decisions += 1
                assert nxt is not None
                nxt.mark_started(now)
                running = nxt
                prefill = sm.prefill_time(nxt.prompt_tokens)
                service = sm.service_time(nxt.prompt_tokens, nxt.actual_output_tokens)
                busy_time += service
                heapq.heappush(events, (now + prefill, EventType.FIRST_TOKEN, next(seq), nxt))
                heapq.heappush(events, (now + service, EventType.COMPLETION, next(seq), nxt))
                if trace is not None:
                    trace.append((now, "dispatch", nxt.request_id))

        if horizon is None:
            unfinished = [r.request_id for r in requests if not r.is_completed]
            if unfinished:
                raise RuntimeError(f"simulation ended with unfinished requests: {unfinished[:5]}")
            end_time = max(r.completion_time for r in requests)  # type: ignore[type-var]
        else:
            end_time = horizon
            if running is not None:
                elapsed = horizon - running.start_time  # type: ignore[operator]
                running.generated_tokens = sm.tokens_generated_by(
                    elapsed, running.prompt_tokens, running.actual_output_tokens
                )
                # Count only the part of the running request's service inside the window.
                busy_time -= sm.service_time(running.prompt_tokens, running.actual_output_tokens) - elapsed

        return SimulationResult(
            requests=requests,
            policy=policy.name,
            predictor=predictor.name if predictor is not None else "none",
            predictor_uses_ground_truth=bool(predictor is not None and predictor.uses_ground_truth),
            first_arrival=min(r.arrival_time for r in requests),
            end_time=end_time,
            horizon=horizon,
            busy_time=busy_time,
            n_decisions=n_decisions,
            wall_time_s=time.perf_counter() - wall_start,
            scheduler_wall_s=sched_wall,
            predictor_wall_s=pred_wall,
            trace=trace,
        )


def count_states(result: SimulationResult) -> dict[str, int]:
    """Number of requests in each lifecycle state at the end of the run."""
    counts = {s.value: 0 for s in RequestState}
    for r in result.requests:
        counts[r.state.value] += 1
    return counts
