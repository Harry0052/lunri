"""Offline eval writes a SIMULATED report and keeps invoice text out of it."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lunri.cli import main


class EvalCliTests(unittest.TestCase):
    def test_mock_smoke_is_labeled_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["eval", "--backend", "mock", "--split", "smoke", "--runs-dir", str(runs)])
            self.assertEqual(code, 0, stdout.getvalue())
            text = stdout.getvalue()
            self.assertIn("inference SIMULATED", text)
            self.assertIn("insufficient evidence", text)
            report = json.loads((runs / "eval-mock-smoke.json").read_text(encoding="utf-8"))
            blob = json.dumps(report)
            self.assertNotIn("SYNTHETIC INVOICE", blob)
            self.assertEqual(report["strategies"]["large"]["attempts"], 3)
            self.assertEqual(report["strategies"]["large"]["quality"], "inconclusive")
            self.assertEqual(report["strategies"]["cascade"]["energy"]["label"], "UNAVAILABLE")
            self.assertIsNone(report["strategies"]["cascade"]["energy"]["aggregate_joules"])

    def test_missing_ollama_is_not_verified(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["eval", "--backend", "ollama", "--split", "smoke"])
        self.assertEqual(code, 2)
        self.assertIn("NOT YET VERIFIED", stderr.getvalue())

    def test_demo_is_hypothetical(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["demo"])
        self.assertEqual(code, 0)
        self.assertIn("HYPOTHETICAL", stdout.getvalue())
        self.assertIn("status=never", stdout.getvalue())

    def test_injected_mac_hardware(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "hardware",
                    "--system",
                    "Darwin",
                    "--machine",
                    "arm64",
                    "--memory-bytes",
                    str(16 * 1024**3),
                    "--brand",
                    "Apple M4",
                ]
            )
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("Apple M4", text)
        self.assertIn("qwen2.5:0.5b", text)
        self.assertIn("qwen2.5:1.5b", text)


if __name__ == "__main__":
    unittest.main()
