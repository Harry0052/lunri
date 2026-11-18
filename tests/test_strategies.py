"""Cascade accounting: false accept, false reject, bad fallback, and timeout."""

from __future__ import annotations

import json
import unittest

from lunri.meter import NullMeter
from lunri.ollama import ModelResult, ScriptedClient
from lunri.response import parse_model_response
from lunri.strategies import run_strategy
from lunri.benchmark import summarize


def _result(text: str, *, ok: bool = True, error: str | None = None, latency: float = 0.1) -> ModelResult:
    return ModelResult(ok, text, error, latency, "test")


def _json(**fields) -> str:
    body = {
        "currency": fields.get("currency", "USD"),
        "invoice_number": fields.get("invoice_number", "INV"),
        "subtotal_cents": fields.get("subtotal_cents"),
        "tax_cents": fields.get("tax_cents"),
        "total_cents": fields.get("total_cents", 100),
    }
    return json.dumps(body)


class StrategyTests(unittest.TestCase):
    def test_wrong_but_valid_small_answer_is_accepted(self) -> None:
        client = ScriptedClient(lambda model, _prompt, _timeout: _result(_json(total_cents=5), latency=0.2))
        bundle = run_strategy("cascade", "text", client, small="small", large="large", timeout=1)
        self.assertFalse(bundle["fallback"])
        self.assertEqual(len(bundle["calls"]), 1)
        self.assertEqual(bundle["output"]["total_cents"], 5)

    def test_correct_answer_with_bad_arithmetic_is_rejected(self) -> None:
        def handler(model, _prompt, _timeout):
            if model == "small":
                return _result(_json(total_cents=100, subtotal_cents=10, tax_cents=10))
            return _result(_json(total_cents=999))

        bundle = run_strategy("cascade", "text", ScriptedClient(handler), small="small", large="large", timeout=1)
        self.assertTrue(bundle["fallback"])
        self.assertEqual(bundle["output"]["total_cents"], 999)
        self.assertEqual(len(bundle["calls"]), 2)
        self.assertFalse(bundle["validations"][0]["accept"])

    def test_timeout_stays_in_the_attempt_count(self) -> None:
        client = ScriptedClient(lambda _model, _prompt, timeout: _result("", ok=False, error="timeout", latency=timeout))
        bundle = run_strategy("large", "text", client, small="small", large="large", timeout=3)
        self.assertEqual(bundle["status"], "error")
        self.assertEqual(bundle["calls"][0]["error"], "timeout")
        summary = summarize(
            [
                {
                    "calls": bundle["calls"],
                    "correct": False,
                    "fallback": False,
                    "false_accept": False,
                    "false_reject": False,
                    "field_correct": {"currency": False, "invoice_number": False, "total_cents": False},
                    "status": "error",
                    "validations": 0,
                }
            ],
            {"label": "UNAVAILABLE", "aggregate_joules": None, "derived_per_attempt_joules": None},
            0.8,
            30,
        )
        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["failed_calls"], 1)
        self.assertIsNone(summary["energy_per_attempt_joules"])
        self.assertIsNone(summary["energy_per_correct_joules"])

    def test_measured_batch_denominators(self) -> None:
        attempts = []
        for correct in (True, True, False, False):
            attempts.append(
                {
                    "calls": [{"ok": True, "latency_s": 0.5}, {"ok": False, "latency_s": 0.25}],
                    "correct": correct,
                    "fallback": True,
                    "false_accept": False,
                    "false_reject": correct,
                    "field_correct": {"currency": correct, "invoice_number": correct, "total_cents": correct},
                    "status": "ok",
                    "validations": 1,
                }
            )
        summary = summarize(
            attempts,
            {
                "label": "MEASURED",
                "aggregate_joules": 100,
                "derived_per_attempt_joules": 25,
                "boundary": "injected",
                "reason": "test",
            },
            0.8,
            30,
        )
        self.assertEqual(summary["attempts"], 4)
        self.assertEqual(summary["calls"], 8)
        self.assertEqual(summary["failed_calls"], 4)
        self.assertEqual(summary["correct"], 2)
        self.assertEqual(summary["energy_per_attempt_joules"], 25)
        self.assertEqual(summary["energy_per_correct_joules"], 50)
        self.assertEqual(summary["false_rejects"], 2)

    def test_validator_ignores_gold(self) -> None:
        parsed, errors = parse_model_response(_json(total_cents=5))
        self.assertEqual(errors, [])
        self.assertTrue(__import__("lunri.validator", fromlist=["validate"]).validate(parsed)["accept"])


class MeterChoiceTests(unittest.TestCase):
    def test_null_meter_runs_the_work(self) -> None:
        value, reading = NullMeter("off").measure(lambda: 7)
        self.assertEqual(value, 7)
        self.assertEqual(reading["label"], "UNAVAILABLE")
        self.assertIsNone(reading["aggregate_joules"])


if __name__ == "__main__":
    unittest.main()
