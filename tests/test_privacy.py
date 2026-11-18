"""Raw invoice text and environment secrets stay out of the default record."""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone

from lunri.fixture import load_cases
from lunri.run import execute_case


class PrivacyTests(unittest.TestCase):
    def test_default_record_drops_raw_text_and_a_planted_secret(self) -> None:
        secret = "SECRET-TOKEN-lunri"
        os.environ["OPENAI_API_KEY"] = secret
        try:
            case = dict(next(item for item in load_cases() if item["id"] == "syn-001"))
            case["text"] = case["text"] + secret + "\n"
            case["raw"] = case["text"].encode("utf-8")
            record = execute_case(
                case,
                created_at=datetime(2026, 11, 18, 17, 0, tzinfo=timezone.utc),
            )
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
        blob = json.dumps(record)
        self.assertNotIn(secret, blob)
        self.assertNotIn("Fixture Goods LLC", blob)
        self.assertFalse(record["privacy"]["raw_text_stored"])
        self.assertFalse(record["privacy"]["telemetry"])
        self.assertFalse(record["privacy"]["upload"])
        self.assertNotIn("raw_text", record)

    def test_keep_raw_text_is_explicit(self) -> None:
        case = next(item for item in load_cases() if item["id"] == "syn-001")
        record = execute_case(
            case,
            created_at=datetime(2026, 11, 18, 17, 0, tzinfo=timezone.utc),
            keep_raw_text=True,
        )
        self.assertTrue(record["privacy"]["raw_text_stored"])
        self.assertIn("SYNTHETIC INVOICE", record["raw_text"])

    def test_injected_malformed_response_stays_labeled_and_unquoted(self) -> None:
        case = next(item for item in load_cases() if item["id"] == "syn-001")
        secret = "SECRET-TOKEN-lunri"
        record = execute_case(
            case,
            created_at=datetime(2026, 11, 18, 17, 0, tzinfo=timezone.utc),
            responder=lambda _text: secret,
        )
        self.assertEqual(record["status"], "error")
        self.assertEqual(record["response_label"], "SIMULATED")
        self.assertEqual(record["energy"]["label"], "SIMULATED")
        self.assertIsNone(record["energy"]["joules"])
        self.assertNotIn(secret, json.dumps(record))


if __name__ == "__main__":
    unittest.main()
