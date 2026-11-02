# -*- coding: utf-8 -*-
"""providers.local —— **本地推理 provider**（OpenAI 兼容），M-05 护城河项的执行体。

⭐⭐ 为什么这个文件重要：
    选了这个 provider ⇒ **对话正文只发往本机回环地址，一个字节都不出网**。
    这不是「承诺」，是**代码里强制**的：非回环地址**构造时就拒绝**
    （``STACKCHAN_LOCAL_ALLOW_REMOTE=1`` 才放行）。

    ⇒ 「个人数据永不入库」从**产品文案**变成**可执行判据**（见 ``tools/check_local_provider.py``）。

接口形状（**全部来自官方文档原文，不是记忆**）：

  chat —— OpenAI 兼容
      POST {base}/v1/chat/completions
      body {"model", "messages": [{"role","content"}], "max_tokens", "temperature", "stream": false}
      200  choices[0].message.content
      出处 ① Ollama 官方 OpenAI 兼容文档
            https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
            （章节「/v1/chat/completions」；示例 base_url='http://localhost:11434/v1/'）
            出处 ② llama.cpp server 官方 README
            https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
            （章节「POST /v1/chat/completions: OpenAI-compatible Chat Completions API」）
      ⚠ 两个后端都提供这个端点 ⇒ **一套代码吃两个后端**（Ollama / llama.cpp / LM Studio 等）。

  tts —— OpenAI 兼容
      POST {base}/v1/audio/speech
      body {"model", "input", "voice", "response_format": "wav", "speed"}
      200  **二进制 WAV**
      出处  Ollama 官方 OpenAI 兼容文档「/v1/audio/speech」章节
            https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
      ⚠ 官方原文两条硬事实：
          「Audio is 16-bit, mono, 24 kHz」
          「The default `response_format` is `wav`, not `mp3`」
          「Unsupported values return a `400` error instead of being ignored」
      ⇒ 我们**请求 wav 并自己解 RIFF 头取真实采样率**，**不硬编码 24 kHz**
        （不同后端/版本可能不同；写死就会出现「韵律算错」的静默偏差）。
      ⚠ 该端点是 **Ollama v0.40.8 才加的**（官方文档原文标注）；
        llama.cpp **没有** ⇒ 没配 TTS 模型时一律报 UNSUPPORTED，**不假装成功**。

本机 HTTP 客户端用标准库 urllib（与 minimax.py 同款，零额外依赖）。
"""

from __future__ import annotations

import ipaddress
import json
import os
import struct
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from .base import (
    ChatReply,
    ErrorKind,
    Provider,
    ProviderError,
    ProviderKind,
    TtsAudio,
    classify_http_status,
)

#: Ollama 本地服务器默认端口（官方文档示例 `http://localhost:11434/v1/`）
DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"

#: 官方文档里反复出现的示例模型（`ollama pull llama3.2`）
DEFAULT_LOCAL_MODEL = "llama3.2"

#: OpenAI 兼容层要求带 key，但 Ollama 官方示例写的是 `api_key='ollama'  # required but ignored`
DEFAULT_LOCAL_API_KEY = "ollama"


# ── 回环地址判定（隐私不变量的核心） ────────────────────────────────────────

def is_loopback_host(host: str) -> bool:
    """这个 host 是不是**本机回环地址**。

    判定口径（**不依赖 DNS**，纯字面量 + 标准库 IP 解析）：

    - ``localhost`` 与任何 ``*.localhost`` ⇒ 回环（RFC 6761 保留域）；
    - IPv4 落在 ``127.0.0.0/8`` ⇒ 回环；
    - IPv6 ``::1`` ⇒ 回环。

    ⚠️ **刻意不做 DNS 解析**：解析一次就可能被 hosts / DNS 劫持指向外网，
       那样「只发往本机」就变成了「发往一个我们以为在本机的东西」。
       ⇒ 宁可**误报**（把某个自定义本机域名判成非回环），不可**漏报**。
    """
    if not host:
        return False
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if h == "localhost" or h.endswith(".localhost"):
        return True
    try:
        addr = ipaddress.ip_address(h)
    except ValueError:
        return False
    return addr.is_loopback


def assert_loopback_base_url(base_url: str) -> None:
    """非回环地址 ⇒ 直接抛错（除非显式放行）。

    这是「个人数据永不入库」的**执行点**：不是文档里的一句承诺，
    而是**任何指向外网的本地 provider 配置都会在构造时炸掉**。

    Raises:
        ValueError: 地址不是回环，且未显式放行
    """
    parts = urlsplit(base_url)
    host = parts.hostname or ""
    if is_loopback_host(host):
        return
    if (os.environ.get("STACKCHAN_LOCAL_ALLOW_REMOTE") or "").strip().lower() in (
            "1", "true", "yes", "on"):
        return
    raise ValueError(
        "LocalProvider refuses non-loopback endpoint %r: "
        "local inference must stay on this machine "
        "(set STACKCHAN_LOCAL_ALLOW_REMOTE=1 to override)" % base_url)


# ── WAV 解析（我们自己解 RIFF 头，不硬编码采样率） ───────────────────────────

class WavInfo(object):
    """一个 WAV 的关键参数 + PCM 载荷。"""

    __slots__ = ("sample_rate", "channels", "bits_per_sample", "pcm")

    def __init__(self, sample_rate: int, channels: int, bits_per_sample: int,
                 pcm: bytes) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.bits_per_sample = bits_per_sample
        self.pcm = pcm


def parse_wav(data: bytes) -> WavInfo:
    """解析 RIFF/WAVE，取出采样率与 PCM 载荷。

    只支持 **PCM（format 1）** 与 16-bit —— 我们的 TtsAudio 契约就是
    「16-bit little-endian 单声道裸 PCM」（见 ``providers/base.py``）。

    Raises:
        ValueError: 不是 WAV / 不是 PCM / 不是 16-bit
    """
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE payload")
    pos = 12
    #: (audio_format, channels, bits_per_sample, sample_rate)
    fmt: Optional[Tuple[int, int, int, int]] = None
    pcm = b""
    total = len(data)
    while pos + 8 <= total:
        chunk_id = data[pos:pos + 4]
        try:
            size = struct.unpack_from("<I", data, pos + 4)[0]
        except struct.error:
            break
        body = data[pos + 8:pos + 8 + size]
        if chunk_id == b"fmt ":
            if len(body) < 16:
                raise ValueError("truncated fmt chunk")
            audio_format, channels, sample_rate = struct.unpack_from("<HHI", body, 0)
            bits = struct.unpack_from("<H", body, 14)[0]
            fmt = (audio_format, channels, bits, sample_rate)
        elif chunk_id == b"data":
            pcm = body
        pos += 8 + size + (size & 1)      # chunk 按偶数字节对齐
    if fmt is None:
        raise ValueError("WAV has no fmt chunk")
    if not pcm:
        raise ValueError("WAV has no data chunk")
    audio_format, channels, bits, sample_rate = fmt
    if audio_format not in (1, 0xFFFE):
        raise ValueError("unsupported WAV audio_format %d (need PCM)" % audio_format)
    if bits != 16:
        raise ValueError("unsupported WAV bits_per_sample %d (need 16)" % bits)
    return WavInfo(sample_rate=int(sample_rate), channels=int(channels),
                   bits_per_sample=int(bits), pcm=pcm)


# ── provider ────────────────────────────────────────────────────────────────

class LocalProvider(Provider):
    """本地推理 provider（OpenAI 兼容端点）。

    ⚠️ **只允许指向回环地址**（见 ``assert_loopback_base_url``）——
       这不是配置建议，是构造时的硬拒绝。
    """

    kind = ProviderKind.LOCAL
    name = "local"

    def __init__(self,
                 base_url: str = DEFAULT_LOCAL_BASE_URL,
                 model: str = DEFAULT_LOCAL_MODEL,
                 api_key: str = "",
                 tts_model: str = "",
                 tts_voice: str = "",
                 chat_timeout: float = 120.0,
                 tts_timeout: float = 180.0,
                 allow_remote: bool = False) -> None:
        self.base_url = self._normalize_base_url(base_url)
        if not allow_remote:
            assert_loopback_base_url(self.base_url)
        elif (os.environ.get("STACKCHAN_LOCAL_ALLOW_REMOTE") or "").strip().lower() not in (
                "1", "true", "yes", "on"):
            # 显式 allow_remote=True 也要求环境变量同时放行（双保险）
            raise ValueError(
                "allow_remote=True still requires STACKCHAN_LOCAL_ALLOW_REMOTE=1")
        self.model = model or DEFAULT_LOCAL_MODEL
        self._api_key = api_key or DEFAULT_LOCAL_API_KEY
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.chat_timeout = chat_timeout
        self.tts_timeout = tts_timeout

    # ── 工具 ────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        """把 base URL 规整成 ``.../v1`` 形式。

        官方文档示例两种写法都出现过：
            ``base_url='http://localhost:11434/v1/'``（OpenAI 客户端用法）
            ``curl http://localhost:11434/v1/chat/completions``（裸 URL）
        ⇒ 用户配 ``http://127.0.0.1:11434`` 或 ``.../v1`` 都能用。
        """
        url = (base_url or DEFAULT_LOCAL_BASE_URL).strip().rstrip("/")
        if not url:
            url = DEFAULT_LOCAL_BASE_URL
        parts = urlsplit(url)
        if not parts.scheme:
            url = "http://" + url
            parts = urlsplit(url)
        path = parts.path or ""
        if not path.rstrip("/").endswith("/v1"):
            path = path.rstrip("/") + "/v1"
        return "%s://%s%s" % (parts.scheme, parts.netloc, path)

    def _mask(self, text: str) -> str:
        """把 key 片段从文本里抹掉（本地 key 通常是占位符，但纪律不放松）。"""
        if not text:
            return text
        if len(self._api_key) >= 8 and self._api_key in text:
            return text.replace(self._api_key, "***")
        return text

    def _post_bytes(self, path: str, payload: Optional[Dict[str, Any]],
                    timeout: float) -> Tuple[int, bytes]:
        """POST；返回 ``(http_status, body_bytes)``；网络异常转 ProviderError。"""
        url = self.base_url + path
        data = None
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read()
            except Exception:
                return exc.code, b""
        except urllib.error.URLError as exc:
            raise ProviderError(
                ErrorKind.NETWORK,
                self._mask("cannot reach local endpoint %s: %s" % (url, exc.reason)),
                provider=self.name) from exc
        except Exception as exc:  # pragma: no cover - 防御
            raise ProviderError(ErrorKind.NETWORK, self._mask(str(exc)),
                                provider=self.name) from exc

    def _raise_for_payload(self, status: int, body: bytes) -> None:
        """按 HTTP 状态码 / JSON 错误体抛出分类后的异常。"""
        message = ""
        try:
            parsed = json.loads(body.decode("utf-8", "ignore"))
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict):
                message = str(err.get("message") or err.get("msg") or "")
            elif err is not None:
                message = str(err)
            if not message:
                message = str(parsed.get("message") or parsed.get("detail") or "")
        if not message:
            message = "HTTP %d %s" % (status, body[:200].decode("utf-8", "ignore"))

        # ⚠ 404 / 501 ⇒ 这个后端**没有**这个端点 ⇒ 能力缺失，不是故障
        if status in (404, 501):
            raise ProviderError(ErrorKind.UNSUPPORTED, self._mask(message),
                                http_status=status, provider=self.name)
        raise ProviderError(classify_http_status(status), self._mask(message),
                            http_status=status, provider=self.name)

    # ── chat ────────────────────────────────────────────────────────────
    def chat(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> ChatReply:
        """OpenAI 兼容对话补全。"""
        payload: Dict[str, Any] = {
            "model": str(kwargs.get("model") or self.model),
            "messages": [{"role": str(m.get("role", "user")),
                          "content": str(m.get("content", ""))}
                         for m in messages],
            "stream": False,
        }
        max_tokens = kwargs.get("max_tokens")
        payload["max_tokens"] = int(max_tokens) if max_tokens is not None else 512
        temperature = kwargs.get("temperature")
        if temperature is not None:
            payload["temperature"] = float(temperature)

        status, body = self._post_bytes("/chat/completions", payload, self.chat_timeout)
        if status != 200:
            self._raise_for_payload(status, body)
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise ProviderError(ErrorKind.UNKNOWN,
                                self._mask("bad chat response: %s" % exc),
                                http_status=status, provider=self.name) from exc

        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = str(message.get("content") or "")
        reasoning = str(message.get("reasoning_content") or "")
        return ChatReply(text=content, reasoning=reasoning,
                         model=str(data.get("model") or payload["model"]),
                         raw=data)

    # ── tts ─────────────────────────────────────────────────────────────
    @property
    def supports_tts(self) -> bool:
        """配了 TTS 模型才有 TTS 能力。

        ⚠️ Ollama 的 ``/v1/audio/speech`` 是 **v0.40.8 才加的**，
        llama.cpp **没有** ⇒ 没配模型就报 UNSUPPORTED，**不假装成功**。
        """
        return bool(self.tts_model)

    def tts(self, text: str, **kwargs: Any) -> TtsAudio:
        """OpenAI 兼容语音合成 → 16-bit 单声道裸 PCM。

        ⚠️ **请求 ``wav`` 并自己解 RIFF 头**：官方文档写死本地是 24 kHz，
        但那是 Ollama 某一版的实现细节 ⇒ **取回真实采样率**，不写死。
        """
        if not self.tts_model:
            raise ProviderError(ErrorKind.UNSUPPORTED,
                                "LocalProvider has no TTS model configured "
                                "(set STACKCHAN_LOCAL_TTS_MODEL)",
                                provider=self.name)
        model = str(kwargs.get("model") or self.tts_model)
        voice = str(kwargs.get("voice") or self.tts_voice or "")
        payload: Dict[str, Any] = {
            "model": model,
            "input": text or "",
            "response_format": "wav",
            "speed": float(kwargs.get("speed", 1.0)),
        }
        if voice:
            payload["voice"] = voice

        status, body = self._post_bytes("/audio/speech", payload, self.tts_timeout)
        if status != 200:
            self._raise_for_payload(status, body)
        try:
            info = parse_wav(body)
        except ValueError as exc:
            raise ProviderError(ErrorKind.UNKNOWN,
                                self._mask("bad tts payload: %s" % exc),
                                http_status=status, provider=self.name) from exc
        return TtsAudio(pcm=info.pcm, sample_rate=info.sample_rate,
                        channels=info.channels, encoding="pcm_s16le",
                        voice=voice, provider=self.name)

    # ── asr ─────────────────────────────────────────────────────────────
    @property
    def supports_asr(self) -> bool:
        """**未验证** ⇒ 不提供。

        ⚠️ Ollama 的 OpenAI 兼容层**列了** ``/v1/audio/transcriptions`` 端点，
        但本仓**没有抓过它的请求/响应形状** ⇒ 按「无实测依据不做实现」处理
        （与 ``providers/base.py`` 对 MiniMax ASR 的同一条纪律）。
        """
        return False

    def __repr__(self) -> str:  # pragma: no cover
        return ("<LocalProvider base=%s model=%s tts=%s>"
                % (self.base_url, self.model, self.tts_model or "(none)"))


__all__ = [
    "LocalProvider", "is_loopback_host", "assert_loopback_base_url",
    "parse_wav", "WavInfo",
    "DEFAULT_LOCAL_BASE_URL", "DEFAULT_LOCAL_MODEL", "DEFAULT_LOCAL_API_KEY",
]
