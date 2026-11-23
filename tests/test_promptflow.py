"""No-key prompt comparison, cited watt-hour arithmetic, and local key redaction."""

from __future__ import annotations

import json
import os
import stat
import unittest
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from lunri.cli import main
from lunri.keystore import settings_path
from lunri.promptflow import demo_prompt_path, run_prompt_benchmark, scrub_report
from lunri.settings_ui import SettingsUI


class PromptDemoTests(unittest.TestCase):
    def test_demo_compares_models_and_labels_estimates(self) -> None:
        with mock.patch.dict(os.environ, {"LUNRI_HOME": ""}, clear=False):
            os.environ["LUNRI_HOME"] = self._home()
            body = run_prompt_benchmark(
                demo_prompt_path().read_text(encoding="utf-8"),
                provider="mock",
                models=("mock-small", "mock-large"),
                grader="mock",
                grader_model=None,
                optimizer="mock",
                optimizer_model=None,
                energy_assumption="a100-output-marginal",
                input_usd_per_million=1,
                output_usd_per_million=1,
            )
        self.assertLess(len(body["optimized_prompt"]), len(body["original_prompt"]))
        self.assertTrue(any(change["kind"] == "redundancy" for change in body["changes"]))
        self.assertGreater(body["grades"]["optimized"]["mean"], body["grades"]["original"]["mean"])
        self.assertEqual([row["model"] for row in body["models"]], ["mock-small", "mock-large"])
        original = body["models"][0]["original"]
        self.assertEqual(original["energy_label"], "ESTIMATE")
        self.assertEqual(original["cost_label"], "ESTIMATE")
        self.assertEqual(original["latency_label"], "SIMULATED")
        self.assertAlmostEqual(original["watt_hours"], original["output_tokens"] * 1.72 / 3600)
        self.assertIn("arxiv.org/abs/2512.01644", body["energy_note"])
        self.assertIn("Not a measurement", body["energy_note"])
        self.assertIsNotNone(body["models"][0]["delta"]["watt_hours"])
        self.assertIsNotNone(body["models"][0]["delta"]["cost_usd"])

    def test_missing_assumption_leaves_watt_hours_empty(self) -> None:
        body = run_prompt_benchmark(
            "Write a status note.",
            provider="mock",
            models=("mock-small",),
            grader="mock",
            grader_model=None,
            optimizer="mock",
            optimizer_model=None,
            energy_assumption=None,
            input_usd_per_million=None,
            output_usd_per_million=None,
        )
        side = body["models"][0]["original"]
        self.assertIsNone(side["watt_hours"])
        self.assertIsNone(side["cost_usd"])
        self.assertEqual(side["energy_label"], "not estimated")
        self.assertEqual(side["cost_label"], "not estimated")

    def test_cli_demo_hides_a_stored_key(self) -> None:
        home = self._home()
        secret = "lunri-test-key-should-not-leak"
        with mock.patch.dict(os.environ, {"LUNRI_HOME": home, "LUNRI_API_KEY": secret}):
            code, saved_out, saved_err = self._run(
                [
                    "settings",
                    "add",
                    "--provider",
                    "openai",
                    "--label",
                    "Desk",
                    "--model",
                    "gpt-test",
                ]
            )
            self.assertEqual(code, 0, saved_err)
            self.assertNotIn(secret, saved_out)
            self.assertNotIn(secret, saved_err)
            self.assertIn(secret, settings_path().read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE(settings_path().stat().st_mode), 0o600)
            runs = Path(home) / "runs"
            code, stdout, stderr = self._run(
                [
                    "prompt",
                    "--demo",
                    "--input-usd-per-million",
                    "1",
                    "--output-usd-per-million",
                    "1",
                    "--runs-dir",
                    str(runs),
                ]
            )
        self.assertEqual(code, 0, stdout + stderr)
        self.assertNotIn(secret, stdout)
        self.assertNotIn(secret, stderr)
        report = (runs / "prompt-comparison.json").read_text(encoding="utf-8")
        self.assertNotIn(secret, report)
        self.assertIn("ESTIMATE", stdout)
        self.assertIn("mock-large", stdout)

    def test_report_redacts_a_key_pasted_into_the_prompt(self) -> None:
        secret = "pasted-key-abcdef"
        home = self._home()
        with mock.patch.dict(os.environ, {"LUNRI_HOME": home, "LUNRI_API_KEY": secret}):
            body = scrub_report(
                run_prompt_benchmark(
                    f"Use {secret} in the draft. Use {secret} in the draft.",
                    provider="mock",
                    models=("mock-small",),
                    grader="mock",
                    grader_model=None,
                    optimizer="mock",
                    optimizer_model=None,
                    energy_assumption=None,
                    input_usd_per_million=None,
                    output_usd_per_million=None,
                )
            )
        rendered = json.dumps(body)
        self.assertNotIn(secret, rendered)
        self.assertIn("[redacted]", rendered)

    def test_invalid_invoice_fixture_is_rejected(self) -> None:
        invalid = Path(__file__).resolve().parents[1] / "src" / "lunri" / "data" / "invalid" / "missing-fields.jsonl"
        code, stdout, stderr = self._run(["fixture", "--path", str(invalid)])
        self.assertEqual(code, 2)
        self.assertIn("fixture rejected", stderr)
        self.assertIn("synthetic must be true", stderr)
        self.assertEqual(stdout, "")
        code, stdout, stderr = self._run(["fixture"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("fixture accepted", stdout)

    def _home(self) -> str:
        path = Path(self.id().replace(".", "_"))
        target = Path(os.environ.get("TMPDIR", "/tmp")) / "lunri-tests" / path
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        import contextlib
        import io

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()


class SettingsUITests(unittest.TestCase):
    def test_page_saves_a_key_and_does_not_display_it(self) -> None:
        home = Path(os.environ.get("TMPDIR", "/tmp")) / "lunri-ui" / self.id()
        home.mkdir(parents=True, exist_ok=True)
        secret = "ui-key-not-for-display-99"
        with mock.patch.dict(os.environ, {"LUNRI_HOME": str(home)}):
            ui = SettingsUI(csrf="token-one")
            _host, port = ui.start()
            self.addCleanup(ui.stop)
            page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read().decode("utf-8")
            self.assertIn("API key", page)
            self.assertIn('type="password"', page)
            body = urllib.parse.urlencode(
                {
                    "api_key": secret,
                    "base_url": "",
                    "csrf": "token-one",
                    "input_usd_per_million": "",
                    "label": "Desk",
                    "model": "demo-model",
                    "output_usd_per_million": "",
                    "provider": "openrouter",
                }
            ).encode("utf-8")
            saved = urllib.request.urlopen(
                urllib.request.Request(f"http://127.0.0.1:{port}/providers", data=body),
                timeout=2,
            ).read().decode("utf-8")
            self.assertNotIn(secret, saved)
            self.assertIn("key saved", saved)
            stored = settings_path().read_text(encoding="utf-8")
            self.assertIn(secret, stored)
            self.assertEqual(stat.S_IMODE(settings_path().stat().st_mode), 0o600)
            again = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read().decode("utf-8")
            self.assertNotIn(secret, again)


class LiveProviderTests(unittest.TestCase):
    def test_openai_compatible_uses_reported_tokens_and_hides_the_key(self) -> None:
        secret = "bearer-key-hidden-123"
        seen = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args) -> None:
                return

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                seen["body"] = self.rfile.read(length)
                seen["auth"] = self.headers.get("Authorization")
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1/elsewhere")
                    self.end_headers()
                    return
                payload = json.dumps(
                    {
                        "choices": [{"message": {"content": json.dumps({
                            "changes": [{"detail": "Cut a repeated line.", "kind": "redundancy"}],
                            "optimized_prompt": "Summarize the notes in under 50 words.",
                        })}}],
                        "usage": {"completion_tokens": 9, "prompt_tokens": 21},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        base = f"http://127.0.0.1:{server.server_address[1]}/v1"
        home = Path(os.environ.get("TMPDIR", "/tmp")) / "lunri-live" / self.id()
        home.mkdir(parents=True, exist_ok=True)
        with mock.patch.dict(os.environ, {"LUNRI_HOME": str(home), "LUNRI_API_KEY": secret}):
            body = scrub_report(
                run_prompt_benchmark(
                    "Please note that it is important to note that I need a summary.\n"
                    "Please note that it is important to note that I need a summary.",
                    provider="openai-compatible",
                    models=("desk-model",),
                    grader="mock",
                    grader_model=None,
                    optimizer="openai-compatible",
                    optimizer_model="cheap-model",
                    energy_assumption="h100-llama31-8b-batch64",
                    input_usd_per_million=None,
                    output_usd_per_million=None,
                    base_url=base,
                    api_key=secret,
                )
            )
        self.assertEqual(seen["auth"], f"Bearer {secret}")
        self.assertNotIn(secret.encode("utf-8"), seen["body"])
        rendered = json.dumps(body)
        self.assertNotIn(secret, rendered)
        self.assertEqual(body["optimizer_label"], "REAL")
        self.assertEqual(body["models"][0]["original"]["input_tokens"], 21)
        self.assertEqual(body["models"][0]["original"]["token_source"], "provider")
        self.assertIn("0.12", body["energy_note"])
        self.assertIn("ml.energy", body["energy_note"])

