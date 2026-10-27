# System Design

This document describes the system **as implemented**. Components named in the synopsis but
not implemented are listed at the end and in `IMPLEMENTATION_STATUS.md`.

## 1. Architecture

```text
 config/*.yaml ──► experiment_runner ──► generate_workload ──► Workload (immutable RequestSpecs)
                          │                                         │  replayed unchanged
                          │                                         ▼  under every condition
                          │        ┌──────────────── Simulator (discrete-event, 1 slot) ─────────────────┐
                          │        │ ARRIVAL ──► LengthPredictor.predict(features) ──► policy.admit()   │
                          │        │ slot free ──► policy.select_next() ──► prefill ──► FIRST_TOKEN     │
                          │        │            ──► decode (n-1 tokens, ACTUAL length) ──► COMPLETION   │
                          │        └──────────────────────────────────┬──────────────────────────────────┘
                          │                                           ▼
                          └──────────► metrics (summary, by-category, per-request) ──► results/*.csv
                                                                                           │
                                         experiments/scripts/analyze.py ◄──────────────────┘
                                         (paired statistics, tables.md, figures/*.png)
```

| Module (`src/llm_scheduler/`) | Responsibility |
|---|---|
| `request.py` | `PromptFeatures` (observable), `RequestSpec` (immutable, holds the actual length), `Request` (per-run mutable state with an enforced state machine) |
| `workload.py` | Seeded synthetic workload generator, three task mixes, length categories |
| `service_model.py` | Service-time model: prefill (emits token 1) + (n − 1) decode steps |
| `predictor.py` | Heuristic predictor, naive baselines, and labelled reference predictors (oracle, noisy oracle) |
| `policies/` | `SchedulingPolicy` interface; FCFS, predictive SJF, SJF with linear aging (extension) |
| `simulator.py` | Discrete-event simulation of one non-preemptive execution slot |
| `metrics.py` | Metric definitions, per-category metrics, confidence intervals |
| `analytical.py` | Closed-form M/G/1 results used to validate the simulator |
| `experiment_runner.py` | Config-driven paired experiments; timestamped outputs, metadata, logs |
| `plotting.py` | Figure style and chart functions |

## 2. Request model and information separation

```text
PromptFeatures  (request_id, prompt_tokens, task_type, detail_requested, max_tokens, user_priority)
      ▲ only this is passed to LengthPredictor.predict()
RequestSpec     (features, arrival_time, actual_output_tokens)      ← immutable, part of the workload
Request         (spec, predicted_output_tokens, state, start_time, first_token_time,
                 completion_time, generated_tokens, preemption_count) ← created fresh per run
```

- Deployable predictors receive `PromptFeatures`, which has no field for the actual length
  (unit-tested).
- `OraclePredictor` and `NoisyOraclePredictor` are built from an explicit
  `ground_truth` mapping, set `uses_ground_truth = True`, and every summary row records
  `predictor_is_reference`. They exist only to isolate the effect of prediction error.
- The simulator computes service time from `actual_output_tokens` only; the prediction is
  used only by the policy (unit-tested with deliberately wrong predictions).

### Request state machine

```text
PENDING ──mark_arrived──► WAITING ──mark_started──► RUNNING ──mark_first_token──► RUNNING ──mark_completed──► COMPLETED
```

Any other transition raises `InvalidTransition`: a request cannot start before it arrives,
complete before its first token, complete twice, or be scheduled again after completing.

## 3. Service-time model

For a request with `p` prompt tokens and `n` output tokens:

```text
prefill(p)      = prefill_base_s + p · prefill_per_token_s       (emits token 1)
service(p, n)   = prefill(p) + (n − 1) · decode_per_token_s
first token at  start + prefill(p)
```

Defaults (`config/default.yaml`): `prefill_base_s = 0.010`, `prefill_per_token_s = 0.0002`,
`decode_per_token_s = 0.025`. These are **assumptions**, chosen so that decode dominates
service time. They are not measurements.
Because the arrival rate is derived from a target utilisation, multiplying all constants by
`c` multiplies every time metric by `c` (unit-tested), so relative comparisons do not
depend on the absolute scale. They do depend on the *ratio* of prefill to decode cost; that
ratio was not varied (see `LIMITATIONS.md`).

## 4. Simulator semantics

- **One execution slot**, non-preemptive: one request is served at a time and runs to
  completion. This is an M/G/1 queue when arrivals are Poisson.
- **Events:** `ARRIVAL`, `FIRST_TOKEN`, `COMPLETION`, held in a binary heap keyed by
  `(time, event type, insertion sequence)`.
- **Equal-time ordering:** `FIRST_TOKEN` < `COMPLETION` < `ARRIVAL`, then insertion
  order; arrivals are inserted in `(arrival_time, request_id)` order.
- **Scheduling decisions** are made only after *all* events at a timestamp have been
  processed. So a request arriving at the instant another completes is a candidate for that
  decision (unit-tested).
- **Prediction** happens once per request at its `ARRIVAL` event (admission time).
- **Termination:** without a horizon the run ends when the event heap is empty, and the
  simulator asserts that every request completed. With a horizon, events after it are not
  processed. Waiting/running requests are kept and reported as incomplete; a running
  request's partial output is counted; requests arriving after the horizon are reported as
  not arrived.
- **Wall-clock instrumentation:** Python `perf_counter` time inside `admit` +
  `select_next` and inside `predict` is recorded. This measures *this Python
  implementation on this laptop*, not a production scheduler.

## 5. Policies

All implemented policies subclass `StaticPriorityPolicy`: the ordering key is computed once
at admission and the queue is a binary heap (O(log n) per operation). Ties on the key are
broken by `request_id`, which follows arrival order.

| Policy | Key (smallest first) | Uses prediction | Preemptive |
|---|---|---|---|
| `fcfs` | `(arrival_time)` | no | no |
| `sjf` (predictive SJF) | `(predicted_output_tokens, arrival_time)` | yes | **no** |
| `sjf_aging` (extension) | `(predicted_output_tokens + a · arrival_time, arrival_time)` | yes | no |

**Why aging fits a static key.** The intended priority of a waiting request at time `t` is
`predicted − a·(t − arrival)`. At any fixed `t`, the term `a·t` is common to every waiting
request, so the order equals the order of `predicted + a·arrival`. `a = 0` is plain SJF
and `a → ∞` is FCFS (both unit-tested).

**Time-varying policies** (MLFQ, preemptive SRPT) cannot use a static key. They would
implement `select_next` directly and need preemption support in the simulator. Neither
exists in this version.

## 6. Predictors

| Name | Inputs | Deployable? | Definition |
|---|---|---|---|
| `heuristic` | task type, detail flag, prompt length, max_tokens | yes | prior[task] × √(prompt/1024) (summarisation only) × 2 (if detail requested), clipped to [1, max_tokens]; priors qa 32, chat 128, summarisation 128, code 256, longform 512 |
| `prompt_length` | prompt length | yes | predicted = prompt tokens (naive) |
| `max_tokens` | max_tokens | yes | predicted = max_tokens (naive) |
| `random` | none | yes (uninformative) | uniform on [1, 4096], hashed from (seed, id) |
| `oracle` | actual length | **no** (reference) | predicted = actual |
| `noisy_oracle` | actual length | **no** (reference) | actual × exp(σ·z), z ~ N(0, 1) hashed from (seed, id) |

The heuristic constants are round numbers set by hand before any evaluation run. They differ
from the generator's parameters (for example, the longform generator median is 700 tokens and
the heuristic prior is 512). However, the heuristic uses the same *features* that drive the
generator. Its accuracy here is therefore an optimistic case (see `LIMITATIONS.md`).

## 7. Metrics

Definitions are in `metrics.py` and `METHODOLOGY.md`. JCT = completion − arrival. TTFT =
first token − arrival = waiting + prefill. Waiting = start − arrival. Slowdown = JCT /
service. Throughput is measured over the observation window [first arrival, last completion
or horizon]. Percentiles are reported only with at least 200 (P95) or 1,000 (P99)
observations.

## 8. Not implemented (planned)

MLFQ with promotion/demotion; preemption (recompute or swap); a KV-cache/memory model;
continuous batching or multiple slots; a learned length predictor; vLLM or any real backend
integration; production deployment. The interface in `policies/base.py` was designed so that
such policies can be added, but no such policy exists or has been tested.
