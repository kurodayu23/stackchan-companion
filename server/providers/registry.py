# -*- coding: utf-8 -*-
"""providers.registry —— provider 选型。

规则（docs/research/60 §1）：

    - 有 MINIMAX_API_KEY ⇒ 默认走 MiniMax；
    - 没有 ⇒ 自动退回离线 stub，**整条链路照样跑得通**（含真实音频合成）；
    - STACKCHAN_PROVIDER=minimax|stub|local|auto 可强制指定。

⚠ MiniMax 的「模型是否可用」是**账号级属性**（60 号 §3.1），
所以这里不做任何「模型清单」预检 —— 只看有没有 key，失败留给真实调用去报。

⭐ ``local``（本地推理 provider）是 **M-05 护城河项的执行体**：
它**只允许指向回环地址** ⇒ 选了它，对话正文**一个字节都不出网**。
详见 ``providers/local.py`` 文件头。
"""

from __future__ import annotations

from typing import List, Optional

from ..stackchan_ai.config import Config
from .base import Provider
from .local import LocalProvider
from .minimax import MiniMaxProvider
from .stub import StubProvider


def available_providers() -> List[str]:
    """可用的 provider 名。"""
    return ["stub", "minimax", "local"]


def build_provider(name: str, config: Config) -> Provider:
    """按名字构造 provider。

    Args:
        name: 'stub' | 'minimax' | 'local' | 'auto'
        config: 配置快照（**key 只从 config.api_key 取，不落盘、不回显**）

    Raises:
        ValueError: 名字不认识
        RuntimeError: 指定 minimax 但环境里没有 key
        ValueError: 指定 local 但地址不是回环（隐私不变量）
    """
    name = (name or "auto").strip().lower()
    if name == "stub":
        return StubProvider()
    if name == "minimax":
        if not config.api_key_present:
            raise RuntimeError(
                "STACKCHAN_PROVIDER=minimax but MINIMAX_API_KEY is not set "
                "(key 只能从环境变量读)")
        return MiniMaxProvider(
            base_url=config.base_url,
            api_key=config.api_key or "",
            chat_model=config.chat_model,
            tts_model=config.tts_model,
            tts_voice=config.tts_voice,
        )
    if name == "local":
        return LocalProvider(
            base_url=config.local_base_url,
            model=config.local_model,
            api_key=config.local_api_key or "",
            tts_model=config.local_tts_model,
            tts_voice=config.local_tts_voice,
            allow_remote=config.local_allow_remote,
        )
    if name == "auto":
        return build_provider(config.provider_name, config)
    raise ValueError("unknown provider %r (available: %s)"
                     % (name, ", ".join(available_providers())))


def default_provider(config: Optional[Config] = None) -> Provider:
    """按配置里的 provider 选型构造。"""
    cfg = config or Config.from_env()
    return build_provider(cfg.provider, cfg)


__all__ = ["available_providers", "build_provider", "default_provider"]
