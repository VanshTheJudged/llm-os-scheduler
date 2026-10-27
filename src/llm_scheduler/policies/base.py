"""Scheduling-policy interface.

The simulator talks to a policy through three calls:

* ``admit(request, now)`` - a request has arrived and joins the waiting queue;
* ``select_next(now)`` - the execution slot is free; remove and return the next request
  (or ``None`` if the queue is empty);
* ``len(policy)`` - number of waiting requests.

New policies subclass :class:`SchedulingPolicy`. Policies whose ordering is fixed once a
request is admitted subclass :class:`StaticPriorityPolicy` and only define
``priority_key``. Time-varying policies such as MLFQ would implement ``select_next``
directly (not implemented in this version).
"""

from __future__ import annotations

import heapq
from abc import ABC, abstractmethod
from typing import Any

from ..request import Request


class SchedulingPolicy(ABC):
    """Abstract waiting-queue discipline for one execution slot."""

    name: str = "policy"
    #: Whether ``admit`` needs ``request.predicted_output_tokens`` to be set.
    requires_prediction: bool = False
    #: Whether the policy may interrupt a running request. All implemented policies: False.
    preemptive: bool = False

    @abstractmethod
    def admit(self, request: Request, now: float) -> None:
        """Add an arrived request to the waiting queue."""

    @abstractmethod
    def select_next(self, now: float) -> Request | None:
        """Remove and return the request to run next, or ``None`` if none is waiting."""

    @abstractmethod
    def __len__(self) -> int:
        """Number of waiting requests."""

    def describe(self) -> dict[str, Any]:
        return {"policy": self.name, "preemptive": self.preemptive}


class StaticPriorityPolicy(SchedulingPolicy):
    """Heap-backed policy: smallest ``priority_key`` runs first.

    Ties on the key are broken by ``request_id`` (ids follow arrival order in generated
    workloads), so selection is fully deterministic. ``admit`` and ``select_next`` are
    O(log n).
    """

    def __init__(self) -> None:
        self._heap: list[tuple[tuple, int, Request]] = []

    @abstractmethod
    def priority_key(self, request: Request) -> tuple:
        """Ordering key computed once, at admission."""

    def admit(self, request: Request, now: float) -> None:
        if self.requires_prediction and request.predicted_output_tokens is None:
            raise ValueError(f"{self.name} requires a predicted output length")
        heapq.heappush(self._heap, (self.priority_key(request), request.request_id, request))

    def select_next(self, now: float) -> Request | None:
        if not self._heap:
            return None
        return heapq.heappop(self._heap)[2]

    def __len__(self) -> int:
        return len(self._heap)
