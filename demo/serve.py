from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def load_runtime():
    root = Path(__file__).resolve().parents[1] / "plugin" / "hermes_ops"
    name = "_ops_demo_loader_" + hashlib.sha256(str(root).encode()).hexdigest()[:24]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / "runtime_loader.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def create_server(data_dir, port=8765):
    runtime = load_runtime()
    runtime.load_core()
    data_dir = Path(data_dir).expanduser().resolve()
    csrf_token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        server_version = "SyntheticOps"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            return

        def send_payload(self, status, payload, content_type="application/json; charset=utf-8"):
            encoded = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; base-uri 'none'; frame-ancestors 'self'; form-action 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def valid_request(self):
            hosts = self.headers.get_all("Host", [])
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if len(hosts) != 1 or hosts[0].lower() not in expected:
                self.send_payload(403, {"error": "Only the loopback server Host is accepted"})
                return False
            origins = self.headers.get_all("Origin", [])
            if origins and (len(origins) != 1 or origins[0] != "http://" + hosts[0]):
                self.send_payload(403, {"error": "Foreign origin rejected"})
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_payload(403, {"error": "Cross-site requests are not accepted"})
                return False
            return True

        def handle_api(self, method):
            if not self.valid_request():
                return
            try:
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc:
                    self.send_payload(403, {"error": "Absolute request targets are not accepted"})
                    return
                path = unquote(parsed.path)
                if method == "GET" and path in {"/", "/ui"}:
                    self.send_payload(200, runtime.render_html("/api", csrf_token), "text/html; charset=utf-8")
                    return
                if not path.startswith("/api/"):
                    raise KeyError(path)
                body = None
                if method == "POST":
                    if not secrets.compare_digest(self.headers.get("X-Ops-CSRF", ""), csrf_token):
                        self.send_payload(403, {"error": "CSRF token required"})
                        return
                    if self.headers.get("Transfer-Encoding"):
                        self.send_payload(400, {"error": "Transfer encoding is unsupported"})
                        return
                    lengths = self.headers.get_all("Content-Length", [])
                    if len(lengths) != 1 or not lengths[0].isdigit():
                        self.send_payload(411, {"error": "One valid Content-Length is required"})
                        return
                    length = int(lengths[0])
                    if length > runtime.BODY_LIMIT:
                        self.send_payload(413, {"error": "Request body exceeds 64 KiB"})
                        return
                    if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                        self.send_payload(415, {"error": "Expected application/json"})
                        return
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError("Incomplete request body")
                    body = runtime.strict_json(raw)
                payload = runtime.dispatch(method, path[4:], body, data_dir)
                self.send_payload(200, payload)
            except Exception as exc:
                status, payload = runtime.error_response(exc)
                self.send_payload(status, payload)

        def do_GET(self):
            self.handle_api("GET")

        def do_POST(self):
            self.handle_api("POST")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Loopback-only synthetic manufacturing control room")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    server = create_server(args.data_dir, args.port)
    print(f"Synthetic operations: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Data root: {args.data_dir.expanduser().resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
