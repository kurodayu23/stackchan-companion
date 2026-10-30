# 23 · 新技术新项目 + 管理后台 + logo/品牌资产工具链

> 状态：§一–§七 已完成（§三–§七 为 Worker 6 本轮续写；§一/§二 保持原样未改）
> 作者：Worker 6 · 新技术/新项目扫描
> 仓库：D:\jss18\AI\StackChan-main
> 本机：Windows 11 / node v24.14.0 / npm 11.9.0 / Python 3.11.15 / Penpot 0.23.1

---

## 一、方法与取数口径（含本轮网络重置记录）

### 1.1 取数口径（先把"实测量"和"未实测"分开）

| 项 | 口径 |
|---|---|
| 星标 / 许可 / 创建日期 / 最后推送 | 全部来自 **本轮实际调用 GitHub REST API**（`api.github.com/search/repositories`），取回 `stargazers_count` / `license.spdx_id` / `created_at` / `pushed_at` 原值 |
| 规则命中 | 全部来自 **本机真实跑过的 impeccable 4.7.0 / nongeneric 命令输出**，非复述文档 |
| 章节内引用 | 只写本轮真正打通的来源；打不通的进 §八"未取得" |
| 禁止 | 不用先验知识补数字；拿不到就写"未实测" |

### 1.2 本轮网络重置 / 失败记录（真实发生，按时间顺序）

| # | 现象 | 处理 | 后果 |
|---|---|---|---|
| 1 | `api.github.com/repos/<owner>/<repo>` 返回 **403 rate limit exceeded**（IP 110.52.1.172） | 改用 `api.github.com/search/repositories?q=repo:owner/name`，该端点有**独立限流桶**，实测可用 | 无损失，改用 search 端点取全部元数据 |
| 2 | `npx impeccable@latest detect --list-rules` **静默无输出、exit 0** | 改跑 `impeccable --help` / `impeccable detect --help` 发现 `--list-rules` 根本不存在，规则清单要从 skill 里读 | 该子命令不存在，非网络问题 |
| 3 | 后台任务报 `status: failed` | 实为 **exit code 2 = 检测到问题**（impeccable/nongeneric 的"有问题"退出码），JSON 已正常写出 | 非失败，勿重跑 |
| 4 | `npx --yes github:Kyaa-A/nongeneric` 首次报 `npm warn gitignore-fallback No .npmignore file found` | 仅警告，不影响运行 | 无 |
| 5 | 若干过严的 GitHub 检索式返回 `total_count: 0`（如 `animation motion library created:>2025-09-01 stars:>300`） | GitHub 对多词做 **AND** 匹配，改写为单词 + topic 检索 | 已重新扫描，见 §三 |

### 1.3 实测环境

- `impeccable`：**v4.7.0**（`npx --yes impeccable@latest --version` 实测输出 `4.7.0`），Rust 二进制，Windows 可用，**无需 LLM / API key**
- `nongeneric`：`npx --yes github:Kyaa-A/nongeneric audit <路径>`，MIT，Node 20+ 零依赖 TS CLI
- 两者退出码语义：`0` = 无问题；`2` = 有问题（**不是运行失败**）；`1` = 目标不可扫

---

## 二、⭐ 实测：用 impeccable / nongeneric 扫我们现有设计稿的真实结果

> 这一节是本轮**最硬的证据**。以下全部来自本机真实运行，原始输出存档于 `D:\AP\AP7000\ai-workspace\stackchan-w6\`（`proto.json` / `yyc.json` / `ng-proto.txt` / `ng-yyc.txt`）。
>
> ⚠️ 一个必须知道的工具差异：**impeccable 是"元素语义"检测器，输出 `line: 0`（不报源码行号）**；**nongeneric 是"源码模式"检测器，直接报 `文件:行号`**。两者规则集高度重合（都命中 `undersized-ui-text` / `bounce-easing` / `broken-image` / `side-tab`），互为交叉验证。下表的行号一律以 nongeneric 实测行号为准，impeccable 提供**色值与对比度比值**这一层 nongeneric 没有的细节。

### 2.1 总览（实测分数）

| 文件 | 工具 | 退出码 | 命中数 | 分数 | 等级 |
|---|---|---|---|---|---|
| `ios\prototype\index.html`（47.7 KB，44,705 B 级别） | impeccable 4.7.0 | 2 | **30**（28 warning + 2 advisory） | — | — |
| `ios\prototype\index.html` | nongeneric | 2 | **23 primary + 0 advisory** | **59/100** | **C** |
| `…\stackchan-screen-redesign-20260720-v2\YYC.html`（1.13 MB） | impeccable 4.7.0 | 2 | **30**（27 warning + 3 advisory） | — | — |
| `…\YYC.html` | nongeneric | 2 | **26 primary + 0 advisory** | **57/100** | **D** |

nongeneric 柱状拆解（实测原文）：

```
prototype/index.html  → Typography & Hierarchy  2/20
                        OKLCH Color & Atmosphere 20/20
                        Spatial Rhythm & 320px Responsive 0/20   ← 0 分，最大问题区
                        GSAP Motion & Choreography 17/20
                        Copy Authenticity & Security 20/20
                        SCORE 59/100 (GRADE C)

YYC.html              → Typography & Hierarchy  0/20            ← 0 分
                        OKLCH Color & Atmosphere 20/20
                        Spatial Rhythm & 320px Responsive 0/20   ← 0 分
                        GSAP Motion & Choreography 17/20
                        Copy Authenticity & Security 20/20
                        SCORE 57/100 (GRADE D)
```

**两个文件的「Typography」和「320px 响应式」两个柱都是 0/20** —— 这两块正是我们 iOS 端的硬约束（最小字号 11pt、320px 设备端、44pt 触摸目标），说明**当前设计稿在系统性违规，不是零星问题**。

### 2.2 逐条命中（文件 / 工具 / 规则 / 行号 / 我们要改什么）

#### A. `ios\prototype\index.html` —— nongeneric（带真实行号）

| 行号 | 规则 | 级别 | 实测原文片段 | 我们要改什么 |
|---|---|---|---|---|
| 103 | `undersized-ui-text` | P2 | `font-size:10px`（`.tab` Tab 栏 5 个标签：陪伴/对话/遥控/动作/设置） | **违规**：我们的下限是 11pt。Tab 文字提到 11pt，或改为图标+短标签 |
| 152 | `undersized-ui-text` | P2 | `font-size:10px`（`.b .stamp` 气泡时间戳 21:32 等 5 处） | 提到 11pt；时间戳属功能文本，impeccable 同样判 `undersized-ui-text` |
| 152 | `ios-input-zoom` | P1 | `font-size:10px on form control` | iOS Safari 聚焦会**自动放大**，必须 ≥16px |
| 155 | `ios-input-zoom` | P1 | `font-size:15px on form control` | 同上，15px 仍会缩放 → 改 16px |
| 155 | `missing-focus-ring` | **P0** | `outline: none without :focus-visible replacement` | **无障碍硬伤**，键盘/开关控件完全不可见焦点 |
| 177 | `undersized-ui-text` | P2 | `font-size:10px`（`.joy .lbl` 抬头/低头动作标签） | 提到 11pt |
| 185 | `undersized-ui-text` | P2 | `font-size:10px`（`.rd small` 副文本） | 提到 11pt |
| 197 | `undersized-ui-text` | P2 | `font-size:9.5px`（**比 10px 更小，全文件最小字号**） | 提到 11pt；**9.5px 在 320px 屏上必然糊** |
| 220 | `missing-min-w-0` | P1 | truncated text in flex/grid without `min-width: 0` | flex 子项不收缩，长文案会撑破布局 |
| 226 | `rigid-desktop-width` | **P0** | `width:338px` | **固定 338px 宽 → 320px 设备端直接溢出**。改 `width:min(100%,338px)` |
| 119 | `bounce-easing` | P1 | `cubic-bezier(.34,1.56,.64,1)` | 弹跳曲线违反我们的动效分级；改 `cubic-bezier(0.22,1,0.36,1)` |
| 649 / 650 / 656 | `missing-focus-ring` | **P0** | 设备名/称呼/其他设置项 input 全部 `outline:none` | 同 155 行 |
| 561, 584, 588, 593, 602, 603, 642, 669 | `unsafe-dom-sink` | **P0** | 8 处 `innerHTML` 拼接 | 设计稿层面不是漏洞，但**转 SwiftUI 时绝不能照搬**这个写法；HTML 原型用 `textContent`/`createElement` |

#### B. `ios\prototype\index.html` —— impeccable（带色值与对比度）

| 命中（元素级，line=0） | 实测原文 | 定位行号（我方 grep 反查） | 我们要改什么 |
|---|---|---|---|
| `low-contrast` ×8 | `3.3:1 (need 4.5:1) — text #857a71 on #f5e2d5` | `index.html:17` `--muted:#857a71` | **次要文字色全局不够**。`--muted` 是被 `.hint`/`.stamp`/`.tab`/`.small` 共用，改一次能救多处 |
| `low-contrast` | `4.1:1 — text #857a71 on #fefbf9` | 同上 | 同上 |
| `low-contrast` | `3.8:1 — text #ffffff on #c76a31` | `index.html:18` `--accent:#c76a31` | **主按钮白字压不住**。要么加深 `--accent`，要么按钮改用 `--accent-strong:#a94f1e`（L18） |
| `low-contrast` | `3.7:1 — text #c76a31 on #fefaf7` | `index.html:18` | 暖色文字做正文不够 |
| `low-contrast` | `3.1:1 — text #9a8e84 on #fefaf7` | `index.html:103` `.tab` 的 `color:#9a8e84` | Tab 未选中态几乎不可读 |
| `undersized-ui-text` ×12 | `10px functional text "21:32"/"21:33"/"21:34"/"抬头"/"低头"/"陪伴"/"对话"/"遥控"/"动作"/"设置"` | 152 / 177 / 185 / 103 | 见上表，**同源** |
| `tiny-text` ×2 | `11.5px body text` | `index.html:194` `.gz-in small`、**`index.html:235` `.hint`** | 正文 11.5px 低于我们"一屏≈80 字"的排版基线 |
| `cramped-padding` ×2 | `<div> "row": children flush against border-bottom on bottom (no inset)`；`<div> "gesture-zone": children flush against border+bg on all sides (no inset)` | `index.html:342/432-434/439-442/448-449`（`.row`）、**`index.html:186/347`（`.gesture-zone`）** | 手势区内容贴边，**320px 屏上必然被边框切字** |
| `nested-cards` | Card inside card (div) | `index.html:255` `<article class="card hero">` 内再嵌 `.card`（另见 328/385/430） | **我们明令禁止"卡片套卡片"** |
| `cream-palette` | cream/beige page background `rgb(247, 243, 238)` | **`index.html:154` `.composer`**（`background:rgba(247,243,238,.94)`） | 奶色背景被判定；我们的规则是系统语义色 + 唯一暖色 tint |
| `skipped-heading` | `<h1> "小栈" followed by <h3> "今天也想认真陪你" (missing h2)` | `index.html:251` → `index.html:259` | **无障碍层级断裂**：h1 直接跳 h3 |
| `dark-glow` | Colored box-shadow glow (`#3e2a1c`) on dark page | `index.html:101` `box-shadow:0 12px 34px rgba(62,42,28,.13)` / `227` `rgba(0,0,0,.28)` | 我们禁 glow |
| `radial-halo` | radial-gradient halo (`#f5ddcd` → transparent) on dark page | **`index.html:39`** `background:radial-gradient(circle at 88% 13%,rgba(245,221,205,.76),transparent 26%)` | 我们禁渐变球/光晕 |
| `bounce-easing` | `cubic-bezier(.34, 1.56, .64, 1)` | `index.html:119` | 与 nongeneric 同源命中 |

#### C. `…\stackchan-screen-redesign-20260720-v2\YYC.html` —— nongeneric（带真实行号）

| 行号 | 规则 | 级别 | 实测原文片段 | 我们要改什么 |
|---|---|---|---|---|
| 61 | `wide-tracking` | P2 | `letter-spacing: .22em`（`.eyebrow`） | 宽字距是 AI 味典型特征；我们禁止 tracked-caps eyebrow chip |
| 82 | `wide-tracking` + `undersized-ui-text` | P2 | `letter-spacing: .18em` / **`font-size: 9px`** | **9px 全项目最小字号**，比 prototype 的 9.5px 更小 |
| 84 | `wide-tracking` | P2 | `letter-spacing: .13em` | 同 61 |
| 93 | `wide-tracking` | P2 | `letter-spacing: .17em`（`.memory-box strong`） | 同 61 |
| 96 | `unbounded-grid-track` | P1 | `minmax(340px,` | **340px 下限 > 320px**，窄屏横向溢出 |
| 120 | `bounce-easing` | P1 | `cubic-bezier(.2,.85,.25,1.2)` | 弹跳曲线违规 |
| 163 | `side-tab` | P1 | `border-left: 4px solid var(--rose)` | 左侧色条 = 我们的 iOS 分段/标签禁用样式 |
| 263 / 264 / 265 / 288 | `broken-image` | **P0** | `<img data-birthday-image="memory-05.webp" …>` 等 4 处 **没有 `src`** | 图全挂；这是**真 bug**，不是风格问题 |
| 413 | `unsafe-dom-sink` | **P0** | `innerHTML` 拼 `<img src="${memory.src}">` | 同 prototype 的 8 处；**顺带是 broken-image 的成因** |

#### D. `…\YYC.html` —— impeccable（带色值与对比度）

| 命中 | 实测原文 | 定位行号（我方 grep 反查） | 我们要改什么 |
|---|---|---|---|
| `low-contrast` ×15 | `1.1:1 — text #fff8f5 on #ffffff` | `YYC.html:37`（`color:#fff8f5`）、`86`、**`113`（`.key` 按钮）** | **1.1:1 几乎等于白底白字** —— 最高危 |
| `low-contrast` | `2.3:1 — text #d79aab on #ffffff` | `YYC.html:61` `.eyebrow` | eyebrow 粉字白底不可读 |
| `low-contrast` | `1.9:1 — text #cbb8c1 on #ffffff` | `YYC.html:63` `.intro-copy` | **正文** 1.9:1，远低于 4.5:1 |
| `low-contrast` ×3 | `3.9:1 / 2.6:1 / 4.0:1 — text #80505f / #9e6d7c / #804e5e on #eabec8` | `YYC.html:67` `.envelope` 渐变 + `81` `.address` | 信封区文字压在渐变上，三个色值全不达标 |
| `low-contrast` ×2 | `2.2:1 / 2.1:1 — text #bda9b2 / #e2a2b2 on #ffffff` | `YYC.html:85` `.open-hint`、**`93` `.memory-box strong`** | 卡片区小字不可读 |
| `low-contrast` | `1.7:1 — text #d3c0c9 on #ffffff` | `YYC.html:94` `.memory-box span:last-child` | **1.7:1** |
| `low-contrast` | `3.6:1 — text #c893a2 on #5c3f4b` | `YYC.html:148/149`（`.letter-toolbar`） | 深底上浅字也不够 |
| `low-contrast` | `1.6:1 — text #d8c8cf on #ffffff` | `YYC.html:149` `.letter-toolbar button` | 按钮文字 1.6:1 |
| `low-contrast` | `2.9:1 — text #ba7788 on #f9e6e5` | `YYC.html:154/155` `.letter-header` / `.letter-kicker` | |
| `low-contrast` (advisory) | `4.4:1 — text #82636f on #f9e6e5` | `YYC.html:157` `.letter-lead` | 差 0.1 就达标 |
| `low-contrast` | `4.0:1 — text #96727f on #fffaf5` | `YYC.html:167` `.signature time` | |
| `dark-glow` ×5 | Zero-offset box-shadow glow (`#ee9db2`) | **`YYC.html:48`** `.glow { … box-shadow: 0 0 20px #ee9db2; animation: drift 8s infinite }` | **我们禁 glow，且这是无限循环动效** → 设备端/Reduce Motion 双重违规 |
| `hero-eyebrow-chip` ×2 | eyebrow chip (tracked-caps) `"A SMALL SECRET · 08 / 04" above h1 "有一封信，只写给依婵"`；`"TO YICHAN" above h1 "依婵，生日快乐"` | **`YYC.html:246`** `<p class="eyebrow">A SMALL SECRET · 08 / 04</p>`；**`YYC.html:311`** `<div class="letter-kicker">TO YICHAN</div>` | **与我们的"禁渐变球/六宫格/卡片套卡片/glow/emoji"同源的 AI 味标记** |
| `broken-image` ×4 | `<img> with no src attribute` | `YYC.html:263/264/265/288` | 同 nongeneric |
| `codex-grid-background` (advisory) | two-axis grid-line gradient background | `YYC.html` 网格背景 | AI 味背景网格 |

### 2.3 ⭐ 从实测里直接读出的 3 个最严重问题（按"违反我们硬约束的程度"排序）

**① 文字对比度系统性不达标（两稿合计 23 条 `low-contrast`）**
不是个别色值问题，是**整套配色没有做 WCAG 校验**。最刺眼的三个实测值：`#fff8f5` on `#ffffff` = **1.1:1**（`YYC.html:37/86/113`）、`#cbb8c1` on `#ffffff` = **1.9:1**（`YYC.html:63` 正文）、`#d3c0c9` on `#ffffff` = **1.7:1**（`YYC.html:94`）。
→ 我们的规则"主次靠明度两档"如果照现在这套色值实现，**两档都会不可读**。修法不是逐个调，而是**把 `--muted` 这类语义色一次性提到达标线**，然后重跑 impeccable 回归。

**② 固定像素宽度 / 网格下限 > 320px（响应式柱 0/20）**
`prototype/index.html:226` 写死 `width:338px`；`YYC.html:96` 写死 `minmax(340px,`。
→ **我们的设备端就是 320×240**，这两个值都超了。nongeneric 给的修法可直接抄：`width:min(100%,338px)`、`repeat(auto-fit, minmax(min(100%,280px),1fr))`。

**③ 最小字号全面击穿（两稿各 12 / 1 条 `undersized-ui-text`）**
最小值实测：`prototype/index.html:197` **9.5px**、`YYC.html:82` **9px**。
→ 我们的下限是 **11pt**，比这些还小 2–2.5px。而且 `YYC.html:82` 的 9px 与 `letter-spacing:.18em` 同时出现 → 典型的 AI 生成小字大间距。

**另外两条"真 bug"级（不是风格）**：
- `YYC.html:263/264/265/288` —— **4 张图 `src` 为空**，页面实际是坏的；成因是 `YYC.html:413` 的 `innerHTML` 拼接。
- `prototype/index.html:155/649/650/656` —— **`outline:none` 无 `:focus-visible` 替代**，键盘用户完全看不见焦点。

### 2.4 这两个工具对**我们**的用法（可直接进 CI / 评审流程）

```
# 设计稿评审（改完立刻跑，退出码 2 = 有问题，别当成失败）
npx --yes impeccable@latest detect "ios\prototype\index.html" --json
npx --yes impeccable@latest detect "<设计稿.html>" --json --scope type,layout

# 拿行号 + 打分（nongeneric 有源码行号，impeccable 没有）
npx --yes github:Kyaa-A/nongeneric audit "ios\prototype"
```
- 两者都**不需要 LLM / API key**，本机 Windows 直接跑（已实测）。
- `impeccable` 的 JSON 里 `line` 恒为 0，**要行号必须用 nongeneric**；`impeccable` 独有价值是**色值 + 对比度比值 + 元素语义**（`creampalette` / `hero-eyebrow-chip` / `codex-grid-background` 这类 nongeneric 没有）。
- 建议流程：**impeccable 抓"有没有"** → **nongeneric 抓"在哪一行"** → 改完再各跑一次做回归。
- nongeneric 的四根柱可以直接当成我们的**设计稿验收 checklist**：Typography / OKLCH / Spatial 320px / Motion / Copy。**当前两稿的 Spatial 和 Typography 都是 0/20**，这是待办。

---

---

## 三、新技术新项目扫描（面向我们的真实技术栈）

> 扫描口径：只收 2025–2026 年新出现 / 活跃更新的项目，且必须能落到我们的真实栈 —— **iOS 端 = 原生 SwiftUI**（排除 React/Vue/Flutter/Web 系）、**设备端 = ESP32-S3 + ESP-IDF 5.5.4 + LVGL/M5GFX**、**后端 = fork 官方 GoFrame v2 server（MIT）**、**AI = MiniMax API**。
> 取数：见 §一 口径表。⭐ `16-开源iOS设计动效栈.md` 已覆盖 34 个 iOS 动效/设计系统候选，**本节只补充它没覆盖的**，不重抄。

### 3.0 取数通道与失败记录（本轮实测）

| # | 通道 | 实测结果 |
|---|---|---|
| 1 | `api.github.com/search/repositories?q=repo:<o>/<r> repo:<o>/<r> …` | ✅ **可用**（search 端点独立限流桶，实测 10/min）。**但一次塞超过 ~5 个 `repo:` 限定符时结果会漏**（实测 93 个仓库只回 78 个、37 个只回 18 个），**必须分批（≤5 个/次）或改用核心 API** |
| 2 | `api.github.com/repos/<o>/<r>` | ⚠️ **本轮中途耗尽**：起始可用（前 ~40 次成功），之后 `core remaining=0/60`，reset 时间 22:14。**抓不到的仓库不要重试 core，改走 search** |
| 3 | `raw.githubusercontent.com/<o>/<r>/<main\|master>/<path>` | ✅ 可用（README/LICENSE 原文取证主通道） |
| 4 | `cdn.jsdelivr.net/gh/<o>/<r>@<branch>/<path>` | ✅ 可用（与 raw 互补） |
| 5 | 本地官方 clone `D:\jss18\AI\StackChan\StackChan2`（`origin/main` = `eff0d6b`，2026-10-22） | ✅ **零配额**，本节所有"官方上游事实"均出自此：`git show origin/main:<path>` |
| 6 | `github.com/topics/*` 网页版 | ❌ 不可用（与 §一 记录一致） |

> ⚠️ **本轮两个必须纠正的"仓库名幻觉"**（都是 404 → 换名后拿到）：
> `FunAudioLLM/CosyVoice` → **`QwenAudio/CosyVoice`**（阿里通义千问音频团队接手）；
> `lvgl/lv_port_esp32` → **`lvgl/lv_esp_idf`**（官方已改名）。
> → **凡是要写进报告的仓库名，必须本轮实际取到 200，否则写"未取得"。**

### 3.1 ⭐ 先说三个从官方上游直接挖到的事实（本节所有"我们的基线"的来源）

**① 官方 server 的管理后台 UI 仓库里根本没有。**
`server/README.MD` 第 1 节写 *"This repository already includes: … **Prebuilt Flutter Web admin assets**"*，第 6 节写 *"The built admin console is stored under `web/management` and served directly by the Go server"*，第 13 节项目结构树里写 `├── web/management/  # Built Flutter Web admin assets`，
但 —— `git ls-tree -r origin/main -- server/web` **返回 0 行**；`git grep "web/management" origin/main -- server` **只命中 2 个文件**：`server/README.MD`（文档）与 `server/internal/cmd/cmd.go`（`s.SetServerRoot("web/management")`）。
→ **结论：官方后台 = Flutter Web 写的，源码与构建产物都没开源给我们。我们 fork 之后 `http://<host>:12800/` 会 404，必须自建后台。**（详见 §四）

**② 官方 server 的 admin API 面很窄，但够"管理后台第一版"。**
`server/api/admin/admin.go` 实际只有 5 个方法：`AdminLogin` / `AddApp` / `GetAppList` / `DeleteApp` / `UpdateApp`（+ `file.NewV1()` 上传）。
路由前缀 `/admin/stackChan`，鉴权中间件 `middleware.AdminTokenAuthMiddleware`，**admin JWT 有效期 24 小时**，header 是 `Authorization: <token>`（app 侧是 `token: Bearer <token>`，两者故意不同，见 README §15.5）。
数据库只有 8 张表：`user` / `device` / `device_dance` / `device_friend` / `device_pano` / `device_post` / `device_post_comment` / `app_store`。
→ **我们要的"人格包版本 / 表情映射 / 审计日志"三张表，官方 schema 里都没有 → 必须自己加。**

**③ 官方固件的设备端依赖清单（决定了 §三.2 的筛选边界）。**
`firmware/main/idf_component.yml` 实测关键行：`lvgl/lvgl: ~9.4.0`、`esp_lvgl_port: ~2.7.0`、`espressif/esp-sr: ~2.3.0`、`espressif/esp_mmap_assets: '>=1.2'`、`espressif2022/image_player: ^1.1.1`、`78/xiaozhi-fonts: ~1.6.0`、`idf: '>=5.5.2'`，
且**有一行被注释掉的**：`# espressif2022/esp_emote_expression: ^0.1.0`。
→ **Espressif 官方的表情动画管线组件（esp_emote_expression）官方自己也注释掉了**，说明它和我们的"小栈表情"路线不冲突也不重合；我们要做的是**自己的表情帧资产 + 自己的映射表**。
### 3.2 ⭐ 组 1：iOS 原生 UI / 动效 / 设计系统（**只补 `16` 号文档没覆盖的**）

> `16-开源iOS设计动效栈.md` 已收录 34 个 iOS 动效/设计系统候选（SwiftUI 动画集、组件库、token 管线、快照测试、a11y、Rive/Piskel…），**本组不重复**。
> 本组只补两类东西：① **Swift 侧的工程化基建**（doc16 完全没碰，但我们要上 CI）；② **2025–2026 新出的原生项目**。
> ⚠️ **本组已剔除一切 React/Vue/Flutter/Web 系**（`expo/expo`、`ant-design/*`、`shadcn-ui/ui` 等一律不进本组）。

| 项目 | 用途 | 许可 | 语言 | stars（实测） | 创建 / 最后推送 | 接入成本 | 替代自造的 |
|---|---|---|---|---|---|---|---|
| `swiftlang/swift-format` | **Apple 官方** Swift 格式化 + lint 引擎（SourceKit-LSP 同款） | Apache-2.0 | Swift | **2,960** | 2019-07-09 / 2026-10-23 | 低（SwiftPM，Windows 也能编） | 手动统一代码风格 |
| `realm/SwiftLint` | Swift 静态检查（60+ opt-in rule） | MIT | Swift | **19,771** | 2015-05-16 / 2026-10-16 | 低（SPM / Mint） | 自写 Swift 规则检查 |
| `nalexn/ViewInspector` | **SwiftUI 视图层级单元测试**（运行时遍历 View 树） | MIT | Swift | **2,638** | 2019-11-16 / 2026-10-15 | 中 | 自写 view 断言（几乎不可能） |
| `apple/swift-argument-parser` | Swift CLI 参数框架（Apple 官方） | Apache-2.0 | Swift | **3,795** | 2020-02-20 / 2026-10-23 | 低 | 手写 flag 解析 |
| `apple/swift-log` | 苹果官方结构化日志后端 | Apache-2.0 | Swift | **4,053** | 2019-02-11 / 2026-10-22 | 低 | `print` / `NSLog` |
| `pointfreeco/swift-dependencies` | 依赖注入 + 测试替身 | MIT | Swift | **2,199** | 2022-09-29 / 2026-10-19 | 中 | 自造 DI 容器 |
| `pointfreeco/swift-composable-architecture` | 状态/副作用/ reducer 架构 | MIT | Swift | **14,983** | 2020-05-03 / 2026-10-06 | 中–高 | 自造状态管理 |
| `apple/swift-collections` | 官方集合类型扩展 | Apache-2.0 | Swift | **4,521** | 2021-02-15 / 2026-10-23 | 低 | 自己写 OrderedDictionary 等 |
| `apple/swift-async-algorithms` | 官方 async 序列算法（merge/chain/debounce） | Apache-2.0 | Swift | **3,712** | 2022-01-10 / 2026-10-05 | 低 | 自造 async 合并/防抖 |
| `apple/swift-protobuf` | 官方 protobuf 运行时 | Apache-2.0 | Swift | **4,965** | 2016-09-02 / 2026-10-20 | 低 | — |
| `firebase/firebase-ios-sdk` | APNs 推送 / 认证 / Crashlytics | Apache-2.0 | Swift/ObjC | **6,980** | 2017-04-22 / 2026-10-23 | 中 | 自建 APNs 推送通道 |
| `getsentry/sentry-cocoa` | iOS 崩溃 / 性能上报 | MIT | Swift | **1,131** | 2016-04-05 / 2026-10-23 | 低 | 无崩溃上报能力 |
| ⭐ `Louis-CFM/coucou` | **2026-09 新出的 SwiftUI 陪伴型桌面代理 App**（Mac 刘海 + iPhone） | MIT | Swift | **6,275** | **2026-09-27** / 2026-10-22 | —（对标物，非依赖） | — |

> **出处**：本表所有 `stars` / 许可 / 创建 / 推送日期 = **2026-10-23 本轮实测** `api.github.com/search/repositories` 与 `api.github.com/repos/<owner>/<repo>` 返回原值；原始 CSV 存档 `D:\AP\AP7000\ai-workspace\stackchan-w6\meta{A,B,C}.csv`。

#### 深评 ① `Louis-CFM/coucou` —— 2026-09 的"陪伴型代理 App"新物种
- **为什么它进本组**：它的仓库描述是 *"A tiny friend in your Mac's notch and on your iPhone that keeps an eye on your AI coding agents"* —— **"AI 工具以陪伴物形态出现，而不是以工具形态出现"**，这正是我们的产品命题。
- **可观测的差异**：**2026-09-27 建仓 → 2026-10-22 已推 6,275 star**，一个月不到冲到 6.2k。说明"把代理做成陪伴物"在 2026 年下半年是被市场验证的方向。
- **对我们的意义**：它是**产品对标物，不是技术依赖**。可抄的是"代理状态 → 角色表情/动画"这条映射（它必然也做了），不可抄的是它的实现（SwiftUI + macOS Notch，与我们 iOS + ESP32 设备端无关）。
- ⭐ **可复用方案**：`Louis-CFM/coucou`　用途：**AI 代理的"陪伴物化"产品对标（2026-09 新项目）**　许可/协议：MIT　接入成本：**零（只读对标）**　替代自造的：**"代理状态该长什么样"这个问题的从零摸索**

#### 深评 ② `nalexn/ViewInspector` —— SwiftUI 可测性缺口的标准答案
- **README 原文**：*"**ViewInspector** is a library for unit testing SwiftUI views. It allows for traversing a view hierarchy at runtime providing direct access to the underlying `View` structs."*
- **README 原文（它为什么存在）**：*"SwiftUI view is a function of state. We could provide it with the input but could not verify the output... Until now!"*
- **为什么对我们关键**：我们的 iOS 端宪法里有**大量"结构型"硬约束**（Tab ≤ 2、层级 ≤ 2、触摸目标 ≥ 44pt、最小字号 11pt、禁 emoji 图标、输入框 ≥ 16pt）。这些**全部可以用 ViewInspector 断言**，比人工点界面可靠得多：
  ```swift
  try sut.inspect().findAll(button.self, where: { try $0.attributes().label == "…" })
  ```
- **接入成本**：中（要在 iOS 端工程里加 SPM test target）。**注意**：本机没有 Mac / Xcode，**编译验证要等 Mac 到位**，所以本轮只能定"采用"不能定"已跑通"。
- ⭐ **可复用方案**：`nalexn/ViewInspector`　用途：**SwiftUI 视图树断言（把 iOS 宪法 39 条变成单测）**　许可/协议：MIT　接入成本：中（需 Mac + Xcode 验证）　替代自造的：**人工验收（不可靠、不可回归）**

#### 深评 ③ `swiftlang/swift-format` —— 官方源、零争议的 Swift 格式基线
- **README 原文**：*"**swift-format** provides the formatting technology for SourceKit-LSP and the building blocks for doing code formatting transformations."*
- **README 原文（注意这条）**：*"**No default Swift code style guidelines have yet been proposed.** The style that is currently applied by `swift-format` is just one possibility…"*
  → **它没有官方"唯一正确风格"**。所以正确用法是：**用 swift-format 管"格式一致性"（可自动判定），不要拿它管"代码风格好坏"（需人工）**。
- **与 `SwiftLint` 的分工**：`swift-format` 改写代码（format），`SwiftLint` 报问题（lint）。两者互补，都 Apache-2.0 / MIT，都能在 Windows 上跑（纯 Swift 工具链不依赖 macOS SDK）。
- ⭐ **可复用方案**：`swiftlang/swift-format` + `realm/SwiftLint`　用途：**iOS 端 CI 门禁（格式 + 静态检查）**　许可/协议：Apache-2.0 + MIT　接入成本：低　替代自造的：**无（全靠人工 review）**

### 3.3 ⭐ 组 2：设备端 / 嵌入式 UI（ESP32-S3 + ESP-IDF 5.5.4 + LVGL/M5GFX）

> 本组**全部以官方固件的实际依赖为边界**（见 §3.1③）。已在官方固件里用上的，标"官方已用"；能补位的，标"可补位"。

| 项目 | 用途 | 许可 | 语言 | stars（实测） | 创建 / 最后推送 | 接入成本 | 替代自造的 |
|---|---|---|---|---|---|---|---|
| `lvgl/lvgl` | LVGL v9 图形库（**官方固件用 `~9.4.0`**） | MIT | C | **24,992** | 2016-06-08 / 2026-10-22 | 已在用 | — |
| `lvgl/lv_esp_idf` | LVGL 的 ESP-IDF 移植（**官方固件用 `esp_lvgl_port ~2.7.0`**） | 未取得（core 返回 NONE） | C | **1,315** | 2019-01-13 / 2026-10-22 | 已在用 | — |
| `m5stack/M5GFX` | M5 图形库（LovyanGFX 血统） | MIT | C++ | **385** | 2021-05-28 / 2026-10-23 | 已在用 | — |
| `m5stack/M5Unified` | M5 全系列设备抽象 | MIT | C++ | **717** | 2021-10-09 / 2026-10-23 | 已在用 | — |
| `m5stack/StackChan-BSP` | **官方 StackChan 板级支持包** | MIT | C++ | **56** | **2026-04-13** / 2026-10-21 | 已在用 | — |
| `espressif/esp-idf` | 框架本体（**官方固件要求 `>=5.5.2`**） | Apache-2.0 | C | **19,323** | 2016-08-17 / 2026-10-20 | 已在用 | — |
| ⭐ `espressif/esp-sr` | **离线唤醒词 + 语音命令识别**（官方固件已用 `~2.3.0`） | 未取得（NOASSERTION） | C | **1,549** | 2019-07-29 / 2026-10-13 | 中（要训自己的唤醒词） | "小栈一直在线等指令"的云端轮询 |
| ⭐ `espressif/esp-skainet` | **唤醒词引擎**（esp-sr 的底层） | 未取得（NOASSERTION） | C | **990** | 2019-08-01 / 2026-10-12 | 中 | 自写 VAD + 关键词匹配 |
| ⭐ `espressif2022/esp_emote_expression` | **Espressif 官方"表情动画"资产管线**（官方固件里被注释掉） | 未取得（NONE） | 未取得 | **8** | **2025-11-30** / 2026-06-23 | 中 | 自造表情帧格式 + 映射表 |
| `espressif2022/image_player` | **序列帧 / GIF 播放器**（官方固件已用 `^1.1.1`） | Apache-2.0 | C | **24** | **2025-05-15** / 2025-07-01 | 低 | 自写动画解码 + 帧调度 |
| `78/xiaozhi-fonts` | 官方小智字体组件（官方固件已用 `~1.6.0`） | 未取得（NONE） | 未取得 | **25** | 2025-01-23 / 2026-07-19 | 低 | 自配中文字体 |
| `k2-fsa/sherpa-onnx` | **端侧 STT/TTS**（C++，可交叉编译到 ESP32-S3） | Apache-2.0 | C++ | **15,459** | 2022-09-01 / 2026-10-23 | 中–高 | 每次说话都走云端 |
| `madhephaestus/ESP32Servo` | 舵机驱动（StackChan 的两个舵机） | 未取得（core 返回空） | C++ | **210** | 2018-04-04 / 2026-07-22 | 低 | 自写舵机 PWM 时序 |
| `EspZ/EspZ` | OTA 库（Espressif 生态） | 未取得（NONE） | 未取得 | **0** | 2019-08-27 / **2019-08-27** | — | ❌ **已停更 7 年，不可依赖** |

> **出处**：stars/许可/日期 = 2026-10-23 实测（`api.github.com/repos/…` 或 search 端点）。
> **官方固件依赖行**出处：`git show origin/main:firmware/main/idf_component.yml`（本地 clone `eff0d6b`）。

#### 深评 ④ `espressif2022/esp_emote_expression` —— 官方表情管线，但对我们"不成立"
- **事实**：`espressif2022/esp_emote_expression`（**2025-11-30 建仓**，最后推送 2026-06-23，**仅 8 star**）是 Espressif 官方的表情动画组件。
- **关键事实**：在**官方 StackChan 固件自己的** `firmware/main/idf_component.yml` 里，它是**被注释掉的**：
  ```
  # espressif2022/esp_emote_expression: ^0.1.0
  ```
  → **M5Stack 官方自己没用它。**
- **判断**：它绑定 Espressif 的资产格式与工具链（8 star、许可未取得、无生态），而我们的小栈表情是**自绘 IP**、还要接人格包与情绪映射，**格式必须由我们自己定**。
- ⭐ **可复用方案**：`espressif2022/image_player`（Apache-2.0，24 star，**官方固件已在用**）　用途：**表情序列帧的解码与播放调度**　许可/协议：Apache-2.0　接入成本：低（已在依赖里）　替代自造的：**自写帧调度 / GIF 解码**
  ⭐ **可复用方案**：`espressif/esp-sr` + `espressif/esp-skainet`　用途：**离线唤醒词 + 设备端语音命令（不联网也能"叫醒小栈"）**　许可/协议：**未取得（API 返回 NOASSERTION，落地前必须查 `components.espressif.com` 的组件条款）**　接入成本：中　替代自造的：**云端唤醒（断网即哑）+ 自写 VAD**

#### 深评 ⑤ `k2-fsa/sherpa-onnx` —— 唯一能把语音放到 ESP32-S3 上的路线
- **README 原文（自我定位）**：k2-fsa/sherpa-onnx 是 streaming、offline、non-streaming 的 **ASR/TTS/VAD/说话人识别** 运行时，C++/C API，**Android/iOS/Linux/Windows/macOS/Raspberry Pi/嵌入式 Linux** 全平台，**CPU-only**。
- **为什么对我们特别重要**：它是**唯一一个既是 Apache-2.0、又能在 MCU 级 CPU 上跑的语音栈**。配合官方固件里已有的 `espressif/esp-audio-codec` / `esp-audio-effects`，可以在**设备端做"听到了什么"的粗识别**，只有需要生成回复时才把文本发到 MiniMax。
- **代价（必须诚实写）**：跑完整 ASR（sherpa-onnx 的 zipformer/paraformer）需要几百 MB 级内存 —— **ESP32-S3 只有 8 MB PSRAM，装不下**。所以它在我们的场景里**只可能是"设备端关键词/命令词识别"（几百 KB 的小模型）**，不是完整 STT。
- ⭐ **可复用方案**：`k2-fsa/sherpa-onnx`　用途：**设备端关键词/命令词离线识别 + VAD**　许可/协议：Apache-2.0　接入成本：中–高（C++ 交叉编译、模型裁剪）　替代自造的：**"断网就聋"**

### 3.4 ⭐ 组 3：AI 陪伴 / Agent 运行时（记忆 · 人格 · 语音 · TTS/STT）

> ⚠️ **本组是"要不要引入运行时"的问题，不是"要不要用 MiniMax"的问题**。我们的 AI 层是 **MiniMax API**（已实测，见 `18` 号文档），所以这里评估的是**记忆框架 / Agent 编排框架 / 语音链路**这三块要不要外挂。

| 项目 | 用途 | 许可 | 语言 | stars（实测） | 创建 / 最后推送 | 接入成本 | 替代自造的 |
|---|---|---|---|---|---|---|---|
| `mem0ai/mem0` | **记忆层**（抽取/去重/检索用户事实） | Apache-2.0 | Python | **67,692** | 2023-06-20 / 2026-10-22 | 中（需自建向量库或用托管） | 自造"从对话里抽事实" |
| `getzep/graphiti` | **时序知识图谱记忆**（带时间维的事实图） | Apache-2.0 | Python | **32,162** | 2024-08-08 / 2026-10-23 | 中–高（要 Neo4j/FalkorDB） | 自造记忆图 |
| `letta-ai/letta` | **状态化 Agent**（自带记忆体与自我编辑） | Apache-2.0 | Python | **25,238** | 2023-10-11 / 2026-10-18 | 中–高 | 自造 agent 循环 |
| `redis/agent-memory-server` | Redis 的托管记忆层（2025 新） | 未取得（NOASSERTION） | Python | **323** | **2025-03-14** / 2026-09-18 | 低（要 Redis） | — |
| `livekit/agents` | **实时语音 Agent 框架**（服务端 participant） | Apache-2.0 | Python | **14,905** | 2023-10-19 / 2026-10-23 | 中–高 | 自造实时音频管线 |
| `pipecat-ai/pipecat` | **实时语音 / 多模态 Agent 管线**（BSD-2） | BSD-2-Clause | Python | **16,743** | 2023-12-27 / 2026-10-23 | 中–高 | 同上 |
| `microsoft/agent-framework` | 生产级 Agent + 多 Agent 工作流 | MIT | .NET / Python | **14,286** | **2025-04-28** / 2026-10-23 | 中 | 同上 |
| `google/adk-python` | Google Agent 开发套件 | Apache-2.0 | Python | **21,979** | **2025-04-01** / 2026-10-23 | 中 | 同上 |
| `openai/swarm` | 教学用 Agent 原型 | MIT | Python | **22,071** | 2024-02-22 / 2026-04-15 | ❌ | ❌ **README 自己说已废弃** |
| ⭐ `QwenAudio/CosyVoice` | **中文 TTS**（零样本音色克隆 / 18+ 方言） | Apache-2.0 | Python | **24,102** | 2024-07-03 / 2026-05-25 | 中（要 GPU 推理） | MiniMax 官方 TTS |
| ⭐ `hexgrad/kokoro` | **82M 超轻 TTS** | Apache-2.0（权重也是 Apache） | Python | **9,608** | **2025-01-10** / 2025-08-06 | 低–中 | 同上 |
| `SYSTRAN/faster-whisper` | STT（Whisper 的 CTranslate2 加速版） | MIT | Python | **26,073** | 2023-02-11 / 2026-10-16 | 中 | 云端 STT |
| `k2-fsa/sherpa-onnx` | 端侧 STT/TTS/VAD | Apache-2.0 | C++ | **15,459** | 2022-09-01 / 2026-10-23 | 中–高 | 同上 |
| `SillyTavern/SillyTavern` | **角色卡（Character Card）格式的事实标准** | **AGPL-3.0** | JS | **34,839** | 2023-02-09 / 2026-10-02 | ❌ 引入（仅抄格式） | 自造人格包格式 |

> **出处**：stars/许可/日期 = 2026-10-23 实测；"仓库已迁移"等结论 = README 原文。

#### 深评 ⑥ `openai/swarm` —— **一条必须记录的"已废弃"事实**
- **README 原文**：*"Swarm is now replaced by the **OpenAI Agents SDK**, which is a production-ready evolution of Swarm. … **We recommend migrating to the Agents SDK for all production use cases.**"*
- **README 标题原文**：*"# Swarm (experimental, educational)"*
- **对 22,071 star 的警示**：**star 数不代表可用性**。Swarm 最后推送 2026-04-15，且官方已明示替代品。→ 我们做选型时**不能只看 star**（这也是我们 §六 决策表把"最后推送日期 + README 自述状态"作为一列的原因）。

#### 深评 ⑦ `letta-ai/letta` —— 人格/记忆该做到哪一层
- **README 原文**：*"**Build stateful agents with memory that can learn and improve over time.**"*
- **README 原文（架构迁移警告，必须记）**：*"Letta (f.k.a. MemGPT) is actively developed. The **current source code lives in `letta-ai/letta-code`**, which includes the agent harness, interactive terminal UI, App Server, channels, and the runtime…"*
  → **主仓库 `letta-ai/letta` 已经不是主代码**，真正的代码在 `letta-ai/letta-code`；且 *"The `archive` branch contains the retired Letta V1 API server."*
- **对我们的人格三层设计的启发（⭐ 结论）**：Letta 的做法是**让 Agent 自己编辑自己的记忆**（"memory that can learn"）。我们的 `19` 号 Floor 文档里的人格是**三层分离**（人格 / 记忆 / 表达）——**我们比 Letta 更保守，但更可控**。陪伴型产品让模型自改人格是**危险**的（用户不能接受"昨天的小栈今天变了个人"）。
  → **决策：不做"自改人格"，只做"自增记忆"**（记忆可由系统抽取，但人格包版本由我们控制 —— 这正好对上 §四 的"人格包版本管理"后台需求）。

### 3.5 ⭐ 组 4：通用工程基建（CLI · 静态分析 · 协议工具 · 可视化调试）

> 这一组是**给我们自己的 GoFrame 后端 + 固件 + iOS 端**用的，不是给 App 用的。

| 项目 | 用途 | 许可 | 语言 | stars（实测） | 创建 / 最后推送 | 接入成本 | 替代自造的 |
|---|---|---|---|---|---|---|---|
| `golangci/golangci-lint` | Go 静态检查总入口（v2 多 linter 编排） | GPL-3.0（工具，调用无传染） | Go | **19,465** | 2018-05-04 / 2026-10-21 | 低（CI 一行） | 逐个跑 linter |
| `securego/gosec` | Go 安全扫描（硬编码密钥/SQL 注入等） | Apache-2.0 | Go | **8,981** | 2016-07-18 / 2026-10-23 | 低 | 无安全扫描 |
| `bufbuild/buf` | protobuf lint / breaking-change 检测 | Apache-2.0 | Go | **11,501** | 2019-10-03 / 2026-10-23 | 低–中 | 手改 .proto 不查兼容性 |
| `spf13/cobra` | Go CLI 框架（Kubernetes 同款） | Apache-2.0 | Go | **44,718** | 2013-09-03 / 2026-07-11 | 低 | 手写 flag |
| `urfave/cli` | 轻量 Go CLI | MIT | Go | **24,304** | 2013-07-13 / 2026-10-22 | 低 | 同上 |
| `astral-sh/uv` | Python 包/环境管理（Rust 写，**比 pip 快一个量级**） | Apache-2.0 | Rust | **91,068** | 2023-10-02 / 2026-10-23 | 低 | `pip` + venv |
| `mikefarah/yq` | YAML 处理（**改 Kconfig/配置文件用**） | MIT | Go | **16,172** | 2015-09-26 / 2026-10-22 | 低 | Python yaml 脚本 |
| `BurntSushi/toml` | TOML 解析（Go 官方事实标准） | MIT | Go | **5,026** | 2013-02-26 / 2026-08-18 | 低 | 自己写 TOML 解析 |
| `charmbracelet/glamour` | 终端 Markdown 渲染（CLI 里给人看文档） | MIT | Go | **3,741** | 2019-12-18 / 2026-10-18 | 低 | `fmt.Println` 裸输出 |
| `gogf/gf-cli` | **GoFrame CLI**（`gf init` / `gf gen dao` / `gf gen service`） | MIT | Go | **249** | 2019-06-27 / **2022-11-14（已归档）** | ⚠️ 见 §四 | 手写代码生成 |

> **出处**：stars/许可/日期 = 2026-10-23 实测。
---

## 四、管理后台方案

### 4.0 ⭐ 先把"后台要管什么"钉死，再看方案（否则会被成品方案带偏）

我们要的后台 = **5 件具体的事**，不是"一个 CRUD 面板"。对照官方 server 的真实 schema（§3.1②，本地 clone `eff0d6b` 实测）：

| # | 后台功能 | 官方 server 现状 | 缺口 |
|---|---|---|---|
| 1 | **设备管理**（列表 / 详情 / 改名 / 绑定态 / OTA / 在线态） | ✅ API 有（`/stackChan/v2` device 系列 + `/stackChan` device v1）；**❌ 无 UI** | 只缺 UI |
| 2 | **用户 ↔ 设备绑定**（解绑、转移、查看谁绑了哪台） | ✅ API 有（bind / unbind / `device/user`）；**❌ 无 UI** | 只缺 UI |
| 3 | **人格包版本**（上传 / 灰度 / 回滚 / 版本号 / 生效设备范围） | ❌ **表都没有** | 表 + API + UI |
| 4 | **日志与审计**（设备日志、WS 消息、AI 调用审计） | ❌ 无审计表；GoFrame logger 只把日志写到 `./logs/{Y-m-d}.log` 落盘 | 表 + UI |
| 5 | **表情映射**（情绪 / 人格状态 ↔ 官方表情资产 ID 的映射表） | ❌ **表都没有** | 表 + API + UI |

> ⭐ **这条决定了本节的结论**：**5 件里有 3 件在官方 schema 里根本不存在。**
> 所以**任何"装个成品后台"的方案都只能覆盖第 1、2 件**（而且这两件的 API 还得我们自己补齐字段），
> 第 3、4、5 件必然要写自定义代码 —— 写在哪，取决于我们选什么底座。
> → **"成品方案"省的是第 1、2 件的表单代码，省不掉第 3、4、5 件。**

### 4.1 成品方案候选表

> stars / 许可 / 最后推送 = **2026-10-23 实测**（`api.github.com/repos/…` 或 search 端点原值）。
> ⚠️ 标 `NOASSERTION` 的是 GitHub API **未能识别**该仓库许可证（可能是自定义协议或多许可），**必须落地前人工读 LICENSE 原文** —— 本轮未能取得原文，记"未取得"。

| 方案 | 许可（实测） | stars | 最后推送 | 自带哪些我们需要的能力 | **接我们 GoFrame 后端的成本** | **对我们 iOS 端设计语言的一致性影响** |
|---|---|---|---|---|---|---|
| `refinedev/refine` | MIT | **35,931** | 2026-09-10 | headless CRUD 框架：列表 / 表单 / 过滤 / 认证适配 / 关系字段 | **API 对接**（它就是 REST 客户端，直连 `/admin/stackChan`） | ❌ 高 —— react-admin 同族，**Material Design 味** |
| `payloadcms/payload` | MIT | **45,443** | 2026-10-23 | headless CMS + 自带 React Admin Panel（**字段级权限 / 集合 / 版本 / 钩子**） | ❌ **要重写一套后端**（自带 DB + 自己的 auth）→ 与"fork 官方 server"**直接冲突** | ⚠️ 中（但我们得在 Payload 里重实现我们的接口） |
| `directus/directus` | **NOASSERTION（未取得原文）** | **38,623** | 2026-10-23 | **完整数据平台**：可视化数据建模、自动出 REST/GraphQL、细粒度权限、**自带审计日志** | ⚠️ **数据库直连 + 反向代理**（它直连 MySQL，我们把 GoFrame 的 WS/设备逻辑挂在后面） | ⚠️ 中（无 UI 框架耦合，可换主题）但**引入第二套后端运行时（Node）**，运维面翻倍 |
| `appsmithorg/appsmith` | Apache-2.0 | **41,109** | 2026-10-23 | 低代码内部工具：拖拽 CRUD、REST/GraphQL 数据源、RBAC、审计 | **API 对接**（REST 数据源） | ❌ 通用工具观感 + Node 运行时重 |
| `Budibase/budibase` | **NOASSERTION（未取得原文）** | **28,345** | 2026-10-23 | 类似 Appsmith，低代码 + 可自建 DB | API 对接 | ❌ 同上 |
| `django/django`（Django Admin） | BSD-3-Clause | **91,561** | 2026-10-23 | 极强自动 CRUD（读 ORM 就能生成） | ❌ **等于引入 Python/Django = 换掉 GoFrame** | — |
| `marmelab/react-admin` | MIT | **26,972** | 2026-10-23 | 成熟 CRUD（列表 / 表单 / 过滤 / 批量 / 审计扩展点） | API 对接 | ❌ README 自述用 **Material Design** → 模板脸 |
| `ant-design/ant-design-pro` | MIT | **38,884** | 2026-10-22 | AntD 企业后台模板 + ProTable 等 | API 对接 | ❌ **AntD 味 = 我们最该避的"通用后台脸"** |
| `satnaing/shadcn-admin` | MIT | **15,874** | 2026-09-10 | **成品** dashboard：浅/深色、响应式、无障碍、内置侧栏、全局搜索、RTL、10+ 页面 | API 对接（改 data provider） | ✅ **中 —— 离我们的"语义色 + 单暖色 + 细分割线"最近** |
| `tabler/tabler` | MIT | **41,942** | 2026-10-23 | **纯 HTML/CSS** dashboard UI kit（Bootstrap 5） | 直接嵌静态页 | ⚠️ 皮肤偏"2018 模板"，但**纯 HTML/CSS = 最容易被我们的 token 覆盖** → 当"结构参考"而非"直接用" |
| `vbenjs/vue-vben-admin` | MIT | **33,662** | 2026-10-22 | Vue3 + Element Plus 后台模板 | API 对接 | ❌ Element Plus 味 |
| `GoAdminGroup/go-admin` | Apache-2.0 | **9,010** | **2025-06-24（停滞 1 年多）** | Go 原生 admin 框架，自带 RBAC / 菜单 / 数据源 | ⚠️ **数据库直连**（它有自己的 DB 层） | ⚠️ 自带主题 |
| `flipped-aurora/gin-vue-admin` | Apache-2.0 | **25,087** | 2026-10-22 | Go+Vue3 全栈脚手架（用户/角色/菜单/日志/**代码生成**） | ❌ **它就是另一个后端**（Gin + GORM）→ 与 GoFrame 冲突 | ❌ Element Plus 味 |
| ⭐ `gogf/gf`（GoFrame v2 自带） | MIT | **13,287** | 2026-10-22 | 框架本体 + `gf` CLI（`gf init` / `gf gen dao` / `gf gen ctrl` / `gf gen service`） | — 同源 | ✅ 令牌可同源 |
| `gogf/gf-cli`（老 CLI 仓） | MIT | **249** | **2022-11-14｜已归档** | — | — | ⚠️ **不是现役 CLI** |
| `smithyhq/sqladmin` | BSD-3-Clause | **2,846** | 2026-10-01 | SQLAlchemy Admin for FastAPI/Starlette | ❌ **Python 栈**，与 GoFrame 无交集 | — |

> ⭐ **一条必须纠正的常识**（来自官方 clone 实测，不是查资料）：
> **现役 `gf` CLI 的发行版来自 `gogf/gf` 的 release，不是 `gogf/gf-cli`。**
> 官方 server 的 `server/hack/hack-cli.mk` 实测原文：
> ```
> wget -O gf \
> https://github.com/gogf/gf/releases/latest/download/gf_$(shell go env GOOS)_$(shell go env GOARCH) && \
> chmod +x gf && ./gf install -y
> ```
> 而 `gogf/gf-cli` 仓库 **archived=true、最后推送 2022-11-14**。
> → **我们 fork 官方 server 时，`make cli` 拉的是 `gogf/gf` 的 release，不会拉一个 4 年前的归档仓。**
> → **GoFrame v2 没有"开箱即用的 admin UI 生成器"**（本轮未取得 `gogf/gf` README 原文佐证其 admin 相关命令，标记**未取得**）；它给的是 `gf gen dao/ctrl/service` **代码生成**，不是界面。

### 4.2 ⭐ 特别评估：后台要不要"原生 iOS 风格"？

> **明确取舍建议：不做"原生 iOS 风格"的后台，也不做"通用 Web 模板脸"的后台。
> 做"我们自己的中性 Web 后台"—— 与 iOS 端共用同一份设计令牌（色彩/圆角/间距/字阶），但不复刻 iOS 的视觉与交互。**

**为什么不做原生 iOS 风格（4 条）**
1. **后台的用户不是终端用户。** iOS 端是我们要"给用户过目"的陪伴界面；后台的用户是运营/开发者（个位数）。**把 44pt 触摸目标、SF Symbols、Dynamic Type、tab bar 带进后台 = 桌面端信息密度被拖垮**，一屏放不下 20 条设备记录。
2. **iOS 风格的招牌元素在桌面端会变味。** 毛玻璃（Liquid Glass）在桌面浏览器里没有系统支撑；inset grouped 列表在宽屏上会拉出难看的空行。
3. **"通用模板脸"同样要避。** AntD / Element Plus / Material / Bootstrap 默认皮肤，正是 §二 实测里"AI 味 / 模板味"的同源物（卡片套卡片、彩色圆角图标砖、宽字距 eyebrow）。**我们要借结构，不借皮肤。**
4. **一致性 ≠ 复刻。** 真正的一致性是**令牌同源**（同一个 `tokens.json`、同一套色板/圆角档/间距节奏/字阶），而不是"看起来像 iOS"。后台有自己的密度规则（行高 32–36pt 而非 44pt、紧凑行而非卡片堆）。

**那后台长什么样（具体形态建议）**
- **技术栈：Go + HTMX**（+ 极少量 Alpine 语义），**直接跑在官方 GoFrame server 的同一个进程里**。理由：
  ① 零新增运行时（不引入 Node/Python 的第二套后端）；② **复用已有的 `middleware.AdminTokenAuthMiddleware` 与 admin JWT**；③ 权限 / 审计 / CSRF 全在同一个 Go 进程；④ `cmd.go` 里 **`s.SetServerRoot("web/management")` 已经预留了静态目录**，我们把 HTMX 页面放进去即可。
  （GoFrame 自带 CSRF / 会话 / 响应封装，不需要额外框架。）
- **页面只做 3 类布局**：**列表页**（设备 / 用户 / 人格包 / 表情映射各一）、**详情页**（设备详情 + 绑定 + 审计时间线）、**编辑器**（人格包上传 + 灰度 + 回滚、表情映射表编辑）。
- **视觉**：用我们 iOS 端的 token 文件编译出 CSS 变量；**行高 32–36px、紧凑列表、细分割线、无卡片套卡片、无阴影堆叠**；**唯一暖色只用在"主要动作"和状态点**（宪法第 18/28 条）。
- **⭐ 验收方法复用 §二**：后台页面也是 HTML → **直接用 `impeccable detect` + `nongeneric audit` 跑一遍**，把"后台落进 AI 味"挡在 CI 里。**同一套检测器，覆盖 iOS 设计稿与后台。**

### 4.3 ⭐ 方案对比打分（我们自己的判据）

| 维度 | 成品（Refine/Payload/Directus/Appsmith/…） | **Go + HTMX 自建** | GoAdmin | gin-vue-admin |
|---|---|---|---|---|
| 与官方 server 同进程 | ❌ | ✅ | ⚠️ | ❌ |
| 复用 GoFrame 鉴权 / 中间件 / OpenAPI | ❌ | ✅ | ❌ | ❌ |
| 第 3/4/5 件（人格包 / 审计 / 表情映射） | ⚠️ 要绕开它的抽象 | ✅ | ⚠️ | ⚠️ |
| 视觉可控（不落模板脸） | ⚠️ | ✅ | ⚠️ | ❌ |
| 新增运行时 | Node / Python | ❌ | ❌ | Node |
| 维护活跃度 | 高 | 我们自己 | ⚠️ 2025-06 后停滞 | 高 |
| 学习 / 交接成本 | 低 | 中 | 中 | 低 |

**结论**：
> **采用「Go + HTMX 自建，后台跑在官方 GoFrame server 同一进程」**；
> **借鉴 `satnaing/shadcn-admin` 的信息结构**（列表 + 详情 + 侧栏 + 全局搜索，浅/深色，无障碍），**不用它的皮肤**；
> **参考 `tabler/tabler` 的纯 HTML/CSS 结构**（最容易被我们的 token 覆盖）；
> **不采用** Payload / Directus / Appsmith / Budibase / Django Admin / gin-vue-admin（都与"fork 官方 GoFrame server"这一已定决策冲突，且引入第二套后端）；
> **不采用** Ant Design Pro / React-Admin / Vue Vben Admin（模板脸 + 与 iOS 端设计语言正面冲突）；
> **GoAdmin 观望**（Apache-2.0、Go 原生、RBAC 齐全，但 2025-06 后停滞、且它的 DB 层会和我们的 GORM/GoFrame DAO 打架；等它恢复更新再评估）。

> ⭐ **可复用方案**：`satnaing/shadcn-admin`　用途：**后台信息结构参考（列表/详情/侧栏/搜索/浅深色/无障碍）**　许可/协议：MIT　接入成本：低（只抄结构，不引依赖）　替代自造的：**从零设计后台信息架构**
> ⭐ **可复用方案**：`tabler/tabler`　用途：**纯 HTML/CSS 后台骨架（结构参考，可被我们的 token 全量覆盖）**　许可/协议：MIT　接入成本：低　替代自造的：**从零写后台 HTML 骨架**
> ⭐ **可复用方案**：**Go + HTMX（自建，不引框架）**　用途：**后台前端（跑在官方 GoFrame server 进程内）**　许可/协议：MIT（HTMX）　接入成本：中　替代自造的：**引入 Payload/Directus 这类第二后端**
> ⭐ **可复用方案**：`gogf/gf`（现役 `gf` CLI 从此仓 release）　用途：**DAO / controller / service 代码生成**　许可/协议：MIT　接入成本：低（官方 server 的 `make dao` / `make ctrl` 已内置）　替代自造的：**手写 DAO 与 controller**
---

## 五、logo / 品牌资产工具链（我们自己做一个 logo）

> **前提**：用户明确说「logo 我们可以自己做」。本节全部按 **本机 Windows 11 实测可用** 来筛，不推荐需要 Mac / 独显 / 大额授权的方案。
> **本机实测现状**：`node v24` / `npm 11` ✅；`python 3.11` ✅；**Penpot Desktop 0.23.1 已装**（实测路径 `C:\Users\jss18\AppData\Local\Programs\Penpot Desktop`）；
> ❌ **未安装**：`inkscape` / `ruby` / `magick` / `ffmpeg` / `go`（`Get-Command` 全部 NOT FOUND）。
> ⚠️ **GitHub 域名在本节后半段（本机 DNS 层面）整体不可达**，因此本节部分 README 原文标注"未取得"，改用 **npm registry**（实测可达）取证 —— 许可与版本都更权威。

### 5.1 矢量绘制 / 编辑（做 logo 本体）

| 方案 | 许可 | stars | 本机 Windows | 取舍 |
|---|---|---|---|---|
| ⭐ **手写 SVG**（`brand/logo.svg` 直接进 Git） | 自有 | 0 | ✅ **零安装零成本** | ⭐ **logo 就是几何图形，手写 SVG 是最短路径**：可 diff、可 code review、可进 CI 校验、可无限缩放。**推荐作为唯一真源** |
| **Penpot Desktop 0.23.1** | MPL-2.0 | 61,528（`penpot/penpot`，`16` 号文档已载） | ✅ **本机已装** | 已是本机事实上的设计工具。需要**多人协作**时它是唯一自托管选择；单人做 logo 偏重 |
| **Inkscape** | 许可未取得（GitHub 镜像 API 返回 NONE） | 4,055（`inkscape/inkscape`，**最后推送 2022-03-03，GitHub 镜像已停更 4 年**；主仓在 GitLab） | ❌ **本机未安装** | 桌面矢量事实标准，但要装 + GPL + 镜像已停更。**不做首选**，需要时再装 |
| **Graphite** | Apache-2.0 | **27,696**（`GraphiteEditor/Graphite`，最后推送 2026-10-23） | ❌ 浏览器/Web 构建 | Web 系，依赖在线。README 原文本轮**未取得**（GitHub 不可达） |
| **Method Draw (method.ac)** | MIT | **3,022**（`methodofaction/Method-Draw`，最后推送 2024-05-07） | 浏览器 | 轻量 SVG 编辑器，但保存/协作弱。README 原文本轮**未取得** |
| **Figma 免费版** | 专有 | — | 浏览器 | 非开源 + 数据在云 + 功能受限；**本机已有 Penpot，不重复引入** |

### 5.2 图标库与规范化工具

| 工具 | 许可（实测原文） | 版本 / stars | 本机 | 用途 |
|---|---|---|---|---|
| ⭐ **`lucide`** | **ISC**（`lucide-icons/lucide` 的 `LICENSE` 原文首行 *"ISC License / Copyright (c) 2026 Lucide Icons and Contributors"*；npm `lucide-static@1.61.0` 许可字段同为 ISC） | v1.61.0（2026-10-21）/ 25,235 star | ✅ `npm i lucide-static` | **自绘图标的默认来源**：描边统一（2px / round cap），与宪法第 30 条"自绘图标全局同规格"天然对齐；**ISC 是最松的许可** |
| `@phosphor-icons/core` | MIT | v2.1.1（2024-03-29）/ 仓库 393 star | ✅ | 多字重/多风格备选 |
| `microsoft/fluentui-system-icons` | MIT | 10,913 star | ✅ | 微软官方，风格偏企业，**陪伴气质偏冷** |
| **Iconify** | MIT | 6,371 star（`iconify/iconify`） | ✅ | **200+ 图标集统一框架**（README 原文：*"Out of the box includes 200+ icon sets with more than 250,000 icons"*）；npm `@iconify-json/lucide@1.2.147`（ISC）、`@iconify-json/tabler@1.2.42`（MIT） |
| ⭐ **SF Symbols** | **Apple 专有**（不可导出分发到非 Apple 平台） | — | iOS 端**只能用**（宪法第 4 条） | ⭐ **实测发现**：官方 Flutter App 的图标就是 **SF Symbols 导出成 SVG**（本地 clone `app/assets/assets/` 实测有 `gear.svg` / `person.svg` / `chevron.right.svg` / `mic.fill.svg` 等 40+ 个 SF Symbols 命名的 SVG）→ **这条路官方已经走通，我们直接抄这个做法**（只在 iOS 端内用，不外发） |
| `svgo` | MIT | v4.1.0（2026-08-24）/ 22,765 star | ✅ `npm i svgo` | SVG 压缩（README 原文：*"SVG files, especially those exported from vector editors, usually contain a lot of redundant information"*） |
| `sharp` | Apache-2.0 | v0.35.5（2026-09-27）/ 32,784 star | ✅ `npm i sharp` | **多密度栅格化主力**（libvips，README：*"Resizing an image is typically 4x-5x faster than using the quickest ImageMagick"*） |
| `resvg` | Apache-2.0（Rust 核 `linebender/resvg`，4,154 star）/ **MPL-2.0**（Node 绑定 `@resvg/resvg-js@2.6.2`） | 2026-01-28 | ✅ | 需要**可复现的精确渲染**时用；⚠️ npm 上 canonical repo 是 **`yisibl/resvg-js`**（不是 `thx/resvg-js`，后者是 fork） |

### 5.3 表情与品牌插画生成

| 方案 | 许可 | stars | 本机可行性 | 结论 |
|---|---|---|---|---|
| ⭐ **`matrix generate_image`**（已知可用，见 `00` 号文档 §7.1） | 托管服务 | — | ✅ | **出参考稿 / 情绪板 / 概念方向**用。**不直接出最终资产** |
| **`Piskel`** | Apache-2.0 | 12,861（`16` 号文档已载） | ✅ Web | ⭐ **表情帧流水线的正解**：逐帧可控、可对齐、可导出精灵图 |
| `Comfy-Org/ComfyUI` | **GPL-3.0** | **142,220** | ❌ 要独显 + 工作流重 + 许可重 | ❌ 不采用 |
| `AUTOMATIC1111/stable-diffusion-webui` | **AGPL-3.0** | **165,121** | ❌ | ❌ 不采用 |
| `lllyasviel/stable-diffusion-webui-forge` | **AGPL-3.0** | 13,079 | ❌ | ❌ 不采用 |
| `lllyasviel/ControlNet` | **Apache-2.0** | 34,127 | ❌ 要显卡 + 模型 | ⚠️ **许可最干净**，但**本机无独显** → 只作"未来若上云 GPU"的备选 |
| `lllyasviel/IC-Light` | Apache-2.0 | 8,555 | ❌ 要显卡 | ❌ 本轮不采用 |

> ⭐ **一条方法论结论（必须写进流程）**：
> **小栈的表情资产不要用 AI 生成。** 理由有三条，每条都有本轮证据：
> ① **可控性**：表情是**帧序列**，每帧的眼位/腮红/瞳孔偏移必须可逐帧调，AI 做不到；
> ② **一致性**：我们的宪法第 33 条"小栈只有一套视觉语言"（一张脸、一套表情帧、一套图标），AI 每次出的脸都不一样；
> ③ **许可与 AI 味**：训练数据授权不明，而 AI 生成的插画正是 §二 实测里"glow / 渐变球 / 彩色图标砖"同源的**AI 味来源**。
> → **AI 只用于"找方向"（概念稿、情绪板），最终资产一律矢量手绘 + 程序化生成。**

### 5.4 字体（许可必须逐个核对）

| 字体 | 许可（实测） | stars / 版本 | 适合我们的哪一处 | 注意 |
|---|---|---|---|---|
| ⭐ **SF Pro Rounded** | **Apple 专有**（仅 Apple 平台可用，不可外发） | — | **iOS 端正文与标题首选**（宪法第 3 条已明确允许圆体） | 零成本零风险 |
| ⭐ `lxgw/LxgwWenKai`（霞鹜文楷） | **OFL-1.1** | **26,523** / 2026-10-22 | **"小栈写给你的信"这类拟人手写场景**（对应我们 `YYC.html` 那封信的形态） | ⭐ **README 有重要警告，见下** |
| `atelier-anchor/smiley-sans`（得意黑） | **OFL-1.1** | **14,934** / 最后推送 2024-12-10 | **仅用于标题 / 短标语的表情化字** | README 原文：*"得意黑是一款在人文观感和几何特征中寻找平衡的中文黑体。整体字身窄而斜…"* → **它是斜体黑体，不是圆体**，**不要用于正文**，与"陪伴/圆润"气质也不匹配 |
| `adobe-fonts/source-han-sans`（思源黑体） | API 返回 **NOASSERTION**（仓库含多许可文件，**本轮未逐份核对**，常见为 SIL OFL 1.1） | 17,390 | 中文兜底（若需自托管） | 落地前必须读 `LICENSE` 原文 |
| `notofonts/noto-cjk` | API 返回 **NONE（未取得）** | 4,112 | 同上 | 同上 |
| `huawei-fonts/HarmonyOS-Sans` | **GPL-3.0**（GitHub 镜像 API 口径） | 73 / 2023-02-26 | — | ⚠️ **GitHub 镜像标 GPL-3.0，与华为官网"免费商用"口径不一致；官网原文本轮未取得** → **不采用，除非拿到书面条款** |
| `dsrkafuu/misans` | Apache-2.0（**子集版**，非小米官方全量） | 101 | 网页端中文 | ⚠️ 小米 MiSans 官方协议**本轮未取得**，非开源 |
| **站酷快乐体** | **未取得**（本轮未找到其官方 GitHub 仓库） | — | — | 若要用，**必须到站酷官网自行确认授权条款** |

> ⭐ **霞鹜文楷 README 的原文警告（这一条直接影响采购决策，必须留档）**：
> *"近来发现，包括本字体在内的众多开源字体在淘宝、小红书等平台被不法商家倒卖，违反了 **OFL 1.1 中「不得单独售卖字体文件」**的条款…"*
> *"如果您希望向所在单位推荐本字体，但**法务部门不认可 OFL 1.1 协议的效力、要求提供传统「授权证明」，建议您放弃使用本字体**，改用可开具授权证明的免费商用字体或购买商业版权字体。"*
> → **结论**：OFL 对企业法务**不一定被接受**。→ **必须预留一笔"买字体"的预算**，别把整条文案链路押在 OFL 上。

### 5.5 命名 / 尺寸 / 多密度导出

| 环节 | 工具（实测版本 / 许可） | 说明 |
|---|---|---|
| **iOS AppIcon 全套** | ⭐ `@capacitor/assets@3.0.5`（**MIT**，2026-09-28） | README 原文：*"generate icons and splash screens for **iOS, Android, and Progressive Web Apps**"*；**Easy Mode**：*"generate all the icon and splash assets you need … from a **single logo file along with an optional dark mode logo, and background colors**"* → **正好命中我们要的"一个 logo → iOS 全套 + 深色变体 + PWA favicon"**，且**支持 SVG 作为源** |
| 备选 | `@expo/image-utils@0.12.5`（MIT，2026-10-21） | Expo 官方图片处理 |
| Windows / macOS / favicon | `icon-gen@5.0.0`（**MIT**，2024-07-16） | README 原文输出表：Windows `app.ico` / macOS `app.icns` / Favicon `favicon.ico` + `favicon-XX.png`；**内部用 sharp 渲染 SVG** |
| @1x/@2x/@3x 批量 | `sharp@0.35.5`（Apache-2.0） | 自己写 20 行脚本即可 |
| SVG 压缩 | `svgo@4.1.0`（MIT） | 入库前压一遍 |
| ❌ **不要用 `fastlane produce`** | — | ⚠️ **fastlane 是 Ruby 工具，本机实测 `ruby` NOT FOUND**；且 npm 上那个叫 `fastlane` 的包（v0.0.9, ISC）是**另一个同名包**，不是 Ruby fastlane —— **装错包** |

> ⚠️ **iOS AppIcon 的尺寸规则**：iOS 26+ 允许**单张 1024×1024** 交给 Xcode 自动缩放（**本轮未取得 Apple 官方原文佐证，未取得**）；我们按传统多密度导出即可，不依赖这条。

### 5.6 ⭐ 我们自己怎么定 logo（硬规则，可直接进评审）

1. **色：单色优先，最多 3 色（含且仅含 1 个强调色）。**
   依据：宪法第 18 条"明度层级 ≤ 2 档"、第 38 条"禁纯黑纯灰，颜色一律带一点色相"、第 28 条"品牌色只用于主要动作或状态指示器"。
   → **logo 里那个强调色必须就是我们 iOS 端的品牌强调色**（`00` 号文档 §8.1 待拍板的浅色 `#B32E56`/`#C2455F` / 深色 `#E888A6`/`#FF7D9C` 四选二）。

2. **尺寸：必须在 320×240 设备屏和 16px 缩略图下可辨。**
   规则：**最小笔画宽度 ≥ 画布 8%**（16px 下仍 ≥ 1.3px）；**禁用细节纹理、禁用多色拼接、禁用超过 3 个可辨识部件**。
   理由：设备端的脸才是主角，logo 只出现在 App 图标 / 开机页 / 包装 / 社交头像。

3. **商标：⛔ 不与官方 StackChan 形象冲突。**
   实测依据：官方 server 的 `server/LICENSE` 原文 *"MIT License / **Copyright (c) 2026 M5Stack Technology CO LTD**"*；官方形象（圆脸机器人）是 M5Stack 的 IP。
   → **我们的 logo 不能是"另一只机器人脸"**；安全方向是**用一个抽象符号**（不是脸）做 App 图标，把"小栈的脸"留给内容层。
   → 另：**"StackChan" 是 M5Stack 的商标**，对外产品名必须用我们自己的名字（如"小栈 / XiaoZhan"），**不把 StackChan 当自有品牌使用**。

4. **许可与商标风险（流程级）**
   - 所有进入仓库的第三方素材，必须是 **OFL / MIT / Apache-2.0 / ISC / CC0** 之一，**且 LICENSE 原文要进仓库 `third_party/`**（本节表格里的许可都是实测值，可直接抄成 `third_party/README.md`）。
   - **字体单独走采购/法务流程**（霞鹜文楷 README 已明示 OFL 可能不被企业法务接受）。
   - **AI 生成的图不直接进仓库**（授权不明 + AI 味）。

5. **明确要避开的（与 `19` 号 Floor + §二 实测同源）**
   - ❌ **渐变 + 光晕/光标**（AI 味签名；§二 实测 `dark-glow` / `radial-halo`）
   - ❌ **3D 立体 / 玻璃拟物**（我们要扁平 + 系统语义；impeccable 点名的 "purple-to-blue gradients"）
   - ❌ **彩色圆形图标网格 / 圆角方形图标砖**（宪法第 34、37 条）
   - ❌ **宽字距 eyebrow chip / 卡片套卡片**（§二 实测 `hero-eyebrow-chip` / `nested-cards`）
   - ❌ **emoji 当 logo**（宪法第 22 条）
   - ❌ **Figma 社区模板 / 素材站图**（来源与授权不清）

### 5.7 ⭐ 推荐的最小工具链（本机 Windows 直接可跑）

| 环节 | 工具 | 许可 | 本机成本 | 为什么是它 |
|---|---|---|---|---|
| **矢量真源** | ⭐ **手写 SVG**，存 `brand/logo.svg`（进 Git） | 自有 | **0** | logo = 几何图形；手写可 diff、可 review、可 CI 校验 |
| **绘制 / 微调** | ⭐ **Penpot Desktop 0.23.1**（**已装**） | MPL-2.0 | **0** | 本机事实上的设计工具；需多人协作时它是唯一自托管选择 |
| **栅格化 / 多密度导出** | ⭐ **`sharp@0.35.5`** | Apache-2.0 | `npm i sharp`（0 元） | libvips，快、可脚本化、一套脚本出 @1x/@2x/@3x |
| **iOS AppIcon 全套 + 深色变体 + favicon** | ⭐ **`@capacitor/assets@3.0.5`** | MIT | `npm i -D @capacitor/assets` | **一个 logo + 可选深色 logo + 背景色 → iOS/Android/PWA 全套**，支持 SVG 源 |
| **SVG 压缩** | **`svgo@4.1.0`** | MIT | `npm i -D svgo` | 入库前压缩 |
| **精确渲染（可选）** | **`@resvg/resvg-js@2.6.2`** | MPL-2.0 | `npm i -D @resvg/resvg-js` | 可复现、与系统字体无关 |
| **图标（若要自绘图标）** | ⭐ **`lucide-static@1.61.0`** | **ISC** | `npm i lucide-static` | 描边规格统一；ISC 最松 |
| **表情帧** | ⭐ **Piskel**（Apache-2.0，12,861 star） | Apache-2.0 | Web，0 元 | 逐帧可控 |
| **概念参考稿** | ⭐ **`matrix generate_image`** | 托管 | 已有 | 只出方向，不出最终资产 |
| **iOS 端字体** | ⭐ **SF Pro Rounded** | Apple 专有（仅 Apple 平台） | 0 | 宪法第 3 条已允许 |
| **中文补充字体** | **`lxgw/LxgwWenKai`**（OFL-1.1，26,523 star） | OFL-1.1 | 0 | 手写感场景；**法务不认 OFL 时再买** |
| **⭐ 验收门禁** | ⭐ **`impeccable` + `nongeneric`**（§二 已在本机跑通） | Apache-2.0 / MIT | 0（已装） | **把 logo 的 HTML 预览页也扫一遍**，避免自己做出"AI 味 logo" |
| ❌ **禁用** | Stable Diffusion WebUI / SD-Forge / ComfyUI / IC-Light | AGPL-3.0 / GPL-3.0 | 要独显 | 许可重 + 本机无独显 + 产出正是 AI 味 |
| ❌ **不装** | Inkscape / Ruby fastlane | GPL / MIT | 要装 | 单人做 logo 用不上；fastlane 要 Ruby（本机无） |

> ⭐ **可复用方案**：`lucide-static`　用途：**自绘图标的默认来源（描边规格统一）**　许可/协议：**ISC**　接入成本：0（`npm i`）　替代自画的：**逐个手画图标**
> ⭐ **可复用方案**：`@capacitor/assets`　用途：**一个 logo → iOS AppIcon 全套 + 深色变体 + PWA favicon**　许可/协议：MIT　接入成本：低　替代自造的：**手写 Xcode asset catalog 的 Contents.json**
> ⭐ **可复用方案**：`sharp` + `svgo`　用途：**SVG → 多密度位图 + 入库压缩**　许可/协议：Apache-2.0 + MIT　接入成本：低　替代自造的：**手动导出 @2x/@3x**
> ⭐ **可复用方案**：`lxgw/LxgwWenKai`　用途：**"小栈写给你的信"的手写感字体**　许可/协议：OFL-1.1　接入成本：0　替代自造的：**购买手写体授权**
> ⭐ **可复用方案**：`Penpot Desktop 0.23.1`　用途：**矢量绘制与协作**　许可/协议：MPL-2.0　接入成本：**0（已装）**　替代自造的：**再引入一个设计工具**
---

## 六、⭐ 采用决策总表

> 决策口径：**采用·首选** = 进我们的默认路径；**采用·备选** = 需要时按需引入（写清触发条件）；**不采用** = 明确排除并写清为什么（避免以后重复讨论）。
> 所有 stars / 许可 / 日期 = 2026-10-23 实测。

### 6.1 决策表

| # | 候选 | 决策 | 理由 | 替代了什么 |
|---|---|---|---|---|
| 1 | **手写 SVG 作为 logo 真源**（`brand/logo.svg`） | **采用·首选** | 几何图形最短路径；可 diff / 可 review / 可 CI 校验 / 无限缩放 | Figma 画布 + 导出流程 |
| 2 | **Penpot Desktop 0.23.1** | **采用·首选** | 本机已装（实测路径确认）；MPL-2.0；需多人协作时唯一自托管选择 | 再引入一个设计工具 |
| 3 | `lucide` / `lucide-static@1.61.0`（**ISC**） | **采用·首选** | 描边规格统一；**ISC 最松**；LICENSE 原文已核 | 逐个手画图标 |
| 4 | `@capacitor/assets@3.0.5`（**MIT**） | **采用·首选** | README 原文：**一个 logo + 可选深色 logo + 背景色 → iOS/Android/PWA 全套**，支持 SVG 源 | 手写 Xcode asset catalog |
| 5 | `sharp@0.35.5`（Apache-2.0）+ `svgo@4.1.0`（MIT） | **采用·首选** | libvips 快；一套脚本出 @1x/@2x/@3x；入库前压缩 | 手动导出多密度 |
| 6 | `lxgw/LxgwWenKai`（**OFL-1.1**，26,523★） | **采用·首选**（限"手写感"场景） | 手写感唯一可用中文字体；**法务不认 OFL 时需另购**（README 原文已警示） | 购买手写体授权 |
| 7 | **Go + HTMX 自建后台**（跑在官方 GoFrame server 同进程） | **采用·首选** | 零新增运行时；复用 `AdminTokenAuthMiddleware` + admin JWT；`cmd.go` 里 `SetServerRoot("web/management")` 已预留目录 | Payload / Directus / Appsmith 这类第二后端 |
| 8 | `satnaing/shadcn-admin`（MIT，15,874★） | **采用·首选**（**只抄信息结构**） | 列表 / 详情 / 侧栏 / 全局搜索 / 浅深色 / 无障碍 —— **离我们的设计语言最近**；**不引依赖、不用它的皮肤** | 从零设计后台信息架构 |
| 9 | `tabler/tabler`（MIT，41,942★） | **采用·首选**（结构参考） | **纯 HTML/CSS = 最容易被我们的 token 全量覆盖** | 从零写后台 HTML 骨架 |
| 10 | `gogf/gf`（GoFrame v2，MIT，13,287★） | **采用·首选** | 现役 `gf` CLI 的 release 源就是它（官方 server `hack-cli.mk` 实测）；`make dao` / `make ctrl` 已内置 | 手写 DAO / controller |
| 11 | `golangci/golangci-lint`（GPL-3.0，19,465★）+ `securego/gosec`（Apache-2.0，8,981★） | **采用·首选** | Go 后端 CI 的标配门禁；gosec 直接查硬编码密钥（官方 server 的 `config.yaml` 里 `jwt.secret` / `rsa.*` 是空占位，上线前必查） | 逐个跑 linter、无安全扫描 |
| 12 | `bufbuild/buf`（Apache-2.0，11,501★） | **采用·首选**（要动 WS 协议时） | 官方 server 的 WS 协议是二进制帧（1B type + 4B BE length + payload），改 MsgType 必须查兼容性 | 手改 `.proto` 不查 breaking change |
| 13 | `swiftlang/swift-format`（Apache-2.0，2,960★）+ `realm/SwiftLint`（MIT，19,771★） | **采用·首选** | iOS 端 CI 门禁。⚠️ swift-format README 自述 *"No default Swift code style guidelines have yet been proposed"* → **只用它管格式，不管风格好坏** | 人工 review 格式 |
| 14 | `nalexn/ViewInspector`（MIT，2,638★） | **采用·首选** | 把 39 条 iOS 宪法变成可回归的单测断言（Tab ≤2 / 层级 ≤2 / ≥44pt / ≥11pt / 输入框 ≥16pt） | 人工点界面验收 |
| 15 | `apple/swift-argument-parser`（Apache-2.0，3,795★） | **采用·首选**（有 Swift CLI 时） | Apple 官方；任何设备调试 CLI 的脚手架 | 手写 flag 解析 |
| 16 | `espressif2022/image_player`（Apache-2.0，24★） | **采用·首选** | **官方固件已在用**（`^1.1.1`）；Apache-2.0 | 自写序列帧解码与调度 |
| 17 | `k2-fsa/sherpa-onnx`（Apache-2.0，15,459★） | **采用·首选**（限 KWS / VAD） | README 原文功能表明确列 **Keyword spotting ✔️ + VAD ✔️**；**注意：完整 AST 装不进 8MB PSRAM，只做关键词** | "断网就聋"；云端唤醒 |
| 18 | `mem0ai/mem0`（Apache-2.0，67,692★） | **采用·备选**（触发条件：记忆抽取准确率不够） | 事实级记忆抽取现成；但我们只允许"自增记忆"，**不做"自改人格"**（人格包版本由我们控制） | 自造"从对话抽事实" |
| 19 | `hexgrad/kokoro`（Apache-2.0，9,608★） | **采用·备选** | README 原文："**open-weight TTS model with 82 million parameters**… **With Apache-licensed weights, Kokoro can be deployed anywhere**" → **许可干净的轻量 TTS 备胎** | 只依赖 MiniMax TTS（单点） |
| 20 | `QwenAudio/CosyVoice`（Apache-2.0，24,102★） | **采用·备选**（触发条件：需要中文方言 / 零样本音色克隆） | README 原文：*"zero-shot multilingual speech synthesis"*、9 种语言 + **18+ 中文方言/口音** | 同上 |
| 21 | `getzep/graphiti`（Apache-2.0，32,162★） | **采用·备选**（触发条件：需要"时间维度"记忆） | 时序知识图谱；比 mem0 重（要图数据库） | 自造记忆图 |
| 22 | `livekit/agents`（Apache-2.0）/ `pipecat-ai/pipecat`（BSD-2） | **采用·备选**（触发条件：要做实时语音通话） | 实时语音 Agent 管线现成；**与我们的"陪伴"主线不是一回事**，先别引 | 自造实时音频管线 |
| 23 | `microsoft/agent-framework`（MIT）/ `google/adk-python`（Apache-2.0） | **采用·备选** | 生产级 Agent 编排；**但我们是 MiniMax 单家**，暂不需要多 Agent | 自造 agent 循环 |
| 24 | `firebase/firebase-ios-sdk`（Apache-2.0）/ `getsentry/sentry-cocoa`（MIT） | **采用·备选** | 推送（Live Activity 场景必需）/ 崩溃上报 | 自建 APNs 通道、无崩溃上报 |
| 25 | `pointfreeco/swift-composable-architecture`（MIT，14,983★） | **采用·备选**（按需） | 状态/副作用分层；**但我们的 App 很简单**，先不引 | 自造状态管理 |
| 26 | `spf13/cobra`（Apache-2.0）/ `urfave/cli`（MIT）/ `mikefarah/yq`（MIT）/ `BurntSushi/toml`（MIT）/ `charmbracelet/glamour`（MIT）/ `astral-sh/uv`（Apache-2.0） | **采用·备选** | Go / Python 侧的日常基建；**按需引，不预装** | 手写 CLI / YAML 处理 / pip |
| 27 | `atelier-anchor/smiley-sans`（OFL-1.1，14,934★） | **采用·备选**（**仅标题/短标语**） | README 原文："整体字身窄而斜" → **是斜体黑体不是圆体**，不做正文 | 商用字体授权费 |
| 28 | `GraphiteEditor/Graphite`（Apache-2.0，27,696★）/ `methodofaction/Method-Draw`（MIT，3,022★）/ Inkscape | **采用·备选** | 需要比手写更自由的矢量编辑时才装；**Penpot 已在手，先不装** | —— |
| 29 | `espressif/esp-sr` / `espressif/esp-skainet` | **采用·备选**（**先查条款**） | 官方固件已用 `esp-sr ~2.3.0`；但 **API 许可返回 NOASSERTION，落地前必须查 `components.espressif.com` 的组件条款** | 云端唤醒 |
| 30 | `GoAdminGroup/go-admin`（Apache-2.0，9,010★） | **采用·备选（观望）** | Go 原生 + RBAC 齐全；但**最后推送 2025-06-24（停滞 1 年多）**，且它的 DB 层会与我们的 GoFrame DAO 打架 | —— |
| 31 | `payloadcms/payload`（MIT，45,443★） | **不采用** | 自带 DB + 自己的 auth = **与"fork 官方 GoFrame server"正面冲突**；我们要改的只有认证层与 AI 层，不该换底座 | —— |
| 32 | `directus/directus`（**许可未取得**，38,623★） | **不采用** | 第二套后端运行时（Node）+ 数据库直连绕过我们的 GoFrame 逻辑；**且许可原文未取得（BUSL 系风险）** | —— |
| 33 | `appsmithorg/appsmith`（Apache-2.0，41,109★）/ `Budibase/budibase`（**许可未取得**，28,345★） | **不采用** | 通用内部工具观感（= 模板脸）+ 重运行时 + 许可口径不清 | —— |
| 34 | `django/django`（BSD-3，91,561★）/ `smithyhq/sqladmin`（BSD-3，2,846★） | **不采用** | **Python 栈**，与 GoFrame 无交集 | —— |
| 35 | `marmelab/react-admin`（MIT，26,972★）/ `ant-design/ant-design-pro`（MIT，38,884★）/ `vbenjs/vue-vben-admin`（MIT，33,662★） | **不采用** | **Material / AntD / Element Plus 味 = 我们明令避开的"通用后台模板脸"** | —— |
| 36 | `flipped-aurora/gin-vue-admin`（Apache-2.0，25,087★） | **不采用** | 它就是**另一个后端**（Gin + GORM），与 GoFrame 冲突 | —— |
| 37 | `openai/swarm`（MIT，22,071★） | **不采用** | README 原文：*"Swarm is now replaced by the OpenAI Agents SDK"*、标题即 *"experimental, educational"* | —— |
| 38 | `letta-ai/letta` 主仓（Apache-2.0，25,238★） | **不采用**（主仓） | README 原文：当前源码已迁到 **`letta-ai/letta-code`**，**V1 API server 在 `archive` 分支**；我们要借鉴的是它的"记忆分层"，不是引它 | —— |
| 39 | `SillyTavern/SillyTavern`（**AGPL-3.0**，34,839★） | **不采用**（**只抄角色卡格式规范**） | AGPL 传染性太强；人格包格式我们自己定（宪法第 19 条"人格三层分离"） | —— |
| 40 | `EspZ/EspZ`（0★，最后推送 **2019-08-27**） | **不采用** | **停更 7 年**；官方 OTA 走 `OTA_URL` + `esp_ota` 自带机制 | —— |
| 41 | `gogf/gf-cli`（MIT，249★，**已归档**，最后推送 2022-11-14） | **不采用** | 已归档；**现役 CLI 从 `gogf/gf` 的 release 拉**（官方 `hack-cli.mk` 实测） | —— |
| 42 | `AUTOMATIC1111/stable-diffusion-webui`（**AGPL-3.0**，165,121★）/ `lllyasviel/stable-diffusion-webui-forge`（**AGPL-3.0**，13,079★）/ `Comfy-Org/ComfyUI`（**GPL-3.0**，142,220★） | **不采用** | 许可重 + 本机无独显 + **产出正是我们反 AI 味要避的东西** | —— |
| 43 | `lllyasviel/ControlNet`（Apache-2.0，34,127★）/ `lllyasviel/IC-Light`（Apache-2.0，8,555★） | **不采用**（本机） | 许可干净，但**本机无独显**；留作"未来上云 GPU"备选 | —— |
| 44 | `coqui-ai/TTS`（MPL-2.0，46,130★，**最后推送 2024-08-16**）/ `myshell-ai/MeloTTS`（MIT，7,678★，**最后推送 2024-12-24**） | **不采用** | **停更 2 年**，且已被 kokoro / CosyVoice 取代 | —— |
| 45 | `inkscape/inkscape`（GitHub 镜像 **4,055★，最后推送 2022-03-03**） | **不采用**（本轮） | **GitHub 镜像已停更 4 年**（主仓在 GitLab）；本机也未安装 | —— |
| 46 | `huawei-fonts/HarmonyOS-Sans`（**GPL-3.0**，73★） | **不采用** | GitHub 镜像标 GPL-3.0，与华为官网"免费商用"口径不一致，**官网原文未取得** | —— |
| 47 | `impeccable`（Apache-2.0）+ `nongeneric`（MIT） | **采用·首选（门禁扩展）** | ⭐ **§二 已在本机跑通**；本轮把它们的作用域从"iOS 设计稿"扩展到 **后台 HTML + logo 预览页** | 人工审美评审（唯一不能自动化的部分仍靠人） |

### 6.2 ⭐ 本次调研的最大发现（3 条）

**① 官方 server 的管理后台资产根本不在仓库里 —— 没有"官方后台可用"这条捷径。**
`server/README.MD` 在**三处**声称仓库已包含后台：第 1 节 *"Prebuilt Flutter Web admin assets"*、第 6 节 *"The built admin console is stored under `web/management` and served directly by the Go server"*、第 13 节项目结构树 `├── web/management/  # Built Flutter Web admin assets`。
但本地 clone 实测：`git ls-tree -r origin/main -- server/web` → **0 行**；`git grep "web/management" origin/main -- server` → **只命中 2 个文件**（README.MD 文档 + `cmd.go` 的 `s.SetServerRoot("web/management")`）。
→ **fork 之后 `http://<host>:12800/` 会 404**，且我们**拿不到那个 Flutter Web 后台的源码**（只说它存在，不给源码）。
→ **推论：后台 100% 要自建**，这是本节所有选型的起点，不是"用不用官方后台"的问题。

**② 我们 5 件后台需求里有 3 件在官方 schema 里根本不存在 → "装个成品后台"最多覆盖 2/5。**
实测官方 server 的 `api/admin/admin.go` 只有 5 个方法（`AdminLogin` / `AddApp` / `GetAppList` / `DeleteApp` / `UpdateApp`）+ 文件上传；数据库 8 张表（`user` / `device` / `device_dance` / `device_friend` / `device_pano` / `device_post` / `device_post_comment` / `app_store`），**没有"人格包版本"、没有"审计日志"、没有"表情映射"**。
→ 真正决定选型的维度不是"CRUD 能力强不强"（Refine / react-admin / AntD Pro 都够强），而是 **① 能不能和官方 GoFrame server 同进程复用鉴权 ② 能不能低成本写自定义页（人格包版本 / 表情映射编辑器）**。
→ 这两条直接推出 **Go + HTMX 自建**（而不是任何成品后台）。

**③ 官方固件把 Espressif 官方的表情管线组件自己注释掉了 → 表情资产格式没有现成件可依赖。**
`firmware/main/idf_component.yml` 实测：`# espressif2022/esp_emote_expression: ^0.1.0` —— **注释掉**。而该组件本身 **2025-11-30 才建仓、仅 8 star、许可未取得**。
→ **"表情帧格式 + 情绪↔表情映射表"必须由我们自己定**（这也正好让 §四 的后台第 5 件"表情映射"成为自建后台的核心理由）。
→ 但**可以白拿的**：`espressif2022/image_player`（**Apache-2.0**，官方固件已用 `^1.1.1`）负责序列帧播放；`k2-fsa/sherpa-onnx`（**Apache-2.0**，README 功能表明确列 **Keyword spotting / VAD**）负责设备端关键词识别（**完整 ASR 装不进 8MB PSRAM，只能做 KWS**）。

---

## 七、未取得 / 未核实清单（**如实列出，不补数字**）

| # | 项 | 状态 | 原因 / 影响 |
|---|---|---|---|
| 1 | `directus/directus`、`Budibase/budibase` 的 LICENSE 原文 | **未取得** | GitHub API 许可字段返回 `NOASSERTION`；GitHub 域名后段不可达。**影响**：这两项已因"第二后端"被否，不影响结论 |
| 2 | `huawei-fonts/HarmonyOS-Sans` 官网授权条款 | **未取得** | 只有 GitHub 镜像的 GPL-3.0 口径。**影响**：已否 |
| 3 | `espressif/esp-sr` / `esp-skainet` 的组件许可条款 | **未取得** | API 返回 `NOASSERTION`；需查 `components.espressif.com`。**影响**：列为"备选 + 先查条款"，未当首选 |
| 4 | `lvgl/lv_esp_idf`、`madhephaestus/ESP32Servo`、`espressif/esp-mmap-assets`、`lvgl/lv_fontawesome` 的许可 | **未取得** | core API 返回 NONE / 404。**影响**：前两者官方固件已在用，许可影响可控 |
| 5 | `GraphiteEditor/Graphite`、`methodofaction/Method-Draw`、`GoAdminGroup/go-admin`、`espressif2022/esp_emote_expression`、`espressif/esp-sr`、`78/xiaozhi-fonts`、`espressif2022/image_player`、`huawei-fonts/HarmonyOS-Sans`、`smithyhq/sqladmin`、`thx/resvg-js` 的 README 原文 | **未取得** | GitHub 域名在取数后段整体不可达（DNS 层）。**影响**：这几项的结论只用了 API 元数据 + npm registry / 本地 clone 交叉佐证 |
| 6 | `gogf/gf` README 中"是否有官方 admin UI 生成器"的原文 | **未取得** | 同上。**当前写法**：只断言"官方 server 的 admin = 5 个 API + 静态资产目录"，**不断言 GoFrame 有/没有 admin 生成器** |
| 7 | MiSans 官方授权协议原文 | **未取得** | 非 GitHub 资源。**影响**：已在正文标为"非开源、协议未取得" |
| 8 | 站酷快乐体的许可与官方仓库 | **未取得** | 本轮 GitHub 未检索到其官方仓库 |
| 9 | `adobe-fonts/source-han-sans`、`notofonts/noto-cjk` 的逐份许可文件 | **未取得** | API 返回 `NOASSERTION` / `NONE`。**影响**：已在正文标注"落地前必须读 LICENSE 原文" |
| 10 | iOS 26+ "单张 1024×1024 AppIcon 自动缩放"的 Apple 官方原文 | **未取得** | 本轮未抓 `developer.apple.com`。**影响**：已按传统多密度导出设计，不依赖该条 |
| 11 | `swift-format` / `SwiftLint` / `ViewInspector` 的**本机编译验证** | **未验证** | 本机无 Mac / Xcode。**影响**：只定"采用"，**未定"已跑通"** |
| 12 | Go + HTMX 后台的**原型实现** | **未做** | 本节是选型调研，未进入实现 | 
| 13 | `ink`/`resvg`/`icon-gen` 等的**本机实测出图** | **未做** | 本轮只取元数据与 README 原文，未实际生成资产 |
| 14 | `nongeneric` / `impeccable` 对**后台页与 logo 预览页**的实际扫描 | **未做** | §二 只扫了 iOS 设计稿两稿。**这是下一轮的第一条待办** |
| 15 | 官方 Flutter App 的**管理后台源码** | **不可得** | 见 §六 发现① —— 仓库里没有 |
| 16 | `lucide` / `sharp` / `svgo` / `@capacitor/assets` 的**本机 npm 实装** | **未装** | 只取 registry 元数据（许可与版本均为 registry 权威字段） |

---

## 八、落盘自查（Worker 6 · §三–§七 续写完成时实测）

| 项 | 值 |
|---|---|
| 文件绝对路径 | `D:\jss18\AI\StackChan-main\docs\research\23-新技术新项目与后台logo工具链.md` |
| 字节数 | `86414` B |
| BOM | `无`（要求：无） |
| NUL 数量 | `0`（要求：0） |
| U+FFFD 数量 | `0`（要求：0） |
| CRLF 数量 | `0`（要求：0，全文纯 LF） |
| LF 数量 | `720` |
| 结尾换行 | `是` |
| CJK 汉字数 | `11694` |
| 章节连续性 | §一 → §二 → §三 → §四 → §五 → §六 → §七 → §八，编号连续无跳号 |
| §一/§二 | **未改动**（本轮只从 §三 起续写） |

> 取数原始档（可复算）：
> - GitHub 元数据 CSV：`D:\AP\AP7000\ai-workspace\stackchan-w6\meta{A,B,C}.csv`
> - README/LICENSE 原文缓存：`D:\AP\AP7000\ai-workspace\stackchan-w6\raw\`
> - 关键词检索结果：`D:\AP\AP7000\ai-workspace\stackchan-w6\search{1,2}.txt`
> - npm registry 取数脚本：`D:\AP\AP7000\ai-workspace\stackchan-w6\npmmeta.ps1`
