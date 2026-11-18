"""Deterministic stand-in that reads invoice text. It does not see gold labels."""

from __future__ import annotations

import json
import re

MODEL_NAME = "mock-deterministic"

INVOICE_RE = re.compile(r"(?m)^Invoice number:\s*(\S+)\s*$")
TOTAL_RE = re.compile(r"(?m)^Total:\s*([0-9]+\.[0-9]{2})\s+([A-Z]{3})\s*$")


def dollars_to_cents(amount: str) -> int:
    """Convert a two-decimal dollar string to integer cents without floats."""
    whole, frac = amount.split(".")
    return int(whole) * 100 + int(frac)


def complete(text: str) -> str:
    """Return one JSON object as text. The same input always returns the same text.

    A field is filled only when the text has exactly one matching line.
    ``Total:`` does not match ``Subtotal:``. No clock, randomness, or network.
    """
    numbers = INVOICE_RE.findall(text)
    totals = TOTAL_RE.findall(text)
    invoice_number = numbers[0] if len(numbers) == 1 else None
    if len(totals) == 1:
        amount, currency = totals[0]
        total_cents = dollars_to_cents(amount)
    else:
        total_cents = None
        currency = None
    body = {
        "currency": currency,
        "invoice_number": invoice_number,
        "total_cents": total_cents,
    }
    return json.dumps(body, separators=(",", ":"), sort_keys=True)
