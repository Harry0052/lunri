"""Three execution strategies. The validator never sees gold labels."""

from __future__ import annotations

from lunri.response import empty_output, parse_model_response
from lunri.validator import validate

STRATEGIES = ("large", "small", "cascade")


def run_strategy(strategy: str, text: str, client, *, small: str, large: str, timeout: float, temperature: float = 0) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy}")
    calls: list[dict] = []
    validations: list[dict] = []
    if strategy == "large":
        final, errors = _call(client, large, text, calls, timeout, temperature)
        bundle = _bundle(strategy, final, errors, calls, validations, fallback=False)
        bundle["small_output"] = None
        return bundle
    if strategy == "small":
        final, errors = _call(client, small, text, calls, timeout, temperature)
        bundle = _bundle(strategy, final, errors, calls, validations, fallback=False)
        bundle["small_output"] = final
        return bundle

    small_output, errors = _call(client, small, text, calls, timeout, temperature)
    verdict = validate(small_output)
    validations.append(verdict)
    fallback = not calls[-1]["ok"] or bool(errors) or not verdict["accept"]
    final = small_output
    if fallback:
        final, errors = _call(client, large, text, calls, timeout, temperature)
    bundle = _bundle(strategy, final, errors, calls, validations, fallback=fallback)
    bundle["small_output"] = small_output
    return bundle


def _call(client, model: str, text: str, calls: list[dict], timeout: float, temperature: float):
    result = client.complete(model, text, timeout=timeout, temperature=temperature)
    calls.append(
        {
            "error": result.error,
            "latency_s": result.latency_s,
            "model": result.model,
            "ok": result.ok,
        }
    )
    if not result.ok:
        return empty_output(), [result.error or "model call failed"]
    return parse_model_response(result.text)


def _bundle(strategy: str, final: dict, errors: list[str], calls: list[dict], validations: list[dict], fallback: bool) -> dict:
    return {
        "calls": calls,
        "errors": errors,
        "fallback": fallback,
        "output": final,
        "status": "ok" if not errors else "error",
        "strategy": strategy,
        "validations": validations,
    }
