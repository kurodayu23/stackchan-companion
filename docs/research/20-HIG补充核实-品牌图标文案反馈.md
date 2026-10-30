# 20 · HIG 补充核实（品牌 / 图标 / 文案 / 反馈 / 侧边栏 / 菜单）

> **本轮补抓**：在已有 25 页 HIG 缓存基础上，新增 11 页原文，HIG 覆盖从 25 页 → **36 页**。
> **权威等级**：⭐⭐⭐ 官方原文（本文件全部条目均逐字引用自 `developer.apple.com` 的 `.md` 版本，非转述）。
> **为什么重要**：新增的 **Branding** 页（2026-09-09 更新）**逐条背书了我们此前"自行裁决"的三项决定**，把"我觉得这样对"升级成"官方这么说"；同时 **Feedback** 页**修正**了我们宪法第 16 条的一个边界。

---

## 一、本轮新增 HIG 页清单

| 页面 | 字节 | 对我们的相关性 |
|---|---|---|
| **`branding.md`** | 6,005 | ⭐⭐⭐ 最高 —— 品牌色怎么用、logo 怎么放、启动页能不能做品牌 |
| `icons.md` | 27,019 | ⭐⭐⭐ 自绘图标（我们要给小栈做图标/表情资产） |
| `writing.md` | 11,757 | ⭐⭐⭐ 人格文案规范（ENFP 语气如何落到字面） |
| `feedback.md` | 4,947 | ⭐⭐⭐ 多通道反馈 —— 直接影响"状态不要用文字"这条 |
| `menus.md` | 18,010 | ⭐⭐ 菜单与子菜单克制 |
| `toolbars.md` | 23,417 | ⭐⭐ 工具栏结构 |
| `sidebars.md` | 9,968 | ⭐⭐ 侧边栏图标配色规则 |
| `virtual-keyboards.md` | 15,375 | ⭐ 输入区与键盘避让 |
| `onboarding.md` | 6,227 | ⭐ 首次体验 |
| `launching.md` | 6,335 | ⭐ 启动页（**与设备端启动器页裁决相关**） |
| `navigation-and-search.md` | 2,176 | ⭐ 导航与搜索 |

抓取失败的页（404，该 slug 在 HIG 中不存在，不要再试）：`tint-color` / `tables` / `assistive-technology` / `spatial`。

---

## 二、⭐⭐⭐ Branding —— 官方原文背书我们的三项裁决

> 页面 Change log：**September 9, 2026 — Refined guidance for using brand color.**（这是 2026 年 9 月才更新的最新表述）

### 2.1 品牌色怎么用（官方原话）

> **"Apply your app's accent color judiciously. Using your brand color too broadly can overwhelm your interface and dilute its impact. Minimize its use on controls and instead use it intentionally for primary actions or status indicators, like badges for unread content or an icon for the selected tab in a tab bar. To express your brand through color, consider moving it into the content layer, where it scrolls beneath Liquid Glass controls and gets picked up dynamically."**

拆成 4 条可执行判据：

| # | 官方要求 | 我们的落地 |
|---|---|---|
| B1 | 品牌色**铺得太广会冲垮界面、稀释品牌** | 暖色只出现在 1 处主操作 + 少量状态指示器，**不做大面积着色** |
| B2 | **"Minimize its use on controls"** —— 品牌色尽量不要用在控件上 | ⭐ 这条**直接支持我们推翻「禁系统默认蓝」的裁决**：系统控件继续用系统语义色，暖色**不铺控件** |
| B3 | 品牌色用于**主要动作**或**状态指示器**（未读徽标、选中 tab 的图标） | 暖色的合法用途就两类：① 主按钮 ② 选中态指示 |
| B4 | ⭐⭐ **"moving it into the content layer, where it scrolls beneath Liquid Glass controls and gets picked up dynamically"** | ⭐⭐ **这条对我们价值最高**：Apple 明确建议**把品牌色放进内容层**，让它在玻璃控件下方被"动态拾取"。<br>**→ 我们的"小栈的脸"区域就是内容层**，暖色应该出现在**小栈脸部的腮红/光晕/情绪色**上，而不是出现在 Tab Bar、按钮、开关上。<br>→ **这不是我们自创的审美偏好，是 Apple 推荐的"品牌色落位"位置。** |

### 2.2 品牌与原生感（官方原话）

> **"Express your brand with familiar components."**
> *"When you use components that people already know, the experience feels immediately reliable and familiar, and people can focus on the unique content and features that make your app stand apart. If you need to customize a component's appearance to reflect your brand, ensure that details like sizing, placement, and behavior continue to preserve a familiar experience that's appropriate for the platform."*

> **"Ensure branding always defers to content."**
> *"Using screen space for an element that does nothing but display a brand asset can mean there's less room for the content people care about."*

> **"Help people feel comfortable by using standard patterns consistently."**
> *"Even a highly stylized interface can be approachable if it maintains familiar behaviors and patterns."*

→ ⭐ 这三条合起来就是"**嵌入苹果系统**"的官方定义：
**用熟悉组件 + 标准位置 + 标准符号 + 标准行为表达品牌，而不是改造组件外观。**
我们的"iOS 端 = Apple 原生骨架 + 唯一自绘是小栈的脸"**完全符合**。

### 2.3 ⭐ Logo 与启动页（官方原话）

> **"Resist the temptation to display your logo throughout your app or game unless it's essential for providing context."**
> *"People seldom need to be reminded which app they're using, and it's usually better to use the space to give people valuable information and controls."*

> **"Avoid using a launch screen as a branding opportunity."**
> *"A launch screen disappears too quickly to convey any information, but you might consider displaying a welcome or onboarding screen that incorporates your branding content at the beginning of your experience."*

→ ⭐⭐ **这两条直接判决了我们设备端的"启动器页"**：
- 我们此前"建议删掉设备端启动器页"的裁决，**现在有官方同向依据**（启动页不做品牌）。
- iOS 端也**不在 App 里到处放小栈 logo**（除了 App 图标）。
- 唯一合理的品牌位：**Onboarding（首次引导）**。

### 2.4 品牌语气与字体（官方原话）

> **"Use your brand's unique voice and tone in all the written communication you display."**
> *"your brand might convey feelings of encouragement and optimism by using plain words, occasional exclamation marks and emoji, and simple sentence structures."*

> **"Consider using a custom font."** … *"It can work well to use a custom font for headlines and subheadings while using system fonts for body copy and captions, because the system fonts are designed for optimal legibility at small sizes."*

→ ⭐ 与我们「**SF Pro Rounded 可用于标题/次标题，正文用系统字体**」的既有裁决**完全一致**。
→ ⚠️ 注意官方给的例子是 "plain words, occasional exclamation marks and **emoji**" —— 但这条说的是**文案语气**，不是**图标**；我们的「禁 emoji 当图标」（Floor F16）不受影响。

---

## 三、Icons —— 自绘图标的硬约束

> 官方原话（逐条）：

| 规则 | 原文要点 |
|---|---|
| **高度简化** | *"Create a recognizable, highly simplified design. Too many details can make an interface icon confusing or unreadable."* |
| **全局一致** | *"all interface icons in your app need to use a consistent size, level of detail, stroke thickness (or weight), and perspective."* |
| ⭐ **系统组件里的图标不用做选中态** | *"Provide a selected-state version of an interface icon only if necessary. You don't need to provide selected and unselected appearances for an icon that's used in standard system components such as toolbars, tab bars, and buttons. **The system updates the visual appearance of the selected state automatically.**"* |
| **矢量优先** | *"use a vector format like PDF or SVG… Alternatively, you can create a custom SF Symbol"*；PNG 不支持缩放，要多倍图 |
| **别画 Apple 硬件** | *"Avoid using replicas of Apple hardware products."* |
| **文字入图标要本地化** | *"If you need to display individual characters in your icon, be sure to localize them."* |
| **小尺寸也要认得出**（文档图标） | *"Your document icon can display as small as 16x16 px…"* / *"Consider reducing complexity in the small versions"* |

### ⭐ 对我们的三条直接影响

1. **"系统组件的选中态由系统自动处理"** → 我们的 Tab 图标（2 个）**不需要自绘 selected/unselected 两套**，交给 `.tint` 与系统即可。**省掉一半图标资产工作量。**
2. **"图标要在小尺寸下仍可辨认"** → 设备端 320×240 上的图标**必须极简**，细节多就糊。这与「表情只用官方 PNG 资产」是同一个方向。
3. **"尺寸/细节级别/描边粗细/透视必须全局一致"** → 我们若自绘图标（设备端的表情/状态图标），要定**一套网格与描边规范**（参考 SF Symbols 的 variable stroke），不能每个图标各画各的。

---

## 四、Writing —— 人格文案的字面规范

> 官方原话要点（对 ENFP 人格包直接可执行）：

| 规则 | 原文要点 | 落地 |
|---|---|---|
| **少即是多** | *"Check each word to be sure it needs to be there. If you can use fewer words, do so."* | 小栈的话**短**。ENFP 的话痨放在后端的回复长度控制里，不放在 UI 文案里 |
| **动词优先、别卖萌** | *"it's almost always best to use a verb… just saying 'Send' often works better than 'Let's do it!'"* | 按钮文案用动词，不写"让我们开始吧！" |
| ⭐ **少用所有格、避免 "we"** | *"Possessive pronouns like my and your are often unnecessary… **Avoid using we altogether** because it may be unclear who the 'we' refers to. This is particularly problematic in error messages like 'We're having trouble loading this content.' Something like 'Unable to load content' is much clearer."* | ⭐ **小栈的自称是"我"，不是"我们"**。错误信息不写"我们遇到了问题"，写"现在有点走神，稍等一下" |
| **空状态给下一步** | *"An empty screen can be daunting if it isn't obvious what to do next… give them a button or link to do so if possible."* | 与 Floor F9 一致 |
| **错误信息就近、不指责、给解法** | *"display it as close to the problem as possible, avoid blame, and be clear about what someone can do to fix… Interjections like 'oops!' or 'uh-oh' are typically unnecessary and can sound insincere."* | ⭐ 陪伴产品的错误信息不能指责用户，也不能太油腻 |
| **大小写风格要一致** | *"Title case is generally considered formal, while sentence case is more casual."* | 中文无此问题，但**英文/双语时**要定死一种 |

---

## 五、⭐⭐ Feedback —— **修正**我们宪法第 16 条的边界

> 官方原话：
> **"Make sure all feedback is accessible. When you use multiple ways to provide feedback, you reach more people and give them the opportunity to receive the feedback in ways that work for them. For example, when you provide feedback using color, text, sound, and haptics, people can receive it whether they silence their device, look away from the screen, or use VoiceOver."**

> **"When it makes sense, confirm that a significant action or task has completed."**
> *"it's generally best to reserve this type of confirmation for activities that are sufficiently important — because people typically expect their action or task to succeed, they only need to know when it doesn't."*

> **"Warn people when they initiate a task that can cause data loss that's unexpected and irreversible. In contrast, don't warn people when data loss is the expected result of their action."**

### ⚠️ 5.1 这**修正**（不是推翻）宪法第 16 条

**原第 16 条**：「"正在听 / 正在想"不用文字标签、不用跳动波形」→ 交给小栈的脸。
**这个方向仍然成立**（依据是 Gemini Live 实测的零文字零波形）。

**但需要补一个边界**（依据 HIG Feedback）：

> ⭐ **"不用文字"针对的是「AI 内部状态的常驻标签」，不是「所有反馈」。**
> Apple 明确要求反馈要**多通道**（颜色 / 文字 / 声音 / 触感），这样静音、不看屏、VoiceOver 用户都能收到。

**我们的多通道映射（正好是产品的强项）**：

| 通道 | 我们的实现 |
|---|---|
| **视觉** | 小栈的脸（表情 + 眼神 + 腮红） |
| **触感** | Core Haptics 自定义波形（摸头 / 生气 / 被夸）—— iOS 端 |
| **声音** | 小栈的语音语气（设备端 1W 喇叭 / iOS TTS） |
| **文字** | ⚠️ **仅用于错误与重要确认**，不用作常驻状态标签 |

→ 所以第 16 条修订为：
> **第 16′ 条**：「正在听 / 正在想」等 **AI 内部状态**不用文字标签、不用跳动波形 → 交给小栈的脸 + 触感 + 声音。
> **但错误提示与重要操作完成反馈必须有文字**（HIG Writing：错误要说明怎么修），且**反馈应尽量多通道**（HIG Feedback）。

### 5.2 "确认动画"要克制

> *"reserve this type of confirmation for activities that are sufficiently important — people typically expect their action to succeed, they only need to know when it doesn't."*

→ ⭐ 这条**反对**"每次成功都弹提示"。之前从 Things 3 学到的是"完成反馈延 0.5 秒 + 触感"，现在要加限定：
**只有"用户可能预期会失败"的操作才给显式完成反馈；日常操作靠触感与状态自然变化，不加弹层。**

---

## 六、Sidebars / Menus / 其他（简）

**Sidebars**：
- *"Make sure any sidebar icon colors you choose serve a clear purpose. By default, sidebar icons use your app's accent color… if you use them sparingly, fixed colors can help clarify the meaning of an icon."*（Mail 的 VIP 黄色）→ ⭐ **印证「少用固定色，但用了就要用于表达含义」**；我们的暖色可作"选中/在陪伴中"的状态色。
- *"Avoid putting critical information or actions at the bottom of a sidebar."*
- *"Consider using a tab bar first."* → 印证我们「Tab 只 2 个」的克制。

**Menus**：
- *"Use submenus sparingly. Each submenu adds complexity to the interface and hides the items it contains."* → 我们的设置项层级 ≤2。
- *"Prefer displaying a menu near the content it controls."*

**Feedback 补充**：
- 只对**意外且不可逆**的数据丢失做警告（"预期的删除不用每次都确认"）。

**Virtual keyboards**：
- *"Avoid duplicating system-provided keyboard features."*
- *"If any of your other views use Liquid Glass… apply Liquid Glass to the view that contains your controls to maintain consistency."* → 输入区上方的自定义控件也要统一玻璃处理。

---

## 七、对宪法 / Floor 规范的增补

| 新增 | 内容 | 来源 |
|---|---|---|
| **F23** | **品牌色只出现在两类位置**：① 主要动作 ② 状态指示器；**不铺控件**；**优先放进内容层**（小栈的脸），让玻璃控件动态拾取 | HIG Branding（B1–B4） |
| **F24** | **反馈多通道**：同一反馈尽量同时给 视觉 + 触感 + 声音 + 文字 | HIG Feedback |
| **F25** | **自绘图标全局同规格**：尺寸 / 细节级别 / 描边粗细 / 透视一致；系统组件里的图标**不做选中态** | HIG Icons |
| **F26** | **文案禁用 "we"、禁 "oops!" 类感叹词、按钮用动词**；人格自称统一为"我" | HIG Writing |
| **F27** | **只在"用户可能预期会失败"的操作上给显式完成反馈**；日常操作靠触感与自然状态变化 | HIG Feedback |
| **R16**（Reflex） | 不在 App 内到处放 logo / 品牌资产；启动页不做品牌 | HIG Branding |
| **R17**（Reflex） | 子菜单少用；侧边栏底部不放关键操作 | HIG Menus / Sidebars |

---

## 八、⚠️ 本轮的一处自我修正

**旧表述**（`00-总纲` 宪法 16 + `19` 号 Floor 文档）容易读成：
> 「不用文字表达状态」

**修正为**：
> 「**AI 内部状态**（正在听/正在想/思考中）不用文字标签、不用跳动波形 → 交给小栈的脸 + 触感 + 声音；
> **错误提示与重要确认必须有文字**，且反馈应尽量多通道。」

这不是推翻原裁决，而是**给它补上边界** —— 原裁决的依据（Gemini Live 零文字零波形）针对的是"AI 内部状态的可视化"，与"错误提示"是两件事。**混为一谈会导致我们把错误提示也做成纯视觉，那是残障用户的可达性问题。**

---

## 九、待确认

| # | 事项 |
|---|---|
| 1 | HIG 的 `tint-color` / `tables` / `assistive-technology` slug 404，**色彩与表格的细则仍以 `color.md`（已抓 41 KB）为准** |
| 2 | HIG 未提供"桌面机器人/非手机设备"专章，设备端 320×240 的细则**仍需我们自造**（`02` 号文档 + `19` 号 Floor 设备端列） |
| 3 | Branding 页提到的 `BreakthroughEffect`（菜单/3D 内容的突破效果）属 visionOS 场景，**iOS 上不适用**，已排除 |
| 4 | Apple 在 2026-09 才细化过 brand color 指引，**其余 HIG 页面可能后续更新**，建议最终设计稿定稿前再抓一次关键页做 diff |
