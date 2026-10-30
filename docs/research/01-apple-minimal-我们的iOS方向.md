# 01 · apple-minimal：我们的 iOS 方向（概念稿精读报告）

> 来源：`D:\jss18\AI\StackChan\output\design\stackchan-concepts-20260720/` 下 4 份 apple-minimal 概念稿
> （`apple-minimal-companion-v1` / `apple-minimal-launcher-companion-v1` / `apple-minimal-launcher-companion-v2-pink-cute` / `apple-minimal-photos-v1`），逐份精读 HTML 源码 + 配套 PNG。
> 状态：完成（含第 11 节开源可复用方案调研）。

---

## 0. 结论速览（先读这段）

**这 4 份稿子全部是机器人本机 320×240 屏幕的概念稿，不是 iOS App 稿。** 但它们的视觉语言是完整、可提炼、可复用的。关键判断：

1. **设计语言已成型，尺度未成型。** 排版规则、圆角梯度、阴影梯度、触控目标（44×44）、胶囊按钮、分页指示器、玻璃拟态，全部已经是 Apple 的标准语汇；但所有数值是**设备像素**，直接搬到 iPhone 会整体偏小一圈。
2. **色彩体系目前有三套并存且未收敛**：中性 Apple 灰阶（`#f5f5f7`/`#1d1d1f`/`#737378`）、珊瑚红强调色（`#ff6b78` / `#ff5f6d` 两个近似值）、v2 浅粉可爱色板（`#fbeef3` 家族）。必须先抽 token 再画稿。
3. **v2 已经证明"粉彩可爱"是方向**（把冷灰换成暖粉、把黑按钮换成粉按钮、把照片换成纯 CSS 绘制的吉祥物），但只换了表面色，没有换结构，也没有做全局暖化。
4. **可直接复用的开源资源多，够用**：Apple 官方 Figma/SF Symbols 资源、Style Dictionary（token→代码）、SwiftGen（token→Swift）、Infinite Red iOS Style Guide、Phosphor/Lucide 图标。需要自造的只有"小栈"吉祥物本身。

---

## 1. 页面结构

### 1.0 先厘清：这 4 份稿子是什么尺度

| 稿子 | 画布 | 定位 |
|---|---|---|
| companion-v1 | 320×240 | 设备屏 · 待机陪伴页 |
| launcher-companion-v1 | 320×240 | 设备屏 · 应用启动器第 1 页（共 8 个应用）|
| launcher-companion-v2-pink-cute | 320×240 | 同上，浅粉可爱版 |
| photos-v1 | 320×240 | 设备屏 · 相册浏览页 |

四份全部 `width:320px; height:240px; overflow:hidden` + `viewport width=320, initial-scale=1`，即**固定 1:1 渲染设备屏，无任何自适应**。

> **对 iOS 的含义**：这批稿子定义的是"设计语言"，不是"iOS 布局"。迁移到 iPhone（390×844pt）时，布局必须重排，但令牌（颜色/圆角/阴影/控件尺寸比例）可以直接继承。

### 1.1 companion-v1（陪伴页）

```
main.screen  320×240  bg #f5f5f7
├─ section.face-stage   320×168  bg #050506   overflow:hidden
│   ├─ img.face          abs left45 top-3  230×173  object-fit:fill   ← 小栈表情大图
│   ├─ div.mode          abs top13 left15   「小栈 · 陪伴」  11px/600
│   └─ div.status        abs top13 right15  ● +「在线」  10px/500
└─ section.info         h72  padding 12px 70px 10px 17px  bg #f5f5f7
    ├─ h1.title          「依婵，我在」        18px/700/24
    ├─ p.subtitle        「轻触屏幕，我会回应你」 11px/500/17
    └─ div.touch         abs right15 top14  44×44 圆形 FAB  #ff6b78
        └─ span.touch-ring  16×16 白描边圆环 + 内实心点
```

- **左右不对称**：`face` 图片 left 45 / 宽 230 → 右边距 45，**居中**；但 stage 上文字 left 15 / right 15 对称。
- **图文区比例**：168 : 72 = **70% : 30%**。
- **FAB 定位**：`right:15 top:14` 相对 `.info` → 全局坐标 x 261–305、y 182–226，落在右下角，且**避开**文字块（`.info` 右侧 padding 预留了 70px）。
- **留白呼吸**：`.info` 顶部 padding 12px，文字块与 FAB 顶端几乎齐平（标题顶 180 vs FAB 顶 182）。

### 1.2 launcher-companion-v1 / v2（启动器）

```
main.screen  320×240  bg #f5f5f7 (v1) / #fbeef3 (v2)
├─ header.topbar        h42  padding 10px 15px 0  flex space-between align-flex-start
│   ├─ div.brand        「小栈」  16px/750/22  ls -.2px
│   └─ div.online       ● +「在线」 10px/600/22  右对齐
├─ section.content      grid 116px / 1fr   gap 18px   padding 18px 16px 0 18px
│   ├─ div.app-art      116×116  圆角25(v1)/28(v2)  ← 应用图标卡
│   │   └─ (v1) img 124×93 abs left-4 top15
│   │   └─ (v2) 纯 CSS 吉祥物：sparkle ✦ + mascot + face-panel + eye×2 + cheek×2 + mouth + hand×2 + heart
│   └─ div.copy         padding-top 1px
│       ├─ p.index      「01 / 08」  10px/750/14  ls .3px  ← 强调色
│       ├─ h1.title     「陪伴」    27px/760/34   ls -.8px
│       ├─ p.subtitle   「听你说话 / 陪你一会」 11px/500/17  ← 两行
│       └─ div.open     132×44  圆角22 胶囊主按钮  padding 0 15px 0 17px
│           ├─ span「进入」  12px/650/16
│           └─ span.arrow「→」 Arial 18px/400
└─ div.pager            abs bottom10  320×10  flex center  gap 5
    └─ 8× span.dot       4×4 圆角2 ；.dot.active 宽14
```

- **左右不对称是刻意的**：content 左 padding 18px、右 padding 16px（差 2px 光学补偿）。
- **v1 与 v2 的 DOM 结构完全相同**，只有 CSS 变量与 `.app-art` 内部实现不同（见第 8 节）。

### 1.3 photos-v1（相册页）

```
main.screen  320×240  bg #050506  overflow hidden
├─ img.photo            abs inset0  320×240  object-fit:fill   ← 全出血照片
├─ div.shade-top        abs top0  h70   linear-gradient(180deg, rgba(0,0,0,.52) → transparent)
├─ div.shade-bottom     abs bottom0 h58  linear-gradient(0deg,  rgba(0,0,0,.48) → transparent)
├─ div.back             abs top4 left4  44×44 grid center
│   └─ span.back-mark   32×32 圆角50%  bg rgba(20,20,22,.48)  border 1px rgba(255,255,255,.22)
│                        白「‹」Arial 25px/300/28  backdrop-filter blur(12px)
├─ div.label            abs top15 left50  「依婵相册」 13px/650/18  白96%  text-shadow
├─ div.count            abs top12 right13  min-w44 h25 圆角13  玻璃chip  「1 / 3」
└─ div.hint             abs bottom10 居中  h26 圆角13  bg rgba(245,245,247,.88)  blur(12px)
    ├─ span.tap-dot     6×6 #ff6b78 + 3px 光晕
    └─ span「轻触切换」  10px/600/14
```

- **这是唯一使用玻璃拟态（backdrop-filter）的稿子**，也是唯一"照片全出血"的稿子。
- 顶部 70px 渐变遮罩专门为 `.label`/`.back`/`.count` 提供可读性；底部 58px 遮罩为 `.hint` 提供对比。

### 1.4 四稿共性结构模板

| 层 | 角色 | 出现于 |
|---|---|---|
| L1 | 全出血视觉层（表情图 / 图标卡 / 照片）| companion、launcher、photos |
| L2 | 顶部/底部浮动玻璃控件层（backdrop-filter）| photos（launcher 无）|
| L3 | 标题区（大标题 + 副标题 + 索引号）| launcher、companion |
| L4 | 主行动控件（胶囊按钮 / 圆形 FAB）| launcher、companion |
| L5 | 分页指示器（胶囊点阵）| launcher |
| L6 | 底部提示条（chip）| photos |

---

## 2. 视觉令牌

### 2.1 颜色

**中性 / Apple 系统灰阶**

| 值 | 名称建议 | 出现位置 | 判定 |
|---|---|---|---|
| `#f5f5f7` | `bg.canvas` | companion body/screen/info、launcher body/screen、photos hint 底（rgba .88）| **设计令牌**（4 处）|
| `#1d1d1f` | `text.primary` / `bg.inverse` | companion body、launcher body、photos hint 文字 | **设计令牌**（3 处）|
| `#737378` | `text.secondary` | companion subtitle、launcher online、launcher subtitle | **设计令牌**（3 处）|
| `#d1d1d6` | `fill.track` | launcher v1 未激活分页点 | 一次性（v2 换成 `#dfc7cf`）|
| `#050506` | `bg.stage` | companion face-stage、launcher app-art、photos screen | **设计令牌**（3 处）|
| `#ffffff` | `text.onDark` / `icon.onDark` | launcher open 文字、photos 文字、companion touch-ring | **设计令牌** |

**强调色（珊瑚红系）**

| 值 | 出现位置 | 判定 |
|---|---|---|
| `#ff6b78` | companion FAB 底、photos tap-dot | 令牌 A |
| `#ff5f6d` | launcher index 文字、launcher active 分页点 | 令牌 B（与 A 仅差 5/6，肉眼几乎不可分）|
| `rgba(255,107,120,.20)` | companion FAB 阴影 | 与令牌 A 配对 |
| `rgba(255,107,120,.16)` | photos tap-dot 光晕 | 与令牌 A 配对 |

**状态色（在线绿）**

| 值 | 出现位置 | 判定 |
|---|---|---|
| `#6bd89e` | companion status 点 | 令牌 A |
| `#44c783` | launcher online 点 | 令牌 B（与 A 明显不同，偏蓝绿）|
| `rgba(107,216,158,.12)` / `rgba(68,199,131,.12)` | 对应光晕 | 与各自令牌配对 |

**玻璃 / 遮罩（photos 专属）**

| 值 | 用途 |
|---|---|
| `rgba(20,20,22,.48)` | 玻璃 chip 底（back-mark、count）|
| `rgba(255,255,255,.22)` | 玻璃 chip 1px 描边 |
| `rgba(245,245,247,.88)` | 浅色玻璃 chip 底（hint）|
| `rgba(0,0,0,.52)` → `rgba(0,0,0,0)` | 顶部渐变遮罩 |
| `rgba(0,0,0,.48)` → `rgba(0,0,0,0)` | 底部渐变遮罩 |
| `rgba(0,0,0,.08)` | 深色卡 1px 描边（launcher app-art）|
| `rgba(0,0,0,.32)` | 相册标题文字投影 |

**浅粉可爱色板（v2 专属）**

| 值 | 用途 | 判定 |
|---|---|---|
| `#fbeef3` | 画布底 | 令牌（v2 底色）|
| `#35262d` | 主文字（暖黑）| 令牌 |
| `#806f76` | 次文字（暖灰）| 令牌 |
| `#fffafb` | 图标卡底 | 令牌 |
| `#f3d7e0` | 图标卡描边 | 令牌 |
| `#f8dce5` | 吉祥物身体 / 手 | 令牌 |
| `#edbdcc` | 吉祥物描边 | 令牌 |
| `#fffdf8` | 面部面板底 | 一次性 |
| `rgba(104,70,79,.08)` | 面部面板描边 | 一次性 |
| `#44343a` | 眼睛 / 嘴 | 令牌 |
| `#f58aa5` | 腮红（opacity .72）| 令牌 |
| `#f16f91` | 爱心 | 令牌 |
| `#eda7ba` | 闪光 ✦ | 一次性 |
| `#d94f78` | index 文字 | 一次性（与 `#ef6e91` 同色系但更深）|
| `#ef6e91` | 主按钮底 + active 分页点 | 令牌 |
| `#dfc7cf` | 未激活分页点 | 令牌 |
| `rgba(125,70,88,.11)` / `rgba(99,55,68,.12)` / `rgba(241,111,145,.20)` / `rgba(239,110,145,.18)` | 卡片/吉祥物/爱心/按钮阴影 | 与各自表面同色系 |

> **关键观察**：v1 内部就已经有两组"几乎相同但不相等"的强调色与状态色（`#ff6b78`/`#ff5f6d`、`#6bd89e`/`#44c783`）。这不是设计语言，是**未收敛**。必须以 token 形式强行收口。

### 2.2 字号 / 行高

| px | 行高 | 行高比 | 字重 | 用途 |
|---|---|---|---|---|
| 10 | 14 | 1.40 | 600 | index、hint、online |
| 10 | 16 | 1.60 | 500 | status（在线）|
| 11 | 16 | 1.45 | 600 | mode（「小栈 · 陪伴」）|
| 11 | 17 | 1.55 | 500 | subtitle、count |
| 12 | 16 | 1.33 | 650 | 主按钮文字「进入」|
| 13 | 18 | 1.38 | 650 | 相册标题 |
| 16 | 22 | 1.375 | 750 | brand「小栈」|
| 18 | 24 | 1.33 | 700 | companion 大标题 |
| 27 | 34 | 1.26 | 760 | launcher 大标题 |
| 17 | 17 | 1.00 | 400 | ✦ 符号（Arial）|
| 18 | 18 | 1.00 | 400 | → 箭头（Arial）|
| 25 | 28 | 1.12 | 300 | ‹ 返回（Arial）|

**规律**：行高比随字号增大而收紧（1.60 → 1.26），这是 Apple 排版的标准做法；小字给松行距、大字给紧行距。

### 2.3 字重

出现过的字重：`300 / 400 / 500 / 600 / 650 / 700 / 750 / 760`。

> ⚠️ **650 / 750 / 760 不是任何主流中文字体的真实字重**。`PingFang SC` 实际只有 Ultralight(100)…Semibold(600)，`SF Pro` 到 Black(900)。浏览器在 macOS 上会对 650/750/760 做**合成加粗或回退到 700**，因此设计稿在 Mac 上和 Win 上呈现不同，迁到 iOS 后 750/760 会落到 700。必须在 token 层直接归一。

### 2.4 圆角

| 值 | 用途 | 规律 |
|---|---|---|
| 2px | 分页点（4×4）| 胶囊 |
| 4px | 爱心旋转方块（20×20）| 小装饰 |
| 5px | 眼睛（8×11）| 竖椭圆近似 |
| 12px（仅下两角）| 嘴（14×8，`0 0 12px 12px`）| 弧线 |
| 13px | 玻璃 chip（h 25/26）| ≈ h/2 |
| 16px | 面部面板（52×39）| ≈ w/3.2 |
| 22px | 主按钮胶囊（h 44）| = h/2 |
| 23px | 吉祥物身体（72×63）| ≈ w/3.1 |
| 25px | app-art 卡（116×116）v1 | ≈ w/4.6（21.6%）|
| 28px | app-art 卡（116×116）v2 | ≈ w/4.1（24.1%）|
| 50% / 999px | 圆形（点、FAB、back-mark）| 全圆 |

**梯度规律**：控件高度 44 → 圆角 22（胶囊）；方形卡 116 → 圆角 25–28（接近 iOS App Icon 的 22.4% 连续圆角，v2 更接近）。

### 2.5 阴影

| 值 | 用途 |
|---|---|
| `0 0 0 3px rgba(107,216,158,.12)` | 状态点光晕 |
| `0 0 0 3px rgba(68,199,131,.12)` | 状态点光晕（v2 同）|
| `0 0 0 3px rgba(255,107,120,.16)` | tap 点光晕 |
| `0 4px 8px rgba(241,111,145,.20)` | 爱心 |
| `0 4px 12px rgba(255,107,120,.20)` | FAB |
| `0 5px 10px rgba(99,55,68,.12)` | 吉祥物 |
| `0 6px 14px rgba(239,110,145,.18)` | 粉色主按钮 |
| `0 8px 20px rgba(0,0,0,.10)` | 深色图标卡 |
| `0 9px 22px rgba(125,70,88,.11)` | 粉色图标卡 |
| `0 1px 6px rgba(0,0,0,.32)` | 相册标题文字投影 |

**规律**：
- 阴影**一律带色**（与表面同色系），唯一例外是照片上的文字投影用纯黑。
- 层次：微元素 8–10 blur / 按钮 12–14 blur / 卡片 20–22 blur。
- 透明度统一在 .10–.22 之间，从不用更重。

### 2.6 边框

| 值 | 用途 |
|---|---|
| `1px solid rgba(0,0,0,.08)` | 深色卡片描边 |
| `1px solid #f3d7e0` | 粉色卡片描边 |
| `1px solid #edbdcc` | 吉祥物描边 |
| `1px solid rgba(104,70,79,.08)` | 面部面板描边 |
| `1px solid rgba(255,255,255,.22)` | 玻璃 chip 描边 |
| `2px solid #fff` | FAB 内环 |
| `2px solid #44343a` | 嘴（border-bottom）|

**规律**：描边一律 1px、极低不透明度（同色系深色），只在需要"贴在浅底上"的元素上出现；2px 只用于图标本身。

### 2.7 间距

出现过的间距/内边距值：`3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 25, 28, 70`（另有 `55 / 78` 属吉祥物内部绝对定位，不计入节奏体系）。

关键节奏值：

| 值 | 含义 |
|---|---|
| **15px** | 屏幕左右基准边距（topbar padding、companion mode/status、photos count）|
| **16 / 18px** | content 左右边距（16 右 / 18 左，光学不对称）|
| **18px** | 栅格列间距 gap，同时是 content 上 padding |
| **10px** | 底部呼吸（pager bottom、companion info 底部 padding、photos hint bottom）|
| **12px** | 卡片内边距 |
| **5px** | 图标与文字 gap、pager dot gap |
| **3px** | 光晕环宽度、进度条类 |
| **9 / 11 / 13px** | 半圆 chip 的水平内边距（h/2 ± 1）|

---

## 3. 布局与栅格

**全部固定 px，零自适应。** 没有一处 `%`、`vw/vh`、`clamp()`、`min()/max()`、`calc()` 或媒体查询。

| 项 | 值 | 占比 |
|---|---|---|
| 画布 | 320×240 | — |
| launcher 图标卡 | 116×116 | 宽 **36.3%** |
| launcher 文案列 | 152px（= 1fr）| 宽 **47.5%** |
| 列间距 | 18px | 5.6% |
| 左 / 右边距 | 18 / 16px | 5.6% / 5.0% |
| topbar 高 | 42px | 17.5% |
| content 顶偏移 | 18px | — |
| pager 高 | 10px，距底 10px | — |

**栅格结论**：这是**单列双栏**布局（左图标卡 / 右文案），不是可扩展栅格。栅格单元 = 116px 图标 + 18px 间距 + 剩余文字列。

**留白节奏**：
- 顶（topbar 10px 内边距 → 18px content 偏移）→ 中（内容）→ 底（10px pager 呼吸）
- 整体是**上紧下松**：顶部 padding 10px，底部 10px + 10px，视觉重心偏上。
- launcher 的 116px 图标卡顶边（y=60）与文案首行「01 / 08」顶边（y=61）**齐平**，是刻意的网格对齐。
- companion 的 FAB 顶（y=182）与标题行顶（y=180）几乎齐平，同样是刻意的。

**迁移到 iOS 的栅格建议**：保留「图标卡 + 文案」的比例关系，但把 116px 图标卡放大到 iOS 尺寸（建议 88–104pt），文案列改用弹性布局；`15/16/18` 的边距直接升到 iOS 的 `16 / 20`。

---

## 4. 字体与排版

**字体栈**：`"Microsoft YaHei UI", "PingFang SC", sans-serif`

> 注意：**Microsoft YaHei UI 排在 PingFang SC 前面**，这是 Windows 渲染环境留下的产物。设计稿的真正意图字体是 **PingFang SC**（简体中文字体，Apple 官方）。迁到 iOS 时应改为 `PingFang SC` 优先（iOS 自带），英文/数字用 **SF Pro**。

**符号字体分裂**：箭头 `→`、返回 `‹`、闪光 `✦` 全部显式指定 `font-family: Arial, sans-serif`——说明设计者意识到中文字体里没有这些字形，但 Arial 的字形在不同系统/版本上并不一致（`✦` 在 Arial 里其实是 fallback 字形）。**这是需要替换成矢量图标的信号。**

**字距（letter-spacing）**：

| 值 | 应用对象 | 相对值 |
|---|---|---|
| `-.2px` | brand 16px、companion title 18px | -1.25% |
| `-.8px` | launcher title 27px | -2.96% |
| `.3px` | index 10px | +3% |
| `0` | mode、subtitle、其余全部 | — |

**规律**：**中文大标题收紧字距（负），小号标签放开字距（正）**。这是 Apple 中文排版规范的做法：中文方块字在大字号下需要收紧才不会散架，而小字号加一点字距提升可读性。

**行高比**（见 2.2）：小字 1.55–1.60，大字 1.26–1.33，逐级收紧。

---

## 5. 色彩策略

### 5.1 强调色的用法规则

强调色（v1 珊瑚红 `#ff6b78`/`#ff5f6d`，v2 玫粉 `#ef6e91`）在这套稿里的用法高度一致，只有三种用法：

1. **主行动按钮底色**（companion FAB、launcher「进入」胶囊）——大面积但面积很小（44×44 / 132×44）。
2. **小型指示性文字**（launcher「01 / 08」索引号）——极小字号 + 强调色。
3. **状态光点 / 激活分页点**（photos tap-dot、launcher active dot）——直径 6px 或 14×4px。

**没有大面积铺色**。整套稿子的彩色面积占比 < 5%。这是 Apple 极简的核心：**颜色是信号，不是装饰**。

### 5.2 深色/浅色的对位关系

| 稿子 | 画面底 | 主体 | 文字 |
|---|---|---|---|
| companion-v1 | 上 70% 近黑 `#050506` + 下 30% 浅灰 `#f5f5f7` | 深色舞台上放表情 | 浅色区用 `#1d1d1f` |
| launcher-v1 | 全浅灰 `#f5f5f7` | 深色图标卡（`#050506`）作为唯一暗块 | `#1d1d1f` / `#737378` |
| launcher-v2 | 全浅粉 `#fbeef3` | 浅粉图标卡（`#fffafb`），主体靠描边+阴影分离 | 暖黑 `#35262d` / 暖灰 `#806f76` |
| photos-v1 | 全黑 + 全出血照片 | 照片 | 白色 + 玻璃层 |

> **launcher v1 的暗色卡 vs v2 的亮色卡**是整个演进里最关键的一步：v1 用"一个黑方块 + 白边描边"表达科技感，v2 用"白卡 + 粉描边 + 柔和阴影"表达可爱感，同时把整个画布从冷灰换成暖粉。

### 5.3 状态色

- **在线 = 绿点 + 光晕环**（6px 圆点 + `0 0 0 3px rgba(绿,.12)`）。两稿的绿值不同（`#6bd89e` / `#44c783`），需收敛为一个。
- **离线/异常状态在这批稿里完全缺失**——只有"在线"一种状态。这是需要补的设计空白。
- 没有使用红/黄/橙等警示色。珊瑚红只承担"行动"语义，**不兼任错误语义**（这其实是好的设计决策，避免语义混淆）。

### 5.4 粉彩色板（v2）的色相关系

v2 的粉是**同色相多明度分层**，不是多个色相：

```
#fbeef3 (底)  →  #fffafb (卡面, 更亮)
              →  #f3d7e0 (卡描边, 更深)
              →  #f8dce5 (吉祥物身体)
              →  #edbdcc (吉祥物描边)
              →  #eda7ba (闪光)
              →  #f58aa5 (腮红)
              →  #f16f91 (爱心)
              →  #ef6e91 (主按钮)
              →  #d94f78 (强调文字, 最深)
```
全部围绕 **330°–350° 玫红**一个色相展开，靠明度+饱和度分层。这是极其克制的粉彩方案，比"多种粉"高级得多。

---

## 6. 图标与插画风格

### 6.1 图标

**几乎没有图标系统。** 全套稿子只有 4 个符号：

| 符号 | 实现 | 问题 |
|---|---|---|
| `→` 进入箭头 | Arial 文字 18px | 字形随系统变化 |
| `‹` 返回 | Arial 文字 25px/300 | 同上，且不是标准 chevron 形状 |
| `✦` 闪光 | Arial 文字 17px | fallback 字形，跨平台不一致 |
| 圆形点 | CSS `border-radius:50%` | 唯一"正经"图形 |

**结论**：这套稿子目前是"无图标设计"，所有图标位都是占位。落地时必须补一套**线性图标系统**（SF Symbols 或 Phosphor/Lucide），否则 iOS App 会显得毛糙。

### 6.2 吉祥物「小栈」的画法

**两条路线并存：**

**路线 A —— 位图表情（`face_gummy_soft.png` 等 16 张）**

- 资源尺寸 320×240（整屏），透明背景 PNG，**只有五官，没有身体**。
- 眼睛：巨大的**圆形眼眶**（奶白/米色描边环 `#f5e6d0` 系），内含深色瞳孔 + 白色高光点 —— 典型的"gummy / 果冻"质感（半透明糖果感来自这圈厚描边）。
- 眉毛/上睑：眼睛上方一条细弧线（表达柔和）。
- 腮红：扁椭圆（宽>高），蜜桃粉 `#f5b8a0` 系，**不对称感轻微**（左低右高 → 表情更灵动）。
- 嘴：一道细弧线 smile，线宽与眼睛描边一致。
- **表情系统共 16 个**：`curious / happy / kiss / nuzzle / peaceful / proud / shy / sleepy / soft / sparkle / starry / surprised / tender / wink / wronged / yawn`。
- 情绪覆盖极广（含负面：wronged / surprised / yawn），说明"表情不只是装饰，是产品核心能力"。
- 渲染方式：companion 里 230×173 铺在上方舞台（几乎等比，因为源 4:3 ≈ 230/173）；launcher 里 124×93 裁切进图标卡，**只露出面部中段**。

**路线 B —— 纯 CSS 绘制的吉祥物（v2 图标卡）**

- 结构：`mascot`（72×63 圆角矩形身体）→ `face-panel`（52×39 圆角矩形，"脸"是一块独立面板）→ 眼睛×2 / 腮红×2 / 嘴；外挂 `hand`×2（15×15 圆）与 `heart`（20×20 旋转 45° 方块 + 两个伪元素圆 = 经典 CSS 心形）。
- 眼睛：8×11 竖椭圆纯色 `#44343a` + 3×3 白色高光（top2 left2）——**这是"日系/韩系扁平萌系"标准画法**。
- 腮红：9×4 扁椭圆 `#f58aa5`，`opacity: .72`（**半透明叠色**，这是让扁平画有层次的关键手法）。
- 嘴：14×8，只有 `border-bottom: 2px` + `border-radius: 0 0 12px 12px` = 用边框弧画出 U 型笑。
- 闪光 `✦` 放在右上角 (top11 right13) 作装饰。
- 比例：身体 72×63 ≈ 1.14:1（**近乎正方略宽**，可爱感来自"头大身小"）。

**路线 A vs B 的本质差别**：

| | 位图表情（路线 A）| CSS 吉祥物（路线 B）|
|---|---|---|
| 风格 | 半透明糖果质感、写实光影 | 扁平纯色块、日系萌系 |
| 情绪表达 | 强（16 种）| 弱（1 种，静态）|
| 制作成本 | 需要画师出图 | 代码可调 |
| 传达的气质 | 温柔、拟物、有生命感 | 甜、软、社交感强 |
| 在产品中的角色 | **机器人本机屏幕上的表情** | **App/启动器里的吉祥物形象** |

> 这其实**不是冲突，而是分工**：机器人屏用高情绪密度的表情图；iOS App 侧用简洁的扁平吉祥物做品牌标识与空态插画。落地时应该把路线 B 的画法**系统化**成一套完整的扁平吉祥物规范（正面/侧面/多种情绪），并与路线 A 的表情命名对齐。

---

## 7. 交互线索

从 HTML 里能读出的交互信息：

| 线索 | 证据 | 推断 |
|---|---|---|
| **分页/滑动切换** | launcher 有 8 个 dot，active 是 14×4 胶囊，aria-label="第 1 个软件，共 8 个"；index 显示「01 / 08」| 启动器是**可横向滑动的分页**，8 个应用分页展示（推测每页 1 个，或 1 页 1 个大卡）。当前实现的 116+152 双栏是**单页单应用**的形态 |
| **轻触响应** | companion 副标题「轻触屏幕，我会回应你」+ 44×44 圆形 FAB；photos hint「轻触切换」+ 红点 | **触摸是主要交互方式**（对应 M5Stack 触摸传感器），交互提示用"轻触"+红点光晕的组合 |
| **主行动按钮** | launcher 的「进入」胶囊按钮（132×44）带 → | 进入应用 |
| **返回** | photos 的 44×44 容器内 32×32 圆形玻璃按钮 `‹` | 返回上一层 |
| **状态指示** | `.dot.active` / status 圆点 | 当前项、在线状态 |
| **hover** | ❌ **完全没有**（无 `:hover` 规则）| 设备屏无指针，纯触摸 |
| **active / pressed** | ❌ 只有 `.dot.active` 表示"选中态"，**没有按下态** | 缺少按压反馈规范 |
| **focus / disabled** | ❌ 无 | 无键盘场景，无禁用态 |
| **过渡动画** | ❌ 无 `transition` / `animation` / `transform`（仅 heart 用了 rotate 静态）| **完全没有动效规范**——这是 iOS 化时最大的空缺 |
| **语义可访问性** | ✅ 有 `aria-label`（screen / touch / back / pager）| 设计者有意识做语义标注 |
| **图片替代文本** | ✅ `alt` 齐全 | 同上 |

> **结论**：这套稿子的"静态视觉"完成度不错，"交互语言"几乎为零。落地 iOS App 时，状态机（默认/按下/选中/禁用/加载）、转场动效、触觉反馈全部需要从零补齐，且必须补成规范而不是靠每个页面自由发挥。

---

## 8. v1 → v2 演进

launcher v1 → v2-pink-cute 的改动**分三层**：

### 8.1 结构层：零改动

DOM 结构、栅格（116px/18px/1fr）、所有尺寸（42px topbar、116×116 卡、132×44 按钮、44/14/4 分页点）、所有字号、字重、行高、字距——**一个数值都没动**。

> 这是很重要的信号：**v2 不是重新设计，是在同一套骨架上换皮**。说明布局本身是被认可的，问题出在"气质不对"。

### 8.2 色板层：整体换血

| 位置 | v1 | v2 | 变化 |
|---|---|---|---|
| 画布底 | `#f5f5f7` 冷灰 | `#fbeef3` 暖粉 | 冷 → 暖 |
| 主文字 | `#1d1d1f` 冷黑 | `#35262d` 暖黑 | 冷 → 暖 |
| 次文字 | `#737378` 冷灰 | `#806f76` 暖灰 | 冷 → 暖 |
| 图标卡底 | `#050506` 近黑 | `#fffafb` 近白粉 | **明暗反转** |
| 图标卡描边 | `rgba(0,0,0,.08)` 冷黑 | `#f3d7e0` 粉 | 冷 → 暖 |
| 图标卡圆角 | 25px | 28px | 更圆 = 更软 |
| 图标卡阴影 | `0 8px 20px rgba(0,0,0,.10)` 冷黑 | `0 9px 22px rgba(125,70,88,.11)` 玫瑰灰 | 冷 → 暖，模糊+2 |
| 索引号 | `#ff5f6d` 珊瑚红 | `#d94f78` 玫红 | 色相一致，明度更深 |
| 主按钮 | `#1d1d1f` 近黑 | `#ef6e91` 玫粉 | **主按钮从黑变粉** |
| 主按钮阴影 | 无 | `0 6px 14px rgba(239,110,145,.18)` | v1 按钮**完全没有阴影** |
| 未激活分页点 | `#d1d1d6` 冷灰 | `#dfc7cf` 暖灰粉 | 冷 → 暖 |
| 激活分页点 | `#ff5f6d` | `#ef6e91` | 与主按钮统一 |
| 在线点 | `#44c783` | `#44c783` | **未变**（唯一没动的颜色）|

### 8.3 内容层：插画从"照片"换成"绘制的吉祥物"

v1 的图标卡是**直接把设备屏的表情位图（`face_gummy_soft.png`）塞进去**，缩放裁切后是一张暗底的黑脸截图——读起来像"截图没处理好"，不像一个设计好的 App 图标。

v2 换成**手绘的扁平吉祥物**：圆润身体 + 大眼睛 + 腮红 + 微笑 + 双手 + 爱心 + 右上角闪光 ✦。

### 8.4 为什么这么改（从视觉元素推断）

1. **"截图感" → "品牌感"**：v1 图标卡里是机器人屏幕的原始像素（黑底、裁切不齐），放在启动器里像"占位图没替换"。v2 画了一个**独立的、专为 App 品牌而生的角色**，图形语言统一。
2. **"科技冷" → "陪伴暖"**：目标用户是 ENFP 女性，机器人是要"陪"的伙伴，不是冷冰冰的设备。黑底方块传达的是"硬件感"，粉底方块传达的是"朋友感"。
3. **拟人化是陪伴感的来源**：爱心 + 双手 + 腮红 + 闪光，这些是**社交符号**，比"表情截图"更直接地传达"它在对你示好"。
4. **明暗反转解决层级问题**：v1 靠一个黑块在浅灰底上制造对比；v2 靠**描边 + 柔和阴影**制造对比。后者更符合 v2 的整体"无硬对比"基调，也更接近 iOS 系统的 Material 毛玻璃质感。
5. **阴影补齐**：v1 的黑色按钮和黑色图标卡几乎"漂浮"在底上，v2 给按钮加了同色投影，浮起感一致。

### 8.5 演进路径总结

```
v1:  冷灰底 + 截图式图标 + 黑色按钮 + 珊瑚红点缀
      ↓ 换底色 / 换插画 / 换按钮色 / 补阴影 / 统一暖化
v2:  暖粉底 + 手绘吉祥物图标 + 粉色按钮 + 玫粉点缀
```

**遗留问题**（v2 未解决）：

- 在线绿点 `#44c783` 没跟着暖化，在粉底上显得突兀/偏"系统"。
- 索引号 `#d94f78` 与主按钮 `#ef6e91`、爱心 `#f16f91` 是三个不同的粉，层级不清。
- 粉底 `#fbeef3` 偏"婴儿粉"，如果要做 ENFP 成人用户的 App，可能需要**降饱和/加深**一档。
- 灰底 `#f5f5f7` 与粉底 `#fbeef3` 两套底色**没有统一的浅色模式**——浅色模式到底用哪个？必须二选一或定义 light/dark 双套。
- 冷灰版和粉版不是"同一设计的深浅两个版本"，而是**两个独立皮肤**，实际产品只能有一套（或做成可切换主题，但要有明确的 token 映射表）。

---

## 9. 可复用设计规范（Design Tokens）

### 9.1 命名原则

- 层级用 `.` 分隔：`语义.角色`（如 `text.secondary`），不写具体色值。
- 颜色按**用途**命名，不按色相命名（`accent.primary` 而不是 `pink`）——因为 v1 冷灰版和 v2 粉版共用同一套语义名。
- 尺寸用 `size.` 前缀，间距用 `space.` 前缀，圆角用 `radius.` 前缀，阴影用 `shadow.` 前缀，文字用 `type.` 前缀。
- 阴影用**层级语义**（`elevation.card`）而非 `shadow.1`，便于换肤。

### 9.2 颜色令牌

```
/* —— 中性 —— */
--bg-canvas:        #f5f5f7     /* v1 底 */
--bg-canvas-warm:   #fbeef3     /* v2 底（建议：合并为一个语义 token + 主题值）*/
--bg-stage:         #050506     /* 深色舞台 / 图标卡（v1）*/
--bg-elevated:      #ffffff     /* 卡片面 */
--bg-inverse:       #1d1d1f     /* 深色实心（v1 主按钮底）*/

/* —— 文字 —— */
--text-primary:     #1d1d1f     /* v1 */
--text-primary-warm:#35262d     /* v2 */
--text-secondary:   #737378     /* v1 */
--text-secondary-warm:#806f76   /* v2 */
--text-on-dark:     rgba(255,255,255,.96)
--text-on-dark-muted: rgba(255,255,255,.78)

/* —— 强调 —— */
--accent-primary:   #ff6b78     /* 珊瑚红 → 建议统一 */
--accent-primary-warm:#ef6e91    /* v2 玫粉 */
--accent-text:      #d94f78     /* 强调小字（v2）*/
--accent-soft:      #f8dce5     /* 吉祥物主体 / 浅底 */

 /* —— 状态 —— */
--status-online:    #44c783     /* 统一绿点 */
--status-online-glow: rgba(68,199,131,.12)
--status-idle:      #d1d1d6     /* 离线（待补）*/

/* —— 玻璃 —— */
--glass-fill:       rgba(20,20,22,.48)
--glass-border:     rgba(255,255,255,.22)
--glass-blur:       12px
--glass-light-fill: rgba(245,245,247,.88)

/* —— 粉彩色板（v2 完整梯度）—— */
--pink-050: #fffafb   --pink-100: #fffdf8   --pink-200: #fbeef3
--pink-300: #f8dce5   --pink-400: #f3d7e0   --pink-500: #edbdcc
--pink-600: #eda7ba   --pink-700: #f58aa5   --pink-800: #f16f91
--pink-900: #ef6e91   --pink-950: #d94f78
--pink-ink: #44343a   /* 吉祥物眼睛/嘴 */
```

### 9.3 排版令牌（**已按 iOS pt 换算**）

设备屏 px → iOS pt 建议 **×2**（320px 屏 → 390pt 屏 ≈ ×2.2），下表给 iOS 值：

| Token | iOS 值 | 字重 | 行高 | 用途 |
|---|---|---|---|---|
| `type.display` | 34pt | Bold(700) | 41 (1.20) | launcher 大标题（27px→27×2=54 太夸张，按 iOS 大标题标准取 34）|
| `type.title` | 22pt | Bold(700) | 28 | companion 大标题（18px）|
| `type.title3` | 20pt | Semibold(600) | 25 | brand（16px）|
| `type.body` | 15pt | Medium(500) | 22 | 副标题（11px）|
| `type.callout` | 15pt | Semibold(600) | 20 | 主按钮文字（12px）|
| `type.caption` | 12pt | Medium(500) | 16 | index / hint（10px）|
| `type.caption2` | 12pt | Semibold(600) | 16 | mode / online（10-11px）|
| `type.micro` | 11pt | Medium(500) | 14 | 计数（1 / 3）|

字距：

| Token | 值 | 用途 |
|---|---|---|
| `tracking.display` | -1.0pt | 大标题（-.8px ×2）|
| `tracking.title` | -0.4pt | 中标题（-.2px ×2）|
| `tracking.caps` | +0.6pt | index 小字（.3px ×2）|
| `tracking.none` | 0 | 其余 |

> **字重归一建议**：650/750/760 → 统一到 `600 / 700`，因为 PingFang SC 只到 Semibold(600)。SwiftUI: `.semibold` / `.bold`。

### 9.4 尺寸 / 圆角 / 间距 / 阴影令牌

```
/* —— 尺寸 —— */
--size-touch-min:     44        /* 触控目标下限（iOS HIG），已在稿中出现 2 次 */
--size-icon-art:      116       /* 启动器图标卡（设备屏）→ iOS 建议 88 */
--size-button-h:      44       /* 主按钮高 */
--size-fab:           44       /* 圆形按钮直径 */
--size-dot:           6        /* 状态点直径 */
--size-dot-track:     4        /* 分页点直径 */
--size-dot-active-w:  14       /* 激活分页点宽 */

/* —— 圆角 —— */
--radius-chip:    13            /* h25/26 胶囊 */
--radius-button:  22            /* h44 胶囊 */
--radius-card:    28            /* 图标卡（v2）*/
--radius-panel:   16
--radius-mascot:  23
--radius-circle:  999
--radius-mood:    12            /* 嘴弧 */

/* —— 间距（iOS pt，×2）—— */
--space-2:   4      --space-3:   6      --space-4:   8
--space-5:   10     --space-6:   12     --space-8:   16
--space-9:   18     --space-10:  20     --space-12:  24
--gutter-screen: 16   /* iOS 屏幕左右边距（设备稿用 15-18）*/
--gutter-column: 18   /* 栅格列间距 */
--space-bottom-safe: 10

/* —— 阴影 —— */
--shadow-1: 0 4px 8px rgba(0,0,0,.10)        /* 微元素 */
--shadow-2: 0 4px 12px rgba(0,0,0,.10)       /* 按钮 */
--shadow-3: 0 8px 20px rgba(0,0,0,.10)       /* 卡片 */
--shadow-accent: 0 6px 14px rgba(accent,.18) /* 强调色按钮（同色投影）*/
--shadow-tint-rose: 0 9px 22px rgba(125,70,88,.11)
--shadow-tint-plum: 0 5px 10px rgba(99,55,68,.12)
--shadow-glow: 0 0 0 3px rgba(accent,.16)    /* 状态光晕 */
```

### 9.5 组件规范（从稿中反推）

| 组件 | 规格 |
|---|---|
| **胶囊主按钮** | h44，圆角 22，水平内边距 15/17（不对称：左 17 右 15，因为左侧是文字右侧是箭头）→ iOS：`.buttonStyle(.borderedProminent)` + `.controlSize(.large)` |
| **圆形 FAB** | 44×44，圆角 999，强调色底，同色投影 0 4px 12px |
| **应用图标卡** | 116×116，圆角 28，1px 同色系描边，同色系投影 |
| **玻璃 chip** | h25/26，圆角 13，rgba(20,20,22,.48) 底 + 1px rgba(255,255,255,.22) 描边 + blur(12) |
| **分页指示器** | 点 4×4 圆角 2 灰；激活 14×4 强调色；间距 5；容器距底 10 |
| **状态点** | 6×6 圆 + 3px 同色光晕环 |
| **照片页渐变遮罩** | 上 70px `rgba(0,0,0,.52)→0`；下 58px `rgba(0,0,0,.48)→0` |

### 9.6 尚未定义、必须补的令牌（空缺清单）

- **暗色模式**：全部令牌目前只有浅色值，深色模式一套没有。
- **状态机**：`hover` / `pressed` / `focus` / `disabled` / `loading` 的视觉规格（设备稿不需要，iOS 必须有）。
- **动效**：时长与缓动曲线（`.interactive` 0.2s ease-out / `.spring` 等）、转场（分页滑动）、微交互（按钮按压缩放 0.97）。
- **触觉反馈**：`UIImpactFeedbackGenerator` 轻/中/重对应场景。
- **字体回退**：中文 PingFang SC、英文 SF Pro、数字 SF Pro Rounded（更可爱）。
- **响应式断点**：iPhone SE 375pt / 标准 390pt / Pro Max 430pt / iPad。
- **安全区**：`safeAreaInset` 与顶部 42px topbar 的关系（设备屏没有刘海，iOS 必须要）。

---

## 10. 设计气质

**这套设计给人的感觉是：像一个住在小小黑盒子里、安静但很在意的朋友。它不炫耀科技感，也不喧闹；它把最大的情绪表达留给一张脸，其余部分全是克制的留白。**

支撑这种气质的具体决策有四条：

1. **颜色被当成信号而不是装饰。** 全部 4 稿的彩色面积 < 5%，强调色只出现在"要你按的地方"。大面积的颜色会让界面显得廉价，这套稿子在物理上禁止了这件事。
2. **情绪的载体是一张脸，不是图标。** 16 种表情的位图（soft/happy/shy/wink/wronged/yawn…）把"机器"和"宠物"的边界抹掉——尤其 `wronged`、`yawn` 这种负面/中性表情的存在，说明设计者要的是一个**有性格的个体**，不是一个会动的控件。
3. **结构上极度节制：每屏一个主张 + 一个动作。** 陪伴页 = 一张脸 + 一句话 + 一个圆钮；启动页 = 一张图 + 一个标题 + 一个按钮；相册页 = 一张照片 + 三个玻璃控件。没有并列的次级按钮、没有侧边栏、没有标签栏。
4. **材质语言是"磨砂玻璃 + 柔和圆角"，不是"硬质金属"。** `backdrop-filter: blur(12px)` 的半透明 chip、25–28px 的大圆角卡片、带色投影——这些让界面看起来像一层柔软的亚克力，而不是冷冰冰的工业面板。

**而 v2 的方向是把这套语言从"苹果极简"扭到"苹果极简 × 粉彩陪伴"**：同一副骨架，底色由冷灰换暖粉、图标卡由黑换粉、按钮由黑换粉、插画由截图换手绘吉祥物。验证了「**结构不需要重做，只需要换皮 + 换插画**」这个判断——这是这批稿子最有价值的结论。

**但也暴露了两个未解决的问题**：一是暖化只做了 60%（在线绿点、索引号、三种粉没有收口）；二是结构本身是为 320×240 触屏设计的，没有为 iOS 手机的纵向长屏与安全区做任何准备。

---

## 可复用方案

调研时间：2026-10-23，全部通过 GitHub API / 官方站点实际核实（stars、license、最近提交时间均取自实时接口）。

### 11.1 直接可用的项目

- **Apple 官方 iOS & iPadOS Figma UI Kit**  用途：Apple 自己发布的 Figma 组件库 + 设计变量（variables）+ 样式，覆盖 iOS 全套系统控件，是所有第三方 iOS 设计系统的事实基准  许可：Apple 免费设计资源（受 Apple Design Resources 条款约束，仅限 Apple 平台设计用途，不可转售或改作商标用途）  接入成本：**低**（Figma 社区文件直接打开即可，可复制为团队内部库）  替代自造的：Figma 端的 iOS 组件骨架、间距/字号变量、控件尺寸基线
  链接：https://www.figma.com/community/file/1651309003795292092/ios-and-ipados-27
  （来源：https://developer.apple.com/design/resources/ ，同页另有 SF Symbols app、App Icon Template 等官方模板）

- **SF Symbols + SFSafeSymbols**  用途：Apple 官方线性图标系统；SFSafeSymbols 用 Swift 类型安全包装 symbol 名，杜绝 `UIImage(systemName:)` 写错字符串导致的运行时空白图标  许可：SF Symbols 本体为 Apple 授权（App 内随 iOS 免费使用，禁止用于非 Apple 平台）；SFSafeSymbols 包装层 **MIT**  接入成本：**零**（SPM 加一个依赖，`.symbol(.heart.fill)` 即可）  替代自造的：整套线性图标 + 图标名常量表
  链接：https://github.com/SFSafeSymbols/SFSafeSymbols

- **Phosphor Icons**  用途：开源线性/duotone/fill 三重量级图标，圆头圆角、笔画柔和，是本批概念稿最缺的"可爱但不幼稚"的那一类图形（闪光 ✦、心形、星星、相机等装饰性图标）  许可：**MIT**  接入成本：**中**（SVG 需转成 Xcode Asset Catalog 的 PDF/SVG，或用 R.swift 之类的包管理）  替代自造的：吉祥物周围的装饰性图标与空态插画元素
  链接：https://github.com/phosphor-icons/core ｜ 备选：Lucide（ISC，https://github.com/lucide-icons/lucide ），更简洁但更"工程感"；**Remix Icon 排除**（自定义的 "Remix Icon License v1.0"，非标准开源协议，不可商用）

- **Style Dictionary**  用途：一份 JSON/YAML token 源，自动导出成 iOS（Swift/xcassets）、Android、CSS、Flutter 等多端产物，保证"设计稿改一个值 → 全端同步"  许可：**Apache-2.0**  接入成本：**中**（Node 工具链 + CI 里跑一次 build）  替代自造的：手写 token→Swift 映射表、CSS 变量维护、多端同步脚本
  链接：https://github.com/style-dictionary/style-dictionary

- **Tokens Studio for Figma**  用途：Figma 端的 token 管理插件，支持 DTCG 格式、Figma Variables 双向同步、导出 JSON 给 Style Dictionary  许可：**MIT**  接入成本：**低**（Figma 插件，团队协作即生效）  替代自造的：Figma 里的颜色样式管理、变量命名规范
  链接：https://github.com/tokens-studio/figma-plugin

- **SwiftGen**  用途：从 JSON/YAML/`.xcassets` 自动生成类型安全的 Swift 常量（Color / Font / Image / String / Asset）  许可：**MIT**  接入成本：**低**（SPM + 一个 Xcode Build Phase，模板用 `stencil` 写）  替代自造的：手写 `enum AppColor { static let accent = Color(hex: 0xEF6E91) }` 这类胶水代码
  链接：https://github.com/SwiftGen/SwiftGen

### 11.2 只作"设计组织方式"参考、**不可作为代码依赖**的项目

- **isamercan/ThemeKit**（MIT，17★，2026-10 仍在更新）— token 驱动的 SwiftUI 设计系统，宣称 130+ 组件绑定 token，主打"改一个 accent 色即可整体换肤"。**它的换肤模型正好解决我们"冷灰版 vs 粉版"是两套独立皮肤、无法共存的问题**。只读其 token 结构和组件分层，不引入依赖。
- **mrkai77/Luminare**（BSD 3-Clause，169★）— "modern, delightful, translucent design system made with SwiftUI"，毛玻璃/半透明语言，与 photos 稿的 `backdrop-filter: blur(12px)` 同源。可参考其材质分层。
- **Dimillian/IceCubesApp**（**AGPL-3.0**，7089★）— SwiftUI 生产级开源 App，Resources/Assets 分层与主题组织方式值得抄结构。**AGPL 有传染性，不可拷贝代码进商业闭源 App**，只可阅读学习。
- **Orange-OpenSource/ouds-ios**（MIT，36★，活跃）— 厂商级统一设计系统包，参考其"design token → Swift Package → 组件"的三层组织方式。
- **liseami/ChunUI**（MIT，542★）— 单色质感 SwiftUI 设计系统，可参考其排版与间距尺度，但明确定位 monochrome，与我们的粉彩方向不符。

### 11.3 找不到的东西（不硬凑）

- **"IBeyond"**：GitHub 全库搜索无结果，未找到该 iOS 开源项目。**"Ivory"**（Infinite Red 的开源 X 客户端）同样搜不到——可能已下线或改名。
- **没有任何现成的开源 SwiftUI 组件库能直接提供"Apple 极简 + 粉彩陪伴"这套视觉**。查到的库要么是中性企业风（ThemeKit 自称 brand-neutral）、要么是单色（ChunUI 自称 Monochrome-quality）、要么是瑞士铁路/橙色的行业系统。**这套视觉本身没有现成实现，必须自造。**
- **没有 SF Symbols 的等价开源替代品**。SF Symbols 在 Apple 平台上免费可用，所以"替代"需求只出现在跨平台（Android/桌面/Web）时；那时用 Phosphor 或 Lucide。

### 11.4 补充建议（非 GitHub）

- **Lottie（airbnb/lottie-ios，Apache-2.0，26.9k★）**：这批稿子**零动效规范**，而小栈有 16 种表情。若要让吉祥物在 iOS 上"活起来"（呼吸、眨眼、爱心跳动），Lottie 是生态最成熟的方案（After Effects 导出 → 资源包）。接入成本中（需动画师出稿）。链接：https://github.com/airbnb/lottie-ios
- **Figma 社区的第三方 iOS UI Kit**：Apple 官方那套已足够且最权威，第三方 kit 多为「参考图」性质而非可维护的组件库，**不建议引入**（会引入第二套真相源）。

### 采用决策：**混合**

**理由**：

1. **视觉层 100% 自造。** 没有任何开源库提供"Apple 极简 + 粉彩陪伴"这套具体气质（见 11.3）。颜色值、圆角梯度、阴影梯度、插画画法、吉祥物形象、组件外观必须由我们自己定义——这正是本报告第 9 节 token 清单的用途。
2. **工具链复用。** Style Dictionary + Tokens Studio + SwiftGen 三件套把"token 定义"这件事从代码里抽出来变成一份可版本管理的 JSON，这是解决我们当前 **颜色漂移（`#ff6b78` vs `#ff5f6d`、三种粉、两套灰底）** 的根本手段，比靠人自觉管用得多。SF Symbols + SFSafeSymbols 直接补上这批稿子完全缺失的图标层。
3. **设计组织方式参考而不依赖。** ThemeKit 的"单 accent 换肤"模型直接对应我们 v1/v2 的双皮肤问题，值得抄结构（自造 token 映射表即可，不必引包）。IceCubesApp 只读结构不抄代码（AGPL）。
4. **Figma 侧以 Apple 官方 kit 为唯一基准**，不再引入第三方 kit，避免两套真相源。

**最小落地路径（建议顺序）**：

1. 先用 Tokens Studio 在 Figma 里把第 9 节的 token 落成一份 JSON（DTCG 格式），**这一步同时就把颜色漂移问题暴露并修掉**；
2. Style Dictionary 把这份 JSON 导出成 Swift 常量 + CSS 变量（Web 预览用）；
3. SwiftUI 侧自建 `DesignSystem` 目录：Color / Typography / Radius / Spacing / Elevation 五个 token 文件 + 组件（胶囊按钮、圆形 FAB、玻璃 chip、分页指示器、应用图标卡）；
4. 图标用 SF Symbols（SFSafeSymbols 包装），装饰性可爱图标从 Phosphor 引入；
5. 吉祥物与动效自造，Lottie 作为动画交付格式。

---

## 附：后续设计最容易做错的地方（基于这批稿子的真实特征）

1. **把 320×240 的字号直接搬到 iPhone。** 稿子里 10px/11px 是设备像素；照搬到 390pt 宽的手机上，11pt 的副标题会小到读不动，且 27px 的"大标题"在手机上根本不算大标题。**必须整体重算字号阶梯**（本报告 9.3 已给出建议值）。
2. **继续用 650 / 750 / 760 这些不存在的字重。** PingFang SC 最高只有 Semibold(600)，Mac/浏览器上会合成，iOS 上会回落成 700 —— 设计稿和真机对不上，评审会直接判"没对齐"。
3. **让颜色继续漂移。** 现在已经有 `#ff6b78`/`#ff5f6d` 两个红、`#6bd89e`/`#44c783` 两个绿、v2 里 `#d94f78`/`#ef6e91`/`#f16f91` 三个粉。下一稿如果再出现第 4 个粉，整套设计语言就散了。**任何新颜色必须先进 token 表再使用。**
4. **在浅色模式上二选一后又不做暗色模式。** 冷灰 `#f5f5f7` 和粉 `#fbeef3` 现在是两套独立皮肤，产品只能留一套；留哪套要现在定，然后补一套完整的暗色 token（尤其 `#050506` 深色舞台和玻璃层在暗色下的表现）。
5. **用 Arial 文字字符当图标（→ ‹ ✦）。** 跨系统字形不一致，`✦` 在很多设备上是 fallback 字形，评审在另一台 Mac 上就会变样。**换成 SF Symbols / 矢量图。**
6. **照抄 `object-fit: fill` 的硬拉伸。** 表情源图是 320×240，在 launcher 里被裁成 124×93、在 companion 里拉成 230×173，全靠 fill 硬凑；继续这么干会放大脸型畸变。要么按比例裁切并对齐眼睛位置，要么重新出图。
7. **漏掉交互状态。** 这批稿只有静态默认态（唯一的状态是 `.dot.active`），没有按下/禁用/加载/错误。iOS App 全是触摸交互，**按压反馈和触觉反馈必须先定规范**，否则每个页面各做各的。
8. **把"可爱"做成"婴儿粉"。** `#fbeef3` + `#f8dce5` 这一档偏甜幼态，面向 ENFP 成人用户可能过于低龄。建议**降饱和或加深一档主粉**（如把强调色从 `#ef6e91` 往 `#e0577f` 方向压一点），保留暖感但不要粉红糖果感。
9. **让 v2 的暖化只做一半。** 在线绿点 `#44c783` 没跟着暖化，在粉底上像系统组件外挂；三个粉也没有层级。**要么整体暖化（含状态色），要么明确"状态色保持系统中性"并写进规范** —— 现在的状态是"没想清楚"。
10. **只换皮不改结构就够了。** v2 证明了结构可以复用，但这套结构是**竖屏手机完全不适用的**：42px 顶栏、116px 图标卡左置、底部 8 点分页器，都是为 320×240 横屏小屏设计的。**布局必须重排**，只有令牌能继承。

