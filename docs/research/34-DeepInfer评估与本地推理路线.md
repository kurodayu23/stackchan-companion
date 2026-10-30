# 34 · DeepInfer 评估：对我们**没有直接帮助**，但逼出了三个真结论

> 核实日期：2026-10-23
> 核实者：我本人（主会话）
> 评估对象：`D:\DeepInfer\DeepInfer`（用户提供的 DeepSeek 推理框架，Apache-2.0，已 clone 到本地）
> 结论口径：**读 README 原文 + 读 Python API 源码 + 实测本机硬件**

---

## 一、一句话结论

> **代码层面：用不上（三重硬不匹配）。**
> **但它逼出了 3 个真结论，其中第 3 个直接改我们的产品路线：**
> ① **我们的情绪状态机应该用「结构化输出」而不是「自由文本 + 解析」**；
> ② **人格一致性需要「确定性采样」**；
> ③ ⭐⭐ **我们的架构必须支持「LLM 跑在用户自己的机器上」—— 这才是「个人定制数据永不入库」的真正落地方式。**

---

## 二、它是什么（README 原文实读）

| 项 | 实测值 |
|---|---|
| 定位 | *"the high-performance inference framework that powers DeepSeek's large-scale production services"* —— **DeepSeek 自己生产服务用的引擎** |
| 支持模型 | **只有 `DeepSeek-V4.1-Flash-1017`** 一个 |
| 支持硬件 | **NVIDIA SM100**（Blackwell 数据中心卡）或 **Huawei Ascend 950 NPU** |
| 构建要求 | **Linux** + GCC ≥ 13.0 + Python 3.12 + **CUDA 13**（NVIDIA）或 **CANN 9.2**（Ascend） |
| 许可 | **Apache-2.0** |
| 形态 | **离线推理**（`LLM.generate(prompts=[...], sampling_params=[...])` 批量 API） |
| 基准规模 | *"Measured on **4 SM100 GPUs for prefill and 64 for decode**"* |
| ⚠️ **不含** | README 明写：*"Required for a complete inference service (**not included in this release**): A KV cache system; VE/Prefill/Decode disaggregation; Load balancing across data-parallel replicas"* |
| 核心 kernel | FlashMLA / DeepGEMM / DeepEP / TileKernels / DeepSelect / 自研 TileLang kernels |
| 高级特性 | DSpark + 置信度调度验证（MTP draft）、SWA bounded replay、异步调度、**batch-invariant inference**、**确定性采样**、**结构化输出** |

**目录规模**：`csrc/` C++ 引擎 33 文件 + `deepinfer/` Python 223 文件 + `doc/` 1.51 MB（含 benchmark 帕累托图）= 7 MB 源码。

---

## 三、⭐ 为什么「用不上」——三重硬不匹配

### 3.1 硬件不匹配（**决定性**）

**本机实测**：
```
NVIDIA GeForce RTX 4070 Laptop GPU, 8188 MiB, 617.42
13th Gen Intel Core i7-13650HX | 20 逻辑核 | 23.7 GB 内存
D: 剩余 97.6 GB
```

| 要求 | 本机 | 判定 |
|---|---|---|
| **SM100**（Blackwell 数据中心卡） | RTX 4070 Laptop = **SM89**（Ada） | ❌ **架构代次不符** |
| Ascend 950 NPU | 无 | ❌ |
| 4 SM100 prefill / 64 SM100 decode | 1 张 8 GB 消费卡 | ❌ 差 3 个数量级 |

**为什么代次不可绕过**：FlashMLA / DeepGEMM / DeepEP / TileKernels 这些 kernel 依赖 **SM100 专属指令族**（`wgmma` / `tcgen05` 等），SM89 上**无法编译或无法走快路径**。这不是"显存小一点"的问题，是**指令集代次**问题。

### 3.2 模型不匹配
只支持 `DeepSeek-V4.1-Flash-1017`（MoE 大模型），权重体积远超本机 8 GB 显存 + 97.6 GB 磁盘余量。

### 3.3 环境不匹配
要求 **Linux + GCC 13 + Python 3.12 + CUDA 13**。本机是 Windows；虽有 VMware，但 **VMware 里的 CUDA 直通几乎不可用**，且 8 GB 显存装不下这个模型。

### 3.4 ⭐ 形态不匹配（**即使有 SM100 集群也不该用它**）
我们要的是**低延迟在线服务**（陪伴产品对延迟极敏感，每轮对话都要快）。
DeepInfer 的形态是**离线批量推理**：一次 `LLM.generate(prompts=[...])` 批处理，
而且 README 明说**真正撑生产的服务层（KV cache 系统、Prefill/Decode 分离、负载均衡）没有开源**。

→ 我们要的是 **OpenAI 兼容的 HTTP 端点**（`POST /v1/chat/completions`，SSE 流式），
DeepInfer **不提供 HTTP 服务层**。

**⇒ 结论：本机跑不动，形态也不合。代码直接用不上。**

---

## 四、⭐ 但它逼出了 4 条真结论（这些是真价值）

### 4.1 ⭐⭐ 结构化输出：我们的情绪状态机应该用它

DeepInfer 的 `SamplingParams` 实读（`deepinfer/sampling_params.py:13`、`:59`、`:82`）：

```python
SamplingParams(temperature=0, max_tokens=128,
                so_args={"schema_type": "json", "schema": json.dumps(json_schema)})
```
- `so_args` 支持 **三种约束**：`json`（JSON Schema）/ `regex` / `ebnf`（EBNF 文法）
- 官方示例 `examples/_structured_output.py` 给的 schema 形如：
  ```python
  {"type": "object",
   "properties": {"color": {"type": "string", "enum": ["red","green","blue"]},
                  "count": {"type": "integer", "enum": [1,2,3]}},
   "required": ["color","count"], "additionalProperties": False}
  ```

**对我们的意义**：
我们的情绪状态机本来要让模型同时产出「**说什么** + **什么情绪** + **什么动作**」。
如果用自由文本再解析，就是"猜"；用 schema 约束，就是"**声明**"：

```json
{
  "reply": "……",
  "emotion": "开心",
  "motion": "点头",
  "intensity": 0.7,
  "followup": "你今天吃饭了吗"
}
```

→ **一个 schema 同时锁住回复与情绪枚举**，情绪映射到官方 `avatar::Emotion` 就不再靠正则碰运气。
→ **这条要写进 `server/providers/` 的接口契约**（见 §六）。

### 4.2 ⭐ 确定性采样：人格一致性的硬需求

`SamplingParams(seq_seed=<uint64>)`（`sampling_params.py:44`、`:61`、`:74`、`:104` 校验范围）。

→ 同样的上下文 + 同样的种子 → **同样的输出**。
→ 对陪伴产品：**"它的性格是稳定的"** 不能靠模型心情。
→ **落点**：我们的**人格包**应该带一个 `seed` 字段；`server/providers/` 接口要支持透传 seed。

### 4.3 ⭐ batch-invariant inference：陪伴连续性
*"Batch-invariant inference: keep model results identical across different batch compositions."*（`DEEPINFER_BATCH_INVARIANT=1`）

→ **不能因为同时有别人的请求在跑，就让小栈这次的回答变了。**
→ 对多用户自建后端（甚至单机多会话）这是硬需求 → 接口层要留这个开关位。

### 4.4 ⭐ DSpark / 置信度调度验证（MTP）→ 降延迟
用 draft token 加速解码，`DEEPINFER_USE_NEXTN_DECODE` 控制最大 draft 长度（默认 5）。

→ **陪伴产品对首字延迟最敏感**（用户说完话到小栈开始出声的间隔）。
→ 这是 DeepSeek 为了压延迟做的工程，**说明"首字延迟"是当前大模型服务的核心战场** → 我们的 provider 接口应该把 **TTFT（首字延迟）** 当一等指标记录，而不是只记总耗时。

---

## 五、⭐⭐⭐ 最重要的结论：**架构必须支持「LLM 跑在用户自己机器上」**

### 5.1 为什么这件事对 StackChan 特别重要

我们的**第一差异化**是「个人定制数据永不入库」（`PRODUCT.md` §7 / 宪法 / `19` 号 Floor）。
但如果 LLM 走云端（MiniMax / DeepSeek / 任何一家），**对话内容必然上云**。
`mask_sensitive_info` 是**内容脱敏**，**不是不外发** —— 这两件事必须分清楚。

**「它在你自己的机器上思考」才是隐私的真正实现**，而不是"我们承诺不上传"。

### 5.2 本机完全跑得动合适的模型

| 项 | 本机 | 可跑什么 |
|---|---|---|
| 显存 | 8 GB | 7B/8B 的 Q4_K_M 量化（≈5–6 GB），14B 部分量化 |
| 内存 | 23.7 GB | 可跑 14B Q4 / 20B 量化；还能留出空间给 KV cache |
| 磁盘 | D: 97.6 GB | 够放 2–3 个量化模型 |

**对陪伴产品，7B–14B 本地模型其实够用**，而且：
- **延迟更低**（本地 30–80 tok/s，远好于云端往返 + 排队）
- **零 token 成本**
- **数据完全不出本机**
- **断网可用** —— ⭐ 这是所有竞品（Replika / Character.AI / Vector / Loona）**都做不到**的事

### 5.3 ⭐ 正确路线：**不是用 DeepInfer，是用 OpenAI 兼容的本地推理**

我们要的是一个 **HTTP 端点**，不是一个 C++ 引擎。正确选型：

| 方案 | 提供什么 | 我们的接入方式 |
|---|---|---|
| **llama.cpp** | `llama-server` 提供 **OpenAI 兼容** `/v1/chat/completions`；⭐ **GBNF grammar** 约束解码（等价于 DeepInfer 的 `ebnf`）；⭐ `seed` 参数（等价于 `seq_seed`）；⭐ `response_format: json_schema` | ⭐ **首选**。Windows 原生二进制，本机直接跑，量化生态最全 |
| **Ollama** | 本地 HTTP API（OpenAI 兼容子集）+ 模型管理 | 备选：上手最快，模型拉取方便 |
| **vLLM** | OpenAI 兼容 server + `guided_json` / structured outputs | 备选：Linux + NVIDIA 多卡时更优；**本机 Windows 不友好** |

⭐ **llama.cpp 的 GBNF 与 DeepInfer 的 EBNF 是同一个思路** → 说明「用文法约束生成」是**业界共识做法**，不是 DeepInfer 独有 → **我们的设计方向被第三方印证了**。

### 5.4 ⇒ 架构修改：`server/providers/` 必须有两个实现

```
server/providers/
├── minimax/     云端默认实现（MiniMax Chat + TTS WebSocket）
└── local/       本地实现（OpenAI 兼容 → llama.cpp / Ollama / vLLM）
```
- 两者都实现**同一个接口**（`chat` / `tts` / `structured_output` / `seed` / `ttft` 指标）
- **切换靠配置**，用户选"云端"或"本地"（这是**产品功能**，不是工程细节）
- 本地模式下：对话**不产生任何外发请求** → 「个人定制数据永不入库」**才成立**
- 本地模式还顺带解决：**断网可用**、**无 token 成本**、**不被模型下线打断**

---

## 六、⚠️ 这条评估暴露的一个**必须回头核实**的问题

`18` 号文档 §四对 MiniMax Chat 参数的实测记录：

> `response_format`：`json_schema` —— **原文明确 "only supported by `MiniMax-Text-01`"**

而我们的主力模型是 **`MiniMax-M3.1-Flash` / `MiniMax-M3`**（`18` 号 §4.5）。

⇒ **如果 M3 系列不支持 `json_schema` 约束生成，那么 §4.1 的"情绪状态机用结构化输出"在云端模式下就没有现成实现。**

**这一条必须核实清楚**，因为它决定情绪状态机的实现路线：

| 方案 | 可行性 |
|---|---|
| A. MiniMax 主力模型若支持 json_schema | ✅ 最省事：直接用 schema 约束 |
| B. 若不支持 → prompt 约束 + 严格解析 + 失败兜底 | ⚠️ 可行但脆（模型偶尔不吐合法 JSON） |
| C. 若不支持 → **用本地模型做「情绪解析器」**，云端只负责说话 | 🔀 复杂但**分离职责**清晰 |
| D. 若不支持 → 情绪由**规则**从文本特征推导（关键词/标点/长度） | 🛠️ 最弱但零依赖 |

⇒ **待办**：核实 MiniMax M3 系列的 `response_format` / 结构化输出支持情况（官方文档原文）。

---

## 七、对既有决策的影响

| 决策 | 是否改变 |
|---|---|
| 「不接 MiniMax Realtime，走 Chat + TTS 两段式」 | ❌ 不变 |
| 「接 MiniMax 做大脑」 | ❌ 不变（仍是默认 provider） |
| 「人格三层分离：通用引擎 / 通用人格包 / 个人数据永不入库」 | ⭐ **加强** —— 只有 provider 支持本地运行，"永不入库"才从承诺变成事实 |
| 「后端 fork 官方 GoFrame server」 | ❌ 不变 |
| 「人格包热更新 / 版本 / 回滚」 | ⭐ 增强 —— `server/providers/` 抽象让 provider 也可配置 |
| 新增 | ⭐ **计划新增 `server/providers/local.py`**（OpenAI 兼容本地推理）作为**第二 provider**（**尚未实现**） |
| 新增 | ⭐ **provider 接口必须支持：结构化输出 / seed / TTFT 指标**（见 §四） |
| 新增 | ⭐ **「离线模式」是一个产品功能**（断网可用 + 零成本 + 不外发） |

---

## 八、未核实 / 未取得（如实登记）

1. **MiniMax M3 系列的 `response_format` / 结构化输出支持** —— 未核实（§六 的待办）。
2. **DeepInfer 实际能不能编译** —— 未编译（本机硬件与平台三重不匹配，编译无意义）。
3. **`vendor/` 子模块内容** —— 空（未 `git submodule update`），不影响结论。
4. **DeepSeek-V4.1-Flash-1017 的权重体积** —— 未查（HF 页面未取）。
5. **llama.cpp / Ollama / vLLM 在本机的实际可用性与量化模型体积** —— **未实测**。本轮只核了 DeepInfer 的 README 与 API 源码；§五.3 的候选是**基于已知的通用事实**，**未在本机跑过**。
6. **DeepInfer 是否有 WebSocket / 流式输出** —— 未逐字读 `deepinfer/engine/llm_engine.py` 的流式路径（离线 API 形态看是不强调流式）。
7. **`doc/` 里的 benchmark 图** —— 未读（1.51 MB 多为图片）。
8. **DeepInfer 与我们 fork 的 GoFrame server 的任何集成点** —— 无。形态不同，不存在直接集成。

---

## 九、附：取证方式

- README 原文：`D:\DeepInfer\DeepInfer\README.md`（本地实读全文 107 行）
- Python API：`deepinfer\sampling_params.py`（`:13` `class SamplingParams` / `:39` `so_args` 说明 / `:44` `seq_seed` 说明 / `:59`、`:61` 参数 / `:82` 赋值 / `:104` 范围校验）
- 结构化输出示例：`examples\_structured_output.py`（`schema_type` 三值 + JSON Schema 样例）
- 目录规模：`csrc/` 33 文件、`deepinfer/` 223 文件、`doc/` 1.51 MB、`.git` 2.4 MB，总计 371 文件 / 7 MB
- 本机硬件：`nvidia-smi --query-gpu=name,memory.total,driver_version` → RTX 4070 Laptop / 8188 MiB / 617.42；`Win32_ComputerSystem` → 23.7 GB
- 许可：README *"DeepInfer is released under the Apache License 2.0"*

*DeepInfer © DeepSeek-AI · Apache-2.0 · 本文档只做评估，未复制其代码。*
