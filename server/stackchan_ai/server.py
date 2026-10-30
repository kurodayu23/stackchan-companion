# -*- coding: utf-8 -*-
"""server —— WebSocket 服务端（设备端 + App 端）+ AI 闭环编排。

协议行为与已交付的 `tools/stackchan_server.py`（协议替身）**逐条对齐**：

    - 角色按 query 的 deviceType 区分（官方云 web_socket.go:120-132）
        deviceType=StackChan        → 设备
        deviceType=App&deviceId=xxx → App
    - 6 类消息剥 12 字节 MAC 前缀后转发给设备
      （web_socket.go:523/537/553/569/588）
    - ⭐ 0x14 Dance **原样转发，不剥前缀**（web_socket.go:740-746）
    - 每 5 秒发一轮 0x10 心跳（官方云 cron.go:35 + socket_task.go:36）；
      固件 10 秒收不到任何帧会报 Heartbeat Timeout（hal_ws_avatar.cpp:171-174）
    - 设备上线/下线广播 0x17 / 0x16
    - 固件发 0x10 → 回 0x11（hal_ws_avatar.cpp:287-294）

⭐ 本文件额外做的事（**协议零改动**，全部在服务端）：

    App 发 0x07 用户文本
      → LLM（stub / MiniMax）出回复文本
      → TTS（stub / MiniMax）合成 16 kHz PCM
      → 韵律提取 → 42 参数 → PCHIP → 0x14 关键帧（25 Hz）
      → 通过 WebSocket 下发给设备（**无 MAC 前缀**）

运行：

    py -3.12 -m server.stackchan_ai.server --serve --port 12800
    py -3.12 -m server.stackchan_ai.server --text "你好呀"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

try:
    import websockets
except ImportError:  # pragma: no cover
    print("need websockets: py -3.12 -m pip install websockets")
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 允许 `python -m server.stackchan_ai.server` 直接跑（仓库根在 sys.path 上时）
if __package__ in (None, ""):  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from . import protocol
from .config import Config
from .llm import LLM
from .memory import ProfileStore
from .persona import Persona, load_persona
from .prosody import ProsodyResult, pcm_to_keyframes
from .tts import TTS

if __package__ in (None, ""):  # pragma: no cover
    from providers.base import Provider, ProviderError
    from providers.registry import build_provider
    from providers.stub import StubProvider
else:
    from ..providers.base import Provider, ProviderError
    from ..providers.registry import build_provider
    from ..providers.stub import StubProvider


class StackChanServer:
    """StackChan 云端（协议替身 + AI 闭环）。

    Args:
        config: 配置快照（API Key 只从环境变量读）
        provider: 可选；不给就按 config 选（auto：有 key 用 MiniMax，否则 stub）
        persona: 可选；不给就按 config 里的 persona id 加载
        store: 可选；关系档案存储（默认落在 private/）
    """

    def __init__(self, config: Optional[Config] = None,
                 provider: Optional[Provider] = None,
                 persona: Optional[Persona] = None,
                 store: Optional[ProfileStore] = None,
                 verbose: bool = True) -> None:
        self.config = config or Config.from_env()
        self.verbose = verbose
        self.persona = persona or load_persona()
        self.provider = provider or build_provider(self.config.provider, self.config)
        self.store = store or ProfileStore(self.config.private_dir)

        # 回落 provider：主 provider 失败时用 stub 保证「设备永远能收到动作」
        self.fallback = StubProvider()
        self.llm = LLM(self.provider, system_prompt=self.persona.system_prompt,
                      fallback=self.fallback)
        self.tts = TTS(self.provider, voice=self.persona.voice, fallback=self.fallback)

        # ── 连接注册表 ─────────────────────────────────────────────────
        self.devices: Dict[str, Any] = {}     # mac -> websocket
        self.apps: List[Any] = []
        self.default_mac = "68ee8fd73668"
        self._pending_dance: Optional[bytes] = None
        self._stop = asyncio.Event()
        self.bound_port: int = 0
        self.bound_host: str = ""

    # ── 日志 ───────────────────────────────────────────────────────────────
    def log(self, message: str) -> None:
        """日志。**只允许 ASCII**，避免 Windows GBK 控制台炸掉。"""
        if self.verbose:
            safe = "".join(ch if ord(ch) < 128 else "?" for ch in message)
            print(safe, flush=True)

    # ── 帧处理（语义同 tools/stackchan_server.py） ─────────────────────────
    def handle_device_frame(self, msg_type: int, payload: bytes) -> List[Tuple[int, bytes]]:
        """设备 → 服务端。返回 ``[(类型, 负载)]``。"""
        if msg_type == protocol.PING:
            return [(protocol.PONG, b"")]
        return []

    def handle_app_frame(self, msg_type: int, payload: bytes,
                         app_mac: Optional[str] = None
                         ) -> List[Tuple[Optional[str], int, bytes]]:
        """App → 服务端。返回 ``[(目标 mac|None, 类型, 负载)]``。

        与官方云 readAppClientMessage 一致：
          - 6 类带 MAC 前缀：用前缀里的 MAC 选目标设备，剥掉前缀转发；
          - 0x14 Dance：原样转发，**不剥前缀**（web_socket.go:740-746）；
          - 其余类型：原样转发。
        """
        if msg_type == protocol.PING:
            return [(None, protocol.PONG, b"")]

        mac, body = protocol.split_mac_prefix(msg_type, payload)
        if msg_type == protocol.DANCE:
            return [(app_mac, protocol.DANCE, body)]

        if mac is not None:
            if mac in self.devices:
                return [(mac, msg_type, body)]
            # 官方云的做法是丢弃（web_socket.go:566）。
            # ⚠ 对**真机**必须放宽：固件连上来的 URL 里没有 MAC
            # （hal_ws_avatar.cpp:88 只有 ?deviceType=StackChan），
            # 官方云是从 Authorization 头解 RSA token 取 MAC（web_socket.go:78-99），
            # 替身服务端解不了 RSA ⇒ 真机只能登记成 default_mac。
            if len(self.devices) == 1:
                only_mac = next(iter(self.devices))
                self.log("[server] 0x%02X mac=%s not matched, fallback to %s"
                         % (msg_type, mac, only_mac))
                return [(only_mac, msg_type, body)]
            self.log("[server] drop 0x%02X for unknown mac %s" % (msg_type, mac))
            return []

        return [(app_mac, msg_type, body)]

    async def dispatch_to_devices(self, frames) -> None:
        """把 ``[(目标 mac|None, 类型, 负载)]`` 投给设备。"""
        for target_mac, msg_type, body in frames:
            if not self.devices:
                self.log("[server] no device online, drop 0x%02X" % msg_type)
                continue
            if target_mac is None:
                targets = list(self.devices.items())
            else:
                ws = self.devices.get(target_mac)
                targets = [(target_mac, ws)] if ws is not None else []
                if not targets:
                    self.log("[server] no device with mac %s, drop 0x%02X"
                             % (target_mac, msg_type))
                    continue
            for mac, ws in targets:
                try:
                    await ws.send(protocol.encode_frame(msg_type, body))
                    self.log("[server] -> device %s 0x%02X %s (%d B)"
                             % (mac, msg_type, protocol.MSG_NAMES.get(msg_type, ""),
                                len(body)))
                except Exception as exc:  # pragma: no cover
                    self.log("[server] send to device %s failed: %s" % (mac, exc))

    async def broadcast_to_apps(self, msg_type: int, body: bytes) -> None:
        for ws in list(self.apps):
            try:
                await ws.send(protocol.encode_frame(msg_type, body))
            except Exception:  # pragma: no cover
                pass

    # ── 0x14 下发 ──────────────────────────────────────────────────────────
    def set_pending_dance(self, sequence) -> bytes:
        """登记一份 0x14 关键帧数组（设备上线后立即下发）。

        校验不通过直接抛 ValueError —— 宁可拒绝下发，也不要让固件静默丢弃
        （固件 json_helper.cpp:192-195 遇到非数组只打日志就返回）。
        """
        errors = protocol.validate_dance_sequence(sequence)
        if errors:
            raise ValueError("invalid dance sequence:\n  " + "\n  ".join(errors))
        payload = protocol.build_dance_payload(sequence)
        self._pending_dance = payload
        return payload

    async def send_dance(self, sequence) -> int:
        """校验 + 下发 0x14。返回成功投递的设备数。"""
        payload = self.set_pending_dance(sequence)
        sent = 0
        for mac, ws in list(self.devices.items()):
            try:
                await ws.send(protocol.encode_frame(protocol.DANCE, payload))
                sent += 1
                self.log("[server] 0x14 dance -> device %s (%d B)" % (mac, len(payload)))
            except Exception as exc:  # pragma: no cover
                self.log("[server] dance send to %s failed: %s" % (mac, exc))
        return sent

    # ── ⭐ AI 闭环 ─────────────────────────────────────────────────────────
    def run_pipeline(self, user_text: str) -> Dict[str, Any]:
        """LLM → TTS → 韵律 → 0x14 关键帧（**同步**，会阻塞；调用方用 to_thread）。

        Returns:
            {"text", "keyframes", "result", "audio"}
        """
        reply = self.llm.reply(user_text)
        audio = self.tts.synthesize(reply.text)
        result: ProsodyResult = pcm_to_keyframes(
            audio.pcm, audio.sample_rate,
            emotion=self.persona.emotion, personal=self.persona.personal)
        # 下发前必须过一遍固件同款校验
        errors = protocol.validate_dance_sequence(result.keyframes)
        if errors:
            raise ValueError("generated keyframes are invalid:\n  "
                             + "\n  ".join(errors))
        return {
            "text": reply.text,
            "reasoning": reply.reasoning,
            "keyframes": result.keyframes,
            "result": result,
            "audio": audio,
        }

    async def handle_user_text(self, user_text: str) -> Dict[str, Any]:
        """App 收到用户文本后的完整闭环（含下发）。

        Returns:
            {"text", "keyframes", "summary", "sent"}
        """
        text = (user_text or "").strip()
        if not text:
            return {"text": "", "keyframes": [], "summary": {}, "sent": 0}
        try:
            outcome = await asyncio.to_thread(self.run_pipeline, text)
        except Exception as exc:
            self.log("[server] pipeline failed: %s" % exc)
            return {"text": "", "keyframes": [], "summary": {}, "sent": 0,
                    "error": str(exc)}

        keyframes = outcome["keyframes"]
        result = outcome["result"]
        stats = protocol.frames_summary(keyframes)
        summary = result.summary()
        summary.update({
            "yawRange": stats["yawRange"],
            "pitchRange": stats["pitchRange"],
            "payloadBytes": len(protocol.build_dance_payload(keyframes)),
            "audioSeconds": round(outcome["audio"].duration_s, 3),
            "provider": self.provider.name,
        })
        sent = await self.send_dance(keyframes)
        self.log("[server] pipeline done: frames=%d dur=%.2fs yaw=%s pitch=%s -> %d device(s)"
                 % (stats["frameCount"], stats["durationSecTotal"],
                    stats["yawRange"], stats["pitchRange"], sent))

        # 事件落 private/（个人数据永不入库）
        try:
            self.store.append_event("default", {
                "type": "dialogue",
                "user": text,
                "reply": outcome["text"],
                "provider": self.provider.name,
            })
        except Exception as exc:  # pragma: no cover
            self.log("[server] persist event failed: %s" % exc)
        return {"text": outcome["text"], "keyframes": keyframes,
                "summary": summary, "sent": sent}

    # ── 连接处理 ───────────────────────────────────────────────────────────
    @staticmethod
    def request_path(ws, legacy_path: Optional[str] = None) -> str:
        """websockets >= 14：路径在 ``ws.request.path``。"""
        for candidate in (getattr(getattr(ws, "request", None), "path", None),
                          legacy_path,
                          getattr(ws, "path", None)):
            if candidate:
                return str(candidate)
        return ""

    async def handler(self, ws, path: Optional[str] = None) -> None:
        request_path = self.request_path(ws, path)
        query = parse_qs(urlparse(request_path).query)
        device_type = (query.get("deviceType") or [""])[0]
        device_id = (query.get("deviceId") or [""])[0]
        raw_mac = (query.get("mac") or [""])[0]

        if device_type == "StackChan":
            mac = protocol.normalize_mac(raw_mac) or self.default_mac
            self.devices[mac] = ws
            self.log("[server] device online: mac=%s path=%s" % (mac, request_path))
            await self.broadcast_to_apps(protocol.DEVICE_ONLINE, mac.encode("ascii"))
            if self._pending_dance is not None:
                await ws.send(protocol.encode_frame(protocol.DANCE, self._pending_dance))
                self.log("[server] 0x14 dance -> device %s (on connect)" % mac)
            try:
                await self.device_loop(ws)
            finally:
                if self.devices.get(mac) is ws:
                    del self.devices[mac]
                self.log("[server] device offline: mac=%s" % mac)
                await self.broadcast_to_apps(protocol.DEVICE_OFFLINE, mac.encode("ascii"))
            return

        if device_type == "App":
            self.apps.append(ws)
            app_mac = protocol.normalize_mac(raw_mac)
            self.log("[server] app connected: deviceId=%s mac=%s"
                     % (device_id or "-", app_mac or "-"))
            macs = sorted(self.devices.keys())
            await ws.send(protocol.encode_frame(
                protocol.DEVICE_ONLINE if macs else protocol.DEVICE_OFFLINE,
                (macs[0] if macs else self.default_mac).encode("ascii")))
            try:
                await self.app_loop(ws, app_mac or None)
            finally:
                if ws in self.apps:
                    self.apps.remove(ws)
                self.log("[server] app disconnected: deviceId=%s" % (device_id or "-"))
            return

        # 其它 deviceType：官方云直接报错（web_socket.go:120-124）
        self.log("[server] reject connection without deviceType: %s" % request_path)
        await ws.close(code=1008, reason="deviceType is required")

    async def device_loop(self, ws) -> None:
        async for raw in ws:
            if isinstance(raw, str):
                # 固件连上后先发一条文本 hello（hal_ws_avatar.cpp:161）
                self.log("[server] device text: %s" % raw[:120])
                continue
            frame = protocol.decode_frame(bytes(raw))
            if frame is None:
                self.log("[server] malformed frame from device")
                continue
            msg_type, payload = frame
            self.log("[server] <- device 0x%02X %s (%d B)"
                     % (msg_type, protocol.MSG_NAMES.get(msg_type, ""), len(payload)))
            for reply_type, reply_body in self.handle_device_frame(msg_type, payload):
                await ws.send(protocol.encode_frame(reply_type, reply_body))

    async def app_loop(self, ws, app_mac: Optional[str] = None) -> None:
        async for raw in ws:
            if isinstance(raw, str):
                self.log("[server] app text: %s" % raw[:120])
                await self.handle_user_text(raw)
                continue
            frame = protocol.decode_frame(bytes(raw))
            if frame is None:
                self.log("[server] malformed frame from app")
                continue
            msg_type, payload = frame
            self.log("[server] <- app 0x%02X %s (%d B)"
                     % (msg_type, protocol.MSG_NAMES.get(msg_type, ""), len(payload)))

            if msg_type == protocol.TEXT_MESSAGE:
                # ⭐ 用户文本 → AI 闭环
                _mac, body = protocol.split_mac_prefix(msg_type, payload)
                text = protocol.parse_text_body(body)
                if text:
                    await self.handle_user_text(text)
                continue

            frames = self.handle_app_frame(msg_type, payload, app_mac)
            await self.dispatch_to_devices(frames)

    # ── 心跳 ───────────────────────────────────────────────────────────────
    async def heartbeat_once(self) -> None:
        targets = list(self.devices.values()) + list(self.apps)
        for ws in targets:
            try:
                await ws.send(protocol.encode_frame(protocol.PING, b""))
            except Exception:  # pragma: no cover
                pass

    async def heartbeat_loop(self) -> None:
        """每 ``heartbeat_interval`` 秒发一轮 0x10。

        官方云每 5 秒发一次（cron.go:35 + socket_task.go:36）；
        固件 10 秒收不到任何帧会报 Heartbeat Timeout（hal_ws_avatar.cpp:171-174）。
        """
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(),
                                       timeout=self.config.heartbeat_interval)
                return
            except asyncio.TimeoutError:
                pass
            await self.heartbeat_once()

    # ── 生命周期 ───────────────────────────────────────────────────────────
    async def serve(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """启动服务（阻塞直到被取消）。"""
        host = host or self.config.host
        port = int(port or self.config.port)
        self._stop.clear()
        heartbeat = asyncio.create_task(self.heartbeat_loop())
        try:
            async with websockets.serve(self.handler, host, port,
                                        ping_interval=20, ping_timeout=20) as ws_server:
                self.bound_port = int(ws_server.sockets[0].getsockname()[1])
                self.bound_host = host
                self.log("[server] listening on ws://%s:%d/stackChan/ws" % (host, port))
                self.log("[server] provider=%s persona=%s key=%s"
                         % (self.provider.name, self.persona.id,
                            self.config.masked_api_key()))
                self.log("[server] devices=%s apps=%d"
                         % (sorted(self.devices.keys()) or "none", len(self.apps)))
                await self._stop.wait()
        finally:
            self._stop.set()
            heartbeat.cancel()

    def stop(self) -> None:
        self._stop.set()


# ── CLI ────────────────────────────────────────────────────────────────────
def _print_pipeline_summary(outcome: Dict[str, Any]) -> None:
    """打印一次离线闭环的摘要（ASCII 安全）。"""
    result = outcome["result"]
    stats = protocol.frames_summary(outcome["keyframes"])
    print("reply      : %s" % outcome["text"].replace("\n", " "))
    print("audio      : %.3f s @ %d Hz mono"
          % (outcome["audio"].duration_s, outcome["audio"].sample_rate))
    print("keyframes  : %d frames (expected %d = ceil(%.3f * 25))"
          % (stats["frameCount"], result.summary()["expectedFrameCount"],
             result.duration_s))
    print("duration   : %.3f s" % stats["durationSecTotal"])
    print("yaw range  : %s (0.1 deg, limit -1280..1280)" % stats["yawRange"])
    print("pitch range: %s (0.1 deg, limit 30..870)" % stats["pitchRange"])
    print("payload    : %d B (no MAC prefix)"
          % len(protocol.build_dance_payload(outcome["keyframes"])))
    features = result.features.as_dict() if result.features else {}
    print("features   : f0=%.1f Hz energy=%.1f dBFS rate=%.2f Hz accents=%d pauses=%d"
          % (features.get("f0_mean_hz", 0.0), features.get("energy_mean_dbfs", 0.0),
             features.get("speech_rate_hz", 0.0),
             int(features.get("f0_accent_count", 0)),
             int(features.get("pause_count", 0))))


async def _serve_async(config: Config) -> None:
    server = StackChanServer(config)
    await server.serve()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="server.stackchan_ai.server",
        description="StackChan cloud backend (protocol stand-in + AI loop)")
    parser.add_argument("--serve", action="store_true", help="start the WebSocket server")
    parser.add_argument("--host", default=None, help="bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default 12800)")
    parser.add_argument("--provider", default=None,
                        choices=["auto", "minimax", "stub"],
                        help="provider selection (default: auto)")
    parser.add_argument("--persona", default=None, help="persona pack id (default enfp)")
    parser.add_argument("--text", default=None,
                        help="run the AI pipeline offline once and print the summary")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.provider:
        config.provider = args.provider
    if args.port:
        config.port = args.port
    if args.host:
        config.host = args.host

    if args.text is not None:
        server = StackChanServer(config)
        outcome = server.run_pipeline(args.text)
        _print_pipeline_summary(outcome)
        return 0

    if not args.serve:
        parser.print_help()
        return 0

    try:
        asyncio.run(_serve_async(config))
    except KeyboardInterrupt:  # pragma: no cover
        print("\n[server] bye")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["StackChanServer", "main"]
