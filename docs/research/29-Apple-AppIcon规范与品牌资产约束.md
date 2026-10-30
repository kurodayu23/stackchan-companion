# 29 · Apple App Icon 规范与我们的品牌资产约束

> 核实日期：2026-10-23
> 核实者：我本人（主会话）
> 权威来源：**Apple HIG `app-icons.md` 官方原文实抓**（`.md` 端点）
> 文档版本：Change log 最新一条 **2026-06-08 "Refined guidance for Liquid Glass."**
> 触发原因：用户明确说「logo 我们可以自己做」→ 动手前必须先知道 Apple 对图标**现在**要求什么

---

## 一、一句话结论

> **iOS 图标已经不是"做一张 PNG"了 —— 现在必须是"分层矢量 + 6 种外观变体 + 用 Icon Composer 导出"。**
> 而 **Icon Composer 随 Xcode 分发 = 需要 macOS**。
> → **这给"Mac 从哪来"那条待拍板项又加了一条硬依赖**：没有 Mac，我们只能交付**分层 SVG 源文件**，导出环节必须外包给有 Mac 的人。

---

## 二、⭐ 规格表（HIG 原文表格）

| 平台 | 布局形状 | 系统遮罩后形状 | 布局尺寸 | 风格 | 外观变体 |
|---|---|---|---|---|---|
| **iOS, iPadOS, macOS** | Square | Rounded rectangle (square) | **1024×1024 px** | **Layered** | **Default, dark, clear light, clear dark, tinted light, tinted dark**（6 种） |
| tvOS | Rectangle (landscape) | Rounded rectangle (rectangular) | 800×480 px | Layered (Parallax) | N/A |
| visionOS | Square | Circular | 1024×1024 px | Layered (3D) | N/A |
| watchOS | Square | Circular | 1088×1088 px | Layered | N/A |

**支持的色彩空间**：sRGB (color) / Gray Gamma 2.2 (grayscale) / **Display P3**（wide-gamut，iOS/iPadOS/macOS/tvOS/watchOS）

> 我们只做 iOS/iPadOS/visionOS 的话，需要交付：**1024×1024 方形分层源文件**（不是圆角成品！）+ 6 种外观标注。
> visionOS 要**圆形**遮罩 → 同一套分层可以同时供 iOS 与 visionOS 用，**这是加分项**：一次设计，两个平台。

---

## 三、⭐ 分层图标机制（我们必须理解的部分）

HIG 原文：

> *"iOS, iPadOS, macOS, and watchOS app icons include a **background layer and one or more foreground layers** that coalesce to create dimensionality. These icons take on **Liquid Glass attributes like specular highlights, refraction, and translucency**."*

> *"You use your favorite design tool to craft the individual foreground layers of your app icon… you then import your icon layers into **Icon Composer**, a design tool included with Xcode and available from the Apple Developer website. In Icon Composer, you define the **background layer**, adjust your **foreground layer placement**, apply visual effects like **specular highlights and refraction**, **annotate for default, dark, and mono appearance variants**, test and preview your icon across system versions, and export your icon for use in Xcode."*

**⭐ 关键含义**：
1. **前景层与背景层分开交付**，系统负责在运行时合成并施加玻璃效果。
2. **玻璃效果不是我们画的** —— 系统加。所以我们的设计**不能自带**高光/投影/发光（见下文禁止项）。
3. **「mono」变体是第三个必须标注的外观**（HIG 表格里列了 6 种，Icon Composer 段落里提 default/dark/mono）——
   mono 是给"着色模式"用的单色版，**在 iOS 26+ 的着色主屏上非常显眼**，必须单独设计。
4. **`Icon Composer` 是 Xcode 附带工具** → 需要 macOS。

---

## 四、HIG 的设计原则（逐条原文 + 对我们的判据）

| # | HIG 原文（节选） | 落到我们的判据 |
|---|---|---|
| 1 | *"**Prefer clearly defined edges in foreground layers.** To ensure system-drawn highlights and shadows look best, avoid soft and feathered edges on foreground layer shapes."* | 前景层**不许羽化边缘**。我们若用"柔和发光的脸"做图标 → **违规**（而且与我们的"禁 glow"同向） |
| 2 | *"**Vary opacity in foreground layers** to increase the sense of depth and liveliness."* | 前景层用**半透明填充**制造层次（官方举 Photos 图标为例）→ 与我们的"禁卡片套卡片"不冲突，是**官方推荐的手法** |
| 3 | *"**Design a background that both stands out and emphasizes foreground content.** If you choose a gradient for your background layer, ensure that it responds well to system lighting effects… If you do import a background layer, make sure it's **full-bleed and opaque**."* | 背景层要么用 Icon Composer 内建的纯色/渐变，要么自定义但**必须满幅不透明** |
| 4 | *"**Prefer vector graphics** when bringing layers into Icon Composer. Unlike raster images, vector graphics (such as SVG or PDF) scale gracefully… Outline artwork and **convert text to outline**."* | ⭐ **交付格式 = SVG 分层矢量，文字转轮廓**。这正好对上我们的开源自制路线（见 §六） |
| 5 | *"**Produce appropriately shaped, unmasked layers.**… Providing layers with **pre-defined masking negatively impacts specular highlight effects and makes edges look jagged**."* | ⭐ **不许自己画圆角**！交付方角，系统负责遮罩。这是很多人会踩的坑 |
| 6 | *"**Keep primary content centered** to avoid truncation when the system adjusts corners or applies masking."* | 主图形居中；visionOS/watchOS 圆形遮罩更要居中 |
| 7 | *"**Embrace simplicity**… Find a concept or element that captures the essence of your app… express it in a **simple, unique way with a minimal number of shapes**. Prefer a **simple background**… **you don't need to fill the entire icon canvas** with content."* | ⭐ 与我们的「一屏一个想法」「不做功能堆叠」同源。**图标只画一个符号** |
| 8 | *"**Consider basing your icon design around filled, overlapping shapes.** Overlapping solid shapes in the foreground, particularly when paired with transparency and blurring, can give an icon a sense of depth."* | 用**填充 + 重叠**，**不要描边**（官方把"圆环 + 描边"标为错误用法） |
| 9 | *"**Include text only when it's essential** to your experience or brand. Text in icons doesn't support accessibility or localization…"* | 图标里**不放文字**（含中文）→ 也避免"小栈"两个字在图标里 |
| 10 | *"**Prefer illustrations to photos and avoid replicating UI components**… avoid extremely thin line weights and sharp corners, because they tend to lose detail and crispness in smaller icon sizes."* | 用插画不用照片；**不许极细线宽**（小尺寸会糊） |
| 11 | *"**Don't use replicas of Apple hardware products.** Apple products are copyrighted and can't be reproduced in your app icons."* | 官方明文：**不许复制苹果硬件**。→ **同理适用于我们**：官方 StackChan 的机身/脸是 M5Stack 的形象资产，我们的图标**不能画成"官方小栈产品图"** |
| 12 | *"**Let the system handle blurring and other visual effects.**… there's no need to include specular highlights, drop shadows between layers, beveled edges, blurs, glows, and other effects."* | ⭐ 我们的图层里**不许有高光/投影/发光/模糊** —— 与我们的反 AI 味禁项完全一致（**互为加强**） |
| 13 | *"**Create layer groupings** to apply effects to multiple layers at once."* | 图层分组（Icon Composer 支持组级效果） |
| 14 | *"**Keep your icon's features consistent across appearances.**… Avoid creating custom icon variants that **swap elements in and out** with each variant."* | 6 种外观**核心特征一致**，不换元素不换构图 |
| 15 | *"**Use your light app icon as the basis for your dark icon.**… dark icons are more subdued, and clear and tinted icons are even more subdued."* | dark 版由 light 版派生，**整体更 subdued**（不能只是亮度反相） |
| 16 | *"**Consider offering alternate app icons.**… If you offer this capability, make sure each icon you design remains **closely related** to your content and experience."* | 可选：提供备选图标（比如"夜间模式的脸"），但必须与主图标强相关 |

---

## 五、⭐ 对我们 logo 的 5 条硬约束（可直接进禁止清单）

| # | 约束 | 依据 | 与我们既有条款的关系 |
|---|---|---|---|
| L1 | **交付分层 SVG，不预切圆角** | HIG 原文 #4、#5 | 新增（应补进 `DESIGN.md` §11） |
| L2 | **图层里不许有高光/投影/发光/模糊** | HIG 原文 #12 | 与既有 F17（禁 glow）、F36 一致，**官方背书** |
| L3 | **不许用羽化/柔和边缘做前景层** | HIG 原文 #1 | 新增 |
| L4 | **不许画成"官方小栈"的样子**（商标/角色形象） | HIG 原文 #11 的同构原则 + M5Stack 商标 | 新增，**法律风险级别** |
| L5 | **必须有 mono 单色版**（着色主屏用） | Icon Composer 段落 + HIG 外观表 | 新增，**不做就在 iOS 26+ 主屏上"消失"** |

**L4 需要展开说明**：
我们用的硬件是**官方成品**，官方 App（Flutter 1.2.8）也自带官方图标与形象。
→ **我们的 App 图标如果画成"官方小栈的脸"，在法律与伦理上都不对**：
① 形象属于 M5Stack；② 用户会误以为这是官方 App；③ 我们的产品定位是"第三方自研软件栈"。
**正确做法**：图标表达的是**我们的**产品 —— 一个"陪伴桌面机器人的控制与对话端"，
用**一个抽象符号**（不是官方脸），配合我们的暖色 `.tint`。

> 这也顺带回答了一个我们一直没拍板的问题：**logo 不画小栈，画什么？**
> 候选方向留给 DESIGN.md / 后续评审，但**约束已经明确**：单符号、填充重叠、无文字、无光效、矢量分层、6 种外观一致。

---

## 六、⭐ 我们能自制的部分与工具路线（结论）

**好消息**：Apple 官方要的是**分层矢量**（SVG/PDF），**不是** Photoshop 技法。
→ 这意味着我们**完全可以开源自制**，且不依赖任何商业设计软件。

**自制工具链（与 `23` 号 §五 交叉引用）**：
1. **矢量 authoring**：手写 SVG / Inkscape（GPL，开源）/ Penpot（已装 0.23.1，MPL-2.0）
2. **图标规范/描边统一**：lucide / Phosphor（MIT / MIT），或自建我们的图标集
3. **导出与检查**：`svgo`（MIT）优化、`resvg`/`sharp`（Apache-2.0 / libvips）栅格化出多密度
4. **分层与外观变体**：**Icon Composer（Apple 官方，需 macOS）** 或手工产出符合规范的图层 + 导出脚本
5. **命名与尺寸**：1024×1024 方形主文件（**不预切圆角**）+ 6 种外观标注

**⚠️ 唯一绕不开的外部依赖 = Icon Composer（macOS）**。
**降级方案（没有 Mac 时）**：
交付**分层 SVG + 一份书面外观标注说明**（每层对应 default/dark/mono 的哪种处理），
让有 Mac 的人用 Icon Composer 导出。**这是可接受的交付形态**，但成品 App 图标要等 Mac。

---

## 七、与已有文档的关系（回填清单）

| 文档 | 需回填 |
|---|---|
| `00-总纲` §8 第 3 条（Mac） | ⭐ **加一条依据**：App Icon 的官方工作流（Icon Composer）同样需要 macOS |
| `DESIGN.md` §6（图标）/ §11（禁止清单） | 补 L1–L5 五条 |
| `DESIGN.md` §12（文案与语气） | 图标里不放文字 → 补一条 |
| `23` 号 §五（logo 工具链） | 引用本文 §六；补充"分层矢量 + Icon Composer + macOS 依赖" |
| `PRODUCT.md` | 品牌定位：我们的图标不是官方小栈（若已写则交叉引用） |

---

## 八、未核实范围（如实登记）

1. **Icon Composer 的具体操作流程与导出格式** —— 只读了 HIG 对它的描述，**未下载/未运行 Icon Composer**（本机无 macOS）。
2. **6 种外观变体在 `Contents.json` 里的确切键名与结构** —— HIG 只给了外观名称，键名需查 Xcode 文档（`<doc://com.apple.documentation/documentation/Xcode/configuring-your-app-icon>`），**未查**。
3. **visionOS / watchOS 的 3D 图标要求细节** —— HIG 只给了轮廓级说明。
4. **App Store 审核对图标的具体红线** —— 只知道"所有变体都受 App Review Guidelines 约束"，**未读审核指南原文**。
5. **mono 变体的官方定义细节** —— HIG 提到 "mono appearance variants" 但未展开它与 "tinted" 的关系。
6. **我们的最终图标概念** —— **尚未设计**。约束已定（L1–L5），概念待评审。

---

## 九、附：HIG 原文出处

- 页面：`https://developer.apple.com/design/human-interface-guidelines/app-icons.md`
- Change log：2026-06-08（Liquid Glass 修订） / 2025-06-09（分层图标 + 跨平台一致性） / 2024-06-10（dark/tinted 变体） / 2024-01-31（备选图标可用性） / 2023-06-21（visionOS） / 2022-09-14（Apple Watch Ultra）
- 相关页：`icons.md`、`images.md`、`dark-mode.md`、`Apple Design Resources`（含 app icon production templates 的网格）
- 开发文档：<doc://com.apple.documentation/documentation/Xcode/creating-your-app-icon-using-icon-composer>
- Copyright © 2026 Apple Inc.
