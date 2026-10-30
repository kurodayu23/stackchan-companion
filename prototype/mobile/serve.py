from __future__ import annotations

import argparse
import json
import os
import secrets
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from mobile_proxy import (
    ACCESS_COOKIE_NAME,
    access_cookie_value,
    has_access_cookie,
    handle_mobile_api,
    pairing_token_matches,
    send_json,
)


APP_DIR = Path(__file__).resolve().parent
UPDATE_COMPONENT_ROOT = APP_DIR.parent / "data" / "updates" / "components"
MODEL_FILE = APP_DIR.parent / "vendor" / "m5stack-StackChan" / "app" / "assets" / "stack_chan_model.glb"
MODEL_URL = "/model-assets/stack_chan_model.glb"
DEFAULT_PORT = 17866
PUBLIC_STATIC_PATHS = frozenset(
    {
        "/",
        "/index.html",
        "/styles.css",
        "/manifest.webmanifest",
        "/sw.js",
        "/api.js",
        "/app.js",
        "/chat.js",
        "/camera_panel.js",
        "/screen_programs.js",
        "/update.js",
        "/settings.js",
        "/remote_control.js",
        "/actions_music.js",
        "/robot_3d.js",
        "/vendor/three.module.js",
        "/vendor/loaders/GLTFLoader.js",
        "/vendor/utils/BufferGeometryUtils.js",
    }
)


def active_mobile_app_dir(update_root: Path = UPDATE_COMPONENT_ROOT) -> Path:
    component_root = update_root / "mobile"
    pointer_path = component_root / "active.json"
    if not pointer_path.is_file():
        return APP_DIR
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return APP_DIR
    active = pointer.get("active") if isinstance(pointer, dict) else None
    if not isinstance(active, str) or not active or Path(active).name != active:
        return APP_DIR
    releases_root = (component_root / "releases").resolve()
    candidate = (releases_root / active).resolve()
    if releases_root not in candidate.parents or not (candidate / "release.json").is_file():
        return APP_DIR
    return candidate


def is_public_static_path(path: str) -> bool:
    try:
        decoded = unquote(path, errors="strict")
    except UnicodeError:
        return False
    if "\0" in decoded or "\\" in decoded or any(part in {".", ".."} for part in decoded.split("/")):
        return False
    if decoded in PUBLIC_STATIC_PATHS:
        return True
    if not decoded.startswith("/assets/"):
        return False
    app_dir = active_mobile_app_dir()
    candidate = (app_dir / decoded.removeprefix("/")).resolve()
    assets_dir = (app_dir / "assets").resolve()
    return candidate.is_file() and assets_dir in candidate.parents


class MobileAppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        decoded = unquote(urlsplit(path).path, errors="replace")
        parts = [part for part in decoded.split("/") if part and part not in {".", ".."}]
        return str(active_mobile_app_dir().joinpath(*parts))

    def log_request(self, code="-", size="-"):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if "pair" not in query:
            super().log_request(code, size)
            return
        self.log_message(
            '"%s %s %s" %s %s',
            self.command,
            f"{parsed.path}?pair=<redacted>",
            self.request_version,
            str(code),
            str(size),
        )

    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if parsed.path == "/mobile-health":
            paired = has_access_cookie(
                self.headers.get("Cookie"),
                os.getenv("STACKCHAN_MOBILE_ACCESS_TOKEN", ""),
            )
            body = json.dumps(
                {
                    "ok": True,
                    "service": "stackchan-mobile",
                    "paired": paired,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-StackChan-Service", "mobile-app")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/" and "pair" in query:
            self._pair(query)
            return
        if parsed.path.startswith("/mobile-api/"):
            handle_mobile_api(
                self,
                "GET",
                parsed.path,
                os.getenv("STACKCHAN_MOBILE_ACCESS_TOKEN", ""),
            )
            return
        if parsed.path == MODEL_URL:
            if not MODEL_FILE.is_file():
                self.send_error(404, "3D model not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(MODEL_FILE.stat().st_size))
            self.end_headers()
            with MODEL_FILE.open("rb") as source:
                self.copyfile(source, self.wfile)
            return
        if not is_public_static_path(parsed.path):
            self.send_error(404, "Not found")
            return
        super().do_GET()

    def do_HEAD(self):
        if not is_public_static_path(urlsplit(self.path).path):
            self.send_error(404, "Not found")
            return
        super().do_HEAD()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path.startswith("/mobile-api/"):
            handle_mobile_api(
                self,
                "POST",
                path,
                os.getenv("STACKCHAN_MOBILE_ACCESS_TOKEN", ""),
            )
            return
        send_json(self, 404, {"detail": "Not found."})

    def _pair(self, query: dict[str, list[str]]) -> None:
        values = query.get("pair", [])
        expected = os.getenv("STACKCHAN_MOBILE_ACCESS_TOKEN", "")
        if set(query) != {"pair"} or len(values) != 1 or not pairing_token_matches(values[0], expected):
            send_json(self, 401, {"detail": "Pairing token is invalid."})
            return
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{ACCESS_COOKIE_NAME}={access_cookie_value(expected)}; HttpOnly; SameSite=Strict; Path=/",
        )
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def end_headers(self):
        headers = getattr(self, "_headers_buffer", ())
        if not any(header.lower().startswith(b"cache-control:") for header in headers):
            self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the StackChan mobile app")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args()

    if not os.getenv("STACKCHAN_MOBILE_ACCESS_TOKEN"):
        os.environ["STACKCHAN_MOBILE_ACCESS_TOKEN"] = secrets.token_urlsafe(32)

    handler = partial(MobileAppHandler, directory=str(APP_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"StackChan mobile app: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
