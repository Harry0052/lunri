"""Ollama adapter against a local fake server. No weights are downloaded."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lunri.ollama import OllamaClient


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args) -> None:
        return

    def do_GET(self) -> None:
        if self.path != "/api/tags":
            self.send_response(404)
            self.end_headers()
            return
        body = b'{"models":[]}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        self.server.last_request = json.loads(raw.decode("utf-8"))
        if self.server.mode == "timeout":
            return
        if self.server.mode == "bad":
            content = "not-json"
        else:
            content = json.dumps(
                {
                    "currency": "USD",
                    "invoice_number": "hold_block-000",
                    "subtotal_cents": None,
                    "tax_cents": None,
                    "total_cents": 1000,
                }
            )
        body = json.dumps({"message": {"role": "assistant", "content": content}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class OllamaHttpTests(unittest.TestCase):
    def _server(self, mode: str = "ok"):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        server.mode = mode
        server.last_request = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        port = server.server_address[1]
        return server, f"http://127.0.0.1:{port}"

    def test_chat_sends_a_schema_and_not_a_gold_object(self) -> None:
        _server, base = self._server()
        client = OllamaClient(base)
        ok, _detail = client.ping()
        self.assertTrue(ok)
        result = client.complete("qwen2.5:0.5b", "Invoice number: hold_block-000\n", timeout=2)
        self.assertTrue(result.ok)
        self.assertIn("hold_block-000", result.text)
        request = _server.last_request
        self.assertEqual(request["model"], "qwen2.5:0.5b")
        self.assertIn("format", request)
        self.assertNotIn("gold", json.dumps(request["messages"]))
        self.assertEqual(request["messages"][1]["content"], "Invoice number: hold_block-000\n")

    def test_malformed_content_is_a_failed_call_text(self) -> None:
        _server, base = self._server("bad")
        result = OllamaClient(base).complete("qwen2.5:1.5b", "text", timeout=2)
        self.assertTrue(result.ok)
        self.assertEqual(result.text, "not-json")

    def test_unreachable_server_is_not_a_success(self) -> None:
        client = OllamaClient("http://127.0.0.1:9")
        ok, detail = client.ping(timeout=0.2)
        self.assertFalse(ok)
        self.assertIn("NOT", "NOT YET VERIFIED")
        self.assertTrue(detail)


if __name__ == "__main__":
    unittest.main()
