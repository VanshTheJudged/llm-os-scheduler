# Limitations and Threats to Validity

## 1. Simulator vs a real inference server (external validity: the largest threat)

| Real LLM server | This simulator | Consequence |
|---|---|---|
| Continuous / iteration-level batching of many sequences | one request at a time (single slot) | Short requests cannot "slip in" beside long ones, so FCFS head-of-line blocking is *stronger* here than in a batched server. Absolute gains are likely overstated for batched serving. |
| Per-token latency depends on batch size and context length | constant decode cost per token | No interference between co-running requests; TBT is constant and not reported |
| KV-cache memory limits admission and forces preemption | no memory model | Memory-driven effects (vLLM swap/recompute, S³-style packing) are absent |
| Preemption (recompute or swap) with real overhead | none: all policies non-preemptive | Preemption-overhead trade-offs (research question 6) are **not** answered |
| Prefill and decode may be chunked or disaggregated | prefill then decode, sequentially | — |

All timing numbers follow from assumed constants (prefill 10 ms + 0.2 ms/token, decode
25 ms/token). Load is expressed as utilisation, so relative results are invariant to a uniform
rescaling of these constants (tested). They are **not** invariant to the prefill/decode
*ratio*, which was not varied.

## 2. Synthetic workload (construct and external validity)

- **No real prompts.** Task types, length distributions and the detail flag are invented
  (log-normal, see `METHODOLOGY.md`). No real dataset or trace was used.
- **Optimistic heuristic.** The heuristic uses the same features that drive the generator:
  task type, detail flag, prompt length for summaries, and `max_tokens`. Its constants differ
  from the generator's, but the *structure* matches by construction. Real prompts do not come
  labelled with a task type. Real accuracy is likely lower, and the EXP4 noise sweep shows
  how much the gain would shrink.
- **Arrivals.** Poisson arrivals only; no bursts, diurnal patterns, or correlated sessions.
- **Fixed `max_tokens` grid.** The uniform choice over {512, …, 4096} creates point masses
  in the length distribution.

## 3. Statistical limitations (conclusion validity)

- **Ten seeds per configuration.** The intervals are Student-t intervals across workload
  realisations of the same model; they do not cover model or parameter uncertainty.
- **Tail metrics are noisy.** P99 uses 50 tail observations per 5,000-request run. Maximum
  wait is a single observation per run.
- **Development choices.** The aging grid was chosen on development seeds 100–104, separate
  from the evaluation seeds 0–9. The heuristic's constants were hand-set and not tuned on
  evaluation seeds. All tested configurations are reported.
- **Post-hoc analyses.** The EXP1 bias diagnostic and the EXP5 tail-composition analysis were
  added after seeing results. They are explanations consistent with the data, not
  pre-specified tests.
- **No significance tests** beyond the reported intervals are claimed.

## 4. Fairness measurement

- **The starvation indicator is a relative definition** chosen for this project: a request
  waiting longer than the largest FCFS wait on the same workload. With finite workloads no
  request waits forever. Unbounded starvation under sustained arrivals of short jobs is a
  known theoretical risk of SJF, but it is not demonstrated here.
- **Fairness conclusions depend on the metric.** By absolute wait, SJF is unfair to long
  requests; by slowdown, FCFS is unfair to short requests.
- **Length categories** use fixed token thresholds (128 and 512).

## 5. Implementation scope (what is missing)

The following are **not** implemented:
- MLFQ;
- preemption (any mode);
- KV-cache management;
- swap to CPU memory;
- multi-slot or batched execution;
- a learned predictor;
- user-priority scheduling;
- any vLLM integration;
- production deployment.

The aging policy is a simple linear-aging extension evaluated only in simulation. It is not
production-quality starvation prevention. See `IMPLEMENTATION_STATUS.md`.

## 6. Measurement of overhead

`sched_us_per_decision` and `predict_us_per_request` are Python `perf_counter`
measurements on a laptop (Intel i5-10300H). They include instrumentation overhead and are
subject to OS noise; one EXP6 configuration showed about 2× variation that was not
investigated. They say nothing about the overhead of a production C++/CUDA scheduler.

## 7. What would be needed to validate on real hardware

1. A Linux machine with a supported GPU and enough memory for a representative model (for
   example a 7B model in fp16 needs well over the 4 GB available here).
2. A serving engine whose admission order can be controlled, such as a vLLM version with a
   pluggable or patchable scheduler, or a serial backend with an admission proxy as in
   Clairvoyant.
3. Real prompts with recorded output lengths, to train or evaluate the predictor out of
   sample.
4. The same paired design: identical traces replayed under each policy, several repetitions,
   and hardware, model, engine version and flags recorded with every run.
5. Batched serving, to test whether the single-slot gains survive continuous batching.
