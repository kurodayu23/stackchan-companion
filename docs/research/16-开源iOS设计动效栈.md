# 16 · 开源 iOS / SwiftUI 设计动效栈

> 产出：Worker 2（开源 iOS / SwiftUI 设计、动效、组件、设计系统与设计工具链猎取与评估）
> 取数口径：所有项目功能描述均来自 **2026-10-23 当日实际抓取的仓库原文**
> （`raw.githubusercontent.com` 的 README / 源码原文、`data.jsdelivr.com` 的文件清单）；
> 抓不到的一律标注"未实测"，不做推测填充。

---

## 一、猎取方法与取数口径

### 1.1 怎么发现（本轮实际走过的通道）

| 通道 | 本轮用法 | 可用性实测 |
|---|---|---|
| GitHub REST Search API `api.github.com/search/repositories` | 按关键词 + `language:Swift` + `sort=stars` 拉候选池（动画 / design tokens / live activity / app intents / rive） | ✅ 可用（本轮 60 次 core 配额 + 10 次/min search，实测未触发限流） |
| `raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md` | 取 README 原文作为功能佐证 | ✅ 可用 |
| `data.jsdelivr.com/v1/packages/gh/<owner>/<repo>@<branch>?structure=flat` | 取仓库文件清单（验证"确实有这些文件"） | ✅ 可用，但**大仓库输出极长**，本轮只在必要时使用 |
| `api.github.com/repos/<owner>/<repo>` | 取 stars / license / default_branch / pushed_at | ✅ 可用 |
| `github.com/topics/...` 网页版 | 尝试过 | ❌ **web_fetch 网络请求失败**（HTML 页面不可达），改用 API |
| `web_search` 工具 | 未使用（任务书已告知该工具在本机持续 `MATRIX_TOOL_REQUEST_FAILED`） | ❌ 不用 |

> **口径纪律**：本文件里每一个项目的"它是什么"，都来自**实际抓到的 README 原文或文件清单原话**；
> stars / license / 最近推送时间来自 `api.github.com/repos/...` 的当日返回值。
> 抓不到的写"未实测"，不猜、不补、不从记忆里"回忆"功能。

### 1.2 为什么不只看 SwiftUI 库

我们的真实约束里有三条会直接改变选型结论：

1. **本机是 Windows，没有 Mac，没有 Xcode** → 任何"必须 macOS 才能跑"的方案只能是**降级项**（参考用），不能是**依赖项**。
   本轮因此把 §六（本机可运行性核查）单列成硬章节，并在 §四 里把"能在 Windows 上跑"当作排序权重。
2. **设计稿流程是 HTML/CSS → 截图评审 → 转 SwiftUI**（代码即设计稿），
   所以"SwiftUI → 设计稿"的双向工具优先级**低于**"HTML/CSS 侧的自动视觉回归 + 无障碍 lint"——
   后者能直接插进现有流程，前者要重做整条链。
3. **我们已经有 Penpot Desktop 0.23.1 + Python playwright**，
   所以 Penpot 生态只看**能不能接进现有链**，而不是"要不要再装一个设计工具"。

### 1.3 判据（沿用已定规则，不新造）

- 动效：默认只动 transform/opacity；单屏持续动效 ≤1 处；一次性反馈动效 ≤2 处、总时长 ≤400ms；必须支持 `accessibilityReduceMotion`。
- 视觉：系统语义色 + 唯一暖色 `.tint`；自定义色必须给 浅/深 × 默认/高对比 **4 变体**；不硬编码系统色值。
- 结构：Tab ≤2；层级 ≤2；触控目标 ≥44×44pt；最小字号 11pt；禁 emoji 图标。
- 设备端：ESP32-S3 / 320×240 / LVGL / 550–700mAh → 任何动效引擎的**内存与 CPU 预算**必须先过这一关。

---

## 二、候选总表（29 + 5 = 34 项）

> stars / 许可 / 最近推送 = **2026-10-23 实测** `api.github.com/repos/...` 返回值。
> "成熟度信号"只写**可验证的事实**（归档状态、最近推送日期、release/tag、issue 数量、语言构成），不写"看起来很成熟"。

| # | 项目 | 用途 | 语言/平台 | 许可 | stars（实测） | 成熟度信号 | 对我们可用性初判 |
|---|---|---|---|---|---|---|---|
| 1 | `amosgyamfi/open-swiftui-animations` | SwiftUI 动效范式集（弹簧/进出场/循环） | Swift / iOS | Unlicense | 5669 | 最近推送 2026-08；topics 含 dynamic-island | ⭐ 参照级，非依赖 |
| 2 | `EmergeTools/Pow` | SwiftUI 视觉效果（粒子/转场） | Swift / iOS | MIT | 4420 | 最近推送 2026-04 | ⚠️ 与"禁 glow/粒子"规则冲突 |
| 3 | `Shubham0812/SwiftUI-Animations` | 动效组件合集 | Swift / iOS | Apache-2.0 | 3581 | 最近推送 2026-10-05 | ⚠️ 演示集，非工程库 |
| 4 | `swiftui-lab/swiftui-hero-animations` | `matchedGeometryEffect` 共享元素转场范例 | Swift / iOS | MIT | 249 | 最后推送 2020-07（**已停更**） | ⭐ 读代码抄思路，不引入 |
| 5 | `haplollc/ThinkingOrbs` | AI 界面加载指示器（点阵 3D） | Swift / iOS | MIT | 277 | 2026-09 建仓，2026-09 最近推送 | ⭐ 新鲜，可抄"克制的加载态" |
| 6 | `SwiftUIX/SwiftUIX` | SwiftUI 扩展全集 | Swift / 跨平台 | MIT | 8185 | 最近推送 2026-09；topics 含 performance | ⭐ 只取单个 API，不整体引入 |
| 7 | `SFSafeSymbols/SFSafeSymbols` | SF Symbols 静态类型封装 | Swift / 跨平台 | MIT | 1897 | 最近推送 2026-03 | ⭐ 替代 emoji 图标的正解 |
| 8 | `signerlabs/ShipSwift` | AI 原生 SwiftUI 组件库（带 MCP） | Swift / iOS | MIT | 3245 | 最近推送 2026-10-18；2025-12 建仓 | ⭐⭐ 高相关，重点评估 |
| 9 | `isamercan/ThemeKit` | 主题化设计系统（130+ token 组件） | Swift / iOS+macOS | MIT | 17 | 2026-06 建仓，最近推送 2026-10-08；topics 含 mcp/figma | ⭐ 4 变体语义色参考 |
| 10 | `muhittincamdali/SwiftUI-Design-System-Pro` | 设计 token + 主题引擎 + 组件 | Swift / Apple 平台 | MIT | 26 | 最近推送 2026-10-20；topics 含 dark-mode/dynamic-type | ⭐ 动态色/字号方案参考 |
| 11 | `rozd/theme-kit` | 环境式主题 + 代码生成 | Swift / iOS | MIT | 42 | 2026-02 建仓，最近推送 2026-08-14 | ⭐ token→代码生成思路 |
| 12 | `jasonkneen/ShadKit` | shadcn/ui + Vercel AI Elements 的 SwiftUI 移植 | Swift / iOS | MIT | 48 | 2026-07 建仓，最近推送 2026-09-15 | ⚠️ 偏 Web 风，慎用 |
| 13 | `salesforce-ux/design-system-ios` | 设计 token → iOS 样式（Lightning token） | Swift / iOS | BSD-3-Clause | 71 | **仓库已归档**；最后推送 2025-06-09 | ⭐ token 落地管线参考（代码只读） |
| 14 | `style-dictionary/style-dictionary` | 跨平台设计 token 构建系统 | JavaScript / Node | Apache-2.0 | 4868 | 最近推送 2026-10-23（**当天仍在动**） | ⭐⭐ Windows 可跑，token 管线主干 |
| 15 | `tokens-studio/sd-transforms` | Tokens Studio → Style Dictionary 转换 | TypeScript / Node | MIT | 251 | 最近推送 2025-12-10 | ⭐ 若走 Penpot/token JSON 则相关 |
| 16 | `pointfreeco/swift-snapshot-testing` | SwiftUI 快照/视觉回归测试 | Swift / 跨平台 | MIT | 4377 | 最近推送 2026-10-21 | ⭐⭐ 视觉回归事实标准 |
| 17 | `doordash-oss/swiftui-preview-snapshots` | Preview ↔ 快照测试共用配置 | Swift / iOS | Apache-2.0 | 197 | 最后推送 2024-07（**已停更**） | ⭐ 思路可抄，代码不用 |
| 18 | `BarredEwe/Prefire` | 由 Preview 生成 Playbook/快照/无障碍测试 | Swift / iOS | Apache-2.0 | 526 | 最近推送 2026-10-22 | ⭐⭐ 把 Preview 变成测试源 |
| 19 | `cashapp/AccessibilitySnapshot` | iOS 无障碍回归测试 | Swift / iOS | Apache-2.0 | 749 | 最近推送 2026-10-15 | ⭐⭐ 无障碍自动化落地 |
| 20 | `dequelabs/axe-core` | Web 无障碍检测引擎（对比度/触摸目标） | HTML/JS | MPL-2.0 | 7692 | 最近推送 2026-10-22 | ⭐⭐ **Windows 可跑**，直接查设计稿 |
| 21 | `pa11y/pa11y` | 无障碍 CLI（封装 axe + HTML_CodeSniffer） | JavaScript / Node | LGPL-3.0 | 4582 | 最近推送 2026-10-19 | ⭐⭐ Windows 可跑，命令行接 CI |
| 22 | `lost-pixel/lost-pixel` | 视觉回归（Percy/Chromatic 开源替代） | TypeScript / Node | MIT | 1679 | **仓库已归档**；最后推送 2026-04-22 | ⭐ 概念可抄，仓库已死 |
| 23 | `rive-app/rive-ios` | Rive 矢量动画 iOS runtime | Swift / iOS | MIT | 848 | 最近推送 2026-10-23 | ⚠️ iOS 可用，设备端过重 |
| 24 | `rive-app/rive-runtime` | Rive C++ 底层 runtime | C++ / 跨平台 | MIT | 1238 | 最近推送 2026-10-23 | ⚠️ 设备端评估项 |
| 25 | `EsotericSoftware/spine-runtimes` | 2D 骨骼动画 runtime | C++ / 跨平台 | **NOASSERTION（专有许可）** | 5328 | 最近推送 2026-10-21 | ❌ 许可需核实，编辑端也收费 |
| 26 | `piskelapp/piskel` | 像素/序列帧精灵图编辑器 | JavaScript / Web | Apache-2.0 | 12861 | 最近推送 2026-10-21 | ⭐⭐ 表情资产流水线（Windows 可跑） |
| 27 | `penpot/penpot` | 开源设计平台（本机已装 Desktop） | Clojure / 跨平台 | MPL-2.0 | 61528 | 最近推送 2026-10-23 | ⭐ 已装，转插件/导出方向 |
| 28 | `awesome-selfhosted/awesome-selfhosted` | 自托管开源应用清单 | Markdown | NOASSERTION | 329508 | 最近推送 2026-10-22 | ⭐ 找"陪伴/待办"类 UI 参照 |
| 29 | `sparrowcode/live-activity-example` | Live Activity + 灵动岛 + 锁屏 | Swift / iOS | MIT | 37 | 最后推送 2024-04 | ⭐⭐ 系统表面落地范式 |

### 2.1 补充候选（Penpot 插件生态，检索 `penpot plugin` 时追加）

| # | 项目 | 用途 | 语言/平台 | 许可 | stars（实测） | 成熟度信号 | 对我们可用性初判 |
|---|---|---|---|---|---|---|---|
| 30 | `penpot/penpot-exporter-figma-plugin` | Penpot → Figma 导出插件 | TypeScript / 插件 | MPL-2.0 | 461 | **最近推送 2026-10-23**（当天仍活跃） | ⚠️ 方向反了（我们无 Figma） |
| 31 | `penpot/penpot-plugin-starter-template` | Penpot 插件脚手架 | TypeScript / 插件 | MIT | 42 | 未归档；最后推送 2025-08-04 | ⭐ 备选（若要写 Penpot 插件） |
| 32 | `penpot/penpot-plugins` | Penpot 插件开发仓库 | TypeScript / 插件 | MPL-2.0 | 60 | **已归档** | ❌ 不用 |
| 33 | `penpot/plugin-examples` | Penpot API 示例 | TypeScript / 插件 | MPL-2.0 | 22 | 未归档；最后推送 2025-03-14 | ⭐ 写插件时的抄写对象 |
| 34 | `penpot/penpot-plugins-samples` | Penpot 插件功能示例 | TypeScript / 插件 | MIT | 21 | 未归档；最后推送 2026-01-29 | ⭐ 同上 |

---

## 三、逐项深评（15 项）

### 3.1 `amosgyamfi/open-swiftui-animations`

- **一句话是什么**：一个 SwiftUI 动效"灵感集"，由 5669 个 star 社区维护的 README + 可运行 Xcode 工程构成，不是可安装的库。
- **实测依据（README 原话）**：
  - "**Why use an animation library instead of creating these tiny effects yourself?** Get inspiration from [here]" —— 作者自己就把它定位成**读代码的灵感库**，而不是依赖。
  - "Most animations here are based on the animations section in the [Apple Developer Documentation]" —— 技术路线全部回到 Apple 官方 API。
  - "Starting in 2025, I will generate some of the SwiftUI animations using SOTA models like Gemini 2.5 Pro, Claude 3.7 Sonnet, OpenAI o3, and o4-mini models." —— **部分内容是 AI 生成**，质量需要我们自己筛，不能照抄。
  - "Note: The animations are unedited. Modify and use them to suit your needs." —— 明确允许改用。
- **许可与依赖**：**Unlicense**（公共领域，无署名义务、无传染性、无付费层）。
- **接入成本**：小时级（抄 3–5 段代码到自己工程）；若当库引入则是天级（无包结构，不值）。
- **⭐ 可复用方案**：用途＝动效"怎么写"的参考；许可＝Unlicense；接入成本＝小时级；替代自造的＝自己查 Apple 文档推导曲线/弹簧参数。
- **采用决策**：**复用（读代码，不引依赖）**。理由：它是本轮唯一"零成本、零许可风险、纯 Apple 原生 API"的动效参考集，且作者已明说这是给人抄的；对我们"默认只动 transform/opacity、单屏持续动效 ≤1 处"的约束，它提供的是**手法**（PhaseAnimator / KeyframeAnimator / 弹簧参数），不是**成品**。
  - ⚠️ 必须人工筛：仓库里有 Liquid Glass、Hue Rotation、Fireworks、Duolingo 风特效，这些**违反我们的"HIG 内容层禁 Liquid Glass / 禁渐变球"规则**，不能进我们的设计稿。
- **⭐ 具体落到**：**iOS 端**。作为 `docs/06-设计方法论与好看规则集` 的附录级素材：每条动效落成"我方版"（只保留 opacity/scale、时长 ≤400ms、尊重 Reduce Motion）。

### 3.2 `haplollc/ThinkingOrbs`

- **一句话是什么**：2026-09 新出的 SwiftUI 点阵 3D 加载指示器包，专门为"AI / Agent 界面"设计，9 种状态各一个图形。
- **实测依据（README 原话）**：
  - "Dotted, genuinely 3D loading indicators for AI and agent interfaces in SwiftUI."
  - "All of them are drawn only in grayscale dots, so they sit quietly in any interface, light or dark." —— **纯灰度、不引入新色**，天然符合"系统语义色 + 唯一暖色 .tint"。
  - "Every orb pauses itself offscreen, stays in phase with the others on screen, and **respects Reduce Motion**."
  - "**With Reduce Motion on, orbs show a single representative frame** and shimmering text holds still at full strength. **With Increase Contrast on, shimmering text also stays at full strength.**" —— **同时覆盖 Reduce Motion 与 Increase Contrast 两个我们必须处理的开关**，这是本轮唯一原生解决"高对比"的开源实现。
  - "the heaviest design (`.composing`, 566 dots) takes 65 µs to compute a frame and 0.27 ms to rasterize it, against 8.3 ms per frame at 120 Hz" —— 有实测性能数字。
  - "One `Canvas` per orb inside one `TimelineView`, with no view per dot." —— 实现方式与我们"只动 transform/opacity"的判据天然兼容。
  - "These are Jakub Antalik's designs... MIT licensed... This package is a native Swift port." —— **上游另有 MIT 作者**。
- **许可与依赖**：MIT（需同时保留 thinking-orbs 原作者与移植者的版权声明）；零第三方依赖；iOS 17+ / Swift 6 / Xcode 16+。
- **接入成本**：小时级（SPM 加依赖 + 传一个枚举状态）。
- **⭐ 可复用方案**：用途＝AI 陪伴状态指示器（思考中/在听/在连）；许可＝MIT（双署名）；接入成本＝小时级；替代自造的＝自己用 `TimelineView` 画点阵（那是 1–2 天的活，且 Reduce Motion 分支要自己写对）。
- **采用决策**：**复用（但只取 1–2 个状态）**。理由：它把"持续动效"这件事做得又轻又克制，正好卡在我们"单屏持续动效 ≤1 处"的上限；而我们只需要 `.breathing`（空闲/陪伴中）一个，**绝不能上 9 个**（那是堆功能，违反产品约束）。
- **⭐ 具体落到**：**iOS 端**。Tab1「陪伴」页里小栈思考状态的指示器；Reduce Motion 开启时自动退化为静态帧。

### 3.3 `signerlabs/ShipSwift`

- **一句话是什么**：3245 star 的"AI 原生"SwiftUI 组件库，带 MCP server，让 LLM 直接调用它的组件配方。
- **实测依据（README 原话）**：
  - "**AI-native SwiftUI component library — production-ready code that LLMs can use to build real apps.**"
  - "All iOS client code is open-source under the MIT license. **Pro recipes** add everything you need to go from prototype to production." —— 客户端 MIT，**后端/合规/踩坑文档是付费层**。
  - "**Option 2: Local Skills (No MCP Required)** — Install skills that read source files directly from this repo — works offline, no server needed" —— 有**离线用法**，不绑定他们的 SaaS。
  - 组件目录原文："**Metal-shader procedural backgrounds:** Metaballs · Halftone · Water · LiquidMetal · NeuroNoise · DotOrbit · Voronoi · SimplexNoise · ColorPanels · SmokeRing · Swirl"、"AnimatedMeshGradient"、"GlowSweep" —— **这些正是我们明令禁止的渐变球/glow/噪声背景**。
  - 依赖规则原文："SWUtil ← no dependencies on other SWPackage directories / SWAnimation ← may depend on SWUtil only" —— 分层纪律可抄。
  - "**Need a custom app built?** We do that too. ... 💵 **From $5,000**" —— 商业化意图明显。
- **许可与依赖**：iOS 客户端 MIT；**MCP 走 `https://api.shipswift.app/mcp` 外部服务**（Pro 配方需要）；技术栈含 Amplify/StoreKit2/VolcEngine ASR 等我们不需要的重依赖。
- **接入成本**：天级（选 3–5 个文件复制走）到周级（整体接入 + 接受其视觉语言）。
- **⭐ 可复用方案**：用途＝(a) 组件"自包含单文件 + 统一 SWUtil 工具层"的分层范式；(b) "给 AI 装一个技能包，让它按目录规范写组件"的 MCP/技能工程化做法；许可＝MIT（取用部分）；接入成本＝天级；替代自造的＝自己写 skill 规范文件。
- **采用决策**：**混合**。理由：**结构抄、视觉不抄**。它的动画组件几乎全是我们禁止的风格（Metal 噪声、glow、mesh gradient），整体引入等于自造"AI 味"界面；但它"把组件做成自包含单文件 + 工具层无依赖 + 给 AI 提供目录级技能包"的工程做法，正是我们要的"设计稿可被 AI 稳定复现"的落地方式。
  - ❗ 不接它的 MCP 远程服务（外部依赖 + 我们的组件库很薄，收益不抵数据外传与付费层风险）。
- **⭐ 具体落到**：**iOS 端 + 设计流程**。① 组件目录按"单文件自包含 + 无跨层依赖"重排；② 在我们的设计 skill 里加一份"组件目录清单"供 AI 取用（对应我们的"一切面向人的 UI 必须先给用户过目"）。

### 3.4 `isamercan/ThemeKit`

- **一句话是什么**：2026-06 起的纯 Swift 主题化设计系统，token 全 JSON + 代码生成 + MCP + Figma 双向。
- **实测依据（README 原话）**：
  - "**Components never hardcode a color** — swap the theme and everything follows." —— 正是我们"不硬编码系统色值"的工程化表达。
  - "**Design tokens everywhere** — colors / radius / spacing from JSON, typography / shadows in code; one semantic name (`fg-hero`, `rd-sm`), different values per theme." —— **语义名 + 每主题不同值**，对应我们的语义色方案。
  - "**Reduce Motion** — decorative/continuous animation is suppressed while functional motion is kept: `BorderBeam`, `Skeleton`, `RollingNumber`, `StatusDot`, `Carousel` autoplay, the OTP caret all calm down; **`Spinner` keeps spinning**." —— **装饰性动效停、功能性动效留**，这是我们该抄的分级规则本身。
  - "**Dynamic Type** — each `TextStyle` anchors to a semantic `Font.TextStyle` via `relativeTo:`."
  - **CSS 直读（对我们的流程最关键）**："Already have a web design system as CSS custom properties? Hand it to ThemeKit **directly** — the `oklch()` / hex variables are parsed on-device at runtime... **No JSON, no build step.**"、"`Theme.shared.setColorScheme(dark: true)` switches to the CSS's .dark block"、"Both the `:root`/`.light` and `.dark` blocks are read"、"the CSS is treated as untrusted text — only `--var: value;` declarations are read, nothing is executed"。
  - 离线转换脚本原文："`python3 tools/import_css_theme.py theme.css --name brand --out Sources/ThemeKitCore/Resources --font Inter`"（产出 `brandTheme.json + brandThemeDark.json`）。
  - MCP 工具清单原文："22 on-demand tools — `get_component_api`, `get_design_tokens`, `search_components`, `validate_code`, `a11y_audit`, `lint_snippet`, `compose_screen`, `scaffold_screen`…" —— **`a11y_audit` + `lint_snippet` + `validate_code` 就是"AI 生成 UI 的质量控制"**。
  - Figma 往返："turn on the Figma desktop **Dev Mode MCP server**（Figma ▸ Preferences ▸ *Enable Dev Mode MCP server*）；it serves at `http://127.0.0.1:3845/mcp`" —— **依赖 Figma 桌面版，我们没有**。
  - 许可原文："[MIT](LICENSE) © 2026 İsa Mercan. Free for commercial and private use — keep the copyright notice"。
- **许可与依赖**：MIT；核心零依赖（Lottie / Calendar 是可选 trait）；内置 32 套 daisyUI 风格预设 + HeroUI 主题 + Montserrat/Inter 字体（SIL OFL）。
- **接入成本**：天级（引 ThemeKitCore + 自己写 10 个组件）到周级（整体换皮）。
- **⭐ 可复用方案**：用途＝(a) **CSS → token JSON 的离线转换脚本**（我们已有 CSS 设计稿，这是最短路径）；(b) token 语义命名 + JSON 存储 + 代码生成的目录结构；(c) Reduce Motion / Dynamic Type 的组件级处理分级；(d) MCP 的 `a11y_audit`/`validate_code` 工具设计。许可＝MIT；接入成本＝天级；替代自造的＝自己写 CSS→JSON 转换器 + Swift 端 4 变体解析。
- **采用决策**：**混合（抄架构，不引组件库）**。理由：它的**视觉语言是 Ant Design / daisyUI**，与"界面必须嵌入苹果系统"正面冲突——175 个组件（Card 套 Card、Badge、Chip、DataTable…）我们一个都不该用；但它的**架构层**（语义 token、never hardcode、Reduce Motion 分级、Dynamic Type relativeTo、CSS 直读）**几乎是为我们的约束定制的**。
  - ❗ 高对比缺口：ThemeKit 只有 light/dark（`defaultTheme / oceanTheme / sunsetTheme (+ Dark)`），**没有高对比变体**——我们的 4 变体要求它满足不了，这一段要靠 3.5 与自建补齐。
- **⭐ 具体落到**：**iOS 端 + 设计流程**。① `tokens.json` 目录结构与语义命名直接照它的 CTI 思路；② CSS → token 的转换脚本按它的 `import_css_theme.py` 思路自写（我们要多导出高对比一套）；③ 每个组件读 `accessibilityReduceMotion` 的分级规则照抄。

### 3.5 `muhittincamdali/SwiftUI-Design-System-Pro`

- **一句话是什么**：MIT 的 SwiftUI 设计系统，**每个颜色 token 有 light / dark / high-contrast 三个值**——这是本轮唯一直接命中我们"4 变体"约束的库。
- **实测依据（README 原话）**：
  - "**Light and dark mode** — every color token has a **light, a dark and a high-contrast value**, and the components pick the right one from the environment." —— **这就是我们要求的 4 变体的实现路径**（浅/深 × 默认/高对比）。
  - "**Contrast checks** — `ColorContrastUtility` computes WCAG contrast ratios; the tests check body text and filled-button labels against **WCAG AA in both color schemes**." —— **对比度自动校验**（我们要用它校验 4 套色的每一对）。
  - "**Tested rendering** — a test renders every component group in light and dark mode and compares it with stored reference fingerprints, **so a color or layout change fails CI**." —— 视觉回归进 CI 的样板。
  - API 原文：`ColorContrastUtility.contrastRatio(.white, Color(hex: "#2563EB"))` / `ColorContrastUtility.meetsWCAG_AA(...)`。
  - 目录结构原文："`Sources/DesignSystemPro ├── Tokens/ ColorTokens, TypographyTokens, SpacingTokens, BorderTokens, ShadowTokens, **AnimationTokens** ├── Theme/ ├── Components/`" —— **动效也是 token**，和我们"动效参数要收敛"的方向一致。
  - ⚠️ 成熟度原文："**The package was reduced to placeholder files in June 2026; 2.0 restores the earlier tokens, theme engine and components**" —— 曾经被掏空重做。
  - ⚠️ 已知缺口（Roadmap 原文）："Raise the contrast of avatar initials on the lighter palette colors and of the checkbox tick in dark mode to WCAG AA." —— 它自己承认有没过的对比度项。
- **许可与依赖**：MIT；零运行时依赖；iOS 17+ / Swift 6 / **Xcode 26+**。
- **接入成本**：天级（引包 + 换成我们的 token）/ 周级（自建同构）。
- **⭐ 可复用方案**：用途＝(a) **light/dark/high-contrast 三值 token 的结构**；(b) `ColorContrastUtility` 的 WCAG 对比度校验；(c) "组件渲染指纹"式视觉回归 CI；(d) token 分层目录（含 AnimationTokens）。许可＝MIT；接入成本＝天级；替代自造的＝自己写对比度计算 + 4 变体表。
- **采用决策**：**复用代码，不引整个包**。理由：它是**唯一把"高对比"当成一等公民**的开源实现，这正是我们 iOS 端最缺的一块；但它的组件是 `DSCard`/`DSSnackbar`/`DSToast` 这类 Web 化组件，且要求 Xcode 26+（我们本机无 Mac/Xcode），所以**只取 Tokens + Contrast 工具这两层**。
- **⭐ 具体落到**：**iOS 端**。① `ColorTokens` 的 4 变体表结构（浅/深 × 默认/高对比）作为我们语义色表的骨架；② `ColorContrastUtility` 的算法抄进我们的校验脚本，对 4 套色全部跑 WCAG AA。

### 3.6 `style-dictionary/style-dictionary`

- **一句话是什么**：4868 star 的跨平台设计 token 构建系统（Node CLI），"一次定义样式，处处使用"。
- **实测依据（README 原话 + 源码原文）**：
  - "> _Style once, use everywhere._"、"A Style Dictionary uses design tokens to define styles once and use those styles on any platform or language... **exports these tokens to all the places you need - iOS, Android, CSS, JS, HTML, sketch files**"。
  - "It is available as a CLI through npm, but can also be used like any normal node module if you want to extend its functionality." —— **CLI 与库两种接法**，本机 node v24.14.0 直接可用。
  - `lib/common/formats.js` 原文证实有 **Swift 输出格式**：`iosSwiftClassSwift`（"Creates a Swift implementation file of a class with values. It adds default `class` object type, `public` access control and `UIKit` import."）、`iosSwiftEnumSwift`、`iosSwiftAnySwift`（"objectType='class'" 可改 `'struct'`、`accessControl='internal'`、`import=['UIKit','AnotherModule']`），模板文件 `ios-swift/any.swift.template.js`。
  - 生成样例原文：`public class StyleDictionary { public static let colorBackgroundDanger = UIColor(red: 1.000, green: 0.918, blue: 0.914, alpha: 1) }` —— **默认产出 `UIColor`（UIKit）而非 SwiftUI `Color`**，我们需要自定义 format。
  - 变换可扩展原文："The style dictionary build system is made to be extended."（`registerTransform` / `registerFormat`）。
  - DTCG 支持：源码中 `usesDtcg` 贯穿全程，支持 W3C Design Tokens 格式（`$value` / `$description`）。
- **许可与依赖**：**Apache-2.0**（含专利授权条款，比 MIT 更严的合规义务）；纯 Node，无原生编译依赖。
- **接入成本**：天级（写 `config.json` + 一个自定义 Swift format + 一个 CSS 变量源）。
- **⭐ 可复用方案**：用途＝**我们设计 token 的唯一真源**：`tokens.json` → 一条命令生成 CSS 变量（给 HTML 设计稿）+ Swift token 文件（给 iOS 端）+ JSON（给 Penpot/其他）。许可＝Apache-2.0；接入成本＝天级；替代自造的＝自己写一套 JSON→多语言生成器（2–3 天，且要维护）。
- **采用决策**：**复用（当作 token 管线主干）**。理由：这是本轮唯一一个**同时覆盖我们两端**（HTML 设计稿 / SwiftUI 代码）且**能在 Windows 上跑**的方案；它还是**工具链**而非视觉库，不与"嵌入苹果系统"冲突。用 `registerFormat` 写一个我们自己的 `swiftui/color.swift` format 即可输出 `Color(light:dark:highContrastLight:highContrastDark:)`。
- **⭐ 具体落到**：**设计流程 + iOS 端**。`tokens/*.json` 作为设计 token 真源 → `style-dictionary build` → `css/variables.css`（喂给 HTML 设计稿）+ `Tokens.swift`（喂给 SwiftUI）。与 3.5 的 4 变体表结构、3.4 的语义命名配套使用。

### 3.7 `pointfreeco/swift-snapshot-testing`

- **一句话是什么**：4377 star 的 Swift 快照测试事实标准，能把任何值（不只是 UIView）快照成图片或文本。
- **实测依据（README 原话）**：
  - "**Delightful Swift snapshot testing.**"、"Once **installed**, _no additional configuration is required_."
  - "While most snapshot testing libraries in the Swift community are limited to `UIImage`s of `UIView`s, SnapshotTesting can work with _any_ format of _any_ value on _any_ Swift platform!"
  - "**Device-agnostic snapshots.** Render views and view controllers for specific devices and trait collections from a single simulator." + 样例 `assertSnapshot(of: vc, as: .image(on: .iPhoneSe))` —— **一个模拟器出多机型截图**，正是我们"HTML 出多尺寸截图"的对偶能力。
  - "You can override trait collections (for specific size classes and content size categories)" —— **能出 Dynamic Type 大字号截图**。
  - ⚠️ "Snapshots must be compared using the exact same simulator that originally took the reference to avoid discrepancies between images."
  - "**Supports any platform that supports Swift.** Write snapshot tests for iOS, Linux, macOS, and tvOS."
  - 插件清单原文（说明生态位置）："[Prefire] generating Snapshot Tests via Swift Package Plugins using SwiftUI `Preview`"、"[PreviewSnapshots] share `View` configurations between SwiftUI Previews and snapshot tests"、"[AccessibilitySnapshot] adds easy regression testing for iOS accessibility"。
- **许可与依赖**：MIT；零运行时依赖（Swift Testing / XCTest 均可）；Swift 6 支持（`Package@swift-6.0.swift` 存在）。
- **接入成本**：天级（加 SPM 依赖 + 写首批断言）；且**必须有 Mac + Xcode**。
- **⭐ 可复用方案**：用途＝iOS 端视觉回归 + 组件多尺寸/多 Dynamic Type 快照基线。许可＝MIT；接入成本＝天级；替代自造的＝自建 SwiftUI 截图管线（ImageRenderer + 自己的 diff，成本更高）。
- **采用决策**：**复用（作为 iOS 端回归基线，但排在 Windows 侧工具之后）**。理由：它是快照测试领域的公认基线，求职作品里"用 Point-Free 的 SnapshotTesting"是加分项；但**我们本机没有 Mac/Xcode**，所以它是**提交到 GitHub 的代码里该有的东西**，不是本机现在就能跑的东西——评审顺序上要让位给 Windows 可跑的方案。
- **⭐ 具体落到**：**iOS 端**。每个关键屏幕（陪伴页、设置页）出 light/dark × 常规/大字号 四张基线。

### 3.8 `BarredEwe/Prefire`

- **一句话是什么**：把 `#Preview` 块自动变成快照测试 + Playbook 组件目录 + 流程文档的 SPM 插件。
- **实测依据（README 原话）**：
  - "**Prefire** transforms your `#Preview` blocks into: ✅ Snapshot tests ✅ Playbook views ✅ Visual flows with states and user stories ✅ Living documentation — fully automated"
  - "📸 **Snapshot Testing** — automatic test generation from previews (iOS, tvOS, macOS)"
  - "🏃 **Flow-aware** — build user stories from multiple preview steps"、".previewUserStory(.auth)"、".previewState(.loading)" —— **把"一屏 ≈ 80 字、One-idea-per-screen"变成可枚举的状态集**，与我们的状态设计天然契合。
  - "Instead of guessing a delay, you can wait until the preview stops changing: `.snapshot(waitForIdle: true)`" —— 解决"动画未停就截图"的经典坑。
  - "⚙️ **SPM + Xcode Plugins** — works in CLI, Xcode build phases, or CI"；"CLI (`brew install prefire`)"。
  - "Requirements — Swift 6.0 or higher / **Xcode 16.0 or higher** / iOS 14 or higher"。
- **许可与依赖**：Apache-2.0；依赖 `pointfreeco/swift-snapshot-testing`（README 的 `Package.swift` 示例同时引两者）。
- **接入成本**：天级；**必须有 Mac + Xcode 16+**。
- **⭐ 可复用方案**：用途＝"设计稿即状态清单"——用 `#Preview` 写状态，Prefire 自动生成状态矩阵（`.previewState`）与快照。许可＝Apache-2.0；接入成本＝天级；替代自造的＝手工维护状态表 + 手写快照断言。
- **采用决策**：**复用（iOS 端，且与 3.7 绑定使用）**。理由：它把"我们要给用户过目的每个状态"变成**代码里的 Preview 声明**，正好满足"一切面向人的 UI 必须先给用户过目"——过目对象就是 Preview 本身，而不是另一份文档。
- **⭐ 具体落到**：**iOS 端**。每个屏幕写 `#Preview` + `.previewState(...)`，Prefire 生成 Playbook（组件目录）与快照基线。

### 3.9 `cashapp/AccessibilitySnapshot`

- **一句话是什么**：把"无障碍层级"做成可快照断言的框架，让 VoiceOver 标签/顺序的回归能被测出来。
- **实测依据（README 原话）**：
  - "AccessibilitySnapshot makes it simple to add regression tests for accessibility in iOS apps. The framework **builds on the idea of snapshot testing** to provide **snapshots of the accessibility hierarchy**."
  - "Accessibility snapshot tests **require that the test target has a host application**."
  - "Snapshots can also be customized in a few ways, for example controlling when to include indicators for the accessibility **activation point** of each element."
  - 可单独引核心："To use only the core accessibility parser, add a dependency on the Core library alone: `AccessibilitySnapshotCore`"。
  - 许可原文："Copyright 2020 Square Inc. Licensed under the Apache License, Version 2.0"。
- **许可与依赖**：Apache-2.0；依赖 SnapshotTesting（或 `iOSSnapshotTestCase`）；iOS 13+ / Xcode 13.2.1+；**必须有 Mac**。
- **接入成本**：天级。
- **⭐ 可复用方案**：用途＝iOS 端"无障碍层级"回归测试（VoiceOver 标签、激活点顺序）。许可＝Apache-2.0；接入成本＝天级；替代自造的＝人工在真机 VoiceOver 里逐屏检查（不可回归、不可进 CI）。
- **采用决策**：**复用（iOS 端，优先级低于 3.7/3.8）**。理由：我们有 44×44pt 触控目标、最小 11pt 字号、禁 emoji 图标等硬约束，但**没有自动校验手段**；这个库把"标签是否写对"变成 CI 能拦的东西。属于"该有但可以晚点做"。
- **⭐ 具体落到**：**iOS 端**。每个交互元素断言其 accessibility label 与 activation point，防"改了 UI 忘了改 VoiceOver"。

### 3.10 `pa11y/pa11y` + `dequelabs/axe-core`

- **一句话是什么**：命令行无障碍测试器（封装 axe-core 与 HTML_CodeSniffer），**直接审 HTML 文件**——我们的设计稿正好是 HTML。
- **实测依据（README 原话）**：
  - "Pa11y is your automated accessibility testing pal. It runs accessibility tests on your pages **via the command line or Node.js**, so you can automate your testing process."
  - "**Windows** — On Windows 11, download a pre-built package from the Node.js website. Pa11y will be usable via the bundled Node.js application as well as the Windows command prompt." —— **官方明确支持 Windows**。
  - "Find accessibility issues in **a local HTML file** (absolute paths only, not relative): `pa11y ./path/to/your/file.html`" —— **不需要起服务器**，直接审我们的设计稿文件。
  - 退出码原文："`0`: Pa11y ran successfully, and there are no errors / `1`: Pa11y failed run due to a technical fault / `2`: Pa11y ran successfully but there are errors in the page" —— **可直接做 CI 门禁**。
  - 标准与运行器："`-s, --standard <name> the accessibility standard to use: WCAG2AAA ..., WCAG2AA (default), or WCAG2A"；"`-e, --runner <runner> the test runners to use: htmlcs (default), axe"；"Use both axe and HTML_CodeSniffer in the same run"。
  - 可隐藏元素：`--hide-elements`（避免把"故意隐藏的装饰层"判成问题）。
  - axe-core 侧证据（`api.github.com/repos/dequelabs/axe-core` 元数据）：description = "Accessibility engine for automated Web UI testing"，7692 star，**MPL-2.0**，最近推送 2026-10-22。
- **许可与依赖**：pa11y = **LGPL-3.0-only**（作为 CLI/npm 开发依赖使用，不链接进我们的 App，无传染风险）；axe-core = **MPL-2.0**（文件级 copyleft，我们不改它的文件）。
- **接入成本**：**小时级**（`npm i -D pa11y` + 一条命令 + 退出码接 CI）。
- **⭐ 可复用方案**：用途＝**我们 HTML 设计稿的无障碍自动门禁**：对比度、标签、焦点顺序、alt 文本、ARIA。许可＝LGPL-3.0（仅开发期 CLI）+ MPL-2.0（引擎）；接入成本＝小时级；替代自造的＝人工对照 WCAG 逐条查（不可能持续）。
- **采用决策**：**复用（列为最高优先级之一）**。理由：这是本轮**唯一一个"能在本机 Windows 上、今天就、能直接校验我们真实产物（HTML 设计稿）"**的工具；而且它能顶替"我们没法在 Mac 上跑 SwiftUI UI Test"这一现实。同理 `axe-core` 可直接以 JS 方式嵌进我们已有的 playwright 视觉回归脚本。
- **⭐ 具体落到**：**设计流程**。`pa11y design/index.html --runner axe --standard WCAG2AA` 作为提交前必过项；配合 playwright 截图评审一起跑。

### 3.11 `doordash-oss/swiftui-preview-snapshots`

- **一句话是什么**：让"同一组配置"同时服务于 SwiftUI Preview 与快照测试的小库（DoorDash 开源）。
- **实测依据（README 原话）**：
  - "Library for **sharing view configurations between SwiftUI previews and SnapshotTesting snapshot tests**."
  - 用法：`static var snapshots: PreviewSnapshots<String> { PreviewSnapshots(configurations: [...], configure: { state in ... }) }`，再 `ContentView_Previews.snapshots.assertSnapshots()`。
  - "Xcode will create an individual SwiftUI Preview for each configuration that's provided."
- **许可与依赖**：Apache-2.0；依赖 `pointfreeco/swift-snapshot-testing`。
- **成熟度实测**：**最后推送 2024-07-19**（已停更约 2 年）。
- **接入成本**：小时级。
- **⭐ 可复用方案**：用途＝"一份配置 → Preview + 快照"的小模型。许可＝Apache-2.0；接入成本＝小时级；替代自造的＝自己写个 20 行的 `Config` 协议。
- **采用决策**：**不引依赖，读思路**。理由：它做的事在 Prefire（3.8）里已被更大范围覆盖（Prefire 直接扫 Preview 生成快照）；且仓库停更。要点只有一条——**状态配置只写一份**，这个我们在自己的 Preview 封装里直接实现（更小、更贴我们的约束）。
- **⭐ 具体落到**：**iOS 端**。自写一个 20 行的 `PreviewConfig` 协议，让同一组状态配置喂给 `#Preview` 与快照断言。

### 3.12 `rive-app/rive-ios`

- **一句话是什么**：Rive 的 iOS/macOS runtime（Swift，MIT），运行时加载矢量交互动画。
- **实测依据（README 原话）**：
  - "An iOS/macOS runtime library for [Rive](https://rive.app) that supports **both UIKit, AppKit, and SwiftUI**."
  - "**Our lightweight open-source runtime libraries** allow them to load their animations into apps, games, and websites." —— **开源的是 runtime，编辑器是闭源商业 SaaS（rive.app）**。
  - "Supported platforms include iOS, macOS, tvOS, and visionOS."
- **许可与依赖**：runtime = MIT；**但创作端 Rive Editor 是商业 SaaS**，我们若采用 .riv 资产就把设计资产生产绑到别人的付费服务上（且他们的付费层与我们的"开源可发布"叙事不合）。
- **接入成本**：天级（iOS 端接入）+ 周级（重做 300+ PNG 表情为矢量骨骼动画）。
- **⭐ 可复用方案**：用途＝iOS 端矢量角色动画（状态机驱动表情）。许可＝MIT（runtime）；接入成本＝周级；替代自造的＝用现有 PNG 序列帧（我们已有 300+ 官方 PNG 资产）。
- **采用决策**：**不采用**。理由三条：① 我们已有官方 StackChan 的 300+ PNG 表情资产，重做成 .riv 是纯浪费且会与设备端 320×240 的像素资产体系割裂；② Rive Editor 是闭源商业服务，与"开源可发布作品"的叙事冲突；③ 设备端 ESP32-S3（550–700mAh、320×240）**根本跑不动 Rive C++ runtime**（`rive-runtime` 仓库 139MB 体量级），会出现"手机端动画很顺、机器人脸不动"的割裂。
- **⭐ 具体落到**：**不落模块**。仅保留一条可借鉴：它的 **state machine** 概念（用输入驱动状态而非播放动画）——我们要给"小栈"做表情状态机时，用 **PNG 帧索引表**实现同样语义，不引入引擎。

### 3.13 `piskelapp/piskel`

- **一句话是什么**：12861 star 的浏览器端像素/精灵图编辑器，专门做精灵图与序列帧动画。
- **实测依据（README 原话）**：
  - "**Piskel is an easy-to-use sprite editor.** It can be used to create game sprites, animations, pixel-art..."
  - "The Piskel editor is purely built in **JavaScript, HTML and CSS**."、"**Browser Support** — Chrome (latest) / Firefox (latest) / Edge (latest) / Brave (latest)"。
  - "**Offline builds are available.**"（wiki: Desktop-applications）—— 支持离线桌面版。
  - 依赖里含 "**gifjs**: generate animated GIFs in javascript, using webworkers" —— **能出动画 GIF / 帧序列**。
  - 许可原文："Copyright 2017 Julian Descottes. Licensed under the Apache License, Version 2.0"。
- **许可与依赖**：Apache-2.0；纯前端，可本地静态托管；无强制付费层。
- **接入成本**：小时级（打开即用）；若要批量导出到我们的资产目录，天级（写脚本调它的 API 或导出 ZIP）。
- **⭐ 可复用方案**：用途＝**表情资产流水线**：把 StackChan 的 PNG 表情重组成精灵图/帧序列、统一帧率与命名、产出可直接嵌进 LVGL 的资源。许可＝Apache-2.0；接入成本＝小时级；替代自造的＝用 PIL 脚本硬切 PNG（能用，但无编辑器、无法人工调帧）。
- **采用决策**：**复用（作为资产整理工具，非运行时依赖）**。理由：我们的表情资产是 300+ PNG，真正的工作量在"归一化（尺寸/帧率/方向/命名）"而不是"创作"；Piskel 正是干这个的，而且是 Windows 浏览器里点开就能用、Apache-2.0、无账号。
- **⭐ 具体落到**：**设备端 + iOS 端资产**。用 Piskel 把官方 PNG 表情整理成按状态分组的帧序列，产出命名规范供两端共用。

### 3.14 `sparrowcode/live-activity-example`

- **一句话是什么**：Live Activity + 灵动岛 + 锁屏三处的最小可运行范例（MIT，37 star）。
- **实测依据（README 原话）**：
  - "**Example how to make, update and end Live Activity. With Dynamic Island and Lock Screen.**"
  - "Supported only for iOS >=16.1"、"Live Activity already enabled for upload with Xcode 14.1 RC"。
  - 清单页原文："Add to `Info.plist` key `Supports Live Activities` to true: `<key>NSSupportsLiveActivities</key><true/>`"。
  - 结构原文："`ActivityConfiguration(for: ActivityAttribute.self) { context in // UI for lock screen } dynamicIsland: { context in // UI for Dynamic Island }`"。
  - 动态/静态分离原文："Dynamic can be updated in time and make changes in UI. Static using only for launch Live Activity."
- **许可与依赖**：MIT；仅需 Widget target + ActivityKit（系统框架，无第三方依赖）。
- **接入成本**：天级（要 Mac + Xcode + 证书 + ActivityKit 权限）。
- **⭐ 可复用方案**：用途＝**"小栈状态"进系统表面**的落地参照：锁屏/灵动岛显示"小栈现在在做什么"。许可＝MIT；接入成本＝天级；替代自造的＝自己啃 ActivityKit 文档（1–2 周）。
- **采用决策**：**复用（作为实现范式，iOS 端）**。理由：它把"锁屏 + 灵动岛 + 更新 + 结束"四件事的最小骨架给全了；我们只要把 `ContentState` 换成"小栈状态"即可。**注意这是 Mac-only 依赖**，且 Live Activity 是"锦上添花"，不是首屏必需（我们 Tab 只 2 个、深度 ≤2 的约束下，系统表面是加分项）。
- **⭐ 具体落到**：**iOS 端**。`ActivityAttributes` 定义"小栈状态"（思考中/聆听中/待办提醒），锁屏与灵动岛共用一份 `ContentState`。

### 3.15 `salesforce-ux/design-system-ios`（作为**反例**深评）

- **一句话是什么**：Salesforce Lightning Design System 的 iOS 静态库——一个"设计 token → iOS 代码"的经典样板，但**已死**。
- **实测依据（README 原话）**：
  - "⚠️ **This POD is no longer being updated.**"、"Current release: **Spring '19**"（实测仓库元数据：`archived: true`，最后推送 2025-06-09）。
  - API 形态原文：`UIColor.sldsBackgroundColor(.colorBackground)`、`UIColor.sldsOverrideBorderColor(.colorBorderBrand, with: UIColor.cyan)` —— **token 语义名 + 运行期可覆盖**，这套 API 形态仍然值得抄。
  - 许可原文："Source code is licensed under **BSD 3-Clause**"、"**All icons and images are licensed under Creative Commons Attribution-NoDerivatives 4.0**"、"The **Salesforce Sans** font is licensed under our font license"。
- **许可与依赖**：源码 BSD-3-Clause（可商用）；**图标 CC BY-ND 4.0（禁止演绎）**；字体为专有许可。
- **接入成本**：天级（但目标是死的，不值）。
- **⭐ 可复用方案**：用途＝**只抄 API 形态**：`UIColor.sldsBackgroundColor(.colorBackground)` 这种"语义名 → 值"的调用风格。许可＝BSD-3-Clause（仅参考调用形态，不复制文件）；接入成本＝小时级。
- **采用决策**：**明确不采用**。理由：① 仓库已归档、版本停在 2019 年春，无人维护；② 视觉语言是 Salesforce 而非 Apple；③ **图标 CC BY-ND 禁止修改**，与我们要做"自己的表情/图标体系"直接冲突；④ 专有字体不可用。列在这里的价值在于**留个墓碑**，以后不用再查。
- **⭐ 具体落到**：**不落模块**。

---

## 四、⭐ 最终采用清单（按优先级，含"先做什么"）

> 排序权重：**① 能不能在 Windows 本机今天就跑起来** → ② 能不能直接校验我们真实产物 → ③ 与"嵌入苹果系统"的视觉/规范冲突程度 → ④ 接入成本。
> P0 = 本机可独立完成，不依赖 Mac；P1 = 写进 iOS 代码（需 Mac 才能编译运行，但代码要进 GitHub 作品集）；P2 = 锦上添花。

### P0 —— 先做这四件（本机 Windows 即可闭环，直接产出可展示的证据）

| 序 | 做什么 | 用哪个项目 | 许可 | 预计投入 | 产出物（可进 GitHub） |
|---|---|---|---|---|---|
| **P0-1** | **HTML 设计稿无障碍门禁**：对比度、alt、焦点顺序、ARIA | `pa11y/pa11y` + `dequelabs/axe-core` | LGPL-3.0（CLI）+ MPL-2.0（引擎） | **小时级** | `npm run a11y` 脚本 + 一份设计稿无障碍报告 |
| **P0-2** | **设计 token 真源**：一份 `tokens.json` → 同时产出 CSS 变量与 Swift token | `style-dictionary/style-dictionary` | Apache-2.0 | **天级** | `tokens/*.json` + `config.json` + `build/tokens.css` + `build/Tokens.swift` |
| **P0-3** | **4 变体语义色落地**：浅/深 × 默认/高对比，每一对跑 WCAG AA | 自建，结构抄 `SwiftUI-Design-System-Pro`（light/dark/high-contrast 三值 token）+ `ColorContrastUtility` | MIT（抄结构与算法） | **天级** | `tokens/color.json`（4 变体）+ 对比度校验脚本 + 报告 |
| **P0-4** | **表情资产归一化**：300+ PNG → 按状态分组的帧序列 + 命名规范 | `piskelapp/piskel` | Apache-2.0 | **小时级** | `assets/faces/<state>/*.png` + 命名与帧率规范 |

> **为什么 P0 先做这四件**：它们**不需要 Mac**，不需要 Figma，不需要任何账号或付费服务，
> 而且校验的是我们**真实存在的产物**（HTML 设计稿、PNG 表情）。在"没有 Mac"的现实下，
> 这是唯一能当场拿出**可复现证据**的路径——对求职作品来说，"能跑的检查脚本"比"截图好看"更有说服力。

### P1 —— 写进 iOS 代码（本机写、Mac 上跑）

| 序 | 做什么 | 用哪个项目 | 许可 | 预计投入 | 说明 |
|---|---|---|---|---|---|
| **P1-1** | **图标体系**：全部改用 SF Symbols，弃 emoji | `SFSafeSymbols/SFSafeSymbols` | MIT | 小时级 | 静态类型、无图标名拼写错、随系统版本演进 |
| **P1-2** | **状态即代码**：`#Preview` + `.previewState` 声明每屏状态，生成快照基线 | `BarredEwe/Prefire` + `pointfreeco/swift-snapshot-testing` | Apache-2.0 + MIT | 天级 | 满足"一切面向人的 UI 必须先给用户过目"——过目对象就是 Preview |
| **P1-3** | **token 层**：语义名 + JSON 真源 + `Color` 解析（含 4 变体） | 结构抄 `isamercan/ThemeKit`（never hardcode / 语义名 / Reduce Motion 分级 / Dynamic Type `relativeTo:`） | MIT | 天级 | 不引组件库，只引架构；组件全部自写，保持 Apple 原生观感 |
| **P1-4** | **Reduce Motion / Dynamic Type 分级**：装饰性动效停、功能性动效留 | 抄 `ThemeKit` 的分级规则原文（`BorderBeam`/`Skeleton` 停，`Spinner` 留） | MIT | 小时级 | 写进我们自己的 `MotionStyle` 单一入口，全 App 复用 |
| **P1-5** | **无障碍层级回归** | `cashapp/AccessibilitySnapshot` | Apache-2.0 | 天级 | 防"改了 UI 忘了改 VoiceOver" |

### P2 —— 增值项（做不完不影响主线）

| 序 | 做什么 | 用哪个项目 | 许可 | 预计投入 | 说明 |
|---|---|---|---|---|---|
| **P2-1** | **陪伴状态指示器**（只取一个状态） | `haplollc/ThinkingOrbs`（只用 `.breathing`） | MIT（需双署名：原设计作者 + 移植者） | 小时级 | 纯灰度、不新增颜色、自带 Reduce Motion / Increase Contrast 处理；**只上一个，不上九个** |
| **P2-2** | **系统表面**：Live Activity + 灵动岛显示"小栈状态" | `sparrowcode/live-activity-example` | MIT | 天级 | Mac-only；是加分项不是首屏必需 |
| **P2-3** | **动效手法参考库** | `amosgyamfi/open-swiftui-animations` | Unlicense | 小时级 | 只抄手法（PhaseAnimator / 弹簧参数），**逐条按我们的规则重写**，禁 Liquid Glass / 渐变球 |

### 一句话执行顺序

> **先做 P0-1（今天就能跑出第一份报告）→ P0-2/P0-3（token 管线，喂给设计稿）→ P0-4（资产）→ 再进 P1（iOS 代码）→ 有余力再 P2。**

---

## 五、⭐ 明确不采用（写清理由，避免以后重复评估）

| 项目 | 不采用的**决定性理由**（一句话） | 留个什么用 |
|---|---|---|
| `Nutlope/hallmark` | 第 14 份文档已评估并采纳其 Floor 16 条规则；规则是 CSS 专属、主题发牌机制与"高度统一"冲突 | 不重复评估 |
| `ibelick/ui-skills` | 第 14 份文档已评估；已采纳 `baseline-ui` 与 `fixing-motion-performance` | 不重复评估 |
| `salesforce-ux/design-system-ios` | 仓库已归档、版本停在 2019 春；**图标 CC BY-ND 禁止演绎**、字体专有 | 只留"语义 token 调用形态"这一思路（§3.15） |
| `EmergeTools/Pow` | 视觉语言是粒子/glow/mesh 渐变，与"禁渐变球/glow/HIG 内容层禁 Liquid Glass"**正面冲突** | 无 |
| `Shubham0812/SwiftUI-Animations` | 演示工程合集，不是可依赖的库；我们只需要动效手法，不需要组件 | 无 |
| `swiftui-lab/swiftui-hero-animations` | 最后推送 2020-07（停更）；且共享元素转场在我们"层级 ≤2、单屏一屏一意"的场景**用不上** | 读一次 matchedGeometryEffect 写法即可 |
| `rive-app/rive-ios` / `rive-runtime` | **编辑器是闭源商业 SaaS**；与我们已有的 300+ PNG 资产重复；**设备端 ESP32-S3 跑不动 C++ runtime** | 只留"状态机"概念，用帧索引表实现 |
| `EsotericSoftware/spine-runtimes` | GitHub 元数据许可为 **NOASSERTION（未识别）**，Spine 另有专有运行时许可与付费编辑器；设备端过重 | 无（且许可需进一步核实，本轮不列为可用依赖） |
| `lost-pixel/lost-pixel` | **仓库已归档**（2026-04-22 最后推送）；视觉回归概念由 3.7 + playwright 覆盖 | 概念可读（Percy/Chromatic 开源替代的思路） |
| `penpot/penpot-plugins` | **仓库已归档**；Penpot 插件生态在成熟度上不稳定 | 用 `penpot-plugin-starter-template`（MIT，未归档）即可 |
| `jasonkneen/ShadKit` | shadcn/ui + Vercel AI Elements 的 SwiftUI 移植＝Web 视觉语言，与"嵌入苹果系统"冲突 | 无 |
| `doordash-oss/swiftui-preview-snapshots` | 最后推送 2024-07（停更）；能力被 Prefire 更大范围覆盖 | 只留"一份配置喂 Preview 与快照"的小模型，自己写 20 行 |
| `tokens-studio/sd-transforms` | 它服务的是 Tokens Studio 导出格式；我们**不采用 Tokens Studio 工作流**（无 Figma） | 若将来引入 Figma 再启用 |
| `SwiftUIX/SwiftUIX` | 8185 star 但提供 200+ 扩展；整体引入＝"套皮"风险，且与"简约不堆功能"冲突 | 若需某个具体 API（如某个 transition）可单独取那一段 |
| `awesome-selfhosted/awesome-selfhosted` | 329k star 的清单，但它是**资料索引**不是依赖；本轮未逐条筛出与我们相关条目（见 §八） | 作为"找陪伴/宠物/待办类 UI 实现"的检索入口 |
| `penpot/penpot-exporter-figma-plugin` | Penpot → Figma 导出；**我们没有 Figma**，方向反了 | 若将来上 Figma 再看 |
| `haplollc/ThinkingOrbs` 的 8 个非 `.breathing` 状态 | 9 个状态 = 堆功能，违反"简约、不堆功能" | 只留 `.breathing` |

---

## 六、本机可运行性核查（Windows / 无 Mac / 无 Xcode）

> 判据：**本机能跑 = 现在就能产出证据**；**Mac-only = 写进代码但本机无法验证**（降级项，不是依赖项）。

### 6.1 ✅ Windows 本机可直接跑（无 Docker、无账号、无 Mac）

| 项目 | 跑起来需要什么 | 本机现状 | 用途 |
|---|---|---|---|
| `pa11y/pa11y` | Node 22.13+ / 24 / 26（README 明确列 `22.13.0`, `24`, `26`）+ 自带 Puppeteer/Chrome | **node v24.14.0 / npm 11.9.0 已装** | 审 HTML 设计稿无障碍 |
| `dequelabs/axe-core` | 浏览器内 JS（本机已有 **playwright**） | Python playwright 已装 | 对比度/焦点顺序自动校验 |
| `style-dictionary/style-dictionary` | Node | 同上 | token → CSS/Swift |
| `piskelapp/piskel` | Chrome/Edge 浏览器；也可本地静态托管 | Windows + 浏览器 | 表情帧序列整理 |
| `penpot/penpot`（Desktop） | 已装 **Penpot Desktop 0.23.1** | 已就绪 | 设计稿本体 |
| `lost-pixel/lost-pixel` | Node | 同上 | ⚠️ 仓库已归档，只读不引 |

### 6.2 🖥 需要 Mac / Xcode（本机写不了、跑不了，只能写进代码等有 Mac 时再验）

| 项目 | 硬性要求（实测自 README） | 我们的处置 |
|---|---|---|
| `pointfreeco/swift-snapshot-testing` | 需 Xcode 快照测试宿主环境；"exact same simulator" 才能比对 | 写进代码，CI 在 macOS runner 上跑 |
| `BarredEwe/Prefire` | "Swift 6.0 or higher / **Xcode 16.0 or higher** / iOS 14 or higher" | 写进代码；Prefire CLI 官方安装方式是 `brew install prefire`（macOS） |
| `cashapp/AccessibilitySnapshot` | "test target has a host application"；Xcode 13.2.1+ | 写进代码 |
| `isamercan/ThemeKit` | Swift 6.2 / iOS 15.6+ / Xcode | **只抄架构，不引包**（引了也跑不了） |
| `muhittincamdali/SwiftUI-Design-System-Pro` | Swift 6.0 / **Xcode 26+** | **只抄 Tokens + Contrast 算法** |
| `signerlabs/ShipSwift` | iOS 18.0+ / Swift 5.0+ | 只抄目录结构与组件组织纪律 |
| `haplollc/ThinkingOrbs` | iOS 17+ / Swift 6 / Xcode 16+ | 写进代码（P2） |
| `rive-app/rive-ios` | Xcode + iOS/macOS | 不采用 |
| `sparrowcode/live-activity-example` | iOS 16.1+ / Xcode 14.1+ / Widget target | 写进代码（P2） |
| `SFSafeSymbols/SFSafeSymbols` | Swift / Xcode | 写进代码（P1-1） |

### 6.3 🌐 需要浏览器 + 对方服务 / 可选

| 项目 | 依赖的外部条件 | 我们的处置 |
|---|---|---|
| `isamercan/ThemeKit` 的 **MCP** | `npx -y @isamercan/themekit-mcp`（纯 npm，**Windows 可跑**）；但 Figma 那一路需要 "Figma desktop Dev Mode MCP server"（`http://127.0.0.1:3845/mcp`）→ **我们没有 Figma** | 只用 MCP 的 `a11y_audit` / `validate_code` / `get_design_tokens` 思路；Figma 那一路整体放弃 |
| `signerlabs/ShipSwift` 的 MCP | 官方 MCP 走 `https://api.shipswift.app/mcp`（外部服务）；但 README 提供 "**Option 2: Local Skills (No MCP Required)**" | 只用本地技能包思路，不连它的服务器 |
| `penpot/penpot-plugin-starter-template` | Penpot Desktop 插件开发 | 备选；不优先 |

### 6.4 🐳 需要 Docker / 服务端

| 项目 | 说明 |
|---|---|
| `penpot/penpot` 自托管 | 需要 Docker 跑前后端；**我们已装 Desktop，不必自托管** |
| `rive-app/rive-runtime`（C++） | 设备端 ESP32-S3 **不适用**（320×240 / 550–700mAh / 无 GPU），且 C++ runtime 体量远超 MCU 预算 |

### 6.5 📱 设备端（ESP32-S3）专门结论

- 本轮**没有找到**能在 ESP32-S3 上跑的高质量 2D 骨骼动画引擎（详见 §七 与 §八）；
- 官方 300+ PNG 表情资产的正解仍是**帧序列 + 索引表**（P0-4 做的归一化正是为此服务）；
- `Rive` / `Spine` 在设备端**均判出局**（体量与许可）。

---

## 七、许可风险清单

| 项目 | 许可 | 传染性 | 商用限制 | 署名要求 | 我们的用法 | 风险 |
|---|---|---|---|---|---|---|
| `pa11y/pa11y` | LGPL-3.0-only | 仅"以库形式链接"才传染；**CLI/npm 开发依赖不传染** | 无 | 需保留版权与许可声明 | 仅开发期 CLI | 🟢 低 |
| `dequelabs/axe-core` | MPL-2.0 | **文件级 copyleft**：改它的文件要公开改后的那些文件；**当作独立依赖使用不传染** | 无 | 改过的文件需标注 | 独立 npm 依赖 | 🟢 低 |
| `style-dictionary/style-dictionary` | Apache-2.0 | 无（**含专利授权终止条款**） | 无 | 需保留 LICENSE/NOTICE | token 管线依赖 | 🟢 低 |
| `isamercan/ThemeKit` | MIT | 无 | 无（"Free for commercial and private use"） | 需保留版权声明 | **只抄思路不引包** | 🟢 低 |
| `muhittincamdali/SwiftUI-Design-System-Pro` | MIT | 无 | 无 | 需保留版权声明 | 只抄 Tokens + Contrast 算法 | 🟢 低 |
| `pointfreeco/swift-snapshot-testing` | MIT | 无 | 无 | 需保留版权声明 | iOS 端测试依赖 | 🟢 低 |
| `BarredEwe/Prefire` | Apache-2.0 | 无 | 无 | 需保留 LICENSE/NOTICE | iOS 端测试插件 | 🟢 低 |
| `cashapp/AccessibilitySnapshot` | Apache-2.0 | 无 | 无 | 需保留版权声明（"Copyright 2020 Square Inc."） | iOS 端测试依赖 | 🟢 低 |
| `SFSafeSymbols/SFSafeSymbols` | MIT | 无 | 无 | 需保留版权声明 | iOS 端依赖 | 🟢 低 |
| `amosgyamfi/open-swiftui-animations` | Unlicense | 无（公共领域） | 无 | **无署名义务**（我们仍自愿注明来源） | 读代码 | 🟢 低 |
| `piskelapp/piskel` | Apache-2.0 | 无 | 无 | 需保留版权声明 | 资产整理工具 | 🟢 低 |
| `haplollc/ThinkingOrbs` | MIT（**双作者**） | 无 | 无 | **必须同时保留 thinking-orbs 原作者（Jakub Antalik）与移植者版权声明** | iOS 端单个指示器 | 🟡 中（易漏署名） |
| `signerlabs/ShipSwift` | iOS 客户端 MIT | 无 | ⚠️ **Pro 配方（后端/合规/踩坑文档）付费**；官方另售 $5,000 定制开发 | 需保留 MIT 声明 | 只读结构，不连其 MCP | 🟡 中（商业化叙事 + 外部服务） |
| `rive-app/rive-ios` / `rive-runtime` | runtime MIT | 无 | ⚠️ **编辑器 Rive Editor 是闭源商业 SaaS**；资产生产被绑定到对方付费层 | 需保留版权声明 | 不采用 | 🔴 高（商业化 + 资产锁定） |
| `EsotericSoftware/spine-runtimes` | **NOASSERTION（GitHub 未识别）** | 未知 | ⚠️ Spine 编辑器付费；运行时另有专有许可条款 | 未知 | 不采用 | 🔴 高（**本轮未取到 LICENSE 原文，不列为可用依赖**） |
| `salesforce-ux/design-system-ios` | 源码 BSD-3-Clause / **图标 CC BY-ND 4.0** / 字体专有 | 无 | ⚠️ **CC BY-ND 禁止演绎**；字体不可商用 | 需署名 | 不采用 | 🔴 高 |
| `penpot/penpot`（已装） | MPL-2.0 | 文件级 | 无 | 改动文件需公开 | 设计稿工具 | 🟢 低 |
| `penpot/penpot-plugin-starter-template` | MIT | 无 | 无 | 需保留声明 | 备选 | 🟢 低 |
| `lost-pixel/lost-pixel` | MIT | 无 | 无 | 需保留声明 | **已归档**，只读 | 🟢 低 |

**传染性小结**：本轮**没有任何一个采用项是 copyleft 且会被链接进我们发布的 App**。
`pa11y`（LGPL）与 `axe-core`（MPL）只作为**开发期命令行工具**存在，不进 App 二进制，**不产生传染义务**。

---

## 八、未取得 / 失败记录（如实写）

### 8.1 取数失败与通道故障

1. **`web_fetch` 访问 `github.com/topics/...` HTML 页面失败**（"web_fetch network request failed"）→ 改用 `api.github.com/search/repositories` 完成全部发现，未走网页榜单。
2. **`web_search` 工具未使用**（任务书已告知该工具在本机持续报 `MATRIX_TOOL_REQUEST_FAILED`）。
3. **仓库路径两次 404**：`amazon/style-dictionary` → 实为 `style-dictionary/style-dictionary`（组织迁移）；`lostpixel/lost-pixel` → 实为 `lost-pixel/lost-pixel`。均已按 404 后的正确路径重取成功。
4. **`data.jsdelivr.com` 文件清单**只在 `pointfreeco/swift-snapshot-testing` 上取过一次——该仓库 300+ 文件导致输出极长（单次近 2 万 token），**此后放弃用 jsdelivr 做通用清单**，改用 `api.github.com/repos/.../contents` 思路与 `raw` 取原文，避免再浪费上下文。

### 8.2 本轮**没有拿到**的东西（未编造，明确留白）

| 想找的 | 状态 |
|---|---|
| **iOS 18 ControlWidget（控制中心控件）的成熟开源实现** | ❌ **未查到有价值的样本**。按 "app intents / shortcut" 搜索只命中 Siri 时代的老 demo（`domeniconicoli/SiriKitIntentsUIExample` 等，20 star 级、2019–2024、无 license 或 MIT）。**未取到 README，未下结论**。 |
| **Action Button（iOS 17 操作按钮）开源实现** | ❌ 未查到独立样本，本轮无证据。 |
| **SwiftUI → 设计稿（Figma/Penpot）双向工具** | ⚠️ **只找到单向**：Penpot → Figma（`penpot-exporter-figma-plugin`，461★，MPL-2.0，仍在更新）。**反向（SwiftUI/HTML → Penpot 或 Figma）本轮未找到成熟方案**；ThemeKit 的 `export_figma_variables` / `import_figma_variables` 是最接近的，但它绑 Figma Dev Mode MCP，我们无 Figma。 |
| **SwiftUI → SVG/PNG 导出工具** | ❌ 未查到专门项目。**间接结论**：我们本机已有 Penpot（可导出 SVG）+ playwright（HTML → PNG），足以覆盖需求，暂不需要专门工具。 |
| **`awesome-selfhosted` 的逐条内容** | ❌ **只取到仓库元数据**（329508 star，2026-10-22 仍在更新），**未拉取完整 README、未筛出具体的陪伴/宠物/待办类条目**。故本文**不引用其中任何具体项目**。 |
| **Live2D / Cubism 的开源运行时** | ❌ 未实测。**仅凭生态常识排除**（Cubism 运行时对非商业用途有单独条款），**本轮未取 LICENSE 原文，不作为结论**。 |
| **`EsotericSoftware/spine-runtimes` 的 LICENSE 原文** | ❌ 未取。GitHub 元数据为 `NOASSERTION`，故本文只写"许可未识别/需核实"，不写成任何具体条款。 |
| **`lost-pixel/lost-pixel` / `tokens-studio/sd-transforms` / `SFSafeSymbols/SFSafeSymbols` / `SwiftUIX/SwiftUIX` / `EmergeTools/Pow` / `Shubham0812/SwiftUI-Animations` 的 README 原文** | ❌ **未取**。这 6 项在 §二 总表中只依据 `api.github.com/repos/...` 的**元数据**（description / license / stars / pushed_at）列出，**未进 §三 深评**，其"用途"栏均为元数据描述而非 README 佐证。 |

### 8.3 口径提醒（给下一个读者）

- 本文所有 **stars / license / pushed_at / archived** 都是 **2026-10-23 当日实测值**，会变；引用时请带日期。
- §三 中每一条"实测依据"都是 **README 或源码原文的直接引用**（英文原句），中文是本轮判断，两者已分开排版，不要把判断当成原文。
- 本文**不含**任何来自记忆或印象的项目功能描述。

---

## 附：本文与第 14 份文档的边界

- 第 14 份（`14-抖音设计情报与开源复用评估.md`）已评估 `Nutlope/hallmark` 与 `ibelick/ui-skills` —— **本文不重复评估**，只在 §五 标注"不重复评估"。
- 本文只负责**开源 iOS / SwiftUI 设计、动效、组件、设计系统与设计工具链**；设备端固件/LVGL/表情引擎的硬件侧评估由并行文档（`17-开源ESP32表情屏桌面机器人栈.md`）负责，本文只在其 §3.12/§6.5 处给出**跨端一致性结论**。
