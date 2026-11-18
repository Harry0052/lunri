"""Packaged invoice texts stay synthetic and separate from gold labels."""

from __future__ import annotations

import unittest

from lunri.fixture import load_cases, select_cases


class FixtureTests(unittest.TestCase):
    def test_packaged_texts_are_marked_synthetic(self) -> None:
        cases = load_cases()
        self.assertEqual([case["id"] for case in cases], ["syn-001", "syn-002", "syn-003"])
        for case in cases:
            self.assertIn("SYNTHETIC", case["text"])
            self.assertTrue(case["sha256"])
            self.assertNotIn("labels", case["text"])

    def test_default_selection_skips_the_malformed_input(self) -> None:
        cases = load_cases()
        chosen = select_cases(cases)
        self.assertEqual([case["id"] for case in chosen], ["syn-001", "syn-002"])
        self.assertEqual([case["id"] for case in select_cases(cases, include_all=True)], ["syn-001", "syn-002", "syn-003"])


if __name__ == "__main__":
    unittest.main()
