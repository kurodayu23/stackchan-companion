# 30 · iOS 系统能力 API 核实清单（"真的嵌进苹果系统"的落地依据）

> 核实日期：2026-10-23
> 核实者：我本人（主会话）
> 权威来源：**Apple 官方框架文档符号页实读原文**（本机缓存 `D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs\`，162 份 `.md`）
> 补充来源：`Updates-ActivityKit.md` / `Updates-AppIntents.md` / `Updates-WidgetKit.md`（Apple 官方"更新"页）
> 触发原因：`09` 号文档给了"要做哪 8 项系统能力"的**概念清单**，但**没有核实真实 API 名与版本** —— 而 API 名错了，SwiftUI 一行都写不出来。

---

## 一、一句话结论

> **「嵌入苹果系统」在 API 层面完全可行，且 Apple 在 2026-06 刚把 App Intents 大幅加强。**
> 我们的 4 个落点全部有官方 API 支撑：
> **App Shortcuts（语音短语）· Live Activity / 灵动岛（状态余光）· 控制中心 / 锁屏控件（ControlWidget）· 触感（Core Haptics）**。
> ⚠️ **同时挖到一条对「隐私三层分离」有直接影响的官方注记** —— 见 §六。

---

## 二、⭐ App Shortcuts（语音短语）—— 让用户不打开 App 就能叫小栈

**已核实的 API**（`AppIntents-app-shortcuts.md` 原文）：

| 类型 | 作用 |
|---|---|
| `protocol AppShortcutsProvider` | 一个类型里集中提供 App 的预置快捷指令 |
| `struct AppShortcut` | 某个 app intent 的预置快捷指令 |
| `struct AppShortcutPhrase` | **触发该快捷指令的口述短语** |
| `enum AppShortcutPhraseToken` | 短语里可用的动态值（参数占位） |
| `struct NegativeAppShortcutPhrase` | 否定式短语（"别…"） |
| `SiriTipView` / `SiriTipUIView` | 在 App 内以 tip view 形式提示可用快捷指令 |
| `ShortcutsLink` / `ShortcutsUIButton` | 跳到「快捷指令」App 的对应页面 |

**关键机制（原文）**：
> *"You create App Shortcuts **programmatically in your code**, and the **compiler generates** the information the rest of the system needs to use it. This approach means that the shortcuts you create are **available as soon as someone installs your app**, and you don't have to register them yourself."*

→ **写在代码里，不用在快捷指令 App 里手工建**。装完即生效。

**我们的用法（建议 2–3 条，不多）**：
| 短语 | 触发 | 目的 |
|---|---|---|
| 「跟小栈说话」 | 打开对话并置为输入态 | 语音入口 |
| 「小栈，过来」 | 唤起设备端动作（转头/看向我） | 物理存在感 |
| 「小栈别吵了」 | 静音 / 停止主动说话 | ⭐ **这个最关键** —— 陪伴产品必须有"立刻闭嘴"的出口 |

> ⚠️ **不做**：不把快捷指令做成"功能清单"。3 条封顶，每条对应用户真实会说出口的话。

---

## 三、⭐ Live Activity / 灵动岛（状态余光的唯一载体）

**已核实的 API**（`ActivityKit-creating-custom-views-for-live-activities.md` 原文）：

```swift
ActivityConfiguration(for: AdventureAttributes.self) { context in
    // Lock Screen / 无灵动岛设备的横幅
} dynamicIsland: { context in
    DynamicIsland {
        // expanded   —— 展开态
    } compactLeading: {
        // compactLeading —— 灵动岛左侧
    } compactTrailing: {
        // compactTrailing —— 灵动岛右侧
    } minimal: {
        // minimal —— 最简态
    }
}
..supplementalActivityFamilies([.small, .medium])
```

- `supplementalActivityFamilies(_:)`（`WidgetKit.ActivityFamily`）—— 声明我们在 **Apple Watch（`.small`）** 与 **iPhone 锁屏/StandBy（`.medium`）** 提供自定义布局。
- `@Environment(\.activityFamily)` —— 运行时按 family 切换布局。

**Live Activity 会出现在哪些地方（官方原文）**：
| 场合 | 呈现形态 |
|---|---|
| iPhone 锁屏 / 主屏横幅 | Lock Screen 呈现 |
| **StandBy**（待机显示） | 系统把锁屏呈现**展开铺满整屏** |
| **Apple Watch** | 自动出现在 Smart Stack，并以 **compact** 形态作为提醒 |
| **CarPlay** | 自动出现在主屏，**compact** 形态 |
| **Mac（菜单栏）** | ActivityKit 2025-06 起自动出现 |

**ActivityKit 增量（2025-06）**：
- Live Activities 自动出现在 **Mac 菜单栏**与 **CarPlay**。
- `Activity.request(attributes:content:pushType:style:alertConfiguration:start:)` —— **可定时启动** Live Activity。

**⭐ 我们的取舍（已与宪法一致）**：
- 我们宪法已定：**「状态余光由灵动岛/Live Activity 承载，App 内不重复表达」**。
  → Live Activity 是**唯一**的状态余光载体；App 内**不再重复**做"正在听/正在想"的文字标签。
- **紧凑优先**：灵动岛 compact 态只放**一个**信息（比如小栈的当前情绪色 + 一个极简状态），**不放文字**。
  → 符合「P7 AI 内部状态不用文字，交给小栈的脸」。
- **不做**：CarPlay / watchOS 专项布局（成本高、场景边缘），但**用 `supplementalActivityFamilies` 留好接口**，
  这样将来上 watchOS 不用重写。`.small` 加上成本很低，**顺手做掉**。
- **不做**：`style: .alert` 的强提醒（会打断）—— 陪伴产品的主动表达应该"轻"，不是"叫醒你"。

---

## 四、⭐ 控制中心 / 锁屏控件（`ControlWidget`）

**已核实的 API**：

| API | 作用 | 版本 |
|---|---|---|
| `ControlConfigurationIntent` | 定义一个可放进控制中心的控件的配置 intent | 2024-06 |
| `WidgetKit.ControlWidgetButton` | 执行一个动作的按钮控件 | 2024-06 |
| `WidgetKit.ControlWidgetToggle` | 切换某个状态的开关控件 | 2024-06 |
| `WidgetKit.WidgetAccentedRenderingMode` | Widget 的 Liquid Glass 强调渲染 | 2025-06 |

**我们的用法（建议只做 1 个）**：
- 一个 `ControlWidgetToggle` = **「小栈静音」**。
  → 理由：控制中心的价值是"高频一键操作"，而我们唯一的高频诉求就是"让它安静"。
- **不做**控制中心的复合面板（参数选择器）—— 那会把控制中心变成我们的功能面板，直接违反「禁功能堆叠」。

---

## 五、⭐ 触感（Core Haptics）

**已核实的 API**（`CoreHaptics-*.md`）：

| API | 作用 |
|---|---|
| `CHHapticEngine` | 触感引擎 |
| `CHHapticPattern` | 触感模式 |
| `CHHapticEvent` | 事件（瞬时/连续） |
| `CHHapticAdvancedPatternPlayer` | 播放进阶模式（参数曲线） |
| `CHHapticDynamicParameter` | 动态参数 |
| `CHHapticParameterCurve` | 参数曲线 |

**我们的用法**：
- **不做**"每次回应都震一下"（廉价感）。
- 只在**三个有意义的时刻**给触感：
  1. **小栈注意到你**（极轻，1 次瞬时）—— "它看见我了"
  2. **你说的话它听清了**（短促确认）—— 闭环
  3. **它要开始说重要的话**（稍重）—— 提示"要出声了"
- 触感承担「反馈多通道」里的**触觉那一路**（宪法 16′ 条：AI 内部状态不用文字，但反馈应多通道）。

> ⚠️ **降级方案（无 Mac 时）**：用 SwiftUI 的 `.sensoryFeedback`（iOS 17+）也能做简单瞬时触感，
> 不依赖 Core Haptics。**复杂模式（参数曲线）才需要 Core Haptics。**

---

## 六、⚠️⭐⭐ 官方注记里的一条隐私发现（直接影响我们的隐私三层分离）

`AppIntents-app-shortcuts.md` 原文：

> *"**Note: Apple may extract anonymized App Shortcuts data such as localized phrases, display representation values, and the title and description of related intents. Machine learning models use this data when training** to help improve the App Shortcuts experience."*

**含义**：
- 我们在 App Shortcuts 里写的**口述短语**、intent 的 title/description，
  **可能被 Apple 匿名提取用于模型训练**。
- 我们的产品有一条硬红线：**个人定制数据永不入库**（人格三层分离：通用引擎 / 通用人格包 / 个人定制数据）。

**⇒ 由此得出的 3 条纪律**（建议进 `PRODUCT.md` §隐私 与 `19` 号 Floor）：

| # | 纪律 | 理由 |
|---|---|---|
| P-1 | **官方 App Shortcuts 只提供通用短语**（"跟小栈说话"这种），**绝不含任何用户自定义内容** | 用户自己设的别名如果进 Shortcuts 体系，就可能被匿名提取用于训练 |
| P-2 | **用户自定义的人格 / 记忆 / 私密话题，一律只留在 App 本地与自建后端**，**不通过 App Intents 的 title/description 暴露** | 同上 |
| P-3 | **在 App 的隐私说明里写清这条边界**（哪些走系统、哪些绝不走） | 这正是我们"隐私是卖点"该有的具体形态，而不是一句口号 |

> **这条把「隐私三层分离」从架构描述变成了可验证的产品行为** —— 值得单独立项写进 `PRODUCT.md`。

---

## 七、App Intents 2026-06 新增（我们的 App Entity / 长任务 / 撤销能力）

`Updates-AppIntents.md` 原文（June 2026）：

| API | 作用 | 对我们 |
|---|---|---|
| `LongRunningIntent` + `performBackgroundTask(options:operation:)` + `LongRunningTaskOptions` | ⭐ 把 intent 的后台运行时延长，可上报进度 | "小栈正在想…" 这类后台任务 |
| `CancellableIntent` + `IntentCancellationReason` | 优雅处理取消（区分主动取消与超时） | 用户打断小栈说话 |
| `UndoableIntent` | ⭐ 让动作可撤销 | "撤销刚才那一下" |
| `supportedModes` + `IntentModes` + `IntentSystemContext.currentMode` | 指定 intent 跑前台/后台/两者 | 语音交互需要前台 |
| `allowedExecutionTargets` + `IntentExecutionTargets` | 声明哪个 target 执行（主 App / App Intents 扩展 / widget 扩展） | 工程细节 |
| `EntityCollection` | ⭐ 高效引用大量 entity（只存 id，按需解析） | 设备列表 / 表情库 |
| `IndexedEntityQuery` | 从 Spotlight 索引按 id 取 entity | 让小栈能被 Spotlight 搜到 |
| `SyncableEntity` | 标识跨设备稳定 | 多设备同步（我们要"个人定制数据不出设备"，所以**不用**跨设备同步 = 一致） |
| `OwnershipProvidingEntity` + `EntityOwnership` | 共享实体上做破坏性操作前要求确认 | 与我们"设备绑定"一致 |
| `RelevantEntities` | 让系统推荐相关媒体实体 | 我们**不做** |
| `IntentValueRepresentation` | entity 到系统 intent 值类型的桥接 | 工程细节 |
| `AppIntentError.init(description:)` | 本地化错误描述 | ⭐ 配合宪法 16′（错误必须有文字且说清怎么修） |
| `AppUnionValue` + `AppUnionValueCasesProviding` + `@UnionValue` | 联合类型参数 | 我们的参数简单，**不做** |

**2024-06 的系统集成能力（仍然重要）**：
- `ControlConfigurationIntent` + WidgetKit → 锁屏 / 控制中心控件（§四）
- `CameraCaptureIntent` / `AudioRecordingIntent` → ❌ 不做（我们不拍照不录音）
- `app-schema-domains` → 接入 Siri / Apple Intelligence

---

## 八、WidgetKit（**我们降级为 P2**）

**已核实的 API**：`WidgetAccentedRenderingMode`（Liquid Glass）、`WidgetPushHandler`（推送触发 timeline 重载）、`widgetAccentable(_:)`、`ActivityFamily.small/.medium`、`RelevanceConfiguration`、`AppIntentConfiguration`。

**降级理由**：
- 我们的产品主张是「**屏幕上唯一会动、唯一被注视的东西是小栈的脸；其他一切都是背景**」。
- 一个常驻在主屏上的 Widget 恰恰是**另一个"会动的东西"**，直接与主张冲突。
- → **Widget 只在两个场景成立**：① **Live Activity 已有**（灵动岛就是系统级 Widget）；② 用户主动添加时表现克制。
- → **不做**独立的小组件。

---

## 九、⭐ 我们真正要做的系统能力（收敛成 4 项 + 2 降级）

| # | 能力 | API | 优先级 | 对应宪法 |
|---|---|---|---|---|
| 1 | **App Shortcuts（3 条）** | `AppShortcutsProvider` / `AppShortcut` / `AppShortcutPhrase` | P0 | P7（无文字状态） |
| 2 | **Live Activity / 灵动岛（状态余光）** | `ActivityConfiguration` / `DynamicIsland` / `supplementalActivityFamilies` | P0 | 「状态余光只在这里」 |
| 3 | **控制中心开关（静音）** | `ControlConfigurationIntent` + `ControlWidgetToggle` | P1 | P6（陪伴不是考核） |
| 4 | **触感（3 个时刻）** | `CHHapticEngine`（或 `.sensoryFeedback` 降级） | P1 | 16′（反馈多通道） |
| — | 独立 Widget | `WidgetKit` | **P2 / 可不做** | 与主张冲突 |
| — | CarPlay / watchOS 专项 | `ActivityFamily.small` 等 | **降级**（接口留着，不投入） | — |

---

## 十、未核实范围（如实登记）

1. **各 API 的精确最低系统版本** —— 本轮读到的是 Updates 页的**时间点**（如 "June 2026"），
   **未逐个符号页核实 `availability` 字段**。部分符号的最低版本需查对应 `.md` 的 frontmatter。
2. **`ActivityAttributes` 的字段设计** —— 未核实 iOS 26 对自定义属性的限制。
3. **灵动岛各态的像素尺寸约束** —— 未核实（HIG 图示有参考，但未取具体数值）。
4. **`SiriTipView` 的视觉表现** —— 未核实（HIG iconography 页可能有，未查）。
5. **App Intents 扩展的打包与签名要求** —— 未核实（工程细节，做的时候再查）。
6. **CarPlay / watchOS 的完整要求** —— 未展开（本就已降级）。
7. **`.sensoryFeedback` 的具体 modifier 与可用样式** —— 未逐字核实（只作为降级方案提及）。

---

## 十一、附：来源索引

| 文档 | 路径（本机缓存） |
|---|---|
| App Shortcuts | `ios-docs\AppIntents-app-shortcuts.md` |
| App Intents 增量 | `ios-docs\Updates-AppIntents.md` |
| ActivityKit 增量 | `ios-docs\Updates-ActivityKit.md` |
| WidgetKit 增量 | `ios-docs\Updates-WidgetKit.md` |
| Live Activity 自定义视图 | `ios-docs\ActivityKit-creating-custom-views-for-live-activities.md` |
| Core Haptics | `ios-docs\CoreHaptics-*.md`（4 份） |
| 控制中心控件 | `ios-docs\controlwidgetbutton.md` |

*Apple 官方文档 · Copyright © 2026 Apple Inc.*
