# StackChanCompanion · iOS App（原生 SwiftUI）

> **M5Stack StackChan 桌面陪伴机器人的官方 iOS App 重写。**
> 官方 App 是 Flutter（不碰），这里是**从零写的 SwiftUI 工程骨架**。
>
> ⭐ **当前状态：工程基座 + 协议层 + 设计系统（4 套方案已落值）+ 界面空壳。**
> 2026-10-25 用户拍板「风格都做」⇒ 设计系统已填**4 套方案**的真实 token；
> 界面层仍是空壳（布局与视觉待用户过目）。

---

## 0. 一句话说清"哪些是真的、哪些是占位"

| 层 | 状态 | 说明 |
|---|---|---|
| **协议层**（`CoreProtocol/`） | ✅ **可用的真代码** | 帧编解码 / 0x14 校验 / 表情参数模型，全部有出处、有单测 |
| **工程结构**（`project.yml` / `pbxproj` / CI） | ✅ 真 | 可在 Mac 上一行命令生成工程并编译 |
| **领域模型**（`CoreModel/` / `Persistence/`） | ✅ 真 | 纯数据，不含视觉 |
| **设计系统**（`DesignSystem/`） | ✅ **4 套方案已落值** | 色值 / 字号 / 圆角 / 间距 / 动效曲线都有真值，且**只允许出现在这里** |
| **界面**（`Features/`） | ⛔ **只有空壳** | 只有类型声明 + 契约注释 + `TODO(pending design decision)`，没有任何布局与视觉 |

> **2026-10-25 更新**：视觉方向已拍板「4 套方案全做」（`docs/spec/07` §3.1b）。
> 设计系统从「全是占位」升级为「**槽位 × 4 套取值**」：
> `ThemeChoice` 有 4 个 case，每个对应一个 `ThemePalette` 实现，
> 色值逐项抄自 `prototype/variants/` 的 4 个原型。
> **新增方案的成本 = 1 个 `ThemePalette` + 1 个 case**，不碰任何 Screen。

---

## 1. 目录结构

```
ios/
├── project.yml                          ← 【权威来源】XcodeGen 工程描述
├── README.md                            ← 本文件
├── StackChanCompanion.xcodeproj/        ← 手写 pbxproj（**未经 Mac 验证**，见 §6）
├── StackChanCompanion/
│   ├── App/                             StackChanCompanionApp.swift / RootScene.swift
│   ├── DesignSystem/                    Tokens / Theme / Typography / Motion / Shapes / Glass
│   │                                    ✅ 4 套方案已落值（纸感陶土 / 纯白留白 / 暖纸衬线 / 深色静谧）
│   ├── CoreProtocol/                    ← 独立 Swift Package（可单独跑单测）
│   │   ├── Package.swift
│   │   ├── Sources/CoreProtocol/
│   │   │   ├── MsgType.swift            官方 25 项消息类型表
│   │   │   ├── Frame.swift              [Type(1)][Length(4 BE)][Payload] 编解码
│   │   │   ├── JSONSchema.swift         0x03 / 0x04 的本地 schema 校验
│   │   │   ├── DanceSequence.swift      0x14 的 8-key 帧模型 + 解码校验
│   │   │   ├── AvatarModel.swift        3 元素 × 5 参数 / weight 极性 / 单位换算 / 6 情绪表
│   │   │   ├── FaceGeometry.swift       固件几何的 Swift 移植（眼位/眼径/眼睑/嘴/旋转）
│   │   │   └── FaceProjection.swift     渲染双模式（.mirror / .stylized）+ 语义指纹守卫
│   │   └── Tests/CoreProtocolTests/     FrameTests / DanceSequenceTests / AvatarModelTests
│   │                                     / FaceGeometryTests / FaceProjectionTests
│   ├── CoreModel/                       Conversation / Message / Mood / Presence / DeviceState
│   ├── Features/
│   │   ├── Companion/                   CompanionView / StatusBar / MessageRow / Composer / MicButton / ActionKeys
│   │   │   └── Face/                    FaceView（镜像 / 风格化两个 Canvas）
│   │   ├── Stack/                       StackView / PosturePreview / PostureReadout / ActionCapsules
│   │   ├── Settings/                    SettingsScene（Tab 2「设置」）
│   │   └── LiveActivity/                StackChanAttributes（共享框架） / Widget / Controller
│   ├── Persistence/                     ArchiveStore（只读本地，永不同步）
│   └── Resources/                       Assets.xcassets / Info.plist / AppIcon 源占位
└── tools/
    ├── validate_project.py              离线静态校验（Python 3.12 标准库）
    └── frame_spec_check.py              协议规则离线复核（Python 3.12 标准库）
```

> **DesignSystem 目录**（视觉 token 唯一落点，门禁强制「目录外不许出现视觉字面量」）：
> `Tokens.swift` / `Theme.swift`（4 套方案）/ `Typography.swift` / `Motion.swift` /
> `Shapes.swift` / `Glass.swift` / **`FaceStyle.swift`**（设备原色 + 风格化样式参数）。

---

## 2. 在 Mac 上怎么打开 / 怎么生成工程

### 2.1 方式一（推荐）：XcodeGen

```bash
brew install xcodegen
cd ios
xcodegen generate        # 依据 project.yml 生成 StackChanCompanion.xcodeproj
open StackChanCompanion.xcodeproj
```

> `project.yml` 是**权威来源**。`xcodegen generate` 会**覆盖**仓库里那份手写 pbxproj，这是预期的。

### 2.2 方式二：直接打开仓库里那份 pbxproj

```bash
open ios/StackChanCompanion.xcodeproj
```

⚠️ 这份 pbxproj 是**手写生成**的（UUID 由脚本确定性推导，结构经离线校验），
**从未在 Mac / Xcode 上打开过**。如果 Xcode 打不开或报奇怪的错，**直接用方式一**重新生成即可。

### 2.3 最低系统版本：**iOS 17.0**

| 能力 | 起始版本 | 本工程用法 |
|---|---|---|
| `@Observable` 状态管理 | iOS 17 | 选型表指定（`docs/spec/05` §技术选型） |
| `.sensoryFeedback` 触感 | iOS 17 | 选型表指定；契约要求"一次交互 ≤ 1 次触感" |
| ActivityKit Live Activity | iOS 16.1 | `docs/research/58` §5 |
| App Intents | iOS 16 | `docs/research/58` §6 |
| Liquid Glass（`Glass` / `glassEffect`） | **iOS 26** | 走 `#available(iOS 26.0, *)` 渐进增强（`DESIGN.md` §7.2） |

⇒ **iOS 17 同时满足前三项，又不必为了 Liquid Glass 抬高门槛**，所以取 17.0。

---

## 3. 怎么跑测试

协议层是**独立 Swift Package**，测试**不需要模拟器、不需要 Xcode 工程**：

```bash
swift test --package-path ios/StackChanCompanion/CoreProtocol
```

> 覆盖：帧编解码往返 / **Data 切片（startIndex ≠ 0）** / 截断帧 / 未知类型 / 超大声明长度 /
> 0x14 顶层数组校验 / 缺 key / 多余 key / x-y 必须同时 int / 舵机限位 / weight 极性 /
> x-y 单位换算（系数 6.25）/ 官方情绪表 / **负 rotation 拒收** / **下发角换算（−400 → 3200）** /
> 设备端几何公式（眼径 / 眼睑偏移 / 嘴矩形）/ 规范默认值 / **6 情绪表逐值** / **左右眼镜像** / **下发角换算**。共 **91** 个测试函数。

编译整个 App：

```bash
cd ios
xcodebuild -project StackChanCompanion.xcodeproj \
           -scheme StackChanCompanion \
           -configuration Debug \
           -destination 'generic/platform=iOS' \
           CODE_SIGNING_ALLOWED=NO \
           build
```

---

## 4. App Icon 怎么出

**官方 App Icon 流程绕不开 macOS**（Icon Composer 随 Xcode 分发），所以走 CI：

1. 矢量源放在 `ios/StackChanCompanion/Resources/AppIcon/AppIcon.svg`
   （⛔ **当前是占位**，没有图形 —— 视觉未拍板）
2. 拍板后按 `docs/research/19` F39–F43 + `DESIGN.md` §6 补画（分层矢量、不预切圆角、
   要 mono 版、不许画成"官方小栈"的样子）
3. 填 `Resources/Assets.xcassets/AppIcon.appiconset/Contents.json`，
   并取消 `project.yml` 里 `ASSETCATALOG_COMPILER_APPICON_NAME` 的注释
4. CI 的 `app-icon` job 会自动：`rsvg-convert` 出 1024 PNG → `sips` 铺全套尺寸 →
   `actool` 编译校验 → `iconutil` 出 `.icns`
   （源文件里还带 `TODO_PENDING_DESIGN_DECISION` 标记时，job 会**跳过**并打 notice）

**本地复现（macOS）**：

```bash
brew install librsvg
rsvg-convert -w 1024 -h 1024 ios/StackChanCompanion/Resources/AppIcon/AppIcon.svg -o /tmp/AppIcon-1024.png
sips -z 180 180 /tmp/AppIcon-1024.png --out /tmp/AppIcon-180.png
```

---

## 5. 本机（Windows）能跑的离线校验

本机**没有 Swift 编译器**，所以协议规则用 Python 重新实现一遍来验：

```bash
py -3.12 ios/tools/validate_project.py     # 工程静态校验
py -3.12 ios/tools/frame_spec_check.py     # 协议规则复核（手写用例 + 真实 292 帧语料）
```

`validate_project.py` 检查：括号配对 / 声明块闭合 / **视觉字面量清零**（色值、字号、圆角、
间距、动效时长、阴影一律不许出现）/ 显式待拍板标记齐全 / `project.yml` 每个源文件路径存在 /
每个 `.swift` 都归属某个 target（漏文件会被抓）/ 消息类型数值与 `docs/spec/03` §2.2 一致 /
测试函数名唯一 / pbxproj 内部自洽。

`frame_spec_check.py` 用例：正常帧 / 截断帧 / 帧头不足 / 未知类型 / 超大声明长度 /
0x14 顶层是对象而非数组 / 顶层是数字 / 空数组 / 缺 key / 多余 key / x 是小数 /
x 是整数值浮点 / 越界的 x·weight·size·rotation·yaw·pitch / **负 rotation** /
颜色格式错 / durationMs 非正 / **12 条逐字段变异用例**（证明断言不是恒真）+
真实 292 帧关键帧语料整批过 + 语料变异被拒。实测 **8 条被接受 / 35 条被拒**。

---

## 6. ⚠️ 哪些步骤**本机未验证**

| 项 | 状态 | 怎么验 |
|---|---|---|
| `xcodegen generate` 能否生成工程 | ❌ **本机未验证**（无 XcodeGen） | Mac 上跑 §2.1；CI `build` job |
| `xcodebuild ... build` 能否编过 | ❌ **本机未验证**（无 Xcode） | CI `build` job |
| 手写 pbxproj 能否被 Xcode 打开 | ❌ **本机未验证** | Mac 上双击；不行就用 `xcodegen generate` |
| `swift test` 91 个测试是否全过 | ❌ **本机未验证**（无 Swift） | CI `test` job；Mac 上跑 §3 |
| Swift 代码本身能否编译 | ❌ **本机未验证** | 同上 |
| App Icon 流水线（rsvg/sips/actool/iconutil） | ❌ **本机未验证** | CI `app-icon` job；本地复现见 §4 |
| 协议规则的**行为**是否与 Swift 侧一致 | ⚠️ **部分验证**：Python 侧按同一套规则实现并跑通 42 条用例，但**两份实现各自独立**，不是同一份代码 | CI 两个 job 都跑 |
| Live Activity 在真机的表现 | ❌ 未验证 | 真机（`docs/research/58` §11 待验证项 5） |
| `JSONSerialization` 对整数/浮点的类型保持 | ❌ 未验证（依赖 Foundation 行为） | 单测 `testJSONSerializationPreservesIntegerTypes` 在 macOS CI 上守门 |

---

## 7. 已知口径差异（**公开订正**，不在本仓库擅自改文档）

> 本表里的第 1–7 条是本工程在实现过程中**回源核对**时发现的口径冲突。
> `docs/` 属于他人所有权范围，本工程**只订正代码、不改文档**，冲突在此公开登记。

| # | 差异 | 本工程的处理 |
|---|---|---|
| 1 | `docs/spec/03` §2.2 小节标题写「消息类型表（**24** 个）」，**表里实际列了 25 项**（0x01–0x1B 去掉 0x08 / 0x0F） | **以表内容为准（25 项）**；`MsgType` 与单测都按 25 写，校验脚本会打 NOTE |
| 2 | `docs/spec/03` §4.1 的六态 vs `docs/research/58` §3 的六态（后者注明引自前者，但枚举不同） | `ConnectionState` **以 03 号 §4.1 为准**，58 号 那组记在文件头备查 |
| 3 | Live Activity 紧凑态：`docs/spec/01` §3 元素 10 + `DESIGN.md` §9 + `docs/research/19` F32 说「零文字」，`docs/research/58` §5 说「状态词 ✅ 放」 | **以"紧凑态零文字"为准**（多数文档一致）；展开态是否带一句话未裁决 ⇒ `ContentState` **不含正文字段** |
| 4 | 动效曲线：`docs/spec/02` §3.2 **禁止** `Animation.timingCurve`、要求两条 spring；原型 18 用的是两条 CSS cubic-bezier | ⭐ **已落地**：`Motion.swift` 用 3 档 `easeOut`/`easeInOut`（0.15 / 0.30 / 0.40 s），**不用 spring**（spring 难保证不 overshoot）；门禁在 DesignSystem 内也禁 `.spring(` |
| 5 | `rotation` 范围：`docs/research/53` §3.2 写 `0…3600`，但同文件情绪表有负值（Sad = −400） | **以 `docs/spec/06` §4.1/§4.2 的 schema 为准：`0…3600`**，负角拒收 |
| 6 | **`docs/spec/06` §5.1 表注的算术笔误**：写「用 **3560** 表达 −40°」—— 3560（0.1°）= 356° = **−4°**，不是 −40° | **按意图实现：`3600 − 400 = 3200`**（0.1° 单位下相减）。`docs/spec/06` 非本仓库所有权 ⇒ 不擅自改，公开订正 |
| 7 | `docs/spec/03` §2.5.3 的 0x14 示例里 `pitchServo.angle = -100`，**落在固件俯仰限位 [30, 870] 之外** | 解码器**严格拒收**越限角度（固件会自行限幅），并在该文件注释里标出这个矛盾 |
| 8 | `docs/spec/06` §1.3：**0x03 的 x/y 必须同时是 int**（缺一个 ⇒ 位置整体不生效），**0x14 的 x/y 各自独立** | 校验器对两条通道都判"成对"，**故意比固件严**（固件在 0x14 下会"丢掉一个、保留另一个"，我们宁可拒收整帧）——已在 `JSONSchema.swift` 注明 |

### 7.1 与 `docs/spec/07`（待拍板清单）的对齐

| 07 号要求 | 本工程 |
|---|---|
| §5.1 视觉 token 集中 + 多方案可切换（2026-10-25 升级后的机制） | ✅ `DesignSystem` 6 个文件承载全部 token；**DesignSystem 之外出现视觉字面量即 FAIL**（`validate_project.py` 强制） |
| §5.1「所有颜色/字号/圆角/间距/动效曲线**集中在 DesignSystem**」 | ✅ 拆成 6 个文件（Tokens/Theme/Typography/Motion/Shapes/Glass），但**集中在 DesignSystem 目录**内，且由门禁强制「目录外不许出现视觉字面量」⇒ 换方案仍只改这一个目录 |
| §3.1b 4 套方案 token 结构（2026-10-25 拍板） | ✅ `ThemeChoice` 4 个 case + 4 个 `ThemePalette` 实现，切换点收敛在一个 enum；深浅是**方案属性**（`isDarkBased`）不是正交维度 |
| §5.2 渲染器只吃参数、不长设计 | ✅ 参数语义与几何公式全在 `CoreProtocol`（`AvatarGeometry`），`Features/Stack/PosturePreview.swift` 只有 TODO |
| §5.3 视觉无关的测试先写先跑 | ✅ 协议编解码/限位/参数语义/帧结构/脸几何 91 个测试，**不含任何视觉断言** |
| §3.0 iOS 原生度（原生 Tab Bar + 导航栈 / Inset Grouped / SF Symbols / sensory feedback） | ✅ `RootScene` 用原生 `TabView`；⭐ **2026-10-25 第二次 IA 后**：两个 Tab 改为**控制 / 设置**，对话不再是 Tab（降为二级页，路由待实现）⇒ 独立 `WindowGroup` 设置场景已移除 |

---

## 8. 隐私与协议红线（写代码时别踩）

- `ArchiveStore` **只读本地**：协议里**故意没有**同步/上传方法；目录设了 `isExcludedFromBackup`
- `CloudGateway` 是**唯一**允许发起网络请求的地方 —— **本工程目前没有网络层**
- `CoreProtocol` **不依赖任何 target**（`docs/research/58` §2）
- 未知 JSON key 在固件侧**静默忽略** ⇒ 本地 schema 校验**故意比固件严**
- Live Activity **不放对话正文**；紧凑态**只有图形没有文字**
- `AgentStage`（关系阶段）**不上 UI**（不做积分 / 等级 / 进度环）
