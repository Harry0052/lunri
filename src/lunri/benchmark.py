"""Compare the three strategies on one split. Gold is applied only after a prediction."""

from __future__ import annotations

import json
from pathlib import Path

from lunri.contracts import NORMALIZATION_ID, PROMPT_VERSION, SCHEMA_VERSION, WARMUP_POLICY
from lunri.dataset import messages_for
from lunri.meter import energy_accountable, with_derived
from lunri.stats import quality_gate, ratio, wilson_interval
from lunri.strategies import STRATEGIES, run_strategy

GOLD_FIELDS = ("currency", "invoice_number", "total_cents")


def config_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "eval_config.json"


def load_config() -> dict:
    return json.loads(config_path().read_text(encoding="utf-8"))


def paired_order(repetition: int, strategies: tuple[str, ...] = STRATEGIES) -> tuple[str, ...]:
    """Rotate which arm is measured first. Repetition 1 keeps the declared order."""
    if repetition < 1:
        raise ValueError("repetition starts at 1")
    if not strategies:
        raise ValueError("strategies must not be empty")
    shift = (repetition - 1) % len(strategies)
    return strategies[shift:] + strategies[:shift]


def run_benchmark(
    rows: list[dict],
    client,
    meter,
    *,
    strategies: tuple[str, ...] = STRATEGIES,
    config: dict | None = None,
    backend: str,
    split: str,
    repetition: int = 1,
) -> dict:
    settings = config if config is not None else load_config()
    target = settings["quality_target"]
    minimum = settings["minimum_attempts_for_decision"]
    small = settings["small_model"]
    large = settings["large_model"]
    timeout = settings["timeout_seconds"]
    temperature = settings["temperature"]
    revisions = {small: _revision(client, small), large: _revision(client, large)}
    expected_ids = [row["id"] for row in rows]
    summaries = {}
    for strategy in strategies:
        def work(strategy=strategy):
            return [
                _one(
                    row,
                    strategy,
                    client,
                    small=small,
                    large=large,
                    timeout=timeout,
                    temperature=temperature,
                    revisions=revisions,
                )
                for row in rows
            ]

        attempts, energy = meter.measure(work)
        seen = [item["id"] for item in attempts]
        if seen != expected_ids or len(seen) != len(set(seen)):
            raise RuntimeError(f"{strategy} ids are not the input ids exactly once in order")
        summary = summarize(attempts, with_derived(energy, len(rows)), target, minimum)
        summary["rows"] = [_public_row(item) for item in attempts]
        summary["id_check"] = {"count": len(expected_ids), "exact_order": True, "once_each": True}
        summary["example_fallback_id"] = next((item["id"] for item in attempts if item["fallback"]), None)
        summaries[strategy] = summary
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
        "schema_version": SCHEMA_VERSION,
        "session": {
            "normalization_id": NORMALIZATION_ID,
            "prompt_version": PROMPT_VERSION,
            "repetition": repetition,
            "run_order": list(strategies),
            "warmup_policy": WARMUP_POLICY,
        },
        "split": split,
        "strategies": summaries,
    }


def compare_repetitions(bodies: list[dict]) -> dict:
    """A paired claim needs the same ids and a complete measured boundary on every arm."""
    id_lists = []
    boundaries = []
    measured = True
    for body in bodies:
        for summary in body["strategies"].values():
            id_lists.append(tuple(row["id"] for row in summary["rows"]))
            energy = summary["energy"]
            boundaries.append(energy.get("boundary"))
            if energy.get("label") != "MEASURED" or energy.get("trace_status") != "complete":
                measured = False
    same_ids = len(set(id_lists)) == 1
    same_boundary = len(set(boundaries)) == 1 and boundaries[0] is not None
    if not same_ids:
        claim = "rejected"
    elif not measured or not same_boundary:
        claim = "unresolved"
    else:
        claim = "comparable"
    return {
        "claim": claim,
        "reason": _claim_reason(claim),
        "same_boundary": same_boundary,
        "same_ids": same_ids,
    }


def _claim_reason(claim: str) -> str:
    if claim == "rejected":
        return "arms or repetitions did not contain the same ids"
    if claim == "unresolved":
        return "a meter trace is missing, partial, reset, simulated, or a boundary does not match"
    return "joules can be compared; a savings claim still requires the quality gate"


def _revision(client, model: str) -> dict:
    method = getattr(client, "revision", None)
    if not callable(method):
        return {"digest": None, "model": model, "source": "unreported"}
    found = method(model)
    if not isinstance(found, dict):
        return {"digest": None, "model": model, "source": "unreported"}
    return {
        "digest": found.get("digest"),
        "model": found.get("model", model),
        "source": found.get("source", "reported"),
    }


def _one(row, strategy, client, *, small, large, timeout, temperature, revisions) -> dict:
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
    if bundle["status"] != "ok":
        verdict = "error"
    elif match:
        verdict = "correct"
    else:
        verdict = "wrong"
    if strategy == "large":
        used = [revisions[large]]
    elif strategy == "small":
        used = [revisions[small]]
    else:
        used = [revisions[small]]
        if bundle["fallback"]:
            used.append(revisions[large])
    return {
        "arm": strategy,
        "call_count": len(bundle["calls"]),
        "calls": bundle["calls"],
        "correct": match,
        "elapsed_s": sum(call["latency_s"] for call in bundle["calls"]),
        "errors": bundle["errors"],
        "fallback": bundle["fallback"],
        "false_accept": false_accept,
        "false_reject": false_reject,
        "field_correct": {field: output.get(field) == gold[field] for field in GOLD_FIELDS},
        "id": row["id"],
        "model_digest": used[0].get("digest"),
        "model_revision": used[0].get("model"),
        "models_called": used,
        "normalization": NORMALIZATION_ID,
        "output": {field: output.get(field) for field in GOLD_FIELDS},
        "prompt_version": PROMPT_VERSION,
        "stage_status": bundle["status"],
        "status": bundle["status"],
        "validations": len(bundle["validations"]),
        "verdict": verdict,
    }


def _public_row(item: dict) -> dict:
    return {
        "arm": item["arm"],
        "call_count": item["call_count"],
        "correct": item["correct"],
        "elapsed_s": item["elapsed_s"],
        "errors": item["errors"],
        "fallback": item["fallback"],
        "field_correct": item["field_correct"],
        "id": item["id"],
        "model_digest": item["model_digest"],
        "model_revision": item["model_revision"],
        "models_called": item["models_called"],
        "normalization": item["normalization"],
        "output": item["output"],
        "prompt_version": item["prompt_version"],
        "stage_status": item["stage_status"],
        "validations": item["validations"],
        "verdict": item["verdict"],
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
    accountable = energy_accountable(energy)
    joules = energy.get("aggregate_joules") if accountable else None
    per_correct = ratio(joules, correct)
    if not accountable:
        per_correct_note = "undefined because energy was not measured"
    elif correct == 0:
        per_correct_note = "undefined because no item was scored correct"
    else:
        per_correct_note = "whole-arm joules divided by correct items"
    return {
        "attempts": count,
        "calls": len(calls),
        "correct": correct,
        "energy": energy,
        "energy_per_attempt_joules": energy.get("derived_per_attempt_joules") if accountable else None,
        "energy_per_correct_joules": per_correct,
        "energy_per_correct_note": per_correct_note,
        "escalation_rate": None if count == 0 else fallbacks / count,
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
