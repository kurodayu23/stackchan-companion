# -*- coding: utf-8 -*-
"""StackChan 云端后端基座（Python 协议替身）。

设计约束（来自任务书 + 仓库 docs/）：
    - 不 fork 官方 Go server（本机无 Go），用 Python 写**协议兼容的替身**；
      路径与帧格式逐字对齐官方，将来换回 Go 只改实现不改协议。
    - 固件事实全部来自 docs/research/ 与 tools/ 已交付代码，引用带 file:line。
    - 个人数据只在 private/（永不入库），通用人格包开源。

子包：
    stackchan_ai/  核心实现（协议、LLM/TTS、韵律、人格、记忆、WebSocket 服务端）
    bridge/        WebSocket 连接管理（设备/客户端）
    providers/     大模型 provider 抽象（chat / tts / asr）
    tests/         单元测试 + 端到端离线测试
"""

__all__ = ["stackchan_ai", "bridge", "providers", "tests"]
