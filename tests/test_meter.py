"""Powermetrics parsing and the guarantee that Linux does not launch it."""

from __future__ import annotations

import unittest

from lunri.meter import (
    HostMeter,
    integrate_joules,
    parse_combined_mw,
    powermetrics_command,
    reading_from_powermetrics_text,
)


SAMPLE = """
CPU Power: 336 mW
GPU Power: 197 mW
ANE Power: 0 mW
Combined Power (CPU + GPU + ANE): 533 mW
GPU Power: 197 mW
Combined Power (CPU + GPU + ANE): 700 mW
"""


class MeterTests(unittest.TestCase):
    def test_combined_line_is_not_added_to_the_rails(self) -> None:
        self.assertEqual(parse_combined_mw(SAMPLE), [533.0, 700.0])
        # 0.533 W * 1 s + 0.700 W * 1 s
        self.assertAlmostEqual(integrate_joules([533, 700], 1), 1.233)
        reading = reading_from_powermetrics_text(SAMPLE, 1)
        self.assertEqual(reading["label"], "MEASURED")
        self.assertEqual(reading["boundary"], "apple-silicon-soc-cpu-gpu-ane")
        self.assertAlmostEqual(reading["aggregate_joules"], 1.233)
        self.assertEqual(reading["samples"], 2)

    def test_cpu_only_text_does_not_claim_the_whole_machine(self) -> None:
        reading = reading_from_powermetrics_text("CPU Power: 2000 mW\n", 1)
        self.assertEqual(reading["boundary"], "cpu-power-sampler-only")
        self.assertAlmostEqual(reading["aggregate_joules"], 2.0)
        self.assertIn("not included", reading["reason"])

    def test_unparsed_text_is_null_not_zero(self) -> None:
        reading = reading_from_powermetrics_text("no power here\n", 1)
        self.assertEqual(reading["label"], "UNAVAILABLE")
        self.assertIsNone(reading["aggregate_joules"])

    def test_linux_does_not_need_sudo(self) -> None:
        called = []

        def work():
            called.append("work")
            return "done"

        value, reading = HostMeter(enabled=True, system="Linux").measure(work)
        self.assertEqual(value, "done")
        self.assertEqual(called, ["work"])
        self.assertEqual(reading["label"], "UNAVAILABLE")
        self.assertIn("macOS", reading["reason"])
        self.assertIsNone(reading["aggregate_joules"])

    def test_command_uses_noninteractive_sudo(self) -> None:
        command = powermetrics_command(4, 1000)
        self.assertEqual(command[0], "sudo")
        self.assertIn("-n", command)
        self.assertNotIn("password", " ".join(command).lower())


if __name__ == "__main__":
    unittest.main()
