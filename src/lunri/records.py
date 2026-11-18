"""Write one JSON file per run. Key order is stable so equal runs match byte for byte."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2


def run_id_for(model: str, fixture_bytes: bytes) -> str:
    """Identity of a model plus the exact fixture bytes. Independent of the clock."""
    digest = hashlib.sha256()
    digest.update(model.encode("utf-8"))
    digest.update(b"\0")
    digest.update(fixture_bytes)
    return digest.hexdigest()[:16]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def format_utc(moment: datetime) -> str:
    """Format an aware datetime as UTC with a trailing ``Z`` and no fractions."""
    if moment.tzinfo is None:
        raise ValueError("timestamp needs a timezone, for example 2026-11-18T17:00:00Z")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    """Parse an ISO-8601 timestamp. ``Z`` is accepted. A timezone is required."""
    normalized = text.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"could not parse timestamp {text!r}") from exc
    if moment.tzinfo is None:
        raise ValueError(f"timestamp {text!r} needs a timezone")
    return moment


def build_record(
    *,
    model: str,
    case_id: str,
    fixture_name: str,
    fixture_bytes: bytes,
    created_at: datetime,
    status: str,
    output: dict,
    energy: dict,
    errors: list[str],
    privacy: dict,
    host: dict,
) -> dict:
    return {
        "benchmark": False,
        "case_id": case_id,
        "created_at": format_utc(created_at),
        "energy": energy,
        "errors": list(errors),
        "fixture_name": fixture_name,
        "fixture_sha256": sha256_hex(fixture_bytes),
        "host": host,
        "model": model,
        "output": output,
        "privacy": privacy,
        "response_label": "SIMULATED",
        "run_id": run_id_for(model, fixture_bytes),
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "synthetic": True,
    }


def dumps(record: dict) -> str:
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def write_record(directory: Path, record: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['run_id']}.json"
    path.write_text(dumps(record), encoding="utf-8")
    return path
