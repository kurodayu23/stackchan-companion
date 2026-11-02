# -*- coding: utf-8 -*-
"""config —— 服务端配置，**全部来自环境变量**。

三个主要环境变量（README 有完整清单）：

    MINIMAX_API_KEY    可选。缺了就自动退回离线 stub provider（有 Key 才有真模型）
    MINIMAX_BASE_URL   默认 https://api.minimaxi.com
    STACKCHAN_PORT     默认 12800

补充变量：

    MINIMAX_CHAT_MODEL   默认 MiniMax-M3.1-Flash
    MINIMAX_TTS_MODEL    默认 speech-02-hd
    MINIMAX_TTS_VOICE    默认 female-shaonv
    STACKCHAN_HOST       默认 0.0.0.0
    STACKCHAN_PROVIDER   auto（默认）/ minimax / stub / local
    STACKCHAN_PRIVATE_DIR / STACKCHAN_PERSONA_DIR

⭐ 本地推理（``STACKCHAN_PROVIDER=local``）专用变量 —— **M-05 护城河项**：

    STACKCHAN_LOCAL_BASE_URL     默认 http://127.0.0.1:11434/v1
    STACKCHAN_LOCAL_MODEL        默认 llama3.2
    STACKCHAN_LOCAL_API_KEY      默认空（OpenAI 兼容层要 key；Ollama 官方示例写的是占位符）
    STACKCHAN_LOCAL_TTS_MODEL    默认空（**空 = 不提供 TTS**）
    STACKCHAN_LOCAL_TTS_VOICE    默认空
    STACKCHAN_LOCAL_ALLOW_REMOTE 默认 0（**只允许回环地址**；置 1 才允许指向外网）

🔒 API Key 纪律（硬性）：
    - 只从环境变量读，**代码里不得出现任何硬编码 key**；
    - **绝不写进任何文件**（含 private/ 下的档案）；
    - **绝不回显**：`repr()` / `str()` / 日志一律打 `***`；
    - key 只在构造 Authorization 头的那一刻出现在内存里。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

#: MiniMax 中国站 base URL。docs/research/60 §1 / §2 实测：
#: 海外域 api.minimax.io 对大陆账号返回 2049 invalid api key ⇒ 必须用 minimaxi.com
DEFAULT_MINIMAX_BASE_URL = "https://api.minimaxi.com"

#: 实测可用的 chat 模型（docs/research/60 §3，账号级属性，换 key 必须重测）
DEFAULT_CHAT_MODEL = "MiniMax-M3.1-Flash"

#: 实测可用的 TTS 模型（docs/research/60 §6）
DEFAULT_TTS_MODEL = "speech-02-hd"

#: 实测可用的音色（docs/research/60 §6；音色 id 无效报 2054）
DEFAULT_TTS_VOICE = "female-shaonv"

#: 本地推理默认地址（Ollama 官方文档示例 `http://localhost:11434/v1/`）
DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"

#: 本地推理默认模型（Ollama 官方文档示例模型 `llama3.2`）
DEFAULT_LOCAL_MODEL = "llama3.2"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 12800

#: 设备固件连的路径（hal_ws_avatar.cpp:88）
DEVICE_PATH = "/stackChan/ws"

#: 掩码串：任何日志里出现的 key 都用这个替换
REDACTED = "***"


def mask_secret(text: str, secret: Optional[str]) -> str:
    """把文本里出现的 key 片段替换成 ``***``。

    日志里**永远**不允许出现 key 本身（哪怕是异常回显 / 上游错误体）。
    """
    if not text:
        return text
    if secret and len(secret) >= 8 and secret in text:
        return text.replace(secret, REDACTED)
    return text


def repo_root() -> Path:
    """仓库根目录（server/ 的上一级）。"""
    return Path(__file__).resolve().parents[2]


class Config:
    """一份不可变的服务端配置快照。

    用法::

        cfg = Config.from_env()
        print(cfg.provider_name)      # 'minimax' 或 'stub'
        print(cfg.api_key_present)    # True / False，**永不打印 key 本身**
    """

    __slots__ = (
        "host", "port", "base_url", "api_key", "chat_model", "tts_model",
        "tts_voice", "provider", "private_dir", "persona_dir",
        "heartbeat_interval", "log_verbose",
        "local_base_url", "local_model", "local_api_key",
        "local_tts_model", "local_tts_voice", "local_allow_remote",
    )

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 base_url: str = DEFAULT_MINIMAX_BASE_URL,
                 api_key: Optional[str] = None,
                 chat_model: str = DEFAULT_CHAT_MODEL,
                 tts_model: str = DEFAULT_TTS_MODEL,
                 tts_voice: str = DEFAULT_TTS_VOICE,
                 provider: str = "auto",
                 private_dir: Optional[Path] = None,
                 persona_dir: Optional[Path] = None,
                 heartbeat_interval: float = 5.0,
                 log_verbose: bool = True,
                 local_base_url: str = DEFAULT_LOCAL_BASE_URL,
                 local_model: str = DEFAULT_LOCAL_MODEL,
                 local_api_key: Optional[str] = None,
                 local_tts_model: str = "",
                 local_tts_voice: str = "",
                 local_allow_remote: bool = False) -> None:
        self.host = host
        self.port = port
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.chat_model = chat_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.provider = provider
        self.private_dir = private_dir or (repo_root() / "private")
        self.persona_dir = persona_dir or (repo_root() / "personas")
        self.heartbeat_interval = heartbeat_interval
        self.log_verbose = log_verbose
        self.local_base_url = (local_base_url or DEFAULT_LOCAL_BASE_URL).strip()
        self.local_model = (local_model or DEFAULT_LOCAL_MODEL).strip()
        self.local_api_key = (local_api_key or "").strip() or None
        self.local_tts_model = (local_tts_model or "").strip()
        self.local_tts_voice = (local_tts_voice or "").strip()
        self.local_allow_remote = bool(local_allow_remote)

    # ── 构造 ───────────────────────────────────────────────────────────────
    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "Config":
        env = os.environ if env is None else env
        raw_key = (env.get("MINIMAX_API_KEY") or "").strip()
        provider = (env.get("STACKCHAN_PROVIDER") or "auto").strip().lower()
        if provider not in ("auto", "minimax", "stub", "local"):
            provider = "auto"
        private_dir = env.get("STACKCHAN_PRIVATE_DIR")
        persona_dir = env.get("STACKCHAN_PERSONA_DIR")
        try:
            port = int(env.get("STACKCHAN_PORT") or DEFAULT_PORT)
        except ValueError:
            port = DEFAULT_PORT
        try:
            heartbeat = float(env.get("STACKCHAN_HEARTBEAT") or 5.0)
        except ValueError:
            heartbeat = 5.0
        local_allow_remote = (env.get("STACKCHAN_LOCAL_ALLOW_REMOTE") or "").strip().lower() \
            in ("1", "true", "yes", "on")
        return cls(
            host=(env.get("STACKCHAN_HOST") or DEFAULT_HOST).strip(),
            port=port,
            base_url=(env.get("MINIMAX_BASE_URL") or DEFAULT_MINIMAX_BASE_URL).strip(),
            api_key=raw_key or None,
            chat_model=(env.get("MINIMAX_CHAT_MODEL") or DEFAULT_CHAT_MODEL).strip(),
            tts_model=(env.get("MINIMAX_TTS_MODEL") or DEFAULT_TTS_MODEL).strip(),
            tts_voice=(env.get("MINIMAX_TTS_VOICE") or DEFAULT_TTS_VOICE).strip(),
            provider=provider,
            private_dir=Path(private_dir) if private_dir else None,
            persona_dir=Path(persona_dir) if persona_dir else None,
            heartbeat_interval=heartbeat,
            log_verbose=(env.get("STACKCHAN_VERBOSE") or "1") not in ("0", "false", "no"),
            local_base_url=(env.get("STACKCHAN_LOCAL_BASE_URL") or DEFAULT_LOCAL_BASE_URL).strip(),
            local_model=(env.get("STACKCHAN_LOCAL_MODEL") or DEFAULT_LOCAL_MODEL).strip(),
            local_api_key=(env.get("STACKCHAN_LOCAL_API_KEY") or "").strip() or None,
            local_tts_model=(env.get("STACKCHAN_LOCAL_TTS_MODEL") or "").strip(),
            local_tts_voice=(env.get("STACKCHAN_LOCAL_TTS_VOICE") or "").strip(),
            local_allow_remote=local_allow_remote,
        )

    # ── 派生属性 ───────────────────────────────────────────────────────────
    @property
    def api_key_present(self) -> bool:
        """有没有 Key（**只返回布尔值，绝不返回 Key 本身**）。"""
        return bool(self.api_key)

    @property
    def provider_name(self) -> str:
        """最终选中的 provider 名：'minimax' / 'stub' / 'local'。"""
        if self.provider == "stub":
            return "stub"
        if self.provider == "minimax":
            return "minimax"
        if self.provider == "local":
            return "local"
        return "minimax" if self.api_key_present else "stub"

    @property
    def ws_url(self) -> str:
        """本机自连地址（设备/测试用）。"""
        host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return "ws://%s:%d%s?deviceType=StackChan" % (host, self.port, DEVICE_PATH)

    # ── 安全 ───────────────────────────────────────────────────────────────
    def masked_api_key(self) -> str:
        """给日志用的 key 表示：一律 ``***``。"""
        return REDACTED if self.api_key_present else "(unset)"

    def auth_header(self) -> Dict[str, str]:
        """构造 Authorization 头。**调用方不要把返回值打印出来**。"""
        if not self.api_key:
            raise RuntimeError("MINIMAX_API_KEY is not set")
        return {"Authorization": "Bearer " + self.api_key}

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试
        return ("Config(host=%r, port=%r, base_url=%r, api_key=%r, "
                "chat_model=%r, tts_model=%r, tts_voice=%r, provider=%r)"
                % (self.host, self.port, self.base_url, self.masked_api_key(),
                   self.chat_model, self.tts_model, self.tts_voice, self.provider))

    __str__ = __repr__


__all__ = [
    "Config", "DEFAULT_MINIMAX_BASE_URL", "DEFAULT_CHAT_MODEL",
    "DEFAULT_TTS_MODEL", "DEFAULT_TTS_VOICE", "DEFAULT_HOST", "DEFAULT_PORT",
    "DEFAULT_LOCAL_BASE_URL", "DEFAULT_LOCAL_MODEL",
    "DEVICE_PATH", "REDACTED", "repo_root", "mask_secret",
]
