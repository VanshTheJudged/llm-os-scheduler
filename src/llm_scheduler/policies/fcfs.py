"""First-Come, First-Served."""

from __future__ import annotations

from ..request import Request
from .base import StaticPriorityPolicy


class FCFSPolicy(StaticPriorityPolicy):
    """Serve requests in arrival order.

    Tie-break: equal arrival times are served in ascending ``request_id``.
    Uses no length information.
    """

    name = "fcfs"

    def priority_key(self, request: Request) -> tuple:
        return (request.arrival_time,)
