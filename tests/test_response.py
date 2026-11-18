"""Malformed model strings fail without being echoed or repaired."""

from __future__ import annotations

import unittest

from lunri.response import parse_model_response


class ResponseTests(unittest.TestCase):
    def test_malformed_payloads_do_not_leak_into_the_error(self) -> None:
        secret = "SECRET-TOKEN-lunri"
        samples = [
            "",
            secret,
            "{",
            "[]",
            '{"invoice_number": ',
        ]
        for sample in samples:
            fields, errors = parse_model_response(sample)
            self.assertEqual(fields["invoice_number"], None)
            self.assertTrue(any(error.startswith("malformed response:") for error in errors))
            self.assertNotIn(secret, " ".join(errors))

    def test_wrong_types_are_malformed(self) -> None:
        payload = '{"currency": "USD", "invoice_number": 5, "total_cents": true}'
        _fields, errors = parse_model_response(payload)
        self.assertTrue(any("invoice_number" in error for error in errors))
        self.assertTrue(any("total_cents" in error for error in errors))

    def test_null_fields_are_missing_rather_than_malformed(self) -> None:
        payload = '{"currency": null, "invoice_number": "SYN-1", "total_cents": null}'
        fields, errors = parse_model_response(payload)
        self.assertEqual(fields["invoice_number"], "SYN-1")
        self.assertIn("missing total_cents", errors)
        self.assertIn("missing currency", errors)
        self.assertFalse(any(error.startswith("malformed response:") for error in errors))

    def test_a_valid_object_passes(self) -> None:
        payload = '{"currency": "USD", "invoice_number": "SYN-1", "total_cents": 2105}'
        fields, errors = parse_model_response(payload)
        self.assertEqual(errors, [])
        self.assertEqual(fields["total_cents"], 2105)


if __name__ == "__main__":
    unittest.main()
