"""Model suggestions from injected chip and RAM. This Linux guest is not a Mac."""

from __future__ import annotations

import unittest

from lunri.hardware import LARGE_MODEL, SMALL_MODEL, _sysctl_int, suggest_models


class HardwareTests(unittest.TestCase):
    def test_apple_silicon_ram_bands(self) -> None:
        small_mac = suggest_models(system="Darwin", machine="arm64", memory_bytes=7 * 1024**3, brand="Apple M2")
        self.assertEqual(small_mac["pull"], [SMALL_MODEL])
        self.assertFalse(small_mac["comparison_ready"])
        self.assertEqual(small_mac["chip"], "Apple M2")
        sixteen = suggest_models(system="Darwin", machine="arm64", memory_bytes=16 * 1024**3, brand="Apple M4")
        self.assertEqual(sixteen["pull"], [SMALL_MODEL, LARGE_MODEL])
        self.assertTrue(sixteen["comparison_ready"])
        eight = suggest_models(system="Darwin", machine="arm64", memory_bytes=8 * 1024**3)
        self.assertIn("tight", eight["note"])
        self.assertEqual(eight["chip"], "Apple Silicon")

    def test_unknown_ram_does_not_invent_a_pull(self) -> None:
        unknown = suggest_models(system="Darwin", machine="arm64", memory_bytes=None)
        self.assertEqual(unknown["pull"], [])
        self.assertFalse(unknown["comparison_ready"])

    def test_intel_mac_is_labeled_cpu_only(self) -> None:
        intel = suggest_models(system="Darwin", machine="x86_64", memory_bytes=16 * 1024**3, brand="Intel Core")
        self.assertIn("CPU only", intel["note"])
        self.assertEqual(intel["chip"], "Intel Core")

    def test_sysctl_parser(self) -> None:
        class Completed:
            returncode = 0
            stdout = "17179869184\n"

        self.assertEqual(_sysctl_int(["sysctl", "-n", "hw.memsize"], lambda *args, **kwargs: Completed()), 17179869184)

        class Broken:
            returncode = 1
            stdout = ""

        self.assertIsNone(_sysctl_int(["sysctl", "-n", "hw.memsize"], lambda *args, **kwargs: Broken()))


if __name__ == "__main__":
    unittest.main()
