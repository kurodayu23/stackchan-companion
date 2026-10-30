# -*- coding: utf-8 -*-
"""http_api.py —— 手机端 ↔ 云后端 的 HTTP 适配层（`/gui/*`）

为什么需要它
------------
`server/` 原本是**纯 WebSocket 协议栈**（设备 / App 通过 `0x03` / `0x14` 帧对话），
而手机端（`prototype/mobile/`）走的是 HTTP `/mobile-api/*` ⇒ 代理再转 `/gui/*`。
⇒ 两边**没有交汇点** ⇒ 作品集没法独立运行（这就是 **Q27**）。

本模块把手机端要的 `/gui/*` 补齐，分两类，**边界写死、不假装成功**：

| 类别 | 含义 | 行为 |
|---|---|---|
| ``owner="mobile"`` | **本仓真实现** | 真跑（对话走完整 LLM→TTS→韵律→关键帧 闭环） |
| ``owner="desktop"`` | **桌面端职责**（固件 / 资源 / OTA / 配网 / 工厂音色） | 显式返回 **501 + owner=desktop**，手机端拿得到明确答复而不是 404 挂死 |

设备侧动作（舵机 / 灯 / 亮度）在本层**只回执**：真正的下发仍走 WS 的 `0x14` 关键帧通道
（见 `docs/research/53` §5：0x14 = 脸 + 脖 + 双 RGB 灯，且绕过 modify lock）。

路由表是**模块级常量** ⇒ 可以被 `tools/check_mobile_app.py` 静态读取，
从而机器守住「**手机端调用的每条路径都必须在本仓后端有对应路由**」（MO-16）。

用法
----
    py -3.12 server/http_api.py --port 17865        # 起 HTTP 适配层
    py -3.12 server/http_api.py --routes             # 只打印路由表

退出码：0 = 正常退出。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.mobile_contract import (  # noqa: E402
    DEVICE_STATUS_SHAPE,
    MEMORY_CATEGORIES,
    SCREEN_PROGRAMS,
    merge_shape,
    memory_payload,
)
from server.stackchan_ai.config import Config  # noqa: E402
from server.stackchan_ai.memory import PrivacyError, ProfileStore  # noqa: E402
from server.stackchan_ai.server import StackChanServer  # noqa: E402

DEFAULT_PORT = 17865

#: 手机端默认档案名（人格档案，永不入库 ⇒ 落在 private/）
DEFAULT_PROFILE = "default"


@dataclass
class DeviceState:
    """设备状态（本仓后端的**单机桩**，真机接入后由 WS 事件覆盖）。

    ⚠️ 诚实边界：本层不驱动真实舵机。`head / brightness / volume / led`
    只更新内存状态并回执，**真实下发走 0x14 关键帧通道**。
    """

    mac: str = "68ee8fd73668"
    connected: bool = False
    battery: int = 86
    charging: bool = False
    wifi: int = 3
    yaw: int = 0
    pitch: int = 45
    brightness: int = 80
    volume: int = 60
    led_on: bool = True
    camera_preview: bool = False

    def snapshot(self) -> Dict[str, Any]:
        """设备状态的**手机端形状**（契约见 ``server/mobile_contract.py``）。

        ⚠️ 值是诚实占位：本仓后端此刻**没有连上真机** ⇒ ``connected`` 恒为 False，
        ``network`` 全空。真实设备上线后由 WS 事件覆盖这里的值。
        """
        return merge_shape(DEVICE_STATUS_SHAPE, {
            "head": {"yaw": self.yaw, "pitch": self.pitch},
            "music": {"volume": self.volume},
            "camera": {"streaming": self.camera_preview},
        })


@dataclass
class Route:
    """一条 `/gui/*` 路由。"""

    method: str
    path: str
    owner: str                 # "mobile" = 本仓真实现；"desktop" = 桌面端职责
    summary: str
    handler: Optional[Callable[["MobileBackend", Dict[str, Any]], Tuple[int, Any]]] = None

    @property
    def implemented(self) -> bool:
        return self.handler is not None


class MobileBackend:
    """手机端 HTTP 后端。

    Args:
        config: 配置快照（API Key 只从环境变量读）
        server: 可选；复用已有 `StackChanServer`（对话要用）
        store: 可选；关系档案存储
    """

    def __init__(self, config: Optional[Config] = None,
                 server: Optional[StackChanServer] = None,
                 store: Optional[ProfileStore] = None) -> None:
        self.config = config or Config.from_env()
        self.server = server or StackChanServer(self.config, verbose=False)
        self.store = store or ProfileStore(self.config.private_dir)
        self.device = DeviceState()
        self._lock = threading.Lock()

    # ── 对话 ───────────────────────────────────────────────────────────
    def handle_chat(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        """真跑完整闭环：LLM → TTS → 韵律 → 42 参数 → PCHIP → 0x14 关键帧。

        ⚠️ 响应的字段名必须是**手机端契约**（``server/mobile_contract.py``）：
        手机端读 ``say``，不是 ``reply`` ⇒ 字段名对不上时前端会静默显示
        「小栈这次没有返回内容」。
        """
        text = str(body.get("text") or body.get("message") or "").strip()
        if not text:
            return 400, {"detail": "text is required"}
        profile = str(body.get("profile") or DEFAULT_PROFILE)
        started = time.monotonic()
        try:
            outcome = self.server.run_pipeline(text)
        except Exception as exc:  # noqa: BLE001 - 上游 provider 任何异常都要变成可读答复
            return 502, {"detail": "pipeline failed: %s" % (exc.__class__.__name__)}
        elapsed_ms = int((time.monotonic() - started) * 1000)
        turn = outcome.get("text")
        if isinstance(turn, str):
            reply = turn
        else:
            reply = getattr(turn, "text", "") if turn is not None else ""
        result = outcome.get("result") or {}
        keyframes = outcome.get("keyframes")
        provider = getattr(self.server, "provider", None)
        return 200, {
            # ★ 手机端读的字段（契约里 non_empty）
            "say": reply,
            "emotion": getattr(self.server.persona, "emotion", "Happy"),
            "model": str(getattr(provider, "name", "") or "unknown"),
            "latency_ms": elapsed_ms,
            # 下面这些是给桌面端 / 调试看的，手机端净化层不会转发
            "reply": reply,
            "emotion_source": "persona_baseline",
            "profile": profile,
            "keyframes": len(keyframes) if hasattr(keyframes, "__len__") else 0,
            "audio_samples": len(getattr(outcome.get("audio"), "pcm", b"")) // 2,
            "result_keys": sorted(result) if isinstance(result, dict) else [],
        }

    # ── 记忆 ───────────────────────────────────────────────────────────
    def handle_memory_list(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        name = str(body.get("profile") or DEFAULT_PROFILE)
        try:
            profiles = self.store.list_profiles()
            profile = self.store.load(name) if name in profiles else {}
            events = self.store.read_events(name, limit=50)
        except PrivacyError as exc:
            return 400, {"detail": str(exc)}
        except OSError:
            profiles, profile, events = [], {}, []
        payload = memory_payload(profile if isinstance(profile, dict) else {}, events)
        payload.update({
            "ok": True,
            "profiles": profiles,
            "active": name if name in profiles else (profiles[0] if profiles else None),
            "events": events,
        })
        return 200, payload

    def handle_memory_remove(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        name = str(body.get("profile") or DEFAULT_PROFILE)
        key = str(body.get("key") or "")
        value = str(body.get("value") or "")
        try:
            profile = self.store.load(name)
            changed = False
            if key and value:
                items = profile.get(key)
                if isinstance(items, list) and value in items:
                    profile[key] = [x for x in items if x != value]
                    self.store.save(name, profile)
                    changed = True
            elif key:
                items = profile.get(key)
                if isinstance(items, list) and items:
                    profile[key] = []
                    self.store.save(name, profile)
                    changed = True
            else:
                changed = self.store.delete(name)
        except PrivacyError as exc:
            return 400, {"detail": str(exc)}
        return 200, {"ok": True, "changed": changed, "profile": name}

    def handle_memory_clear(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        name = str(body.get("profile") or DEFAULT_PROFILE)
        key = str(body.get("key") or "")
        try:
            if key:
                if key not in MEMORY_CATEGORIES:
                    return 400, {"detail": "unknown memory category"}
                profile = self.store.load(name)
                changed = bool(profile.get(key))
                if changed:
                    profile[key] = []
                    self.store.save(name, profile)
            else:
                changed = self.store.delete(name)
        except PrivacyError as exc:
            return 400, {"detail": str(exc)}
        return 200, {"ok": True, "changed": changed, "profile": name}

    # ── 设备 ───────────────────────────────────────────────────────────
    def handle_device_status(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        return 200, self.device.snapshot()

    def handle_device_head(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        with self._lock:
            if "yaw" in body:
                self.device.yaw = int(body["yaw"])
            if "pitch" in body:
                self.device.pitch = int(body["pitch"])
            snap = self.device.snapshot()
        return 200, {"ok": True, "yaw": snap["head"]["yaw"], "pitch": snap["head"]["pitch"],
                     "speed": snap["head"]["speed"],
                     "applied_to": "state-only",
                     "note": "真实下发走 0x14 关键帧通道（本层只回执）"}

    def handle_device_brightness(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        value = body.get("brightness")
        if type(value) is not int or not 1 <= value <= 100:
            return 400, {"detail": "brightness must be between 1 and 100"}
        with self._lock:
            self.device.brightness = value
        return 200, {"ok": True, "brightness": value, "applied_to": "state-only",
                     "note": "真实下发走 0x14 关键帧通道（本层只回执）"}

    def handle_device_volume(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        value = body.get("volume")
        if type(value) is not int or not 0 <= value <= 100:
            return 400, {"detail": "volume must be between 0 and 100"}
        with self._lock:
            self.device.volume = value
        return 200, {"ok": True, "volume": value, "applied_to": "state-only",
                     "note": "真实下发走 0x14 关键帧通道（本层只回执）"}

    def handle_device_led(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        rgb: Dict[str, int] = {}
        for key in ("red", "green", "blue"):
            value = body.get(key)
            if type(value) is not int or not 0 <= value <= 168:
                return 400, {"detail": "%s must be between 0 and 168" % key}
            rgb[key] = value
        with self._lock:
            self.device.led_on = any(rgb.values())
        return 200, dict({"ok": True, "applied_to": "state-only",
                          "note": "真实下发走 0x14 关键帧通道（本层只回执）"}, **rgb)

    # ── 屏幕程序 ───────────────────────────────────────────────────────
    def handle_screen_programs(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        return 200, {"ok": True,
                     "programs": [dict(p) for p in SCREEN_PROGRAMS],
                     "status": self.device.snapshot()}

    def handle_screen_programs_control(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        target = str(body.get("program_id") or body.get("id") or body.get("program") or "")
        program = next((p for p in SCREEN_PROGRAMS if p["id"] == target), None)
        if program is None:
            return 404, {"detail": "unknown program",
                         "available": [p["id"] for p in SCREEN_PROGRAMS]}
        return 200, {"ok": True, "action": "open",
                     "program": {"id": program["id"], "name": program["name"],
                                 "description": program["description"],
                                 "icon": program["icon"]},
                     "device": self.device.snapshot()}

    # ── 摄像头 ─────────────────────────────────────────────────────────
    def handle_camera_start(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        with self._lock:
            self.device.camera_preview = True
        return 200, {"ok": True, "preview": True,
                     "note": "本仓后端不接真实摄像头（真机画面由设备侧提供）"}

    def handle_camera_stop(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        with self._lock:
            self.device.camera_preview = False
        return 200, {"ok": True, "preview": False}

    def handle_camera_frame(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        # 没有真实画面 ⇒ 明确说没有，而不是给一张假图骗人。
        return 404, {"detail": "no camera frame (no device connected)",
                     "preview": self.device.camera_preview}

    # ── 桌面端职责 ─────────────────────────────────────────────────────
    def handle_desktop_only(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        return 501, {"detail": "this capability belongs to the desktop console",
                     "owner": "desktop"}


# ---------------------------------------------------------------------------
# 路由表（模块级常量 ⇒ 可被门禁静态读取）
# ---------------------------------------------------------------------------
def build_routes() -> List[Route]:
    """列出手机端要的**全部** `/gui/*` 路由。

    ★ 覆盖范围由 `prototype/mobile/` 的实际调用决定 ⇒ 门禁 MO-16 会核对。
    """
    return [
        # ── 核心：真实现 ───────────────────────────────────────────────
        Route("POST", "/gui/mobile-chat", "mobile", "对话（真跑 LLM→TTS→韵律→关键帧）",
              MobileBackend.handle_chat),
        Route("GET", "/gui/device/status", "mobile", "设备状态", MobileBackend.handle_device_status),
        Route("GET", "/gui/memory", "mobile", "记忆档案与事件", MobileBackend.handle_memory_list),
        Route("POST", "/gui/memory/remove", "mobile", "删除一条记忆",
              MobileBackend.handle_memory_remove),
        Route("POST", "/gui/memory/clear", "mobile", "清空记忆", MobileBackend.handle_memory_clear),
        Route("GET", "/gui/screen-programs", "mobile", "屏幕程序列表",
              MobileBackend.handle_screen_programs),
        Route("POST", "/gui/screen-programs/control", "mobile", "启动屏幕程序",
              MobileBackend.handle_screen_programs_control),
        Route("POST", "/gui/device/head", "mobile", "头部朝向（yaw/pitch）",
              MobileBackend.handle_device_head),
        Route("POST", "/gui/device/camera-preview/start", "mobile", "开启摄像头预览",
              MobileBackend.handle_camera_start),
        Route("POST", "/gui/device/camera-preview/stop", "mobile", "关闭摄像头预览",
              MobileBackend.handle_camera_stop),
        Route("GET", "/gui/device/camera/latest", "mobile", "摄像头元信息（无画面）",
              MobileBackend.handle_camera_frame),
        Route("GET", "/gui/device/camera/latest.jpg", "mobile", "摄像头单帧",
              MobileBackend.handle_camera_frame),

        # ── 设备参数：真实现（只回执）────────────────────────────────────
        Route("POST", "/gui/device/brightness", "mobile", "屏幕亮度",
              MobileBackend.handle_device_brightness),
        Route("POST", "/gui/device/volume", "mobile", "音量",
              MobileBackend.handle_device_volume),
        Route("POST", "/gui/device/led", "mobile", "氛围灯颜色",
              MobileBackend.handle_device_led),

        # ── 桌面端职责：显式 501 ─────────────────────────────────────────
        Route("GET", "/gui/experience", "desktop", "体验设置（桌面端）"),
        Route("POST", "/gui/experience", "desktop", "写体验设置（桌面端）"),
        Route("GET", "/gui/firmware/status", "desktop", "固件状态（桌面端）"),
        Route("POST", "/gui/firmware/install", "desktop", "刷固件（桌面端）"),
        Route("GET", "/gui/assets/status", "desktop", "资源包状态（桌面端）"),
        Route("POST", "/gui/assets/install", "desktop", "装资源包（桌面端）"),
        Route("GET", "/gui/update/status", "desktop", "升级状态（桌面端）"),
        Route("POST", "/gui/update/check", "desktop", "检查升级（桌面端）"),
        Route("POST", "/gui/update/prepare", "desktop", "准备升级（桌面端）"),
        Route("POST", "/gui/update/install", "desktop", "执行升级（桌面端）"),
        Route("GET", "/gui/music-library", "desktop", "音乐库（桌面端）"),
        Route("GET", "/gui/music-library/status", "desktop", "音乐库状态（桌面端）"),
        Route("POST", "/gui/music-library/play", "desktop", "播放音乐（桌面端）"),
        Route("POST", "/gui/music-library/control", "desktop", "音乐控制（桌面端）"),
        Route("POST", "/gui/device/network/status", "desktop", "配网状态（桌面端）"),
        Route("POST", "/gui/device/network/scan", "desktop", "扫描 Wi-Fi（桌面端）"),
        Route("POST", "/gui/device/network/connect", "desktop", "连接 Wi-Fi（桌面端）"),
        Route("GET", "/gui/device/network/key", "desktop", "配网密钥（桌面端）"),
        Route("GET", "/gui/device/factory-voices", "desktop", "工厂音色（桌面端）"),
        Route("GET", "/gui/device/factory-audio", "desktop", "工厂音频（桌面端）"),
        Route("POST", "/gui/device/factory-audio", "desktop", "播放工厂音频（桌面端）"),
        Route("POST", "/gui/device/macro", "desktop", "宏指令（桌面端）"),
    ]


ROUTES: List[Route] = build_routes()
ROUTE_INDEX: Dict[Tuple[str, str], Route] = {(r.method, r.path): r for r in ROUTES}


def route_table() -> Dict[str, Any]:
    """路由表的自描述（手机端 / 工具都能查）。"""
    return {
        "count": len(ROUTES),
        "implemented": sum(1 for r in ROUTES if r.implemented),
        "desktop_only": sum(1 for r in ROUTES if not r.implemented),
        "routes": [
            {"method": r.method, "path": r.path, "owner": r.owner,
             "summary": r.summary, "implemented": r.implemented}
            for r in ROUTES
        ],
    }


# ---------------------------------------------------------------------------
# HTTP 服务
# ---------------------------------------------------------------------------
class GuiHandler(BaseHTTPRequestHandler):
    backend: MobileBackend = None  # type: ignore[assignment]

    server_version = "StackChanGui/1.0"

    def log_message(self, fmt, *args):  # noqa: A003 - 静默默认访问日志
        pass

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _send(self, status: int, payload: Any, content_type: str = "application/json") -> None:
        if isinstance(payload, (bytes, bytearray)):
            body = bytes(payload)
        else:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, method: str) -> None:
        path = urlsplit(self.path).path
        if path == "/gui/routes" and method == "GET":
            self._send(200, route_table())
            return
        if path == "/gui/health" and method == "GET":
            self._send(200, {"ok": True, "service": "stackchan-backend-http"})
            return
        route = ROUTE_INDEX.get((method, path))
        if route is None:
            self._send(404, {"detail": "no such route", "method": method, "path": path})
            return
        if route.handler is None:
            self._send(501, {"detail": "this capability belongs to the desktop console",
                             "owner": "desktop", "path": path})
            return
        body = self._read_body()
        try:
            status, payload = route.handler(self.backend, body)
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"detail": "handler error: %s" % exc.__class__.__name__})
            return
        self._send(status, payload)

    def do_GET(self):  # noqa: N802
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")


def serve(config: Optional[Config] = None, host: str = "127.0.0.1",
          port: int = DEFAULT_PORT, backend: Optional[MobileBackend] = None) -> ThreadingHTTPServer:
    """起 HTTP 适配层。返回已经绑定端口的 server（调用方负责 shutdown）。"""
    backend = backend or MobileBackend(config)
    handler = type("BoundGuiHandler", (GuiHandler,), {"backend": backend})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="StackChan 后端 HTTP 适配层（/gui/*）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--routes", action="store_true", help="只打印路由表")
    ap.add_argument("--provider", default=None, choices=["auto", "minimax", "stub"])
    args = ap.parse_args(argv)

    if args.routes:
        table = route_table()
        print("路由 %d 条：实现 %d / 桌面端职责 %d" %
              (table["count"], table["implemented"], table["desktop_only"]))
        for r in table["routes"]:
            mark = "OK " if r["implemented"] else "501"
            print("  [%s] %-6s %-38s %s" % (mark, r["method"], r["path"], r["summary"]))
        return 0

    config = Config.from_env()
    if args.provider:
        config.provider = args.provider
    httpd = serve(config, args.host, args.port)
    print("StackChan backend HTTP: http://%s:%d/gui/routes" % (args.host, args.port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[http_api] bye")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
