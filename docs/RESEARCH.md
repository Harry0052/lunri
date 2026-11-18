# Research notes

Inspected 2026-11-18 from this remote Linux guest, using the public GitHub API, the `LICENSE` file at each commit below, the start of each README at that commit, and the Ollama structured-outputs page. No repository was cloned, installed, or copied. A security review of those codebases was not done. Dates, star counts, and issue counts are the API fields returned that day, not a judgment of quality.

The first prompt attachment was missing. The file `Lunri_Grok_Bot_Build_Prompts` was read on the second pass. `Lunri_Lab.zip` and `Lunri_YC_Application.md` are still absent. There is no simulator to preserve.

## Sources

| Project | Commit inspected | License file | Last commit date on that branch | Release | Archived |
| --- | --- | --- | --- | --- | --- |
| [ml-energy/zeus](https://github.com/ml-energy/zeus) | `9604d1346215f820fb04983cb3df2468f9c873e4` on `master` | Apache License 2.0 | 2026-11-17 | `zeus-v0.17.0` published 2026-11-15 | no |
| [ml-energy/benchmark](https://github.com/ml-energy/benchmark) | `c1d6557fbf7c7c495749b0fcf649f71774eabde9` on `master` | Apache License 2.0 | 2026-05-10 | `v3.0` published 2025-12-01 | no |
| [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM) | `0b64fdafe049e596a3f5657c219329f24af24198` on `main` | Apache License 2.0 | 2024-08-10 | GitHub returned 404 for `/releases/latest` | no |
| [Aagam-Bothara/Joule](https://github.com/Aagam-Bothara/Joule) | `0cece839ff01b6ed7e4bfd99af69a8f357bc69e3` on `main` | MIT. Copyright line: "Copyright (c) 2024 Joule Contributors" | 2026-10-01 | GitHub returned 404 for `/releases/latest` | no |
| [SupermodularAI/local_bench](https://github.com/SupermodularAI/local_bench) | `df78acaa7342b7c56069ef050cedb7815b98840c` on `main` | MIT. Copyright (c) 2026 Supermodular AI. Copyright (c) 2026 aiwinsyou@gmail.com (original "homebench" project) | 2026-08-11 | GitHub returned 404 for `/releases/latest` | no |
| [danielcregg/joulebench](https://github.com/danielcregg/joulebench) | `841d1a5049e196c45f691acaa4fb3f5fdf55f8a0` on `main` | MIT. Copyright (c) 2026 Daniel Cregg | 2026-03-30 | GitHub returned 404 for `/releases/latest` | no |
| [mlco2/codecarbon](https://github.com/mlco2/codecarbon) | `9b02bdc8bafd57023e10e7ff0388ab86b329831e` on `master` | MIT. Copyright lines for Mila, BCG Gamma, CometML, Haverford College, and Code Carbon NGO | 2026-11-16 | `v3.3.2` published 2026-10-23 | no |

API counts the same day: Zeus 389 stars, 52 forks, 9 open issues. Benchmark 21 stars, 3 forks, 0 open issues. RouteLLM 5716 stars, 455 forks, 45 open issues. Joule 0 stars, 0 forks, 0 open issues. local_bench 10 stars, 1 fork, 0 open issues. JouleBench 1 star, 0 forks, 0 open issues. CodeCarbon 1950 stars, 358 forks, 144 open issues. None of the seven repositories was archived.

Ollama structured outputs were read at https://docs.ollama.com/capabilities/structured-outputs on 2026-11-18. That page says a local request can set `format` to `"json"` or to a JSON schema, and it says Ollama's cloud does not support structured outputs. The page's examples use model names `gpt-oss` and `gemma4`. No text from the page was copied into this repository. This stage does not call Ollama. Schema-shaped JSON is not evidence that an extracted field is correct.

## What those READMEs say they do

Quoted or paraphrased only from the files at the commits above.

- Zeus README title is "Deep Learning Energy Measurement and Optimization". It describes a Python package that measures deep-learning energy and also ships optimizers. A news line dated 2025/05 says Zeus supports CPU, DRAM, AMD GPU, Apple Silicon, and NVIDIA Jetson energy measurement. That line was not re-tested here.
- ML.ENERGY Benchmark README describes a framework for energy and performance of generative models (LLMs, multimodal LLMs, diffusion) and points at a public leaderboard and a NeurIPS 2025 paper. It is not an invoice extractor.
- RouteLLM README describes serving and evaluating routers that send easier queries to cheaper models, as a drop-in around an OpenAI client. The cost claims on that README are about API price, not joules. The last commit on `main` is 2024-08-10.
- Joule README describes a verification-driven agent runtime: it runs an external check and escalates to another model when that check fails. Its budget table lists "Energy (Wh)" as "Estimated compute energy" and "Carbon (gCO₂)" as "Estimated carbon emissions". The estimator's source was not read, so this note does not say how the estimate is computed. The quickstart uses provider API keys. The repository is TypeScript.
- local_bench README describes a local terminal leaderboard for models already installed in Ollama, LM Studio, llama.cpp, vLLM, or another OpenAI-compatible server. It measures tokens per second, time to first token, memory, optional joules per token, and a fixed quality suite. The energy row says samples come from macOS `powermetrics` or Linux RAPL during a speed probe, minus an idle baseline, and that this needs root. Its quality list includes an extraction category. It does not describe a small-model-then-validator-then-large-model workflow for one invoice.
- JouleBench README says it measures GPU inference energy with NVML, in joules per token, with idle subtraction. The hardware section names an NVIDIA A100. It does not describe CPU-only or Apple Silicon metering.
- CodeCarbon README says the package estimates hardware electricity (GPU, CPU, and RAM) and applies a regional carbon intensity. A later row says Linux RAPL can "read real energy counters instead of estimating". Both statements are in that README. Remote API calls are explicitly out of its scope there.

## Overlap with Lunri

These projects already cover pieces of the same category:

- Energy instrumentation and estimates: Zeus, the ML.ENERGY Benchmark, local_bench, JouleBench, and CodeCarbon.
- Routing or escalation: RouteLLM (price routing) and Joule (check, then escalate, with an estimated energy budget).
- Asking a local model for JSON: Ollama structured outputs.

Lunri's stated hypothesis is a reproducible comparison of complete workflows, including quality, retries, verification, the measurement boundary, and the energy spent finding an optimization. This inspection does not show that no one else is doing that combination, and it does not show that Lunri is first. No novelty claim is made.

Stage 1 does not import any of this code. The mock path is original and labeled SIMULATED. It is not a measurement and not a router.

## Fit for a later stage

Zeus is the closest library to reuse for a real meter, and its license is Apache-2.0, so a later copy or dependency must keep that license and must not be described as only MIT. CodeCarbon is MIT and already distinguishes estimates from RAPL readings; using it would still require saying which one produced a number. local_bench shows one way to sample `powermetrics` and RAPL, with root, and its license has two copyright holders. JouleBench is a GPU/NVML design. RouteLLM's last commit is more than two years old as of this inspection. Joule's escalation pattern is relevant, and its README marks energy as estimated.

None of these was installed. Whether Zeus actually reads Apple Silicon power on Harry's Mac was not verified here.
