# OS-Inspired Scheduling for Concurrent LLM Inference Requests Using Output-Length Prediction

*A comparative simulation study of FCFS, predictive Shortest-Job-First, and fairness-aware
aging*

Final-year B.Tech project report. Team members, supervisor, department and institution are not
recorded in this repository and should be added by the authors.

---

## Abstract

LLM inference servers commonly admit requests first-come, first-served (FCFS). Short requests
then wait behind long generations, the convoy effect that classical operating systems address
with Shortest-Job-First (SJF) and aging. We evaluate whether a lightweight, interpretable
output-length predictor can make SJF useful for LLM requests, and at what fairness cost. Because
the available machine cannot run a real serving stack (no vLLM, no WSL or Docker, a 4 GB
laptop GPU), we built a discrete-event simulator of a single non-preemptive execution slot.
We validated it against the Pollaczek–Khinchine and Cobham queueing formulas and an independent
Lindley recursion (agreement to 1.3 × 10⁻⁹ s).

On synthetic workloads (10 paired seeds × 5,000 requests per configuration), predictive SJF
with a heuristic predictor reduced mean job completion time (JCT) by 17.6 % at load 0.5 and
64.9 % at load 0.95 (44.6 % [43.0, 46.1] at load 0.8). That is 88 % of the gain of an oracle
that knows true lengths. The gain tracked the *rank* correlation of predictions. A random
predictor gave no gain, and a positively correlated prompt-length predictor made JCT worse than
FCFS.

The cost fell on long requests: worst-case waits were roughly 3–9× FCFS's. With heuristic
predictions, P99 JCT was worse than FCFS at load ≥ 0.9, because coarse predictions placed a
block of requests at the back of the queue. Throughput was unchanged below capacity. A linear
aging extension traded mean JCT for worst-case wait smoothly but did not remove the trade-off.
All results are simulated; none are GPU measurements.

## 1. Introduction

Autoregressive LLMs generate one token per model step, so a request's service time grows with
its output length. Output lengths span three orders of magnitude, from one-word answers to
multi-thousand-token code or essays. In a FCFS queue, a short request that arrives behind a long
one waits for the whole long generation. Operating systems faced the same problem with CPU
bursts and answered it with SJF (minimum mean waiting time), MLFQ (learning job lengths
online), and aging (bounding starvation). The obstacle for LLMs is that output length is not
known in advance; it must be predicted.

This project brings these OS disciplines to LLM request scheduling and measures their effect
under controlled conditions. It implements and evaluates about half of the proposed system: the
request model, workload generator, heuristic predictor, FCFS, non-preemptive predictive SJF, a
simulated backend, the metrics, and experiment automation, plus one extension (aging). MLFQ,
preemption, KV-cache modelling and real-engine integration remain future work.

## 2. Problem statement

Design a request scheduler that predicts each request's output length at admission and orders
requests by OS-style policies. Evaluate its effect on responsiveness (TTFT), completion time
(mean, median and tail JCT), throughput and fairness relative to FCFS. Evaluate also how the
effect depends on prediction quality, load and workload composition.

## 3. Research objectives

**Main question.** Can lightweight output-length prediction and OS-inspired scheduling improve
completion time and responsiveness versus FCFS without unacceptable fairness or overhead costs?

| Secondary question | Addressed by | Outcome |
|---|---|---|
| RQ1 Does predicted length reduce mean JCT? | EXP2A, EXP3 | Yes, in simulation |
| RQ2 How does predictor accuracy matter? | EXP4 | Gain tracks rank quality; degrades smoothly |
| RQ3 Does SJF delay long requests? | EXP3, EXP5 | Yes; worst case roughly 3–9× FCFS |
| RQ4 Can aging/MLFQ reduce starvation? | EXP7 | Aging: partly (trade-off). MLFQ: not implemented |
| RQ5 Does the workload distribution matter? | EXP3 | Yes; larger gain with more size variability |
| RQ6 Latency vs preemption overhead? | — | **Not answered**: no preemption implemented; only decision overhead measured (EXP6) |
| RQ7 Which conclusions survive a real GPU? | §20 | Discussed, not tested |

## 4. Background and related work

Verified citations and comparisons are in `LITERATURE_REVIEW.md`.

**Serving systems.**
- Orca (Yu et al., OSDI 2022) introduced iteration-level scheduling.
- vLLM (Kwon et al., SOSP 2023) introduced PagedAttention. Its paper states that vLLM serves
  requests FCFS and preempts the *latest* arrivals first, recovering them by swap or recompute.
  (The synopsis said "oldest-first"; we correct this.)
- FastServe (Wu et al., NSDI 2026) uses token-level preemption with a skip-join MLFQ.
- QLLM (Siavashi et al., 2025) adds priority-aware preemption for MoE inference.

**Length prediction.**
- S³ (Jin et al., NeurIPS 2023) predicts length with a fine-tuned DistilBERT to pack memory for
  throughput. (The synopsis described it as heuristic.)
- LTR (Fu et al., NeurIPS 2024) learns to *rank* lengths and approximates SJF.
- Clairvoyant (Sundaresan, arXiv 2026) applies predictive SJF admission with an XGBoost lexical
  classifier in front of *serial* backends. This is the setting closest to ours.
- TRAIL (Shahout et al., arXiv 2024) refines remaining-length predictions from model embeddings,
  with limited preemption.

**Theory.**
- Cobham (1954): mean waits for non-preemptive priority queues.
- Kleinrock (1965): conservation law.
- Harchol-Balter (2013): M/G/1 scheduling.
- Arpaci-Dusseau (OSTEP, ch. 8): MLFQ.

**Scoped contribution.** FCFS, non-preemptive SJF and linear aging are established algorithms.
Our contribution is a validated, reproducible evaluation of them on LLM-shaped workloads. Its
parts are:
- a controlled map from prediction rank quality to scheduling gain;
- per-length-category fairness analysis, including a tail regression caused by coarse
  predictions;
- an aging trade-off curve.

## 5. System architecture

```text
config ─► experiment runner ─► workload generator ─► immutable RequestSpecs (replayed per condition)
                                                          │
            ┌──────────── discrete-event simulator, one execution slot ─────────────┐
            │ ARRIVAL ─► predictor(features only) ─► policy.admit                   │
            │ slot free ─► policy.select_next ─► prefill ─► FIRST_TOKEN             │
            │            ─► decode (actual length) ─► COMPLETION                    │
            └───────────────────────────────┬───────────────────────────────────────┘
                                            ▼
                         metrics (run / category / request) ─► CSV ─► analysis ─► tables, figures
```

Module responsibilities, request state machine and event semantics are in `SYSTEM_DESIGN.md`.
Two design points matter for validity:
1. **Information separation.** A predictor receives only `PromptFeatures`, which has no
   actual-length field. Oracle predictors must be constructed from an explicit ground-truth map
   and are flagged as references.
2. **Paired replay.** Each workload is an immutable list replayed under every condition, with
   fresh per-run state.

## 6. Implementation scope and completion status

| Status | Components |
|---|---|
| Completed and tested (59 unit tests) | request model; workload generator (3 mixes); heuristic predictor + naive and reference predictors; FCFS; non-preemptive predictive SJF; single-slot DES with horizon; metrics; analytical validators; experiment runner; analysis and plots |
| Partial | aging: linear aging only, as the single extension |
| Planned | MLFQ; recompute and swap preemption; KV-cache/memory and batching; ML predictor; priority scheduling |
| Blocked | vLLM integration and GPU measurements (environment) |

Details and evidence: `IMPLEMENTATION_STATUS.md`.

## 7. Simulator assumptions

- **One execution slot, non-preemptive** (an M/G/1 queue under Poisson arrivals).
- **Service time:** prefill = 0.010 s + 0.0002 s × prompt tokens, which emits the first token;
  then 0.025 s per further output token. These constants are **assumed**, not measured. Load is
  set as utilisation ρ, and uniform rescaling of the constants rescales every time metric
  identically (unit-tested).
- **Event order at equal times:** first-token, then completion, then arrival. Scheduling
  decisions are made after all same-time events.
- **No batching, memory, preemption or inter-request interference.** TBT is constant and not
  reported.

## 8. Length-prediction methodology

**Heuristic** (deployable, interpretable):

```text
prediction = prior[task] × sqrt(prompt / 1024)   [summarisation only]
                         × 2                     [if a detailed answer is requested]
clipped to [1, max_tokens]
priors: qa 32, chat 128, summarisation 128, code 256, long-form 512 tokens
```

The constants were set by hand as round numbers before evaluation and differ from the
generator's parameters. However, the heuristic uses the generator's features, so its accuracy
(Spearman 0.88, MAE 121 tokens, bias −54 tokens on the mixed workload) is optimistic.

**Naive baselines:** prompt length; `max_tokens`; random (uninformative).

**References (not deployable):** oracle (actual length); noisy oracle, actual × exp(σz) with
z ~ N(0, 1) and σ from 0.1 to 3. These isolate the effect of error. Randomised predictors hash
(seed, request id), so predictions do not depend on call order.

## 9. Scheduling algorithms

| Policy | Rule | Tie-break | Preemptive |
|---|---|---|---|
| FCFS | earliest arrival | request id | no |
| Predictive SJF | smallest predicted length | earlier arrival, then id | no |
| SJF + linear aging (extension) | smallest predicted − a × waiting time ≡ predicted + a × arrival | arrival, id | no |

The aging rule reduces to a static key because a × t is common to every waiting request at a
given time t. So all three policies run on a binary heap with O(log n) per operation.
a = 0 gives SJF and a → ∞ gives FCFS (unit-tested).

## 10. Experimental methodology

- **Pairing.** One workload per (mix, load, size, seed), replayed under every condition.
- **Seeds.** Evaluation seeds 0–9. Development seeds 100–104 were used only to pick the aging
  grid. Seeds 1000–1019 were used for an independent validation check.
- **Unit of analysis.** One workload seed. Requests within a run are correlated, so they are
  not treated as independent.
- **Statistics.** For each seed, relative improvement r = (M_FCFS − M_X) / M_FCFS × 100 (sign
  reversed for throughput). We report the mean and a two-sided 95 % Student-t interval over
  seeds, plus the number of seeds where X beat FCFS. No other significance claims are made.
- **Pre-registration.** Hypotheses were written into each config before its evaluation run.
- **Records.** Every run writes a timestamped directory with config, raw CSVs, metadata (code
  hash, versions, command) and a log (`EXPERIMENT_LOG.md`).

| ID | Purpose | Design |
|---|---|---|
| EXP1 | Validation | Hand example; P-K and Cobham on 3 mixes × 3 loads × 5 seeds × 50k requests; Lindley recursion on 60 fresh workloads; determinism hash; unit tests |
| EXP2A | FCFS vs SJF | Mixed, ρ 0.5–0.95 |
| EXP2B | Overload throughput | ρ ∈ {1.1, 1.3}, horizon = last arrival |
| EXP3 | Composition | 3 mixes × ρ ∈ {0.8, 0.9} |
| EXP4 | Predictor quality | 14 conditions × ρ ∈ {0.8, 0.9} |
| EXP5 | Fairness | 3 mixes, ρ = 0.9, all per-request records |
| EXP6 | Size | n = 500 … 100,000 |
| EXP7 | Aging (extension) | a ∈ {0.1 … 100} tokens/s, 2 mixes, ρ = 0.9 |

## 11. Workload generation

Five task types (qa, chat, summarisation, code, long-form) with log-normal prompt and output
lengths, a "detail requested" flag (×1.8 output) and a `max_tokens` cap. The three mixes differ
in task proportions (`METHODOLOGY.md` §2):

| Mix | Mean output (tokens) | Median | Service CV | Short / medium / long |
|---|---|---|---|---|
| short_heavy | 123 | 46 | 1.69 | 74 / 23 / 4 % |
| mixed | 282 | 131 | 1.39 | 49 / 36 / 14 % |
| long_heavy | 490 | 357 | 1.03 | 25 / 45 / 30 % |

Arrivals are Poisson with rate ρ / mean service time of the sample. Size and arrival streams are
independent, so request sizes are identical across loads for a given seed.

## 12. Metrics and definitions

- **Waiting** = start − arrival.
- **TTFT** = first token − arrival (= waiting + prefill).
- **JCT** = completion − arrival.
- **Slowdown** = JCT / service time.
- **Throughput** = completed requests (or generated tokens) / [first arrival, last completion
  or horizon].
- **Percentiles** are reported only with ≥ 200 (P95) or ≥ 1,000 (P99) observations.
- **Prediction error:** MAE, bias, MdAPE, and Spearman and Kendall rank correlation.
- **Gain captured** = (FCFS − X) / (FCFS − oracle).
- **Starvation indicator** = requests waiting longer than the largest FCFS wait on the same
  workload.
- **Jain's index** over per-request slowdown (secondary).

Full table: `METHODOLOGY.md` §4.

## 13. Results

Detailed tables and all 15 figures: `RESULTS.md`; raw tables: `experiments/results/analysis/tables.md`.

### 13.1 Validation (EXP1)
- **Tests and hand example:** 59/59 unit tests pass, and the hand example matches exactly.
- **Determinism:** identical seeds give identical records (SHA-256).
- **Lindley recursion:** FCFS matches it to 1.3 × 10⁻⁹ s.
- **Queueing formulas:** simulated mean waits agree with P-K and Cobham within 2.2 % (mean
  absolute error over 27 cells). Per-seed deviations reach ±14 % at ρ = 0.9, the expected
  finite-sample scatter near saturation.

### 13.2 FCFS vs SJF (EXP2A)

| Mixed, ρ = 0.8 | FCFS | SJF-heuristic | Improvement | SJF-oracle |
|---|---|---|---|---|
| Mean JCT (s) | 46.8 | 25.9 | 44.6 % [43.0, 46.1] (10/10) | 23.0 (50.6 %) |
| Median JCT (s) | 30.7 | 12.8 | 58.2 % | 12.2 |
| P95 JCT (s) | 151.1 | 88.5 | 40.6 % [34.6, 46.6] | 75.2 |
| P99 JCT (s) | 223.7 | 226.6 | −3.0 % [−17.1, 11.1] | 182.1 |
| Mean TTFT (s) | 39.8 | 18.8 | 52.5 % | 16.0 |
| Max wait (s) | 280 | 749 | −174 % (0/10) | 1,203 |
| Throughput | 0.112 req/s, 31.7 tok/s | identical | 0 % | identical |

![Mean JCT vs load](../experiments/figures/fig02_exp2a_mean_jct_vs_load.png)

*Figure 1. Mean JCT vs load (mixed; 95 % CI bands).* The mean-JCT reduction grows from 17.6 %
(ρ = 0.5) to 64.9 % (ρ = 0.95). P95 improves at every load. **P99 with heuristic predictions is
worse than FCFS at ρ = 0.9 (−40.5 % [−71.8, −9.1]) and ρ = 0.95 (−92.2 %).**

![JCT summary](../experiments/figures/fig05_exp2a_jct_summary_load08.png)

*Figure 2. Median, mean, P95 and P99 JCT at ρ = 0.8.* The gain is concentrated in the body of
the distribution.

### 13.3 Throughput (EXP2A, EXP2B)

![Throughput](../experiments/figures/fig06_exp2b_throughput.png)

*Figure 3. Completed requests/s and tokens/s.* The two policies are identical below capacity.
Under overload with a cut-off at the last arrival, SJF finishes 7.7 % (ρ = 1.1) and 22.1 %
(ρ = 1.3) more requests while generating 0.05–0.16 % fewer tokens.

### 13.4 Workload composition (EXP3)

![By mix](../experiments/figures/fig07_exp3_reduction_by_mix.png)

*Figure 4. Mean-JCT reduction by mix.*

| | short_heavy | mixed | long_heavy |
|---|---|---|---|
| Reduction at ρ = 0.8 (heuristic) | 48.7 % | 44.6 % | 32.2 % |
| Reduction at ρ = 0.9 (heuristic) | 63.1 % | 57.7 % | 43.4 % |
| Service-time CV | 1.69 | 1.39 | 1.03 |

The gain grows with size variability. At ρ = 0.8, SJF-heuristic cut short-request mean waits by
71–78 % and raised long-request mean waits by 18–71 % across the three mixes (`RESULTS.md`
Figure 8). At ρ = 0.9 the corresponding ranges were 84–88 % and 22–94 %.

### 13.5 Predictor quality (EXP4)

![Rank vs JCT](../experiments/figures/fig09_exp4_rank_vs_jct.png)

*Figure 5. Mean JCT relative to FCFS vs Spearman correlation of predictions.*

| Predictor (ρ = 0.8) | Spearman | Mean-JCT improvement | Gain captured |
|---|---|---|---|
| oracle (ref.) | 1.00 | 50.6 % | 100 % |
| noisy σ = 0.5 / 1.0 / 3.0 (ref.) | 0.94 / 0.80 / 0.39 | 48.2 / 43.2 / 27.7 % | 95 / 85 / 55 % |
| heuristic | 0.88 | 44.6 % | 88 % |
| max_tokens | 0.03 | 8.6 % | 17 % |
| prompt_length | 0.36 | −9.5 % | −19 % |
| random | 0.00 | 0.8 % [−2.1, 3.7] | 1 % |

### 13.6 Fairness (EXP5)

![Wait ECDF](../experiments/figures/fig11_exp5_wait_ecdf.png)

*Figure 6. Waiting-time CDFs by category (mixed, ρ = 0.9).*

| Mixed, ρ = 0.9 | FCFS | SJF-heuristic | SJF-oracle |
|---|---|---|---|
| Mean wait short / medium / long (s) | 85 / 85 / 86 | 11 / 26 / 118 | 10 / 16 / 96 |
| Per-seed max wait, long requests (s) | 413 | 1,427 | 2,710 |
| Requests per seed exceeding FCFS's max wait | 0 | 60.8 (4.7 of them medium) | 30.4 (all long) |
| Mean slowdown of short requests | 113 | 14.3 | 13.5 |

### 13.7 Workload size (EXP6)
The reduction stayed between 42.5 % and 46.6 % from 500 to 100,000 requests. Its across-seed SD
fell from 6.3 to 0.6 points. Measured on this laptop, Python scheduling cost was about 0.7 µs per
decision and the heuristic prediction about 0.5 µs per request.

### 13.8 Extension: aging (EXP7)

![Aging](../experiments/figures/fig15_exp7_aging_tradeoff.png)

*Figure 7. Mean JCT vs worst-case wait across aging rates (ρ = 0.9).*

| Mixed | SJF | a = 1 | a = 3 | a = 10 | FCFS |
|---|---|---|---|---|---|
| Mean-JCT improvement vs FCFS | 57.7 % | 55.5 % | 41.2 % | 18.3 % | 0 |
| Max wait (s) | 1,432 | 899 | 562 | 451 | 436 |

## 14. Figures and tables

Fifteen figures are in `experiments/figures/` (Figures 1–15 in `RESULTS.md`) and are generated
by `experiments/scripts/analyze.py`. Every figure states that its data are simulated. Derived
tables are in `experiments/results/analysis/`, and `sources.json` maps each figure to its run
directory.

## 15. Statistical analysis

- **Comparisons.** All are paired by seed. Mean-JCT improvements have narrow intervals
  (±1.5–3 points) and were positive on 10/10 seeds in every EXP2A/EXP3 cell.
- **Tail metrics.** These have wide intervals; for example, P99 at ρ = 0.8 was −3.0 %
  [−17.1, 11.1], which is inconclusive.
- **EXP6 seed variability.** The seed-to-seed SD of the improvement shrinks roughly with
  1/√n: 6.3 points at n = 500, 2.2 at 5,000, 0.6 at 100,000.
- **What the intervals mean.** They describe variability across workload realisations of one
  synthetic model under one service model. They do not quantify uncertainty about real
  hardware or real prompts.

## 16. Discussion

1. **Why SJF helps.** In a single non-preemptive slot, FCFS's mean wait is set by the second
   moment of service time (Pollaczek–Khinchine). Serving short jobs first stops them from paying
   for long ones. The larger the size variability and the higher the load, the larger the
   effect. That is exactly what EXP2A and EXP3 show.
2. **Ordering is what matters.** SJF uses predictions only to order requests. The noise sweep,
   the heuristic's position on it, and the random-predictor control together show that the gain
   is governed by how well long and short requests are separated, not by absolute error. This
   supports the ranking-based framing of LTR and Clairvoyant, here in a controlled simulation.
3. **A single correlation number can mislead.** The prompt-length predictor ranks qa requests
   correctly but promotes long-form answers. The mis-ordering of long jobs dominates mean
   waiting time.
4. **The fairness cost is real and depends on the definition.**
   - SJF moves waiting onto long requests and lengthens the worst case.
   - Imperfect predictions also spread the delay onto medium (and occasionally short) requests
     that were mispredicted as long.
   - By slowdown, FCFS is the less fair policy.
   - A deployment would need to choose which notion of fairness it must protect.
5. **Throughput is not the benefit.** Work conservation fixes token throughput. SJF improves
   *latency* and, only under overload with abandonment, the *count* of finished requests.
6. **Aging is a dial, not a cure.** Linear aging recovers worst-case waiting only by giving up
   mean-JCT gain. It also raised P95 at intermediate rates.

## 17. Failure cases and negative results

- **P99 regression.** SJF-heuristic's P99 JCT was worse than FCFS at ρ ≥ 0.9. A post-hoc
  diagnostic attributes this to the coarse ≥ 1,024-token prediction class.
- **Maximum waiting time.** Max wait was worse than FCFS for every SJF condition, in every
  configuration.
- **Prompt-length predictor.** It made mean JCT 9.5–22.5 % worse than FCFS.
- **`max_tokens` as a predictor.** It gave a small mean gain (8.6–12.2 %) but worse P95.
- **Aging.** It raised P95 JCT above plain SJF at intermediate rates, and no rate achieved
  both goals.
- **A bug in our own test.** The first test run had one failure, caused by a wrong hand
  calculation in the test itself (see `EXPERIMENT_LOG.md`). The simulator was not changed.
- **Validation scatter.** EXP1 run 1 showed a +5–8 % deviation at ρ = 0.9 for long_heavy. An
  independent Lindley check showed this was sampling noise, not a simulator bias.

## 18. Threats to validity

**Internal validity.** Simulator correctness is supported by EXP1, and paired replay removes
workload confounding.

**Construct validity.**
- The heuristic shares the generator's features.
- "Starvation" is a relative indicator.
- Length categories use fixed thresholds.

**External validity**, the dominant threat:
- a single slot with no batching;
- assumed service times;
- synthetic prompts;
- no memory or preemption.

In a continuously batched server, short requests can share iterations with long ones, so FCFS's
head-of-line blocking is weaker and SJF's gains are likely smaller.

**Conclusion validity.**
- There are 10 seeds per configuration, and tail metrics are noisy.
- Two analyses are post-hoc and are labelled as such.

## 19. Limitations

See `LIMITATIONS.md`. In brief, the study has these limitations:
- simulation only;
- a single non-preemptive slot;
- assumed timing constants, with the prefill/decode ratio never varied;
- synthetic Poisson workloads;
- an optimistic heuristic;
- no MLFQ, preemption, memory model, ML predictor or priority classes;
- overhead measured only for a Python prototype on a laptop.

## 20. Future work

1. **MLFQ** with demotion by tokens generated relative to the predicted length, plus a
   periodic priority boost. This needs a time-varying policy interface and preemption.
2. **Preemption modes** in the simulator: recompute (re-prefill cost) and swap (a PCIe
   transfer-cost model). Measure the latency-versus-overhead trade-off (RQ6).
3. **Batching and memory:** multiple slots or continuous batching with a KV-cache budget, to
   test whether single-slot conclusions survive.
4. **Learned predictor:** for example gradient boosting on lexical features or a small ranking
   model, trained and evaluated out of sample on real prompts with logged output lengths.
5. **Real-system validation:** a Linux GPU server with a patchable vLLM scheduler, or an
   admission proxy in front of a serial backend, replaying the same paired traces.
6. **Sensitivity:** bursty arrivals, the prefill/decode cost ratio, and deadline-based or
   bounded-wait aging.

## 21. Conclusion

In a validated single-slot simulation, ordering LLM requests by a simple, interpretable
output-length prediction cut mean completion time and time-to-first-token substantially:
44.6 % and 52.5 % respectively at 80 % load. It captured most (88 %) of what perfect knowledge
would give, and the scheduling decisions themselves were cheap. The gain depends on ranking long
requests correctly, grows with load and size variability, and vanishes with uninformative
predictions.

The gain is not free. Long requests wait longer, worst-case waits grow several-fold, and with
coarse predictions the extreme tail can become worse than FCFS. Linear aging lets an operator
choose a point on that trade-off but does not eliminate it. These findings come from a simulator
with assumed timing and synthetic workloads. They motivate, but do not replace, an evaluation on
a real batched inference server.

## 22. References

1. G.-I. Yu, J. S. Jeong, G.-W. Kim, S. Kim, B.-G. Chun. *Orca: A Distributed Serving System for Transformer-Based Generative Models.* OSDI 2022, pp. 521–538.
2. W. Kwon, Z. Li, S. Zhuang, Y. Sheng, L. Zheng, C. H. Yu, J. E. Gonzalez, H. Zhang, I. Stoica. *Efficient Memory Management for Large Language Model Serving with PagedAttention.* SOSP 2023. arXiv:2309.06180.
3. B. Wu, Y. Zhong, Z. Zhang, S. Liu, F. Liu, Y. Sun, G. Huang, X. Liu, X. Jin. *FastServe: Iteration-Level Preemptive Scheduling for Large Language Model Inference.* NSDI 2026. Preprint arXiv:2305.05920.
4. Y. Jin, C.-F. Wu, D. Brooks, G.-Y. Wei. *S³: Increasing GPU Utilization during Generative Inference for Higher Throughput.* NeurIPS 2023. arXiv:2306.06000.
5. Y. Fu, S. Zhu, R. Su, A. Qiao, I. Stoica, H. Zhang. *Efficient LLM Scheduling by Learning to Rank.* NeurIPS 2024. arXiv:2408.15792.
6. A. Sundaresan. *Clairvoyant: Predictive Shortest-Job-First Admission for Serial LLM Inference.* arXiv:2606.07248, 2026 (preprint).
7. R. Shahout, E. Malach, C. Liu, W. Jiang, M. Yu, M. Mitzenmacher. *Don't Stop Me Now: Embedding Based Scheduling for LLMs.* arXiv:2410.01035, 2024.
8. M. Siavashi, F. Keshmiri Dindarloo, D. Kostić, M. Chiesa. *Priority-Aware Preemptive Scheduling for Mixed-Priority Workloads in MoE Inference.* arXiv:2503.09304, 2025 (venue of the related ACM DOI 10.1145/3721146.3721956 not verified).
9. A. Cobham. *Priority Assignment in Waiting Line Problems.* Journal of the Operations Research Society of America 2(1):70–76, 1954.
10. L. Kleinrock. *A Conservation Law for a Wide Class of Queueing Disciplines.* Naval Research Logistics Quarterly 12:181–192, 1965.
11. M. Harchol-Balter. *Performance Modeling and Design of Computer Systems: Queueing Theory in Action.* Cambridge University Press, 2013.
12. R. H. Arpaci-Dusseau, A. C. Arpaci-Dusseau. *Operating Systems: Three Easy Pieces.* Arpaci-Dusseau Books, online edition, ch. 8.

## 23. Reproduction instructions

From `llm-os-scheduler/`, using the commands tested in the final audit (see `README.md`):

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -e . --no-deps
.venv\Scripts\python -m pytest -q
.venv\Scripts\python experiments/scripts/run_all.py
.venv\Scripts\python experiments/scripts/analyze.py
```

The runs are deterministic, so new run directories reproduce the per-request records exactly.
Only the wall-clock overhead figures (EXP6) depend on the machine.
