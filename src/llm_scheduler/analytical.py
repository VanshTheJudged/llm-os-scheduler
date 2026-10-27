"""Closed-form M/G/1 results used to validate the simulator (Experiment 1).

Both functions take the *empirical* distribution of a workload sample (its service times,
and for priority scheduling its priority keys), so they predict what the simulator should
produce for that sample when arrivals are Poisson with rate ``arrival_rate``.

* :func:`pk_mean_wait` - Pollaczek-Khinchine mean waiting time for FCFS:
  ``W = lambda * E[S^2] / (2 * (1 - rho))``.
* :func:`nonpreemptive_priority_mean_wait` - Cobham's formula for non-preemptive priority
  classes (class 1 = highest priority):
  ``W_k = W0 / ((1 - sigma_{k-1}) * (1 - sigma_k))``, with ``W0 = lambda * E[S^2] / 2`` and
  ``sigma_k`` the load of classes 1..k. Treating each distinct key value as one class gives
  the exact mean wait of non-preemptive SJF on that key.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def pk_mean_wait(service_times: Sequence[float], arrival_rate: float) -> float:
    s = np.asarray(service_times, dtype=float)
    rho = arrival_rate * s.mean()
    if rho >= 1:
        raise ValueError(f"unstable system: rho = {rho:.3f}")
    return float(arrival_rate * np.mean(s**2) / (2.0 * (1.0 - rho)))


def nonpreemptive_priority_mean_wait(
    service_times: Sequence[float], keys: Sequence[float], arrival_rate: float
) -> float:
    s = np.asarray(service_times, dtype=float)
    k = np.asarray(keys, dtype=float)
    if s.shape != k.shape:
        raise ValueError("service_times and keys must have the same length")
    n = len(s)
    rho = arrival_rate * s.mean()
    if rho >= 1:
        raise ValueError(f"unstable system: rho = {rho:.3f}")
    w0 = arrival_rate * np.mean(s**2) / 2.0
    order = np.argsort(k, kind="stable")
    k_sorted, s_sorted = k[order], s[order]
    uniq, start = np.unique(k_sorted, return_index=True)
    bounds = list(start) + [n]
    sigma_prev = 0.0
    total = 0.0
    for i in range(len(uniq)):
        cls = s_sorted[bounds[i] : bounds[i + 1]]
        p = len(cls) / n
        sigma = sigma_prev + arrival_rate * p * cls.mean()
        total += p * w0 / ((1.0 - sigma_prev) * (1.0 - sigma))
        sigma_prev = sigma
    return float(total)
