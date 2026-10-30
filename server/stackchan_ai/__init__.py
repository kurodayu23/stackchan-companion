# -*- coding: utf-8 -*-
"""stackchan_ai —— StackChan 云端核心实现。

模块清单：
    config.py    配置（全部从环境变量读；API Key 不落盘）
    protocol.py  帧编解码 + 消息类型 + 0x14 校验
    llm.py       MiniMax chat 封装（OpenAI 兼容端点）
    tts.py       MiniMax TTS 封装
    prosody.py   韵律 → 0x14 关键帧编译器
    memory.py    关系档案存储（只落在 private/）
    persona.py   人格包加载
    server.py    WebSocket 服务端（设备端 + App 端）+ AI 闭环编排
"""

__version__ = "0.1.0"

__all__ = [
    "config", "protocol", "llm", "tts", "prosody",
    "memory", "persona", "server",
]
