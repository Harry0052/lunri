# Third-party notices

Lunri 0.1.1 original code is under the MIT license in `LICENSE`. Copyright (c) 2026 Harry Malhi.

No third-party source is vendored. The runtime uses the Python standard library only. Nothing from the projects below was modified or copied. Their text stays in their repositories. If a later stage imports one of them, this file has to be updated and that project's license has to ship with the import.

Python is covered by the PSF License. This repository does not redistribute the interpreter.

An editable install uses setuptools as a build tool. setuptools is MIT: https://github.com/pypa/setuptools/blob/main/LICENSE . It is not part of the Lunri package.

The invoice texts in `src/lunri/data/invoices/` and the labels in `src/lunri/data/labels.json` were written for this repository. They are synthetic.

## Inspected, not included

Fetched 2026-11-18. Details and overlap are in `docs/RESEARCH.md`.

| Source | Commit | License at that commit | Included |
| --- | --- | --- | --- |
| https://github.com/ml-energy/zeus | `9604d1346215f820fb04983cb3df2468f9c873e4` | Apache License 2.0 | no |
| https://github.com/ml-energy/benchmark | `c1d6557fbf7c7c495749b0fcf649f71774eabde9` | Apache License 2.0 | no |
| https://github.com/lm-sys/RouteLLM | `0b64fdafe049e596a3f5657c219329f24af24198` | Apache License 2.0 | no |
| https://github.com/Aagam-Bothara/Joule | `0cece839ff01b6ed7e4bfd99af69a8f357bc69e3` | MIT, Copyright (c) 2024 Joule Contributors | no |
| https://github.com/SupermodularAI/local_bench | `df78acaa7342b7c56069ef050cedb7815b98840c` | MIT. Copyright (c) 2026 Supermodular AI. Copyright (c) 2026 aiwinsyou@gmail.com (original "homebench" project) | no |
| https://github.com/danielcregg/joulebench | `841d1a5049e196c45f691acaa4fb3f5fdf55f8a0` | MIT, Copyright (c) 2026 Daniel Cregg | no |
| https://github.com/mlco2/codecarbon | `9b02bdc8bafd57023e10e7ff0388ab86b329831e` | MIT. Copyright lines for Mila, BCG Gamma, CometML, Haverford College, and Code Carbon NGO | no |

Apache-2.0 code is not MIT. This package does not relicense those projects.

Ollama's application `LICENSE` file is MIT (https://github.com/ollama/ollama/blob/main/LICENSE). The structured-outputs page https://docs.ollama.com/capabilities/structured-outputs was read and not copied. `powermetrics` is part of macOS. This version does not call either program.

No model weights are included. The Ollama library page for `qwen2.5`, retrieved 2026-11-18, lists `qwen2.5:0.5b` at 398MB and `qwen2.5:1.5b` at 986MB, and says every Qwen2.5 size except 3B and 72B is Apache 2.0. Those two tags are the ones the Mac setup pulls. The weight files and their digests were not downloaded here, and the Apache text inside the weight repository was not opened. The 3B and 72B tags are not suggested.
