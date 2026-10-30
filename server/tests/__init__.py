# -*- coding: utf-8 -*-
"""tests —— StackChan 后端测试。

    test_protocol.py      帧编解码 + 0x14 校验（含变异用例）
    test_providers.py     provider 抽象 + stub provider
    test_memory.py        关系档案读写（临时目录）
    test_e2e_offline.py   ⭐ 端到端离线：stub → 韵律 → 0x14 → 设备模拟器收到字节

一条命令跑完全部测试：
    py -3.12 server/run_tests.py            # 退出码 0 才算过
    py -3.12 server/run_tests.py --self-test # 只跑离线自检
"""

__all__ = [
    "test_protocol",
    "test_providers",
    "test_memory",
    "test_e2e_offline",
]
