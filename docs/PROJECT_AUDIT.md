# Project Audit

Audit date: 2026-10-27. Performed before any code was written.

## 1. Existing files

The working directory `C:\Users\Vansh\Desktop\Vineet Prod` was **empty** at audit time:
no repository, no source code, no datasets, no previous experiments, reports, plots or
presentation files. Nothing had to be preserved or merged. The project was created from
scratch in the subfolder `llm-os-scheduler/`.

The only specification is the project synopsis supplied in the chat ("OS-Inspired
Preemptive Scheduling for Concurrent LLM Inference Requests Using Output-Length
Prediction").

## 2. Hardware and software

All values were read from the machine during the audit (commands in brackets).

| Item | Finding |
|---|---|
| OS | Windows 11 Home Single Language 10.0.26200 |
| CPU | Intel Core i5-10300H @ 2.50 GHz, 4 cores / 8 threads (`Get-CimInstance Win32_Processor`) |
| RAM | 15.8 GB (`Win32_ComputerSystem`) |
| Free disk | ~23 GB free of 255 GB on `C:` (`df -h`) |
| GPU | NVIDIA GeForce GTX 1650 Ti, 4096 MiB VRAM, compute capability 7.5, driver 566.14, CUDA 12.7 driver API (`nvidia-smi`) |
| Python | 3.13.3 (`C:\Python313\python.exe`) |
| PyTorch | 2.13.0+cpu, `torch.cuda.is_available() == False` (CPU-only build) |
| vLLM | not installed (`ModuleNotFoundError: No module named 'vllm'`) |
| WSL | not installed (`wsl.exe -l -v`: "The Windows Subsystem for Linux is not installed") |
| Docker / conda | not found |
| Pre-installed scientific packages | numpy 2.2.6, pandas 3.0.5, scipy 1.18.1, scikit-learn 1.9.0, PyYAML 6.0.3, python-pptx 1.0.2 |
| Installed during audit | matplotlib 3.11.2, pytest 9.1.1 (`pip install matplotlib pytest`) |
| Node.js / git | Node 22.16.0, npm 10.9.2, git 2.56.0 (directory is not a git repository) |

## 3. Existing implementations

None. No scheduler, simulator, predictor, workload generator or metrics code existed.

## 4. Datasets and traces

No prompt datasets or benchmark traces were present on disk. No dataset was downloaded:
the workload is synthetic (see `METHODOLOGY.md`), and that choice is recorded as a
limitation.

## 5. Missing components (relative to the synopsis)

Everything in the synopsis was missing: request generator, length predictor (heuristic and
ML), FCFS, predictive-SJF, MLFQ, aging, preemption (recompute and swap), inference backend
(vLLM or simulator), metrics collector, experiment automation, report and presentation.

## 6. Major risks

| Risk | Impact | Mitigation |
|---|---|---|
| vLLM does not run natively on Windows, WSL/Docker absent | Route B (real vLLM integration) would first need WSL2 + CUDA toolkit setup | Use Route A (simulator); keep a policy interface that could later be ported |
| 4 GB VRAM, Turing GPU | Even under WSL2, only very small models (<1B parameters) would fit; measurements would not represent production serving | Do not claim GPU measurements; treat real-hardware validation as future work |
| CPU-only PyTorch | No local GPU inference even outside vLLM | Same as above |
| No real prompt dataset | Predictor accuracy on synthetic prompts is likely optimistic | Synthetic predictor-error sweep (Experiment 4) and explicit threats-to-validity section |
| Simulated timing | Absolute latency numbers are assumptions, not measurements | Express load as utilisation; report relative changes; validate the simulator against queueing-theory formulas |
| Scope creep (MLFQ, swap, KV-cache) | Core experiments left unfinished | Fixed 50 % boundary below; at most one extension |

## 7. Recommended implementation route

**Route A: discrete-event simulator.** Rationale and alternatives are in
`IMPLEMENTATION_DECISION.md`.

## 8. What "50 % completion" means here

The synopsis describes ten engineering components. The 50 % boundary is a coherent,
end-to-end subset that runs, is tested, and produces the evaluation:

| # | Synopsis component | In 50 % scope? |
|---|---|---|
| 1 | Request generator / workload model | Yes |
| 2 | Heuristic length predictor | Yes |
| 3 | FCFS baseline | Yes |
| 4 | Predictive-SJF (non-preemptive) | Yes |
| 5 | Simulated backend (single execution slot, discrete-event) | Yes |
| 6 | Metrics collector | Yes |
| 7 | Experiment automation, results, plots | Yes |
| 8 | Aging | One simple variant as the single optional extension (Experiment 7) |
| 9 | MLFQ with promotion/demotion | No (planned) |
| 10 | Preemption: recompute and swap modes | No (planned) |
| 11 | Learned (ML) length predictor | No (planned) |
| 12 | vLLM integration, KV-cache management, continuous batching | No (planned) |

"Complete" for the subset means: the code runs end to end from a config file, unit tests
pass, the planned experiments ran and their raw outputs are saved, and the report and slides
describe only what the saved evidence supports. Actual status is tracked in
`IMPLEMENTATION_STATUS.md`.
