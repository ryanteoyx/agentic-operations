from __future__ import annotations

import hashlib
import importlib.util
import secrets
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_NAME = "_ops_dashboard_loader_" + hashlib.sha256(str(_ROOT).encode()).hexdigest()[:24]
if _NAME not in sys.modules:
    _SPEC = importlib.util.spec_from_file_location(_NAME, _ROOT / "runtime_loader.py")
    _MODULE = importlib.util.module_from_spec(_SPEC)
    sys.modules[_NAME] = _MODULE
    _SPEC.loader.exec_module(_MODULE)
runtime = sys.modules[_NAME]
CSRF_TOKEN = secrets.token_urlsafe(32)
API_PREFIX = "/api/plugins/agentic-operations"
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; base-uri 'none'; frame-ancestors 'self'; form-action 'none'",
}


def create_router():
    from fastapi import APIRouter, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from starlette.concurrency import run_in_threadpool

    globals()["Request"] = Request
    result = APIRouter()

    @result.get("/ui", response_class=HTMLResponse)
    def ui():
        return HTMLResponse(runtime.render_html(API_PREFIX, CSRF_TOKEN), headers=SECURITY_HEADERS)

    @result.api_route("/{path:path}", methods=["GET", "POST"])
    async def api(path: str, request: Request):
        try:
            body = None
            if request.method == "POST":
                origin = request.headers.get("origin")
                if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                    return JSONResponse({"error": "Foreign origin rejected"}, status_code=403, headers=SECURITY_HEADERS)
                if not secrets.compare_digest(request.headers.get("x-ops-csrf", ""), CSRF_TOKEN):
                    return JSONResponse({"error": "CSRF token required"}, status_code=403, headers=SECURITY_HEADERS)
                if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                    return JSONResponse({"error": "Expected application/json"}, status_code=415, headers=SECURITY_HEADERS)
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > runtime.BODY_LIMIT:
                        return JSONResponse({"error": "Request body exceeds 64 KiB"}, status_code=413, headers=SECURITY_HEADERS)
                body = runtime.strict_json(raw)
            payload = await run_in_threadpool(runtime.dispatch, request.method, "/" + path, body)
            return JSONResponse(payload, headers=SECURITY_HEADERS)
        except Exception as exc:
            status, payload = runtime.error_response(exc)
            return JSONResponse(payload, status_code=status, headers=SECURITY_HEADERS)

    return result


try:
    import fastapi
except ImportError:
    router = None
else:
    router = create_router()
