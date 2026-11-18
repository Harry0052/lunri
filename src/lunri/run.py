"""Run one invoice text through the mock model and build a record."""

from __future__ import annotations

from datetime import datetime

from lunri.energy import describe_sensor
from lunri.hostinfo import detect_host
from lunri.mock_model import MODEL_NAME, complete
from lunri.privacy import privacy_defaults
from lunri.records import build_record
from lunri.response import parse_model_response


def execute_case(
    case: dict,
    *,
    created_at: datetime,
    keep_raw_text: bool = False,
    responder=None,
) -> dict:
    """Extract fields from ``case['text']``. ``responder`` overrides the mock in tests."""
    produce = responder if responder is not None else complete
    payload = produce(case["text"])
    output, errors = parse_model_response(payload)
    privacy = privacy_defaults()
    record = build_record(
        model=MODEL_NAME,
        case_id=case["id"],
        fixture_name=case["name"],
        fixture_bytes=case["raw"],
        created_at=created_at,
        status="ok" if not errors else "error",
        output=output,
        energy=describe_sensor(),
        errors=errors,
        privacy=privacy,
        host=detect_host(),
    )
    if keep_raw_text:
        record["privacy"]["raw_text_stored"] = True
        record["raw_text"] = case["text"]
    return record
