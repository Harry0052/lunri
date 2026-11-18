"""Runtime checks that never receive a gold label."""

from __future__ import annotations

import re

CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def validate(parsed: dict) -> dict:
    """Accept a shape-valid answer. A plausible wrong total still passes."""
    reasons: list[str] = []
    invoice = parsed.get("invoice_number")
    total = parsed.get("total_cents")
    currency = parsed.get("currency")
    if invoice is not None and (not isinstance(invoice, str) or not invoice.strip()):
        reasons.append("invoice_number is not a string")
    if total is not None and (type(total) is not int or total < 0):
        reasons.append("total_cents is not a non-negative integer")
    if currency is not None and (not isinstance(currency, str) or not CURRENCY_RE.fullmatch(currency)):
        reasons.append("currency is not three uppercase letters")
    subtotal = parsed.get("subtotal_cents")
    tax = parsed.get("tax_cents")
    if type(subtotal) is int and type(tax) is int and type(total) is int:
        if subtotal + tax != total:
            reasons.append("subtotal_cents plus tax_cents does not equal total_cents")
    return {"accept": not reasons, "reasons": reasons}
