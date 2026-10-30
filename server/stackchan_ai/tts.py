# -*- coding: utf-8 -*-
"""tts —— 语音合成封装（回复文本 → 16 kHz 单声道 PCM）。

职责边界：
    - **不**直接调 API：走 `providers` 抽象（stub / minimax 共用路径）；
    - 输出统一为 **16 kHz 单声道 16-bit PCM**（韵律提取器的输入约定）；
    - 失败时按需回落到离线桩（桩合成的是**真实可分析**的类语音信号，不是静音）。

MiniMax 侧事实（docs/research/60 §6）：
    - 端点 POST /v1/t2a_v2，model=speech-02-hd，format=pcm，sample_rate=16000，channel=1；
    - 成功判据是 ``base_resp.status_code == 0``（音色无效时也返回 HTTP 200）；
    - 音色 id 无效报 **2054**，余额不足报 **1008** —— 两个码必须分开判。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..providers.base import ErrorKind, Provider, ProviderError, TtsAudio

#: 韵律提取器要求的采样率（tools/prosody_to_motion.py 的分析窗按 16 kHz 标定）
TARGET_SAMPLE_RATE = 16000


class TTS:
    """语音合成封装。"""

    def __init__(self, provider: Provider,
                 voice: Optional[str] = None,
                 fallback: Optional[Provider] = None) -> None:
        self.provider = provider
        self.voice = voice
        self.fallback = fallback
        self.last_error: Optional[ProviderError] = None

    def synthesize(self, text: str, **kwargs: Any) -> TtsAudio:
        """合成语音。

        Args:
            text: 要念出来的文本（**不要**把 ``<think>`` 推理内容念出来）

        Raises:
            ProviderError: 主 provider 与 fallback 都失败
        """
        text = (text or "").strip()
        if not text:
            text = "嗯。"
        if self.voice:
            kwargs.setdefault("voice", self.voice)
        try:
            audio = self.provider.tts(text, **kwargs)
        except ProviderError as exc:
            self.last_error = exc
            if self.fallback is None:
                raise
            audio = self.fallback.tts(text, **kwargs)
        if audio.sample_rate != TARGET_SAMPLE_RATE:
            # ⚠ 重采样没有实现：采样率不符时如实报错，而不是悄悄给出错位音画
            raise ProviderError(
                ErrorKind.BAD_REQUEST,
                "TTS returned %d Hz, expected %d Hz (resampling not implemented)"
                % (audio.sample_rate, TARGET_SAMPLE_RATE),
                provider=self.provider.name)
        return audio

    def describe(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.name,
            "fallback": self.fallback.name if self.fallback else None,
            "voice": self.voice,
            "sampleRate": TARGET_SAMPLE_RATE,
        }


__all__ = ["TTS", "TARGET_SAMPLE_RATE"]
