# StackChan 云端后端基座（server/）

> M5Stack StackChan 桌面陪伴机器人的云端替身。
> **不 fork 官方 Go server**（本机无 Go），用 Python 写一个**协议兼容的替身**：
> 路径与帧格式逐字对齐官方，将来换回 Go 只改实现、不改协议。

---

## 一、跑起来（3 条命令）

```powershell
# 1) 装依赖（本机 py -3.12 已装：websockets 15.0.1 / numpy 1.26.4 / scipy 1.17.1）
py -3.12 -m pip install -r server/requirements.txt

# 2) ⭐ 没有 API Key 也能跑通全链路（离线桩 provider，合成真实可分析的语音）
py -3.12 server/run.py --demo

# 3) ⭐ 一条命令跑完全部测试（退出码 0 才算过）
py -3.12 server/run_tests.py
```

其它入口：

```powershell
py -3.12 server/run.py --serve --port 12800          # 起服务端
py -3.12 server/run.py --text "你好呀"                # 离线跑一次 AI 闭环并打印摘要
py -3.12 server/run.py --demo --provider stub         # 强制离线桩（完全不联网）
py -3.12 server/run_tests.py --self-test              # 只跑离线端到端自检
py -3.12 -m server.stackchan_ai.server --serve --port 12800   # 等价入口
py -3.12 -m server.tests.test_e2e_offline             # 只跑端到端测试
```

---

## 二、架构图

```
                        ┌──────────────────────────────────────────┐
   用户(App/手机)  ──┐  │  server/stackchan_ai/server.py           │
                    │  │  ┌────────────────────────────────────┐  │
                    └──┤  │  0x07 TextMessage（带 12B MAC 前缀） │  │
                       │  │            ↓ 剥前缀                 │  │
   设备(ESP32-S3) ──┐  │  │  persona.py（人格包）                │  │
                    │  │  │            ↓                        │  │
                    └──┤  │  llm.py  ──► providers/             │  │
                       │  │              ├ minimax.py（真模型） │  │
   ws://<host>:12800  │  │              └ stub.py（离线桩）     │  │
   /stackChan/ws      │  │            ↓ 回复文本                 │  │
   ?deviceType=...    │  │  tts.py  ──► 16 kHz 单声道 PCM       │  │
                       │  │            ↓                        │  │
                       │  │  prosody.py（7 维韵律 → 42 参数     │  │
                       │  │             → PCHIP → 0x14 关键帧）  │  │
                       │  │            ↓                        │  │
                       │  │  protocol.py（帧编解码 + 0x14 校验）  │  │
                       │  └────────────────────────────────────┘  │
                       │  protocol.py（帧编解码 + 0x14 校验）     │
                       │  memory.py ──► private/（永不入库）      │
                       └──────────────────────────────────────────┘
                                      │
                                      ▼ 0x14 DanceSequence（顶层 JSON 数组，**无 MAC 前缀**）
                              ┌───────────────────┐
                              │  设备侧模拟器      │  server/bridge/ws_client.py
                              │  DeviceSimulator  │  （也扮演真机的角色）
                              └───────────────────┘
```

数据流（一次交互）：

```
用户说一句话
  → LLM（stub / MiniMax）拿到回复文本
  → TTS（stub / MiniMax）合成 16 kHz PCM
  → 韵律提取 → 42 参数 → 语义锚点 → PCHIP → 0x14 关键帧（25 Hz，durationMs=40）
  → 通过 WebSocket 下发给设备（**不带也不剥 12 字节 MAC 前缀**）
  → 设备侧模拟器打印：帧数 / 总时长 / yaw·pitch 范围 / 收到的字节数
```

---

## 三、环境变量

| 变量 | 必需 | 默认值 | 说明 |
|---|---|---|---|
| `MINIMAX_API_KEY` | 否 | 空 | **只从环境变量读**。缺了就自动用离线桩（`auto` 模式）。**绝不入库、绝不回显**（日志里一律 `***`） |
| `MINIMAX_BASE_URL` | 否 | `https://api.minimaxi.com` | 中国站。⚠ 海外域 `api.minimax.io` 对大陆账号返回 **2049 invalid api key** |
| `STACKCHAN_PORT` | 否 | `12800` | 服务端监听端口 |
| `STACKCHAN_HOST` | 否 | `0.0.0.0` | 监听地址 |
| `STACKCHAN_PROVIDER` | 否 | `auto` | `auto` / `minimax` / `stub` |
| `MINIMAX_CHAT_MODEL` | 否 | `MiniMax-M3.1-Flash` | ⚠ 模型可用性是**账号级属性**，换 key 必须重测 |
| `MINIMAX_TTS_MODEL` | 否 | `speech-02-hd` | TTS 模型 |
| `MINIMAX_TTS_VOICE` | 否 | `female-shaonv` | ⚠ 音色 id 无效报 **2054**，余额不足报 **1008**，两个码分开判 |
| `STACKCHAN_PRIVATE_DIR` | 否 | `<仓库根>/private` | 关系档案目录（**永不入库**） |
| `STACKCHAN_PERSONA_DIR` | 否 | `<仓库根>/personas` | 通用人格包目录（**只读**） |
| `STACKCHAN_HEARTBEAT` | 否 | `5.0` | 0x10 心跳间隔（秒）。官方云也是 5 秒 |

设 key 的方式（**不要**写进任何仓库文件）：

```powershell
$env:MINIMAX_API_KEY = [Environment]::GetEnvironmentVariable('MINIMAX_API_KEY','User')
```

---

## 四、接真机

设备固件连的是 **编译期常量** 地址（`firmware/main/hal/utils/secret_logic/secret_logic.cpp:11-18`
读 `CONFIG_STACKCHAN_SERVER_URL`，默认值见 `firmware/main/Kconfig.projbuild:5`）：

```
http://47.113.125.164:12800/stackChan/ws?deviceType=StackChan
```

⇒ **本机跑服务端并不能让真机自动连过来**。两条接管路线（见 `docs/research/61`）：

1. **网络层接管（不动固件）**：在设备所在网段做透明 TCP 代理，把发往
   `47.113.125.164:12800` 的连接劫持到本机服务端。设备零改动，风险最低，
   但要求设备与代理同网段，且上游官方服务器会同时收到连接。
2. **重编译刷写**：改 `sdkconfig.defaults.local` 的 `CONFIG_STACKCHAN_SERVER_URL`
   指向本机再刷机。⚠ 要写设备 flash，**必须先取得明确授权**，且刷前先确认
   `backups\pre-reflash-20261011\full-flash-16mb.bin` 备份完好。

本服务端已实现固件侧需要的全部行为：

- 路径 `/stackChan/ws`，按 query 的 `deviceType` 区分设备（`StackChan`）与 App（`App`）；
- 6 类消息剥 12 字节 MAC 前缀后转发；⭐ **0x14 原样转发，不剥也不加前缀**；
- 每 5 秒发一轮 `0x10` 心跳，固件收 `0x10` 回 `0x11`（固件 10 秒收不到帧会报 Heartbeat Timeout）；
- 设备上线/下线广播 `0x17` / `0x16`；
- 设备连上后发的文本 hello 会被记录（固件 `hal_ws_avatar.cpp:161`）。

---

## 五、协议事实（本实现逐条对齐）

| 项 | 事实 | 出处 |
|---|---|---|
| 帧格式 | `[Type(1)][Length(4 BE)][Payload]` | `hal_ws_avatar.cpp:549-561` |
| 消息类型 | `0x03` 控制表情 / `0x04` 控制动作 / `0x07` 文本 / `0x10` 心跳 / `0x11` Pong / `0x14` 舞蹈 | `hal_ws_avatar.cpp:49-72` |
| MAC 前缀 | **只有** `0x01 0x02 0x03 0x04 0x07 0x09` 带 12 字节前缀；`0x14` 不带 | 官方云 `web_socket.go:523/537/553/569/588` vs `:740-746` |
| 0x14 顶层 | 必须是 **JSON 数组**（包成对象会被固件直接丢弃） | `json_helper.cpp:192-195` |
| 0x14 每帧 | 8 个 key：`leftEye` `rightEye` `mouth` `yawServo` `pitchServo` `leftRgbColor` `rightRgbColor` `durationMs` | `json_helper.cpp:201-224` |
| 舵机 | `{"angle":Int,"speed":Int}`，单位 **0.1 度**；yaw ±1280、pitch 30..870 | `json_helper.cpp:166-176`、`hal_servo.cpp:340/:349` |
| 表情元素 | `{"x":Int,"y":Int,"rotation":Int,"weight":Int,"size":Int}`，x/y **必须同时是 int** | `json_helper.cpp:145-164`、`:18` |
| 极性 | 眼睛 weight **越大越睁开**；嘴 weight **越大越张开** | `eyes.cpp:71-78`、`mouth.cpp:48-58` |
| 固件没有 | `0x15 GetAvatarPosture` —— 不发、不期待回复 | `hal_ws_avatar.cpp:49-72` |

---

## 六、隐私边界（个人数据永不入库）

| 数据 | 落点 | 是否入库 |
|---|---|---|
| 通用人格包 | `personas/`（仓库根，**只读**）或 `server/stackchan_ai/personas/` | ✅ 可入库（开源通用资产） |
| 个人关系档案 / 事件流 | `private/profiles/`、`private/events/` | ❌ **永不入库** |

实现方式（不是靠约定，是靠代码拦）：

1. **`.gitignore` 第 11 行已有 `private/`** ⇒ 档案目录天然被排除（`git check-ignore -v private/x.json` 可验证）；
2. `memory.ProfileStore` **每次写盘前**都校验目标路径解析后确实在 `private/` 下，否则抛 `PrivacyError`；
3. 档案名只允许 `[A-Za-z0-9_-]{1,64}` ⇒ 杜绝 `../` 路径穿越；
4. 写入前递归扫描字段名，命中 `api_key` / `access_token` / `secret` / `password` 等
   **直接抛错** ⇒ 密钥不可能被写进档案；
5. `Config.api_key` 只从环境变量读；`repr()`/日志里一律显示 `***`；
   `MiniMaxProvider` 的异常信息在抛出前会用 `mask_secret` 把 key 片段抹掉。

⚠ **个人定制人格数据**同样只允许落在 `private/`，不要写回 `personas/`。

---

## 七、目录结构

```
server/
  README.md              本文件
  requirements.txt       运行依赖（只列已装且真实 import 的包）
  run.py                 便捷入口（--serve / --text / --demo）
  run_tests.py           一条命令跑完全部测试（--self-test 只跑离线自检）
  stackchan_ai/
    config.py            配置（环境变量；API Key 不落盘）
    protocol.py          帧编解码 + MsgType + 0x14 校验
    llm.py               对话封装（人格 + 上下文 → 回复）
    tts.py               语音合成封装（→ 16 kHz 单声道 PCM）
    prosody.py           韵律 → 0x14 关键帧编译器（移植自 tools/prosody_to_motion.py）
    memory.py            关系档案存储（只落 private/）
    persona.py           人格包加载（三层合并：私人层 > 通用包 > 内置兜底）
    server.py            WebSocket 服务端 + AI 闭环编排
    personas/enfp.json   内置兜底人格包（通用包缺失时用）
  bridge/
    ws_client.py         连接管理 + 设备侧模拟器
  providers/
    base.py              provider 抽象（chat / tts / asr）+ 错误码分类
    minimax.py           MiniMax provider（chat + t2a_v2）
    stub.py              离线桩（合成**真实可分析**的类语音，不是静音）
    registry.py          选型（有 key → minimax，无 key → stub）
  tests/
    test_protocol.py     帧编解码 + 0x14 校验（含变异用例）
    test_providers.py    provider 抽象 + 离线桩
    test_memory.py       档案读写 + 隐私边界
    test_persona.py      人格包三层合并（通用包 / 私人层 / 内置兜底）
    test_e2e_offline.py  ⭐ 端到端离线：stub → 韵律 → 0x14 → 设备字节
```

---

## 七点五、人格包三层合并

`persona.py` 实现的加载顺序（**优先级从高到低**）：

| 层 | 位置 | 入库 | 说明 |
| --- | --- | --- | --- |
| 私人层 | `private/persona.local.json` | ❌ **永不入库** | 只在本机；覆盖通用层 |
| 通用人格包 | `personas/enfp.json` | ✅ | 开源、可社区 fork |
| 内置兜底 | `server/stackchan_ai/personas/enfp.json` | ✅ | 保证服务端永远有人格可用 |

合并语义：

- 标量 / 列表字段（`name` / `summary` / `emotion` / `voice` / `system_prompt` / `speech_style`）
  ⇒ **上层有值即覆盖**；
- `personal` ⇒ **逐键合并**（上层只覆盖同名字键，其余保留）。

**私人层容错**：文件缺失 / JSON 语法坏 ⇒ **静默跳过**，只走通用层。
一份坏掉的个人档案**绝不能让机器人变哑巴**（`18` 号 §6.2 的原始要求）。

**隐私边界**：`private/` 已在仓库根 `.gitignore` 里；引擎对它**只读不写**。
`test_persona.py` 里有断言守着这条不变量（`.gitignore` 必须含 `private/`）。

⚠️ **扩展名是 `.json`，不是 `.yaml`**：`docs/research/18` §6.1 / `31` 号的 YAML 设计稿
（含 `index.yaml` 清单、热更新回滚）**没有实现**，实现走 JSON。详见 18 号「公开订正」。

---

## 八、测试

```powershell
py -3.12 server/run_tests.py             # 全部（退出码 0 才算过）
py -3.12 server/run_tests.py --self-test # 只跑离线端到端
```

端到端离线测试的**真断言**（`server/tests/test_e2e_offline.py`）：

1. 关键帧数 `== ceil(音频时长 × 25)`；
2. 每帧**恰好** 8 个 key（不多不少）；
3. `yaw ∈ [-1280, 1280]`、`pitch ∈ [30, 870]`（固件限位，0.1 度）；
4. 表情 `x` / `y` 是 `int`，**不是 float、不是 bool**；
5. 收到的字节数 `== 帧头 5 + payload 长度`，且 **payload 没有 MAC 前缀**、顶层是数组；
6. ⭐ **变异用例**：把 0x14 包成对象 → 校验必须拒绝（`validate_dance_sequence` 报错 + `set_pending_dance` 抛 `ValueError`）；
7. 韵律特征非平凡（F0 / 能量 / 语速 / 重音峰 / 停顿都要有值）；
8. 设备收到的 payload 与独立算出的期望 payload **逐字节相同**。

---

## 九、已知限制 / 未验证项

| 项 | 状态 |
|---|---|
| 真机联调（设备 ↔ 本服务端） | ❌ **未验证**：固件服务器地址是编译期常量，需要网络层接管或刷机才能连上（见第四节）。协议行为按官方源码逐条对齐，但**没有在真机上跑过** |
| 官方 App ↔ 本服务端 | ❌ **未验证**：App 的 `0x07` body 具体形态未取证，本实现以纯文本为主、兼容 JSON 包装 |
| 语音下发到设备 | ❌ **未实现**：0x14 只带动作不带音频；音频通道（`0x18` + Opus）不在本基座范围内。当前 TTS 音频只用于**提取韵律** |
| MiniMax 模型可用性 | ⚠ 与账号绑定（`docs/research/60` §3.1），换 key 必须重测；`/v1/models` 列表不可信 |
| MiniMax ASR | ❌ 不支持：仓库里没有 ASR 接口的实测依据，provider 明确报 `UNSUPPORTED` |
| 25 Hz 关键帧能否被设备主循环吃下 | ❌ 未验证（`docs/research/59` §11.4：主循环频率不在本仓库） |
| 舵机实际运动手感 / `pitch` 角度语义方向 | ❌ 未验证（`docs/research/59` §4） |
