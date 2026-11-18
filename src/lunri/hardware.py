"""Suggest local models from the machine that was actually detected."""

from __future__ import annotations

import subprocess

from lunri.hostinfo import detect_host

GIB = 1024 ** 3

# Figures from the Ollama library page for qwen2.5, retrieved 2026-11-18.
# Digests are unknown until a pull. 3B and 72B are a different license and are not suggested.
SMALL_MODEL = "qwen2.5:0.5b"
LARGE_MODEL = "qwen2.5:1.5b"
SMALL_SIZE = "398MB"
LARGE_SIZE = "986MB"


def suggest_models(*, system: str, machine: str, memory_bytes: int | None, brand: str = "") -> dict:
    """Pick the stage-2 pair from RAM. Unknown RAM does not invent a size."""
    apple = system == "Darwin" and machine == "arm64"
    intel_mac = system == "Darwin" and machine != "arm64"
    if apple:
        chip = brand or "Apple Silicon"
    elif intel_mac:
        chip = brand or "Intel Mac"
    else:
        chip = f"{system} {machine}".strip()
    pair = [
        {"name": SMALL_MODEL, "role": "small", "listed_size": SMALL_SIZE},
        {"name": LARGE_MODEL, "role": "large", "listed_size": LARGE_SIZE},
    ]
    if memory_bytes is None:
        return {
            "chip": chip,
            "comparison_ready": False,
            "memory_bytes": None,
            "models": pair,
            "note": "RAM was not detected. Both tags are listed, and nothing should be pulled until RAM is known.",
            "pull": [],
        }
    gib = memory_bytes / GIB
    if gib < 8:
        return {
            "chip": chip,
            "comparison_ready": False,
            "memory_bytes": memory_bytes,
            "models": pair,
            "note": "Under 8 GiB. Only the 0.5B tag is suggested. The 1.5B comparison is not recommended on this RAM.",
            "pull": [SMALL_MODEL],
        }
    if gib < 16:
        note = (
            "8 to 16 GiB. Both tags can be pulled. 1.5B is about 986MB on the Ollama page "
            "and is tight beside macOS on an 8 GiB machine."
        )
    else:
        note = "16 GiB or more. Both tags fit more comfortably. This is not a measure of speed."
    if intel_mac:
        note += " Ollama's macOS page says Intel Macs run on CPU only."
    if not apple and not intel_mac:
        note += " This host is not a Mac. The tags are the same pair a Mac setup would pull."
    return {
        "chip": chip,
        "comparison_ready": True,
        "memory_bytes": memory_bytes,
        "models": pair,
        "note": note,
        "pull": [SMALL_MODEL, LARGE_MODEL],
    }


def detect_hardware(run=subprocess.run) -> dict:
    """Detect this process's machine. Darwin memory comes from sysctl, not a guess."""
    host = detect_host()
    brand = ""
    if host["system"] == "Darwin":
        memory = _sysctl_int(["sysctl", "-n", "hw.memsize"], run)
        if memory is not None:
            host["memory_bytes"] = memory
        brand = _sysctl_text(["sysctl", "-n", "machdep.cpu.brand_string"], run)
    host["suggestion"] = suggest_models(
        system=host["system"],
        machine=host["machine"],
        memory_bytes=host["memory_bytes"],
        brand=brand,
    )
    return host


def _sysctl_int(args: list[str], run) -> int | None:
    text = _sysctl_text(args, run)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _sysctl_text(args: list[str], run) -> str | None:
    try:
        completed = run(args, capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip()
    return text or None
