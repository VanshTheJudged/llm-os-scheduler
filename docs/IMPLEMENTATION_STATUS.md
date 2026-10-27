# Implementation Status

Status as of 2026-10-28. Vocabulary: **COMPLETED** (implemented, tested, used in experiments) ·
**PARTIAL** (implemented in a reduced form) · **PLANNED** (not implemented) · **BLOCKED**
(cannot be done in this environment).

## Component status

| # | Component (from the synopsis) | Status | Evidence |
|---|---|---|---|
| 1 | Request model (id, arrival, prompt length, actual/predicted length, priority, state, generated tokens, completion, waiting, preemption count) | COMPLETED | `src/llm_scheduler/request.py`; `tests/test_request.py` (8 tests) |
| 2 | Workload generator, 3 patterns, deterministic seeds | COMPLETED | `workload.py`; `tests/test_workload.py` (9 tests); EXP3 statistics |
| 3 | Heuristic length predictor (+ naive baselines, labelled reference predictors) | COMPLETED | `predictor.py`; `tests/test_predictor.py` (7 tests); EXP4 |
| 4 | FCFS baseline | COMPLETED | `policies/fcfs.py`; `tests/test_fcfs.py` (7 tests, including the Lindley cross-check); EXP1 |
| 5 | Predictive-SJF, non-preemptive | COMPLETED | `policies/predictive_sjf.py`; `tests/test_sjf.py` (8 tests); EXP1 Cobham check |
| 6 | Simulated backend: discrete-event, single slot, horizon support | COMPLETED | `simulator.py`, `service_model.py`; `tests/test_simulator.py` (13 tests) |
| 7 | Metrics collector (TTFT, JCT mean/median/P95/P99, waiting, throughput, prediction error, completed/incomplete) | COMPLETED | `metrics.py`; `tests/test_metrics.py` (7 tests) |
| 8 | Experiment automation (configs, paired runs, timestamped outputs, logs, metadata) | COMPLETED | `experiment_runner.py`, `experiments/configs/`, `experiments/scripts/run_all.py` |
| 9 | Plots and analysis | COMPLETED | `plotting.py`, `experiments/scripts/analyze.py`, 15 figures |
| 10 | Analytical validation (P-K, Cobham) | COMPLETED (not in synopsis) | `analytical.py`; EXP1 |
| 11 | Aging (starvation guard) | PARTIAL | Linear aging only (`AgingSJFPolicy`), evaluated as the single extension (EXP7). It is not integrated with MLFQ and does not guarantee a bound on waiting. |
| 12 | MLFQ with promotion/demotion | PLANNED | — |
| 13 | Preemption: recompute mode | PLANNED | `preemption_count` field exists and is always 0 |
| 14 | Preemption: swap mode (KV-cache to CPU RAM) | PLANNED | — |
| 15 | KV-cache / memory model, continuous batching, multiple slots | PLANNED | — |
| 16 | Learned (ML) length predictor | PLANNED | — |
| 17 | User-priority scheduling | PLANNED | `user_priority` field exists; no policy uses it |
| 18 | vLLM scheduler integration / real GPU measurements | BLOCKED | No vLLM, no WSL/Docker, 4 GB GTX 1650 Ti (`PROJECT_AUDIT.md`) |
| 19 | Production deployment, multi-node serving | PLANNED (out of scope) | — |

Test evidence: **59 tests, 59 passed**
(`experiments/results/EXP1_20261028-001156/pytest_output.txt`; re-run during the final audit,
see `README.md`).

## What "50 %" means here

By engineering scope, items 1–9 and a partial item 11 are done. These cover the synopsis's
request generator, heuristic predictor, FCFS, SJF, backend (simulated), metrics, and
automation, together forming one end-to-end pipeline. Items 12–17 (MLFQ, both preemption
modes, memory, ML predictor, priority) are the other half and are not started. Item 18 is
blocked by the environment.

By research questions:

| Research question | Answered? |
|---|---|
| RQ1: does predicted length reduce JCT? | yes, in simulation (EXP2A) |
| RQ2: effect of predictor accuracy | yes, in simulation (EXP4) |
| RQ3: does SJF delay long requests? | yes (EXP3, EXP5) |
| RQ4: can aging/MLFQ reduce starvation? | aging partly (EXP7); MLFQ no |
| RQ5: effect of workload distribution | yes (EXP3) |
| RQ6: latency gain vs **preemption** overhead | **no**: preemption not implemented; only scheduling-decision overhead was measured (EXP6) |
| RQ7: which conclusions survive the simulator → GPU move | discussed qualitatively (`LIMITATIONS.md`), not tested |

## Simulated vs real

Nothing in this repository runs a model, touches a GPU, manages KV-cache blocks, or modifies
vLLM. Every latency and throughput number is produced by the simulator under assumed service
times.
