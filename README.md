# Lunri

Lunri compares three ways of reading an invoice: a larger local model, a smaller local model, and the smaller model plus a check that can escalate. It reports accuracy with a 95% Wilson interval and energy only when a meter actually sampled the run. Version 0.2.0 was built and tested on Ubuntu Linux. It was not run on a Mac. No energy saving is claimed.

The invoice texts are synthetic. Gold answers are stored beside them and are not sent to the model. Raw invoice text is left out of reports unless you pass `--keep-raw-text` on the stage-1 mock command.

## One command on a Mac

Clone the repository, then:

```bash
git clone https://github.com/Harry0052/lunri.git
cd lunri
bash scripts/macos-setup.sh --install-ollama --smoke
```

That creates `.venv`, installs Lunri, prints the chip and RAM it detected, installs Ollama if the `ollama` command is missing, pulls `qwen2.5:0.5b` (listed as 398MB) and `qwen2.5:1.5b` (listed as 986MB) when RAM is at least 8 GiB, runs the offline mock smoke, and runs a 3-invoice Ollama smoke. The script prints each download before it starts. Those sizes and the Apache 2.0 note for every Qwen2.5 size except 3B and 72B come from the Ollama library page retrieved 2026-11-18. Digests show up only after the pull.

If Ollama is already installed:

```bash
bash scripts/macos-setup.sh --smoke
```

Under 8 GiB the script pulls only `qwen2.5:0.5b` and the three-way comparison is not recommended. Unknown RAM pulls nothing.

## Smallest checks

Offline, no model download:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
lunri eval --backend mock --split smoke
```

Real models, still no energy sample:

```bash
lunri eval --backend ollama --split smoke
```

Three invoices. The quality line will say `inconclusive` because the predeclared minimum is 30 attempts. The full synthetic comparison is:

```bash
lunri eval --backend ollama --split heldout
```

Apple Silicon energy, after you type your password at the sudo prompt yourself:

```bash
sudo -v
lunri eval --backend ollama --split heldout --energy powermetrics
```

Lunri starts `powermetrics` with `sudo -n`. It does not ask for a password. If the sudo cache is empty, the report says energy is `UNAVAILABLE` and joules are null. The combined CPU+GPU+ANE line is labeled `apple-silicon-soc-cpu-gpu-ane`. A CPU-only line is labeled `cpu-power-sampler-only` and is not called whole-machine energy. Nothing here is wall-plug energy.

`lunri hardware` prints the detected machine. On the Ubuntu machine used to check this release it reported `memory_bytes 16780623872` (16003 MiB) and `chip Linux x86_64`.

## What was verified on 2026-11-18

`bash scripts/macos-setup.sh` exited 2 and printed that the host is Linux.

`lunri doctor` exited 0. Required checks passed. Ollama and the energy sensor were skipped.

`lunri eval --backend mock --split smoke` exited 0. Three attempts, accuracy 1.0000, quality `inconclusive`, energy `UNAVAILABLE`, decision `insufficient evidence` because inference is `SIMULATED`.

`lunri eval --backend mock --split heldout` exited 0. 30 attempts, 12 correct, accuracy 0.4000, Wilson 0.2459 to 0.5768, quality `misses_target`. The line parser only understands `Invoice number:` and `Total:` lines, so the held-out block and gap families fail. Cascade made 48 calls and 18 fallbacks. Energy stayed null. The decision still says inference is `SIMULATED`.

`lunri eval --backend ollama --split smoke` exited 2:

```text
real inference NOT YET VERIFIED. Ollama is not reachable: OSError.
```

`lunri demo` printed three `HYPOTHETICAL` break-even cases, including `status=never` and `status=unavailable`.

`python -m unittest discover -s tests` reported `Ran 53 tests in 1.107s` and `OK`.

## Commands

| Command | Role |
| --- | --- |
| `lunri doctor` | Local checks. No API key. |
| `lunri run` | Stage-1 mock on three packaged texts. Labeled `SIMULATED`. |
| `lunri hardware` | Chip, RAM, and which tags to pull. |
| `lunri generate` | Rewrite `dataset.jsonl` from seed 20261118. |
| `lunri eval --backend mock` | Line-parser comparison. Not a model result. |
| `lunri eval --backend ollama` | Real local models, if Ollama is up. |
| `lunri demo` | Hypothetical arithmetic only. |

The quality target is 0.8 and the minimum sample is 30, both in `src/lunri/data/eval_config.json`. The eval command does not change them.

## Layout

The dataset has 30 dev rows, 30 held-out rows, and 3 smoke rows. Families do not cross splits. See `docs/MACOS.md`, `docs/RESEARCH.md`, `CONTRIBUTING.md`, and `SECURITY.md`.

## Limits

Ollama, Qwen, and `powermetrics` were not run here. Zeus was inspected and not installed. A batch energy figure divided by attempts is an average, not a per-invoice meter reading. Optimization overhead was not measured, so break-even on a real run stays unavailable. The mock held-out score is the line parser missing other layouts, not a judgment of Qwen.
