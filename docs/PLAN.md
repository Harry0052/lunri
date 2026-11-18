# Architecture and milestone plan

Lunri compares complete local workflows on one task: extract a few fields from invoice text, and later see whether a smaller model plus a check can use less energy without missing an accuracy target. This repository is only the foundation. Prompts 2–7 were not started. No energy saving is claimed.

`Lunri_Lab.zip` was not supplied. There is no HTML simulator to keep. `Lunri_YC_Application.md` was not supplied. It is a planning draft when it exists, not evidence.

## This stage

```
synthetic invoice text
  -> mock-deterministic (fixed line rules, no gold labels)
  -> response parser (malformed strings fail)
  -> JSON run record labeled SIMULATED
```

`lunri doctor` checks the machine it is actually running on: operating system, CPU count, and Linux MemTotal when `/proc/meminfo` exists. It does not assume a Mac model or a RAM size. Missing Ollama or a missing energy sensor is optional.

The mock reads only the invoice text. It fills `invoice_number`, `total_cents`, and `currency` when a line matches exactly once. Gold answers are in `src/lunri/data/labels.json` for tests. The mock does not import them.

Default records omit the raw text. Nothing is uploaded. Joules stay null. The word SIMULATED is on the mock response and on the energy object so a null is not read as a measurement or an estimate.

## Modules

| Module | Role |
| --- | --- |
| `lunri.fixture` | Three synthetic texts |
| `lunri.labels` | Test labels only |
| `lunri.mock_model` | Deterministic text extractor |
| `lunri.response` | Accept or reject a response string |
| `lunri.run` | One case to one record |
| `lunri.records` | Stable JSON file |
| `lunri.energy` | Sensor presence. No sample |
| `lunri.hostinfo` | OS, CPU count, optional memory |
| `lunri.doctor` | Required checks with no API key |
| `lunri.cli` | `doctor` and `run` |

## Later stages, coded and not yet run on a Mac

The held-out set, Ollama adapter, three strategies, Wilson gate, and powermetrics parser are in the tree. On this Linux guest the Ollama command exits 2 with `NOT YET VERIFIED`, and powermetrics is not started. A public release was not created. Zeus was not installed.

## Out of scope here

Paid APIs, accounts, a dashboard, a public release, and any sentence that says energy was saved.
