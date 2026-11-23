"""Model calls. The mock provider needs no key. Live calls use a key the user stored locally."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from lunri.grading import GRADER_INSTRUCTIONS
from lunri.keystore import find_provider
MAX_RESPONSE_BYTES = 2_000_000


class ProviderError(RuntimeError):
    pass


@dataclass
class Completion:
    ok: bool
    text: str
    error: str | None
    latency_s: float
    input_tokens: int | None
    output_tokens: int | None
    token_source: str
    label: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def estimate_tokens(text: str) -> int:
    """Character rule of thumb: about four English characters per token.

    Used only when a provider does not report a usage count. It is an estimate.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class MockProvider:
    """Fixture model. Output and token counts are computed locally."""

    def complete(self, model: str, prompt: str, *, timeout: float, temperature: float = 0) -> Completion:
        words = prompt.split()
        preview = " ".join(words[:8])
        text = f"MOCK {model}: {preview}".strip()
        return Completion(
            True,
            text,
            None,
            0.0,
            estimate_tokens(prompt),
            estimate_tokens(text),
            "chars-per-4-estimate",
            "SIMULATED",
        )


def complete_live(
    provider: str,
    model: str,
    prompt: str,
    *,
    timeout: float,
    base_url: str | None = None,
    api_key: str | None = None,
    system: str | None = None,
) -> Completion:
    stored = find_provider(provider, model=model)
    key = api_key if api_key is not None else (stored or {}).get("api_key") or ""
    url = base_url or (stored or {}).get("base_url") or _default_base(provider)
    if provider != "ollama" and not key:
        raise ProviderError(
            f"no API key is stored for {provider}. Add one in the local settings UI. "
            "Lunri does not accept a key on the command line."
        )
    if provider == "ollama" and not url:
        url = "http://127.0.0.1:11434"
    messages_system = system
    import time

    started = time.perf_counter()
    try:
        if provider == "anthropic":
            status, payload = _anthropic(url, model, prompt, key, timeout, messages_system)
        elif provider == "google":
            status, payload = _google(url, model, prompt, key, timeout, messages_system)
        elif provider == "ollama" and _is_native_ollama(url):
            status, payload = _ollama_native(url, model, prompt, timeout, messages_system)
        else:
            status, payload = _openai_compatible(url, model, prompt, key, timeout, messages_system)
    except ProviderError as exc:
        elapsed = time.perf_counter() - started
        return Completion(False, "", str(exc), elapsed, None, None, "unreported", "REAL")
    except (TimeoutError, OSError) as exc:
        elapsed = time.perf_counter() - started
        return Completion(False, "", exc.__class__.__name__, elapsed, None, None, "unreported", "REAL")
    elapsed = time.perf_counter() - started
    if status != 200:
        return Completion(False, "", f"HTTP {status}", elapsed, None, None, "unreported", "REAL")
    try:
        text, input_tokens, output_tokens = _parse_provider(provider, payload, url)
    except (KeyError, TypeError, ValueError):
        return Completion(False, "", "malformed provider response", elapsed, None, None, "unreported", "REAL")
    source = "provider"
    if input_tokens is None:
        input_tokens = estimate_tokens(prompt)
        source = "chars-per-4-estimate"
    if output_tokens is None:
        output_tokens = estimate_tokens(text)
        source = "chars-per-4-estimate"
    return Completion(True, text, None, elapsed, input_tokens, output_tokens, source, "REAL")


def _default_base(provider: str) -> str:
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    if provider == "anthropic":
        return "https://api.anthropic.com"
    if provider == "google":
        return "https://generativelanguage.googleapis.com"
    if provider == "ollama":
        return "http://127.0.0.1:11434"
    return ""


def _is_native_ollama(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"} and not parsed.path.rstrip("/").endswith("/v1")


def _ollama_native(url: str, model: str, prompt: str, timeout: float, system: str | None) -> tuple[int, dict]:
    """Plain local chat. This does not use the invoice extraction schema."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"messages": messages, "model": model, "options": {"temperature": 0}, "stream": False}
    endpoint = url.rstrip("/") + "/api/chat"
    return _post(endpoint, body, {"Content-Type": "application/json"}, timeout)


def _openai_compatible(url: str, model: str, prompt: str, key: str, timeout: float, system: str | None) -> tuple[int, dict]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"messages": messages, "model": model, "temperature": 0}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    endpoint = url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    return _post(endpoint, body, headers, timeout)


def _anthropic(url: str, model: str, prompt: str, key: str, timeout: float, system: str | None) -> tuple[int, dict]:
    body: dict = {
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
        "model": model,
        "temperature": 0,
    }
    if system:
        body["system"] = system
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": key,
    }
    endpoint = url.rstrip("/")
    if endpoint.endswith("/v1"):
        endpoint += "/messages"
    elif not endpoint.endswith("/v1/messages"):
        endpoint += "/v1/messages"
    return _post(endpoint, body, headers, timeout)


def _google(url: str, model: str, prompt: str, key: str, timeout: float, system: str | None) -> tuple[int, dict]:
    text = prompt if not system else f"{system}\n\n{prompt}"
    quoted = urllib.parse.quote(model, safe="")
    endpoint = url.rstrip("/") + f"/v1beta/models/{quoted}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"temperature": 0},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    return _post(endpoint, body, headers, timeout)


def _post(url: str, body: dict, headers: dict, timeout: float) -> tuple[int, dict]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProviderError("refusing a provider URL that is not http or https")
    if parsed.username or parsed.password:
        raise ProviderError("refusing a provider URL that contains a secret")
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise ProviderError("refusing to follow a provider redirect") from exc
        raw = exc.read(MAX_RESPONSE_BYTES + 1)
        status = exc.code
    except socket.timeout as exc:
        raise TimeoutError("timed out") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError("timed out") from exc
        raise OSError(exc.__class__.__name__) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("provider response is too large")
    if status != 200:
        return status, {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("malformed provider response") from exc
    if not isinstance(payload, dict):
        raise ProviderError("malformed provider response")
    return status, payload


def _parse_provider(provider: str, payload: dict, url: str) -> tuple[str, int | None, int | None]:
    if provider == "anthropic":
        content = payload["content"]
        text = content[0]["text"]
        usage = payload.get("usage") or {}
        return text, _int_or_none(usage.get("input_tokens")), _int_or_none(usage.get("output_tokens"))
    if provider == "google":
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        usage = payload.get("usageMetadata") or {}
        return (
            text,
            _int_or_none(usage.get("promptTokenCount")),
            _int_or_none(usage.get("candidatesTokenCount")),
        )
    if provider == "ollama" and _is_native_ollama(url):
        return payload["message"]["content"], None, None
    text = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage") or {}
    return text, _int_or_none(usage.get("prompt_tokens")), _int_or_none(usage.get("completion_tokens"))


def _int_or_none(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def grader_system() -> str:
    return GRADER_INSTRUCTIONS
