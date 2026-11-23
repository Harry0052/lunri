# Project contract

Status: accepted for implementation after the overlap review on 2026-11-23. Decision: proceed. See `docs/overlap.md`.

## User and task

Local AI workflow developers measure electricity per correct result on their own hardware.

The task is one held-out list of synthetic invoices, run three times with the same item ids:

1. Larger local model (`qwen2.5:1.5b` in `src/lunri/data/eval_config.json`).
2. Smaller local model (`qwen2.5:0.5b`).
3. Smaller model, then a validator, then the larger model only when the validator or the parse fails.

The judge compares `invoice_number`, `total_cents`, and `currency` with exact equality. Null matches null. There is no numeric tolerance. A JSON object that parses and still has the wrong amount is wrong. Energy per correct answer is undefined when the correct count is zero.

## Minimum dependencies

- Python 3.11 or newer. The standard library is the runtime. No paid API and no API key.
- Build: setuptools, as declared in `pyproject.toml`.
- Optional, for a real model run: Ollama on `127.0.0.1` only, and the two tags above. Weights are not stored in this repository.
- Optional, for a measured energy claim: macOS `powermetrics` (combined CPU+GPU+ANE, or a CPU-only line that must be labeled as CPU-only) or a complete monotonic hardware counter trace. If the meter is missing, partial, or reset, joules stay null and the label is `UNAVAILABLE`.
- A scripted meter is allowed in tests. Its joules are labeled `SIMULATED` and cannot support a savings claim.

The offline demo does not download models or datasets.

## Acceptance case

Fixture: `src/lunri/data/dataset.jsonl`, seed `20261118`, smoke split for the short demo and held-out split for the id check.

One measurable case:

- Every arm sees the same ids, each exactly once, in the input order.
- A controlled fake meter wraps the whole arm, so validation, retries, failed calls, and fallbacks stay inside the joule total. The label is `SIMULATED`.
- A syntax-valid wrong invoice does not increment the correct count.
- When that count is zero, joules per correct answer is null.
- A counter trace that is missing, short, or reset does not produce a joule value.
- The report states the accuracy floor (`0.8`), the Wilson interval, the sample count, the meter boundary, and that no saving is claimed unless inference is real, the trace is a complete measurement, the boundary matches across arms, and every arm meets the quality gate.

Commands that must keep working:

```bash
python3 -m unittest discover -s tests
lunri doctor
lunri eval --backend mock --split smoke
lunri eval --backend ollama --split heldout
```

The Ollama command is the real-inference path. On a machine with no supported meter it still has to record the meter reason and leave joules empty when Ollama itself is reachable. When Ollama is not reachable, the command exits with an error and does not invent a result.
