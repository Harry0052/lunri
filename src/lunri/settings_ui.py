"""Local settings page. It binds to loopback and never prints an API key."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from lunri.keystore import (
    PROVIDERS,
    SettingsError,
    delete_provider,
    public_providers,
    redact,
    upsert_provider,
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lunri settings</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; font: 16px/1.45 sans-serif; color: #172026; background: #f4f7f8; }
  main { max-width: 40rem; margin: 0 auto; padding: 1rem; }
  h1 { font-size: 1.4rem; }
  form, section { background: #fff; border: 1px solid #c9d3d8; padding: 1rem; margin: 1rem 0; }
  label { display: block; margin: 0.7rem 0 0.2rem; font-weight: 600; }
  input, select, button { width: 100%; box-sizing: border-box; font: inherit; padding: 0.45rem; }
  button { margin-top: 0.8rem; background: #173f4f; color: #fff; border: 0; }
  button:focus, input:focus, select:focus { outline: 3px solid #0b6e4f; outline-offset: 2px; }
  .status { min-height: 1.4rem; }
  li { margin: 0.4rem 0; }
  @media (max-width: 24rem) { main { padding: 0.5rem; } }
</style>
</head>
<body>
<main>
  <h1>Lunri settings</h1>
  <p>Keys are written only to the settings file on this computer. This page does not show a key after it is saved, and Lunri does not upload it.</p>
  <p id="status" class="status" role="status">__STATUS__</p>
  <form method="post" action="/providers">
    <input type="hidden" name="csrf" value="__CSRF__">
    <label for="provider">Provider</label>
    <select id="provider" name="provider">
      __OPTIONS__
    </select>
    <label for="label">Name</label>
    <input id="label" name="label" required maxlength="80" autocomplete="off">
    <label for="model">Default model</label>
    <input id="model" name="model" maxlength="200" autocomplete="off">
    <label for="base_url">Base URL, if this is not the provider default</label>
    <input id="base_url" name="base_url" inputmode="url" autocomplete="off">
    <label for="input_price">Input USD per million tokens, optional</label>
    <input id="input_price" name="input_usd_per_million" inputmode="decimal">
    <label for="output_price">Output USD per million tokens, optional</label>
    <input id="output_price" name="output_usd_per_million" inputmode="decimal">
    <label for="api_key">API key</label>
    <input id="api_key" name="api_key" type="password" autocomplete="off">
    <button type="submit">Save on this computer</button>
  </form>
  <section>
    <h2>Saved providers</h2>
    __LIST__
  </section>
</main>
</body>
</html>
"""


class SettingsUI:
    def __init__(self, csrf: str = "lunri-local"):
        self.csrf = csrf
        self.httpd: ThreadingHTTPServer | None = None

    def start(self, host: str = "127.0.0.1", port: int = 0) -> tuple[str, int]:
        if host != "127.0.0.1":
            raise SettingsError("the settings UI only binds to 127.0.0.1")
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args) -> None:
                return

            def do_GET(self) -> None:
                if self.path.split("?", 1)[0] != "/":
                    self._send(404, b"not found\n", "text/plain; charset=utf-8")
                    return
                self._send(200, ui.render("").encode("utf-8"), "text/html; charset=utf-8")

            def do_POST(self) -> None:
                path = self.path.split("?", 1)[0]
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length > 100_000:
                    self._send(413, b"too large\n", "text/plain; charset=utf-8")
                    return
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                form = {key: values[0] for key, values in parse_qs(raw, keep_blank_values=True).items()}
                if form.get("csrf") != ui.csrf:
                    self._send(403, ui.render("The form token did not match.").encode("utf-8"), "text/html; charset=utf-8")
                    return
                try:
                    if path == "/providers":
                        upsert_provider(
                            {
                                "api_key": form.get("api_key", ""),
                                "base_url": form.get("base_url", ""),
                                "input_usd_per_million": form.get("input_usd_per_million") or None,
                                "label": form.get("label", ""),
                                "model": form.get("model", ""),
                                "output_usd_per_million": form.get("output_usd_per_million") or None,
                                "provider": form.get("provider", ""),
                            }
                        )
                        message = "Saved. The key is stored locally and is not shown here."
                    elif path == "/providers/delete":
                        delete_provider(form.get("id", ""))
                        message = "Removed that provider from the local file."
                    else:
                        self._send(404, b"not found\n", "text/plain; charset=utf-8")
                        return
                except SettingsError as exc:
                    message = str(exc)
                self._send(200, ui.render(message).encode("utf-8"), "text/html; charset=utf-8")

            def _send(self, status: int, body: bytes, content_type: str) -> None:
                safe = redact(body.decode("utf-8")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(safe)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(safe)

        self.httpd = ThreadingHTTPServer((host, port), Handler)
        thread_target = self.httpd.serve_forever
        import threading

        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()
        bound = self.httpd.server_address
        return str(bound[0]), int(bound[1])

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()

    def render(self, status: str) -> str:
        options = "\n".join(f'<option value="{name}">{name}</option>' for name in PROVIDERS)
        items = public_providers()
        if not items:
            listing = "<p>No providers saved.</p>"
        else:
            rows = []
            for item in items:
                key = "key saved" if item["key_set"] else "no key"
                rows.append(
                    "<li>"
                    f"{_escape(str(item['label']))} ({_escape(str(item['provider']))}, "
                    f"model {_escape(str(item['model'] or 'unset'))}, {key})"
                    f"<form method=\"post\" action=\"/providers/delete\">"
                    f"<input type=\"hidden\" name=\"csrf\" value=\"{_escape(self.csrf)}\">"
                    f"<input type=\"hidden\" name=\"id\" value=\"{_escape(str(item['id']))}\">"
                    "<button type=\"submit\">Remove</button></form></li>"
                )
            listing = "<ul>" + "".join(rows) + "</ul>"
        page = (
            PAGE.replace("__STATUS__", _escape(status))
            .replace("__CSRF__", _escape(self.csrf))
            .replace("__OPTIONS__", options)
            .replace("__LIST__", listing)
        )
        return page


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def public_settings_json() -> str:
    return json.dumps(public_providers(), indent=2, sort_keys=True) + "\n"
