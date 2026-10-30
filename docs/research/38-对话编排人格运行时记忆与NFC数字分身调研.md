# 38 · 对话编排 / 人格运行时 / 记忆 / NFC 数字分身 —— 开源技术栈调研

> 状态：调研进行中（持续追加）
> 调研范围：为 StackChan 桌面陪伴机器人找齐「后端 + 人格可传播」所需的**可复用开源技术栈**
> 后端基座（已定）：fork 官方 M5Stack StackChan server（GoFrame v2 / Go 1.26.3 / MIT），替换认证层与 AI 层，自建后端跑在 `server/`，AI 层接 MiniMax
> 官方 server 基线：本地 clone `D:\jss18\AI\StackChan\StackChan2` 的 `origin/main`（`eff0d6b`），用 `git show origin/main:server/<path>` 读
> 取数纪律：所有事实必须有可点击 URL 或原文引用 + 文件路径行号；抓不到写「未取得」，严禁编造 star 数 / 版本 / 许可条款 / API 名

## 目录

- §一 结论摘要（**未完成**，待下一轮）
- §二 实时语音 Agent 编排框架评估
- §三 记忆层评估（逐项标注能否自托管）
- §四 角色卡格式规范与自定义人格包字段设计
- §五 人格运行时热切换设计
- §六 NFC 一碰换人格完整链路
- §七 声音克隆 / 数字分身（商用许可风险）
- §八 本地 LLM provider 与结构化输出
- §九 情绪 → 表情/动作语义标签体系
- §十 复用决策汇总（**未完成**，见 §11.1 U14）
- §十一 未取得与风险清单
- 文末自查

---

## §0 · 官方基线事实（先钉死，后续所有判断的锚点）

来源类型：**本地 git 原文**（`D:\jss18\AI\StackChan\StackChan2` 的 `origin/main` = `eff0d6b`，命令 `git show origin/main:<path>`）

### 0.1 官方 server 的「AI 层」真相 —— 不是自建 LLM，是 xiaozhi.me 的转发代理

- `server/internal/xiaozhi/xiaozhi.go:45-49` 常量表写死了上游：`baseUrl = "https://xiaozhi.me/"`，路径含 `api/developers/token`、`api/developers/agent-templates/list`、`api/user/tts-list`、`api/developers/devices`、`api/agents`、`api/chats/list`。
- `server/internal/xiaozhi/xiaozhi.go:60-83`：`init()` 起一个 24 小时 ticker，token 到期自动清空重取；`doRequest()` 统一带 `Authorization: Bearer <token>` 转发。
- `server/internal/model/xiaozhi/agent.go`、`server/internal/service/agent.go` 是对应的数据模型与服务层。
- `git grep -i -E "minimax|openai|anthropic|llm|chat/completions" origin/main -- server/` 仅命中 `server/internal/model/xiaozhi/agent.go`、`server/internal/service/agent.go`、`server/internal/xiaozhi/xiaozhi.go` 三个文件。

> **结论**：官方 server 的 AI 能力 = 「小智开放平台」的 REST 转发壳。我们 fork 后要换的「AI 层」就是这三处 + 固件侧的 WebSocket 协议对接层。本调研的所有方案都要能同时满足：**① 对固件暴露与官方一致的协议面**；**② 后端真正自持人格/记忆/编排状态**。

### 0.2 server 技术栈（逐行取数）

`server/go.mod:1-9`：

```
module stackChan
go 1.26.3
require (
	github.com/gogf/gf/contrib/drivers/mysql/v2 v2.10.0
	github.com/gogf/gf/v2 v2.10.2
	github.com/golang-jwt/jwt/v5 v5.3.1
	github.com/gorilla/websocket v1.5.3
)
```

- GoFrame v2 `v2.10.2`、MySQL driver `v2.10.0`、JWT v5、**gorilla/websocket v1.5.3**（→ 固件↔服务端的实时通道底座就在依赖里，替换 AI 层不需要换传输层）。
- `server/LICENSE` 存在；`firmware/LICENSE` 存在；固件源码头部统一 `SPDX-License-Identifier: MIT`（例：`firmware/main/stackchan/avatar/avatar/elements/emotion.h:1-6`）。

### 0.3 固件的第三方组件锁（决定「表情/动作从哪来」）

`firmware/repos.json`（原文全文 6 条）关键项：

| 依赖 | URL | 分支/版本 | 落位 |
|---|---|---|---|
| xiaozhi-esp32 | `https://github.com/78/xiaozhi-esp32.git` | **`v2.2.4`** | `firmware/xiaozhi-esp32`（构建期 clone，非 vendored） |
| mooncake | `https://github.com/Forairaaaaa/mooncake.git` | `v2.3.3` | `components/mooncake` |
| smooth_ui_toolkit | `https://github.com/Forairaaaaa/smooth_ui_toolkit.git` | `v2.12.0` | `components/smooth_ui_toolkit` |
| ArduinoJson | `https://github.com/bblanchon/ArduinoJson.git` | `v7.4.2` | `components/ArduinoJson` |

- `firmware/fetch_repos.py:1-30` 确认：构建时 `git clone` → `git checkout <branch>` → 应用 `firmware/patches/xiaozhi-esp32.patch`。
- `firmware/main/CMakeLists.txt`：`set(XIAOZHI_MAIN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../xiaozhi-esp32/main")`，并纳入 `display/lvgl_display/lvgl_display.cc`、`display/lvgl_display/emoji_collection.cc`、`device_state_machine.cc`、`assets.cc`。
- `firmware/main/idf_component.yml`：**`espressif2022/esp_emote_expression: ^0.1.0` 这一行是注释掉的**（`# espressif2022/esp_emote_expression: ^0.1.0`），说明官方**没有**采用该表情组件；表情资产走 xiaozhi-esp32 的 `emoji_collection.cc` + assets 分区。

> **结论**：300+ 表情/动作命名不在 `firmware/main/stackchan/` 里，而在 **xiaozhi-esp32 v2.2.4 的 `emoji_collection.cc`**（+ assets 分区）。这是我们做「情绪 → 表情/动作」映射时唯一的事实来源。

---

## §二 实时语音 Agent 编排框架评估

### 2.1 许可与形态（来源类型：**上游 LICENSE / README 原文**）

| 项目 | 许可 | 取数 |
|---|---|---|
| **pipecat-ai/pipecat** | **BSD 2-Clause**（"Copyright (c) 2024–2026, Daily"） | https://raw.githubusercontent.com/pipecat-ai/pipecat/main/LICENSE |
| **livekit/agents** | **Apache License 2.0** | https://raw.githubusercontent.com/livekit/agents/main/LICENSE |

### 2.2 关键发现：Pipecat **原生自带 MiniMax TTS 服务**

pipecat README 的「Available services」表（https://raw.githubusercontent.com/pipecat-ai/pipecat/main/README.md）逐字列出：

- **TTS 类别含 `MiniMax`** → `https://docs.pipecat.ai/api-reference/server/services/tts/minimax`
- TTS 另含 **Piper**、**XTTS**、**Fish**（Fish Speech 的 TTS 服务）、**Kokoro**
- **LLM 类别含 `Ollama`**、`OpenAI`、`DeepSeek`、`Mistral`、`Qwen` 等
- **Memory 类别含 `mem0`**（唯一列出的一个）
- Transport 类别含 `FastAPI Websocket`、`WebSocket Server`、`Local`、WebRTC 类（Daily / LiveKit / SmallWebRTC）
- 官方 Client SDK 列表里直接列了 **ESP32: https://github.com/pipecat-ai/pipecat-esp32**

> **含义**：我们要接的 MiniMax **恰好是 pipecat 官方支持的一等服务**，不需要自己写 service adapter —— 这把「接 MiniMax」的接入成本从「写插件」降到「填两个 key」。

### 2.3 但：pipecat 是 Python，与 Go 后端是**两种语言**

- pipecat 要求 **Python ≥ 3.11（推荐 ≥ 3.12）**（README "Developing Pipecat / Minimum Python Version"）。
- 我们的后端基座是 **Go 1.26.3 + GoFrame v2**，且已定「自建后端跑在 `server/` 目录」。
- 引入 pipecat 意味着：**Go 后端 + Python 实时编排进程**双栈，或把编排层整体搬到 Python。

### 2.4 MiniMax 是 Chat + TTS 两段式（非 Realtime），对编排框架意味着什么

- pipecat 的 **Speech-to-Speech**（真正的双向流式）类别里只有：AWS Nova Sonic、Azure Voice Live、Gemini Multimodal Live、Grok Voice Agent、OpenAI Realtime、Ultravox —— **不含 MiniMax**（README 表格原文）。
- 因此 MiniMax 只能走 pipecat 的 **两段式管道**：`STT → (LLM) → TTS`，这与我们的 MiniMax 形态一致。

---

## §三 记忆层评估（逐项标注能否自托管）

### 3.1 许可矩阵（来源类型：**上游 LICENSE 原文**）

| 项目 | 许可 | 取数 |
|---|---|---|
| **mem0ai/mem0** | **Apache License 2.0**（"Copyright [2023] [Taranjeet Singh]"） | https://raw.githubusercontent.com/mem0ai/mem0/main/LICENSE |
| **letta-ai/letta** | **Apache License 2.0**（"Copyright 2023, Letta authors"） | https://raw.githubusercontent.com/letta-ai/letta/main/LICENSE |
| **getzep/zep** | **Apache License 2.0** | https://raw.githubusercontent.com/getzep/zep/main/LICENSE |
| **langchain-ai/langgraph** | **MIT**（"Copyright (c) 2024 LangChain, Inc."） | https://raw.githubusercontent.com/langchain-ai/langgraph/main/LICENSE |

> 注：仓库地址经核对为 `letta-ai/letta`（非 `letta-ai/letta` 的历史名 `letta-ai/letta`）。zep 的仓库实际路径为 `getzep/zep`。

### 3.2 记忆模型类型 / 自托管形态 / 接入成本（逐项评）

> 原文引用均来自各项目 **README 原文**（已下载到 `D:\AP\AP7000\ai-workspace\stackchan-research\`）；来源类型：**上游 README 原文**。
> ⚠️ 本节最重要的发现是 **两个主仓在本轮已发生形态变化**（letta 主仓变 stub、zep 主仓只剩 examples），直接改变了记忆层选型结论。

#### 3.2.1 mem0ai/mem0 —— 唯一「自托管 + HTTP API + Dashboard」三项齐全

| 维度 | 结论 | 取数依据 |
|---|---|---|
| 记忆模型类型 | **向量语义记忆为主 + 混合检索增强**。README 原文：安装 `mem0ai[nlp]` 可获得 "enhanced hybrid search with BM25 keyword matching and entity extraction"；默认嵌入模型为 OpenAI 的 `text-embedding-3-small` | mem0 README `:136`、`:209` |
| 能否完全自托管 | ✅ **能**。README 的三形态对照表原文：`Library`（`pip install mem0ai`）/ **`Self-Hosted Server`（`docker compose up`，`http://localhost:3000`）** / `Cloud Platform`；自托管版含 Dashboard、Auth 与 API Key（原文 "Self-hosted auth is on by default"，可用 `ADMIN_API_KEY` / `AUTH_DISABLED=true`） | mem0 README `:120-123`、`:149-161` |
| 接 Go 后端的方式 | **HTTP API**（自托管 server 的 API key 机制）。⚠️ README 只提供 pip / npm 官方 SDK（`pip install mem0ai`、`npm install mem0ai`），**未见官方 Go SDK** → Go 侧自写 `net/http` 薄封装即可 | mem0 README `:130-147` |
| 接入成本 | 🟢 **低**：`cd server && make bootstrap` 一条命令起栈；Go 侧一个 HTTP client。**唯一硬伤**：默认嵌入走 OpenAI → 要全离线/降成本必须自配本地嵌入模型 | mem0 README `:149-161`、`:209` |
| 一句话结论 | **首选** —— 开源记忆层里唯一同时满足「可完全自托管 + 有 HTTP API + 有可视化面板」的 | — |

#### 3.2.2 letta-ai/letta —— ⚠️ 主仓已变 stub，研究价值高但工程代价大

| 维度 | 结论 | 取数依据 |
|---|---|---|
| 仓库状态变化（**选型关键**） | `letta-ai/letta` 的 **main 分支现在只是指路牌**：README 原文 "The current source code lives in `letta-ai/letta-code`"。**archive 分支** README 原文："This repository contains the **legacy Letta server** (the API server behind the Letta V1 API and SDKs). Active development has moved to the Letta Agent repo (`letta-ai/letta-code`), and **self-hosting an API server is now done via the App Server**." | letta README `:5`；letta archive README `:1-12` |
| 记忆模型类型 | **上下文自改写式记忆**（agent 自己重写自己的上下文）。`letta-code` README 原文："Agents programmatically rewrite their context to improve and adapt over time, including system prompt learning (through **memory blocks**)"；另有 **MemFS**：原文 "All context (including memory blocks) is tracked via git"，可用 `/memory-repository` 同步到 GitHub 私有库 | letta-code README `:21`、`:23` |
| 能否完全自托管 | ✅ 能（`letta server` 起 App Server；或 Letta Cloud） | letta README `:16-20`；letta-code README `:30` |
| 接 Go 后端的方式 | **HTTP API**。⚠️ 官方 SDK 只有 TypeScript（`npm install @letta-ai/letta-agent-sdk`），**未见 Go SDK** → Go 侧只能打 REST 或再起一个 TS/Python 侧进程 | letta archive README `:30-40` |
| 接入成本 | 🔴 **高**：V1 REST server 已归档，只能吃 V2 App Server 的协议；运行时要求 Node.js 22.19+；记忆与「agent 自我改写」强耦合，与我们要的「人格可预测、可回滚」相冲突 | letta archive README `:9`、`:22`；letta-code README `:39` |
| 一句话结论 | **不做记忆层底座** —— 「自改进记忆」值得研究，但对我们（Go 后端 + 官方 agent 结构对齐 + 人格要稳定可回滚）不划算 | — |

#### 3.2.3 getzep/zep —— ⚠️ 主仓只剩 examples，OSS 实体已迁到 Graphiti 且 CE 已弃用

| 维度 | 结论 | 取数依据 |
|---|---|---|
| 仓库状态变化（**选型关键**） | main README 首行即："This repository is **not** Zep's product or service. It contains **example code, framework integrations, and tools** for building agent memory with **Zep Cloud**"。OSS 时序知识图谱框架已独立为 `getzep/graphiti`；旧的社区版在 `legacy/` 目录，README 目录表原文标注 "**Deprecated** Zep Community Edition (**unsupported**)" | zep README `:16-19`、`:38` |
| 记忆模型类型 | **时序知识图谱（timeline / graph）**。Graphiti README 原文：context graph = "entities, relationships, and facts" + "**episodes** — the raw data that produced it" + communities；对照表原文 "Explicit **bi-temporal** tracking with automatic fact invalidation" | graphiti README `:62-77`、`:148-152` |
| 能否完全自托管 | ⚠️ **Zep CE 已弃用**；**Graphiti = "Self-hosted only"**（Graphiti/Zep 对照表：Zep "Fully managed or in your cloud (BYOC)" vs Graphiti "Self-hosted only"）；图数据库自备：**Neo4j 5.26 / FalkorDB 1.1.2 / Amazon Neptune** | graphiti README `:102-110`、`:165` |
| 接 Go 后端的方式 | 官方 **Go SDK 确实存在**：`github.com/getzep/zep-go/v4`（README 原文 "This module requires Go version >= 1.13"）——**但它指向 Zep Cloud（托管 API）**，与自托管 Graphiti 不是同一套接口；Graphiti 本身是 **Python** 框架 | zep README `:26`；zep-go README `:36-46`；graphiti README `:81` |
| 接入成本 | 🔴 **高**：Graphiti 为 Python + 需自备图数据库 + 无 Go SDK → Go 后端要么再养一个 Python 服务再转 HTTP，要么放弃 | — |
| 一句话结论 | **不做记忆层底座**；若将来真需要「时序图记忆」，正确姿势是 **Graphiti 独立 Python 服务 + Go 侧 HTTP 封装**，且用 Go SDK 接 Zep Cloud 作托管兜底 | — |

#### 3.2.4 langchain-ai/langgraph —— 定位是编排框架，不是记忆产品

| 维度 | 结论 | 取数依据 |
|---|---|---|
| 记忆模型类型 | 自述为 **"Low-level orchestration framework for building stateful agents"**；记忆能力是 "short-term working memory for ongoing reasoning and **long-term persistent memory** across sessions" | langgraph README `:21`、`:43` |
| 能否完全自托管 | ⚠️ 库本身可自托管（`pip install -U langgraph`；JS/TS 版另有 `langgraphjs`）；但**部署面**指向 LangSmith Deployment（云） | langgraph README `:34-36`、`:70-72` |
| 接 Go 后端的方式 | ❌ **无 Go 实现**（Python / JS 双栈） | langgraph README `:34-38` |
| 接入成本 | 🔴 **高**：与我们的 Go 后端语言栈冲突；若再叠加 §二 的 pipecat（Python），后端会变成三语言 | — |
| 一句话结论 | **出局** —— 它的价值在「编排」而非「记忆存储」；我们的记忆需求（会话摘要 + 长期事实 + 情绪标签）用 mem0 + 自建摘要表足够 | — |

#### 3.2.5 记忆层选型结论

| 候选 | 自托管 | Go 接入 | 成本 | 结论 |
|---|---|---|---|---|
| **mem0** | ✅ 官方支持（docker compose + API key + Dashboard） | HTTP API（自写封装） | 🟢 低 | ✅ **采用** |
| letta | ✅（App Server） | HTTP API（无 Go SDK） | 🔴 高 | ⏸ 观察 |
| Graphiti / Zep | ✅（自备图库） | 需 Python 侧中转 | 🔴 高 | ⏸ 观察 |
| langgraph | ✅ | ❌ 无 Go | 🔴 高 | ❌ 出局 |

> **一句话**：记忆层选 **mem0 自托管 server**；`letta` 与 `zep` 的**主仓形态已变**（stub / examples-only），不能再像旧资料那样「直接 clone 主仓自托管」——任何引用这两个主仓的选型文档都应标注为**过期**。

---

## §四 角色卡格式规范与自定义人格包字段设计

### 4.1 三份公开规范的本轮取数状态（**只借鉴公开格式，严禁复制 AGPL 实现**）

| 规范来源 | 仓库地址 | 本轮取数 | 结论 |
|---|---|---|---|
| SillyTavern 角色卡规范 V2 | `github.com/michalfurman/character-card-spec-v2` | 🔴 **未取得**（`raw.githubusercontent.com` 与 `cdn.jsdelivr.net` 两条路径均只回 14 字节 404 / 连接重置，见 §十一） | 字段清单**待核**，不可当作已确认事实 |
| a16z-infra 角色卡规范 | `github.com/a16z-infra/character-card-spec` | 🔴 **未取得**（同上） | 待核 |
| 中文角色卡生态（SillyTavern 中文社区） | — | 🔴 **未取得**（本机 `web_search` 报 `MATRIX_TOOL_REQUEST_FAILED`，无可用检索通道） | 只能认定为「**生态惯例**，无独立公开规范文件」 |

> **合规红线（本节最重要的一条）**：SillyTavern 服务端实现属 **AGPL 系**（🔴 本轮未取得其 LICENSE 一手原文 → **按最坏情况当作 AGPL 处理**）。
> 因此我们的做法是：**只借鉴「公开的 JSON 字段格式」这一事实性数据结构**，**不复制其任何实现代码**（不引入其解析器/服务端/前端），schema 与解析器由我们在 Go 侧**从零自写**。字段名本身是事实性数据，不受版权保护；实现代码受copyleft 约束。

#### 4.1.1 ✅ 我们真正可以确定的字段全集 —— 来自**官方 server 自己的数据模型**（来源类型：**本地 git 原文**）

不去猜社区字段，直接用官方 `server/internal/model/xiaozhi/agent.go` 的三个结构体 —— 这是官方**已经在线上跑的人格数据模型**，权威度高于任何社区规范：

`AgentConfig`（`server/internal/model/xiaozhi/agent.go:70-86`）：

```go
type AgentConfig struct {
	AgentName           string   `json:"agent_name"`
	AssistantName       string   `json:"assistant_name"`
	LlmModel            string   `json:"llm_model"`
	TtsVoice            string   `json:"tts_voice"`
	TtsSpeechSpeed      string   `json:"tts_speech_speed"`
	TtsPitch            int      `json:"tts_pitch"`
	AsrSpeed            string   `json:"asr_speed"`
	Language            string   `json:"language"`
	Character           string   `json:"character"`
	Memory              string   `json:"memory"`
	MemoryType          string   `json:"memory_type"`
	KnowledgeBaseIds    []int    `json:"knowledge_base_ids"`
	McpEndpoints        []string `json:"mcp_endpoints"`
	ProductMcpEndpoints []string `json:"product_mcp_endpoints"`
}
```

`Agent`（同文件 `:88-113`）在此之上补齐了传播与归属字段：`id / user_id / agent_name / tts_voice / llm_model / assistant_name / user_name / memory / character / long_memory_switch / lang_code / language / tts_speech_speed / asr_speed / tts_pitch / agent_template_id / memory_updated_at / share_agent_id / source / mcp_endpoints / memory_type / knowledge_base_ids / max_message_count / product_mcp_endpoints / deviceCount / lastDevice`。

`AgentTemplate`（同文件 `:39-55`）是**模板态**（可分享的人格模板）：`agent_name / tts_voices / default_tts_voice / llm_model / assistant_name / user_name / character / tts_speech_speed / asr_speed / tts_pitch / knowledge_base_ids / tts_voice_name`。

**由官方模型反推的「生态普遍字段」分类**（这部分是**我们从官方代码验证出来的**，不是猜的）：

| 分类 | 官方字段 |
|---|---|
| 身份 | `assistant_name` / `agent_name` / `user_name` |
| **人格正文** | **`character`**（唯一的人格描述字段）、`memory` / `memory_type` / `long_memory_switch` |
| 声音 | `tts_voice` / `default_tts_voice` / `tts_voices[]` / `tts_speech_speed` / `tts_pitch` / `asr_speed` / `language` / `lang_code` |
| 知识 | `knowledge_base_ids` |
| 工具 | `mcp_endpoints` / `product_mcp_endpoints` |
| 传播 / 归属 | `agent_template_id` / `share_agent_id` / `source` / `max_message_count` |

> **含义**：我们要做的「人格包」，**必须超集于**上面这张表 —— 这样人格包既能驱动我们自己替换后的 AI 层，也能原样喂给官方前端的 `agent_configuration.dart`（`app/lib/view/popup/agent_configuration.dart:369-395` 实际显示的就是 `id / llmModel / ttsVoice / ttsSpeechSpeed / ttsPitch`）。

### 4.2 我们的自定义人格包 schema（**自造设计**，版本化 + 可签名）

**形态**：单文件 JSON（`*.persona.json`），配套一份 JSON Schema 做校验；服务端存 registry 一行 + 可导出该文件。

```json
{
  "schema_version": "1.0",
  "persona_version": 3,
  "id": "p_5f3a9c",
  "name": "小夏",
  "description": "桌面陪伴机器人的人格：活泼、话痨、偶尔傲娇",
  "persona": "你叫小夏，是住在用户桌面上的小机器人……（自由文本，等价于官方 character 字段）",
  "system_prompt": "可选：覆盖默认系统提示词",
  "greeting": "我回来啦！",
  "tags": ["中文", "活泼", "傲娇"],
  "voice": {
    "tts_voice": "<小智 voice_id>",
    "tts_speech_speed": "1.0",
    "tts_pitch": 0,
    "asr_speed": "normal",
    "language": "zh",
    "lang_code": "zh-CN"
  },
  "emotion": {
    "default": "happy",
    "overrides": { "thinking": { "expression": "thinking", "decorator": "dizzy" } }
  },
  "memory": { "type": "mem0", "scope": "device" },
  "knowledge_base_ids": [],
  "mcp_endpoints": [],
  "author": "jss18",
  "license": "CC-BY-4.0",
  "created_at": "2026-10-23T00:00:00Z",
  "updated_at": "2026-10-23T00:00:00Z",
  "key_id": "k_2026a",
  "signature": "<Ed25519 签名的 base64url>"
}
```

**字段约束与枚举（全部对齐我们已核实的事实，不臆造）**：

| 字段 | 约束 | 依据 |
|---|---|---|
| `schema_version` | 字符串 `"主.次"`；我们只承诺 `1.x` 兼容 | 自造 |
| `persona_version` | 整数，单调递增，用于「同 id 不同内容」的灰度与回滚 | 自造 |
| `id` | `p_` + 短哈希，全局唯一 | 自造 |
| `persona` | 必填非空；对应官方 `character` | 本地 git 原文 |
| `voice.tts_voice` | 必须是服务端**已注册**的 voice_id 集合内取值（可从官方 `api/user/tts-list` 拉取，§0.1） | 本地 git 原文 |
| `voice.tts_speech_speed` / `asr_speed` | **保持 string 类型**（官方就是 `string`，不是 float —— 官方取值集合本轮未取得 → 我们不设枚举，只透传） | 本地 git 原文 |
| `voice.tts_pitch` | 整数 | 本地 git 原文 |
| `emotion.default` + `emotion.overrides` 的 key | **必须是 §9.5 的 L0 标签集成员**（24 项）；固件不认识的一律降级到 `neutral`（官方行为：`Unknown emotion: %s, using NEUTRAL`） | 本地 git 原文 |
| `emotion.overrides[].expression` | 必须是 §9.4 第 5 层 `ExpressionData.type` 的语义标签；其值体（`ExpressionItem{x,y,rotation,weight,size}`）由**服务端**按标签查表填充，不放进人格包 | 本地 git 原文 |
| `memory.type` | 枚举：`mem0` / `local`（对应 §3.2 选型） | 自造（对齐 §3.2） |
| `key_id` / `signature` | `key_id` 指向服务端 registry 的公钥条目；`signature` = 对**去掉 signature 字段后的规范化 JSON**（键名排序、无多余空白）的 Ed25519 签名，base64url | 自造（Go 标准库 `crypto/ed25519`） |

**人格 ↔ 表情/动作/音色的绑定关系**（明确三层，避免人格包无限膨胀）：

| 绑定 | 存在哪 | 说明 |
|---|---|---|
| 人格 → **音色** | 人格包内 `voice.*` | 直接字段。克隆音色（§七）另带 `voice_asset_ref`（服务端资产 ID，**不内嵌音频**） |
| 人格 → **情绪标签默认值** | 人格包内 `emotion.default` | 人格自带「默认表情」 |
| 人格 → **情绪 → 表情/动作参数** | **服务端映射表**（不在人格包内） | 复用官方 `ExpressionData` / `MotionData` / `DanceData` schema（§9.4 第 5 层），人格包只存**标签**，参数由服务端查表下发 |
| 人格 → **动作/舞蹈** | 服务端 `device_dance` 表 | 官方已有独立表与 API（`server/api/dance/v1`、`v2`），不塞进人格包 |

> **设计原则**：人格包 = **纯数据 + 可签名 + 小体积**；一切**资产**（表情参数表、音频、舞蹈）留服务端。这样 NFC 卡才能只带一个 ID（§六），且人格包可随时更新而不需要重新发卡。

---

## §五 人格运行时热切换（运行中换人格，不重启服务、不重连设备）

### 5.1 先钉事实：官方 WS 协议面本身就允许「连着换」（来源类型：**本地 git 原文**）

- 二进制帧格式（`server/README.MD:931-936`）：`1 byte msgType` + `4 bytes payload length (big endian)` + `N bytes payload`。
- 消息类型表（`server/README.MD:938-964`，与 `server/internal/web_socket/web_socket.go:29-56` 的常量表一致）：`0x03 ControlAvatar`（表情控制）、`0x04 ControlMotion`（动作控制）、`0x07 TextMessage`、`0x14 Dance`、`0x15 GetAvatarPosture`、`0x10 ping` / `0x11 pong` 等。
- **连接是按 mac 索引的长连接**：`stackChanClientPool = sync.Map{}`（`server/internal/web_socket/web_socket.go:63`），握手时 `GetMac()` 用 RSA token 解出 mac 并校验 ±10s 时间窗（`web_socket.go:77-115`），`deviceType=StackChan` 走设备分支（`web_socket.go:117-140`）。
- 每连接一个发送队列 + 独立写协程：`StackChanClient{ sendChan chan *WsSendMsg /* 缓冲 100 */ }` + `StartWriterCoroutine()`（`server/internal/model/web_socket_model.go:30-48`、`:95-118`）。
- 心跳：每 5s 发一次，每 15s 清理过期连接（`server/README.MD:966-972`）。

> **结论（本章的地基）**：官方 WS 是**按 mac 维护的、带多路 opcode 的长连接**。**人格状态完全不在连接里，而在服务端内存/DB 里** → 换人格 = 换服务端的一个指针，**天然不需要重启服务、不需要重连设备、不需要动固件传输层**。

### 5.2 三层结构（Go 后端，GoFrame v2）

| 层 | 职责 | 实现要点 |
|---|---|---|
| **① Personality Registry** | 人格包的权威存储：`id → 人格包（含签名、公钥 `key_id`、吊销状态、版本）` | 沿用官方 MySQL + GoFrame ORM 模式（`server/go.mod:6-7` 已含 `gf/contrib/drivers/mysql/v2` 与 `gf/v2`）；进程内加一层 `sync.RWMutex` 保护的只读缓存 |
| **② Provider Router** | 按人格声明决定「谁来做 LLM / TTS / 记忆」 | 路由键 = 人格里的 `llm_model` / `voice.*` / `memory.type`（§4.2）；实现为 provider 接口表：MiniMax（云）、Ollama（§八 本地）、本地 TTS（§七）、mem0（§3.2） |
| **③ Session Binding** | `device mac → 当前生效人格` + **原子指针** | 每个已连接设备一个 `atomic.Pointer[ActivePersonality]`；切换 = 一次 `Store()` |

### 5.3 原子切换的具体做法（Go 侧）

```go
// 每个在线设备一份；写者只有一个（切换请求），读者是每次对话请求。
type ActivePersonality struct {
	Pack     *PersonaPack   // 不可变快照
	Revision uint64         // 每次切换 +1，用于回声与排障
}

var active atomic.Pointer[ActivePersonality]
```

- **切换动作只有一次 `active.Store(&ActivePersonality{Pack: p, Revision: old+1})`** → 读者要么看到旧人格、要么看到新人格，**不存在中间态**（Go 内存模型保证 `atomic.Pointer` 的读写语义）。
- **进行中的那一轮对话用旧快照**：对话开始时 `snap := active.Load()`，整轮（LLM prompt 组装 → TTS 合成 → 表情下发）都用 `snap`，**不中途换人格** → 不会出现「前半句是小夏、后半句是李雷」的错位。
- **下一轮立即生效**：切换完成后的下一次请求 `active.Load()` 拿到的就是新人格。
- **不需要重建任何连接**：`stackChanClientPool` 里那条 WS 原封不动；人格切换**不产生任何网络层动作**。

### 5.4 切换的三个触发源

| 触发源 | 入口 | 说明 |
|---|---|---|
| App / Web 下发 | 新增 REST：`POST /api/persona/activate`（body：`persona_id` + 目标 `device_id`/mac） | GoFrame v2 路由风格与官方 `server/api/...` 一致 |
| **NFC 碰卡** | §六 链路（固件上报 → 服务端校验 → 切换） | 见 §六 |
| 场景 / 定时规则 | 服务端定时任务（官方 `server/internal/boot/cron.go` 已有 cron 基础设施） | 如「夜间 23:00 自动切安静人格」 |

### 5.5 固件侧需要收到什么？——**必须为零，可选一件**

| 项 | 固件是否要改 | 说明 |
|---|---|---|
| 系统提示词 / 人格正文 / 记忆 / LLM provider | ❌ **不用改** | 全在服务端，固件不感知 |
| 音色 / 语速 / 音高 | ❌ **不用改** | `tts_voice` / `tts_speech_speed` / `tts_pitch` 是**服务端 TTS 参数**（官方 `Agent` 字段），随合成请求下发给 TTS 服务商（MiniMax），固件只负责播音 |
| 「人格已切换」的通知 | ⚠️ **可选小改** | 建议新增 opcode `0x1B PersonaChanged`（沿用 `1+4+N` 帧格式），payload 放 `persona_id` + `status`；固件收到后可播一句招呼语 + 换表情 |
| 表情 / 动作 | ⚠️ **可选小改** | 复用现成 opcode `0x03 ControlAvatar` / `0x04 ControlMotion`，语义标签用 §9.5 的 L0 标签集 |

> **最小改动结论**：**只换后端，固件零改动即可实现「运行中切人格」**；要「切换时有反馈」才需要加 1 个 opcode + 1 个表情动作。

### 5.6 人格与「语速 / 音色 / 表情偏好」的**下发时机**

| 项 | 生效时机 | 载体 |
|---|---|---|
| 人格正文 / system prompt | **下一轮请求组装时** | 服务端内部（对话开始时取快照） |
| 音色 / 语速 / 音高 | **下一次 TTS 合成时**（**不能**改已在播放的音频） | MiniMax TTS 请求参数（对应官方 `tts_voice` / `tts_speech_speed` / `tts_pitch`） |
| 表情偏好（`emotion.default` / `overrides`） | **该轮情绪判定之后**，随该轮文本一起下发 | `0x03 ControlAvatar` + `ExpressionData`；情绪字符串走 §9.2 的 8 个官方输入 |
| 动作 / 舞蹈 | 该轮表演单元组装时 | `0x04 ControlMotion` / `0x14 Dance`（官方 `DanceData`） |

### 5.7 我们 fork 后端时**必须动的地方**（清单）

1. 替换 §0.1 的 AI 层三处（`server/internal/xiaozhi/xiaozhi.go`、`server/internal/model/xiaozhi/agent.go`、`server/internal/service/agent.go`）→ 换成自建 LLM/TTS 编排。
2. 新增 `server/api/persona/` + `server/internal/controller/persona/` + `server/internal/model/persona/`（registry + 签名校验 + 吊销表）。
3. 新增 WS opcode `0x1B`（`server/internal/web_socket/web_socket.go:29-56` 常量表 + 发送分支）。
4. `server/internal/boot/cron.go` 增加可选的自动切换规则任务。
5. `server/check_list/create_mysql_database.sql` 增加 `persona` / `persona_key` / `persona_revoke` 表。

### 5.8 本节风险

- **切换风暴**：NFC 连碰可能触发频繁切换 → 用 `Revision` + 节流（同一 `persona_id` 重复切换在 N 秒内不重复下发通知）。
- **会话串人格**：切人格时旧人格的会话摘要要不要带过去？建议**记忆按 `persona_id` 分区**（mem0 用 `user_id` / filters 隔离，§3.2.1 的 `search(..., filters={"user_id": ...})` 形态可直接借用）。
- **人格包的信任**：签名校验必须**在服务端做**（§六 3）—— 固件无公钥、无吊销表，不能让设备自己判断可信。

---

## §六 NFC 一碰换人格完整链路

### 6.1 设备侧读卡方案 —— **硬件已有 NFC 模块，但开源固件里没有驱动**

**已核实事实（来源类型：本地 git 原文）**：

| 事实 | 原文 / 路径 |
|---|---|
| 主控是 **M5Stack CoreS3**，**ESP32-S3** SoC（240MHz 双核 / 16MB Flash / 8MB PSRAM / Wi-Fi + BLE） | `README.md:13`："It uses the M5Stack flagship IoT development kit CoreS3 as its main controller, powered by an **ESP32-S3** SoC … with 16MB Flash and 8MB PSRAM onboard, and supporting Wi-Fi and BLE" |
| **机器人本体自带 NFC 模块** | `README.md:15`："The **robot body**, connected to the main unit, includes a USB-C interface for power and data, a 550 mAh battery, two feedback servos …, two rows totaling 12 RGB LEDs, infrared transmitter and receiver, a three-zone touch panel, and **a full-featured NFC module**" |
| 板级支持包地址 | `README.md:24`："Board support package: https://github.com/m5stack/StackChan-BSP" |
| 固件目标芯片 | `firmware/sdkconfig.defaults`：`CONFIG_IDF_TARGET="esp32s3"` |
| **官方开源固件里没有任何 NFC 驱动代码** | 全库检索 `nfc\|pn532\|pn5180\|ntag\|mifare`（`git grep -i` 于 `origin/main`）**唯一命中就是 `README.md:15` 那句硬件描述**；xiaozhi-esp32 v2.2.4 源码检索 `pn532\|pn5180\|nfc` 仅命中一个 `.ogg` 二进制误匹配（**零驱动代码**） |

> **推论（本节最关键的一条）**：
> ① **硬件侧不需要我们外挂读卡芯片** —— 官方本体已有 NFC 模块；
> ② 但 **NFC 驱动不在本仓库**，只能在 **BSP（`m5stack/StackChan-BSP`）** 里，或者**尚未开源** → 🔴 **NFC 芯片型号 / 总线接口（I²C / SPI / UART）/ 读写能力，BSP 驱动 API 全部未取得**，是第一优先取证项。
> ③ 关于「ESP32-S3 是否片上集成 NFC」：🔴 本轮**未取得 Espressif 数据手册原文**（网络受限），记为未取得 —— 但**本项目结论不依赖它**：官方硬件走的是**独立 NFC 模块**，不是片上外设。

**读卡方案的三个候选（按可行性排序）**：

| 方案 | 前提 | 成本 | 状态 |
|---|---|---|---|
| **A. 用官方本体的 NFC 模块** | 需要 BSP 暴露读卡 API（🔴 未取得） | 最低（驱动已存在则几乎为零） | ⏳ 待 BSP 取证 |
| B. 外挂 PN532（I²C） | 需自己写/移植驱动 | 中 | 备选（PN532 常见于 M5Stack 生态，本轮未取数，不做断言） |
| C. 外挂 PN5180（SPI） | 需自己写/移植驱动 | 中高 | 备选（同上，未取数） |

> **本报告不对 PN532 / PN5180 的型号、接口、许可、驱动来源做任何断言** —— 一手资料未取得。

### 6.2 iOS 侧 CoreNFC：**`NFCNDEFReaderSession` 是「读」会话，不能写卡**

- 🔴 **Apple 文档一手原文本轮未取得**（网络受限）。以下为**背景知识，待一手核验**，但**设计结论按最保守（最不利）假设来定**：
  - `NFCNDEFReaderSession` —— 类名与官方文档标题即语义为 **读取** NDEF 标签的会话 → **iPhone 用它只能读卡，不能写卡**。
  - iPhone **写卡** 需要走 `NFCISO7816Tag`（ISO/IEC 7816-4 协议标签，如 MIFARE 系列），且需要 Apple 授权的 entitlement 与 `com.apple.developer.nfc.readersession.formats` 配置 —— 属于**受限能力**，不保证可申请。
- **因此：写卡端不能放在 iPhone 侧。** 可选写卡端：
  1. **Android 手机**（`NfcAdapter` / `Tag` 技术，可写 NDEF 到 MIFARE Ultralight）—— 需要 Android App。
  2. **产线 / 桌面工具 + USB 读卡器**（推荐）：人格包是服务端资产，批量烧卡最省事、最好审计。
  3. 若官方 NFC 模块本身是**读写**模块且 BSP 暴露写 API，则可由固件直接写（🔴 待取证）。

### 6.3 NDEF 记录里存什么 —— **只存指针与凭证，不存人格包本体**

理由：NDEF 可用容量小（Ultralight 通常几十到一百多字节可用），而人格包含 prompt + 音色 + 表情表（KB 级）；且人格包必须**服务端可校验、可吊销、可更新**（发卡不能跟着人格版本走）。

```
NDEF record:
  URI type: https://stackchan.local/p/<persona_id>?v=<schema_version>&k=<key_id>&s=<sig_b64url>
```

| 段 | 内容 | 长度量级 |
|---|---|---|
| `persona_id` | 人格 id（`p_` + 短哈希） | ~10 B |
| `v` | 人格包 `schema_version` | ~3 B |
| `k` | 公钥条目 id（`key_id`） | ~8 B |
| `s` | Ed25519 签名（base64url） | ~22 B（16B 签名） |
| `exp`（建议加） | 过期时间戳（Unix） | ~10 B |
| `fb`（建议加） | 卡片失效时的兜底人格 id | ~10 B |

- **签名对象**：对规范化串 `persona_id|schema_version|key_id|exp` 做 **Ed25519** 签名（Go 标准库 `crypto/ed25519`）。卡上只有 ~50–70 B 有效载荷。
- **签名的意义**：卡片是**可复制**的。签名只能证明「这张卡由我们签发」，**不能**阻止复制 → 真正的防伪靠服务端吊销表（见 6.5）。
- **人格包本体仍在服务端**（§4.2 的 registry），卡 = 一张**指针卡**。

### 6.4 端到端时序 —— 读卡换人格（不重连设备）

```
[手机/App]                    [机器人固件(ESP32-S3)]              [我们的 Go 后端]
     │                                │                                 │
 ① 生成卡(persona_id+sig)   ────────► │ (写卡端: Android/产线工具)       │
 ② 用户把卡贴到本体 NFC 模块 ───────► │                                 │
 ③ 读 NDEF → 解析 persona_id/sig      │                                 │
 ④ 只做格式校验(长度/前缀/base64)     │                                 │
 ⑤ 经【已建立的 WS】上报 ◄───────────┼──── 0x1B PersonaRequest ────────►│
                                     │                                 │ ⑥ 查 registry + 验签 + 查吊销/过期
                                     │ ◄──── 0x1B PersonaChanged ────── │ ⑦ atomic.Store 原子切换
 ⑧ 播招呼语 + 换表情(可选)          │                                 │
 ⑨ 下一轮对话用新人格                                                │
```

- **⑤ 走的是原有那条长连接**（§5.1），**不新建连接、不重连**；
- **⑦ 切换完成即刻生效**，但对话内容按 §5.3 的「轮次快照」规则 → **下一轮**起用人格；
- **⑧** 固件收到 `PersonaChanged` 后可播固定招呼语并换表情（复用 `0x03 ControlAvatar` + §9.5 L0 标签）。

### 6.5 失败处理（**任何异常一律保持原人格**）

| 场景 | 固件上报 | 服务端响应 | 用户可见行为 |
|---|---|---|---|
| 贴卡但读不到 / 卡不是 NDEF | `PersonaRequest{status:"no_tag"}` | 保持原人格 | 播「没读到卡」 |
| `persona_id` 不存在 | — | `status:"unknown_persona"` | 保持原人格 + 提示未知人格 |
| 签名不匹配 | — | `status:"bad_signature"` | 保持原人格（**绝不降级到未知人格**） |
| 卡已过期 | — | `status:"expired"` | 保持原人格 |
| 卡已吊销 | — | `status:"revoked"` | 保持原人格 |
| 设备当前离线（WS 未连） | 本地队列缓存（建议 ≤5 条） | — | WS 重连后补发，仍走服务端校验 |
| 卡片被复制 | — | 服务端按 `persona_id` 吊销即全量失效 | — |

### 6.6 接入成本汇总

| 工作项 | 量级 | 说明 |
|---|---|---|
| 固件：NFC 读卡驱动 | 🟢 低（若 BSP 已有）/ 🔴 高（若要自己写驱动） | 取决于 §6.1 的 BSP 取证结果 |
| 固件：新增 `0x1B` 上报 + 可选表情/招呼 | 🟢 低 | 沿用现有 `1+4+N` 帧格式与 opcode 表 |
| 服务端：registry + Ed25519 验签 + 吊销表 + 新 opcode + REST | 🟢 低-中 | 与 §4.2 / §5.7 同一批工作量 |
| 写卡端 | 🟡 中 | Android App **或** 产线 USB 读卡器工具（推荐后者）；**iPhone 不可写** |
| **总评** | **🟡 中** | 最大不确定性 = 官方 NFC 模块型号 / 总线 / BSP 驱动（🔴 未取得） |

### 6.7 本节结论

> **NFC 一碰换人格在硬件上成立（官方本体自带 NFC 模块）、在协议上成立（长连接上多一个 opcode）、在信任模型上成立（服务端验签 + 吊销）**；
> 唯一**未闭合**的是「**NFC 驱动从哪来**」（BSP 或自研）与「**iPhone 不能写卡** → 写卡端必须另选」。
> 推荐落地顺序：① 先用 REST/App 下发切人格（§5.4，零硬件依赖）验证人格链路 → ② 再接 NFC（只增加 §6.4 的 ⑤ 与驱动）。

---

## §八 本地 LLM provider 与结构化输出（部分）

### 8.1 Ollama —— 结构化输出已实测于文档原文（来源类型：**上游 docs/api.md 原文**）

取数：https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md

- **JSON Schema 结构化输出**：把 JSON Schema 放进 `format` 参数。
  - `/api/generate` 参数表原文：`format`: the format to return a response in. Format can be `json` or a JSON schema
  - `/api/chat` 参数表原文同上。
  - 文档给出「Request (Structured outputs)」示例（`/api/chat`，model `llama3.1`），`format` 内含 `type/properties/required`，并配 `options.temperature: 0`。
- **可复现性**：`options.seed` —— 文档「Request (Reproducible outputs)」示例，`{"model":"mistral","prompt":"...","options":{"seed":123}}`。
- **工具调用**：`/api/chat` 的 `tools` 参数支持 function calling（文档给出完整 `tools` + `tool_calls` 响应示例）。
- **文档给出的规模参考**（`/api/tags` 示例）：`llama3.2` = 3.2B / Q4_K_M / `size: 2019393189`；`deepseek-r1` = 7.6B / Q4_K_M / `size: 4683075271`。

> **对本项目**：8GB 显存 + 23.7GB RAM 跑 7–8B Q4 是现实区间（Q4_K_M 7.6B 权重约 4.68 GB）。

---

## §九 情绪 → 表情/动作语义标签体系（部分）

### 9.1 官方固件已有的情绪枚举 —— 可直接复用（来源类型：**本地 git 原文**）

`firmware/main/stackchan/avatar/avatar/elements/emotion.h` 全文：

```cpp
namespace stackchan::avatar {
enum class Emotion {
    Neutral = 0,
    Happy,
    Angry,
    Sad,
    Doubt,
    Sleepy,
};
}
```

**只有 6 个内部情绪值。**

### 9.2 官方固件对外暴露的情绪「字符串协议」—— 8 个输入 → 6 个枚举

`firmware/main/hal/board/stackchan_display.cc:321-372`（`StackChanAvatarDisplay::SetEmotion(const char* emotion)`）逐字映射：

| 输入字符串 | 映射到 `Emotion::` | 备注 |
|---|---|---|
| `neutral` | Neutral | |
| `happy` | Happy | |
| `laughing` | Happy | 折叠 |
| `angry` | Angry | |
| `sad` | Sad | |
| `crying` | Sad | 折叠 |
| `sleepy` | Sleepy | 额外：`setSpeech("Zzz…")`、停 idle motion、`pitchServo().moveWithSpeed(0, 80)` 回默认姿态 |
| `doubtful` | Doubt | |
| 其他 | Neutral | 原文：`ESP_LOGW(TAG, "Unknown emotion: %s, using NEUTRAL", emotion);` |

**这张表就是我们的「情绪 → 表情」第一层映射的天然契约** —— 服务端只要按这 8 个字符串下发，固件无需任何改动即可正确表现。

### 9.3 官方还有 5 个「装饰器」可叠加（来源类型：**本地 git 原文**）

`firmware/main/stackchan/avatar/decorators/decorators.h` 定义：`HeartDecorator`、`AngryDecorator`、`SweatDecorator`、`ShyDecorator`、`DizzyDecorator`（各带 `destroyAfterMs` 生命周期参数）。
`firmware/main/stackchan/avatar/decorators/assets/` 对应资产：`decorator_angry.c`、`decorator_dizzy.c`、`decorator_heart.c`、`decorator_shy.c`、`decorator_sweat.c`。

> **含义**：固件表情能力 = **6 情绪（脸）× 5 装饰（叠加层）**。语义标签体系应区分「情绪轴」与「装饰轴」两层，而不是拉平成一个 30 项大表。

### 9.4 ⭐ 「300+ 表情/动作命名」在官方仓库中**未取得** —— 真实的表达词汇表是多层小集合

这一条与兄弟报告 `37-程序化动作合成与物理具身技术栈调研.md` §2.1/2.2 的结论**一致且互证**（该报告已独立断言「300+ 表情」在官方固件中未取得）。本节把**所有**相关层逐层点名，让「300+」这个数字的归属无死角。

#### 第 1 层：xiaozhi-esp32 的 emoji 表情集合 = **21 个唯一名**（×2 尺寸 = 42 个图像句柄）

来源类型：**本地 clone 源码**（`D:\AP\AP7000\ai-workspace\stackchan-research\repos\xiaozhi-esp32` @ `v2.2.4`，克隆自 `https://github.com/78/xiaozhi-esp32.git`）
文件：`main/display/lvgl_display/emoji_collection.cc`

`extern` 声明共 **42** 条 = 21 个名字 × {32px, 64px}。21 个唯一名（与注释一一对应，Unicode codepoint 见括号）：

```
neutral(1f636)  happy(1f642)   laughing(1f606) funny(1f602)   sad(1f614)
angry(1f620)    crying(1f62d)  loving(1f60d)  embarrassed(1f633) surprised(1f62f)
shocked(1f631)  thinking(1f914) winking(1f609) cool(1f60e)    relaxed(1f60c)
delicious(1f924) kissy(1f618)  confident(1f60f) sleepy(1f634) silly(1f61c)
confused(1f644)
```

`AddEmoji("neutral", new LvglSourceImage(&emoji_1f636_32));` 等 42 条注册语句（`emoji_collection.cc:54-123`）。
`GetEmojiImage()` 未命中时返回 nullptr 并打日志 `Emoji not found: %s`。

#### 第 2 层：StackChan 覆盖层的情绪枚举 = **6 个**

`firmware/main/stackchan/avatar/avatar/elements/emotion.h:12-19`（见 §9.1）。

#### 第 3 层：StackChan 覆盖层的对外字符串协议 = **8 个输入**

`firmware/main/hal/board/stackchan_display.cc:321-372`（见 §9.2）。

#### 第 4 层：StackChan 装饰器 = **5 个**

`firmware/main/stackchan/avatar/decorators/decorators.h`（见 §9.3）。

#### 第 5 层：**动作/舞蹈/表情参数** —— 这才是官方的「可编程表情」本体

来源类型：**本地 git 原文** —— `server/internal/model/expressionData.go`（官方 server 的数据模型，**MIT** SPDX 头）

```go
type ExpressionData struct {
	Type     string         `json:"type"`
	LeftEye  ExpressionItem `json:"leftEye"`
	RightEye ExpressionItem `json:"rightEye"`
	Mouth    ExpressionItem `json:"mouth"`
}
type ExpressionItem struct {
	X        int `json:"x"`
	Y        int `json:"y"`
	Rotation int `json:"rotation"`
	Weight   int `json:"weight"`
	Size     int `json:"size"`
}
type MotionData struct {
	Type       string         `json:"type"`
	PitchServo MotionDataItem `json:"pitchServo"`
	YawServo   MotionDataItem `json:"yawServo"`
}
type MotionDataItem struct {
	Angle  int `json:"angle"`
	Speed  int `json:"speed"`
	Rotate int `json:"rotate"`
}
type DanceData struct {
	LeftEye    ExpressionItem `json:"leftEye"`
	RightEye   ExpressionItem `json:"rightEye"`
	Mouth      ExpressionItem `json:"mouth"`
	PitchServo MotionDataItem `json:"pitchServo"`
	YawServo   MotionDataItem `json:"yawServo"`
	DurationMs int            `json:"durationMs"`
}
```

App 侧同名同构的 Dart 类：`app/lib/model/expression_data.dart:9-40`（`ExpressionData{type,leftEye,rightEye,mouth}`，`ExpressionItem{x,y,rotation,weight,size}`，`type` 默认值 `"bleAvatar"`）。
另有 Kotlin 版 `app/android/app/src/main/kotlin/com/m5stack/stackchan/model/ExpressionData.kt`、`ExpressionItem.kt`、`MotionData.kt`、`MotionDataItem.kt`、`DanceData.kt`，Swift 版 `app/ios/Runner/Model/ExpressionData.swift`。

> **这张 schema 是我们整个「情绪 → 表情/动作」体系的落地契约**：
> - `ExpressionData.Type` = **语义标签的载体**（如 `"happy"`、`"thinking"`）
> - `ExpressionItem{5 参数}` = 表情的**连续参数向量**（3 个 Feature = 左眼/右眼/嘴）
> - `MotionData.Type` + `MotionDataItem{angle,speed,rotate}` = 动作语义标签（俯仰/偏航舵机）
> - `DanceData` = 表情 + 动作 + 时长，**一个完整表演单元**

#### 「300+」最可能的真实归属 —— **未取得**

穷举核查（来源类型：**本地 git 原文 + 本地 clone 文件计数**）：

| 候选位置 | 实测计数 | 结论 |
|---|---|---|
| `firmware/main/stackchan/` 的字符串字面量 | **12** 个（`angle` `damping` `jumps` `mouth` `rotate` `rotation` `size` `snap` `speed` `spring` `stiffness` `weight`） | ❌ 那里**没有任何**表情/动作命名表 |
| `firmware/main/assets/` | **25** 个文件 | ❌ 全是图标/字体/音效 |
| xiaozhi-esp32 `main/assets/` | **635** 个文件 | ❌ 但绝大多数是 `locales/<语言>/` 的字体与音频（`ar-SA`、`bg-BG`、`ca-ES`…）与 `common/` 5 个 ogg |
| `firmware/main/stackchan/avatar/decorators/assets/` | 5 个 `.c` | ❌ |
| 官方 server 侧 `ExpressionData` | 0 个具体实例（只有结构体） | ❌ 预设不在仓库里 |

> **定论**：「300+ 表情与动作命名」这个数字 **在官方仓库的任何一个可数位置都不成立**。它极可能来自：(a) 官方 App 端或小智平台侧的**表情预设库**（服务端下发，仓库里查不到）；(b) `espressif2022/esp_emote_expression` 组件的资产数（官方**已注释掉**该依赖：`firmware/main/idf_component.yml` 中 `# espressif2022/esp_emote_expression: ^0.1.0`）；(c) 社区/第三方表情包。
> **本报告不对「300+」做任何断言**，按「未取得」记录，并在 §十一 风险清单里列出。

### 9.5 我们需要的「情绪 → 表情/动作」语义标签体系 —— 设计建议（自造部分明确标注）

**现状事实**：官方固件已经给了一套**小而确定的**渲染词汇（6 情绪 / 8 字符串 / 21 emoji / 5 装饰 / 15 维参数向量），并且 App↔server↔device 已经有一套 `ExpressionData`/`MotionData`/`DanceData` 的 JSON 线协议。**没有任何现成的「情绪语义标签集」可以复用** —— 官方根本不用 Plutch/Geneva 这类外部情绪模型。

因此：

| 层 | 内容 | 来源 | 决策 |
|---|---|---|---|
| **L0 情绪标签**（对外语义） | 我们定义的中文/英文情绪枚举 | **自造** | 自造。必须**超集于**官方 8 字符串协议 |
| **L1 降级映射** | L0 → 官方 8 字符串 | 自造 | 必备。固件不认识的一律落到 `neutral`（官方行为：`Unknown emotion: %s, using NEUTRAL`） |
| **L2 表情参数** | 标签 → `ExpressionData{type,leftEye,rightEye,mouth}` | **自造**（schema 复用官方） | 复用官方 schema，自造映射表 |
| **L3 动作参数** | 标签 → `MotionData{type,pitchServo,yawServo}` / `DanceData` | 同上 | 复用官方 schema，自造映射表 |

**L0 建议标签集**（21 emoji + 6 enum + 5 decorator 的并集扩展，逐一给出官方降级目标）：

| L0 标签 | 中文 | 官方 `SetEmotion` 字符串 | 可叠加装饰器 |
|---|---|---|---|
| `neutral` | 平静 | `neutral` | — |
| `happy` | 开心 | `happy` | heart |
| `laughing` | 大笑 | `laughing` | heart |
| `funny` | 搞怪 | `laughing` | silly |
| `sad` | 难过 | `sad` | — |
| `crying` | 哭 | `crying` | — |
| `angry` | 生气 | `angry` | angry |
| `loving` | 撒娇 | `happy` | heart / shy |
| `embarrassed` | 害羞 | `happy` | shy |
| `surprised` | 惊讶 | `neutral` | — |
| `shocked` | 震惊 | `neutral` | sweat |
| `thinking` | 思考 | `doubtful` | — |
| `winking` | 眨眼 | `happy` | — |
| `cool` | 酷 | `neutral` | — |
| `relaxed` | 放松 | `neutral` | — |
| `delicious` | 满足 | `happy` | — |
| `kissy` | 亲亲 | `happy` | heart / shy |
| `confident` | 自信 | `neutral` | — |
| `sleepy` | 困倦 | `sleepy` | — |
| `silly` | 傻气 | `happy` | — |
| `confused` | 困惑 | `doubtful` | dizzy |
| `doubtful` | 怀疑 | `doubtful` | — |
| `dizzy` | 头晕 | `doubtful` | dizzy |
| `sweat` | 流汗 | `neutral` | sweat |

> 设计依据：L0 的 21 个名字**直接采用 xiaozhi-esp32 `emoji_collection.cc` 的原名**（保证与生态词汇一致、可被社区理解），再补 3 个来自 StackChan 装饰器的标签（`dizzy` `sweat` `doubtful`）与 `embarrassed` 等已有名的合并处理。
> **社区情绪标签集（Plutch 八情绪 / Geneva Emotion Wheel / ClueLab）本轮未取得一手出处**（网络受限，见 §十一），且**官方固件并不使用它们**；我们的 L0 只需覆盖「可渲染的 21+3 项」，**没有必要引入外部情绪模型做映射依据** —— 这是本节最重要的判断：**自造一个 24 项的标签集，比接入 Plutch/Geneva 更贴合固件实际能力，且零外部依赖**。

---

## §七 声音克隆 / 数字分身 —— 许可矩阵（**商用风险重点**）

> 本节的结论是整个调研里**商业风险最高**的部分。

### 7.1 已确认的许可事实（来源类型：**上游 LICENSE 原文**）

| 项目 | 许可 | 商用风险等级 | 取数 |
|---|---|---|---|
| **RVC-Boss/GPT-SoVITS** | **MIT**（"Copyright (c) 2024 RVC-Boss"） | 🟢 代码 MIT | https://raw.githubusercontent.com/RVC-Boss/GPT-SoVITS/main/LICENSE |
| **SWivid/F5-TTS** | **MIT**（"Copyright (c) 2024 Yushen CHEN"） | 🟢 代码 MIT | https://raw.githubusercontent.com/SWivid/F5-TTS/main/LICENSE |
| **rhasspy/piper**（原始仓库） | **MIT**（"Copyright (c) 2022 Michael Hansen"） | 🟢 代码 MIT | https://raw.githubusercontent.com/rhasspy/piper/master/LICENSE.md |
| **coqui-ai/TTS**（XTTS-v2 代码） | **MPL 2.0** | 🟡 代码 MPL 2.0（弱著佐权，可商用） | https://raw.githubusercontent.com/coqui-ai/TTS/dev/LICENSE.txt |
| **fishaudio/fish-speech** | **Fish Audio Community License v1.0（FACL）** | 🔴 **高** | https://raw.githubusercontent.com/fishaudio/fish-speech/main/LICENSE |
| **OHF-Voice/piper1-gpl** | ⚠️ **未取得**（仓库名含 `-gpl`，`LICENSE.md`/`LICENSE` 均 404，网络受限） | 🔴 **疑似 GPL 系** | 待补，见 §十一 |

### 7.2 🔴 Fish Speech（FACL v1.0）的商用限制 —— 逐条抄录原文

来源：https://raw.githubusercontent.com/fishaudio/fish-speech/main/LICENSE

- **收入门槛**：原文 "Fish Audio grants You a non-exclusive ... license to use, reproduce, distribute, and create Derivative Works of, and make modifications to the Fish Audio Materials for a Commercial Purpose, **but only while Your Annual Revenue is less than USD 500,000** (the "Revenue Threshold")"。
- **突破门槛后**：原文 "After the Transition Period, any use for a Commercial Purpose requires a separate written license agreement from Fish Audio"。
- **Hosted Service 一律禁止**（不看收入）：原文 "**no license is granted under this Agreement to offer a Hosted Service**, which requires a separate written license agreement from Fish Audio."
  - 但**明确豁免**了我们的场景："None of the following is a Hosted Service: **(1) generating speech for content that You create, select, or control, or that Your own product generates (for example, narration, dubbing, game or app characters, or an assistant's spoken replies), and delivering that speech in or with Your products or services**"。
  - → **StackChan 作为「自有产品 + 陪伴机器人语音回复」落在豁免 (1) 里**，只要我们不是把 Fish Speech 做成「用户上传样本就能克隆」的对外 API 服务。
- **强制署名**：原文 "you shall prominently display **"Built with Fish Audio"** on a related website, user interface, blogpost, about page, or product documentation."
- **声音克隆伦理红线（已写入协议）**：原文禁止 "generate speech that imitates the voice of an identifiable natural person **without that person's prior consent**"、"impersonate any person or organization in order to deceive, defraud, or harass"，并禁止 "intentionally remove, disable, circumvent, or obscure any watermark or provenance signal applied by the Fish Audio Materials"。
- **禁止用于训练其他模型**：原文 "You will not use the Fish Audio Materials ... to create, train, distill, or improve any foundational generative AI model or any speech, audio, or voice generation model"。
- **分发时的 Notice 义务**：须随分发附带 "These Fish Audio Materials are licensed under the Fish Audio Community License, Version 1.0. Copyright © 39 AI, INC. All Rights Reserved."

### 7.3 ⚠️ XTTS-v2 的**模型权重**许可与**代码**许可不同

- 代码：`coqui-ai/TTS` = **MPL 2.0**（已确认）。
- **模型权重（XTTS-v2）另有独立许可（CPML / Coqui Public Model License）**，该许可**限制商用**。
- **本轮未取得该权重许可原文**（`coqui-ai/TTS/dev/README.md` 取数时网络 `request timed out`，见 §十一）→ **在拿到原文前，不得把 XTTS-v2 列入商用候选**。

### 7.4 ⚠️ GPT-SoVITS / F5-TTS 的**预训练权重**许可同样独立于代码 MIT

- 代码是 MIT **不代表权重可商用**。GPT-SoVITS 的底模（HuBERT / SoVITS 预训练）、F5-TTS 的预训练模型各自带独立许可与使用限制。
- **本轮未取得权重许可原文**（网络受限）→ 见 §十一。

### 7.5 初步商用判断（待权重许可补齐后确认）

| 方案 | 代码许可 | 权重许可 | 商用 | 备注 |
|---|---|---|---|---|
| **Piper**（原始 rhasspy） | MIT | 需逐个查各 voice 模型 | 🟢 大概率可用 | 本地 TTS，速度快、内存小，**最适合 ESP32 侧或作为兜底音** |
| **Piper1-GPL** | ⚠️ 未取得 | — | 🔴 待查 | 仓库名暗示 GPL，**若确为 GPL-3.0 则不可闭源分发** |
| **F5-TTS** | MIT | 未取得 | 🟡 待查 | 零样本克隆，RTX 4070 8GB 可跑 |
| **GPT-SoVITS** | MIT | 未取得 | 🟡 待查 | 中文效果好，本项目首选候选；需 6–8GB 显存 |
| **XTTS-v2** | MPL 2.0 | 🔴 CPML（限制商用） | 🔴 商用受限 | 中文音色弱于 GPT-SoVITS |
| **Fish Speech** | FACL v1.0 | FACL v1.0 | 🟡 收入 < 50 万美元 + 必须署名 + 禁 Hosted Service | 有豁免条款可用，但条款负担重 |

---

## §十一 未取得与风险清单

> 本节登记本轮**网络反复重置 / 连接重置**导致的全部未取到项，以及由此产生的技术风险。
> 取数纪律见文首：抓不到写「未取得」，**严禁编造** star 数 / 版本 / 许可条款 / API 名 / 芯片型号。

### 11.1 未取得清单

| # | 未取到的内容 | 尝试过的路径 | 影响面 |
|---|---|---|---|
| U1 | **SillyTavern 角色卡 V2 规范一手原文**（`michalfurman/character-card-spec-v2` 的 `spec_v2.md` / `spec_v2.json`） | `raw.githubusercontent.com/.../main/...` → 14 字节 404；`.../master/...` → 404；jsdelivr `data.jsdelivr.com` 目录 API → 失败 | §4.1 的「生态字段清单」不能作为**已确认**规范，只能用官方 server 数据模型（本地 git 原文）替代 |
| U2 | **a16z-infra `character-card-spec` README 一手原文** | raw（main/master）均 404 | 同 U1 |
| U3 | **中文角色卡生态的公开规范/字段清单** | 无可用检索通道（本机 `web_search` 报 `MATRIX_TOOL_REQUEST_FAILED`） | §4.1 只能认定「生态惯例，无独立公开规范文件」 |
| U4 | **SillyTavern 服务端 LICENSE 一手原文**（AGPL 系） | 未取到 | 已按**最坏情况当作 AGPL** 处理：只借字段格式、不复制实现（§4.1 合规红线） |
| U5 | **ESP32-S3 数据手册**（是否片上集成 NFC 外设） | 未取到 | **不影响本项目结论**（官方本体用独立 NFC 模块，见 §6.1） |
| U6 | **官方机器人本体 NFC 模块的芯片型号 / 总线接口 / 读写能力**；**BSP 仓库 `m5stack/StackChan-BSP` 内的驱动 API** | 未取到 | §6.1 读卡方案只能给「方案 A/B/C + 待取证」，**不能断言**该模块是读卡器还是读写器 |
| U7 | **Apple CoreNFC 文档一手原文**（`NFCNDEFReaderSession` 读写语义、`NFCISO7816Tag` 写权限、entitlement 名称） | 未取到 | §6.2 相关表述标注为「背景知识，待一手核验」；**设计按「iPhone 不可写卡」的最保守假设推进** |
| U8 | **Zep 社区版（legacy）自托管步骤**（`getzep/zep` 的 `legacy/README.md`） | 404 | §3.2.3 只能确认「CE 已 deprecated（unsupported）」，**拿不到自托管步骤** |
| U9 | **`getzep/graphiti` 的独立 LICENSE 原文** | 未取到 | §3.2.3 只引用 zep 主仓 Apache-2.0（§3.1），**Graphiti 自身许可未确认** |
| U10 | **mem0 的图记忆（graph memory）能力细节**；mem0 自托管 server 的**具体 REST 端点清单** | README 只给出部署方式与 API key 机制 | §3.2.1 只按「HTTP API + API key」定性，**未臆造端点路径**；图记忆能力记为未取得 |
| U11 | **mem0 官方 Go SDK** | README 仅列 pip / npm | 结论：需自写 HTTP 封装（不影响选型） |
| U12 | **Letta V1 REST API 的端点细节 / V2 App Server 的协议文档** | `docs.letta.com` 页面未取到 | §3.2.2 只按定性结论（无 Go SDK、需 Node 22.19+）写 |
| U13 | **`tts_speech_speed` / `asr_speed` 的官方取值集合** | 未取到 | §4.2 人格包中这两个字段**保持 string 透传**，不设枚举 |
| U14 | 本报告 §十「复用决策汇总」**未编写** | 本轮范围外 | 需下一轮补齐（可由 §3.2.5 / §7.5 / §八 / §九 的结论直接汇总） |

### 11.2 风险清单

| # | 风险 | 等级 | 依据 / 应对 |
|---|---|---|---|
| R1 | **上游仓库形态突变**：letta 主仓变 stub、zep 主仓只剩 examples（CE 弃用） | 🔴 高 | §3.2 —— 只依赖 **HTTP 边界 + 锁定版本**，不 vendor 上游仓库、不假设「clone 主仓即可自托管」 |
| R2 | **mem0 默认嵌入走 OpenAI**（`text-embedding-3-small`） | 🔴 高 | 隐私 + 出网合规 + 成本 → 必须自配**本地嵌入模型**（README 提到可换 Qwen/gte 类模型） |
| R3 | **NFC 驱动未开源**（不在官方仓库、不在 xiaozhi-esp32） | 🔴 高 | §6.1 —— 先做「REST 下发切人格」跑通人格链路，NFC 作为第二阶段；驱动工作量取决于芯片型号（U6） |
| R4 | **iPhone 不能写卡**（`NFCNDEFReaderSession` 为读会话） | 🟡 中 | §6.2 —— 写卡端改用 Android App 或产线 USB 读卡器（推荐产线） |
| R5 | **替换 AI 层后固件协议面失配**（官方 AI 层是小智平台转发） | 🟡 中 | §0.1 / §5.7 —— 逐项对齐：情绪 8 字符串（§9.2）、表情/动作 schema（§9.4）、WS opcode 表（§5.1） |
| R6 | **「300+ 表情与动作」在官方仓库不成立** | 🟡 中 | §9.4 —— 已实证为「21 emoji / 6 情绪 / 5 装饰 / 15 维参数」，不要按 300+ 做资产规划 |
| R7 | **声音克隆权重许可未取得**（GPT-SoVITS / F5-TTS / XTTS-v2） | 🔴 高 | §7.3 / §7.4 —— 在拿到权重许可原文前不得商用；XTTS-v2 暂不列入候选 |
| R8 | **Fish Speech FACL v1.0 条款负担**（收入门槛 / 强制署名 / 禁 Hosted Service） | 🟡 中 | §7.2 —— 落在「自有产品语音回复」豁免 (1)，但**不能**做成「用户上传样本即可克隆」的对外 API |
| R9 | **人格包可信链**（卡可复制、固件无吊销表） | 🟡 中 | §5.8 / §6.5 —— 验签与吊销**一律在服务端**；固件只做格式校验 |
| R10 | **切换风暴 / 会话串人格** | 🟢 低 | §5.8 —— `Revision` + 节流；mem0 按 `persona_id` 分区记忆（`filters`） |
| R11 | **官方固件与开源仓库不同步** | 🟢 低 | 官方 README 自述 "Update of this repo could be a little late than the released firmware and mobile app" → 取数以仓库为准，实际行为需实机核对 |

---

## 文末自查

> 每条结论标注**取数来源类别**：`上游 LICENSE 原文` / `上游 README 原文` / `上游 API 文档原文` / `本地 git 原文` / `本地 clone 源码` / `自造设计` / `未取得`。

| # | 结论 | 来源类别 | 出处 |
|---|---|---|---|
| C1 | 官方 server 的 AI 层 = xiaozhi.me 转发代理（`baseUrl = "https://xiaozhi.me/"`） | 本地 git 原文 | §0.1，`server/internal/xiaozhi/xiaozhi.go:45-49` |
| C2 | 传输层 = gorilla/websocket v1.5.3（GoFrame v2 / Go 1.26.3 / MIT） | 本地 git 原文 | §0.2，`server/go.mod:1-9` |
| C3 | pipecat = BSD-2-Clause；livekit/agents = Apache-2.0 | 上游 LICENSE 原文 | §2.1 |
| C4 | pipecat 官方支持 MiniMax TTS；MiniMax 不在 Speech-to-Speech 类 | 上游 README 原文 | §2.2 / §2.4 |
| C5 | mem0 = Apache-2.0 / letta = Apache-2.0 / zep = Apache-2.0 / langgraph = MIT | 上游 LICENSE 原文 | §3.1 |
| C6 | mem0 三形态（Library / **Self-Hosted Server** / Cloud），自托管 `docker compose up` → `:3000`，含 Dashboard + Auth + API Key | 上游 README 原文 | §3.2.1 |
| C7 | mem0 默认嵌入 = OpenAI `text-embedding-3-small`；`[nlp]` 增强提供 BM25 + 实体抽取 | 上游 README 原文 | §3.2.1 |
| C8 | **letta 主仓已 stub**（源码迁至 `letta-ai/letta-code`），V1 server 在 `archive` 分支，自托管改走 App Server | 上游 README 原文 | §3.2.2 |
| C9 | **zep 主仓 = Zep Cloud 的 examples/integrations**，CE 在 `legacy/` 且 deprecated | 上游 README 原文 | §3.2.3 |
| C10 | Graphiti = 时序知识图谱（entities / facts + 有效期 / episodes / communities），Self-hosted only，自带 Neo4j / FalkorDB / Neptune | 上游 README 原文 | §3.2.3 |
| C11 | zep-go = `github.com/getzep/zep-go/v4`，Go ≥ 1.13，但面向 Zep Cloud | 上游 README 原文 | §3.2.3 |
| C12 | langgraph = 低层编排框架，Python / JS 双栈，**无 Go** | 上游 README 原文 | §3.2.4 |
| C13 | 官方人格字段全集（`character` / `memory` / `memory_type` / `tts_voice` / `tts_speech_speed` / `tts_pitch` / `asr_speed` / `knowledge_base_ids` / `mcp_endpoints` / `share_agent_id` …） | 本地 git 原文 | §4.1.1，`server/internal/model/xiaozhi/agent.go:39-113` |
| C14 | SillyTavern V2 规范 / a16z 规范 / 中文生态规范的具体字段清单 | **未取得**（U1–U3） | §4.1、§11.1 |
| C15 | 我们的「人格包 schema」（字段、枚举、版本、Ed25519 签名、情绪/音色绑定） | **自造设计** | §4.2 |
| C16 | WS 二进制帧 = `1 byte msgType + 4 bytes length(BE) + payload`；opcode 表含 `0x03 ControlAvatar` / `0x04 ControlMotion` / `0x14 Dance` | 本地 git 原文 | §5.1，`server/README.MD:931-964`、`server/internal/web_socket/web_socket.go:29-56` |
| C17 | 连接按 mac 维护长连接（`stackChanClientPool`）、握手 RSA token ±10s、每连接发送队列 100 + 独立写协程、5s 心跳 / 15s 清理 | 本地 git 原文 | §5.1 |
| C18 | 「切人格不重连、不重启」在协议层天然成立；原子切换 = 一次 `atomic.Pointer.Store`；轮次快照保证不串人格 | 本地 git 原文 + **自造设计** | §5.1–§5.3 |
| C19 | 固件**零改动**即可切人格（人格/音色/语速均在服务端）；可选加 1 个 `0x1B PersonaChanged` opcode | 本地 git 原文 + **自造设计** | §5.5–§5.7 |
| C20 | 硬件：CoreS3 / ESP32-S3 / 16MB Flash / 8MB PSRAM；**机器人本体自带 "a full-featured NFC module"** | 本地 git 原文 | §6.1，`README.md:13,15` |
| C21 | 官方开源固件栈**零 NFC 驱动代码**（仓库检索 + xiaozhi-esp32 v2.2.4 检索） | 本地 git 原文 + 本地 clone 源码 | §6.1 |
| C22 | NFC 芯片型号 / 总线 / 读写能力；BSP 驱动 API | **未取得**（U6） | §6.1、§11.1 |
| C23 | `NFCNDEFReaderSession` 为**读**会话；iPhone 写卡需 `NFCISO7816Tag` + entitlement | **未取得**（U7，按最保守假设采用） | §6.2 |
| C24 | NDEF 只存 `persona_id + schema_version + key_id + Ed25519 签名(+exp/fb)`，人格包本体留服务端 | **自造设计** | §6.3 |
| C25 | 端到端时序（读卡 → 现有 WS 上报 `0x1B` → 服务端验签/吊销 → 原子切换 → 下一轮生效）与 7 类失败处理 | **自造设计** | §6.4、§6.5 |
| C26 | 情绪标签体系 L0（24 项）+ L1 降级 + L2/L3 参数化 | **自造设计**（schema 复用官方） | §9.5 |
| C27 | 固件情绪枚举 6 个 / 对外字符串 8 个 / 装饰器 5 个 / emoji 21 个 | 本地 git 原文 + 本地 clone 源码 | §9.1–§9.3 |
| C28 | Ollama 支持 JSON Schema 结构化输出、`seed` 复现、function calling | 上游 API 文档原文 | §8.1 |
| C29 | 声音克隆四家的代码许可与 Fish Speech FACL 条款逐条原文 | 上游 LICENSE 原文 | §7.1–§7.2 |
| C30 | XTTS-v2 / GPT-SoVITS / F5-TTS 的**权重许可**、Piper1-GPL 的 LICENSE、Fish Speech 托管依赖 | **未取得** | §7.1、§7.3、§7.4、§11.1 |
| C31 | 本报告 §十「复用决策汇总」尚未编写 | **未完成**（U14） | §11.1 |

> **未完成项汇总**：§十（U14）+ 上表 30 条未取得项，均已在 §十一 登记；**在补齐前，相关结论不得进入商用决策**。

