"""Human-readable benchmark reports. Labels stay on every energy and inference claim."""

from __future__ import annotations

from lunri.stats import break_even


def render_report(body: dict) -> str:
    lines = [
        f"inference {body['inference_label']}",
        "This report is not an energy-saving claim.",
        f"backend {body['backend']}",
        f"split {body['split']}",
        (
            f"quality_target {body['config']['quality_target']} "
            f"minimum_attempts {body['config']['minimum_attempts_for_decision']}"
        ),
        f"small_model {body['config']['small_model']}",
        f"large_model {body['config']['large_model']}",
    ]
    if body["inference_label"] == "SIMULATED":
        lines.append("The numbers below come from the deterministic line parser, not from Qwen or Ollama.")
    for name, summary in body["strategies"].items():
        energy = summary["energy"]
        wilson = summary["wilson"]
        if wilson is None:
            interval = "n/a"
        else:
            interval = f"{wilson['low']:.4f}..{wilson['high']:.4f}"
        lines.append(
            f"{name} attempts={summary['attempts']} correct={summary['correct']} "
            f"failed={summary['failed']} accuracy={_fmt(summary['full_record_accuracy'])} "
            f"wilson95={interval} quality={summary['quality']}"
        )
        lines.append(
            f"  calls={summary['calls']} failed_calls={summary['failed_calls']} "
            f"fallbacks={summary['fallbacks']} validations={summary['validations']} "
            f"false_accepts={summary['false_accepts']} false_rejects={summary['false_rejects']} "
            f"latency_s={summary['latency_s']:.4f}"
        )
        lines.append(
            f"  energy {energy['label']} boundary={energy['boundary']} "
            f"aggregate_joules={_fmt(energy['aggregate_joules'])} "
            f"per_attempt={_fmt(summary['energy_per_attempt_joules'])} "
            f"per_correct={_fmt(summary['energy_per_correct_joules'])}"
        )
        lines.append(f"  energy_note {energy['reason']}")
    lines.append("decision " + decision_line(body))
    return "\n".join(lines) + "\n"


def decision_line(body: dict) -> str:
    if body["inference_label"] != "REAL":
        return "insufficient evidence. Inference is SIMULATED, so no model comparison is claimed."
    energies = [summary["energy"] for summary in body["strategies"].values()]
    if any(item["label"] != "MEASURED" for item in energies):
        return "insufficient evidence. At least one strategy has no measured energy."
    boundaries = {item["boundary"] for item in energies}
    if len(boundaries) != 1:
        return "insufficient evidence. Measurement boundaries differ."
    qualities = {name: summary["quality"] for name, summary in body["strategies"].items()}
    if any(value != "meets_target" for value in qualities.values()):
        return "no energy recommendation. A strategy does not meet the predeclared quality target."
    return "quality gate passed on this sample and energy was measured. Compare the per-attempt figures above. Overhead was not measured, so break-even is unavailable."


def hypothetical_cases() -> list[dict]:
    """Fixed arithmetic examples. They are not measurements from a Mac."""
    saving = break_even(
        overhead_joules=30,
        baseline_joules_per_attempt=10,
        candidate_joules_per_attempt=4,
        same_boundary=True,
        baseline_meets_quality=True,
        candidate_meets_quality=True,
    )
    no_saving = break_even(
        overhead_joules=30,
        baseline_joules_per_attempt=4,
        candidate_joules_per_attempt=10,
        same_boundary=True,
        baseline_meets_quality=True,
        candidate_meets_quality=True,
    )
    missing = break_even(
        overhead_joules=None,
        baseline_joules_per_attempt=10,
        candidate_joules_per_attempt=4,
        same_boundary=True,
        baseline_meets_quality=True,
        candidate_meets_quality=True,
    )
    return [
        {"label": "HYPOTHETICAL", "name": "saving", "result": saving},
        {"label": "HYPOTHETICAL", "name": "no-saving", "result": no_saving},
        {"label": "HYPOTHETICAL", "name": "missing-overhead", "result": missing},
    ]


def render_hypotheticals() -> str:
    lines = ["HYPOTHETICAL decision examples. Not a physical result and not this computer."]
    for case in hypothetical_cases():
        result = case["result"]
        lines.append(
            f"{case['label']} {case['name']} status={result['status']} "
            f"attempts={result['attempts']} reason={result['reason']}"
        )
    return "\n".join(lines) + "\n"


def _fmt(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
