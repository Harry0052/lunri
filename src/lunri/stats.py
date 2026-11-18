"""Accuracy interval, denominators, and break-even. No measured energy is invented."""

from __future__ import annotations

import math

Z_95 = 1.96


def wilson_interval(correct: int, attempts: int, z: float = Z_95) -> dict | None:
    """95% Wilson interval for a binomial proportion. None when attempts is 0."""
    if attempts < 0 or correct < 0 or correct > attempts:
        raise ValueError("correct must be between 0 and attempts")
    if attempts == 0:
        return None
    phat = correct / attempts
    z2 = z * z
    denom = 1 + z2 / attempts
    center = (phat + z2 / (2 * attempts)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / attempts + z2 / (4 * attempts * attempts)) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return {"high": high, "low": low, "point": phat, "z": z}


def ratio(numerator: float | None, denominator: int) -> float | None:
    """Divide only when the denominator is positive and the numerator is known."""
    if numerator is None or denominator <= 0:
        return None
    return numerator / denominator


def break_even(
    *,
    overhead_joules: float | None,
    baseline_joules_per_attempt: float | None,
    candidate_joules_per_attempt: float | None,
    same_boundary: bool,
    baseline_meets_quality: bool,
    candidate_meets_quality: bool,
) -> dict:
    """Attempts to recover measured optimization overhead. Unavailable when a prerequisite is missing."""
    if overhead_joules is None:
        return {"attempts": None, "status": "unavailable", "reason": "optimization overhead was not measured"}
    if baseline_joules_per_attempt is None or candidate_joules_per_attempt is None:
        return {"attempts": None, "status": "unavailable", "reason": "strategy energy per attempt is not measured"}
    if not same_boundary:
        return {"attempts": None, "status": "unavailable", "reason": "measurement boundaries differ"}
    if not baseline_meets_quality or not candidate_meets_quality:
        return {"attempts": None, "status": "unavailable", "reason": "a strategy misses the quality target"}
    delta = baseline_joules_per_attempt - candidate_joules_per_attempt
    if delta <= 0:
        return {"attempts": None, "status": "never", "reason": "candidate energy per attempt is not lower"}
    attempts = math.ceil(overhead_joules / delta)
    return {
        "attempts": attempts,
        "reason": "workload-dependent estimate from aggregate energy, not a guarantee",
        "status": "estimate",
    }


def quality_gate(*, correct: int, attempts: int, target: float, minimum_attempts: int) -> str:
    """Decide from the predeclared target. The target is not changed here."""
    if attempts < minimum_attempts:
        return "inconclusive"
    interval = wilson_interval(correct, attempts)
    if interval is None:
        return "inconclusive"
    if interval["low"] >= target:
        return "meets_target"
    if interval["high"] < target:
        return "misses_target"
    return "inconclusive"
