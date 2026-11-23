"""Local provider settings. API keys stay in this file and are never logged."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlparse

PROVIDERS = ("openai", "openai-compatible", "openrouter", "anthropic", "google", "ollama")
SECRET_ENV = "LUNRI_API_KEY"
_QUERY_SECRET = re.compile(r"(?i)(key|token|secret|password)=")


class SettingsError(ValueError):
    pass


def home_dir() -> Path:
    override = os.environ.get("LUNRI_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "lunri"


def settings_path() -> Path:
    return home_dir() / "settings.json"


def load_settings() -> dict:
    path = settings_path()
    if not path.is_file():
        return {"providers": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsError(f"cannot read settings file: {exc.__class__.__name__}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("providers"), list):
        raise SettingsError("settings file must contain a providers array")
    return data


def save_settings(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, payload.encode("utf-8"))
    finally:
        os.close(descriptor)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def public_providers(data: dict | None = None) -> list[dict]:
    """Provider rows safe to print. The key itself is omitted."""
    body = data if data is not None else load_settings()
    rows = []
    for item in body.get("providers", []):
        if not isinstance(item, dict):
            continue
        key = item.get("api_key")
        rows.append(
            {
                "base_url": _public_url(item.get("base_url")),
                "id": item.get("id"),
                "input_usd_per_million": item.get("input_usd_per_million"),
                "key_set": bool(isinstance(key, str) and key),
                "label": item.get("label") or item.get("id"),
                "model": item.get("model"),
                "output_usd_per_million": item.get("output_usd_per_million"),
                "provider": item.get("provider"),
            }
        )
    return rows


def find_provider(provider: str, *, model: str | None = None) -> dict | None:
    matches = []
    for item in load_settings().get("providers", []):
        if not isinstance(item, dict) or item.get("provider") != provider:
            continue
        if model and item.get("model") not in {None, "", model}:
            continue
        matches.append(item)
    if not matches:
        return None
    for item in matches:
        if model and item.get("model") == model:
            return item
    return matches[0]


def upsert_provider(entry: dict) -> None:
    cleaned = _validate_entry(entry)
    data = load_settings()
    providers = [item for item in data["providers"] if item.get("id") != cleaned["id"]]
    providers.append(cleaned)
    data["providers"] = providers
    save_settings(data)


def delete_provider(provider_id: str) -> bool:
    data = load_settings()
    kept = [item for item in data["providers"] if item.get("id") != provider_id]
    if len(kept) == len(data["providers"]):
        return False
    data["providers"] = kept
    save_settings(data)
    return True


def known_secrets() -> list[str]:
    secrets = []
    try:
        data = load_settings()
    except SettingsError:
        data = {"providers": []}
    for item in data.get("providers", []):
        key = item.get("api_key") if isinstance(item, dict) else None
        if isinstance(key, str) and len(key) >= 6:
            secrets.append(key)
    env = os.environ.get(SECRET_ENV)
    if isinstance(env, str) and len(env) >= 6:
        secrets.append(env)
    return secrets


def redact(text: str, secrets: list[str] | None = None) -> str:
    cleaned = text
    for secret in secrets if secrets is not None else known_secrets():
        if secret:
            cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


def _validate_entry(entry: dict) -> dict:
    provider = entry.get("provider")
    if provider not in PROVIDERS:
        raise SettingsError("provider must be one of " + ", ".join(PROVIDERS))
    label = str(entry.get("label") or provider).strip()
    if not label or len(label) > 80:
        raise SettingsError("label must be 1 to 80 characters")
    provider_id = str(entry.get("id") or _slug(label))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", provider_id):
        raise SettingsError("id must be lowercase letters, numbers, and hyphens")
    base_url = str(entry.get("base_url") or "").strip()
    if base_url:
        _check_base_url(base_url)
    key = entry.get("api_key")
    if key is None:
        key = ""
    if not isinstance(key, str):
        raise SettingsError("api_key must be a string")
    if len(key) > 4096:
        raise SettingsError("api_key is too long")
    model = str(entry.get("model") or "").strip()
    return {
        "api_key": key,
        "base_url": base_url,
        "id": provider_id,
        "input_usd_per_million": _optional_price(entry.get("input_usd_per_million")),
        "label": label,
        "model": model,
        "output_usd_per_million": _optional_price(entry.get("output_usd_per_million")),
        "provider": provider,
    }


def _optional_price(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError("prices must be numbers or empty") from exc
    if number < 0 or number > 10000:
        raise SettingsError("price per million tokens must be from 0 to 10000")
    return number


def _check_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SettingsError("base_url must be an http or https URL")
    if parsed.username or parsed.password:
        raise SettingsError("base_url must not contain a username or password")
    if parsed.query and _QUERY_SECRET.search(parsed.query):
        raise SettingsError("base_url must not carry a key in the query string")


def _public_url(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}{parsed.path}"


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug[:64] or "provider"
