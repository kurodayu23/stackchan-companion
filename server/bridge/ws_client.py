# -*- coding: utf-8 -*-
"""bridge.ws_client —— WebSocket 连接管理 + 设备侧模拟器。

两个角色：

    WsLink          通用连接管理（连接 / 发帧 / 收帧 / 关连接）
    DeviceSimulator 扮演**固件**的角色：连 ``ws://<host>:<port>/stackChan/ws?deviceType=StackChan``，
                    按固件协议收帧，并统计收到的 0x14 关键帧
                    （帧数 / 总时长 / yaw·pitch 范围 / 字节数 / 是否有 MAC 前缀）。

固件行为对齐（出处见 tools/stackchan_server.py 头注释）：
    - 固件连上后先发一条**文本** hello（hal_ws_avatar.cpp:161）
      ``{"type":"hello","msg":"Hello from StackChan!"}``；
    - 固件收到 0x10 会回 0x11（hal_ws_avatar.cpp:287-294）；
    - 固件 10 秒收不到任何帧会报 Heartbeat Timeout（hal_ws_avatar.cpp:171-174）。

模拟器**不发** 0x15 GetAvatarPosture —— 固件没有这个类型。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore

from ..stackchan_ai import protocol
from ..stackchan_ai.config import DEVICE_PATH

#: 设备连上来的路径（固件 hal_ws_avatar.cpp:88，配置项见 config.DEVICE_PATH）

#: 固件连上后发的 hello（hal_ws_avatar.cpp:161）
DEVICE_HELLO = json.dumps({"type": "hello", "msg": "Hello from StackChan!"})


def device_url(host: str, port: int, mac: Optional[str] = None) -> str:
    """设备连接 URL。

    固件侧的 URL 是**编译期常量**（``{}/stackChan/ws?deviceType=StackChan``），
    不带 mac；``mac=`` 是替身服务端额外支持的联调参数。
    """
    url = "ws://%s:%d%s?deviceType=StackChan" % (host, port, DEVICE_PATH)
    if mac:
        url += "&mac=" + mac
    return url


def app_url(host: str, port: int, device_id: str = "app",
            mac: Optional[str] = None) -> str:
    """App 连接 URL（官方云按 deviceType=App 区分，web_socket.go:120-132）。"""
    url = "ws://%s:%d%s?deviceType=App&deviceId=%s" % (host, port, DEVICE_PATH, device_id)
    if mac:
        url += "&mac=" + mac
    return url


@dataclass
class DanceSummary:
    """设备侧收到的 0x14 摘要。"""
    frameCount: int = 0
    durationMsTotal: int = 0
    yawRange: List[int] = field(default_factory=list)
    pitchRange: List[int] = field(default_factory=list)
    payloadBytes: int = 0
    receivedBytes: int = 0          # 收到的整帧字节数（5 字节帧头 + payload）
    frameHeaderBytes: int = 0
    hasMacPrefix: bool = False
    topLevelIsArray: bool = False
    keysOk: bool = True
    keyCount: int = 0

    @property
    def durationSecTotal(self) -> float:
        return round(self.durationMsTotal / 1000.0, 3)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "frameCount": self.frameCount,
            "durationMsTotal": self.durationMsTotal,
            "durationSecTotal": self.durationSecTotal,
            "yawRange": list(self.yawRange),
            "pitchRange": list(self.pitchRange),
            "payloadBytes": self.payloadBytes,
            "receivedBytes": self.receivedBytes,
            "frameHeaderBytes": self.frameHeaderBytes,
            "hasMacPrefix": self.hasMacPrefix,
            "topLevelIsArray": self.topLevelIsArray,
            "keysOk": self.keysOk,
            "keyCount": self.keyCount,
        }

    def describe(self) -> str:
        return ("[device] 0x14 frames=%d total=%.2fs yaw=%s pitch=%s "
                "payload=%dB frame=%dB macPrefix=%s array=%s"
                % (self.frameCount, self.durationSecTotal, self.yawRange,
                   self.pitchRange, self.payloadBytes, self.receivedBytes,
                   self.hasMacPrefix, self.topLevelIsArray))


class WsLink:
    """通用 WebSocket 连接管理。"""

    def __init__(self, url: str, name: str = "link") -> None:
        if websockets is None:  # pragma: no cover
            raise RuntimeError("need websockets: py -3.12 -m pip install websockets")
        self.url = url
        self.name = name
        self.ws = None

    async def connect(self):
        self.ws = await websockets.connect(self.url, ping_interval=20, ping_timeout=20)
        return self.ws

    async def send_frame(self, msg_type: int, payload: bytes = b"") -> None:
        if self.ws is None:
            raise RuntimeError("not connected")
        await self.ws.send(protocol.encode_frame(msg_type, payload))

    async def send_text(self, text: str) -> None:
        if self.ws is None:
            raise RuntimeError("not connected")
        await self.ws.send(text)

    async def recv(self, timeout: Optional[float] = None) -> Optional[Tuple[int, bytes]]:
        """收一帧，返回 ``(type, payload)``；超时返回 None。"""
        if self.ws is None:
            raise RuntimeError("not connected")
        if timeout is None:
            raw = await self.ws.recv()
        else:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        if isinstance(raw, str):
            return None
        return protocol.decode_frame(bytes(raw))

    async def close(self) -> None:
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None


class DeviceSimulator:
    """设备侧模拟器：扮演固件，统计收到的 0x14。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 12800,
                 mac: str = "68ee8fd73668", name: str = "device-sim") -> None:
        self.host = host
        self.port = port
        self.mac = mac
        self.name = name
        self.link: Optional[WsLink] = None
        self.received_frames = 0
        self.received_bytes = 0
        self.pongs = 0
        self.pings = 0
        self.last_dance: Optional[DanceSummary] = None
        self.last_dance_payload: Optional[bytes] = None
        self.dances: List[DanceSummary] = []

    @property
    def url(self) -> str:
        return device_url(self.host, self.port, self.mac)

    async def connect(self) -> "DeviceSimulator":
        self.link = WsLink(self.url, self.name)
        await self.link.connect()
        # 固件连上后先发一条文本 hello（hal_ws_avatar.cpp:161）
        await self.link.send_text(DEVICE_HELLO)
        return self

    async def send_frame(self, msg_type: int, payload: bytes = b"") -> None:
        assert self.link is not None
        await self.link.send_frame(msg_type, payload)

    async def _drain_once(self, timeout: float) -> Optional[DanceSummary]:
        """收一帧；收到 0x14 就解析成摘要。"""
        assert self.link is not None
        try:
            frame = await self.link.recv(timeout=timeout)
        except asyncio.TimeoutError:
            return None
        if frame is None:
            return None
        msg_type, payload = frame
        self.received_frames += 1
        self.received_bytes += 5 + len(payload)
        if msg_type == protocol.PING:
            self.pings += 1
            await self.send_frame(protocol.PONG, b"")
            return None
        if msg_type == protocol.PONG:
            self.pongs += 1
            return None
        if msg_type != protocol.DANCE:
            return None
        summary = summarize_dance_payload(payload)
        summary.receivedBytes = 5 + len(payload)
        summary.frameHeaderBytes = 5
        self.last_dance = summary
        self.last_dance_payload = bytes(payload)
        self.dances.append(summary)
        return summary

    async def wait_for_dance(self, timeout: float = 15.0) -> Optional[DanceSummary]:
        """等待一帧 0x14（期间自动回 0x11 Pong）。"""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remain = deadline - asyncio.get_event_loop().time()
            if remain <= 0:
                return None
            summary = await self._drain_once(min(remain, 1.0))
            if summary is not None:
                return summary

    async def close(self) -> None:
        if self.link is not None:
            await self.link.close()
            self.link = None


def summarize_dance_payload(payload: bytes) -> DanceSummary:
    """把 0x14 payload 解析成设备侧摘要（并检查有没有被误加 MAC 前缀）。"""
    summary = DanceSummary()
    summary.payloadBytes = len(payload)

    # MAC 前缀检测：前 12 字节若是合法 hex ⇒ 被误加了前缀
    if len(payload) >= protocol.MAC_LEN:
        mac = protocol.normalize_mac(payload[:protocol.MAC_LEN].decode("ascii", "ignore"))
        summary.hasMacPrefix = bool(mac)

    text = payload.decode("utf-8", "ignore").lstrip()
    summary.topLevelIsArray = text.startswith("[")
    try:
        sequence = json.loads(payload.decode("utf-8"))
    except Exception:
        return summary
    if not isinstance(sequence, list):
        return summary

    stats = protocol.frames_summary(sequence)
    summary.frameCount = int(stats["frameCount"])
    summary.durationMsTotal = int(stats["durationMsTotal"])
    summary.yawRange = list(stats["yawRange"])
    summary.pitchRange = list(stats["pitchRange"])
    summary.keyCount = len(protocol.DANCE_KEYS)
    summary.keysOk = all(set(frame.keys()) == set(protocol.DANCE_KEYS)
                         for frame in sequence if isinstance(frame, dict))
    return summary


__all__ = [
    "WsLink", "DeviceSimulator", "DanceSummary",
    "device_url", "app_url", "summarize_dance_payload", "DEVICE_PATH",
]
