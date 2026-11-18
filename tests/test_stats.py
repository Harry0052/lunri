"""Hand-checked interval, quality gate, and break-even cases."""

from __future__ import annotations

import math
import unittest

from lunri.reporting import hypothetical_cases
from lunri.stats import Z_95, break_even, quality_gate, wilson_interval


class StatsTests(unittest.TestCase):
    def test_wilson_matches_the_hand_calculation_for_50_of_100(self) -> None:
        interval = wilson_interval(50, 100, z=1.96)
        z = 1.96
        attempts = 100
        phat = 0.5
        z2 = z * z
        denom = 1 + z2 / attempts
        center = (phat + z2 / (2 * attempts)) / denom
        margin = z * math.sqrt(phat * (1 - phat) / attempts + z2 / (4 * attempts * attempts)) / denom
        self.assertAlmostEqual(interval["low"], center - margin)
        self.assertAlmostEqual(interval["high"], center + margin)
        self.assertAlmostEqual(interval["low"], 0.4038, places=3)
        self.assertAlmostEqual(interval["high"], 0.5962, places=3)
        self.assertEqual(Z_95, 1.96)

    def test_small_samples_and_crossing_intervals_are_inconclusive(self) -> None:
        self.assertEqual(quality_gate(correct=29, attempts=29, target=0.8, minimum_attempts=30), "inconclusive")
        self.assertEqual(quality_gate(correct=50, attempts=100, target=0.8, minimum_attempts=30), "misses_target")
        self.assertEqual(quality_gate(correct=0, attempts=0, target=0.8, minimum_attempts=30), "inconclusive")

    def test_break_even_cases(self) -> None:
        saving = break_even(
            overhead_joules=30,
            baseline_joules_per_attempt=10,
            candidate_joules_per_attempt=4,
            same_boundary=True,
            baseline_meets_quality=True,
            candidate_meets_quality=True,
        )
        self.assertEqual(saving["status"], "estimate")
        self.assertEqual(saving["attempts"], 5)
        never = break_even(
            overhead_joules=31,
            baseline_joules_per_attempt=4,
            candidate_joules_per_attempt=10,
            same_boundary=True,
            baseline_meets_quality=True,
            candidate_meets_quality=True,
        )
        self.assertEqual(never["status"], "never")
        self.assertIsNone(never["attempts"])
        missing = break_even(
            overhead_joules=None,
            baseline_joules_per_attempt=10,
            candidate_joules_per_attempt=4,
            same_boundary=True,
            baseline_meets_quality=True,
            candidate_meets_quality=True,
        )
        self.assertEqual(missing["status"], "unavailable")
        mismatch = break_even(
            overhead_joules=10,
            baseline_joules_per_attempt=10,
            candidate_joules_per_attempt=4,
            same_boundary=False,
            baseline_meets_quality=True,
            candidate_meets_quality=True,
        )
        self.assertEqual(mismatch["status"], "unavailable")
        quality = break_even(
            overhead_joules=10,
            baseline_joules_per_attempt=10,
            candidate_joules_per_attempt=4,
            same_boundary=True,
            baseline_meets_quality=True,
            candidate_meets_quality=False,
        )
        self.assertEqual(quality["status"], "unavailable")
        partial = break_even(
            overhead_joules=7,
            baseline_joules_per_attempt=10,
            candidate_joules_per_attempt=6,
            same_boundary=True,
            baseline_meets_quality=True,
            candidate_meets_quality=True,
        )
        self.assertEqual(partial["attempts"], math.ceil(7 / 4))

    def test_hypothetical_demo_is_labeled(self) -> None:
        cases = hypothetical_cases()
        self.assertTrue(all(case["label"] == "HYPOTHETICAL" for case in cases))
        by_name = {case["name"]: case["result"] for case in cases}
        self.assertEqual(by_name["saving"]["attempts"], 5)
        self.assertEqual(by_name["no-saving"]["status"], "never")
        self.assertEqual(by_name["missing-overhead"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
