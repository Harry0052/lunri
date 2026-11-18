# Environment inspection

Observed 2026-11-18 on the computer that built this stage. These commands were run here. This is not Harry's Mac.

| Check | Result |
| --- | --- |
| `uname -srm` | Linux 6.12.113+ x86_64 |
| OS | Ubuntu 24.04.5 LTS |
| CPU | 4 vCPU, Intel Xeon, KVM guest |
| Memory | `free -h` showed 15 GiB total and no swap. `/proc/meminfo` MemTotal was 16780623872 bytes. `lunri doctor` prints that as 16003 MiB. |
| Disk | 254G filesystem, about 247G free |
| `python3 --version` | Python 3.12.3 at `/usr/bin/python3` |
| `python3 -m pip --version` | pip 24.0 |
| setuptools | 68.1.2, already installed |
| `git --version` | git 2.43.0 |
| Branch | `main` |
| `command -v ollama` | not installed |
| `pytest`, `pydantic`, `httpx`, `ollama` Python modules | not installed |
| `command -v powermetrics` | not installed (it is a macOS tool) |
| `command -v sensors` | not installed |
| `command -v nvidia-smi` | not installed |
| `/sys/class/powercap` | absent, so no Intel RAPL interface |
| `/sys/class/power_supply` | directory exists and contains no devices |

Build notes from outside this repository are not included. `Lunri_Lab.zip` and `Lunri_YC_Application.md` are not in the tree. There is no simulator to preserve.

`lunri doctor` on this guest reports Linux, x86_64, 4 CPUs, 16003 MiB, Python 3.12.3. It does not name a Mac model. Ollama is skipped because it is not on `PATH`. The energy line is labeled SIMULATED because no sensor was sampled and no wattage was estimated.
