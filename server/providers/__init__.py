# -*- coding: utf-8 -*-
"""providers —— 大模型 provider 抽象。

    base.py    抽象基类（chat / tts / asr 三个能力）+ 错误分类
    minimax.py MiniMax provider（OpenAI 兼容 chat + /v1/t2a_v2 TTS）
    local.py   本地推理 provider（OpenAI 兼容；**只允许回环地址** ⇒ 对话不出网）
    stub.py    离线桩（没有 API Key 也能跑通全链路）

选型规则（docs/research/60-MiniMax账号与模型可用性实测.md §1）：
    base URL 必须是 https://api.minimaxi.com（海外域 api.minimax.io 对大陆账号报 2049）；
    chat 走 OpenAI 兼容端点 POST /v1/chat/completions；
    TTS 走 POST /v1/t2a_v2。
"""

from .base import (
    ChatReply,
    Provider,
    ProviderError,
    ProviderKind,
    TtsAudio,
    classify_status,
)
from .local import LocalProvider
from .registry import available_providers, build_provider, default_provider

__all__ = [
    "ChatReply",
    "LocalProvider",
    "Provider",
    "ProviderError",
    "ProviderKind",
    "TtsAudio",
    "classify_status",
    "available_providers",
    "build_provider",
    "default_provider",
]
