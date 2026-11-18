# Contributing

Lunri is a local benchmark. Changes should keep reports honest.

- Do not commit API keys, passwords, real invoices, or model weights.
- Do not label a mock run, an injected meter, or a hypothetical break-even figure as a measurement.
- If energy was not sampled, leave joules null. Do not write zero.
- Gold labels stay out of the model prompt. Add a test if a new prompt field could leak them.
- Run `python -m unittest discover -s tests` before sending a change.
- New third-party code needs an entry in `THIRD_PARTY_NOTICES.md` with the commit, the license, and what was copied. Apache-2.0 code is not relicensed as MIT.
