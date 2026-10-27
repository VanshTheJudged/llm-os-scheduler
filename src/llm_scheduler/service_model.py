"""Service-time model of the simulated execution slot.

A request with ``p`` prompt tokens and ``n`` output tokens is served as:

* **prefill**: ``prefill_base_s + p * prefill_per_token_s`` seconds. Prefill produces the
  first output token (as in common inference engines, where the prefill forward pass emits
  token 1).
* **decode**: the remaining ``n - 1`` tokens, ``decode_per_token_s`` seconds each.

So ``service_time = prefill + (n - 1) * decode_per_token_s`` and
``first_token_offset = prefill``.

The default constants (see ``config/default.yaml``) are *assumed* values chosen so that
decode dominates service time, which is typical of autoregressive generation. They are not
measurements of any GPU. Because the workload generator sets the arrival rate from a target
utilisation, multiplying every constant by ``c`` multiplies every time metric by ``c`` and
leaves relative comparisons between policies unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceModel:
    """Deterministic per-request service time on a single execution slot."""

    prefill_base_s: float = 0.010
    prefill_per_token_s: float = 0.0002
    decode_per_token_s: float = 0.025

    def __post_init__(self) -> None:
        for name in ("prefill_base_s", "prefill_per_token_s", "decode_per_token_s"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a non-negative finite number")
        if self.prefill_base_s == 0 and self.prefill_per_token_s == 0 and self.decode_per_token_s == 0:
            raise ValueError("service model must have positive service time")

    def prefill_time(self, prompt_tokens: int) -> float:
        return self.prefill_base_s + prompt_tokens * self.prefill_per_token_s

    def service_time(self, prompt_tokens: int, output_tokens: int) -> float:
        """Total time a request holds the execution slot."""
        if output_tokens < 1:
            raise ValueError("output_tokens must be >= 1")
        return self.prefill_time(prompt_tokens) + (output_tokens - 1) * self.decode_per_token_s

    def tokens_generated_by(self, elapsed: float, prompt_tokens: int, output_tokens: int) -> int:
        """Tokens emitted ``elapsed`` seconds after service started (for horizon cut-offs)."""
        prefill = self.prefill_time(prompt_tokens)
        if elapsed < prefill:
            return 0
        if self.decode_per_token_s == 0:
            return output_tokens
        decoded = int((elapsed - prefill) // self.decode_per_token_s)
        return min(output_tokens, 1 + decoded)

    def scaled(self, factor: float) -> "ServiceModel":
        """Return a copy with every constant multiplied by ``factor``."""
        return ServiceModel(
            self.prefill_base_s * factor,
            self.prefill_per_token_s * factor,
            self.decode_per_token_s * factor,
        )
