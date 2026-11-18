"""Load the packaged synthetic invoice texts. Labels live in a separate module."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class FixtureError(ValueError):
    """A fixture file is missing or is not marked synthetic."""


def data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def load_manifest() -> dict:
    path = data_dir() / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"cannot read manifest {path}: {exc}") from exc
    if data.get("synthetic") is not True:
        raise FixtureError("manifest synthetic must be true")
    if not isinstance(data.get("cases"), list) or not data["cases"]:
        raise FixtureError("manifest cases must be a non-empty array")
    return data


def load_cases() -> list[dict]:
    """Return each packaged invoice text. This does not read labels.json."""
    manifest = load_manifest()
    cases: list[dict] = []
    for item in manifest["cases"]:
        path = data_dir() / item["file"]
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise FixtureError(f"cannot read {path}: {exc}") from exc
        if "SYNTHETIC" not in text:
            raise FixtureError(f"{path.name} is not marked SYNTHETIC")
        cases.append(
            {
                "id": item["id"],
                "name": path.name,
                "path": path,
                "raw": raw,
                "role": item["role"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "text": text,
            }
        )
    return cases


def select_cases(
    cases: list[dict],
    *,
    case_id: str | None = None,
    include_all: bool = False,
) -> list[dict]:
    if case_id:
        matched = [case for case in cases if case["id"] == case_id]
        if not matched:
            known = ", ".join(case["id"] for case in cases)
            raise FixtureError(f"unknown case {case_id}. known cases: {known}")
        return matched
    if include_all:
        return list(cases)
    return [case for case in cases if case["role"] == "success"]
