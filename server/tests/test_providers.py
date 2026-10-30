# -*- coding: utf-8 -*-
"""test_providers —— provider 抽象 + 离线桩。

重点验证：
    - 没有 API Key 也能拿到**真实可分析**的音频（不是静音）；
    - 错误码分类只认实测过的码（2049 / 2054 / 1008 / 2069）；
    - key 绝不出现在 repr / 日志里。
"""

from __future__ import annotations

import io
import unittest
import wave

import numpy as np

from server.providers import base, minimax, stub
from server.stackchan_ai.config import Config


class StubChatTest(unittest.TestCase):

    def setUp(self):
        self.provider = stub.StubProvider()

    def test_chat_returns_text(self):
        reply = self.provider.chat([{"role": "user", "content": "你好"}])
        self.assertTrue(reply.text)
        self.assertTrue(reply)

    def test_chat_is_deterministic(self):
        messages = [{"role": "user", "content": "今天怎么样"}]
        self.assertEqual(self.provider.chat(messages).text,
                         self.provider.chat(messages).text)

    def test_chat_mentions_user_text(self):
        reply = self.provider.chat([{"role": "user", "content": "你好呀"}])
        self.assertIn("你好呀", reply.text)


class StubTtsTest(unittest.TestCase):

    def setUp(self):
        self.provider = stub.StubProvider()
        self.audio = self.provider.tts("你好呀，这是测试。今天天气不错。")

    def test_audio_is_not_silent(self):
        """⭐ 桩必须合成**真实**音频，否则韵律提取器跑不出非平凡结果。"""
        samples = np.frombuffer(self.audio.pcm, dtype="<i2").astype(np.float64) / 32768.0
        self.assertGreater(len(samples), 16000)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        self.assertGreater(rms, 0.01, "stub audio must not be silence")
        self.assertGreater(float(np.max(np.abs(samples))), 0.1)

    def test_audio_shape(self):
        self.assertEqual(self.audio.sample_rate, 16000)
        self.assertEqual(self.audio.channels, 1)
        self.assertEqual(self.audio.encoding, "pcm_s16le")
        self.assertGreater(self.audio.duration_s, 0.5)
        self.assertEqual(len(self.audio.pcm) % 2, 0)

    def test_audio_to_wav_is_readable(self):
        wav_bytes = self.audio.to_wav()
        self.assertEqual(wav_bytes[:4], b"RIFF")
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getnframes(), self.audio.frame_count)

    def test_pauses_exist_in_synthesized_audio(self):
        """合成信号里必须有真正的静音段（标点停顿）⇒ VAD 能检出停顿。"""
        samples = np.frombuffer(self.audio.pcm, dtype="<i2").astype(np.float64) / 32768.0
        frame = 160  # 10 ms
        n = len(samples) // frame
        energy = np.sqrt(np.mean(samples[:n * frame].reshape(n, frame) ** 2, axis=1))
        quiet = energy < 0.01
        self.assertGreater(int(quiet.sum()), 5, "stub audio must contain pauses")


class ErrorClassificationTest(unittest.TestCase):

    def test_verified_codes(self):
        self.assertIs(base.classify_status(2049), base.ErrorKind.INVALID_KEY)
        self.assertIs(base.classify_status(2054), base.ErrorKind.VOICE_NOT_FOUND)
        self.assertIs(base.classify_status(1008), base.ErrorKind.INSUFFICIENT_BALANCE)
        self.assertIs(base.classify_status(2069), base.ErrorKind.MODEL_UNAVAILABLE)

    def test_unknown_code_stays_unknown(self):
        """未实测过的码**不得**编造语义。"""
        self.assertIs(base.classify_status(123456), base.ErrorKind.UNKNOWN)

    def test_2054_and_1008_are_different(self):
        """60 号 §6.1：音色无效与余额不足必须分开判。"""
        self.assertIsNot(base.classify_status(2054), base.classify_status(1008))

    def test_http_status_classification(self):
        self.assertIs(base.classify_http_status(401), base.ErrorKind.AUTH_FAILED)
        self.assertIs(base.classify_http_status(429), base.ErrorKind.RATE_LIMIT)
        self.assertIs(base.classify_http_status(404), base.ErrorKind.UNKNOWN)

    def test_provider_error_hint(self):
        err = base.ProviderError(base.ErrorKind.VOICE_NOT_FOUND, "voice id not exist",
                                 code=2054, provider="minimax")
        self.assertIn("音色", err.hint)
        self.assertIn("2054", str(err))


class ThinkStripTest(unittest.TestCase):

    def test_inline_think_is_removed(self):
        """60 号 §1：M3 / M2.7 把 <think> 内联在 content 里。"""
        text, reasoning = minimax.strip_think("<think>我先想想</think>你好呀")
        self.assertEqual(text, "你好呀")
        self.assertIn("<think>", reasoning)

    def test_plain_text_untouched(self):
        text, reasoning = minimax.strip_think("你好呀")
        self.assertEqual(text, "你好呀")
        self.assertEqual(reasoning, "")


class RegistryTest(unittest.TestCase):

    def test_stub_provider_without_key(self):
        from server.providers.registry import build_provider
        config = Config.from_env(env={"MINIMAX_API_KEY": ""})
        built = build_provider("stub", config)
        self.assertEqual(built.name, "stub")
        self.assertTrue(built.supports_tts)

    def test_auto_falls_back_to_stub_without_key(self):
        from server.providers.registry import build_provider
        config = Config.from_env(env={})
        self.assertEqual(config.provider_name, "stub")
        self.assertEqual(build_provider("auto", config).name, "stub")

    def test_minimax_requires_key(self):
        from server.providers.registry import build_provider
        config = Config.from_env(env={})
        with self.assertRaises(RuntimeError):
            build_provider("minimax", config)

    def test_minimax_provider_never_leaks_key(self):
        from server.providers.registry import build_provider
        # 假 key，仅用于断言「key 不出现在 repr 里」；不是任何真实凭据
        fake_key = "TESTKEY-not-a-real-secret-000"
        config = Config.from_env(env={"MINIMAX_API_KEY": fake_key})
        built = build_provider("minimax", config)
        self.assertNotIn(fake_key, repr(built))
        self.assertNotIn(fake_key, str(config))
        self.assertIn("***", repr(built))

    def test_unknown_provider_name(self):
        from server.providers.registry import build_provider
        with self.assertRaises(ValueError):
            build_provider("nope", Config.from_env(env={}))


class CapabilityTest(unittest.TestCase):

    def test_stub_has_no_asr(self):
        provider = stub.StubProvider()
        self.assertFalse(provider.supports_asr)
        with self.assertRaises(base.ProviderError):
            provider.asr(b"\x00\x00")

    def test_minimax_has_no_asr(self):
        """仓库里没有 ASR 接口的实测依据 ⇒ 明确不支持。"""
        provider = minimax.MiniMaxProvider("https://api.minimaxi.com", "fake-key-123456")
        self.assertFalse(provider.supports_asr)
        with self.assertRaises(base.ProviderError):
            provider.asr(b"\x00\x00")


if __name__ == "__main__":
    unittest.main()
