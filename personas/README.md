# 人格包（通用层）

> **这一层是开源的、可社区 fork 的产品资产。**
> 它只影响 **system prompt 组装** 与 **表现参数**，**不改写已存的记忆**。

## 三层结构

| 层 | 位置 | 是否入库 | 作用 |
|---|---|---|---|
| 通用人格包 | `personas/<id>.json` | ✅ 入库 | 所有人共用的形象 / 声音 / 人设 / 技能四维 |
| 个人定制层 | `private/persona.local.json` | ❌ **永不入库** | 只在本机，覆盖通用层；可热改、可回滚 |
| 代码兜底 | `server/stackchan_ai/personas/<id>.json` | ✅ 入库 | 通用层缺失时的兜底，保证服务端永远有人格可用 |

**合并优先级**：`private/persona.local.json` > `personas/<id>.json` > 内置兜底。

- 标量字段（`name` / `summary` / `emotion` / `voice` / `system_prompt` …）：上层有值即覆盖。
- `speech_style`：整表覆盖。
- `personal`：**逐键合并**（上层只覆盖同名字键）。

## 文件格式

JSON。字段口径见 `server/stackchan_ai/persona.py` 的模块 docstring。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 人格 id，同时是文件名（`<id>.json`） |
| `name` | string | 名字 |
| `mbti` | string | MBTI 标签 |
| `summary` | string | 一句话介绍 |
| `emotion` | string | 韵律情绪基线（`prosody.EMOTION_BASELINE` 的键） |
| `voice` | string | TTS 音色 id（MiniMax 音色名） |
| `system_prompt` | string | 交给 LLM 的人格提示词 |
| `speech_style` | string[] | 说话风格标签 |
| `personal` | object | 表现参数（覆盖 `prosody.PERSONAL_DEFAULTS`） |

> ⚠️ **扩展名是 `.json`，不是 `.yaml`。**
> `docs/research/18` §6.1 与 `31` 号最初的设计稿用的是 YAML + `index.yaml` 清单，
> 那套设计**没有实现**；实现走 JSON（见 `persona.py` 的 `_candidate_dirs`）。
> 详见 `docs/research/18` 的「公开订正」段。

## 怎么加一个人格

1. 复制 `enfp.json` → `personas/<新id>.json`
2. 改 `id` / `name` / `summary` / `system_prompt` / `voice`
3. 服务端启动时自动可发现（`list_personas()` 扫 `personas/*.json`）

## 隐私边界

- `private/` 已在仓库根 `.gitignore` 里 ⇒ **个人定制层永不入库、不接后端、不进日志**。
- 引擎对 `private/` **只读不写**（`memory.py` 的 `_assert_private` 是写入侧的兜底）。
- 人格包**不承载记忆**；记忆在 `private/memory/`，与本目录物理隔离。
