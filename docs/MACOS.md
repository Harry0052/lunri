# macOS steps

None of these commands were run. The build machine is a remote Ubuntu 24.04 KVM guest.

## Clone and set up

```bash
git clone https://github.com/Harry0052/lunri.git
cd lunri
bash scripts/macos-setup.sh --install-ollama --smoke
```

Python 3.11 or newer has to be on `PATH` before that. The script will not install Python.

What the script does, in order:

1. Refuses to continue if `uname -s` is not `Darwin`.
2. Creates `.venv` and runs `python -m pip install -e .`.
3. Runs `lunri hardware`, which reads `sysctl -n hw.memsize` and `sysctl -n machdep.cpu.brand_string` on a Mac.
4. If `ollama` is missing and `--install-ollama` was passed, runs `curl -fsSL https://ollama.com/install.sh | sh` after printing that it is about to. Without the flag it stops and tells you to drag the app from https://ollama.com/download into `/Applications`.
5. Pulls the tags `lunri hardware` listed. At least 8 GiB pulls `qwen2.5:0.5b` and `qwen2.5:1.5b`. Under 8 GiB pulls only `qwen2.5:0.5b`.
6. Runs `lunri eval --backend mock --split smoke`.
7. With `--smoke`, runs `lunri eval --backend ollama --split smoke`.

Ollama's macOS page, retrieved 2026-11-18, says Sonoma 14 or newer, Apple silicon for CPU and GPU, and Intel Macs for CPU only. Models land in `~/.ollama`.

## Smallest real smoke

After the setup script has pulled the tags:

```bash
. .venv/bin/activate
lunri eval --backend ollama --split smoke
```

Open `runs/eval-ollama-smoke.json`. Expect `inference REAL` if Ollama answered, `quality inconclusive`, and `energy UNAVAILABLE`. Three rows are not a decision.

## Held-out comparison

```bash
lunri eval --backend ollama --split heldout
```

That is 30 synthetic invoices. The report's quality gate uses the target 0.8 already stored in `src/lunri/data/eval_config.json`. A lower Wilson bound under 0.8 is a miss, not a prompt to edit the target.

## Energy

Type the password only when macOS asks for it:

```bash
sudo -v
lunri eval --backend ollama --split heldout --energy powermetrics
```

The process runs `sudo -n powermetrics --samplers cpu_power,gpu_power,ane_power -i 1000 -n 5`. If that fails, joules stay null. Do not add the CPU, GPU, and ANE lines yourself. Lunri uses the `Combined Power (CPU + GPU + ANE)` line when it is present, and otherwise a `CPU Power` line with an explicit CPU-only boundary.

`man powermetrics` on the Mac is the manual. This Linux guest cannot show it.

## Copy a failure back

Redact any invoice text first, then copy the command and the last 40 lines of output. The report path is on the last line that starts with `report `.
