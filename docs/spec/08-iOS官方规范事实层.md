# 08 · iOS 官方规范事实层（Apple HIG / Developer Documentation 摘录）

> 建立日期：2026-10-25（夜间）
> 目的：把「iOS 原生感」从**口头争论**变成**可引用、可机器判定的官方事实**。
> 数据源：本机缓存的 Apple 官方文档 —— **62 页 HIG 正文（md）** + **163 份 developer documentation（md）**，
> 抓取于 2026-10-25，缓存在 `D:\AP\AP7000\ai-workspace\stackchan-research\{hig-md,ios-docs,ios-fetch}`。
> 边界：本文只写**事实层**（官方说了什么）。配色、强调色、脸怎么画等仍是 `docs/spec/07` §3 的**决策层**，未销账。

---

## 一、本文的核心方法：出处等级

「官方出处」这四个字在本项目里被用过很多次，但**大多没核对过**。本轮逐页核对了 62 页 HIG 正文后发现：

> ⚠️ **HIG 网页正文基本不给 iOS 布局数值。**
> Tab Bar 的高度／左右边距／圆角、Inset Grouped 的组圆角、分割线粗细、UISwitch 的尺寸 ——
> **这些在 HIG 正文里都查不到**。官方数值藏在 Apple Design Resources 的 Figma/Sketch 模板和官方图示里，不在文字里。
>
> ⚠️ **2026-10-27**：Figma Connector 已接入，但**本轮未能读到 Apple 官方社区套件**（账号不可见，
> 见 `docs/research/89`）⇒ 下述「查不到」目前**仍未被 Figma 解决**，本文数值等级暂不变。

所以本文给每条事实打**出处等级**标签，任何引用都必须带标签：

| 等级 | 含义 | 能否当「官方数值」引用 | 能否当「官方规则」引用 |
|---|---|---|---|
| **T1** | Apple 官方文档**明文写出**的数值 | ✅ 可以 | ✅ 可以 |
| **T2** | 官方文档**只给规则不给数值** | ❌ 不可编造数值 | ✅ 可以 |
| **T3** | 本项目**实测**（官方 App / 系统截图 / 渲染测量） | ⚠️ 须标「实测」 | ❌ |
| **T4** | 本项目**自研设定** | ⚠️ 须标「自研」 | ❌ |

**规则 ID 命名**：`IOS-<域>-<序号>`，例：`IOS-TAB-01`、`IOS-COL-03`、`IOS-A11Y-02`。
机器判定器（`prototype/ios/check_ios.py`）按这些 ID 建规则；本文 ID 与代码里的规则一一对应。

---

## 二、Tab Bar（`IOS-TAB-*`）

出处：`hig-md/tab-bars.md`（正文）+ `ios-docs/X-SwiftUI-TabView.md` + `ios-fetch/tabrole.md`

| ID | 官方规则要点 | 出处 | 等级 |
|---|---|---|---|
| `IOS-TAB-01` | Tab Bar 用来**导航**，不用来**触发动作**；要动作就用 toolbar | `tab-bars.md:24` | T2 |
| `IOS-TAB-02` | 切换 section 时 **Tab Bar 必须保持可见**；唯一例外是**模态视图盖住 Tab Bar**（模态是临时的、自包含的） | `tab-bars.md:26` | T2 |
| `IOS-TAB-03` | Tab 数量按需给，**越少越好导航**；复杂结构改用 sidebar / 可自适应 sidebar 的 tab bar | `tab-bars.md:28` | T2 |
| `IOS-TAB-04` | **不许出现溢出 Tab（More）** | `tab-bars.md:30` | T2 |
| `IOS-TAB-05` | **不许禁用或隐藏某个 Tab 按钮**；内容为空要解释原因，不许隐藏按钮 | `tab-bars.md:32` | T2 |
| `IOS-TAB-06` | 每个 Tab **必须有文字标签**，尽量用**单个词** | `tab-bars.md:34` | T2 |
| `IOS-TAB-07` | 图标用 **SF Symbols**；**优先用 filled（实心）符号**以保持平台一致性 | `tab-bars.md:36` | T2 |
| `IOS-TAB-08` | Badge = **红色椭圆 + 白字**，内容是数字或感叹号；只用于真正关键的信息 | `tab-bars.md:44` | T2 |
| `IOS-TAB-09` | **Tab 标签颜色不要和内容层背景撞色**；内容层色彩丰富时用**单色** Tab Bar 或选差异足够的强调色 | `tab-bars.md:48` | T2 |
| `IOS-TAB-10` | iOS 上 Tab Bar **浮在内容之上**，底部；材质允许内容从下方「透出来」 | `tab-bars.md:56` | T2 |
| `IOS-TAB-11` | 可在尾部放**专用搜索 Tab** | `tab-bars.md:68` | T2 |

### 2.1 ⛔ `IOS-TAB-02` 与官方 App 的实现**冲突**（需用户拍板）

官方 StackChan App（Flutter）实现是 `tabBarHidden: !isCurrentRoute` —— **push 二级页时隐藏 Tab Bar**。

- HIG `IOS-TAB-02` 说：**除了模态，不许隐藏 Tab Bar**（理由是「人会忘记自己在哪个区」）。
- 官方 App 属于**违反 HIG 的实现**。

⇒ **这不是我们抄不抄官方 App 的问题，是「官方 App 也可能不合规」的证据。**
处理：默认按 HIG 走（二级页**保持** Tab Bar 可见），把「是否与官方 App 一致」列为可翻转项，写进 `docs/spec/07` §3 待拍板。
在拍板前，**原型保持现状（二级页隐藏 Tab Bar）并显式标注这是「跟随官方 App」而非「符合 HIG」**。

### 2.2 SwiftUI API（`Tab` / `TabView` / `TabRole`）

| API | 签名 / 说明 | 出处 | 等级 |
|---|---|---|---|
| `Tab` | `Tab(_ titleKey: LocalizedStringKey, systemImage: String, value: V, @ViewBuilder content:)` | `X-SwiftUI-TabView.md:49` | T1 |
| `TabView(selection:content:)` | 用 binding 驱动选中态；每个 Tab 的 value 必须唯一且同类型 | `X-SwiftUI-TabView.md:79` | T1 |
| `TabRole` | `prominent` / `search`，iOS 18.0.0+ | `ios-fetch/tabrole.md` | T1 |
| `TabViewStyle` | `sidebarAdaptable` / `tabBarOnly` / `grouped` | `U-Updates-SwiftUI.md:182` | T1 |
| `TabViewCustomization` | `tabViewCustomization(_:)` + `@AppStorage` 持久化，iOS 18+ | `X-SwiftUI-TabView.md:293-294` | T1 |

⚠️ 本机无 Swift 工具链 ⇒ 上述 API 只做了**文档级核实**，**未编译验证**。

---

## 三、导航栈与导航栏（`IOS-NAV-*`）

出处：`ios-docs/X-SwiftUI-NavigationStack.md`、`hig-md/toolbars.md`、`hig-md/navigation-and-search.md`

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-NAV-01` | `NavigationStack` 提供 push/pop，**内置平台原生的返回按钮与右滑手势**；root 不可被移除 | `X-SwiftUI-NavigationStack.md` Overview | T1 |
| `IOS-NAV-02` | iPadOS 上同一套 `TabView` 可随尺寸在**底部 Tab Bar ↔ 侧边栏**之间切换（`sidebarAdaptable`） | `X-SwiftUI-TabView.md:109-209` | T1 |
| `IOS-NAV-03` | 导航层级深时用 **sidebar** 做二级导航；用了 sidebar 就**不要让 sidebar 的选择改变当前 Tab** | `tab-bars.md:131` | T2 |
| `IOS-NAV-04` | Toolbar 是**横向排布在视图上/下边缘**的一组控件，按逻辑分组 | `toolbars.md:20` | T2 |

> **注**：`hig-md/navigation-and-search.md` 只是一个**合集页**，把 path control / search field / sidebar / tab bar / token field 串起来；
> 真正的「Navigation Bars」单独页在 Apple 站点上已 404（`navigation-bars` → 404），内容并入 `toolbars.md`。
> ⇒ **HIG 里没有独立的「导航栏大标题 34pt」明文**；大标题的数值来自 §七 字体表（见下）。

---

## 四、列表与表单（`IOS-LIST-*`）

出处：`hig-md/lists-and-tables.md`、`hig-md/collections.md`、`ios-docs/X-SwiftUI-List.md`、`ios-docs/X-SwiftUI-Form.md`

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-LIST-01` | iOS 上 **Form 呈现为 grouped list**（macOS 是垂直对齐的堆叠）⇒ iOS 上 Form ≈ 分组列表 | `X-SwiftUI-Form.md` Overview | T1 |
| `IOS-LIST-02` | `Form` 会自动套用**平台相应的样式**（按钮、开关、标签、列表），这些样式**可能平台相关** | 同上 | T1 |
| `IOS-LIST-03` | 用 `listStyle(_:)` 切换列表样式（如 `.plain`） | `X-SwiftUI-List.md:301-305` | T1 |
| `IOS-LIST-04` | 表格/列表样式要**和数据、平台相协调**；iOS 上 grouped list 用分组容器表达层级 | `lists-and-tables.md:42` | T2 |
| `IOS-LIST-05` | 多列表格要有**描述性列标题**（名词短语，title-style 大小写） | `lists-and-tables.md:38` | T2 |
| `IOS-LIST-06` | 分组列表行尾用 **disclosure indicator（chevron）** 表达「可进入下一级」 | `lists-and-tables.md:58`（图注） | T2 |
| `IOS-LIST-07` | 用 `listRowSpacing(_:)` / `listSectionSpacing(_:)` 调行距与分组间距 | `U-Updates-SwiftUI.md:377` | T1 |
| `IOS-LIST-08` | `LabeledContent` 会**自动适配所在容器**（form / toolbar）的排版 | `SwiftUI-LabeledContent.md` Overview | T1 |

⚠️ **本轮逐页核对 `lists-and-tables.md` 全文：HIG 正文没有给行高、组圆角、分割线粗细的数值。**
⇒ 原型里的 `--r-group:11px`、行高 44px、分割线 `0.5px` **不是官方数值**，见 §十二订正。

---

## 五、材质：Liquid Glass（`IOS-MAT-*`）

出处：`hig-md/materials.md`、`ios-docs/SwiftUI-Glass.md`、`ios-fetch/glass-{regular,clear,interactive}.md`

| ID | 官方规则要点 | 出处 | 等级 |
|---|---|---|---|
| `IOS-MAT-01` | 两种材质：**Liquid Glass**（控件与导航的**功能层**）与 **standard materials**（内容层） | `materials.md` | T2 |
| `IOS-MAT-02` | ⛔ **不要在内容层用 Liquid Glass**；内容层用 standard materials（如 app 背景） | `materials.md` | T2 |
| `IOS-MAT-03` | 例外：内容层里**临时性的交互控件**（slider、toggle）可以用 Glass 强调可交互性 | `materials.md` | T2 |
| `IOS-MAT-04` | **少用** Liquid Glass；系统组件会自动继承，自定义控件要克制 | `materials.md` | T2 |
| `IOS-MAT-05` | `clear` 变体只用在**视觉丰富背景**上（照片、视频）；背景亮时加**深色遮罩 35% 不透明度** | `materials.md:32` / `materials.md:50` | T2 |
| `IOS-MAT-06` | `regular` 变体用于**背景内容可能影响可读性**或**文字较多**的场景（alert、sidebar、popover） | `materials.md` | T2 |
| `IOS-MAT-07` | iOS/iPadOS 提供 **4 种 standard materials**：ultra-thin / thin / **regular（默认）** / thick | `materials.md` | T2 |
| `IOS-MAT-08` | 材质上放文字要用 **vibrant 颜色**；label 4 级（label/secondary/tertiary/quaternary）、fill 3 级、separator 1 级 | `materials.md` | T2 |

### SwiftUI API（iOS 26.0.0+）

| API | 签名 | 出处 |
|---|---|---|
| `Glass` | `struct Glass` | `SwiftUI-Glass.md` |
| `.glassEffect(_:in:)` | 视图修饰符 | `SwiftUI-Glass.md` |
| `Glass.regular` / `Glass.clear` / `Glass.identity` | 三种变体 | `glass-regular.md` / `glass-clear.md` / `SwiftUI-Glass.md` |
| `Glass.interactive(_:)` | `func interactive(_ isEnabled: Bool = true) -> Glass` | `glass-interactive.md` |
| `Glass.tint(_:)` | `func tint(Color?) -> Glass` | `SwiftUI-Glass.md` |
| `GlassEffectContainer` | 让相邻 Glass 视图**互相形变** | `SwiftUI-Glass.md` |

`clear` 的官方示例（`glass-clear.md`）：

```
Label("Flag", systemImage: "flag.fill")
    .padding()
    .glassEffect(.clear)
    .background(.black.opacity(0.3))
```

⚠️ **对本项目的直接约束**：App 里的**小栈的脸属于内容层** ⇒ 按 `IOS-MAT-02`，**脸不能用 Liquid Glass**，
否则就是官方明文禁止的做法。脸的载体只能是 solid / standard material。

---

## 六、颜色（`IOS-COL-*`）★ 含一处官方值订正

出处：`hig-md/color.md`（Specifications 段）

### 6.1 官方系统色（iOS 26，T1 —— 逐值抄录自 `color.md:225-243`）

| 名称 | SwiftUI API | 默认浅色 | 默认深色 | 高对比浅色 | 高对比深色 |
|---|---|---|---|---|---|
| Red | `Color.red` | R 255 G 56 B 60 | R 255 G 66 B 69 | R 233 G 21 B 45 | R 255 G 97 B 101 |
| Orange | `Color.orange` | R 255 G 141 B 40 | R 255 G 146 B 48 | R 197 G 83 B 0 | R 255 G 160 B 86 |
| Yellow | `Color.yellow` | R 255 G 204 B 0 | R 255 G 214 B 0 | R 161 G 106 B 0 | R 254 G 223 B 67 |
| Green | `Color.green` | R 52 G 199 B 89 | R 48 G 209 B 88 | R 0 G 137 B 50 | R 74 G 217 B 104 |
| Mint | `Color.mint` | R 0 G 200 B 179 | R 0 G 218 B 195 | R 0 G 133 B 117 | R 84 G 223 B 203 |
| Teal | `Color.teal` | R 0 G 195 B 208 | R 0 G 210 B 224 | R 0 G 129 B 152 | R 59 G 221 B 236 |
| Cyan | `Color.cyan` | R 0 G 192 B 232 | R 60 G 211 B 254 | R 0 G 126 B 174 | R 109 G 217 B 255 |
| **Blue** | `Color.blue` | **R 0 G 136 B 255** | **R 0 G 145 B 255** | R 30 G 110 B 244 | R 92 G 184 B 255 |
| Indigo | `Color.indigo` | R 97 G 85 B 245 | R 109 G 124 B 255 | R 86 G 74 B 222 | R 167 G 170 B 255 |
| Purple | `Color.purple` | R 203 G 48 B 224 | R 219 G 52 B 242 | R 176 G 47 B 194 | R 234 G 141 B 255 |
| Pink | `Color.pink` | R 255 G 45 B 85 | R 255 G 55 B 95 | R 231 G 18 B 77 | R 255 G 138 B 196 |
| Brown | `Color.brown` | R 172 G 127 B 94 | R 183 G 138 B 102 | R 149 G 109 B 81 | R 219 G 166 B 121 |

### 6.2 iOS 系统灰阶（T1 —— `color.md:244-256`）

| 名称 | UIKit API | 默认浅色 | 默认深色 | 高对比浅色 | 高对比深色 |
|---|---|---|---|---|---|
| systemGray | `UIColor.systemGray` | R 142 G 142 B 147 | R 142 G 142 B 147 | R 108 G 108 B 112 | R 174 G 174 B 178 |
| systemGray2 | `UIColor.systemGray2` | R 174 G 174 B 178 | R 99 G 99 B 102 | R 142 G 142 B 147 | R 124 G 124 B 128 |
| systemGray3 | `UIColor.systemGray3` | R 199 G 199 B 204 | R 72 G 72 B 74 | R 174 G 174 B 178 | R 84 G 84 B 86 |
| systemGray4 | `UIColor.systemGray4` | R 209 G 209 B 214 | R 58 G 58 B 60 | R 188 G 188 B 192 | R 68 G 68 B 70 |
| systemGray5 | `UIColor.systemGray5` | R 229 G 229 B 234 | R 44 G 44 B 46 | R 216 G 216 B 220 | R 54 G 54 B 56 |
| systemGray6 | `UIColor.systemGray6` | R 242 G 242 B 247 | R 28 G 28 B 30 | R 235 G 235 B 240 | R 36 G 36 B 38 |

### 6.3 ⛔ 订正：`systemBlue` 在 iOS 26 已经不是 `#007AFF`

| | 旧值（iOS 13–18 时代） | **官方 iOS 26 值（T1）** |
|---|---|---|
| 浅色 | `#007AFF`（R 0 G 122 B 255） | **`#0088FF`**（R 0 G 136 B 255） |
| 深色 | `#0A84FF`（R 10 G 132 B 255） | **`#0091FF`**（R 0 G 145 B 255） |

出处：`hig-md/color.md:225-243` Specifications → System colors → Blue 行。

⚠️ **本项目当前状态**：`prototype/ios/ios-light.html:27` 用 `--system-blue:#007AFF`，
`prototype/ios/ios-dark.html:27` 用 `#0A84FF` ⇒ **是 iOS 26 之前的旧值**，而我们的目标是 iOS 26 原生。
⇒ 已列为 `IOS-COL-03`，待 §十二 修判定器时一并订正。

### 6.4 官方颜色规则（`IOS-COL-*`）

| ID | 官方规则要点 | 出处 | 等级 |
|---|---|---|---|
| `IOS-COL-01` | ⛔ **不要硬编码系统色值**；用 `Color` API。文档里的数值仅供参考，**实际值可能随版本/环境变化** | `color.md:72` | T2 |
| `IOS-COL-02` | ⛔ **不要重新定义动态系统色的语义**（别拿 separator 当文字色、别拿 secondaryLabel 当背景色） | `color.md:76` | T2 |
| `IOS-COL-03` | iOS 26 `systemBlue` = `#0088FF` / `#0091FF`（见 §6.3） | `color.md:225-243` | **T1** |
| `IOS-COL-04` | Liquid Glass 默认**无固有颜色**，颜色从背后内容取；可以给 Glass 元素上色做强调 | `color.md:80` | T2 |
| `IOS-COL-05` | 小元素（toolbar / tab bar）上的 Liquid Glass 会在浅/深之间自适应；**符号和文字默认单色** | `color.md:88` | T2 |
| `IOS-COL-06` | **少给 Glass 上色**；强调主操作时**给背景上色，不给符号/文字上色**；不要给多个控件的背景都上色 | `color.md:92` | T2 |
| `IOS-COL-07` | 背景色彩丰富时，toolbar / tab bar 优先**单色**，或选差异足够的强调色 | `color.md:96` | T2 |
| `IOS-COL-08` | 关注**内容层里颜色的位置**；控件的静息状态也要保持清晰可读 | `color.md:102` | T2 |

⚠️ 注意 `IOS-COL-01` 与我们「强调色候选」的关系：候选 `#E3A857 / #9E3B26 / #B74332 / #AF4C37` 都是**自定义品牌色**，
不是系统色 ⇒ 不受 `IOS-COL-01` 约束，但**必须**满足 §八 的对比度与 `IOS-COL-02` 的语义边界。

---

## 七、字体：Dynamic Type 文字样式（`IOS-TYP-*`）★ 官方全表

出处：`hig-md/typography.md:185-240`「iOS, iPadOS Dynamic Type sizes」，**Large (default)** 档

| Style | Weight | Size (points) | Leading | Emphasized |
|---|---|---|---|---|
| Large Title | Regular | **34** | 41 | Bold |
| Title 1 | Regular | 28 | 34 | Bold |
| Title 2 | Regular | 22 | 28 | Bold |
| Title 3 | Regular | 20 | 25 | Semibold |
| Headline | Semibold | 17 | 22 | Semibold |
| **Body** | Regular | **17** | 22 | Semibold |
| Callout | Regular | 16 | 21 | Semibold |
| Subhead | Regular | 15 | 20 | Semibold |
| Footnote | Regular | 13 | 18 | Semibold |
| Caption 1 | Regular | 12 | 16 | Semibold |
| Caption 2 | Regular | 11 | 13 | Semibold |

其他档位（同一张表的上游档位，T1）：

| Style | xSmall | Small | Medium | Large(默认) |
|---|---|---|---|---|
| Large Title | 31 / 38 | 32 / 39 | 33 / 40 | 34 / 41 |
| Title 1 | 25 / 31 | 26 / 32 | 27 / 33 | 28 / 34 |
| Title 2 | 19 / 24 | 20 / 25 | 21 / 26 | 22 / 28 |
| Title 3 | 17 / 22 | 18 / 23 | 19 / 24 | 20 / 25 |
| Headline | 14 / 19 | 15 / 20 | 16 / 21 | 17 / 22 |
| Body | 14 / 19 | 15 / 20 | 16 / 21 | 17 / 22 |
| Callout | 13 / 18 | 14 / 19 | 15 / 20 | 16 / 21 |
| Subhead | 12 / 16 | 13 / 18 | 14 / 19 | 15 / 20 |
| Footnote | 12 / 16 | 12 / 16 | 12 / 16 | 13 / 18 |
| Caption 1 | 11 / 13 | 11 / 13 | 11 / 13 | 12 / 16 |
| Caption 2 | 11 / 13 | 11 / 13 | 11 / 13 | 11 / 13 |

（格式：字号 / 行高，单位 point）

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-TYP-01` | iOS/iPadOS 系统文字样式**默认 17pt、最小 11pt** | `accessibility.md:40` / `typography.md:26` | **T1** |
| `IOS-TYP-02` | 大标题 34pt / 行高 41（Default 档） | `typography.md` Large (default) 表 | **T1** |
| `IOS-TYP-03` | 正文 17pt / 行高 22；**Title 3 是 20pt 不是 17pt** | 同上 | **T1** |
| `IOS-TYP-04` | 界面必须支持文字**至少放大 200%** | `accessibility.md:34` | **T1** |
| `IOS-TYP-05` | 自定义字号要跟随平台推荐默认值；**细字重要放大字号**，粗字重更易读 | `accessibility.md:36` | T2 |
| `IOS-TYP-06` | 变量字体支持**光学尺寸（optical sizing）**，系统字体在每个字号动态调整字距 | `typography.md:66` | T2 |

⚠️ **对本项目的直接约束**：原型里 `--fs-tab:10px`（Tab 标签 10pt）**不是官方 Dynamic Type 文字样式** ——
Tab 标签是系统组件自带的小字，不是正文样式，不在 Dynamic Type 表里 ⇒ 它属于 **T4 自研设定**，且**不得写死字号**，
SwiftUI 里应交给 `.tabItem` / `Tab` 自动渲染。

---

## 八、无障碍（`IOS-A11Y-*`）

出处：`hig-md/accessibility.md`

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-A11Y-01` | **对比度下限**：≤17pt 文字 **4.5:1**；18pt 文字 **3:1**；**粗体**任意字号 **3:1** | `accessibility.md:60-62` | **T1** |
| `IOS-A11Y-02` | 默认达不到对比度时，必须在系统 **Increase Contrast** 开启时提供更高对比度方案；浅色深色**两种外观都要查** | `accessibility.md:64` | T2 |
| `IOS-A11Y-03` | **最小触控尺寸**：iOS/iPadOS **44×44 pt**（次要目标 28×28 pt） | `accessibility.md:135` | **T1** |
| `IOS-A11Y-04` | 触控目标周围留白：有 bezel 的元素约 **12pt**，无 bezel 约 **24pt** | `accessibility.md:141` | T2 |
| `IOS-A11Y-05` | 优先用**系统定义的颜色**（自带 accessible 变体，自动适配 Increase Contrast 与浅/深） | `accessibility.md:78` | T2 |
| `IOS-A11Y-06` | **不要只用颜色传递信息**，要配形状/图标等视觉指示 | `accessibility.md:88` | T2 |
| `IOS-A11Y-07` | 音频/视频的**关键信息不能只靠声音传达**，要给文字途径（字幕等） | `accessibility.md:110` | T2 |
| `IOS-A11Y-08` | 所有界面与内容都要为 **VoiceOver** 描述 | `accessibility.md:102` | T2 |
| `IOS-A11Y-09` | **Increase Contrast / Reduce Transparency** 等辅助设置会改变材质表现 ⇒ 材质选择必须考虑这些开关 | `materials.md:32` | T2 |

⚠️ 触控目标 44×44pt 与 §七 的 17pt 正文、§六 的 4.5:1 对比度是本项目**唯一三条 T1 级 iOS 数值硬指标**，
可直接进 CI 门禁（原型 HTML 也能查）。

---

## 九、SF Symbols（`IOS-SYM-*`）

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-SYM-01` | SF Symbols 数千个符号，与 SF 字体**自动对齐**（字重、字号） | `hig-md/sf-symbols.md` | T2 |
| `IOS-SYM-02` | Tab Bar 图标**优先 filled（实心）**符号 | `tab-bars.md:36` | T2 |
| `IOS-SYM-03` | 符号支持多图层（multilayer）与**四种渲染模式**（ monochrome / hierarchical / palette / multicolor） | `ios-docs/symbols.md` | T1 |
| `IOS-SYM-04` | 符号尺寸用 **point** 表达；`Image(systemName:)` 的 size 与 weight 会影响渲染 | `ios-docs/symbols.md` | T1 |
| `IOS-SYM-05` | 用 `SymbolEffect` 做符号动效（iOS 17+） | `ios-docs/symbols-symboleffect.md` | T1 |

⚠️ **原型现状**：22 个内联 SVG 是**手绘的 SF Symbols 风格**，不是真 SF Symbols。
SwiftUI 工程里必须用 `Image(systemName:)`（真 SF Symbols），**不得把 SVG 描进工程当图标**。
⇒ 判定器里 `sf_symbols_svg` 一项的语义是「风格一致」，不是「就是 SF Symbols」，已在 §十二 订正。

---

## 十、Live Activity / Widget（`IOS-WG-*`）

出处：`ios-docs/ActivityKit-*.md`、`ios-docs/widgetkit.md`、`hig-md/live-activities.md`、`hig-md/widgets.md`

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-WG-01` | Live Activity 显示在**锁屏、灵动岛、CarPlay、配对的 Mac/Apple Watch** | `ActivityKit-Displaying-live-data-with-Live-Activities.md` Overview | T1 |
| `IOS-WG-02` | Live Activity 基于 **WidgetKit**，实现是返回 `ActivityConfiguration` 的 widget | 同上 | T1 |
| `IOS-WG-03` | `ActivityAttributes` 描述 Live Activity 内容，内层 `ContentState` 表示**动态内容**；两者都 `Decodable, Encodable` | `ActivityKit-ActivityAttributes.md` | T1 |
| `IOS-WG-04` | 可以用 `typealias HeroStatus = ContentState` 起别名 | `ActivityKit-Displaying-live-data-with-Live-Activities.md` | T1 |
| `IOS-WG-05` | `WidgetCenter` 提供用户配置的 widget 信息（family 等） | `WidgetKit-WidgetCenter.md` | T1 |
| `IOS-WG-06` | `ActivityKit` / `WidgetKit` 需 iOS 16.1+（Live Activity 推送更新需 iOS 17.2+） | `ios-docs/ActivityKit-*.md` availability | T1 |

⇒ 本项目 `ios/StackChanCompanion/Features/LiveActivity/` 的存在是**符合平台原生方向**的（锁屏看小栈状态）。

---

## 十一、框架能力与权限（`IOS-API-*`）

### 11.1 WebSocket（连我们的云端）

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-API-01` | `URLSessionWebSocketTask` 是 `URLSessionTask` 的具体子类，走 **RFC 6455** WebSocket over TCP/TLS | `Y-Foundation-URLSessionWebSocketTask.md` | T1 |
| `IOS-API-02` | 用 `ws:` / `wss:` URL 创建；握手完成后经 session delegate 回调 | 同上 | T1 |
| `IOS-API-03` | 发送 `send(_:completionHandler:)`、接收 `receive(completionHandler:)`；支持**二进制帧与 UTF-8 文本帧** | 同上 | T1 |
| `IOS-API-04` | 握手完成前入队的读写会在握手完成后执行 | 同上 | T1 |

⇒ 我们的云端协议是 `[Type(1)][Length(4 BE)][Payload]` **二进制帧** ⇒ iOS 侧必须用**二进制帧**收发，
`URLSessionWebSocketTask.Message.data(...)`，不是 `.string(...)`。这是协议层的硬约束。

### 11.2 权限文案（Info.plist 键）

| 键 | 何时必需 | 出处 | 等级 |
|---|---|---|---|
| `NSBluetoothAlwaysUsageDescription` | App 使用设备蓝牙接口时**必需** | `Y-Bundleresources-...NSBluetoothAlwaysUsageDescription.md` | T1 |
| `NSMicrophoneUsageDescription` | 使用访问麦克风的 API 时**必需** | `Y-Bundleresources-...NSMicrophoneUsageDescription.md` | T1 |
| `NSLocalNetworkUsageDescription` | 直接或间接使用**局域网**（含 Bonjour、直连本地主机）时**应包含** | `Y-Bundleresources-...NSLocalNetworkUsageDescription.md` | T1 |
| `NSUserTrackingUsageDescription` | 只有使用 AppTrackingTransparency 时才需要 | `Y-Bundleresources-...NSUserTrackingUsageDescription.md` | T1 |

⚠️ **漏任何一个 ⇒ App Store 审核直接拒**。本项目三条都要用到：
BLE（蓝牙）、语音输入（麦克风）、局域网直连（可选通道）。

### 11.3 其它框架

| 框架 | 用途 | 出处 | 等级 |
|---|---|---|---|
| `CoreBluetooth` | `CBCentralManager` / `CBCentralManagerDelegate` / `CBCentralManagerState` —— 设备 BLE 直连 | `X-CoreBluetooth.md:50/54/184` | T1 |
| `Speech` | `SFSpeechRecognizer` + `SFSpeechAudioBufferRecognitionRequest` —— 语音输入 | `Speech.md`、`Speech-SFSpeechAudioBufferRecognitionRequest.md` | T1 |
| `AVFoundation` | 音频会话/播放 | `AVFoundation-AVCaptureSession.md` | T1 |
| `CoreHaptics` | 触感反馈 | `CoreHaptics-*.md` | T1 |
| `BackgroundTasks` | 后台任务 | `BackgroundTasks.md` | T1 |
| `SwiftUI.Canvas` | 画动态 2D 图形（**App 里的脸**的技术选项） | `X-SwiftUI-Canvas.md` | T1 |
| `SpeechAnalyzer` / `SpeechTranscriber` | 新的语音管线（iOS 26） | `ios-fetch/speechanalyzer.md` / `speechtranscriber.md` | T1 |

### 11.4 ⭐ 语音识别与音频会话（2026-10-25 补充取证，T1）

> 来源：`docs/research/apple-docs-evidence/03-haptics-speech.md`（DeepSeek 员工取证档案，**我已逐条回源抽验 8 条全部命中**）。
> 原始档案含完整事实表（A2，45 条）、逐问答复、**官方未给数值清单**、**缓存未覆盖项**、以及**逐条引用行号复核节（G）**。

#### 11.4.1 识别 API 的分流规则（T1）

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-SPK-01` | 框架职责：对**实时或预录**音频做识别，产出转写 / 备选 / 置信度 | `ios-docs/Speech.md:28` | T1 |
| `IOS-SPK-02` | **文件 vs 实时**的分流点：`SFSpeechURLRecognitionRequest`（文件）/ `SFSpeechAudioBufferRecognitionRequest`（音频流） | `ios-docs/Speech-SFSpeechRecognizer.md:55` | T1 |
| `IOS-SPK-03` | 实时录音必须显式调 `endAudio()` 才停止识别，**不会自动停** | `ios-docs/Speech-SFSpeechAudioBufferRecognitionRequest.md:38` | T1 |
| `IOS-SPK-04` | 喂音频三签名：`append(AVAudioPCMBuffer)` / `appendAudioSampleBuffer(CMSampleBuffer)` / `endAudio()` | 同上 `:46`、`:50`、`:54` | T1 |
| `IOS-SPK-05` | `nativeAudioFormat` 给出「最佳识别音频格式」 | 同上 `:60` | T1 |
| `IOS-SPK-06` | 起任务五步：授权 → 建 recognizer → 查 `isAvailable` → 备音频 → 建 request → `recognitionTask` | `ios-docs/Speech-SFSpeechRecognizer.md:48-53` | T1 |
| `IOS-SPK-07` | ⭐ **官方明文数值：识别任务超过 1 分钟会被框架停止** | `ios-docs/Speech-SFSpeechRecognizer.md:62` | T1 |
| `IOS-SPK-08` | `finish()` = 停收新音频、把已收的跑完；`cancel()` = 立即取消（**语义不同**） | `ios-docs/Z-Speech-SFSpeechRecognitionTask.md:54`、`:44` | T1 |
| `IOS-SPK-09` | 创建成功 ≠ 服务可用；`isAvailable` 是独立属性 | `ios-docs/Speech-SFSpeechRecognizer.md:88` | T1 |
| `IOS-SPK-10` | `supportsOnDeviceRecognition` = 该 recognizer **能否无网络运行**（只读能力位，**不是开关**） | `ios-docs/Speech-SFSpeechRecognizer.md:92` | T1 |
| `IOS-SPK-11` | 权限 API：`requestAuthorization((SFSpeechRecognizerAuthorizationStatus) -> Void)` / `authorizationStatus()` | 同上 `:98`、`:102` | T1 |

**⇒ 对本项目的直接约束**：
1. **「按住说话」不可能无限长** —— 官方 1 分钟硬上限（`IOS-SPK-07`）。产品上必须给按住说话设更短的上限（建议 30 s），
   否则用户会撞到「静默失败」（识别被框架掐掉但 App 没提示）。
2. **松开麦克风按钮时必须显式 `endAudio()`**（`IOS-SPK-03`）—— 不调就是识别一直跑，耗电且后台被拒。
3. **`finish()` ≠ `cancel()`**（`IOS-SPK-08`）：用户「说完」= `finish()`；用户「取消这次说话」= `cancel()`。

#### 11.4.2 iOS 26 新语音管线（`SpeechAnalyzer` / `SpeechTranscriber`）

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-SPK-20` | `SpeechAnalyzer` / `SpeechTranscriber` 均**自 iOS 26.0.0 起**可用 | `ios-fetch/speechanalyzer.md:4`、`speechtranscriber.md:4` | T1 |
| `IOS-SPK-21` | `SpeechAnalyzer` 是 **`final actor`**（并发语义由 actor 保证）；`SpeechTranscriber` 是 `final class` | 同上 `:32` | T1 |
| `IOS-SPK-22` | 同一时刻**只能分析一路输入序列** | 同上 `:52` | T1 |
| `IOS-SPK-23` | 输入/输出/会话控制解耦，走 `AsyncSequence`（取代 delegate 模式） | 同上 `:50` | T1 |
| `IOS-SPK-24` | 同时分析数有「保守上限」，**官方不给数字**；超限抛 `insufficientResources`，可用 `ignoresResourceLimits` 解除 | 同上 `:206`、`:210` | T1/T2 |
| `IOS-SPK-25` | `prepareToAnalyze(in:)` 可预热以**减少首个结果延迟** | 同上 `:178` | T2 |
| `IOS-SPK-26` | 结束方法三选一：`finalizeAndFinish(through:)` / `cancelAndFinishNow()` / `finalizeAndFinishThroughEndOfInput()` | 同上 `:284`、`:276`、`:280` | T1 |
| `IOS-SPK-27` | `installedLocales`（已装）vs `supportedLocales`（含**可下载**）—— 语言资产需显式安装 | `ios-fetch/speechtranscriber.md:83`、`:87` | T1 |

⚠️ **一处必须记录、不可调和掉的官方事实张力**：`ios-docs/Speech.md` 的**框架级** availability 写 `iOS: 10.0.0 -`（`Speech.md:4`），
但 `SpeechAnalyzer` / `SpeechTranscriber` **各自页面**写 `iOS: 26.0.0 -`。
⇒ **引用时以具体类型页为准**：新架构 = iOS 26+；旧 `SFSpeechRecognizer` = iOS 10+。

⇒ **对本项目的取舍**：本项目 iOS 目标 **17.0**（见 `ios/project.yml`）⇒ **不能依赖 `SpeechAnalyzer`**。
`IOS-SPK-25` 的「预热减首延迟」在新架构上可用，但与我们无关。

#### 11.4.3 音频会话（`AVAudioSession`）—— 官方**未给** API 的部分

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-AUD-01` | 必须选一个符合用法的 audio category | `hig-md/playing-audio.md:36` | T2 |
| `IOS-AUD-02` | `Record`：不响应静音开关、不混音、可后台录音 | `hig-md/playing-audio.md:43` | T1 |
| `IOS-AUD-03` | `Play and record`：**可同时录放**、可后台 | `hig-md/playing-audio.md:44` | T1 |
| `IOS-AUD-04` | 打断分 **resumable**（来电）/ **nonresumable**（用户开了新歌单），据类型决定是否自动恢复 | `hig-md/playing-audio.md:60` | T2 |
| `IOS-AUD-05` | 临时打断他人音频时要用 `notifyOthersOnDeactivation` 让对方知道何时可恢复 | `hig-md/playing-audio.md:52` | T2 |
| `IOS-AUD-06` | Core Haptics 引擎可能因来电/通知停止 ⇒ 通话结束后需重启 | `ios-docs/CoreHaptics-preparing-your-app-to-play-haptics.md:99-101` | T1 |

**⇒ 对本项目的直接约束**：本项目「按住说话」= 麦克风采集 ⇒ audio category 官方对应项是
**`Play and record`**（`IOS-AUD-03`，边听边录、可后台）；若某阶段只录不放则退到 `Record`（`IOS-AUD-02`）。
⚠️ **`AVAudioSession` 本身在官方缓存里没有独立文档页**（`setCategory` / `playAndRecord` / `HFP` / `routeChange` 全部 0 命中）
⇒ 本文**不写 `AVAudioSession` 的具体 API**，只写 HIG 明文的行为规则。

#### 11.4.4 触感（CoreHaptics / `UIFeedbackGenerator`）

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-HAP-01` | `UIFeedbackGenerator` 是抽象父类，**禁止自行子类化/实例化**；具体子类 4 个（selection / notification / impact / canvas） | `ios-fetch/uifeedbackgenerator.md:34`、`:36-39` | T1 |
| `IOS-HAP-02` | `UIImpactFeedbackGenerator.FeedbackStyle` 语义 = **碰撞物体的质量** | `ios-fetch/uiimpactfeedbackgenerator.md:93` | T1 |
| `IOS-HAP-03` | 可用 `impactOccurred(intensity:at:)` 指定强度与位置 | 同上 `:113` | T1 |
| `IOS-HAP-04` | SwiftUI `SensoryFeedback` 是独立类型（iOS 17 起），经 `View.sensoryFeedback` 使用 | `ios-fetch/sensoryfeedback.md:4`、`:38` | T1 |
| `IOS-HAP-05` | AHAP 参数值统一归一化到 **0–1**；越界值会被**钳制**到最接近的边界 | `ios-docs/Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:65`、`:22` | T1 |
| `IOS-HAP-06` | 触感**必须可关闭**；要与视觉/听觉一致；不要滥用 | `hig-md/playing-haptics.md:39`、`:33`、`:35` | T2 |
| `IOS-HAP-07` | 不支持触感的设备：iPad、iPod touch、Apple Vision Pro（用 `capabilitiesForHardware.supportsHaptics` 查） | `ios-docs/CoreHaptics-preparing-your-app-to-play-haptics.md:25`、`:33` | T1 |
| `IOS-HAP-08` | 主动 `stop()` **不会**触发 stoppedHandler，只走 stop 的 completion | `ios-docs/hapticengine.md:126` | T1 |

#### 11.4.5 BackgroundTasks / AppIntents / Spotlight

| ID | 事实 | 出处 | 等级 |
|---|---|---|---|
| `IOS-BG-01` | 后台任务的具体类型与调度规则 | `ios-docs/BackgroundTasks.md` | T1 |
| `IOS-AI-01` | AppIntents / Shortcuts / Spotlight 的可用能力面 | `ios-docs/AppIntents.md` 等 | T1 |

（完整事实表 23 + 43 条见 `docs/research/apple-docs-evidence/04-background-appintents.md`。）

---

## 十二、⛔ 对 `prototype/ios/check_ios.py` 登记表订正（9 条数值出处）

本轮逐条核对后，`check_ios.py` 的 `IOS_VALUES` 表里 **7 条「官方出处」指向 HIG 正文中并不存在的内容**。
这正是本项目自己的教训（登记表标签必须与真实输入一致）。订正如下：

| # | 原登记出处 | 核对结果 | 订正后出处等级 | 处置 |
|---|---|---|---|---|
| 1 | 「HIG hig-tabbars.json：Tab bar floats above content」→ 12px | HIG 只说「floating」，**没有 12px** | **T4 自研设定** | 改标签为「自研：左右 12px 浮动边距（对齐官方 App 观感）」 |
| 2 | 「iOS 26 Liquid Glass 连续曲率」→ 26px 圆角 | HIG **未给数值** | **T4 自研设定** | 改标签为「自研：26px 圆角（连续曲率观感）」 |
| 3 | 「HIG：floating tab bar」→ 高 56px | HIG 的 68pt 是 **tvOS**，iOS 无此数值 | **T4 自研设定** | 改标签为「自研：56px（官方 App 实测观感）」 |
| 4 | 「research/08 号：chevron 7~8 × 13~14pt」→ 8×14 | 08 号**自述为像素估算** | **T4 自研设定** | 改标签为「自研：chevron 8×14（照 SF Symbols 描摹）」 |
| 5 | 「HIG Controls：UISwitch 51×31pt」 | **HIG 正文查不到**；`toggles.md` 只说 mini switch 高度与按钮相当 | **T4 自研设定** | 改标签为「自研：51×31（UISwitch 观感）」 |
| 6 | 「HIG Lists：separator 0.5pt」 | HIG 正文查不到 | **T4 自研设定** | 改标签为「自研：0.5px 分割线」 |
| 7 | 「HIG Lists：inset grouped 10~12pt」 | HIG 正文查不到 | **T4 自研设定** | 改标签为「自研：--r-group 11px」 |
| 8 | 「Apple 系统语义色 systemBlue」→ `#007AFF`/`#0A84FF` | 那是 iOS 13–18 的值 | **T1 官方 iOS 26 值**（`color.md:225-243`） | 改为 `#0088FF` / `#0091FF` |
| 9 | 「HIG：tab label 10pt」 | HIG 正文查不到；Tab 标签不是 Dynamic Type 样式 | **T4 自研设定** | 改标签为「自研：Tab 标签 10px」 |

**结论**：9 条里 **8 条是自研设定**、**1 条是官方值但我们用错了版本**。
⇒ 本项目**没有任何一条 iOS 布局数值是 Apple 官方给死的** —— 这不是缺陷，是事实，
但**必须在文档里写清楚**，否则就是「拿自研值冒充官方值」，正是本项目要避免的失分点。

真正能当官方硬指标用的只有 **T1 的三条 iOS 数值**：

| 指标 | 官方值 | 出处 | 可否进 CI 门禁 |
|---|---|---|---|
| 触控目标 | **44×44 pt** | `accessibility.md:135` | ✅ 可 |
| 正文对比度 | **4.5:1**（≤17pt） | `accessibility.md:60` | ✅ 可 |
| 正文字号 | **17pt**（最小 11pt） | `accessibility.md:40` | ✅ 可（原型 px ↔ pt 1:1） |

---

## 十三、数值总表（官方 / 实测 / 自研 三分）

| 数值 | 值 | 等级 | 出处 |
|---|---|---|---|
| 触控目标 | 44×44 pt | **T1** | `accessibility.md:135` |
| 正文对比度下限 | 4.5:1 | **T1** | `accessibility.md:60` |
| 加大字号对比度下限 | 3:1 | **T1** | `accessibility.md:61` |
| 粗体对比度下限 | 3:1 | **T1** | `accessibility.md:62` |
| 正文默认字号 | 17 pt（最小 11 pt） | **T1** | `accessibility.md:40` |
| 大标题 | 34 pt / 41 | **T1** | `typography.md` Large(default) |
| Title 1 / 2 / 3 | 28 / 22 / 20 pt | **T1** | 同上 |
| Headline / Callout / Subhead | 17 / 16 / 15 pt | **T1** | 同上 |
| Footnote / Caption 1 / Caption 2 | 13 / 12 / 11 pt | **T1** | 同上 |
| systemBlue 浅 / 深 | `#0088FF` / `#0091FF` | **T1** | `color.md:225-243` |
| systemGreen 浅 / 深 | R52G199B89 / R48G209B88 | **T1** | 同上 |
| systemGray6 浅 / 深 | R242G242B247 / R28G28B30 | **T1** | `color.md:244-256` |
| 文字放大倍数 | ≥200% | **T1** | `accessibility.md:34` |
| tvOS Tab Bar 高 | 68 pt（**非 iOS**） | T1（但平台不匹配） | `tab-bars.md:101` |
| Tab Bar 浮动边距 / 高 / 圆角 | 12 / 56 / 26 px | **T4 自研** | 本项目设定 |
| Inset Grouped 组圆角 | 11 px | **T4 自研** | 本项目设定 |
| 分割线 | 0.5 px | **T4 自研** | 本项目设定 |
| 行高 | 44 px（对齐 T1 触控目标） | T4（受 T1 约束） | 本项目设定 |
| UISwitch | 51×31 px | **T4 自研** | 本项目设定 |
| Tab 标签字号 | 10 px | **T4 自研** | 本项目设定 |
| chevron | 8×14 | **T4 自研** | 本项目设定 |

---

## 十四、边界声明

1. 本文的 T1 数值**只来自 Apple 官方文档正文**；凡官方只给规则不给数值的，本文明确写「HIG 未给数值」。
2. **Apple HIG 正文不是完整规格书**：完整数值在 Apple Design Resources（Figma/Sketch 模板）里，
   本轮未下载模板 ⇒ 若将来要把某个数值升为 T1，需先取模板或从系统实测。
   —— ⚠️ **2026-10-27 更新**：取模板的**通路已具备**（用户已接入 Figma Connector，2 个只读工具），
   但**本轮实测 10 次调用未读到 Apple 官方社区套件**（`figma_not_found` ＝ 当前账号看不到社区文件，
   需账号内显式授权）⇒ **本文没有任何数值被升为 T1**，相关未验证项见 `docs/research/89` §2 与
   `docs/research/06` 的 **U2（仍未销账）**。
3. 本文**不改任何产品决策**：配色、强调色、脸怎么画已是 `docs/spec/07` §3.1b/§3.3/§3.4 的**已拍板项**；
   仍待拍板的是 §3.5 的其余清单（音频承载方式 Q10、二级页 Tab Bar Q11 等）。
4. 本文所有 API 事实**只做了文档级核实**，本机无 Swift 工具链 ⇒ **未编译验证**。
5. `IOS-TAB-02` 与官方 App 实现冲突，见 §2.1，已转 `docs/spec/07` 待拍板。
6. **§11.4 的取证来自 DeepSeek 员工档案，但由我逐条回源抽验**（语音 8 条 + 触感 6 条 = 14 条，全部命中且引文与断言一致）。
   原始档案（含未命中项、官方未给数值清单、逐条复核节）存 `docs/research/apple-docs-evidence/`，
   **未抽验的部分按「员工产出、未独立验证」对待**，不直接当 T1 用。

---

## 十五、2026-10-25 补充：语音与音频的**可执行约束**（本文的落地摘要）

> 这一节是 §11.4 的**行动摘要**，供实现时直接对照。全部 T1，出处见 §11.4。

| # | 约束 | 依据 | 影响 |
|---|---|---|---|
| 1 | **按住说话必须设上限**（建议 30 s，硬上限 60 s） | `IOS-SPK-07` 官方 1 分钟停止 | 不设限 = 用户撞静默失败 |
| 2 | **松开按钮必须显式 `endAudio()`** | `IOS-SPK-03` | 不调 = 识别不停、耗电、后台被拒 |
| 3 | **「说完」用 `finish()`，「取消」用 `cancel()`** | `IOS-SPK-08` | 语义不同，不能混用 |
| 4 | **必须查 `isAvailable`**（创建成功 ≠ 可用） | `IOS-SPK-09` | 否则识别静默不启动 |
| 5 | **audio category 用 `Play and record`** | `IOS-AUD-03` | 边听边录 + 可后台 |
| 6 | **iOS 17 目标 ⇒ 不能依赖 `SpeechAnalyzer`** | `IOS-SPK-20` vs `ios/project.yml` 目标 17.0 | 新管线只能作 iOS 26 增强层 |
| 7 | **触感必须可关闭** | `IOS-HAP-06` | 设置页要给开关 |
| 8 | **触感参数会被钳制到 0–1** | `IOS-HAP-05` | 别写超界值 |

---
