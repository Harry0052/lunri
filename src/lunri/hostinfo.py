"""Read the machine this process is on. Missing values stay null."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def detect_host() -> dict:
    processor = platform.processor().strip()
    return {
        "cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "memory_bytes": memory_bytes(),
        "processor": processor or "unknown",
        "python": platform.python_version(),
        "release": platform.release(),
        "system": platform.system(),
    }


def memory_bytes() -> int | None:
    """Linux MemTotal, when /proc/meminfo exists. Other systems return null."""
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    return None
