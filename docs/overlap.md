# Overlap

Access date: 2026-11-23. Lunri already exists at https://github.com/Harry0052/lunri (MIT, package version 0.2.0). This note asks whether that repository still has a distinct job: measured joules per correct synthetic invoice for a larger local model, a smaller local model, and the smaller model plus validation and fallback.

The acceptance case held constant for every probe:

- Input: the packaged smoke invoice `smoke-smoke_plain-000`. The text states `Total: 10.24 USD` and `Invoice number: smoke_plain-000`. The hand conversion is `10 * 100 + 24 = 1024` cents. Gold currency is `USD`.
- Expected artifact: joules per correct extraction, with a 95% Wilson interval, a sample count, a meter boundary, and the energy of validation and fallback inside the same window.
- Rule: estimated wattage must not be reported as measured. A missing meter leaves joules null.

## Capability matrix

| Project | Primary URL | Version or commit | License | What was checked | Matches the acceptance case |
| --- | --- | --- | --- | --- | --- |
| Lunri | https://github.com/Harry0052/lunri | working tree on `main` at the start of this phase, package 0.2.0 | MIT | Observed run, below | Partial. It scores the fixture and refuses to invent joules. It does not yet label a fake-meter window as simulated energy-per-correct, and it does not yet reject a reset counter. |
| ML.ENERGY Benchmark | https://github.com/ml-energy/benchmark | commit `c1d6557fbf7c7c495749b0fcf649f71774eabde9` (2026-05-10); release `v3.0` (2025-12-01) | Apache-2.0 | Documentation | No. Tasks are arena chat, GPQA, fill-in-the-middle, multimodal chat, and diffusion. No invoice correctness denominator and no validator-fallback arm. |
| CodeCarbon | https://github.com/mlco2/codecarbon and https://docs.codecarbon.io/latest/explanation/accuracy/ | PyPI 3.3.3; commit `42b35001b16666c4177d45a1271cc42b74434067` (2026-11-22) | MIT | Documentation, plus an observed sensor check on this host | No. It measures or estimates CPU, GPU, and RAM electricity. The TDP fallback is documented as roughly −60% to +190% versus RAPL. It has no correct-answer denominator. |
| Zeus | https://github.com/ml-energy/zeus | release `zeus-v0.17.0` (2026-11-15); license Apache-2.0 from the repository API | Apache-2.0 | Documentation | No. It is an energy measurement and optimization library, not an invoice cascade. |
| Intelligence Per Watt | https://github.com/HazyResearch/intelligence-per-watt | commit `3f8998125825bb196704cb527821396aff04ea1c` (2026-10-15) | Apache-2.0 | Documentation | No. It reports intelligence per joule for standard benchmarks and can talk to Ollama. It does not score this invoice fixture or a validator-then-fallback window. Python `>=3.13` is required; this machine has 3.12.3. |
| local_bench | https://github.com/SupermodularAI/local_bench | commit `df78acaa7342b7c56069ef050cedb7815b98840c` (2026-08-11) | MIT | Documentation | No. Energy is joules per output token from `powermetrics` or RAPL, with an idle baseline. Quality is a separate suite. There is no small-model, validator, large-model cascade for one invoice. |
| LeanLM routing note | https://leanlm.ai/blog/llm-model-routing | page retrieved 2026-11-23; no package version | page terms not a code license | Documentation | No. Single-model GPU joules are measured. The cascade row is modeled as `cheap + escalation_rate * frontier`, not a measured window that includes the validator. The task is code tests, not this fixture. |
| devVHG1/TaskForge | https://github.com/devVHG1/TaskForge | README retrieved 2026-11-23 | not used | Documentation | No. That public repository is a background-job runner. It does not measure inference joules per correct invoice. |

Dataset terms: Lunri's invoices are synthetic and generated in this repository (seed `20261118`). None of the other projects' datasets were downloaded. ML.ENERGY Benchmark auto-downloads third-party prompt sets (LM Arena, GPQA, and others) that are not redistributed here.

GitHub repository search for `local LLM energy per correct answer validation cascade meter` returned `total_count: 0` on 2026-11-23. Broader web search found the rows above. No closer project was installed.

## Probes

### Lunri, observed

Command, from `/agent/repos/lunri` with `PYTHONPATH=src`:

```text
python3 -m unittest discover -s tests
python3 -m lunri eval --backend mock --split smoke --runs-dir /tmp/lunri-p01-runs
```

Results: `Ran 53 tests` and `OK` in 1.113s. The smoke report scored 3/3 on every arm, Wilson 95% `0.4385..1.0000`, quality `inconclusive` (minimum sample 30), energy `UNAVAILABLE`, joules null. Cascade made 3 calls and 0 fallbacks on this split because the line parser already matched. The decision line refused a comparison because inference is `SIMULATED`.

`describe_sensor()` on this host returned sensor `none`: Linux, no `powermetrics`, no Intel RAPL powercap device, no `power_supply` devices. Joules stayed null. That is an observed host check, not a CodeCarbon run.

### Other tools

- ML.ENERGY Benchmark was not executed. Its overview (https://github.com/ml-energy/benchmark/blob/master/docs/overview.md, commit above) lists no invoice task, and a run needs vLLM or xDiT plus downloaded datasets. Evidence: documentation.
- CodeCarbon was not installed. Its accuracy page, retrieved 2026-11-23, says RAPL and NVML are counter paths and CPU-load times TDP is an estimate. This host has no RAPL device, so a CodeCarbon run here would take the estimate path. That number must not enter Lunri's measured metric. Evidence: documentation plus the observed sensor check. A live CodeCarbon process was not started, so its exact log line on this host is unresolved.
- Intelligence Per Watt, Zeus, and local_bench were not installed. Running them would need a newer Python, a Rust monitor, model weights, or root meter access that this phase did not grant. Evidence: documentation. Whether their meters agree with a wall plug on this machine is unresolved.

## What already matches

Energy counters and estimates exist (Zeus, ML.ENERGY Benchmark, CodeCarbon, local_bench, Intelligence Per Watt). Small-to-large routing exists in papers and in the LeanLM note, sometimes with modeled rather than measured cascade energy. Asking Ollama for JSON already exists. None of those combine, on one held-out synthetic invoice list, a frozen field judge, a validator that can escalate, whole-arm joules that include the failed attempts, and a hard split between measured counters and estimates.

## Uncertainties

- Wall-plug error for RAPL, NVML, and `powermetrics` is not settled by CodeCarbon's own page (no external wattmeter validation). Lunri should keep publishing the meter boundary and should not call a counter reading wall energy.
- Model digests for `qwen2.5:0.5b` and `qwen2.5:1.5b` are unknown until a local pull. Ollama was not on `PATH` during this probe.
- A private tool could still overlap. Public evidence does not show one that already runs this acceptance case.

## Decision

**Proceed.** Keep Lunri as its own repository. Do not vendor Zeus, CodeCarbon, or the benchmark suites. Do not send estimated channels through the measured joules-per-correct field. The fixture provenance path is the in-repository generator, seed `20261118`, MIT, no remote download at run time.

Contribution or integration would not meet the acceptance case: those projects would still need the invoice judge, the cascade window, and the estimate exclusion. The smaller change is to extend Lunri's existing CLI.
