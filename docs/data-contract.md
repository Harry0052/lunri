# Data contract

Schema version 1. The checker is `lunri fixture check`. Limits live in `lunri.contracts`.

## Input

One JSON object per line. Blank lines are ignored. The packaged file is `src/lunri/data/dataset.jsonl`.

| Field | Rule | Unit |
| --- | --- | --- |
| `synthetic` | must be true | flag |
| `id` | non-empty string, unique in the file | id |
| `split` | `dev`, `heldout`, or `smoke` | label |
| `family` | non-empty string; one family cannot appear in two splits | label |
| `kind` | non-empty string | label |
| `text` | string, at most 8000 characters, must contain `SYNTHETIC` | text |
| `gold.invoice_number` | non-empty string | id |
| `gold.total_cents` | null or an integer greater than or equal to 0 | cents |
| `gold.currency` | null or three uppercase letters | ISO-style code |

The integer `total_cents` must not appear as digits inside `text`. The prompt sent to a model is the invoice text only.

Bounds: file at most 2_000_000 bytes, line at most 16_384 bytes, at most 500 rows.

Error categories, printed as `line N: ...` and exiting 2:

- not JSON, or JSON that is not an object
- missing or illegal fields, including `synthetic` not true
- oversize file, line, or text
- duplicate id
- family leakage across splits
- cent integer copied into the prompt
- packaged checksum or seed mismatch (`20261118`, sha256 in `fixture_manifest.json`)

The labeled invalid file is `src/lunri/data/invalid/missing-fields.jsonl`. It is not synthetic and has no gold object.

## Output

Eval JSON schema version 1. Energy labels are `MEASURED`, `SIMULATED`, or `UNAVAILABLE`. Trace status is `complete`, `partial`, `reset`, or `unavailable`. Canonical energy is joules (`J`). Raw `powermetrics` samples stay in milliwatts (`mW`). A cumulative hardware counter stays in microjoules (`uJ`) until a complete monotonic delta is converted to joules.

`energy_per_correct_joules` is the whole-arm joules divided by the correct count. It is null when the trace is not a complete measured or simulated window, and when the correct count is zero. `SIMULATED` joules are arithmetic from a scripted meter. They are not a hardware claim.

Each arm row records item id, arm, prompt version `invoice-extract-1`, model revision and digest (digest null when no weight was loaded), stage status, elapsed seconds, call count, verdict (`correct`, `wrong`, or `error`), and normalization id `exact-cents-v1`. Rows do not include the invoice text.

Verdict `wrong` means the response parsed and failed the gold match. Verdict `error` means the response did not parse or the call failed. Both are not correct.

## Oracle

`docs/oracle.md` records the hand calculation for `smoke-smoke_plain-000`.
