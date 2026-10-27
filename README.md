# OS-Inspired Scheduling for LLM Inference Requests — a Simulation Study

*A comparative study of FCFS, predictive Shortest-Job-First, and an aging extension for LLM
inference, using output-length prediction.*

> **Read this first.** This project is a **discrete-event simulation**. It does not run a model,
> use a GPU, manage KV-cache memory, or modify vLLM. All latency and throughput numbers come
> from a simulated single execution slot with assumed service times. See
> `docs/IMPLEMENTATION_DECISION.md` and `docs/LIMITATIONS.md`.

## Research question

Can lightweight output-length prediction combined with OS-style scheduling reduce LLM request
completion time and improve responsiveness compared with FCFS, without unacceptable fairness
costs or overhead?

Short answer, in simulation:

- **Mean JCT.** Predictive SJF with a simple heuristic cuts mean JCT by 18–65 % depending on
  load (44.6 % at ρ = 0.8) and keeps 88 % of an oracle's gain.
- **Fairness cost.** Long requests pay for it: worst-case waits are roughly 3–9× FCFS's, and
  with heuristic predictions P99 JCT is *worse* than FCFS at ρ ≥ 0.9.
- **Aging.** Linear aging trades part of the gain for lower worst-case waits.

See `docs/RESULTS.md`.

## What is implemented

| Implemented (tested) | Planned (not implemented) |
|---|---|
| Request model with an enforced state machine | MLFQ with promotion/demotion |
| Seeded synthetic workloads (short-heavy, mixed, long-heavy) | Preemption (recompute and swap) |
| Heuristic length predictor, naive baselines, labelled oracle/noisy references | KV-cache / memory model, batching |
| FCFS and non-preemptive predictive SJF | Learned length predictor |
| Discrete-event single-slot simulator with horizon support | User-priority scheduling |
| Metrics: TTFT, JCT (mean/median/P95/P99), waiting, slowdown, throughput, prediction error | vLLM integration / real GPU runs (**blocked** on this machine) |
| Config-driven paired experiments, analysis, figures | |
| *Extension:* SJF with linear aging | |

Full status with evidence: `docs/IMPLEMENTATION_STATUS.md`.

## Environment

- **Tested on:** Windows 11, Python 3.13.3, CPU only. Any Python ≥ 3.10 with the packages in
  `requirements.txt` should work.
- **Hardware:** no GPU is needed.

## Installation

PowerShell commands, run from this directory (tested):

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python -m pip install -e . --no-deps
```

On Linux/macOS, replace `.venv\Scripts\python` with `.venv/bin/python` (unverified on those
platforms). The remaining commands use plain `python`, meaning the venv's interpreter.

## Configuration

- `config/default.yaml` holds the service-model constants and defaults.
- Each `experiments/configs/*.yaml` overrides them and lists the conditions (policy + predictor),
  mixes, loads, sizes, seeds, an optional horizon, and the hypothesis written before the run.
- `--seeds` overrides the seeds; `--tag dev` marks a development run.

## Commands

Run the unit tests (59 tests):

```bash
python -m pytest -q
```

Run Experiment 1 (simulator validation; about 4 minutes):

```bash
python experiments/scripts/exp1_validate.py
```

Run one evaluation experiment (each takes 5–100 s):

```bash
python -m llm_scheduler.experiment_runner --config experiments/configs/exp2a_fcfs_vs_sjf_load.yaml
```

The other configs are `exp2b_overload_horizon.yaml`, `exp3_workload_composition.yaml`,
`exp4_predictor_quality.yaml`, `exp5_fairness.yaml`, `exp6_workload_size.yaml` and
`exp7_aging_extension.yaml`.

Run everything (EXP1–EXP7) in sequence (about 8 minutes):

```bash
python experiments/scripts/run_all.py
```

Regenerate all tables and figures from the latest completed runs:

```bash
python experiments/scripts/analyze.py
```

Run the command-line demo (fixed workload → FCFS → SJF → comparison → saved outputs → plot):

```bash
python experiments/scripts/demo.py
```

Check that a fresh re-run reproduces a recorded run exactly (tested on EXP2A):

```bash
python experiments/scripts/repro_check.py --config experiments/configs/exp2a_fcfs_vs_sjf_load.yaml --original EXP2A_20261028-001549
```

Rebuild the slides from the saved results. This needs Node.js and `pptxgenjs@3.12.0`; set
`NODE_PATH` to the `node_modules` folder that contains it.

```bash
python presentation/build_data.py
```

```bash
node presentation/build_deck.js
```

## Where things are

| Path | Contents |
|---|---|
| `src/llm_scheduler/` | the package (request, workload, predictor, policies, simulator, metrics, analytical, runner, plotting) |
| `tests/` | unit tests |
| `experiments/configs/` | experiment configs with pre-registered hypotheses |
| `experiments/results/<ID>_<timestamp>/` | raw results: `summary.csv`, `by_category.csv`, `requests/*.csv.gz`, `config.yaml`, `run_meta.json` |
| `experiments/results/analysis/` | derived tables (`tables.md`, CSVs) and `sources.json` (which run fed which output) |
| `experiments/figures/` | the 15 figures |
| `experiments/logs/` | execution logs |
| `docs/` | audit, decision, design, methodology, experiment log, results, limitations, status, literature review, final report, viva Q&A |
| `presentation/` | slide deck, outline, speaker notes |

## Reproducing the main findings

Runs are deterministic given the seeds. Re-running `run_all.py` creates new timestamped
directories; the per-request records should match the originals exactly. EXP1 checks
determinism with a SHA-256 of the records. `analyze.py` always uses the most recent COMPLETED
untagged run of each experiment. Pass `--run EXP2A=<dir>` to pin a specific run.

Wall-clock overhead numbers (EXP6) depend on the machine and will differ.

## Known limitations

Single execution slot with no batching; assumed service times; synthetic prompts and lengths;
a heuristic that shares the generator's features (optimistic accuracy); no preemption or memory
model; 10 seeds per configuration. Details: `docs/LIMITATIONS.md`.
