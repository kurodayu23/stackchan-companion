# StackChan · DESIGN

> 视觉系统层 · 平台无关底线见 `docs/research/19-设计底线-平台无关设计Floor规范.md`（Floor F1–F46 / Reflex R1–R20）
> 状态：2026-10-23 · 产品真相层见 `PRODUCT.md`（本文不重复其内容）

本文只回答三件事：界面长什么样、凭什么这么长、什么是绝对禁止的。
数值一律标注出处文档与章节；**未实测的数值一律不写**。

---

## 0. 一句话设计主张

> **屏幕上唯一会动、唯一被注视的东西是小栈的脸；其他一切都是背景。**

出处：19 号 Floor §5「镜像测试」指定的唯一差异化决策；11 号 §6 Apple Fitness「一个超级视觉核心」。

---

## 1. 设计原则

| # | 原则 | 可判定判据 | 出处 |
|---|---|---|---|
| P1 | **一个焦点，动作唯一** | 一屏 1 个主按钮 + ≤2 次级；首页可点元素 ≤4；只承载「标题 + 一句话 + 一个操作」 | 00 §2.4；02 §6.1；F19 |
| P2 | **主次靠明度两档，不靠色相多** | 除唯一强调色外明度层级 ≤2 档；同屏彩色元素 ≤3；同屏功能强调色 ≤1 | F20；06 §3.4；02 禁止项 25 |
| P3 | **品牌色只做点，不铺面** | 强调色只在 ① 主要动作 ② 状态指示器；iOS 内容区 ≤5% 面积，设备端单卡 ≤8% | HIG Branding B1–B4（20 §2.1）；06 §3.5 |
| P4 | **角色永远在场** | 小栈的脸/身体占首屏视觉面积 ≥40%；任何页面不得人为遮挡 | 02 L8；08 §7.1 |
| P5 | **层级靠明度差 + 1pt 描边，不靠重阴影** | 阴影只作辅助；禁单层大模糊影；两层表面明度差 ≥1.15:1 | 02 S2；06 §4.2 修订表 12 |
| P6 | **陪伴不是考核** | 无「今日完成 N 次」类计数、无红叉、无进度环、无运营 Banner | 00 宪法 17；11 §6.3、§8.2 |
| P7 | **AI 内部状态不用文字；错误必须有文字** | 「正在听/在想」零文字零波形；错误提示与重要确认必须有文字并说明怎么修 | 00 宪法 16′；20 §5.1 |
| P8 | **手势是加速器，不是入口** | 所有关键操作有可见入口，边缘手势只作快捷方式 | 02 S10 |

---

## 2. 色彩

### 2.1 iOS：系统语义色 + 唯一暖色

骨架用系统语义色，**不自绘表面色**（00 §2.2）。

| 角色 | 取值 | 出处 |
|---|---|---|
| 画布 | `systemBackground` | 00 §2.2 |
| 表面 / 次级表面 | `secondarySystemGroupedBackground` / `tertiarySystemGroupedBackground` | 00 §2.2；06 §6.1 |
| 主文字 / 次文字 / 分割线 | `label` / `secondaryLabel` / `separator` | 00 §2.2、§3.3-4（次文字不固定 `#7B626C`） |
| **唯一品牌暖色** | 浅 `#B33A55` / 深 `#E8638C` | 00 §3.3、§3.1 实测 |

- 不硬编码系统色值；自定义色给 **浅/深 × 默认/高对比 4 个变体**（00 宪法 9–10）。
- 暖色**不铺控件**，只做主动作与状态点。HIG Branding 原文："Minimize its use on controls and instead use it intentionally for primary actions or status indicators."（20 §2.1 B2/B3）
- 暖色**优先放进内容层**。HIG 原文："consider moving it into the content layer, where it scrolls beneath Liquid Glass controls and gets picked up dynamically."（20 §2.1 B4）→ 落到**小栈的脸**（腮红/情绪色），不落到 Tab Bar、开关、按钮底。
- **`.tint` 是材质属性，不是控件底色**：品牌暖色落在玻璃上用 `glassEffect(.regular.tint(warmColor))`（SwiftUI API 见 §7），**不用品牌色去给按钮、开关、列表行染色**——那才是"铺控件"。主动作按钮用 accent 填充 + 白字（对比度见 §2.4），属 HIG 允许的 primary actions 一类，与 tint 分开计。
- 「iOS 端不用系统默认蓝」**已被推翻**：系统语义色是骨架，暖色只作品牌 `.tint`（00 §8.2）。

### 2.2 设备端 320×240：保留深色

| 令牌 | 值 | 出处 |
|---|---|---|
| 画布 / 页面底 | `#080A0F` / `#0E1117` | 02 §1.3（prototype.html:8 / :270,313） |
| 卡面 / 边 | `#171B23` / `#2A303B` | 02 §1.3 |
| 标题 / 描述 / 设置值 | `#F7F8FA` / `#9299A6` / `#9FA9B8` | 02 §1.3 |
| 按下态 / 边框加强 | `#1B2029` / `#343C48` | 02 §1.3 |
| 页点 / 激活页点 | `#3D4450` / `#DCE1E8` | 02 §1.3 |
| 状态色（在线/工作中） | `#00D2FF` | 02 §1.3；00 §2.2 |

- **青 `#00D2FF` 降级为状态色，不当主色**：浅底实测仅 1.74:1（00 §3.1）；青色是技术色，与"陪伴"气质不符（00 §2.2）。
- 禁纯黑/纯灰，颜色一律带一点色相（F37）；`#080A0F` 满足。
- 设备端**不铺品牌色**，状态灯用状态色（19 F23 设备端列）。
- 8 组功能色只用于该功能自己那一屏、同屏 ≤1；实测对其 tint 6.34:1–8.46:1、对底色 `#0E1117` 8.28:1–11.42:1（06 §7.1）。

### 2.3 语义色与状态色

| 语义 | 浅色 | 实测（对 canvas） | 深色 | 实测（对 canvas） |
|---|---|---|---|---|
| success | `#28694B` | 5.11:1 | `#5BD39B` | 10.11:1 |
| warning 文字 / 填充 | `#805900` / `#F5C542` | 4.91:1 / 压深字 8.47:1 | `#F0C674` | 11.73:1 |
| danger | `#B62A43` | 4.83:1 | `#FF7A85` | 7.54:1 |
| 在线 / 工作中 | — | — | `#00D2FF` | 深 surface 9.45:1 |

出处：06 §7.1（实测），青值出自 00 §3.1。旧契约三处**不达标**已弃用：success `#4FA77A` 2.84:1、warning `#FFD078` 1.39:1、danger `#D6455E` 4.16:1（06 §3.6、§7.1）。每个状态色必须**同时配文字或形状**（F3）。

### 2.4 对比度实测结论

WCAG 2.2 相对亮度公式（sRGB→linear），脚本 `D:\AP\AP7000\ai-workspace\stackchan-research\_contrast.py`；00 与 06 两套独立脚本复算，结论一致（00 §3.4）。

| 配对 | 实测 | 阈值 | 出处 |
|---|---|---|---|
| 白字 on `#B33A55`（主按钮） | **5.75** | 4.5 ✅ | 00 §3.2 |
| 白字 on `#D94F78`（旧契约） | **3.93** | 4.5 ❌ | 00 §3.2 |
| `#B33A55` on `#FFFFFF` | **5.75** | 4.5 ✅ | 00 §3.1 |
| `#E8638C` on `#1C1C1E` | **5.34** | 4.5 ✅ | 00 §3.1 |
| `#00D2FF` on `#1C1C1E` | 9.45 | 3:1 ✅ | 00 §3.1 |
| `#00D2FF` on `#FFFFFF` | **1.74** | 不可读 ❌ | 00 §3.1 |
| `#4FA77A` on `#FFFAF7` | **2.84** | ❌ | 00 §3.1 |
| `#FFD078` on `#FFFAF7` | **1.39** | ❌ | 00 §3.5 |

**阈值**：正文 ≥4.5:1；大字（≥18pt 或 ≥14pt bold）≥3:1；非文字 UI 组件 ≥3:1（06 §3.2）。陪伴型产品**不放宽**：想更柔就降饱和度，不降明度差（06 §3.2）。

> ⚠️ **未实测**：上表深色列底色是 `#1C1C1E` / `#000000`，设备端实际画布是 `#080A0F`，06 §7.1 用 `#1C212B`。**实际 token 与实测底色未对齐，接入后需用同一脚本重算。**

---

## 3. 排版

### 3.1 iOS（SF Pro / Dynamic Type，Large 默认档）

| 令牌 | 字号 | 行高 | 字重 | tracking | 用途 |
|---|---|---|---|---|---|
| largeTitle | 34 | 41 | Regular/Bold | +0.40 | 全屏大标题 |
| title1 | 28 | 34 | Regular/Bold | +0.38 | 模态/次级页标题 |
| title2 | 22 | 28 | Regular/Bold | −0.26 | 区块主标题、卡片标题 |
| title3 | 20 | 25 | Regular/Semibold | −0.45 | 列表分组标题 |
| headline | 17 | 22 | Semibold | −0.43 | 列表主文、按钮文字 |
| body | 17 | 22 | Regular | −0.43 | 正文（系统默认字号） |
| subhead | 15 | 20 | Regular | −0.23 | 卡片描述 |
| footnote | 13 | 18 | Regular | −0.08 | 辅助说明、状态 |
| caption1 | 12 | 16 | Regular | 0 | 标签、时间戳 |
| caption2 | 11 | 13 | Regular | +0.06 | **下限** |

出处：06 §2.1（引 HIG typography.md Specifications）、§7.2。

- **字重只用 4 档** Regular / Medium / Semibold / Bold，禁 Light / Thin / Ultralight（00 宪法 2；F7）。
- **字体家族 ≤2**：SF Pro（正文/说明）+ SF Pro Rounded（**仅标题与次标题**）。HIG Branding 原文："use a custom font for headlines and subheadings while using system fonts for body copy and captions"（20 §2.4）。
- **最小字号 11pt**（00 宪法 1）；**输入框 ≥16pt**（F35，nongeneric Responsive Breakage：<16px 触发 iOS Safari 自动放大）。
- tracking：**12pt 是零点**，越小越松、越大越紧，24pt 以上转正（06 §2.2）；自绘稿必须手动补 tracking，否则与真机不一致。
- **中文行高 ≥ 字号 × 1.5**（下限），长段引语 ×1.65，标题 ×1.25–1.35（clreq → 06 §2.5；比英文值大 15%–25%）。
- Dynamic Type：能用系统 text style 就不自定义字号；层级在放大后必须保持（06 §2.1）。

### 3.2 设备端 320×240（px）

| 角色 | 字号 | 行高 | 用途 |
|---|---|---|---|
| display | 28 | 34 | 计时数字（**唯一允许的大字，≤2 处/屏**） |
| title | 21 | 28 | 页面标题 |
| cardTitle | 18 | 24 | 卡片标题、导航标题 |
| quote | 15 | 22 | 引语、重点正文 |
| body | 13 | 19 | 正文 |
| description | 12 | 17 | 描述、次要文案 |
| meta | 11 | 15 | 元数据（**绝对下限**） |
| <11 | — | — | **禁止** |

出处：06 §2.3、§7.2（推导含未验证假设：屏幕 2.0 吋对角 → PPI ≈ 200）。旧原型 9 / 10 / 10.5 px 低于下限，须提至 11 / 11–12 / 12 px（06 §2.3 体检结论）。

---

## 4. 间距与栅格

**iOS**：档位 `4 / 8 / 12 / 16 / 20 / 24 / 32`；页面左右边距 20pt；卡片间距 16pt；卡片内边距 20pt；列表行高 ≥56pt、图标行 ≥60pt；内容最大宽 480pt 居中（02 L4/L7、§8.1；06 §2.7）。

**设备端**：档位 `4 / 8 / 12 / 16 / 24`（02 §1.2）；8 栏栅格 `边距12 + 8×30 + 7×8 + 边距12 = 320`；卡片内边距 20–24px；**不设多列网格 UI**，栅格只用于内部对齐（06 §2.7）。

共同规则（06 §2.6；HIG layout.md "Use consistent spacing."）：相邻间距比 ≤2:1，主链 `4→8→16→32`，插入档 `12 / 20 / 24` 不得打断主链；段间距 > 字间距，段后 ≥ 行高 × 0.5；容器内边距 ≥ 容器内最大字号 × 0.75。

---

## 5. 形状与圆角

| 令牌 | 设备 (px) | iOS (pt) | 用途 |
|---|---|---|---|
| radius.xs / .sm | 4 / 8 | 4 / 8 | 小图标底、页点 / 图标容器、小按钮 |
| radius.control | 12 | 12 | 按钮、输入框 |
| radius.tile | 16 | 16 | 功能 tile、列表分组 |
| radius.card | 20 | 20 | 卡片、主卡 |
| radius.sheet | 24 | 24 | 底部抽屉、对话框 |
| radius.full | 999 | 999 | 胶囊、头像、状态点 |

出处：06 §7.4（M3 shape scale 为外部锚点）。

- iOS 圆角用**连续曲率**；模态浮层用 `ContainerRelativeShape` 与容器圆角同心对齐，不硬编码（00 §4.6）。
- 同心规则：外圆角 = 内圆角 + 内边距（06 §7.4）；公式 `radius ≈ min(容器短边 × 0.10, 20 pt)`（06 §4.1）。
- 卡片圆角 20px（修订自 24px：24/156 = 15% 偏高，显玩具感）——06 §4.2 修订表 11。
- **禁**：24–28px 大圆角 + 999px 胶囊 + 弥散阴影堆叠 + glow 光晕四件套（00 §2.5）。

---

## 6. 图标

- iOS 一律 **SF Symbols**，不画不描 emoji（00 宪法 4；F16）。
- 自绘图标全局同规格：尺寸 / 细节级别 / 描边粗细 / 透视一致（20 §3，HIG Icons）。
- **系统组件里的图标不做选中态**，系统自动处理（20 §3）→ 2 个 Tab 图标不必画两套。
- 设备端线性图标：`viewBox 0 0 64 64`、48×48、`stroke-width 1.7`、round cap/join、`fill:none`；容器 92×92 圆角 27（02 §3.2）。
- App 图标：glyph 占容器 45%–60%，四周留 20%–25% 等距负空间（08 §1.1）；元素 ≤2 个（02 S7）；**不含文字**，全部本地化（02 §3.1）。
- 设备端表情只用官方 PNG 资产，不用 emoji（F16）；表情主体占 512×512 画布 45%–76%，缩到 154px 卡片区仍可辨（02 §3.1）。
- **禁标题上方的"圆角方形图标砖"**（F33）。

---

## 7. 材质与层次

### 7.1 四条原则（判据 + Apple 原文出处）

**原则 1 · 玻璃只给导航与浮层，内容层用 standard material**
- 判据：`glassEffect(_:in:)` 只允许出现在导航栏、标签栏、Sheet/浮层、悬浮工具键；页面背景、列表、卡片一律用 standard material 或纯色表面。
- 原文（HIG `materials.md`）：*"Don't use Liquid Glass in the content layer. Liquid Glass works best when it provides a clear distinction between interactive elements and content… Instead, use standard materials for elements in the content layer, such as app backgrounds."*
- 同页原文（层级关系）：*"Liquid Glass forms a distinct functional layer for controls and navigation elements — like tab bars and sidebars — that floats above the content layer, establishing a clear visual hierarchy between functional elements and content."*

**原则 2 · 自定义控件上的玻璃要少；系统控件不手动套玻璃**
- 判据：自定义控件上的 `glassEffect(` 每屏 ≤1 处；Tab Bar / Sidebar / Button / Toolbar 等系统组件**不手动加** `glassEffect`（系统自动获得玻璃外观与行为）。
- 原文：*"Use Liquid Glass effects sparingly. Standard components from system frameworks pick up the appearance and behavior of this material automatically. If you apply Liquid Glass effects to a custom control, do so sparingly… Limit these effects to the most important functional elements in your app."*

**原则 3 · 默认只用 `Glass.regular`，`Glass.clear` 不启用**
- 判据：`Glass.clear` 的唯一准入条件是**底层是视觉丰富的背景**（照片、波形、彩色内容层）。我们的背景是内容层（小栈的脸 + 文字），视觉不丰富 → **`Glass.clear` 不用**。
- 原文：*"Only use clear Liquid Glass for components that appear over visually rich backgrounds. Liquid Glass provides two variants — Glass/regular and Glass/clear…"*

**原则 4 · 内容层的瞬时交互控件，激活时才玻璃化**
- 判据：滑块 / 开关类控件在**被激活的瞬间**才呈现玻璃外观，未激活时用 standard material。
- 原文（原则 1 同段的例外条款）：*"An exception to this is for controls in the content layer with a transient interactive element like sliders and toggles; in these cases, the element takes on a Liquid Glass appearance to emphasize its interactivity when a person activates it."*
- 落地：iOS 端若做「半圆转盘」的对应物属此类；**设备端 320×240 不适用**（LCD + 无系统材质）。

### 7.2 SwiftUI Liquid Glass 真实 API（Apple 官方 SwiftUI 文档符号页，原文实读）

| 符号 | 说明 |
|---|---|
| `Glass` | struct，iOS 26.0+ |
| `Glass.regular` | 默认变体 |
| `Glass.clear` | 另一变体（准入条件见原则 3） |
| `Glass.interactive(Bool) -> Glass` | 是否随交互响应 |
| `Glass.tint(Color?) -> Glass` | 给玻璃材质本身着色 |
| `View.glassEffect(_ glass: Glass = .regular, in shape: some Shape = DefaultGlassEffectShape()) -> some View` | 默认取 `.regular` 变体 + 默认胶囊形状 |
| `GlassEffectContainer(spacing: CGFloat?, content: () -> Content)` | 把多个玻璃形状**合并渲染**（性能更好）并支持形状之间互相 morph；`spacing` 越大越早开始融合 |

可用平台：iOS 26.0+ / iPadOS 26 / macOS 26 / tvOS 26 / watchOS 26 / macCatalyst 26。
→ 我们的最低部署 iOS 17（`00` §5.5），故以上 API 全部走 `#available(iOS 26.0, *)` 渐进增强。

### 7.3 其余材质纪律

- 玻璃用量 **≤10%–15%**，主背景保持纯净实色，列表项是纯实色（11 §4.2，Things on iOS 26 实测）。
- 内容层用 standard material `regular`（00 宪法 7）；不用 `quaternaryLabel` 于 thin/ultraThin 之上（宪法 8）。
- **玻璃是背景，不是内容容器**：文字永远浮在玻璃之上（08 §2.1）；玻璃上不放长文本，只承载高识别度极简动作（11 §4.3；08 §2.5）。
- clear 玻璃上亮背景加 35% 暗蒙层（00 宪法 15）；材质上方文字用 vibrant color（宪法 14）。
- 设备端：**禁 `backdrop-filter` 毛玻璃**（02 禁止项 12）、禁极光/渐变光斑（11）、禁文字投影（13）。

---

## 8. 动效预算

**硬预算**（F10–F13）：单屏**持续**动效 ≤1 处且只能是**小栈的脸**；一次性反馈 ≤2 处且**总时长 ≤400ms**（F12）。默认只动 `transform` / `opacity`，**禁动画布局属性**（F11）；paint 级动画仅限脸部。禁弹跳/弹性缓动（`animate-bounce` / 过冲 spring）；禁 `transition: all`（F38）。必须支持 `accessibilityReduceMotion`，所有动画有等价静态形态，设备端另设「关闭呼吸/摆动」开关（F10）。禁大面积模糊动画，模糊幅度 ≤8px 且只做一次性短效果（F13）。

| 令牌 | 时长 | 缓动 | 用途 |
|---|---|---|---|
| instant | 80ms | standard | 状态点闪烁 |
| press | 120–150ms | emphasized-decelerate | 按下回弹（scale 0.96） |
| toggle | 200ms | standard | 开关、选中 |
| enter | 250–300ms | emphasized | 元素进场 |
| screen | 300–400ms | emphasized | 页面转场 / sheet 弹出 |
| layer | 400–450ms | emphasized | 浮层出现 |
| character | 400–700ms | spring | 表情变化（设备端） |
| blink | 闭 120 + 开 90ms | standard | 眨眼（设备端） |
| idle / sway | 3.5–5s / 4–6s | ease-in-out | 待机呼吸 / 摆动（设备端） |

出处：06 §7.5。主曲线 `cubic-bezier(0.2, 0.8, 0.2, 1)`（= emphasized-decelerate），两端共用（02 §4.3；06 §4.4.2）。待机周期定 3.5–5s（0.2–0.25 Hz），**修订**上游 `motion.ambient 1.45s`（0.69 Hz，读感是"躁"不是"呼吸"）——06 §4.4.1。眨眼间隔 **2.5–6s 随机**（固定间隔 = 机械感）——06 §4.4.4。半圆转盘松手吸附 ≤200ms（22 §3.1 ③；F29）。

---

## 9. 组件清单

| 组件 | 用途 | 平台 | 规格 | 禁止事项 |
|---|---|---|---|---|
| **小栈的脸（表情层）** | 唯一主视觉，承载 AI 内部状态 | 两端 | 设备端全屏；iOS 首屏占视觉面积 ≥40% | 不用文字标签表达"正在听/在想"；不用 emoji；不用逐字流式 |
| **生命力核心** | 同心三层：外层依恋 / 中层情绪 / 内层能量 | iOS | 参照 11 §5.5 | 不用圆环表达完成度或连续天数（R18）；不编造数字（F2） |
| **状态胶囊** | 一行既是状态指示器又是过滤器 | iOS | 顶部 L0，图标 + 统计 | 不用装饰性圆点；不用"·"连接元信息（F18） |
| **功能卡（单焦点）** | 一个功能一张卡 | 两端 | 设备端 284×156 圆角 20；iOS 宽 = 屏宽 − 40 | 禁六宫格/多卡同屏；禁卡片套卡片（F15） |
| **分体式动作卡** | 徽标 = 主操作，卡片其余 = 次操作 | iOS | 11 §1.4 | 不用颜色/描边划分主次 |
| **主按钮** | 屏幕唯一主动作 | iOS | accent 填充 + 白字（5.75:1）；尺寸档 44 / 52 / 64 pt | 禁圆角方形图标砖；禁 emoji 按钮；禁营销文案；**不手动给系统 Button 套 `glassEffect`** |
| **次级按钮 / 文字按钮** | 次要路径 | iOS | regular material；动词文案 | 禁"让我们开始吧！"式；禁用"we" |
| **就地展开行** | 详情不跳页 | iOS | 展开/收起同位；完成反馈延 0.5s + 触感 | 禁 push 新页做同类详情；禁逐行翻页转场（R20） |
| **半圆转盘** | 档位参数调节 | 设备端 | 3–5 档；拖动实时高亮；松手吸附 ≤200ms；档位名以文字标 1 个 | 禁连续任意值；禁画历史曲线 |
| **按住说话条** | 语音输入 | 两端 | 按住说话 / 松手结束；iOS 按住时浮出「发送/取消」 | 禁隐藏手势（必须另有可见入口） |
| **Inset Grouped 列表** | 设置与陪伴列表 | iOS | 行高 44–52pt（常用 52）；16pt 边距；10–12pt 圆角；0.5pt 分割线 | 禁第三种信息轴；禁危险操作不分组 |
| **记忆条目** | 回顾 | iOS | 默认收起：最近一句 + 一个表情；点开就地展开 | 禁一屏铺满气泡列表（F19） |
| **空状态** | 首次 / 无内容 | 两端 | ≤1 个主按钮；给一个明确下一步 | 禁多按钮空状态（F9） |
| **错误提示条** | 失败处理 | 两端 | 就地显示在动作发生处；有文字；说明怎么修 | 禁全局 toast（F8）；禁"oops!"；禁指责用户 |
| **Live Activity / 灵动岛** | 承载"在听/在想" | iOS | 卡片圆角 20–24pt；高 44–48pt；间距 8–10pt | 禁写文字状态标签；静止即状态，不做跳动波形 |
| **状态灯（12 LED）** | 设备端状态外显 | 设备端 | 状态色 + 形状 + 文字三通道 | 禁只靠颜色（F3）；禁品牌色铺底 |

**玻璃纪律**：系统组件（Tab Bar / Sidebar / Button / Toolbar）的玻璃外观由系统自动提供，我们只按 §7 原则 2 的配额使用自定义玻璃。

---

## 10. 设备端 320×240 专属规范

**物理约束**：320×240，ILI9342E LCD，2.0 吋对角 → **PPI ≈ 200**（06 §2.3，**假设未验证**）。按 500mm 视距、16 弧分舒适阅读反推，正文需 ≥18.3px；交叉验证：14px @200PPI 的张角约为 iPhone 最小字号的 **46%**。
→ **结论（物理必然，非审美偏好）**：320×240 承载不了长文案，只能承载「一个标题 + 一行短句 + 一个动作」。

| 项 | 规定 | 出处 |
|---|---|---|
| 栅格 | 8 栏，边距 12，列宽 30，gutter 8（12+8×30+7×8+12=320） | 06 §2.7 |
| 字号 / 文字量 | 七档 11–28px，<11px 禁；每屏 ≈30 字（iOS ≈80 字） | 06 §7.2；19 F19 |
| 触摸目标 | ≥44×44px | F5；19 §4.2 |
| 圆角 / 间距 | 见 §4、§5（设备列） | 06 §7.3、§7.4 |
| 屏幕数 | 一次只显示一张功能卡 | 02 §6.1；00 §2.4 |
| 材质 | 禁 backdrop-filter、禁渐变光斑、禁文字投影 | 02 禁止项 11–13 |
| 动效 | 持续动效只有脸部呼吸/眨眼；其余一次性 ≤2 且 ≤400ms | F12；06 §7.5 |
| 禁 | 圆环（R18）、彩色圆形图标网格（F36）、emoji 图标（F16）、glow（F17） | — |

---

## 11. 禁止清单

**禁止什么 · 为什么 · 命中哪条规则**。规则来源：impeccable（62 条确定性检测器）/ nongeneric（82 条检测器）/ 19 号 Floor。

> `impeccable` 62 条与 `nongeneric` 82 条的**完整规则目录尚未导出**（25 号 §4 待办 T1/T2），下表"命中规则"列只写**已核实的规则名**，其余给 Floor 编号，导出后回填。

| # | 禁止 | 为什么 | 命中规则 |
|---|---|---|---|
| 1 | **标题上方放圆角方形图标砖** | AI 直出界面的招牌动作 | impeccable README 点名 *"the rounded-square icon tile above every heading"*；F33 |
| 2 | **Inter / Roboto 到处都是** | SaaS 模板味；字体应 ≤2 家族 | impeccable overused-font；nongeneric Visual Slop |
| 3 | **紫→蓝渐变** | AI 味第 2 条；我们零渐变 | impeccable purple gradients；nongeneric Visual Slop（`#8b5cf6→#6366f1`）；F17 |
| 4 | **卡片套卡片** | AI 味第 3 条 | impeccable cards nested in cards；F15 |
| 5 | **彩色底上的灰字** | AI 味第 4 条；且 WCAG 失败 | impeccable gray text on colored backgrounds |
| 6 | **`background-clip: text` 彩虹标题** | 视觉噪声 | nongeneric Visual Slop；F36 |
| 7 | **`border-l-4` 侧边条纹 + 圆角卡片** | 模板化装饰 | nongeneric Visual Slop；F36 |
| 8 | **彩色圆形图标网格 / 六宫格** | 工具型范式，把陪伴降格 | nongeneric Visual Slop；F36；02 禁止项 3 |
| 9 | **弥散霓虹 glow / 暗色光晕** | AI 味四大元凶之一 | impeccable dark glows；F17 |
| 10 | **弹跳 / 弹性缓动 `animate-bounce`** | 过时感 | impeccable bounce easing；nongeneric Motion Slop；F38 |
| 11 | **`transition: all`** | 隐式全量动画 | nongeneric Motion Slop；F38 |
| 12 | **动画布局属性（width/height/top/left）** | 触发全量重排 | nongeneric Motion Slop；F11 |
| 13 | **缺 `prefers-reduced-motion` 分支** | 晕动症可达性 | nongeneric Motion Slop；F10 |
| 14 | **输入框字号 <16px** | 触发 iOS Safari 自动放大 | nongeneric Responsive Breakage；F35 |
| 15 | **`100vw` 横向滚动 / flex-grid 子项缺 `min-width:0`** | 320px 不变量被破坏 | nongeneric Responsive Breakage |
| 16 | **触摸目标 <44px / 44pt** | HIG 硬值 | impeccable small touch targets；nongeneric harden 44px；F5 |
| 17 | **emoji 充当图标** | 跨平台渲染不一致 | F16 |
| 18 | **文案 "Not a X. A Y." 格言句式** | AI 文案招牌动作，ENFP 人格最易中招 | nongeneric Copy Slop；F34 |
| 19 | **文案营销词 / ✨ 闪光 emoji / 破折号滥用** | 同一检测器 | nongeneric Copy Slop；F34 |
| 20 | **眉标题（eyebrow，全大写小标签）** | AI 味头号来源 | F14（hallmark Floor 第 9 条） |
| 21 | **手绘 OS 窗口边框、装饰性圆点、`·` 连接元信息** | 伪造原生感 | F18 |
| 22 | **纯黑 / 纯灰** | 颜色一律带一点色相 | impeccable Anti-Patterns；F37 |
| 23 | **编造指标**（假"亲密度 87"） | 陪伴产品最容易造假 | F2 |
| 24 | **KPI 考核面**（计数、红叉、进度环、催促震动、运营 Banner） | 把"伴侣"降格成"电子宠物" | 00 宪法 17；R18；11 §6.3、§8.2 |
| 25 | **AI 内部状态用文字标签或跳动波形** | 交给小栈的脸 | 00 宪法 16′；R5 |
| 26 | **错误提示没有文字 / 不说怎么修** | 可达性硬伤 | 20 §5.1；F8 |
| 27 | **深色卡片 + 粗白字作为所有功能的统一模板** | 设备端旧模板 | 02 禁止项 2 |
| 28 | **大面积高饱和 `#FF6699` 类整屏底色** | S=100%，是本项目 canvas 的 2.6 倍，必甜腻 | 02 禁止项 1；06 §3.5 |
| 29 | **同屏出现第二个强调色 / 两种以上功能强调色** | 眼睛无法建立优先级 | F20；R15；02 禁止项 25 |
| 30 | **导航深度 >2 层 / 无限滚动 / 多选批量操作** | 工具型范式 | 02 禁止项 20 / 23；R17、R19 |
| 31 | **启动页做品牌、App 内到处放 logo** | 官方明文 | R16（20 §2.3） |
| 32 | **内容层用 Liquid Glass / 玻璃上放大段文字** | 官方明文 | 00 宪法 5；11 §4.3 |

---

## 12. 文案与语气

- **少即是多 + 按钮用动词**：每个字都问它是否必要（HIG Writing："Check each word to be sure it needs to be there."，20 §4）；"Send" 好过 "Let's do it!"。小栈的话短，ENFP 的话痨放在后端回复长度控制里。
- **禁 "we"、禁 "oops!" / "uh-oh" 感叹词**；人格自称统一为"我"；错误信息就近显示、不指责用户、说清怎么修，写"现在有点走神，稍等一下"而不是"我们遇到了问题"（20 §4）。
- **禁 "Not a X. A Y." 格言句式 / 营销词 / 破折号滥用 / ✨ 闪光 emoji 堆砌**（nongeneric Copy Slop；F34）。图标层一律禁 emoji；人格语气可偶尔用一个 emoji，但不得承担状态或图标职能（20 §2.4 注）。
- **一屏 ≈80 字**（iOS）/ **≈30 字**（设备端）；首屏只承载「标题 + 一句话 + 一个操作」（F19）。
- **空状态给一个下一步**；**Onboarding 一次只问一件事**（22 §3.1 ④）。
- **显式完成反馈只给"用户可能预期会失败"的操作**，日常操作靠触感与状态自然变化（HIG Feedback，20 §5.2；F27）。
- **反馈多通道**：视觉（脸）+ 触感（Core Haptics）+ 声音（语音）+ 文字（**仅错误与重要确认**）（20 §5.1；F24）。**品牌位只在 App 图标 + Onboarding**（R16）。

---

## 13. 自动化校验接线

**两个独立实现的确定性检测器，两个都过才算过**（25 号 §3.1）。

```bash
npx impeccable detect <file|dir> --json                  # 62 条，本机已跑通 v4.7.0
npx impeccable detect --list-rules                       # 规则目录，用于回填禁止清单的规则名列
npx impeccable detect --github <dir>                     # GitHub Actions annotations
npx --yes github:Kyaa-A/nongeneric audit <file|dir>      # 82 条 + 0–100 分 + P0–P3
```

**分工**：
- `nongeneric` 覆盖 **OKLCH / Typography / Spatial 320px / Motion / Copy 四根柱**，并给出 0–100 分与 P0–P3 整改计划。
- `impeccable` 的独有价值是**色值 + 对比度比值 + 元素语义**——这层 `nongeneric` 没有，正好补上我们 §2.4 的实测缺口。
- **两者都不需要 LLM / API key**，本机 Windows 直接跑，无外部依赖成本。

**退出码**（`impeccable detect`，25 号 §1.1）：`0` = 无主要问题（通过）/ `2` = 有主要问题 / `1` = 目标无法扫描。
⚠️ **别把 2 当失败**：2 = "扫到了问题"，是门禁该拦的结果；只有 1 才是工具本身出错。CI 里用 0 放行、2 判不通过、1 判"工具故障另算"。

**行号问题**：`impeccable` 的 JSON 里 `line` 恒为 0，**要定位到行必须用 `nongeneric`**。
→ 因此固定流程：**impeccable 抓「有没有」→ nongeneric 抓「在哪一行」→ 改完再各跑一次做回归。**

**逐文件豁免**：`<!-- impeccable-disable overused-font: exported brand doc -->`，豁免必须写理由。

**我们额外加的闸**（19 号 §4.1/§4.2）：

| 检查项 | 判据 | 工具 |
|---|---|---|
| SwiftUI 字面量颜色 / 字号 | `Color(red:`、`Color(.white)`、`.font(.system(size:` → 0 | grep，CI 跑 |
| LVGL 字面量颜色 | 绘制调用中的 `0x[0-9A-Fa-f]{6}` → 收敛到 `Theme` | grep |
| 令牌外溢 | 颜色/字号/间距必须落在本文阶梯上 | stylelint 规则 |
| 对比度 | 令牌表自动跑 WCAG | `_contrast.py`（`D:\AP\AP7000\ai-workspace\stackchan-research\`） |
| 触摸目标 | ≥44pt / ≥44px | axe-core + 运行时截图 |
| Reduce Motion 覆盖 | 每个含动画的 View 能证明有减动效分支 | `accessibilityReduceMotion` 关键词 + 人工 |

**三条评审纪律**（25 号 §3.3）：① **分数不是质量证书**（nongeneric 原话：空 body 页面也能拿 100 分），检测器通过只是必要条件，人工冷评必须保留；② **明确报告未验证的范围**；③ **伪造通过本身就是 AI 味**，评审记录必须如实写未通过项。

**流程**（19 号 §6；25 号 §3.1）：只做首屏 → 渲染成 HTML → 双检测器扫描 → 修完所有 FAIL / P0–P1 → 冷评（新上下文子代理，双角色：设计总监 + 目标访客）→ 首屏通过后才逐屏往下做。

---

## 14. 待确认项

| # | 事项 | 推荐值 | 影响面 |
|---|---|---|---|
| 1 | **视觉方向**（00 §8.1 #1） | iOS 走「Apple 原生骨架 + 单一暖色」，设备端保留深色；柔雾樱花只留规则内核（边框优先于重阴影、每画面一个主动作、4/8/12/16/24 节奏、圆角克制、禁渐变球/六宫格），丢弃整屏粉底 | 全部画布/表面 token、材质策略、评审基线。备选 = 保留大面积粉底，与 HIG「内容层不该有装饰性底色」相悖 |
| 2 | **强调色具体值**（00 §8.1 #2） | 浅 `#B33A55` / 深 `#E8638C`；深色三档另用 `#F2A0B8` / `#E888A6` / `#F4A9BE` | 只影响 `.tint`、主按钮填充、状态点、小栈脸的腮红与情绪色，**不影响布局**。备选：浅 `#C2455F`（更亮）/ 深 `#FF7D9C`（更甜） |
| 3 | **设备端是否保留 8 组功能强调色** | 保留（同屏 ≤1，实测全过）；若合并为单色需重做设备端信息架构 | 设备端图标资产与 tint 容器 |
| 4 | **iOS 底部是否用 Tab Bar** | Tab 2 个（**控制 / 设置**）+ **对话降级为二级页**，不用厚重玻璃 Dock（Things on iOS 26 用无底栏结构，省 60–80pt）⭐ **2026-10-25 第二次拍板**：主界面 = 舵机控制台，聊天分到小功能 | 底部纵向空间、首页构图、00 §5.4 的 IA |
| 5 | **Mac 端策略**（00 §8.1 #3） | 待定。若降级 PWA，Core Haptics / Live Activity / 灵动岛 / Widget / 快捷指令 / 控制中心全部失效 | **不定则 iOS 端只能停在设计稿阶段**，无法编译验证 |

---

## 附：文末自查

| 项 | 值 |
|---|---|
| 文件绝对路径 | `D:\jss18\AI\StackChan-main\DESIGN.md` |
| 字节数 | 32577 |
| 大小 | 31.81 KB |
| UTF-8 BOM | False |
| NUL 字节数 | 0 |
| U+FFFD 替换符 | 0 |
| CR（CRLF）数 | 0 |
| LF 数 | 421 |
| 中文字符数（CJK） | 4947 |
| 全部字符数 | 20282 |

- 编码：UTF-8 无 BOM · 纯 LF · 无 NUL · 无 U+FFFD。
- 数值来源：全部标注于 `docs/research/` 现有文档章节；未实测的数值一律不写。
- 未写入（未找到出处，不补编）：iPhone 17 Pro 屏幕 / 灵动岛尺寸；设备端 PPI 200（06 号 §2.3 未验证假设）；`impeccable` 62 条与 `nongeneric` 82 条的完整规则目录（25 号 T1/T2 未导出）；对比度的 axe-core 实测复核（00 号 §9 风险 7）；设备端实际画布 `#080A0F` 上的对比度复算；M3 深色 surface 编号的明度方向。
