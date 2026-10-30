# -*- coding: utf-8 -*-
"""test_e2e_offline —— ⭐ 端到端离线闭环。

    用户输入一句话
      → LLM（stub）拿到回复文本
      → TTS（stub）合成 16 kHz PCM
      → 韵律提取 → 42 参数 → PCHIP → 0x14 关键帧
      → 通过 WebSocket 下发给设备（**无 MAC 前缀**）
      → 设备侧模拟器统计收到的帧数 / 总时长 / yaw·pitch 范围

**全程不联网、不需要 API Key**（stub provider）。

断言是真断言，不是「跑通就算」：
    1. 关键帧数 == ceil(音频时长 × 25)
    2. 每帧 8 个 key 齐全（且不多不少）
    3. yaw / pitch 在固件限位内（±1280 / 30..870，单位 0.1 度）
    4. 表情 x / y 是 int，**不是 float**（也不是 bool）
    5. 收到的字节数 == 帧头 5 + payload 长度（**没有 MAC 前缀**）
    6. 变异用例：把 0x14 包成对象 → 校验必须拒绝
    7. 韵律特征非平凡（F0 / 能量 / 语速 / 重音 / 停顿都要有值）
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from server.bridge.ws_client import DeviceSimulator, WsLink, app_url
from server.providers.stub import StubProvider
from server.stackchan_ai import protocol, prosody
from server.stackchan_ai.config import Config
from server.stackchan_ai.memory import ProfileStore
from server.stackchan_ai.persona import load_persona
from server.stackchan_ai.server import StackChanServer

USER_TEXT = "你好呀，今天过得怎么样？"
DEVICE_MAC = "68ee8fd73668"


class EndToEndOfflineTest(unittest.TestCase):
    """端到端：stub provider → 韵律 → 0x14 → 设备模拟器收到正确的字节。"""

    def test_full_loop(self):
        asyncio.run(self._full_loop())

    # ── 主体 ───────────────────────────────────────────────────────────────
    async def _full_loop(self):
        persona = load_persona()

        # ── 0. 独立算一遍「期望值」（与服务端用同一套确定性算法） ─────────
        offline_provider = StubProvider()
        expected_reply = offline_provider.chat([{"role": "user", "content": USER_TEXT}])
        expected_audio = offline_provider.tts(expected_reply.text)
        expected = prosody.pcm_to_keyframes(
            expected_audio.pcm, expected_audio.sample_rate,
            emotion=persona.emotion, personal=persona.personal)
        expected_frames = max(1, int(math.ceil(expected_audio.duration_s * prosody.OUT_FPS)))
        expected_payload = protocol.build_dance_payload(expected.keyframes)

        with tempfile.TemporaryDirectory() as tmp:
            private_dir = Path(tmp) / "private"
            config = Config(host="127.0.0.1", port=0, provider="stub",
                            private_dir=private_dir)
            server = StackChanServer(
                config, provider=StubProvider(), persona=persona,
                store=ProfileStore(private_dir), verbose=False)

            serve_task = asyncio.create_task(server.serve("127.0.0.1", 0))
            try:
                # 等端口就绪
                for _ in range(200):
                    if server.bound_port:
                        break
                    await asyncio.sleep(0.02)
                self.assertTrue(server.bound_port, "server did not start")

                # ── 1. 设备连上来（扮演固件） ─────────────────────────────
                device = DeviceSimulator("127.0.0.1", server.bound_port, DEVICE_MAC)
                await device.connect()
                self.assertIn(DEVICE_MAC, server.devices)

                # ── 2. App 连上来并发 0x07 用户文本（带 12 字节 MAC 前缀，
                #        与官方 App 一致：avatar.dart:720 / dance.dart:191） ──
                app = WsLink(app_url("127.0.0.1", server.bound_port, "test-app"),
                             "app-sim")
                await app.connect()
                await app.send_frame(protocol.TEXT_MESSAGE,
                                     protocol.build_text_payload(DEVICE_MAC, USER_TEXT))

                # ── 3. 设备等 0x14 ────────────────────────────────────────
                summary = await device.wait_for_dance(timeout=30.0)
                self.assertIsNotNone(summary, "device did not receive any 0x14 frame")
                print("[e2e] " + summary.describe())

                # 重新取一次原始 payload（summary 里已有统计，这里要原始字节）
                raw_payload = device.last_dance_payload
                self.assertIsNotNone(raw_payload)
                received_sequence = json.loads(raw_payload.decode("utf-8"))

                # ══ 断言 1：关键帧数 == ceil(音频时长 × 25) ═════════════
                self.assertEqual(summary.frameCount, expected_frames,
                                 "frame count must be ceil(audio duration * 25)")
                self.assertEqual(summary.frameCount, len(expected.keyframes))
                self.assertEqual(summary.frameCount,
                                 max(1, int(math.ceil(expected_audio.duration_s * 25))))

                # ══ 断言 2：每帧 8 个 key 齐全 ═══════════════════════════
                self.assertEqual(len(received_sequence), summary.frameCount)
                for index, frame in enumerate(received_sequence):
                    self.assertEqual(set(frame.keys()), set(protocol.DANCE_KEYS),
                                     "frame[%d] must carry exactly the 8 firmware keys"
                                     % index)

                # ══ 断言 3：yaw / pitch 在固件限位内 ═════════════════════
                for index, frame in enumerate(received_sequence):
                    yaw = frame["yawServo"]["angle"]
                    pitch = frame["pitchServo"]["angle"]
                    self.assertIsInstance(yaw, int)
                    self.assertIsInstance(pitch, int)
                    self.assertGreaterEqual(yaw, protocol.YAW_MIN_RAW)
                    self.assertLessEqual(yaw, protocol.YAW_MAX_RAW)
                    self.assertGreaterEqual(pitch, protocol.PITCH_MIN_RAW)
                    self.assertLessEqual(pitch, protocol.PITCH_MAX_RAW)

                # ══ 断言 4：表情 x / y 是 int，不是 float / bool ══════════
                for index, frame in enumerate(received_sequence):
                    for element in ("leftEye", "rightEye", "mouth"):
                        for field in ("x", "y"):
                            value = frame[element][field]
                            self.assertIsInstance(value, int)
                            self.assertNotIsInstance(value, bool)
                            self.assertNotIsInstance(value, float)

                # ══ 断言 5：收到的字节数 == 帧头 5 + payload 长度（无 MAC 前缀）══
                self.assertEqual(summary.receivedBytes, 5 + summary.payloadBytes)
                self.assertEqual(summary.frameHeaderBytes, 5)
                self.assertEqual(len(raw_payload), summary.payloadBytes)
                self.assertFalse(summary.hasMacPrefix,
                                 "0x14 must NOT carry a 12-byte MAC prefix")
                self.assertTrue(summary.topLevelIsArray,
                                "0x14 top level must be a JSON array")
                self.assertTrue(raw_payload.startswith(b"["))

                # 与独立算出的期望 payload 完全一致（强断言）
                self.assertEqual(raw_payload, expected_payload)
                self.assertEqual(summary.payloadBytes, len(expected_payload))

                # 总时长与帧率对齐（25 Hz → 每帧 40 ms）
                self.assertEqual(summary.durationMsTotal, summary.frameCount * 40)
                self.assertLessEqual(
                    abs(summary.durationMsTotal / 1000.0 - expected_audio.duration_s),
                    40 / 1000.0 + 1e-6)

                # ══ 断言 6：变异用例 —— 把 0x14 包成对象，校验必须拒绝 ════
                wrapped = {"frames": received_sequence}
                errors = protocol.validate_dance_sequence(wrapped)
                self.assertTrue(errors, "0x14 wrapped in an object MUST be rejected")
                self.assertIn("array", errors[0])
                with self.assertRaises(ValueError):
                    server.set_pending_dance(wrapped)

                # ══ 断言 7：韵律特征非平凡 ═══════════════════════════════
                features = expected.features.as_dict()
                self.assertGreater(features["f0_mean_hz"], 50.0)
                self.assertLess(features["energy_mean_dbfs"], -10.0)
                self.assertGreater(features["speech_rate_hz"], 0.5)
                self.assertGreaterEqual(int(features["f0_accent_count"]), 1)
                self.assertGreaterEqual(int(features["pause_count"]), 1)
                self.assertGreater(features["f0_accent_peak_semitone"], 0.5)

                # yaw 确实在动（不是恒定值）
                yaw_values = {frame["yawServo"]["angle"] for frame in received_sequence}
                self.assertGreater(len(yaw_values), 1)

                # 档案落在 private/ 下（个人数据不入库）
                self.assertTrue((private_dir / "events" / "default.jsonl").exists())

                await app.close()
                await device.close()
            finally:
                server.stop()
                serve_task.cancel()
                try:
                    await serve_task
                except (asyncio.CancelledError, Exception):
                    pass

    @staticmethod
    async def _noop():
        return None


class DancePayloadRetentionTest(unittest.TestCase):
    """单独验证：模拟器能保留 0x14 原始字节（供端到端测试逐字节比对）。"""

    def test_summary_round_trip(self):
        from server.bridge.ws_client import summarize_dance_payload
        sequence = [protocol.sample_keyframe(yaw=10, pitch=500)]
        payload = protocol.build_dance_payload(sequence)
        summary = summarize_dance_payload(payload)
        self.assertEqual(summary.frameCount, 1)
        self.assertEqual(summary.payloadBytes, len(payload))
        self.assertFalse(summary.hasMacPrefix)
        self.assertTrue(summary.topLevelIsArray)


if __name__ == "__main__":
    unittest.main()
