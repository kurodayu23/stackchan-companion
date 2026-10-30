# -*- coding: utf-8 -*-
"""llm —— 对话封装（人格 + 上下文 → 回复文本）。

职责边界：
    - **不**直接调 API：走 `providers` 抽象，stub 与 MiniMax 共用同一条路径；
    - **不**处理密钥：key 只在 provider 内部（从环境变量读）；
    - 失败时按需回落到离线桩，保证「设备永远能收到动作」。

人格来源：`persona.py` 加载的人格包（通用人格包开源，个人定制档案在 private/）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ..providers.base import ChatReply, ErrorKind, Provider, ProviderError

#: 对话历史保留的最大轮数（避免上下文无限增长）
DEFAULT_HISTORY_TURNS = 6


class LLM:
    """对话封装。

    Args:
        provider: 任意 provider（stub / minimax）
        system_prompt: 人格系统提示词
        max_tokens: 单次回复上限
        history_turns: 保留多少轮历史
        fallback: 主 provider 失败时的回落 provider（一般是 stub）
    """

    def __init__(self, provider: Provider,
                 system_prompt: str = "",
                 max_tokens: int = 512,
                 history_turns: int = DEFAULT_HISTORY_TURNS,
                 fallback: Optional[Provider] = None) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.history_turns = history_turns
        self.fallback = fallback
        self.last_error: Optional[ProviderError] = None

    # ── 消息组装 ───────────────────────────────────────────────────────────
    def build_messages(self, user_text: str,
                       history: Optional[Sequence[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """组装 OpenAI 兼容的 messages 列表。

        结构：system（可选） → 历史（截断） → 本轮 user。
        """
        messages: List[Dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if history:
            kept = list(history)[-self.history_turns * 2:]
            for item in kept:
                role = str(item.get("role") or "user")
                content = str(item.get("content") or "")
                if role not in ("user", "assistant", "system"):
                    role = "user"
                if content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        return messages

    # ── 主入口 ─────────────────────────────────────────────────────────────
    def reply(self, user_text: str,
              history: Optional[Sequence[Dict[str, str]]] = None,
              **kwargs: Any) -> ChatReply:
        """拿一句回复。

        主 provider 抛 ProviderError 时：
            - 有 fallback ⇒ 用 fallback 再试一次（并记录 last_error）；
            - 没有 ⇒ 异常继续上抛（由调用方决定要不要降级）。
        """
        messages = self.build_messages(user_text, history)
        options = {"max_tokens": self.max_tokens}
        options.update(kwargs)
        try:
            return self.provider.chat(messages, **options)
        except ProviderError as exc:
            self.last_error = exc
            if self.fallback is None:
                raise
            return self.fallback.chat(messages, **options)

    def reply_text(self, user_text: str,
                   history: Optional[Sequence[Dict[str, str]]] = None,
                   **kwargs: Any) -> str:
        """只要文本（空串 ⇒ 调用方应走兜底）。"""
        return self.reply(user_text, history, **kwargs).text

    def describe(self) -> Dict[str, Any]:
        """自述（**不含任何密钥**）。"""
        return {
            "provider": self.provider.name,
            "fallback": self.fallback.name if self.fallback else None,
            "systemPromptChars": len(self.system_prompt),
            "maxTokens": self.max_tokens,
        }


__all__ = ["LLM", "DEFAULT_HISTORY_TURNS"]
