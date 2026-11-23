"""Text report for a prompt comparison. Estimates stay labeled."""

from __future__ import annotations


def render_prompt_report(body: dict) -> str:
    lines = [
        f"inference {body['inference_label']}",
        "Side-by-side prompt comparison. Deltas are original minus optimized.",
        "A positive token, cost, or watt-hour delta means the optimized prompt used less.",
        "This is not a measured saving on this computer unless a meter reading is shown.",
        f"optimizer {body['optimizer_label']}",
        "original prompt:",
        _block(body["original_prompt"]),
        "optimized prompt:",
        _block(body["optimized_prompt"]),
        "changes:",
    ]
    for change in body["changes"]:
        lines.append(f"  {change['kind']}: {change['detail']}")
    lines.append("grades:")
    for name in ("original", "optimized"):
        lines.extend(_grade_lines(name, body["grades"][name]))
    lines.append(body["price_note"])
    lines.append(body["energy_note"])
    for row in body["models"]:
        lines.append(f"model {row['model']} provider {row['provider']}")
        lines.append("  original " + _metrics(row["original"]))
        lines.append("  output " + _one_line(row["original"]["text"]))
        lines.append("  optimized " + _metrics(row["optimized"]))
        lines.append("  output " + _one_line(row["optimized"]["text"]))
        delta = row["delta"]
        lines.append(
            "  delta "
            f"input_tokens={_fmt(delta['input_tokens'])} "
            f"output_tokens={_fmt(delta['output_tokens'])} "
            f"latency_s={_fmt(delta['latency_s'])} "
            f"cost_usd={_fmt(delta['cost_usd'])} "
            f"watt_hours={_fmt(delta['watt_hours'])}"
        )
        if row["original"]["error"]:
            lines.append(f"  original_error {row['original']['error']}")
        if row["optimized"]["error"]:
            lines.append(f"  optimized_error {row['optimized']['error']}")
    return "\n".join(lines) + "\n"


def _grade_lines(name: str, grade: dict) -> list[str]:
    if grade.get("scores") is None:
        return [f"  {name} label {grade.get('label', 'UNAVAILABLE')} error {grade.get('error', 'unavailable')}"]
    scores = grade["scores"]
    rendered = " ".join(f"{key}={scores[key]}" for key in sorted(scores))
    lines = [f"  {name} label {grade['label']} mean={grade['mean']:.2f} {rendered}"]
    for item in grade["feedback"]:
        lines.append(f"    feedback {item}")
    return lines


def _metrics(side: dict) -> str:
    return (
        f"ok={str(side['ok']).lower()} "
        f"input_tokens={_fmt(side['input_tokens'])} output_tokens={_fmt(side['output_tokens'])} "
        f"tokens {side['token_source']} "
        f"latency_s={_fmt(side['latency_s'])} latency {side['latency_label']} "
        f"cost_usd={_fmt(side['cost_usd'])} cost {side['cost_label']} "
        f"watt_hours={_fmt(side['watt_hours'])} energy {side['energy_label']}"
    )


def _block(text: str) -> str:
    return "\n".join(f"  {line}" if line else "  " for line in text.splitlines()) or "  "


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _fmt(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)
