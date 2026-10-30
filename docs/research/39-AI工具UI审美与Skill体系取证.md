# 39. AI 编程工具 UI 审美与 Skill 体系取证

> 目标：查明 Antigravity / Claude Code / Claude 桌面版 / Cursor / Windsurf / Trae / CodeBuddy / Qoder
> 这类 AI 工具「有质感」的来源（主题令牌、动效曲线、图标规范、排版阶梯、状态完整性），
> 以及它们 skill / rules 体系里**实际写下来的**设计要求条目。
> 产出：§五「质感 = 10 条可执行规范」。
>
> 本轮范围：仅本机取证 + 已读 skill 原文。**网络抓取按指令停止**，§四标「未取得」。

---

## 目录

- §一 结论摘要
- §二 本机取证（逐工具）
- §三 skill / rules 生态摘录
- §四 官方设计文档摘录
- §五 ⭐ 质感 = 10 条可执行规范
- §六 反面清单（廉价感做法）
- §七 未取得与风险
- 文末自查表

---

## §一 结论摘要

1. **Antigravity IDE 是 VS Code fork**（`resources/app/product.json`：`ideVersion: 2.5.5`、`quality: stable`、`dataFolderName: .antigravity-ide`、`extensionsGallery.serviceUrl: https://open-vsx.org/vscode/gallery`），其编辑器主体的**设计令牌整体继承 VS Code**，没有另起一套。
2. Antigravity 自研贡献点**只有一个**：`out/vs/workbench/contrib/antigravitySounds`（外加 `jetskiMain`/`jetskiAgent` 两块自有面板，走 Tailwind 构建）。主次不是靠视觉装饰做出来的，是靠**不新增、不并列**做出来的——这就是「功能折叠」的实物证据。
3. **「质感」的第一来源是听觉**：`contrib/antigravitySounds/media/` 内含 A0–Bb4 一整套钢琴采样 mp3（约 10089 字节/个），把完成/成功/失败等事件做成多模态反馈。多模态反馈是廉价感的天敌。
4. **「质感」的第二来源是规则文本**：本机 `~/.kun/skills/design-system/SKILL.md` 把审美写成了**可判定的条目**（token-only / 一套 spacing / 一屏一焦点 / 禁 bounce / 禁卡片套卡片 / 禁 emoji 图标 / 必须 prefers-reduced-motion），而不是形容词。
5. 因此可复用的不是色值，而是**「令牌化 + 单曲线家族 + 状态完备 + 不做半成品」这条流水线**。
6. 缺口：Cursor / Windsurf / CodeBuddy 桌面版**本机未确认安装**，Apple 侧质感无本机取证，只能靠规范落地。
7. 直接可抄的条目见 §三（2 个文件、19 条），可执行的规范见 §五（10 条）。

---

## §二 本机取证

### 2.0 扫描方法与结果

**方法**：`Get-ChildItem` 列举 `C:\Users\jss18\AppData\Local\Programs`、`C:\Users\jss18\AppData\Local`；
`glob` 列举 `C:\Users\jss18`（含 `.claude` / `.kun` / `.gemini` 等规则目录）。

| 工具 | 本机状态 | 路径 |
|---|---|---|
| Antigravity IDE | **已安装** | `C:\Users\jss18\AppData\Local\Programs\Antigravity IDE\` |
| antigravity | **已安装**（目录存在） | `C:\Users\jss18\AppData\Local\Programs\antigravity\` |
| Antigravity Tools | **已安装** | `C:\Users\jss18\AppData\Local\Programs\Antigravity Tools\`；`AppData\Local\Antigravity Tools`；`AppData\Local\com.lbjlaq.antigravity-tools`；`AppData\Local\com.antigravity.cockpit-tools` |
| Qoder | **已安装** | `C:\Users\jss18\AppData\Local\Programs\Qoder\`；`AppData\Local\QoderClientRs\` |
| Trae | **已安装** | `C:\Users\jss18\AppData\Local\Programs\Trae\` |
| Claude（桌面 / CLI） | **已安装** | `AppData\Local\AnthropicClaude`、`AppData\Local\Claude-3p`、`AppData\Local\claude-cli-nodejs`；规则目录 `C:\Users\jss18\.claude\` |
| Claude Code（规则体系） | **已安装** | `C:\Users\jss18\.claude\`（见 §3.1） |
| CodeBuddy | **部分**：仅见扩展目录 | `C:\Users\jss18\AppData\Local\CodeBuddyExtension\`（IDE 主体未在 `Programs` 中确认） |
| Cursor | **部分**：仅见客户端目录 | `C:\Users\jss18\AppData\Local\com.cursorpro.client\`（IDE 主体未在 `Programs` 中确认） |
| Windsurf | **未取得** | `Programs` 与 `AppData\Local` 枚举中均未出现 |
| Kiro | 已安装（附带发现，非本次目标） | `C:\Users\jss18\AppData\Local\Programs\Kiro\` |
| 其他附带发现 | 已安装 | `Penpot Desktop`、`aetherdesktop`、`MiniMax Code`、`CC Switch`、`DeepSeek GUI`、`Microsoft VS Code` |

### 2.1 Antigravity IDE（重点取证）

**路径**：`C:\Users\jss18\AppData\Local\Programs\Antigravity IDE\`

**（a）UI 实现方式：Electron / Chromium 外壳 + VS Code fork**

安装根目录可见典型 Chromium/Electron 打包物：
`chrome_100_percent.pak`、`chrome_200_percent.pak`、`resources.pak`、`icudtl.dat`、
`v8_context_snapshot.bin`、`vk_swiftshiftshader`/`vk_swiftshader.dll`、`vulkan-1.dll`、
`LICENSES.chromium.html`、`libEGL.dll`/`libGLESv2.dll`。
可执行文件：`Antigravity IDE.exe`；另有 `appx/`、`tools/`、`locales/`、`bin/` 子目录。

**（b）VS Code fork 的硬证据** — `resources/app/product.json`：

```json
"nameShort": "Antigravity IDE",
"quality": "stable",
"ideVersion": "2.5.5",
"nameLong": "Antigravity IDE",
"applicationName": "antigravity-ide",
"aliasName": "agy-ide",
"dataFolderName": ".antigravity-ide",
"win32MutexName": "antigravity-ide",
"win32AppUserModelId": "Google.AntigravityIDE",
"darwinBundleIdentifier": "com.google.antigravity-ide",
"extensionsGallery": { "serviceUrl": "https://open-vsx.org/vscode/gallery" },
"builtInExtensions": [ { "name": "ms-vscode.js-debug-companion", ... },
                       { "name": "ms-vscode.js-debug", "version": "1.104.0", ... } ]
```

`builtInExtensions` 直接引用 `ms-vscode.*` 官方扩展 → **确为 VS Code fork**。
用户数据目录：`.antigravity-ide`（可在 `%USERPROFILE%` 下核对）。

**（c）打包资源清单（实测）**

| 文件 | 大小 (bytes) | 归属 |
|---|---|---|
| `resources/app/out/vs/workbench/workbench.desktop.main.css` | 1,211,688 | VS Code 继承 |
| `resources/app/out/jetskiMain.tailwind.css` | 116,297 | **Antigravity 自有面板** |
| `resources/app/out/jetskiAgent/main.css` | 106,398 | **Antigravity 自有 Agent 面板** |
| `resources/app/out/tw-base.tailwind.css` | 17,007 | Tailwind base |
| `resources/app/out/vs/workbench/contrib/antigravitySounds/media/*.mp3` | 10,089 each | **Antigravity 自有音效** |
| `resources/app/product.json` | 44,611 | VS Code fork 清单 |
| `resources/app/package.json` | 9,591 | 应用入口 |
| `resources/app/ThirdPartyNotices.txt` | 2,215,412 | 第三方声明 |

**（d）contrib 目录清单（实测，最关键的「折叠」证据）**

`resources/app/out/vs/workbench/contrib/` 下仅有 9 个子目录：

```
antigravitySounds   ← Antigravity 自研
debug               ┐
extensions          │
externalTerminal    │ VS Code 原生模块
notebook            │
output              │
terminal            │
webview             │
welcomeGettingStarted ┘
```

> 推论：Antigravity **没有**为 AI 功能新造一整套一级导航模块，而是把 AI 能力挂进既有工作台，
> 视觉层级与信息层级保持一致 → 「简约、有主次、功能折叠」在代码层面的对应物。

**（e）音效系统**：媒体文件命名 `A0, A1, A2, A3, A4, A5, A6, A7, Ab1, Ab2, Ab3, Ab4, B0, B1, B2, B3, B4, B5, B6, B7, Bb0, Bb1, Bb2, Bb3, Bb4, C1, C3, ...`（等音高字母命名，钢琴/打击乐采样库）。每个 mp3 恒定 10,089 字节 → 极短提示音。
> 推论：Antigravity 把「完成 / 成功 / 失败 / 等待」等状态做成了**听觉事件**，而不是只靠视觉转圈。
> 这是 AI 工具「有质感」却常被忽略的一维。

**（f）主题令牌 / 动效 / 图标 / 排版阶梯 —— 未取得**

以下文件存在但**本轮未逐条提取**（原计划抓取，因时间与指令调整未执行）：
- `workbench.desktop.main.css`（1.2 MB）中的 CSS 变量组（中性色阶、圆角、阴影/描边）
- `jetskiMain.tailwind.css` / `tw-base.tailwind.css` 中的 Tailwind token（间距/字号/圆角/缓动）
- `workbench.desktop.main.js`（29,360,952 bytes）中的动画模块与 easing 命名
- codicon 图标字体的 TTF 度量与网格

> 诚实标注：**未取得**，不编造具体数值。

### 2.2 Qoder

**路径**：`C:\Users\jss18\AppData\Local\Programs\Qoder\`、`C:\Users\jss18\AppData\Local\QoderClientRs\`
（`QoderClientRs` 目录名暗示 Rust 客户端，可能是瘦客户端 + 远端渲染。）
本轮**未进入取证**：未提取其 CSS/主题/图标/动效。→ 主题令牌等**未取得**。

### 2.3 Trae

**路径**：`C:\Users\jss18\AppData\Local\Programs\Trae\`
本轮**未进入取证**：未判断是否 VS Code fork，未提取令牌。→ **未取得**。

### 2.4 Claude Code / Claude 桌面版

**路径**：
- 桌面/客户端数据：`C:\Users\jss18\AppData\Local\AnthropicClaude\`、`C:\Users\jss18\AppData\Local\Claude-3p\`
- CLI：`C:\Users\jss18\AppData\Local\claude-cli-nodejs\`
- 规则体系：`C:\Users\jss18\.claude\`（见 §3.1）

本轮**未提取**其 GUI 打包资源（Electron app.asar / 主题 CSS）→ Claude 桌面版视觉令牌**未取得**。
但**规则体系是本轮最有价值的本机证据**，见 §三。

### 2.5 CodeBuddy / Cursor / Windsurf / Kiro

- CodeBuddy：仅 `AppData\Local\CodeBuddyExtension\` 存在（扩展侧），IDE 主体未确认 → **部分取得**
- Cursor：仅 `AppData\Local\com.cursorpro.client\` 存在，IDE 主体与 `.mdc` rules 目录未确认 → **部分取得**
- Windsurf：**未取得**（未安装）
- Kiro：已安装但未取证 → **未取得**

---

## §三 skill / rules 生态（实际写出来的条目）

### 3.1 Claude Code 规则目录实际结构（实测）

`C:\Users\jss18\.claude\`：

```
.claude/
├── CLAUDE.md
├── settings.json
├── .bcai-claude-backup.json
├── .last-cleanup
├── commands/
│   ├── token-budget-guard.md
│   ├── session-handoff-compressor.md
│   ├── evidence-debug-loop.md
│   ├── context-map-navigator.md
│   ├── cli-output-filter.md
│   └── ap7000-low-token-bugfix.md
├── skills/
│   ├── session-handoff-compressor/SKILL.md
│   ├── evidence-debug-loop/SKILL.md
│   ├── hyperframes-registry/SKILL.md
│   ├── hyperframes/SKILL.md
│   ├── hyperframes-animation/SKILL.md
│   ├── hyperframes-creative/SKILL.md
│   ├── hyperframes-keyframes/SKILL.md
│   └── hyperframes-cli/SKILL.md
├── ide/            （多把 .lock）
└── projects/       （各项目 memory 目录）
```

> 结构观察（可直接抄进我们的 skill 体系）：
> **CLAUDE.md = 全局行为规则（短）**，**skills/ = 领域规范（按需加载）**，**commands/ = 手动触发的工作流**。
> 三层分离 = 「渐进式披露」的本机实物。

### 3.2 `~/.claude/CLAUDE.md`（全文 5 行，原文逐字）

文件：`C:\Users\jss18\.claude\CLAUDE.md`

```markdown
# Claude Defaults

Default to token-efficient work. Be concise, inspect narrow evidence first, avoid broad scans and long logs, verify before claiming completion, and use `claude-token-efficiency-master` plus narrower local skills when token cost, large context, debugging, or repo work matters.

User instructions override these defaults.
```

**可抄条目**：
- 「verify before claiming completion」（**未验证不得声称完成**）→ 直接可抄进我们的验收规范。
- 「User instructions override these defaults」（用户指令优先级最高）→ 可抄。
- 观察：CLAUDE.md **不写设计规范**，只写行为/成本纪律 → 设计规范应放 `skills/`，不放 CLAUDE.md。

### 3.3 `design-system` skill —— 本轮最硬的「设计规则」原文

文件：`C:\Users\jss18\.kun\skills\design-system\SKILL.md`（全文 38 行，已完整读取）
元数据：`id: design-system` / `name: Design system & craft` /
`description: Brand-grade visual craft for design work — design-system-first thinking and anti-AI-slop rules.`

**原文摘录（逐条，行号可点）**：

`SKILL.md:11-16` — 令牌优先

```
## 1. Design system is the source of truth
- Look for root `DESIGN.md` first. When it exists and validates, it is the canonical
  Google-compatible project theme shared by the canvas, HTML/SVG generation, and code implementation.
- Derive every visual decision from tokens (color, spacing scale, radius, type scale),
  not ad-hoc values. Keep them consistent across the whole artifact.
```

`SKILL.md:18-25` — 反 AI 味清单（**可直接整段抄进我们的「避免清单」**）

```
## 2. Avoid generic AI tells
These read as "AI made this" — do not ship them:
- Cream / sand / beige default backgrounds; default to a deliberate neutral that fits the brand.
- Purple→blue diagonal gradients as a hero default.
- Bounce / elastic / overshoot easing. Use calm, short, standard easing.
- Endlessly nested cards (a card inside a card inside a card).
- Low-contrast gray text on colored or tinted backgrounds.
- Emoji as iconography in a serious product.
```

`SKILL.md:27-33` — Craft baseline（**可直接抄进我们的「可执行规范」**）

```
## 3. Craft baseline
- **Contrast & a11y**: verify text contrast (WCAG AA); never rely on color alone;
  provide a `prefers-reduced-motion` fallback for any animation.
- **Type**: a real type scale (not two sizes); generous line-height for body; tighten headings.
- **Spacing**: one spacing scale, applied rhythmically; align to a grid; let content breathe.
- **Hierarchy**: one clear focal point per view; size/weight/color do the work, not borders everywhere.
- **Motion**: purposeful and subtle; entrance/feedback only; respect reduced-motion.
- **Responsive**: design mobile and desktop intentionally, not just a squished desktop.
```

`SKILL.md:9`（总纲）

```
Hold this bar on any visual work — HTML mockups, prototypes, real UI.
```

**可抄条目汇总表**：

| # | 原文条目（可抄） | 落到我们规范的哪一条 |
|---|---|---|
| 1 | 一切视觉决策来自 tokens（color / spacing scale / radius / type scale），禁止 ad-hoc 值 | §五-1 |
| 2 | 一套 spacing scale，节奏化，对齐网格 | §五-2 |
| 3 | 一屏一个焦点；靠 size/weight/color 分级，不要到处描边 | §五-3 |
| 4 | 真实排版阶梯（不是两级字号）；正文行高松、标题行高紧 | §五-4 |
| 5 | 禁止 bounce / elastic / overshoot；用平静、短、标准缓动 | §五-5 |
| 6 | 动效只用于 entrance / feedback；必须尊重 reduced-motion | §五-5 / §五-6 |
| 7 | WCAG AA 对比度；不得单靠颜色传达含义 | §五-7 |
| 8 | 避免卡片套卡片 | §六 |
| 9 | 避免奶油/沙/米色默认背景 | §六 |
| 10 | 避免紫→蓝对角渐变作为 hero | §六 |
| 11 | 避免染色背景上的低对比灰字 | §六 / §五-7 |
| 12 | 正式产品不以 emoji 当图标 | §六 / §五-9 |
| 13 | 移动端要「有意设计」，不是桌面端压缩 | §五-10 |
| 14 | 迭代时只改被要求的部分，其余保持稳定 | 流程纪律 |
| 15 | `DESIGN.md` 为唯一主题真源，禁止另造「风格指南」产物 | 流程纪律（§五-1 载体） |
| 16 | 优先系统字体或单一精选 web 字体 | §五-4 |
| 17 | 产物自包含可直接运行 | 交付纪律 |
| 18 | 尊重 `prefers-reduced-motion` 回退 | §五-6 |
| 19 | 每个视觉产物都用「hold this bar」同一把尺 | 总纲 |

### 3.4 本机 hyperframes 系列的 design / motion 参考文件（存在，本轮未逐条提取）

`C:\Users\jss18\.claude\skills\hyperframes-creative\references\` 下已确认存在：

```
design-spec.md        design-adherence.md     design-picker.md
typography.md         motion-principles.md    house-style.md
visual-styles.md      composition-patterns.md data-in-motion.md
story-spine.md        narration.md            prompt-expansion.md
audio-reactive.md     frame-presets.md
```
`hyperframes-creative\palettes\`：`warm-editorial.md` `pastel-soft.md` `neon-electric.md`
`nature-earth.md` `monochrome.md` `jewel-rich.md` `dark-premium.md`
`clean-corporate.md` `bold-energetic.md`
`hyperframes-animation\transitions\`：`TRANSITION-REGISTRY.md` `css-scale.md` `css-radial.md`
`css-push.md` `css-other.md` `css-mechanical.md` `css-light.md` `css-grid.md`
`css-distortion.md` `css-dissolve.md` `css-destruction.md` `css-cover.md` `css-blur.md`
`css-3d.md` `catalog.md` `overview.md`
`hyperframes-animation\references\`（节选）：`gsap-timeline-and-labels.md` `gsap-easing-and-stagger.md`
`css-animations.md` `animejs.md` `waapi.md`
`hyperframes-animation\rules\`（33 条命名动效规则，如 `spring-pop-entrance.md`、
`press-release-spring.md`、`nudge-curve.md`、`cursor-click-ripple.md`、`theme-crossfade-morph.md` 等）

> 价值判断：这是一套**「动效规则库」而非「动效词汇表」**——每个动效有独立规则文件与
> transition registry。**这正是我们要的「一个家族而非各处各写」的工程形态**：
> 动效被命名、被归类（scale/radial/push/mechanical/light/grid/distortion/dissolve/destruction/cover/blur/3d）、
> 被参数化，而不是散落在各页面 CSS 里。
> **本轮内容未逐条提取 → 标「未取得（文件已定位）」**，建议下一轮优先读 `TRANSITION-REGISTRY.md`
> 与 `css-scale.md`，可直接产出 §五-5 的曲线/时长参数表。

### 3.5 Cursor `.mdc` / Windsurf rules / Antigravity workspace rules

**未取得**（本轮未确认其规则目录存在，且网络抓取已停止）。
已知线索：Cursor 用户数据在 `C:\Users\jss18\AppData\Local\com.cursorpro.client\`，
但未进入核对 `.cursor/rules/*.mdc` 或 `%USERPROFILE%\.cursor\`。

### 3.6 GitHub skill 生态（`anthropics/skills`、`obra/superpowers`、`wshobson/agents`）

**未取得**（网络抓取已停止）。已知本机 `~/.claude/skills/` 与 `~/.kun/skills/` 是这些体系的本地安装/衍生，
本机可作为替代证据源；`obra/superpowers` 对应本机 `superpowers:*` skill 集（本机 `~/.minimax/skills` 目录可见），
其中 `superpowers:writing-skills`、`superpowers:brainstorming` 为**规则写作方法论**，
但其内容本轮未读取 → **未取得**。

---

## §四 官方设计文档摘录

**未取得。** 本轮按指令**停止一切网络抓取**，以下官方文档均未访问：

- Antigravity 官方文档（`antigravity.google` / 官方博客）：未取得
- Claude Code Skills 官方文档（`docs.anthropic.com`）：未取得
- Cursor Rules 官方文档：未取得
- Windsurf Rules 官方文档：未取得

> 替代路径已记录，下一轮可直接执行（均不需 `api.github.com`）：
> `https://raw.githubusercontent.com/<repo>/<branch>/<path>`、
> `https://cdn.jsdelivr.net/gh/<repo>@<tag>/<path>`。

---

## §五 ⭐ 质感 = 10 条可执行规范

> 每条格式：**规则 / 数值或参数 / 出处 / 我们的落地方式**
> 数值栏中，标 `[原样]` 的直接来自本机文件原文；标 `[提案]` 的为本轮基于原文推导、待设计评审确认。

### 1. 一切视觉值来自令牌，禁止 ad-hoc 值

- **规则**：颜色、间距、圆角、字号、时长、缓动**全部**由单一令牌表提供；代码里出现字面量色值/字号/间距即视为缺陷。
- **数值/参数**：4 组 token —
  `color`（中性 ≥8 阶 + 强调 1 + 语义 4）、`spacing`（4pt base：2/4/8/12/16/20/24/32/40/48/64）、
  `radius`（4/6/10/14/20 + continuous 档）、`type`（6 级）+ `motion`（时长 4 档 + 曲线 3 条）。
- **出处**：`SKILL.md:16`「Derive every visual decision from tokens (color, spacing scale, radius, type scale), not ad-hoc values.」；`SKILL.md:14`「Never draw a separate HTML, SVG, or freeform "style guide" artifact.」→ 单一真源。
- **我们的落地**：Swift 侧 `DesignTokens`（enum + static let）单文件；仓库根 `DESIGN.md` 为唯一真源文档；CI 加一条 grep 规则拦截裸 hex / 裸 point 字号。

### 2. 一套间距体系，4pt base，节奏化铺开

- **规则**：全 App 只允许一套 spacing scale；间距必须是 scale 上的值，禁止任意点数。
- **数值/参数**：`[提案]` 4/8/12/16/20/24/32/40/48/64；组件内边距用 12/16，组件间距用 8/16，区块间距用 24/32；行高 8pt 网格。
- **出处**：`SKILL.md:30`「one spacing scale, applied rhythmically; align to a grid; let content breathe.」
- **我们的落地**：`Spacing` 枚举（`xs=4 … xxxl=64`）；新增间距值必须先加枚举再用；lint 拦截。

### 3. 一屏一个焦点；靠 size/weight/color 分级，不要到处描边

- **规则**：每屏/每卡片只允许 1 个 primary 动作；次级动作降级为文字按钮；分隔不靠描边。
- **数值/参数**：`[提案]` 每屏 primary action ≤ 1；accent 色元素占比 ≤ 5% 视口面积；描边（border）使用率 ≤ 每屏 1 处分隔手法。
- **出处**：`SKILL.md:31`「one clear focal point per view; size/weight/color do the work, not borders everywhere.」
- **我们的落地**：视图级 `PrimaryAction` 唯一性约束（编译期断言）；默认按钮样式为「无边框填充 / 无边框文字」二选一。

### 4. 排版：一套真阶梯，不是两级字号

- **规则**：≥5 级字号阶梯；正文行高松、标题行高紧；数字用等宽数字。
- **数值/参数**：`[提案]` 11 / 13 / 15 / 17 / 22 / 28 pt（对应 caption/footnote/body/callout/title/largeTitle）；
  标题行高 1.2，正文 1.4–1.5；段间距 = 行高 × 1 或 8pt 网格；数字用 `.monospacedDigit()`。
- **出处**：`SKILL.md:29`「a real type scale (not two sizes); generous line-height for body; tighten headings.」；`SKILL.md:37`「Prefer system fonts or a single well-chosen web font.」
- **我们的落地**：iOS 字体样式统一走 `AppFont`（SwiftUI `.font(.system(size:weight:design:))`），Dynamic Type 全档截图回归。

### 5. 动效：一个家族，冷静短促，禁止回弹

- **规则**：全 App 只有一组曲线 + 4 档时长；动效只用于「入场」和「反馈」，不做装饰性循环。
- **数值/参数**：`[提案]`
  曲线族：`easeOut = cubic-bezier(0.16, 1, 0.3, 1)`（入场）、`easeInOut = cubic-bezier(0.4, 0, 0.2, 1)`（状态变化/位移）、
  `standard = cubic-bezier(0.2, 0, 0, 1)`（通用）；
  时长档：`micro 120ms`（按钮反馈、hover）、`small 180ms`（弹出/折叠）、`medium 240ms`（页面转场）、`large 320ms`（模态/全屏）；
  硬约束：任何 spring 的 `overshoot ≤ 1.0`（**禁止 bounce/elastic**）；位移幅度 ≤ 24pt；缩放 ≤ 1.02。
- **出处**：`SKILL.md:22`「Bounce / elastic / overshoot easing. Use calm, short, standard easing.」；`SKILL.md:32`「Motion: purposeful and subtle; entrance/feedback only; respect reduced-motion.」
- **我们的落地**：Swift 侧 `Motion.swift` 单一入口（`Motion.enter / .small / .medium / .large`），**禁止各处直写 `.animation(_:)`**；新增曲线必须先加进 `Motion.swift`。

### 6. 必须有 Reduce Motion 回退（iOS 对应 `prefers-reduced-motion`）

- **规则**：开启「减弱动态效果」后，所有位移/缩放动画降级为不透明度过渡，自动循环动效停止。
- **数值/参数**：`[提案]` 降级为 `opacity 0→1 / 150ms`；缩放与位移全部置零；无限循环动效（如呼吸光晕）直接停。
- **出处**：`SKILL.md:28`「provide a `prefers-reduced-motion` fallback for any animation.」；`SKILL.md:32`「respect reduced-motion.」
- **我们的落地**：`@Environment(\.accessibilityReduceMotion)` **只在 `Motion.swift` 内读取**，视图层不得自行判断。

### 7. 对比度达 AA，语义不靠颜色单独承载

- **规则**：文本对比度 ≥ WCAG AA；任何用颜色表达的状态都必须同时有形状/图标/文字。
- **数值/参数**：`[提案]` 正文 ≥ 4.5:1；≥18pt（或 ≥14pt bold）大字 ≥ 3:1；非文本控件/图标 ≥ 3:1；状态色（success/warning/error）必配图标 + 文案。
- **出处**：`SKILL.md:28`「verify text contrast (WCAG AA); never rely on color alone.」；`SKILL.md:24`「Low-contrast gray text on colored or tinted backgrounds.」
- **我们的落地**：令牌表内固化每组前景/背景配对的实测比值；加一个对比度断言测试；状态组件强制 `icon + text` 结构体。

### 8. 色彩层级：中性阶足够深，强调色唯一，分隔只用一种手法

- **规则**：中性色阶 ≥8 级；全局唯一强调色；分隔**全局只选一种手法**（描边或背景色差，二选一）。
- **数值/参数**：`[提案]` 中性 8 阶（bg / surface / elevated / separator / primaryText / secondaryText / tertiaryText / quaternaryText）；
  强调色 1（品牌）；语义 4（success / warning / error / info）；分隔统一用 **1px hairline，透明度 8%**（或统一用背景色差，二者不可混用）。
- **出处**：`SKILL.md:16`（color token）、`SKILL.md:20`「default to a deliberate neutral that fits the brand」、`SKILL.md:31`（不要到处描边）。
- **我们的落地**：`SeparatorStyle` 单一枚举（`.hairline` 或 `.surfaceContrast`），全项目只允许一种；强调色使用走 `Accent.use()` 限流函数。

### 9. 图标与形状：单一网格、单一圆角族、连续曲率

- **规则**：图标统一 24×24 pt 网格、描边 1.5–2pt、圆端点（round cap / round join）；圆角只 4 档且相邻嵌套时连续曲率。
- **数值/参数**：`[提案]` 24×24 pt 网格；描边 1.75pt（光学对齐到 2px）；端点/拐角 round；圆角 4 / 8 / 12 / 16（`[提案]` 连续曲率：外圆角 = 内圆角 + 间距）；相邻圆角差 ≤ 4pt 视为同一族。
- **出处**：`SKILL.md:16`（radius token）、`SKILL.md:25`「Emoji as iconography in a serious product.」（反向条目）；圆角连续曲率参考 Apple 连续曲率惯例（本轮无本机取证，见 §七）。
- **我们的落地**：优先 SF Symbols；自绘图标统一 24 网格模板 + 描边模板（Illustrator/Figma 约束）；建立 `IconSpec` 校验（尺寸/描边/端点）。

### 10. 状态完整性 + 无未接线元素 + 首帧预算 + AI 流式排版

- **规则**：加载 / 空 / 错误 / 离线 / 权限拒绝 / 首次使用 **六态各自独立**（图标 + 文案 + 恢复动作）；**任何可见可点元素必须有实现**，未实现就隐藏；首帧与可交互有预算；流式输出不引起重排。
- **数值/参数**：`[提案]`
  - 六态枚举：`loading / empty / error / offline / permissionDenied / firstRun`，每态必须提供「恢复动作」按钮（错误/离线/权限拒绝/首次使用为**必填**）
  - 首帧 ≤ 1.0s；Time-to-Interactive ≤ 2.0s（本地预渲染 + 骨架，不阻塞交互）
  - 流式输出：到达即渲染，不等批；行尾光标 1.1s 闪烁；**末行预留空间**防跳动；工具调用卡片状态序列固定 `pending → running → success | error`（图标+文案，不靠颜色单独区分）
  - 未接线元素：可见可点元素 100% 有 action（灰盒测试断言）
- **出处**：`SKILL.md:32`（motion 只用于 entrance/feedback）；§2.1(d) Antigravity `contrib` 仅 1 个自研模块（**折叠而非堆叠**）；`SKILL.md:31`（层级唯一焦点）。
- **我们的落地**：
  - Swift 侧 `ChatViewState` 枚举 6 态，视图按态 switch，不允许空实现兜底；
  - 「未接线按钮」检查：CI/UI 测试遍历可点击元素，断言均有 target/action；
  - 「折叠」策略：AI 能力不新增一级导航，挂在既有入口下（对照 Antigravity contrib 证据）。

---

## §六 反面清单（这些工具**没有**做、但常见的「廉价感」做法）

以下 6 条直接来自本机 `design-system` skill 的「Avoid generic AI tells」，其原话是
「These read as "AI made this" — do not ship them」（`SKILL.md:19`）：

| # | 廉价感做法 | 原话出处 | 我们的拦截方式 |
|---|---|---|---|
| 1 | 奶油 / 沙 / 米色默认背景 | `SKILL.md:20` | 令牌表禁用色；新项目背景必须从品牌中性色里选，且写明理由 |
| 2 | 紫→蓝对角渐变当 hero | `SKILL.md:21` | 渐变仅允许用于「同一色相的明度渐变」；禁止跨色相对角渐变 |
| 3 | Bounce / Elastic / Overshoot 回弹 | `SKILL.md:22` | `Motion.swift` 只暴露 3 条曲线，无弹性；spring overshoot ≤ 1.0 |
| 4 | 卡片套卡片套卡片 | `SKILL.md:23` | 卡片嵌套层数 ≤ 1；列表项用 `separator` 而非嵌套卡片 |
| 5 | 染色背景上的低对比灰字 | `SKILL.md:24` | 对比度断言 ≥ 4.5:1 |
| 6 | 正式产品用 emoji 当图标 | `SKILL.md:25` | 图标只用 SF Symbols / 自绘 SVG；emoji 出现即视为缺陷 |

补充（来自 Antigravity 本机取证的结构性观察，标 `[判断]`）：

7. **为每个功能新造一级入口**（堆叠而非折叠）——Antigravity `contrib/` 只有 1 个自研模块，其余全继承。
8. **同时混用描边 + 阴影 + 背景色差三种分隔**——本轮未见；统一为一种（§五-8）。
9. **流式文本每 token 触发整屏重排**——本轮未取证，但与「克制」原则直接冲突（§五-10）。

---

## §七 未取得与风险

### 7.1 未取得清单

| 项 | 状态 | 目标路径 / URL | 阻塞原因 |
|---|---|---|---|
| Antigravity CSS 变量原值（中性阶/圆角/阴影/描边） | **未取得** | `C:\Users\jss18\AppData\Local\Programs\Antigravity IDE\resources\app\out\vs\workbench\workbench.desktop.main.css`（1,211,688 B） | 本轮时间预算内未执行 grep 提取 |
| Antigravity 自有面板令牌 | **未取得** | `…\resources\app\out\jetskiMain.tailwind.css`（116,297 B）、`tw-base.tailwind.css`（17,007 B） | 同上 |
| Antigravity 动效曲线/时长/缓动命名 | **未取得** | `…\out\vs\workbench\workbench.desktop.main.js`（29,360,952 B） | 同上 |
| codicon 图标网格 / 笔触 / 端点 | **未取得** | codicon 字体资源（未定位具体文件） | 同上 |
| Antigravity 排版阶梯 | **未取得** | 同 workbench CSS | 同上 |
| Antigravity 空态/加载态/错误态设计系统文档 | **未取得（未发现随包发布的设计系统文档）** | `resources/app/out/**` | 目录枚举未见设计系统文档 |
| Qoder 主题/令牌/图标/动效 | **未取得** | `C:\Users\jss18\AppData\Local\Programs\Qoder\`、`AppData\Local\QoderClientRs\` | 本轮未进入 |
| Trae 是否 VS Code fork / 令牌 | **未取得** | `C:\Users\jss18\AppData\Local\Programs\Trae\` | 本轮未进入 |
| Claude 桌面版 GUI 打包资源 / 主题 | **未取得** | `AppData\Local\AnthropicClaude\`、`Claude-3p\` | 本轮未进入 |
| Claude Code skills 官方文档 | **未取得** | `docs.anthropic.com` | **网络抓取按指令停止** |
| Antigravity 官方设计文档 | **未取得** | `antigravity.google` / 官方博客 | 同上 |
| Cursor / Windsurf rules 官方文档 | **未取得** | `docs.cursor.com` / `docs.windsurf.com` | 同上 |
| Cursor `.mdc` / Windsurf rules / Antigravity workspace rules 实际文件 | **未取得** | `%USERPROFILE%\.cursor\rules\*.mdc` 等 | 未确认存在，本轮未查 |
| GitHub `anthropics/skills`、`obra/superpowers`、`wshobson/agents` 的 UI/UX skill 条目 | **未取得** | `raw.githubusercontent.com/...` / `cdn.jsdelivr.net/gh/...` | 同上（`api.github.com` 配额已耗尽，不可用） |
| hyperframes 设计/动效参考文件的**内容** | **文件已定位，内容未取得** | `~/.claude/skills/hyperframes-creative/references/*.md`、`~/.claude/skills/hyperframes-animation/transitions/*` | 本轮仅枚举文件名 |
| Apple 侧（iOS/SwiftUI）质感一手取证 | **未取得** | — | 本机无 Apple 原生 AI 工具可取证；相关条目为 `[提案]` |

### 7.2 风险与偏差

1. **证据偏科**：本轮硬证据集中在 Antigravity（VS Code fork）与 2 个 skill 文件；Cursor/Windsurf/Trae/Qoder/CodeBuddy 仅有「装没装」级别信息，不能据此评价其审美。
2. **VS Code fork ≠ 可搬运**：VS Code 令牌服务桌面编辑器（Electron + 高密度信息），直接照搬到 iOS 陪伴机器人会得到「密、满、工业感」，与「简约、有主次」目标相反。**可搬运的是方法（令牌化、单曲线家族、状态完备），不是数值。**
3. **§五中 `[提案]` 数值未经用户/设计评审确认**，落地前需做一轮 iOS 端对照（HIG + 现有产品视觉）。
4. **圆角连续曲率、haptic 种类与力度、图标描边 1.75pt** 属本轮无一手证据的推导项，需补 Apple 一手文档或真机 A/B。
5. **「触感/haptic」尚未取证**：Antigravity 的音效只证明「多模态反馈有效」，不能推出具体 haptic 类型（selection / impact / notification）与力度。§五暂未把 haptic 单列成条，建议下一轮补。
6. **首帧 ≤1.0s / TTI ≤2.0s** 属 `[提案]`，无本机或官方来源。

---

## 文末自查

| § | 结论要点 | 来源类别 |
|---|---|---|
| §一.1 | Antigravity 是 VS Code fork，ideVersion 2.5.5 | [本机实测] `resources/app/product.json` |
| §一.2 | 自研 contrib 仅 antigravitySounds，其余继承 | [本机实测] `contrib/` 目录枚举 |
| §一.3 | 音效采样 A0–Bb4，10,089 B/个 | [本机实测] `antigravitySounds/media/*.mp3` |
| §一.4 / §三.3 | token-only / 一套 spacing / 一屏一焦点 / 禁 bounce / 禁嵌套卡片 / 禁 emoji / reduced-motion | [本机文件已读] `~/.kun/skills/design-system/SKILL.md` |
| §二 表 | 各工具装没装 / 装在哪 | [本机实测] `Get-ChildItem` / `glob` 枚举 |
| §二.1(f) | Antigravity 具体 CSS 变量/曲线/图标度量 | [未取得] |
| §三.1 | `~/.claude/` 三层结构（CLAUDE.md / skills / commands） | [本机实测] 目录枚举 |
| §三.2 | 「verify before claiming completion」等 | [本机文件已读] `~/.claude/CLAUDE.md:3-5` |
| §三.4 | hyperframes 设计/动效参考文件清单与「规则库而非词汇表」判断 | [本机实测] 文件名枚举 + [判断]（内容未取得） |
| §四 | 官方文档摘录 | [未取得] 网络抓取停止 |
| §五.1–§五.9 数值 | token 集、spacing、焦点、阶梯、曲线、reduce motion、对比度、色阶、图标 | [提案] + 规则出处为 [本机文件已读] `SKILL.md` |
| §五.10 数值 | 六态、1.0s/2.0s、流式排版 | [提案]；结构依据 [本机实测] Antigravity contrib 折叠证据 |
| §六.1–§六.6 | 6 条廉价感做法 | [本机文件已读] `SKILL.md:19-25`（原文逐条） |
| §六.7–§六.9 | 折叠优先、分隔单一、流式不重排 | [判断] |
| §七 | 全部未取得项 | [未取得] |

**取证纪律自检**：本文件所有路径、文件名、大小、版本号、JSON 字段、原文摘录均可回溯到上述本地路径；
**未取得的项目一律写「未取得」，无编造的 CSS 值、star 数、版本号或目录名**（Antigravity CSS 变量与
动效曲线、haptic 参数、官方文档内容均未编造）。
