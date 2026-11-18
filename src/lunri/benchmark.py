"""Compare the three strategies on one split. Gold is applied only after a prediction."""

from __future__ import annotations

import json
from pathlib import Path

from lunri.dataset import messages_for
from lunri.meter import with_derived
from lunri.stats import quality_gate, ratio, wilson_interval
from lunri.strategies import STRATEGIES, run_strategy

GOLD_FIELDS = ("currency", "invoice_number", "total_cents")


def config_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "eval_config.json"


def load_config() -> dict:
    return json.loads(config_path().read_text(encoding="utf-8"))


def run_benchmark(
    rows: list[dict],
    client,
    meter,
    *,
    strategies: tuple[str, ...] = STRATEGIES,
    config: dict | None = None,
    backend: str,
    split: str,
) -> dict:
    settings = config if config is not None else load_config()
    target = settings["quality_target"]
    minimum = settings["minimum_attempts_for_decision"]
    small = settings["small_model"]
    large = settings["large_model"]
    timeout = settings["timeout_seconds"]
    temperature = settings["temperature"]
    summaries = {}
    for strategy in strategies:
        def work(strategy=strategy):
            return [
                _one(row, strategy, client, small=small, large=large, timeout=timeout, temperature=temperature)
                for row in rows
            ]

        attempts, energy = meter.measure(work)
        summaries[strategy] = summarize(attempts, with_derived(energy, len(rows)), target, minimum)
    return {
        "backend": backend,
        "config": {
            "large_model": large,
            "minimum_attempts_for_decision": minimum,
            "quality_target": target,
            "small_model": small,
            "temperature": temperature,
            "timeout_seconds": timeout,
        },
        "inference_label": "SIMULATED" if backend == "mock" else "REAL",
        "split": split,
        "strategies": summaries,
    }


def _one(row, strategy, client, *, small, large, timeout, temperature) -> dict:
    # The client sees text only. Gold stays in this function's caller-side record.
    prompt = messages_for(row)[1]["content"]
    bundle = run_strategy(
        strategy,
        prompt,
        client,
        small=small,
        large=large,
        timeout=timeout,
        temperature=temperature,
    )
    gold = row["gold"]
    output = bundle["output"]
    match = all(output.get(field) == gold[field] for field in GOLD_FIELDS)
    false_accept = False
    false_reject = False
    if strategy == "cascade" and bundle["small_output"] is not None:
        small_match = all(bundle["small_output"].get(field) == gold[field] for field in GOLD_FIELDS)
        if bundle["fallback"] and small_match:
            false_reject = True
        if not bundle["fallback"] and not small_match and bundle["status"] == "ok":
            false_accept = True
    return {
        "calls": bundle["calls"],
        "correct": match,
        "errors": bundle["errors"],
        "fallback": bundle["fallback"],
        "false_accept": false_accept,
        "false_reject": false_reject,
        "field_correct": {field: output.get(field) == gold[field] for field in GOLD_FIELDS},
        "id": row["id"],
        "output": {field: output.get(field) for field in GOLD_FIELDS},
        "status": bundle["status"],
        "validations": len(bundle["validations"]),
    }


def summarize(attempts: list[dict], energy: dict, target: float, minimum: int) -> dict:
    count = len(attempts)
    correct = sum(1 for row in attempts if row["correct"])
    failed = sum(1 for row in attempts if row["status"] != "ok")
    calls = [call for row in attempts for call in row["calls"]]
    failed_calls = sum(1 for call in calls if not call["ok"])
    fallbacks = sum(1 for row in attempts if row["fallback"])
    validations = sum(row["validations"] for row in attempts)
    latency = sum(call["latency_s"] for call in calls)
    interval = wilson_interval(correct, count) if count else None
    field_hits = {
        field: sum(1 for row in attempts if row["field_correct"][field]) for field in GOLD_FIELDS
    }
    measured = energy.get("label") == "MEASURED"
    return {
        "attempts": count,
        "calls": len(calls),
        "correct": correct,
        "energy": energy,
        "energy_per_attempt_joules": energy.get("derived_per_attempt_joules") if measured else None,
        "energy_per_correct_joules": ratio(energy.get("aggregate_joules") if measured else None, correct),
        "failed": failed,
        "failed_calls": failed_calls,
        "fallbacks": fallbacks,
        "false_accepts": sum(1 for row in attempts if row["false_accept"]),
        "false_rejects": sum(1 for row in attempts if row["false_reject"]),
        "field_hits": field_hits,
        "full_record_accuracy": None if count == 0 else correct / count,
        "latency_s": latency,
        "quality": quality_gate(correct=correct, attempts=count, target=target, minimum_attempts=minimum),
        "validations": validations,
        "wilson": interval,
    }
