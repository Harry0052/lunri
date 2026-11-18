# Security

Lunri reads invoice text on the machine where it is run. It does not upload that text.

- The default record and eval report omit the raw invoice.
- `--keep-raw-text` is opt-in and applies to the stage-1 mock record.
- The program does not read API keys. Ollama is contacted at `127.0.0.1` only.
- `powermetrics` is started with `sudo -n`. Lunri never asks for, stores, or forwards a password. If the sudo cache is empty, energy is unavailable.
- Do not commit `.env` files, credentials, or customer documents. `runs/` is gitignored because a report can contain extracted fields.

Report a vulnerability privately to the repository owner. There is no public bug-bounty program.
