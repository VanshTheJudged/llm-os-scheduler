"""Request representation.

Three layers keep observable and hidden information apart:

* :class:`PromptFeatures` - what a scheduler can see at admission time.
* :class:`RequestSpec` - an immutable workload entry: features, arrival time and the
  *actual* output length (ground truth, never passed to a predictor).
* :class:`Request` - the mutable per-simulation state of one request. A fresh ``Request``
  is created from each ``RequestSpec`` for every simulation run, so the same workload can
  be replayed under different policies without leaking state between runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RequestState(str, Enum):
    """Lifecycle of a request inside the simulator."""

    PENDING = "pending"  # not yet arrived
    WAITING = "waiting"  # arrived, in the scheduler queue
    RUNNING = "running"  # holds the execution slot
    COMPLETED = "completed"


class InvalidTransition(RuntimeError):
    """Raised when a request is moved to a state that its lifecycle forbids."""


@dataclass(frozen=True)
class PromptFeatures:
    """Information observable before generation starts.

    Attributes:
        request_id: Unique identifier.
        prompt_tokens: Prompt length in tokens.
        task_type: Coarse task label (e.g. ``"qa"``, ``"code"``).
        detail_requested: Whether the prompt explicitly asks for a detailed answer.
        max_tokens: User-specified generation cap.
        user_priority: Optional user priority (lower is more urgent). Not used by the
            implemented policies; kept for future priority scheduling.
    """

    request_id: int
    prompt_tokens: int
    task_type: str
    detail_requested: bool
    max_tokens: int
    user_priority: int = 0


@dataclass(frozen=True)
class RequestSpec:
    """One immutable workload entry.

    ``actual_output_tokens`` is ground truth used only by the simulator to compute service
    time (and by explicitly labelled oracle reference predictors).
    """

    features: PromptFeatures
    arrival_time: float
    actual_output_tokens: int

    def __post_init__(self) -> None:
        if self.arrival_time < 0:
            raise ValueError("arrival_time must be non-negative")
        if self.actual_output_tokens < 1:
            raise ValueError("actual_output_tokens must be >= 1")
        if self.features.prompt_tokens < 1:
            raise ValueError("prompt_tokens must be >= 1")

    @property
    def request_id(self) -> int:
        return self.features.request_id


class Request:
    """Mutable state of one request during one simulation run."""

    __slots__ = (
        "spec",
        "predicted_output_tokens",
        "state",
        "start_time",
        "first_token_time",
        "completion_time",
        "generated_tokens",
        "preemption_count",
    )

    def __init__(self, spec: RequestSpec) -> None:
        self.spec = spec
        self.predicted_output_tokens: int | None = None
        self.state = RequestState.PENDING
        self.start_time: float | None = None
        self.first_token_time: float | None = None
        self.completion_time: float | None = None
        self.generated_tokens = 0
        # Always 0 in this version: the implemented policies are non-preemptive.
        self.preemption_count = 0

    # --- convenience accessors -------------------------------------------------------
    @property
    def request_id(self) -> int:
        return self.spec.features.request_id

    @property
    def arrival_time(self) -> float:
        return self.spec.arrival_time

    @property
    def prompt_tokens(self) -> int:
        return self.spec.features.prompt_tokens

    @property
    def actual_output_tokens(self) -> int:
        return self.spec.actual_output_tokens

    @property
    def is_completed(self) -> bool:
        return self.state is RequestState.COMPLETED

    # --- derived timings (None until defined) -----------------------------------------
    @property
    def waiting_time(self) -> float | None:
        """Queueing delay: start of service minus arrival."""
        if self.start_time is None:
            return None
        return self.start_time - self.arrival_time

    @property
    def ttft(self) -> float | None:
        """Time to first token: first-token time minus arrival."""
        if self.first_token_time is None:
            return None
        return self.first_token_time - self.arrival_time

    @property
    def jct(self) -> float | None:
        """Job completion time: completion time minus arrival (not absolute time)."""
        if self.completion_time is None:
            return None
        return self.completion_time - self.arrival_time

    @property
    def service_time(self) -> float | None:
        if self.completion_time is None or self.start_time is None:
            return None
        return self.completion_time - self.start_time

    # --- lifecycle transitions ------------------------------------------------------
    def mark_arrived(self, now: float) -> None:
        if self.state is not RequestState.PENDING:
            raise InvalidTransition(f"request {self.request_id}: arrive from {self.state}")
        if now < self.arrival_time:
            raise InvalidTransition(f"request {self.request_id}: arrives before its arrival time")
        self.state = RequestState.WAITING

    def mark_started(self, now: float) -> None:
        if self.state is not RequestState.WAITING:
            raise InvalidTransition(f"request {self.request_id}: start from {self.state}")
        if now < self.arrival_time:
            raise InvalidTransition(f"request {self.request_id}: starts before arrival")
        self.state = RequestState.RUNNING
        self.start_time = now

    def mark_first_token(self, now: float) -> None:
        if self.state is not RequestState.RUNNING or self.first_token_time is not None:
            raise InvalidTransition(f"request {self.request_id}: first token from {self.state}")
        self.first_token_time = now
        self.generated_tokens = 1

    def mark_completed(self, now: float) -> None:
        if self.state is not RequestState.RUNNING:
            raise InvalidTransition(f"request {self.request_id}: complete from {self.state}")
        if self.first_token_time is None:
            raise InvalidTransition(f"request {self.request_id}: completes before first token")
        self.state = RequestState.COMPLETED
        self.completion_time = now
        self.generated_tokens = self.actual_output_tokens

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Request(id={self.request_id}, arr={self.arrival_time:.3f}, "
            f"out={self.actual_output_tokens}, pred={self.predicted_output_tokens}, "
            f"state={self.state.value})"
        )
