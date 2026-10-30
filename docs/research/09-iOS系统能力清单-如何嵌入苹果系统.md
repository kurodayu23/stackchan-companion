# 09 · iOS 系统能力清单 —— 「嵌入苹果系统」的三种读法与落地方案

> 上游文档：`02-设计契约与交互规范.md`（设备端视觉令牌与交互契约）、`08-iOS26视觉规范.md`（iOS 26 / Liquid Glass 视觉实测）。
> 姊妹文档：`10-AppleHIG官方核实.md`（用真实 HIG 页原文核实的排版 / 材质 / 颜色硬约束，**冲突时以 10 为准**）。本文在 §3.1.5、§3.4 与之对齐。
> 本文**在其之上补充，不覆盖**。08 已定视觉语言，10 已定 HIG 硬约束，本文定**系统能力清单 + 信息架构 + 权限表达 + 可行性边界**。
> 方法：Apple 官方文档逐条抓取核实 API 名（用 `https://developer.apple.com/documentation/<path>.md` 的 Markdown 版本，其 JSON frontmatter 带 `availability` 字段），本地缓存 166 个文件于 `D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs\`。
> 纪律：**API 名写错比不写更糟**。所有拿不到官方出处的，一律标注「未验证」。

---

## 0. 结论速览

**「嵌入苹果系统」= 三层同时做到，缺一层就露馅。**

| 读法 | 一句话定义 | 露馅的标志 | 我们的交付 |
|---|---|---|---|
| **A 视觉层** | 界面看起来像系统自带 App | 看到硬编码色值、手绘分隔线、非系统字体的标签栏 | 全部用系统控件 + 系统语义色 + SF Symbols |
| **B 功能层** | 能力接入系统，不自建一套 | 小栈只能待在 App 里，用户要专门打开 App | Live Activity / Widget / Shortcuts / 控制中心 / Action Button |
| **C 生态位** | 信息架构模仿系统 App | 一屏塞 8 个功能入口，首页是仪表盘 | 首页 = 小栈的脸，2 层钻取，2–3 个 Tab |

**给 ENFP 用户的具体判断**：陪伴型 App 的核心不是"功能多"，而是**「小栈一直在我身边」**。这句话直接决定技术选型 —— 陪伴感 = 存在感，而存在感 = 系统级的存在（锁屏在、灵动岛在、桌面在、控制中心在），而不是"App 里有个按钮"。

**最该做的 8 项（详见 §3.3）**：Live Activity → App Intents/Shortcuts → Interactive Widget → Core Haptics → Home 首页即脸 → Action Button → 控制中心控件 → 按需权限。

---

## 1. 三种读法的判定标准（先立标准，再谈方案）

用户说的「嵌入苹果系统」，验收标准不是"我们做了 Live Activity"，而是：**一个不认识我们 App 的 iPhone 用户，会不会以为这是系统自带的东西。**

| 读法 | 验收问题 | 失败样例 | 通过样例 |
|---|---|---|---|
| A 视觉层 | 关掉 App 图标，只看界面截图，能认出是 iOS 吗？ | 深色卡片 + 青色 `#00D2FF` 大按钮 + 自绘 tab 栏 | `List(.insetGrouped)` + 语义色 + SF Symbols + `NavigationStack` |
| B 功能层 | 不打开 App，能不能用到小栈的能力？ | 一切都得先点进 App | 锁屏在显示小栈状态、灵动岛在、`Hey Siri 让小栈抬头` 能用、控制中心能静音 |
| C 生态位 | 界面组织方式像不像系统 App？ | 首页 8 宫格功能面板 | 首页是小栈的脸，向下钻取 2 层，设置独立成页 |

### 1.1 为什么这三条是**同一个**东西，不是三个选项

系统 App 的共同特征不是"用了 SwiftUI"，而是**它把能力分散到系统的各个表面，每个表面只放一件事**：

- **锁屏** = 正在发生的事（Live Activity）
- **桌面** = 一眼可读的状态（Widget）
- **语音** = 一个动作（App Shortcut / App Intent）
- **控制中心** = 一个开关（Control）
- **App 内** = 完整的历史与设置

StackChan 的产品形态天然匹配这套分工：小栈是**单主体、有状态、少量高频动作、长期陪伴**。这几乎是 Live Activity + Widget 的教科书用例。所以「嵌入苹果系统」对我们不是炫技，是**产品形态的最优解**。

### 1.2 与既有研究的衔接

| 既有结论 | 出处 | 本文的处理 |
|---|---|---|
| 深色 `StackChan OS` 视觉系统是最终态 | 02 §1.3 | iOS 端**不复刻**设备端配色，改用系统语义色 + iOS 26 玻璃层；品牌色只留在「小栈的脸」 |
| 不用系统默认蓝作强调色 | 02 §5.4 #17 | **在 iOS 端推翻**。iOS 端用 `.tint` + 语义色；系统蓝是「原生感」的一部分，自造色相是「露馅」的开始 |
| 不做超过 2 层导航深度 | 02 §5.4 #20 | 直接采纳为 IA 硬约束（§4） |
| 不用 iOS 标准 Tab Bar 承载 8 个功能 | 02 §5.4 #16 | 采纳并收得更紧：2–3 个 Tab，且首页不放功能入口 |
| 玻璃当背景介质，不当内容容器 | 08 §2.1 | iOS 端用 `glassEffect(_:in:)`（iOS 26+），只给「浮起的主要动作」 |
| 「正在做事」用跳动数字 + 状态色表达，不用进度条 | 08 §9 #9 | Live Activity 的 `ContentState` 直接这样设计 |

---

## 2. 系统框架能力清单

> **版本口径**：截至 2026-10，Apple 官方文档中**当前发布版为 iOS 27**（SwiftUI / UIKit 更新日志最新条目为 "September 2026"，见 `Updates/SwiftUI`）；**iOS 26** 是 Liquid Glass 那一代（iPhone 17 时代）。本项目若要「嵌入 iPhone 17 及更新机型」，**最低部署目标建议 iOS 18**（理由见 §7.1），但**所有 Live Activity / 意图 / 触感能力在 iOS 16–17 就已存在**，不必被 iOS 26 的新 API 绑架。
>
> 下表中每个 API 名都已从 Apple 官方文档的 Markdown 版本（`https://developer.apple.com/documentation/<path>.md`）取到并核对 JSON frontmatter 的 `availability` 字段。拿不到官方符号页的，标注「未验证」。

### 2.1 存在感层 —— 让小栈出现在系统表面（优先级最高）

| 能力 | 官方 API / 框架 | iOS 版本要求 | 我们的什么功能用它 | 优先级 |
|---|---|---|---|---|
| 锁屏实时状态 | `ActivityKit`：`ActivityAttributes`、`ActivityContent`（`state`/`staleDate`/`relevanceScore`）、`Activity.request(attributes:content:pushType:)`、`Activity.update(_:)`、`Activity.end(_:dismissalPolicy:)` | ActivityKit 16.1+；`ActivityContent` 16.2+ | 锁屏常驻「小栈正在听 / 正在说 / 当前情绪 / 电量 / 待办提醒」 | **P0** |
| 灵动岛 | `WidgetKit` 的 `ActivityConfiguration(for:content:dynamicIsland:)`；`DynamicIsland`、`DynamicIslandExpandedRegion(.leading/.trailing/.bottom/.center)`、`DynamicIslandExpandedRegionPosition`、`DynamicIslandExpandedContentBuilder`；`@Environment(\.isDynamicIslandLimitedInWidth)` | 16.1+ | 灵动岛 compact 显示小栈表情 + 一句正在说的话；expanded 显示状态明细 | **P0** |
| Live Activity 交互 | `AppIntents` 的 `LiveActivityIntent` 协议 + `Button(intent:)`；`AppIntent.openAppWhenRun` | `LiveActivityIntent` 17.0+ | 灵动岛/锁屏上直接「摸摸小栈」「静音」，不打开 App | P1 |
| Live Activity 远程更新 | ActivityKit push notifications（`pushType: .token`，`Activity.pushTokenUpdates`） | 16.1+ | 小栈在后台时（App 未运行）仍更新锁屏状态 | P2（**需后端**） |
| 桌面 / 今日视图小组件 | `WidgetKit`：`Widget`、`WidgetBundle`、`WidgetFamily`、`StaticConfiguration`；`AppIntentConfiguration`（可配置小组件） | WidgetKit 14.0+；`AppIntentConfiguration` 17.0+ | 桌面小组件显示小栈当前表情 + 今日心情 + 待办 | **P0**（表情）/ P1（可配置） |
| 锁屏配件小组件 | `WidgetFamily` 的 `.accessoryCircular` / `.accessoryCorner` / `.accessoryRectangular` / `.accessoryInline` | 14.0+ | 锁屏小组件只放「小栈情绪 + 电量」一格信息 | P1 |
| 控制中心 / 锁屏控件 | `WidgetKit` 的 `ControlWidget` 协议、`ControlWidgetButton`、`ControlWidgetToggle`、`StaticControlConfiguration`、`AppIntentControlConfiguration`、`ControlCenter`；动作由 `AppIntent` 执行 | 18.0+ | 控制中心放「小栈静音 / 叫醒小栈」；锁屏控件一键静音 | P1 |
| Action Button（iPhone 17 等机型） | **通过 App Shortcuts 生效**：用户可在「设置 → 操作按钮」里把任意 `AppShortcut` 指派给 Action Button；控件（Control）也可放到 Action Button | `AppShortcutsProvider` 16.0+；控件 18.0+ | 长按 Action Button → 小栈抬头 / 立刻静音。**没有独立的「Action Button API」**，走 Shortcuts 通道 | P1 |
| 系统捷径 / 快捷指令 | `AppIntents`：`AppIntent`、`AppShortcutsProvider`、`AppShortcut`、`AppShortcutPhrase`、`AppShortcutPhraseToken`、`AppShortcutsBuilder`、`ParameterSummary`、`IntentDialog` | 16.0+ | 「让小栈抬头」「摸摸小栈」「问小栈今天天气」出现在快捷指令 App 与 Spotlight | **P0** |
| App 内提示快捷指令 | `SiriTipView`、`ShortcutsLink`、`ShortcutsUIButton` | 16.0+ | App 内提示用户「这条也能用快捷指令说」，把功能推给系统 | P2 |
| Spotlight 收录 | `CoreSpotlight`：`CSSearchableIndex`、`CSSearchableItem`、`CSSearchableItemAttributeSet`；App Intents 路线：`IndexedEntity`（18.0+）、`IndexedEntityQuery` | `CSSearchableIndex` 9.0+；`IndexedEntity` 18.0+ | 小栈的记忆/日记条目可被系统搜索到（可选） | P2 |
| 通知 | `UserNotifications`：`UNUserNotificationCenter`、`UNNotificationAction` | 10.0+ | 待办提醒、番茄钟完成 | P1 |
| 后台任务 | `BackgroundTasks`：`BGTaskScheduler` | 13.0+ | App 被切走后继续与设备保持连接、收尾同步 | P2 |
| 推送 | APNs + Background Mode `remote-notification` | — | 小栈主动说一句话 | P1（**需后端**） |

### 2.2 交互与连接层

| 能力 | 官方 API / 框架 | iOS 版本要求 | 我们的什么功能用它 | 优先级 |
|---|---|---|---|---|
| 语音唤起小栈 | `AppIntents`（`AppIntent` 自动进入 Siri / Apple Intelligence）；旧路 `Intents` 的 `INIntent`、`INInteraction` | App Intents 16.0+；`INIntent` 10.0+ | 「嘿 Siri，问小栈……」 | P1 |
| 设备连接（BLE） | `CoreBluetooth`；权限 `NSBluetoothAlwaysUsageDescription` | `NSBluetoothAlwaysUsageDescription` 13.0+ | 手机 ↔ 小栈（ESP32-S3）直连 | **P0** |
| 局域网直连 | `Network` 框架：`NWConnection`（12.0+）、`NWBrowser`（13.0+）；权限 `NSLocalNetworkUsageDescription` | 12.0+；权限键 14.0+ | 同 Wi-Fi 下发现并连接小栈（比 BLE 更快） | **P0** |
| 麦克风（语音输入） | `Speech`：`SFSpeechRecognizer`、`SFSpeechAudioBufferRecognitionRequest`、`SFSpeechRecognitionTask`；权限 `NSMicrophoneUsageDescription` | Speech 10.0+；权限键 7.0+ | 在手机上按住说话 → 转写 → 发给小栈 | **P0** |
| 相机 | `AVFoundation`：`AVCaptureSession`、`AVCaptureDevice`；权限 `NSCameraUsageDescription` | 4.0+；权限键 7.0+ | 小栈的「摄像头」在手机上代拍（拍给小栈看） | P2 |
| 相册 | `PhotosUI`：`PhotosPicker`（SwiftUI）、`PHPickerViewController` | `PhotosPicker` 16.0+；`PHPickerViewController` 14.0+ | 选一张照片给小栈看 / 存进小栈相册 | P1 |
| 分享 | `SwiftUI.ShareLink`（16.0+）；`UIKit.UIActivityViewController` | 16.0+ | 把小栈拍的图 / 小栈说的话分享出去 | P2 |
| 深链 / Universal Links | Associated Domains（`Xcode` 文档：Supporting associated domains） | — | `https://stackchan.app/...` 打开 App 到指定场景；小组件/灵动岛点击直达 | P1 |
| Handoff | `Foundation.NSUserActivity`（`becomeCurrent` / `userInfo` / `activityType`） | 8.0+ | 从 iPhone 的 App 接力到 iPad / Mac 的 App | P2 |

### 2.3 数据与隐私层

| 能力 | 官方 API / 框架 | iOS 版本要求 | 我们的什么功能用它 | 优先级 |
|---|---|---|---|---|
| 隐私清单 | `PrivacyInfo.xcprivacy`：`NSPrivacyCollectedDataTypes`、`NSPrivacyCollectedDataType`、`NSPrivacyCollectedDataTypeLinked`、`NSPrivacyCollectedDataTypeTracking`、`NSPrivacyCollectedDataTypePurposes`；必需理由 API：`NSPrivacyAccessedAPITypes`、`NSPrivacyAccessedAPIType`、`NSPrivacyAccessedAPITypeReasons` | 提交 App Store 前必备 | 声明「我们的私人数据永不入库」——**清单里就写不收集** | **P0** |
| 权限文案 | `NSMicrophoneUsageDescription` / `NSCameraUsageDescription` / `NSBluetoothAlwaysUsageDescription` / `NSLocalNetworkUsageDescription` / `NSUserTrackingUsageDescription` | 7.0 / 7.0 / 13.0 / 14.0 / 14.0 | 每个权限写人话（§5） | **P0** |
| 跨设备同步 | `CloudKit`：`CKContainer`、`CKRecord`、`CKModifyRecordsOperation` | 8.0+ | 手机 ↔ 小栈的状态同步（是否用见 §7.3） | P2（**需后端 / iCloud**） |
| 本地持久化 | `Foundation.UserDefaults`（2.0+）、`CoreSpotlight` | — | 设置项、情绪记录本地留档 | P1 |
| 钥匙串 | `Security` 框架 | — | 存设备配对密钥 | P1 |

### 2.4 iOS 26 / iOS 27 新增（只写取到官方出处的）

| 能力 | 官方 API / 框架 | iOS 版本要求 | 我们的什么功能用它 | 优先级 |
|---|---|---|---|---|
| Liquid Glass 材质 | `SwiftUI`：`Glass`、`GlassEffectContainer`、`View.glassEffect(_:in:)` | 26.0+ | 首页「主要动作」浮起；iOS 26+ 才生效，26 以下自动走材质回退 | P1 |
| 主次自适应布局 | `SwiftUI.ArrangementView` + `View.arrangementViewStyle(_:)` + `ArrangementViewStyle`（`split` / `overlay`）+ `View.splitArrangementLayoutRatio(_:)` | 27.0+ | **直接对应「分得清主次」**：主内容 + 次要内容自适应排布 | P2（iOS 27 机型） |
| 工具栏溢出菜单 | `SwiftUI.ToolbarOverflowMenu` + `ToolbarContent.visibilityPriority(_:)` + `ToolbarItemPlacement.topBarPinnedTrailing` | 27.0+ | 次要动作进溢出菜单，工具栏只留主要动作 | P2 |
| 工具栏最小化 | `SwiftUI.View.toolbarMinimizationBehavior(_:)` | 27.0+ | 滚动时工具栏自动收起，把屏幕让给小栈的脸 | P2 |
| 预留区域感知 | `SwiftUI.ReservedRegion`、`GeometryProxy.reservedRegions(kind:options:layoutDirectionBehavior:)`（`.occlusion` / `.division`） | 27.0+ | 在带灵动岛/折叠的机型上，小栈的脸不被摄像头/铰链区域遮住 | P2 |
| 折叠屏适配 | `View.onHingeChange(isEnabled:_:)` + `DeviceHinge`（`.closed`/`.partiallyOpen`/`.fullyOpen`） | 27.0+ | 折叠展开时把脸移到外屏 | P3 |
| 长时间后台意图 | `AppIntents.LongRunningIntent` + `performBackgroundTask(options:operation:)` + `LongRunningTaskOptions` | 27.0+ | 「让小栈讲个故事」这类长任务不必留在前台 | P3 |
| 跨设备实体同步 | `AppIntents.SyncableEntity` | 27.0+ | 同一份小栈人格包在 iPhone / iPad 间延续 | P2 |
| Spotlight 语义化 | `CoreSpotlight.SpotlightSearchTool`、`CSSearchableIndexDescription` | 27.0+ | 让 Foundation models 能用自然语言搜到小栈的记忆 | P3 |
| 图像生成（Image Playground） | `ImagePlayground` 框架：`View.imagePlaygroundSheet(isPresented:concept:sourceImage:onCompletion:onCancellation:)`、`ImagePlaygroundViewController`、`ImageCreator`、`ImagePlaygroundConcept`、`ImagePlaygroundStyle` | 18.0+（框架本身） | 让用户给小栈生成一张「合照」，存进小栈相册 | P2 |
| 统一结果构建器 | `SwiftUI.ContentBuilder`（替代 `ToolbarContentBuilder` / `CommandsBuilder`） | 27.0+ | 代码层整洁 | P3 |

> **未验证**：iOS 26/27 的 **Genmoji** 生成没有面向第三方 App 的独立编程接口（Apple 官方把 Genmoji 放在 Messages / Image Playground 内），**不能假设 App 可以程序化生成 Genmoji**。本文不写这一条。

---
### 2.5 「它让 App 看起来像系统的一部分」的具体机制

这一节是本表真正的判断依据。**同一项能力，放在 App 里面 = 第三方 App；放在系统表面上 = 系统的一部分。** 差别不在技术，在位置。

| 能力 | 出现在哪 | 用户的心理模型 | 为什么这是「像系统的」而不是「像 App 的」 |
|---|---|---|---|
| Live Activity | 锁屏（iPhone/iPad）、灵动岛、桌面、CarPlay 桌面、Mac 菜单栏、Apple Watch 智能叠放 | 「我手机锁屏上一直有它」 | 锁屏是**系统级独占表面**，第三方 App 的内容出现在这里时，视觉规格完全由系统定义，用户不会产生「这是某个 App 的东西」的认知。**这是所有能力里性价比最高的一项** |
| 灵动岛 | 灵动岛（刘海区域） | 「它在我眼前」 | 同上。且 Dynamic Island 是 iOS 16.1 起系统级的实时区域，第三方能占用说明它被当作「状态播报」而非「广告位」 |
| Widget | 桌面、今日视图、锁屏、Mac 通知中心、Watch 智能叠放、Vision Pro 3D、CarPlay 小组件屏 | 「我随时能看到它」 | Widget 是用户**主动摆放**的。愿意把一个 App 的小组件摆到桌面上 = 用户已经把它当系统组件看待 |
| Control | 控制中心、锁屏、Action Button、Mac 控制中心、Watch 智能叠放 | 「我随手就能调它」 | Control 是**开关**语义。系统控制中心里出现「小栈」开关，等于它被当设备看待而不是被当 App 看待 |
| Action Button | 机身侧键 | 「我不用打开它就能叫它」 | 这是**系统级快捷入口**，不是 App 内的按钮。Action Button 的自定义入口本身就是 iOS 的「App 快捷动作」槽位 |
| App Shortcut | 快捷指令 App、Siri、Spotlight、快捷指令建议、控制中心 | 「我说一句话它就动」 | 系统级动词。用户在快捷指令里看到「小栈」这个 App 分组时，它和「天气」「提醒」是**同一层级**的东西 |
| Spotlight | 下拉搜索 | 「它在我能搜到的地方」 | Spotlight 是系统的「万能入口」。能被 Spotlight 搜到 = 内容是系统资产 |
| 通知 | 锁屏横幅 / 通知中心 | 「它在跟我说话」 | 通知的措辞、声音、动效全由系统定，App 只提供内容与动作 |
| Handoff | 接力（锁屏底部 / 控制中心 / Dock） | 「我在设备间接得上」 | 跨设备连续性是系统级概念 |
| Universal Links | Safari / 邮件 / 短信点击 | 「这是网页，也是 App 里的同一件事」 | 与系统浏览器、邮件、Safari 共享同一套链接解析 |

**一句话结论**：StackChan 的「嵌入苹果系统」在功能层的本质，是**把「小栈在做什么」这件事从 App 内部搬到锁屏、桌面、控制中心、快捷指令这些系统表面上**。App 本身退居为「完整历史的查看器 + 设置」，这反而是对的 —— 系统 App 里的设置页从来不是核心功能区。

---

## 3. 视觉层嵌入（读法 A）

### 3.1 必须用系统提供的、不能自绘的清单

**这一节的原则：只要系统有，就不许自绘。** 自绘 = 放弃深浅色适配、放弃 Dynamic Type、放弃 iPad 分栏、放弃触感反馈、放弃无障碍。

#### 3.1.1 颜色（语义色，不是色值）

| 用途 | API | 说明 |
|---|---|---|
| 页面底 | `Color.systemBackground` | 主内容背景，随深浅色切换 |
| 分组卡片底 | `Color.secondarySystemBackground` | `List(.insetGrouped)` 里卡片与底槽的对比 |
| 三级填充 | `Color.tertiarySystemFill` / `Color.tertiarySystemBackground` | 更弱的层次 |
| 主文字 | `Color.primary` / `Color.label` | **不要用 `Color.white`/`Color.black`** |
| 次文字 | `Color.secondary` / `Color.secondaryLabel` | 说明、副标题 |
| 三级文字 | `Color.tertiary` / `Color.tertiaryLabel` | 时间戳、脚注 |
| 分隔线 | `Color.separator` / `Color.opaqueSeparator` | **不要手画 0.5pt 线** |
| 强调色 | `.tint` / `Color.accentColor`（默认 `systemBlue`） | 交互色，**不要写 `#007AFF`** |
| 破坏性 | `Color.red` / `role: .destructive` | 删除、清空 |
| 填充背景 | `Color(uiColor: .systemBackground)` 等 UIKit 语义色桥接 | 混用 UIKit/SwiftUI 时 |

#### 3.1.2 布局与容器

| 用途 | API | iOS |
|---|---|---|
| 导航栈 | `NavigationStack` | 16.0+ |
| 钻取链接 | `NavigationLink` + `NavigationLink(value:)` + `.navigationDestination(for:)` | 16.0+ |
| 分组列表 | `List` / `List { }` + `.listStyle(.insetGrouped)` | 13.0+ / `.insetGrouped` 13.0+ |
| 表单 | `Form` | 13.0+ |
| 标签栏 | `TabView` | 13.0+ |
| 标签栏选中态 | `Tab`（iOS 18+）优于 `tabItem` | 18.0+ |
| 标签栏可隐藏 | `.toolbar(.hidden, for: .tabBar)` | 16.0+ |
| 设置页独立 Scene | `Settings` | 13.0+ |
| 设置数据 | `@AppStorage` / `AppPreferences`（Apple 模板生成） | 14.0+ / 17.0+ |

#### 3.1.3 控件与动作

| 用途 | API |
|---|---|
| 开关行 | `Toggle(...).toggleStyle(.switch)` / `Form` 里的 `Toggle` 自动带开关 |
| 标签 + 值行 | `LabeledContent`（16.0+） |
| 图标 + 文字 | `Label("标题", systemImage: "face.smiling")` |
| 搜索 | `.searchable(text:)` |
| 工具栏 | `.toolbar { ToolbarItem(placement: .topBarTrailing) { ... } }` |
| 滑动操作 | `.swipeActions(edge:)` |
| 弹层 | `.sheet(isPresented:)` + `.presentationDetents([.medium, .large])` |
| 确认对话框 | `.confirmationDialog` |
| 警告 | `.alert` |
| 触感（系统级） | `sensoryFeedback`（17.0+）/ `UIImpactFeedbackGenerator` / `UISelectionFeedbackGenerator` |
| 分享 | `ShareLink`（16.0+） |
| 相册选择 | `PhotosPicker`（16.0+） |
| 预览 | `#Preview` |

#### 3.1.4 字体与图标

| 用途 | API | 注意 |
|---|---|---|
| 字体 | `.font(.title)` / `.headline` / `.body` / `.caption` / `.fontDesign(...)` | **不要硬编码字号**。系统文本样式自动跟随 Dynamic Type |
| 圆体品牌音 | `.fontDesign(.rounded)` | **系统自带 SF Pro Rounded**（见 `10-AppleHIG官方核实.md` §1.3）。小栈是圆润的桌面机器人，Rounded 能做到「像系统的、但更可爱」，且**不引入自定义字体**（省掉字体授权 + Dynamic Type 适配两个坑）。这是「品牌表达」与「嵌入系统」唯一不冲突的字体手段 |
| 等宽数字 | `.monospacedDigit()` | 计时器、电量这类跳动数字必须用（08 §5.3 的「跳动大数字」需要它） |
| 图标 | `Image(systemName: "…")` / `Label(…, systemImage:)` | **不要用 emoji 当功能图标**（02 §5.4 #18）；不要自绘 SF Symbols |
| SF Symbols 版本 | Xcode 随附的符号目录 | 提交前用 `SF Symbols` App 核对可用符号与可用系统版本 |

#### 3.1.5 iOS 26 材质（可选增强）

| 用途 | API | iOS |
|---|---|---|
| 玻璃材质 | `Glass` / `View.glassEffect(_:in:)` / `GlassEffectContainer` | 26.0+ |

**用法边界（08 §2 已定，10 §2 已用 HIG 原文确认，此处只补实现约束）**：HIG 原文**明令「内容层不要用 Liquid Glass」**且要求**克制使用**；08 §2 的结论是「玻璃是背景，不是内容容器」。落到代码上就是：**玻璃只给一个主要动作**（例如首页的「叫醒小栈」按钮），不要给整页、给内容文字、给每个图标套玻璃（08 §6.3 判定会立刻变丑）。26 以下必须自动回退到 Material（`.regularMaterial` 等），不能崩、不能留白。

### 3.2 为什么「用系统控件」就等于「嵌入苹果系统」（根本原因）

这是本报告最需要说清的一条。很多人以为「用系统控件」只是审美问题，其实它是**工程问题**：

| 系统控件免费送给我们的东西 | 自绘要付出什么 |
|---|---|
| **深浅色自动切换** | 手写两套颜色 + 监听 trait 变化 + 处理截图时的 `userInterfaceStyle` |
| **Dynamic Type 自动放大** | 手写尺寸计算，否则用户设大字号时直接崩版 |
| **iPad 分栏 / Slide Over / 多窗口自动适配** | 手写响应式断点，而系统的断点是**跟着设备走**的，不是我们定的 |
| **正确的触感反馈** | `Toggle`/`Picker` 自带 `UISelectionFeedbackGenerator`，自绘按钮要自己接 `UIImpactFeedbackGenerator`，且极易在不该震动的地方震动 |
| **VoiceOver 无障碍**（`accessibilityLabel` / `accessibilityValue` / `accessibilityHint` / 焦点顺序 / `accessibilityElement` 组合） | 自绘视图默认对 VoiceOver 是一块空白，**这在开源作品集里是硬伤** |
| **键盘 / 表单自动行为**（`.submitLabel`、焦点移动、`TextField` 的清除按钮） | 全部要自建 |
| **正确的 Hit Target**（44pt 最小可点区） | 自绘容易做成 36pt（02 §4.2 记录过设备端 `.snake-btn` 36×36 的违规） |
| **系统级撤销/重做与菜单**（iOS 26+ 的 `UndoableIntent`、菜单栏） | 无 |
| **新系统版本自动跟进** | 自己适配每一个 iOS 大版本 |

**结论**：一个用了全部系统控件的 App，**它「看起来像系统 App」不是因为我们模仿了像素，而是因为它继承了系统的一切行为**。反过来说，一个自绘了导航栏、分隔线、色值的 App，即便像素对齐了，用户仍会在「切换深色模式时某个角落没变」「系统调大字号时标题被截断」「VoiceOver 念不出这个按钮」这三处露馅。

### 3.3 哪些地方**必须**自绘（这是小栈的品牌表达）

系统控件表达「这是系统的」，自绘表达「这是小栈」。**边界要清楚，否则要么失去品牌，要么失去原生感。**

| 自绘对象 | 为什么必须自绘 | 实现方式 | 对齐既有设计契约 |
|---|---|---|---|
| **小栈的脸（表情）** | 这是小栈本身，系统没有任何「机器人脸」控件 | SwiftUI `Shape` / `Canvas`（`Canvas` iOS 15+）/ 逐帧 `Image` | 02 §3.2 已定：CSS 矢量脸 → SwiftUI `Shape`，8 表情 × 3 tint（lilac/mint/peach），眼/嘴/腮红/眉 |
| 待机动画 / 呼吸 / 漂浮 | 品牌动作，系统没有 | `TimelineView` + `Canvas` 或 `PhaseAnimator`（iOS 17+）；动效曲线沿用 `(0.2, 0.8, 0.2, 1)` | 02 §4.4：呼吸 0.72s、待机漂浮 2.4s、闲置摆动 1.45s |
| 「正在听 / 正在说」指示 | 需要表达小栈的实时状态，不是标准控件 | 呼吸圆环 / 声波条自绘；`Canvas` 逐帧 | 08 §7.2 批评 Dribbble 稿「状态暗示不明」——这里要明确 |
| 12 颗 RGB LED 的映射预览 | 设备特有 | 自绘色带 + `Canvas` | — |
| App 图标 | 系统不提供 | 自绘矢量 → `Icon Composer`（iOS 26+）或导出 PNG | 08 §1.1：glyph 占容器 45–60%，四周留 20–25% 负空间 |

**自绘的禁区（同时踩了两个坑）**：
- 不要把「小栈的脸」放进 `.insetGrouped` 的 `List` 行里当装饰 —— 那会变成「一张图 + 一行字」，立刻退回成普通 App。
- 不要用自绘的导航栏 / 标签栏 / 分隔线 —— 那是纯负收益。

### 3.4 反例警告：哪些「看起来像 iOS」的做法其实是假的原生感

| 反例 | 为什么假 | 正确做法 |
|---|---|---|
| 手写 `Color(red: 0, green: 0.478, blue: 1)` 当强调色 | 放弃了 `.tint` 的语义；系统「强调色」是可访问性设置项（增强对比度、色盲滤镜会改它） | `.tint(...)` 或默认 `accentColor` |
| 手画 0.5pt 灰色分隔线 | 深浅色模式下需要两套值；分隔线在 `List` 里由系统按行自动绘制 | 用 `List` 的分隔线；需要自定义时用 `Color.separator` |
| 自绘顶部导航栏（自己画标题 + 返回箭头） | 丢掉了系统的返回手势、标题栏材质、滚动收起、灵动岛避让 | `NavigationStack` + `.navigationTitle` + `.toolbar` |
| 自绘 Tab Bar | 丢掉 iPad/iOS 18+ 的侧边 Tab、丢掉 iOS 26 的液态玻璃、丢掉横竖屏策略 | `TabView` + `Tab` |
| 用 emoji 当功能图标 | 跨设备字形不同、渲染不可控、违反 02 §5.4 #18 | SF Symbols |
| 硬编码字号（如 `.font(.system(size: 17))`） | 不随 Dynamic Type 缩放 | `.font(.body)` 等语义字体 |
| 手写圆角 + 阴影做卡片 | 系统卡片有正确的材质、层次、阴影与深浅色适配 | `List(.insetGrouped)` 或 `background(.regularMaterial)` |
| 全屏自定义背景色 | 系统 App 会随壁纸/深浅色变化，自绘背景会显得「贴上去的」 | `Color.systemBackground` 或 `.background(.ultraThinMaterial)` |
| 自己实现「共享」按钮 | 丢掉系统的分享面板与「小栈」在系统里的可见度 | `ShareLink` |
| 在 App 里自建一个「待办提醒中心」 | 系统通知中心就是这个东西 | `UNUserNotificationCenter` + 通知动作 |
| 用自定义弹窗代替系统动作表 | 系统 `.confirmationDialog` 自带 iPad 锚定与无障碍 | `.confirmationDialog` / `.alert` |

---
## 4. 信息架构（读法 C）—— 具体的 IA

### 4.1 设计原则（来自用户原话 + 02/08 既有结论）

1. **首页不是功能面板，是小栈的脸。** 08 §7.3 已判定：陪伴型 App 失败的最大原因是「主屏极简但唤起后是高密度卡片，小栈去哪了」。所以首页 = 小栈实时存在 + 一个主要动作。
2. **导航深度 ≤ 2 层。**（02 §5.4 #20）
3. **Tab 数 2–3。** 超过 3 个就开始像工具箱；5 个是 Launcher 思维（02 §1.4 已否决网格化陈列）。
4. **每个画面只保留一个主要动作。** 见 §4.5 检查表。
5. **历史与设置走 push 钻取，不叠层。**（08 §7.3 的直接启示）

### 4.2 IA 图

```
┌──────────────────────────────────────────────────────────────────────┐
│  App 内（唯一「主场」）                                                │
│                                                                      │
│  Tab 1 ── 小栈（Home）           Tab 2 ── 陪伴（Companion）          │
│  ┌────────────────────────┐      ┌────────────────────────────┐     │
│  │                        │      │                            │     │
│  │      ╭──────────╮      │      │  ┌──────────────────────┐  │     │
│  │      │  小栈的脸 │      │      │  │  今日心情            │  │     │
│  │      │  (自绘)   │      │      │  │  [表情网格 3×?]      │  │     │
│  │      ╰──────────╯      │      │  │  ← 一天一记，横向      │  │     │
│  │                        │      │  └──────────────────────┘  │     │
│  │  「早，今天有点困」     │      │  ┌──────────────────────┐  │     │
│  │  (气泡，不是聊天列表)   │      │  │  悄悄话              │  │     │
│  │                        │      │  │  (与小栈的私密对话)   │  │     │
│  │  ● 正在听…（状态明确）  │      │  └──────────────────────┘  │     │
│  │                        │      │  ┌──────────────────────┐  │     │
│  │  ┌────────────────┐    │      │  │  待办提醒            │  │     │
│  │  │  ◎ 叫醒小栈    │    │      │  └──────────────────────┘  │     │
│  │  │  (唯一主要动作)│    │      │                            │     │
│  │  └────────────────┘    │      │  主要动作：[记一下今天]     │     │
│  │                        │      │                            │     │
│  │  (底部不放功能宫格)     │      └────────────────────────────┘     │
│  └────────────────────────┘                                          │
│           │                    │                     │                │
│           │ 1 层钻取            │ 1 层钻取             │ 1 层钻取        │
│           ▼                    ▼                     ▼                │
│   ┌───────────────┐   ┌──────────────────┐  ┌────────────────┐      │
│   │ 设备          │   │ 某一天的心情     │  │ 某次对话        │      │
│   │  电量/信号/温度│   │  (只读这一天)     │  │  (只读这一次)   │      │
│   │ [连接设置]    │   └──────────────────┘  └────────────────┘      │
│   └───────────────┘                                                  │
│                                                                      │
│  Tab 3 ── 设置（独立 Settings Scene，不放 Tab 里）                     │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  [系统设置风格：List(.insetGrouped)]                          │    │
│  │                                                               │    │
│  │   小栈                                                            │    │
│  │     人格包            [樱花粉 ▸]                                │    │
│  │     称呼              [小栈 ▸]                                  │    │
│  │     主动搭话          [ 开关 ]                                  │    │
│  │                                                               │    │
│  │   连接                                                          │    │
│  │     蓝牙设备          [我的小栈 ▸]                              │    │
│  │     局域网发现        [ 开关 ]                                  │    │
│  │                                                               │    │
│  │   通知与系统                                              ●    │    │
│  │     待办提醒          [ 开关 ]                                  │    │
│  │     锁屏实时状态      [ 开关 ]  ← 关掉 = 不启动 Live Activity   │    │
│  │     桌面小组件        [ 开关 ]                                  │    │
│  │                                                               │    │
│  │   隐私                                                          │    │
│  │     语音识别          [仅在设备上 ▸]                            │    │
│  │     数据              [永不入库 · 查看说明 ▸]                   │    │
│  │                                                               │    │
│  │   关于            [版本 1.0 (1)]                                 │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  系统表面（App 之外 —— 这才是「嵌入苹果系统」的主战场）               │
│                                                                      │
│  锁屏 Live Activity    ┌──────────────────────────────────┐          │
│                       │ 😴  小栈有点困了              22:10 │          │
│                       │     ▓▓▓▓▓▓░░░  电量 68%              │          │
│                       │  [摸摸它]              [静音]       │          │
│                       └──────────────────────────────────┘          │
│                                                                      │
│  灵动岛        ╭──────────────────────────╮                          │
│                │ 😴  困困   ▓▓▓▓ 22:10       │  ← compact / expanded  │
│                ╰──────────────────────────╯                          │
│                                                                      │
│  桌面 Widget   ┌───────────┐  ┌───────────┐                         │
│                │  😊       │  │  😊  今天  │                          │
│                │  小栈     │  │  心情：晴  │                          │
│                │  在线 68% │  │  待办 2 项 │                          │
│                └───────────┘  └───────────┘                         │
│                                                                      │
│  控制中心 Control  ┌─────────────┐                                   │
│                    │ 🔇 小栈静音  │                                   │
│                    │ ☀️ 抬头      │                                   │
│                    └─────────────┘                                   │
│                                                                      │
│  快捷指令 App / Siri                                                  │
│    ┌ 小栈 ────────────────┐                                          │
│    │ ▸ 让小栈抬头          │                                          │
│    │ ▸ 摸摸小栈            │                                          │
│    │ ▸ 问小栈今天天气  [地点]│                                         │
│    │ ▸ 让小栈讲个故事        │                                          │
│    └──────────────────────┘                                          │
│                                                                      │
│  Action Button（iPhone 17 等）                                       │
│    长按 → 「让小栈抬头」或「小栈静音」（用户自己在设置里指派）        │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 Tab 为什么是 2 个（而不是 3 个）

| 候选 Tab | 收不收 | 理由 |
|---|---|---|
| 小栈（Home） | **收，必有，且是 Tab 0** | 品牌的锚点。用户打开 App 的第一眼必须是「小栈在」，不是功能列表 |
| 陪伴（Companion） | **收** | 承载「有时间维度的内容」：今日心情、悄悄话、待办。这三样在 02 的设备端分属 3 个应用（心情日记 / 小栈悄悄话 / 番茄钟），但它们在 iOS 上是**同一类东西：和小栈有关的历史**。合成一个 Tab，用 `List` 分组，而不是三个 Tab。→ 这正是 02 §1.3「一次只显示一张功能卡」的手机化：手机上不横滑切换，用纵向列表 |
| 设备 | **不收** | 设备状态是**低频**信息，藏在「小栈」Tab 的 1 层钻取里。做成 Tab 会让用户觉得这是个遥控器 App |
| 游戏 | **不收** | 02 §5.4 #3 已否决「六宫格、多功能堆叠」。游戏做成 Live Activity + Widget 更好玩，且不污染主 IA |
| 相册 | **不收** | 收进「陪伴」Tab 的钻取层 |
| 设置 | **不做 Tab** | 用**独立的 `Settings` Scene**（iOS 13+ `Settings` 场景），App 内通过系统「设置」入口进入。**这是「像系统 App」最强的信号之一** —— 系统 App 都有独立设置页，而不是自己画一个设置 Tab |

> **重要**：iOS 26 起的系统设置 App 会把 App 的独立设置页收进「Apps」分组下。独立 Settings Scene 是 Apple 明确支持的机制。

### 4.4 哪些功能**不应该**进 App，而应该做成系统表面

这是本节最有价值的部分 —— **每做对一个，就是「嵌入苹果系统」；每做错一个，就是「又做了个功能面板」**。

| 功能 | 错的做法 | 对的做法 | 为什么 |
|---|---|---|---|
| 小栈的实时状态 | App 首页顶部一个状态条 | **Live Activity**（锁屏 + 灵动岛） | 状态的价值在于「不用打开 App 就知道」 |
| 小栈的情绪变化 | App 内轮播卡片 | **Widget**（桌面）+ Live Activity 里的表情 | 情绪是「随时可瞥一眼」的信息 |
| 今日心情 | App 内一个统计图 | **锁屏 Live Activity 一行** + Widget | 每天一行，不是一张图 |
| 待办提醒 | App 内「待办」列表页 + App 内弹窗 | **系统通知**（`UNUserNotificationCenter`）+ 通知动作 | 用户不需要为「被提醒」而打开 App |
| 番茄钟 | App 内计时器页 + App 内通知 | **Live Activity 显示跳动数字**（08 §9 #9）+ 通知 | 计时要能锁屏看，这是 Live Activity 的经典用例 |
| 静音 / 叫醒 | App 内设置里的开关 | **控制中心 Control** + **Action Button** | 高频开关应该零次点击 |
| 「摸摸小栈」 | App 内按钮 | **App Shortcut**（Siri / 快捷指令 / Spotlight）+ Live Activity 交互按钮 | 动作应该在「说话」和「按一下」之间发生 |
| 「问小栈天气」 | App 内搜索框 | **App Shortcut**（参数化：地点） | 系统级动词比 App 内搜索更快 |
| 拍照给小栈看 | App 内相机页（一个完整相机 UI） | **PhotosPicker** 选一张 + 相机入口藏在 `sheet` 里 | 相册选择器是系统组件，比自绘相机更原生 |
| 历史对话 | App 首页塞聊天列表 | **陪伴 Tab 的 1 层钻取** | 首页留给脸 |
| 设备设置（温度、电量） | App 内独立页 | **小栈 Tab 的 1 层钻取** + Widget 上的电量角标 | 低频 |

### 4.5 「每个画面只保留一个主要动作」落地检查表

每个界面交付前逐条打勾，任何一条不过就重做。

| # | 检查项 | 判定 |
|---|---|---|
| 1 | 这个画面上，**视觉权重最高且可点击**的元素有几个？ | 必须恰好 1 个。其余要么不可点，要么降级为次要样式 |
| 2 | 这个画面上有没有第二个「彩色大按钮」？ | 有 → 二选一。颜色是稀缺资源，用掉一次就少一次 |
| 3 | 主要动作的文案是不是动词 + 具体结果？ | 「叫醒小栈」而不是「唤醒」；「记一下今天」而不是「添加」 |
| 4 | 去掉主要动作后，剩余内容是否还能构成一个完整画面？ | 不能 → 说明是弹窗的错，应该做成 `.sheet` |
| 5 | 这个动作能不能用一句话说清楚「按了会发生什么」？ | 不能 → 是功能菜单，不是动作。改写成 `NavigationLink` |
| 6 | 是不是有「更多」按钮藏了 3 个以上功能？ | 是 → 这些功能属于系统表面或另一个 Tab，不属于这里 |
| 7 | 这个画面有没有第二个导航层级？ | 有 → 违反 02 §5.4 #20，退回 |
| 8 | 主要动作是不是被任何系统表面（通知、Live Activity、快捷指令）重复表达了？ | 是 → App 里那个可以删。**能被系统表达的功能，就不要在 App 里再表达一次** |
| 9 | 画面里有没有自绘的导航元素？ | 有 → 删掉换系统控件 |
| 10 | 关掉深色模式，这个画面还成立吗？ | 不成立 → 说明用了硬编码色值（§3.4） |

---

## 5. 权限与隐私的原生表达

### 5.1 触发时机：按需触发，绝不在启动时索要

**这是 App Store 审核与「像系统 App」的双重要求。** 系统 App 也有权限弹窗，但都是在用户做出明确意图时弹的。

| 权限 | 触发时机（唯一正确时机） | 错误时机（常见坑） |
|---|---|---|
| 麦克风 `NSMicrophoneUsageDescription` | 用户在首页点「按住说话」或「语音输入」的**那一刻** | App 启动即请求；进入首页就请求 |
| 语音识别 `Speech`（`NSSpeechRecognitionUsageDescription`） | 与麦克风**同时**、同一意图下请求（用户已经说要说话了） | 单独一个「开启语音功能」的开关在设置里提前索要 |
| 相机 `NSCameraUsageDescription` | 用户点「拍给小栈看」的**那一刻** | 首页有相机入口就提前请求 |
| 蓝牙 `NSBluetoothAlwaysUsageDescription` | 用户点「连接我的小栈」进入**配对流程**时 | App 启动即请求蓝牙 |
| 本地网络 `NSLocalNetworkUsageDescription` | 同上，**和蓝牙一起**，在同一个「连接小栈」流程里 | 单独一个「局域网发现」开关在启动时请求 |
| 通知 | 用户完成第一次「添加一条待办」或主动打开「待办提醒」开关时（**给一个上下文**） | App 启动即弹「允许通知？」 |
| 跟踪 `NSUserTrackingUsageDescription` | **完全不请求**（我们不做广告/追踪） | —— |

**组合原则**：蓝牙 + 本地网络应该合并成一次「连接小栈」的引导流程（先 BLE，找不到再局域网）。系统弹窗只有一次性的机会，所以要等用户表达意图。

### 5.2 权限文案（写成人话，且说清后果）

Apple 的审核指南要求权限描述要**具体说明用途**，而不是泛泛说「需要访问 XXX」。以下是可直接用的候选文案。

| 权限键 | 候选文案（中文） | 英文候选 | 写法要点 |
|---|---|---|---|
| `NSMicrophoneUsageDescription` | **「你想跟小栈说话时，我们才会听。」** | "We only listen when you want to talk to StackChan." | 说清**何时**发生，不是「需要麦克风来提供功能」 |
| `NSSpeechRecognitionUsageDescription`（若走 Speech） | **「把你的话变成文字发给小栈。可以只在本机处理。」** | "We turn your words into text for StackChan. Recognition can stay on this device." | 同时说明「可离线」 —— 这是我们隐私承诺的一部分 |
| `NSCameraUsageDescription` | **「只有你让它拍照时，才会打开相机。」** | "The camera opens only when you ask StackChan to take a photo." | 说清「只有你让它」 |
| `NSBluetoothAlwaysUsageDescription` | **「用来找你的小栈并跟它说话。」** | "Used to find and talk to your StackChan." | 说清对象，不说「蓝牙通信」 |
| `NSLocalNetworkUsageDescription` | **「小栈和你的手机在同一 Wi‑Fi 时，用它来找到小栈。」** | "Used to find StackChan when it's on the same Wi-Fi as your phone." | 说清触发条件（同一 Wi-Fi） |
| `NSUserTrackingUsageDescription` | **不写 —— 我们不请求跟踪权限。** | —— | 不请求 = 不写这一项 |

**写法规则**：
1. 开头讲**时机**，不是讲功能（「你想说话时才听」优于「麦克风用于语音输入」）。
2. 讲**用途对象**（「你的小栈」优于「蓝牙连接」）。
3. 能承诺**本地/离线**就写上（我们的差异化优势）。
4. 不用「为了提供更好的体验」这类空话。

### 5.3 App 隐私清单（Privacy Manifest）与「私人数据永不入库」的承诺如何对齐

**我们的项目承诺**（开源分两层）：通用引擎 + 通用人格包开源；**个人定制数据永不入库**。

**承诺与系统机制的对齐点**：

| 承诺 | 系统机制 | 具体做法 |
|---|---|---|
| 「不收集」 | `PrivacyInfo.xcprivacy` 的 `NSPrivacyCollectedDataTypes` 数组 | 数组留空 = 声明「不收集任何数据类型」。**注意**：用到的第三方 SDK 若声明收集，会被合并进报告 —— 这也是 §6 选型时的约束 |
| 「不跟踪」 | `NSPrivacyCollectedDataTypeTracking` / 不请求 `NSUserTrackingUsageDescription` | 全部不写 = 不进 IDFA |
| 「本地处理」 | 无需特殊声明，但影响 `NSPrivacyAccessedAPITypes` | 若用了 `UserDefaults`，必须申报 `NSPrivacyAccessedAPIType` = `NSPrivacyAccessedAPICategoryUserDefaults`，并给出 reason code。**这是硬性要求，漏了会被 App Store Connect 拒绝或导致构建警告** |
| 「小栈在本地」 | 权限文案里明说 | 见 §5.2 |
| 「用户能看能删」 | App 内提供「数据 → 查看/清空」，并支持导出 | 建议进 `Settings` 的「隐私」组 |

**`NSPrivacyAccessedAPITypes` 必报清单（按我们的技术栈预判）**：

| 类别 | 我们用在哪 | 是否需要申报 |
|---|---|---|
| `NSPrivacyAccessedAPICategoryUserDefaults` | `UserDefaults` / `@AppStorage` 存设置项 | **需要**（reason 用 Apple 提供的 `CA92.1` 之类应用内偏好代码 —— 具体 code 取值需以 Apple 官方清单为准，**本文未逐一核实 code，标注未验证**） |
| `NSPrivacyAccessedAPICategoryFileTimestamp` | 读文件 mtime（若有） | 需要时再报 |
| `NSPrivacyAccessedAPICategorySystemBootTime` | 读启动时间（若有） | 需要时再报 |
| `NSPrivacyAccessedAPICategoryDiskSpace` | 查剩余空间（若有） | 需要时再报 |
| `NSPrivacyAccessedAPICategoryActiveKeyboards` | 若做自定义键盘 | **我们不做**，不报 |

> **诚实标注**：Apple 对每个 reason code 有严格枚举（形如 `CA92.1`、`35F9.1`）。**本文未逐一抓取官方 reason code 全表，落地时必须以 `Describing use of required reason API` 官方文档为准。**

### 5.4 其他原生隐私表达

| 项 | 做法 |
|---|---|
| 麦克风指示 | iOS 系统的橙色指示点会替我们显示 —— 这是**免费的用户信任信号**，不要试图绕过 |
| 语音转写落盘 | 默认只在内存；落盘必须放在 `NSFileProtectionComplete` 保护的容器里 |
| 蓝牙配对密钥 | 存 Keychain（`Security` 框架），不存 `UserDefaults` |
| 日志 | 用 `os.Logger` 打点，**不要把用户内容写进日志** |
| 截图保护 | 情绪日记等私密内容可用 `UIApplication.shared.isProtectedDataAvailable` 感知锁屏；如需防截屏可用 `UITextField.isSecureTextEntry` 技巧（**技巧性 API，Apple 未公开支持，仅作兜底**） |

---
## 6. 可复用方案（不自造）

### 6.1 清单

可复用方案：
  - **SwiftUI**（Apple 官方框架） 用途：全部界面层  许可/协议：Apple SDK 许可（随 Xcode 分发，不可再分发）  接入成本：零（框架自带）  替代自造的：手绘导航栏、手绘列表、手绘开关、自定义动效引擎
  - **WidgetKit**（Apple 官方框架） 用途：桌面小组件 / 锁屏配件 / 实时活动 UI / 控制中心控件  许可/协议：Apple SDK 许可  接入成本：低（需加 Widget Extension target）  替代自造的：自建「桌面挂件」系统、自建控制中心面板
  - **ActivityKit**（Apple 官方框架） 用途：锁屏实时状态 + 灵动岛  许可/协议：Apple SDK 许可  接入成本：中（需 Activity Attributes + Widget Extension + Info.plist 的 `NSSupportsLiveActivities`）  替代自造的：自建锁屏通知样式、自绘灵动岛占位
  - **App Intents**（Apple 官方框架） 用途：Siri / 快捷指令 / Spotlight / Action Button / Widget 交互 / Control 动作  许可/协议：Apple SDK 许可  接入成本：中（一个 `AppShortcutsProvider` 就能让全部系统表面同时开口）  替代自造的：自建语音助手命令层、自建快捷指令协议、自建 Action Button 处理
  - **Core Haptics**（Apple 官方框架） 用途：小栈的定制触感波形（摸头 / 生气 / 被夸）  许可/协议：Apple SDK 许可  接入成本：中（波形调参，需真机反复试）  替代自造的：`UIImpactFeedbackGenerator` 的四种固定样式（做不出"小栈的情绪"）
  - **ImagePlayground**（Apple 官方框架） 用途：让用户给小栈生成合照（系统级图像生成界面）  许可/协议：Apple SDK 许可  接入成本：低（`imagePlaygroundSheet` 一行）  替代自造的：自建生图界面、自接文生图 API（要后端 + 成本）
  - **Apple 官方示例「Emoji Rangers」** 用途：Live Activity + 交互式 Widget + 动画 的官方参考实现  许可/协议：Apple 示例代码许可（可读、可借鉴，不可直接搬运闭源发布）  接入成本：读代码即可  替代自造的：自己摸索灵动岛布局与 Widget 交互的写法
  - **SFSafeSymbols**（github.com/SFSafeSymbols/SFSafeSymbols，MIT，1897★） 用途：类型安全的 SF Symbols 访问  许可/协议：MIT  接入成本：极低（SPM 一行）  替代自造的：手写 SF Symbols 字符串常量（拼错不报错、图标版本不可控）
  - **SQLite.swift**（github.com/stephencelis/SQLite.swift，MIT，10185★） 用途：本地情绪日记 / 记忆库的关系型存储  许可/协议：MIT  接入成本：低  替代自造的：自写 SQLite 封装、手写 JSON 文件存储（并发写会坏）
  - **lottie-ios**（github.com/airbnb/lottie-ios，Apache-2.0，26917★） 用途：**备选** —— 若小栈的待机动画改由设计工具出稿，用 Lottie 播放  许可/协议：Apache-2.0  接入成本：中（需绑定动画文件，体积涨）  替代自造的：`TimelineView` 逐帧绘制复杂动画
  - **rive-ios**（github.com/rive-app/rive-ios，MIT，848★） 用途：**备选** —— 同上，状态机驱动表情动画  许可/协议：MIT  接入成本：中  替代自造的：`PhaseAnimator` 组合式动画
  - **SwiftFormat**（github.com/nicklockwood/SwiftFormat，MIT，8941★） 用途：代码格式化（开源项目的基本工程素养）  许可/协议：MIT  接入成本：极低（.swiftformat 配置）  替代自造的：手改格式
  - **SwiftLint**（github.com/realm/SwiftLint，MIT，19771★） 用途：静态检查（强制 SF 命名、`@AppStorage` 而非散落 `UserDefaults` 等）  许可/协议：MIT  接入成本：极低  替代自造的：无
  - **swift-log**（github.com/apple/swift-log，Apache-2.0，4053★） 用途：结构化日志  许可/协议：Apache-2.0  接入成本：极低  替代自造的：`print` 满天飞
  - **ESP-IDF**（github.com/espressif/esp-idf，Apache-2.0，**本轮 GitHub API 限流未核实 star/许可元数据**） 用途：ESP32-S3 固件  许可/协议：Apache-2.0（未在本轮验证）  接入成本：中高  替代自造的：自写 ESP32 固件框架
  - **ESPHome**（github.com/esphome/esphome，11945★，GitHub API 返回许可 NOASSERTION，**LICENSE 文件未核对**） 用途：**备选** —— 如果后续想把小栈接入 Home Assistant 生态  许可/协议：NOASSERTION（未核实，仓库声明为 MIT）  接入成本：中高  替代自造的：自建 HA 集成
  - **Nimble**（github.com/Quick/Nimble，Apache-2.0，4834★） 用途：**备选** —— 若需要写单元测试（Live Activity 的 `ContentState` 编码、Intent 参数解析）  许可/协议：Apache-2.0  接入成本：低  替代自造的：裸 XCTest（可，但 Nimble 的 matcher 可读性更好）

采用决策：**混合**

理由：
1. **系统框架层 → 全部复用，不自造。** ActivityKit / WidgetKit / App Intents / Core Haptics 这四个是「嵌入苹果系统」的物理基础，自造等于放弃整个产品命题。它们没有替代品。
2. **小栈的脸 → 自造。** 这是品牌资产。系统控件里没有「小栈的脸」，任何第三方库（Lottie / Rive）也只是**播放**我们自己的资产，不产生资产本身。02 §3.3 已定「同一套底座，不拼图标库」，用 Lottie/Rive 会引入「外部图标库」的味道，与该结论冲突。
3. **工程基建 → 复用。** SFSafeSymbols / SwiftLint / SwiftFormat / SQLite.swift / swift-log 都是无审美主张的基础设施，零争议复用。
4. **动画引擎 → 暂不自造，暂不复用。** 先用 `TimelineView` + `Canvas` 做（`Canvas` iOS 15+），若表达力不够再评估 Lottie/Rive。理由：02 §4.4 的动效签名 `(0.2, 0.8, 0.2, 1)` 和 8 表情 × 3 tint 是**规则化**的，规则化动画用代码表达比用设计工具更轻更可控。
5. **固件 → 复用 ESP-IDF**（若项目已有则沿用，见项目 `stackchan_ai` / 固件目录）；**HA 生态暂不接**。

### 6.2 复用时必须守住的约束

| 约束 | 为什么 |
|---|---|
| 第三方库必须能进 `PrivacyInfo.xcprivacy` 的分析 | 任何带网络/埋点的 SDK 会污染「私人数据永不入库」的承诺 |
| 优先 SPM（Swift Package Manager）依赖 | SwiftUI 时代，SPM 依赖不会产生 CocoaPods 的工程污染，对开源作品集加分 |
| 动画/图像资源自己画，不引外部图标库 | 02 §5.4 #18、#15 |
| 不引 UI 组件库（如 `UIKit` 第三方控件集） | 它们自带自己的配色与间距，会污染 §3 的「系统控件优先」原则 |

---

## 7. 可行性边界（诚实标注）

### 7.1 部署目标版本

| 目标 | 能否拿到全部能力 | 建议 |
|---|---|---|
| iOS 16.0+ | Live Activity / Widget / App Intents / Shortcuts / Core Haptics 全部可用；但**无 Control Center 控件、无 Live Activity 交互、无 iOS 26 玻璃** | 最低可用线 |
| **iOS 17.0+** | 补齐 `LiveActivityIntent`（锁屏/灵动岛直接交互）、`AppIntentConfiguration`（可配置小组件）、`Settings` 的 `AppPreferences` | **建议最低线** |
| **iOS 18.0+** | 补齐 `ControlWidget`（控制中心 / 锁屏控件 / Action Button 控件）、`IndexedEntity`（Spotlight 实体）、`Tab` API | **建议主力线**（覆盖 iPhone 16 及以后多数机型） |
| iOS 26.0+ | 补齐 `glassEffect(_:in:)` / `Glass` / `GlassEffectContainer` | 玻璃是**渐进增强**，26 以下必须自动回退到 Material，不能崩 |
| iOS 27.0+ | `ArrangementView`、`ToolbarOverflowMenu`、`LongRunningIntent`、`SyncableEntity` | 只做 iOS 27 机型用户的增强，**不能成为主路径** |

**结论**：**最低 iOS 17.0，主力 iOS 18.0**，iOS 26/27 特性全部按 `if #available` 渐进增强。这样 90% 的设备都能拿到「Live Activity + 快捷指令 + 触感」，而 iPhone 17 用户额外拿到玻璃与新布局。

### 7.2 时间成本与后端依赖

| 能力 | 实现成本 | 需要后端？ | 说明 |
|---|---|---|---|
| Live Activity（本地更新） | **中** | 否 | 只需 App 前台/后台跑着时用 `Activity.update` 推送 |
| Live Activity 远程推送 | **高** | **是** | 需要 APNs provider 服务端签发 token 推送 |
| 灵动岛 | 中 | 否 | 与 Live Activity 同一套代码 |
| Widget（静态/交互） | 中 | 否 | Widget 靠 `WidgetCenter.reloadTimelines` 更新；交互走 `Button(intent:)` |
| 控制中心 Control | 中 | 否 | 与 Widget 共用 Extension target |
| App Intents + App Shortcuts | **中** | 否 | 一个 `AppShortcutsProvider` 同时点亮 Siri / 快捷指令 / Spotlight / Action Button |
| Core Haptics 波形 | **中**（调参耗时） | 否 | 代码简单，**波形好不好听要真机反复试** |
| Action Button | **低** | 否 | 不写代码，只是提供 `AppShortcut` 供用户指派 |
| Spotlight 索引 | 低 | 否 | `CSSearchableIndex` |
| 权限流程（按需触发） | 低 | 否 | 主要是文案与时机设计 |
| Privacy Manifest | **低**（但必做） | 否 | 一个 `PrivacyInfo.xcprivacy` 文件 |
| CloudKit 同步 | 中 | **是**（iCloud） | 且需要 Apple Developer 账号配置容器 |
| Handoff | 低 | 否 | `NSUserActivity` |
| Universal Links | 低 | 否 | 需要域名 + `apple-app-site-association` 文件（**需要有可访问的域名**） |
| 通知 / APNs | 中 | **是** | APNs 需要证书 + 服务端 |
| 本地网络发现 | 中 | 否 | `NWBrowser` + Bonjour 服务类型（`_stackchan._tcp` 之类，需在 `Info.plist` 声明 `NSBonjourServices`） |
| iOS 26 玻璃 | 低 | 否 | 一层 `.glassEffect`，但要在 26 以下优雅回退 |
| iOS 27 `ArrangementView` | 低 | 否 | 只在 27 上生效，其他走 fallback |

### 7.3 明确的阻塞：本机是 Windows，没有 Xcode

**这是本任务最大的硬阻塞，必须诚实列出。**

以下能力**只能在 macOS + Xcode 上编译、预览、运行、真机验证**，本轮（Windows 环境）**全部未验证**：

| 无法在本机验证的事 | 为什么 | 影响 |
|---|---|---|
| 任何 Swift 代码的**编译与类型检查** | 无 Xcode / 无 Swift toolchain for iOS SDK | 本文所有 API 名与版本号**来自 Apple 官方文档**（已核对 JSON frontmatter），但**没有任何一行代码被编译过** |
| `ActivityKit` 的 `ActivityAttributes` / `ActivityContent` 的实际泛型签名 | 同上 | API 名已验证，**参数标签顺序未逐一核对** |
| Widget Extension target 的实际配置（`NSSupportsLiveActivities`、App Group、Widget 预览） | 同上 | 官方文档已确认 key 名，**target 搭建流程未跑过** |
| `ControlWidget` 的实际呈现（控制中心图标大小、深浅色、锁屏位置） | 同上 | 需真机 |
| `CoreHaptics` 波形的**实际手感** | 同上 | 波形是主观的，**必须在真机上和用户一起调** |
| `glassEffect(_:in:)` 在真实内容上的可读性 | 同上 | 08 已从截图判断「玻璃只承载极简动作」，但**没在真机上验证过小栈的脸放在玻璃上是否可读** |
| 灵动岛 `DynamicIslandExpandedRegion` 在真机上的裁切 | 同上 | 官方文档提到「iPhone Duo / 横屏 / 多个 Live Activity 时会变窄」，**真机行为未验证** |
| Dynamic Type 放大到 AX5 时的布局 | 同上 | §3.2 说「用系统控件就自动适配」是**原理性结论**，**不是实测结论** |
| iPad 分栏 / Slide Over | 同上 | 同上 |
| VoiceOver 朗读顺序与文案 | 同上 | §5.2 的权限文案**未经 VoiceOver 实测** |
| 通知、Live Activity、Widget 在锁屏上的真实观感 | 同上 | 08 的 Live Activity 视觉规范来自**截图实测**，不是我们的实现 |
| 通用链接（Universal Links） | 需要域名 + HTTPS 服务器 | 无 |
| APNs / Live Activity push | 需要开发者账号 + 服务端 | 无 |

**建议的解锁顺序**（拿到 Mac 后按此顺序验证，每步都能独立出成果）：
1. 空白 SwiftUI App + Widget Extension → 跑通 `NSSupportsLiveActivities` → 出一个最简 Live Activity 出现在锁屏。**这一步验证完，「嵌入苹果系统」的命题就成立了一半。**
2. 加 `AppShortcutsProvider` → 在快捷指令 App 里看到「小栈」分组 + 在 Spotlight 里能搜到。
3. 加 `ControlWidget` → 控制中心出现小栈控件。
4. 加 `CoreHaptics` → 调 3 条波形（摸头 / 生气 / 被夸），和用户一起定手感。
5. 补 `PrivacyInfo.xcprivacy` → 跑一次 Xcode 的隐私报告。
6. 最后做视觉层：系统控件铺满 + 自绘的脸 + iOS 26 玻璃回退。

### 7.4 与「开源求职作品」的取舍建议

| 项 | 建议 | 理由 |
|---|---|---|
| 完整 Live Activity + 灵动岛 | **必做** | 这是作品集里最能证明「我懂 iOS 平台」的一屏 |
| 完整 Widget / Control / Shortcut 三件套 | **必做** | 证明「我知道系统表面不止 App 一个」 |
| 完整权限流程 + Privacy Manifest | **必做** | 证明「我懂隐私与审核」 |
| Live Activity 远程推送 | **可不做** | 需要后端，与「iOS 平台能力」主线无关，且会分散精力 |
| CloudKit 同步 | **可不做** | 需要 iCloud 容器配置，且不是「嵌入系统」的核心 |
| Handoff | **可不做** | 收益低，且难在作品集里被看到 |
| iOS 27 专属特性（`ArrangementView` 等） | **不做** | 会把项目门槛抬到只有最新系统能用，招聘方未必有 |

---
## 8. 未验证项清单（务必阅读）

以下内容本轮**没有拿到官方出处**，或**拿到了出处但没有验证到可用级别**。按纪律标注，不猜。

### 8.1 API 名 / 可用性未验证

| # | 项 | 状态 | 原因与后续动作 |
|---|---|---|---|
| 1 | `ActivityConfiguration` / `ActivityContentState` 的独立符号页 | **未验证（独立页 404）** | 但 Apple 官方 "Displaying live data with Live Activities" 文章的示例代码里明确使用了 `ActivityConfiguration(for:content:dynamicIsland:)`（位于 **WidgetKit** 命名空间）以及 `Activity.ContentState` typealias。**这两个名字在文中出现并被使用，可信度高**；但「是否存在 `/documentation/WidgetKit/ActivityConfiguration` 独立页」未证实 |
| 2 | `AccessoryWidget` 协议 / `AccessoryInline` / `AccessoryCircular` / `AccessoryRectangular` | **未验证（独立页 404）** | 但 `WidgetFamily` 的 `.accessoryCircular` / `.accessoryCorner` / `.accessoryRectangular` / `.accessoryInline` 四个 case 已从官方 `WidgetFamily` 符号页确认。落地时以这四个 case 为准 |
| 3 | `WidgetConfiguration` 协议 | **未验证（独立页 404）** | 已确认存在的具体配置类型：`StaticConfiguration`（14.0+）、`AppIntentConfiguration`（17.0+）、`IntentConfiguration`（14.0+） |
| 4 | `ControlWidget` 协议 | **未验证（独立页 404）** | 但官方 "Creating controls to perform actions across the system" 文章的示例代码中明确 `struct TimerToggle: ControlWidget`，**该名字在官方示例里被使用** |
| 5 | `NSUserActivity` 的具体 Handoff API | **部分验证** | `Foundation.NSUserActivity` 符号页已取到（iOS 8.0+）。但 Handoff 的完整流程（`NSUserActivity` + `activityType` + `becomeCurrent()` + Info.plist 的 `NSUserActivityTypes`）本轮未逐项核对 |
| 6 | `Security` 框架的 Keychain API 名 | **未验证（符号页 404）** | Keychain 本身是公认 API，但具体类型名（如 `SecItemAdd`）本轮未从官方页取到 |
| 7 | `AVAudioSession` / `AVAudioEngine` / `AVAudioRecorder` | **未验证（符号页 404）** | `AVFoundation` 框架已确认（`AVCaptureSession` iOS 4.0+、`AVCaptureDevice` iOS 4.0+）。音频录制类的具体类型名本轮未逐个核实 |
| 8 | `SoundRecognition` 框架 | **未验证（符号页 404）** | 本轮未取到官方页，**因此本报告不在能力表中列入 Sound Recognition** |
| 9 | `NSSpeechRecognitionUsageDescription` | **未验证** | 本文只引用了已确认的 `NSMicrophoneUsageDescription`（iOS 7.0+）。若使用 `Speech` 框架，**大概率还需要这个权限键，但本轮未核实** |
| 10 | `NSPrivacyAccessedAPIType` 的 reason code 全表 | **未验证** | 键名与结构已确认（`NSPrivacyAccessedAPITypes` / `NSPrivacyAccessedAPIType` / `NSPrivacyAccessedAPITypeReasons`），但具体 code（如 `CA92.1`）本轮**未逐条抓取官方枚举表**，落地必须查 `Describing use of required reason API` |
| 11 | `NSSupportsLiveActivities` / `NSSupportsLiveActivitiesFrequentUpdates` 的 Info.plist 路径 | **部分验证** | 两个 key 名已从 ActivityKit 官方索引确认；本轮未取到 `BundleResources` 下的独立符号页 |
| 12 | `WidgetKit` 独立符号页 | **部分验证** | 框架总览页与 `Controls-Collection`、`LiveActivities-Collection` 等分节已取到；`/documentation/WidgetKit` 单独页 404，框架总览页已下载并核对 |
| 13 | `ImagePlayground` 框架的最低版本 | **未验证** | 符号页已取到（含 `imagePlaygroundSheet` / `ImageCreator` / `ImagePlaygroundConcept` / `ImagePlaygroundStyle` / `ImagePlaygroundViewController` / `ImagePlaygroundOptions`），但该页 frontmatter 的 availability 为空 |
| 14 | iOS 26 的 `Icon Composer` App | **未验证** | 未从官方页确认 |
| 15 | `Genmoji` 的第三方编程接口 | **结论：不存在公开接口** | 本轮未取到官方页说明其不可用，**但本文明确不写这一项**，以免误导 |
| 16 | `NSBonjourServices`（本地网络服务声明） | **未验证** | 未从官方页取到 |
| 17 | 灵动岛在 iPhone 17/18 上的**具体尺寸与裁切行为** | **未验证** | 08 已从截图给出 62pt 顶部安全区等**估算值**，但**官方数值未核实**（08 §9 已标注同一问题） |

### 8.2 结论性判断（不是 API，但会影响设计）

| # | 判断 | 依据 | 置信度 |
|---|---|---|---|
| 1 | iOS 27 是当前发布版（2026-09），iOS 26 是上一代 | Apple 官方 `Updates/SwiftUI` 与 `Updates/UIKit` 最新条目为 "September 2026"；`Updates/CoreSpotlight` 有 "July 2026" 条目；`AppIntents/adopting-app-intents-to-support-system-experiences` 的 availability 为 iOS 27.0.0 | **高** |
| 2 | Action Button 没有独立 API，走 App Shortcuts | 官方 "Hardware interactions" 文章明确写 "people can assign any App Shortcuts you create"，且 Control 可放到 Action Button | **高** |
| 3 | iOS 27 的 `ArrangementView` 是「分主次」的官方答案 | 官方 SwiftUI 更新日志原文："Arrange primary and secondary content using an adaptive layout" | **高** |
| 4 | `ForegroundContinuableIntent` 在 iOS 26 起已废弃（availability 区间 16.4–26.0） | 官方 frontmatter | **高**（落地时改用新的 `supportedModes` / `IntentSystemContext.currentMode`） |
| 5 | 通用链接需要自有域名 | Apple 的 Associated Domains 文档机制上要求域名的 `apple-app-site-association` 文件 | 中（机制理解，流程未验证） |

### 8.3 本轮**确实没有做**的事（避免误导）

- **没有写任何 Swift 代码**，没有建 Xcode 工程，没有编译，没有真机验证。
- **本轮我自己没有抓取 HIG 的 Live Activities / Widgets / Action button 页面**（本轮聚焦 API 层）。HIG 的排版 / 材质 / 颜色硬约束由姊妹文档 `10-AppleHIG官方核实.md` 用真实 HIG 页原文核实，**本文 §3.1.5、§3.4 已与之对齐**。
- **没有验证任何 API 在具体 Xcode 版本下的编译结果**。
- **没有查 `swift-argument-parser` 等未通过 GitHub API 核实的仓库**（API 限流）。

---

## 9. 落地清单：最该做的 8 项（按优先级）

> 排序依据：**「做了之后，用户会不会更觉得这是系统的一部分」** × **投入产出比** × **作品集说服力**。

| 序 | 做什么 | 读法 | 为什么排这个位置 | 成本 | 后端 |
|---|---|---|---|---|---|
| **1** | **Live Activity + 灵动岛**：`ActivityAttributes` 定义小栈的静态/动态状态，`ActivityContent` 带 `relevanceScore`，`ActivityConfiguration(for:content:dynamicIsland:)` 出锁屏卡 + 灵动岛 compact/expanded | B | **唯一能让用户「不用打开 App 就看到小栈」的能力**。锁屏是系统独占表面，第三方内容出现在那里，用户的心理模型直接变成「这是系统的一部分」。也是作品集里最亮的一屏 | 中 | 否 |
| **2** | **App Intents + App Shortcuts**：一个 `AppShortcutsProvider` 同时点亮 Siri、快捷指令 App、Spotlight、Action Button | B | **一次投入，四个系统入口**。而且它直接解决 02 §4.4 提的「唤醒后不知道该干什么」—— 用户可以直接说「让小栈抬头」 | 中 | 否 |
| **3** | **首页 = 小栈的脸（自绘）+ 唯一主要动作** | A + C | 这是「嵌入苹果系统」在**视觉层**的落点，也是产品定位的落点。用全部系统控件承载界面（`List(.insetGrouped)` / `NavigationStack` / 语义色 / SF Symbols），只有脸自绘。**同时它是唯一无法被系统替代的部分** | 中 | 否 |
| **4** | **Interactive Widget**：桌面小组件显示当前表情 + 今日心情；`AppIntentConfiguration` 做到可配置 | B | 用户**主动把小组件摆到桌面上** = 最高形式的「我接受它进我的系统」。Widget 的锁屏/桌面视觉规格由系统定，天然不像第三方 | 中 | 否 |
| **5** | **Core Haptics 自定义波形**：摸头 / 生气 / 被夸 三条波形 | B | **iOS 独有能力，也是「陪伴感」最直接的载体** —— 摸一下手机，小栈"抖"一下。Android/Web 做不到这一点。也是作品集里最容易讲出「我理解平台特性」的细节 | 中（调参久） | 否 |
| **6** | **Action Button 接入**（提供 `AppShortcut` 供用户指派；iOS 18+ 再加 Control） | B | 「长按侧键就叫醒小栈」—— 这是**用户能主动展示给别人看**的嵌入感。实现成本几乎为零（只是多写几条 `AppShortcut`） | 低 | 否 |
| **7** | **控制中心 Control**：`ControlWidget` + `ControlWidgetButton` / `ControlWidgetToggle` | B | 控制中心里出现「小栈静音 / 抬头」，等于小栈被当成**一台设备**而不是一个 App。这是「读法 B」里最系统的一步 | 中 | 否 |
| **8** | **按需权限 + Privacy Manifest** | A + 信任 | 权限弹窗的时机和文案，是用户判断「这 App 懂不懂 iOS」的第一现场。加上 `PrivacyInfo.xcprivacy` 声明「不收集」，把「私人数据永不入库」从口号变成**可被 App Store 验证的事实** | 低 | 否 |

**紧随其后（有余力再做）**：Spotlight 索引（`IndexedEntity`）→ 锁屏 Live Activity 交互（`LiveActivityIntent`）→ 通用链接 → iOS 26 玻璃渐进增强 → 通知与待办。

**明确不做（本期）**：Live Activity 远程推送、CloudKit 同步、Handoff、iOS 27 专属特性（§7.4）。

---

## 10. 一页速查

```
┌─ 读法 A 视觉层 ───────────────────────────────────────┐
│ 全系统控件：NavigationStack / List(.insetGrouped) /     │
│   NavigationLink / .searchable / .toolbar / TabView /   │
│   LabeledContent / Label / .swipeActions / .sheet /     │
│   .presentationDetents / Form / .toggleStyle(.switch) / │
│   .alert / .confirmationDialog / Settings Scene         │
│ 语义色：systemBackground / secondarySystemBackground /  │
│   tertiarySystemFill / label / secondaryLabel /          │
│   separator / .tint / .destructive                        │
│ 字体：.body/.headline/.title + .monospacedDigit（禁用硬编码字号）│
│ 图标：SF Symbols（禁用 emoji、禁自绘）                    │
│ iOS26：.glassEffect(_:in:) 只给「主要动作」，26 以下回退    │
│ ── 唯一自绘区：小栈的脸、待机动画、状态指示、App 图标 ──      │
└───────────────────────────────────────────────────────┘

┌─ 读法 B 功能层 ───────────────────────────────────────┐
│ 锁屏/灵动岛  ActivityKit + WidgetKit                    │
│ 桌面/锁屏    WidgetKit（Static/AppIntent Configuration）  │
│ 控制中心     WidgetKit ControlWidget（iOS18+）           │
│ Action Button  App Shortcuts（无独立 API）              │
│ Siri/快捷指令/Spotlight  AppIntents + AppShortcutsProvider│
│ 通知         UNUserNotificationCenter                   │
│ 触感         CoreHaptics（CHHapticEngine/CHHapticPattern）│
│ 设备连接     CoreBluetooth + Network（NWBrowser/NWConnection）│
│ 语音         Speech（SFSpeechRecognizer）                │
└───────────────────────────────────────────────────────┘

┌─ 读法 C 生态位 ───────────────────────────────────────┐
│ 首页 = 小栈的脸（不是功能面板）                          │
│ Tab = 2 个：小栈 / 陪伴        设置 = 独立 Settings Scene │
│ 深度 ≤ 2 层       每屏 1 个主要动作                     │
│ 能在系统表面表达的功能，不要在 App 里再表达一次            │
└───────────────────────────────────────────────────────┘
```

---

## 11. 出处清单

**方法说明**：Apple 开发者文档站是 JS 渲染，但每个文档页都提供 Markdown 版本：`https://developer.apple.com/documentation/<path>.md`。本轮所有 API 名与 iOS 版本号都从该 Markdown 版本的 **JSON frontmatter `availability` 字段**核对而来（本地缓存：`D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs\`，82+ 个 .md + 4 个框架索引 JSON）。本文档本身不含这些缓存文件。

### 11.1 Apple 官方文档（一手来源）

| 主题 | URL |
|---|---|
| ActivityKit 框架总览 | https://developer.apple.com/documentation/activitykit |
| Live Activity 数据模型与写法 | https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities |
| Live Activity 远程推送 | https://developer.apple.com/documentation/activitykit/starting-and-updating-live-activities-with-activitykit-push-notifications |
| 从 Live Activity 启动 App（深链） | https://developer.apple.com/documentation/activitykit/launching-your-app-from-a-live-activity |
| Activity 类 | https://developer.apple.com/documentation/activitykit/activity |
| ActivityAttributes | https://developer.apple.com/documentation/activitykit/activityattributes |
| ActivityContent | https://developer.apple.com/documentation/activitykit/activitycontent |
| ActivityAuthorizationInfo | https://developer.apple.com/documentation/activitykit/activityauthorizationinfo |
| ActivityUIDismissalPolicy | https://developer.apple.com/documentation/activitykit/activityuidismissalpolicy |
| WidgetKit 框架总览 | https://developer.apple.com/documentation/widgetkit |
| WidgetKit 更新日志 | https://developer.apple.com/documentation/updates/widgetkit |
| Controls（控制中心 / 锁屏 / Action Button） | https://developer.apple.com/documentation/widgetkit/controls-collection |
| 创建系统级动作控件 | https://developer.apple.com/documentation/widgetkit/creating-controls-to-perform-actions-across-the-system |
| 控件的样式与配置 | https://developer.apple.com/documentation/widgetkit/adding-refinements-and-configuration-to-controls |
| Widget 交互 | https://developer.apple.com/documentation/widgetkit/adding-interactivity-to-widgets-and-live-activities |
| Widget 数据更新动画 | https://developer.apple.com/documentation/widgetkit/animating-data-updates-in-widgets-and-live-activities |
| Widget 与 Live Activity 跳转场景 | https://developer.apple.com/documentation/widgetkit/linking-to-specific-app-scenes-from-your-widget-or-live-activity |
| Widget / 配件总览 | https://developer.apple.com/documentation/widgetkit/widgets-and-complications-collection |
| WidgetFamily | https://developer.apple.com/documentation/widgetkit/widgetfamily |
| StaticConfiguration | https://developer.apple.com/documentation/widgetkit/staticconfiguration |
| AppIntentConfiguration | https://developer.apple.com/documentation/widgetkit/appintentconfiguration |
| WidgetCenter | https://developer.apple.com/documentation/widgetkit/widgetcenter |
| App Intents 框架总览 | https://developer.apple.com/documentation/appintents |
| App Intents 更新日志 | https://developer.apple.com/documentation/updates/appintents |
| App Shortcuts | https://developer.apple.com/documentation/appintents/app-shortcuts |
| AppShortcutsProvider | https://developer.apple.com/documentation/appintents/appshortcutsprovider |
| AppIntent 协议 | https://developer.apple.com/documentation/appintents/appintent |
| 硬件交互（Action Button / 侧键） | https://developer.apple.com/documentation/appintents/hardware-interactions |
| Spotlight 集成 | https://developer.apple.com/documentation/appintents/spotlight |
| Widgets / Live Activities / Controls 与 App Intents | https://developer.apple.com/documentation/appintents/widgets-live-activities-and-controls |
| Apple Intelligence 与 Siri | https://developer.apple.com/documentation/appintents/apple-intelligence-and-siri-ai |
| 采纳 App Intents 支持系统体验（availability = iOS 27） | https://developer.apple.com/documentation/appintents/adopting-app-intents-to-support-system-experiences |
| Core Haptics 框架总览 | https://developer.apple.com/documentation/corehaptics |
| 触感准备 | https://developer.apple.com/documentation/corehaptics/preparing-your-app-to-play-haptics |
| 触感与 App 体验 | https://developer.apple.com/documentation/corehaptics/delivering-rich-app-experiences-with-haptics |
| CHHapticEngine | https://developer.apple.com/documentation/corehaptics/chhapticengine |
| CHHapticPattern | https://developer.apple.com/documentation/corehaptics/chhapticpattern |
| CHHapticParameterCurve | https://developer.apple.com/documentation/corehaptics/chhapticparametercurve |
| SwiftUI 更新日志（含 iOS 27 新 API） | https://developer.apple.com/documentation/updates/swiftui |
| UIKit 更新日志 | https://developer.apple.com/documentation/updates/uikit |
| Core Spotlight 更新日志（含 iOS 27 语义搜索） | https://developer.apple.com/documentation/updates/corespotlight |
| Liquid Glass：`glassEffect(_:in:)` | https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:) |
| Liquid Glass：`Glass` | https://developer.apple.com/documentation/swiftui/glass |
| Liquid Glass：`GlassEffectContainer` | https://developer.apple.com/documentation/swiftui/glasseffectcontainer |
| ImagePlayground 框架 | https://developer.apple.com/documentation/imageplayground |
| Core Spotlight | https://developer.apple.com/documentation/corespotlight |
| CSSearchableIndex | https://developer.apple.com/documentation/corespotlight/cssearchableindex |
| 隐私清单：数据使用描述 | https://developer.apple.com/documentation/bundleresources/describing-data-use-in-privacy-manifests |
| 隐私清单：必需理由 API | https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes |
| 权限：麦克风 | https://developer.apple.com/documentation/bundleresources/information-property-list/nsmicrophoneusagedescription |
| 权限：相机 | https://developer.apple.com/documentation/bundleresources/information-property-list/nscamerausagedescription |
| 权限：蓝牙 | https://developer.apple.com/documentation/bundleresources/information-property-list/nsbluetoothalwaysusagedescription |
| 权限：本地网络 | https://developer.apple.com/documentation/bundleresources/information-property-list/nslocalnetworkusagedescription |
| Speech 框架 | https://developer.apple.com/documentation/speech |
| SFSpeechRecognizer | https://developer.apple.com/documentation/speech/sfspeechrecognizer |
| PhotosPicker | https://developer.apple.com/documentation/photosui/photospicker |
| ShareLink | https://developer.apple.com/documentation/swiftui/sharelink |
| LabeledContent | https://developer.apple.com/documentation/swiftui/labeledcontent |
| NSUserActivity | https://developer.apple.com/documentation/foundation/nsuseractivity |
| UNUserNotificationCenter | https://developer.apple.com/documentation/usernotifications/unusernotificationcenter |
| BGTaskScheduler | https://developer.apple.com/documentation/backgroundtasks/bgtaskscheduler |
| CloudKit | https://developer.apple.com/documentation/cloudkit |
| Associated Domains（通用链接） | https://developer.apple.com/documentation/xcode/supporting-associated-domains |

### 11.2 Apple 官方示例（参考实现，非直接复用）

| 示例 | URL |
|---|---|
| Emoji Rangers：Live Activity + 交互式 Widget + 动画 | https://developer.apple.com/documentation/widgetkit/emoji-rangers-supporting-live-activities-interactivity-and-animations |

### 11.3 第三方开源项目（许可经 GitHub API 核对）

| 项目 | 许可 | Star 数（本轮查询时） |
|---|---|---|
| https://github.com/SFSafeSymbols/SFSafeSymbols | MIT | 1897 |
| https://github.com/realm/SwiftLint | MIT | 19771 |
| https://github.com/nicklockwood/SwiftFormat | MIT | 8941 |
| https://github.com/stephencelis/SQLite.swift | MIT | 10185 |
| https://github.com/airbnb/lottie-ios | Apache-2.0 | 26917 |
| https://github.com/rive-app/rive-ios | MIT | 848 |
| https://github.com/Quick/Nimble | Apache-2.0 | 4834 |
| https://github.com/apple/swift-log | Apache-2.0 | 4053 |
| https://github.com/esphome/esphome | NOASSERTION（LICENSE 未核对） | 11945 |

### 11.4 上游项目文档（同目录）

| 文档 | 路径 |
|---|---|
| 设备端设计契约 | `docs/research/02-设计契约与交互规范.md` |
| iOS 26 / Liquid Glass 视觉实测 | `docs/research/08-iOS26视觉规范.md` |
| Apple 极简方向 | `docs/research/01-apple-minimal-我们的iOS方向.md` |
| **Apple HIG 官方核实（排版/材质/颜色硬约束，冲突时以其为准）** | `docs/research/10-AppleHIG官方核实.md` |

---

## 12. 收尾：本报告与用户三句原话的对齐

| 用户原话 | 本报告的落点 |
|---|---|
| 「不管它适合女孩子还是男孩子，我要求它的界面就是很适合嵌入苹果系统」 | §3 全篇 —— 视觉层不是"好看"，是"用系统控件 = 继承系统行为"。**性别中立**恰恰要求不靠粉色/可爱字体做识别，而靠系统规范 + 小栈的脸（§3.3）做识别 |
| 「多去学一学优秀的，放在苹果上面，尤其是苹果十七」 | §2 全篇 + §7.1 —— iPhone 17 属 iOS 26 代；本文覆盖 iOS 26 的 `glassEffect` 与 iOS 27 的新布局能力，给出「最低 17 / 主力 18 / 26–27 渐进增强」的部署建议 |
| 「如何设计才好看，要分得清主次，简约，主要功能都齐全，不要总是想着去堆功能」 | §4.5 的十项检查表（每屏一个主要动作）+ §4.4（能在系统表面表达的不进 App）+ iOS 27 官方的 `ArrangementView`（primary / secondary）。**「主要功能都齐全」由系统表面承担，不是由 App 内的按钮数量承担** |
