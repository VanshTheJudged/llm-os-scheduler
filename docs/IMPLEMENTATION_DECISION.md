# Implementation Decision

Decision date: 2026-10-27.

## Decision

**Route A: a discrete-event simulator of a single LLM execution slot.**
Real inference integration (Route B) is deferred to future work.

## Evidence that drove the decision

From `PROJECT_AUDIT.md`:

- vLLM is not installed, and vLLM targets Linux; this machine runs Windows 11 with no WSL
  and no Docker.
- The only GPU is a GTX 1650 Ti with 4 GB VRAM. Even with a Linux environment it could hold
  only very small models, so any "real" latency measured here would not represent the
  serving regime the synopsis is about.
- The installed PyTorch is the CPU-only build.

Setting up WSL2, a CUDA toolkit, and a working vLLM build on a 4 GB laptop GPU would consume
most of the available effort and would still produce measurements of limited relevance.
The synopsis itself names the simulator as the fallback ("Path B: if no GPU access").

## What the simulator is and is not

It **is**:

- An event-driven model of request arrival, queueing, a scheduling decision, prefill (which
  produces the first token), token-by-token decode, and completion, on **one** execution
  slot (one request served at a time, non-preemptive).
- Deterministic given a seed, and validated against closed-form queueing results
  (Pollaczek–Khinchine for FCFS, Cobham's non-preemptive priority formula for SJF with exact
  lengths). See Experiment 1.

It is **not**:

- A model of continuous batching, GPU memory, KV-cache blocks, or PagedAttention.
- A measurement of any real GPU. Every latency number it produces is a consequence of the
  assumed service-time constants in `config/default.yaml`.
- An integration with vLLM's scheduler. No vLLM code is used or modified.

## Why a single execution slot

A single non-preemptive server (an M/G/1 queue) is the setting in which FCFS and SJF are
classically defined and analysed. It isolates the question the project asks — does ordering
requests by predicted length help? — from batching effects, and it allows exact analytical
validation. The cost is realism: real servers batch many sequences per forward pass. This is
the main threat to external validity and is discussed in `LIMITATIONS.md`.

## Consequences for the rest of the project

- Load is set as a target utilisation ρ (arrival rate = ρ / mean service time of the
  workload sample), so results do not depend on the absolute values of the assumed timing
  constants (a uniform rescaling of all constants rescales every time metric by the same
  factor; this is unit-tested).
- Time-between-tokens (TBT) is constant by construction in a single-slot model, so it is not
  reported as a result.
- Throughput is identical for all work-conserving policies when every request completes, so
  throughput differences can only appear under overload with a finite horizon
  (Experiment 2, part B).
- Preemption, swap and recompute are not modelled in this version.

## Route B, if pursued later

Minimum steps: Linux (native or WSL2) with a supported CUDA setup; a GPU with enough memory
for a representative model; a vLLM version whose scheduler can be wrapped; record hardware,
model, vLLM version and serving flags with every measurement. The `SchedulingPolicy`
interface in `src/llm_scheduler/policies/base.py` is the intended porting point, but it has
not been tested against vLLM.
