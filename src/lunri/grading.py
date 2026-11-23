"""Rubric grades. The mock grader is a fixture. A live grader must return the same JSON shape."""

from __future__ import annotations

import json
import re

RUBRIC = ("clarity", "redundancy", "specificity", "token_efficiency")
GRADE_VERSION = "rubric-1"

GRADER_INSTRUCTIONS = (
    "Grade the user prompt. Reply with one JSON object and no other text. "
    "scores must contain integers from 0 to 5 for clarity, redundancy, specificity, "
    "and token_efficiency. redundancy and token_efficiency are higher when the prompt "
    "is less wasteful. feedback is an array of short strings naming a concrete edit. "
    "Do not answer the prompt itself."
)


def grade_prompt(text: str) -> dict:
    """Score a prompt from countable text features. Labeled SIMULATED."""
    sentences = [part.strip() for part in re.split(r"(?<=[.?!])\s+", text.strip()) if part.strip()]
    keys = [sentence.casefold() for sentence in sentences]
    duplicates = len(keys) - len(set(keys))
    fillers = len(re.findall(r"please note that|it is important to", text, flags=re.IGNORECASE))
    words = re.findall(r"[A-Za-z0-9']+", text)
    has_end = bool(text.strip().endswith((".", "?", "!")))
    has_constraint = bool(re.search(r"\b(must|under|only|exactly)\b|\d", text, flags=re.IGNORECASE))
    scores = {
        "clarity": 4 if has_end and len(words) >= 4 else 2,
        "redundancy": max(0, 5 - duplicates),
        "specificity": 4 if has_constraint else 2,
        "token_efficiency": max(0, 5 - fillers),
    }
    feedback: list[str] = []
    if duplicates:
        feedback.append(f"Remove {duplicates} repeated sentence(s).")
    if fillers:
        feedback.append(f"Cut {fillers} filler phrase(s) such as 'please note that'.")
    if not has_constraint:
        feedback.append("Add a concrete limit, such as a length or a required field.")
    if not has_end:
        feedback.append("End the prompt with a clear question or instruction.")
    if not feedback:
        feedback.append("No rubric rule suggested an edit.")
    return _body(scores, feedback, label="SIMULATED", source="fixture-rubric")


def parse_grade(payload: str) -> dict:
    """Accept a live grader's JSON. Reject anything that is not the rubric."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("grader response was not JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("grader response was not an object")
    raw_scores = data.get("scores")
    if not isinstance(raw_scores, dict):
        raise ValueError("grader response is missing scores")
    scores: dict[str, int] = {}
    for name in RUBRIC:
        value = raw_scores.get(name)
        if type(value) is not int or not 0 <= value <= 5:
            raise ValueError(f"grader score {name} must be an integer from 0 to 5")
        scores[name] = value
    feedback = data.get("feedback")
    if not isinstance(feedback, list) or not feedback or not all(isinstance(item, str) and item.strip() for item in feedback):
        raise ValueError("grader feedback must be a non-empty list of strings")
    if len(feedback) > 12:
        raise ValueError("grader feedback has too many items")
    return _body(scores, [item.strip() for item in feedback], label="REAL", source="model")


def _body(scores: dict[str, int], feedback: list[str], *, label: str, source: str) -> dict:
    return {
        "feedback": feedback,
        "label": label,
        "mean": sum(scores.values()) / len(RUBRIC),
        "rubric_version": GRADE_VERSION,
        "scores": scores,
        "source": source,
    }
