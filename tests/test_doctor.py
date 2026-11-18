"""Doctor passes with no keys and reports a missing optional tool."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lunri.doctor import format_text, report


class DoctorTests(unittest.TestCase):
    def test_required_checks_pass_and_hide_a_planted_secret(self) -> None:
        secret = "lunri-planted-secret-value"
        previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = secret
        try:
            with tempfile.TemporaryDirectory() as tmp:
                body = report(Path(tmp) / "runs", repo_root=Path(tmp), tool_finder=lambda _name: None)
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous
        self.assertTrue(body["ok"])
        self.assertFalse(body["benchmark"])
        rendered = format_text(body) + json.dumps(body)
        self.assertNotIn(secret, rendered)
        self.assertIn("SIMULATED", rendered)
        by_name = {check["name"]: check for check in body["checks"]}
        for name in ("python", "fixture", "mock_model", "run_records", "privacy", "secrets"):
            self.assertEqual(by_name[name]["status"], "pass", name)
        self.assertEqual(by_name["ollama"]["status"], "skip")
        self.assertIn("SIMULATED", by_name["energy_sensor"]["detail"])
        self.assertEqual(by_name["simulator"]["status"], "skip")
        self.assertIn(body["host"]["system"], {"Linux", "Darwin", "Windows"})
        self.assertIsInstance(body["host"]["cpu_count"], int)
        self.assertGreater(body["host"]["cpu_count"], 0)
        if body["host"]["system"] == "Linux":
            self.assertIsInstance(body["host"]["memory_bytes"], int)

    def test_a_present_ollama_binary_is_not_called(self) -> None:
        called = []

        def finder(name: str):
            called.append(name)
            if name == "ollama":
                return "/usr/bin/ollama"
            return None

        with tempfile.TemporaryDirectory() as tmp:
            body = report(Path(tmp) / "runs", repo_root=Path(tmp), tool_finder=finder)
        ollama = next(check for check in body["checks"] if check["name"] == "ollama")
        self.assertEqual(ollama["status"], "pass")
        self.assertIn("does not call", ollama["detail"])
        self.assertEqual(called, ["ollama"])

    def test_unwritable_runs_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "runs"
            blocker.write_text("not a directory\n", encoding="utf-8")
            body = report(blocker, repo_root=Path(tmp))
        self.assertFalse(body["ok"])
        records = next(check for check in body["checks"] if check["name"] == "run_records")
        self.assertEqual(records["status"], "fail")


if __name__ == "__main__":
    unittest.main()
