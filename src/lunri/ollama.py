"""Local Ollama chat client. Tests point it at a fake server. No API key."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from lunri.dataset import messages_for

DEFAULT_BASE = "http://127.0.0.1:11434"

# Shape from the Ollama structured-outputs page retrieved 2026-11-18.
# Not verified against a live server in this environment.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "currency": {"type": "string"},
        "invoice_number": {"type": "string"},
        "subtotal_cents": {"type": "integer"},
        "tax_cents": {"type": "integer"},
        "total_cents": {"type": "integer"},
    },
    "required": ["currency", "invoice_number", "total_cents"],
}


@dataclass
class ModelResult:
    ok: bool
    text: str
    error: str | None
    latency_s: float
    model: str


class LineMockClient:
    """Offline stand-in. Both model names use the same line parser."""

    def complete(self, model: str, prompt: str, *, timeout: float, temperature: float = 0) -> ModelResult:
        from lunri.mock_model import complete as line_complete

        return ModelResult(True, line_complete(prompt), None, 0.0, model)

    def revision(self, model: str) -> dict:
        return {"digest": None, "model": model, "source": "mock-deterministic"}


class ScriptedClient:
    """Test double. ``handler(model, prompt)`` returns a ModelResult."""

    def __init__(self, handler):
        self.handler = handler

    def complete(self, model: str, prompt: str, *, timeout: float, temperature: float = 0) -> ModelResult:
        return self.handler(model, prompt, timeout)


def require_loopback(base_url: str) -> str:
    """Accept only an HTTP Ollama on this machine."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    if parsed.scheme != "http" or host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            f"refusing model endpoint {base_url!r}. Lunri only contacts a loopback Ollama."
        )
    return base_url.rstrip("/")


class OllamaClient:
    def __init__(self, base_url: str = DEFAULT_BASE):
        self.base_url = require_loopback(base_url)
        self._revisions: dict[str, dict] = {}

    def ping(self, timeout: float = 2) -> tuple[bool, str]:
        try:
            status, _body = _request(self.base_url + "/api/tags", None, timeout)
        except TimeoutError:
            return False, "timed out contacting Ollama"
        except OSError as exc:
            return False, f"Ollama is not reachable: {exc.__class__.__name__}"
        if status != 200:
            return False, f"Ollama /api/tags returned HTTP {status}"
        return True, "reachable"

    def complete(self, model: str, prompt: str, *, timeout: float, temperature: float = 0) -> ModelResult:
        import time

        body = chat_body(model, prompt, temperature)
        started = time.perf_counter()
        try:
            status, raw = _request(self.base_url + "/api/chat", body, timeout)
        except TimeoutError:
            return ModelResult(False, "", "timeout", timeout, model)
        except OSError as exc:
            elapsed = time.perf_counter() - started
            return ModelResult(False, "", f"connection error: {exc.__class__.__name__}", elapsed, model)
        elapsed = time.perf_counter() - started
        if status != 200:
            return ModelResult(False, "", f"HTTP {status}", elapsed, model)
        try:
            payload = json.loads(raw.decode("utf-8"))
            content = payload["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            return ModelResult(False, "", "malformed ollama response", elapsed, model)
        if not isinstance(content, str):
            content = json.dumps(content, sort_keys=True)
        return ModelResult(True, content, None, elapsed, model)

    def revision(self, model: str) -> dict:
        cached = self._revisions.get(model)
        if cached is not None:
            return cached
        found = {"digest": None, "model": model, "source": "unavailable"}
        try:
            status, raw = _request(self.base_url + "/api/show", {"model": model}, 5)
        except (OSError, TimeoutError):
            self._revisions[model] = found
            return found
        if status != 200:
            self._revisions[model] = found
            return found
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._revisions[model] = found
            return found
        digest = payload.get("digest")
        if not isinstance(digest, str) or not digest:
            details = payload.get("details")
            if isinstance(details, dict):
                digest = details.get("digest")
        if isinstance(digest, str) and digest:
            found = {"digest": digest, "model": model, "source": "ollama"}
        self._revisions[model] = found
        return found


def chat_body(model: str, prompt: str, temperature: float) -> dict:
    """Request JSON. ``prompt`` is the invoice text only."""
    return {
        "format": RESPONSE_SCHEMA,
        "messages": messages_for({"text": prompt}),
        "model": model,
        "options": {"temperature": temperature},
        "stream": False,
    }


def _request(url: str, body: dict | None, timeout: float) -> tuple[int, bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except socket.timeout as exc:
        raise TimeoutError("timed out") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError("timed out") from exc
        raise OSError(str(exc.reason)) from exc
