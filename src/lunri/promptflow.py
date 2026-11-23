"""Compare one original prompt with a shorter one, per selected model."""

from __future__ import annotations

import json
from pathlib import Path

from lunri.assumptions import assumption_note, find_assumption, watt_hours
from lunri.grading import grade_prompt, parse_grade
from lunri.keystore import find_provider, redact
from lunri.providers import Completion, MockProvider, complete_live, grader_system
from lunri.rewrite import optimize_prompt

MAX_PROMPT_CHARS = 20_000
DEMO_MODELS = ("mock-small", "mock-large")


def demo_prompt_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "prompts" / "redundant.txt"


def run_prompt_benchmark(
    prompt: str,
    *,
    provider: str,
    models: tuple[str, ...],
    grader: str,
    grader_model: str | None,
    optimizer: str,
    optimizer_model: str | None,
    energy_assumption: str | None,
    input_usd_per_million: float | None,
    output_usd_per_million: float | None,
    timeout: float = 60,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict:
    if not prompt.strip():
        raise ValueError("prompt is empty")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"prompt is longer than {MAX_PROMPT_CHARS} characters")
    if not models:
        raise ValueError("select at least one model")
    assumption = find_assumption(energy_assumption)
    if optimizer == "mock":
        rewritten = optimize_prompt(prompt)
    else:
        rewritten = _live_optimize(
            optimizer,
            optimizer_model or models[0],
            prompt,
            timeout=timeout,
            base_url=base_url,
            api_key=api_key,
        )
    optimized = rewritten["optimized_prompt"]
    grades = {
        "optimized": _grade(grader, grader_model, optimized, timeout, base_url, api_key),
        "original": _grade(grader, grader_model, prompt, timeout, base_url, api_key),
    }
    rows = []
    for model in models:
        original = _run(provider, model, prompt, timeout, base_url, api_key)
        revised = _run(provider, model, optimized, timeout, base_url, api_key)
        prices = _prices(provider, model, input_usd_per_million, output_usd_per_million)
        rows.append(
            {
                "delta": _delta(original, revised, prices, assumption),
                "model": model,
                "optimized": _side(revised, prices, assumption),
                "original": _side(original, prices, assumption),
                "provider": provider,
            }
        )
    price_source = "caller-supplied" if input_usd_per_million is not None else "not supplied"
    return {
        "changes": rewritten["changes"],
        "energy_assumption": assumption,
        "energy_note": assumption_note(assumption),
        "grades": grades,
        "inference_label": "SIMULATED" if provider == "mock" else "REAL",
        "models": rows,
        "optimized_prompt": optimized,
        "optimizer_label": rewritten.get("label", "REAL"),
        "original_prompt": prompt,
        "price_note": (
            "ESTIMATE from prices supplied for this run. Lunri did not look up a vendor price list."
            if input_usd_per_million is not None
            else "not estimated. No price per million tokens was supplied."
        ),
        "prices": {
            "input_usd_per_million": input_usd_per_million,
            "output_usd_per_million": output_usd_per_million,
            "source": price_source,
        },
        "schema_version": 1,
    }


def _grade(grader, grader_model, text, timeout, base_url, api_key) -> dict:
    if grader == "mock":
        return grade_prompt(text)
    model = grader_model or "grader"
    result = complete_live(
        grader,
        model,
        text,
        timeout=timeout,
        base_url=base_url,
        api_key=api_key,
        system=grader_system(),
    )
    if not result.ok:
        return {"error": result.error or "grader failed", "label": "UNAVAILABLE", "scores": None}
    try:
        return parse_grade(result.text)
    except ValueError as exc:
        return {"error": str(exc), "label": "UNAVAILABLE", "scores": None}


def _live_optimize(provider, model, prompt, *, timeout, base_url, api_key) -> dict:
    system = (
        "Rewrite the user prompt so it is shorter and less redundant. "
        "Keep the task. Reply with one JSON object: "
        "optimized_prompt (string) and changes (array of objects with kind and detail). "
        "Do not answer the prompt."
    )
    result = complete_live(
        provider,
        model,
        prompt,
        timeout=timeout,
        base_url=base_url,
        api_key=api_key,
        system=system,
    )
    if not result.ok:
        raise ValueError(result.error or "optimizer call failed")
    try:
        data = json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise ValueError("optimizer response was not JSON") from exc
    optimized = data.get("optimized_prompt") if isinstance(data, dict) else None
    changes = data.get("changes") if isinstance(data, dict) else None
    if not isinstance(optimized, str) or not optimized.strip():
        raise ValueError("optimizer response did not include optimized_prompt")
    if not isinstance(changes, list) or not changes:
        raise ValueError("optimizer response did not include changes")
    cleaned = []
    for item in changes:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str) or not isinstance(item.get("detail"), str):
            raise ValueError("optimizer change must have kind and detail strings")
        cleaned.append({"detail": item["detail"], "kind": item["kind"]})
    return {"changes": cleaned, "label": "REAL", "optimized_prompt": optimized.strip()}


def _run(provider, model, prompt, timeout, base_url, api_key) -> Completion:
    if provider == "mock":
        return MockProvider().complete(model, prompt, timeout=timeout)
    return complete_live(provider, model, prompt, timeout=timeout, base_url=base_url, api_key=api_key)


def _prices(provider, model, input_price, output_price) -> tuple[float | None, float | None]:
    if input_price is not None or output_price is not None:
        return input_price, output_price
    stored = find_provider(provider, model=model) or {}
    return stored.get("input_usd_per_million"), stored.get("output_usd_per_million")


def _side(result: Completion, prices: tuple[float | None, float | None], assumption: dict | None) -> dict:
    cost = _cost(result.input_tokens, result.output_tokens, prices)
    energy = watt_hours(result.output_tokens, assumption) if result.ok else None
    return {
        "cost_label": "ESTIMATE" if cost is not None else "not estimated",
        "cost_usd": cost,
        "energy_label": "ESTIMATE" if energy is not None else "not estimated",
        "error": result.error,
        "input_tokens": result.input_tokens,
        "latency_label": "SIMULATED" if result.label == "SIMULATED" else "measured-client-elapsed",
        "latency_s": result.latency_s,
        "ok": result.ok,
        "output_tokens": result.output_tokens,
        "text": result.text,
        "token_source": result.token_source,
        "watt_hours": energy,
    }


def _cost(input_tokens, output_tokens, prices: tuple[float | None, float | None]) -> float | None:
    input_price, output_price = prices
    if input_price is None or output_price is None or input_tokens is None or output_tokens is None:
        return None
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def _delta(original: Completion, revised: Completion, prices, assumption) -> dict:
    left = _side(original, prices, assumption)
    right = _side(revised, prices, assumption)
    return {
        "cost_usd": _subtract(left["cost_usd"], right["cost_usd"]),
        "input_tokens": _subtract(left["input_tokens"], right["input_tokens"]),
        "latency_s": _subtract(left["latency_s"], right["latency_s"]),
        "output_tokens": _subtract(left["output_tokens"], right["output_tokens"]),
        "watt_hours": _subtract(left["watt_hours"], right["watt_hours"]),
    }


def _subtract(left, right):
    if left is None or right is None:
        return None
    return left - right


def scrub_report(body: dict) -> dict:
    return json.loads(redact(json.dumps(body)))
