"""Gold labels for tests. The mock model must not import this module."""

from __future__ import annotations

import json

from lunri.fixture import data_dir


def load_labels() -> dict:
    path = data_dir() / "labels.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("labels.json must be marked synthetic")
    return data["cases"]
