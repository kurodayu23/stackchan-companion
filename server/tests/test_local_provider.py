# -*- coding: utf-8 -*-
"""test_local_provider —— 本地推理 provider（OpenAI 兼容）的行为与**隐私不变量**。

⭐ 这个测试文件的价值不在「provider 能用」，而在**它证明对话出不了网**：

    - 非回环地址在**构造时**就被拒绝（隐私不变量的执行点）；
    - 就算显式 allow_remote，也必须同时有环境变量放行（双保险）；
    - 回环判定**刻意不做 DNS 解析**（防 hosts / DNS 劫持）。

接口形状依据（**官方文档原文**，不是记忆）：
    Ollama   https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
    llama.cpp https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
"""

from __future__ import annotations

import io
import json
import os
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.providers import base, local
from server.stackchan_ai.config import Config


# ── 一个假的「本地 OpenAI 兼容服务器」 ───────────────────────────────────────

class _FakeLocalHandler(BaseHTTPRequestHandler):
    """只实现我们要用的两个端点；请求全部记在 ``server.requests`` 里。"""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # pragma: no cover - 静音
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, blob, status=200, ctype="audio/wav"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler 的约定
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        server = self.server
        server.requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": raw,
        })
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            payload = {}

        if self.path.endswith("/chat/completions"):
            if server.chat_status != 200:
                self._send_json({"error": {"message": "boom"}}, server.chat_status)
                return
            self._send_json({
                "model": payload.get("model", "fake"),
                "choices": [{"message": {"role": "assistant",
                                         "content": "本地模型回你一句。"}}],
            })
            return

        if self.path.endswith("/audio/speech"):
            if server.tts_status != 200:
                self._send_json({"error": {"message": "no speech endpoint"}},
                                 server.tts_status)
                return
            self._send_bytes(server.wav_bytes)
            return

        self._send_json({"error": {"message": "not found"}}, 404)


class _FakeLocalServer(object):
    """在**真回环地址**上起一个假服务器（127.0.0.1 + 随机端口）。"""

    def __init__(self, chat_status=200, tts_status=200, sample_rate=24000):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLocalHandler)
        self.httpd.requests = []
        self.httpd.chat_status = chat_status
        self.httpd.tts_status = tts_status
        self.httpd.wav_bytes = make_wav(sample_rate=sample_rate)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        host, port = self.httpd.server_address[0], self.httpd.server_address[1]
        return "http://%s:%d" % (host, port)

    @property
    def requests(self):
        return self.httpd.requests

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_wav(sample_rate=24000, frames=480, channels=1, width=2):
    """造一段最小的 WAV（**故意用 24 kHz**，验证我们不写死采样率）。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x01" * frames * channels)
    return buf.getvalue()


# ── 回环判定 ────────────────────────────────────────────────────────────────

class LoopbackDetectionTest(unittest.TestCase):

    def test_localhost_and_127_are_loopback(self):
        for host in ("localhost", "LOCALHOST", "127.0.0.1", "127.0.0.2",
                     "127.1.2.3", "::1", "[::1]"):
            self.assertTrue(local.is_loopback_host(host), host)

    def test_public_hosts_are_not_loopback(self):
        for host in ("example.com", "8.8.8.8", "192.168.1.5", "10.0.0.1",
                     "api.minimaxi.com", "", "notlocalhost"):
            self.assertFalse(local.is_loopback_host(host), host)

    def test_subdomain_localhost_is_loopback(self):
        """RFC 6761 保留域。"""
        self.assertTrue(local.is_loopback_host("ollama.localhost"))


class PrivacyInvariantTest(unittest.TestCase):
    """⭐「个人数据永不入库」的执行点。"""

    def test_non_loopback_base_url_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            local.LocalProvider(base_url="http://example.com/v1")

    def test_allow_remote_still_requires_env_flag(self):
        """显式 allow_remote=True 也**不能**绕开环境变量。"""
        os.environ.pop("STACKCHAN_LOCAL_ALLOW_REMOTE", None)
        with self.assertRaises(ValueError):
            local.LocalProvider(base_url="http://example.com/v1", allow_remote=True)

    def test_env_flag_allows_remote(self):
        os.environ["STACKCHAN_LOCAL_ALLOW_REMOTE"] = "1"
        try:
            provider = local.LocalProvider(base_url="http://example.com/v1",
                                           allow_remote=True)
            self.assertEqual(provider.base_url, "http://example.com/v1")
        finally:
            os.environ.pop("STACKCHAN_LOCAL_ALLOW_REMOTE", None)

    def test_built_provider_always_loopback(self):
        from server.providers.registry import build_provider
        provider = build_provider("local", Config.from_env(env={}))
        self.assertTrue(local.is_loopback_host(
            provider.base_url.split("//", 1)[1].split(":")[0]))


class BaseUrlNormalizeTest(unittest.TestCase):

    def test_bare_host_gets_v1(self):
        self.assertEqual(local.LocalProvider(base_url="http://127.0.0.1:11434").base_url,
                         "http://127.0.0.1:11434/v1")

    def test_existing_v1_is_kept(self):
        self.assertEqual(
            local.LocalProvider(base_url="http://127.0.0.1:11434/v1/").base_url,
            "http://127.0.0.1:11434/v1")

    def test_missing_scheme_gets_http(self):
        self.assertEqual(local.LocalProvider(base_url="127.0.0.1:11434").base_url,
                         "http://127.0.0.1:11434/v1")


# ── chat ────────────────────────────────────────────────────────────────────

class LocalChatTest(unittest.TestCase):

    def setUp(self):
        self.server = _FakeLocalServer()
        self.addCleanup(self.server.close)
        self.provider = local.LocalProvider(base_url=self.server.base_url,
                                            model="fake-model")

    def test_chat_returns_text(self):
        reply = self.provider.chat([{"role": "user", "content": "你好"}])
        self.assertTrue(reply.text)
        self.assertIn("本地模型", reply.text)

    def test_request_shape_is_openai_compatible(self):
        self.provider.chat([{"role": "user", "content": "你好"}], max_tokens=64,
                           temperature=0.2)
        self.assertTrue(self.server.requests)
        req = self.server.requests[-1]
        self.assertTrue(req["path"].endswith("/v1/chat/completions"))
        body = json.loads(req["body"].decode("utf-8"))
        self.assertEqual(body["model"], "fake-model")
        self.assertEqual(body["messages"], [{"role": "user", "content": "你好"}])
        self.assertEqual(body["max_tokens"], 64)
        self.assertEqual(body["temperature"], 0.2)
        self.assertFalse(body["stream"], "本地 provider 必须是非流式，否则后端读不到完整回复")

    def test_http_error_is_classified(self):
        server = _FakeLocalServer(chat_status=500)
        self.addCleanup(server.close)
        provider = local.LocalProvider(base_url=server.base_url)
        with self.assertRaises(base.ProviderError) as ctx:
            provider.chat([{"role": "user", "content": "hi"}])
        self.assertIn(ctx.exception.kind,
                      (base.ErrorKind.NETWORK, base.ErrorKind.UNKNOWN))

    def test_missing_endpoint_is_unsupported_not_failure(self):
        server = _FakeLocalServer(chat_status=404)
        self.addCleanup(server.close)
        provider = local.LocalProvider(base_url=server.base_url)
        with self.assertRaises(base.ProviderError) as ctx:
            provider.chat([{"role": "user", "content": "hi"}])
        self.assertIs(ctx.exception.kind, base.ErrorKind.UNSUPPORTED)

    def test_unreachable_endpoint_is_network_error(self):
        # 指向一个没人监听的回环端口
        provider = local.LocalProvider(base_url="http://127.0.0.1:9")
        with self.assertRaises(base.ProviderError) as ctx:
            provider.chat([{"role": "user", "content": "hi"}], )
        self.assertIs(ctx.exception.kind, base.ErrorKind.NETWORK)


# ── tts ────────────────────────────────────────────────────────────────────

class LocalTtsTest(unittest.TestCase):

    def test_tts_absent_without_model(self):
        provider = local.LocalProvider(base_url="http://127.0.0.1:11434")
        self.assertFalse(provider.supports_tts)
        with self.assertRaises(base.ProviderError) as ctx:
            provider.tts("你好")
        self.assertIs(ctx.exception.kind, base.ErrorKind.UNSUPPORTED)

    def test_tts_reads_real_sample_rate(self):
        """⭐ 官方文档说本地是 24 kHz ⇒ **不许写死 16 kHz**。"""
        server = _FakeLocalServer(sample_rate=24000)
        self.addCleanup(server.close)
        provider = local.LocalProvider(base_url=server.base_url,
                                       tts_model="speech-model")
        audio = provider.tts("你好呀")
        self.assertEqual(audio.sample_rate, 24000)
        self.assertEqual(audio.channels, 1)
        self.assertEqual(audio.encoding, "pcm_s16le")
        self.assertGreater(len(audio.pcm), 0)
        self.assertGreater(audio.duration_s, 0.0)

    def test_tts_request_uses_wav_format(self):
        server = _FakeLocalServer()
        self.addCleanup(server.close)
        provider = local.LocalProvider(base_url=server.base_url,
                                       tts_model="speech-model", tts_voice="Freya")
        provider.tts("你好")
        body = json.loads(server.requests[-1]["body"].decode("utf-8"))
        self.assertEqual(body["response_format"], "wav")
        self.assertEqual(body["input"], "你好")
        self.assertEqual(body["voice"], "Freya")

    def test_tts_missing_endpoint_is_unsupported(self):
        server = _FakeLocalServer(tts_status=404)
        self.addCleanup(server.close)
        provider = local.LocalProvider(base_url=server.base_url,
                                       tts_model="speech-model")
        with self.assertRaises(base.ProviderError) as ctx:
            provider.tts("你好")
        self.assertIs(ctx.exception.kind, base.ErrorKind.UNSUPPORTED)


class WavParseTest(unittest.TestCase):

    def test_parse_wav_reads_rate(self):
        info = local.parse_wav(make_wav(sample_rate=24000))
        self.assertEqual(info.sample_rate, 24000)
        self.assertEqual(info.channels, 1)
        self.assertEqual(info.bits_per_sample, 16)

    def test_parse_wav_rejects_garbage(self):
        with self.assertRaises(ValueError):
            local.parse_wav(b"not a wav file at all")

    def test_parse_wav_rejects_missing_data(self):
        with self.assertRaises(ValueError):
            local.parse_wav(b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")


# ── 注册与配置 ──────────────────────────────────────────────────────────────

class RegistryTest(unittest.TestCase):

    def test_local_is_available(self):
        from server.providers.registry import available_providers
        self.assertIn("local", available_providers())

    def test_build_local_provider(self):
        from server.providers.registry import build_provider
        provider = build_provider("local", Config.from_env(env={}))
        self.assertIsInstance(provider, local.LocalProvider)
        self.assertEqual(provider.kind, base.ProviderKind.LOCAL)

    def test_provider_name_from_env(self):
        cfg = Config.from_env(env={"STACKCHAN_PROVIDER": "local"})
        self.assertEqual(cfg.provider_name, "local")

    def test_local_env_vars_are_read(self):
        cfg = Config.from_env(env={
            "STACKCHAN_PROVIDER": "local",
            "STACKCHAN_LOCAL_BASE_URL": "http://127.0.0.1:9999/v1",
            "STACKCHAN_LOCAL_MODEL": "my-model",
            "STACKCHAN_LOCAL_TTS_MODEL": "my-tts",
        })
        self.assertEqual(cfg.local_base_url, "http://127.0.0.1:9999/v1")
        self.assertEqual(cfg.local_model, "my-model")
        self.assertEqual(cfg.local_tts_model, "my-tts")

    def test_local_api_key_never_leaked(self):
        from server.providers.registry import build_provider
        fake_key = "TESTKEY-not-a-real-secret-000"
        cfg = Config.from_env(env={"STACKCHAN_PROVIDER": "local",
                                   "STACKCHAN_LOCAL_API_KEY": fake_key})
        provider = build_provider("local", cfg)
        self.assertNotIn(fake_key, repr(provider))
        self.assertNotIn(fake_key, str(cfg))

    def test_local_has_no_asr(self):
        """Ollama 列了 /v1/audio/transcriptions，但我们**没抓过形状** ⇒ 不实现。"""
        provider = local.LocalProvider(base_url="http://127.0.0.1:11434")
        self.assertFalse(provider.supports_asr)
        with self.assertRaises(base.ProviderError):
            provider.asr(b"\x00\x00")


if __name__ == "__main__":
    unittest.main()
