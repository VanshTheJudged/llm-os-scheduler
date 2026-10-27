# Speaker notes

About one minute per slide (15 slides, about 15 minutes). The same notes are embedded in the deck's notes pane.

### Slide 1: OS-Inspired Scheduling for LLM Inference Requests

Introduce the project in one sentence: we ask whether ordering LLM requests by a predicted output length, the way an operating system orders CPU jobs by burst length, makes requests finish sooner than first-come-first-served, and what it costs. The chips show the idea: the same six requests, wide ones are long generations, orange ones are short. Under FCFS the short ones queue behind the long one; SJF moves them forward. Say up front that everything is a simulation study.

### Slide 2: Under FCFS, short requests wait behind long ones

An LLM generates one token per step, so a request's service time grows with its output length, which ranges from a handful of tokens to thousands. vLLM's paper states it serves requests first-come-first-served. The worked example on the right is the hand-calculated case from Experiment 1: four requests, one second per token. Under FCFS, the two short requests R2 and R3 wait behind R1. Under SJF they go first: mean completion time drops from 6.75 to 6.00 seconds, but R1, the longest of the waiting requests, now waits 7 seconds instead of 4. That trade-off — faster on average, slower for long jobs — is the whole story of the project.

### Slide 3: Research question and objectives

State the research question exactly as written. Then the three objectives, the metrics we judge by, and the scope. The scope box is important for honesty: everything is done in a simulator with one execution slot, seven experiments, ten paired seeds each.

### Slide 4: Where this project sits in prior work

Left: the four OS concepts we borrow. Right: the LLM systems most relevant to us, each verified from the paper's abstract or proceedings page. Two corrections to our original synopsis: vLLM's paper says it preempts the latest-arrived requests first, not the oldest; and S3 uses a learned DistilBERT predictor, not a heuristic. Clairvoyant is the closest setting to ours: predictive SJF admission in front of a serial backend. Our contribution is deliberately modest: a validated, reproducible evaluation of known policies, not a new algorithm.

### Slide 5: System architecture as implemented

Walk the pipeline left to right. A seeded generator produces an immutable workload. At arrival the predictor sees only observable prompt features, never the true length. The policy orders the waiting queue. The simulated execution slot runs prefill, which emits the first token, then decodes the remaining tokens at the true length. Metrics are computed per run, per length category and per request. The dashed boxes are planned and not built. The key design decision for validity: the same workload is replayed under every policy, so all comparisons are paired.

### Slide 6: Implementation status: what is built and tested

About half of the proposed system is built, as one working pipeline rather than half-finished pieces: 9 of the synopsis's 18 components are complete and one, aging, is partial. Everything on the left is unit-tested: 59 passed in 7.59s. The planned half — MLFQ, both preemption modes, memory and batching, a learned predictor, priority classes — is not started; vLLM and GPU work is blocked by the hardware audit. For the demo, run python experiments/scripts/demo.py: it generates a fixed workload, runs FCFS and SJF on it, prints the comparison, saves CSVs and regenerates a plot. In the recorded run (DEMO_20261028-003120) mean JCT went from 56.4 to 29.4 seconds.

### Slide 7: Three policies behind one interface

All three policies share one interface and are binary-heap queues with an ordering key fixed at admission. FCFS orders by arrival. Predictive SJF orders by predicted output length and never interrupts a running request — it is non-preemptive, which matters when comparing with FastServe. The aging extension subtracts a times the waiting time; because that term is the same for every waiting request at a given moment, it is exactly equivalent to a static key, predicted plus a times arrival time. a = 0 is SJF and very large a is FCFS, both unit-tested. MLFQ needs a time-varying policy and preemption, so it is planned. The heuristic predictor at the bottom uses only observable features.

### Slide 8: Paired experiments on a validated simulator

Methodology on the left: three synthetic workload mixes, Poisson arrivals at a target utilisation, ten paired seeds of five thousand requests, and confidence intervals computed across seeds, never across correlated requests. The service-time constants are assumptions; because load is set as utilisation, rescaling them rescales every time metric equally. On the right is why the simulator can be trusted: an independent Lindley recursion for FCFS agrees to 1.3e-9 seconds; simulated mean waits agree with the Pollaczek-Khinchine and Cobham formulas within 2.2% on average over 27 cells; reruns are bit-identical; all unit tests pass.

### Slide 9: Predictive SJF cuts mean JCT by 45% at 80% load

This is the core result, EXP2A, mixed workload. The chart shows mean job completion time against load for FCFS, SJF with the heuristic predictor, and SJF with an oracle that knows true lengths — a reference, not deployable. FCFS blows up near saturation; SJF grows much more slowly. At load 0.8 the heuristic cuts mean JCT by 44.6%, interval 43.0 to 46.1, better on all ten seeds; TTFT by 52.5%; P95 by 40.6%. Across loads the reduction goes from 17.6% to 64.9%. Throughput does not change, because both policies keep the slot busy whenever work is waiting.

### Slide 10: Gains follow ranking quality and size variability

Left, EXP4: mean-JCT improvement over FCFS for each predictor, with its Spearman rank correlation in brackets. Starred bars are references that read the true length plus synthetic noise. The gain degrades smoothly: even sigma 1 keeps most of it. The heuristic captures 88% of the oracle's gain. Two controls matter: random predictions give FCFS's mean, as queueing theory predicts; and prompt length, despite a positive correlation of 0.36, is 9.5% worse than FCFS because it promotes long-form answers, which have short prompts. Right, EXP3: the gain is largest when request sizes vary most — short-heavy has the highest coefficient of variation.

### Slide 11: Long requests pay for the gain

EXP5, mixed workload at load 0.9. Left: mean waiting time by the request's true length category. FCFS treats every category the same, about 85 seconds. SJF cuts short-request waits to about 11 seconds and pushes long-request waits up to 118.4. Right: the worst case per seed for long requests rises from 413 to 1427 seconds with the heuristic and 2710 with the oracle. Three things on the bottom row. The negative result: with heuristic predictions, P99 completion time is worse than FCFS at load 0.9 and above, because the coarse 'very long' prediction class — 5.6% of requests — waits as a block. Prediction error spreads the harm to medium requests. And by slowdown, FCFS is actually the less fair policy for short requests. Nothing in plain SJF bounds a long request's wait.

### Slide 12: Extension: aging trades mean JCT for worst-case wait

EXP7, the one extension we built: SJF with linear aging, mixed workload at load 0.9. Read left to right along the aging rate a, in tokens of priority per second waited. The left chart is the mean-JCT gain over FCFS; the right is the worst-case wait. Both fall together. At a = 1, aging keeps 96% of SJF's mean gain and cuts the worst-case wait by 37%. But no rate we tested reaches FCFS's worst case while keeping most of the gain — aging is a dial, not a cure. The grid was chosen on separate development seeds. This is simulated, and it is not production-quality starvation prevention.

### Slide 13: What these results do not show

Be direct about validity. Biggest threat: a single execution slot. A real server batches many sequences, so short requests can share iterations with long ones and FCFS head-of-line blocking is weaker; our absolute gains are probably overstated for batched serving. Timing constants are assumptions. The workload is synthetic, and our heuristic uses the same features the generator uses, so its accuracy is optimistic — that is why EXP4 sweeps prediction error. We did not implement preemption, so the latency-versus-preemption-overhead question is unanswered. Ten seeds per configuration is enough for means but tails are noisy, and two analyses were post-hoc.

### Slide 14: Next steps toward a real system

The future-work order follows the gaps. First MLFQ with a priority boost, which needs a time-varying policy interface and preemption in the simulator. Then the two preemption modes, recompute and swap, with modelled costs, which finally answers research question six. Then batching with a KV-cache budget to see whether single-slot conclusions survive. Then a learned predictor trained and tested on real prompts with logged lengths. Finally real-hardware validation: a patched vLLM scheduler or an admission proxy in front of a serial backend, replaying the same paired traces.

### Slide 15: Conclusion

Three findings, all from simulation. One: ordering requests by a simple, interpretable length prediction cut mean completion time by 17.6% to 64.9% depending on load, and time to first token by 52.5% at 80% load. Two: the gain depends on ranking long requests correctly; uninformative predictions give nothing, and a misleading feature can be worse than FCFS. Three: long requests pay — worst-case waits grow about 3 to 9 times — and aging trades rather than removes that cost. The practical message: length-aware admission is worth testing on a real batched server, with a starvation guard. Then invite questions.

## Likely viva questions

Copied from `docs/VIVA_QUESTIONS.md`.

All numbers are from simulation; experiment IDs refer to `docs/EXPERIMENT_LOG.md`.

**1. Why use SJF instead of FCFS?**
FCFS makes short requests wait behind long ones (the convoy effect). Serving the shortest
waiting job first minimises mean waiting time among non-preemptive policies when job sizes are
known. In our simulation, SJF with heuristic predictions cut mean JCT by 44.6 % [43.0, 46.1] at
load 0.8 on the mixed workload (EXP2A).

**2. Why is output-length prediction difficult?**
The output length is decided during generation. It depends on the model's sampling, on the
content of the answer, and on stop conditions. The prompt gives only indirect hints (task,
"explain in detail", `max_tokens`). Prior work therefore predicts buckets or rankings rather
than exact lengths (LTR, Clairvoyant).

**3. What is the difference between TTFT and JCT?**
TTFT = first-token time − arrival; it measures responsiveness and here equals waiting + prefill.
JCT = completion time − arrival; it measures the whole request including all decode steps.
JCT is not the absolute completion timestamp.

**4. Why can SJF hurt fairness?**
Long requests are always passed over while shorter ones keep arriving. In EXP5 (mixed,
ρ = 0.9), long requests' mean wait rose from 86 s to 118 s. Their per-seed maximum wait rose
from 413 s to 1,427 s with the heuristic and 2,710 s with the oracle. With imperfect
predictions, some medium requests mispredicted as long were also delayed beyond anything FCFS
produced. By *slowdown*, however, FCFS is the unfair one: short requests wait about 113× their
service time under FCFS and about 14× under SJF.

**5. What is the purpose of aging?**
To prevent starvation by raising a waiting request's priority as it waits. Our extension uses
priority = predicted length − a × waiting time. In EXP7 (mixed), a = 1 token/s cut SJF's
worst-case wait by 37 % while keeping 96 % of its mean-JCT gain. No rate removed the trade-off
entirely.

**6. What is MLFQ?**
A multi-level feedback queue keeps several priority queues. Jobs start high and are demoted as
they use up their time quantum, so short jobs finish quickly without knowing sizes in advance.
A periodic priority boost prevents starvation (OSTEP ch. 8). FastServe adapts it to LLMs with
token-level preemption. **MLFQ is not implemented in this project.**

**7. Why is oracle prediction not a deployable solution?**
It uses the actual output length, which is unknown until generation ends. We use it only as an
upper-bound reference to measure how much of the possible gain a real predictor captures (the
heuristic captured 88 % at ρ = 0.8, EXP4). Oracle conditions are labelled
`predictor_is_reference` in every result file.

**8. How does prediction error affect scheduling?**
In EXP4 the gain fell smoothly as synthetic noise grew: σ = 1 still kept 85 % of the oracle's
gain. What matters is the *ordering* of requests, especially long ones. A random predictor gave
the same mean JCT as FCFS. The prompt-length predictor, despite positive rank correlation
(0.36), made mean JCT 9.5–22.5 % worse because it pushed long-form answers ahead.

**9. Why use a simulator?**
The machine has no vLLM, no WSL or Docker, and a 4 GB GPU (`PROJECT_AUDIT.md`). A simulator
lets us replay identical workloads under every policy, run many seeds, and validate against
queueing theory. Real-hardware experiments would make all three harder.

**10. What are the limitations of simulated timing?**
- Service times come from assumed constants, not measurements.
- A single slot ignores batching, so FCFS's head-of-line blocking is stronger than in a batched
  server and the absolute gains are probably overstated.
- There is no memory model and no interference between requests.
- Relative results are invariant to rescaling all constants (tested), but not to the
  prefill/decode ratio or to batching.

**11. How can preemption increase overhead?**
- **Recompute mode:** stopping a running request throws away its KV cache, so its prefill
  (prompt plus generated tokens) must be redone later.
- **Swap mode:** the KV blocks are copied to CPU memory and back over PCIe.
- **Either way:** frequent preemption wastes compute or bandwidth and can lower throughput.
  Our policies are non-preemptive, so this overhead was not measured.

**12. What is the difference between simulated preemption and real KV-cache preemption?**
A simulated preemption would only move a request between queue states and add a modelled delay.
Real preemption frees or moves actual GPU memory blocks, interacts with the memory allocator,
and has hardware-dependent cost. This project implements neither; `preemption_count` is always 0.

**13. What is the project's actual contribution?**
A reproducible, validated simulation study of established algorithms (FCFS, non-preemptive
predictive SJF, linear aging) on LLM-shaped workloads. It covers four things:
1. a simulator checked against Pollaczek–Khinchine, Cobham, and an independent Lindley
   recursion;
2. a controlled mapping from prediction rank quality to scheduling gain;
3. per-length-category fairness measurements, including a tail regression caused by coarse
   predictions;
4. an aging trade-off curve.

It is not a new algorithm and not a real-system result.

**14. What remains incomplete?**
- **Not implemented:** MLFQ; recompute and swap preemption; a KV-cache/memory model;
  batching; an ML predictor; priority scheduling.
- **Blocked by hardware:** vLLM integration and GPU measurements.

See `IMPLEMENTATION_STATUS.md`.

**15. Which results are supported by experiments?**
Those listed in `RESULTS.md` §9:
- the mean-JCT reductions and their growth with load (EXP2A) and with size variability (EXP3);
- unchanged throughput below capacity (EXP2A/2B);
- worse worst-case waits and, with heuristic predictions, worse P99 at ρ ≥ 0.9 (EXP2A, EXP5);
- the prediction-quality relationship (EXP4);
- size stability (EXP6);
- the aging trade-off (EXP7).

All of these hold in simulation only.

**16. What would be needed to validate the conclusions on real hardware?**
1. A Linux GPU server that can host a representative model.
2. A serving engine with a controllable admission order (a patched vLLM scheduler, or an
   admission proxy in front of a serial backend).
3. Real prompts with logged output lengths to train and test a predictor out of sample.
4. The same paired-trace design with repetitions, recording hardware, model, engine version
   and flags.
5. Batched serving, to check whether single-slot gains survive continuous batching.

**17. (Likely follow-up) Why did SJF's P99 get worse while its P95 improved?**
The heuristic produces coarse predictions. Requests predicted ≥ 1,024 tokens (5.6 % of the
mixed workload) all go to the back of the queue together and wait in FCFS order among
themselves. At ρ ≥ 0.9 those requests make up the slowest 1 % (EXP5-tail diagnostic, post-hoc).
The oracle spreads the delay only over the truly longest requests, so its P99 still improves.

**18. (Likely follow-up) Why is throughput the same for FCFS and SJF?**
Both are work-conserving: the slot is never idle while work waits, so the busy periods and the
last completion time are identical. Only under overload with a cut-off (EXP2B) does SJF finish
more requests (+7.7 % at ρ = 1.1, +22.1 % at ρ = 1.3). It still generates the same number of
tokens.

**19. (Likely follow-up) Is 10 seeds enough?**
For mean JCT, yes: the seed-to-seed SD of the improvement is about 2 points at 5,000 requests,
and the 95 % intervals are about ±1.5 points (EXP6, EXP2A). For P99 and maximum wait the
intervals are much wider, and we report them as such.
