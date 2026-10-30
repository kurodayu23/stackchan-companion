# 75 · 真实 MiniMax 端到端闭环实测 与「TTS 不可复现」的关键发现

> **取证时间**：2026-10-25 06:40（第三轮夜间）
> **产出方式**：本机实跑（不是复述、不是推断）——`server/run.py` 连真实 MiniMax API
> **命令**：`py -3.12 server/run.py --demo --provider minimax --text "..."`
> **原始日志（本仓留存）**：[`docs/research/runs/20261025-0640-e2e-minimax.log`](runs/20261025-0640-e2e-minimax.log)

---

## 一、三条结论

1. **真实链路是通的**：真实 MiniMax Chat（ENFP 人格包）→ 真实 TTS → 韵律 → 42 参数 → PCHIP → `0x14` 关键帧 → WebSocket → 设备模拟器收到帧，**全程无异常，退出码 0**。
2. **协议层行为与官方实测一致**：`0x14` **不带 MAC 前缀**（`macPrefix=False`）、载荷是**数组**（`array=True`）、帧头固定 **+5 B**。
3. ⭐ **MiniMax TTS 的输出不可复现**：同一段文本、同一音色、连跑 3 次，音频时长 **4.598 s / 5.759 s / 6.095 s**（极差 **+32.6%**），**连 LLM 的回复文本每次都不一样**。
   ⇒ **关键帧不能预烘焙**，必须以「本次合成的实际 PCM」实时算；否则音画必然错位。

---

## 二、环境与前置

| 项 | 值 |
|---|---|
| Python | 3.12（`py -3.12`） |
| 依赖 | `websockets` / `numpy` / `scipy` / `soundfile` |
| Provider | `minimax`（真实 API，`MINIMAX_API_KEY` 走**用户级环境变量**，不入库、不回显） |
| 人格 | `personas/enfp.json`（日志里 `persona=enfp`） |
| 设备端 | ⚠️ **`DeviceSimulator`（协议模拟器），不是真机** |
| 云端 | 本机 `ws://127.0.0.1:<随机端口>/stackChan/ws` |

---

## 三、完整原始日志

> 以下逐行摘自仓内留痕文件 [`runs/20261025-0640-e2e-minimax.log`](runs/20261025-0640-e2e-minimax.log)，未做任何删改。

### 3.1 仅跑流水线（真实 MiniMax），**同一段文本连跑 3 次**

```
=== [A1] pipeline (same text, run 1) ===
reply      : 诶，听到你这么说我也超开心！今天有什么好消息，愿意跟我分享吗？
audio      : 6.095 s @ 16000 Hz mono
keyframes  : 153 frames (expected 153 = ceil(6.095 * 25))
duration   : 6.120 s
yaw range  : [-44, 37] (0.1 deg, limit -1280..1280)
pitch range: [703, 838] (0.1 deg, limit 30..870)
payload    : 49133 B (no MAC prefix)
features   : f0=246.6 Hz energy=-36.6 dBFS rate=5.03 Hz accents=15 pauses=6

=== [A2] pipeline (same text, run 2) ===
reply      : 诶，听你这么说我也很开心呀！今天有什么好事发生了吗？
audio      : 4.598 s @ 16000 Hz mono
keyframes  : 115 frames (expected 115 = ceil(4.598 * 25))
duration   : 4.600 s
yaw range  : [-45, 43] (0.1 deg, limit -1280..1280)
pitch range: [711, 840] (0.1 deg, limit 30..870)
payload    : 37096 B (no MAC prefix)
features   : f0=254.3 Hz energy=-37.4 dBFS rate=5.88 Hz accents=9 pauses=6

=== [A3] pipeline (same text, run 3) ===
reply      : 诶，听你这么说我也超开心呀！今天是什么让你这么开心？
audio      : 5.759 s @ 16000 Hz mono
keyframes  : 144 frames (expected 144 = ceil(5.759 * 25))
duration   : 5.760 s
yaw range  : [-22, 48] (0.1 deg, limit -1280..1280)
pitch range: [705, 840] (0.1 deg, limit 30..870)
payload    : 46322 B (no MAC prefix)
features   : f0=256.6 Hz energy=-36.2 dBFS rate=6.52 Hz accents=10 pauses=8
```

### 3.2 全链路（云端 + 设备模拟器 + App 模拟端）

```
=== [B1] full loop (demo, text 1) ===
[server] listening on ws://127.0.0.1:0/stackChan/ws
[server] provider=minimax persona=enfp key=***
[server] device online: mac=68ee8fd73668 path=/stackChan/ws?deviceType=StackChan&mac=68ee8fd73668
[server] device text: {"type": "hello", "msg": "Hello from StackChan!"}
[server] app connected: deviceId=demo-app mac=-
[server] <- app 0x07 textMessage (51 B)
[server] 0x14 dance -> device 68ee8fd73668 (48857 B)
[server] pipeline done: frames=152 dur=6.08s yaw=[-49, 45] pitch=[703, 838] -> 1 device(s)
[demo] [device] 0x14 frames=152 total=6.08s yaw=[-49, 45] pitch=[703, 838] payload=48857B frame=48862B macPrefix=False array=True
[server] app disconnected: deviceId=demo-app
[server] device offline: mac=68ee8fd73668

=== [B2] full loop (demo, text 2) ===
[server] 0x14 dance -> device 68ee8fd73668 (60092 B)
[server] pipeline done: frames=187 dur=7.48s yaw=[-48, 44] pitch=[693, 828] -> 1 device(s)
[demo] [device] 0x14 frames=187 total=7.48s yaw=[-48, 44] pitch=[693, 828] payload=60092B frame=60097B macPrefix=False array=True
```

---

## 四、独立复算（不信任工具自己的输出，逐条手算）

| 量 | 工具输出 | 手算 | 结论 |
|---|---|---|---|
| 关键帧数（6.095 s） | 153 | `ceil(6.095 × 25) = ceil(152.375) = 153` | ✅ 一致 |
| 关键帧数（4.598 s） | 115 | `ceil(4.598 × 25) = ceil(114.95) = 115` | ✅ 一致 |
| 关键帧数（5.759 s） | 144 | `ceil(5.759 × 25) = ceil(143.975) = 144` | ✅ 一致 |
| 时间轴时长（153 帧） | 6.120 s | `153 × 0.040 s = 6.120 s` | ✅ 一致 |
| 时间轴时长（115 帧） | 4.600 s | `115 × 0.040 s = 4.600 s` | ✅ 一致 |
| 时间轴时长（144 帧） | 5.760 s | `144 × 0.040 s = 5.760 s` | ✅ 一致 |
| 时间轴时长（152 帧） | 6.08 s | `152 × 0.040 s = 6.08 s` | ✅ 一致 |
| 时间轴时长（187 帧） | 7.48 s | `187 × 0.040 s = 7.48 s` | ✅ 一致 |
| 帧长（0x14，B1） | `frame=48862B` vs `payload=48857B` | 差 **5 B** = 帧头 `[Type(1)][Length(4)]` | ✅ 一致 |
| 帧长（0x14，B2） | `frame=60097B` vs `payload=60092B` | 差 **5 B** | ✅ 一致 |
| 载荷/帧（5 次） | 49133 / 37096 / 46322 / 48857 / 60092 B | ÷153 /÷115 /÷144 /÷152 /÷187 = **321.1 / 322.6 / 321.7 / 321.4 / 321.3 B** | 单帧结构固定 ≈ **321–323 B** |
| yaw 限位 | 观测 `[-44, 37]` / `[-45, 43]` / `[-22, 48]` vs 限位 `-1280..1280` | 观测在限位内，余量 ~26 倍 | ✅ 未撞限位 |
| pitch 限位 | 观测 `[703, 838]` / `[711, 840]` / `[705, 840]` vs 限位 `30..870` | 观测在限位内 | ✅ 未撞限位 |

> ⚠️ **yaw 限位 −1280..1280（0.1° 单位 ⇒ ±128.0°）是本仓 `spec/00` O-11 的源码事实**，
> 不是通行说法里的「360°」⇒ 「生气时背给你」这类设计做不到 180°。

---

## 五、⭐ 关键发现：MiniMax 的输出**不可复现**

### 5.1 TTS 侧（仓内留痕日志的 3 次，同文本同音色）

| 次序 | 音频时长 | 关键帧数 | 基频 f0 | 能量 | 语速 | 重音数 | 停顿数 |
|---|---|---|---|---|---|---|---|
| A1 | 6.095 s | 153 | 246.6 Hz | −36.6 dBFS | 5.03 Hz | 15 | 6 |
| A2 | **4.598 s** | 115 | 254.3 Hz | −37.4 dBFS | 5.88 Hz | 9 | 6 |
| A3 | 5.759 s | 144 | 256.6 Hz | −36.2 dBFS | 6.52 Hz | 10 | 8 |

| 指标 | 观测 | 说明 |
|---|---|---|
| 时长极差 | 4.598 ~ 6.095 s | **+32.6%**（最慢比最快多 1.497 s） |
| 基频极差 | 246.6 ~ 256.6 Hz | +4.1% |
| 语速极差 | 5.03 ~ 6.52 Hz | +29.6% |
| 重音数 | 9 / 15 / 10 | 极差 1.67 倍 |
| 停顿数 | 6 / 6 / 8 | 极差 1.33 倍 |

### 5.2 LLM 侧：**回复文本每次都不一样**

同一句输入，三次回复分别是：

- 「诶，听到你这么说我也超开心！今天有什么好消息，愿意跟我分享吗？」
- 「诶，听你这么说我也很开心呀！今天有什么好事发生了吗？」
- 「诶，听你这么说我也超开心呀！今天是什么让你这么开心？」

⇒ **不能拿「上一次的回答」做断言基准**；人格一致性必须靠**人格包 + 评测集**，不能靠「上次是这么说的」。

### 5.3 ⭐ 旁证（证据等级较低，明确标注）

本轮在**写留痕日志之前**还发起过 4 次探索性调用，观测到时长 **5.631 / 5.666 / 5.712 / 8.139 s**。
⇒ 若把这 4 次也算进去，样本 7 次的极差是 **4.598 ~ 8.139 s（+77.0%）**。
⚠️ **这 4 次没有留原始日志文件**，按本仓的证据纪律只能算**旁证**，不作为结论依据。
**但它说明抖动可能远大于 3 次样本给出的 +32.6%** ⇒ §5.4 的三条约束必须按**最坏情况**设计。

### 5.4 这条发现对架构的三条硬约束

| # | 约束 | 理由（来自上面的实测） |
|---|---|---|
| 1 | **关键帧必须由「本次合成的实际 PCM」实时编译** | 时长差可达 1.5 s（最坏可能 3.5 s）⇒ 任何预烘焙/预录的关键帧序列都会与实际语音错位 |
| 2 | **不能把「预计时长」写进任何对外承诺、缓存键或 UI 文案** | 同一个输入两次请求拿到的是**不同长度**的音频与不同帧数 |
| 3 | **「音画对齐」的判据必须是相对时间轴，不是绝对时间点** | 帧数随音频变（115 / 144 / 153 / 152 / 187）⇒ 对齐只能在「同一份 PCM 的时间轴」上成立 |

### 5.5 顺带说明为什么我们坚持「关键帧驱动切法」

`tools/audio_chunk.py` 的切法是**以关键帧为栅格**切 PCM（`framesPerChunk=4` ⇒ 160 ms/片）。
正因为关键帧随每次合成的音频变，**切片的片数也会变** —— 这是设计预期，不是 bug；
规格 `docs/spec/07` §3.6.1 里「2350 ms ⇒ 15 片」这类数字只能当**示例**，不能当契约。

---

## 六、未验证清单

| 项 | 状态 |
|---|---|
| **真机**收到并执行这批 `0x14` 帧 | ❌ **未验证** —— 这里用的是 `DeviceSimulator` |
| 设备端舵机实际转动与限位余量 | ❌ **未验证** —— 限位只是源码事实，没有真机行程实测 |
| 音频在 iOS 上播放、与动作同步 | ❌ **未验证** —— 本仓还没有 App 侧音频播放实现（Q10 未拍板） |
| MiniMax 计费与配额消耗 | ⚠️ 未知 —— 本轮共发起 **5 次**真实调用（3 次流水线 + 2 次全链路） |
| 网络抖动下的表现 | ⚠️ 本机回环，无抖动 |
| TTS 抖动是否**每次**都出现 | ⚠️ 仓内留痕样本量 **3 次**；另有 4 次无留痕旁证 ⇒ **只能说「出现过 +32.6% 的抖动」**，不能断言分布 |
| LLM 回复的不确定性对人格一致性的长期影响 | ❌ **未验证**（需多轮会话评测） |

---

## 七、复现步骤

```powershell
$env:PYTHONIOENCODING='utf-8'
$repo='D:\jss18\AI\StackChan-main'
Set-Location $repo

# 1) 仅流水线（不联网到设备侧）
py -3.12 server\run.py --text "今天真开心啊，见到你真好。" --provider minimax

# 2) 全链路（云端 + 设备模拟器 + App 模拟端）
py -3.12 server\run.py --demo --provider minimax --text "今天真开心啊，见到你真好。"

# 3) 不可复现性验证：同文本连跑 3 次
1..3 | ForEach-Object { py -3.12 server\run.py --text "今天真开心啊，见到你真好。" --provider minimax }
```

> 🔑 `MINIMAX_API_KEY` 只从**用户级环境变量**读，**不入库、不回显**（日志里显示为 `key=***`）。
> 没有 key 时自动退回离线 `stub` provider，**整条链路照样跑得通**（含真实音频合成）。

---

## 八、溯源

| 结论 | 来源 |
|---|---|
| 帧数公式 `ceil(秒 × 25)` / `OUT_DT_MS = 40` | `tools/prosody_to_motion.py` |
| `0x14` 不带 MAC 前缀 | `server/stackchan_ai/server.py`；官方 `web_socket.go:740-746`（`docs/research/53`） |
| yaw 限位 ±128.0° | 固件源码实测（`docs/spec/00` O-11） |
| provider 抽象与错误码分类 | `server/providers/base.py`；`docs/research/60` |
| 人格包 `personas/enfp.json` | `docs/spec/07` §二（三层结构） |
| 本文件引用的全部原始输出 | [`runs/20261025-0640-e2e-minimax.log`](runs/20261025-0640-e2e-minimax.log) |
