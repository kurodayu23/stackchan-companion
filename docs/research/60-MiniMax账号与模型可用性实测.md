# 60 号 · MiniMax 账号与模型可用性实测（2026-10-24）

> 类型：**实测探测**（全部为本机真实调用返回，非文档摘抄）
> 探测脚本：第 1 轮 `r59\probe_minimax.py` / `r59\probe_models.py`；第 2 轮 `r60\probe_new_key.py` / `r60\probe_tts.py` / `r60\probe_endpoints.py` / `r60\probe_detail.py`
> ⚠️ API Key 只从用户级环境变量 `MINIMAX_API_KEY` 读取，**不写盘、不回显**（本号不含任何 key 片段）

---

## 订正说明（第 2 轮 · 换 key 后重测）

| 订正项 | 第 1 轮结论（旧 key） | 第 2 轮结论（新 key，本号当前内容） |
|---|---|---|
| 可用模型 | 只有 `MiniMax-M3` + `MiniMax-M3.1-Flash` | **6 个可用**：`M3.1-Flash` / `M3` / `M2.7` / `M2.7-highspeed` / `M2.5` / `M2.5-highspeed`；`M2.1` / `M2.1-highspeed` / `M2` 三个仍 2069 |
| `MiniMax-M2.5` | 「已下线（2069）」 | ⛔ **该结论被推翻**：新 key 下**两个端点都 HTTP 200 正常返回** ⇒ 第 1 轮是把「旧端点整体失效」误判成了「模型下线」 |
| 旧端点 `/v1/text/chatcompletion_v2` | 「全面失效，所有模型 2069」 | ⚠️ 新 key 下**可用**（`M3.1-Flash` / `M3` / `M2.7` / `M2.5` 均正常返回）⇒ 同样是**账号级**结论，不是端点级 |
| `reasoning_content` | 未验证（402 挡在前面） | ✅ **已验证存在**（`MiniMax-M3.1-Flash`），但**非必现**、且不同模型载体不同 |
| 阻塞 | 余额耗尽（402 / 1008） | ✅ **已解除**：旧 key 的 1008 是**该账号余额耗尽**，不是平台故障；换用有余额的账号后 chat 与 TTS 均已打通 |
| TTS | 余额耗尽，未生成 | ✅ 已生成真实 PCM（`female-shaonv`，11.68 s / 373 750 B）并跑通编译器 |

---

## 1. 结论先行

| 项 | 实测结论 |
|---|---|
| **Base URL** | ⭐ **`https://api.minimaxi.com`**（中国站）。`https://api.minimax.io` 对同一个 key 返回 `invalid api key (2049)` —— **49 号引用的海外域名对大陆账号不可用** |
| **⭐ 核心更正** | **「模型是否可用」是账号级属性，不是平台级属性。** 旧 key 下 `M2.7` / `M2.5-highspeed` 报 2069，新 key 下**同一模型可用** ⇒ 2069 `no longer available` **至少部分是账号 / 区域 / 权限维度的**。更进一步：本轮发现「旧端点整体失效」也曾被误判成「模型下线」 ⇒ 任何「某模型已下线」的说法都必须标注 **(账号, 端点, 测试时间)**；**换 key 必须重测** |
| **可用模型** | ⭐ **6 个**：`MiniMax-M3.1-Flash`、`MiniMax-M3`、`MiniMax-M2.7`、`MiniMax-M2.7-highspeed`、`MiniMax-M2.5`、`MiniMax-M2.5-highspeed`。`/v1/models` 仍列出 9 个，其中 3 个（`MiniMax-M2.1` / `MiniMax-M2.1-highspeed` / `MiniMax-M2`）调用时返回 `no longer available (2069)` |
| **选型端点** | 用 OpenAI 兼容的 **`/v1/chat/completions`**（本项目要 SSE + 推理内容）。旧端点 `/v1/text/chatcompletion_v2` 在新 key 下也能用，但**返回体没有 `reasoning_content`，也没有 `<think>` 分流字段** |
| **推理内容载体** | ⚠️ **不同模型不一样**：`MiniMax-M3.1-Flash` 把推理放在 **`reasoning_content` 字段**；`MiniMax-M3` / `MiniMax-M2.7` 把 `<think>` 原文**内联在 `content`** 里。客户端**两者都要处理**，且都**不能假定必现** |
| **TTS** | ✅ `/v1/t2a_v2` + `speech-02-hd` + `format=pcm` + `sample_rate=16000` + `channel=1` 可用；**6 个音色可用、4 个报 2054**；音色列表接口全部 404 |
| **当前阻塞** | ✅ **无**。旧 key 的 `insufficient balance (1008)` 是**账号级**（该账号余额耗尽），**不是平台故障**；换用有余额的账号后 chat 与 TTS 均已打通 |

---

## 2. 端点矩阵（实测）

| 端点 | 方法 | `api.minimaxi.com` | `api.minimax.io` |
|---|---|---|---|
| `/v1/models` | GET | ✅ HTTP 200，返回 9 个模型 id | ❌ 401 `invalid api key (2049)` |
| `/v1/chat/completions` | POST | ✅ 6 个模型可用，3 个返回 2069 | ❌ 401 `2049` |
| `/v1/text/chatcompletion_v2` | POST | ⚠️ 新 key 下可用，但返回体**无 `reasoning_content`** | ❌ 401 `2049` |
| `/v1/t2a_v2`（TTS） | POST | ✅ 可用 | ❌ 401 `2049` |
| `/v1/get_voice`、`/v1/voice/list`、`/v1/t2a_voice_list` | GET | ❌ 全部 404（音色清单走文档 / 控制台，不走这三个路径） | — |

> ⭐ **`/v1/models` 的可用性判断不可靠，选型必须逐个真调一次。**
> 实测：`/v1/models` 返回 **9 个**，但真调后实际能用的只有 **6 个**（第 1 轮旧 key 下只有 2 个）。
> 列表里**包含已下线模型**（`MiniMax-M2` / `MiniMax-M2.1` / `MiniMax-M2.1-highspeed` 这 3 个始终 2069）。
> ⇒ 只看列表选型会踩坑。

---

## 3. 模型可用性矩阵（9 个逐个真调）

> 测法：`POST /v1/chat/completions`，短问句 + `max_tokens=16`（与第 1 轮 `r59\probe_models.py` 同形），逐个真调。
> 第 2 轮结果为 **2026-10-24 晚**在**新 key** 下的复测；第 1 轮结果来自 `r59\probe_models.py` 的运行记录（旧 key，已不可复跑）。

| 模型 id | `/v1/models` 列出 | 第 1 轮（旧 key） | 第 2 轮（新 key，本号实测） | 第 2 轮备注 |
|---|---|---|---|---|
| `MiniMax-M3.1-Flash` | ✅ | 402 `1008` 余额耗尽 | ✅ HTTP 200 | `reasoning_content` **字段存在**（实测 63~64 字符）；长问句下未出现 ⇒ **非必现** |
| `MiniMax-M3` | ✅ | 402 `1008` | ✅ HTTP 200 | `<think>` **内联在 `content`** 里（短问句出现、长问句未出现） |
| `MiniMax-M2.7` | ✅ | 404 `2069` | ✅ HTTP 200 | `<think>` **内联在 `content`** 里；`usage.completion_tokens_details.reasoning_tokens = 14` |
| `MiniMax-M2.7-highspeed` | ✅ | 404 `2069` | ✅ HTTP 200 | — |
| `MiniMax-M2.5` | ✅ | 404 `2069`（⚠️ 当时打的是**旧端点**） | ✅ HTTP 200 | ⛔ 第 1 轮「已下线」是**误判**，见 §4 |
| `MiniMax-M2.5-highspeed` | ✅ | 404 `2069` | ✅ HTTP 200 | — |
| `MiniMax-M2.1` | ✅ | 404 `2069` | ❌ 404 `2069` | 两个端点都 2069 |
| `MiniMax-M2.1-highspeed` | ✅ | 404 `2069` | ❌ 404 `2069` | 两个端点都 2069 |
| `MiniMax-M2` | ✅ | 404 `2069` | ❌ 404 `2069` | 两个端点都 2069 |

> ⚠️ **错误码形态在两个端点不一样**：OpenAI 兼容端点返回 **HTTP 404** + `base_resp`；旧端点返回 **HTTP 200** + `base_resp.status_code = 2069`。
> ⇒ 判定「模型不可用」**不能只看 HTTP 状态码**，必须读 `base_resp.status_code`。

### 3.1 旧 key vs 新 key 的差异（核心）

| 模型 | 旧 key | 新 key | 结论 |
|---|---|---|---|
| `MiniMax-M2.7` | 2069 | ✅ 可用 | 同一模型，换账号即可用 ⇒ **2069 不是平台级下线** |
| `MiniMax-M2.5-highspeed` | 2069 | ✅ 可用 | 同上 |
| `MiniMax-M2.5` | 2069（当时打的是旧端点） | ✅ 可用（两个端点都可用） | 第 1 轮结论被本轮**推翻** |
| `MiniMax-M3` / `MiniMax-M3.1-Flash` | 402 `1008` 余额耗尽 | ✅ 可用 | **1008 是账号余额问题，不是平台故障** |
| `MiniMax-M2` / `M2.1` / `M2.1-highspeed` | 2069 | ❌ 2069 | 目前**两个 key 下都不可用**，是本号唯一跨账号稳定的结论 |

> ⚠️ **第 1 轮为什么会误判 `MiniMax-M2.5`**：第 1 轮的 `r59\probe_models.py` 模型清单只有 8 个，**根本不含 `MiniMax-M2.5`**；`M2.5` 是在 `r59\probe_chat.py` 里对**旧端点** `/v1/text/chatcompletion_v2` 打的，而那一轮旧端点对**所有**模型都返回 2069。
> ⇒ **端点级故障被当成了模型级下线。** 这是本号最值得记住的一条教训。

---

## 4. 与既有文档的冲突（必须订正）

| 既有结论 | 出处 | 现状 | 处置 |
|---|---|---|---|
| 「Apple `foundation-models-utilities` README 两处点名 `minimax-m2.5`」 | 49 号 | `MiniMax-M2.5` 在**旧 key 下**返回 `2069`；**新 key 下两个端点都 HTTP 200 可用** | 保留该引用（它说明的是**第三方库的写法**），但**不得据此选型**；选型以本号 §3 的实测为准 |
| 「走 OpenAI 兼容 `/v1/chat/completions` + SSE + `reasoning_content`」 | 49 号 | ✅ **端点正确**；`reasoning_content` **已实测存在**（`MiniMax-M3.1-Flash`） | ✅ 保留并补 §3；⚠️ 另需处理 `<think>` 内联的情况（§1「推理内容载体」） |
| `MiniMax-M2` 作为大脑 | 31 号 / 05 号早期设想 | ❌ 两个 key 下都 2069 | **必须换掉**（推荐 `MiniMax-M3.1-Flash` 或 `MiniMax-M3`） |

> ✅ **`reasoning_content` 已验证**：第 1 轮标注「未验证」的一项，本轮实测 `MiniMax-M3.1-Flash` 返回体中该字段存在（63~64 字符）。
> ⚠️ **但它不能被当成必有字段**：是否进入「思考」状态由模型自行决定，同一模型同一端点、不同 `max_tokens` / 提示词下**出现过也未出现过**。⇒ 客户端必须按**可选字段**处理，缺失时不能报错。

---

## 5. 对本项目的影响

| 项 | 影响 | 处置 |
|---|---|---|
| 05 号 / 31 号的「后端接 MiniMax」 | ✅ **阻塞已解除** | base URL = `https://api.minimaxi.com`；模型 id 用本号 §3 的实测值；key 从**用户级环境变量** `MINIMAX_API_KEY` 读，不落盘 |
| 59 号 §10 第 1 项「接真实 TTS PCM 跑编译器」 | ✅ **已执行** | **11.68 s 真实 TTS 音频已生成并跑通**：`female-shaonv` / `speech-02-hd` / `format=pcm` / `sample_rate=16000` / `channel=1` / **373 750 B**（见 `r59\minimax_tts_meta.json` 与 `r59\minimax_tts_16k.pcm`） |
| 04 号 / 05 号的「不接 MiniMax Realtime」 | 无影响 | 该结论仍成立 |
| 端侧 `Core AI` 路线（58 号） | 无影响 | 与 MiniMax 账号无关 |

---

## 6. 音色可用清单（实测逐个真调 `/v1/t2a_v2`）

| 音色 id | 结果 |
|---|---|
| `female-shaonv` | ✅ 可用 |
| `presenter_female` | ✅ 可用 |
| `male-qn-qingse` | ✅ 可用 |
| `audiobook_female_1` | ✅ 可用 |
| `Chinese (Mandarin)_Warm_Girl` | ✅ 可用 |
| `female-chengshu` | ✅ 可用 |
| `female-qn-qingse` | ❌ `2054 voice id not exist` |
| `female-tian-shan` | ❌ `2054 voice id not exist` |
| `female-yuejie` | ❌ `2054 voice id not exist` |
| `male-qn-jingxing` | ❌ `2054 voice id not exist` |

- 音色列表接口 `/v1/get_voice`、`/v1/voice/list`、`/v1/t2a_voice_list` **全部 404** ⇒ 音色清单**无法程序化枚举**，只能走官方文档 / 控制台。
- 实测生成参数：`model=speech-02-hd`、`format=pcm`、`sample_rate=16000`、`channel=1`、`bitrate=128000`、`stream=false`。
  - 短句（19 字）`female-shaonv`：**5.71 s / 182 788 B**（16 kHz 单声道 PCM）。
  - 端到端跑编译器那次（长文本）：**11.68 s / 373 750 B**，`r59\minimax_tts_meta.json`。
- TTS 的成功判据要看 **`base_resp.status_code == 0`**（本轮 6 个可用音色全部返回 `status_code=0` + `data.audio` 十六进制串），**不要只看 HTTP 状态码** —— 音色无效时返回的也是 **HTTP 200**。

### 6.1 两条工程纪律

1. **音色 id 无效（2054）与余额不足（1008）要分开判**，否则会把「没余额」误诊成「音色写错了」。
   实测：旧 key 下 `female-qn-qingse` 返回 **2054**（voice id not exist），而 `female-shaonv` 返回 **1008**（insufficient balance）—— 同一个接口、同一个账号，两种完全不同的病因。
   ⇒ 排查顺序：先看 `base_resp.status_code`，**2054 ⇒ 换音色 id**，**1008 ⇒ 换账号 / 充值**，两者不可互相推断。
2. **任何「某模型已下线」的说法，都必须标注「在哪个账号、哪个端点、什么时候测的」；换 key 必须重测。**
   本号就是反例：第 1 轮的「`M2.5` 已下线」「旧端点全面失效」两条结论，换 key 后**都被推翻**（§3.1）。

---

## 7. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:MINIMAX_API_KEY = [Environment]::GetEnvironmentVariable('MINIMAX_API_KEY','User')
py -3.12 "D:\AP\AP7000\ai-workspace\stackchan-research\r60\probe_new_key.py" --chat
py -3.12 "D:\AP\AP7000\ai-workspace\stackchan-research\r60\probe_tts.py"
py -3.12 "D:\AP\AP7000\ai-workspace\stackchan-research\r60\probe_endpoints.py"
```

> 脚本从**用户级环境变量**读 key；不打印、不落盘。第 1 条命令显式把用户级变量注入当前进程，避免其它 shell 读不到。

---

## 8. 未取得 / 未核实

| 项 | 说明 |
|---|---|
| 旧 key 下的原始响应体 | **未取得**（旧 key 已被替换，无法重跑）。第 1 轮的 2069 / 1008 结果来自 `r59\probe_models.py` 的运行记录与第 1 轮正文，**本轮不能复现验证**，只能作为「历史观测」引用 |
| 2069 的精确判定维度（账号 / 区域 / 权限 / 时间） | **未取得**。只能证明「换账号后同一模型从 2069 变可用」，**不能证明**平台侧的判定规则 |
| `reasoning_content` / `<think>` 的出现条件 | **未取得**。观察到「短问句多出现、长问句少出现、同一 prompt 也时有时无」，但**未做**系统性对照实验（固定温度、多次采样统计出现率） |
| 音色的完整清单 | **未取得**（列表接口 404）。只验证了上表这 10 个 id，**其余音色是否存在未知** |
| `MiniMax-M3` / `M2.7` 的独立推理字段 | **未取得**。观察到推理内容内联在 `content` 里，但**没有**确认它们是否在其它参数（如 `stream=true`）下会改走 `reasoning_content` 字段 |
| TTS 长文本的音画同步质量 | **未评估**。只验证了「能生成、字节数与 `sample_rate` 自洽」，**未听测**音质与韵律自然度 |
