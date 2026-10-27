"""Output-length predictors.

Deployable predictors implement ``predict(features)`` and receive only
:class:`~llm_scheduler.request.PromptFeatures`; they cannot see the actual output length.

The *reference* predictors (``OraclePredictor``, ``NoisyOraclePredictor``) are not
deployable. They are built from an explicit ``ground_truth`` mapping so that experiments can
isolate the effect of prediction error. They set ``uses_ground_truth = True`` and every
result produced with them is labelled as a reference condition.

Randomised predictors draw their noise from a hash of ``(seed, request_id)`` rather than a
shared generator, so a prediction does not depend on the order in which requests are seen.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Mapping

from .request import PromptFeatures

_MASK64 = (1 << 64) - 1


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & _MASK64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _MASK64
    return x ^ (x >> 31)


def hash_uniform(seed: int, request_id: int, stream: int = 0) -> float:
    """Deterministic uniform number in (0, 1) for one request."""
    h = _splitmix64((seed * 1_000_003 + stream) & _MASK64)
    h = _splitmix64(h ^ (request_id & _MASK64))
    return ((h >> 11) + 0.5) / float(1 << 53)


def hash_normal(seed: int, request_id: int) -> float:
    """Deterministic standard normal (Box-Muller) for one request."""
    u1 = hash_uniform(seed, request_id, 1)
    u2 = hash_uniform(seed, request_id, 2)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


class LengthPredictor(ABC):
    """Predicts the number of output tokens a request will generate."""

    name: str = "predictor"
    #: True only for reference predictors that read the actual output length.
    uses_ground_truth: bool = False

    @abstractmethod
    def predict(self, features: PromptFeatures) -> int:
        """Return a predicted output length (>= 1 token)."""


class HeuristicPredictor(LengthPredictor):
    """Interpretable rule-based predictor.

    ``prediction = prior[task_type] x (sqrt(prompt/1024) if summarization)
    x (detail_multiplier if detail requested)``, clipped to ``[1, max_tokens]``.

    The priors are round powers of two set by hand before evaluation; they were not fitted to
    any evaluation workload. They are deliberately not equal to the generator's medians.
    """

    name = "heuristic"
    DEFAULT_PRIORS = {"qa": 32, "chat": 128, "summarization": 128, "code": 256, "longform": 512}

    def __init__(
        self,
        priors: Mapping[str, float] | None = None,
        default_prior: float = 128.0,
        detail_multiplier: float = 2.0,
        summary_reference_prompt: float = 1024.0,
    ) -> None:
        self.priors = dict(priors or self.DEFAULT_PRIORS)
        self.default_prior = default_prior
        self.detail_multiplier = detail_multiplier
        self.summary_reference_prompt = summary_reference_prompt

    def predict(self, features: PromptFeatures) -> int:
        estimate = self.priors.get(features.task_type, self.default_prior)
        if features.task_type == "summarization":
            estimate *= math.sqrt(features.prompt_tokens / self.summary_reference_prompt)
        if features.detail_requested:
            estimate *= self.detail_multiplier
        return int(min(max(round(estimate), 1), features.max_tokens))


class PromptLengthPredictor(LengthPredictor):
    """Naive baseline: assume the answer is as long as the prompt."""

    name = "prompt_length"

    def predict(self, features: PromptFeatures) -> int:
        return int(min(max(features.prompt_tokens, 1), features.max_tokens))


class MaxTokensPredictor(LengthPredictor):
    """Naive baseline: assume every request uses its full ``max_tokens`` budget."""

    name = "max_tokens"

    def predict(self, features: PromptFeatures) -> int:
        return int(features.max_tokens)


class RandomPredictor(LengthPredictor):
    """Prediction independent of the request: uniform on ``[1, upper]``.

    Under SJF this yields random-order service; it is a "no information" control.
    """

    name = "random"

    def __init__(self, seed: int, upper: int = 4096) -> None:
        self.seed = seed
        self.upper = upper

    def predict(self, features: PromptFeatures) -> int:
        return 1 + int(hash_uniform(self.seed, features.request_id) * self.upper)


class OraclePredictor(LengthPredictor):
    """REFERENCE ONLY: returns the actual output length. Not deployable."""

    name = "oracle"
    uses_ground_truth = True

    def __init__(self, ground_truth: Mapping[int, int]) -> None:
        self._truth = dict(ground_truth)

    def predict(self, features: PromptFeatures) -> int:
        return int(self._truth[features.request_id])


class NoisyOraclePredictor(LengthPredictor):
    """REFERENCE ONLY: actual length times log-normal noise ``exp(sigma * z)``.

    ``sigma`` controls the error level synthetically; this isolates the effect of prediction
    error and does not validate any real predictor.
    """

    uses_ground_truth = True

    def __init__(self, ground_truth: Mapping[int, int], sigma: float, seed: int) -> None:
        if sigma < 0:
            raise ValueError("sigma must be non-negative")
        self._truth = dict(ground_truth)
        self.sigma = sigma
        self.seed = seed
        self.name = f"noisy_oracle_s{sigma:g}"

    def predict(self, features: PromptFeatures) -> int:
        actual = self._truth[features.request_id]
        noisy = actual * math.exp(self.sigma * hash_normal(self.seed, features.request_id))
        return max(1, int(round(noisy)))


def build_predictor(spec: Mapping[str, Any] | None, ground_truth: Mapping[int, int], seed: int) -> LengthPredictor | None:
    """Create a predictor from a config entry such as ``{"type": "heuristic"}``.

    ``ground_truth`` is passed only to reference predictors. ``seed`` drives randomised
    predictors. Returns ``None`` when ``spec`` is ``None`` (no predictor, e.g. FCFS).
    """
    if spec is None:
        return None
    kind = spec["type"]
    if kind == "heuristic":
        return HeuristicPredictor(**{k: v for k, v in spec.items() if k != "type"})
    if kind == "prompt_length":
        return PromptLengthPredictor()
    if kind == "max_tokens":
        return MaxTokensPredictor()
    if kind == "random":
        return RandomPredictor(seed=seed, upper=int(spec.get("upper", 4096)))
    if kind == "oracle":
        return OraclePredictor(ground_truth)
    if kind == "noisy_oracle":
        return NoisyOraclePredictor(ground_truth, sigma=float(spec["sigma"]), seed=seed)
    raise KeyError(f"unknown predictor type {kind!r}")
