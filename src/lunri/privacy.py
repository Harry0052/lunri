"""Defaults for a local run. Raw invoice text stays off the record unless asked."""

from __future__ import annotations


def privacy_defaults() -> dict:
    return {
        "raw_text_stored": False,
        "secrets_logged": False,
        "telemetry": False,
        "upload": False,
    }
