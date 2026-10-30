# -*- coding: utf-8 -*-
"""mobile_contract.py —— 手机端可见的响应契约（唯一真源）。

为什么需要它
------------
手机端（``prototype/mobile/``）读的是 ``/mobile-api/*``，代理（``mobile_proxy.py``）
的净化层用 ``_pick()`` **只保留上游已经存在的键**：

    def _pick(payload, allowed):
        return {key: value for key, value in payload.items() if key in allowed}

⇒ 后端少给一个字段，前端就拿到 ``undefined``，
页面**静默显示错内容**（``say`` 缺失 ⇒ 聊天页报「小栈这次没有返回内容」；
``network.ssid`` 缺失 ⇒ 状态页永远显示「未上报」），**全程没有任何报错**。

本模块把「手机端读到哪些字段」写成**机器可查的契约**，
由 ``tools/check_mobile_contract.py`` 同时核对三方：

1. **本仓后端**（``server/http_api.py``）的真实响应
2. **代理净化层**（``prototype/mobile/mobile_proxy.py``）放行的字段
3. **手机端 JS**（``prototype/mobile/*.js``）真正读取的字段

三处对不齐 ⇒ 门禁变红。

字段路径
--------
* ``fields`` —— **手机端可见**（过完代理净化层之后仍然存在）的字段路径
* ``backend_fields`` —— 后端**必须产出**（净化之前）的字段路径
* ``non_empty`` —— ``fields`` 里必须**非空**的字段（空值等于没给）
* ``js_files`` —— 会读这条路由的手机端 JS 文件（用于「JS 读到的字段必须在契约里」）

路径支持 ``a.b`` 与 ``items[].b``（数组元素）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class RouteContract:
    """一条手机端路由的响应契约。"""

    mobile_method: str
    mobile_path: str
    backend_method: str
    backend_path: str
    owner: str                      # "mobile" = 本仓真实现；"desktop" = 桌面端职责
    fields: Tuple[str, ...] = ()           # 净化后仍须存在的字段路径
    backend_fields: Tuple[str, ...] = ()   # 后端须产出的字段路径
    non_empty: Tuple[str, ...] = ()        # 必须非空的字段路径
    js_files: Tuple[str, ...] = ()         # 读这条路由的手机端 JS
    desktop_only: bool = False             # True ⇒ 只要求显式 501，不校验字段

    @property
    def mobile_key(self) -> str:
        return "%s %s" % (self.mobile_method, self.mobile_path)

    @property
    def backend_key(self) -> str:
        return "%s %s" % (self.backend_method, self.backend_path)


#: 记忆分类（必须与 ``mobile_proxy.MEMORY_KEYS`` 一致，门禁 MC-06 会核对）
MEMORY_CATEGORIES: Tuple[str, ...] = (
    "likes",
    "dislikes",
    "goals",
    "important",
    "relationship",
    "giver",
    "temporary",
    "conversation_notes",
    "insights",
)

#: 设备屏幕上的 8 个「程序」（必须与 ``mobile_proxy.SCREEN_PROGRAM_IDS`` 一致，门禁 MC-06 会核对）
SCREEN_PROGRAM_IDS: Tuple[str, ...] = (
    "chat",
    "quote",
    "album",
    "mood",
    "pomodoro",
    "fortune",
    "game",
    "settings",
)

#: 屏幕程序目录（``id`` / ``name`` / ``description`` / ``icon`` 会被代理透传给手机端）
SCREEN_PROGRAMS: Tuple[Dict[str, Any], ...] = (
    {"id": "chat", "name": "AI Chat", "description": "和小栈自然对话", "icon": "chat",
     "emotion": "Neutral", "duration_s": 0},
    {"id": "quote", "name": "小栈悄悄话", "description": "生日彩蛋与温柔留言", "icon": "letter",
     "emotion": "Happy", "duration_s": 0},
    {"id": "album", "name": "相册", "description": "翻看依婵的照片", "icon": "album",
     "emotion": "Happy", "duration_s": 0},
    {"id": "mood", "name": "心情日记", "description": "记录今天的心情", "icon": "mood",
     "emotion": "Neutral", "duration_s": 0},
    {"id": "pomodoro", "name": "番茄钟", "description": "开始一段专注时间", "icon": "focus",
     "emotion": "Focus", "duration_s": 1500},
    {"id": "fortune", "name": "今日运势", "description": "抽一张今天的小运势", "icon": "fortune",
     "emotion": "Happy", "duration_s": 6},
    {"id": "game", "name": "游戏专区", "description": "三款完整音效游戏", "icon": "game",
     "emotion": "Happy", "duration_s": 0},
    {"id": "settings", "name": "系统设置", "description": "网络、亮度与设备信息", "icon": "settings",
     "emotion": "Neutral", "duration_s": 0},
)

#: 设备状态响应的**形状模板**（值是「未连接」时的诚实占位，不是假数据）
#:
#: ⚠️ 只给形状，不给假状态：``connected`` 恒为 ``False``，
#:    因为本仓后端此刻并没有连上真机（见 ``docs/research/98``）。
DEVICE_STATUS_SHAPE: Dict[str, Any] = {
    "connected": False,
    "connected_seconds": None,
    "last_seen_seconds": None,
    "music": {
        "state": "idle",
        "track_id": None,
        "title": None,
        "progress": 0.0,
        "elapsed_seconds": 0.0,
        "duration_seconds": 0.0,
        "volume": 60,
        "error": None,
    },
    "stage": {"state": "idle", "preset": None, "error": None},
    "camera": {"available": False, "streaming": False, "age_seconds": None},
    "head": {"yaw": 0, "pitch": 45, "speed": 180, "updated_at": None, "source": "commanded"},
    "network": {
        "available": False,
        "connected": False,
        "state": "offline",
        "ssid": None,
        "rssi": None,
        "channel": None,
        "ip": None,
        "firmwareVersion": None,
        "firmware_version": None,
        "otaSupported": False,
        "ota_supported": False,
        "assetsVersion": None,
        "assets_version": None,
        "assetsOtaSupported": False,
        "assets_ota_supported": False,
        "age_seconds": None,
    },
}

#: 全部契约（**唯一真源**）
CONTRACTS: Tuple[RouteContract, ...] = (
    # ── 对话：手机端主界面 ───────────────────────────────────────────────
    RouteContract(
        "POST", "/mobile-api/chat", "POST", "/gui/mobile-chat", "mobile",
        fields=("say", "model"),
        backend_fields=("say", "emotion", "model", "latency_ms",
                        "keyframes", "audio_samples"),
        non_empty=("say",),
        js_files=("chat.js",),
    ),
    # ── 设备状态：首页 + 设置页 ─────────────────────────────────────────
    RouteContract(
        "GET", "/mobile-api/device/status", "GET", "/gui/device/status", "mobile",
        fields=(
            "connected", "connected_seconds", "last_seen_seconds",
            "music.state", "music.title", "music.volume",
            "stage.state",
            "camera.available", "camera.streaming",
            "network.connected", "network.ssid", "network.ip", "network.rssi",
            "network.channel", "network.age_seconds",
            "network.firmware_version", "network.ota_supported",
            "network.assets_ota_supported",
        ),
        backend_fields=("connected", "network", "music", "stage", "camera", "head"),
        js_files=("app.js", "settings.js", "actions_music.js"),
    ),
    # ── 屏幕程序：设备屏幕上的 8 个 App ─────────────────────────────────
    RouteContract(
        "GET", "/mobile-api/screen-programs", "GET", "/gui/screen-programs", "mobile",
        fields=("programs[].id", "programs[].name", "programs[].description",
                "device.connected"),
        backend_fields=("ok", "programs", "status"),
        js_files=("screen_programs.js",),
    ),
    RouteContract(
        "POST", "/mobile-api/screen-programs/control", "POST", "/gui/screen-programs/control",
        "mobile",
        fields=("program.name",),
        backend_fields=("ok", "action", "program", "device"),
        js_files=("screen_programs.js",),
    ),
    # ── 记忆 ────────────────────────────────────────────────────────────
    RouteContract(
        "GET", "/mobile-api/memory", "GET", "/gui/memory", "mobile",
        fields=MEMORY_CATEGORIES,
        backend_fields=("ok", "profiles", "active", "events"),
        js_files=("settings.js",),
    ),
    RouteContract(
        "POST", "/mobile-api/memory/remove", "POST", "/gui/memory/remove", "mobile",
        fields=("changed",),
        backend_fields=("ok", "changed"),
        js_files=("settings.js",),
    ),
    RouteContract(
        "POST", "/mobile-api/memory/clear", "POST", "/gui/memory/clear", "mobile",
        fields=("changed",),
        backend_fields=("ok", "changed"),
        js_files=("settings.js",),
    ),
    # ── 设备参数（只回执，真实下发走 0x14 关键帧通道）────────────────────
    RouteContract(
        "POST", "/mobile-api/device/head", "POST", "/gui/device/head", "mobile",
        fields=(),
        backend_fields=("ok", "yaw", "pitch"),
        js_files=("remote_control.js",),
    ),
    RouteContract(
        "POST", "/mobile-api/device/brightness", "POST", "/gui/device/brightness", "mobile",
        fields=("brightness", "ok"),
        backend_fields=("ok", "brightness"),
        js_files=("actions_music.js", "settings.js"),
    ),
    RouteContract(
        "POST", "/mobile-api/device/volume", "POST", "/gui/device/volume", "mobile",
        fields=("volume",),
        backend_fields=("ok", "volume"),
        js_files=("actions_music.js",),
    ),
    RouteContract(
        "POST", "/mobile-api/device/led", "POST", "/gui/device/led", "mobile",
        fields=("ok",),
        backend_fields=("ok",),
        js_files=("settings.js",),
    ),
    # ── 摄像头 ──────────────────────────────────────────────────────────
    RouteContract(
        "POST", "/mobile-api/device/camera-preview/start", "POST",
        "/gui/device/camera-preview/start", "mobile",
        fields=("ok",),
        backend_fields=("ok", "preview"),
        js_files=("settings.js", "camera_panel.js"),
    ),
    RouteContract(
        "POST", "/mobile-api/device/camera-preview/stop", "POST",
        "/gui/device/camera-preview/stop", "mobile",
        fields=("ok",),
        backend_fields=("ok", "preview"),
        js_files=("settings.js", "camera_panel.js"),
    ),
    RouteContract(
        "GET", "/mobile-api/device/camera/latest", "GET", "/gui/device/camera/latest",
        "mobile",
        fields=(),
        backend_fields=("detail",),
        js_files=("camera_panel.js",),
    ),
    # ── 桌面端职责：显式 501，不校验字段 ───────────────────────────────
    # ⚠️ 这些路由手机端**确实会调**（固件页 / 更新页 / 网络页 / 音色页），
    #    本仓暂不实现 ⇒ 后端回 501 + owner=desktop。
    #    但契约仍然要写清楚「等桌面端迁过来之后应该长什么样」，
    #    这样 MC-07（前端读到的字段）才不会漏。
    RouteContract(
        "GET", "/mobile-api/firmware/status", "GET", "/gui/firmware/status", "desktop",
        fields=("update.state", "update.progress", "device.current_version",
                "device.connected", "device.ota_supported",
                "artifact.id", "artifact.version"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "GET", "/mobile-api/assets/status", "GET", "/gui/assets/status", "desktop",
        fields=("update.state", "update.progress", "device.current_version",
                "device.connected", "device.ota_supported",
                "artifact.id", "artifact.version"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/firmware/install", "POST", "/gui/firmware/install", "desktop",
        fields=("ok", "update.state"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/assets/install", "POST", "/gui/assets/install", "desktop",
        fields=("ok", "update.state"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "GET", "/mobile-api/update/status", "GET", "/gui/update/status", "desktop",
        fields=("state", "message", "release_id", "release_version",
                "components[].current_version", "components[].target_version",
                "components[].state", "components[].progress"),
        js_files=("update.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/update/check", "POST", "/gui/update/check", "desktop",
        fields=(),
        js_files=("update.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/update/prepare", "POST", "/gui/update/prepare", "desktop",
        fields=(),
        js_files=("update.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/update/install", "POST", "/gui/update/install", "desktop",
        fields=(),
        js_files=("update.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/device/network/status", "POST", "/gui/device/network/status",
        "desktop",
        fields=("network.connected", "network.ssid"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/device/network/scan", "POST", "/gui/device/network/scan",
        "desktop",
        fields=("ok", "wifi_scan.networks[].ssid", "wifi_scan.networks[].signal",
                "wifi_scan.networks[].open"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/device/network/connect", "POST", "/gui/device/network/connect",
        "desktop",
        fields=("ok", "ssid", "state"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "GET", "/mobile-api/device/network/key", "GET", "/gui/device/network/key", "desktop",
        fields=("algorithm", "key_id", "public_key"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "GET", "/mobile-api/device/factory-voices", "GET", "/gui/device/factory-voices",
        "desktop",
        fields=("voices[].id", "voices[].label", "select_supported"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "GET", "/mobile-api/device/factory-audio", "GET", "/gui/device/factory-audio",
        "desktop",
        fields=("sounds[].id", "sounds[].label"),
        js_files=("actions_music.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/device/factory-audio", "POST", "/gui/device/factory-audio",
        "desktop",
        fields=("ok", "label"),
        js_files=("actions_music.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/device/macro", "POST", "/gui/device/macro", "desktop",
        fields=("ok", "label", "state", "duration_ms"),
        js_files=("actions_music.js",),
        desktop_only=True,
    ),
    RouteContract(
        "GET", "/mobile-api/experience", "GET", "/gui/experience", "desktop",
        fields=("persona", "reaction", "privacy", "voice.profile"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
    RouteContract(
        "POST", "/mobile-api/experience", "POST", "/gui/experience", "desktop",
        fields=("persona", "reaction", "privacy"),
        js_files=("settings.js",),
        desktop_only=True,
    ),
)

CONTRACT_BY_MOBILE: Dict[str, RouteContract] = {c.mobile_key: c for c in CONTRACTS}
CONTRACT_BY_BACKEND: Dict[str, RouteContract] = {c.backend_key: c for c in CONTRACTS}


# ---------------------------------------------------------------------------
# 路径解析
# ---------------------------------------------------------------------------
def resolve_path(payload: Any, path: str) -> Tuple[bool, Any]:
    """按契约路径取值，返回 ``(是否存在, 值)``。

    支持 ``a.b`` 与 ``items[].b``。数组元素只要**至少有一个**带该子字段就算存在。
    """
    current: List[Any] = [payload]
    for segment in path.split("."):
        is_array_step = segment.endswith("[]")
        key = segment[:-2] if is_array_step else segment
        nxt: List[Any] = []
        for item in current:
            if is_array_step:
                # ``programs[]`` ⇒ 取 programs 这个数组，再把数组元素摊平
                if isinstance(item, dict) and isinstance(item.get(key), list):
                    nxt.extend(x for x in item[key] if isinstance(x, dict))
                continue
            if isinstance(item, dict) and key in item:
                nxt.append(item[key])
        if not nxt:
            return False, None
        current = nxt
    return True, current[0]


def path_exists(payload: Any, path: str) -> bool:
    """契约路径是否存在（值可以是 ``None``）。"""
    found, _ = resolve_path(payload, path)
    return found


def path_non_empty(payload: Any, path: str) -> bool:
    """契约路径是否存在**且非空**（空串 / 空列表 / ``None`` 都算空）。"""
    found, value = resolve_path(payload, path)
    if not found or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def merge_shape(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """把 ``override`` 叠到形状模板 ``base`` 上（深合并，返回新对象）。"""
    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = merge_shape(current, value)
        else:
            result[key] = value
    return result


def memory_payload(profile: Dict[str, Any], events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """把档案 + 事件投影成手机端的「9 个分类」。

    ⚠️ 档案本来就允许用这 9 个分类做键（见 ``server/tests/test_memory.py``），
    这里只是原样透传 + 把对话事件归到 ``conversation_notes``。
    """
    result: Dict[str, Any] = {key: [] for key in MEMORY_CATEGORIES}
    for key in MEMORY_CATEGORIES:
        value = profile.get(key)
        if isinstance(value, list):
            result[key] = [str(x) for x in value if isinstance(x, (str, int, float))]
    notes = list(result["conversation_notes"])
    for event in events:
        if not isinstance(event, dict):
            continue
        user = str(event.get("user") or "").strip()
        reply = str(event.get("reply") or "").strip()
        if user or reply:
            notes.append("%s｜%s" % (user, reply) if user and reply else (user or reply))
    result["conversation_notes"] = notes[-50:]
    return result


def conversation_note(event: Dict[str, Any]) -> Optional[str]:
    """从一条事件里抽出一句话摘要（给 ``conversation_notes`` 用）。"""
    if not isinstance(event, dict):
        return None
    user = str(event.get("user") or "").strip()
    reply = str(event.get("reply") or "").strip()
    if user and reply:
        return "%s｜%s" % (user, reply)
    return user or reply or None


__all__ = [
    "RouteContract",
    "CONTRACTS",
    "CONTRACT_BY_MOBILE",
    "CONTRACT_BY_BACKEND",
    "MEMORY_CATEGORIES",
    "SCREEN_PROGRAM_IDS",
    "SCREEN_PROGRAMS",
    "DEVICE_STATUS_SHAPE",
    "resolve_path",
    "path_exists",
    "path_non_empty",
    "merge_shape",
    "memory_payload",
    "conversation_note",
]
