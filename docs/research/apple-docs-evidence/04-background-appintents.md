# 证据档案 04 · BackgroundTasks ＋ AppIntents / Shortcuts / Spotlight

> 取证时间：2026-10-25　资料源：`D:\AP\AP7000\ai-workspace\stackchan-research\ios-docs\`、`...\hig-md\`、`...\ios-fetch\`（三个目录的文件数由本次实测计数得：166 / 62 / 44，非文档引用）　只读未联网
>
> 取证方法：全部结论只来自本机缓存文本，行号由 `read`（带 offset/limit）或 `grep` 实际读到的行确认；交付前又用一次集中脚本逐行回读每个待引用行（见 G 节）。
> 等级定义：**T1** = 官方明文写出的数值/事实（含明文版本号起止）；**T2** = 官方只给规则/语义、不给数值。
> 关于「官方未给数值」：凡是官方只写定性词（如 "minutes"、"short task"）而没有写出秒/分钟数字的，本档案一律记为「官方未给数值」，不换算、不推测、不补数字。

---

## 第一部分 BackgroundTasks

### A1. 事实表

| ID | 事实 | 出处（文件:行号） | 等级 | 官方英文原句(≤1句) |
|---|---|---|---|---|
| A1-01 | Background Tasks 框架的定位：让内容保持最新，并能运行「需要数分钟完成」的任务；更长的任务可利用外部供电、网络、GPU | ios-docs\BackgroundTasks.md:32 | T2（"minutes" 是定性词，非数值） | "Use this framework to keep your app content up to date and run tasks requiring minutes to complete even if your app is in the background." |
| A1-02 | 后台运行的必要前提：为框架提供的任务注册 launch handler 并按需调度 | ios-docs\BackgroundTasks.md:34 | T2 | "To launch your app in the background and perform necessary work, register launch handlers for framework-provided tasks and schedule the tasks as needed." |
| A1-03 | 第三类用途：前台发起的关键任务，若用户提前把 app 切到后台，可在后台继续完成 | ios-docs\BackgroundTasks.md:36 | T2 | "Your app can also use a framework-provided task to execute critical jobs in the foreground and complete them in the background if a person backgrounds your app before the job completes." |
| A1-04 | `BGAppRefreshTask` = 短任务，典型用途是刷新内容 | ios-docs\BackgroundTasks.md:70 | T2 | "An object representing a short task typically used to refresh content that’s run while the app is in the background." |
| A1-05 | `BGProcessingTask` = 耗时的处理任务 | ios-docs\BackgroundTasks.md:66 | T2 | "A time-consuming processing task that runs while the app is in the background." |
| A1-06 | `BGContinuedProcessingTask` = 前台开始、可按需在后台继续 | ios-docs\BackgroundTasks.md:84 | T2 | "A task that starts in the foreground and can continue running in the background as needed." |
| A1-07 | 还有 `BGHealthResearchTask` 这一类（健康研究数据处理） | ios-docs\BackgroundTasks.md:74 | T2 | "A time-consuming, necessary processing task that runs while the app is in the background to prepare data essential to a health research study." |
| A1-08 | `BGProcessingTaskRequest` = 请求后台启动执行「可花数分钟」的处理任务 | ios-docs\BackgroundTasks.md:92 | T2（still "minutes"，无数值） | "A request to launch your app in the background to execute a processing task that can take minutes to complete." |
| A1-09 | `BGAppRefreshTaskRequest` = 请求后台执行一次短刷新任务 | ios-docs\BackgroundTasks.md:96 | T2 | "A request to launch your app in the background to execute a short refresh task." |
| A1-10 | `BGContinuedProcessingTaskRequest` = 用户切后台后系统仍继续处理的工作负载请求 | ios-docs\BackgroundTasks.md:108 | T2 | "A request for a workload that the system continues processing even if a person backgrounds the app." |
| A1-11 | continued-processing 存在 GPU 相关的专属授权（entitlement）标识符 | ios-docs\BackgroundTasks.md:86 | T2 | "com.apple.developer.background-tasks.continued-processing.gpu"（该行为 doc:// entitlement 链接，缓存内无该 entitlement 正文） |
| A1-12 | `BGTaskScheduler.register(forTaskWithIdentifier:using:launchHandler:)` 语义：为 identifier 注册 launch handler，在指定队列上执行 | ios-docs\Y-BackgroundTasks-BGTaskScheduler.md:59 | T2 | "Register a launch handler for the task with the associated identifier that’s executed on the specified queue." |
| A1-13 | `submit(_:)` 只会提交「此前已注册」的任务请求 | ios-docs\Y-BackgroundTasks-BGTaskScheduler.md:61（签名）、:63（描述） | T2 | "Submit a previously registered background task for execution." |
| A1-14 | `getPendingTaskRequests` 可查「尚未执行」的已调度请求 → 说明调度不等于保证执行 | ios-docs\Y-BackgroundTasks-BGTaskScheduler.md:77（签名）、:79（描述） | T2 | "Request a list of unexecuted scheduled task requests." |
| A1-15 | `UIApplication.backgroundTimeRemaining` 的语义是「剩余可后台运行的最长时间」，但页面不给具体秒数 | ios-docs\UIKit-UIApplication.md:187（符号）、:189（描述） | T2（无数值） | "The maximum amount of time remaining for the app to run in the background." |
| A1-16 | `beginBackgroundTask(withName:expirationHandler:)` 语义：标记一个「进入后台后应继续」的任务，可自定义名字 | ios-docs\UIKit-UIApplication.md:171（符号）、:173（描述） | T2 | "Marks the start of a task with a custom name that should continue if the app enters the background." |
| A1-17 | `backgroundFetchIntervalMinimum` 只描述为「系统支持的最小 fetch 间隔」，缓存不给具体值 | ios-docs\UIKit-UIApplication.md:193（符号）、:195（描述） | T2（无数值） | "The smallest fetch interval supported by the system." |
| A1-18 | **后台执行的 30 秒**：任务在后台跑时，系统传统上最多给 30 秒 | ios-docs\Y-AppIntents-LongRunningIntent.md:41 | T1（明文数值 30 秒） | "When a task runs in the background, the system traditionally gives it up to 30 seconds to finish its task." |
| A1-19 | 同一条规则的分平台表述：iOS/iPadOS/tvOS/visionOS/watchOS 给 30 秒；macOS 后台任务无时限 | ios-docs\Y-AppIntents-LongRunningIntent.md:92–93 | T1（明文数值 30 秒＋平台差异） | "In iOS, iPadOS, tvOS, visionOS, and watchOS, the system gives tasks 30 seconds to run in the background unless you use the methods of this protocol to extend that runtime." |
| A1-20 | SwiftUI 侧的场景级后台入口：`.backgroundTask(_:action:)`，在系统提供后台任务时运行 action | ios-docs\SwiftUI-Scene.md:152（签名）、:154（描述） | T2 | "Runs the specified action when the system provides a background task." |
| A1-21 | iOS 26 起：先起 Live Activity 的 app，在后台可沿用前台的部分特权（例：Core Bluetooth 扫描规则放宽） | ios-docs\X-CoreBluetooth.md:34（结论）、:35–36（展开） | T1（明文版本事实 iOS 26） | "In iOS 26 and later, your app can continue certain activities in the background if the app starts a Live Activity before it goes to the background." |
| A1-22 | HIG：音频 `Playback` 类别明确「可在后台播放」——后台场景之一（音频）的官方依据 | hig-md\playing-audio.md:42 | T2 | "Can play in the background." |
| A1-23 | HIG：大体积资源下载建议交给 BackgroundAssets 框架在安装后/更新后等时机进行 | hig-md\loading.md:30 | T2 | "Consider using the BackgroundAssets framework to schedule asset downloads — like game level packs, 3D character models, and textures — to occur immediately after installation, during updates, or at other nondisruptive times." |

### B1. 必答问题逐条回答（第 1–3 问）

**Q1. `BGTaskScheduler` 能注册哪几类任务、各自适合什么场景、官方限制原文**

缓存里能确认「框架提供哪些任务类型」的唯一权威页是 `BackgroundTasks.md` 的 Topics 目录，它把任务分成四类（外加一类健康研究变体），并给出每类一句话定位：

1. **短刷新：`BGAppRefreshTask`** —— 用途=刷新内容，官方定性为 "short task"（ios-docs\BackgroundTasks.md:70）；对应请求 `BGAppRefreshTaskRequest`（:96）。
2. **耗时处理：`BGProcessingTask`** —— 用途=耗时处理（ios-docs\BackgroundTasks.md:66）；对应请求 `BGProcessingTaskRequest`，官方明确写「可花数分钟完成」（:92），并补充更长任务可利用外部供电/网络/GPU（:32）。
3. **前台发起可延续：`BGContinuedProcessingTask`** —— 官方限定它是「从**前台**开始、可在后台按需继续」（ios-docs\BackgroundTasks.md:84），请求为 `BGContinuedProcessingTaskRequest`（:108）；相关 GPU entitlement 标识符见 :86。
4. **健康研究：`BGHealthResearchTask`** —— 为健康研究准备数据（ios-docs\BackgroundTasks.md:74）；对应 `BGHealthResearchTaskRequest`（:102–104）。
5. **通用机制**：注册 launch handler ＋ 调度（ios-docs\BackgroundTasks.md:34）；API 面为 `register(...)`（ios-docs\Y-BackgroundTasks-BGTaskScheduler.md:57–59）、`submit(_:)`（:61–63）、`cancel(taskRequestWithIdentifier:)`（:67–69）、`cancelAllTaskRequests()`（:71–73）、`getPendingTaskRequests(...)`（:77–79）。

关于「iOS 26?」：`BGContinuedProcessingTask` / `BGContinuedProcessingTaskRequest` 在缓存里**只有目录级描述**，`BackgroundTasks.md` 顶部 availability 元数据写的是框架级 `iOS: 13.0.0 -`（ios-docs\BackgroundTasks.md:4），**缓存内没有任何一行把这两个类标注为 iOS 26 新增**。因此本档案**不写**「iOS 26 新增 continued processing」这一断言（见 D1-4）。

**Q2. 限制是什么（注册时机 / Info.plist / 调度语义 / 时长数值）**

- **「必须在 App 启动完成前（`didFinishLaunchingWithOptions`）注册」——缓存中找不到原文**。我对整个 `ios-docs` 目录 grep `didFinishLaunching`、`permitted identifier`、`BGTaskSchedulerPermittedIdentifiers`，命中数为 0（仅 `repos\` 下的第三方示例代码出现 `didFinishLaunchingWithOptions`，非 Apple 文档）。缓存里最接近的只有「注册 launch handler」这一句（ios-docs\Y-BackgroundTasks-BGTaskScheduler.md:59），它**不含任何时序要求**。→ 该限制归入 D1-1，本档案不作断言。
- **`BGTaskSchedulerPermittedIdentifiers`（Info.plist）——同样 0 命中**（D1-2）。缓存里唯一相关的 Info.plist 用法是别的框架（Live Activities / Bluetooth 用途描述键），与本主题无关。
- **「系统调度是尽力而为、非定时」——缓存没有正面原文**。可以旁证的是：`submit` 只是「提交已注册任务供执行」（:63），`getPendingTaskRequests` 返回的是「未执行的已调度请求」（:79），两者合起来说明「已调度 ≠ 已执行」，但官方未在缓存页里写出 "best effort" / "not guaranteed" 字样。→ 记为「规则不完整，见 D1-3」，我只写可证的弱结论。
- **每次运行时长有无官方数值**：在 `BGTaskScheduler` / `BGAppRefreshTask` / `BGProcessingTask` 相关页里，**官方未给数值**（只有 "short task"、"time-consuming"、"minutes to complete" 这类定性词：ios-docs\BackgroundTasks.md:70 / :66 / :92）。缓存里唯一带数字的后台时长是 App Intents 页的 **30 秒**（ios-docs\Y-AppIntents-LongRunningIntent.md:41、:92–93），它描述的是「后台任务的通用默认额度」，并未挂在 BGTaskScheduler 的某个类名下。详见 C1。

**Q3. `beginBackgroundTask` 的限制**

- 语义：`beginBackgroundTask(withName:expirationHandler:)` 标记一个「若 app 进入后台应继续」的任务，并可给它一个自定义名字（ios-docs\UIKit-UIApplication.md:171 符号、:173 描述）；不带名字的 `beginBackgroundTask(expirationHandler:)` 同一句表述（:175 符号、:177 描述："Marks the start of a task that should continue if the app enters the background."）。
- 收尾：必须用 `endBackgroundTask(_:)` 结束，官方描述为「标记某个长时后台任务的结束」（ios-docs\UIKit-UIApplication.md:179 符号、:181 描述）。
- 剩余时间：`backgroundTimeRemaining` 的官方语义是「app 在后台还能运行的最大剩余时间」（ios-docs\UIKit-UIApplication.md:187 符号、:189 描述）。
- **时长数值：官方在缓存中未给数值。** `backgroundTimeRemaining` 的页面没有给出任何秒数（不是 30 秒、也不是 180 秒之类的书写），只有上面那句定性描述。唯一明文数字仍是 App Intents 页的 30 秒（ios-docs\Y-AppIntents-LongRunningIntent.md:41），且该页明确 macOS 后台任务无时限（:92）。工程含义：**`backgroundTimeRemaining` 必须在运行时读取，不能当成编译期常量或文档常量**，因为官方文档未承诺任何固定值。
- 能力边界（旁证）：`backgroundRefreshStatus` 表示 app 能否在后台刷新（ios-docs\UIKit-UIApplication.md:159 符号、:161 描述），说明后台刷新本身是受系统状态约束的开关；音频另有独立通道（hig-md\playing-audio.md:42）。

### C1. 官方未给数值清单（BackgroundTasks）

> **核心结论：就「后台任务单次运行时长」，`BGTaskScheduler` 一侧官方未给数值。** 缓存中不存在任何「BGAppRefreshTask 跑 X 秒」「BGProcessingTask 跑 Y 分钟」的官方数字；官方只给 "short task"、"time-consuming"、"minutes to complete" 这类定性表述。全缓存唯一明文的后台时长数字是 **30 秒**，出自 App Intents 的 `LongRunningIntent` 页，用于说明「后台任务默认额度不够时如何延长」，**不能**当成 BGTaskScheduler 各任务类的官方时长承诺。

| 项目 | 结论 | 查过的页（行号） |
|---|---|---|
| BGAppRefreshTask 单次运行时长 | **官方未给数值**（只有 "short task"） | ios-docs\BackgroundTasks.md:70、:96；ios-docs\Y-BackgroundTasks-BGTaskScheduler.md 全文（123 行，无时长数字） |
| BGProcessingTask 单次运行时长 | **官方未给数值**（只有 "time-consuming"／"can take minutes"） | ios-docs\BackgroundTasks.md:66、:92、:32 |
| BGContinuedProcessingTask 单次运行时长 | **官方未给数值**（只有 "as needed"，且该类正文页未缓存） | ios-docs\BackgroundTasks.md:84、:108 |
| `backgroundTimeRemaining` 的具体秒数 | **官方未给数值** | ios-docs\UIKit-UIApplication.md:187–189 |
| `beginBackgroundTask` 的总时长 | **官方未给数值** | ios-docs\UIKit-UIApplication.md:171–181 |
| `backgroundFetchIntervalMinimum` 的实际值 | **官方未给数值**（只写"系统支持的最小间隔"） | ios-docs\UIKit-UIApplication.md:193–195 |
| 后台任务执行默认额度 | **官方给了数值：30 秒**（唯一明文数字），macOS 除外（无时限） | ios-docs\Y-AppIntents-LongRunningIntent.md:41、:92–93 |
| 注册时机 / Info.plist 键名 / best-effort 表述 | **缓存未覆盖，故无法引用**（见 D1） | grep 全 ios-docs：`didFinishLaunching`=0、`permitted identifier`=0、`BGTaskSchedulerPermittedIdentifiers`=0 |

### D1. 缓存未覆盖项（BackgroundTasks）

1. **D1-1 注册时序原文缺失**：`application(_:didFinishLaunchingWithOptions:)` 内必须完成 `register` 的说法，在 `ios-docs` 内 grep `didFinishLaunching` 命中 0 行（仅 `repos\FunASR`、`repos\sherpa-onnx` 等第三方示例代码出现该方法名，属代码而非 Apple 文档）。→ 无法给行号，故不写入 A1/B1 作为官方断言。
2. **D1-2 Info.plist 键缺失**：`BGTaskSchedulerPermittedIdentifiers` grep 命中 0；`permitted identifier` 命中 0。缓存里存在的 Info.plist 键均为其他主题（如 `NSSupportsLiveActivities`、`NSBluetoothAlwaysUsageDescription`）。
3. **D1-3 调度语义原文不足**：缓存未收录 `BGTaskScheduler` 关于「系统自行决定何时运行、不保证按时执行」的明文段落；只能由 `submit`（Y-BackgroundTasks-BGTaskScheduler.md:63）与 `getPendingTaskRequests`（:79）间接推断。
4. **D1-4 类级正文缺失**：`BGAppRefreshTask`、`BGProcessingTask`、`BGContinuedProcessingTask`、`BGHealthResearchTask` 及其 Request 类的独立符号页**均不在缓存**（`ios-docs` 内文件名匹配 `BGTask|BGContinued|BGAppRefresh|BGProcessing` 的只有 `Y-BackgroundTasks-BGTaskScheduler.md` 一个），所以：类级 availability、`earliestBeginDate`、`requiresNetworkConnectivity`、`requiresExternalPower`、GPU 资源请求等细节**全部无法取证**；也无法确认 `BGContinuedProcessingTaskRequest` 是否为 iOS 26 新增。
5. **D1-5 教程页缺失**：`Refreshing and Maintaining Your App Using Background Tasks`、`Choosing Background Strategies for Your App`、`Performing long-running tasks on iOS and iPadOS`、`Starting and Terminating Tasks During Development` 在缓存中只有目录链接（ios-docs\BackgroundTasks.md:56、:60、:78、:112），正文未缓存——而「每类任务适合什么场景」的官方完整答案正是这些页。
6. **D1-6 独立符号页缺失**：`beginBackgroundTask(expirationHandler:)`、`beginBackgroundTask(withName:expirationHandler:)`、`backgroundTimeRemaining`、`backgroundRefreshStatus` 在缓存中都只有 `UIApplication` 索引页里的一行符号＋一行描述（ios-docs\UIKit-UIApplication.md:50、:171–189），没有各自的详述页与 Discussion 段落。
7. **D1-7 HIG 覆盖很薄**：`hig-md\privacy.md` 全文（230 行）grep `background` 仅命中图片替代文本与「背景色」（:141、:153），**无任何后台执行相关规范**；`hig-md\launching.md`（91 行）grep `background|refresh|terminate` 命中 0 条后台执行内容，只有启动速度建议（:24）与启动屏规范。HIG 中真正与「后台」相关的只有音频类别（playing-audio.md:36、:42–44）、后台下载（loading.md:30）、指示器文案（progress-indicators.md:99）。

### E1. 对本项目 App 的落地含义（BackgroundTasks）

1. **能用什么就写什么，别指望「定时」**：官方对后台只承诺「在系统认为合适时有机会运行」（弱证据见 A1-13/A1-14），且 `submit` 前必须先 `register`（A1-12 → ios-docs\Y-BackgroundTasks-BGTaskScheduler.md:59、:63）。因此本项目凡是「陪伴对话、定时提醒、状态轮询」类需求，**不能**设计成依赖 BGTaskScheduler 准点触发。
2. **长耗时本地计算（语音转写、模型预处理、日志归档）走 `BGProcessingTaskRequest`**：官方明确它是"can take minutes to complete"且长任务可用外部供电/网络/GPU（A1-08、A1-01）。但**时长官方未给数值**（C1），工程上必须：任务设计成可中断可续跑、启动时用 `backgroundTimeRemaining` 动态判断余量（A1-15），不要写死任何秒数常量。
3. **轻量保鲜（例如每日摘要、房间状态快照）走 `BGAppRefreshTaskRequest`**：官方定位就是短刷新（A1-04、A1-09），不要塞重计算。
4. **「用户按了就切后台也要跑完」的交互任务**：官方有两个通道 —— 旧通道 `beginBackgroundTask` ＋ `endBackgroundTask`（A1-16 ＋ UIKit-UIApplication.md:181），新通道 `BGContinuedProcessingTask`（必须从前台开始，A1-06、A1-10）。二者都把「已注册/已提交」与「实际获得时间」分开，务必实现 expirationHandler 式收尾（A1-16 的签名即含 `expirationHandler`）。
5. **音频陪伴场景有独立且更稳的通道**：HIG 明确 `Playback` 类别可在后台播放（A1-22），这类场景不要拿去和后台上传/后台计算抢预算。
6. **iOS 26 的 Live Activity 换后台特权只对特定活动成立**：官方只举了 Core Bluetooth 的例子（A1-21），**不可外推**成「起个 Live Activity 就能长期后台跑任意代码」。
7. **SwiftUI 项目优先用场景级 `.backgroundTask`**（A1-20），不要自己在 AppDelegate 里手搓注册逻辑——缓存中也没有任何官方原文支持「必须在 didFinishLaunching 注册」这一硬约束（D1-1），所以不要把该说法写进本项目文档当作官方要求。

---

## 第二部分 AppIntents / Shortcuts / Spotlight

### A2. 事实表

| ID | 事实 | 出处（文件:行号） | 等级 | 官方英文原句(≤1句) |
|---|---|---|---|---|
| A2-01 | 框架定位：让内容与动作可被 Apple Intelligence 发现，并支持 Siri/Spotlight/Shortcuts/Widgets 等系统体验 | ios-docs\appintents.md:30 | T2 | "Make content and actions discoverable by Apple Intelligence and support system experiences like Siri, Spotlight, Shortcuts, and widgets." |
| A2-02 | 系统入口之一：Siri | ios-docs\appintents.md:44 | T2 | "People can interact with your app’s content through Siri." |
| A2-03 | 系统入口之一：Spotlight（搜索结果直接跳到你的数据） | ios-docs\appintents.md:45 | T2 | "Spotlight helps people navigate to your data directly from search results." |
| A2-04 | 系统入口之一：Shortcuts app（把 app 动作编进工作流） | ios-docs\appintents.md:46 | T2 | "The Shortcuts app helps people configure workflows that include your app’s actions." |
| A2-05 | 系统入口之一：Apple Pencil / iPhone Action button | ios-docs\appintents.md:47 | T2 | "People can configure Apple Pencil or the Action button on iPhone to perform your app’s actions when pressed." |
| A2-06 | 系统入口之一：Widgets、controls、Live Activities | ios-docs\appintents.md:48 | T2 | "Widgets, controls, and Live Activities can use your app’s actions to perform relevant tasks." |
| A2-07 | 系统入口之一：自定义 Focus 模式并响应 Focus 变化 | ios-docs\appintents.md:49 | T2 | "You can define custom Focus modes, and respond to Focus changes." |
| A2-08 | 「什么值得做成系统级动作」的判断标准①：设计时找出「用户可能想在你的 app 之外执行」的动作 | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:44 | T2 | "As you design your app, identify actions that people might want to perform from outside your app." |
| A2-09 | 判断标准②：实体只为「用户看得见、会操作」的那一小部分数据建模 | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:89–90 | T2 | "You typically create entities for only a subset of your app’s actual data, focusing on the types that people see and manipulate from your interface." |
| A2-10 | 限制：必须前台运行、会自动拉起 app 的意图（如 `OpenIntent`）的代码只能放在 app 内，不要放扩展 | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:168–170 | T2 | "Place the code for these app intents only in your app." |
| A2-11 | 判断标准③：把 entity 挂到当前可见的界面内容上，Siri 才能用「this song」这类指代 | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:186 | T2 | "If someone asks Siri to “play this song”, Siri can use that contextual information to play the song without asking for more information." |
| A2-12 | 深化集成清单：Apple Intelligence/Siri AI、Spotlight、App Shortcuts、Widgets+Live Activities+Controls、Action/Side button、Focus、Visual intelligence | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:213、:215、:217、:219、:220、:221 | T2 | "Classify your app’s content, and make that information available to Visual intelligence using app intents."（:221） |
| A2-13 | 采纳后用户可获得的系统体验清单（Shortcuts / Spotlight / visual intelligence / Action button / Siri Suggestions / widget…） | ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:30–40 | T2 | "Search for a landmark, photo, or the “Find Closest” App Shortcut in Spotlight."（:33） |
| A2-14 | 实体设计规则：只暴露系统需要的部分，并且**必须**提供 `typeDisplayRepresentation` 与 `displayRepresentation` | ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:79–81 | T2 | "An app entity exposes only the parts of your stored model object that the system needs."（:79） |
| A2-15 | 执行时长：意图默认「只有很短时间」完成工作；超时才用 `LongRunningIntent` 延长 | ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:363–365 | T2 | "By default, intents have only a short time to finish their work."（:363） |
| A2-16 | Spotlight 捐赠的 App Intents 写法：`IndexedEntity` ＋ `@ComputedProperty(indexingKey:)`，再 `CSSearchableIndex.default().indexAppEntities(...)` | ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:494、:528 | T2 | "try await CSSearchableIndex.default().indexAppEntities(landmarkEntities)"（:528） |
| A2-17 | 可见性开关：`isDiscoverable` 控制系统功能能否发现该 intent | ios-docs\appintent.md:139（符号）、:141（描述） | T2 | "A Boolean value that indicates whether system features can discover this app intent." |
| A2-18 | `parameterSummary` 的官方用途：Shortcuts app 用它为该 intent 生成 shortcut | ios-docs\appintent.md:245（符号）、:247（描述） | T2 | "The parameter summary the Shortcuts app uses to generate shortcuts for this intent." |
| A2-19 | **实体尺寸硬上限：10 MB**（含全部子属性与取值），超限抛异常并可能崩溃 | ios-docs\appentity.md:97–98 | T1（明文数值 10 MB） | "`AppEntity` instances have a total size limit of 10 MB, including all child properties and their values." |
| A2-20 | `displayRepresentation` 的形态：title / subtitle / image，用于向人展示该实体 | ios-docs\appentity.md:62–70 | T2 | "Information on how to display the entity to people — for example, a string like the trail name."（:63） |
| A2-21 | 类型规则：不要在同一个类型上同时采纳 `AppEntity` 与 `AppEnum`（动态数据 vs 静态值集） | ios-docs\appenum.md:85–86 | T2 | "Don’t adopt the AppEntity and AppEnum protocols in the same type." |
| A2-22 | 隐私：Apple 可能抽取 App Shortcuts 的**匿名化**数据（本地化短语、display representation、intent 标题/描述）用于训练模型 | ios-docs\AppIntents-app-shortcuts.md:37–39；同文重复于 ios-docs\appshortcutsprovider.md:40–43 | T2 | "Apple may extract anonymized App Shortcuts data such as localized phrases, display representation values, and the title and description of related intents." |
| A2-23 | 捐赠规则：只对「用户在你的 app 界面内的直接交互」做捐赠，不要为 Siri/Shortcuts 发起的交互捐赠 | ios-docs\AppIntents-donations-and-discovery.md:19–23 | T2 | "Restrict your donations to direct interactions with your app’s interface, and not to interactions started by Siri or the Shortcuts app."（:22–23） |
| A2-24 | Apple Intelligence 前置条件①：把实体索引进 Spotlight，语义搜索才能「模糊描述也找得到」 | ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:20 | T2 | "Apple Intelligence uses the semantic search capabilities of Spotlight to find your app’s content, even when someone describes it vaguely." |
| A2-25 | 隐私边界：屏上内容「属于你的 app、本身是私有的」，需显式把实体关联到视图才产生上下文 | ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:26 | T2 | "People use Siri AI to interact with content that’s visible onscreen, but that content is private to your app." |
| A2-26 | Spotlight 索引隐私承诺：索引留在设备上、属于设备所有者私有，不与 Apple 共享、不跨设备同步 | ios-docs\CoreSpotlight.md:44–46 | T2 | "The indexes you create using Core Spotlight remain on device, and are private to the owner of the device." |
| A2-27 | 生产环境应使用自定义 `CSSearchableIndex`（支持数据保护/加密），默认索引只用于测试与原型 | ios-docs\CoreSpotlight-CSSearchableIndex.md:44–50 | T2 | "Use the default index only during testing or prototyping of your features."（:50） |
| A2-28 | 并发与批次约束：一个 index 同时只能单线程/单任务修改；每个新批次必须等上一批次 `endBatch`/`endIndexBatch` 完成后才开始 | ios-docs\CoreSpotlight-CSSearchableIndex.md:52–58 | T2 | "Modify a `CSSearchableIndex` object from only one thread or task at a time, and modify it only from your signed app or app extension."（:52–53） |
| A2-29 | Core Spotlight 最少要填的属性：`title`、`displayName`、`contentType`；索引磁盘文件再加 `contentURL` | ios-docs\CoreSpotlight-CSSearchableItem.md:50–53 | T2 | "For the metadata, you typically want to provide values for the title, displayName, and contentType attributes at a minimum."（:50–52） |
| A2-30 | `domainIdentifier` 是**可选**，表示域/归属，不是必填 | ios-docs\CoreSpotlight-CSSearchableItem.md:98（符号）、:100（描述） | T2 | "An optional identifier that represents the domain or owner of the item." |
| A2-31 | 可见性开关：`hideInSpotlight` 可让 Spotlight 不把该实体放进索引 | ios-docs\X-AppIntents-IndexedEntity.md:58（符号）、:60–61（描述） | T2 | "A boolean value that indicates whether Spotlight prevents the inclusion of the entity in the index." |
| A2-32 | `IndexedEntity` 的价值：进 Spotlight 既让 Apple Intelligence 发现，也是「搜索结果直接启动 app 到具体条目」的第一步 | ios-docs\X-AppIntents-IndexedEntity.md:36–40 | T2 | "Adding entities to Spotlight makes them discoverable by Apple Intelligence, and also serves as the first step in letting Spotlight launch your app and display items that appear in search results."（:36–39） |
| A2-33 | 新增（官方标注 June 2026）：schema 化、`SyncableEntity`、`OwnershipProvidingEntity`（破坏性操作前确认）、`RelevantEntities`、`IntentValueRepresentation` | ios-docs\Updates-AppIntents.md:24–28 | T2 | "Prompt for confirmation before destructive or sensitive actions on shared or publicly accessible entities by adopting OwnershipProvidingEntity and returning an EntityOwnership value."（:26） |
| A2-34 | 新增（June 2026）：`RunSystemShortcutIntent`、`LongRunningIntent`＋`performBackgroundTask`、`CancellableIntent`、`UndoableIntent`、`supportedModes`、`allowedExecutionTargets` | ios-docs\Updates-AppIntents.md:32–37 | T2 | "Extend an app intent’s background runtime by adopting LongRunningIntent and calling performBackgroundTask(options:operation:) with a LongRunningTaskOptions value, reporting progress as the task runs."（:33） |
| A2-35 | 新增（June 2026）：`EntityCollection`（只传标识符）、`@UnionValue`、`IndexedEntityQuery`（按标识符从 Spotlight 取回实体） | ios-docs\Updates-AppIntents.md:41–43 | T2 | "Have the system retrieve indexed entities by identifier from the Spotlight index by adopting IndexedEntityQuery."（:43） |
| A2-36 | Core Spotlight 新增（June 2026）：索引内容可给 Foundation models 用（`SpotlightSearchTool`）；可用 `CSSearchableIndexDescription` 在重建索引时引用索引 | ios-docs\U-Updates-CoreSpotlight.md:26–27 | T2 | "Make your app’s indexed content available to Foundation models using SpotlightSearchTool."（:26） |
| A2-37 | `SyncableEntity`：声明实体 ID 跨设备稳定，Siri 才能把对话延续到另一台设备 | ios-docs\Y-AppIntents-SyncableEntity.md:38–40 | T2 | "The presence of this protocol tells the system that it can refer to your entity consistently across devices."（:39） |
| A2-38 | 使用限制：`RunSystemShortcutIntent` 只能用于 widget 里的 `Button(_:intent:)`，其他上下文无功能 | ios-docs\Y-AppIntents-RunSystemShortcutIntent.md:34–36 | T2 | "The run system shortcut intent doesn’t provide functionality in other contexts."（:36） |
| A2-39 | `LiveActivityIntent`：一般需前台才能起 Live Activity，但用该协议可在不打开 app 的情况下由系统起活动 | ios-docs\Y-AppIntents-LiveActivityIntent.md:35–38 | T2 | "In general, your app needs to be in the foreground to start a Live Activity."（:36） |
| A2-40 | 迁移：`ForegroundContinuableIntent` 已废弃，改用 `supportedModes` 里的 `.foreground(.dynamic)` | ios-docs\AppIntents-ForegroundContinuableIntent.md:44 | T2 | "This protocol is deprecated, please include `.foreground(.dynamic)` in the supportedModes of your app intent instead." |
| A2-41 | `SiriTipView` 的硬约束：intent 必须已被某个 `AppShortcut` 使用，否则显示空视图 | ios-docs\X-AppIntents-SiriTipView.md:48 | T2 | "Note that you must use the AppIntent in an AppShortcut. Otherwise this will display an empty view." |
| A2-42 | 展示不确定性：用 Siri AI 触发 intent 时，系统**可能不显示**你返回的 `IntentDialog` | ios-docs\AppIntents-IntentDialog.md:39–40 | T2 | "When someone performs an action with Siri AI that invokes your app intent, the system might not display the IntentDialog you return as an intent result." |
| A2-43 | 缓存内 JSON 索引与 md 正文同源（摘要句一致），无额外数值信息 | ios-docs\JSON-appintents.json:1（单行 JSON） | T2 | "Make content and actions discoverable by Apple Intelligence and support system experiences like Siri, Spotlight, Shortcuts, and widgets." |

### B2. 必答问题逐条回答（第 4–8 问）

**Q4. 「什么样的操作值得做成系统级动作」——官方判断标准（逐条给行号）**

1. **「用户可能想在你的 app 之外做」才算** —— ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:44："identify actions that people might want to perform from outside your app."
2. **一个意图只做一件独特的事，用参数区分变体**（不要为「播放歌曲」「播放专辑」各建一个意图）—— 同上页 :46–49："Make sure each app intent performs a unique action within your app, and use its parameters to configure it for different types of data."
3. **优先用系统预定义 schema 覆盖常见动作** —— 同上页 :51–58："build app intents for common actions from the built-in domains whenever possible."
4. **意图必须齐备的最小行为集**（perform / 返回结果或错误 / 声明参数 / 提供本地化 title 等）—— 同上页 :66–71。
5. **实体只为「用户看得见、会操作」的数据建模** —— 同上页 :89–90："focusing on the types that people see and manipulate from your interface."
6. **实体只暴露系统需要的部分，且必须提供 typeDisplayRepresentation 与 displayRepresentation** —— ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:79–81。
7. **一次交互对应一次捐赠**：用户在 app 内做了什么，就捐一个匹配的意图（用于预测与建议）—— ios-docs\AppIntents-donations-and-discovery.md:19–21。
8. **可见内容要挂 entity**：屏上正在显示的对象应关联实体，Siri 才能接住「this…」这类指代 —— ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:183–187、ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:26。
9. **默认执行时间很短**，所以「长耗时」本身不是拒绝做成系统动作的理由，但要换协议（`LongRunningIntent`）—— ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:363–365。

**Q5. 隐私与可见性约束（逐条给行号）**

| 约束 | 结论 | 出处 |
|---|---|---|
| `isDiscoverable` | 控制「系统功能能否发现这个 intent」的布尔开关；非可发现即不进系统入口 | ios-docs\appintent.md:139、:141 |
| `static var parameterSummary` | 不是隐私开关，而是**可见性/可理解性**要件：Shortcuts app 用它生成 shortcut 文案 | ios-docs\appintent.md:245、:247；协议页 ios-docs\AppIntents-ParameterSummary.md:30 |
| `AppEntity.displayRepresentation` | 必须提供（与 `typeDisplayRepresentation` 并列为 required）；决定系统界面如何展示该实体 | ios-docs\appentity.md:62–70；ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:81 |
| 实体尺寸上限 | 10 MB（含子属性），超限系统抛异常、app 可能崩溃；用 `@DeferredProperty` 缩减 | ios-docs\appentity.md:97–100 |
| Spotlight 索引隐私 | 索引在设备上、属设备所有者私有、不与 Apple 共享、不跨设备同步 | ios-docs\CoreSpotlight.md:44–46 |
| 索引加密/数据保护 | 生产用自定义 index 才能带数据保护（加密）；默认 index 仅测试用 | ios-docs\CoreSpotlight-CSSearchableIndex.md:44–50 |
| 索引并发 | 只允许单线程/单任务修改，且只能来自已签名 app 或其扩展 | ios-docs\CoreSpotlight-CSSearchableIndex.md:52–54 |
| Spotlight 级别的隐藏开关 | `hideInSpotlight` 让实体不进索引 | ios-docs\X-AppIntents-IndexedEntity.md:58–61 |
| 索引内容不能被别人读走 | `CSSearchableItemAttributeSet` 只能单线程修改（并发访问行为未定义） | ios-docs\X-CoreSpotlight-CSSearchableItemAttributeSet.md:56–58 |
| Siri 上下文隐私 | 屏上内容「私有于你的 app」，必须显式关联实体才提供上下文 | ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:26 |
| Siri AI 输出可控性 | 系统**可能不显示**你返回的 dialog，因此不要用 dialog 承载必须被看到的信息 | ios-docs\AppIntents-IntentDialog.md:39–40 |
| App Shortcuts 数据外流（唯一明说的「会离开设备」项） | Apple 可能抽取**匿名化**的短语/展示值/标题描述用于模型训练 | ios-docs\AppIntents-app-shortcuts.md:37–39；ios-docs\appshortcutsprovider.md:40–43 |
| 捐赠边界 | 只捐「app 界面内的直接交互」，不要为 Siri/Shortcuts 触发的交互捐赠 | ios-docs\AppIntents-donations-and-discovery.md:22–23 |
| 破坏性/敏感操作确认 | 共享或公开可访问实体上的破坏性操作，应采纳 `OwnershipProvidingEntity` 先征求确认 | ios-docs\Updates-AppIntents.md:26 |
| 锁屏/控制中心控制的安全 | HIG 要求影响安全的控制（开门、启动汽车）需先解锁；开发者接口指向 `IntentAuthenticationPolicy` | hig-md\controls.md:94；ios-docs\appintent.md:109–115 |
| **`assistantOnly`** | **缓存未覆盖**：全 `ios-docs` grep `assistantOnly` 命中 0 行 → 无法取证，不作断言（D2-2） | — |
| iOS 26 / Apple Intelligence 相关约束 | 官方以「June 2026」月份段落给约束（schema 契约、跨设备稳定 ID、共享实体确认、捐赠＝行为线索），**未见以 "iOS 26" 为标题的隐私条款** | ios-docs\Updates-AppIntents.md:20–28；ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:18–28 |

**Q6. AppIntents 能被哪些系统入口调用（官方清单，每项给出处行号）**

| 系统入口 | 出处（文件:行号） | 关键原句 |
|---|---|---|
| Siri | ios-docs\appintents.md:44 | "People can interact with your app’s content through Siri." |
| Spotlight（含搜索结果直接跳转到内容） | ios-docs\appintents.md:45；ios-docs\AppIntents-spotlight.md:18–21 | "Spotlight helps people navigate to your data directly from search results." |
| Shortcuts app（自定义工作流） | ios-docs\appintents.md:46 | "The Shortcuts app helps people configure workflows that include your app’s actions." |
| App Shortcuts（免配置、装完即用，可被 Siri/Spotlight 使用） | ios-docs\AppIntents-app-shortcuts.md:18–35 | "App Shortcuts provide a polished experience for your app intents and entities in the Shortcuts app and other system experiences."（:18–19） |
| Apple Pencil / iPhone Action button | ios-docs\appintents.md:47；ios-docs\AppIntents-hardware-interactions.md:19–22 | "This button is configurable in Settings, so people can assign any App Shortcuts you create to quickly access your app’s features."（hardware:20–21） |
| iPhone Side button（特定地区，语音对话型 app） | ios-docs\AppIntents-hardware-interactions.md:21–22、:64–66 | "Let people in Japan configure the side button of iPhone to launch your voice-based conversational app."（:66） |
| Apple Watch Action button（`StartWorkoutIntent` / `StartDiveIntent`） | ios-docs\AppIntents-hardware-interactions.md:24–26 | "supports app intents that support the StartWorkoutIntent or StartDiveIntent protocol."（:25–26） |
| Widgets / Lock Screen / Control Center controls | ios-docs\appintents.md:48；ios-docs\AppIntents-widgets-live-activities-and-controls.md:18–20、:34–36 | "An interface for configuring a Control Center module."（:36） |
| Live Activities | ios-docs\appintents.md:48；ios-docs\Y-AppIntents-LiveActivityIntent.md:35–39 | "An intent that starts, pauses, or otherwise modifies a Live Activity when it runs."（widgets页:44） |
| Focus（Focus filter） | ios-docs\appintents.md:49；ios-docs\AppIntents-focus.md:21–25 | "When someone engages a Focus, the system executes your app’s custom SetFocusFilterIntent."（focus:23–24） |
| Visual intelligence（圈选/相机搜索） | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:221；ios-docs\AppIntents-visual-intelligence.md:19–23 | "The system relies on app intents to perform searches and open any search results."（visual页:22–23） |
| Apple Intelligence / Siri AI | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:213；ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:18 | "Apple Intelligence combines language models with your app’s actions and content to power Siri AI."（:18） |
| 组件化清单（官方一段话枚举 6 项） | ios-docs\AppIntents-getting-started-with-the-app-intents-framework.md:213–221 | "Classify your app’s content, and make that information available to Visual intelligence using app intents."（:221） |
| 用户侧体验清单（Shortcuts/Spotlight/visual intelligence/Action button/Siri Suggestions/widget） | ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:28–40 | "Trigger a custom shortcut or the App Shortcut using the Action button."（:35） |
| widget 内的「跳去别的 app / 跑快捷指令」按钮 | ios-docs\Y-AppIntents-RunSystemShortcutIntent.md:34–43 | "Only use RunSystemShortcutIntent to initialize a Button with the Button(_:intent:) initializer and place the button in a widget."（:34–35） |

**Q7. Spotlight 索引怎么做（两条路 + 必需字段 + 批量约束）**

**路线 A：Core Spotlight 直写（`CSSearchableItem` + `CSSearchableItemAttributeSet`）**
- 对象模型：`CSSearchableItem` 唯一标识一段内容，并携带 `CSSearchableItemAttributeSet` 元数据（ios-docs\CoreSpotlight-CSSearchableItem.md:37–49）。
- 最少字段：`title`、`displayName`、`contentType`；若索引磁盘文件再加 `contentURL`（ios-docs\CoreSpotlight-CSSearchableItem.md:50–53）。属性定义见属性集页：`title` = ios-docs\X-CoreSpotlight-CSSearchableItemAttributeSet.md:168–170；`displayName` = :136–138；`contentType` = :120–122；`contentURL` = :128–130；`contentDescription` = :186–188。
- 标识符：`uniqueIdentifier` 是「在你的 app 内唯一」的必填标识（ios-docs\CoreSpotlight-CSSearchableItem.md:94–96）；`domainIdentifier` 是**可选**的域/归属标识（:98–100）。→ **题干里的「`domainIdentifier` 是必需字段」不成立**：官方明文写 optional。
- 写入：`indexSearchableItems(_:completionHandler:)`（ios-docs\CoreSpotlight-CSSearchableIndex.md:99–101）；删除用 `deleteAllSearchableItems` / `deleteSearchableItems(withDomainIdentifiers:)` / `deleteSearchableItems(withIdentifiers:)`（:103–113）。
- 批量约束：`beginBatch()` → `endBatch(withClientState:completionHandler:)` 或 `endIndexBatch(expectedClientState:newClientState:completionHandler:)`（ios-docs\CoreSpotlight-CSSearchableIndex.md:131–141），且**每个新批次必须等上一批次 end 之后才开始**（:54–58）；`fetchLastClientState` 可取回上次状态以便续跑（:143–145）。
- 并发约束：一个 index 同一时刻只能被单线程/单任务修改，且只能由已签名 app/扩展修改；多线程并发访问属编程错误（ios-docs\CoreSpotlight-CSSearchableIndex.md:52–54）。
- 选择 index：生产用 `init(name:)` / `init(name:protectionClass:)` 的自定义 index（支持数据保护、批量、可断点续跑），`default()` 只用于测试/原型（ios-docs\CoreSpotlight-CSSearchableIndex.md:44–50、:68–78）。
- 可用性自检：`isIndexingAvailable()`（ios-docs\CoreSpotlight-CSSearchableIndex.md:82–85）。
- 属性集并发：`CSSearchableItemAttributeSet` 只能单线程修改（ios-docs\X-CoreSpotlight-CSSearchableItemAttributeSet.md:56–58）。

**路线 B：App Intents 实体（`IndexedEntity`）**
- 采纳 `IndexedEntity`（继承 `AppEntity`）即可把实体纳入 app 的 Spotlight 索引（ios-docs\X-AppIntents-IndexedEntity.md:30–40；协议意义见 ios-docs\AppIntents-spotlight.md:34–36）。
- 定制元数据：`attributeSet`（自定义属性集，提升检索准确度）、`defaultAttributeSet`（默认属性集）（ios-docs\X-AppIntents-IndexedEntity.md:48–54）。
- 隐藏：`hideInSpotlight`（:58–61）。
- 索引字段映射：用 `@ComputedProperty(indexingKey: \.contentDescription)` 把属性映射到 Spotlight 键，或用 `customIndexingKey:` 配 `CSCustomAttributeKey`（ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:497–521；更新说明 ios-docs\Updates-AppIntents.md:52）。
- 写入：`CSSearchableIndex.default().indexAppEntities(entities)`（ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:528）；带优先级版本 `indexAppEntities(_:priority:)`（ios-docs\CoreSpotlight-CSSearchableIndex.md:117–119）；删除 `deleteAppEntities(ofType:)` / `deleteAppEntities(identifiedBy:ofType:)`（:121–127）。
- 反查：`IndexedEntityQuery` 让系统按标识符从 Spotlight 取回实体（ios-docs\Updates-AppIntents.md:43）。
- 两者可打通：实体可与 `CSSearchableItem` 关联（`associateAppEntity(_:priority:)`，ios-docs\CoreSpotlight-CSSearchableItem.md:149–159；属性集侧 ios-docs\X-CoreSpotlight-CSSearchableItemAttributeSet.md:80–84；索引页总述 ios-docs\CoreSpotlight-CSSearchableIndex.md:39–41）。

**取舍（官方依据）**
- 走 B（实体）的唯一独占收益：Spotlight 命中能**直接启动 app 到具体条目**，并让 Apple Intelligence 可发现/可语义检索（ios-docs\X-AppIntents-IndexedEntity.md:36–39；ios-docs\AppIntents-spotlight.md:20–21；ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:20）。
- 走 A（自建 index）的收益：可用自定义索引名隔离、带数据保护、可分批＋断点续跑、可只索引「非实体化」的海量内容（ios-docs\CoreSpotlight-CSSearchableIndex.md:36–50）。
- 官方**没有**给出「何时必须选 A、何时必须选 B」的判定表（缓存中无此段）→ 记为 D2-3；工程上按「要不要被 Siri/AI 当实体用」来决定：需要实体语义就走 B，否则 A，两者可叠加关联。

**Q8. iOS 26 新能力（严格按缓存原文）**

先给一条方法论结论：**缓存中的 `Updates-AppIntents.md` 与 `U-Updates-CoreSpotlight.md` 不使用 iOS 版本号分段，而是用月份标题分段**（`June 2026`、`June 2025`、`November 2024`、`June 2024` —— ios-docs\Updates-AppIntents.md:20、:49、:56、:62；`July 2026`、`June 2026`、`June 2024` —— ios-docs\U-Updates-CoreSpotlight.md:20、:24、:29）。因此**不能**把「June 2026」直接等同于「iOS 26」；本档案不自行换算。

官方标注为 **June 2026** 的 App Intents 新增（逐条）：
1. 用 app schema domain 把 intent/entity/enum 与系统契约绑定 —— ios-docs\Updates-AppIntents.md:24
2. `SyncableEntity`：跨设备稳定标识，支持跨设备续任务 —— :25（细节 ios-docs\Y-AppIntents-SyncableEntity.md:38–45）
3. `OwnershipProvidingEntity` + `EntityOwnership`：共享/公开实体上的破坏性操作前确认 —— :26
4. `RelevantEntities`：训练等场景由 AI 建议媒体实体 —— :27
5. `IntentValueRepresentation`：把实体桥接到系统 intent 值类型 —— :28
6. `RunSystemShortcutIntent`：widget 里跑 App Shortcut / 自定义快捷指令 / 系统动作 / 打开别的 app —— :32（限制见 ios-docs\Y-AppIntents-RunSystemShortcutIntent.md:34–36）
7. `LongRunningIntent` + `performBackgroundTask(options:operation:)` + `LongRunningTaskOptions`：延长后台执行并汇报进度 —— :33（数值与平台差异 ios-docs\Y-AppIntents-LongRunningIntent.md:41、:92–93）
8. `CancellableIntent` + `IntentCancellationReason`：区分「主动取消」与「超时」并做清理 —— :34
9. `UndoableIntent`：为动作提供撤销 —— :35
10. `supportedModes`（`IntentModes`）+ `IntentSystemContext.currentMode`：声明前台/后台/两者，并在 `perform()` 内按当前模式分支 —— :36
11. `allowedExecutionTargets`（`IntentExecutionTargets`）：指定主 app / App Intents 扩展 / widget 扩展执行 —— :37
12. `EntityCollection`：只传标识符、按需解析，避免批量操作全量解析 —— :41
13. `@UnionValue` / `AppUnionValue`：联合类型参数的富选择器 —— :42
14. `IndexedEntityQuery`：按标识符从 Spotlight 索引取回实体 —— :43
15. `AppIntentError` 的 `init(description:)`：可本地化的错误描述 —— :47

官方标注为 **June 2026 / July 2026** 的 Core Spotlight 新增：
16. `SpotlightSearchTool`：把索引内容作为 Foundation models 的上下文 —— ios-docs\U-Updates-CoreSpotlight.md:26
17. `CSSearchableIndexDescription`：重建实体索引时引用具体索引 —— :27
18. 自然语言检索索引内容的示例 app（July 2026）—— :22

**唯一出现「iOS 26」字样的后台相关条目**（不属 App Intents 但影响本项目）：
19. `X-CoreBluetooth.md:34`："In iOS 26 and later, your app can continue certain activities in the background if the app starts a Live Activity before it goes to the background." 并在 :35–36 说明可用与前台相同的扫描特权。

另需注意的 availability 事实（避免误标版本）：`LongRunningIntent` 与 `SyncableEntity` 的 availability 元数据写的是 `iOS: 27.0.0 -`（ios-docs\Y-AppIntents-LongRunningIntent.md:4、ios-docs\Y-AppIntents-SyncableEntity.md:4），`ForegroundContinuableIntent` 写的是 `iOS: 16.4.0 - 26.0.0`（ios-docs\AppIntents-ForegroundContinuableIntent.md:4，已废弃，:44）。缓存中并存 26/27 两个版本号，**不能**简单把「June 2026 的新增」标注为 iOS 26。

### C2. 官方未给数值清单（AppIntents / Spotlight）

| 项目 | 结论 | 查过的页 |
|---|---|---|
| 单个 app 可注册多少个 App Shortcut | **官方未给数值** | ios-docs\AppIntents-app-shortcuts.md 全文（153 行）、ios-docs\appshortcutsprovider.md 全文（93 行），均无数量上限 |
| 每个 App Shortcut 至少/最多几条 spoken phrase | **官方未给数值**（只有 `phrases:` 数组参数） | ios-docs\X-AppIntents-AppShortcut.md:49–59、ios-docs\X-AppIntents-AppShortcutPhrase.md:40 |
| App Intent 默认执行时长（秒） | **官方未给数值**（只有 "a short time"） | ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:363 |
| 后台任务时长 | **官方给了数值：30 秒**（macOS 无限制） | ios-docs\Y-AppIntents-LongRunningIntent.md:41、:92–93 |
| `AppEntity` 体积上限 | **官方给了数值：10 MB**（含子属性） | ios-docs\appentity.md:97 |
| Spotlight 索引条数 / 单批次条数上限 | **官方未给数值**（只给「分批＋串行」规则与 client state 机制） | ios-docs\CoreSpotlight-CSSearchableIndex.md:44–58、:129–145 |
| Spotlight 索引大小上限 / 属性集字段数上限 | **官方未给数值** | ios-docs\X-CoreSpotlight-CSSearchableItemAttributeSet.md 全文（921 行）未见任何容量数字 |
| 捐赠保留时长 / 建议刷新频率 | **官方未给数值** | ios-docs\AppIntents-donations-and-discovery.md 全文（100 行） |
| `isDiscoverable` 的默认值 | **官方未给**（缓存页只有一句语义描述，未写默认值） | ios-docs\appintent.md:139–141（独立符号页未缓存，D2-1） |
| `hideInSpotlight` 的默认值 | **官方未给**（同上） | ios-docs\X-AppIntents-IndexedEntity.md:58–61（独立符号页未缓存） |

### D2. 缓存未覆盖项（AppIntents / Spotlight）

1. **D2-1 大量符号的独立页缺失**：`isDiscoverable`、`parameterSummary`、`supportedModes`、`IntentModes`、`IntentExecutionTargets`、`IndexedEntity/attributeSet`、`hideInSpotlight`、`EntityCollection`、`LongRunningTaskOptions` 在缓存中只有索引行（`appintent.md`、`X-AppIntents-IndexedEntity.md` 等），**没有各自的详述页**，因此默认值、边界条件、错误码无法取证。
2. **D2-2 `assistantOnly` 完全缺失**：`ios-docs` 与 `hig-md` 两个目录 grep `assistantOnly` 均命中 0 行；B2-Q5 已按此记为「缓存未覆盖」，未作任何断言。
3. **D2-3 「A 路 vs B 路」官方取舍表缺失**：`making-app-entities-available-in-spotlight`、`adding-your-app-s-content-to-spotlight-indexes`、`making-actions-and-content-discoverable-by-apple-intelligence` 在缓存中只有目录链接（ios-docs\AppIntents-spotlight.md:27–30；ios-docs\CoreSpotlight.md:60–63；ios-docs\AppIntents-apple-intelligence-and-siri-ai.md:39–42、:74–76），正文未缓存。
4. **D2-4 schema 域正文缺失**：`app-schema-domains`、各 `AssistantSchemas` 子页均未缓存，故「哪些 schema 对应哪些系统入口」无法逐条取证。
5. **D2-5 `IndexedEntityQuery` / `SyncableEntityIdentifier` / `EntityOwnership` 正文缺失**：只在 Updates 与 adopting 页被提及（ios-docs\Updates-AppIntents.md:25–26、:43）。
6. **D2-6 HIG 侧覆盖极薄**：`hig-md\` 62 个文件里，`Siri|Shortcuts|Spotlight|App Intent` 仅 6 处命中，其中与 App Intents 相关的实质内容只有 2 处：`hig-md\live-activities.md:216`（用 App Shortcut 起 Live Activity）、`hig-md\accessibility.md:169`（用 Siri/Shortcuts 支持纯语音操作）；另有 `hig-md\controls.md:94`（安全类控制需鉴权，指向 `IntentAuthenticationPolicy`）、`hig-md\settings.md:20`（系统设置里可关闭 Siri 集成）。**HIG 的 `siri`、`app-shortcuts`、`spotlight`、`action-button` 专页均不在缓存**（`appintents.md:57–62` 链接指向的 HIG 页面无一在 `hig-md\` 中）。
7. **D2-7 隐私条款正文缺失**：`hig-md\privacy.md`（230 行）全文无 Siri/Shortcuts/Spotlight/App Intent 段落（grep 命中仅 2 条且与图片背景相关：:141、:153），故「Siri 相关隐私规则」只能引用 App Intents 页与 Core Spotlight 页的说明，不能引用 HIG 隐私章。

### E2. 对本项目 App 的落地含义（AppIntents / Shortcuts / Spotlight）

1. **先按「是否在 app 外被需要」筛动作**（A2-08、A2-09）：陪伴类 app 里真正值得暴露的是「开始/结束一段会话」「问一句当前状态」「切到某个角色/场景」「收藏/标记今天的片段」这类；而不是内部设置项。
2. **数量克制、参数化**：一个意图＋参数，不要为每个角色/每个设备各建一个意图（A2-08 页 :46–49）。
3. **实体要小**：`AppEntity` 有 10 MB 硬上限（A2-19），陪伴场景下不要把整段对话历史/整段音频塞进实体；只放 id、名字、一句摘要，长内容用 `@DeferredProperty`（ios-docs\appentity.md:99–101）。
4. **两条 Spotlight 路可叠加**：把「角色/会话/收藏」做成 `IndexedEntity`（用户搜得到、点了能直接进对应页面，A2-32），同时用自定义 `CSSearchableIndex` 存大体量条目（带数据保护＋分批串行写入，A2-27、A2-28）。注意最小字段是 `title`/`displayName`/`contentType`（A2-29），`domainIdentifier` 可选（A2-30）。
5. **可见性双开关**：不想被系统发现/不想被搜索的（例如私密会话、临时调试实体）用 `isDiscoverable = false`（A2-17）与 `hideInSpotlight`（A2-31）显式关掉——这既是产品需求也是隐私默认值。
6. **隐私叙事要诚实**：官方只承诺「索引留在这台设备、不与 Apple 共享」（A2-26），但**明说 App Shortcuts 的短语/标题描述可能被匿名化抽取用于训练**（A2-22）。因此本项目若做「自定义唤醒短语/角色口令」，应在隐私说明里区分「留在设备的索引」与「可能被匿名抽取的 App Shortcuts 元数据」这两件事。
7. **Siri/Shortcuts 触发的执行不要回捐**（A2-23），否则会污染系统对你用户习惯的判断。
8. **语音陪伴的「长任务」有官方延长通道**：`LongRunningIntent` 明确把默认 30 秒额度延长，并自动以 Live Activity 展示进度（ios-docs\Y-AppIntents-LongRunningIntent.md:39–46；ios-docs\AppIntents-adopting-app-intents-to-support-system-experiences.md:363–365）——这正好契合「机器人/陪伴设备做长耗时上传或推理」的场景，且需定期更新 `progress`，否则系统会取消延长（ios-docs\Y-AppIntents-LongRunningIntent.md:50–54）。
9. **别把 dialog 当唯一反馈渠道**：Siri AI 可能不显示你返回的 `IntentDialog`（A2-42），关键状态要用 snippet/返回值或 app 内 UI 兜底。
10. **`SiriTipView` 只有在同 intent 已进 `AppShortcut` 时才非空**（A2-41），「教用户怎么说」的教学位要据此摆放，否则会出现空白卡片。

---

## F. 查证过的文件清单（文件名 + 是否全读 + 行数）

> 说明：「全读」= 用 `read` 从头读到尾（或分块读完全部行）；「读关键段＋定向 grep」= 只读了 overview/主题段并用 grep 定位所有待引用的具体属性行，未逐行读完剩余的重复属性清单——这两种状态本表如实区分，不混用。

### ios-docs（上表所列 45 个文件，行数合计 6731 行；非整个目录的 166 个文件）

| 文件 | 行数 | 阅读状态 |
|---|---|---|
| BackgroundTasks.md | 120 | 全读 |
| Y-BackgroundTasks-BGTaskScheduler.md | 123 | 全读 |
| UIKit-UIApplication.md | 471 | 全读 |
| SwiftUI-Scene.md | 420 | 读关键段（140–179「Creating background tasks」）＋ grep `backgroundTask` 全目录 |
| X-CoreBluetooth.md | 204 | 读关键段（22–51，含 iOS 26 后台段落） |
| appintents.md | 199 | 全读 |
| appintent.md | 374 | 全读 |
| AppIntents-getting-started-with-the-app-intents-framework.md | 225 | 全读 |
| AppIntents-adopting-app-intents-to-support-system-experiences.md | 567 | 全读 |
| AppIntents-app-shortcuts.md | 153 | 全读 |
| AppIntents-donations-and-discovery.md | 100 | 全读 |
| AppIntents-spotlight.md | 46 | 全读 |
| appentity.md | 188 | 全读（另与 X-AppIntents-AppEntity.md MD5 一致） |
| appenum.md | 146 | 全读 |
| AppIntents-DisplayRepresentation.md | 84 | 全读 |
| AppIntents-ParameterSummary.md | 59 | 全读 |
| AppIntents-focus.md | 61 | 全读 |
| AppIntents-visual-intelligence.md | 42 | 全读 |
| AppIntents-hardware-interactions.md | 72 | 全读 |
| AppIntents-OpenIntent.md | 82 | 全读 |
| AppIntents-ForegroundContinuableIntent.md | 78 | 全读 |
| AppIntents-IntentDialog.md | 84 | 全读（与 X-AppIntents-IntentDialog.md MD5 一致） |
| AppIntents-ReturnsValue.md | 52 | 全读 |
| AppIntents-AppIntentsPackage.md | 77 | 全读 |
| AppIntents-apple-intelligence-and-siri-ai.md | 105 | 全读 |
| AppIntents-widgets-live-activities-and-controls.md | 64 | 全读 |
| appshortcutsprovider.md | 93 | 全读（与 X-AppIntents-AppShortcutsProvider.md MD5 一致） |
| X-AppIntents-AppShortcut.md | 65 | 全读 |
| X-AppIntents-AppShortcutPhrase.md | 56 | 全读 |
| X-AppIntents-AppShortcutsBuilder.md | 60 | 全读 |
| X-AppIntents-IndexedEntity.md | 89 | 全读 |
| X-AppIntents-SiriTipView.md | 70 | 全读 |
| X-AppIntents-ShortcutsLink.md | 64 | 全读 |
| Y-AppIntents-SyncableEntity.md | 96 | 全读 |
| Y-AppIntents-LongRunningIntent.md | 129 | 全读 |
| Y-AppIntents-RunSystemShortcutIntent.md | 139 | 全读 |
| Y-AppIntents-LiveActivityIntent.md | 59 | 全读 |
| CoreSpotlight.md | 202 | 全读 |
| CoreSpotlight-CSSearchableIndex.md | 179 | 全读 |
| CoreSpotlight-CSSearchableItem.md | 189 | 全读 |
| X-CoreSpotlight-CSSearchableItemAttributeSet.md | 921 | **读关键段＋定向 grep**：读 1–250 行（Overview＋全部 Important＋general/document/user 三组属性）＋grep 出全部 20 个 `###` 小节位置（`^### ` 命中 20 个；另有 1 处 `> Important` 在 56–58 行已读）与 `title/displayName/contentType/contentDescription/contentURL/keywords/relatedUniqueIdentifier` 各行号；251–921 的属性清单未逐行读 |
| Updates-AppIntents.md | 88 | 全读（与 U-Updates-AppIntents.md MD5 一致，逐字节相同的重复副本） |
| U-Updates-CoreSpotlight.md | 35 | 全读 |
| JSON-appintents.json | 1（单行 32189 字符） | 全读（全文即一行；核对了 abstract 与 md 同源、无额外数值） |

### hig-md（本主题相关 8 个文件）

| 文件 | 行数 | 阅读状态 |
|---|---|---|
| privacy.md | 230 | 全目录 grep `background\|refresh\|Siri\|Shortcuts\|Spotlight\|widget`＋读命中段；**无后台、无 Siri/App Intent 实质内容** |
| launching.md | 91 | 全目录 grep `background\|launch\|refresh\|terminate`＋读命中行；**无后台执行规范** |
| playing-audio.md | 136 | grep 命中段（:36、:40–44 音频类别表） |
| loading.md | 71 | grep 命中段（:26、:30、:66） |
| live-activities.md | 436 | grep 命中段（:216 App Shortcut 起 Live Activity） |
| accessibility.md | 293 | grep 命中段（:169 Siri/Shortcuts 纯语音） |
| controls.md | 97 | grep 命中段（:94 安全控制鉴权→IntentAuthenticationPolicy） |
| settings.md | 94 | grep 命中段（:20 系统设置里可关闭 Siri 集成） |

### 目录级 grep（用于证明「缺失」）

| grep 模式 | 范围 | 结果 |
|---|---|---|
| `BGTaskScheduler | BGAppRefreshTask | BGProcessingTask\|BGContinuedProcessingTask\|permitted identifier\|BGTaskSchedulerPermittedIdentifiers` \| ios-docs 全目录 \| 24 命中，全部集中在 `BackgroundTasks.md` 与 `Y-BackgroundTasks-BGTaskScheduler.md`（类级正文页缺失） |
| `backgroundTimeRemaining | beginBackgroundTask | didFinishLaunching\|permitted\|Info.plist` \| ios-docs 全目录 \| `backgroundTimeRemaining`/`beginBackgroundTask` 仅 `UIKit-UIApplication.md:50,171,175,187`；`didFinishLaunching` 在 ios-docs 命中 0 |
| `assistantOnly | isDiscoverable | hideInSpotlight` \| ios-docs 全目录 \| 仅 2 命中（`appintent.md:139`、`X-AppIntents-IndexedEntity.md:58`）；`assistantOnly`＝0 |
| `30 seconds | minutes to complete | few minutes\|time limit` \| ios-docs 全目录 \| 6 命中，唯一带数字时长的是 `Y-AppIntents-LongRunningIntent.md:41`、`:92–93` |
| `iOS 26 | continued-processing | backgroundTask\(` \| ios-docs 全目录 \| 8 命中，唯一直写 "iOS 26" 的是 `X-CoreBluetooth.md:34` |
| `background task | background execution | suspended\|background refresh\|prewarm\|scenePhase` \| ios-docs 全目录 \| 35 命中，与本主题相关者已全部纳入 A1 |
| `Siri | Shortcuts | Spotlight\|App Intent` \| hig-md 全目录 \| 6 命中（accessibility:169、live-activities:216、settings:20 及 3 条无关命中） |
| `background task | in the background | background execution\|background refresh` \| hig-md 全目录 \| 13 命中，实质相关仅 playing-audio:36–44、loading:30、progress-indicators:99 |

---

## G. 自检：引用行号复核（A1＋A2 每条贴出实际读到的该行原文）

> 复核方式：交付前运行一次性脚本，按「文件:行号」回读该行原文并打印（超长行截断）。下表左侧为 A1/A2 的 ID，右侧为脚本实际打印内容。**若有任何一条与 A 表引述不符，该条必须撤回；本次 66 条全部一致。**

### G1. A1（BackgroundTasks，23 条）

| ID | 回读到的原文（截断显示） |
|---|---|
| A1-01 | `BackgroundTasks.md:32` → "Use this framework to keep your app content up to date and run tasks requiring minutes to complete even if your app is in the background. Longer tasks can leverage external power, network connectivity, and the GPU on supported dev …" |
| A1-02 | `BackgroundTasks.md:34` → "To launch your app in the background and perform necessary work, register launch handlers for framework-provided tasks and schedule the tasks as needed." |
| A1-03 | `BackgroundTasks.md:36` → "Your app can also use a framework-provided task to execute critical jobs in the foreground and complete them in the background if a person backgrounds your app before the job completes." |
| A1-04 | `BackgroundTasks.md:70` → "An object representing a short task typically used to refresh content that’s run while the app is in the background." |
| A1-05 | `BackgroundTasks.md:66` → "A time-consuming processing task that runs while the app is in the background." |
| A1-06 | `BackgroundTasks.md:84` → "A task that starts in the foreground and can continue running in the background as needed." |
| A1-07 | `BackgroundTasks.md:74` → "A time-consuming, necessary processing task that runs while the app is in the background to prepare data essential to a health research study." |
| A1-08 | `BackgroundTasks.md:92` → "A request to launch your app in the background to execute a processing task that can take minutes to complete." |
| A1-09 | `BackgroundTasks.md:96` → "A request to launch your app in the background to execute a short refresh task." |
| A1-10 | `BackgroundTasks.md:108` → "A request for a workload that the system continues processing even if a person backgrounds the app." |
| A1-11 | `BackgroundTasks.md:86` → "  `<doc://com.apple.documentation/documentation/BundleResources/Entitlements/com.apple.developer.background-tasks.continued-processing.gpu>`" |
| A1-12 | `Y-BackgroundTasks-BGTaskScheduler.md:59` → "Register a launch handler for the task with the associated identifier that’s executed on the specified queue." |
| A1-13 | `Y-BackgroundTasks-BGTaskScheduler.md:61` → "[`func submit(BGTaskRequest) throws`](/documentation/BackgroundTasks/BGTaskScheduler/submit(_:))" ／ `:63` → "Submit a previously registered background task for execution." |
| A1-14 | `Y-BackgroundTasks-BGTaskScheduler.md:77` → "[`func getPendingTaskRequests(completionHandler: ([BGTaskRequest]) -> Void)`](…)" ／ `:79` → "Request a list of unexecuted scheduled task requests." |
| A1-15 | `UIKit-UIApplication.md:189` → "The maximum amount of time remaining for the app to run in the background."（符号行 :187 = "[`var backgroundTimeRemaining: TimeInterval`](…)") |
| A1-16 | `UIKit-UIApplication.md:173` → "Marks the start of a task with a custom name that should continue if the app enters the background." |
| A1-17 | `UIKit-UIApplication.md:195` → "The smallest fetch interval supported by the system." |
| A1-18 | `Y-AppIntents-LongRunningIntent.md:41` → "up to 30 seconds to finish its task. For some types of tasks, this amount" |
| A1-19 | `Y-AppIntents-LongRunningIntent.md:92` → "> Note: In macOS, the system allows background tasks to run without time limits. In iOS," ／ `:93` → "> iPadOS, tvOS, visionOS, and watchOS, the system gives tasks 30 seconds to run in the background" |
| A1-20 | `SwiftUI-Scene.md:152` → "[`func backgroundTask<D, R>(BackgroundTask<D, R>, action: (D) async -> R) -> some Scene`](…)" ／ `:154` → "Runs the specified action when the system provides a background task." |
| A1-21 | `X-CoreBluetooth.md:34` → "In iOS 26 and later, your app can continue certain activities in the background if the app starts a Live Activity before it goes to the background." |
| A1-22 | `hig-md\playing-audio.md:42` → "\|Playback \|Sound is essential and might mix with other audio. … \|Doesn’t respond to the silence switch. May or may not mix with other sounds. Can play in the background. \|" |
| A1-23 | `hig-md\loading.md:30` → "**Improve installation and launch time by downloading large assets in the background.** Consider using the <doc://…BackgroundAssets> framework to schedule asset downloads — like game level pack …" |

### G2. A2（AppIntents / Spotlight，43 条）

| ID | 回读到的原文（截断显示） |
|---|---|
| A2-01 | `appintents.md:30` → "Make content and actions discoverable by Apple Intelligence and support system experiences like Siri, Spotlight, Shortcuts, and widgets." |
| A2-02 | `appintents.md:44` → "- People can interact with your app’s content through Siri." |
| A2-03 | `appintents.md:45` → "- Spotlight helps people navigate to your data directly from search results." |
| A2-04 | `appintents.md:46` → "- The Shortcuts app helps people configure workflows that include your app’s actions." |
| A2-05 | `appintents.md:47` → "- People can configure Apple Pencil or the Action button on iPhone to perform your app’s actions when pressed." |
| A2-06 | `appintents.md:48` → "- [Widgets](…), [controls](…), and [Live Activities](…) can us …"（下文："…can use your app’s actions to perform relevant tasks."） |
| A2-07 | `appintents.md:49` → "- You can define custom Focus modes, and respond to Focus changes." |
| A2-08 | `getting-started…md:44` → "As you design your app, identify actions that people might want to perform from outside your app." |
| A2-09 | `getting-started…md:89` → "of truth. You typically create entities for only a subset of your app’s actual data, focusing" ／ `:90` → "on the types that people see and manipulate from your interface." |
| A2-10 | `getting-started…md:168` → "> Note: Some intents require your app to run in the foreground, and automatically launch your" ／ `:170` → "> launches your app to display a specific item. Place the code for these app intents only in your app." |
| A2-11 | `getting-started…md:186` → "for that song to the view. If someone asks Siri to “play this song”, Siri can use that" |
| A2-12 | `getting-started…md:213` → "- [Apple Intelligence and Siri AI](…) work better for app intents" ／ `:215` → "- [Spotlight](…) uses entity donations to support enhanced interactions with your app." ／ `:217` → "- [Widgets, Live Activities, and Controls](…) can use app" ／ `:219` → "- Customize the [Action button and Side button](…) behaviors on iPhone using app intents." ／ `:220` → "- Respond to [Focus](…) mode changes using app intents." ／ `:221` → "- Classify your app’s content, and make that information available to [Visual intelligence](…) using app intents." |
| A2-13 | `adopting…md:30` → "- Find and run the app’s intents in Shortcuts." ／ `:33` → "- Search for a landmark, photo, or the “Find Closest” App Shortcut in Spotlight." ／ `:35` → "- Trigger a custom shortcut or the App Shortcut using the Action button." |
| A2-14 | `adopting…md:79` → "An app entity exposes only the parts of your stored model object that the system needs. It also adds required information" ／ `:81` → "required `typeDisplayRepresentation` and `displayRepresentation` properties but doesn’t include every property of the `Landmark` model object:" |
| A2-15 | `adopting…md:363` → "By default, intents have only a short time to finish their work. For tasks that take longer, for example, uploading a large photo in chunks," |
| A2-16 | `adopting…md:528` → "    try await CSSearchableIndex.default().indexAppEntities(landmarkEntities)" ／ `:494` → "The app describes its data as app entities so the system can use that data when running app intents. The app also donates the entities to the semantic search index so people can find them in Spotlight. …" |
| A2-17 | `appintent.md:139` → "[`static var isDiscoverable: Bool`](…)" ／ `:141` → "A Boolean value that indicates whether system features can discover this app intent." |
| A2-18 | `appintent.md:245` → "[`static var parameterSummary: Self.SummaryContent`](…)" ／ `:247` → "The parameter summary the Shortcuts app uses to generate shortcuts for this intent." |
| A2-19 | `appentity.md:97` → "> Important: `AppEntity` instances have a total size limit of 10 MB, including all child properties and their values." ／ `:98` → "> If your entity exceeds this limit, the system throws an exception, and your app might crash." |
| A2-20 | `appentity.md:66` → "    var displayRepresentation: DisplayRepresentation {"（:63 为注释 "Information on how to display the entity to people …"） |
| A2-21 | `appenum.md:85` → "> Note: Don’t adopt the `AppEntity` and `AppEnum` protocols in the same type. An app entity type represents data" |
| A2-22 | `AppIntents-app-shortcuts.md:37` → "> Note: Apple may extract anonymized App Shortcuts data such as localized phrases, display" ／ `:38` → "> representation values, and the title and description of related intents. Machine learning"；同文见 `appshortcutsprovider.md:40` → "> Note: Apple may extract anonymized App Shortcuts data such as localized" |
| A2-23 | `donations-and-discovery.md:19` → "When someone performs an action in your app’s interface, create a matching app intent and donate" ／ `:22` → "proactively suggest the same action each morning. Restrict your donations to direct interactions" ／ `:23` → "with your app’s interface, and not to interactions started by Siri or the Shortcuts app." |
| A2-24 | `apple-intelligence-and-siri-ai.md:20` → "**Index entities to make them available in Spotlight.** Apple Intelligence uses the semantic search capabilities of Spotlight to find your app’s content, even when someone describes it vaguely." |
| A2-25 | `apple-intelligence-and-siri-ai.md:26` → "**Associate entities with views and other structures.** People use Siri AI to interact with content that’s visible onscreen, but that content is private to your app. …" |
| A2-26 | `CoreSpotlight.md:44` → "isn’t currently displaying. The indexes you create using Core Spotlight remain" ／ `:45` → "on device, and are private to the owner of the device. Devices don’t share" ／ `:46` → "indexed data with Apple, or synchronize that data with the person’s other devices." |
| A2-27 | `CoreSpotlight-CSSearchableIndex.md:44` → "Create custom `CSSearchableIndex` objects in your production code to store your app’s content," ／ `:45` → "instead of using the default index. Custom indexes support data protection, which allows" ／ `:46` → "you to encrypt your data and protect it from unauthorized access. Custom indexes also" |
| A2-28 | `CSSearchableIndex.md:52` → "Modify a `CSSearchableIndex` object from only one thread or task at a time, and modify it" ／ `:55` → "updates on an index, start each new batch operation only after calling the" |
| A2-29 | `CSSearchableItem.md:50` → "the item. For the metadata, you typically want to provide values for" ／ `:52` → "and [`contentType`](…) attributes at a minimum."（`title`/`displayName` 在 :51 同一句内） |
| A2-30 | `CSSearchableItem.md:98` → "[`var domainIdentifier: String?`](…)" ／ `:100` → "An optional identifier that represents the domain or owner of the item." |
| A2-31 | `X-AppIntents-IndexedEntity.md:58` → "[`var hideInSpotlight: Bool`](…)" ／ `:60` → "A Boolean value that indicates whether Spotlight prevents the inclusion of the entity" |
| A2-32 | `X-AppIntents-IndexedEntity.md:36` → "Adopt this protocol in app entities you want to include in your app’s Spotlight index." ／ `:37` → "Adding entities to Spotlight makes them discoverable by Apple Intelligence, and also" ／ `:38–39` → "serves as the first step in letting Spotlight launch your app and display items that appear in search results." |
| A2-33 | `Updates-AppIntents.md:24` → "- Integrate your app with Apple intelligence by conforming your app intents, app entities, and app enums to an app schema in one of the <…app-schema-domains>." ／ `:26` → "- Prompt for confirmation before destructive or sensitive actions on shared or publicly accessible entities by adopting <…OwnershipProvidingEntity> and returning an <…EntityOwnership> value." |
| A2-34 | `Updates-AppIntents.md:32` → "- Let people perform App Shortcuts, custom shortcuts, system actions, or open another app from interactive widgets with <…RunSystemShortcutIntent>." ／ `:33` → "- Extend an app intent’s background runtime by adopting <…LongRunningIntent> and calling <…performBackgroundTask(…)…> …" ／ `:36` → "- Specify whether your app intent runs in the foreground, the background, or both by setting the `supportedModes` property …" ／ `:37` → "- Tell the system which target may perform your app intent or entity query — the main app, the App Intents extension, or a widget extension — …" |
| A2-35 | `Updates-AppIntents.md:41` → "- Refer to a large set of entities efficiently using <…EntityCollection>, which stores only entity identifiers …" ／ `:42` → "- Define union-type Shortcuts parameters with rich picker UI and custom metadata by adopting <…AppUnionValue> …" ／ `:43` → "- Have the system retrieve indexed entities by identifier from the Spotlight index by adopting <…IndexedEntityQuery>." |
| A2-36 | `U-Updates-CoreSpotlight.md:26` → "- Make your app’s indexed content available to Foundation models using <…SpotlightSearchTool>." ／ `:27` → "- Refer to your Spotlight indexes when reindexing entities using <…CSSearchableIndexDescription>." |
| A2-37 | `Y-AppIntents-SyncableEntity.md:38` → "Adopt the `SyncableEntity` protocol in your entity types when they have an identifier that’s the same across devices. The presence of this" ／ `:39` → "protocol tells the system that it can refer to your entity consistently across devices. …" |
| A2-38 | `Y-AppIntents-RunSystemShortcutIntent.md:34` → "Only use `RunSystemShortcutIntent` to initialize a <…SwiftUI/Button> with the" ／ `:36` → "The run system shortcut intent doesn’t provide functionality in other contexts." |
| A2-39 | `Y-AppIntents-LiveActivityIntent.md:36` → "In general, your app needs to be in the foreground to start a Live Activity. However, you can use a `LiveActivityIntent` and start" |
| A2-40 | `AppIntents-ForegroundContinuableIntent.md:44` → "This protocol is deprecated, please include `.foreground(.dynamic)` in the [`supportedModes`](…) of your app intent instead." |
| A2-41 | `X-AppIntents-SiriTipView.md:48` → "Note that you must use the [`AppIntent`](…) in an [`AppShortcut`](…). Otherwise this will display an empty view." |
| A2-42 | `AppIntents-IntentDialog.md:39` → "When someone performs an action with Siri AI that invokes your app intent, the system" ／ `:40` → "might not display the `IntentDialog` you return as an intent result." |
| A2-43 | `JSON-appintents.json:1`（单行全文）开头 → "…\"abstract\":[{\"text\":\"Make content and actions discoverable by Apple Intelligence and support system experiences like Siri, Spotlight, Shortcuts, and widgets.\",\"type\":\"text\"}]…" |

### G3. 撤回记录

| 撤回项 | 原拟主张 | 撤回原因 | 处置 |
|---|---|---|---|
| R-1 | 「必须在此 `application(_:didFinishLaunchingWithOptions:)` 内完成 `BGTaskScheduler.register`」并引用原文行号 | 全 `ios-docs` grep `didFinishLaunching` 命中 0；缓存无该段原文，无法给真实行号 | 已删除该断言，改记 D1-1，B1-Q2 明确写「缓存中找不到原文」 |
| R-2 | 「Info.plist 需声明 `BGTaskSchedulerPermittedIdentifiers`」并引用原文行号 | grep `BGTaskSchedulerPermittedIdentifiers` 与 `permitted identifier` 均命中 0 | 已删除，改记 D1-2 |
| R-3（同批自查） | 「`BGContinuedProcessingTaskRequest` 是 iOS 26 新增」 | 缓存中该类只有目录级描述（`BackgroundTasks.md:106–108`），无 availability 元数据；同批的 Updates 页用月份而非 iOS 版本号分段 | 未写入 A/B，改记 D1-4 与 B2-Q8 的方法论说明 |
| R-4（同批自查） | 「Spotlight 的 `domainIdentifier` 是必需字段」 | 官方明文写 "An optional identifier…"（`CoreSpotlight-CSSearchableItem.md:100`），与题干假设相反 | 已在 A2-30 与 B2-Q7 明确纠正为「可选」，不按题干假设写 |

> 统计：A1 实列 23 条、A2 实列 43 条，共 66 条，G 节逐条回读全部一致，**正式撤回 2 条（R-1、R-2）＋自查纠正 2 条（R-3、R-4）**。
> 全文数字来源：`30 seconds`（Y-AppIntents-LongRunningIntent.md:41、:93）、`10 MB`（appentity.md:97）、版本号 `iOS 13.0.0`（BackgroundTasks.md:4）、`iOS 16.0.0`（appintent.md:4）、`iOS 17.0.0`（Y-AppIntents-LiveActivityIntent.md:4）、`iOS 18.0.0`（X-AppIntents-IndexedEntity.md:4）、`iOS 26`（X-CoreBluetooth.md:34）、`iOS 16.4.0 - 26.0.0`（AppIntents-ForegroundContinuableIntent.md:4）、`iOS 27.0.0`（Y-AppIntents-LongRunningIntent.md:4、Y-AppIntents-SyncableEntity.md:4）、月份标题 `June 2026 / July 2026 / June 2025 / November 2024 / June 2024`（Updates-AppIntents.md:20,49,56,62；U-Updates-CoreSpotlight.md:20,24,29）—— 均已在正文标注出处，无未标注数字。
