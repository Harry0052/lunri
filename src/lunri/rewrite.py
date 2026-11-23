"""Deterministic prompt cleanup used by the no-key demo. Not a model."""

from __future__ import annotations

import re

FILLERS = (
    "please note that ",
    "it is important to note that ",
    "it is important to remember that ",
)

PROMPT_VERSION = "rewrite-fixture-1"


def optimize_prompt(text: str) -> dict:
    """Drop filler and repeated sentences. Each change is explained."""
    changes: list[dict] = []
    cleaned = text.replace("\r\n", "\n").strip()
    collapsed = re.sub(r"[ \t]+", " ", cleaned)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    if collapsed != cleaned:
        changes.append(
            {
                "detail": "Collapsed repeated spaces and blank lines.",
                "kind": "whitespace",
            }
        )
    without_filler, removed = _strip_fillers(collapsed)
    for phrase in removed:
        changes.append(
            {
                "detail": f"Removed the filler phrase {phrase!r}.",
                "kind": "filler",
            }
        )
    sentences = _sentences(without_filler)
    kept: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for sentence in sentences:
        key = sentence.casefold()
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        kept.append(sentence)
    if duplicates:
        changes.append(
            {
                "detail": f"Removed {duplicates} repeated sentence(s).",
                "kind": "redundancy",
            }
        )
    optimized = " ".join(kept).strip()
    if not changes:
        changes.append({"detail": "No redundancy rule fired.", "kind": "unchanged"})
    return {
        "changes": changes,
        "label": "SIMULATED",
        "optimized_prompt": optimized,
        "prompt_version": PROMPT_VERSION,
    }


def _strip_fillers(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    current = text
    for phrase in FILLERS:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(current):
            removed.append(phrase.strip())
            current = pattern.sub("", current)
    current = re.sub(r"[ \t]{2,}", " ", current)
    current = re.sub(r" +([.?!])", r"\1", current)
    return current.strip(), removed


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.?!])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]
