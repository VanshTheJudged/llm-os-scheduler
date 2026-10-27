# Literature Review

Citation style: author list, year, title, venue. Each entry was checked on 2026-10-28
against the publisher page, the arXiv abstract page, or the proceedings page linked in the
entry. Only abstracts, proceedings metadata and (for vLLM) the paper's scheduling section
were read; claims below are limited to what those sources state. Reported speed-ups are the
papers' own numbers on their own hardware and are **not** comparable with this project's
simulated numbers.

## 1. LLM serving systems and schedulers

### Orca: iteration-level scheduling
**Citation.** Gyeong-In Yu, Joo Seong Jeong, Geon-Woo Kim, Soojeong Kim, Byung-Gon Chun.
2022. *Orca: A Distributed Serving System for Transformer-Based Generative Models.* 16th
USENIX Symposium on Operating Systems Design and Implementation (OSDI '22), pp. 521–538.
<https://www.usenix.org/conference/osdi22/presentation/yu>

- **Problem.** Generative models emit one token per model iteration, so request-level
  batching makes early-finishing requests wait for the whole batch.
- **Technique.** Iteration-level scheduling (the scheduler runs one model iteration at a
  time and can admit or retire requests between iterations) and selective batching.
- **Relation to this project.** Orca establishes the per-iteration decision point that
  modern schedulers use. This project's simulator makes decisions only when a request
  finishes (one slot, non-preemptive), which is the request-level regime Orca moved away
  from.
- **Differences / limits of comparison.** No batching, no model, no GPU here. Orca's
  results (e.g. a reported 36.9× throughput gain over FasterTransformer at equal latency on
  GPT-3 175B) cannot be compared with simulated numbers.

### vLLM and PagedAttention
**Citation.** Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao
Yu, Joseph E. Gonzalez, Hao Zhang, Ion Stoica. 2023. *Efficient Memory Management for Large
Language Model Serving with PagedAttention.* 29th ACM Symposium on Operating Systems
Principles (SOSP '23). arXiv:2309.06180. <https://arxiv.org/abs/2309.06180>

- **Problem.** KV-cache memory is wasted by fragmentation and over-reservation, which
  limits batch size.
- **Technique.** PagedAttention stores the KV cache in fixed-size blocks, analogous to OS
  virtual-memory paging. The scheduling section states that vLLM uses FCFS for all requests,
  that the *latest-arrived* requests are preempted first, and that preempted sequences are
  recovered by either swapping KV blocks to CPU memory or recomputing the KV cache.
- **Relation.** vLLM's FCFS admission is the baseline this project studies. Its two recovery
  modes are the "swap" and "recompute" modes in the synopsis, and neither is implemented here.
- **Correction to the synopsis.** The synopsis says vLLM preempts "oldest-first". The SOSP
  paper says the latest requests are preempted first. Later vLLM releases may differ; that
  was not checked.
- **Limits.** No memory model exists in this project, so none of vLLM's memory findings can
  be examined.

### FastServe: token-level preemption with a skip-join MLFQ
**Citation.** Bingyang Wu, Yinmin Zhong, Zili Zhang, Shengyu Liu, Fangyue Liu, Yuanhang
Sun, Gang Huang, Xuanzhe Liu, Xin Jin. 2026. *FastServe: Iteration-Level Preemptive
Scheduling for Large Language Model Inference.* 23rd USENIX Symposium on Networked Systems
Design and Implementation (NSDI '26). Earlier preprint: Wu et al. 2023, *Fast Distributed
Inference Serving for Large Language Models*, arXiv:2305.05920.
<https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang>

- **Problem.** Run-to-completion scheduling causes head-of-line blocking behind long jobs.
- **Technique.** Preemption at the granularity of output tokens, with a *skip-join*
  multi-level feedback queue. A job's input length chooses its starting queue, skipping
  higher queues to reduce demotions.
- **Relation.** This is the closest prior design to the synopsis's MLFQ component. MLFQ is
  planned, not implemented, in this project.
- **Limits.** The reported gains differ between preprint and NSDI versions (the NSDI
  abstract reports up to 6.1× throughput over vLLM). No preemption exists here, so FastServe's
  central mechanism is outside this evaluation.

### QLLM: priority-aware preemption for MoE inference
**Citation.** Mohammad Siavashi, Faezeh Keshmiri Dindarloo, Dejan Kostić, Marco Chiesa.
2025. *Priority-Aware Preemptive Scheduling for Mixed-Priority Workloads in MoE
Inference.* arXiv:2503.09304; related ACM DOI 10.1145/3721146.3721956 (the venue behind this
DOI was **not verified**). <https://arxiv.org/abs/2503.09304>

- **Problem.** Iteration-level FCFS lets best-effort jobs delay latency-sensitive ones.
- **Technique.** Expert-level preemption in mixture-of-experts inference, prioritising
  latency-sensitive requests' TTFT.
- **Relation.** Represents the "priority + preemption" thread named in the synopsis. The
  `user_priority` field exists in this project's request model but no policy uses it.

## 2. Output-length prediction for scheduling

### S³: predicting output length to size memory allocations
**Citation.** Yunho Jin, Chun-Feng Wu, David Brooks, Gu-Yeon Wei. 2023. *S³: Increasing GPU
Utilization during Generative Inference for Higher Throughput.* Advances in Neural
Information Processing Systems 36 (NeurIPS 2023). arXiv:2306.06000.
<https://proceedings.neurips.cc/paper_files/paper/2023/hash/3a13be0c5dae69e0f08065f113fb10b8-Abstract.html>

- **Problem.** Reserving KV memory for the maximum sequence length forces small batches.
- **Technique.** Predict each request's output length and use the prediction to schedule
  and allocate memory. Mispredicted sequences that overflow are preempted, and the predictor
  is retrained. The arXiv version describes a fine-tuned DistilBERT predictor.
- **Correction to the synopsis.** The synopsis calls S³'s predictor a "heuristic estimate".
  The paper describes a learned (fine-tuned DistilBERT) model.
- **Relation / difference.** S³ optimises **throughput** through memory packing. This project
  optimises **completion time** through ordering, with no memory model. Its throughput is
  unchanged by construction when all requests complete (EXP2A).

### LTR: learning to rank output lengths
**Citation.** Yichao Fu, Siqi Zhu, Runlong Su, Aurick Qiao, Ion Stoica, Hao Zhang. 2024.
*Efficient LLM Scheduling by Learning to Rank.* Advances in Neural Information Processing
Systems 37 (NeurIPS 2024). arXiv:2408.15792.
<https://proceedings.neurips.cc/paper_files/paper/2024/hash/6c8985579293e0209bdaa4f21bb1d237-Abstract.html>

- **Problem.** Exact output length is hard to predict, but SJF needs only an *ordering*.
- **Technique.** A small auxiliary model (e.g. OPT-125M) is trained to rank requests by
  length. Kendall's τ against the oracle order measures ranking quality. The ranking
  approximates SJF/SRTF in a serving system.
- **Relation.** The finding most relevant here: EXP4 measures Spearman and Kendall rank
  correlation for every predictor. It finds that mean JCT tracks rank correlation, and that
  the heuristic can have a large absolute error (MAE) while ranking well. This agrees with
  LTR's premise in a simulated setting. It is not a replication of LTR.

### Clairvoyant: predictive SJF admission for serial backends
**Citation.** Aravind Sundaresan. 2026. *Clairvoyant: Predictive Shortest-Job-First
Admission for Serial LLM Inference.* arXiv:2606.07248 (preprint, v2 July 2026; no venue
listed). <https://arxiv.org/abs/2606.07248>

- **Problem.** Serial backends (one request at a time, e.g. on edge devices) with FCFS
  admission make short queries wait behind long generations. Continuous batching may need too
  much memory there.
- **Technique.** A sidecar proxy that reorders admission by predicted length, using an
  XGBoost classifier over 19 lexical features (abstract reports sub-millisecond prediction).
- **Relation.** This is the closest match to this project's setting: a **single serial slot**
  with non-preemptive predictive SJF. Its reported real-hardware results (short-request P50
  latency reductions of about 70 %) are a useful external reference point. This project
  cannot confirm them.

### TRAIL: embedding-based remaining-length prediction
**Citation.** Rana Shahout, Eran Malach, Chunwei Liu, Weifan Jiang, Minlan Yu, Michael
Mitzenmacher. 2024. *Don't Stop Me Now: Embedding Based Scheduling for LLMs.*
arXiv:2410.01035. <https://arxiv.org/abs/2410.01035>

- **Technique.** Reuses the target LLM's internal embeddings to predict *remaining* length
  after each token, with a prediction-based SRPT variant and limited preemption.
- **Relation.** Shows a direction this project does not take: predictions refined during
  generation, combined with preemption.

## 3. Classical scheduling and queueing theory

**Cobham (1954).** Alan Cobham. *Priority Assignment in Waiting Line Problems.* Journal of
the Operations Research Society of America 2(1):70–76. DOI 10.1287/opre.2.1.70. Derives
mean waiting time per class in a single-server non-preemptive priority queue with arbitrary
service-time distributions. **Used in EXP1** to predict the mean wait of SJF exactly. (A
correction, vol. 3 no. 4 p. 547, concerns permanently saturated systems, which are not used
in the validation.)

**Kleinrock (1965).** Leonard Kleinrock. *A Conservation Law for a Wide Class of Queueing
Disciplines.* Naval Research Logistics Quarterly 12:181–192. The load-weighted sum of
class waiting times is invariant across a class of work-conserving disciplines. **Used to
interpret EXP4**: a size-blind ordering (random predictor) cannot change FCFS's mean wait.

**Harchol-Balter (2013).** Mor Harchol-Balter. *Performance Modeling and Design of Computer
Systems: Queueing Theory in Action.* Cambridge University Press. DOI
10.1017/CBO9781139226424. A textbook treatment of M/G/1 scheduling (FCFS, SJF, priority,
size-based policies) and of heavy-tailed job sizes. It is the background for the
Pollaczek–Khinchine formula and the analysis approach used here.

**Arpaci-Dusseau & Arpaci-Dusseau.** *Operating Systems: Three Easy Pieces.* Arpaci-Dusseau
Books, online edition <https://pages.cs.wisc.edu/~remzi/OSTEP/>, chapter 8 "Scheduling: The
Multi-Level Feedback Queue". This is the textbook source for MLFQ, including the priority
boost used against starvation. The project's planned MLFQ would follow this design.

## 4. How this project relates

| Thread | Prior work | This project |
|---|---|---|
| Iteration-level / batched serving | Orca, vLLM | not modelled (single slot) |
| Predicted-length ordering | S³, LTR, Clairvoyant, TRAIL | predictive SJF with a heuristic predictor, plus a controlled prediction-error sweep |
| Preemption, MLFQ | FastServe, QLLM, vLLM swap/recompute | planned, not implemented |
| Starvation avoidance | OSTEP (MLFQ priority boost) | linear aging, implemented as one extension |

**Scoped contribution.** The algorithms here (FCFS, non-preemptive SJF, linear aging) are
long established. The contribution is a **reproducible, validated simulation study** of
them on LLM-shaped workloads. It covers the following:

1. A simulator checked against closed-form queueing results.
2. A controlled sweep showing how prediction error (expressed as rank correlation) maps to
   completion-time gain.
3. Per-length-category fairness measurements.
4. An aging trade-off curve.

It does not propose a new algorithm. It also does not validate anything on real hardware.

## 5. Sources still to verify

- The venue of QLLM's ACM DOI (10.1145/3721146.3721956).
- Whether current vLLM releases still preempt latest-arrived requests first. Only the 2023
  paper was checked.
- Full-text details (methods, exact losses, exact datasets) of S³, LTR, Clairvoyant and
  TRAIL. Only abstracts and summaries were read.
