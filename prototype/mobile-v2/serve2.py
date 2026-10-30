"""mobile-v2 同源服务：静态页面 + /mobile-api/* 白名单代理转发到 17865 后端。

设计要点（对齐旧 mobile_proxy 的安全模型）：
- 页面与接口同源（同一端口），浏览器从不直接接触后端地址；
- /mobile-api/* 只转发白名单路由，不接受客户端提供主机/协议/路径；
- 写操作要求 CSRF 头 + Origin 同源校验；
- 无配对逻辑：本项目定位为「个人局域网遥控台」，与旧项目 17865 同机部署。
"""
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

ROOT = Path(__file__).resolve().parent
UPSTREAM_ORIGIN = os.getenv("STACKCHAN_UPSTREAM", "http://127.0.0.1:17865")
LISTEN_PORT = int(os.getenv("STACKCHAN_MOBILE2_PORT", "17867"))
UPSTREAM_TIMEOUT_SECONDS = 15.0
CHAT_UPSTREAM_TIMEOUT_SECONDS = 45.0
MAX_REQUEST_BODY_BYTES = 32 * 1024

ALLOWED_ROUTES = {
    ("GET", "/mobile-api/device/status"): "/gui/device/status",
    ("GET", "/mobile-api/experience"): "/gui/experience",
    ("POST", "/mobile-api/chat"): "/gui/mobile-chat",
    ("POST", "/mobile-api/device/head"): "/gui/device/head",
    ("POST", "/mobile-api/device/macro"): "/gui/device/macro",
    ("POST", "/mobile-api/device/led"): "/gui/device/led",
    ("POST", "/mobile-api/device/volume"): "/gui/device/volume",
    ("POST", "/mobile-api/device/brightness"): "/gui/device/brightness",
}

STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
    "/api.js": "api.js",
    "/remote.js": "remote.js",
    "/chat.js": "chat.js",
    "/preview3d.js": "preview3d.js",
    "/manifest.webmanifest": "manifest.webmanifest",
    "/device-screen.html": "device-screen.html",
    "/vendor/three/three.module.js": "vendor/three/three.module.js",
    "/vendor/three/GLTFLoader.js": "vendor/three/GLTFLoader.js",
    "/vendor/utils/BufferGeometryUtils.js": "vendor/utils/BufferGeometryUtils.js",
    "/assets/stack_chan_model.glb": "assets/stack_chan_model.glb",
}

_OPENER = build_opener()


def _send_json(handler, status: int, payload) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler) -> dict:
    content_type = handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ValueError("Content-Type must be application/json")
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        raise ValueError("Content-Length is required")
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("Content-Length is invalid") from exc
    if length < 0 or length > MAX_REQUEST_BODY_BYTES:
        raise ValueError("Request body is too large")
    raw = handler.rfile.read(length) if length else b""
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _proxy(handler, method: str, path: str) -> None:
    upstream = ALLOWED_ROUTES.get((method, path))
    if upstream is None:
        _send_json(handler, 404, {"detail": "Mobile API route was not found."})
        return

    payload = None
    if method == "POST":
        if handler.headers.get("X-StackChan-CSRF") != "1":
            _send_json(handler, 403, {"detail": "CSRF validation failed."})
            return
        origin = handler.headers.get("Origin")
        if origin:
            expected = f"http://{handler.headers.get('Host', '')}"
            if origin.rstrip("/") != expected.rstrip("/"):
                _send_json(handler, 403, {"detail": "Cross-site request was rejected."})
                return
        try:
            payload = _read_json_body(handler)
        except ValueError as exc:
            _send_json(handler, 400, {"detail": str(exc)})
            return

    timeout = CHAT_UPSTREAM_TIMEOUT_SECONDS if path == "/mobile-api/chat" else UPSTREAM_TIMEOUT_SECONDS
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(f"{UPSTREAM_ORIGIN}{upstream}", data=body, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            raw = response.read()
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                _send_json(handler, 502, {"detail": "上游返回了无法解析的内容。"})
                return
            _send_json(handler, 200, data)
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
        except Exception:
            detail = str(exc)
        _send_json(handler, exc.code, {"detail": detail})
    except (URLError, TimeoutError) as exc:
        _send_json(handler, 502, {"detail": f"上游不可用：{exc}"})


class Mobile2Handler(BaseHTTPRequestHandler):
    server_version = "Mobile2/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _serve_static(self, path: str) -> None:
        rel = STATIC_FILES.get(path)
        if rel is None:
            self.send_error(404)
            return
        target = (ROOT / rel).resolve()
        if not target.is_file() or ROOT not in target.parents:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".glb":
            content_type = "model/gltf-binary"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path.startswith("/mobile-api/"):
            _proxy(self, "GET", self.path)
        else:
            self._serve_static(path)

    def do_POST(self):
        if self.path.startswith("/mobile-api/"):
            _proxy(self, "POST", self.path)
        else:
            _send_json(self, 404, {"detail": "Not found."})


def main() -> None:
    httpd = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Mobile2Handler)
    print(f"mobile-v2 serving on http://127.0.0.1:{LISTEN_PORT}  (upstream {UPSTREAM_ORIGIN})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()