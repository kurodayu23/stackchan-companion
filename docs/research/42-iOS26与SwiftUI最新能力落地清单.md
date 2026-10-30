# 42 · iOS 26 / SwiftUI 最新能力落地清单

> **取证日期**：2026-10-23
> **取证方式**：① Apple 官方文档 `.md` 纯文本端点（`https://developer.apple.com/documentation/<path>.md`）；② HIG 官方 JSON 数据端点（`https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<slug>.json`）；③ 本机既有缓存 `D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs\`（166 份 Apple 文档原文）。全部条目均取自官方原文，未取到的一律标注「未取得」。
> **来源标注**：`[Apple 官方文档原文]` = 直接引用 Apple 文档/HIG 正文；`[我的推断]` = 基于原文的工程推断，非 Apple 承诺。
> **适配对象**：StackChan iOS App（SwiftUI，陪伴聊天型，2 Tab + 独立设置 Scene，设备端 320×240 屏）。

---

## §一 结论摘要

| # | 能做什么 | 对我们的意义 | 成本 |
|---|---|---|---|
| 1 | **官方明文禁止在内容层用 Liquid Glass**：「Don't use Liquid Glass in the content layer.」 | **我们已定的「玻璃只给导航与浮层、内容层不用」策略与 Apple 官方 guidance 完全一致，且是原文级背书，不是审美偏好**。这条可以直接写进设计文档当依据 | 低（只是不改代码） |
| 2 | 标准系统组件（`TabView` / `NavigationStack` / `toolbar` / `sheet` / `Menu`）**自动继承玻璃**，不需要手写 `glassEffect` | 「交付感」的大头来自「用对系统组件」，不是自己画玻璃。我们只要不写自定义背景去覆盖它就有 80% 效果 | 低 |
| 3 | `glassEffect(_:in:)` / `GlassEffectContainer` / `.buttonStyle(.glass)` 均需 **iOS 26.0+**；容器默认形状是 `Capsule` | 我们的 App 若要支持 iOS 17/18，这些 API 全部要 `if #available(iOS 26, *)` 包起来；建议**直接不做自定义玻璃**，把成本降到 0 | 低 |
| 4 | `.sensoryFeedback(_:trigger:)`（**iOS 17+**）用**声明式**触发触感，可精确绑定到状态变化 | 「一次交互最多 1 次触感」红线**可以用一行修饰符达成**，不需要自己管 UIKit generator 生命周期 | 极低 |
| 5 | `SensoryFeedback` 内置 **12 个静态语义**（start / stop / alignment / decrease / increase / levelChange / selection / pathComplete / success / warning / error / impact，其中 `impact` 另有 `weight:` 与 `flexibility:` 两个带力度参数的重载） | 我们可以把「陪伴」的触感语义**定死成一套映射表**（比如：选中=selection、发消息成功=success、小栈说话=impact(weight:.soft)），天然满足「一次一触」 | 低 |
| 6 | ActivityKit 新增 `ActivityStyle.transient`（**iOS 26**），Live Activity 可只在灵动岛扩展区短暂存在，锁屏/收起即结束 | 完美匹配「小栈思考中」这种**短时状态**，比常驻 Live Activity 省电得多，也不会在锁屏堆积 | 中 |
| 7 | Live Activity **4 KB 数据上限 + 8 小时活动上限 + 12 小时锁屏上限**，且 Live Activity **无网络权限** | 我们的「小栈当前状态」Live Activity **必须只放状态词**（监听中/思考中/说话中/等你回来/离线），绝不能放对话内容——正好和我们的「不显示敏感内容」红线一致 | 低 |
| 8 | App Intents + `AppShortcut` + `AppShortcutsProvider` 可让 **Siri / 快捷指令 / Spotlight 直接调 App Intent** | 「Hey Siri，让小栈过来」作为演示点**技术上完全成立**，且 App Shortcut 装 App 即生效、**不需要注册** | 中 |
| 9 | `SpeechAnalyzer` / `SpeechTranscriber`（**iOS 26 全新 Speech 框架**）做**端侧**语音转写 | 陪伴场景要「说话给小栈听」；新 API 是端侧推理（`SpeechTranscriber` 是本地模块），**隐私叙事更好**（旧 `SFSpeechRecognizer` 的端云行为本次未取证，见 §9.1） | 中高（全新 API 学习曲线） |
| 10 | **Foundation Models** 框架（iOS 26）提供端侧 LLM：`LanguageModelSession`、`@Generable` 结构化输出、`Tool` 工具调用、PCC 私有云端 | 如果陪伴对话要本地兜底/润色，端侧模型入口系统已给；但**需要 Apple Intelligence 支持设备**，国内用户机型覆盖要评估 | 高 |
| 11 | `onScrollGeometryChange(for:of:action:)`（**iOS 18**）+ `ScrollEdgeEffectStyle`（**iOS 26**，`automatic`/`hard`/`soft`）+ `scrollEdgeEffectHidden` | 对话流滚动时，顶部/底部栏的**可读性由系统保证**，我们不用自己做渐隐遮罩，也不用自绘背景盖住玻璃 | 低 |
| 12 | `Tab(role: .search)`（iOS 26 起 `TabRole` 体系）、`tabBarMinimizeBehavior(_:)`（iOS 26）、`TabView` 支持 `TabSection` 分组、`tabViewCustomization(_:)` | 两个 Tab（陪伴/小栈）**不需要任何定制**即得标准 iOS 质感；`TabRole.prominent`（iOS 26.x）可把「小栈」做成尾部独立区，但**我们 Tab 只有 2 个，不该用** | 低 |

> 成本口径：**低** = 半天内可落地；**中** = 1–2 天；**高** = 需专门设计与联调。

---

## §二 Liquid Glass：边界与正确用法（含官方原文）

### 2.1 官方 guidance 原文（逐条引用）

**来源 A — Apple HIG「Materials」**（`[Apple 官方文档原文]`，源：`developer.apple.com/design/human-interface-guidelines/materials`，该页 `metadata.customMetadata` 标注 `alert-date: 2025-09-09`、`alert-text: "Updated guidance for Liquid Glass."`）：

> **"Don't use Liquid Glass in the content layer.** Liquid Glass works best when it provides a clear distinction between interactive elements and content, and including it in the content layer can result in unnecessary complexity and a confusing visual hierarchy. Instead, use (standard materials) for elements in the content layer, such as app backgrounds. An exception to this is for controls in the content layer with a transient interactive element like (sliders) and (toggles); in these cases, the element takes on a Liquid Glass appearance to emphasize its interactivity when a person activates it."

> **"Use Liquid Glass effects sparingly.** Standard components from system frameworks pick up the appearance and behavior of this material automatically. If you apply Liquid Glass effects to a custom control, do so sparingly. Liquid Glass seeks to bring attention to the underlying content, and overusing this material in multiple custom controls can provide a subpar user experience by distracting from that content. **Limit these effects to the most important functional elements in your app.** For developer guidance, see (Applying Liquid Glass to custom views)."

> "Liquid Glass forms a distinct functional layer for controls and navigation elements — like tab bars and sidebars — that floats above the content layer, establishing a clear visual hierarchy between functional elements and content."

> "Only use clear Liquid Glass for components that appear over visually rich backgrounds. … The **regular** variant blurs and adjusts the luminosity of background content to maintain legibility of text and other foreground elements. … Use the regular variant when background content might create legibility issues, or when components have a significant amount of text, such as alerts, sidebars, or popovers."

> "The **clear** variant is highly translucent, which is ideal for prioritizing the visibility of the underlying content … Use this variant for components that float above media backgrounds — such as photos and videos … For optimal contrast and legibility, determine whether to add a dimming layer behind components with clear Liquid Glass: If the underlying content is bright, consider adding a **dark dimming layer of 35% opacity**."

**来源 B — Apple 官方技术总览「Adopting Liquid Glass」**（`[Apple 官方文档原文]`，源：`https://developer.apple.com/documentation/TechnologyOverviews/adopting-liquid-glass`）：

> "**Leverage system frameworks to adopt Liquid Glass automatically.** In system frameworks, standard components like bars, sheets, popovers, and controls automatically adopt this material."

> "**Reduce your use of custom backgrounds in controls and navigation elements.** Any custom backgrounds and appearances you use in these elements might overlay or interfere with Liquid Glass or other effects that the system provides, such as the scroll edge effect. Make sure to check any custom backgrounds in elements like split views, tab bars, and toolbars. **Prefer to remove custom effects and let the system determine the background appearance.**"

> "**Avoid overusing Liquid Glass effects.** … Limit these effects to the most important functional elements in your app."

> "**Combine custom Liquid Glass effects to improve rendering performance.** If you apply these effects to custom elements, make sure to combine them using a (GlassEffectContainer), which helps optimize performance while fluidly morphing Liquid Glass shapes into each other."

> "**Test your interface with a variety of display and accessibility settings.** … people can choose a preferred look for Liquid Glass in their device's settings, or turn on accessibility settings that reduce transparency or motion in the interface. These settings can remove or modify certain effects."

> "To update and ship your app with the latest SDKs while keeping your app as it looks when built against previous versions of the SDKs, you can add the (UIDesignRequiresCompatibility) key to your project's Info pane."

**来源 C — SwiftUI「Applying Liquid Glass to custom views」**（`[Apple 官方文档原文]`，源：`https://developer.apple.com/documentation/swiftui/applying-liquid-glass-to-custom-views`）：

> "Creating too many Liquid Glass effect containers and applying too many effects to views outside of containers can degrade performance. **Limit the use of Liquid Glass effects onscreen at the same time.**"

> "The `glassEffect(_:in:)` modifier captures the content to send to the container to render. **Apply the `glassEffect(_:in:)` modifier after other modifiers that affect the appearance of the view.**"

> "A spacing value on the container that's larger than the spacing of an interior HStack, VStack, or other layout container causes Liquid Glass effects to blend together at rest because the views are too close to each other."

### 2.2 对我们既定策略的核实结论

**我们已决定：「玻璃只给导航与浮层，内容层不用」。→ 判定：✅ 正确，且是 Apple 原文直接支持的策略。**

逐条对齐：

| 我们的红线 | Apple 原文 | 判定 |
|---|---|---|
| 玻璃只给导航与浮层 | "Don't use Liquid Glass in the content layer." | ✅ 逐字一致 |
| 内容层不用玻璃 | "Instead, use standard materials for elements in the content layer, such as app backgrounds." | ✅ 内容层应走 `Material`（ultraThin/thin/regular/thick）而非 Liquid Glass |
| 一级元素 ≤ 12 / Tab ≤ 5 个 | "Limit these effects to the most important functional elements in your app." | ✅ 元素少 → 玻璃面少 → 视觉层级天然成立 |
| 一次交互最多 1 次触感（玻璃的 interactive 反馈也要克制） | "overusing this material in multiple custom controls can provide a subpar user experience" | ✅ 玻璃自带 interactive 形变，触感再叠加就会过量 |

**但有 3 处必须注意的「例外条款」（会被我们踩到）：**

1. **Tab 栏 / 侧栏本身自动就是玻璃** —— HIG 原文："Key navigation elements like tab bars and sidebars float in this Liquid Glass layer to help people focus on the underlying content." 这**不是我们主动"用"玻璃**，是系统给的，我们的策略不应去覆盖它。
2. **Slider / Toggle 这类"瞬时交互元素"在内容层可以用玻璃** —— HIG 原文给了明确例外："An exception to this is for controls in the content layer with a transient interactive element like sliders and toggles"。如果设置页里有滑动条，可以用玻璃质感；**这是 Apple 认可的，不违反我们的红线**。
3. **自定义背景会遮挡/干扰玻璃** —— 这是最容易犯的错：如果我们给 TabView 或 NavigationStack 加了自定义 `background`，玻璃和 scroll edge effect 都会失效，质感立刻塌掉。**结论：我们不要写任何自定义导航背景。**

### 2.3 API 形态与系统版本下限（全部实测自 Apple 文档 availability 字段）

| API | 官方签名（原文） | iOS 最低版本 |
|---|---|---|
| `Glass` 结构 | `struct Glass`（`.regular` / `.clear` / `.identity`；`tint(Color?)`；`interactive(Bool)`） | **26.0+** |
| `View.glassEffect(_:in:)` | `nonisolated func glassEffect(_ glass: Glass = .regular, in shape: some Shape = DefaultGlassEffectShape()) -> some View` | **26.0+** |
| `GlassEffectContainer` | `init(spacing: CGFloat?, content: () -> Content)` | **26.0+** |
| `Glass.interactive(_:)` | `func interactive(_ isEnabled: Bool = true) -> Glass` | **26.0+** |
| `PrimitiveButtonStyle.glass` | `@export(implementation) nonisolated static var glass: GlassButtonStyle { get }` | **26.0+** |
| `PrimitiveButtonStyle.glassProminent` | 官方在 Adopting Liquid Glass 中列出 | 26.0+ `[Apple 官方文档原文]`（未单独抓取该符号页） |
| `PrimitiveButtonStyle.glass(_:)` | 官方在 Adopting Liquid Glass 中列出 | 26.0+ `[Apple 官方文档原文]`（未单独抓取该符号页） |
| `GlassEffectTransition` / `.matchedGeometry` / `.materialize` | 官方在 Applying Liquid Glass 中列出 | 26.0+ `[Apple 官方文档原文]` |
| `View.glassEffectUnion(id:namespace:)` / `View.glassEffectID(_:in:)` | 官方在 Applying Liquid Glass 中列出 | 26.0+ `[Apple 官方文档原文]` |
| `UIKit.UIGlassEffect` | 官方在 Adopting Liquid Glass 中列出 | 26.0+ `[Apple 官方文档原文]`（未单独抓取该符号页） |

**关键默认值（会影响我们的实现）：**
- `glassEffect()` **默认形状是 `Capsule`**（原文："SwiftUI uses the `regular` variant by default along with a `Capsule` shape."）。所以对我们这种非胶囊形的自定义控件，**必须显式给 `in:` 参数**，否则形状会出错。
- `glassEffect()` **默认 `.regular`**（有字、对比度需要保障时用 `.regular`；只在媒体背景上浮才用 `.clear`）。
- `Glass.identity`：「The identity variant of glass. When applied, your content remains unaffected as if no glass effect was applied.」——**这是我们做降级/开关的官方姿势**：给用户一个「关闭玻璃」开关时，套 `.glassEffect(.identity)` 而不是硬编码路径。

**我们的落地建议 `[我的推断]`：**
> **不在业务代码里写 `glassEffect` / `GlassEffectContainer` / `.buttonStyle(.glass)`。** 理由：(1) 官方说标准组件自动继承玻璃；(2) 官方说自定义玻璃要"sparely"、要"限制同屏数量"；(3) 我们的内容层是长对话流（滚动文字），玻璃压在上面会直接损害可读性——HIG 明确玻璃属于"navigation layer"，对话流属于"content layer"。导航与浮层（Tab 栏、设置 sheet、输入框上方的浮条）交给系统自动获得玻璃即可。
> 唯一可能需要自定义玻璃的场景：**「小栈」Tab 顶部的 3D 姿态预览卡片**——但那是内容层，仍应不用玻璃；应改用 `Material.regular` + 分隔。
> 若未来一定要做「两个 Tab 的选中态之间做玻璃形变」，用 `GlassEffectContainer(spacing:)` + `glassEffectID` + `GlassEffectTransition.matchedGeometry`，且**容器 spacing 必须 ≤ 内部布局 spacing**，否则静止状态就会互相融合（原文明确警告）。

---

## §三 SwiftUI 新能力清单

> 版本号全部来自 Apple 文档 availability 字段实测，非记忆。

### 3.1 总表

| API | 用途 | 可用系统版本 | 我们的落点 |
|---|---|---|---|
| `View.glassEffect(_:in:)` | 给自定义视图加 Liquid Glass | **iOS 26.0+** | ❌ **不用于内容层**。仅在确有必要时给「浮层」用（如输入框上方浮条），且需 `if #available(iOS 26, *)` |
| `GlassEffectContainer(spacing:content:)` | 合并多个玻璃形状、彼此形变 | **iOS 26.0+** | ❌ 不用（我们没有需要形变的自定义玻璃） |
| `Glass`（`.regular/.clear/.identity`、`.tint`、`.interactive`） | 玻璃材质配置 | **iOS 26.0+** | ⚠️ 仅备用于设置页 Slider/Toggle（HIG 明确允许内容层瞬时交互元素用玻璃） |
| `buttonStyle(.glass)` / `.glassProminent` / `.glass(_:)` | 玻璃按钮样式 | **iOS 26.0+** | ⚠️ 备用。我们主操作按钮用 `.borderedProminent` 更稳；玻璃按钮会吸走「每屏 1 处强调色」的配额 |
| `View.glassEffectUnion(id:namespace:)` / `glassEffectID(_:in:)` / `GlassEffectTransition` | 玻璃形变过渡 | **iOS 26.0+** | ❌ 不用 |
| `ScrollEdgeEffectStyle`（`.automatic/.hard/.soft`）+ `scrollEdgeEffectStyle(_:for:)` | 滚动边缘与固定控件之间的模糊/不透明过渡 | **iOS 26.0+** | ✅ **对话流滚动时顶部栏/底部输入栏的可读性交给它**；`.soft` 更贴合陪伴调性，`.hard` 更接近「分隔线」质感 |
| `scrollEdgeEffectHidden(_:for:)` | 彻底关掉某条边的滚动边缘效果 | **iOS 26.0+** | ⚠️ 仅当 `.soft` 仍不满足「分隔只用一种手法」时，用它把多余的边关掉 |
| `View.safeAreaBar(edge:alignment:spacing:content:)` | 自定义安全区条（自带 scroll edge 效果） | **iOS 26.0+** | ⚠️ 若要做「输入框上方浮条」用系统 API 而非自绘 |
| `View.backgroundExtensionEffect()` | 内容延伸到侧栏/检视器下方的镜像+模糊 | **iOS 26.0+** | ❌ iPhone 单栏 App 用不到 |
| `View.onScrollGeometryChange(for:of:action:)` | 滚动几何变化时回调（可把几何转成自己的类型） | **iOS 18.0+** | ✅ **陪伴 Tab 的对话流**：用它判断「是否滚到底 / 是否越过顶部」，驱动「回到最新」按钮的出现（位移 ≤ 24pt） |
| `View.onChange(of:initial:_:)` | 值变化时触发副作用，支持 `initial` | **iOS 17.0+** | ✅ 设备状态条变化、消息到达、连接状态切换的**唯一**副作用入口 |
| `SensoryFeedback` + `View.sensoryFeedback(_:trigger:)` | 声明式触感（12 个静态语义 + impact 的力度参数重载） | **iOS 17.0+** | ✅ **「一次交互最多 1 次触感」的主力工具**（详见 §四） |
| `SymbolEffect` 协议 + `View.symbolEffect(_:options:value:)` | SF Symbol 动效（`pulse/scale/replace/drawOn/drawOff/variableColor/breathe/rotate/wiggle/appear/disappear/bounce/automatic`） | **iOS 17.0+**（`breathe/rotate/wiggle` 为 iOS 18 追加） | ✅ 「小栈状态」图标用 `.pulse` 或 `.replace`；**禁用 `.bounce`**（违反红线「禁止 bounce」） |
| `TabRole`（`.search` / `.prominent`） | Tab 的语义角色 | 类型 iOS 18+；`.search` iOS 26；`.prominent` iOS 26.x | ❌ 我们只有 2 个 Tab，**不需要搜索 Tab**，`.prominent` 会把「小栈」挤到尾部独立区，破坏两栏对称 |
| `View.tabBarMinimizeBehavior(_:)` | 滚动时自动收起 Tab 栏 | **iOS 26.0+** | ⚠️ 可选。收起后 Tab 栏失去导航意义，与「2 Tab 固定结构」冲突，**建议不用** |
| `TabSection`（嵌套 Tab 分组） | Tab 分组 | iOS 18+ | ❌ 只有 2 个 Tab，不需要分组 |
| `View.tabViewCustomization(_:)` + `TabViewCustomization` | 用户自定义 Tab 顺序并持久化 | iOS 18+ | ❌ 2 个 Tab 固定，不需要 |
| `TabViewStyle.sidebarAdaptable` | Tab 栏在 iPad 上自适应成侧栏 | iOS 18+ | ❌ 我们是 iPhone-only（或 iPhone 优先） |
| `ToolbarSpacer` / `SpacerSizing.fixed` | 工具栏项之间的视觉分组 | **iOS 26.0+** | ⚠️ 「小栈」Tab 顶栏若有多于 1 个图标，用它分隔，避免自绘分隔线（我们的「分隔只用一种手法」） |
| `ToolbarContent.visibilityPriority(_:)` / `ToolbarOverflowMenu` / `ToolbarItemPlacement.topBarPinnedTrailing` | 工具栏优先级与溢出 | iOS 26.x | ⚠️ 配合「绝不用 More 溢出 Tab」——我们不塞工具栏项，不触发溢出 |
| `View.navigationTransition(_:)` + `NavigationTransition.crossFade` | 导航过渡 | iOS 18+ / `.crossFade` iOS 26.x | ✅ 设置 Scene 打开时用 `.crossFade`（淡入=无位移，符合「位移 ≤ 24pt」） |
| `View.alert(_:item:)` / `alert(error:)` / `confirmationDialog(_:item:)` | 用数据项驱动弹窗 | iOS 26.x | ✅ 错误提示统一走 `alert(error:)`，避免手写 `isPresented` 双状态 |
| `View.swipeActions(edge:allowsFullSwipe:content:onPresentationChanged:)` | 自定义滑动手势 | iOS 26.x | ⚠️ 对话气泡左滑删除（长按删除会多一级交互），但**必须保留完整删除路径**（无障碍要求） |
| `DynamicViewContent.reorderable()` + `reorderContainer(for:isEnabled:move:)` | 拖拽重排 | iOS 26.x | ❌ 不做重排 |
| `View.animatable()` 宏 / `Animatable()` | 自定义可动画数据 | iOS 26+ | ⚠️ 若 3D 姿态预览需要连续插值可考虑；我们的动效只有 3 档时长，**用不上** |
| `Slider` 刻度（`init(_:value:in:step:)`） | 刻度滑块 | iOS 26+ | ✅ 设置页「音量 / 灵敏度」用刻度滑块（但音量滑块属 HIG 允许的玻璃例外，可考虑） |
| `TextEditor` + `AttributedString` / `AttributedTextSelection` / `FindContext` | 富文本编辑与查找 | iOS 26+ | ❌ 我们的输入是单行 `TextField`，富文本无用 |
| `AssistiveAccess` | 辅助访问支持 | iOS 26+ | ⚠️ 可顺手支持（系统会给一个简化布局），但**我们的 ≤5 元素约束天然适配** |
| `Color.ResolvedHDR` | 带 HDR headroom 的颜色 | iOS 26+ | ❌ 不做 HDR 主题 |
| `AsyncImage.init(request:scale:)` / `asyncImageURLSession(_:)` | 图片请求与本地缓存 | iOS 26.x | ❌ 陪伴 App 无图片流 |
| `MeshGradient` | 网格渐变 | iOS 18+ | ❌ 不用（且渐变背景易糊） |
| `SpeechAnalyzer`（`final actor`） | 端侧语音分析会话 | **iOS 26.0+** | ✅ 若做「按住说话」，用新 Speech 框架的端侧转写 |
| `SpeechTranscriber` | 端侧语音转文字模块 | **iOS 26.0+** | ✅ 同上；`SpeechTranscriber.isAvailable` 需先检查设备支持 |
| `AVSpeechSynthesizer`（**注意在 AVFAudio 框架，不是 AVFoundation**） | 语音合成 | iOS 7.0+ | ✅ 「小栈朗读回复」；新增 `write(_:toBufferCallback:)` 可缓存音频 |
| `AVSpeechSynthesizer.PersonalVoice` 授权（`requestPersonalVoiceAuthorization`） | 使用用户「个人语音」 | 见 §七 | ⚠️ 可选增强，需单独授权流程 |
| Foundation Models（`LanguageModelSession` / `@Generable` / `Tool` / `SystemLanguageModel` / `PrivateCloudComputeLanguageModel`） | 端侧大模型 | **iOS 26.0+**，且**需要 Apple Intelligence 支持的机型** | ⚠️ 陪伴对话的本地兜底/润色；**国内机型覆盖率需先确认**，不能作为唯一链路 |
| `SwiftData` | 持久化 | iOS 17.0+ | ✅ 会话历史持久化首选（`@Model` / `ModelContext` / `@Query`） |
| `App Intents` / `AppShortcut` / `AppShortcutsProvider` / `SiriTipView` | Siri / 快捷指令 / Spotlight 调用 | iOS 16+ | ✅ **「用 Siri 跟小栈说话」的落点**（详见 §六） |
| `OpenIntent` | 打开 App 到指定页面 | iOS 16.0+ | ✅ 从 Live Activity / 小组件 / 控制中心跳回 App 对应页 |
| `WidgetKit` 交互小组件 / `ControlWidgetButton` / `ControlWidgetToggle` / `ControlCenter` | 锁屏、控制中心、灵动岛操作按钮 | iOS 17+/18+/26+ | ✅ 「叫醒小栈」「静音小栈」做成 Control Widget（详见 §六） |
| `ActivityStyle.transient`（ActivityKit） | 短时 Live Activity（只在灵动岛扩展区存在） | **iOS 26.0+** | ✅ **「小栈思考中」专用**（详见 §五） |

### 3.2 逐条要点（问题指定的几个 API）

#### `onChange`（iOS 17.0+）
官方签名：`nonisolated func onChange<V>(of value: V, initial: Bool = false, _ action: @escaping () -> Void) -> some View where V : Equatable`

> "The system may call the action closure on the main actor, so **avoid long-running tasks in the closure**. If you need to perform such tasks, detach an asynchronous background task."

**对我们的意义** `[我的推断]`：设备状态（监听中/思考中/说话中/等你回来/离线）→ Live Activity 刷新 → 这条链路必须 `Task { }` 甩出去，绝不能在 `onChange` 闭包里同步做网络或 ActivityKit 调用（会掉帧）。**红线关联**：状态变化 = 一次交互 = 最多 1 次触感，正好在这里用 `sensoryFeedback(_:trigger:)` 触发。

#### `onScrollGeometryChange(for:of:action:)`（iOS 18.0+）
官方签名：`nonisolated func onScrollGeometryChange<T>(for type: T.Type, of transform: @escaping (ScrollGeometry) -> T, action: @escaping (T, T) -> Void) -> some View where T : Equatable`

> "The geometry of a scroll view changes frequently while scrolling. **You should avoid updating large parts of your app whenever the scroll geometry changes.**"

> "If multiple scroll views are found within the view hierarchy, **only the first one will invoke the closure** you provide and a runtime issue will be logged."

**对我们的意义** `[我的推断]`：
- **必须把 transform 收敛成 `Bool` 或小结构体**，绝不能把整个 `ScrollGeometry` 传下去（官方明确警告）。
- **我们的陪伴 Tab 只有 1 个滚动视图**（对话流），所以「只有第一个会触发」不成问题；但若在「小栈」Tab 也用这个 modifier，**同一 view 层级里不能有第二个 ScrollView**。
- 典型用法：判断是否已滚到底 → 控制「回到最新」按钮的显示（配合 `onScrollVisibilityChange` 亦可，但那是 iOS 18 的另一个 API）。

#### `.scrollEdgeEffect` / `ScrollEdgeEffectStyle`（iOS 26.0+）
官方定义：`struct ScrollEdgeEffectStyle`，三个值 `.automatic` / `.hard` / `.soft`；配套 `scrollEdgeEffectStyle(_:for:)` 与 `scrollEdgeEffectHidden(_:for:)`。

> "By default, the system sets an automatic scroll edge effect to provide a visual transition between scrolling content and stationary controls at both edges of the scroll view in the scrolling direction. The system determines which style to apply based on the platform and context."

> "The **hard** style provides a more opaque, clearly defined linear boundary, and the **soft** style provides a subtle blurred transition."

> "Apply `scrollEdgeEffectHidden(_:for:)` to a scroll view to remove the scroll edge effect entirely for an edge you specify."

**对我们的意义** `[我的推断]`：**这直接解决「分隔只用一种手法」的红线**。我们的对话流从底部输入栏下方穿过，如果自己画一条渐变遮罩 + 一条分割线，就是两种手法；用 `.soft` scroll edge effect 之后，**底部输入栏本身就是唯一分隔**，不需要任何自绘分隔线。
⚠️ 注意：**「自动」风格是 hard 还是 soft 由系统按上下文决定**，我们如果依赖它就必须显式写 `.soft`，否则不同设备表现不一致。

#### `TabView` 新 API（iOS 26）
- `Tab(role: .search)`：`TabRole` 类型 iOS 18+，`.search` 为 iOS 26。官方原文（Adopting Liquid Glass）："The system automatically separates the search tab from other tabs and places it at the trailing end"。
- `TabRole.prominent`：iOS 26.x，官方原文："Set the `prominent` role on a tab to place the tab in a separate, trailing position of the tab bar."
- `tabBarMinimizeBehavior(_:)`：iOS 26，官方示例 `TabView { ... }.tabBarMinimizeBehavior(.onScrollDown)`。
- `TabViewBottomAccessoryPlacement`：iOS 26，用于 Tab 视图附件（输入框类附件）。

**对我们的意义** `[我的推断]`：**我们两个 Tab（陪伴 / 小栈）都不需要任何新 API**。标准 `TabView { Tab("陪伴", systemImage: ...) { ... } }` 就拿到 iOS 26 的标准玻璃质感。**唯一值得考虑的是 `TabViewBottomAccessoryPlacement`** ——把「输入框」作为陪伴 Tab 的底部附件，滚动时自动隐藏，是 iOS 26 官方的「聊天 App 输入栏」做法，比自己 `safeAreaInset` 更原生。**成本低、收益高，建议采纳**。

#### `.sensoryFeedback`（iOS 17.0+）
见 §四 完整展开。

#### `symbolEffect`（iOS 17.0+）
官方签名：`nonisolated func symbolEffect<T, U>(_ effect: T, options: SymbolEffectOptions = .default, value: U) -> some View where T : DiscreteSymbolEffect, T : SymbolEffect, U : Equatable`

> "`value` — the value to monitor for changes, **the animation is triggered each time the value changes**."

`SymbolEffect` 提供：`appear` / `disappear` / `bounce` / `pulse` / `scale` / `variableColor` / `breathe` / `rotate` / `wiggle` / `automatic` / `drawOff` / `drawOn` / `replace`。

**对我们的意义** `[我的推断]`：
- 「小栈当前状态」用一个 SF Symbol + `.symbolEffect(.pulse, value: isThinking)` 就能表达「思考中」。
- **`.bounce` 必须禁用**（红线明文禁止 bounce）；`.scale` 要注意其缩放幅度不受我们 1.02 上限控制 → **建议只用 `.pulse` 和 `.replace`**。
- `.replace` 特别适合「状态切换时图标换成另一个」——**比缩放更符合「无位移、无缩放」的红线**。

---

## §四 触感系统详解（可直接编码）

### 4.1 三层能力怎么选

| 层 | 框架 | 最低版本 | 能做什么 | 我们用不用 |
|---|---|---|---|---|
| L1 声明式 | SwiftUI `SensoryFeedback` + `.sensoryFeedback(_:trigger:)` | **iOS 17.0+** | 12 个静态语义（impact 带力度重载），零生命周期管理 | ✅ **主力** |
| L2 UIKit | `UIImpactFeedbackGenerator` / `UISelectionFeedbackGenerator` / `UINotificationFeedbackGenerator` / `UICanvasFeedbackGenerator` | **iOS 10.0+** | 可指定力度(`intensity:`)、可指定位置(`at:`) | ✅ **兜底**（需要力度/位置时） |
| L3 自定义 | CoreHaptics `CHHapticEngine` / `CHHapticPattern` / `CHHapticEvent` / `CHHapticParameterCurve` | **iOS 13.0+** | 自定义时间轴图案、连续包络、动态参数 | ⚠️ 仅「小栈说话中」这类需要专属纹理的场景 |

### 4.2 L1：SwiftUI `SensoryFeedback` 全量语义（官方 Topics 原文）

**指示开始/结束** `[Apple 官方文档原文]`
- `.start` — "Indicates that an activity started."
- `.stop` — "Indicates that an activity stopped."

**指示变化/选择**
- `.alignment` — "Indicates the alignment of a dragged item."
- `.decrease` — "Indicates that an important value decreased below a significant threshold."
- `.increase` — "Indicates that an important value increased above a significant threshold."
- `.levelChange` — "Indicates movement between discrete levels of pressure."
- `.selection` — "Indicates that a UI element's values are changing."
- `.pathComplete` — "Indicates a drawn path has completed and/or recognized."

**指示操作结果**
- `.success` — "Indicates that a task or action has completed."
- `.warning` — "Indicates that a task or action has produced a warning of some kind."
- `.error` — "Indicates that an error has occurred."

**物理冲击**
- `.impact` — "Provides a physical metaphor you can use to complement a visual experience."
- `.impact(weight: SensoryFeedback.Weight, intensity: Double)`
- `.impact(flexibility: SensoryFeedback.Flexibility, intensity: Double)`

**按压/释放/选择（结构化）**
- `.press(SensoryFeedback.PressFeedback)` / `.release(SensoryFeedback.ReleaseFeedback)` / `.selection(SensoryFeedback.SelectionFeedback)`

### 4.3 L2：UIKit 反馈生成器（官方 Topics 原文）

**基类** `UIFeedbackGenerator`（iOS 10.0+）——官方原文："Don't subclass or create instances of this class yourself."；提供 `init()`、`convenience init(view: UIView)`、`prepare()`。

**`UIImpactFeedbackGenerator`**（iOS 10.0+）
> "Use impact feedback to indicate when an impact occurs. For example, you might trigger impact feedback when a user interface object collides with another object."

方法：`impactOccurred()` / `impactOccurred(intensity: CGFloat)` / `impactOccurred(at: CGPoint)` / `impactOccurred(intensity:at:)`；枚举 `UIImpactFeedbackGenerator.FeedbackStyle`（"The mass of the objects in the collision simulated by an impact feedback generator object."）。

**`UISelectionFeedbackGenerator`**（iOS 10.0+）
> "Use selection feedback to communicate movement through a series of discrete values."

方法：`selectionChanged()` / `selectionChanged(at: CGPoint)`。

**`UINotificationFeedbackGenerator`**（iOS 10.0+）
> "Use notification feedback to communicate that a task or action succeeded, failed, or produced a warning of some kind."

方法：`notificationOccurred(UINotificationFeedbackGenerator.FeedbackType)` / `notificationOccurred(_:at:)`。

**`UICanvasFeedbackGenerator`** — "Use canvas feedback to indicate when a drawing event occurs, such as an object snapping to a guide or ruler."（我们无画布，**不用**）

### 4.4 L3：CoreHaptics 要点

- `CHHapticEngine`（iOS 13.0+）："you need to create a haptic engine. The haptic engine establishes the connection between your app and the underlying device hardware."；官方三步：① 创建 engine 并**保持强引用** ② `start()` / `start(completionHandler:)` ③ 结束时 `stop(completionHandler:)`。
- `CHHapticEngine` 官方警告："Even though your app makes a request through the haptic engine, **the operating system could still override the request with system services**."（所以触感不能作为唯一反馈通道。）
- `CHHapticPattern`：构造 `init(events:parameterCurves:)` / `init(events:parameters:)`；属性 `duration: TimeInterval`。
- `CHHapticEvent`：`init(eventType:parameters:relativeTime:)` / `init(eventType:parameters:relativeTime:duration:)`；官方原文："Specify the intensity of a haptic event by creating an event parameter with ID `hapticIntensity`."（另有 `hapticSharpness`）。`CHHapticEvent.EventType` 含 `.transient` 与 `.continuous`。
- `CHHapticParameterCurve`：用参数曲线做连续包络（力度随时间变化）。
- `CHHapticEngine.isAutoShutdownEnabled`："A Boolean value that indicates whether the haptic engine starts and stops automatically on request from one of its pattern players, or when idle."

### 4.5 ⭐ 统一封装设计（可直接编码）

**设计目标（对齐红线「一次交互最多 1 次触感」）**：① 全 App **只有一个**触感出口；② 调用方**只声明语义**，不允许直接指定力度/位置（力度由映射表集中管理）；③ 同一次交互内，同一语义**只播一次**；④ 触感**永不与动效强耦合**（系统通知可覆盖）。

```swift
// Haptics.swift
import SwiftUI
import UIKit

/// 全 App 唯一的触感出口。
/// 红线：一次交互最多 1 次触感 —— 由 `play(_:)` 内的「同语义去重」强制保证。
@MainActor
final class Haptics {
    static let shared = Haptics()

    /// 触感语义。调用方只选语义，不选力度 —— 力度由下方映射表统一管理。
    enum Semantic: Hashable {
        case selection     // 选中/切换 Tab、切换候选词
        case impact        // 物理落位：消息气泡送达、卡片吸附
        case success       // 发送成功、连接成功
        case warning       // 设备电量低、信号弱
        case error         // 发送失败、连接失败
        case start         // 小栈开始说话 / 开始聆听
        case stop          // 小栈停止说话
        case levelChange   // 灵敏度/音量档位变化
    }

    // MARK: - 力度映射表（唯一可调力度的地方）

    /// 语义 → UIKit 力度/样式。集中在此，便于统一调参。
    private enum Recipe {
        static let selection = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.rigid, 0.55)
        static let impact    = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.soft,  0.70)
        static let success   = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.light, 0.60)
        static let warning   = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.medium, 0.80)
        static let error     = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.heavy, 0.90)
        static let start     = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.soft,  0.45)
        static let stop      = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.soft,  0.35)
        static let levelChange = (style: UIImpactFeedbackGenerator.FeedbackStyle, intensity: CGFloat) = (.rigid, 0.45)
    }

    // MARK: - 生成器（长生命周期持有，官方要求）

    private lazy var impactGen     = UIImpactFeedbackGenerator(style: .light)
    private lazy var selectionGen = UISelectionFeedbackGenerator()
    private lazy var notifyGen    = UINotificationFeedbackGenerator()

    // MARK: - 「一次交互最多一次」的去重状态

    /// 当前交互内已经播过的语义。
    private var playedInCurrentInteraction: Set<Semantic> = []
    /// 当前交互标识。跨 interaction 切换时清空去重表。
    private var currentInteraction: String = ""

    /// 开启一次「交互」。在用户手势的起点调用（例如 Button 的 action 入口）。
    /// 同一 interaction 内重复的相同语义会被丢弃。
    func beginInteraction(_ id: String) {
        guard id != currentInteraction else { return }
        currentInteraction = id
        playedInCurrentInteraction.removeAll()
        impactGen.prepare()
        selectionGen.prepare()
        notifyGen.prepare()
    }

    /// 播放一次触感。返回是否真的播了（被去重时返回 false，便于自测断言）。
    @discardableResult
    func play(_ semantic: Semantic) -> Bool {
        guard !playedInCurrentInteraction.contains(semantic) else { return false }
        playedInCurrentInteraction.insert(semantic)

        switch semantic {
        case .selection:
            selectionGen.selectionChanged()
        case .impact:
            let r = Recipe.impact;    impactGen.impactOccurred(intensity: r.intensity)
        case .success:
            let r = Recipe.success;   impactGen.impactOccurred(intensity: r.intensity)
        case .warning:
            let r = Recipe.warning;   impactGen.impactOccurred(intensity: r.intensity)
        case .error:
            notifyGen.notificationOccurred(.error)
        case .start:
            let r = Recipe.start;     impactGen.impactOccurred(intensity: r.intensity)
        case .stop:
            let r = Recipe.stop;      impactGen.impactOccurred(intensity: r.intensity)
        case .levelChange:
            let r = Recipe.levelChange; impactGen.impactOccurred(intensity: r.intensity)
        }
        return true
    }
}
```

**SwiftUI 侧的两种接法**

```swift
// 接法 A（推荐）：声明式，触发源就是状态变化 —— 天然「一次状态变化 = 一次触感」
Button("发送") { send() }
    .sensoryFeedback(.success, trigger: sendState)   // sendState: .idle/.sending/.sent/.failed

// 接法 B：需要跨组件去重、或需要力度映射时，走统一出口
Button("发送") {
    Haptics.shared.beginInteraction("send")
    Haptics.shared.play(.success)
    send()
}
```

**⭐ 我们的语义映射表（陪伴场景）** `[我的推断]`

| 交互 | 语义 | 理由 |
|---|---|---|
| 切换 Tab | `.selection` | 离散值变化，官方语义完全对应 |
| 从候选词里选一条 | `.selection` | 同上 |
| 消息气泡送达 | `.impact(soft, 0.70)` | 有「落位」隐喻，且 soft 不惊扰 |
| 消息发送成功 | `.success` | 官方语义「task completed」 |
| 小栈开始说话 | `.start` | 官方语义「activity started」 |
| 小栈停止说话 | `.stop` | 官方语义「activity stopped」 |
| 设备连接断开 | `.error` | 用 notification 的 error（唯一需要"坏消息"触感的地方） |
| 设备电量低 | `.warning` | notification 的 warning |
| 灵敏度档位变化 | `.levelChange` | 官方语义「movement between discrete levels」 |

### 4.6 与我们红线的对齐检查

| 红线 | 本方案如何满足 |
|---|---|
| 一次交互最多 1 次触感 | `beginInteraction` + `playedInCurrentInteraction` 去重；同一交互内同一语义只播一次 |
| 触感不与动效/玻璃叠加 | 触感只在**用户手势路径**上播；**设备状态变化**（如「小栈开始思考」）只走动画，**不播触感**（除非 App 在前台且用户正在看） |
| 触感语义集中 | 语义枚举在 `Haptics.swift` 内，力度在 `Recipe` 表内，视图层不得出现 `UIImpactFeedbackGenerator` |
| 无 bounce/overshoot | 触感不走动画曲线；L3 CoreHaptics 若使用，禁止 `hapticSharpness` 突变造成"弹跳感" |
| 设备端不参与 | 触感只在 iPhone 端；**设备端 320×240 屏的振荡周期 ≥ 9000 ms 约束与本节无关**，不要把触感参数下发到设备端 |

## §五 Live Activity 完整方案（数据模型 + 刷新策略 + 能耗）

### 5.1 系统的硬约束（全部 `[Apple 官方文档原文]`）

| 约束 | 原文 | 对我们的影响 |
|---|---|---|
| **活动时长上限 8 小时** | "A Live Activity can be active for up to eight hours unless its app or a person ends it before this limit. After the eight-hour limit, the system automatically ends the Live Activity" | 「小栈在线」不能靠一个常驻 Live Activity 撑 24 小时 |
| **锁屏最长 12 小时** | "the Live Activity remains on the Lock Screen until a person removes it or for up to four additional hours before the system removes it — whichever comes first. As a result, a Live Activity remains on the Lock Screen for a maximum of 12 hours." | 同上 |
| **数据 4 KB 上限** | "Static and dynamic data for a Live Activity, including data for ActivityKit updates and ActivityKit push notifications, **can't exceed a combined size of 4 KB**." | **只放状态词，绝不放对话内容** —— 与我们的「不显示敏感内容」红线天然一致 |
| **无网络权限** | "Each Live Activity runs in its own sandbox, and, unlike a widget, a Live Activity **can't access the network** or receive location updates." | 状态必须由 App 推给系统，不能让 Live Activity 自己拉 |
| **只能前台启动** | "your app needs to be in the foreground to start a Live Activity. You can update or end a Live Activity from your app while it runs in the background" | 用户首次打开 App 时才创建；之后靠 `update` / `end` |
| **后台可启动的唯一口子是 LiveActivityIntent** | "you can start a Live Activity while your app is in the background by using an app intent that conforms to `LiveActivityIntent`" | Control Center 的「叫醒小栈」按钮可以后台拉起 Live Activity |
| **relevanceScore 相对值** | "Assign a higher value for an important Live Activity content update — for example, a score of `100` — and use lower values for less important Live Activity content updates — for example, `50`." | 「等你回来」= 100（有情绪重量），「说话中」= 50 |
| **staleDate** | "The `staleDate` tells the system when the Live Activity content becomes outdated… the `activityState` changes to `ActivityState.stale` and `isStale` changes to `true`." | 状态过期时系统会标记，我们可以在展开态显示"可能已过期" |
| **必须支持展开态** | "In addition to the compact and minimal presentations, **you must support the expanded presentation**." | Dynamic Island 展开态不可省 |
| **HIG：只在有新内容时更新** | "**Update a Live Activity only when new content is available.** If the underlying content or status remains the same, maintain the same display until the underlying content or status changes." | 5 档状态 → 最多 5 次内容变化，天然低频 |
| **HIG：只为必要更新报警** | "**Alert people only for essential updates that require their attention.** Live Activity alerts light up the screen and by default play the notification sound" | **不用 `AlertConfiguration`**。陪伴 App 的状态变化不该点亮屏幕 + 响铃 |
| **HIG：结束后尽快清理** | "**Always end a Live Activity immediately when the task or event ends, and consider setting a custom dismissal time.** … In most cases, 15 to 30 minutes is adequate." | 设备离线 → 立刻 `end(..., dismissalPolicy: .after(...))` |

### 5.2 数据模型

```swift
// StackChanActivityAttributes.swift
import ActivityKit

/// 小栈当前状态 —— 只描述「状态」，绝不承载对话内容。
struct StackChanAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        /// 与 UI 状态一一对应；文案放 App 侧，不进 Live Activity。
        var phase: Phase
        /// 进入该状态的时刻，用于展开态显示"已持续 3 分钟"。
        var since: Date
    }

    /// 静态属性：设备名（用户自己起的名字，不敏感）。
    var deviceName: String

    enum Phase: String, Codable, Hashable {
        case listening    // 监听中
        case thinking    // 思考中
        case speaking    // 说话中
        case waiting     // 等你回来
        case offline     // 离线
    }
}
```

**约束落地检查** `[我的推断]`：
- `ContentState` 只含 1 个枚举 + 1 个 `Date` → 序列化后几十字节，**离 4 KB 上限极远**，安全。
- **没有 `String` 承载对话文本**——即使模型加字段也不加内容字段（可在 `ContentState` 上加 `// 禁止添加对话内容` 注释 + 单测断言字段数）。

### 5.3 视图结构（锁屏 + 灵动岛）

```swift
// StackChanLiveActivity.swift
import ActivityKit
import SwiftUI
import WidgetKit

struct StackChanLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: StackChanAttributes.self) { context in
            // 锁屏 / 横幅呈现
            LockScreenView(phase: context.state.phase, since: context.state.since)
                .activityBackgroundTint(Color(.systemBackground))
                .activitySystemActionForegroundColor(.primary)
        } dynamicIsland: { context in
            DynamicIsland {
                // ① 展开态（系统强制要求支持）
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: icon(for: context.state.phase))
                        .symbolEffect(.pulse, value: context.state.phase == .thinking)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.since, style: .timer)
                        .monospacedDigit()
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text(label(for: context.state.phase))
                        .font(.headline)
                }
            } compactLeading: {
                // ② 紧凑态：leading —— 单个状态图标
                Image(systemName: icon(for: context.state.phase))
            } compactTrailing: {
                // ③ 紧凑态：trailing —— 短文字（≤ 4 字符更稳）
                Text(shortLabel(for: context.state.phase))
                    .font(.caption2)
            } minimal: {
                // ④ 最小态：只有一个小图标
                Image(systemName: icon(for: context.state.phase))
            }
            .keylineTint(.primary)
        }
    }
}
```

**灵动岛尺寸纪律** `[我的推断]`：
- HIG 原文："Keep content as narrow as possible and ensure it's snug against the TrueDepth camera. Try not to obscure key information in the status bar, and **don't add padding between content and the TrueDepth camera**."
- 所以 compactLeading **只放一个 symbol**，compactTrailing **只放 2–4 个汉字**（"听/想/说/等/离"）。不要放时间戳（会挤）。
- 「每屏 1 处强调色」→ 灵动岛里**不要给状态图标上色**，用 `.primary` 单色，保留强调色给 App 内的当前状态。

### 5.4 刷新策略

```swift
// LiveActivityController.swift
@MainActor
final class LiveActivityController {
    static let shared = LiveActivityController()
    private var activity: Activity<StackChanAttributes>?

    /// 相关度：需要用户注意的状态给高值
    private func relevance(for phase: StackChanAttributes.Phase) -> Double {
        switch phase {
        case .waiting:  return 100   // 官方示例的重要值
        case .offline:  return 80
        case .thinking: return 50    // 官方示例的次要值
        case .speaking: return 50
        case .listening: return 30
        }
    }

    func start(deviceName: String, phase: StackChanAttributes.Phase) async {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        guard activity == nil else { return update(phase: phase); }

        let attributes = StackChanAttributes(deviceName: deviceName)
        let content = ActivityContent(
            state: .init(phase: phase, since: Date()),
            staleDate: Date().addingTimeInterval(60 * 30),   // 30 分钟未更新即视为可能过期
            relevanceScore: relevance(for: phase)
        )
        activity = try? Activity.request(
            attributes: attributes,
            content: content,
            pushType: nil                                   // 见 5.5「要不要 push」的取舍
        )
    }

    func update(phase: StackChanAttributes.Phase) async {
        guard let activity else { return }
        let content = ActivityContent(
            state: .init(phase: phase, since: Date()),
            staleDate: Date().addingTimeInterval(60 * 30),
            relevanceScore: relevance(for: phase)
        )
        await activity.update(content)                      // 无 AlertConfiguration → 不点亮屏幕
    }

    func end(phase: StackChanAttributes.Phase) async {
        guard let activity else { return }
        await activity.end(
            ActivityContent(state: .init(phase: phase, since: Date()), staleDate: nil),
            dismissalPolicy: .after(Date().addingTimeInterval(60 * 15))   // HIG: 15–30 分钟足够
        )
        self.activity = nil
    }
}
```

### 5.5 刷新频率与能耗（关键取舍）

| 问题 | 结论 | 依据 |
|---|---|---|
| **要不要 ActivityKit push？** | **第一版不要**。我们的状态来自 BLE 设备端，App 不在前台就收不到 BLE 事件，push 也没用；等有了服务端中转再做。 | `pushType: nil` |
| **更新频率上限？** | 我们只有 5 档状态，**每次状态迁移更新一次**即可，天然 ≤ 几十次/小时。HIG 明确要求"只在有新内容时更新"。 | HIG live-activities 原文 |
| **要不要 `AlertConfiguration`？** | **不要**。陪伴 App 的状态变化不该点亮屏幕 + 播提示音。 | HIG 原文 |
| **App 不在前台时怎么办？** | 状态会"过期"。用 `staleDate`（30 分钟）让系统标记 `isStale`，展开态可显示"可能已过期"。 | ActivityKit 原文 |
| **能耗来源？** | Live Activity 的**渲染由系统负责**，App 不常驻、不轮询。真正的能耗风险是我们自己写的 BLE 轮询循环 —— **不要为了刷新 Live Activity 而提高 BLE 轮询频率**。 | `[我的推断]` |
| **8 小时上限怎么办？** | 「等你回来」这种长驻状态**到期就结束**，下次 App 打开再重建；不要试图续期。 | ActivityKit 原文 |

### 5.6 ⭐ iOS 26 新增：`ActivityStyle.transient`

官方原文（Displaying live data with Live Activities）：
> "Live Activities can appear temporarily in the **extended presentation in the Dynamic Island** to allow interactions and status updates while a person is actively performing a task. **Locking the device, collapsing the extended presentation in the Dynamic Island, or tapping outside the Dynamic Island ends the Live Activity.**"
> "To start a transient Live Activity, use `request(attributes:content:pushType:style:)` and pass `ActivityStyle.transient` as the `style` parameter."

**我们的用法** `[我的推断]`：
- **「小栈思考中」/「小栈说话中」→ 用 transient**：这是"正在进行中的短暂状态"，锁屏就结束、不留痕、不占锁屏位置，**最省电也最不打扰**。
- **「等你回来」/「离线」→ 用常规 Live Activity**：这是需要用户回头看到的持久状态，值得占锁屏。
- 这是 iOS 26 独有的能力，**很可能是我们"交付感"的一个隐藏加分项**：用户跟小栈说话后，锁屏灵动岛短暂冒出一个"想"字图标，说话结束自动消失——非常克制、非常 Apple。

---

## §六 App Intents / 小组件 / Control Widget 方案

### 6.1 ⭐ App Intent 能否让用户用 Siri 直接跟小栈说话？

**结论：能。技术上完全成立，而且有 Apple 官方的一等公民支持。** `[Apple 官方文档原文]`

关键依据：
- `AppIntents` 官方文档：App Intents 就是为「Siri, Spotlight, and the Shortcuts app」服务的。
- `AppShortcuts` 官方文档原文："Improve the experience of using your app intents and entities in system experiences like **Siri, Spotlight, and the Shortcuts app**."；并且 "**the shortcuts that you create are available as soon as someone installs your app, and you don't have to register them yourself.**"
- `AppShortcutsProvider` 协议：`static var appShortcuts: [AppShortcut]`，用 `AppShortcutsBuilder` result builder 声明式描述。
- `AppShortcut` 构造：`init(intent:phrases:shortTitle:systemImageName:)`；`AppShortcutPhrase` 是 `ExpressibleByStringLiteral`（直接写字符串短语）。
- `SiriTipView` / `ShortcutsLink`：可在 App 内提示用户「你可以对 Siri 说：…」。

**⭐ 关于「跟小栈说话」的两种形态（成本差异很大，要分清）：**

| 形态 | 做法 | Siri 说什么 | 能否拿到自由文本 | 成本 |
|---|---|---|---|---|
| **A. 指令型（推荐）** | `AppIntent` + `@Parameter` 接收一个 `String`（或一个 `AppEntity`） | "用小栈说'过来'" / "让小栈过来" | ✅ 拿到一段自由文本 → **转发给设备端播放** | **中**（1–2 天） |
| **B. 自由对话型** | `AppIntent` 里启动麦克风录音 → 转写 → 转发 | "小栈，我到楼下了" | ✅ 也能拿到，但要走 `SpeechAnalyzer` + 录音权限 | **高**（要处理录音会话、权限、转写） |

**形态 A 的实现骨架** `[我的推断]`（API 形态均有官方出处）：

```swift
// TalkToStackChanIntent.swift
import AppIntents

struct TalkToStackChanIntent: AppIntent {
    static var title: LocalizedStringResource = "跟小栈说话"
    static var description = IntentDescription("把你说的话转交给小栈说出来。")
    static var openAppWhenRun: Bool = false     // 不打开 App，直接下发

    /// 用户说给 Siri 的话。Siri 会把它填进这个参数。
    @Parameter(title: "说的话")
    var message: String

    @Parameter(title: "语气", default: .default)
    var tone: Tone

    enum Tone: String, AppEnum {
        case `default`, gentle, excited
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        // 1) 通过 BLE 把文本发给设备端
        // 2) 立刻返回一句确认，让 Siri 读出来
        return .result(dialog: "好的，我转给小栈了。")
    }
}

// AppShortcutsProvider.swift
struct StackChanShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: TalkToStackChanIntent(),
            phrases: [
                "用 \(.applicationName) 说话",
                "让 \(.applicationName) 转告小栈 \(.$message)",
                "\(.$message) 用 \(.applicationName) 告诉小栈"
            ],
            shortTitle: "跟小栈说话",
            systemImageName: "waveform"
        )
    }
}
```

**演示价值 `[我的推断]`**：形态 A 的演示脚本是——「Hey Siri，用小栈说话，小栈该吃饭了」→ 手机不打开 App → 设备端小栈用它的喇叭把这话说出来。**这个 demo 的完成度极高且实现量不大**，是本次调研里性价比最高的「苹果交付感」演示点。

⚠️ **必须验证的点**（本地无法验证，需真机）：中文 Siri 的 phrase 命中率、中文 `@Parameter` 填充、App 未打开时 `perform()` 能否拿到 BLE 权限（**BLE 在后台/未激活时通常不可用** → 可能必须 `openAppWhenRun = true`）。**这是本节最大的技术风险**，见 §九。

### 6.2 Control Widget / 控制中心 / 锁屏按钮

官方原文（WidgetKit「Controls」）：
> "Controls act as a button that initiates an action from your app or opens your app to a specific view, or as a toggle."
> "On devices with an Action button, people can place a controls action in the Action button. On iPhone and iPad, people place controls in Control Center and on the Lock Screen."
> "To offer a control for your app, use WidgetKit API to configure and update the control, create its layout with SwiftUI, and **perform its action using App Intents**."

相关 API：`StaticControlConfiguration` / `AppIntentControlConfiguration` / `ControlWidgetButton` / `ControlWidgetToggle` / `ControlCenter` / `ControlInfo` / `ControlValueProvider` / `AppIntentControlValueProvider`。

**我们的 Control Widget 清单** `[我的推断]`：

| 控件 | 类型 | 作用 | 成本 |
|---|---|---|---|
| 「叫醒小栈」 | `ControlWidgetButton` + `AppIntent` | 从控制中心/锁屏一键唤醒设备端 | 低 |
| 「小栈静音」 | `ControlWidgetToggle` + `AppIntent` | 一键静音/取消静音设备端 | 低 |
| 「小栈状态」 | `ControlWidgetButton`（只读） | 点击后跳 App（`OpenIntent`，iOS 16+） | 低 |

⚠️ **一致性红线**：Control Widget 是 App 外的入口，**它的视觉必须与 App 内一致**（同一套 SF Symbol、同一套文案）。不要在 Widget 里另发明一套设计。

### 6.3 小组件（WidgetKit）

`WidgetFamily`（iOS 14+）支持锁屏 accessory 家族（iOS 16+）、主屏小/中/大（iOS 14+）、灵动岛（iOS 16+）。

**我们的建议** `[我的推断]`：
- **只做 1 个小组件**：主屏中尺寸「小栈状态卡」（设备名 + 状态图标 + 状态词）。
- **不做锁屏 accessory 小组件**（`.accessoryCircular` 等）——它们极小，"小栈状态"两个字都放不下，反而破坏质感。
- 小组件要能显示「离线」状态，并引导用户打开 App。
- **一个 Live Activity + 一个小组件就够了**。小组件是"我主动看一眼"，Live Activity 是"系统推给我"，两者定位不重复。

### 6.4 成本收益矩阵

| 能力 | 交付感提升 | 实现成本 | 是否进第一版 |
|---|---|---|---|
| 标准 `TabView` 双 Tab（自动玻璃） | ★★★★★ | 0 | ✅ 必做 |
| `.sensoryFeedback` 统一触感 | ★★★★☆ | 低 | ✅ 必做 |
| Live Activity（常规 + transient） | ★★★★☆ | 中 | ✅ 必做 |
| `AppShortcut` + `AppIntent`（Siri 说话） | ★★★★★ | 中 | ✅ 必做（需真机验证） |
| 锁屏/主屏小组件（1 个） | ★★★☆☆ | 中 | ⚠️ 第二版 |
| Control Widget（叫醒/静音） | ★★★☆☆ | 中 | ⚠️ 第二版 |
| Foundation Models 端侧对话 | ★★☆☆☆ | 高 | ❌ 不进第一版（机型覆盖未知） |
| `SpeechAnalyzer` 按住说话 | ★★★☆☆ | 中高 | ⚠️ 第二版，先确认国内机型端侧模型可用性 |

---

## §七 ⭐「以前要自己做、现在系统给了」的省力清单

> 本节是本次调研**价值最高**的部分。每一行都是「我们原本要写的代码 → 系统现在给的 API」。
> 标注约定：✅ 建议第一版就用 · ⚠️ 有条件再用 · ❌ 不适合我们

### 7.1 视觉与材质

| 以前要自己做 | 现在系统给了 | 证据 | 建议 |
|---|---|---|---|
| 自己用 `UIVisualEffectView` + `UIBlurEffect` 做模糊，再手绘高光/描边/阴影来模仿"玻璃" | **Liquid Glass**：模糊 + 折射 + 随触摸实时形变，全部系统渲染 | `[Apple 官方文档原文]` 玻璃是"a material that blurs content behind it, reflects color and light of surrounding content, and **reacts to touch and pointer interactions in real time**" | ✅ 但**只在导航/浮层用**，内容层坚决不用（§二） |
| 自己做多层玻璃形状的融合与形变动画 | `GlassEffectContainer(spacing:)` + `glassEffectID` + `GlassEffectTransition(.matchedGeometry/.materialize)` | 官方文档原文 | ⚠️ 只在确实需要时用；我们不需要 |
| 给 Tab 栏 / NavigationStack 手工加半透明底 + 阴影 | **不写任何代码**，标准组件自动获得玻璃 | "standard components like bars, sheets, popovers, and controls automatically adopt this material" | ✅ 删代码 |
| 给滚动列表顶部/底部手工做渐变遮罩 mask | `ScrollEdgeEffectStyle`（`.automatic/.hard/.soft`）+ `scrollEdgeEffectHidden(_:for:)` | iOS 26 官方文档 | ✅ **同时解决"分隔只用一种手法"** |
| 用 `CAAnimation` / `Lottie` 做状态图标动效 | `symbolEffect(_:options:value:)`，14 种内置效果 | iOS 17+ 官方文档 | ✅ 用 `.pulse` / `.replace`，**禁用 `.bounce`** |
| 自己写网格渐变 shader | `MeshGradient`（iOS 18+） | June 2024 更新 | ❌ 不需要 |
| 自己写 blend mode 混色 | `Color.mix(with:by:in:)`（iOS 18+） | June 2024 更新 | ⚠️ 备选 |
| 自己写 shader 并等运行时编译 | `Shader.compile(as:)` 构建期预编译 | June 2024 更新 | ❌ 不需要 |

### 7.2 触感与反馈

| 以前要自己做 | 现在系统给了 | 证据 | 建议 |
|---|---|---|---|
| 自己写 CoreHaptics 引擎 + 事件 + 包络，只为"点一下有反馈" | **`.sensoryFeedback(.selection, trigger: x)`** 一行 | `SensoryFeedback` iOS 17+，12 个静态语义 | ✅ **本次最大省力项** |
| 自己判断"该用轻触还是重击" | `SensoryFeedback.impact(weight:intensity:)` / `impact(flexibility:intensity:)` | 官方文档 | ✅ |
| 自己写"按下/抬起"两段式反馈 | `SensoryFeedback.press(_:)` / `.release(_:)` | 官方文档 | ⚠️ 我们"一次交互一次触感"，不用按压式 |
| 自己画成功/失败徽标 | `.sensoryFeedback(.success/.warning/.error)` | 官方文档 | ✅ |
| 自己管 `UIImpactFeedbackGenerator` 的创建/持有/释放 | SwiftUI 侧完全不用管；UIKit 侧官方也明确"不要自己子类化" | 官方文档 | ✅ 交给 `Haptics.swift` 统一持有 |

### 7.3 语音与 AI ⭐

| 以前要自己做 | 现在系统给了 | 证据 | 建议 |
|---|---|---|---|
| 自己打包 Whisper / 自己接云 ASR / 自己做 VAD | **`SpeechAnalyzer` + `SpeechTranscriber`**（端侧，iOS 26） | `final actor SpeechAnalyzer`，模块化，`AsyncSequence` 出结果 | ✅ **端侧 = 隐私叙事 + 离线可用** |
| 自己判断设备是否支持端侧模型 | `SpeechTranscriber.isAvailable` / `supportedLocales` / `installedLocales` | 官方文档 | ✅ 先查再降级 |
| 自己写音频资产下载/校验 | `AssetInventory.assetInstallationRequest(supporting:)` | 官方文档示例 | ✅ |
| 自己塞 llama.cpp / GGUF / 量化，做端侧 LLM | **Foundation Models 框架**：`SystemLanguageModel`、`LanguageModelSession`、`@Generable`、`Tool` | iOS 26 官方文档 | ⚠️ 收益高但**需要 Apple Intelligence 机型** |
| 自己写 JSON schema 约束 + 解析校验 | `@Generable` / `@Guide` / `GenerationSchema` 宏 | 官方文档 | ⚠️ 同上 |
| 自己写工具调用协议（JSON schema + 解析） | `protocol Tool` + `LanguageModelExecutor` | 官方文档 | ⚠️ 同上 |
| 自己串 LLM 请求到云端（怕隐私） | `PrivateCloudComputeLanguageModel`（私有云端，Apple 托管） | 官方文档 | ⚠️ 同上 |
| 自己把 TTS 音频拼成文件缓存 | `AVSpeechSynthesizer.write(_:toBufferCallback:)`（+ `toMarkerCallback:`） | AVFAudio 官方文档 | ✅ **小栈的固定语音可预生成缓存** |
| 自己实现"克隆我的声音" | `AVSpeechSynthesizer.requestPersonalVoiceAuthorization` + Personal Voice | AVFAudio 官方文档 | ⚠️ 需单独授权流程，成本高 |
| 自己实现"模型答不上来时兜底" | `LanguageModelError` + `SystemLanguageModel` 能力查询 | 官方文档 | ⚠️ |

### 7.4 系统集成（以前要写一堆胶水代码）

| 以前要自己做 | 现在系统给了 | 证据 | 建议 |
|---|---|---|---|
| 自己写 URL Scheme + `openURL` 解析，让 Siri/快捷指令能调 App | **App Intents + App Shortcuts**：`AppIntent`、`@Parameter`、`AppShortcut`、`AppShortcutsProvider` | 官方文档："available as soon as someone installs your app, and **you don't have to register them yourself**" | ✅ **Siri 演示点** |
| 自己写 Today Extension 做锁屏/控制中心按钮 | **Control Widget**：`ControlWidgetButton` / `ControlWidgetToggle` / `StaticControlConfiguration` / `AppIntentControlConfiguration` / `ControlCenter` | WidgetKit 官方文档 | ⚠️ 第二版 |
| 自己写通知扩展做灵动岛 | **ActivityKit + WidgetKit**：`ActivityConfiguration` / `DynamicIsland` | 官方文档 | ✅ |
| 自己写"从小组件跳到 App 指定页" | `OpenIntent`（iOS 16+） | 官方文档 | ✅ |
| 自己写"在 App 里提示用户能用 Siri 说什么" | `SiriTipView` / `SiriTipUIView` / `ShortcutsLink` | 官方文档 | ✅ 成本极低，加分 |
| 自己写状态持久化（Codable + 文件 + 迁移） | **SwiftData**（`@Model` / `ModelContext` / `@Query` / `@Relationship` / `@Unique`） | iOS 17+ 官方文档 | ✅ 会话历史 |
| 自己写文本编辑的查找/替换/选区 | `FindContext` / `AttributedTextSelection` / `AttributedTextFormattingDefinition` / `TextEditor` 支持 `AttributedString` | iOS 26 官方文档 | ❌ 我们是单行输入 |
| 自己写键盘候选词 | `textInputSuggestions(_:)` / `textInputCompletion(_:)` | June 2024 更新 | ❌ |
| 自己写拖拽重排 | `DynamicViewContent.reorderable()` + `reorderContainer(for:isEnabled:move:)` | iOS 26.x 更新 | ❌ |
| 自己写滑动手势 + 侧滑菜单 | `swipeActions(edge:allowsFullSwipe:content:onPresentationChanged:)` | iOS 26.x 更新 | ⚠️ 消息删除 |
| 自己写工具栏的分组间隔线 | `ToolbarSpacer` / `SpacerSizing.fixed` | iOS 26 官方文档 | ⚠️ |
| 自己写 Alert 的 `isPresented` 双状态 | `alert(_:item:)` / `alert(error:)` / `confirmationDialog(_:item:)` | iOS 26.x 更新 | ✅ |
| 自己写图片选择（还要申请相册权限） | **`PhotosPicker`**（iOS 16+，基于 `PHPickerViewController`，**不需要相册权限**） | 官方文档 | ❌ 陪伴 App 无图片需求（若加"给小栈看图"就用它） |
| 自己处理 Dynamic Type 字号表 | 系统 text style + `.dynamicTypeSize(...)` 限定 | HIG typography | ✅ |
| 自己写手势来源限制（排除铅笔/间接触摸） | `GestureInputKinds`（iOS 26.x，`DragGesture`/`TapGesture` 等新增 input sources） | iOS 26.x 更新 | ❌ |

### 7.5 可访问性

| 以前要自己做 | 现在系统给了 | 证据 | 建议 |
|---|---|---|---|
| 自己读 `UIAccessibility.isReduceMotionEnabled` | `EnvironmentValues.accessibilityReduceMotion` | 标准 SwiftUI 环境值 | ✅ **只在 `Motion.swift` 内读**（我们的红线） |
| 自己给图标写 VoiceOver 标签 | `accessibilityLabel` + `accessibilityValue`；iOS 18 起支持字符串插值里写 `"\(accessibilityName: myColor)"` | June 2024 更新 | ✅ |
| 自己实现"简化界面"给认知障碍用户 | `AssistiveAccess`（iOS 26）——系统会给一个精简版布局 | iOS 26 官方文档 | ⚠️ 我们的 ≤5 元素约束天然适配 |
| 自己标注 Tab 栏角色给 VoiceOver | `AccessibilityTraits.isTabBar`（iOS 18+） | June 2024 更新 | ✅ |
| 自己写隐私清单 `PrivacyInfo.xcprivacy` | 官方模板 + `NSPrivacyAccessedAPITypes`（Required Reason API） | BundleResources 官方文档（缓存） | ✅ 上架前必做 |

### 7.6 ⚠️ 一句话总结

> **这一代 iOS 最大的变化不是"多了几个 API"，而是"我们原本要自己写的那层质感胶水代码，现在全部有系统实现"。**
> 对我们最直接的三条：
> 1. **触感**（自己写 CoreHaptics → 一行 `.sensoryFeedback`）
> 2. **玻璃 / 滚动渐隐 / 图标动效**（自己画 → 系统材质 + `ScrollEdgeEffectStyle` + `symbolEffect`）
> 3. **Siri / 快捷指令 / 控制中心 / 灵动岛**（自己写胶水 → App Intents + App Shortcuts + Control Widget + ActivityKit）

---

## §八 可访问性与极端档位破版清单

### 8.1 Dynamic Type 极端档位的真实倍率（Apple 官方数值）

`[Apple 官方文档原文]` HIG typography「Supporting Dynamic Type」给出的 **AX5（最大档）** 与 Large 档对照：

| Text style | Large（题面给定） | **AX5（官方）** | 倍率 |
|---|---|---|---|
| Large Title | 34 / 41 | **60 / 70** | 1.76× |
| Title 1 | 28 / 34 | **58 / 68** | 2.07× |
| Title 2 | 22 / 25 | **56 / 66** | 2.55× |
| Title 3 | 20 / 23 | **55 / 65** | 2.75× |
| Headline | 17 / 21 | **53 / 62** | 3.12× |
| Body | 17 / 21 | **53 / 62** | 3.12× |
| Callout | 16 / 19 | **51 / 60** | 3.19× |
| Subhead | 15 / 18 | **49 / 58** | 3.27× |
| Footnote | 13 / 16 | **44 / 52** | 3.38× |
| Caption 1 | 12 / 13 | **43 / 51** | 3.58× |
| Caption 2 | 11 / 13 | **40 / 48** | 3.64× |

HIG accessibility 原文："Ideally, give people the option to enlarge text by **at least 200 percent**."

### 8.2 ⭐ 按我们的红线逐条算，AX5 档会破在哪

| 我们的约束 | Large 档 | **AX5 档** | 破版风险 |
|---|---|---|---|
| **内容最大宽度 320 pt** | 320/17 ≈ **18 个汉字/行**（Body） | 320/53 ≈ **6 个汉字/行** | 🔴 **必破**。消息气泡变成"每行 6 字"，对话流没法读 |
| **控件中心距 ≥ 60 pt** | 按钮高 ≈ 44 pt，间距 60 合理 | 按钮高 ≈ 75+ pt | 🟡 间距没问题，但**一屏能装的控件数减半** |
| **单个 Tab 一级元素 ≤ 5 个** | 5 个控件 ≈ 5×(44+60) = 520 pt | 5 个控件 ≈ 5×(75+60) = 675 pt | 🟡 iPhone SE 高度 667 pt → **放不下 5 个**。需在 AX 档隐藏次要元素 |
| **全 App 一级可见元素 ≤ 12 个** | 12 个 | 12 个 | 🟡 数量不变，但**一屏放不下 12 个** → 需滚动或折叠 |
| **字号只用系统 text style** | ✅ | ✅ | 🟢 无风险（这正是只用 text style 的回报：**不用自己维护字号表**） |
| **每屏 1 处强调色** | ✅ | ✅ | 🟢 无风险 |
| **位移 ≤ 24 pt** | ✅ | ✅ | 🟢 无风险（位移是 pt，不随字号缩放） |
| **设备端 320×240 屏** | 与 iOS 无关 | 与 iOS 无关 | 🟢 **注意：设备端屏和 iOS 档位无关**，不要把两边的 Dynamic Type 逻辑混在一起 |

### 8.3 破版清单（按风险排序）

| # | 位置 | 风险 | 表现 | 修复方向 `[我的推断]` |
|---|---|---|---|---|
| 1 | **陪伴 Tab 对话气泡** | 🔴 高 | 320 pt 宽在 AX5 下每行仅 6 字，气泡被撑成竖条 | ① 气泡宽度改为 `min(320, 屏宽 − 32)` 的**相对**约束；② 在 AX 档**取消气泡固定宽**，改为占满让文本换行；③ 字号随 text style 自动缩放，**不要为了"好看"锁死 17 pt** |
| 2 | **陪伴 Tab 设备状态条** | 🔴 高 | 状态条横向排布 3–4 项，AX5 下必然换行/挤压 | AX 档改为**纵向堆叠**或**只显示最关键的一项**，其余进详情 |
| 3 | **小栈 Tab 3D 姿态预览** | 🔴 高 | 预览区是固定尺寸方形，AX5 下标签文字溢出方框 | 预览区尺寸用 `GeometryReader` 动态算；AX 档把标签移到预览下方 |
| 4 | **底部输入栏** | 🟡 中 | 输入框 + 发送按钮横排，AX5 下按钮变高、输入框被挤 | AX 档改为**上下堆叠**；发送按钮 `.iconOnly` 但保留 ≥44×44 可点区域 |
| 5 | **Live Activity 锁屏视图** | 🟡 中 | 锁屏 Live Activity 空间有限，AX5 下文字撑爆 | Live Activity 里**只用 `caption`/`headline` 且不显示长文本**；我们只显示状态词，风险低 |
| 6 | **灵动岛 compactTrailing** | 🟡 中 | "思考中"3 个字在 AX5 下超出灵动岛尾部 | 灵动岛区域**固定用短标签**（"想"/"说"/"听"），**不让 Dynamic Type 影响它** |
| 7 | **设置 Scene** | 🟡 中 | `Form` 行高由系统放大，但自定义 `LabeledContent` 可能固定高 | 设置项**全部用系统 `Form` + `LabeledContent`**，不自定义行高 |
| 8 | **小组件** | 🟡 中 | 小组件尺寸固定，AX5 下文字溢出 | 用 WidgetKit 自己的渲染模式与缩放策略 |
| 9 | **Tab 栏** | 🟢 低 | 系统 Tab 栏自带 Dynamic Type 支持 | 不动 |

### 8.4 VoiceOver 标签清单

| 元素 | 标签 | 值 / 提示 | 备注 |
|---|---|---|---|
| Tab「陪伴」 | "陪伴" | — | 系统自带；自定义容器可加 `.accessibilityAddTraits(.isTabBar)` |
| Tab「小栈」 | "小栈" | — | 同上 |
| 设备状态条 | "小栈状态" | **值** = "思考中" / "说话中" / "等你回来" / "离线" | 用 `.accessibilityValue` 而不是把状态词塞进 label |
| 消息气泡（我） | "我说的" | 正文 | 气泡里的文字应被读出，**不要**用 `.accessibilityElement(children: .ignore)` 吞掉 |
| 消息气泡（小栈） | "小栈说的" | 正文 | 同上 |
| 状态图标（纯图标） | "小栈状态：思考中" | — | 纯图标必须给 label，否则 VoiceOver 读"SF Symbol, ..." |
| 发送按钮 | "发送" | — | Adopting Liquid Glass 原文："**Provide an accessibility label for every icon.**" |
| 3D 姿态预览 | "小栈的姿态预览" | 值 = "头部向左转 15 度" | 3D 姿态是**视觉信息**，必须给文字等价物 |
| 返回最新按钮 | "回到最新消息" | — | 出现时（滚动）才可聚焦 |

### 8.5 Reduce Motion 的正确实现

HIG accessibility 官方原文（Reduce Motion 激活时）：
> "ensure your app or game responds by reducing automatic and repetitive animations, including **zooming, scaling, and peripheral motion**. Other best practices for reducing motion include:
> - **Tightening animation springs to reduce bounce effects**
> - Tracking animations directly with people's gestures
> - Avoiding animating depth changes in z-axis layers
> - **Replacing transitions in x-, y-, and z-axes with fades to avoid motion**
> - **Avoiding animating into and out of blurs**"

**我们的红线与 Apple 的 Reduce Motion 建议高度一致**（禁 bounce / 禁 overshoot / 位移小）→ `[我的推断]`：**我们本来就不会做出 Reduce Motion 需要「大幅削弱」的动画**，所以实现成本极低。

```swift
// Motion.swift  —— 全 App 唯一允许读取 accessibilityReduceMotion 的文件
import SwiftUI

enum Motion {
    /// 三档时长（红线：只 3 档）
    enum Duration {
        static let fast: Double = 0.15
        static let normal: Double = 0.25
        static let slow: Double = 0.40
    }

    /// 两条曲线（红线：只 2 种）
    enum Curve {
        static let standard = Animation.easeInOut
        static let linear = Animation.linear
    }
}
```

**对外暴露派生后的 Profile，而不是裸的环境值** `[我的推断]`：

```swift
// ✅ Motion.swift 是唯一读取点
struct MotionProfile: Equatable {
    let reduceMotion: Bool
    let duration: (Motion.Duration) -> Double
    let curve: Animation

    static let standard = MotionProfile(
        reduceMotion: false,
        duration: { $0 },
        curve: Motion.Curve.standard
    )
    static let reduced = MotionProfile(
        reduceMotion: true,
        duration: { _ in Motion.Duration.fast },   // 一律缩短
        curve: .easeOut                              // 用淡入淡出代替位移
    )
}

private struct MotionProfileKey: EnvironmentKey {
    static let defaultValue: MotionProfile = .standard
}

extension EnvironmentValues {
    var motionProfile: MotionProfile {
        get { self[MotionProfileKey.self] }
        set { self[MotionProfileKey.self] = newValue }
    }
}

// ✅ 唯一的注入点（放在根 Scene）
struct RootView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion   // ← 这一行是全 App 唯一一处
    var body: some View {
        TabView { ... }
            .environment(\.motionProfile, reduceMotion ? .reduced : .standard)
    }
}
```

**关键约束**：
- `accessibilityReduceMotion` **只在 `Motion.swift` 内读取**（我们的红线），其它视图通过 `Environment` 拿 `MotionProfile`。
- Reduce Motion 开启时：**把位移/缩放动画替换为淡入淡出**（HIG 原文），而不是简单地"什么都不动"——那样会让状态变化"无反馈"。
- **3D 姿态预览**：Reduce Motion 下应**停止自动振荡**，改为用户手动拖拽时才跟随（HIG 原文 "Avoiding animating depth changes in z-axis layers"——3D 深度变化正是这条）。
- **设备端 320×240 的持续振荡周期 ≥ 9000 ms 是设备端约束**，与 iOS 的 Reduce Motion **无关**；可选地，当 iOS 端 Reduce Motion 开启时同步关闭设备端自动振荡（属 App → 设备指令，红线只约束 App 端，故标为可选）。

---

## §九 未取得与风险

### 9.1 未取得的条目（明确标注，不编造）

| 条目 | 状态 | 说明 |
|---|---|---|
| **PrivacyKit** | ❌ **未取得** | `https://developer.apple.com/documentation/privacykit.md`、`/privacykit/privacykit.md`、`/tutorials/data/documentation/privacykit.json` 全部 404。**本机不存在可引用的官方文档**。本文档**不声称其存在**。 |
| **App 隐私报告（App Privacy Report）** | ❌ **未取得官方开发文档** | HIG privacy.md 只提到 App Store 产品页的「App privacy details」（`developer.apple.com/app-store/app-privacy-details/`），**用户侧「App 隐私报告」的开发者文档未抓到**。 |
| **`PrimitiveButtonStyle.glassProminent` / `.glass(_:)` 独立符号页** | ⚠️ 仅见于 Adopting Liquid Glass 正文 | 已确认存在且为 iOS 26，但**未抓到独立符号页 → 未确认精确签名**。 |
| **`UIKit.UIGlassEffect` 独立符号页** | ⚠️ 同上 | 同上。 |
| **`AVSpeechSynthesizer` 新增能力的引入版本** | ⚠️ 页面 availability 为 iOS 7.0+ | `PersonalVoice` 授权、`write(_:toBufferCallback:)` 的**具体引入版本未取得**。 |
| **`Foundation Models` 页面 availability** | ⚠️ 框架根页未给 iOS 号 | 各符号页未抓；正文语境为 iOS 26，本文按 iOS 26 记。 |
| **WWDC 视频转录** | ❌ 未使用 | 本次全部结论取自**文档原文**，未引用任何 WWDC 转录；`[WWDC 视频转录]` 标注在本文件中**未出现**。 |
| **`ActivityStyle.transient` 独立符号页** | ⚠️ 仅见于 ActivityKit 文章正文 | 正文给了确切用法 `request(attributes:content:pushType:style:)` + `ActivityStyle.transient`，**未单独抓取枚举页**。 |
| **iOS 26.1 / 26.2 等小版本差异** | ❌ 未取得 | 本文档只区分 `iOS 26.0+` 与 `iOS 26.x`（后者来自 SwiftUI Updates 的 "June 2026 / September 2026" 条目，未标注小版本号）。 |
| **HIG 中文版（zh-CN）正文** | ❌ 未取得 | HIG JSON 端点只返回英文正文。 |
| **3D 姿态预览的框架选型（SceneKit/RealityKit）** | ❌ 未调研 | 不在本次取证范围。 |

### 9.2 真实技术风险（按严重度）

| # | 风险 | 严重度 | 说明 | 缓解 |
|---|---|---|---|---|
| R1 | **Siri 在 App 未运行时能否拿到 BLE 能力** | 🔴 高 | `AppIntent.perform()` 在 App 未激活时执行，**BLE 外设连接通常要求 App 在前台**（iOS 后台蓝牙限制）。这直接决定「Siri 跟小栈说话」demo 能否成立。 | ① 先做**真机最小验证**：一个只 `perform()` 里写日志的 Intent，Siri 调用看是否拿到后台执行；② 若不行，改为 `openAppWhenRun = true`（打开 App 再下发），demo 改为「Siri 打开 App 并说话」，仍成立但弱一点；③ 备选：App Intent 只把文本发给服务器，服务器再下发设备端——**成本最高但唯一稳**。 |
| R2 | **Foundation Models 的机型覆盖** | 🔴 高 | 官方原文："To use Apple Foundation Models, people need a device that **supports Apple Intelligence**." 国内在售机型的 Apple Intelligence 可用性未知。 | **第一版完全不用 Foundation Models**。端侧对话先用自建/云端方案兜底。若要用，**先做机型白名单调研**再立项。 |
| R3 | **`SpeechAnalyzer` 端侧模型的语言支持** | 🟠 中 | `SpeechTranscriber` 有 `supportedLocales` / `installedLocales`，**中文（zh-CN）是否在端侧可用未取得**（需真机查 `installedLocales`）。 | 先写一段探测代码打印 `SpeechTranscriber.installedLocales`，**有中文再做**。 |
| R4 | **iOS 26 专属 API 与最低支持版本冲突** | 🟠 中 | `glassEffect` / `ScrollEdgeEffectStyle` / `ActivityStyle.transient` / `safeAreaBar` 全是 iOS 26.0+。若 App 要支持 iOS 17/18，全部要 `if #available` 分支。 | **策略：不做 iOS 26 专属 UI**（玻璃/滚动边缘都用系统默认），把 `if #available` 压到 0。`ActivityStyle.transient` 是唯一值得为它做分支的（可退化为常规 Live Activity）。 |
| R5 | **Live Activity 在 App 后台时状态陈旧** | 🟠 中 | BLE 事件只在 App 活跃时可达，后台状态会过期。 | `staleDate`（30 分钟）+ 展开态显示"可能已过期"；不要用 push（无服务器）。 |
| R6 | **Live Activity 4 KB 上限** | 🟢 低 | ContentState 只有 1 个枚举 + 1 个 Date，余量极大。 | 加单测断言字段数。 |
| R7 | **Liquid Glass 在旧机型/降级模式下的观感** | 🟢 低 | 官方提供 `UIDesignRequiresCompatibility` 保留旧外观。 | 若需要，默认不设该 key（跟随系统新外观）。 |
| R8 | **Liquid Glass 的"减少透明度"辅助设置** | 🟢 低 | HIG 原文：玻璃会随 "reduce transparency" 设置改变外观。 | 用标准组件即自动适配；自定义玻璃需在设置里实测。 |
| R9 | **3D 姿态预览的原生重实现成本** | 🟠 中 | three.js 思路迁到 SwiftUI 需要 SceneKit / RealityKit / 自写矩阵；本次调研**未覆盖 3D 框架选型**。 | 单独调研；建议 v1 用 `Model3D`（RealityKit）快速验证。 |
| R10 | **中文字体下的 `symbolEffect` 表现** | 🟢 低 | SF Symbol 动效与中文字形混排时基线可能跳。 | 真机目视检查；必要时对中文标签用 `.fixedSize()`。 |

### 9.3 本文档的方法论风险（诚实声明）

- 本文档**全部结论来自 Apple 官方文档原文**，但**没有任何一条在真机/模拟器上编译验证过**。API 名与版本号来自文档的 availability 字段（可信度高），但**"这个 API 在我们代码里怎么组合"的部分是 `[我的推断]`**，已逐条标注。
- HIG 是 **JS 渲染站点**，本次通过其 **JSON 数据端点**（`/tutorials/data/design/human-interface-guidelines/<slug>.json`）取得正文；已成功取得 `materials`、`accessibility`、`privacy`、`typography`、`live-activities` 等页面的正文。**未能**取得 HIG 中文版正文，引用均为英文原文。
- 本机缓存 `ios-docs/` 的 166 份文档中，大量是集合页/索引页；本次实际逐字引用的是其中能提供正文的部分。
- **本次调研完全没有触碰仓库内任何代码**，所有 API 名称、行为描述均以 Apple 文档为准。

---

## 文末自查表

> 交付前逐条打勾；每条后面是本文档里给出答案的章节。

### A. Liquid Glass 策略（§二）

- [ ] A1 已确认「玻璃只给导航与浮层、内容层不用」是 Apple 原文支持的策略，且原文可引用 → §2.1 / §2.2
- [ ] A2 已确认不写任何自定义导航/栏背景，避免遮挡系统玻璃与 scroll edge effect → §2.1 来源 B
- [ ] A3 已确认不主动使用 `glassEffect` / `GlassEffectContainer` / `.buttonStyle(.glass)` → §2.3
- [ ] A4 若将来必须用，已确认默认形状是 `Capsule`、默认变体是 `.regular`、需显式给 `in:` 参数 → §2.3
- [ ] A5 已确认 `GlassEffectContainer` 的 spacing 必须 ≤ 内部布局 spacing，否则静止状态就会融合 → §2.1 来源 C
- [ ] A6 已确认所有玻璃相关 API 都是 iOS 26.0+，并已规划 `if #available` 策略 → §3.1 / 风险 R4

### B. SwiftUI 能力（§三）

- [ ] B1 对话流滚动可读性交给 `ScrollEdgeEffectStyle`（显式写 `.soft`，不依赖 `.automatic`）→ §3.1 / §3.2
- [ ] B2 「回到最新」按钮用 `onScrollGeometryChange(for: Bool.self)`，transform 收敛成 `Bool` → §3.2
- [ ] B3 确认每个 `onScrollGeometryChange` 作用域内只有 1 个 ScrollView → §3.2
- [ ] B4 副作用统一走 `onChange(of:initial:_:)`，且不在闭包内做长任务 → §3.2
- [ ] B5 状态图标动效只用 `.pulse` / `.replace`，**禁用 `.bounce`** → §3.2 / §7.1
- [ ] B6 陪伴 Tab 底部输入框考虑用 `TabViewBottomAccessoryPlacement`（iOS 26）→ §3.2
- [ ] B7 未使用 `TabRole.search` / `.prominent` / `tabBarMinimizeBehavior` → §3.1

### C.触感（§四）

- [ ] C1 全 App 只有一个触感出口 `Haptics.swift`，视图层不出现 `UIImpactFeedbackGenerator` → §4.5
- [ ] C2 调用方只声明语义，不直接指定力度；力度集中在 `Recipe` 表 → §4.5
- [ ] C3 同一交互内同一语义只播一次（去重机制已实现）→ §4.5
- [ ] C4 已建立陪伴场景的语义映射表（8 种）→ §4.5
- [ ] C5 设备状态自动变化（如"小栈开始思考"）**不**播触感，只有用户手势才播 → §4.6
- [ ] C6 已确认 `UIFeedbackGenerator` 不可子类化，生成器已长生命周期持有 → §4.3 / §4.4

### D. Live Activity（§五）

- [ ] D1 `ContentState` 只含状态枚举 + 时间，**不含任何对话文本** → §5.2
- [ ] D2 已实现 compactLeading / compactTrailing / minimal / expanded **四个区域** → §5.3
- [ ] D3 灵动岛用短标签（≤4 字符），不加 padding，不使用强调色 → §5.3
- [ ] D4 `relevanceScore` 已分级（等待=100 / 离线=80 / 其余=50 或更低）→ §5.4
- [ ] D5 已设置 `staleDate`（30 分钟）→ §5.4
- [ ] D6 **不使用** `AlertConfiguration`（不点亮屏幕、不响铃）→ §5.1 / §5.5
- [ ] D7 离线/结束状态用 `end(_:dismissalPolicy:.after(15 分钟))` 立即结束 → §5.1 / §5.4
- [ ] D8 「思考中/说话中」用 `ActivityStyle.transient`（iOS 26），「等你回来/离线」用常规 Live Activity → §5.6
- [ ] D9 已知晓 8 小时活动上限 / 12 小时锁屏上限 / 4 KB 数据上限 → §5.1
- [ ] D10 确认**没有**为了刷新 Live Activity 而提高 BLE 轮询频率 → §5.5

### E. App Intents / 小组件（§六）

- [ ] E1 已实现至少 1 个 `AppIntent` + `AppShortcut`（Siri 演示点）→ §6.1
- [ ] E2 已在 App 内用 `SiriTipView` 提示可用的 Siri 短语 → §6.1
- [ ] E3 **已完成 R1 真机验证**：App 未运行时 `perform()` 能否下发 BLE；不能则降级为 `openAppWhenRun = true` 或服务端中转 → §9.2 R1
- [ ] E4 Control Widget 与 App 内视觉一致（同 SF Symbol、同文案）→ §6.2
- [ ] E5 小组件数量 ≤ 1，Live Activity 与小组件定位不重复 → §6.3

### F. 省力清单（§七）

- [ ] F1 已逐条核对：凡是「以前自己写过」的胶水代码，是否都能换成系统 API → §7.1–§7.6
- [ ] F2 触感、滚动渐隐、图标动效三处已切换到系统实现 → §7.1 / §7.2
- [ ] F3 会话历史持久化已用 SwiftData → §7.4
- [ ] F4 已确认未使用 Foundation Models（第一版）→ §9.2 R2
- [ ] F5 上架前已准备 `PrivacyInfo.xcprivacy`（Required Reason API）→ §7.5

### G. 可访问性（§八）

- [ ] G1 已核算 AX5 档下 320 pt 宽只容 6 个汉字，对话气泡已改为相对宽度 → §8.2 / §8.3 #1
- [ ] G2 设备状态条在 AX 档已改为纵向或只显示最关键项 → §8.3 #2
- [ ] G3 3D 姿态预览尺寸已动态计算，AX 档标签已移位 → §8.3 #3
- [ ] G4 输入栏在 AX 档已上下堆叠 → §8.3 #4
- [ ] G5 灵动岛 / Live Activity 文案不受 Dynamic Type 影响 → §8.3 #5 #6
- [ ] G6 所有纯图标元素都有 `accessibilityLabel`（含发送按钮、状态图标）→ §8.4
- [ ] G7 状态条用 `accessibilityValue` 表达状态，而不是塞进 label → §8.4
- [ ] G8 3D 姿态有文字等价物（方向/角度）→ §8.4
- [ ] G9 `accessibilityReduceMotion` **只在 `Motion.swift` 内读取** → §8.5
- [ ] G10 Reduce Motion 下：位移/缩放 → 淡入淡出；3D 自动振荡停止 → §8.5
- [ ] G11 已确认设备端 320×240 振荡周期 ≥ 9000 ms 是**设备端**约束，未混入 iOS 端逻辑 → §8.2 / §8.5

### H. 证据完整性（§九）

- [ ] H1 文中所有 API 名与版本号均可回溯到 Apple 文档 availability 字段 → 全文
- [ ] H2 未取得的条目（PrivacyKit、App 隐私报告等）已如实标注，无编造 → §9.1
- [ ] H3 `[我的推断]` 与 `[Apple 官方文档原文]` 已区分标注 → 全文
- [ ] H4 已知悉本文档**未经真机编译验证** → §9.3
- [ ] H5 未引用任何 WWDC 转录（本次未使用）→ §9.1

---

**文档结束。**
**取证范围**：Apple 官方文档原文 + Apple HIG 官方 JSON 正文 + 本机 166 份 Apple 文档缓存。
**未改动仓库内任何其他文件。**
