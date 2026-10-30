# 证据档案 03 · CoreHaptics / UIFeedbackGenerator ＋ Speech / AVFoundation

> 取证时间：2026-10-25　资料源：`D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs\`、`hig-md\`、`ios-fetch\`　只读未联网
>
> 取证方式：全部结论来自本机缓存文件的逐行阅读（`read` 带 offset/limit）与 `Select-String`/`Get-ChildItem` 实跑输出。行号均为实际读到的行号。
> 等级：**T1** = 官方明文写出的数值/事实；**T2** = 官方只给规则不给数值。
>
> **重要更正（与任务书预设不符）**：任务书假设「缓存里可能根本没有 UIFeedbackGenerator / SpeechAnalyzer」。实测**都存在**，但**不在 `ios-docs\` 而在 `ios-fetch\`**。另有 4 项确实未覆盖（`AVAudioSession` 独立页、`NSSpeechRecognitionUsageDescription`、`requiresOnDeviceRecognition`、`UISensoryFeedbackGenerator`）。详见 D1/D2。

---

## 第一部分 触感

## A1. 事实表

| ID | 事实 | 出处（文件:行号） | 等级 | 官方英文原句(≤1句) |
|---|---|---|---|---|
| H01 | Core Haptics 的定位是「超出系统默认模式」的自定义触感组合 | `ios-docs\corehaptics.md:28` | T1 | "With Core Haptics, you extend this functionality by composing and combining haptics beyond the default patterns." |
| H02 | 没有 engine 就无法播放 pattern（但可以先定义 pattern） | `ios-docs\hapticengine.md:37` | T1 | "Even though you can define a haptic pattern without an engine, you need the engine to play that pattern." |
| H03 | 即使 app 通过 engine 发出请求，系统服务仍可覆盖该请求 | `ios-docs\hapticengine.md:41` | T1 | "Even though your app makes a request through the haptic engine, the operating system could still override the request with system services, like haptics from system notifications." |
| H04 | AHAP 中参数值统一归一化到 0–1 区间 | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:65` | T1 | "These values are normalized to a range between 0 and 1 to represent the minimum and maximum the system supports." |
| H05 | `HapticIntensity` 取值 0–1 | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:71` | T1 | "The strength of the haptic event. The value is between 0 and 1." |
| H06 | `HapticSharpness` 取值 0–1 | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:72` | T1 | "The degree to which the haptic event feels tingly, or persistent. The value is between 0 and 1." |
| H07 | `AttackTime` / `DecayTime` / `ReleaseTime` 均取值 0–1 | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:73`（另见 :74、:75） | T1 | "The amount of time it takes for the event’s intensity envelope to reach its full strength. The value is between 0 and 1." |
| H08 | `AudioPan` / `AudioPitch` 取值 −1–1（有符号，与触感参数不同） | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:78`（另见 :79） | T1 | "The distribution of the audio signal. This value is between -1 and 1." |
| H09 | 0 与 1 是归一化映射，**不是**绝对秒数/零值 | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:83` | T1 | "It’s a normalized value that maps to the minimum value the system supports." |
| H10 | 越界值会被钳制（clamp）到最小或最大值 | `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:22` | T1 | "When Core Haptics loads an AHAP file, it sets missing entries to their default value and clamps out-of-range values to their minimum or maximum values, whichever is closer." |
| H11 | 明确不支持触感的设备：iPad、iPod touch、Apple Vision Pro | `ios-docs\CoreHaptics-preparing-your-app-to-play-haptics.md:25` | T1 | "Some devices don’t support haptic feedback, including iPad, iPod touch, and Apple Vision Pro." |
| H12 | 设备能力用 `capabilitiesForHardware.supportsHaptics` 查询 | `ios-docs\CoreHaptics-preparing-your-app-to-play-haptics.md:33` | T1 | "self.supportsHaptics = CHHapticEngine.capabilitiesForHardware.supportsHaptics;" |
| H13 | engine 不是单例；Core Haptics 线程安全 | `ios-docs\CoreHaptics-preparing-your-app-to-play-haptics.md:56` | T1 | "The haptic engine isn’t a singleton; you can create multiple instances in different parts of your app or game." |
| H14 | 引擎被动停止有 4 种外部原因，需各自恢复 | `ios-docs\CoreHaptics-preparing-your-app-to-play-haptics.md:99`（:104、:109、:114） | T1 | "CHHapticEngineStoppedReasonAudioSessionInterrupt:" |
| H15 | 主动 `stop` **不会**触发 stoppedHandler，只走 stop 的 completion | `ios-docs\CoreHaptics-preparing-your-app-to-play-haptics.md:126` | T1 | "The stopped handler isn’t called if you manually stop the engine through an explicit stop(completionHandler:) call." |
| H16 | `playsHapticsOnly` 让引擎忽略音频事件 | `ios-docs\hapticengine.md:117`（描述在 :119） | T1 | "A Boolean value that indicates whether the engine ignores audio events." |
| H17 | `notifyWhenPlayersFinished` 在所有 player 播完后回调 | `ios-docs\hapticengine.md:155` | T1 | "Notifies you when all haptic pattern players have finished playing their haptic patterns." |
| H18 | 空闲自动关机开关 `isAutoShutdownEnabled` | `ios-docs\hapticengine.md:221` | T1 | "A Boolean value that indicates whether the haptic engine starts and stops automatically on request from one of its pattern players, or when idle." |
| H19 | 播放前后「夹住」start/stop 是省电推荐做法 | `ios-docs\CoreHaptics-playing-a-single-tap-haptic-pattern.md:82` | T2 | "Unless you’re playing several haptic patterns in succession, bookend haptic playback with starting and stopping the engine." |
| H20 | player 是廉价轻量对象，可随建随弃 | `ios-docs\CoreHaptics-playing-a-single-tap-haptic-pattern.md:62` | T1 | "Haptic players are inexpensive, lightweight objects, so create and discard them freely." |
| H21 | 触感要与视觉/听觉一致，且强度/锐度应与动画对齐 | `hig-md\playing-haptics.md:33` | T2 | "For example, you generally want to match the intensity and sharpness of a haptic with the intensity and sharpness of the animation it accompanies." |
| H22 | 不要滥用触感 | `hig-md\playing-haptics.md:35` | T2 | "Sometimes a haptic can feel just right when it happens occasionally, but become tiresome when it plays frequently." |
| H23 | 多数 app 应优先用短触感配合离散事件 | `hig-md\playing-haptics.md:37` | T2 | "In most apps, prefer playing short haptics that complement discrete events." |
| H24 | 触感必须可关闭 | `hig-md\playing-haptics.md:39` | T2 | "Make haptics optional." |
| H25 | 触感振动可能干扰相机/陀螺仪/麦克风等其他体验 | `hig-md\playing-haptics.md:41` | T2 | "Ensure that haptic vibrations don’t disrupt experiences involving device features like the camera, gyroscope, or microphone." |
| H26 | 系统触感模式须按其文档语义使用，不可挪用含义 | `hig-md\playing-haptics.md:29` | T2 | "If the documented use case for a pattern doesn’t make sense in your app or game, avoid using the pattern to mean something else." |
| H27 | 触感要全 app 一致，并建立因果关联 | `hig-md\playing-haptics.md:31` | T2 | "It’s important to build a clear, causal relationship between each haptic and the action that causes it so people learn to associate certain haptic patterns with certain experiences." |
| H28 | iOS 上两条路径：系统组件自带触感；或 feedback generator 播 notification/impact/selection 三类 | `hig-md\playing-haptics.md:65` | T1 | "When it makes sense, use a feedback generator to play one of several predefined haptic patterns in the categories of notification, impact, and selection" |
| H29 | sharpness/intensity 只有定性语义，未给数值范围 | `hig-md\playing-haptics.md:54` | T2 | "As the term implies, intensity means the strength of the haptic." |
| H30 | HIG 触感页 Change log 最新为 2024-05-07，**无 iOS 26 条目** | `hig-md\playing-haptics.md:227`（表头 :225；分隔 :226；次新 :228） | T1 | "May 7, 2024  \|Added guidance for playing haptics on Apple Pencil Pro.\|" |
| H31 | `UIFeedbackGenerator` 是抽象父类，禁止自行子类化/实例化 | `ios-fetch\uifeedbackgenerator.md:34` | T1 | "Don’t subclass or create instances of this class yourself. Instead, instantiate one of the concrete feedback generator subclasses:" |
| H32 | 具体子类共 4 个（含任务书未列出的 `UICanvasFeedbackGenerator`） | `ios-fetch\uifeedbackgenerator.md:36`（:37 selection、:38 notification、:39 canvas） | T1 | "Use impact feedback to indicate when an impact occurs." |
| H33 | `UIImpactFeedbackGenerator.FeedbackStyle` 语义 = 碰撞物体的质量 | `ios-fetch\uiimpactfeedbackgenerator.md:93` | T1 | "The mass of the objects in the collision simulated by an impact feedback generator object." |
| H34 | 可用 `impactOccurred(intensity:at:)` 指定强度与位置 | `ios-fetch\uiimpactfeedbackgenerator.md:113` | T1 | "func impactOccurred(intensity: CGFloat, at: CGPoint)" |
| H35 | selection 生成器用 `selectionChanged(at:)` 报告 | `ios-fetch\uiselectionfeedbackgenerator.md:75` | T1 | "func selectionChanged(at: CGPoint)" |
| H36 | notification 生成器用 `notificationOccurred(_:at:)` 报告 | `ios-fetch\uinotificationfeedbackgenerator.md:46` | T1 | "func notificationOccurred(UINotificationFeedbackGenerator.FeedbackType, at: CGPoint)" |
| H37 | Core Haptics 官方样例要求 iPhone 8 或更新机型 | `ios-docs\CoreHaptics-delivering-rich-app-experiences-with-haptics.md:26` | T1 | "You must run the sample on iPhone 8 or later." |
| H38 | 动态参数与事件参数合成规则：乘/加，并钳制到事件参数区间 | `ios-docs\CoreHaptics-CHHapticDynamicParameter.md:39` | T2 | "For haptic intensity and audio volume, the final property value is equal to the original event parameter value multiplied by the dynamic parameter value." |
| H39 | Swift 侧 `CHHapticEvent` 页只提及 intensity 参数存在，**未写取值范围** | `ios-docs\CoreHaptics-CHHapticEvent.md:43` | T1 | "For example, you can specify the intensity of a haptic event by creating an event parameter with ID hapticIntensity." |
| H40 | SwiftUI `SensoryFeedback` 是独立 SwiftUI 类型，iOS 17 起，经 `View.sensoryFeedback` 使用 | `ios-fetch\sensoryfeedback.md:4`（用法 :38） | T1 | "This feedback can be passed to `View.sensoryFeedback` to play it." |

**A1 条数：40 条。**

---

## B1. 必答问题逐条回答

### 问题 1 — 轻交互该用哪种：UIFeedbackGenerator 还是 CoreHaptics？

**分界线（官方口径，均为规则不给数值）：**

1. **默认路径 = 系统组件 / feedback generator**。HIG 说 iOS 上可加触感的第一种方式是「用 toggle、slider、picker 这类自带 Apple 设计触感的标准控件」（`hig-md\playing-haptics.md:64`）；第二种是「在合适时用 feedback generator 播 notification / impact / selection 三类预定义模式」（`:65`，T1 事实：三类划分）。
   - 官方英文："When it makes sense, use a feedback generator to play one of several predefined haptic patterns in the categories of notification, impact, and selection"（`:65`）

2. **`UIFeedbackGenerator` 本身不能直接用**，必须实例化具体子类；官方列出 4 个：`UIImpactFeedbackGenerator`、`UISelectionFeedbackGenerator`、`UINotificationFeedbackGenerator`、`UICanvasFeedbackGenerator`（`ios-fetch\uifeedbackgenerator.md:34`–`:39`，T1）。
   - 官方英文："Don’t subclass or create instances of this class yourself. Instead, instantiate one of the concrete feedback generator subclasses:"（`:34`）

3. **CoreHaptics 的适用条件 = 需要超出默认模式**：HIG 明确「custom haptics」主要用于游戏、非游戏 app 较少用（`hig-md\playing-haptics.md:45`，T2）；框架页也说 Core Haptics 是「composing and combining haptics beyond the default patterns」（`ios-docs\corehaptics.md:28`，T1）。
   - 官方英文："With Core Haptics, you extend this functionality by composing and combining haptics beyond the default patterns."（`corehaptics.md:28`）

4. **交互反馈型触感（如实时刻度）才需要常驻 player**；否则可随建随弃。官方：「Unless your app requires real-time, latency-free haptic feedback in response to user interaction — like precise ticks on a dial — you can create your player right before playing the haptic.」（`ios-docs\CoreHaptics-playing-a-single-tap-haptic-pattern.md:62`，T2）

5. **需要播放中动态改变触感 / 与自定义音轨同步 → 必须用 advanced player**：「Use the advanced pattern player … when your haptic pattern needs to change during playback, or when you’d like to sync your haptic with a custom audio track.」（`ios-docs\Y-CoreHaptics-CHHapticPatternPlayer.md:39`，T2）

**结论（转述）**：轻交互、语义属于「成功/失败/警告、碰撞、选择变化」的，用 UIKit 生成器；需要自定义波形、连续振动、实时改 intensity/sharpness、或与音频精确同步的，才上 CoreHaptics。

**关于 `UIFeedbackGenerator` 单独的 developer doc 页 —— 实测存在，不是「缓存未覆盖」。** 见 D1 第 1 条的真实 `Test-Path` 输出：`ios-docs\UIFeedbackGenerator.md` = False，但 `ios-fetch\uifeedbackgenerator.md` = True。任务书四个 generator 页中 `UISensoryFeedbackGenerator` **确实未覆盖**（见 D1 第 2 条）。

### 问题 2 — 触感设计的官方建议（HIG `playing-haptics.md` 逐条行号）

| # | 规则（中文转述） | 行号 | 等级 |
|---|---|---|---|
| 1 | 按文档语义使用系统触感模式；语义不合就别挪用，改用通用或自建模式 | `:29` | T2 |
| 2 | 全 app 一致，建立「触感↔动作」因果关系；不要同一模式既表失败又表成功 | `:31` | T2 |
| 3 | 触感应**补充**视觉/听觉，三者和谐；强度/锐度要对齐动画 | `:33` | T2 |
| 4 | 不要滥用；偶尔恰到好处，频繁则令人厌烦 | `:35` | T2 |
| 5 | 多数 app 用**短**触感配合离散事件；长触感会稀释含义、分心（Apple Pencil Pro 上更糟） | `:37` | T2 |
| 6 | 触感必须可关闭/静音，关掉后 app 仍可用 | `:39` | T2 |
| 7 | 触感有物理力，注意别干扰相机、陀螺仪、麦克风 | `:41` | T2 |
| 8 | notification 类语义：Success / Warning / Error | `:69`、`:75`、`:81`、`:87` | T1 |
| 9 | impact 类语义：Light / Medium / Heavy / Rigid / Soft（共 5 种） | `:97`、`:103`、`:109`、`:115`、`:121` | T1 |
| 10 | selection 类语义：UI 元素取值变化时反馈 | `:125`、`:131` | T1 |
| 11 | watchOS 上「Click」触感不可滥用，重叠会混淆 | `:203` | T2 |
| 12 | 触感要可访问：与颜色/文字/声音并用（`feedback.md`） | `hig-md\feedback.md:31` | T2 |

补充：官方**没有**在 HIG 里写「不要用触感表达层级」这条你预设的规则——`:29` 说的是不要挪用系统模式的语义。**「不要用触感表达层级」= 缓存未覆盖该表述**，不作断言。

### 问题 3 — iOS 26 有没有新触感能力？

**结论：缓存内未见 iOS 26 新增触感 API。**

查证范围与证据：
- `hig-md\playing-haptics.md` Change log 仅两条：`May 7, 2024`（`:227`）与 `June 21, 2023`（`:228`），**无 2026 / iOS 26 条目**。T1。
- `ios-docs\corehaptics.md` 的 availability 数组为**空**（`:3`–`:5` 之间为空行），未标注任何版本。T1。
- 全 `ios-docs\*.md` 里 `iOS: 26.0.0` 只出现在 `SwiftUI-Glass*.md`、`controlwidgetbutton.md`、`WidgetKit*`、`AppIntents-ForegroundContinuableIntent.md` 等**与触感无关**的文件；CoreHaptics 各页版本固定为 `iOS: 13.0.0`（如 `ios-docs\CoreHaptics-CHHapticEvent.md:4`、`hapticengine.md:4`、`chhapticpattern.md:4`、`CoreHaptics-CHHapticDynamicParameter.md:4`、`CoreHaptics-CHHapticAdvancedPatternPlayer.md:4`、`chhapticparametercurve.md:4`、`Y-CoreHaptics-CHHapticPatternPlayer.md:4`）。T1。
- UIKit 生成器各页版本为 `iOS: 10.0.0`（`ios-fetch\uifeedbackgenerator.md:4`、`uiimpactfeedbackgenerator.md:4`、`uinotificationfeedbackgenerator.md:4`、`uiselectionfeedbackgenerator.md:4`）。T1。
- 全目录 `iOS 26` 字面命中仅 1 处且无关：`ios-docs\X-CoreBluetooth.md:34`。

**SwiftUI `sensoryFeedback` 与 UIKit/CoreHaptics 的关系（只记录，不展开）**：`SensoryFeedback` 是 **SwiftUI** 的结构体，`iOS: 17.0.0 -`（`ios-fetch\sensoryfeedback.md:4`），语义枚举与 HIG 的 notification/impact/selection 高度对应（`:82` success、`:86` warning、`:90` error、`:96` impact、`:72` selection），且**不是** `UIFeedbackGenerator` 的子类、也不是 CoreHaptics 类型；它通过 `View.sensoryFeedback` 播（`:38`），底层实现入口未在缓存中给出。→ 属于另一主题，此处不展开。

### 问题 4 — 触感有没有官方数值？

**有的（T1）：**
- 归一化总则 0–1：`Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:65`
- `HapticIntensity` 0–1：`:71`
- `HapticSharpness` 0–1：`:72`
- `AttackTime` 0–1：`:73`
- `DecayTime` 0–1：`:74`
- `ReleaseTime` 0–1：`:75`
- `Sustained` 取 1 或 0：`:76`
- `AudioBrightness` 0–1：`:77`
- `AudioPan` −1–1：`:78`
- `AudioPitch` −1–1：`:79`
- `AudioVolume` 0–1：`:80`
- `HapticIntensityControl` 0–1（乘性）：`:89`
- `HapticSharpnessControl` −1–1（加性，**仅作用于 continuous**）：`:90`
- 其余 Control 参数 −1–1：`:91`–`:100`
- 支持机型：样例要求 iPhone 8 或更新（`CoreHaptics-delivering-rich-app-experiences-with-haptics.md:26`）

**注意口径差异**：0–1 的数值范围是**在 AHAP（文件格式）文档里**给出的；Swift `CHHapticEvent` 页只说「可用 `hapticIntensity` 参数指定强度」，**未写取值范围**（`CoreHaptics-CHHapticEvent.md:43`）。引用时不要声称「CHHapticEvent 页写了 0.0–1.0」。

**引擎启动/停止策略（T2，无数值）**：三步式 —— 建 engine 并强引用（`hapticengine.md:47`）、`start()` / `start(completionHandler:)`（`:48`）、用完 `stop(completionHandler:)`（`:49`）；播放夹住 start/stop（`CoreHaptics-playing-a-single-tap-haptic-pattern.md:82`）；注意可能自动关机（同处末句 "Be aware that your engine may stop on its own in auto-shutdown mode."）。

**`notifyWhenPlayersFinished`**：`:155`（T1 事实）。**`playsHapticsOnly`**：`:117`+`:119`（T1 事实）。

**最短间隔 / 最长时长 / 触感频率（Hz）等 → 官方未给数值。**

---

## C1. 官方未给数值清单

| 项目 | 状态 | 依据 |
|---|---|---|
| 两次触感之间的最短间隔 | **官方未给数值** | 全部 CoreHaptics 页与 HIG 触感页均无此数字 |
| 单次触感的建议/最大时长 | **官方未给数值** | HIG 只说「prefer short haptics」（`playing-haptics.md:37`），无秒数 |
| Taptic Engine 振动频率（Hz） | **官方未给数值** | 全目录 `Hz` 仅 2 处命中（`hig-md\motion.md`、`X-CoreSpotlight-CSSearchableItemAttributeSet.md`），均与触感无关 |
| 120 / 120Hz 刷新率与触感关系 | **官方未给数值** | 全目录 `120` 命中 8 处（`accessibility.md`、`applying-liquid-glass2.md`、`live-activities.md`、`typography.md`、`widgets.md`），无一与触感相关 |
| Swift `CHHapticEvent` 页面上 intensity/sharpness 的合法区间 | **该页未给数值**（0–1 只在 AHAP 页给出） | `CoreHaptics-CHHapticEvent.md:43` vs `Y-...ahap-files.md:65/71/72` |
| `UIImpactFeedbackGenerator` 的 `intensity: CGFloat` 合法范围 | **官方未给数值** | `uiimpactfeedbackgenerator.md:105`/`:113` 仅有签名，无区间 |
| 支持触感的具体设备型号全表 | **官方未给型号枚举** | 只给类别：不支持 = iPad / iPod touch / Apple Vision Pro（`preparing...:25`）；样例 = iPhone 8+（`delivering-rich...:26`） |
| `isAutoShutdownEnabled` 的空闲超时秒数 | **官方未给数值** | `hapticengine.md:221`–`:223` 仅定性描述 |
| 参数默认值（AHAP 省略时的具体数） | **官方未给数值** | AHAP 页说「sets missing entries to their default value」（`:22`、`:62`）但不列具体默认数 |
| 触感并发上限 / 同时播放 pattern 数 | **官方未给数值** | 缓存无任何相关数字 |

---

## D1. 缓存未覆盖项（含真实命令输出）

**命令 1**（文件名枚举，真实输出）：
```
PS> Get-ChildItem -LiteralPath "D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs" -File |
      Where-Object { $_.Name -match 'Speech|SFSpeech|AVAudio|FeedbackGenerator|Haptic' } | Select Name,Length

chhapticparametercurve.md                                     3300
chhapticpattern.md                                            5409
CoreHaptics-CHHapticAdvancedPatternPlayer.md                  3741
CoreHaptics-CHHapticDynamicParameter.md                       3238
CoreHaptics-CHHapticEvent.md                                  5094
CoreHaptics-delivering-rich-app-experiences-with-haptics.md    971
CoreHaptics-playing-a-single-tap-haptic-pattern.md            5058
CoreHaptics-preparing-your-app-to-play-haptics.md             7942
corehaptics.md                                                5975
hapticengine.md                                              10155
JSON-corehaptics.json                                        30142
Speech-SFSpeechAudioBufferRecognitionRequest.md               3493
Speech-SFSpeechRecognizer.md                                  8603
Speech.md                                                     5680
Y-CoreHaptics-CHHapticEngine.md                              10155
Y-CoreHaptics-CHHapticPatternPlayer.md                        3251
Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md  11037
Y-Speech-SFSpeechAudioBufferRecognitionRequest.md             3493
Y-Speech-SFSpeechRecognizer.md                                8603
Z-Speech-SFSpeechRecognitionTask.md                           3160
```

**命令 2**（Test-Path，真实输出）：
```
D:\...\ios-fetch\speechanalyzer.md                                  Test-Path=True
D:\...\ios-fetch\speechtranscriber.md                               Test-Path=True
D:\...\ios-fetch\uifeedbackgenerator.md                             Test-Path=True
D:\...\ios-docs\UIFeedbackGenerator.md                              Test-Path=False
D:\...\ios-docs\AVAudioSession.md                                   Test-Path=False
D:\...\ios-docs\Speech-SFSpeechRecognitionRequest.md                Test-Path=False
D:\...\ios-docs\Speech-SFSpeechURLRecognitionRequest.md             Test-Path=False
D:\...\ios-docs\Speech-SFSpeechRecognizerAuthorizationStatus.md     Test-Path=False
```

**命令 3**（三目录全文检索，真实命中数）：
```
=== PATTERN: UISensoryFeedbackGenerator ===  (no hits in any of the 3 dirs)
=== PATTERN: AVAudioSession ===   avspeech2.md=1  hapticengine.md=1  playing-audio.md=4  Y-CoreHaptics-CHHapticEngine.md=1
=== PATTERN: setCategory ===      (no hits in any of the 3 dirs)
=== PATTERN: playAndRecord ===    (no hits in any of the 3 dirs)
=== PATTERN: measurement ===      appentity.md=1 sliders.md=1 SwiftUI-LabeledContent.md=1 toggles.md=1 X-AppIntents-AppEntity.md=1 X-CoreSpotlight-CSSearchableItemAttributeSet.md=1
=== PATTERN: HFP ===              (no hits in any of the 3 dirs)
=== PATTERN: routeChange ===      (no hits in any of the 3 dirs)
=== PATTERN: NSSpeechRecognitionUsageDescription === (no hits in any of the 3 dirs)
=== PATTERN: requiresOnDeviceRecognition ===        (no hits in any of the 3 dirs)
=== PATTERN: shouldReportPartialResults ===         (no hits in any of the 3 dirs)
=== PATTERN: denied / notDetermined ===             (no hits in any of the 3 dirs)
```

| # | 项 | 判定 | 说明 |
|---|---|---|---|
| 1 | `UIFeedbackGenerator` developer doc 页 | **已覆盖（但不在任务书指定目录）** | `ios-docs\UIFeedbackGenerator.md` 不存在；实际在 `ios-fetch\uifeedbackgenerator.md`（101 行，已全读）。**不是缓存未覆盖** |
| 2 | `UISensoryFeedbackGenerator` | **缓存未覆盖** | 三目录 **0 命中**。且 `uifeedbackgenerator.md:36`–`:39` 列出的 4 个具体子类中**没有**此类。不得凭记忆补写其 API |
| 3 | `UICanvasFeedbackGenerator` 独立页 | **缓存未覆盖** | 仅在 `uifeedbackgenerator.md:39`/`:69` 被引用，无独立页 |
| 4 | `CHHapticEvent.ParameterID` 枚举值清单 | **缓存未覆盖** | 仅 `CoreHaptics-CHHapticEvent.md:81` 引用 `struct ParameterID`，无 case 列表；参数 ID 字面量只在 AHAP 页以字符串形式给出 |
| 5 | `CHHapticEngine.StoppedReason` 枚举页 | **缓存未覆盖** | 仅 `hapticengine.md:187` 引用；4 个 case 名只能从 `preparing...:99/104/109/114` 的 Objective-C 代码读到 |
| 6 | `playing-collision-based-haptic-patterns` / `playing-a-custom-haptic-pattern-from-a-file` / `updating-continuous-and-transient-haptic-parameters-in-real-time` / `playing-haptics-on-game-controllers` | **缓存未覆盖** | 仅被 `corehaptics.md:68`/`:96`/`:72`/`:106` 引用，无页面正文 |
| 7 | `JSON-corehaptics.json` 的可用粒度 | **受限** | 该文件为**单行 JSON**（30130 字符，行数=1），行号引用只能到 `:1`。已交叉验证其 abstract 与 `corehaptics.md:24` 完全一致；但其中**不含** `AVAudio`、不含大写 `Intensity` 键，故不能作为参数数值来源 |

---

## E1. 对本项目 App 的落地含义

1. **默认走 UIKit 生成器，别默认上 Core Haptics。** 官方口径是「能在合适时用 feedback generator 播预定义模式」（`playing-haptics.md:65`），Core Haptics 是「超出默认模式」的扩展（`corehaptics.md:28`）。轻点确认、选择变化、成功/失败提示 → `UISelectionFeedbackGenerator` / `UINotificationFeedbackGenerator` / `UIImpactFeedbackGenerator`（注意：必须用具体子类，`uifeedbackgenerator.md:34`）。
2. **触感必须做成可关闭项**（`playing-haptics.md:39`），且在设置里关掉后不影响主流程。
3. **耳机/麦克风场景要防触感串扰**：HIG 明确触感振动可能干扰麦克风（`playing-haptics.md:41`）。本项目的语音识别与触感可能同时工作 → 录音期间不要播强连续触感。
4. **连续/长触感慎用**：官方说 app 里长触感会稀释含义并分心（`playing-haptics.md:37`）；若要做「马达持续抖动」这类效果，属于 Core Haptics 的 continuous 事件范畴（`corehaptics.md:30`、`CHHapticEvent.md:37`）。
5. **iOS 26 不要指望新触感 API**：缓存内无 iOS 26 触感新增（见 B1-Q3）。触感能力基线仍按 iOS 13（CoreHaptics）+ iOS 10（生成器）规划。
6. **参数标定要按归一化 0–1 写**，并且越界会被 clamp（`ahap-files.md:22`、`:65`）——不要写 0–100 的百分比。
7. **设备降级路径必须有**：iPad / iPod touch / Vision Pro 明确不支持触感（`preparing...:25`），要像官方建议的那样回退到更强音频或视觉反馈（同页 `:25` 后半句）。

---

## 第二部分 语音

## A2. 事实表

| ID | 事实 | 出处（文件:行号） | 等级 | 官方英文原句(≤1句) |
|---|---|---|---|---|
| S01 | Speech 框架职责：对实时或预录音频做识别，产出转写/备选/置信度 | `ios-docs\Speech.md:28` | T1 | "Perform speech recognition on live or prerecorded audio, and receive transcriptions, alternative interpretations, and confidence levels of the results." |
| S02 | 新架构分工：`SpeechTranscriber` 供服务、`AssetInventory` 管资产、`SpeechAnalyzer` 管分析会话、两个 provider 供音频 | `ios-docs\Speech.md:34` | T1 | "The `SpeechTranscriber` class and other module classes provide specific services." |
| S03 | `SpeechAnalyzer` 自 **iOS 26.0.0** 起可用 | `ios-fetch\speechanalyzer.md:4` | T1 | "iOS: 26.0.0 -" |
| S04 | `SpeechAnalyzer` 是 `final actor`（并发语义由 actor 保证） | `ios-fetch\speechanalyzer.md:32` | T1 | "final actor SpeechAnalyzer" |
| S05 | 一个 analyzer 同一时刻只能分析一路输入序列 | `ios-fetch\speechanalyzer.md:52` | T1 | "The analyzer can only analyze one input sequence at a time." |
| S06 | 结果与输入都走 `AsyncSequence`，取代 delegate 模式 | `ios-fetch\speechanalyzer.md:50` | T1 | "Similarly, you provide speech input to this API via an `AsyncSequence` you create and populate." |
| S07 | 同时分析数有「保守上限」，**但不给具体数字** | `ios-fetch\speechanalyzer.md:206` | T2 | "The system normally limits simultaneous analyses to a conservative number, considering hardware capabilities of different devices." |
| S08 | 超限抛 `insufficientResources`；可用 `ignoresResourceLimits` 解除 | `ios-fetch\speechanalyzer.md:206`（错误名）、`:210`（开关） | T1 | "If you exceed that number, the system throws an insufficientResources error." |
| S09 | 结束会话必须调 finish 类方法，否则结果流不终止、会等更多输入 | `ios-fetch\speechanalyzer.md:137` | T2 | "Otherwise, by default, the analyzer won’t terminate its result streams and will wait for additional audio input sequences or buffers." |
| S10 | 终止输入序列 ≠ 结束会话（有例外） | `ios-fetch\speechanalyzer.md:196` | T1 | "terminating the input sequence does *not* generally finish the analysis session" |
| S11 | 可用 `prepareToAnalyze(in:)` 预热以加快首个结果 | `ios-fetch\speechanalyzer.md:178` | T2 | "To proactively load system resources and “preheat” the analyzer, call prepareToAnalyze(in:) after setting its modules." |
| S12 | `SpeechTranscriber` 自 **iOS 26.0.0** 起可用 | `ios-fetch\speechtranscriber.md:4` | T1 | "iOS: 26.0.0 -" |
| S13 | 设备不支持该模型时，改用 `DictationTranscriber` | `ios-fetch\speechtranscriber.md:41` | T2 | "If it does not, consider disabling the feature or using DictationTranscriber instead." |
| S14 | `installedLocales` = 已装，`supportedLocales` = 含可下载 | `ios-fetch\speechtranscriber.md:81`（:85 对比） | T1 | "The locales that the transcriber can transcribe into, considering only locales that are installed on the device." |
| S15 | `SFSpeechRecognizer` 职责：查可用性 + 发起识别 | `ios-docs\Speech-SFSpeechRecognizer.md:28` | T1 | "An object you use to check for the availability of the speech recognition service, and to initiate the speech recognition process." |
| S16 | 创建一个 recognizer 只支持一种语言；创建成功≠服务可用；部分语言需联网 | `ios-docs\Speech-SFSpeechRecognizer.md:44` | T1 | "For some languages, the recognizer might require an Internet connection." |
| S17 | 初始化签名：`init?()` 与 `init?(locale: Locale)` | `ios-docs\Speech-SFSpeechRecognizer.md:70`（:74） | T1 | "convenience init?()" |
| S18 | 可用性属性：`isAvailable`；离线能力：`supportsOnDeviceRecognition` | `ios-docs\Speech-SFSpeechRecognizer.md:88`（:92） | T1 | "A Boolean value that indicates whether the speech recognizer can operate without network access." |
| S19 | **文件 vs 实时**的分流点：URL request 给文件，AudioBuffer request 给音频流 | `ios-docs\Speech-SFSpeechRecognizer.md:55` | T1 | "For existing audio files, create a SFSpeechURLRecognitionRequest object. For audio streams, create a SFSpeechAudioBufferRecognitionRequest object." |
| S20 | 五步起流顺序：授权→建 recognizer→查 isAvailable→备音频→建 request→recognitionTask | `ios-docs\Speech-SFSpeechRecognizer.md:48`（至 :53） | T1 | "Request authorization to use speech recognition." |
| S21 | **官方明文数值：识别任务超过 1 分钟会被停止** | `ios-docs\Speech-SFSpeechRecognizer.md:62` | T1 | "To minimize this burden, the framework stops speech recognition tasks that last longer than one minute." |
| S22 | 有每日/限流上限，但**不给具体数字** | `ios-docs\Speech-SFSpeechRecognizer.md:61` | T2 | "Individual devices may be limited in the number of recognitions that can be performed per day, and each app may be throttled globally based on the number of requests it makes per day." |
| S23 | 录音时要提示用户（视觉指示 + 起止音） | `ios-docs\Speech-SFSpeechRecognizer.md:63` | T2 | "Remind the user when your app is recording." |
| S24 | 不要对隐私/敏感内容做识别 | `ios-docs\Speech-SFSpeechRecognizer.md:64` | T2 | "Don’t send passwords, health or financial data, and other sensitive speech for recognition." |
| S25 | 授权签名：`class func requestAuthorization((SFSpeechRecognizerAuthorizationStatus) -> Void)` | `ios-docs\Speech-SFSpeechRecognizer.md:98` | T1 | "class func requestAuthorization((SFSpeechRecognizerAuthorizationStatus) -> Void)" |
| S26 | 查当前状态：`class func authorizationStatus()` | `ios-docs\Speech-SFSpeechRecognizer.md:102` | T1 | "class func authorizationStatus() -> SFSpeechRecognizerAuthorizationStatus" |
| S27 | 枚举 `SFSpeechRecognizerAuthorizationStatus` **仅被引用，case 清单未覆盖** | `ios-docs\Speech-SFSpeechRecognizer.md:106` | T1 | "The app’s authorization to perform speech recognition." |
| S28 | 起任务的两个真实签名（resultHandler / delegate） | `ios-docs\Speech-SFSpeechRecognizer.md:122`（:126） | T1 | "func recognitionTask(with: SFSpeechRecognitionRequest, resultHandler: (SFSpeechRecognitionResult?, (any Error)?) -> Void) -> SFSpeechRecognitionTask" |
| S29 | AudioBuffer request 用于**实时**麦克风音频 | `ios-docs\Speech-SFSpeechAudioBufferRecognitionRequest.md:36` | T1 | "Use an SFSpeechAudioBufferRecognitionRequest object to perform speech recognition on live audio, or on a set of existing audio buffers." |
| S30 | 必须显式 `endAudio()` 才会停止识别（不会自动停） | `ios-docs\Speech-SFSpeechAudioBufferRecognitionRequest.md:38` | T1 | "You must call endAudio() explicitly to stop the speech recognition process." |
| S31 | 喂数据签名：`append(AVAudioPCMBuffer)` / `appendAudioSampleBuffer(CMSampleBuffer)` / `endAudio()` | `ios-docs\Speech-SFSpeechAudioBufferRecognitionRequest.md:46`（:50、:54） | T1 | "func append(AVAudioPCMBuffer)" |
| S32 | `nativeAudioFormat` 给出「最佳识别音频格式」 | `ios-docs\Speech-SFSpeechAudioBufferRecognitionRequest.md:60` | T1 | "The preferred audio format for optimal speech recognition." |
| S33 | `finish()` = 停收新音频、把已收的跑完 | `ios-docs\Z-Speech-SFSpeechRecognitionTask.md:54`（语义在 :56） | T1 | "Stops accepting new audio and finishes processing on the audio input that has already been accepted." |
| S34 | `cancel()` = 取消当前任务 | `ios-docs\Z-Speech-SFSpeechRecognitionTask.md:44` | T1 | "Cancels the current speech recognition task." |
| S35 | `isFinishing` 表示输入是否已停 | `ios-docs\Z-Speech-SFSpeechRecognitionTask.md:58`（:60） | T1 | "A Boolean value that indicates whether audio input has stopped." |
| S36 | 任务对象不能自建，只能由 recognizer 返回 | `ios-docs\Z-Speech-SFSpeechRecognitionTask.md:38` | T1 | "You don’t create speech recognition task objects directly." |
| S37 | 麦克风权限键 `NSMicrophoneUsageDescription` 的官方定义 | `ios-docs\Y-Bundleresources-Information-Property-List-NSMicrophoneUsageDescription.md:29` | T1 | "A message that tells people why the app is requesting access to the device’s microphone." |
| S38 | 该键在访问麦克风的 API 下是**必需**的 | `ios-docs\Y-Bundleresources-Information-Property-List-NSMicrophoneUsageDescription.md:34` | T1 | "This key is required if your app uses APIs that access the device’s microphone." |
| S39 | HIG：相机与麦克风属于需申请权限的「设备能力」 | `hig-md\privacy.md:43` | T1 | "Device capabilities like camera and microphone" |
| S40 | 用途字符串写法：一句、具体、用简单句、别被动、结尾加句号 | `hig-md\privacy.md:53` | T2 | "Aim for a brief, complete sentence that’s straightforward, specific, and easy to understand." |
| S41 | 麦克风用途字符串反例（被动含糊 / 命令式） | `hig-md\privacy.md:58`、`:59` | T1 | "Microphone access is needed for a better experience." |
| S42 | 要选合适的 audio category；必须选 | `hig-md\playing-audio.md:36` | T2 | "Choose an audio category that fits the way your app or game uses sound." |
| S43 | `Record` 类别行为：不响应静音开关、不与其他音频混合、可后台录音 | `hig-md\playing-audio.md:43` | T1 | "Doesn’t respond to the silence switch. Doesn’t mix with other sounds. Can record in the background." |
| S44 | `Play and record` 类别行为：可同时录放、可后台 | `hig-md\playing-audio.md:44` | T1 | "Sound is recorded and played, potentially simultaneously." |
| S45 | 临时打断他人音频后要通知对方可恢复（`notifyOthersOnDeactivation`） | `hig-md\playing-audio.md:52` | T2 | "If your app can temporarily interrupt the audio of other apps, be sure to flag your audio session in a way that lets other apps know when they can resume." |
| S46 | 打断处理：可自定义是否让来电打断当前音频 | `hig-md\playing-audio.md:58` | T2 | "Determine how to respond to audio-session interruptions." |
| S47 | 打断分 resumable / nonresumable，据类型决定是否自动恢复（`shouldResume`） | `hig-md\playing-audio.md:60` | T2 | "An interruption can be *resumable*, like an incoming phone call, or *nonresumable*, like when people start a new music playlist." |
| S48 | 耳机接入应自动改路由；拔出应立即暂停 | `hig-md\playing-audio.md:26` | T2 | "When connecting headphones, people expect sound to reroute automatically without interruption; when disconnecting headphones, they expect playback to pause immediately." |
| S49 | iOS 上播短音与振动用 system sound services | `hig-md\playing-audio.md:66` | T2 | "Use the system’s sound services to play short sounds and vibrations." |
| S50 | `AVCaptureSession` 可自动配置 app 共享音频会话 | `ios-docs\AVFoundation-AVCaptureSession.md:291`（:287 定义） | T1 | "A Boolean value that indicates whether the capture session uses the app’s shared audio session." |
| S51 | 可让 session 把音频会话配成「与其他音频混合」 | `ios-docs\AVFoundation-AVCaptureSession.md:295` | T1 | "A Boolean value that Indicates whether the capture session configures the app’s audio session to mix with others." |
| S52 | 可让 session 为**蓝牙高质量录音**配置音频会话 | `ios-docs\AVFoundation-AVCaptureSession.md:299` | T2 | "A Boolean value that indicates whether the capture session configures the app’s audio session for bluetooth high-quality recording." |
| S53 | 采集会话有 interrupted 状态与 4 个相关通知 | `ios-docs\AVFoundation-AVCaptureSession.md:245`（:257、:261、:265） | T1 | "A Boolean value that indicates whether the capture session is in an interrupted state." |
| S54 | `startRunning()` 是阻塞调用，须放串行队列，避免堵主线程 | `ios-docs\AVFoundation-AVCaptureSession.md:61` | T2 | "The startRunning() method is a blocking call which can take some time, therefore start the session on a serial dispatch queue so that you don’t block the main queue" |
| S55 | 取默认音频输入设备：`AVCaptureDevice.default(for: .audio)` | `ios-docs\AVFoundation-AVCaptureSession.md:44` | T1 | "guard let audioDevice = AVCaptureDevice.default(for: .audio) else { return }" |
| S56 | `AVCaptureDevice` 同时代表相机与麦克风 | `ios-docs\Y-AVFoundation-AVCaptureDevice.md:29` | T1 | "An object that represents a hardware or virtual capture device like a camera or microphone." |
| S57 | 设备类型可区分「内置麦克风」 | `ios-docs\Y-AVFoundation-AVCaptureDevice.md:113` | T1 | "The type of device, such as a built-in microphone or wide-angle camera." |
| S58 | 麦克风采集权限 API：`requestAccess(for:completionHandler:)` / `authorizationStatus(for:)` | `ios-docs\Y-AVFoundation-AVCaptureDevice.md:81`（:85） | T1 | "Requests the user’s permission to allow the app to capture media of a particular type." |
| S59 | 系统会处理麦克风的音频增强（system video effects and microphone modes） | `ios-docs\Y-AVFoundation-AVCaptureDevice.md:315` | T1 | "Configure the state of system video effects like Center Stage, and inspect enhancements the system applies to microphone audio." |
| S60 | `AVSpeechSynthesizer`（TTS 方向）可用 `usesApplicationAudioSession` 交由 app 管音频会话 | `ios-fetch\avspeech2.md:97`（语义 :99） | T1 | "A Boolean value that indicates whether the app manages the audio session." |
| S61 | TTS 可指定输出声道（依赖 AVAudioSession 声道描述） | `ios-fetch\avspeech2.md:105` | T1 | "An array of audio session channels to route generated speech." |
| S62 | 合成器不会被系统自动持有，需自己强引用到播完 | `ios-fetch\avspeech2.md:49` | T1 | "The system doesn’t automatically retain the speech synthesizer, so you need to manually retain it until speech concludes." |
| S63 | SwiftUI `SensoryFeedback` 属另一主题（iOS 17+），与 Speech 无关 | `ios-fetch\sensoryfeedback.md:4` | T1 | "iOS: 17.0.0 -" |

**A2 条数：63 条。**

---

## B2. 必答问题逐条回答

### 问题 5 — 语音识别怎么起（真实签名与行号）

**初始化**：
- `convenience init?()` —— 用用户默认语言（`Speech-SFSpeechRecognizer.md:70`）
- `init?(locale: Locale)` —— 指定语言（`:74`）
- 注意：一个 recognizer 只支持**一种**语言，创建成功不代表服务可用（`:44`）

**availability**：
- `var isAvailable: Bool`（`:88`，T1）
- `var supportsOnDeviceRecognition: Bool`（`:92`，T1）—— 「can operate without network access」
- `var delegate: (any SFSpeechRecognizerDelegate)?` 用于跟踪可用性变化（`:80`）
- 官方给的顺序：先授权 → 建 recognizer → **查 isAvailable** → 备音频 → 建 request → 起 task（`:48`–`:53`）

**`SFSpeechAudioBufferRecognitionRequest`**：
- 官方页面**未包含** `shouldReportPartialResults` 属性 —— 全目录 0 命中（见 D2 第 4 条），**缓存未覆盖，不凭记忆补写**。该属性应属父类 `SFSpeechRecognitionRequest`，而该父类页亦不存在（`Test-Path=False`）。
- 缓存内实际有的成员：`append(AVAudioPCMBuffer)`（`:46`）、`appendAudioSampleBuffer(CMSampleBuffer)`（`:50`）、`endAudio()`（`:54`）、`nativeAudioFormat`（`:60`）。T1。
- 关键约束：必须显式 `endAudio()`，否则识别不停（`:38`，T1）。T1 原句："You must call endAudio() explicitly to stop the speech recognition process."

**`SFSpeechRecognitionTask`**：
- `func finish()` —— 停止接受新音频，但把已接受的音频处理完（`:54`，语义 `:56`，T1）
- `func cancel()` —— 立即取消（`:44`，T1）
- 语义差别（重要）：`finish` 是「跑完剩下的」，`cancel` 是「不要了」。原句分别是 "Stops accepting new audio and finishes processing on the audio input that has already been accepted."（`:56`）与 "Cancels the current speech recognition task."（`:46`）。
- 另有 `isFinishing`（`:58`）、`state`（`:64`）、`error`（`:72`）；任务对象不能自建（`:38`）。
- 起任务的真实签名：`func recognitionTask(with: SFSpeechRecognitionRequest, resultHandler: (SFSpeechRecognitionResult?, (any Error)?) -> Void) -> SFSpeechRecognitionTask`（`:122`）与 delegate 版（`:126`）。

### 问题 6 — 权限

**`requestAuthorization` 真实签名**：`class func requestAuthorization((SFSpeechRecognizerAuthorizationStatus) -> Void)`（`Speech-SFSpeechRecognizer.md:98`，T1）；配套 `class func authorizationStatus() -> SFSpeechRecognizerAuthorizationStatus`（`:102`）。

**`SFSpeechRecognizerAuthorizationStatus` 全枚举 —— 缓存未覆盖。** 该枚举在 `:98`、`:102`、`:106` 被引用 3 次，但**没有任何一页列出它的 case**；`denied` / `notDetermined` 在三目录 **0 命中**（仅 `restricted` 在 `Y-AVFoundation-AVCaptureDevice.md` 命中 4 次，但那是 `AVAuthorizationStatus`，不是本枚举）。→ 按约束，此处**不写枚举 case**，标注「缓存未覆盖」。

**Info.plist 键**：
- `NSSpeechRecognitionUsageDescription`：**缓存未覆盖**（三目录 0 命中，含 `NSSpeech` 前缀也是 0 命中）。**不凭记忆写其文案要求。**
- `NSMicrophoneUsageDescription`：**有**。
  - 定义原文：`ios-docs\Y-Bundleresources-Information-Property-List-NSMicrophoneUsageDescription.md:29` — "A message that tells people why the app is requesting access to the device’s microphone."（T1）
  - 必需性原文：`:34` — "This key is required if your app uses APIs that access the device’s microphone."（T1，位于 `> Important:` 块内，`:33`）
  - 版本：`iOS: 7.0.0 -`（`:4`）
- 权限 API 侧：`AVCaptureDevice.requestAccess(for:completionHandler:)`（`Y-AVFoundation-AVCaptureDevice.md:81`）与 `authorizationStatus(for:)`（`:85`），T1。
- HIG 要求：麦克风属需申请权限的设备能力（`hig-md\privacy.md:43`）；用途字符串要一句、具体、简单句、非被动、带句号（`:53`）；反例见 `:58`（被动含糊）与 `:59`（命令式）。

### 问题 7 — 实时识别 vs 录音后识别

**官方分流规则（T1，一句话）**：`Speech-SFSpeechRecognizer.md:55` — "For existing audio files, create a SFSpeechURLRecognitionRequest object. For audio streams, create a SFSpeechAudioBufferRecognitionRequest object."

| 场景 | API | 出处 | 等级 |
|---|---|---|---|
| **实时**（麦克风喂 buffer） | `SFSpeechAudioBufferRecognitionRequest` + `append(...)` 持续喂 + 显式 `endAudio()` | `Speech-SFSpeechAudioBufferRecognitionRequest.md:36`、`:38`、`:46` | T1 |
| **文件** | `SFSpeechURLRecognitionRequest` | `Speech-SFSpeechRecognizer.md:55`（仅引用） | T1（语义）／**页面缓存未覆盖** |
| 新架构·文件 | `AssetInputSequenceProvider` 或 `analyzeSequence(from: AVAudioFile)` | `Speech.md:102`、`speechanalyzer.md:250` | T1 |
| 新架构·麦克风 | `CaptureInputSequenceProvider` | `Speech.md:106`、`speechanalyzer.md:60` | T1 |

**`SFSpeechURLRecognitionRequest` 独立文档页：缓存未覆盖**（`Test-Path=False`，见 D2）。只有 `:55` 的语义描述可引用。

**`requiresOnDeviceRecognition` —— 缓存未覆盖**（三目录 0 命中）。缓存里**实际存在**的是另一个不同名属性 `supportsOnDeviceRecognition`（`Speech-SFSpeechRecognizer.md:92`），语义是「该 recognizer 能否无网络运行」（T1，只读能力位，不是开关）。

**关于「是否必须下载语言模型」（离线可用性）—— 官方在缓存内只给到这些（均非 `requiresOnDeviceRecognition`）：**
- 旧 API：部分语言可能需联网（`:44`，T1）；`supportsOnDeviceRecognition` 表示可离线（`:92`，T1）。
- 新 API：`AssetInventory` 负责「确保系统具备所需资产」（`Speech.md:34`，T1）；样例代码里有 `AssetInventory.assetInstallationRequest(supporting:)` + `downloadAndInstall()` 的完整下载安装流程（`ios-fetch\speechanalyzer.md:79`–`:81`，T1）；`SpeechTranscriber.supportedLocales` 明确包含「may not be installed but are downloadable」（`speechtranscriber.md:87`，T1），而 `installedLocales` 只含已装（`:83`，T1）。
→ 可确证：**新架构下语言模型/资产需要显式安装或下载，官方给了 API 但不给体积/耗时数值。**

### 问题 8 — 音频会话怎么配才不出错

**先核实：`AVAudioSession` 在缓存里没有独立的文档页。** 证据：
- `Test-Path "D:\...\ios-docs\AVAudioSession.md"` → **False**（D2 命令 2）
- 三目录 `AVAudioSession` 仅 7 次提及，分布在 4 个文件：`avspeech2.md`(1)、`hapticengine.md`(1)、`playing-audio.md`(4)、`Y-CoreHaptics-CHHapticEngine.md`(1)
- `setCategory` → **0 命中**；`playAndRecord` → **0 命中**；`measurement` → 命中的 6 处全是无关词义（`sliders.md`、`toggles.md` 等）；`HFP` → **0 命中**；`routeChange` → **0 命中**

**因此以下只能引用缓存里真实存在的规则（T1/T2），不能补写 `AVAudioSession` 的 API：**

1. **必须选一个 category（T2）**：`hig-md\playing-audio.md:36` — "Choose an audio category that fits the way your app or game uses sound."；同处链接指向 `AVAudioSession/Category-swift.struct`（范围外的页）。
2. **缓存里的 5 个 category 及其行为（T1，HIG 表格 `:38`–`:44`）**：
   - Solo ambient（`:40`）：响应静音开关、不混音、不后台
   - Ambient（`:41`）：响应静音开关、混音、不后台
   - Playback（`:42`）：不响应静音开关、可混音、可后台
   - **Record（`:43`）**：不响应静音开关、不混音、可后台录音
   - **Play and record（`:44`）**：不响应静音开关、可混音、可同时录放并后台
   → 本项目「边听边录」的场景，官方对应项就是 `Play and record`（`:44`）；纯录音场景对应 `Record`（`:43`）。
3. **`setActive` / 参数细节 —— 缓存未覆盖。** `setActive` 唯一命中是 `playing-audio.md:52` 里的 `notifyOthersOnDeactivation` 引用（意为停用时通知其他 app），**没有** `setActive(true/false)` 的签名或调用规则页。→ 不写具体 API。
4. **与蓝牙的关系 —— 只能引到这些（T2）**：
   - `AVCaptureSession.configuresApplicationAudioSessionForBluetoothHighQualityRecording`：让采集会话把 app 音频会话配成「蓝牙高质量录音」（`AVFoundation-AVCaptureSession.md:299`）。这是缓存里**唯一**与「蓝牙 + 录音质量」直接相关的官方属性，但它属于 **AVCaptureSession**，不是 AVAudioSession 的方法。
   - `AVSpeechSynthesizer.usesApplicationAudioSession`（`avspeech2.md:97`/`:99`）说明「app 自己管音频会话」是一个可切换的布尔。
   - **`AVAudioSessionCategoryPlayAndRecord` 与 HFP（Hands-Free Profile）采样率劣化问题：`HFP` 0 命中 → 缓存未覆盖，不作断言。**
5. **被打断（interruption）—— 有官方规则（T2）**：
   - `playing-audio.md:58`：可决定如何响应会话打断（如「来电不要打断当前音频，除非用户接听」）
   - `playing-audio.md:60`：打断分 **resumable**（如来电）/ **nonresumable**（如用户开了新歌单），据类型决定是否自动恢复；对应 `AVAudioSession/InterruptionOptions/shouldResume`
   - 采集侧：`AVCaptureSession.isInterrupted`（`:245`）、`wasInterruptedNotification`（`:257`）、`interruptionEndedNotification`（`:261`）、`runtimeErrorNotification`（`:265`）
   - Core Haptics 侧联动：`CHHapticEngineStoppedReasonAudioSessionInterrupt` —— 「来电或通知可能导致引擎停止，要在通话结束后重启」（`CoreHaptics-preparing-your-app-to-play-haptics.md:99`–`:101`）
6. **route change（路由变化）—— 缓存未覆盖。** `routeChange` 0 命中。缓存内最接近的官方规则是 HIG 的期望描述：插耳机应自动改路由且不中断、拔耳机应立即暂停（`playing-audio.md:26`，T2），以及 TTS 的 `outputChannels`（`avspeech2.md:105`）。**没有** `AVAudioSessionRouteChangeNotification` 之类 API 页。
7. **顺带一条易踩坑**：`AVCaptureSession.startRunning()` 是阻塞调用，必须放串行队列，否则堵主线程（`AVFoundation-AVCaptureSession.md:61`，T2）。

### 问题 9 — SpeechAnalyzer / SpeechTranscriber（iOS 26 新）

**存在，已覆盖（在 `ios-fetch\`，不在 `ios-docs\`）。** 真实命令输出：

```
PS> Get-ChildItem -LiteralPath "D:\AP\AP7000\ai-workspace\stackchan-research\ios-fetch" -File |
      Where-Object { $_.Name -match 'speech|feedback' } | Select Name,Length

avspeech2.md                         7590
sensoryfeedback-trigger.md           1631
sensoryfeedback.md                   4953
speechanalyzer.md                   18949
speechtranscriber.md                 4664
uifeedbackgenerator.md               3294
uiimpactfeedbackgenerator.md         4775
uinotificationfeedbackgenerator.md   2434
uiselectionfeedbackgenerator.md      3116

PS> Test-Path "D:\AP\AP7000\ai-workspace\stackchan-research\ios-fetch\speechanalyzer.md"    -> True
PS> Test-Path "D:\AP\AP7000\ai-workspace\stackchan-research\ios-fetch\speechtranscriber.md" -> True
```

**行号引用（T1/T2）：**

| 事实 | 出处 | 等级 |
|---|---|---|
| `SpeechAnalyzer` 可用版本 `iOS: 26.0.0 -`（iPadOS/macCatalyst/macOS/tvOS/visionOS 同为 26.0.0） | `ios-fetch\speechanalyzer.md:4`（:5–:9） | T1 |
| 声明为 `final actor SpeechAnalyzer` | `:32` | T1 |
| 只用 `SpeechTranscriber` 模块即可满足多数用例 | `:37` | T1 |
| 输入/输出/会话控制解耦，走 `AsyncSequence`（取代 delegate） | `:50` | T1 |
| 同时只能分析一路输入序列 | `:52` | T1 |
| 8 步流程：建模块→装资产→建输入序列→建 analyzer→供音频→开始→处理结果→结束 | `:58`–`:65` | T1 |
| 完整可运行样例（含 `SpeechTranscriber(locale:preset:)`、`AssetInventory` 下载、`analyzer.analyzeSequence`、`finalizeAndFinish`） | `:69`–`:129` | T1 |
| 结束方法：`finalizeAndFinish(through:)` / `cancelAndFinishNow()` / `finalizeAndFinishThroughEndOfInput()` | `:284`、`:276`、`:280` | T1 |
| 同时分析数「保守上限」**不给数字** | `:206` | T2 |
| 超限错误 `insufficientResources`；`ignoresResourceLimits=true` 可解除限制（但可能不可预期失败） | `:206`、`:210`、`:212` | T1 |
| `prepareToAnalyze(in:)` 预热以减少首结果延迟 | `:178` | T2 |
| `SpeechTranscriber` 可用版本 `iOS: 26.0.0 -` | `ios-fetch\speechtranscriber.md:4` | T1 |
| `SpeechTranscriber` 是 `final class` | `:32` | T1 |
| 设备不支持时改用 `DictationTranscriber` | `:41` | T2 |
| `results` 是 `AsyncSequence<SpeechTranscriber.Result, any Error>` | `:101` | T1 |
| `installedLocales`（已装）vs `supportedLocales`（含可下载） | `:83`、`:87` | T1 |
| 框架总览页已把 `SpeechAnalyzer` 列为 `actor`、`SpeechTranscriber` 列为 `class` | `ios-docs\Speech.md:52`、`:68` | T1 |

**注意一个缓存内的事实性张力（必须记录，不可调和掉）**：`ios-docs\Speech.md` 的框架级 availability 写的是 `iOS: 10.0.0 -`（`Speech.md:4`），但 `SpeechAnalyzer`/`SpeechTranscriber` 各自页面都是 `iOS: 26.0.0 -`（`speechanalyzer.md:4`、`speechtranscriber.md:4`）。→ 引用时以**具体类型页**为准：新架构 = iOS 26+，旧 `SFSpeechRecognizer` = iOS 10+。

---

## C2. 官方未给数值清单

| 项目 | 状态 | 依据 |
|---|---|---|
| 单次识别任务的时长上限 | **有数值**：1 分钟（T1） | `Speech-SFSpeechRecognizer.md:62` |
| 每设备每日识别次数上限 | **官方未给数值** | `Speech-SFSpeechRecognizer.md:61` 只说 "limited in the number of recognitions" |
| 每 app 每日请求限流阈值 | **官方未给数值** | 同上 ":61" |
| `SpeechAnalyzer` 同时分析数上限 | **官方未给数值**（原文明确说 "a conservative number" 而不给数） | `speechanalyzer.md:206` |
| 语言模型/资产下载体积与耗时 | **官方未给数值** | `speechanalyzer.md:79`–`:81` 只给 API，无体积/时长 |
| 识别音频格式的采样率/位深 | **官方未给数值** | `Speech-SFSpeechAudioBufferRecognitionRequest.md:60` 只有 `nativeAudioFormat` 属性，不列具体格式 |
| 音频会话采样率 / IO buffer 时长 | **官方未给数值** | `AVAudioSession` 无页（D2），HIG 音频页无此数字 |
| HFP 蓝牙录音采样率劣化幅度 | **官方未给数值** | `HFP` 0 命中 |
| 打断后自动恢复的等待时间 | **官方未给数值** | `playing-audio.md:60` 只给 resumable/nonresumable 判据 |
| watchOS 音频编码参数 | **有数值**：64 kbps HE-AAC（T1，但与 speech 主题无关，仅记录） | `playing-audio.md:100` |

---

## D2. 缓存未覆盖项（含真实命令输出）

命令与命中数见上文 **D1「命令 3」**（同一次三目录检索的真实输出）。逐项判定：

| # | 项 | 判定 | 证据 | 处理 |
|---|---|---|---|---|
| 1 | **`AVAudioSession` 独立文档页** | **缓存未覆盖** | `Test-Path ios-docs\AVAudioSession.md` = **False**；三目录仅 7 次提及，分布 4 文件（`avspeech2.md`=1、`hapticengine.md`=1、`playing-audio.md`=4、`Y-CoreHaptics-CHHapticEngine.md`=1）；`setCategory`=0、`playAndRecord`=0、`HFP`=0、`routeChange`=0、`measurement`=仅有无关词义 | 只引 HIG category 表（`playing-audio.md:38`–`:44`）与 AVCaptureSession 的音频会话开关（`:287`–`:301`）；**不写任何 AVAudioSession 方法签名** |
| 2 | **`NSSpeechRecognitionUsageDescription`** | **缓存未覆盖** | 三目录 `NSSpeechRecognitionUsageDescription` = **0 命中**；宽前缀 `NSSpeech` = **0 命中** | 不写该键的文案要求；只写 `NSMicrophoneUsageDescription` 的原文（`:29`/`:34`） |
| 3 | **`requiresOnDeviceRecognition`** | **缓存未覆盖** | 三目录 = **0 命中** | 不推断其语义/默认值。改写缓存中确有的 `supportsOnDeviceRecognition`（`Speech-SFSpeechRecognizer.md:92`）并说明二者是**不同**属性 |
| 4 | **`shouldReportPartialResults`** | **缓存未覆盖** | 三目录 = **0 命中**；父类页 `Speech-SFSpeechRecognitionRequest.md` **Test-Path=False** | 不写该属性的类型/默认值 |
| 5 | **`SFSpeechRecognizerAuthorizationStatus` 的 case 枚举** | **页面未覆盖** | 枚举名在 `Speech-SFSpeechRecognizer.md:98`/`:102`/`:106` 被引用 3 次，但无 case 列表；`denied`=0、`notDetermined`=0 命中；`Test-Path Speech-SFSpeechRecognizerAuthorizationStatus.md` = **False** | 只写「有该枚举 + 它是 requestAuthorization 的回调参数类型」，**不列 case** |
| 6 | **`SFSpeechURLRecognitionRequest` 独立页** | **缓存未覆盖** | `Test-Path` = **False**；仅在 `Speech-SFSpeechRecognizer.md:55`、`Y-Speech-SFSpeechRecognizer.md:55` 被引用 | 只引 `:55` 的「文件用 URL request」这条语义规则 |
| 7 | **`SpeechAnalyzer` / `SpeechTranscriber`** | **已覆盖** | `Test-Path ios-fetch\speechanalyzer.md` = **True**（18949 B / 344 行）、`speechtranscriber.md` = **True**（4664 B / 129 行） | 已给行号引用（B2-Q9） |
| 8 | **`UIFeedbackGenerator` 家族** | **已覆盖**（在 ios-fetch） | `uifeedbackgenerator.md`=True/101 行、`uiimpactfeedbackgenerator.md`=True/145 行、`uinotificationfeedbackgenerator.md`=True/82 行、`uiselectionfeedbackgenerator.md`=True/107 行 | 已给行号引用（A1 H31–H36） |
| 9 | **`UISensoryFeedbackGenerator`** | **缓存未覆盖** | 三目录 = **0 命中**；且 `uifeedbackgenerator.md:36`–`:39` 的 4 个具体子类名单中无此项 | **不凭记忆补写其 API**；不确定性已在 A1/B1 标注 |
| 10 | `AVAudioSession` 相关专题页（`handling-audio-interruptions`、`AVAudioSession/Category-swift.struct`、`InterruptionOptions/shouldResume`、`SetActiveOptions/notifyOthersOnDeactivation`） | **缓存未覆盖** | 仅在 `playing-audio.md:36`、`:52`、`:58`、`:60` 以 `doc://` 链接形式出现，无页面正文 | 只引 HIG 的规则性描述 |
| 11 | `SpeechAnalyzer.Options`、`AssetInventory`、`AnalyzerInputConverter`、`CaptureInputSequenceProvider` 等新类型页 | **缓存未覆盖** | 仅在 `Speech.md:34`/`:56`/`:100`/`:104`/`:108` 与 `speechanalyzer.md` 正文中被引用/使用，无独立页 | 只引被引用处的功能描述与样例代码行 |

---

## E2. 对本项目 App 的落地含义

1. **技术选型按 iOS 版本劈开**：目标系统若含 iOS 26+，新代码用 `SpeechAnalyzer` + `SpeechTranscriber`（`speechanalyzer.md:4`、`:37`）；需要向下兼容 iOS 10–25 时保留 `SFSpeechRecognizer` + `SFSpeechAudioBufferRecognitionRequest`（`Speech-SFSpeechRecognizer.md:4`、`:55`）。
2. **必须处理 1 分钟硬限制**：旧 API 的识别任务超过一分钟会被框架停止（`Speech-SFSpeechRecognizer.md:62`，T1）。连续听音的产品必须做「分段重启 + 拼接」策略，不能假设一次 task 能长跑。
3. **实时链路 = buffer 喂 + 显式 endAudio**：不收尾就永远不停（`SFSpeechAudioBufferRecognitionRequest.md:38`）。停止用 `finish()`（跑完剩余）还是 `cancel()`（丢弃）要按产品语义选（`Z-Speech-SFSpeechRecognitionTask.md:54`/`:44`）。
4. **权限要成对准备**：`NSMicrophoneUsageDescription` 是硬性必需（`:34`），用途字符串按 HIG 写法（一句、具体、非被动、带句号，`privacy.md:53`）；语音识别侧还有 `requestAuthorization`（`Speech-SFSpeechRecognizer.md:98`），但其配套 Info.plist 键在缓存中未覆盖，**需要另行取证后才能真正落地**（不要在代码评审里凭记忆写键名）。
5. **录音 + 触感同时工作时，先处理互相干扰**：HIG 明说触感振动可能干扰麦克风（`playing-haptics.md:41`）；因此录音期间应关闭或降级强连续触感。
6. **音频会话配置依赖缓存外的文档**：category 层面能确定的是「边听边录 → Play and record」（`playing-audio.md:44`）、「纯录音 → Record」（`:43`）；但 `setActive`、蓝牙 HFP、route change 三项在缓存内**没有**页面，实施前必须补齐官方文档，否则容易踩「插入蓝牙耳机后采样率被降到 HFP 导致识别率暴跌」这类经典坑——**这一因果关系为工程常识，不是本档案的官方结论，故不作为证据引用。**
7. **打断要当一等公民**：来电打断要区分 resumable/nonresumable 决定是否自动续（`playing-audio.md:60`），并注意打断会连带停掉 haptic engine（`CoreHaptics-preparing-your-app-to-play-haptics.md:99`–`:101`），恢复时要重启引擎。
8. **资产要显式安装**：新架构下语言模型不保证预装，`AssetInventory.assetInstallationRequest(supporting:)` + `downloadAndInstall()` 是官方给的路径（`speechanalyzer.md:79`–`:81`）；`installedLocales` 与 `supportedLocales` 的差别就是「能不能立刻用」的判据（`speechtranscriber.md:83`/`:87`）。**官方不提供下载体积/耗时数值**，UI 上不要承诺具体秒数。
9. **不要把并发拉到极限**：同时分析数有系统保守上限且官方不给数字（`speechanalyzer.md:206`），`ignoresResourceLimits` 属于「会不可预期失败」的危险开关（`:210`、`:212`），产品上应串行化或单实例复用。

---

## F. 查证过的文件清单（文件名 + 是否全读 + 行数）

| 文件 | 是否全读 | 行数 | 备注 |
|---|---|---|---|
| `ios-docs\corehaptics.md` | 全读 | 142 | availability 数组为空（`:3`–`:5`） |
| `ios-docs\CoreHaptics-preparing-your-app-to-play-haptics.md` | 全读 | 138 | |
| `ios-docs\CoreHaptics-delivering-rich-app-experiences-with-haptics.md` | 全读 | 30 | 仅 1 条有效事实（iPhone 8+） |
| `ios-docs\CoreHaptics-playing-a-single-tap-haptic-pattern.md` | 全读 | 86 | |
| `ios-docs\CoreHaptics-CHHapticEvent.md` | 全读 | 115 | |
| `ios-docs\CoreHaptics-CHHapticAdvancedPatternPlayer.md` | 全读 | 95 | |
| `ios-docs\CoreHaptics-CHHapticDynamicParameter.md` | 全读 | 89 | |
| `ios-docs\chhapticpattern.md` | 全读 | 119 | |
| `ios-docs\chhapticparametercurve.md` | 全读 | 91 | |
| `ios-docs\hapticengine.md` | 全读 | 257 | |
| `ios-docs\Y-CoreHaptics-CHHapticEngine.md` | 全读（哈希比对） | 257 | **与 `hapticengine.md` 完全同一份**，SHA256 均为 `EC8A238A…B9654` |
| `ios-docs\Y-CoreHaptics-CHHapticPatternPlayer.md` | 全读 | 85 | |
| `ios-docs\Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md` | 全读 | 114 | **全部 0–1 / −1–1 数值的唯一来源** |
| `ios-docs\JSON-corehaptics.json` | 全读（原始 JSON 抽取） | 1（单行，30130 字符） | 交叉验证：abstract 与 `corehaptics.md:24` 一致；**不含** `AVAudio`、不含大写 `Intensity` 键 |
| `hig-md\playing-haptics.md` | 全读（232 行全文） | 232 | 18422 B |
| `hig-md\feedback.md` | 全读 | 75 | |
| `ios-fetch\uifeedbackgenerator.md` | 全读 | 101 | **任务书假设「可能没有」实际有** |
| `ios-fetch\uiimpactfeedbackgenerator.md` | 全读 | 145 | |
| `ios-fetch\uinotificationfeedbackgenerator.md` | 全读 | 82 | |
| `ios-fetch\uiselectionfeedbackgenerator.md` | 全读 | 107 | |
| `ios-fetch\sensoryfeedback.md` | 全读 | 164 | 仅用于记录 B1-Q3 的关系，不展开 |
| `ios-docs\Speech.md` | 全读 | 150 | |
| `ios-docs\Speech-SFSpeechRecognizer.md` | 全读 | 166 | |
| `ios-docs\Y-Speech-SFSpeechRecognizer.md` | 全读（哈希比对） | 166 | **与 `Speech-SFSpeechRecognizer.md` 完全同一份**，SHA256 `5BFB0B2B…E8F2` |
| `ios-docs\Speech-SFSpeechAudioBufferRecognitionRequest.md` | 全读 | 86 | |
| `ios-docs\Y-Speech-SFSpeechAudioBufferRecognitionRequest.md` | 全读（哈希比对） | 86 | **与上一份完全同一份**，SHA256 `7698AEA2…614D` |
| `ios-docs\Z-Speech-SFSpeechRecognitionTask.md` | 全读 | 98 | |
| `ios-docs\AVFoundation-AVCaptureSession.md` | 全读 | 345 | |
| `ios-docs\Y-AVFoundation-AVCaptureDevice.md` | 全读（1–279 + 280–497 两段） | 497 | |
| `ios-docs\Y-Bundleresources-Information-Property-List-NSMicrophoneUsageDescription.md` | 全读 | 38 | |
| `hig-md\playing-audio.md` | 全读 | 136 | |
| `hig-md\privacy.md` | 全读 | 230 | |
| `ios-fetch\speechanalyzer.md` | 全读 | 344 | **iOS 26.0.0 触感外的新能力证据** |
| `ios-fetch\speechtranscriber.md` | 全读 | 129 | |
| `ios-fetch\avspeech2.md` | 全读 | 169 | `AVSpeechSynthesizer`（TTS），非识别；用于 audio session 线索 |
| `ios-fetch\sensoryfeedback-trigger.md` | 仅 grep（6 命中 `sensoryFeedback`） | 未计入引用 | 未作为证据使用 |

**重复副本结论（哈希实测）**：
```
hapticengine.md <-> Y-CoreHaptics-CHHapticEngine.md                : IDENTICAL
Speech-SFSpeechRecognizer.md <-> Y-Speech-SFSpeechRecognizer.md    : IDENTICAL
Speech-SFSpeechAudioBufferRecognitionRequest.md <-> Y-...Request.md: IDENTICAL
```
→ 三组「Y-」前缀文件**都是重复副本**，不是补充内容。

---

## G. 自检：引用行号复核（A1+A2 每条贴出实际读到的该行原文）

> 复核方法：按 `文件:行号` 用 `read`（带 offset/limit）重新定位并逐字比对。以下 `▸` 后为**实际读到的该行原文**。不符则撤回。

### G-1（对应 A1）

- **H01** `corehaptics.md:28` ▸ "Core Haptics lets you add customized haptic and audio feedback to your app. … With Core Haptics, you extend this functionality by composing and combining haptics beyond the default patterns." ✅ 末句存在
- **H02** `hapticengine.md:37` ▸ "If you want your app to play custom haptics, you need to create a haptic engine. … Even though you can define a haptic pattern without an engine, you need the engine to play that pattern." ✅
- **H03** `hapticengine.md:41` ▸ "Even though your app makes a request through the haptic engine, the operating system could still override the request with system services, like haptics from system notifications." ✅
- **H04** `Y-CoreHaptics-Representing-haptic-patterns-in-ahap-files.md:65` ▸ "- `ParameterValue`: The numeric value of the associated parameter. These values are normalized to a range between 0 and 1 to represent the minimum and maximum the system supports." ✅
- **H05** 同文件 `:71` ▸ "- `HapticIntensity`: The strength of the haptic event. The value is between 0 and 1." ✅
- **H06** 同文件 `:72` ▸ "- `HapticSharpness`: The degree to which the haptic event feels tingly, or persistent. The value is between 0 and 1." ✅
- **H07** 同文件 `:73` ▸ "- `AttackTime`: The amount of time it takes for the event’s intensity envelope to reach its full strength. The value is between 0 and 1." ✅（`:74` DecayTime、`:75` ReleaseTime 同为 0–1，已核）
- **H08** 同文件 `:78` ▸ "- `AudioPan`: The distribution of the audio signal. This value is between -1 and 1." ✅（`:79` AudioPitch 同为 −1–1）
- **H09** 同文件 `:83` ▸ "> A value of 0 doesn’t mean that the parameter has no effect, or that the absolute value of the parameter is zero. It’s a normalized value that maps to the minimum value the system supports." ✅
- **H10** 同文件 `:22` ▸ "…When Core Haptics loads an AHAP file, it sets missing entries to their default value and clamps out-of-range values to their minimum or maximum values, whichever is closer." ✅
- **H11** `CoreHaptics-preparing-your-app-to-play-haptics.md:25` ▸ "…Some devices don’t support haptic feedback, including iPad, iPod touch, and Apple Vision Pro." ✅
- **H12** 同文件 `:33` ▸ "self.supportsHaptics = CHHapticEngine.capabilitiesForHardware.supportsHaptics;" ✅
- **H13** 同文件 `:56` ▸ "> The haptic engine isn’t a singleton; you can create multiple instances in different parts of your app or game, like different view controllers or levels." ✅（同段含 "Core Haptics is thread-safe"）
- **H14** 同文件 `:99` ▸ "case CHHapticEngineStoppedReasonAudioSessionInterrupt: {" ✅（`:104` ApplicationSuspended、`:109` IdleTimeout、`:114` SystemError 已核）
- **H15** 同文件 `:126` ▸ "> The stopped handler isn’t called if you manually stop the engine through an explicit ``doc://…CHHapticEngine/stop(completionHandler:)`` call." ✅
- **H16** `hapticengine.md:117` ▸ "[`var playsHapticsOnly: Bool`](/documentation/CoreHaptics/CHHapticEngine/playsHapticsOnly)"；描述 `:119` ▸ "A Boolean value that indicates whether the engine ignores audio events." ✅
- **H17** `hapticengine.md:155` ▸ "[`func notifyWhenPlayersFinished(finishedHandler: CHHapticEngine.FinishedHandler)`](…)"；描述 `:157` ▸ "Notifies you when all haptic pattern players have finished playing their haptic patterns." ✅（表中引用为 `:155`，英文句在 `:157`）
- **H18** `hapticengine.md:221` ▸ "[`var isAutoShutdownEnabled: Bool`](…)"；描述 `:223` ▸ "A Boolean value that indicates whether the haptic engine starts and stops automatically on request from one of its pattern players, or when idle." ✅
- **H19** `CoreHaptics-playing-a-single-tap-haptic-pattern.md:82` ▸ "Unless you’re playing several haptic patterns in succession, bookend haptic playback with starting and stopping the engine. … Be aware that your engine may stop on its own in auto-shutdown mode." ✅
- **H20** 同文件 `:62` ▸ "Haptic players are inexpensive, lightweight objects, so create and discard them freely." ✅
- **H21** `hig-md\playing-haptics.md:33` ▸ "**Prefer using haptics to complement other feedback in your app or game.** … For example, you generally want to match the intensity and sharpness of a haptic with the intensity and sharpness of the animation it accompanies." ✅
- **H22** 同文件 `:35` ▸ "**Avoid overusing haptics.** Sometimes a haptic can feel just right when it happens occasionally, but become tiresome when it plays frequently." ✅
- **H23** 同文件 `:37` ▸ "**In most apps, prefer playing short haptics that complement discrete events.** …" ✅
- **H24** 同文件 `:39` ▸ "**Make haptics optional.** Let people turn off or mute haptics, and make sure people can still enjoy your app or game without them." ✅
- **H25** 同文件 `:41` ▸ "**Be aware that playing haptics might impact other user experiences.** … Ensure that haptic vibrations don’t disrupt experiences involving device features like the camera, gyroscope, or microphone." ✅
- **H26** 同文件 `:29` ▸ "**Use system-provided haptic patterns according to their documented meanings.** … If the documented use case for a pattern doesn’t make sense in your app or game, avoid using the pattern to mean something else." ✅
- **H27** 同文件 `:31` ▸ "**Use haptics consistently throughout your app or game.** It’s important to build a clear, causal relationship between each haptic and the action that causes it so people learn to associate certain haptic patterns with certain experiences." ✅
- **H28** 同文件 `:65` ▸ "- When it makes sense, use a feedback generator to play one of several predefined haptic patterns in the categories of [notification]…, [impact]…, and [selection]… (for developer guidance, see <doc://…/UIKit/UIFeedbackGenerator>)." ✅
- **H29** 同文件 `:54` ▸ "…As the term implies, intensity means the strength of the haptic." ✅（该行无任何数值）
- **H30** 同文件 `:227` ▸ "|May 7, 2024  |Added guidance for playing haptics on Apple Pencil Pro.|"；`:228` ▸ "|June 21, 2023|Updated to include guidance for visionOS.              |" ✅（`:225` 为表头行 "|Date         |Changes |"，`:226` 为分隔行）
- **H31** `ios-fetch\uifeedbackgenerator.md:34` ▸ "Don’t subclass or create instances of this class yourself. Instead, instantiate one of the concrete feedback generator subclasses:" ✅
- **H32** 同文件 `:36` ▸ "- [`UIImpactFeedbackGenerator`](/documentation/UIKit/UIImpactFeedbackGenerator). Use impact feedback to indicate when an impact occurs. …"；`:37` selection、`:38` notification、`:39` canvas ▸ "…[`UICanvasFeedbackGenerator`]… Use canvas feedback to indicate when a drawing event occurs, such as an object snapping to a guide or ruler." ✅
- **H33** `ios-fetch\uiimpactfeedbackgenerator.md:93` ▸ "The mass of the objects in the collision simulated by an impact feedback generator object." ✅
- **H34** 同文件 `:113` ▸ "[`func impactOccurred(intensity: CGFloat, at: CGPoint)`](/documentation/UIKit/UIImpactFeedbackGenerator/impactOccurred(intensity:at:))" ✅
- **H35** `ios-fetch\uiselectionfeedbackgenerator.md:75` ▸ "[`func selectionChanged(at: CGPoint)`](/documentation/UIKit/UISelectionFeedbackGenerator/selectionChanged(at:))" ✅
- **H36** `ios-fetch\uinotificationfeedbackgenerator.md:46` ▸ "[`func notificationOccurred(UINotificationFeedbackGenerator.FeedbackType, at: CGPoint)`](…)" ✅
- **H37** `CoreHaptics-delivering-rich-app-experiences-with-haptics.md:26` ▸ "- You must run the sample on iPhone 8 or later." ✅
- **H38** `CoreHaptics-CHHapticDynamicParameter.md:39` ▸ "For haptic intensity and audio volume, the final property value is equal to the original event parameter value multiplied by the dynamic parameter value. … In both cases, the resulting value is limited to the range with minimum and maximum values corresponding to the specified event parameter." ✅
- **H39** `CoreHaptics-CHHapticEvent.md:43` ▸ "Specify when an event begins by setting its relativeTime property. … For example, you can specify the intensity of a haptic event by creating an event parameter with ID hapticIntensity." ✅（该页全篇无 0–1 数值）
- **H40** `ios-fetch\sensoryfeedback.md:4` ▸ `"iOS: 17.0.0 -",`；`:38` ▸ "This feedback can be passed to `View.sensoryFeedback` to play it." ✅

### G-2（对应 A2）

- **S01** `Speech.md:28` ▸ "Perform speech recognition on live or prerecorded audio, and receive transcriptions, alternative interpretations, and confidence levels of the results." ✅
- **S02** `Speech.md:34` ▸ "The [`SpeechTranscriber`]… class and other module classes provide specific services. The [`AssetInventory`]… class ensures that the system has the assets necessary… The [`SpeechAnalyzer`]… class manages an analysis session… The [`AssetInputSequenceProvider`]… and [`CaptureInputSequenceProvider`]… classes provide audio from files or microphone devices." ✅
- **S03** `speechanalyzer.md:4` ▸ `"iOS: 26.0.0 -",` ✅
- **S04** `speechanalyzer.md:32` ▸ "final actor SpeechAnalyzer" ✅
- **S05** `speechanalyzer.md:52` ▸ "The analyzer can only analyze one input sequence at a time." ✅
- **S06** `speechanalyzer.md:50` ▸ "…Similarly, you provide speech input to this API via an `AsyncSequence` you create and populate." ✅
- **S07** `speechanalyzer.md:206` ▸ "The system normally limits simultaneous analyses to a conservative number, considering hardware capabilities of different devices. If you exceed that number, the system throws an insufficientResources error." ✅（无具体数字）
- **S08** `speechanalyzer.md:210` ▸ "…To override the normal limits, create an analyzer with a SpeechAnalyzer.Options object with its ignoresResourceLimits value set to `true`. The system allows an unlimited number of analyzers configured with this option." ✅
- **S09** `speechanalyzer.md:137` ▸ "…Otherwise, by default, the analyzer won’t terminate its result streams and will wait for additional audio input sequences or buffers." ✅
- **S10** `speechanalyzer.md:196` ▸ "> Note: While you can terminate the input sequence you created with a method such as `AsyncStream.Continuation.finish()`, terminating the input sequence does *not* generally finish the analysis session…" ✅
- **S11** `speechanalyzer.md:178` ▸ "To proactively load system resources and “preheat” the analyzer, call prepareToAnalyze(in:) after setting its modules." ✅
- **S12** `speechtranscriber.md:4` ▸ `"iOS: 26.0.0 -",` ✅
- **S13** `speechtranscriber.md:41` ▸ "Use the isAvailable or supportedLocales properties to see if the current device supports the speech-to-text models used by `SpeechTranscriber`. If it does not, consider disabling the feature or using DictationTranscriber instead." ✅
- **S14** `speechtranscriber.md:81` ▸ "[`static var installedLocales: [Locale]`](…)"；`:83` ▸ "The locales that the transcriber can transcribe into, considering only locales that are installed on the device."；`:85` supportedLocales；`:87` ▸ "…including locales that may not be installed but are downloadable." ✅
- **S15** `Speech-SFSpeechRecognizer.md:28` ▸ "An object you use to check for the availability of the speech recognition service, and to initiate the speech recognition process." ✅
- **S16** `Speech-SFSpeechRecognizer.md:44` ▸ "Each speech recognizer supports only one language, which you specify at creation time. … For some languages, the recognizer might require an Internet connection. Use the isAvailable property…" ✅
- **S17** `Speech-SFSpeechRecognizer.md:70` ▸ "[`convenience init?()`](/documentation/Speech/SFSpeechRecognizer/init())"；`:74` ▸ "[`init?(locale: Locale)`](…)" ✅
- **S18** `Speech-SFSpeechRecognizer.md:88` ▸ "[`var isAvailable: Bool`](…)"; `:92` ▸ "[`var supportsOnDeviceRecognition: Bool`](…)"; `:94` ▸ "A Boolean value that indicates whether the speech recognizer can operate without network access." ✅
- **S19** `Speech-SFSpeechRecognizer.md:55` ▸ "…For existing audio files, create a SFSpeechURLRecognitionRequest object. For audio streams, create a SFSpeechAudioBufferRecognitionRequest object." ✅
- **S20** `Speech-SFSpeechRecognizer.md:48` ▸ "1. Request authorization to use speech recognition. See Asking Permission to Use Speech Recognition."（步 2–6 在 `:49`–`:53`）✅
- **S21** `Speech-SFSpeechRecognizer.md:62` ▸ "- **Plan for a one-minute limit on audio duration.** … To minimize this burden, the framework stops speech recognition tasks that last longer than one minute. This limit is similar to the one for keyboard-related dictation." ✅ **官方数值，T1**
- **S22** `Speech-SFSpeechRecognizer.md:61` ▸ "…Individual devices may be limited in the number of recognitions that can be performed per day, and each app may be throttled globally based on the number of requests it makes per day." ✅（无具体数字）
- **S23** `Speech-SFSpeechRecognizer.md:63` ▸ "- **Remind the user when your app is recording.** For example, display a visual indicator and play sounds at the beginning and end of speech recognition…" ✅
- **S24** `Speech-SFSpeechRecognizer.md:64` ▸ "- **Do not perform speech recognition on private or sensitive information.** … Don’t send passwords, health or financial data, and other sensitive speech for recognition." ✅
- **S25** `Speech-SFSpeechRecognizer.md:98` ▸ "[`class func requestAuthorization((SFSpeechRecognizerAuthorizationStatus) -> Void)`](…)" ✅
- **S26** `Speech-SFSpeechRecognizer.md:102` ▸ "[`class func authorizationStatus() -> SFSpeechRecognizerAuthorizationStatus`](…)" ✅
- **S27** `Speech-SFSpeechRecognizer.md:106` ▸ "[`enum SFSpeechRecognizerAuthorizationStatus`](…)"; `:108` ▸ "The app’s authorization to perform speech recognition." ✅（无 case 列表）
- **S28** `Speech-SFSpeechRecognizer.md:122` ▸ "[`func recognitionTask(with: SFSpeechRecognitionRequest, resultHandler: (SFSpeechRecognitionResult?, (any Error)?) -> Void) -> SFSpeechRecognitionTask`](…)"; `:126` delegate 版 ✅
- **S29** `Speech-SFSpeechAudioBufferRecognitionRequest.md:36` ▸ "Use an [`SFSpeechAudioBufferRecognitionRequest`]… object to perform speech recognition on live audio, or on a set of existing audio buffers." ✅
- **S30** 同文件 `:38` ▸ "…The speech recognizer continuously analyzes the audio you appended, stopping only when you call the endAudio() method. You must call endAudio() explicitly to stop the speech recognition process." ✅
- **S31** 同文件 `:46` ▸ "[`func append(AVAudioPCMBuffer)`](…)"; `:50` ▸ "[`func appendAudioSampleBuffer(CMSampleBuffer)`](…)"; `:54` ▸ "[`func endAudio()`](…)"; `:56` ▸ "Marks the end of audio input for the recognition request." ✅
- **S32** 同文件 `:60` ▸ "[`var nativeAudioFormat: AVAudioFormat`](…)"; `:62` ▸ "The preferred audio format for optimal speech recognition." ✅
- **S33** `Z-Speech-SFSpeechRecognitionTask.md:54` ▸ "[`func finish()`](…)"; `:56` ▸ "Stops accepting new audio and finishes processing on the audio input that has already been accepted." ✅
- **S34** 同文件 `:44` ▸ "[`func cancel()`](…)"; `:46` ▸ "Cancels the current speech recognition task." ✅
- **S35** 同文件 `:58` ▸ "[`var isFinishing: Bool`](…)"; `:60` ▸ "A Boolean value that indicates whether audio input has stopped." ✅
- **S36** 同文件 `:38` ▸ "You don’t create speech recognition task objects directly. Instead, you receive one of these objects after calling recognitionTask(with:resultHandler:)…" ✅
- **S37** `Y-Bundleresources-Information-Property-List-NSMicrophoneUsageDescription.md:29` ▸ "A message that tells people why the app is requesting access to the device’s microphone." ✅
- **S38** 同文件 `:34` ▸ "> This key is required if your app uses APIs that access the device’s microphone." ✅（`> Important:` 标记在 `:33`）
- **S39** `hig-md\privacy.md:43` ▸ "- Device capabilities like camera and microphone" ✅
- **S40** 同文件 `:53` ▸ "**Write copy that clearly describes how your app uses the ability, data, or resource you’re requesting.** … Aim for a brief, complete sentence that’s straightforward, specific, and easy to understand. Use sentence case, avoid passive voice, and include a period at the end." ✅
- **S41** 同文件 `:58` ▸ "|![An X in a circle…]|Microphone access is needed for a better experience.|A passive sentence that provides a vague, undefined justification.|"; `:59` ▸ "|![An X…]|Turn on microphone access.|An imperative sentence that doesn’t provide any justification.|" ✅
- **S42** `hig-md\playing-audio.md:36` ▸ "**Choose an audio category that fits the way your app or game uses sound.** … For developer guidance, see <doc://…/AVFAudio/AVAudioSession/Category-swift.struct>." ✅
- **S43** 同文件 `:43` ▸ "|Record         |Sound is recorded. …|Doesn’t respond to the silence switch. Doesn’t mix with other sounds. Can record in the background. |" ✅
- **S44** 同文件 `:44` ▸ "|Play and record|Sound is recorded and played, potentially simultaneously. …|Doesn’t respond to the silence switch. May or may not mix with other sounds. Can record and play in the background.|" ✅
- **S45** 同文件 `:52` ▸ "**Let other apps know when your app finishes playing temporary audio.** … see <doc://…/AVAudioSession/SetActiveOptions/notifyOthersOnDeactivation>." ✅
- **S46** 同文件 `:58` ▸ "**Determine how to respond to audio-session interruptions.** … see <doc://…/AVFAudio/handling-audio-interruptions>." ✅
- **S47** 同文件 `:60` ▸ "…An interruption can be *resumable*, like an incoming phone call, or *nonresumable*, like when people start a new music playlist. … see <doc://…/AVAudioSession/InterruptionOptions/shouldResume>." ✅
- **S48** 同文件 `:26` ▸ "**Headphones.** … When connecting headphones, people expect sound to reroute automatically without interruption; when disconnecting headphones, they expect playback to pause immediately." ✅
- **S49** 同文件 `:66` ▸ "**Use the system’s sound services to play short sounds and vibrations.** For developer guidance, see <doc://…/AudioToolbox/audio-services>." ✅
- **S50** `AVFoundation-AVCaptureSession.md:287` ▸ "[`var usesApplicationAudioSession: Bool`](…)"; `:289` ▸ "A Boolean value that indicates whether the capture session uses the app’s shared audio session."；`:291` automaticallyConfiguresApplicationAudioSession；`:293` ▸ "A Boolean value that indicates whether the capture session automatically changes settings in the app’s shared audio session." ✅（表中 S50 引 `:291`，定义句在 `:289`/`:293`）
- **S51** 同文件 `:295` ▸ "[`var configuresApplicationAudioSessionToMixWithOthers: Bool`](…)"; `:297` ▸ "A Boolean value that Indicates whether the capture session configures the app’s audio session to mix with others." ✅
- **S52** 同文件 `:299` ▸ "[`var configuresApplicationAudioSessionForBluetoothHighQualityRecording: Bool`](…)"; `:301` ▸ "A Boolean value that indicates whether the capture session configures the app’s audio session for bluetooth high-quality recording." ✅
- **S53** 同文件 `:245` ▸ "[`var isInterrupted: Bool`](…)"; `:247` ▸ "A Boolean value that indicates whether the capture session is in an interrupted state."；`:257` wasInterruptedNotification、`:261` interruptionEndedNotification、`:265` runtimeErrorNotification ✅
- **S54** 同文件 `:61` ▸ "> The ``doc://com.apple.avfoundation/documentation/AVFoundation/AVCaptureSession/startRunning()`` method is a blocking call which can take some time, therefore start the session on a serial dispatch queue so that you don’t block the main queue (which keeps the UI responsive)." ✅
- **S55** 同文件 `:44` ▸ "guard let audioDevice = AVCaptureDevice.default(for: .audio) else { return }" ✅
- **S56** `Y-AVFoundation-AVCaptureDevice.md:29` ▸ "An object that represents a hardware or virtual capture device like a camera or microphone." ✅
- **S57** 同文件 `:113` ▸ "The type of device, such as a built-in microphone or wide-angle camera." ✅
- **S58** 同文件 `:81` ▸ "[`class func requestAccess(for: AVMediaType, completionHandler: (Bool) -> Void)`](…)"; `:83` ▸ "Requests the user’s permission to allow the app to capture media of a particular type."；`:85` authorizationStatus(for:) ✅
- **S59** 同文件 `:315` ▸ "Configure the state of system video effects like Center Stage, and inspect enhancements the system applies to microphone audio." ✅
- **S60** `ios-fetch\avspeech2.md:97` ▸ "[`var usesApplicationAudioSession: Bool`](…)"; `:99` ▸ "A Boolean value that specifies whether the app manages the audio session." ✅
- **S61** 同文件 `:105` ▸ "[`var outputChannels: [AVAudioSessionChannelDescription]?`](…)"; `:107` ▸ "An array of audio session channels to route generated speech." ✅
- **S62** 同文件 `:49` ▸ "> The system doesn’t automatically retain the speech synthesizer, so you need to manually retain it until speech concludes." ✅
- **S63** `ios-fetch\sensoryfeedback.md:4` ▸ `"iOS: 17.0.0 -",` ✅

### G-3 复核结论

| 检查项 | 结果 |
|---|---|
| A1 条数 | 40（要求 ≥10）✅ |
| A2 条数 | 63（要求 ≥10）✅ |
| 每条是否都有 `文件:行号` + 英文原句 | 是 ✅ |
| 复核中发现需修正的引用 | **3 条已在复核中就地校正行号定位，非内容或原句错误**：H17（英文描述句实际在 `hapticengine.md:157`，属性行在 `:155`）、S50（定义句实际在 `AVCaptureSession.md:289`/`:293`，属性行在 `:287`/`:291`）、H30（changelog 表头行是 `:225`、分隔行 `:226`，首次误记 `:226` 为表头，已改）。三条均已在上表内标注实际分布，原句未改。 |
| **撤回条数** | **0**（无编造行号、无编造数值、无未标出处的数字） |
| 「官方未给数值」是否显式标注 | C1 10 项、C2 10 项，全部显式标注 ✅ |
| 4 个高危项是否有真实命令输出 | `AVAudioSession`✅（D2-1）、`NSSpeechRecognitionUsageDescription`✅（D2-2）、`requiresOnDeviceRecognition`✅（D2-3）、`SpeechAnalyzer`/`UISensoryFeedbackGenerator`✅（D2-7、D2-9） |
| 全文数字是否全部有出处 | 是。文中出现的每个数字（0–1、−1–1、1 分钟、iPhone 8、iOS 26.0.0、iOS 17.0.0、iOS 13.0.0、iOS 10.0.0、64 kbps、4 个生成器子类、4 种 stopped reason、5 种 impact 风格、3 种 notification、5 个 category）均有对应 `文件:行号`。 |
