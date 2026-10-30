# -*- coding: utf-8 -*-
"""providers.base —— provider 抽象（chat / tts / asr 三个能力）+ 错误码分类。

设计约束：
    - 上游 API 的字段名**不靠记忆**，全部来自 docs/research/60 号实测文档
      与 ai-workspace 下跑通过的探测脚本；
    - 错误码分类只认**实测过**的码（2049 / 2054 / 1008 / 2069），
      其余一律归 UNKNOWN 并保留原始 code —— **不编造错误码语义**。

实测依据（docs/research/60-MiniMax账号与模型可用性实测.md）：
    2049  invalid api key            （api.minimax.io 对大陆账号）
    2054  voice id not exist          （TTS 音色 id 写错）
    1008  insufficient balance        （账号余额耗尽）
    2069  no longer available         （模型在**该账号**下不可用）
    ⚠ 2054 与 1008 必须分开判（60 号 §6.1），否则会把「没余额」误诊成「音色写错」。
    ⚠ TTS 成功判据是 ``base_resp.status_code == 0``，不能只看 HTTP 状态码
      （音色无效时也返回 HTTP 200）。
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class ProviderKind(Enum):
    """provider 种类。"""
    MINIMAX = "minimax"
    STUB = "stub"


class ErrorKind(Enum):
    """错误分类。**只对实测过的码给出确定语义**。"""
    INVALID_KEY = "invalid_key"            # 2049
    VOICE_NOT_FOUND = "voice_not_found"    # 2054
    INSUFFICIENT_BALANCE = "insufficient_balance"   # 1008
    MODEL_UNAVAILABLE = "model_unavailable"         # 2069
    AUTH_FAILED = "auth_failed"            # HTTP 401/403
    RATE_LIMIT = "rate_limit"              # HTTP 429
    BAD_REQUEST = "bad_request"            # HTTP 400
    NETWORK = "network"                    # 连不上 / 超时
    UNSUPPORTED = "unsupported"            # 该能力本 provider 不提供
    UNKNOWN = "unknown"


#: 60 号实测过的业务错误码 → 分类。**只收有实测依据的码**。
VERIFIED_STATUS_CODES: Dict[int, ErrorKind] = {
    2049: ErrorKind.INVALID_KEY,
    2054: ErrorKind.VOICE_NOT_FOUND,
    1008: ErrorKind.INSUFFICIENT_BALANCE,
    2069: ErrorKind.MODEL_UNAVAILABLE,
}

#: 60 号实测过的业务错误码 → 中文处置建议
STATUS_HINTS: Dict[int, str] = {
    2049: "API Key 无效或用错了域名（大陆账号必须用 api.minimaxi.com）",
    2054: "音色 id 不存在，换成 60 号 §6 实测可用的音色",
    1008: "账号余额不足，换账号或充值（**不是音色问题**）",
    2069: "该模型在当前账号下不可用，换 key 后需重测（60 号 §3.1）",
}


class ProviderError(Exception):
    """provider 调用失败。

    Attributes:
        kind: 错误分类
        code: 原始业务码（如 2054）或 HTTP 状态码；未知时为 0
        message: 上游返回的原始信息（已脱敏）
        provider: 出错的 provider 名
    """

    def __init__(self, kind: ErrorKind, message: str, code: int = 0,
                 provider: str = "", http_status: int = 0) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code
        self.message = message
        self.provider = provider
        self.http_status = http_status

    def __str__(self) -> str:
        parts = ["[%s]" % self.kind.value]
        if self.code:
            parts.append("code=%d" % self.code)
        if self.http_status:
            parts.append("http=%d" % self.http_status)
        if self.provider:
            parts.append("provider=%s" % self.provider)
        return " ".join(parts) + ": " + self.message

    @property
    def hint(self) -> str:
        """可执行的处置建议（只对实测过的码有内容）。"""
        return STATUS_HINTS.get(self.code, "")


def classify_status(code: int, message: str = "") -> ErrorKind:
    """按业务码分类（**未实测过的码一律 UNKNOWN**）。"""
    return VERIFIED_STATUS_CODES.get(int(code), ErrorKind.UNKNOWN)


def classify_http_status(status: int) -> ErrorKind:
    """按 HTTP 状态码分类。"""
    if status in (401, 403):
        return ErrorKind.AUTH_FAILED
    if status == 402:
        return ErrorKind.INSUFFICIENT_BALANCE
    if status == 400:
        return ErrorKind.BAD_REQUEST
    if status == 429:
        return ErrorKind.RATE_LIMIT
    if status in (500, 502, 503, 504):
        return ErrorKind.NETWORK
    return ErrorKind.UNKNOWN


@dataclass
class ChatReply:
    """一次对话回复。"""
    text: str = ""
    reasoning: str = ""
    model: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.text.strip())


@dataclass
class TtsAudio:
    """一段合成语音。

    约定：**裸 PCM**（16-bit little-endian、单声道），sample_rate 自带。
    """
    pcm: bytes = b""
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "pcm_s16le"
    voice: str = ""
    provider: str = ""

    @property
    def duration_s(self) -> float:
        if self.sample_rate <= 0 or self.channels <= 0:
            return 0.0
        bytes_per_frame = 2 * self.channels
        return len(self.pcm) / float(bytes_per_frame * self.sample_rate)

    @property
    def frame_count(self) -> int:
        if self.channels <= 0:
            return 0
        return len(self.pcm) // (2 * self.channels)

    def to_wav(self) -> bytes:
        """包成标准 WAV（RIFF/PCM16）字节流。"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(self.pcm)
        return buf.getvalue()


class Provider(ABC):
    """provider 抽象基类：三个能力 chat / tts / asr。

    - **chat**：必需
    - **tts**：必需（本项目的核心链路：TTS → 韵律 → 0x14）
    - **asr**：可选。本仓库没有任何 ASR 接口的实测依据（60 号只覆盖 chat 与
      t2a_v2），所以 MiniMax provider 的 ``asr`` 一律报 UNSUPPORTED。
    """

    kind: ProviderKind = ProviderKind.STUB
    name: str = "base"

    # ── 能力声明 ───────────────────────────────────────────────────────────
    @property
    def supports_chat(self) -> bool:
        return True

    @property
    def supports_tts(self) -> bool:
        return True

    @property
    def supports_asr(self) -> bool:
        return False

    # ── 三个能力 ───────────────────────────────────────────────────────────
    @abstractmethod
    def chat(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> ChatReply:
        """对话补全。``messages`` 形如 ``[{"role": "user", "content": "..."}]``。"""

    @abstractmethod
    def tts(self, text: str, **kwargs: Any) -> TtsAudio:
        """语音合成，返回 16 kHz 单声道裸 PCM。"""

    def asr(self, pcm: bytes, sample_rate: int = 16000, **kwargs: Any) -> str:
        """语音识别（可选能力）。默认不支持。"""
        raise ProviderError(ErrorKind.UNSUPPORTED,
                            "provider %s does not support ASR" % self.name,
                            provider=self.name)

    # ── 辅助 ───────────────────────────────────────────────────────────────
    def describe(self) -> Dict[str, Any]:
        """能力自述（进日志用，**不含任何密钥**）。"""
        return {
            "name": self.name,
            "kind": self.kind.value,
            "chat": self.supports_chat,
            "tts": self.supports_tts,
            "asr": self.supports_asr,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return "<%s name=%s>" % (type(self).__name__, self.name)


__all__ = [
    "ProviderKind", "ErrorKind", "ProviderError",
    "VERIFIED_STATUS_CODES", "STATUS_HINTS",
    "classify_status", "classify_http_status",
    "ChatReply", "TtsAudio", "Provider",
]
