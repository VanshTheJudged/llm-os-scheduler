"""Scheduling policies."""

from __future__ import annotations

from typing import Any, Mapping

from .base import SchedulingPolicy, StaticPriorityPolicy
from .fcfs import FCFSPolicy
from .predictive_sjf import AgingSJFPolicy, PredictiveSJFPolicy

__all__ = [
    "SchedulingPolicy",
    "StaticPriorityPolicy",
    "FCFSPolicy",
    "PredictiveSJFPolicy",
    "AgingSJFPolicy",
    "build_policy",
]


def build_policy(spec: Mapping[str, Any]) -> SchedulingPolicy:
    """Create a fresh policy from a config entry such as ``{"policy": "sjf"}``."""
    kind = spec["policy"]
    if kind == "fcfs":
        return FCFSPolicy()
    if kind == "sjf":
        return PredictiveSJFPolicy()
    if kind == "sjf_aging":
        return AgingSJFPolicy(aging_rate=float(spec["aging_rate"]))
    raise KeyError(f"unknown policy {kind!r}")
