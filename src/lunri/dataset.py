"""Synthetic invoice texts and independent labels. The model prompt is the text only."""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20261118

INSTRUCTIONS = (
    "Extract fields from the invoice text. "
    "invoice_number is the invoice id. "
    "total_cents is the amount due as an integer number of cents. "
    "currency is a three-letter code. "
    "subtotal_cents and tax_cents are optional integers in cents, or null. "
    "Use null when a field is not stated. "
    "Do not invent an amount from a phone number, account number, or reference. "
    "Reply with one JSON object."
)

# Whole families stay inside one split so near-duplicate layouts do not leak.
FAMILIES = (
    {"family": "dev_ledger", "split": "dev", "kind": "ledger", "count": 12},
    {"family": "dev_memo", "split": "dev", "kind": "memo", "count": 12},
    {"family": "dev_gap", "split": "dev", "kind": "missing_total", "count": 6},
    {"family": "hold_block", "split": "heldout", "kind": "block", "count": 12},
    {"family": "hold_distract", "split": "heldout", "kind": "distract", "count": 12},
    {"family": "hold_gap", "split": "heldout", "kind": "missing_amount", "count": 6},
    {"family": "smoke_plain", "split": "smoke", "kind": "smoke", "count": 3},
)

CURRENCIES = ("USD", "EUR", "GBP")


def dataset_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "dataset.jsonl"


def generate(seed: int = SEED) -> list[dict]:
    """Build the fixed synthetic set. Same seed, same rows."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for spec in FAMILIES:
        for index in range(spec["count"]):
            rows.append(_row(rng, spec["family"], spec["split"], spec["kind"], index))
    return rows


def dumps(rows: list[dict]) -> str:
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows]
    return "\n".join(lines) + "\n"


def load_dataset(path: Path | None = None) -> list[dict]:
    source = path if path is not None else dataset_path()
    rows = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def select_split(rows: list[dict], split: str) -> list[dict]:
    return [row for row in rows if row["split"] == split]


def messages_for(row: dict) -> list[dict]:
    """Prompt payload. Gold labels are not included."""
    return [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": row["text"]},
    ]


def _row(rng: random.Random, family: str, split: str, kind: str, index: int) -> dict:
    number = f"{family}-{index:03d}"
    currency = CURRENCIES[index % len(CURRENCIES)]
    cents = 1000 + index * 137 + rng.randrange(0, 50)
    # Keep the cent integer out of the prose. The text shows a decimal amount.
    for _ in range(20):
        text, gold = _render(kind, number, currency, cents)
        if str(cents) not in text:
            break
        cents += 3
    else:
        raise RuntimeError(f"could not keep {cents} out of the text for {number}")
    return {
        "family": family,
        "gold": gold,
        "id": f"{split}-{number}",
        "kind": kind,
        "split": split,
        "synthetic": True,
        "text": text,
    }


def _money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def _render(kind: str, number: str, currency: str, cents: int) -> tuple[str, dict]:
    money = _money(cents)
    banner = "SYNTHETIC INVOICE. Not a real invoice, vendor, person, or payment."
    if kind in {"ledger", "smoke"}:
        text = f"{banner}\nInvoice number: {number}\nTotal: {money} {currency}\n"
        gold = {"currency": currency, "invoice_number": number, "total_cents": cents}
    elif kind == "memo":
        text = (
            f"{banner}\nPlease remit {money} {currency} for invoice {number}.\n"
            "The reference code 100.00 is not the amount due.\n"
        )
        gold = {"currency": currency, "invoice_number": number, "total_cents": cents}
    elif kind == "missing_total":
        text = f"{banner}\nInvoice number: {number}\nAmount due: see attachment\n"
        gold = {"currency": None, "invoice_number": number, "total_cents": None}
    elif kind == "block":
        text = f"{banner}\nINVOICE\nNo. {number}\nAmount due: {currency} {money}\n"
        gold = {"currency": currency, "invoice_number": number, "total_cents": cents}
    elif kind == "distract":
        text = (
            f"{banner}\nPhone: 555-0199\nAccount: 404\nSubtotal: 1.00 {currency}\n"
            f"Invoice number: {number}\nTotal: {money} {currency}\n"
        )
        gold = {"currency": currency, "invoice_number": number, "total_cents": cents}
    elif kind == "missing_amount":
        text = f"{banner}\nNumber {number}\nBalance will be sent later.\n"
        gold = {"currency": None, "invoice_number": number, "total_cents": None}
    else:
        raise ValueError(kind)
    return text, gold
