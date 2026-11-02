# 101 · 本地推理 provider 与「个人数据永不出网」的机器化

> **一句话**：把 M-05 护城河项「个人数据永不入库」从**产品文案**变成**代码里强制 + 机器可判**的事 ——
> 新增 `server/providers/local.py`（OpenAI 兼容，**构造时就拒绝非回环地址**）+ 新门禁 `tools/check_local_provider.py`
> （**第 48 / 49 项**，6 条判据 + 7/7 变异自检）。
>
> ⚠️ **诚实边界**：本机**没有** Ollama / llama.cpp ⇒ 接口形状的依据是**两个项目的官方文档原文**（URL 见 §二），
> **不是**实机实测；行为验证全部用**真回环地址上的假服务器**完成。

---

## 一、起因：Q14 —— 这条护城河项一直停在「计划中」

| 出处 | 原文 | 状态 |
|---|---|---|
| `docs/spec/05` §二 T4 | 「本地模型是否进 P0 → **不进**。P0 只做 MiniMax；本地模型放 P4 之后当差异化」 | 排期裁决（不变） |
| `docs/spec/05` §二 T4 的 Q 栏 | 「`server/providers/local.py` **计划新增**，做不做」 | **Q14 待拍板** |
| `docs/spec/07` §3.5 Q14 | 「它是 M-05 护城河项（『个人数据永不入库』从承诺变成事实），但要接 OpenAI 兼容后端（Ollama / llama.cpp）。**当前状态：计划中，未实现**」 | **未实现** |

⇒ 本轮做的事**不是**「把本地模型塞进 P0」（那会违反 T4 的排期裁决），
而是把 **Q14 的能力本身**做出来，并让「不出网」这条不变式**可机检**。

> ⚠️ **排期不变**：T4 仍然成立 —— 本地 provider **不进 P0**，默认链路仍是 MiniMax（`STACKCHAN_PROVIDER=auto`）。
> 这次只是把「以后要切本地时不必从零写」这件事提前做掉。

---

## 二、接口形状：**官方文档原文**，不是记忆

### 2.1 两个后端都提供 OpenAI 兼容的 chat 端点 ⇒ 一套代码吃两个后端

| 端点 | 请求 | 响应 | 出处 |
|---|---|---|---|
| `POST /v1/chat/completions` | `{"model", "messages":[{"role","content"}], "max_tokens", "temperature", "stream": false}` | `choices[0].message.content` | ① Ollama 官方 OpenAI 兼容文档（章节「`/v1/chat/completions`」）：<https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx> ② llama.cpp server 官方 README（章节「POST `/v1/chat/completions`: OpenAI-compatible Chat Completions API」）：<https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md> |

Ollama 官方示例里的 base URL 是 `http://localhost:11434/v1/`（两份文档都这么写）⇒
本仓的默认值取 `http://127.0.0.1:11434/v1`（`127.0.0.1` 而非 `localhost`：**绕开 DNS/hosts 解析**，见 §三）。

### 2.2 TTS：只有 Ollama 有，且是 **v0.40.8 才加的**

| 事实 | 原文 | 处置 |
|---|---|---|
| 端点 | `POST /v1/audio/speech`，请求 `{"model", "input", "voice", "response_format", "speed"}` | 只在**配了 `STACKCHAN_LOCAL_TTS_MODEL`** 时提供能力，否则明确报 `UNSUPPORTED` |
| 默认格式 | 「The default `response_format` is `wav`, **not** `mp3`」 | 我们**显式请求 `wav`** |
| 音频参数 | 「Audio is 16-bit, mono, **24 kHz**」 | ⚠️ **不写死 24 kHz** —— 我们**自己解 RIFF 头取真实采样率**（见 §四 LP-05） |
| 不支持的取值 | 「Unsupported values return a `400` error instead of being ignored」 | 400 → 按 `BAD_REQUEST` 分类报错，不静默降级 |
| llama.cpp | **没有**这个端点 | ⇒ 404/501 一律映射成 `UNSUPPORTED`（**能力缺失 ≠ 故障**） |

### 2.3 ASR：**不实现**（同一纪律的延续）

Ollama 的 OpenAI 兼容层**列了** `/v1/audio/transcriptions` 端点，
但本仓**没有抓过它的请求/响应形状** ⇒ 按「**无实测依据不做实现**」处理
（与 `providers/base.py` 对 MiniMax ASR 的同一条纪律）。

---

## 三、⭐ 隐私不变量的执行化：为什么不能只写在文档里

### 3.1 问题

「个人数据永不入库」如果只写在 README 里，它就是**一句文案** ——
改个默认 base URL、顺手把 `localhost` 换成内网 IP，它就悄悄破了，而且**没有任何东西会红**。

### 3.2 处置：让「不改对就起不来」

| 机制 | 做法 |
|---|---|
| **构造时拒绝** | `LocalProvider(base_url="http://example.com/v1")` ⇒ **直接抛 `ValueError`**，连对象都造不出来 |
| **双保险** | 即使显式 `allow_remote=True`，**仍必须**有环境变量 `STACKCHAN_LOCAL_ALLOW_REMOTE=1` 才放行 ⇒ 想破这条不变式需要**两个独立的显式动作** |
| **回环判定不做 DNS** | 只认 `localhost` / `*.localhost` / `127.0.0.0/8` / `::1` 的**字面量** ⇒ **解析一次 DNS 就可能被 hosts 劫持指向外网**，那「只发往本机」就变成了「发往一个我们以为在本机的东西」⇒ 宁可**误报**（把某个自定义本机域名判成非回环），不可**漏报** |
| **逃生口存在但显式** | 需要连局域网里的另一台机器跑模型时：显式环境变量 + 显式参数，**两条都写**才生效 |

### 3.3 一句话总结这轮的设计取向

> 护城河不能靠「我们不这么做」来守，要靠「我们这么做时**做不到错**」来守。

---

## 四、新增门禁 `tools/check_local_provider.py`（**第 48 / 49 项**）

| 码 | 判据 | 判法 |
|---|---|---|
| LP-01 | 非回环地址在**构造时**被拒（`allow_remote` 也必须环境变量双保险） | 行为 |
| LP-02 | 请求形状：chat → `/v1/chat/completions`（`stream:false`）；tts → `/v1/audio/speech`（`response_format:"wav"`） | 行为（**真回环假服务器**） |
| LP-03 | 配置认得 `STACKCHAN_LOCAL_*`；`STACKCHAN_PROVIDER=local` ⇒ `provider_name == "local"` | 行为 |
| LP-04 | **默认 base URL 常量必须解析到回环地址**（防默认值被改成云地址） | 源码 |
| LP-05 | `local.py` **不得硬编码采样率 24000**（必须从 WAV 头取真值） | 源码 |
| LP-06 | 注册表必须认 `local`（`available_providers()` + `build_provider` 分支） | 源码 |

### 4.1 门禁**零第三方依赖**（为什么）

`server/providers/__init__.py` 会 import `.stub` ⇒ **numpy**。
本门禁要能在 **CI 的 docs-gate job**（不装 numpy）里跑 ⇒ 用 `importlib` 造一个**合成包**，
只加载 `base.py` + `local.py`，**绕开 `__init__.py`** ⇒ 相对导入照常工作，依赖为零。

### 4.2 变异自检 7/7（证明判据不是摆设）

| 变异 | 被谁抓住 |
|---|---|
| 构造非回环地址时不再拒绝 | LP-01 |
| chat 路径改成非 OpenAI 兼容 | LP-02 |
| tts 请求体不再要 `wav` | LP-02 |
| 默认 base URL 指向外网 | LP-04 |
| 硬编码采样率 24000 | LP-05 |
| 注册表漏掉 `local` | LP-06 |

⚠️ **第一版夹具有两个是无效的**（改了文档串而不是代码 ⇒ 行为没变 ⇒ 判据当然抓不到），
**这正是「变异夹具必须能证明判据有分辨力」的意义**：夹具无效 = 判据可能已经失效了但没人知道。
⇒ 已改成带上下文的精确替换。

---

## 五、验证结果

| 项 | 结果 |
|---|---|
| 新门禁（真实仓） | ✅ **6/6 判据 PASS**，FAIL=0 |
| 新门禁自检 | ✅ **7/7 PASS**（干净夹具 0 FAIL + 6 个变异全被抓） |
| 后端测试 | ✅ **130 个全绿**（原 102 + 新增 28 个本地 provider 测试） |
| 全量门禁 | ✅ **49/49 PASS**（47 → 49：新增门禁本体 + 其自检） |
| U+FFFD | ✅ **0** |
| CI（ubuntu） | ⏳ 待复跑（见 §六） |

---

## 六、未验证 / 遗留

- ⛔ **没有真机 Ollama / llama.cpp** ⇒ 本文档里所有接口形状的依据是**官方文档原文**，
  **不是**实机实测；「本地 provider 接真模型跑通一整轮对话」**未验证**。
  ⇒ 第一版接真机的验收方式：装 Ollama → `ollama pull llama3.2` → `STACKCHAN_PROVIDER=local` 起服务 → 走一遍对话与 TTS。
- ⚠️ 本地 **TTS** 只在 **Ollama v0.40.8+** 存在；llama.cpp 没有 ⇒ 只做 chat 是常态。
- ⚠️ **「个人数据永不入库」目前只覆盖「对话正文」**（模型请求体）；
  **记忆 / 档案**的切分仍按 **Q5** 待拍板（读法 A/B），本轮**没有**擅自改。
- ⚠️ 本地模型的**质量**（小模型能不能撑住 ENFP 人格）**完全未评估** ⇒
  这也是 T4「不进 P0」的实质原因，不是保守。

---

## 七、落点

| 落点 | 内容 |
|---|---|
| `server/providers/local.py` | **新增**：本地推理 provider（回环守卫 / OpenAI 兼容 chat / wav TTS / 自解 RIFF 头） |
| `server/tests/test_local_provider.py` | **新增**：28 个测试（回环判定 / 隐私不变量 / 请求形状 / WAV 解析 / 注册与配置） |
| `server/providers/base.py` | 加 `ProviderKind.LOCAL` |
| `server/providers/registry.py` | 注册 `local`（`available_providers()` + `build_provider` 分支） |
| `server/providers/__init__.py` | 导出 `LocalProvider` |
| `server/stackchan_ai/config.py` | 加 `STACKCHAN_LOCAL_*` 六项配置 |
| `tools/check_local_provider.py` | **新增**：门禁第 48/49 项（6 判据 + 7 变异自检） |
| `tools/gates.txt` | +2 行 ⇒ **47 → 49 项** |
| `.github/workflows/ci.yml` | docs-gate job +2 步（本体 + 自检） |
| `docs/spec/05` §二 T4 | 标注 Q14 已实现（**排期不变：仍不进 P0**） |
| `docs/spec/07` §3.5 Q14 | 销账 |
| `docs/spec/09` §二 | 资产快照同步（server 22 源文件 / 8 测试文件 / tools 31 / 门禁 49 / 测试 130） |

**抓取来源**（可复现）：
- Ollama OpenAI 兼容文档：<https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx>
- Ollama 原生 API + openapi.yaml：<https://github.com/ollama/ollama/blob/main/docs/api.md> · <https://github.com/ollama/ollama/blob/main/docs/openapi.yaml>
- llama.cpp server README：<https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>
