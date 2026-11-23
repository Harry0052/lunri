"""Versioned fixture checks. This module does not call a model or a meter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lunri.dataset import SEED

SCHEMA_VERSION = 1
PROMPT_VERSION = "invoice-extract-1"
NORMALIZATION_ID = "exact-cents-v1"
NORMALIZATION = (
    "Exact match on invoice_number, total_cents, and currency. "
    "Null matches null. Amounts are integer cents with no rounding tolerance. "
    "A response that parses and still misses a field is wrong, not a parse failure."
)
WARMUP_POLICY = (
    "none; no calls are discarded. The meter window starts at the first scored item "
    "and includes every call, validation, retry, and fallback in that arm."
)
MAX_FILE_BYTES = 2_000_000
MAX_LINE_BYTES = 16_384
MAX_ROWS = 500
MAX_TEXT_CHARS = 8_000
SPLITS = frozenset({"dev", "heldout", "smoke"})


class ContractError(ValueError):
    """The fixture failed a published check. ``errors`` is safe to print."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def fixture_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "fixture_manifest.json"


def load_fixture_manifest() -> dict:
    path = fixture_manifest_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError([f"cannot read fixture manifest {path.name}: {exc.__class__.__name__}"]) from exc
    return data


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_dataset_bytes(raw: bytes) -> list[dict]:
    """Return rows or raise ``ContractError`` with one actionable line per problem."""
    if len(raw) > MAX_FILE_BYTES:
        raise ContractError(
            [f"fixture is {len(raw)} bytes, which is over the {MAX_FILE_BYTES} byte limit"]
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(["fixture is not UTF-8"]) from exc
    if not text.strip():
        raise ContractError(["fixture is empty"])

    errors: list[str] = []
    rows: list[dict] = []
    families: dict[str, str] = {}
    seen_ids: set[str] = set()
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        encoded = line.encode("utf-8")
        if len(encoded) > MAX_LINE_BYTES:
            errors.append(
                f"line {index}: {len(encoded)} bytes is over the {MAX_LINE_BYTES} byte line limit"
            )
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line {index}: not a JSON object")
            continue
        if not isinstance(item, dict):
            errors.append(f"line {index}: JSON value is not an object")
            continue
        row_errors = _row_errors(item, f"line {index}")
        if row_errors:
            errors.extend(row_errors)
            continue
        item_id = item["id"]
        if item_id in seen_ids:
            errors.append(f"line {index}: duplicate id {item_id}")
        seen_ids.add(item_id)
        family = item["family"]
        split = item["split"]
        previous = families.get(family)
        if previous is not None and previous != split:
            errors.append(
                f"line {index}: family {family} appears in splits {previous} and {split}"
            )
        families[family] = split
        rows.append(item)
    if len(rows) + len(errors) == 0:
        errors.append("fixture has no rows")
    if len(rows) > MAX_ROWS:
        errors.append(f"fixture has {len(rows)} rows; limit is {MAX_ROWS}")
    if errors:
        raise ContractError(errors)
    return rows


def check_packaged_checksum(raw: bytes, manifest: dict) -> None:
    digest = sha256_bytes(raw)
    expected = manifest.get("sha256")
    if digest != expected:
        raise ContractError([f"fixture sha256 {digest} does not match manifest {expected}"])
    if manifest.get("seed") != SEED:
        raise ContractError([f"fixture manifest seed must be {SEED}"])
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(
            [f"fixture manifest schema_version must be {SCHEMA_VERSION}"]
        )


def _row_errors(item: dict, prefix: str) -> list[str]:
    errors: list[str] = []
    if item.get("synthetic") is not True:
        errors.append(f"{prefix}: synthetic must be true")
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        errors.append(f"{prefix}: id must be a non-empty string")
    if item.get("split") not in SPLITS:
        errors.append(f"{prefix}: split must be one of dev, heldout, smoke")
    family = item.get("family")
    if not isinstance(family, str) or not family.strip():
        errors.append(f"{prefix}: family must be a non-empty string")
    kind = item.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        errors.append(f"{prefix}: kind must be a non-empty string")
    text = item.get("text")
    if not isinstance(text, str):
        errors.append(f"{prefix}: text must be a string")
        text = ""
    else:
        if len(text) > MAX_TEXT_CHARS:
            errors.append(f"{prefix}: text is {len(text)} characters; limit is {MAX_TEXT_CHARS}")
        if "SYNTHETIC" not in text:
            errors.append(f"{prefix}: text must contain the SYNTHETIC marker")
    gold = item.get("gold")
    if not isinstance(gold, dict):
        errors.append(f"{prefix}: gold must be an object with invoice_number, total_cents, and currency")
    else:
        errors.extend(_gold_errors(gold, text, prefix))
    return errors


def _gold_errors(gold: dict, text: str, prefix: str) -> list[str]:
    errors: list[str] = []
    extra = sorted(set(gold) - {"currency", "invoice_number", "total_cents"})
    if extra:
        errors.append(f"{prefix}: gold has unknown fields {', '.join(extra)}")
    invoice = gold.get("invoice_number")
    if not isinstance(invoice, str) or not invoice.strip():
        errors.append(f"{prefix}: gold.invoice_number must be a non-empty string")
    if "total_cents" not in gold:
        errors.append(f"{prefix}: gold.total_cents is required")
    else:
        total = gold["total_cents"]
        if total is not None and (type(total) is not int or total < 0):
            errors.append(f"{prefix}: gold.total_cents must be a non-negative integer or null")
        elif isinstance(total, int) and str(total) in text:
            errors.append(
                f"{prefix}: gold.total_cents {total} appears in the text; keep the cent integer out of the prompt"
            )
    if "currency" not in gold:
        errors.append(f"{prefix}: gold.currency is required")
    else:
        currency = gold["currency"]
        if currency is not None and (
            not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or currency != currency.upper()
        ):
            errors.append(f"{prefix}: gold.currency must be three uppercase letters or null")
    return errors
