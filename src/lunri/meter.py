"""Energy windows. A missing meter returns null, not zero."""

from __future__ import annotations

import re
import shutil
import subprocess

COMBINED_RE = re.compile(r"Combined Power \(CPU \+ GPU \+ ANE\):\s*([0-9]+(?:\.[0-9]+)?)\s*mW")
CPU_RE = re.compile(r"^CPU Power:\s*([0-9]+(?:\.[0-9]+)?)\s*mW\s*$", re.MULTILINE)


def unavailable(reason: str) -> dict:
    return {
        "aggregate_joules": None,
        "boundary": None,
        "derived_per_attempt_joules": None,
        "estimate": False,
        "interval_s": None,
        "label": "UNAVAILABLE",
        "measured": False,
        "method": None,
        "reason": reason,
        "samples": 0,
    }


def measured_aggregate(joules: float, *, boundary: str, method: str, interval_s: float, samples: int) -> dict:
    return {
        "aggregate_joules": joules,
        "boundary": boundary,
        "derived_per_attempt_joules": None,
        "estimate": False,
        "interval_s": interval_s,
        "label": "MEASURED",
        "measured": True,
        "method": method,
        "reason": "aggregate window, not a per-task meter reading",
        "samples": samples,
    }


def with_derived(reading: dict, attempts: int) -> dict:
    """Attach a batch average without pretending each task was metered."""
    updated = dict(reading)
    joules = reading.get("aggregate_joules")
    if reading.get("label") == "MEASURED" and joules is not None and attempts > 0:
        updated["derived_per_attempt_joules"] = joules / attempts
        updated["reason"] = (
            "aggregate window divided by attempts. This is not a per-task measurement."
        )
    return updated


class NullMeter:
    def __init__(self, reason: str):
        self.reason = reason

    def measure(self, work):
        value = work()
        return value, unavailable(self.reason)


class ScriptedMeter:
    """Test fixture with a known joule total. Not a physical result."""

    def __init__(self, joules: float, boundary: str = "injected"):
        self.joules = joules
        self.boundary = boundary

    def measure(self, work):
        value = work()
        reading = measured_aggregate(
            self.joules,
            boundary=self.boundary,
            method="injected-test-meter",
            interval_s=1,
            samples=1,
        )
        reading["label"] = "SIMULATED"
        reading["measured"] = False
        reading["reason"] = "HYPOTHETICAL injected meter for a test. Not a physical result."
        return value, reading


def parse_combined_mw(text: str) -> list[float]:
    """Use only the combined CPU+GPU+ANE line, so rails are not added twice."""
    return [float(match) for match in COMBINED_RE.findall(text)]


def parse_cpu_mw(text: str) -> list[float]:
    return [float(match) for match in CPU_RE.findall(text)]


def integrate_joules(samples_mw: list[float], interval_s: float) -> float | None:
    if not samples_mw or interval_s <= 0:
        return None
    watts = [sample / 1000 for sample in samples_mw]
    return sum(watts) * interval_s


def reading_from_powermetrics_text(text: str, interval_s: float) -> dict:
    combined = parse_combined_mw(text)
    if combined:
        joules = integrate_joules(combined, interval_s)
        if joules is None:
            return unavailable("powermetrics combined samples could not be integrated")
        return measured_aggregate(
            joules,
            boundary="apple-silicon-soc-cpu-gpu-ane",
            method="powermetrics combined power",
            interval_s=interval_s,
            samples=len(combined),
        )
    cpu = parse_cpu_mw(text)
    if cpu:
        joules = integrate_joules(cpu, interval_s)
        if joules is None:
            return unavailable("powermetrics CPU samples could not be integrated")
        reading = measured_aggregate(
            joules,
            boundary="cpu-power-sampler-only",
            method="powermetrics CPU Power line",
            interval_s=interval_s,
            samples=len(cpu),
        )
        reading["reason"] = "CPU sampler only. GPU, ANE, and the rest of the machine are not included."
        return reading
    return unavailable("powermetrics output had no Combined Power or CPU Power sample")


def powermetrics_command(samples: int, interval_ms: int = 1000) -> list[str]:
    """Non-interactive sudo. It fails closed when the credential cache is empty."""
    return [
        "sudo",
        "-n",
        "powermetrics",
        "--samplers",
        "cpu_power,gpu_power,ane_power",
        "-i",
        str(interval_ms),
        "-n",
        str(samples),
    ]


class HostMeter:
    """Run powermetrics only on Darwin when asked. Otherwise return unavailable."""

    def __init__(self, *, enabled: bool, system: str, interval_s: float = 1, samples: int = 5):
        self.enabled = enabled
        self.system = system
        self.interval_s = interval_s
        self.samples = samples

    def measure(self, work):
        if not self.enabled:
            value = work()
            return value, unavailable("energy sampling was not requested")
        if self.system != "Darwin":
            value = work()
            return value, unavailable("powermetrics is a macOS tool and was not run")
        if shutil.which("powermetrics") is None:
            value = work()
            return value, unavailable("powermetrics is not on PATH")
        # The work runs after the command is built. Sampling itself is best-effort
        # and never prompts for a password.
        command = powermetrics_command(self.samples, int(self.interval_s * 1000))
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as exc:
            value = work()
            return value, unavailable(f"powermetrics could not be started: {exc.__class__.__name__}")
        value = work()
        process.terminate()
        try:
            stdout, _stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _stderr = process.communicate()
        if not stdout:
            return value, unavailable(
                "powermetrics produced no output. sudo -n does not prompt for a password."
            )
        return value, reading_from_powermetrics_text(stdout, self.interval_s)
