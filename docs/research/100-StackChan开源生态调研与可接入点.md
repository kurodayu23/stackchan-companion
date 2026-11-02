# 100 · StackChan 开源生态调研与可接入点

> 调研时间：2026-10-30 ｜ 方法：GitHub API 检索 + 逐仓库 README / 关键源码实读
> 触发：用户要求「必须搜索相关的开源项目，思考怎么接入机器人」
> ⚠️ 事实与判断分栏：标「事实」的有 URL 可复核；标「判断」的是我基于实读的推论，可推翻。

---

## 一、生态全景（GitHub 检索结果，按星数）

| 项目 | ★ | 定位（事实，取自仓库 description） | 与本项目关系 |
|---|---|---|---|
| [`stack-chan/stack-chan`](https://github.com/stack-chan/stack-chan) | 1832 | "JavaScript-driven M5Stack-embedded super-kawaii robot"（Moddable JS 固件 + Web 工具集） | ⭐ **官方原始项目**，Web 工具集最全 |
| [`m5stack/StackChan`](https://github.com/m5stack/StackChan) | 1457 | "StackChan open source!"（本仓库的上游厂商版） | 本仓库上游 |
| [`kisaragi-mochi/stackchan-mcp`](https://github.com/kisaragi-mochi/stackchan-mcp) | 167 | "MCP gateway for StackChan (xiaozhi-esp32)" | MCP 接入 |
| [`ronron-gh/AI_StackChan_Ex`](https://github.com/ronron-gh/AI_StackChan_Ex) | 158 | 基于 robo8080 的 AI 服务扩展版 | 固件侧参考 |
| [`robo8080/M5Unified_StackChan_ChatGPT`](https://github.com/robo8080/M5Unified_StackChan_ChatGPT) | 155 | ChatGPT API 版 StackChan | 固件侧参考 |
| [`robo8080/AI_StackChan2`](https://github.com/robo8080/AI_StackChan2) | 152 | AI_StackChan2 | 固件侧参考 |
| [`BrettKinny/dotty-stackchan`](https://github.com/BrettKinny/dotty-stackchan) | 121 | 自托管语音栈（xiaozhi-esp32-server + pi agent） | ⭐ **后端/隐私设计可借** |
| [`migratorywhale/stackchan-mcp`](https://github.com/migratorywhale/stackchan-mcp) | 98 | "Give your AI a body. MCP bridge" | MCP 接入 |
| [`zziying/stackchan-openapi`](https://github.com/zziying/stackchan-openapi) | 91 | **"Turn StackChan into a WiFi-controlled robot with HTTP API"** | ⭐ **与本项目架构最同构** |
| [`uezo/AIAvatarStackChan`](https://github.com/uezo/AIAvatarStackChan) | 64 | AIAvatarKit 驱动的语音交互框架（含 lip sync） | ⭐ **口型/表情同步可借** |
| [`m5stack/StackChan-BSP`](https://github.com/m5stack/StackChan-BSP) | 59 | Arduino 板级支持包 | 固件侧 |
| [`ciniml/stackchan-idf`](https://github.com/ciniml/stackchan-idf) | 48 | ESP-IDF 固件 | 固件侧 |
| [`Corvelis/stackchan-pet-fw`](https://github.com/Corvelis/stackchan-pet-fw) | 42 | 宠物化情感固件 | 固件侧 |

**判断**：社区生态**没有任何一个项目**做「手机 Web + 3D 模型 1:1 镜像 + 摇杆」这套交互——与我们此前 `docs/research/48` 的竞品扫描结论一致。
最接近的是 `stack-chan/stack-chan` 的 Web 工具集（但它服务的是**开发者刷机与 MOD 编辑**，不是日常遥控）。

---

## 二、逐项剖析：能从它们身上拿什么

### 2.1 `stack-chan/stack-chan` 的 Web 工具集（最有价值）

**事实**：`web/` 目录结构（GitHub contents API 实读）：

```
web/
├── editor/        MOD 应用编辑器
├── face-editor/   表情编辑器
├── flash/         Web 固件刷写器（WebSerial）
├── simulator/     ⭐ 设备模拟器（含 geometry.mjs / bridge.mjs）
├── local-peer/    ⭐ ble-local-peer.mjs（浏览器 BLE 直连，555 行）
├── mediapipe/     手势/人脸检测
├── mod-gallery/   MOD 应用库
├── i18n.mjs       国际化
└── src/entries/home.tsx   React + TS + Vite（index.html 实读）
```

**可直接接入的两个模块：**

#### ① `web/simulator/geometry.mjs` —— 官方真实几何（327 行，实读前 55 行）

```js
STACKCHAN_FACE_MM  = { width: 54, height: 54, radius: 4, depth: 54, bevelThickness: 1.2 }
STACKCHAN_FOOT_MM  = { width: 24, height: 8, depth: 48, radius: 2, count: 2 }
M5STACK_CORE_MM    = { width: 54, height: 54, depth: 16, shellSeamOverlap: 6.2 }
STACKCHAN_SHELL_STL = { url: './assets/case/v1/shell.stl', frontOpeningWidthMm: 51.6, ... }
SCREEN_CANVAS = { width: 320, height: 240, aspectRatio: 4/3 }
```

**接入点**：我们 `prototype/mobile-v2/device-screen.html` 的模拟器目前用**估算比例**；改用官方 mm 真值后，
「脸占屏比例 / 边距 / 圆角」从「看着像」变成「按官方数算」。
（本仓库 `docs/research/96` 已有设备屏几何真值订正，两者可交叉验证。）

#### ② `web/local-peer/ble-local-peer.mjs` —— 浏览器 BLE 直连（555 行，实读前 55 行）

```js
SERVICE_UUID = '6e400001-b5a3-f393-e0a9-e50e24dcca9e'   // Nordic UART
RX_UUID      = '6e400002-...'  TX_UUID = '6e400003-...'
RECORD_MAGIC = 'SLB1'  FRAME_MAGIC = 'SLP1'
RECORD_HEADER_BYTES = 22  FRAME_HEADER_BYTES = 18  FRAME_BYTES = 234
GATT_CHUNK_BYTES = [244, 60, 20]        // MTU 256 → 回退 60 / 20
AUTH_DOMAIN = 'stackchan-local-peer-auth-v1:'           // 带认证
RecordKind = { HELLO: 1, DATA: 2 }
FrameKind  = { DISCOVER: 1, ANNOUNCE: 2, DATA: 3, ACK: 4 }
FrameFlag  = { RELIABLE: 1, BROADCAST: 2 }
```

**判断（重要）**：这是**浏览器 ↔ 设备的 BLE 直连**，不经过任何后端。
- 优点：局域网不可用也能控；延迟低。
- 局限：**iOS Safari 不支持 Web Bluetooth** ⇒ 对「朋友用 iPhone」这条路无效（与 `docs/research/90` 的结论一致）。
- **接入点**：作为**桌面 Chrome/Edge 的直连兜底**（比如电脑连不上 Wi-Fi 时），
  或在 Android 上作为主通道。协议已现成，接线成本约 1 天。

#### ③ `web/flash/` —— Web 固件刷写（WebSerial + esptool-js）

**接入点**：以后做「设备管理页」时直接复用，不必自己写 WebSerial 时序。

### 2.2 `zziying/stackchan-openapi`（91★）—— 架构同构验证

**事实**（README 实读）：

```
主机电脑 Host (Mac/PC/RPi)          StackChan (ESP32-S3)
  你的 AI/应用/脚本  ──HTTP──▶  HTTP API Server（ESP32 上）
  find_face.py / face_tracker.py / speak.py
```
> "All AI/ML computation runs on a host computer — the ESP32 only handles the hardware."
> 硬件：GC0308 摄像头、双麦、扬声器、2 舵机（yaw ±128°、pitch 0-90°）、3 区触摸、320×240 屏

**判断**：**这就是我们旧项目 17865 的同一条路线**（Wi-Fi HTTP 主机计算 + 设备只做硬件）。
它独立存在且被使用，说明「手机 Web 遥控」这条路**是社区验证过的**，不是我们瞎走。
- 差别：它把 HTTP API 跑在 **ESP32 上**（设备当 server）；我们是**主机当 server**（设备当 client）。
  两者都可，但**主机当 server 更适合「一个后端服务多端（手机/桌面/语音）」**。
- **接入点**：它的 API 端点划分（servo / face / camera / audio）可以作为我们 `server/` 路由命名的参考。

### 2.3 `BrettKinny/dotty-stackchan`（121★）—— 隐私与状态机

**事实**（README 实读）：

| 设计 | 原文要点 |
|---|---|
| **Kid Mode** | 人设 + 系统提示 + **屏蔽词过滤**（"a blocked-words filter replaces a matching LLM reply before it is spoken"） |
| **6 状态 + 2 开关** | `idle / talk / story_time / security / sleep / dance` + `kid_mode` / `smart_mode`，由固件 StateManager 持有，12 像素 LED 环显示 |
| **Privacy sleep** | 睡眠态**关掉人脸检测 / 语音处理 / 唤醒词**，只有摸头或显式状态切换能唤醒（"not a hardware power cut" 诚实标注） |
| **流式回复** | "streams the model's reply into TTS sentence by sentence, so Dotty starts talking before the whole answer is written" |
| **表情约定** | "every reply starts with an emoji that the firmware turns into a face"（9 种 face） |
| 技术栈 | `bridge/` = Python + Jinja2 模板 + Tailwind（dashboard.html / face.html / state.html / memory_list.html …） |

**接入点**：
1. **6 状态机**比我们 `spec/00` 的情绪枚举更粗但**更适合固件实现**（状态少 = LED 环能表达）；
2. **privacy sleep = 关传感器而不是关机**，这个措辞与实现都值得抄进我们的隐私文案；
3. **「回复首字符是表情编码」**是个极简协议（比我们的 42 参数关键帧轻），可作**降级通道**。

### 2.4 `uezo/AIAvatarStackChan`（64★）—— 口型同步

**事实**：AIAvatarKit 配对；"expressions, automatic blinking, and mouth animation synced to speech (lip sync)"。

**接入点**：我们 `server/stackchan_ai/prosody.py` 已有能量通道 ⇒ **嘴部开合**可直接由能量驱动（lip sync 的简化版），
这正是 `docs/research/88` 测出「能量→嘴」SNR 0.19 的那个通道。它给了我们一个**外部实现佐证**：
社区确实用能量做嘴形，但也没解决「情绪淹没」问题（与 88 号结论一致，不算反驳）。

### 2.5 MCP 两个项目（167★ / 98★）

**事实**：`kisaragi-mochi/stackchan-mcp` = "MCP gateway for StackChan (xiaozhi-esp32): bridge any MCP client"；
`migratorywhale/stackchan-mcp` = "Give your AI a body. MCP bridge for Stack-chan (M5Stack CoreS3)"。

**判断**：这两个是**让 Claude/Cursor 等 AI agent 直接驱动机器人**（说话/转头/表情）。
**接入点**：如果我们 `server/` 暴露一个 MCP server（工具：`set_head` / `say` / `set_face` / `photo`），
就能让任何 MCP 客户端（包括本 DSH）直接操控小栈 —— **这是「自己再创造一个技术」的最短路径**，
而且是本仓库「作品集」定位的加分项（展示 agent 集成能力）。工作量估计 1 天（MCP Python SDK + 5 个工具）。

---

## 三、⭐ 与 mobile-v2 的对照：我们已经做对了什么 / 差什么

| 维度 | 社区最佳实践 | 我们 mobile-v2 现状 | 判断 |
|---|---|---|---|
| 控制通道 | Wi-Fi HTTP（openapi 91★）/ BLE 直连（stack-chan 官方） | Wi-Fi HTTP（同源代理 → 17865） | ✅ 同构，且代理层更严（CSRF/Origin/白名单） |
| 3D 姿态镜像 | 无项目做（stack-chan simulator 只做静态外观） | ⭐ **官方 GLB + setPose 1:1** | ✅ **领先**，这是我们的差异点 |
| 设备屏模拟 | 官方 `simulator/geometry.mjs`（mm 精确） | 估算比例 | ⚠️ **该抄官方尺寸** |
| 浏览器直连 | `ble-local-peer.mjs`（协议完整） | 无（只走 HTTP） | ⚠️ 缺兜底通道 |
| 聊天 | dotty（流式 + 表情首字符）/ AIAvatar（lip sync） | 纯文字 + 思考态 | ⚠️ 可加「首字符表情」降级 |
| 状态机 | dotty 6 状态 + LED | 未实现 | 待做（不在本轮） |
| AI agent 接入 | MCP 两个项目 | 无 | 💡 新机会 |

---

## 四、本轮实际落地（不只写文档）

| 项 | 状态 |
|---|---|
| 官方真实几何接入 device-screen 模拟器 | ✅ 已改（见 §五） |
| BLE 直连方案登记为二期 | ✅ 记在 mobile-v2 README §七 |
| MCP 接口提议 | 📋 记在本文 §2.5，待你拍板是否做 |

## 五、几何真值（已接入模拟器）

来自 `stack-chan/stack-chan web/simulator/geometry.mjs`（实读）+ 本仓库 `docs/research/96`：

| 元素 | 官方值 | 用途 |
|---|---|---|
| 脸（屏） | 54 × 54 mm，圆角 4 mm | 模拟器屏占比 |
| 屏画布 | 320 × 240（4:3） | 已一致 |
| 脚 | 24 × 8 × 48 mm × 2 | 底座比例 |
| CoreS3 机身 | 54 × 54 × 16 mm | 厚度参考 |
| 前开口宽 | 51.6 mm | 屏边距（±1.2 mm 边框） |

---

## 六、未取得 / 诚实边界

- GitHub API 未认证（60 次/小时限流），检索结果可能不全；未覆盖 GitLab / Gitee / 私有仓库。
- 只实读了 4 个仓库的关键文件（stack-chan web 的 2 个模块、openapi/dotty/AIAvatar 的 README），其余仅看 description。
- `web-search` 工具本轮**不可用**（API key 失效，HTTP 401），本轮检索全部走 **GitHub REST API + raw.githubusercontent.com**（本机网络直连）。
- 未验证这些项目在**真机**上的行为（只读代码/文档）。

## 七、溯源

| 结论 | 出处 |
|---|---|
| 生态清单与星数 | `https://api.github.com/search/repositories?q=stackchan&sort=stars`（2026-10-30 实取） |
| 官方 Web 工具集结构 | `api.github.com/repos/stack-chan/stack-chan/contents/web` |
| 真实几何 mm 值 | `raw.githubusercontent.com/stack-chan/stack-chan/main/web/simulator/geometry.mjs` |
| BLE 直连协议 | `raw.githubusercontent.com/stack-chan/stack-chan/main/web/local-peer/ble-local-peer.mjs` |
| HTTP API 架构 | `raw.githubusercontent.com/zziying/stackchan-openapi/main/README.md` |
| 状态机 / 隐私 sleep | `raw.githubusercontent.com/BrettKinny/dotty-stackchan/main/README.md` |
| lip sync | `raw.githubusercontent.com/uezo/AIAvatarStackChan/main/README.md` |