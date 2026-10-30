# 89 —— Figma 接入实测与「Figma → AI」落地管线

> **一句话结论**：Figma Connector 已接入且**只有 2 个只读/导出工具**（不能替我们画稿、不能改用户文件）；
> 10 次真实调用里 **9 次返回 `figma_not_found`** ⇒ **不是 fileKey 错，是当前 Figma 账号看不到社区文件**；
> 因此本轮**没能**读到 Apple 官方 iOS 套件取到圆角真值（`research/06` U2 **仍未销账**），
> 但 Figma 的**真正价值路线**已定并已落地第一段工具：**把用户的设计稿变成可判的数值漂移报告**。

- 日期：2026-10-27
- 触发：用户「我给你接入了 figma，如何利用 figma 做 ai 呢」
- 性质：**只读取证 + 一件新工具交付**（未改动任何产品逻辑代码）

---

## 一、结论速览

| # | 结论 | 证据 |
|---|---|---|
| 1 | Figma Connector **已连上**，provider `figma`，共 **2 个工具** | `mcode-tools connector tools --keyword figma` |
| 2 | 两个工具**都是只读/导出型**：`get_figma_data`（读）、`download_figma_images`（导出签名 URL） | 逐个 `connector tool` 查 schema |
| 3 | **不能替用户画稿、不能改用户文件** | 目录里没有任何写/创建/更新类工具 |
| 4 | **10 次真实调用**：9 次 `figma_not_found`、1 次本地网络错误 | §2.2 |
| 5 | **不是 fileKey 错**：`1651309003795292092`（Apple iOS 27 套件）已被 **2 个独立来源**交叉验证为正确 | §2.3 |
| 6 | ⇒ 根因是**当前连接的 Figma 账号看不到社区文件**（社区套件需账号内显式授权/另存） | §2.3 + §2.4 |
| 7 | `figma.com` **网页**本机被 CloudFront 403 拦截 ⇒ 授权动作**无法由本机代劳** | §2.5 |
| 8 | `api.figma.com` **可达**（403=缺 token，DNS/网络通） | `Invoke-WebRequest` 实测 |
| 9 | 已交付 `tools/figma_design_sync.py`：Figma 稿 ⇄ Swift DesignSystem **数值漂移体检**，自检 6/6 | §4 |
| 10 | Figma 在本项目的定位＝**只读输入源**（读稿→核数→校验/生成 SwiftUI），**不是**主稿载体 | §3 |

---

## 二、实测：Connector 能力与访问边界

### 2.1 Connector 目录（实测）

```
mcode-tools connector tools --keyword figma
```

返回 `partial: false`，provider `figma` 命中 2 个工具：

| 工具 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `connector__figma__get_figma_data` | 读布局 / 样式 / 文本 / 资源引用 | `fileKey`（必填，`^[a-zA-Z0-9]+$`）、`nodeId`（可选，`0:1` / `I1:2;3:4`）、`depth`（可选 1~100） | `output_schema` 声明为 **null**（未声明） |
| `connector__figma__download_figma_images` | 导出 PNG/SVG/GIF | `fileKey`、`nodes`（1~20，每项 `{nodeId, fileName}`）、`pngScale`（0.01~4，默认 2） | **签名 URL，有效期 1 小时**；**不接受 `localPath`** |

⚠️ 两个**结构性限制**，决定了 Figma 在本项目只能当**输入源**：

1. **无写接口** —— 目录里没有 create/update/delete 类工具 ⇒ **AI 不能替用户画 Figma 稿、不能改用户文件**。
2. **`output_schema` 为 null** —— 输出格式**未声明** ⇒ 任何解析器都只能按 **Figma 公开文档格式**写，并**必须 fail loud**（认不出输入就报 FAIL，绝不静默通过）。

### 2.2 十次真实调用

| # | fileKey | 工具 / 参数 | 结果 |
|---|---|---|---|
| 1 | `1651309003795292092` | `get_figma_data` depth=1 | `figma_not_found` |
| 2 | `1527721578857867021` | `get_figma_data` depth=1 | `figma_not_found` |
| 3 | `pDmGXdYu2k8xlf1SQoU9PW` | `get_figma_data` depth=1 | 本地网络错误 `UND_ERR_SOCKET`（**非 Figma 侧判定**） |
| 4 | `1121065701252736567` | `get_figma_data` depth=1 | `figma_not_found` |
| 5 | `1645923469870515372` | `get_figma_data` depth=1 | `figma_not_found` |
| 6 | `1251588934545918753` | `get_figma_data` depth=1 | `figma_not_found` |
| 7 | `1253443272911187215` | `get_figma_data` depth=1 | `figma_not_found` |
| 8 | `1250144691121363237` | `get_figma_data` depth=1 | `figma_not_found` |
| 9 | `1651309003795292092` | `get_figma_data` nodeId=`0:1` depth=1 | `figma_not_found` |
| 10 | `1651309003795292092` | `download_figma_images` nodeId=`0:1` | `figma_not_found` |

覆盖的 6 个 fileKey 分别是 Apple 官方 **iOS 27 UI kit / iOS 26 UI kit / iOS 16 社区套件 / App Icon 27 / macOS / visionOS**。

Figma 侧返回原文：

```
error: figma_not_found: Figma 文件、节点或图片不存在，或当前用户不可见。 (latency_ms=0)
```

⚠️ `latency_ms=0` 且错误文案是 **Figma 域的业务错误**（不是我们的 HTTP/鉴权错误）⇒ **连接器本身是通的**，是**文件这一层**过不去。

> 📌 一次**工具用法**失误（非 Figma 侧问题，已修）：PowerShell 下用
> `--args '{"fileKey":"...","depth":1}'` 内联 JSON 时，转义被吃掉，报
> `error: Connector arguments must be valid JSON`。
> **正解＝`--args-file <path>`**（本轮全部改用该写法后调用才真正打到 Figma）。

### 2.3 判定：不是 fileKey 错，是账号不可见

要把「key 写错了」和「账号看不到」分开，必须**独立验证 key 本身**。本轮用 `web_search` 做了交叉验证：

| fileKey | 独立来源给出的标题 / 状态 |
|---|---|
| `1651309003795292092` | 「iOS and iPadOS 27 Figma」—— slug `ios-and-ipados-27`，来源 A 与来源 B 两个独立结果集均给出同一 URL 与同一 slug；另一条来源称「Updated October 21, 2026」 |
| `1527721578857867021` | 「iOS and iPadOS 26 Figma」—— 「23.6k / 265k users / Updated July 24, 2026」 |
| `1645923469870515372` | 「iOS/iPadOS/watchOS 27 app icon template」 |

⇒ **key 已被多来源交叉验证为正确** ⇒ 排除「H1：key 错」。
⇒ 剩下唯一解释是 **H2：当前连接的 Figma 账号/令牌看不到这些社区文件**。
Figma 现行策略要求社区文件进入账号侧的**可访问授权范围**（或先「另存到我的文件」）才可被 API 读取；
社区套件**不随公开而自动可读**。

### 2.4 为什么本机代劳不了授权

| 端点 | 实测 | 含义 |
|---|---|---|
| `https://www.figma.com/community/file/...` | **HTTP 403**（CloudFront「Request blocked」） | 网页端被拦 ⇒ 无法在本机打开社区文件页去点授权 |
| `https://api.figma.com/v1/files/<key>` | **HTTP 403**（缺 token），但**连接建立成功** | API 域可达 ⇒ 网络不是问题，缺的是凭据与授权 |

⇒ 授权动作**必须在用户自己的 Figma 账号里点**，本机无法代办。

### 2.5 本轮未能取到的目标值（诚实记账）

`research/06` §B 的 **U2「iOS 各系统组件的官方圆角数值」** 本轮**尝试未成功、仍未销账**：
Apple 官方 iOS 26/27 套件读不到 ⇒ `spec/06` / `spec/08` 里那些「Apple HIG 查不到、靠估」的圆角数值
**本轮无法用官方套件回填**。已就地标注尝试记录（见 §5）。

---

## 三、⭐「Figma 做 AI」在本项目到底能做什么

先划边界，再谈用法。

### 3.1 能做（4 条管线）

#### 管线 A：Figma 稿 → **数值漂移体检** ⭐ 已落地

**问题**：本仓库的 iOS 视觉 token 目前有**三个真值源** —— `prototype/variants/*.html` 的 CSS 变量、
`ios/StackChanCompanion/DesignSystem/Tokens.swift` + `Shapes.swift`、以及将来用户的 Figma 稿。
三份东西**会漂**，而漂了没人知道。

**做法**：把 Figma 稿当**机器可读输入**，自动核对我们自己的 Swift token。

- 输入：Figma 文档 JSON（REST `GET /v1/files/:key` 形状）/ Figma Variables 导出 / DTCG 三选一
- 比对：`Shapes.swift` 的圆角与间距档、`Tokens.swift` 的 4 套调色板 12 槽位
- 输出：漂移报告（每条含 来源值 / 我们的值 / 判定）+ 归一化 token JSON（可入库做版本回归）

**收益**：Q15（视觉终选）一旦在 Figma 里定稿，**色值与圆角从「拍的」变成「从设计稿抄的、而且自动核过一致性」**。

#### 管线 B：Figma 变量 → DTCG → Style Dictionary → Swift

`research/06` 已经把 Tokens Studio / DTCG / Style Dictionary 的链路研究清楚了，但**一直缺一个起点**。
Figma Connector 补上了这个起点：用户在 Figma 里维护变量 → 导出 JSON → 走既有 SD 链生成 Swift token。
**这与本仓库的决策不冲突**（`research/07` §6 仍维持「不把 Figma 当主稿载体」）。

#### 管线 C：Figma 导出 @2x/@3x → **视觉回归基线**

`download_figma_images` 返回 1 小时有效的签名 URL ⇒ 导出 PNG/SVG 落进 `prototype/` 或 `assets/`，
作为「设计稿渲染结果」的基线图，和现有 Playwright 截图回归**互为参照**。
⚠️ 注意：Figma 稿**不是** iOS 原生度判据 —— 判据仍是 `prototype/ios/check_ios.py`（80 项）。

#### 管线 D：Figma 稿 → **设计走查清单**

把 Figma 稿解析成一份「这份稿违反了哪些已登记硬线」清单（触控目标 ≥ 44pt、字号 ≥ 11pt、
圆角是否在登记档内、颜色是否在调色板槽位内），让走查**可判**而不是靠眼力。

### 3.2 不能做（红线）

| 红线 | 原因 |
|---|---|
| ⛔ **让 AI 替用户画 Figma 稿** | Connector 无写接口；而且**所有面向人的 UI 必须用户过目** |
| ⛔ **把设备端 320×240 点阵 / 12 颗 LED 灯带图案放进 Figma** | 固件才是真值；Figma 稿会变成第二套真相源 |
| ⛔ **把 Figma 稿当 iOS 原生度判据** | 判据是 `check_ios.py` 80 项 + HIG 引用，不是稿子好看 |
| ⛔ **改写 `Tokens.swift` 取值**（未经用户确认） | 4 套方案取值是用户拍板产物；工具**只报不改** |
| ⛔ **在 Figma 稿里定业务逻辑** | 交互与 IA 的真值是 `spec/01` / `spec/02`，不是稿子 |

---

## 四、已交付的工具：`tools/figma_design_sync.py`

| 项 | 内容 |
|---|---|
| 位置 | `tools/figma_design_sync.py`（26 315 B） |
| 判据 | FD-01 输入形状可识别（认不出 ⇒ FAIL）｜FD-02 Swift 侧 token 提取非空｜FD-03 圆角漂移｜FD-04 字号 ≥ 11pt｜FD-05 触控目标 ≥ 44pt（WARN）｜FD-06 颜色白名单（WARN） |
| 输入 | `--figma <design.json>`（Figma 文档 / Variables / DTCG 自动识别） |
| 输出 | 终端报告 或 `--json`；`--emit-tokens <out.json>` 导出归一化 token |
| 自检 | `--self-test` ⇒ **PASS 6/6** |

**自检怎么做的（阴性夹具必须是真正的变换）**：

| 夹具 | 期望 | 实测 |
|---|---|---|
| 干净稿 | 0 个 FAIL | ✅ 0 |
| 漂移稿（圆角 24 未登记 / 字号 9pt / 容器 30×30 / 未登记颜色） | 触发 FD-03/04/05/06，且 **FAIL 数必须比干净稿多** | ✅ 2 个 FAIL，4 个码全触发 |
| 乱输入 `{"hello":"world"}` | 报 **FD-01**（fail loud） | ✅ 只报 FD-01 |

⭐ 自检**第一版真的抓到了 bug**：干净稿里整屏容器的 `cornerRadius: 0` 被误判为「圆角漂移」。
查证后确认 **0 是合法的直角容器**（整屏/满幅底板），本仓库 `Shapes.swift` 只是没登记「屏幕」这个槽位
⇒ 已加豁免（0 直角、≥100 视作胶囊 999），**豁免理由写进了代码注释**，不是悄悄放宽。

### 4.1 本轮**没有**把它接进门禁（诚实说明）

`tools/gates.txt` 是门禁唯一真值。新增门禁必须**可运行**且**有真实输入**。
本轮**没有任何可读的 Figma 文件** ⇒ 把它接成门禁会得到一个「永远报『无输入』」的空门禁。
⇒ **本轮不接**，等拿到第一个可读文件、并把该文件的一份快照入库后，再作为**第 43 项门禁**接入
（届时同步改 `tools/gates.txt` + `.github/workflows/ci.yml`）。

---

## 五、公开订正（6 处，就地回改）

按「**保留原字 + 加时点限定 + 给闭环指针**」处理，**不是**只在文末加订正节。

| 文件 | 行 | 订正内容 |
|---|---|---|
| `docs/research/00` | 28 | 「没有 Figma MCP 连接器」已失效（provider 现含 `figma`）；「没有 Figma 桌面版」仍成立 |
| `docs/research/07` | 13 | connector provider 列表已变，现含 `figma`（2 个只读/导出工具） |
| `docs/research/07` | 134 | 路线 C「连接器不支持」已失效；「本机无桌面版 / 要付费」仍成立 |
| `docs/research/07` | 140 | 「Figma 不引入」**决策维持、理由部分失效** ⇒ 改为「只做只读输入源」 |
| `docs/research/14` | 358 | 「本机无 Figma/MCP 生态」已失效；「不引入外部注册表依赖」结论不变 |
| `docs/research/06` | 1505 | **U2 仍未销账**，补记本轮尝试路径与失败原因（`figma_not_found` + key 已交叉验证正确） |

---

## 六、用户侧唯一需要做的动作

⛔ 社区套件（Apple 官方 UI kit）**需要账号内显式授权**才能被 Connector 读到，
且本机 `figma.com` 被 CloudFront 拦、**代劳不了**。两条路，任选其一：

1. **给一个你自己账号里的 Figma 文件 key**（Figma 打开文件 → 链接里 `file/` 后那段或 `/design/<key>/`）——
   最快，我立刻就能跑管线 A，把你的稿子和 `Tokens.swift` 逐项核一遍。
2. **把 Apple 官方 iOS 27 套件在 Figma 里「另存到我的草稿」**，再把新文件 key 给我 ——
   这样能取到官方组件圆角真值，**顺带销账 `research/06` U2**。

> 拿到 key 之前，管线 A 的工具已经就位并自检通过；**只差一份真实输入**。

---

## 七、本文的适用范围与未验证项

| 项 | 状态 |
|---|---|
| Connector 2 个工具的 schema 与行为 | ✅ 实测 |
| `figma_not_found` 的触发条件 | ✅ 实测 9 次 |
| key 正确性 | ✅ 2 个独立来源交叉验证 |
| 根因＝账号不可见 | ⚠️ **推定**（排除了 key 错 + 网络不通；未取得 Figma 侧确认文档） |
| Connector 成功返回时的**输出格式** | ❌ **未取得**（`output_schema` 为 null，且无一次成功调用） |
| `figma_design_sync.py` 对**真实** Figma 输出的解析 | ❌ **未验证**（只对自造夹具验证过） |
| Apple 官方组件圆角真值 | ❌ **未取得**（U2 未销账） |
| Figma Variables / DTCG 两种输入格式的解析 | ❌ 未用真实文件验证（仅自造夹具） |

⚠️ **重要**：`tools/figma_design_sync.py` 的解析器按 **Figma 公开文档格式**（REST `GET /v1/files/:key`）
实现，并按**已声明的** Connector 输出（`output_schema: null`）**做 fail loud 处理** ——
认不出输入形状就报 FD-01 FAIL，**绝不静默通过**。拿到真实文件后第一步就是核对这条。
