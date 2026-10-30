# 58 · iOS 端架构决策（原生 SwiftUI，从零写）

> 日期：2026-10-24
> 定位：把 `docs/spec/03` §5 的 10 项预设 + `docs/spec/04` §4 的 8 条留存机制 + §5.7 的冷启动方案，**落成具体的 iOS 架构决策**
> 输入依据：03 号（协议与链路）、04 号（护城河与留存）、05 号（技术选型）、41 号（端侧能力与隐私分层）、42 号（iOS 26 能力）、53 号（表情/动作通道边界）
> 标注约定：`[已核实]` = 官方文档或源码实证｜`[自研设定]` = 我们自己定的设计｜`[未验证]` = 需真机

---

## §0 一句话结论

**中国大陆的端侧能力比预想的多**：Apple 官方 Core AI 文档明写这套路径就是为「**不支持 Apple Intelligence 的设备**」设计的 ⇒ **端侧语言能力可用**，不可用的只有 Apple 自家的端侧大模型与私有云。
⇒ iOS 架构定成**三个正交状态 + 双轨表情渲染 + 单出口隐私网关 + 端侧语义走 Core AI**。

---

## §1 ⭐ 端侧能力矩阵：大陆到底还剩什么（解决 41 号遗留）

### 1.1 裁定

| 能力 | 大陆可用 | 依据 |
|---|---|---|
| **Apple Vision**（人脸/人体姿态/3D 姿态/手部姿态/人矩形/人像分割/显著图/光流/跟踪/OCR/分类） | ✅ **可用** | `[已核实]` Vision 框架文档（`developer.apple.com/tutorials/data/documentation/vision.json`）**未声明任何 Apple Intelligence 前置条件**；它是独立系统框架，Swift-only API 自 iOS 18.0 起提供 |
| **Core ML / Create ML**（自训分类器） | ✅ **可用** | `[已核实]` Core ML 是标准 ML 框架，与 Apple Intelligence 无关 |
| **Core AI 导出的开源模型（~0.6B）跑在 Foundation Models 会话里** | ✅ **可用** | `[已核实]` Apple 官方文档原文：**"Support a range of devices that might not support Apple Intelligence."**；"Running and integrating a Core AI model requires macOS 27, iOS 27, and…"；"Choose a model around **0.6B parameters** as a good first choice because it downloads quickly and runs comfortably on device" |
| **AVFoundation / SoundAnalysis**（音频采集、特征、韵律分析） | ✅ **可用** | `[已核实]` 系统媒体框架，不依赖 Apple Intelligence |
| **`LanguageModelExecutor` + 自定义 provider**（接 MiniMax） | ⚠️ **未验证** | `[已核实]` `LanguageModelExecutor` 文档：*"An executor is the bridge between the framework types and the system that actually generates the tokens, like a **server API** or a local inference engine."*；**文档未说明自定义 provider 是否受 Apple Intelligence 地区限制** ⇒ 必须真机实测 |
| `SystemLanguageModel`（Apple 端侧大模型） | ❌ **不可用** | `[已核实]` Apple 支持页原文：Apple Intelligence 特性"will **not currently work** for supported devices purchased in China mainland"（41 号 §2.2） |
| `PrivateCloudComputeLanguageModel` | ❌ **不可用** | `[已核实]` PCC 需要"支持 Apple Intelligence 的设备"（41 号 §2.2 结论 3） |

### 1.2 两条关键推论

**推论 1（架构）**：Foundation Models 框架**不是不能用，是不能用 Apple 自带的那两个模型**。
⇒ 我们用它的**会话/工具/结构化输出抽象**，但**模型提供方换成两个**：
- 端侧：**Core AI 导出的 ~0.6B 开源模型**（零出网）
- 云端：**MiniMax**（经 `LanguageModelExecutor` 自定义 provider，走 OpenAI 兼容 `/v1/chat/completions`）

**推论 2（叙事）**：Apple 官方那句话反过来成了我们的**隐私叙事资产** —— "我们的端侧模型跑在**连 Apple Intelligence 都用不了的设备**上" 是可验证的、对外可讲的硬事实，不是营销词。

### 1.3 Core AI 路线的现实代价（必须写进风险）

| 项 | 事实 | 影响 |
|---|---|---|
| 导出工具链 | Core AI 导出需要 **macOS 27 + iOS 27** 环境 | `[未验证]` 本机无 Mac ⇒ 导出必须走 CI（macOS runner）或借机 |
| 模型要**按设备分别导出** | 官方原文："Because models are specialized to the device they run on, you need to export a model for…" | `[自研设定]` 首发只支持 1~2 款机型，不承诺全机型 |
| 参数量 | 官方建议 **~0.6B** 起步 | `[自研设定]` 0.6B 只够做**意图分类 / 槽位抽取 / 情绪标注 / 短摘要**，**不做长对话** |
| 大陆账号是否被框架层拦截 | **官方文档无任何说明** | `[未验证]` 必须真机测；**不能靠推断下结论** |

---

## §2 模块边界（Swift Package 切分，不是文件夹约定）

`[自研设定]` —— 41 号 §5.3 的风险提示：**靠命名约定隔离个人数据会被一次 review 疏忽破掉**，所以用 module 边界隔离。

| Package target | 职责 | 允许依赖 | ⭐ 硬约束 |
|---|---|---|---|
| `CoreProtocol` | 消息类型、帧格式、JSON schema（0x03/0x04/0x07/0x14/0x1B…） | 无 | **不依赖任何 target**；所有 JSON 有 schema 校验 |
| `CoreState` | `ConnectionState` / `AgentStage` / `ExpressionState` 三个状态机 | `CoreProtocol` | 纯值类型，无 IO |
| `AgentCore` | 人格包、提示词模板、情绪→表情映射、动作编译 | `CoreProtocol` `CoreState` | **不含任何个人数据** |
| `PersonalStore` | 私人层：档案、记忆原文、日期锚点、关系年鉴 | 无 | **只读本地**（SwiftData/SQLite/Keychain）；**永不同步**；不被 `CloudGateway` 引用 |
| `LocalLLM` | Core AI 端侧模型、MLX/llama.cpp、Vision 感知、韵律特征 | `CoreProtocol` | **零出网**（CI 用 `URLProtocol` 桩断言） |
| `CloudGateway` | ⭐ **唯一出网出口**：MiniMax、遥测、WS 服务端 | `CoreProtocol` | **唯一允许发起网络请求的 target** |
| `AppUI` | SwiftUI 视图、Live Activity、App Intents、Widget | 全部 | **不直接持有网络客户端**；只通过 `CloudGateway` / `LocalLLM` |

> ⚠️ **红线**：`PersonalStore` 与 `CloudRequestBody` **必须分属不同 target**。`CloudRequestBody` 的 `Encodable` 合成代码里**不存在**个人记忆字段 ⇒ 类型系统层面不可能序列化上去。

---

## §3 三个正交状态（不要混成一个枚举）

`[自研设定]`

| 状态机 | 取值 | 来源 | UI 呈现 |
|---|---|---|---|
| `ConnectionState` | `disconnected` / `connecting` / `connectedDeviceOffline` / `connectedDeviceOnline` / `permissionPending` / `error` | 03 号 §4.1 六态 | 状态条（**不弹窗、不打断对话**） |
| `AgentStage` | `stranger` / `probing` / `familiar` / `dependent` / `distant` / `reunion`（离散，**不是分数**） | 04 号 §3 / P3 | ⭐ **完全不出现在 UI**（红线：不做积分·等级·进度条）；只影响服务端行为参数 |
| `ExpressionState` | 当前表情参数（3 元素 × 5 参数）+ 目标姿态 + 生效剩余时间 | 53 号 §3 | 小栈形象区 + 动作胶囊 |

**为什么必须正交**：
- 连接断了 ≠ 关系断了（`ConnectionState` 与 `AgentStage` 互不影响）
- 表情 ≠ 情绪（设备只有 6 种情绪 + 连续参数；`ExpressionState` 存的是**参数**，不是情绪标签）
- `AgentStage` 不上 UI ⇒ 用户看不到「等级」，只感到「它对我不一样了」——这正是 M1–M8 的实现前提

---

## §4 ⭐ 双轨表情渲染：「设备是身体，App 是镜子」

### 4.1 事实基础

`[已核实]` 53 号 §3–§5：
- 设备端表情通道（0x13）**只认 3 元素 × 5 字段**，**撑不过 2 秒**（被 blink/idle/breath 覆盖）
- 设备端动作通道（0x14）是一条**关键帧时间轴**，脸 + 脖 + **双 RGB 灯**，**绕过 modify lock**
- 设备端情绪**只有 6 种**（Neutral/Happy/Angry/Sad/Doubt/Sleepy），**不可远程设置**

### 4.2 决策

`[自研设定]`

| 轨道 | 渲染在哪 | 能表达什么 | 保真度 |
|---|---|---|---|
| **设备轨（身体）** | 设备上的 320×240 屏 + 舵机 + 12 灯 | 官方 6 情绪 + 连续参数 + 0x14 时间轴 | **低但真实**：在物理空间里、会被摸到、会自己动回去 |
| **App 轨（镜子）** | iPhone 上我们自写的 SwiftUI/Canvas 表情渲染器 | **任意表情**（我们不受 6 情绪 / 5 参数限制） | **高但只是影子**：是记忆的投影，不是设备真值 |

### 4.3 为什么这是护城河的一部分（不是花活）

`[自研设定]` 接 04 号 §3.6 第 6 条（设备即档案）：

> **设备上的表情是稀疏采样，手机上的是连续记录。**
> 设备每 2 秒被自己的动画覆盖一次 —— 这意味着**设备的表情本身是不可信的记录**；
> 而 App 端完整、连续、可回看、可导出、可审计 ⇒ **关系档案必须建在 App 端，设备端只是「当下的身体」**。

⇒ 这条同时解释了两件事：
1. 为什么档案永不入库也不该入库 —— 它本来就在用户自己的 iPhone 上，是**设备即档案**的极端形态；
2. 为什么 App 端必须有一个**自己的表情渲染器** —— 它不是 UI 装饰，它是**档案的显示层**。

### 4.4 实现约束

| 约束 | 内容 |
|---|---|
| 渲染器参数化 | 复用设备端同一套 5 参数语义（x/y/rotation/weight/size），让 App 与设备**说同一种语言** |
| 设备侧保活 | 0x13 表情下发后按 **< 2000 ms** 周期重发（53 号 §4.3），由后端 `ExpressionKeepAlive` 负责（05 号 P0-5） |
| 不伪造设备状态 | App 端的表情是**「它想表达什么」**，设备端是**「它现在长什么样」** —— 文案必须区分，不能混称「实时姿态」（05 号 §3 裁决） |
| 离线可看 | 设备离线时 App 端表情轨**照常工作**（读本地档案），只有设备轨失效 ⇒ 降级态不空屏（03 号 §5 第 9 条） |

---

## §5 Live Activity 放什么

`[已核实]` 42 号 §二第 7 条：Live Activity **4 KB 数据上限 + 8 小时活动上限 + 12 小时锁屏上限**，且 **Live Activity 无网络权限**。

`[自研设定]`

| 内容 | 放不放 | 理由 |
|---|---|---|
| 状态词（监听中 / 思考中 / 说话中 / 等你回来 / 离线） | ✅ **放** | 状态词就是内容，4 KB 绰绰有余 |
| 对话正文 | ❌ **不放** | 红线「不显示敏感内容」；且 Live Activity 会被锁屏暴露 |
| 情绪标签 | ❌ **不放** | 情绪不是用户该被提醒的东西（对照 Loona 的 No Commentary 边界） |
| 设备姿态角 | ❌ **不放** | 我们只有乐观值（05 号 §3 裁决）⇒ 放了就是撒谎 |

- 样式：`ActivityStyle.transient`（iOS 26）用于「小栈思考中」这类**短时状态** —— 只在灵动岛扩展区存在，收起即结束，不在锁屏堆积 `[已核实，42 号 §二第 6 条]`
- 刷新链路：状态变化 → `Task { }` 甩出去，**绝不在 `onChange` 闭包里同步调 ActivityKit**（会掉帧）`[自研设定]`
- 触感：同一次状态变化 = 一次交互 = **最多 1 次触感** → `.sensoryFeedback(_:trigger:)` 声明式触发 `[已核实，42 号 §四]`

---

## §6 App Intents：让 Siri 直接跟小栈说话

`[已核实]` 42 号 §二第 8 条：App Intents + `AppShortcut` + `AppShortcutsProvider` 可让 **Siri / 快捷指令 / Spotlight** 直接调 App Intent；App Shortcut 装 App 即生效、**不需要注册**。

`[自研设定]` 我们要暴露的 5 个 Intent：

| Intent | 作用 | 隐私注意 |
|---|---|---|
| `TalkToStackChan` | 把一句话交给小栈（走同一套路由判定） | **必须走 `CloudGateway`/本地路由**，不得绕过敏感词判定 |
| `AskStackChanToLookAtMe` | 请求它转过来（**只发 0x04 目标角**，不承诺它真转了） | 无 |
| `RecallStackChanMemory` | 问「它记得我什么」 | ⭐ **只能查 `PersonalStore` 本地**，不得回传云端 |
| `SetStackChanQuietUntil` | 设置勿扰时段 | 本地 |
| `ExportRelationshipArchive` | 导出关系年鉴（默认脱敏） | 本地文件 |

⚠️ `RecallStackChanMemory` 是**最容易破隐私红线的一个**：它是「个人数据出网」的天然入口 ⇒ 它的实现必须落在 `PersonalStore` 内、**不经过 `CloudGateway`**。

---

## §7 隐私路由落到代码结构

`[已核实]` 41 号 §5.3 的六条硬约束 + 四条 CI 测试，此处只做**落位**：

| 约束 | 落在哪个 target | CI 测试 |
|---|---|---|
| ① 单一出口 | `CloudGateway` 是唯一持有 `URLSession` 的 target | `testEgressOnlyFromCloudGateway` |
| ② 类型级白名单 | `CloudRequestBody`（在 `CloudGateway` 内）与 `PersonalStore` 不同 target | `testNoPersonalDataInCloudPayload` |
| ③ 工具边界 | 切云端时**重建 session，工具集合置空** | `testNoPersonalDataInCloudPayload` |
| ④ 只读本地存储 | `PersonalStore` 无同步 API | `testServerRejectsPersonalFields` |
| ⑤ 审计 ≠ 内容 | 只留 `route`/`intentClass`/`payloadByteCount`/`payloadHash`/`personaVersion`/`latencyMs` | — |
| ⑥ CI 可跑 | 注入 `URLProtocol` 桩 | `testNoEgressFromLocalLayer` |

### 7.1 路由判定（单一决策点，顺序不可调换）

`[自研设定]` 接 41 号 §5.2：

```
1. 端侧模型可用？（Core AI 模型已加载 / MLX 已加载）→ 否：走 MiniMax（UI 明示「已联网」）
2. 本轮请求命中敏感类别？→ 是：端侧作答，不出网
3. 需要长上下文 / 复杂推理 / TTS？→ 是：MiniMax；否：端侧
```

**两个陷阱（41 号已指出，此处定死）**：
- 本地判定**不能只靠关键词** —— 边界由「**本轮请求携带的字段**」决定，不是「用户说了什么」
- 切到云端**不能把本地上下文整包带上** —— 路由决策要产出「**云端可见视图**」（`localSummary` 是本地模型生成的摘要，非原文）

---

## §8 03 号 10 项预设 → iOS 组件落位

| # | 预设项 | iOS 落位 |
|---|---|---|
| 1 | 服务器地址 | `Settings` 独立 Scene；开发/生产切换；**不出现在主界面** |
| 2 | App ↔ 设备身份 | `deviceId` 由后端签发 → `Keychain` 存 token；`CoreProtocol` 负责拼 `MAC(12B ASCII)` 前缀 |
| 3 | 配对流程 | 首次启动页；二维码/NFC（52 号：NFC 只搬公开层，配对用二维码更稳） |
| 4 | 消息类型子集 | `CoreProtocol` 只实现 `0x03/0x04/0x07/0x14/0x1B/0x10/0x11/0x12/0x18/0x19`；**过滤 `0x15/0x16/0x17`**（设备不实现，53 号 §8.6） |
| 5 | 表情参数映射 | `AgentCore` 的 `EmotionMapper`：我们的情绪 → 官方 6 枚举 → 15 维参数；**装饰器单独一层**（官方装饰器不走远程通道） |
| 6 | 动作语义表 | ⭐ **动作由服务端编译成 0x14 关键帧**（55 号方案），App 只发目标角/序列，不本地算轨迹 |
| 7 | 数据上传边界 | `onCamera` **默认关**；麦克风按需；`CloudGateway` 单出口可审计 |
| 8 | 本地存储 | `PersonalStore` 只读本地 + 导出/清空入口；**永不同步** |
| 9 | 断线行为 | `ConnectionState` → `connectedDeviceOffline`：**收起设备入口，不报错、不禁用聊天** |
| 10 | 后台行为 | 后台切服务器中转；回前台重连 + 重切 LAN；**静默无 UI 变化** |

---

## §9 04 号 8 条留存机制 → iOS 组件落位

| 机制 | iOS 落位 | ⭐ 红线检查 |
|---|---|---|
| **M1 档案在长厚** | 「小栈」Tab 的档案时间线 | **只展示条目本身，不展示计数**（「本周新增 12 条」绝对不做） |
| **M2 它先开口** | App 内顶部**轻量提示条**（不是弹窗）；或 `ActivityStyle.transient` 灵动岛 | 勿扰时段 + 主动降频；**「它今天没话说」是合法状态** |
| **M3 身体先说话** | 设备轨（真转头）+ App 轨（影子表情同步） | 冷却 + 节流 + 两段式（先转头→确认→决定是否继续） |
| **M4 它拒绝我** | 对话流内的**明确拒绝**，不是错误态 | **拒绝必须由状态驱动，不能是随机台词** |
| **M5 默契** | 不上 UI；只体现在「它没打断我」 | 不学口头禅 |
| **M6 串门（NFC）** | `ExportPersonaCard` / `ImportPersonaCard` Intent + 二维码备份通道 | **卡片必须签名；私人层绝不经 NFC**；串门记忆独立成层 |
| **M7 它今天做了一件事** | 「小栈的一天」流（接 03 号 §6 的 `device_post` 改造） | **每条必须与关系有关，否则删掉** |
| **M8 关系年鉴** | 导出页 + 时间线视图 | **导出默认脱敏** |

---

## §10 端侧韵律分析放哪（接 54 号 / 55 号）

`[自研设定]` —— 依据 53 号的通道边界与 54 号的可行性结论（**结论以 54 号为准，此处只定落位原则**）：

| 候选 | 判断 | 理由 |
|---|---|---|
| ⭐ **服务端算韵律 → 直接编译成 0x14 下发** | ⭐ **首选（已订正）** | ① **服务端同时握着用户上行 PCM 与 TTS 下行 PCM**（31 号目标架构：PCM 16 kHz 单声道 / 60 ms 帧）——**我们要合成的语音，其韵律就是设备该表达的身体语言**，这是最精确的信号源；② 05 号 P0-6「关键帧动作合成器」本来就在服务端 ⇒ **零固件改动、零 App 改动、零协议改动**（韵律只作服务端内部编排输入）；③ 54 号实测：**Apple 侧无任何内置音高 API**，esp-sr 全树也**零 F0 提取**（只有响度 `data_volume` 与停顿 `vad_state`）⇒ 端侧本来就没有现成韵律源 |
| iPhone 端算韵律 | **备选** | 若要做到「本地不上传音频」才可用；但我们已用 TTS 下行 PCM 做代理信号，**不需要上传用户语音** ⇒ 隐私成本更低 |
| 设备端（ESP32-S3）算韵律 | ❌ **不做** | ① 05 号红线 1「不改固件」⇒ ESP32-S3 上**没有我们代码的载体**；② esp-sr 官方只有响度与停顿，**没有 F0**；③ 官方 AFE 字段只在固件进程内，外部读不到 |
| 把用户语音上云算韵律 | ❌ **不做** | 韵律是**最像「情绪」的隐私数据**，上云即破「本地感知」叙事，且与「设备即档案」互斥 |

⇒ **架构上预留**：设备协议只需一条「0x14 关键帧」通道，**韵律从哪算都不改协议** ⇒ 这是把韵律放在**服务端**的最大好处（协议不泄漏实现位置，App 零改动，固件零改动）。

---

## §11 待验证项

| # | 待验证 | 方法 |
|---|---|---|
| 1 | `LanguageModelExecutor` + 自定义 provider 在**大陆账号**下能否实例化 | 真机（**官方文档无说明，不能推断**） |
| 2 | Core AI 导出的 ~0.6B 模型在目标 iPhone 上的实际延迟与内存 | 真机 + Instruments |
| 3 | Core AI 导出流程能否完全在 **CI（macOS runner）** 上跑通 | CI 实跑 |
| 4 | Vision 的 `DetectHumanBodyPose3D` / 显著图在**非 Apple Intelligence 设备**上是否可用 | 真机（文档未声明前置条件，但未实测） |
| 5 | `ActivityStyle.transient` 在灵动岛的实际停留表现 | 真机 |
| 6 | App Intents 在后台被唤起时的连接状态处理 | 真机 |

---

## §12 文末自查

| 项 | 状态 |
|---|---|
| 每条能力裁定是否有官方依据 | ✅ Vision / Core AI / SystemLanguageModel / PCC 四条都有 Apple 官方文档原文；`[未验证]` 的 2 条已显式标注 |
| 是否区分了「已核实 / 自研设定 / 未验证」 | ✅ 全文三档标注 |
| 是否与 03/04/05 号冲突 | ✅ 协议语义沿用 53 号；留存机制沿用 04 号；模块划分沿用 05 号 §2.1 三条红线 |
| 是否守住隐私红线 | ✅ `PersonalStore` 与 `CloudGateway` 物理隔离（不同 target）；6 条硬约束 + 4 条 CI 测试落位 |
| 是否守住「不做积分/等级」红线 | ✅ `AgentStage` 明确不上 UI |
| 是否引入新协议 | ✅ 无 —— 复用官方 24 MsgType，只过滤设备未实现的 3 个 |
| 待验证项是否诚实标注 | ✅ 6 条，全标 `[未验证]` 并写明验证方法 |

**交叉引用**：`docs/spec/03`（协议）、`docs/spec/04`（护城河与留存）、`docs/spec/05`（技术选型与红线）、`docs/research/41`（端侧能力与隐私分层）、`docs/research/42`（iOS 26 能力）、`docs/research/53`（表情/动作通道）、`docs/research/54`（韵律可行性）、`docs/research/55`（插值与映射）。
