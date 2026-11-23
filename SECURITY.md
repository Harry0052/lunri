# Security

Lunri reads invoice text on the machine where it is run. It does not upload that text.

- The default record and eval report omit the raw invoice.
- `--keep-raw-text` is opt-in and applies to the stage-1 mock record.
- The invoice commands do not read API keys. Their Ollama client is contacted at `127.0.0.1` only.
- Prompt commands can call a provider you name. The API key comes from `~/.config/lunri/settings.json` or from `LUNRI_API_KEY` for `lunri settings add`. It is not a command argument, is not written into the report, and the settings page does not display it after save. The settings page binds to `127.0.0.1` only.
- `powermetrics` is started with `sudo -n`. Lunri never asks for, stores, or forwards a password. If the sudo cache is empty, energy is unavailable.
- Do not commit `.env` files, credentials, or customer documents. `runs/` is gitignored because a report can contain extracted fields.

Report a vulnerability privately to the repository owner. There is no public bug-bounty program.
