# Methodology

## 1. Evidence types used in this project

| Label | Meaning | Example |
|---|---|---|
| **Simulated** | Output of the discrete-event simulator under the assumed service model | every JCT, TTFT, waiting time and throughput number |
| **Measured (implementation)** | Wall-clock time of this Python code on the audit laptop | `sim_wall_s`, `sched_us_per_decision` in EXP6 |
| **Analytical** | Closed-form queueing results | Pollaczek–Khinchine and Cobham formulas in EXP1 |
| **Hypothesis** | Statement written into the config *before* the run | `hypothesis:` field of every `experiments/configs/*.yaml` |
| **Interpretation** | Our reading of the results | Discussion sections |

No GPU or real inference engine was used. No number in this project is a GPU measurement.

## 2. Workload generation

The workloads are synthetic (no prompt dataset was available or downloaded). Each request
draws a task type from the mix, then a prompt length, a detail flag, a `max_tokens` cap and
an actual output length:

| Task | Prompt median (σ) | Output median (σ) | P(detail requested) |
|---|---|---|---|
| qa | 40 (0.5) | 25 (0.6) | 0.10 |
| chat | 120 (0.7) | 150 (0.7) | 0.25 |
| summarisation | 1000 (0.5) | 100·√(prompt/1000) (0.4) | 0.15 |
| code | 200 (0.6) | 300 (0.8) | 0.30 |
| longform | 80 (0.5) | 700 (0.6) | 0.50 |

Lengths are log-normal with the given median and log-standard-deviation σ. A requested
detailed answer multiplies the output by 1.8. `max_tokens` is uniform over
{512, 1024, 2048, 4096} and truncates the output. Prompts are clipped to [4, 8192] tokens.

| Mix | qa | chat | summarisation | code | longform | Why it is relevant |
|---|---|---|---|---|---|---|
| `short_heavy` | 0.60 | 0.30 | 0.05 | 0.03 | 0.02 | interactive Q&A / chat traffic; few long jobs but very high size variability |
| `mixed` | 0.30 | 0.25 | 0.15 | 0.15 | 0.15 | general-purpose assistant; the primary configuration |
| `long_heavy` | 0.10 | 0.15 | 0.10 | 0.30 | 0.35 | code and long-form generation; long jobs common, lower relative variability |

Measured statistics of the generated samples are in
`experiments/results/analysis/EXP3_workload_stats.csv`.

**Arrivals** are Poisson. The rate is calibrated to the sample:
`rate = ρ / mean(service time)`, so the offered load equals the target utilisation ρ.
Request sizes and inter-arrival gaps come from independent random streams seeded by
`(seed, mix, purpose)`. For a fixed seed the sizes are therefore identical across loads, and
only arrival times are rescaled (common random numbers across the load sweep).

**Length categories** use the *actual* output length: short ≤ 128 tokens, medium 129–512,
long > 512.

## 3. Pairing, seeds and the unit of analysis

- For each (mix, load, size, seed) the runner generates **one** workload and replays it under
  every condition. Differences between conditions are therefore not caused by different
  arrivals or lengths.
- **Evaluation seeds:** 0–9 (10 independent workloads per configuration).
  **Development seeds:** 100–104, used only to choose the aging-rate grid (EXP7 dev run).
  EXP1 additionally uses seeds 1000–1019 for an independent check.
- **Unit of analysis = one workload seed.** Within a run, requests are strongly correlated
  (they share queues and busy periods), so requests are *not* treated as independent
  observations. For a metric `M` and condition `X`:

```text
per-seed relative improvement r_s = (M_FCFS,s − M_X,s) / M_FCFS,s × 100      (lower-is-better metrics)
                               r_s = (M_X,s − M_FCFS,s) / M_FCFS,s × 100      (throughput)
reported: mean of r_s over seeds, with a two-sided 95 % Student-t interval (df = seeds − 1),
          and the number of seeds on which X beat FCFS
```

- The t-interval describes variation across workload realisations of the *same simulated
  model*. It says nothing about real hardware, real prompts, or other service models. No
  significance tests beyond these intervals are claimed.

## 4. Metric definitions

| Metric | Definition | Requests included |
|---|---|---|
| Waiting time | start of service − arrival | started requests |
| TTFT | first-token time − arrival = waiting + prefill | completed |
| JCT | completion time − arrival (not the absolute completion timestamp) | completed |
| Mean / median / P95 / P99 JCT | statistics of JCT within one run; P95 needs ≥ 200 values, P99 ≥ 1,000, else n/a | completed |
| Slowdown | JCT / service time (1 = no waiting) | completed |
| Observation window | [first arrival, last completion] or [first arrival, horizon] | — |
| Request throughput | completed requests / window | — |
| Token throughput | output tokens generated inside the window / window (includes partial output at a horizon) | all |
| Utilisation | busy time inside the window / window | — |
| Prediction MAE | mean of abs(predicted − actual), in tokens | requests with a prediction |
| Prediction bias | mean (predicted − actual) | ditto |
| MdAPE | median of abs(predicted − actual) / actual × 100 | ditto |
| Spearman / Kendall | rank correlation between predicted and actual length | ditto |
| Gain captured | (JCT_FCFS − JCT_X) / (JCT_FCFS − JCT_oracle) × 100, seed-averaged mean JCT | EXP4 |
| Starvation indicator | number of requests whose wait exceeds the maximum FCFS wait on the same workload | EXP5 |
| Jain's index | (Σx)² / (n Σx²) over per-request slowdowns within one run; 1 = all equal. Sensitive to outliers and to the choice of x; used only as a secondary indicator | EXP5 |
| Scheduling overhead | Python wall-clock time in admit + select per dispatched request (µs) | EXP6 |

TBT (time between tokens) is constant (`decode_per_token_s`) in a single-slot model, so it is
not reported.

## 5. Experiments

| ID | Question | Design |
|---|---|---|
| EXP1 | Is the simulator correct? | unit tests; hand-calculated 4-request example; simulated mean wait vs Pollaczek–Khinchine (FCFS) and Cobham (SJF) for 3 mixes × ρ ∈ {0.5, 0.7, 0.9} × 5 seeds × 50,000 requests; FCFS vs an independent Lindley recursion on 60 fresh workloads; determinism hash |
| EXP2A | FCFS vs SJF | mixed; ρ ∈ {0.5, 0.6, 0.7, 0.8, 0.9, 0.95}; 10 seeds × 5,000 requests; FCFS, SJF-heuristic, SJF-oracle (reference) |
| EXP2B | Throughput under overload | mixed; ρ ∈ {1.1, 1.3}; horizon = last arrival; FCFS, SJF-heuristic |
| EXP3 | Workload composition | 3 mixes × ρ ∈ {0.8, 0.9}; FCFS, SJF-heuristic, SJF-oracle |
| EXP4 | Predictor quality | mixed; ρ ∈ {0.8, 0.9}; FCFS; SJF with oracle, noisy oracle σ ∈ {0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3}, heuristic, max_tokens, prompt_length, random |
| EXP5 | Fairness | 3 mixes; ρ = 0.9; FCFS, SJF-heuristic, SJF-oracle; all per-request records saved |
| EXP6 | Workload size | mixed; ρ = 0.8; n ∈ {500, …, 100,000}; FCFS, SJF-heuristic |
| EXP7 | Extension: aging | mixed and long_heavy; ρ = 0.9; aging rate a ∈ {0.1, …, 100} tokens/s; grid chosen on development seeds |

Hypotheses were written into each config before its evaluation run. Outcomes, including the
ones that contradict a hypothesis, are recorded in `EXPERIMENT_LOG.md`.

## 6. Analytical expectations used for interpretation

- **Pollaczek–Khinchine (M/G/1 FCFS):** W = λE[S²] / (2(1 − ρ)). Mean wait grows with the
  second moment of service time and diverges as ρ → 1.
- **Cobham (non-preemptive priority classes):** W_k = W₀ / ((1 − σ_{k−1})(1 − σ_k)) with
  W₀ = λE[S²]/2. Short classes see only the load of shorter classes.
- **Size-blind non-preemptive policies:** in M/G/1, every non-preemptive, work-conserving
  policy that chooses the next job without using its size (FCFS, random order, LCFS) has the
  same mean waiting time (Harchol-Balter, 2013; Kleinrock's conservation law). An
  uninformative predictor should therefore reproduce FCFS's mean, and only size information
  can lower it.
- **Work conservation:** all implemented policies keep the slot busy whenever work is waiting,
  so the busy periods, and hence throughput, are identical when every request completes.
