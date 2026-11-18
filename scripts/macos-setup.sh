#!/usr/bin/env bash
# macOS setup for Lunri. Prints each download before it starts.
# Linux hosts are refused so this script does not install Ollama here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

INSTALL_OLLAMA=0
PULL=1
SMOKE=0
for arg in "$@"; do
  case "$arg" in
    --install-ollama) INSTALL_OLLAMA=1 ;;
    --no-pull) PULL=0 ;;
    --smoke) SMOKE=1 ;;
    -h|--help)
      echo "Usage: bash scripts/macos-setup.sh [--install-ollama] [--no-pull] [--smoke]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This setup script is for macOS. This host is $(uname -s)."
  echo "Offline check from the repository root:"
  echo "  python3 -m venv .venv && . .venv/bin/activate && python -m pip install -e . && python -m unittest discover -s tests && lunri eval --backend mock --split smoke"
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not on PATH. Install Python 3.11 or newer, then rerun this script."
  exit 2
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python %s is older than 3.11" % sys.version.split()[0])
print("python", sys.version.split()[0])
PY

python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install -e .

echo "---- hardware ----"
lunri hardware

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not on PATH."
  echo "Manual install: download https://ollama.com/download and drag Ollama to /Applications."
  echo "The app can link the ollama command into /usr/local/bin."
  if [[ "$INSTALL_OLLAMA" != "1" ]]; then
    echo "Rerun with --install-ollama to run https://ollama.com/install.sh, or install the app and rerun this script."
    exit 2
  fi
  echo "About to run the Ollama install script from https://ollama.com/install.sh"
  curl -fsSL https://ollama.com/install.sh | sh
fi

echo "---- model tags ----"
TAGS=()
while IFS= read -r tag; do
  if [[ -n "$tag" ]]; then
    TAGS+=("$tag")
  fi
done < <(python - <<'PY'
from lunri.hardware import detect_hardware
suggestion = detect_hardware()["suggestion"]
for tag in suggestion["pull"]:
    print(tag)
PY
)

if [[ ${#TAGS[@]} -eq 0 ]]; then
  echo "No model will be pulled. lunri hardware did not recommend a tag."
  echo "qwen2.5:0.5b is listed as 398MB on the Ollama page retrieved 2026-11-18. Pull it yourself only if you want that download."
  PULL=0
fi

if [[ "$PULL" == "1" ]]; then
  for tag in "${TAGS[@]}"; do
    echo "About to download ${tag}."
    echo "Page sizes retrieved 2026-11-18: qwen2.5:0.5b 398MB, qwen2.5:1.5b 986MB. Digests appear after the pull."
    ollama pull "$tag"
  done
fi

echo "---- offline mock smoke ----"
lunri eval --backend mock --split smoke

if [[ "$SMOKE" == "1" ]]; then
  echo "---- real local smoke, 3 synthetic invoices ----"
  lunri eval --backend ollama --split smoke
fi

echo "Energy was not sampled."
echo "On Apple Silicon, type your password only at the sudo prompt, then:"
echo "  sudo -v"
echo "  .venv/bin/lunri eval --backend ollama --split smoke --energy powermetrics"
echo "Lunri calls sudo -n and will not ask for the password itself."
