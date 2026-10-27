# Experiment Log

Status vocabulary: PLANNED · RUNNING · COMPLETED · FAILED · BLOCKED.
All times are local (2026-10-28) and are taken from the run-directory names.

**Common settings.**
- **Environment:** Windows 11, Python 3.13.3, project venv `.venv` installed from
  `requirements.txt`; numpy 2.2.6, pandas 3.0.5, scipy 1.18.1, matplotlib 3.11.2, PyYAML 6.0.3.
- **Simulator:** single non-preemptive slot. Service model: prefill 0.010 s +
  0.0002 s/prompt-token, decode 0.025 s/token (assumed values, see `SYSTEM_DESIGN.md` §3).
- **Repetitions:** 5,000 requests per workload and 10 evaluation seeds (0–9), unless stated.
- **Code version:** the directory is not a git repository. Every run records a SHA-256 prefix
  of `src/llm_scheduler/*.py` as `code_hash` in `run_meta.json`:
  - `529c4e7089cc` — EXP7-dev and both EXP1 runs;
  - `d4d9a2a9d87c` — EXP2A–EXP7.

  The only difference between the two is that `plotting.py` was added (figure code, not
  used by the simulator). The simulation code was identical for every run.
- **Hypotheses** were written into each config file before its evaluation run.

## Experiment index

| ID | Status | Config / script | Results directory | Log | Figures |
|---|---|---|---|---|---|
| EXP7-dev | COMPLETED (development) | `experiments/configs/exp7_aging_extension.yaml` (original grid) `--seeds 100..104 --tag dev` | `experiments/results/EXP7_dev_20261028-000452/` | `experiments/logs/EXP7_dev_20261028-000452.log` | — |
| EXP1 (run 1) | COMPLETED (superseded) | `experiments/scripts/exp1_validate.py` | `experiments/results/EXP1_20261028-000609/` (+ `bias_diagnostic.csv`) | `experiments/logs/EXP1_console.log` | — |
| EXP1 (run 2) | COMPLETED | same script, with the Lindley check added | `experiments/results/EXP1_20261028-001156/` | `experiments/logs/run_all_console.log` | fig01 |
| EXP2A | COMPLETED | `experiments/configs/exp2a_fcfs_vs_sjf_load.yaml` | `experiments/results/EXP2A_20261028-001549/` | `experiments/logs/EXP2A_20261028-001549.log` | fig02–fig05 |
| EXP2B | COMPLETED | `experiments/configs/exp2b_overload_horizon.yaml` | `experiments/results/EXP2B_20261028-001612/` | `experiments/logs/EXP2B_20261028-001612.log` | fig06 |
| EXP3 | COMPLETED | `experiments/configs/exp3_workload_composition.yaml` | `experiments/results/EXP3_20261028-001619/` | `experiments/logs/EXP3_20261028-001619.log` | fig07, fig08 |
| EXP4 | COMPLETED | `experiments/configs/exp4_predictor_quality.yaml` | `experiments/results/EXP4_20261028-001639/` | `experiments/logs/EXP4_20261028-001639.log` | fig09, fig10 |
| EXP5 | COMPLETED | `experiments/configs/exp5_fairness.yaml` | `experiments/results/EXP5_20261028-001705/` | `experiments/logs/EXP5_20261028-001705.log` | fig11–fig13 |
| EXP5-tail | COMPLETED (post-hoc diagnostic) | `experiments/scripts/diag_tail.py` | `experiments/results/analysis/EXP5_tail_composition.csv` | console | — |
| EXP6 | COMPLETED | `experiments/configs/exp6_workload_size.yaml` | `experiments/results/EXP6_20261028-001732/` | `experiments/logs/EXP6_20261028-001732.log` | fig14 |
| EXP7 | COMPLETED (extension) | `experiments/configs/exp7_aging_extension.yaml` | `experiments/results/EXP7_20261028-001913/` | `experiments/logs/EXP7_20261028-001913.log` | fig15 |
| Analysis | COMPLETED | `experiments/scripts/analyze.py` | `experiments/results/analysis/` (`tables.md`, CSVs, `sources.json`) | console | all 15 in `experiments/figures/` |
| DEMO | COMPLETED (demonstration, not an experiment) | `experiments/scripts/demo.py` | `experiments/results/DEMO_20261028-003120/` | `experiments/logs/DEMO_console.log` | `demo_wait_by_category.png` in the run directory |
| AUDIT-repro | COMPLETED | `experiments/scripts/repro_check.py` on EXP2A | `experiments/results/_reproduction/EXP2A_repro_20261028-004731/` (`repro_report.json`) | `experiments/logs/final_audit_repro.txt` | — |
| AUDIT-tests | COMPLETED | `python -m pytest -q` | — | `experiments/logs/final_audit_pytest.txt` | — |

EXP1–EXP7 were run in sequence by `experiments/scripts/run_all.py`; its console output is in
`experiments/logs/run_all_console.log`.

---

## Pre-experiment events

- **Smoke test** (not a recorded experiment): one development seed (100) was run on each mix
  to check that the pipeline executes. Its numbers are not reported anywhere.
- **First unit-test run: 1 FAILED, 57 passed.** The failure was
  `test_horizon_records_unfinished_requests`. It expected 2 generated tokens for a request cut
  off at t = 6.5 s. The hand calculation was wrong: the request starts at 5, emits token 1
  at 6, and token 2 would come at 7. **Corrective action:** fixed the test's expectation to
  1 token. The simulator was not changed. Rerun: 58 passed. A Lindley-recursion test was
  added later (59 tests).

---

## EXP7-dev — aging-rate grid selection (development run)

1. **ID / name:** EXP7-dev, aging grid exploration.
2. **Date / time:** 2026-10-28 00:04:52.
3. **Question:** over what range of aging rates does linear aging change SJF's behaviour?
4. **Hypothesis:** none (exploratory).
5. **Code:** `529c4e7089cc`.
6. **Config:** `exp7_aging_extension.yaml`, original grid a ∈ {0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100}.
7. **Workload:** mixed and long_heavy, synthetic.
8. **Requests / seeds:** 5,000 × development seeds 100–104.
9. **Policies / predictor:** FCFS, SJF-heuristic, SJF-aging (heuristic predictor).
10. **Assumptions:** load 0.9, common settings.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp7_aging_extension.yaml --seeds 100 101 102 103 104 --tag dev`
12. **Completed:** yes (110 runs, 9.6 s).
13. **Outputs:** `experiments/results/EXP7_dev_20261028-000452/`.
14. **Observed:** a ≤ 0.1 gave results identical to SJF on both mixes. The transition from
    SJF-like to FCFS-like behaviour lay between a ≈ 0.3 and a ≈ 30.
15. **Baseline comparison:** not used for reporting.
16. **Interpretation:** the original grid wasted three points.
17. **Limitations:** development seeds only; these results are not reported as findings.
18. **Next action:** changed the evaluation grid to {0.1, 0.3, 0.5, 1, 2, 3, 5, 10, 30, 100}
    (recorded as a comment in the config) and ran EXP7 on evaluation seeds 0–9.

## EXP1 — simulator validation

1. **ID / name:** EXP1, simulator validation.
2. **Date / time:** run 1 at 00:06:09; run 2 at 00:11:56 (reported).
3. **Question:** does the simulator implement FCFS and SJF correctly?
4. **Hypothesis:** simulated mean waits agree with Pollaczek–Khinchine (FCFS) and Cobham (SJF)
   within sampling error; the hand example matches exactly; runs are deterministic.
5. **Code:** `529c4e7089cc`.
6. **Config:** constants inside `experiments/scripts/exp1_validate.py`.
7. **Workload:**
   - the 4-request hand example;
   - generated workloads, 3 mixes × ρ ∈ {0.5, 0.7, 0.9}.
8. **Requests / seeds:**
   - analytical check: 50,000 requests × seeds 0–4;
   - Lindley check: 50,000 requests × seeds 1000–1019 per mix at ρ = 0.5.
9. **Policies / predictors:** FCFS; SJF-oracle; SJF-heuristic.
10. **Assumptions:** common settings. The hand example uses prefill 1 s and decode 1 s/token.
11. **Command:** `python experiments/scripts/exp1_validate.py`
12. **Completed:** yes, both runs (status COMPLETED in `run_meta.json`).
13. **Outputs:** `pytest_output.txt`, `hand_example.csv`, `analytical_check.csv`,
    `lindley_check.csv` (run 2 only), `determinism.json`, `run_meta.json`.
14. **Observed (run 2):**
    - **Unit tests:** 59 passed.
    - **Hand example:** all 8 request rows match the hand calculation. Mean JCT is 6.75 s
      (FCFS) and 6.00 s (SJF-oracle).
    - **Determinism:** two identical runs gave identical SHA-256 of the per-request records.
    - **Lindley recursion:** the maximum difference from the simulator over 60 workloads was
      1.3 × 10⁻⁹ s.
    - **P-K on fresh seeds:** mean relative error −0.15 % to −0.72 % per mix (standard error
      about 0.4–0.6 %).
    - **Analytical check (5 seeds):** mean absolute relative error over the 27 cells is 2.17 %.
      Per-seed deviation reaches ±14 % at ρ = 0.9.
15. **Baseline comparison:** n/a.
16. **Interpretation:**
    - **Run 1** showed a consistent +5 to +8 % deviation for long_heavy at ρ = 0.9.
      `exp1_bias_diagnostic.py` (post-hoc) found that recomputing P-K with each sample's
      *realised* arrival rate roughly halves that deviation (to +3.6 %), so part of it is
      arrival-rate sampling noise.
    - To rule out a simulator bug, an independent Lindley-recursion implementation of FCFS
      was added (run 2). It agrees to floating-point precision, and P-K agrees within
      −0.7 % ± 0.4 % on 20 fresh seeds.
    - **Conclusion:** the FCFS and SJF logic is correct. The remaining deviations at ρ = 0.9
      are finite-sample effects: slow convergence at high load and a start-empty transient.
      They are not bias.
17. **Limitations:** this validates queueing logic only, not the realism of the service model.
    Cobham validation of SJF holds because the implemented SJF is a static-priority policy.
18. **Next action:** proceed to EXP2–EXP7.

## EXP2A — FCFS vs predictive-SJF across load

1. **ID / name:** EXP2A, FCFS vs SJF across load.
2. **Date / time:** 00:15:49.
3. **Question:** does ordering by predicted output length reduce mean and tail JCT?
4. **Hypothesis:** SJF-heuristic lowers mean JCT at every load; the reduction grows with load;
   throughput is unchanged.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp2a_fcfs_vs_sjf_load.yaml`.
7. **Workload:** mixed.
8. **Requests / seeds:** 5,000 × 0–9; ρ ∈ {0.5, 0.6, 0.7, 0.8, 0.9, 0.95}.
9. **Policies / predictors:** FCFS; SJF-heuristic; SJF-oracle (reference).
10. **Assumptions:** common settings.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp2a_fcfs_vs_sjf_load.yaml`
12. **Completed:** yes (180 runs, 20.8 s).
13. **Outputs:** `summary.csv`, `by_category.csv`, `requests/` (load 0.8, all seeds).
    Derived: `analysis/EXP2A_paired.csv`.
14. **Observed (paired, mean [95 % CI] over 10 seeds):**
    - **Mean JCT at ρ = 0.8:** FCFS 46.8 s, SJF-heuristic 25.9 s (−44.6 % [43.0, 46.1],
      10/10 seeds), SJF-oracle 23.0 s (−50.6 %).
    - **Mean-JCT reduction by load (heuristic):** 17.6 % at ρ = 0.5 rising to 64.9 % at
      ρ = 0.95.
    - **P95 JCT:** −40.6 % at ρ = 0.8.
    - **P99 JCT (heuristic):** better at ρ ≤ 0.7 (+6 to +8 %); inconclusive at 0.8 (−3.0 %
      [−17.1, 11.1]); **worse** at 0.9 (−40.5 % [−71.8, −9.1]) and 0.95 (−92.2 %).
    - **Maximum wait:** 174 % higher than FCFS at ρ = 0.8 (0/10 seeds better).
    - **Throughput:** identical to FCFS (0.0 %).
15. **Baseline comparison:** see 14.
16. **Interpretation:**
    - The mean-JCT hypothesis is supported, and so is "throughput unchanged".
    - Tail behaviour is *not* uniformly better. With heuristic predictions the slowest 1 %
      gets worse at high load (explained in EXP5-tail).
17. **Limitations:** single slot; synthetic workload; heuristic shares features with the
    generator.
18. **Next action:** EXP2B for throughput under overload; EXP5-tail for the P99 result.

## EXP2B — overload with finite horizon

1. **ID / name:** EXP2B, overload throughput.
2. **Date / time:** 00:16:12.
3. **Question:** how do completed-request and token throughput differ when ρ > 1?
4. **Hypothesis:** SJF completes more requests within the horizon; token throughput stays
   within a few percent of FCFS.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp2b_overload_horizon.yaml`.
7. **Workload:** mixed.
8. **Requests / seeds:** 5,000 × 0–9; ρ ∈ {1.1, 1.3}; horizon = last arrival.
9. **Policies / predictors:** FCFS; SJF-heuristic.
10. **Assumptions:** common settings. Requests unfinished at the horizon are reported as
    incomplete.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp2b_overload_horizon.yaml`
12. **Completed:** yes (40 runs, 5.2 s).
13. **Outputs:** `summary.csv`, `by_category.csv`; derived `analysis/EXP2B_paired.csv`.
14. **Observed:**
    - **Completed requests:** +7.7 % [6.9, 8.4] at ρ = 1.1 and +22.1 % [20.8, 23.4] at
      ρ = 1.3.
    - **Incomplete requests:** −76 % at both loads.
    - **Token throughput:** −0.05 % and −0.16 %.
    - **Utilisation:** ≈ 0.996–0.998 for both.
15. **Baseline comparison:** see 14.
16. **Interpretation:** hypothesis supported. SJF converts the same busy time into more
    *finished* requests by finishing short ones. It does not generate more tokens.
17. **Limitations:**
    - Mean JCT of completed requests (−83 % and −95 %) is survivorship-biased and should not
      be read as a latency win.
    - The horizon choice affects all numbers.
18. **Next action:** none.

## EXP3 — workload composition

1. **ID / name:** EXP3, workload composition.
2. **Date / time:** 00:16:19.
3. **Question:** does SJF's benefit depend on the length distribution?
4. **Hypothesis:** SJF reduces mean JCT on all three mixes; short requests gain most; long
   requests wait longer than under FCFS.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp3_workload_composition.yaml`.
7. **Workload:** short_heavy, mixed, long_heavy.
8. **Requests / seeds:** 5,000 × 0–9; ρ ∈ {0.8, 0.9}.
9. **Policies / predictors:** FCFS; SJF-heuristic; SJF-oracle.
10. **Assumptions:** common settings.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp3_workload_composition.yaml`
12. **Completed:** yes (180 runs, 17.5 s).
13. **Outputs:** `summary.csv`, `by_category.csv`; derived `analysis/EXP3_*.csv`.
14. **Observed (SJF-heuristic, mean-JCT reduction):**
    - **At ρ = 0.8:** short_heavy 48.7 %, mixed 44.6 %, long_heavy 32.2 %.
    - **At ρ = 0.9:** 63.1 %, 57.7 %, 43.4 % respectively.
    - **Workload variability:** service-time CV is 1.69 / 1.39 / 1.03 for the three mixes.
    - **Mean waits by category (mixed, ρ = 0.8):**

      | Category | FCFS | SJF-heuristic |
      |---|---|---|
      | short | 39.6 s | 9.5 s |
      | medium | 39.7 s | 17.9 s |
      | long | 40.1 s | 52.8 s |
    - **Long requests waited longer under SJF-heuristic in every mix and load.** Under the
      oracle, long_heavy long requests waited the *same* at ρ = 0.8 (48.5 s vs 48.5 s) and
      *less* at ρ = 0.9 (96.1 s vs 110.1 s).
15. **Baseline comparison:** see 14. SJF-heuristic beat FCFS on mean JCT on 10/10 seeds in
    every cell. Weakest cell: P95 improvement on long_heavy at ρ = 0.9 was 15.9 % [4.6, 27.3], better on 8/10 seeds.
16. **Interpretation:**
    - Supported, with one refinement. The gain shrinks as the length distribution becomes
      less variable (lower CV), as queueing theory predicts.
    - "Long requests wait longer" holds for the heuristic. It does not always hold for the
      oracle, because the "long" category (> 512 tokens) contains many moderately long
      requests that overtake the very longest.
17. **Limitations:** the categories use fixed token thresholds; the mixes are synthetic.
18. **Next action:** EXP5 for a deeper fairness analysis.

## EXP4 — predictor quality

1. **ID / name:** EXP4, predictor quality.
2. **Date / time:** 00:16:39.
3. **Question:** how does prediction error affect SJF?
4. **Hypothesis:**
   - mean JCT rises monotonically with noise σ;
   - a random predictor matches FCFS;
   - a predictor anti-correlated with length can be worse than FCFS.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp4_predictor_quality.yaml`.
7. **Workload:** mixed.
8. **Requests / seeds:** 5,000 × 0–9; ρ ∈ {0.8, 0.9}.
9. **Policies / predictors:** FCFS; SJF with:
   - oracle;
   - noisy oracle σ ∈ {0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3} (synthetic, reference only);
   - heuristic;
   - max_tokens;
   - prompt_length;
   - random.
10. **Assumptions:** noisy predictions are generated artificially from the actual length. This
    isolates the effect of error; it does not validate a predictor.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp4_predictor_quality.yaml`
12. **Completed:** yes (280 runs, 23.1 s).
13. **Outputs:** `summary.csv`, `by_category.csv`; derived `analysis/EXP4_*.csv`.
14. **Observed (ρ = 0.8; gain captured relative to the oracle):**

    | Predictor | Spearman | Mean-JCT change vs FCFS | Gain captured |
    |---|---|---|---|
    | oracle | 1.00 | −50.6 % | 100 % |
    | σ = 0.5 | 0.94 | — | 95 % |
    | σ = 1.0 | 0.80 | — | 85 % |
    | σ = 3.0 | 0.39 | — | 55 % |
    | heuristic | 0.881 (MAE 121 tokens, bias −54) | −44.6 % | 88 % |
    | max_tokens | 0.03 | −8.6 % (P95 +15 % worse) | — |
    | prompt_length | 0.36 | **+9.5 % worse** (+22.5 % worse at ρ = 0.9) | — |
    | random | 0.00 | +0.8 % [−2.1, 3.7] (ρ = 0.9: −1.4 % [−4.5, 1.7]) | — |
15. **Baseline comparison:** see 14.
16. **Interpretation:**
    - (a) **Supported:** mean JCT is monotone in σ at both loads.
    - (b) **Supported:** random ≈ FCFS, as the size-blind conservation result predicts.
    - (c) **Refined:** prompt_length was worse than FCFS although its *overall* rank
      correlation is positive. It systematically promotes long-form requests, which have
      short prompts and long outputs. A single correlation number does not capture whether
      the *long* jobs are mis-ordered, and that is what dominates waiting time.
    - The heuristic sits on the noisy-oracle curve at its Spearman value. Ranking quality,
      not absolute error, drives the gain (its MAE is about the same as σ = 0.5, yet its
      gain matches σ ≈ 0.75).
17. **Limitations:**
    - Noise is multiplicative log-normal and independent of request type; real errors are
      likely correlated with task type.
    - The heuristic's accuracy is optimistic (see `LIMITATIONS.md`).
18. **Next action:** none.

## EXP5 — fairness and long-request delay

1. **ID / name:** EXP5, fairness.
2. **Date / time:** 00:17:05.
3. **Question:** does SJF disproportionately delay long requests?
4. **Hypothesis:** short requests wait much less, long requests wait longer, and maximum wait
   is higher than under FCFS.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp5_fairness.yaml`.
7. **Workload:** all three mixes.
8. **Requests / seeds:** 5,000 × 0–9; ρ = 0.9.
9. **Policies / predictors:** FCFS; SJF-heuristic; SJF-oracle.
10. **Assumptions:** common settings.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp5_fairness.yaml`
12. **Completed:** yes (90 runs, 24.7 s; all per-request records saved).
13. **Outputs:** `summary.csv`, `by_category.csv`, `requests/`; derived `analysis/EXP5_*.csv`.
14. **Observed (mixed):**
    - **Mean wait by category:**

      | Category | FCFS | SJF-heuristic |
      |---|---|---|
      | short | 85.0 s | 11.0 s |
      | medium | 85.2 s | 25.6 s |
      | long | 86.3 s | 118.4 s |
    - **Per-seed maximum wait of long requests:** 413 s (FCFS), 1,427 s (heuristic),
      2,710 s (oracle).
    - **Starvation indicator** (requests per seed waiting longer than the maximum FCFS wait):
      - heuristic: 60.8, mostly long, but 4.7 medium;
      - oracle: 30.4, all long;
      - short_heavy, heuristic: 1.1 *short* requests per seed.
    - **Slowdown (JCT / service time):** for short requests, FCFS 113 vs SJF 14. Jain's index
      over slowdowns: FCFS 0.165 vs SJF-heuristic 0.219.
    - **Completion rate:** 1.0 everywhere, because there is no horizon.
15. **Baseline comparison:** see 14.
16. **Interpretation:**
    - Supported. SJF transfers waiting from short to long requests, and its worst-case wait is
      roughly 3–9× FCFS's (per-seed maxima).
    - **Prediction error spreads the harm:** with the heuristic, mispredicted medium (and
      occasionally short) requests also starve.
    - **Fairness depends on the definition:** by absolute wait SJF is unfair to long
      requests, while by slowdown FCFS is far more unfair to short ones.
17. **Limitations:** "starvation" is a relative indicator defined here. With a finite workload
    no request waits forever.
18. **Next action:** EXP7 (aging); EXP5-tail.

## EXP5-tail — composition of the slowest 1 % (post-hoc diagnostic)

1. **ID / name:** EXP5-tail.
2. **Date / time:** after the analysis run.
3. **Question:** why is SJF-heuristic's P99 JCT worse than FCFS at ρ ≥ 0.9?
4. **Hypothesis:** none stated beforehand (post-hoc).
5. **Code:** `d4d9a2a9d87c`.
6. **Script:** `experiments/scripts/diag_tail.py`.
7. **Workload:** EXP5 per-request records, mixed, ρ = 0.9.
8. **Seeds:** 0–9.
9. **Policies:** FCFS; SJF-heuristic; SJF-oracle.
10. **Assumptions:** n/a.
11. **Command:** `python experiments/scripts/diag_tail.py`
12. **Completed:** yes.
13. **Outputs:** `experiments/results/analysis/EXP5_tail_composition.csv`.
14. **Observed:**
    - Under SJF-heuristic, 100 % of the slowest 1 % had predictions ≥ 1,024 tokens, a class
      holding 5.6 % of requests.
    - The heuristic produces about 209 distinct predictions per workload, versus about 929
      for the oracle.
    - Mean wait in the tail: 814 s (heuristic) vs 682 s (oracle) vs 395 s (FCFS).
15. **Baseline comparison:** see 14.
16. **Interpretation:**
    - The heuristic assigns a coarse "very long" class (long-form or code with a detail
      request). That whole class is served last, in FCFS order among themselves, so a
      sizeable block of requests waits together.
    - The oracle spreads the delay over the truly longest requests only.
    - This is a *post-hoc* explanation consistent with the data, not a tested hypothesis.
17. **Limitations:** a single configuration.
18. **Next action:** reported as a negative result.

## EXP6 — workload size

1. **ID / name:** EXP6, workload size.
2. **Date / time:** 00:17:32.
3. **Question:** do the findings persist as n grows?
4. **Hypothesis:** relative reduction is similar across sizes; seed variation shrinks; wall
   time grows about linearly.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp6_workload_size.yaml`.
7. **Workload:** mixed, ρ = 0.8.
8. **Requests / seeds:** n ∈ {500, 1k, 2k, 5k, 10k, 20k, 50k, 100k} × 0–9.
9. **Policies / predictors:** FCFS; SJF-heuristic.
10. **Assumptions:** wall-clock numbers are this laptop running Python.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp6_workload_size.yaml`
12. **Completed:** yes (160 runs, 97.5 s).
13. **Outputs:** `summary.csv`; derived `analysis/EXP6_*.csv`.
14. **Observed:**
    - **Mean-JCT reduction:** between 42.5 % and 46.6 % at every size. The across-seed SD
      fell from 6.3 points (n = 500) to 0.64 (n = 100k).
    - **Simulation wall time (FCFS):** 0.0024 s → 0.534 s, i.e. ×220 for ×200 requests.
    - **Python time per scheduling decision:** about 0.7 µs for both policies. The heuristic
      prediction takes about 0.5 µs per request.
    - The SJF 100k runs measured about 2× slower per request (1.2 µs/decision, 0.9 µs per
      prediction), including the prediction step. Most likely this is machine noise; it was
      not investigated.
15. **Baseline comparison:** see 14.
16. **Interpretation:** supported. The 5,000-request workloads used elsewhere are large enough
    for the mean (SD ≈ 2 points); P95 is noisier (SD ≈ 8 points).
17. **Limitations:**
    - The overhead figures describe a Python heap on a laptop, not a production scheduler.
    - Overhead is negligible relative to simulated service times of seconds, but that
      comparison mixes measured and assumed quantities.
18. **Next action:** none.

## EXP7 — EXTENSION: linear aging

1. **ID / name:** EXP7, aging extension.
2. **Date / time:** 00:19:13.
3. **Question:** can aging reduce long-request worst-case waiting while keeping most of
   SJF's mean gain?
4. **Hypothesis:** results move continuously from SJF toward FCFS as the rate grows;
   intermediate rates cut maximum wait substantially while giving up only part of the gain.
5. **Code:** `d4d9a2a9d87c`.
6. **Config:** `exp7_aging_extension.yaml` (grid from EXP7-dev).
7. **Workload:** mixed, long_heavy.
8. **Requests / seeds:** 5,000 × 0–9; ρ = 0.9.
9. **Policies / predictors:** FCFS; SJF-heuristic; SJF-aging a ∈ {0.1, 0.3, 0.5, 1, 2, 3, 5,
   10, 30, 100} with the heuristic predictor.
10. **Assumptions:** common settings.
11. **Command:** `python -m llm_scheduler.experiment_runner --config experiments/configs/exp7_aging_extension.yaml`
12. **Completed:** yes (240 runs, 20.6 s).
13. **Outputs:** `summary.csv`, `by_category.csv`; derived `analysis/EXP7_*.csv`.
14. **Observed (mixed; mean-JCT gain vs FCFS / max wait vs FCFS):**

    | Policy | Mean-JCT gain | Max wait vs FCFS | Max wait (s) |
    |---|---|---|---|
    | SJF | 57.7 % | +231 % | 1,432 |
    | a = 1 | 55.5 % | +109 % | 899 |
    | a = 3 | 41.2 % | +29 % | 562 |
    | a = 10 | 18.3 % | +4 % | 451 |
    | FCFS | 0 % | 0 % | 436 |

    long_heavy follows the same shape.
15. **Baseline comparison:** see 14.
16. **Interpretation:**
    - Supported. At a = 1, aging removes 37 % of SJF's maximum wait while keeping 96 % of its
      mean-JCT gain.
    - **No rate tested** reaches FCFS's worst case while keeping most of the gain. Linear
      aging is a trade-off, not a fix.
    - P95 JCT gets *worse* than SJF's for intermediate rates (mixed: 126 s at a = 0 vs 217 s
      at a = 2), because medium requests lose their priority to aged long ones.
17. **Limitations:**
    - The aging rate is in tokens per second, which ties it to the service model.
    - Only linear aging was tested. This is not production-quality starvation prevention,
      and MLFQ was not implemented.
18. **Next action:** future work (MLFQ with priority boost; deadline-based aging).

## Final audit (2026-10-28, after all documents and slides were written)

- **Unit tests:** `.venv\Scripts\python -m pytest -q` gave 59 passed (`experiments/logs/final_audit_pytest.txt`).
- **Reproduction:** `python experiments/scripts/repro_check.py --config experiments/configs/exp2a_fcfs_vs_sjf_load.yaml --original EXP2A_20261028-001549`
  re-ran EXP2A from scratch into `experiments/results/_reproduction/`.
  - All 180 summary rows were identical to the recorded run, excluding wall-clock columns.
  - All 30 per-request files were identical.
- **Demo:** `python experiments/scripts/demo.py` ran end to end (fixed workload → FCFS → SJF →
  comparison → saved CSVs → plot). Mixed workload, 2,000 requests, load 0.9, seed 42; mean JCT
  56.4 s (FCFS) vs 29.4 s (SJF-heuristic).
- **Consistency:** report, results, viva answers and slides draw on the same tables.
  - The slide numbers are read programmatically from `experiments/results/analysis/` by
    `presentation/build_data.py`.
  - The figures are listed in `experiments/results/analysis/sources.json` with their source run
    directories.

## Planned but not run

| Experiment | Status | Reason |
|---|---|---|
| MLFQ vs SJF vs FCFS | PLANNED | MLFQ not implemented (outside the 50 % scope) |
| Recompute vs swap preemption | PLANNED | preemption and memory not modelled |
| ML length predictor (e.g. gradient boosting) vs heuristic | PLANNED | not implemented |
| Real GPU / vLLM validation | BLOCKED | no vLLM, no WSL/Docker, 4 GB GPU (see `PROJECT_AUDIT.md`) |
| Sensitivity to prefill/decode cost ratio and bursty arrivals | PLANNED | not run in this version |
