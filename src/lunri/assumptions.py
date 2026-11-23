"""Turn token counts into watt-hours using cited measurements, or leave the field empty."""

from __future__ import annotations

import json
from pathlib import Path

JOULES_PER_WH = 3600.0


def assumptions_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "energy_assumptions.json"


def load_assumptions() -> list[dict]:
    data = json.loads(assumptions_path().read_text(encoding="utf-8"))
    return list(data["assumptions"])


def find_assumption(assumption_id: str | None) -> dict | None:
    if not assumption_id or assumption_id == "none":
        return None
    for item in load_assumptions():
        if item["id"] == assumption_id:
            return item
    known = ", ".join(item["id"] for item in load_assumptions())
    raise ValueError(f"unknown energy assumption {assumption_id}. known: {known}")


def watt_hours(output_tokens: int | None, assumption: dict | None) -> float | None:
    """Estimate watt-hours from output tokens. None when no cited figure applies."""
    if assumption is None or output_tokens is None:
        return None
    joules = assumption.get("joules_per_output_token")
    if joules is None:
        return None
    return output_tokens * float(joules) / JOULES_PER_WH


def assumption_note(assumption: dict | None) -> str:
    if assumption is None:
        return "not estimated. No cited energy assumption was selected."
    return (
        "ESTIMATE. Not a measurement of this computer. "
        f"{assumption['detail']} Boundary: {assumption['boundary']} Source: {assumption['source']}"
    )
