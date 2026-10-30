# -*- coding: utf-8 -*-
"""bridge —— WebSocket 连接管理。

    ws_client.py  设备/客户端连接管理器 + 设备侧模拟器

设备侧模拟器（DeviceSimulator）用于离线端到端测试：
扮演固件的角色，连 ws://<host>:<port>/stackChan/ws?deviceType=StackChan，
解帧并统计收到的 0x14 关键帧数量 / 总时长 / yaw·pitch 范围。
"""

__all__ = ["ws_client"]
