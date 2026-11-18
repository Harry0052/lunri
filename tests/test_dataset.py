"""The labeled set is deterministic, and prompts do not carry gold objects."""

from __future__ import annotations

import json
import unittest

from lunri.dataset import dumps, generate, load_dataset, messages_for


class DatasetTests(unittest.TestCase):
    def test_regeneration_matches_the_committed_file(self) -> None:
        self.assertEqual(dumps(generate()), dumps(load_dataset()))

    def test_families_do_not_cross_splits(self) -> None:
        seen: dict[str, str] = {}
        for row in load_dataset():
            self.assertTrue(row["synthetic"])
            self.assertIn("SYNTHETIC", row["text"])
            previous = seen.setdefault(row["family"], row["split"])
            self.assertEqual(previous, row["split"])
        splits = {row["split"] for row in load_dataset()}
        self.assertEqual(splits, {"dev", "heldout", "smoke"})

    def test_prompt_is_the_invoice_text_and_not_the_gold_object(self) -> None:
        for row in load_dataset():
            message = messages_for(row)
            self.assertEqual(message[1]["content"], row["text"])
            blob = json.dumps(message)
            self.assertNotIn('"gold"', blob)
            cents = row["gold"]["total_cents"]
            if cents is not None:
                self.assertNotIn(str(cents), row["text"])


if __name__ == "__main__":
    unittest.main()
