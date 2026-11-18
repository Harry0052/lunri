"""The mock reads invoice text and does not import gold labels."""

from __future__ import annotations

import unittest
from pathlib import Path

from lunri.fixture import load_cases
from lunri.labels import load_labels
from lunri.mock_model import complete
from lunri.response import parse_model_response


class MockModelTests(unittest.TestCase):
    def test_mock_source_does_not_mention_the_label_file(self) -> None:
        source = Path(complete.__code__.co_filename).read_text(encoding="utf-8")
        self.assertNotIn("labels.json", source)
        self.assertNotIn("load_labels", source)
        self.assertNotIn("lunri.labels", source)

    def test_success_cases_match_independent_labels(self) -> None:
        labels = load_labels()
        for case in load_cases():
            if case["role"] != "success":
                continue
            first = complete(case["text"])
            second = complete(case["text"])
            self.assertEqual(first, second)
            fields, errors = parse_model_response(first)
            self.assertEqual(errors, [])
            for key, value in labels[case["id"]].items():
                self.assertEqual(fields[key], value)

    def test_distractors_do_not_become_the_total(self) -> None:
        case = next(item for item in load_cases() if item["id"] == "syn-002")
        self.assertIn("100.00 USD", case["text"])
        fields, errors = parse_model_response(complete(case["text"]))
        self.assertEqual(errors, [])
        self.assertEqual(fields["total_cents"], 1296)
        self.assertNotEqual(fields["total_cents"], 10000)

    def test_missing_total_line_is_a_field_failure(self) -> None:
        case = next(item for item in load_cases() if item["id"] == "syn-003")
        fields, errors = parse_model_response(complete(case["text"]))
        self.assertEqual(fields["invoice_number"], "SYN-2026-0003")
        self.assertIsNone(fields["total_cents"])
        self.assertIn("missing total_cents", errors)

    def test_two_total_lines_are_not_guessed(self) -> None:
        text = "SYNTHETIC\nInvoice number: SYN-X\nTotal: 1.00 USD\nTotal: 2.00 USD\n"
        fields, errors = parse_model_response(complete(text))
        self.assertIsNone(fields["total_cents"])
        self.assertIn("missing total_cents", errors)


if __name__ == "__main__":
    unittest.main()
