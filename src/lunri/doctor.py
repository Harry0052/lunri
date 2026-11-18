"""Local health check. It does not read keys, call a model service, or sample energy."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from lunri import __version__
from lunri.energy import describe_sensor
from lunri.fixture import FixtureError, load_cases
from lunri.hostinfo import detect_host
from lunri.mock_model import MODEL_NAME, complete
from lunri.response import parse_model_response

CHECK_ORDER = (
    "python",
    "fixture",
    "mock_model",
    "run_records",
    "privacy",
    "secrets",
    "ollama",
    "energy_sensor",
    "simulator",
)


def report(
    runs_dir: Path,
    repo_root: Path | None = None,
    tool_finder=shutil.which,
) -> dict:
    checks = [
        _python_check(),
        _fixture_check(),
        _mock_check(),
        _records_check(runs_dir),
        _privacy_check(),
        _secrets_check(),
        _ollama_check(tool_finder),
        _energy_check(),
        _simulator_check(repo_root if repo_root is not None else Path.cwd()),
    ]
    by_name = {check["name"]: check for check in checks}
    ordered = [by_name[name] for name in CHECK_ORDER]
    ok = all(check["status"] != "fail" for check in ordered if check["required"])
    host = detect_host()
    return {
        "benchmark": False,
        "checks": ordered,
        "host": host,
        "ok": ok,
        "tool": "lunri",
        "version": __version__,
    }


def format_text(report_body: dict) -> str:
    host = report_body["host"]
    memory = host["memory_bytes"]
    memory_text = "unknown" if memory is None else f"{memory // (1024 * 1024)} MiB"
    lines = [
        f"lunri {report_body['version']} doctor",
        "  note             not a benchmark. No model was called. Energy was not sampled.",
        (
            f"  host             {host['system']} {host['release']} {host['machine']}"
            f"  cpus={host['cpu_count']}  mem={memory_text}  Python {host['python']}"
        ),
    ]
    for check in report_body["checks"]:
        scope = "required" if check["required"] else "optional"
        lines.append(
            f"  {check['name']:<16} {check['status']:<4} {scope:<8} {check['detail']}"
        )
    lines.append("required checks passed" if report_body["ok"] else "required checks failed")
    return "\n".join(lines) + "\n"


def _check(name: str, status: str, required: bool, detail: str) -> dict:
    return {"detail": detail, "name": name, "required": required, "status": status}


def _python_check() -> dict:
    version = sys.version
    short = sys.version.split()[0]
    if sys.version_info >= (3, 11):
        return _check("python", "pass", True, short)
    return _check("python", "fail", True, f"{version} is older than 3.11")


def _fixture_check() -> dict:
    try:
        cases = load_cases()
    except FixtureError as exc:
        return _check("fixture", "fail", True, str(exc))
    ids = ", ".join(case["id"] for case in cases)
    return _check("fixture", "pass", True, f"{len(cases)} synthetic texts ({ids})")


def _mock_check() -> dict:
    try:
        cases = load_cases()
    except FixtureError as exc:
        return _check("mock_model", "fail", True, str(exc))
    sample = next(case for case in cases if case["id"] == "syn-001")
    first = complete(sample["text"])
    second = complete(sample["text"])
    if first != second:
        return _check("mock_model", "fail", True, f"{MODEL_NAME} returned two different strings")
    output, errors = parse_model_response(first)
    if errors or output["invoice_number"] != "SYN-2026-0001" or output["total_cents"] != 2105:
        return _check("mock_model", "fail", True, f"{MODEL_NAME} did not extract syn-001")
    return _check(
        "mock_model",
        "pass",
        True,
        f"SIMULATED {MODEL_NAME} syn-001 total_cents=2105",
    )


def _records_check(runs_dir: Path) -> dict:
    probe = runs_dir / ".doctor-write-probe"
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return _check("run_records", "fail", True, f"cannot write {runs_dir}: {exc}")
    return _check("run_records", "pass", True, f"writable {runs_dir}")


def _privacy_check() -> dict:
    return _check(
        "privacy",
        "pass",
        True,
        "local only; telemetry off; raw invoice text is not stored unless --keep-raw-text",
    )


def _secrets_check() -> dict:
    return _check("secrets", "pass", True, "no API key is read or required")


def _ollama_check(tool_finder) -> dict:
    found = tool_finder("ollama")
    if found:
        return _check(
            "ollama",
            "pass",
            False,
            f"found at {found}. This stage does not call it.",
        )
    return _check(
        "ollama",
        "skip",
        False,
        "not on PATH. Optional. See docs/MACOS.md before any real local model.",
    )


def _energy_check() -> dict:
    sensor = describe_sensor()
    detail = sensor["reason"]
    if sensor["sensor"] == "none":
        return _check("energy_sensor", "skip", False, detail)
    return _check("energy_sensor", "pass", False, detail)


def _simulator_check(root: Path) -> dict:
    expected = ("Lunri_Lab.zip", "Lunri_YC_Application.md")
    found = [name for name in expected if (root / name).is_file()]
    if found:
        return _check("simulator", "pass", False, "found " + ", ".join(found) + ". Leave it labeled as a simulation.")
    return _check(
        "simulator",
        "skip",
        False,
        "Lunri_Lab.zip and Lunri_YC_Application.md were not provided. No simulator to preserve.",
    )
