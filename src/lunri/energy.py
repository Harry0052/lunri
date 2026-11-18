"""Report whether this host exposes an energy sensor. Do not sample it."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path


def describe_sensor() -> dict:
    """Describe the sensor interface only.

    Stage 1 never starts ``powermetrics`` and never reads a counter, so
    ``measured`` is false and ``joules`` is null on every host.
    """
    system = platform.system()
    powermetrics = shutil.which("powermetrics")
    rapl_root = Path("/sys/class/powercap")
    rapl = rapl_root.is_dir() and any(rapl_root.glob("intel-rapl:*"))
    supply_root = Path("/sys/class/power_supply")
    devices: list[str] = []
    if supply_root.is_dir():
        devices = sorted(path.name for path in supply_root.iterdir())

    if powermetrics:
        sensor = "powermetrics"
        reason = "powermetrics is on PATH. This stage does not sample it."
    elif rapl:
        sensor = "rapl"
        reason = "An Intel RAPL powercap device is present. This stage does not sample it."
    elif devices:
        sensor = "power_supply"
        joined = ", ".join(devices)
        reason = f"power_supply devices exist ({joined}). This stage does not sample them."
    else:
        sensor = "none"
        parts = [f"host is {system}"]
        if system == "Darwin":
            parts.append("powermetrics was not found on PATH")
        else:
            parts.append("powermetrics is a macOS tool and was not found")
        parts.append("no Intel RAPL powercap device")
        parts.append("no power_supply devices")
        parts.append("this stage does not sample energy")
        reason = "; ".join(parts)

    return {
        "estimate": False,
        "joules": None,
        "label": "SIMULATED",
        "measured": False,
        "reason": reason + ". Label SIMULATED: no wattage was measured or estimated.",
        "sensor": sensor,
    }
