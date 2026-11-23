# Grokbot progress

## P01 — Research overlap and confirm the MVP

**Phase and status:** PASS

**Files changed:** `docs/overlap.md`, `docs/project-contract.md`, `docs/grokbot-progress.md`

**Commands and results:**

- GitHub repository search for `local LLM energy per correct answer validation cascade meter` on 2026-11-23 returned `total_count: 0`.
- Primary pages and commits recorded in `docs/overlap.md` for ML.ENERGY Benchmark (`c1d6557fbf7c7c495749b0fcf649f71774eabde9`, release `v3.0`, Apache-2.0), CodeCarbon (PyPI 3.3.3, commit `42b35001b16666c4177d45a1271cc42b74434067`, MIT), Zeus (`zeus-v0.17.0`, Apache-2.0), Intelligence Per Watt (`3f8998125825bb196704cb527821396aff04ea1c`, Apache-2.0), and local_bench (`df78acaa7342b7c56069ef050cedb7815b98840c`, MIT).
- CodeCarbon accuracy page https://docs.codecarbon.io/latest/explanation/accuracy/ retrieved 2026-11-23. Estimated CPU-load × TDP is documented apart from RAPL and NVML counters.
- Observed Lunri probe from this checkout:

```text
PYTHONPATH=src python3 -m unittest discover -s tests
Ran 53 tests in 1.113s
OK

PYTHONPATH=src python3 -m lunri eval --backend mock --split smoke --runs-dir /tmp/lunri-p01-runs
large/small/cascade attempts=3 correct=3 accuracy=1.0000 wilson95=0.4385..1.0000 quality=inconclusive
energy UNAVAILABLE aggregate_joules=null
decision insufficient evidence. Inference is SIMULATED
```

- `describe_sensor()` on this Linux host: sensor `none` (no powermetrics, no RAPL powercap, no power_supply devices). Joules null.

**Artifact paths:** `docs/overlap.md`, `docs/project-contract.md`

**Open issues:** Ollama was not on `PATH` during the probe, so model digests are unknown. CodeCarbon, Zeus, Intelligence Per Watt, and local_bench were not executed; their live meter agreement with a wall plug is unresolved. That does not cover the acceptance case, so it does not change the decision.

**Next phase:** P02

## Owner direction — prompt comparison

**Phase and status:** PASS

**Files changed:** prompt flow, local settings UI, cited watt-hour table, invoice fixture checker, tests, README, and CI. Existing invoice commands stay.

**Commands and results:**

- `PYTHONPATH=src python3 -m unittest discover -s tests` → `Ran 60 tests` and `OK`.
- `lunri prompt --demo --input-usd-per-million 1 --output-usd-per-million 1` exited 0 in 0.0046s. Optimized prompt: `I need a summary of the notes. the summary must be under 50 words.` Mock-small delta: input tokens 48, output tokens 2, cost `0.000050` USD from the `$1` rates on the command line, watt-hours `0.000956` from the cited 1.72 J/output-token A100 fit. Report label says it is not a measurement of this computer.
- `lunri fixture` accepted the packaged JSONL. `lunri fixture --path src/lunri/data/invalid/missing-fields.jsonl` exited 2 with `synthetic must be true`.
- Settings UI at `http://127.0.0.1:8766/` saved a Google provider named Desk. The page status was `Saved. The key is stored locally and is not shown here.` The key text was not in the page. Remove cleared `settings.json` to an empty provider list. Tab moved focus to the provider control. A 360px viewport still showed the form.

**Artifact paths:** `runs/prompt-comparison.json` (gitignored), `src/lunri/data/energy_assumptions.json`, `docs/grokbot-progress.md`

**Open issues:** Live provider calls are implemented and covered with a local fake server. This session did not call OpenRouter, Anthropic, Google, or a paid API. Ollama is optional and was not required for the demo. Invoice energy on this host remains unmeasured.

**Next phase:** publish on a pull request, wait for GitHub Actions, tag the next free version. Do not merge.
