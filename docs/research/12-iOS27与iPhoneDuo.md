# 12 · iOS 27 与 iPhone Duo —— 折叠双屏时代的适配（2026-09 新增）

> 方法：`https://developer.apple.com/documentation/updates/swiftui.md` 官方更新日志（纯文本直取）。
> **这一页是本轮调研里对"iPhone 17 怎么设计才好看"最直接的回答 —— 而且答案超出现有认知。**

---

## 0. 关键结论（先说最重要的三条）

1. **当前最新系统是 iOS 27（2026 年 9 月发布），不是 iOS 26。**
   - iOS **26** = iPhone 17 那一代（2025 年 9 月随 iPhone 17 发布）。
   - iOS **27** = 2026 年 9 月发布，**随 iPhone Duo（折叠双屏）发布**。
   - 官方 SwiftUI 更新日志的条目顺序：September 2026（iOS 27 正式）→ June 2026（iOS 27 预览）→ June 2025（iOS 26 预览）。

2. **iOS 27 引入 `iPhone Duo`（折叠双屏）的一整套 API**，这是 Apple 第一次把"折叠屏"作为一等公民写进 SwiftUI。

3. **对小栈这种"桌面陪伴机器人"，折叠双屏是天然契合的形态，不是可选项**：
   - **合上时**：外屏 = 小栈的一只"眼睛"，像它一直在看着你 → 这是陪伴感最强的形态。
   - **展开时**：内屏 = 完整 App（对话 / 记忆 / 动作库），铰链角度还能驱动表情。
   - **拍照时**：外屏直接显示取景与"小栈看到的画面" → "拍照给小栈看"变成一个物理上成立的交互。

---

## 1. iOS 27 的 SwiftUI 新增（September 2026 段，官方原文要点）

### 1.1 Arrangement views —— 主次内容的自适应布局
| API | 用途 |
|---|---|
| `ArrangementView` | 主/次内容的自适应布局容器 |
| `View.arrangementViewStyle(_:)` | 配置样式 |
| `ArrangementViewStyle.split` | 主次内容**并排**（可 `SplitArrangementViewStyle.axes(_:)` 限制方向） |
| `View.splitArrangementLayoutRatio(...)` | 主次**宽度/高度比例**（有 min/ideal/max 三档） |
| `View.splitArrangementLayoutSize(minWidth:idealWidth:maxWidth:...)` | 绝对尺寸约束 |
| `ArrangementViewStyle.overlay` | 主内容**叠在**次内容之上（z-order） |
| `View.overlayArrangementEdge(_:)` | 叠放内容锚定到某条边 |
| `EnvironmentValues.splitArrangementAxis` / `overlayArrangementZIndex` | 子视图读取当前轴向 / z-index |

→ **对我们的用法**：
- 折叠展开 → `.split` 布局：**左 = 小栈的脸（主）**，**右 = 对话/内容（次）**，比例可调。
- 合上 → `.overlay`：脸浮在底图之上。

### 1.2 Reserved regions —— 硬件预留区（相机/铰链）
| API | 说明 |
|---|---|
| `ReservedRegion` | 识别被硬件预留的区域 |
| `GeometryProxy.reservedRegions(kind:options:layoutDirectionBehavior:)` | 查询与视图相交的预留区 |
| `ReservedRegion.Kind` | `.occlusion`（**相机遮挡**）/ `.division`（**铰链分割**） |
| `ReservedRegion.QueryOptions.includeInactive` | 包含未激活的预留区 |
| `ReservedRegion.ID` | 跨坐标空间识别/追踪 |

→ **必须做**：小栈的脸如果放在屏幕顶部，必须避开 `.occlusion`；折叠时必须避开 `.division`。这是"看起来像原生"与"看起来像拼的"的分界线之一。

### 1.3 Hinge —— 铰链状态
| API | 说明 |
|---|---|
| `View.onHingeChange(isEnabled:_:)` | 监听 **iPhone Duo** 铰链状态变化，回调给 `DeviceHingeContext` |
| `DeviceHinge` | 读取当前角度/状态：**`.closed` / `.partiallyOpen` / `.fullyOpen`** |

→ **超纲的用法**：铰链角度直接驱动小栈的**姿态**——
- `.closed`（合上）→ 只露外屏，眼神收敛
- `.partiallyOpen`（半开）→ 侧耳/好奇（像个歪头）
- `.fullyOpen`（全开）→ 正面全神贯注

这是**物理交互驱动表情**，是 iOS 独有能力，Android 做不到 —— 作品集里极有说服力。

### 1.4 Scene accessories —— 外屏内容
> `CameraCaptureAccessory`：当设备处于打开状态、App 在前台、**且正在进行相机采集**时，把内容呈现在 **iPhone Duo 的外屏**。

→ **完美的用例**：拍照给小栈看时，**外屏显示"小栈视角"**，内屏显示取景器。物理上就是"你举起手机，小栈从口袋里往外看"。

### 1.5 Controls on the vertical axis —— 纵向轴控件
| API | 说明 |
|---|---|
| `EnvironmentValues.toolbarVerticalEdge` | 读取系统放置纵向轴控件的边 |
| `View.toolbarVerticalBehavior(_:)` | 退出纵向轴，回落到标准上下工具栏 |
| `ToolbarContent.axisBehavior(_:)` / `CustomizableToolbarContent.axisBehavior(_:)` | 单个工具栏项选纵向还是横向（`.horizontalOnly` / `.verticalPreferred`） |
| `View.toolbarVerticalCompressionBehavior(_:)` | 空间不足时工具栏与 Tab Bar 的压缩优先级（`.prefersToolbarItems` / `.prefersTabBar`） |

→ 折叠/半折状态下，系统会把工具栏移到**竖边**。我们的"叫醒小栈"这类主操作可以顺势落在铰链侧边。

### 1.6 Tab bars（iOS 27 新增）
> `TabRole.prominent` —— 让某个 tab 处于**独立的尾随位置**（separate, trailing position）。

→ 我们的 IA 是 2 个 Tab（小栈 / 陪伴）。可以把**"小栈"设成 `.prominent`** → 它被单独拎出来放在 Tab Bar 尾侧，视觉权重天然高于"陪伴"。**这比我们自己调色调尺寸更"原生"。**

---

## 2. iOS 27（June 2026 段）其他与本项目相关的变化

| 分类 | 新增 | 用途 |
|---|---|---|
| **General** | Xcode 27 起 `@State` 宏、`ContentBuilder` 统一 builder | 工程基线要跟到 Xcode 27 |
| **Toolbars** | `ToolbarContent.visibilityPriority(_:)`（空间不足时优先保留） | **主操作保底可见** —— 正是我们要的"主要动作不被挤掉" |
| | `ToolbarOverflowMenu`（次要操作直接进溢出菜单） | 次要动作不占版面 |
| | `ToolbarItemPlacement.topBarPinnedTrailing` | 固定尾随项 |
| | `View.toolbarMinimizationBehavior(_:for:)` | 控制滚动时工具栏收缩 |
| **Transitions** | `NavigationTransition.crossFade` | sheet 以淡入方式出现（**比默认上滑更"安静"**） |
| **Gestures** | 手势可指定输入源（直接/间接触摸、铅笔、指针） | 我们的手势控舵机需要区分"手指直接操作"与"UI 间接拖动" |
| | `WindowDragGesture` / `SpatialTapGesture` 等 | — |
| **General** | `DynamicViewContent.reorderable()` / `View.reorderContainer(...)` | 列表拖拽排序（动作库可自定义顺序） |
| | `View.swipeActions(edge:allowsFullSwipe:...)` | 行滑动手势 |
| **Images** | `AsyncImage.asyncImageURLSession(_:)` 本地缓存 | 表情帧缓存 |

---

## 3. 对我们 App 的三条具体设计影响

### 3.1 首页构图要"可折叠"
小栈的脸不能当成一张贴图铺满 —— 它必须是一个**能塞进半屏/外屏也能成立**的元素。
- 展开：脸占左半屏（`.split` + `splitArrangementLayoutRatio`）
- 合上：脸居中于外屏，带一个"眼睛"级别的极简状态表达
- 建议：脸部主视觉至少准备 **2 套密度**（完整表情 / 极简眼神）

### 3.2 铰链 = 免费的表情驱动通道
`onHingeChange` → 映射到小栈表情/舵机姿态。这条**零后端成本、零协议改动、纯本地**，是"作品集里最能讲出平台理解"的一个点。

### 3.3 "拍照给小栈看"在 Duo 上是原生体验
`CameraCaptureAccessory` + 外屏 → 不需要我们自己写相机 UI 就能做双屏取景。

---

## 4. 部署与版本策略（修正）

| 目标 | 建议 |
|---|---|
| 最低部署 | **iOS 17** |
| 主力 | **iOS 18**（Control Widget 在 18+） |
| 渐进增强 | iOS 26：`glassEffect(_:in:)` / `Glass` / `GlassEffectContainer` |
| 渐进增强 | iOS 27：`ArrangementView` / `TabRole.prominent` / `ToolbarOverflowMenu` / `visibilityPriority` / `NavigationTransition.crossFade` / `ReservedRegion` / `onHingeChange` / `CameraCaptureAccessory` |
| 工程基线 | **Xcode 27**（`@State` 宏与 `ContentBuilder` 需要） |

> ⚠️ 这些 API 的**可用性只从官方更新日志读到名字与语义**，**未在真机/模拟器验证**（本机无 Xcode）。

---

## 5. 未验证项

- `iPhone Duo` 的**屏幕尺寸、分辨率、外屏形态**未核实（更新日志只讲 API）。
- `iPhone Duo` 是否属于"iPhone 17 那一代"未核实 —— 官方日志把 Duo 放在 iOS 27（2026-09）里，**时间上晚于 iPhone 17**。**不要把它说成"iPhone 17 是折叠屏"**。
- 所有 API 的实际行为（铰链角度精度、外屏触发条件）未验证。
- `ReservedRegion` 的 `.occlusion` / `.division` 在非折叠设备上的返回未验证。
