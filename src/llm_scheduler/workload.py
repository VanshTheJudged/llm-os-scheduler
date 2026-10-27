"""Synthetic workload generation.

A workload is a fixed list of :class:`~llm_scheduler.request.RequestSpec`. It is generated
once per (mix, seed, load, size) and replayed unchanged under every policy, so policy
comparisons are paired.

Generative model (the "ground truth" of the synthetic world)
-----------------------------------------------------------
Each request draws a task type from the mix, then:

* ``prompt_tokens ~ LogNormal(log(prompt_median), prompt_sigma)``, clipped to [4, 8192];
* ``detail_requested ~ Bernoulli(p_detail)``;
* ``max_tokens`` uniform over ``MAX_TOKENS_CHOICES``;
* ``output ~ LogNormal(log(output_median), output_sigma)``, multiplied by
  ``DETAIL_MULTIPLIER`` if detail was requested, clipped to [1, max_tokens].
  For ``summarization`` the median scales with ``sqrt(prompt_tokens / 1000)``.

Arrivals form a Poisson process whose rate is calibrated to the sample so that the offered
load equals the target utilisation: ``rate = load / mean(service_time)``.

Request sizes and inter-arrival gaps use independent random streams. For a fixed seed the
request sizes are therefore identical across loads and only the arrival times are rescaled
(common random numbers across the load sweep).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from .request import PromptFeatures, RequestSpec
from .service_model import ServiceModel

#: Output-length category thresholds (inclusive upper bounds, in tokens).
SHORT_MAX_TOKENS = 128
MEDIUM_MAX_TOKENS = 512
LENGTH_CATEGORIES = ("short", "medium", "long")

DETAIL_MULTIPLIER = 1.8
MAX_TOKENS_CHOICES = (512, 1024, 2048, 4096)
PROMPT_TOKEN_RANGE = (4, 8192)


def length_category(output_tokens: int) -> str:
    """Category of a request by its *actual* output length."""
    if output_tokens <= SHORT_MAX_TOKENS:
        return "short"
    if output_tokens <= MEDIUM_MAX_TOKENS:
        return "medium"
    return "long"


@dataclass(frozen=True)
class TaskProfile:
    prompt_median: float
    prompt_sigma: float
    output_median: float
    output_sigma: float
    p_detail: float


TASK_PROFILES: dict[str, TaskProfile] = {
    "qa": TaskProfile(prompt_median=40, prompt_sigma=0.5, output_median=25, output_sigma=0.6, p_detail=0.10),
    "chat": TaskProfile(prompt_median=120, prompt_sigma=0.7, output_median=150, output_sigma=0.7, p_detail=0.25),
    "summarization": TaskProfile(prompt_median=1000, prompt_sigma=0.5, output_median=100, output_sigma=0.4, p_detail=0.15),
    "code": TaskProfile(prompt_median=200, prompt_sigma=0.6, output_median=300, output_sigma=0.8, p_detail=0.30),
    "longform": TaskProfile(prompt_median=80, prompt_sigma=0.5, output_median=700, output_sigma=0.6, p_detail=0.50),
}

#: Task-type proportions for the three evaluated workload patterns.
WORKLOAD_MIXES: dict[str, dict[str, float]] = {
    "short_heavy": {"qa": 0.60, "chat": 0.30, "summarization": 0.05, "code": 0.03, "longform": 0.02},
    "mixed": {"qa": 0.30, "chat": 0.25, "summarization": 0.15, "code": 0.15, "longform": 0.15},
    "long_heavy": {"qa": 0.10, "chat": 0.15, "summarization": 0.10, "code": 0.30, "longform": 0.35},
}


@dataclass(frozen=True)
class Workload:
    """A generated workload plus the parameters that produced it."""

    mix: str
    seed: int
    target_load: float
    arrival_rate: float
    specs: tuple[RequestSpec, ...] = field(repr=False)

    def __len__(self) -> int:
        return len(self.specs)

    def describe(self, service_model: ServiceModel) -> dict[str, float]:
        """Summary statistics of the sample (sizes and offered load)."""
        out = np.array([s.actual_output_tokens for s in self.specs], dtype=float)
        svc = np.array(
            [service_model.service_time(s.features.prompt_tokens, s.actual_output_tokens) for s in self.specs]
        )
        cats = [length_category(int(o)) for o in out]
        span = self.specs[-1].arrival_time - self.specs[0].arrival_time if len(self.specs) > 1 else 0.0
        return {
            "n_requests": float(len(self.specs)),
            "mean_output_tokens": float(out.mean()),
            "median_output_tokens": float(np.median(out)),
            "p95_output_tokens": float(np.percentile(out, 95)),
            "mean_service_s": float(svc.mean()),
            "cv_service": float(svc.std() / svc.mean()),
            "share_short": cats.count("short") / len(cats),
            "share_medium": cats.count("medium") / len(cats),
            "share_long": cats.count("long") / len(cats),
            "arrival_rate_per_s": self.arrival_rate,
            "arrival_span_s": float(span),
        }


def _stream(seed: int, mix: str, purpose: str) -> np.random.Generator:
    """Independent, reproducible random stream for one (seed, mix, purpose)."""
    key = [seed, zlib.crc32(mix.encode()), zlib.crc32(purpose.encode())]
    return np.random.default_rng(np.random.SeedSequence(key))


def generate_workload(
    mix: str,
    n_requests: int,
    load: float,
    seed: int,
    service_model: ServiceModel,
    mixes: Mapping[str, Mapping[str, float]] = WORKLOAD_MIXES,
) -> Workload:
    """Generate a deterministic synthetic workload.

    Args:
        mix: Name of a task mix in ``mixes``.
        n_requests: Number of requests.
        load: Target utilisation of the single execution slot (``rate * E[service]``).
            Values >= 1 create an overloaded system.
        seed: Workload seed.
        service_model: Used only to calibrate the arrival rate.
        mixes: Task-type proportions per mix.
    """
    if mix not in mixes:
        raise KeyError(f"unknown mix {mix!r}; known: {sorted(mixes)}")
    if n_requests < 1:
        raise ValueError("n_requests must be >= 1")
    if load <= 0:
        raise ValueError("load must be positive")

    proportions = mixes[mix]
    task_names = list(proportions)
    probs = np.array([proportions[t] for t in task_names], dtype=float)
    if not np.isclose(probs.sum(), 1.0):
        raise ValueError(f"mix {mix!r} proportions sum to {probs.sum()}, expected 1")

    size_rng = _stream(seed, mix, "sizes")
    arrival_rng = _stream(seed, mix, "arrivals")

    tasks = size_rng.choice(len(task_names), size=n_requests, p=probs)
    prompt_tokens = np.empty(n_requests, dtype=int)
    detail = np.empty(n_requests, dtype=bool)
    output_tokens = np.empty(n_requests, dtype=int)
    max_tokens = size_rng.choice(MAX_TOKENS_CHOICES, size=n_requests)
    # Standard normals drawn up front so every request consumes the same amount of randomness.
    z_prompt = size_rng.standard_normal(n_requests)
    z_output = size_rng.standard_normal(n_requests)
    u_detail = size_rng.random(n_requests)

    for i in range(n_requests):
        name = task_names[tasks[i]]
        prof = TASK_PROFILES[name]
        p = int(round(np.exp(np.log(prof.prompt_median) + prof.prompt_sigma * z_prompt[i])))
        p = int(np.clip(p, *PROMPT_TOKEN_RANGE))
        median = prof.output_median
        if name == "summarization":
            median *= np.sqrt(p / 1000.0)
        o = np.exp(np.log(median) + prof.output_sigma * z_output[i])
        d = bool(u_detail[i] < prof.p_detail)
        if d:
            o *= DETAIL_MULTIPLIER
        prompt_tokens[i] = p
        detail[i] = d
        output_tokens[i] = int(np.clip(round(o), 1, max_tokens[i]))

    service = np.array([service_model.service_time(int(p), int(o)) for p, o in zip(prompt_tokens, output_tokens)])
    arrival_rate = load / float(service.mean())
    gaps = arrival_rng.standard_exponential(n_requests) / arrival_rate
    arrivals = np.cumsum(gaps)

    specs = tuple(
        RequestSpec(
            features=PromptFeatures(
                request_id=i,
                prompt_tokens=int(prompt_tokens[i]),
                task_type=task_names[tasks[i]],
                detail_requested=bool(detail[i]),
                max_tokens=int(max_tokens[i]),
            ),
            arrival_time=float(arrivals[i]),
            actual_output_tokens=int(output_tokens[i]),
        )
        for i in range(n_requests)
    )
    return Workload(mix=mix, seed=seed, target_load=load, arrival_rate=arrival_rate, specs=specs)


def workload_from_rows(rows: list[dict], mix: str = "manual", seed: int = -1) -> Workload:
    """Build a small hand-specified workload (used by tests and the worked example).

    Each row needs ``arrival_time``, ``prompt_tokens`` and ``output_tokens``; optional keys
    are ``task_type``, ``detail_requested`` and ``max_tokens``. Rows are sorted by
    ``(arrival_time, original index)`` and request ids follow that order.
    """
    ordered = sorted(enumerate(rows), key=lambda item: (item[1]["arrival_time"], item[0]))
    specs = []
    for new_id, (_, row) in enumerate(ordered):
        specs.append(
            RequestSpec(
                features=PromptFeatures(
                    request_id=new_id,
                    prompt_tokens=int(row["prompt_tokens"]),
                    task_type=row.get("task_type", "chat"),
                    detail_requested=bool(row.get("detail_requested", False)),
                    max_tokens=int(row.get("max_tokens", 4096)),
                ),
                arrival_time=float(row["arrival_time"]),
                actual_output_tokens=int(row["output_tokens"]),
            )
        )
    return Workload(mix=mix, seed=seed, target_load=float("nan"), arrival_rate=float("nan"), specs=tuple(specs))
