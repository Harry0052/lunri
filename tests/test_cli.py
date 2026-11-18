"""CLI smoke test, report labels, and a missing model runtime."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lunri.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_default_smoke_labels_every_record_simulated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["run", "--runs-dir", str(runs), "--now", "2026-11-18T17:00:00Z"])
            self.assertEqual(code, 0)
            text = stdout.getvalue()
            self.assertIn("SIMULATED report", text)
            self.assertIn("response_label SIMULATED", text)
            self.assertIn("energy_label SIMULATED", text)
            self.assertIn("not benchmark results", text)
            records = [json.loads(path.read_text(encoding="utf-8")) for path in runs.glob("*.json")]
            self.assertEqual(len(records), 2)
            for record in records:
                self.assertEqual(record["response_label"], "SIMULATED")
                self.assertEqual(record["energy"]["label"], "SIMULATED")
                self.assertIsNone(record["energy"]["joules"])
                self.assertFalse(record["energy"]["measured"])
                self.assertFalse(record["energy"]["estimate"])
                self.assertFalse(record["privacy"]["raw_text_stored"])

    def test_malformed_input_is_recorded_as_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "run",
                        "--case",
                        "syn-003",
                        "--runs-dir",
                        str(runs),
                        "--now",
                        "2026-11-18T17:00:00Z",
                    ]
                )
            self.assertEqual(code, 1)
            record = json.loads(next(runs.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "error")
            self.assertEqual(record["response_label"], "SIMULATED")
            self.assertIn("missing total_cents", record["errors"])

    def test_unknown_model_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["run", "--model", "ollama", "--runs-dir", str(runs)])
            self.assertEqual(code, 2)
            self.assertEqual(list(runs.glob("*.json")), [])

    def test_doctor_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["doctor", "--runs-dir", str(Path(tmp) / "runs"), "--repo-root", tmp])
            self.assertEqual(code, 0)
            self.assertIn("required checks passed", stdout.getvalue())
            self.assertIn("not a benchmark", stdout.getvalue())

    def test_committed_example_matches_syn_001(self) -> None:
        saved = json.loads((ROOT / "docs/examples/synthetic-run.json").read_text(encoding="utf-8"))
        self.assertEqual(saved[0]["response_label"], "SIMULATED")
        self.assertEqual(saved[0]["energy"]["label"], "SIMULATED")
        self.assertIsNone(saved[0]["energy"]["joules"])
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["run", "--case", "syn-001", "--runs-dir", str(runs), "--now", "2026-11-18T17:00:00Z", "--json"]
                )
            fresh = json.loads(next(runs.glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        for key in ("case_id", "fixture_sha256", "model", "output", "privacy", "response_label", "run_id", "status"):
            self.assertEqual(fresh[key], saved[0][key], key)

    def test_module_invocation_hides_a_secret(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["LUNRI_DOCTOR_SECRET"] = "should-not-appear"
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, "-m", "lunri", "doctor", "--runs-dir", str(Path(tmp) / "runs"), "--repo-root", tmp],
                cwd=tmp,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("should-not-appear", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
