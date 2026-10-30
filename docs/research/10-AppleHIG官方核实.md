# 10 · Apple HIG 官方核实（用真实文档页校对，不靠印象）

> 方法：用 chrome-devtools MCP 真实打开 `developer.apple.com/design/human-interface-guidelines/*` 页面，提取正文 `innerText`。
> 这一份的权威性**高于** `08-iOS26视觉规范.md`（那份是视觉模型从像素估计的）。两者冲突时**以本文件为准**。
> 抓取时间：2026-10-23。

---

## 1. Typography（官方原文要点）

来源：https://developer.apple.com/design/human-interface-guidelines/typography

### 1.1 字号（官方表）
| 平台 | 默认字号 | **最小字号** |
|---|---|---|
| **iOS / iPadOS** | **17 pt** | **11 pt** |
| macOS | 13 pt | 10 pt |
| tvOS | 29 pt | 23 pt |
| visionOS | 17 pt | 12 pt |
| watchOS | 16 pt | 12 pt |

> ✅ **证实**：iOS 端 11pt 是官方下限。`02-设计契约与交互规范.md` 里把设备端 9–10.5px 直接搬到 iOS 会破规，必须放大。

### 1.2 字重（官方明确劝阻）
> "In general, avoid light font weights. For example, if you're using system-provided fonts, prefer **Regular, Medium, Semibold, or Bold** font weights, and **avoid Ultralight, Thin, and Light** weights, which can be difficult to see, especially when text is small."

→ 我们做"柔雾/轻盈"风格时**不能用 Light/Thin 字重**去追求"轻盈感"，轻要用**颜色/留白**做，不是用字重。

### 1.3 字体家族
- **San Francisco (SF)**：SF Pro、SF Compact、SF Arabic / Armenian / Georgian / Hebrew、SF Mono。
- **系统还提供 SF Pro / SF Compact 的 Rounded（圆体）变体** —— 官方原文：*"you can coordinate text with the appearance of soft or rounded UI elements, or to provide an alternative typographic voice."*
  → 💡 **对「小栈」极其相关**：小栈是圆润的桌面机器人，iOS 端用 **SF Pro Rounded** 会天然"像系统里的、但更可爱"，且不用引入自定义字体（省掉字体授权与 Dynamic Type 适配的坑）。
- **New York (NY)**：衬线，与 SF 搭配。
- 变量字体 + **dynamic optical sizes**：系统自动在 Text/Display 等离散光学尺寸间插值。

### 1.4 层级（text styles）
- 系统 text style 指定 weight + point size + leading 一组值，构成 typographic hierarchy。
- 官方要求：**"Minimize the number of typefaces you use"** —— 字体家族混用会破坏层级、降低可读性、让界面显得内部不一致。
- **Dynamic Type**：用 text styles 才能随系统字号缩放；"some content is more important" —— 放大字号时应优先放大关心的内容（如对话正文），而不是所有东西。

### 1.5 SF Symbols
> "SF Symbols provides a comprehensive library of symbols that integrate seamlessly with the San Francisco system font, **automatically aligning with text in all weights and sizes**."

→ 图标与文字**同字重自动对齐**，这是"看起来像原生"的一个隐性但关键因素。**禁止自绘图标**（我们此前的初稿就有自绘 emoji 图标的问题）。

---

## 2. Materials / Liquid Glass（iOS 26 官方原文，**最关键的一份**）

来源：https://developer.apple.com/design/human-interface-guidelines/materials

### 2.1 材料的定义与分层（原文）
> "A material is a visual effect that creates a sense of depth, layering, and hierarchy between foreground and background elements."
> "Apple platforms feature two types of materials: **Liquid Glass**, and **standard materials**."
> "Liquid Glass forms a distinct functional layer for **controls and navigation elements — like tab bars and sidebars** — that **floats above the content layer**."

### 2.2 🚫 官方明令：**内容层不要用 Liquid Glass**
> "**Don't use Liquid Glass in the content layer.** Liquid Glass works best when it provides a clear distinction between interactive elements and content, and including it in the content layer can result in **unnecessary complexity and a confusing visual hierarchy**. Instead, use standard materials for elements in the content layer, such as app backgrounds. An exception to this is for **controls in the content layer with a transient interactive element like sliders and toggles**; in these cases, the element takes on a Liquid Glass appearance to emphasize its interactivity when a person activates it."

→ ✅ **完全印证视觉模型的结论**："玻璃是背景介质，不是内容容器"。
→ 且给了一个**例外规则**：内容层里"滑块/开关这类瞬时交互控件"可以在激活时呈现玻璃态 —— 这正是"摸摸头时那个按钮亮起来"该用的手法。

### 2.3 🚫 官方明令：**克制使用**
> "**Use Liquid Glass effects sparingly.** Standard components from system frameworks **pick up the appearance and behavior of this material automatically**. If you apply Liquid Glass effects to a custom control, do so sparingly. Liquid Glass seeks to bring attention to the underlying content, and **overusing this material in multiple custom controls can provide a subpar user experience by distracting from that content.** Limit these effects to **the most important functional elements** in your app."

→ **战略含义**：我们**几乎不需要手写任何 Liquid Glass 效果**。用系统组件（`TabView`、`toolbar`、`NavigationStack`、`.searchable`、`.popover`、`.sheet`）就自动获得 Liquid Glass 观感。手写玻璃 = 立刻变成"第三方在炫技"。

### 2.4 两种变体
| 变体 | 官方定义 | 适用 |
|---|---|---|
| **regular** | "blurs and adjusts the luminosity of background content to maintain legibility"；滚动边缘效应进一步模糊降不透明度 | **大多数系统组件用这个**。背景可能造成可读性问题时、或组件文字多时（alerts、sidebars、popovers） |
| **clear** | "highly translucent"，优先保证底层内容可见 | **浮在媒体背景上**（照片/视频）时，追求沉浸 |

**clear 变体的对比度处理（官方数值）**：
> "If the underlying content is bright, consider adding a **dark dimming layer of 35% opacity**."
> "If the underlying content is sufficiently dark, or if you use standard media playback controls from AVKit that provide their own dimming layer, you don't need to apply a dimming layer."

→ 我们的 App 首页如果有"小栈的脸"作为媒体背景，上面浮着按钮/文字层，就该用 **clear + 亮背景时加 35% 暗层**。

### 2.5 标准材质与 vibrancy（内容层用这套）
- iOS/iPadOS 标准材质四档：**ultraThin / thin / regular（默认）/ thick**
- vibrant labels（**任何材质上都能用**）：
  `UIVibrancyEffectStyle.label`（默认）/ `.secondaryLabel` / `.tertiaryLabel` / `.quaternaryLabel`
  → ⚠️ 官方提醒：**避免把 quaternary 用在 thin / ultraThin 上**，对比度过低。
- vibrant fills：`UIVibrancyEffectStyle.fill`（默认）/ `.secondaryFill` / `.tertiaryFill`
- separator：系统只提供**一个**默认 vibrancy 值，通用。

### 2.6 材质选择的判据（官方）
> "**Avoid selecting a material or effect based on the apparent color it imparts to your interface**, because system settings can change its appearance and behavior. Instead, match the material or vibrancy style to your **specific use case**."

→ 不要因为"看起来好看"选材质，按语义选。

### 2.7 对比度与 vibrant color
> "Help ensure legibility by using **vibrant colors on top of materials**. When you use system-defined vibrant colors, you don't need to worry about colors seeming too dark, bright, saturated, or low contrast in different contexts. **Regardless of the material you choose, use vibrant colors on top of it.**"

→ 用系统 vibrant color 放材质上，自动适配，不用自己算对比度。

---

## 3. Color（官方原文要点）

来源：https://developer.apple.com/design/human-interface-guidelines/color

### 3.1 🚫 不要硬编码系统色值
> "**Avoid hard-coding system color values in your app.** Documented color values are for your reference during the design process. **The actual color values may fluctuate from release to release**, based on a variety of environmental variables. Use APIs like `Color` to apply system colors."

→ 我们之前把 `#F1DFE5`、`#D94F78` 之类写死，等于**放弃系统的动态适配能力**。系统语义色（`systemBackground` / `secondarySystemBackground` / `tertiarySystemFill` / `label` / `secondaryLabel` / `separator`）必须用 API 取。

### 3.2 自定义色必须给全 4 个变体
> "If you define a custom color, make sure to supply **light and dark variants, and an increased contrast option for each variant**... **Even if your app ships in a single appearance mode, provide both light and dark colors to support Liquid Glass adaptivity in these contexts.**"

→ 自定义色 = **4 个值**（浅/深 × 默认/高对比度）。这是一条硬性交付要求。

### 3.3 颜色语义一致性
> "Avoid using the same color to mean different things."（同色不同义最混乱）
> "Make sure all your app's colors work well in **light, dark, and increased contrast** contexts."

### 3.4 无障碍与文化
- **不能只靠颜色区分**（色盲）：必须同时给文字标签或形状差异。
- **中西方文化差异**：官方举例 —— Stocks App 里 **英文用绿色表示上涨，中文用红色表示上涨**。
  → 💡 **对我们直接相关**：产品面向中文用户，若用颜色表示"小栈心情好/坏"，**红色在中文语境是"涨/喜"而非"危险"**。我们之前设计契约里的 `#4FA77A` 成功绿 + `#D94F78` 强调玫红，如果用红表示"负面情绪"会与中国用户直觉冲突。

### 3.5 环境适配
- True Tone 会调白点；App 可用 `UIWhitePointAdaptivityStyle` 指定对阅读/视频/游戏的影响强度。
- 颜色随环境光变化（强光下发暗发灰，暗环境下发亮发饱和）。
- 材质/半透明会改变邻近颜色的观感（地图在 map/satellite 模式切浅/深）。

---

## 4. HIG 核实后的硬性约束清单（可直接变成 lint 规则）

| # | 约束 | 检查方法 |
|---|---|---|
| 1 | iOS 字号 ≥ **11pt** | 令牌表 lint：字号档位里没有 < 11 的值 |
| 2 | 不用 Ultralight / Thin / Light 字重 | 令牌表 lint：weight 白名单 = Regular/Medium/Semibold/Bold |
| 3 | 字体家族 ≤ 2 个 | 令牌表 lint |
| 4 | 必须用 **SF Symbols**，不自绘图标 | code review / 素材清单核查 |
| 5 | 内容层不用 Liquid Glass | code review：自定义 `glassEffect` 只允许出现在导航/浮层 |
| 6 | 手写 Liquid Glass 效果要**克制**（只给最重要的功能元素） | code review |
| 7 | 内容层用 standard material（ultraThin/thin/regular/thick 四档之一） | 令牌表 |
| 8 | 不用 quaternary label 于 thin/ultraThin 之上 | code review |
| 9 | **不硬编码系统色值**，一律用语义色 API | lint：色值必须来自 token 且不能是系统色常量 |
| 10 | 自定义色提供 浅/深 × 默认/高对比 共 4 个变体 | 令牌表结构检查 |
| 11 | 同一颜色不得表达两种语义 | 设计评审 |
| 12 | 不只靠颜色传达信息（配文字/形状） | a11y 审计 + 评审 |
| 13 | 触摸目标 ≥ 44pt（Touch target） | axe-core / Playwright |
| 14 | 材质上方的文字用 vibrant color | code review |
| 15 | clear Liquid Glass 上，亮背景需加 35% 暗蒙层 | 人工检查（对比度实测） |

---

## 5. 未验证项

- 本文件只覆盖 **Typography / Materials / Color** 三页。Lists、Layout、Buttons、Live Activities、Widgets、Accessibility 等页未逐页核实（部分由 `09-iOS系统能力清单` 子代理负责）。
- Liquid Glass 的具体 API 名称（`glassEffect`、`GlassEffectContainer` 等）与参数签名**未核实** —— 本文件只引用 HIG 的**设计规则**，未涉及 API。
- iPhone 17 Pro / 17 Pro Max 的具体屏幕尺寸与灵动岛尺寸**未核实**（本轮聚焦视觉语言）。
- Material 3 侧（Google）**未用浏览器逐页核实**，由 `05-Google设计体系与AI产品设计.md` 子代理负责，其结论本文件未交叉验证。
