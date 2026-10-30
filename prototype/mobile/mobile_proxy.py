from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import socket
from http.cookies import CookieError, SimpleCookie
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


#: 上游后端地址。默认指向**桌面端电脑后台**（17865）；
#: 想让手机端跑在本仓自带的 HTTP 适配层上，就设：
#:   $env:STACKCHAN_BACKEND_ORIGIN="http://127.0.0.1:17865"   # 本仓 server/http_api.py
#: （两个进程不能同时占同一端口 ⇒ 指向本仓时把它跑在 17868 之类）
UPSTREAM_ORIGIN = os.getenv("STACKCHAN_BACKEND_ORIGIN", "http://127.0.0.1:17865").rstrip("/")
UPSTREAM_TIMEOUT_SECONDS = 15.0
CHAT_UPSTREAM_TIMEOUT_SECONDS = 45.0
MAX_REQUEST_BODY_BYTES = 16 * 1024
MAX_DISCARD_BODY_BYTES = 64 * 1024
MAX_JSON_RESPONSE_BYTES = 1024 * 1024
MAX_CAMERA_RESPONSE_BYTES = 4 * 1024 * 1024
ACCESS_COOKIE_NAME = "stackchan_mobile_access"

ALLOWED_ROUTES = {
    ("GET", "/mobile-api/device/status"): "/gui/device/status",
    ("POST", "/mobile-api/chat"): "/gui/mobile-chat",
    ("GET", "/mobile-api/screen-programs"): "/gui/screen-programs",
    ("POST", "/mobile-api/screen-programs/control"): "/gui/screen-programs/control",
    ("GET", "/mobile-api/experience"): "/gui/experience",
    ("POST", "/mobile-api/experience"): "/gui/experience",
    ("GET", "/mobile-api/memory"): "/gui/memory",
    ("POST", "/mobile-api/memory/remove"): "/gui/memory/remove",
    ("POST", "/mobile-api/memory/clear"): "/gui/memory/clear",
    ("GET", "/mobile-api/firmware/status"): "/gui/firmware/status",
    ("POST", "/mobile-api/firmware/install"): "/gui/firmware/install",
    ("GET", "/mobile-api/assets/status"): "/gui/assets/status",
    ("POST", "/mobile-api/assets/install"): "/gui/assets/install",
    ("GET", "/mobile-api/update/status"): "/gui/update/status",
    ("POST", "/mobile-api/update/check"): "/gui/update/check",
    ("POST", "/mobile-api/update/prepare"): "/gui/update/prepare",
    ("POST", "/mobile-api/update/install"): "/gui/update/install",
    ("GET", "/mobile-api/music-library"): "/gui/music-library",
    ("GET", "/mobile-api/music-library/status"): "/gui/music-library/status",
    ("POST", "/mobile-api/music-library/play"): "/gui/music-library/play",
    ("POST", "/mobile-api/music-library/control"): "/gui/music-library/control",
    ("POST", "/mobile-api/device/network/status"): "/gui/device/network/status",
    ("POST", "/mobile-api/device/network/scan"): "/gui/device/network/scan",
    ("POST", "/mobile-api/device/network/connect"): "/gui/device/network/connect",
    # 2026-10-30 补：settings.js:486 真实调用 `/device/network/key`，
    # 原白名单漏了它 ⇒ 代理层直接 404，页面永远拿不到配网信息。
    ("GET", "/mobile-api/device/network/key"): "/gui/device/network/key",
    ("GET", "/mobile-api/device/factory-voices"): "/gui/device/factory-voices",
    ("GET", "/mobile-api/device/factory-audio"): "/gui/device/factory-audio",
    ("POST", "/mobile-api/device/factory-audio"): "/gui/device/factory-audio",
    ("GET", "/mobile-api/device/camera/latest"): "/gui/device/camera/latest",
    ("GET", "/mobile-api/device/camera/latest.jpg"): "/gui/device/camera/latest.jpg",
    ("POST", "/mobile-api/device/camera-preview/start"): "/gui/device/camera-preview/start",
    ("POST", "/mobile-api/device/camera-preview/stop"): "/gui/device/camera-preview/stop",
    ("POST", "/mobile-api/device/volume"): "/gui/device/volume",
    ("POST", "/mobile-api/device/brightness"): "/gui/device/brightness",
    ("POST", "/mobile-api/device/led"): "/gui/device/led",
    ("POST", "/mobile-api/device/head"): "/gui/device/head",
    ("POST", "/mobile-api/device/macro"): "/gui/device/macro",
}

MEMORY_KEYS = {
    "likes",
    "dislikes",
    "goals",
    "important",
    "relationship",
    "giver",
    "temporary",
    "conversation_notes",
    "insights",
}
REACTION_FLAGS = {"auto_gaze_enabled", "visual_tracking_enabled", "thinking_cue_enabled"}
PRIVACY_FLAGS = {"memory_enabled", "chat_history_enabled", "camera_enabled"}
MACRO_PRESETS = {"nod", "cheer", "listen", "ielts_focus", "shy", "sleep", "focus_ping"}
FACTORY_AUDIO_IDS = {
    "new_notification",
    "camera_shutter",
    "music_soft_chime",
    "music_focus_loop",
    "music_sleep_pad",
    "music_stop",
}
SCREEN_PROGRAM_IDS = {
    "chat",
    "quote",
    "album",
    "mood",
    "pomodoro",
    "fortune",
    "game",
    "settings",
}


class ProxyRequestError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_UPSTREAM_OPENER = build_opener(_NoRedirect())


class _ProvisioningKey:
    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_der = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.key_id = hashlib.sha256(public_der).hexdigest()[:24]
        self.public_key = base64.b64encode(public_der).decode("ascii")

    def decrypt(self, key_id: Any, ciphertext: Any) -> str:
        if key_id != self.key_id or not isinstance(ciphertext, str) or not ciphertext:
            raise ProxyRequestError(400, "配网请求已经失效，请重新选择网络。")
        try:
            encrypted = base64.b64decode(ciphertext, validate=True)
            if len(encrypted) != 256:
                raise ValueError("invalid ciphertext length")
            plaintext = self._private_key.decrypt(
                encrypted,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            password = plaintext.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProxyRequestError(400, "配网请求已经失效，请重新选择网络。") from exc
        if len(password.encode("utf-8")) > 64 or "\0" in password:
            raise ProxyRequestError(400, "Wi-Fi 密码格式不受支持。")
        return password


_PROVISIONING_KEY = _ProvisioningKey()


def send_json(handler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("X-Content-Type-Options", "nosniff")
    if handler.close_connection:
        handler.send_header("Connection", "close")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        handler.close_connection = True


def pairing_token_matches(provided: str, expected: str) -> bool:
    return bool(provided and expected) and _constant_time_text_matches(provided, expected)


def _constant_time_text_matches(provided: str, expected: str) -> bool:
    try:
        return hmac.compare_digest(provided, expected)
    except TypeError:
        return False


def has_access_cookie(cookie_header: str | None, expected: str) -> bool:
    if not cookie_header or not expected:
        return False
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except CookieError:
        return False
    morsel = cookie.get(ACCESS_COOKIE_NAME)
    return morsel is not None and pairing_token_matches(morsel.value, access_cookie_value(expected))


def access_cookie_value(pairing_token: str) -> str:
    if not pairing_token:
        return ""
    digest = hmac.new(
        pairing_token.encode("utf-8"),
        b"stackchan-mobile-session-v1",
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def handle_mobile_api(handler, method: str, path: str, access_token: str) -> None:
    if method == "GET" and path == "/mobile-api/device/network/key":
        if not has_access_cookie(handler.headers.get("Cookie"), access_token):
            send_json(handler, 401, {"detail": "需要先完成手机配对。"})
            return
        send_json(
            handler,
            200,
            {
                "algorithm": "RSA-OAEP-256",
                "key_id": _PROVISIONING_KEY.key_id,
                "public_key": _PROVISIONING_KEY.public_key,
            },
        )
        return
    upstream_path = ALLOWED_ROUTES.get((method, path))
    if upstream_path is None:
        if method == "POST":
            _discard_small_request_body(handler)
        send_json(handler, 404, {"detail": "Mobile API route was not found."})
        return
    if not has_access_cookie(handler.headers.get("Cookie"), access_token):
        send_json(handler, 401, {"detail": "需要先完成手机配对。"})
        return

    try:
        payload = None
        if method == "POST":
            _require_write_headers(handler)
            raw_payload = _read_json_body(handler)
            _require_confirmation(handler, path)
            payload = _validate_payload(path, raw_payload)
            if path in {"/mobile-api/firmware/install", "/mobile-api/assets/install"}:
                status_path = "/gui/firmware/status" if path == "/mobile-api/firmware/install" else "/gui/assets/status"
                staged = _request_json("GET", status_path, None).get("artifact")
                if not isinstance(staged, dict) or staged.get("id") != payload.get("artifact_id"):
                    raise ProxyRequestError(409, "可安装版本已经变化，请重新检查更新。")
            if path == "/mobile-api/update/install":
                staged = _request_json("GET", "/gui/update/status", None)
                if staged.get("state") != "staged" or staged.get("release_id") != payload.get("release_id"):
                    raise ProxyRequestError(409, "可安装版本已经变化，请重新检查更新。")

        if path == "/mobile-api/device/camera/latest.jpg":
            content_type, body = _request_bytes(method, upstream_path, payload, MAX_CAMERA_RESPONSE_BYTES)
            handler.send_response(200)
            handler.send_header("Content-Type", "image/jpeg" if content_type.startswith("image/jpeg") else "application/octet-stream")
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Cache-Control", "no-store, max-age=0")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.end_headers()
            handler.wfile.write(body)
            return

        response = _request_json(method, upstream_path, payload)
        send_json(handler, 200, _sanitize_response(path, response))
    except ProxyRequestError as exc:
        send_json(handler, exc.status, {"detail": exc.detail})


def _require_write_headers(handler) -> None:
    if handler.headers.get("X-StackChan-CSRF") != "1":
        raise ProxyRequestError(403, "CSRF validation failed.")
    origin = handler.headers.get("Origin")
    if origin:
        expected = f"http://{handler.headers.get('Host', '')}"
        if not _constant_time_text_matches(origin.rstrip("/"), expected.rstrip("/")):
            raise ProxyRequestError(403, "Cross-site request was rejected.")


def _require_confirmation(handler, path: str) -> None:
    required = {
        "/mobile-api/memory/clear": "clear-memory",
        "/mobile-api/firmware/install": "install-firmware",
        "/mobile-api/assets/install": "install-assets",
        "/mobile-api/device/network/connect": "connect-wifi",
        "/mobile-api/update/prepare": "prepare-release",
        "/mobile-api/update/install": "install-release",
    }.get(path)
    if required and handler.headers.get("X-StackChan-Confirm") != required:
        raise ProxyRequestError(403, "Explicit confirmation is required.")


def _read_json_body(handler) -> dict[str, Any]:
    content_type = handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ProxyRequestError(415, "Content-Type must be application/json.")
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        raise ProxyRequestError(411, "Content-Length is required.")
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ProxyRequestError(400, "Content-Length is invalid.") from exc
    if length < 0:
        raise ProxyRequestError(400, "Content-Length is invalid.")
    if length > MAX_REQUEST_BODY_BYTES:
        _discard_small_request_body(handler, length)
        handler.close_connection = True
        raise ProxyRequestError(413, "Request body is too large.")
    raw_body = handler.rfile.read(length)
    if len(raw_body) != length:
        raise ProxyRequestError(400, "Request body is incomplete.")
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProxyRequestError(400, "Request body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ProxyRequestError(400, "Request body must be a JSON object.")
    return payload


def _discard_small_request_body(handler, length: int | None = None) -> None:
    if length is None:
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError:
            handler.close_connection = True
            return
    if length < 0 or length > MAX_DISCARD_BODY_BYTES:
        handler.close_connection = True
        return
    remaining = length
    while remaining:
        chunk = handler.rfile.read(min(remaining, 16 * 1024))
        if not chunk:
            handler.close_connection = True
            return
        remaining -= len(chunk)


def _validate_payload(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    validators: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "/mobile-api/chat": _validate_chat,
        "/mobile-api/screen-programs/control": _validate_screen_program_control,
        "/mobile-api/experience": _validate_experience,
        "/mobile-api/memory/remove": _validate_memory_remove,
        "/mobile-api/memory/clear": _validate_memory_clear,
        "/mobile-api/music-library/play": _validate_music_play,
        "/mobile-api/music-library/control": _validate_music_control,
        "/mobile-api/device/network/status": _validate_empty,
        "/mobile-api/device/network/scan": _validate_empty,
        "/mobile-api/device/network/connect": _validate_wifi_connect,
        "/mobile-api/device/camera-preview/start": _validate_camera_start,
        "/mobile-api/device/camera-preview/stop": _validate_empty,
        "/mobile-api/device/volume": _validate_volume,
        "/mobile-api/device/brightness": _validate_brightness,
        "/mobile-api/device/led": _validate_led,
        "/mobile-api/device/head": _validate_head,
        "/mobile-api/device/macro": _validate_macro,
        "/mobile-api/device/factory-audio": _validate_factory_audio,
        "/mobile-api/firmware/install": _validate_firmware_install,
        "/mobile-api/assets/install": _validate_firmware_install,
        "/mobile-api/update/check": _validate_empty,
        "/mobile-api/update/prepare": _validate_release_prepare,
        "/mobile-api/update/install": _validate_release_prepare,
    }
    validator = validators.get(path)
    if validator is None:
        raise ProxyRequestError(404, "Mobile API route was not found.")
    return validator(payload)


def _expect_fields(payload: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    unexpected = set(payload) - allowed
    missing = required - set(payload)
    if unexpected:
        raise ProxyRequestError(400, f"Unexpected field: {sorted(unexpected)[0]}")
    if missing:
        raise ProxyRequestError(400, f"Missing field: {sorted(missing)[0]}")


def _integer(value: Any, minimum: int, maximum: int, field: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProxyRequestError(400, f"{field} must be between {minimum} and {maximum}.")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ProxyRequestError(400, f"{field} must be a boolean.")
    return value


def _validate_chat(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"message"}, {"message"})
    message = payload["message"]
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ProxyRequestError(400, "message must contain 1 to 2000 characters.")
    return {"message": message.strip()}


def _validate_screen_program_control(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"program_id", "action"}, {"program_id", "action"})
    program_id = payload["program_id"]
    action = payload["action"]
    if not isinstance(program_id, str) or program_id not in SCREEN_PROGRAM_IDS:
        raise ProxyRequestError(400, "Screen program is not available.")
    if action != "open":
        raise ProxyRequestError(400, "Only the open action is available.")
    return {"program_id": program_id, "action": "open"}


def _validate_experience(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"persona", "reaction", "privacy"}, set())
    if not payload:
        raise ProxyRequestError(400, "Experience patch is empty.")
    result: dict[str, Any] = {}
    if "persona" in payload:
        persona = payload["persona"]
        if not isinstance(persona, dict) or not persona:
            raise ProxyRequestError(400, "persona must be a non-empty object.")
        _expect_fields(persona, {"address_name", "style"}, set())
        validated: dict[str, Any] = {}
        if "address_name" in persona:
            value = persona["address_name"]
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 20:
                raise ProxyRequestError(400, "address_name must contain 1 to 20 characters.")
            validated["address_name"] = value.strip()
        if "style" in persona:
            style = persona["style"]
            if not isinstance(style, str) or style not in {"lively", "gentle"}:
                raise ProxyRequestError(400, "style must be lively or gentle.")
            validated["style"] = style
        result["persona"] = validated
    if "reaction" in payload:
        reaction = payload["reaction"]
        if not isinstance(reaction, dict) or not reaction:
            raise ProxyRequestError(400, "reaction must be a non-empty object.")
        _expect_fields(reaction, REACTION_FLAGS | {"liveliness_level"}, set())
        validated = {}
        for key, value in reaction.items():
            validated[key] = (
                _integer(value, 0, 3, key) if key == "liveliness_level" else _boolean(value, key)
            )
        result["reaction"] = validated
    if "privacy" in payload:
        privacy = payload["privacy"]
        if not isinstance(privacy, dict) or not privacy:
            raise ProxyRequestError(400, "privacy must be a non-empty object.")
        _expect_fields(privacy, PRIVACY_FLAGS, set())
        result["privacy"] = {key: _boolean(value, key) for key, value in privacy.items()}
    return result


def _validate_memory_key(value: Any) -> str:
    if not isinstance(value, str) or value not in MEMORY_KEYS:
        raise ProxyRequestError(400, "Memory key is not editable.")
    return value


def _validate_memory_remove(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"key", "value"}, {"key", "value"})
    value = payload["value"]
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 48:
        raise ProxyRequestError(400, "Memory value must contain 1 to 48 characters.")
    return {"key": _validate_memory_key(payload["key"]), "value": value.strip()}


def _validate_memory_clear(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"key"}, {"key"})
    return {"key": _validate_memory_key(payload["key"])}


def _validate_music_play(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"track_id"}, {"track_id"})
    track_id = payload["track_id"]
    if not isinstance(track_id, str) or not 1 <= len(track_id.strip()) <= 255 or "\0" in track_id:
        raise ProxyRequestError(400, "track_id is invalid.")
    return {"track_id": track_id.strip()}


def _validate_music_control(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"action"}, {"action"})
    action = payload["action"]
    if not isinstance(action, str) or action not in {"pause", "resume", "stop"}:
        raise ProxyRequestError(400, "Unsupported music action.")
    return {"action": action}


def _validate_empty(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, set(), set())
    return {}


def _validate_wifi_connect(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(
        payload,
        {"ssid", "key_id", "password_ciphertext"},
        {"ssid", "key_id", "password_ciphertext"},
    )
    ssid = payload["ssid"]
    if not isinstance(ssid, str):
        raise ProxyRequestError(400, "请选择有效的 Wi-Fi。")
    ssid = ssid.strip()
    if not ssid or len(ssid.encode("utf-8")) > 32 or "\0" in ssid:
        raise ProxyRequestError(400, "请选择有效的 Wi-Fi。")
    password = _PROVISIONING_KEY.decrypt(payload["key_id"], payload["password_ciphertext"])
    return {"ssid": ssid, "password": password}


def _validate_camera_start(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"quality"}, set())
    if "quality" not in payload:
        return {}
    return {"quality": _integer(payload["quality"], 10, 90, "quality")}


def _validate_volume(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"volume", "permanent"}, {"volume"})
    if "permanent" in payload and type(payload["permanent"]) is not bool:
        raise ProxyRequestError(400, "permanent must be a boolean.")
    return {"volume": _integer(payload["volume"], 0, 100, "volume"), "permanent": False}


def _validate_brightness(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"brightness"}, {"brightness"})
    return {"brightness": _integer(payload["brightness"], 1, 100, "brightness")}


def _validate_led(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"red", "green", "blue"}, {"red", "green", "blue"})
    return {key: _integer(payload[key], 0, 168, key) for key in ("red", "green", "blue")}


def _validate_head(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"yaw", "pitch", "speed"}, set())
    if "yaw" not in payload and "pitch" not in payload:
        raise ProxyRequestError(400, "At least one head axis is required.")
    result: dict[str, Any] = {}
    if "yaw" in payload:
        result["yaw"] = _integer(payload["yaw"], -128, 128, "yaw")
    if "pitch" in payload:
        result["pitch"] = _integer(payload["pitch"], 0, 90, "pitch")
    if "speed" in payload:
        result["speed"] = _integer(payload["speed"], 100, 1000, "speed")
    return result


def _validate_macro(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"preset"}, {"preset"})
    preset = payload["preset"]
    if not isinstance(preset, str) or preset not in MACRO_PRESETS:
        raise ProxyRequestError(400, "Unsupported macro preset.")
    return {"preset": preset}


def _validate_factory_audio(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"sound"}, {"sound"})
    sound = payload["sound"]
    if not isinstance(sound, str) or sound not in FACTORY_AUDIO_IDS:
        raise ProxyRequestError(400, "Unsupported factory audio preset.")
    return {"sound": sound}


def _validate_firmware_install(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"artifact_id", "route"}, {"artifact_id", "route"})
    artifact_id = payload["artifact_id"]
    if not isinstance(artifact_id, str) or not 1 <= len(artifact_id) <= 128:
        raise ProxyRequestError(400, "artifact_id is invalid.")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in artifact_id):
        raise ProxyRequestError(400, "artifact_id is invalid.")
    if payload["route"] != "auto":
        raise ProxyRequestError(400, "Only the automatic update route is available.")
    return {"artifact_id": artifact_id, "route": "auto"}


def _validate_release_prepare(payload: dict[str, Any]) -> dict[str, Any]:
    _expect_fields(payload, {"release_id"}, {"release_id"})
    release_id = payload["release_id"]
    if (
        not isinstance(release_id, str)
        or not 1 <= len(release_id) <= 64
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in release_id)
    ):
        raise ProxyRequestError(400, "可用更新已经变化，请重新检查。")
    return {"release_id": release_id}


def _request_json(method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    _, body = _request_bytes(method, path, payload, MAX_JSON_RESPONSE_BYTES)
    try:
        result = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProxyRequestError(502, "连接服务返回了无效数据。") from exc
    if not isinstance(result, dict):
        raise ProxyRequestError(502, "连接服务返回了无效响应。")
    return result


def _request_bytes(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    response_limit: int,
) -> tuple[str, bytes]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{UPSTREAM_ORIGIN}{path}", data=data, headers=headers, method=method)
    try:
        timeout_seconds = (
            CHAT_UPSTREAM_TIMEOUT_SECONDS if path == "/gui/mobile-chat" else UPSTREAM_TIMEOUT_SECONDS
        )
        response = _UPSTREAM_OPENER.open(request, timeout=timeout_seconds)
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            exc.close()
            raise ProxyRequestError(502, "连接服务返回了不安全的跳转。") from exc
        detail = _safe_error_detail(exc)
        status = exc.code if 400 <= exc.code < 500 else 502
        raise ProxyRequestError(status, detail) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ProxyRequestError(504, "连接请求超时，请稍后重试。") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ProxyRequestError(504, "连接请求超时，请稍后重试。") from exc
        raise ProxyRequestError(502, "连接暂不可用，请稍后重试。") from exc
    except OSError as exc:
        raise ProxyRequestError(502, "连接暂不可用，请稍后重试。") from exc

    with response:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > response_limit:
                    raise ProxyRequestError(502, "连接服务返回的数据过大。")
            except ValueError:
                pass
        body = response.read(response_limit + 1)
        if len(body) > response_limit:
            raise ProxyRequestError(502, "连接服务返回的数据过大。")
        return response.headers.get_content_type(), body


def _safe_error_detail(error: HTTPError) -> str:
    try:
        body = error.read(MAX_REQUEST_BODY_BYTES + 1)
    finally:
        error.close()
    if len(body) > MAX_REQUEST_BODY_BYTES:
        return "连接请求失败，请稍后重试。"
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "连接请求失败，请稍后重试。"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if not isinstance(detail, str) or not detail.strip():
        return "连接请求失败，请稍后重试。"
    public_detail = " ".join(detail.split())[:500]
    if "小栈还没有连上后台" in public_detail:
        return "小栈未连接，请等待重新连接后再试。"
    public_detail = public_detail.replace("电脑后台", "连接服务").replace("后台", "连接服务")
    return public_detail


def _sanitize_response(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if path == "/mobile-api/device/status":
        return _sanitize_device_status(payload)
    if path == "/mobile-api/chat":
        return _pick(
            payload,
            {"say", "emotion", "face", "motion", "route", "model", "latency_ms"},
        )
    if path == "/mobile-api/screen-programs":
        programs = payload.get("programs")
        return {
            "ok": payload.get("ok") is True,
            "programs": [
                _sanitize_screen_program(program)
                for program in programs
                if isinstance(program, dict) and program.get("id") in SCREEN_PROGRAM_IDS
            ]
            if isinstance(programs, list)
            else [],
            "device": _sanitize_device_status(payload.get("status")),
        }
    if path == "/mobile-api/screen-programs/control":
        return {
            "ok": payload.get("ok") is True,
            "action": "open" if payload.get("action") == "open" else None,
            "program": _sanitize_screen_program(payload.get("program")),
            "device": _sanitize_device_status(payload.get("device")),
        }
    if path == "/mobile-api/experience":
        return _sanitize_experience(payload)
    if path == "/mobile-api/memory":
        return _sanitize_memory(payload)
    if path in {"/mobile-api/memory/remove", "/mobile-api/memory/clear"}:
        return {
            "ok": payload.get("ok") is True,
            "changed": payload.get("changed") is True,
        }
    if path == "/mobile-api/music-library":
        return _sanitize_music_library(payload)
    if path == "/mobile-api/music-library/status":
        return {
            "ok": payload.get("ok") is True,
            "playback": _sanitize_music(payload.get("playback")),
            "device": _sanitize_device_status(payload.get("device")),
        }
    if path == "/mobile-api/music-library/play":
        return {
            "ok": payload.get("ok") is True,
            "track": _pick(payload.get("track"), {"id", "title"}),
            "device_file_play_supported": payload.get("device_file_play_supported") is True,
            "playback": _sanitize_music(payload.get("playback")),
        }
    if path == "/mobile-api/music-library/control":
        return {
            "ok": payload.get("ok") is True,
            "playback": _sanitize_music(payload.get("playback")),
        }
    if path == "/mobile-api/firmware/status":
        return _sanitize_firmware_status(payload)
    if path == "/mobile-api/assets/status":
        return _sanitize_firmware_status(payload)
    if path in {"/mobile-api/firmware/install", "/mobile-api/assets/install"}:
        return {
            "ok": payload.get("ok") is True,
            "update": _without(payload.get("update"), {"target_device_id"}),
            "device": _without(payload.get("device"), {"device_id"}),
        }
    if path in {
        "/mobile-api/update/status",
        "/mobile-api/update/check",
        "/mobile-api/update/prepare",
        "/mobile-api/update/install",
    }:
        return _sanitize_release_status(payload)
    if path == "/mobile-api/device/network/status":
        return {
            "ok": payload.get("ok") is True,
            "network": _pick(
                payload.get("network"),
                {"connected", "ssid", "rssi", "channel", "ip"},
            ),
        }
    if path == "/mobile-api/device/network/scan":
        return {
            "ok": payload.get("ok") is True,
            "wifi_scan": _sanitize_wifi_scan(payload.get("wifi_scan")),
        }
    if path == "/mobile-api/device/network/connect":
        state = payload.get("state")
        return {
            "ok": payload.get("ok") is True,
            "ssid": payload.get("ssid") if isinstance(payload.get("ssid"), str) else None,
            "state": state
            if state in {"accepted", "connecting", "waiting", "online", "failed"}
            else "connecting",
        }
    if path == "/mobile-api/device/camera/latest":
        return _pick(payload, {"available", "streaming", "age_seconds"})
    if path == "/mobile-api/device/brightness":
        return {
            "ok": payload.get("ok") is True,
            "brightness": payload.get("brightness"),
        }
    if path == "/mobile-api/device/factory-audio":
        if isinstance(payload.get("sounds"), list):
            return {
                "sounds": [
                    _pick(item, {"id", "label", "description"})
                    for item in payload["sounds"]
                    if isinstance(item, dict) and item.get("id") in FACTORY_AUDIO_IDS
                ]
            }
        return {
            "ok": payload.get("ok") is True,
            "sound": payload.get("sound") if payload.get("sound") in FACTORY_AUDIO_IDS else None,
            "label": payload.get("label") if isinstance(payload.get("label"), str) else None,
        }
    if path in {
        "/mobile-api/device/led",
        "/mobile-api/device/camera-preview/start",
        "/mobile-api/device/camera-preview/stop",
    }:
        return {"ok": payload.get("ok") is True}
    if path == "/mobile-api/device/macro":
        duration_ms = payload.get("duration_ms")
        return {
            "ok": payload.get("ok") is True,
            "accepted": payload.get("accepted") is True,
            "state": payload.get("state") if payload.get("state") in {"running", "completed", "failed"} else None,
            "preset": payload.get("preset"),
            "label": payload.get("label"),
            "duration_ms": duration_ms if isinstance(duration_ms, int) and not isinstance(duration_ms, bool) and 0 <= duration_ms <= 60000 else None,
        }
    return payload


def _sanitize_screen_program(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    return _pick(source, {"id", "name", "description", "icon"})


def _sanitize_experience(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "persona": _pick(payload.get("persona"), {"address_name", "style"}),
        "reaction": _pick(payload.get("reaction"), REACTION_FLAGS | {"liveliness_level"}),
        "privacy": _pick(payload.get("privacy"), PRIVACY_FLAGS),
        "voice": _pick(payload.get("voice"), {"profile"}),
    }


def _sanitize_memory(payload: dict[str, Any]) -> dict[str, list[str]]:
    return {
        key: [value for value in payload.get(key, []) if isinstance(value, str)]
        if isinstance(payload.get(key), list)
        else []
        for key in MEMORY_KEYS
    }


def _sanitize_wifi_scan(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    networks = source.get("networks")
    def clean_network(network: dict[str, Any]) -> dict[str, Any]:
        signal = network.get("signal")
        if not isinstance(signal, (int, float)) or isinstance(signal, bool):
            rssi = network.get("rssi")
            signal = max(0, min(100, 2 * (rssi + 100))) if isinstance(rssi, (int, float)) else None
        return {
            "ssid": network.get("ssid") if isinstance(network.get("ssid"), str) else "",
            "open": network.get("open") is True,
            "signal": round(signal) if isinstance(signal, (int, float)) else None,
        }
    return {
        "networks": [clean_network(network) for network in networks if isinstance(network, dict)]
        if isinstance(networks, list)
        else []
    }


def _sanitize_device_status(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "connected": source.get("connected") is True,
        "connected_seconds": source.get("connected_seconds"),
        "last_seen_seconds": source.get("last_seen_seconds"),
        "music": _sanitize_music(source.get("music")),
        "stage": _pick(source.get("stage"), {"state", "preset", "error"}),
        "camera": _pick(source.get("camera"), {"available", "streaming", "age_seconds"}),
        "head": _sanitize_head(source.get("head")),
        "network": _sanitize_network(source.get("network")),
    }


def _sanitize_head(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    result: dict[str, Any] = {}
    for key in ("yaw", "pitch", "speed", "updated_at"):
        value = source.get(key)
        if type(value) in {int, float} and math.isfinite(value):
            result[key] = value
    pose_source = source.get("source")
    if isinstance(pose_source, str) and 1 <= len(pose_source) <= 32 and all(
        character.isalnum() or character in {"_", "-"} for character in pose_source
    ):
        result["source"] = pose_source
    return result


def _sanitize_music(payload: Any) -> dict[str, Any]:
    return _pick(
        payload,
        {
            "state",
            "track_id",
            "title",
            "progress",
            "elapsed_seconds",
            "duration_seconds",
            "volume",
            "error",
        },
    )


def _sanitize_network(payload: Any) -> dict[str, Any]:
    return _pick(
        payload,
        {
            "available",
            "connected",
            "state",
            "ssid",
            "rssi",
            "channel",
            "ip",
            "firmwareVersion",
            "firmware_version",
            "otaSupported",
            "ota_supported",
            "assetsVersion",
            "assets_version",
            "assetsOtaSupported",
            "assets_ota_supported",
            "age_seconds",
        },
    )


def _sanitize_music_library(payload: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: value
        for key, value in payload.items()
        if key in {"ok", "count", "device_file_play_supported", "supported_extensions"}
    }
    tracks = payload.get("tracks")
    result["tracks"] = [
        _pick(track, {"id", "title", "filename", "extension", "bytes"})
        for track in tracks
        if isinstance(track, dict)
    ] if isinstance(tracks, list) else []
    return result


def _sanitize_firmware_status(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: payload.get(key) for key in ("ok", "limits") if key in payload}
    artifact = payload.get("artifact")
    result["artifact"] = _pick(artifact, {"id", "filename", "version", "size", "sha256", "createdAt"}) if artifact else None
    result["update"] = _without(payload.get("update"), {"target_device_id"})
    result["device"] = _without(payload.get("device"), {"device_id"})
    result["routes"] = _pick(payload.get("routes"), {"lan_available", "remote_available"})
    return result


def _sanitize_release_status(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_states = {
        "unavailable",
        "idle",
        "checking",
        "available",
        "downloading",
        "staged",
        "installing",
        "completed",
        "failed",
        "rolling_back",
        "rolled_back",
    }
    state = payload.get("state")
    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    return {
        "ok": payload.get("ok") is True,
        "configured": payload.get("configured") is True,
        "state": state if state in allowed_states else "failed",
        "release_id": payload.get("release_id")
        if isinstance(payload.get("release_id"), str)
        else None,
        "release_version": payload.get("release_version")
        if isinstance(payload.get("release_version"), str)
        else None,
        "message": payload.get("message") if isinstance(payload.get("message"), str) else "",
        "components": {
            name: _pick(
                components.get(name),
                {"current_version", "target_version", "state", "progress"},
            )
            for name in ("computer", "mobile", "firmware", "assets")
        },
    }


def _pick(payload: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if key in allowed}


def _without(payload: Any, excluded: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if key not in excluded}
