"""Turn a model response string into fields. Bad strings are failures, not guesses."""

from __future__ import annotations

import json
import re

REQUIRED = ("currency", "invoice_number", "total_cents")
OPTIONAL = ("subtotal_cents", "tax_cents")
FIELDS = REQUIRED + OPTIONAL
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def empty_output() -> dict:
    return {
        "currency": None,
        "invoice_number": None,
        "subtotal_cents": None,
        "tax_cents": None,
        "total_cents": None,
    }


def parse_model_response(payload: str) -> tuple[dict, list[str]]:
    """Parse one response. Error text does not echo the payload."""
    if payload.strip() == "":
        return empty_output(), ["malformed response: empty"]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return empty_output(), ["malformed response: not JSON"]
    if not isinstance(data, dict):
        return empty_output(), ["malformed response: JSON value is not an object"]

    extra = sorted(set(data) - set(FIELDS))
    missing_keys = sorted(set(REQUIRED) - set(data))
    if extra or missing_keys:
        errors: list[str] = []
        if missing_keys:
            errors.append("malformed response: missing " + ", ".join(missing_keys))
        if extra:
            errors.append("malformed response: unknown " + ", ".join(extra))
        return empty_output(), errors

    output = empty_output()
    errors = []
    invoice_number = data["invoice_number"]
    if invoice_number is None:
        errors.append("missing invoice_number")
    elif isinstance(invoice_number, str) and invoice_number.strip():
        output["invoice_number"] = invoice_number
    else:
        errors.append("malformed response: invoice_number must be a string or null")

    total = data["total_cents"]
    if total is None:
        errors.append("missing total_cents")
    elif type(total) is int and total >= 0:
        output["total_cents"] = total
    else:
        errors.append("malformed response: total_cents must be a non-negative integer or null")

    currency = data["currency"]
    if currency is None:
        errors.append("missing currency")
    elif isinstance(currency, str) and CURRENCY_RE.fullmatch(currency):
        output["currency"] = currency
    else:
        errors.append("malformed response: currency must be three uppercase letters or null")

    for key in OPTIONAL:
        if key not in data or data[key] is None:
            output[key] = None
            continue
        value = data[key]
        if type(value) is int and value >= 0:
            output[key] = value
        else:
            errors.append(f"malformed response: {key} must be a non-negative integer or null")
    return output, errors
