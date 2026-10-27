# Viva Questions and Answers

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
