# 05 · Google 设计体系与 AI 产品设计（可执行研究）

> 研究目标：搞清「谷歌怎么把 AI 产品设计得好看」，并判断 **StackChan iOS 控制端** 能抄什么。
> 场景锚点：桌面陪伴机器人 StackChan（M5Stack CoreS3 / ESP32-S3 / 320×240） + 原生 iOS App；目标用户为 ENFP 用户；最终开源至 GitHub 作为求职作品。
> 用户硬性要求：界面必须「嵌入苹果系统」，像 iOS 26 / iPhone 17 原生 App 一样自然；同时用户点名「去学习谷歌的设计」。
> 写法：每条结论给出处（URL 或 文件路径:行号）；拿不到出处的写「未验证」。本文为增量追加写作。

## 0. 速读结论（TL;DR）

**一句话**：谷歌的设计体系能抄的是**数值与机制**（M3 的 7 档圆角/15 档字号/4 档动效、"角色→tone→色值"的取色骨架、"过程必须可见但要软"的 AI 交互观），抄不了的是**壁纸动态取色**（iOS 无此机制）；而且**谷歌自己就说不该"heroize technology"**——所以本项目应当「**以苹果为壳、谷歌为过程、小栈的脸为 AI 的化身**」。

**三条关键事实（均有出处）**
1. M3 Expressive 不是"更花哨"，是**更情绪 + 更好用**：46 项研究 / 18,000+ 参与者；18–24 岁偏好度高达 **87%**；眼动定位关键元素快 **4 倍**；品牌现代感 **+34%**（`p_expressive_research_w.txt:7,23,34,39`）。
2. Gemini Live 在摄像头态下**没有任何文字状态、没有波形**（`describe_text.txt:59-61`）——状态靠**图标形态**表达；而 Google 自己的研究说 **"not heroize technology"**、AI **太快反而让人看不懂**（`p_ai_roundtable_w.txt:24-28`）。
3. NotebookLM 把 AI 产物做成**独立内容类型 + 常驻 mini player**，而不是聊天记录（`describe_text.txt:75-83`）——这是"避免聊天框地狱"的可抄解法。

**最该抄的 5 条**：① 状态不写字、交给小栈的脸（内部运动=在想）② 用 M3 官方数值收敛形状/字号/动效并写成 lint 规则 ③ 把"角色化取色"搬成**设备状态派生主题** ④ AI 产物有独立形态 ⑤ 能力交给系统（App Intents）、人格做成参数（话痨度/主动性/语速/吐槽度）。

**复用/自造**：**混合** —— 复用 M3 数值（material-tokens / material-web，Apache-2.0）、复用 Apple 系统框架（App Intents / Background Tasks / 通知）、复用开源校验链（style-dictionary / stylelint / axe-core）；**自造**令牌体系与设备状态主题算法、陪伴型交互规范。

**未验证**：PAIR Guidebook 正文、Android 官方 M3 文档、AI Studio/Vertex/Firebase 文档、Apple HIG 正文、labs.google.com 与 gemini/notebooklm.google.com 产品内实测 —— 详见第 7 节 U-01~U-13。


---

## 0.1 研究方法与来源清单（2026-10-23 实测）

- 本机 `web_search` 不可用（报 MATRIX_TOOL_REQUEST_FAILED），duckduckgo html 不通 → **全部走 `web_fetch` 直抓 URL**。
- `m3.material.io` 是 Angular SPA，直抓 HTML 只返回外壳（实测拿到的是 `<mio-root>` 与字体 CSS，无正文）。**但它的 CSS 里带真实设计令牌**，可作为数值旁证。
- **可抓正文的权威源已实测可用**：
  - `https://raw.githubusercontent.com/material-components/material-web/main/tokens/...` —— Material Web 的 SCSS 令牌源（Apache-2.0），含 shape / typescale / elevation / motion / palette 的**真实数值**；
  - `https://api.github.com/...` —— 取仓库元数据（license / stars / archived 状态，实测值）。
- 实测失败：`https://developer.android.com/design/material/material-3-expressive`（web_fetch 超时）、`https://pair.google.com/`（network request failed）、`https://r.jina.ai/...`（network request failed）。→ 这些内容改由其它可达镜像/仓库补齐，并在文中标注。

---

## 1. Material Design 演进

### 1.1 Material 3（Material You）的核心机制：一切都是「角色 → 色板 → tone」

M3 的底层不是"颜色值"，而是三层结构。官方 token 源码把这件事写死了：

| 层 | 官方 token 家族 | 实测证据 |
|---|---|---|
| 参考层 Reference | `md.ref.palette.*` | 每族一套 0–100 的 tone（primary / secondary / tertiary / neutral / neutral-variant / error），tone 是**亮度刻度**而不是颜色 |
| 系统层 System | `md.sys.color.*` | 把 palette 映射成**语义角色**：`surface`→neutral98、`on-surface`→neutral90、`surface-container`→neutral94、`outline-variant`→neutral30 … |
| 组件层 Component | `md.comp.*` | 由系统层再派生（button / card / fab / chip …） |

出处（均为本地实测下载，源文件可回溯）：
- 家族结构图：`D:\AP\AP7000\ai-workspace\stackchan-research\google-ref\mt_tokens_md.txt:1-190`（`md.sys.color ----> md.ref.palette.neutral0` 等）
- 语义角色映射：`D:\AP\AP7000\ai-workspace\stackchan-research\google-ref\tokens_color.txt:28-70`（浅色）、`:87-129`（深色）
- tone 实际色值：`...\tokens_palette.txt:19-67`

**这就是"动态取色（Material You）"的可抄内核**：不让设计师直接写 hex，而是写「角色」；角色指向 tone；tone 由一个可算法化的来源（Android 12+ 的壁纸取色 / HCT 色空间）产生。
> ⚠️ HCT/CAM16 取色算法本身**未验证**：`developer.android.com` 与 `pair.google.com` 在本机网络不可达（见 0.1），只能验证"角色→tone→色值"这套骨架。Android 壁纸取色由系统提供，**不是设计系统能复刻的能力**——所以我们只能抄"角色化"，抄不了"壁纸取色"。

### 1.2 四个机制，对我们真正有用的部分

| M3 机制 | 官方实现 | 对 StackChan iOS 端意味着什么 |
|---|---|---|
| **动态取色** | 系统从壁纸生成 seed，再生成整套 tonal palette | iOS **没有** Material You。但我们可以把"seed"换成**设备状态**（小栈当前情绪色 / 电量 / 温度），自造一套 `deviceSeed → tonalPalette → role` 的管线（见 D-06） |
| **surface tint** | `surface-tint` = primary40(浅) / primary80(深)；组件 surface 用主色微调 | iOS 无 tint 机制；但可用 `UIColor` 的 `.withAlphaComponent` 在**导航栏/按钮**上做 ≤8% 主色叠加，观感接近 M3 |
| **elevation 用颜色而非阴影** | `surface-container-lowest/low/container/high/highest` 五个容器色阶替代 M2 的阴影层级 | iOS 的 `secondarySystemGroupedBackground` / `tertiarySystemGroupedBackground` 正好是**系统自带的三级容器**，可直接用，不必自造 |
| **shape / type / motion token 化** | 每个维度都是有限档位，禁止自由值 | 这三条**可以直接照抄数值**（见 1.3 表），是本报告最可执行的部分 |

### 1.3 M3 可落地数值表（全部实测自官方 token 源）

**① Shape scale（圆角档位）** — `...\tokens_shape.txt:17-31`
| Token | 值 | 典型用途 |
|---|---|---|
| corner-none | 0px | 贴边容器、全屏页 |
| corner-extra-small | 4px | 极小标签、进度条片段 |
| corner-small | 8px | 小按钮、输入框、chip |
| corner-medium | 12px | 中卡片、菜单项、列表容器 |
| corner-large | 16px | 大卡片、对话框、底部 sheet |
| corner-extra-large | 28px | 超大容器、Hero 卡、展开面板 |
| corner-full | 9999px | 胶囊按钮、头像、状态胶囊 |

> 注：M3 的 shape scale **只有 7 档**，且**不随组件语义变化**（Expressive 之后才引入"夸张形状"变体，见 1.4）。
> iOS 对照：Apple 没有公开 radius token，实际惯例是 8 / 10 / 12 / 16 / 20 / 28 / 连续（capsule）。我们**直接采用 M3 的 7 档**作为自有令牌，是最省事的对齐方式。

**② Type scale（字号 / 行高 / 字重）** — `...\tokens_typescale.txt`（rem 按 1rem = 16px 换算为 px）
| 角色 | 字号 px | 行高 px | 字重 | tracking |
|---|---|---|---|---|
| display-large | 57 | 64 | 400 | -0.25px |
| display-medium | 45 | 52 | 400 | 0 |
| display-small | 36 | 44 | 400 | 0 |
| headline-large | 32 | 40 | 400 | 0 |
| headline-medium | 28 | 36 | 400 | 0 |
| headline-small | 24 | 32 | 400 | 0 |
| title-large | 22 | 28 | 400 | 0 |
| title-medium | 16 | 24 | 500 | 0.15px |
| title-small | 14 | 20 | 500 | 0.1px |
| body-large | 16 | 24 | 400 | 0.5px |
| body-medium | 14 | 20 | 400 | 0.25px |
| body-small | 12 | 16 | 400 | 0.4px |
| label-large | 14 | 20 | 500 | 0.1px |
| label-medium | 12 | 16 | 500 | 0.5px |
| label-small | 11 | 16 | 500 | 0.5px |

字重只有三档：`weight-regular 400 / weight-medium 500 / weight-bold 700` — `...\tokens_ref_typeface.txt:15-19`。
字体：M3 参考字体是 **Roboto**（`brand` / `plain`）— `...\tokens_ref_typeface.txt:16-17`。**我们不用 Roboto**（iOS 上会与系统字体打架）；只抄"档位结构"，字族用 SF Pro。

**③ Motion tokens（时长 + 缓动）** — `...\tokens_motion.txt:17-52`
| 档位 | 时长 | 用途 |
|---|---|---|
| short1–short4 | 50 / 100 / 150 / 200ms | 微交互（按下、涟漪、小图标） |
| medium1–medium4 | 250 / 300 / 350 / 400ms | 组件进出、卡片展开、Toast |
| long1–long4 | 450 / 500 / 550 / 600ms | 页面转场、全屏 sheet |
| extra-long1–4 | 700 / 800 / 900 / 1000ms | 超长动画（AI 生成进度条等） |

| 缓动 token | cubic-bezier | 语义 |
|---|---|---|
| easing-standard | (0.2, 0, 0, 1) | 默认通用 |
| easing-emphasized | (0.2, 0, 0, 1) | 强调（= standard 同值） |
| easing-standard-decelerate | (0, 0, 0, 1) | 进入（减速落位） |
| easing-standard-accelerate | (0.3, 0, 1, 1) | 退出（加速离场） |
| easing-emphasized-decelerate | (0.05, 0.7, 0.1, 1) | 强减速（大件入场） |
| easing-emphasized-accelerate | (0.3, 0, 0.8, 0.15) | 强加速 |
| easing-legacy | (0.4, 0, 0.2, 1) | 旧版通用 |

> **可直接用的翻译**：`easing-standard-decelerate (0,0,0,1)` 在 iOS 上 ≈ `UIView.AnimationOptions.curveEaseOut`；`standard-accelerate (0.3,0,1,1)` ≈ `curveEaseIn`。**M3 Expressive 之后的 spring 动效在 iOS 上没有 1:1 对应**，需要用 `UIViewPropertyAnimator` 自造（见 1.4）。

**④ Elevation 与 surface container 层级（含实测 hex）**
- Elevation 档位：`level0..level5` → 0 / 1 / 3 / 6 / 8 / 12（dp）— `...\tokens_elevation.txt:17-22`
- 浅色模式容器色（`md.sys.color`，`...\tokens_color.txt:61-70` + `...\tokens_palette.txt`）：

| 角色 | tone | 浅色 hex | 深色 hex |
|---|---|---|---|
| surface-container-lowest | neutral100 / neutral4 | #fffbff | #0f0d13 |
| surface-container-low | neutral96 / neutral10 | #f7f2fa | #1d1b20 |
| surface-container | neutral94 / neutral12 | #f3edf7 | #211f26 |
| surface-container-high | neutral92 / neutral17 | #ece6f0 | #2b2930 |
| surface-container-highest | neutral90 / neutral22 | #e6e0e9 | #36343b |
| surface | neutral98 / neutral6 | #fef7ff | #141218 |
| surface-bright | neutral98 / neutral24 | #fef7ff | #3b383e |
| surface-dim | neutral87 / neutral6 | #ded8e1 | #141218 |
| surface-variant | neutral-variant30 / 90 | #49454f | #e7e0ec |
| outline-variant | neutral-variant30 / 80 | #49454f | #cac4d0 |
| on-surface-variant | neutral-variant80 / 30 | #cac4d0 | #49454f |
| surface-tint | primary40 / primary80 | 见 palette | 见 palette |
| scrim / shadow | neutral0 | #000000 | #000000 |

> **关键结论**：M3 的 5 级容器是**同一中性色的不同 tone**，靠明度差（Δ 很小）分层，所以"看起来平"而不是"看起来卡"。我们的 iOS 端**不要用阴影堆层级**，改用 `secondarySystemGroupedBackground`（≈ container）/ `tertiarySystemGroupedBackground`（≈ container-high）+ 极轻分割线。
> ⚠️ M3 容器之间的**精确 tone 差**（如 94→92 是 Δ2）已由上表给出，但官方是否规定"必须相邻 2 tone"——**未验证**（这是 token 生成结果，不是规范条文）。

**⑤ 间距系统**
> ⚠️ **未验证**：M3 的官方 token 源里**没有 spacing token 家族**（`material-web/tokens/` 下无 spacing 文件，实测目录清单见 `...\google-ref` 下载记录）。业界普遍说"M3 沿用 4dp 栅格"，但本次**没能从官方文档抓到**（developer.android.com 不可达）。→ 我们的间距**不抄 M3**，直接抄 iOS 的 8/12/16/20/24（见 02 号设计契约文档）。

**⑥ 官方可下载资源（本机实测可达性见 0.1）**
| 资源 | URL | 用途 | 本机实测 |
|---|---|---|---|
| Material Design 官网 | https://m3.material.io/ | 规范正文 | ✅ 可达（SPA，需渲染） |
| M3 Expressive 专页 | https://m3.material.io/blog/building-with-m3-expressive | Expressive 动因 | ✅ 可达（标题/描述可读，正文是 SPA） |
| Material Web（npm） | https://github.com/material-components/material-web ，npm `@material/web` | **可直接复用的 M3 令牌与组件实现** | ✅ GitHub 可达 |
| Material 令牌源仓库 | https://github.com/material-foundation/material-tokens | M3 令牌真源（Apache-2.0，**已 archived**） | ✅ 可达 |
| Material Symbols | https://fonts.google.com/icons | 变体图标字体 | ⚠️ 本机超时（未验证） |
| Material Theme Builder | https://m3.material.io/theme-builder/ | 在线生成 M3 色板 | ⚠️ 未验证 |
| Android Design Kit（Figma） | https://www.figma.com/community | 官方套件 | ⚠️ 未验证 |

---

### 1.4 Material 3 Expressive（2025）：它到底改了什么、为什么改

**时间线与出处**：官方发布稿 *Android and Wear OS are getting a big refresh*（Mindy Brooks，VP of Product Management and User Experiences, Android Platform，2025-05-13）https://blog.google/products-and-platforms/platforms/android/material-3-expressive-android-wearos-launch/ ；研究稿 *Expressive Design: Google's UX Research* https://design.google/library/expressive-material-design-google-research ；播客稿 *Material 3 Expressive – Design Notes*（Liam Spradlin 访谈 Material Design 创意总监 Andy Stewart / UX 研究员 Michael Gilbert / PM Aneesha Kommineni）https://design.google/library/design-notes-material-3-expressive-liam-spradlin
（本地留存正文：`D:\AP\AP7000\ai-workspace\stackchan-research\google-ref\p_blog_m3e_launch_w.txt`、`p_expressive_research_w.txt`、`p_dn_m3_expressive_w.txt`）

#### 1.4.1 官方动因：不是"更花哨"，是"更有情绪 + 更好用"

> "Expressive design makes you feel something. It inspires emotion, communicates function, and helps users achieve their goals."
> "The fundamental parts of expressive design are the use of **color, shape, size, motion, and containment**."
> —— design.google/library/expressive-material-design-google-research（本地 `p_expressive_research_w.txt:10-11`）

研究规模（官方自述，可直接引用到作品集）：
- **46 项独立研究**、数百套设计、**超过 18,000 名参与者**（`p_expressive_research_w.txt:7`）
- 起源故事：2022 年研究实习生发现"为什么 Google 自家 App 都长得一样、无聊"，引发全队设计辩论（`p_expressive_research_w.txt:3-6`）
- 方法：眼动追踪、问卷与焦点小组、实验、可用性测试（`p_expressive_research_w.txt:15-17`）

#### 1.4.2 量化效果（这是最有说服力的一组数字）

| 指标 | 结果 | 出处 |
|---|---|---|
| 18–24 岁用户偏好 expressive 设计 | 高达 **87%** | `p_expressive_research_w.txt:23` |
| 眼动：定位关键 UI 元素速度 | 最快 **4 倍**（10 个 App 随机顺序对比） | `p_expressive_research_w.txt:39` |
| 45+ 用户年龄效应 | 几乎被抹平，与年轻人持平 | `p_expressive_research_w.txt:47-49` |
| 品牌"现代感"（modernity） | **+34%** | `p_expressive_research_w.txt:34` |
| 品牌"亚文化相关性"（subculture） | **+32%** | `p_expressive_research_w.txt:33` |
| 品牌"叛逆感"（rebelliousness） | **+30%** | `p_expressible_research_w.txt:34` |
| 点击关键动作耗时 | 跨多个设计**减少数秒** | `p_expressive_research_w.txt:41-42` |
| 情绪属性评分 | "energetic / emotive / positive vibe / creative / playful / friendly" 全面升高 | `p_expressive_research_w.txt:29-30` |

#### 1.4.3 五个「表达性」增强到底指什么

官方定义的原话是"color, shape, size, motion, containment"五要素（`p_expressive_research_w.txt:11`），落到具体机制：

| 维度 | M3 Expressive 的做法 | 官方描述 | 出处 |
|---|---|---|---|
| **形状夸张度** | 组件形状更"圆、更弹"，并提供 **wiggle shape**（会扭动的形状）变体；创意总监原话："Expressive can mean quiet... For example, loaders and spinners: You can take the basic one… Or you can go expressive and it has more of the **wiggle shape**" | **flexibility 是 M3 Expressive 的定义性原则** | `p_dn_m3_expressive_w.txt:6-7` |
| **Spring motion** | 引入"更自然、更有弹性的动画体系"（springy animations）：滑掉通知时相邻通知会**跟着你的拖拽轻微响应**，甩出时配"满足的触感震动"（haptic rumble） | "introduces a system of more natural, springy animations meant to bring a moment of delight" | `p_blog_m3e_launch_w.txt:31-33` |
| **对比强化 / 层次** | 关键按钮更大、放在键盘正上方、并**用次级色**把注意力拉过来（Send 按钮案例：眼睛 4 倍速度找到） | "making key actions stand out and grouping like elements together" | `p_expressive_research_w.txt:12-13, 42-46` |
| **模糊制造景深** | 下拉面板背景**微微模糊**，制造纵深、让动效显轻 | "We even subtly blur the shade background to provide a sense of depth" | `p_blog_m3e_launch_w.txt:34-35` |
| **动态主题扩展** | 动态取色跨 Google 应用与手表盘面；新增 **responsive components** 与 **emphasized typography** | "Android is also getting updated dynamic color themes, responsive components and emphasized typography" | `p_blog_m3e_launch_w.txt:35-36` |
| **形状变形（响应式形态）** | 元素在不同屏幕尺寸间**形变**（shape-morphing）以适配；表盘圆形屏用"会贴合曲率滚动"的动画；按钮"拉伸贴合圆屏" | "smooth transitions with shape-morphing elements that adapt to the smaller screen size" | `p_blog_m3e_launch_w.txt:43-45` |
| **实时信息卡（Live Updates）** | 把进度类通知做成"一眼可读"的常驻更新（如外卖配送进度） | "glanceable, helpful information" / Live Updates | `p_blog_m3e_launch_w.txt:39-40` |

#### 1.4.4 官方给的"不要用错"清单（对我们尤其重要）

> "Expressive design isn't a one-size-fits-all solution. What works in a media player or email app might not be suitable for something like a **banking interface**."
> 失败案例 1：把音乐歌单换成"专辑封面凌乱排布"→ 用户觉得"现代又刺激"，但**可用性分数下降**，且用户根本没认出那是歌单。
> 失败案例 2：**去掉邮件操作项的文字标签**→ 可用性下降。
> "**No amount of expressive design will beat basic functionality.**"
> —— `p_expressive_research_w.txt:51-58`

官方六条落地建议（`p_expressive_research_w.txt:60-67`）：
1. **Start experimenting**：在更新后的 M3 Design Kit 里试；
2. **Try the tactics**：用 expressive 设计战术，但**要围绕核心用户旅程裁剪**；
3. **Be intentional and start from user need**："虽然鲜艳的 expressive 设计广受欢迎，但**有相当一部分用户更喜欢更平静、更不刺激的版本**。永远从用户需要出发。"
4. **Prioritize functionality**：不要为了视觉花活牺牲核心功能；
5. **Follow accessibility standards**：对比度、屏幕阅读器、导航等；
6. **Iterate, iterate, iterate**：用研究找"新鲜 vs 熟悉、俏皮 vs 专业"的平衡点。

> **对 StackChan 的直接推论**：我们的目标用户是 ENFP 女性用户 → 偏"playful / friendly / positive vibe"是**合适**的；但**说话入口、连接状态、充电提醒这类功能性信息绝不能 expressive 化**（官方 banking 案例）。而且"小栈"本体已经有表情/动画这条 expressive 通道，**iOS 端应该保持克制，把表达性预算全部留给"小栈"这个角色本身**——这正好和"界面要嵌入苹果系统"的用户要求一致。

---

## 2. Google 的 AI 产品设计：视觉与交互决策

### 2.0 官方 AI 设计资料的可达性（2026-10-23 实测，重要前提）

| 资料 | URL | 本机状态 | 能否作为本文依据 |
|---|---|---|---|
| Google Design（设计官方站） | https://design.google/ | ✅ 可达 | ✅ **本文 B/D 节主要依据** |
| Google Blog | https://blog.google/ | ✅ 可达（新品发布稿） | ✅ 产品功能与官方表态 |
| Material 官网 | https://m3.material.io/ | ✅ 可达（SPA） | ⚠️ 仅标题/描述可读 |
| **PAIR / People + AI Guidebook** | https://pair.google.com/ | ❌ DNS 解析失败（`pair.withgoogle.com` 亦超时） | ⚠️ 只能通过 Google Design 转述引用 |
| AI Studio 文档 | https://ai.google.dev/ | ❌ 超时 | ❌ 未验证 |
| Firebase AI Logic | https://firebase.google.com/docs/ai-logic | ❌ 超时 | ❌ 未验证 |
| Vertex AI 文档 | https://cloud.google.com/vertex-ai/… | ❌ 超时 | ❌ 未验证 |
| Android 开发者文档 | https://developer.android.com/design/material/… | ❌ 连接超时 | ❌ 未验证（已用 token 源码替代） |
| Apple HIG | https://developer.apple.com/design/human-interface-guidelines/… | ✅ 可达但**正文是 JS 渲染**，抓到的正文仅 266 字符 | ⚠️ 只作 URL 引用，不作事实依据 |
| Apple 官方文档 API（App Intents / BackgroundTasks） | https://developer.apple.com/documentation/appintents | ✅ 可达（同上，正文未渲染） | ⚠️ 同上 |

> **可引用的 Google 官方 AI 设计文档（design.google，均实测可达）**：
> - `People + AI Guidebook` → https://design.google/library/people-ai-guidebook （本次直抓失败，**正文未验证**）
> - `Demystifying AI: 6 Key Terms for UX Designers` → https://design.google/library/six-ai-terms ✅
> - `Gemini AI Visual Design` → https://design.google/library/gemini-ai-visual-design ✅（**本报告最关键的一份**）
> - `A New Interaction Design Paradigm` → https://design.google/library/a-new-interaction-paradigm ✅
> - `Expressive Design: Google's UX Research` → https://design.google/library/expressive-material-design-google-research ✅
> - `Material 3 Expressive – Design Notes` → https://design.google/library/design-notes-material-3-expressive-liam-spradlin ✅
> - `AI Design Roundtable Discussion` → https://design.google/library/ai-design-roundtable-discussion ✅
> - `Designing for Transparent Screens` → https://design.google/library/transparent-screens ✅
> - `AI is design's latest material` → https://design.google/library/ai-designs-latest-material ✅（正文未逐条引用）

---

### 2.1 Gemini App（对话主界面）

**实测来源**：Google 官方图 `Temporary_Chat.width-1200.format-webp.webp`（blog.google Gemini 博文配图），本机下载 → `mcode-tools connector call connector__matrix__describe_images` 视觉解析，本地留存 `D:\AP\AP7000\ai-workspace\stackchan-research\google-ref\describe_text.txt:29-47`。

| 观察项 | Google 的做法 | 对我们的意义 |
|---|---|---|
| 输入框位置与形态 | **紧贴键盘**的圆角胶囊卡，左上角多行输入占位；框**内底部一行图标**：`+`（附件）、滑杆图标（工具） | 输入区永远是"界面底部一条窄带"，不是整屏留白 → **天然避免聊天框地狱** |
| 语音入口 | 输入框内右侧两个独立控件：**麦克风按钮**（语音转文字）+ **圆形"闪"按钮**（Gemini Live） | **语音转文字**与**实时对话**分成两个入口，用户预期清晰 |
| 模型切换 | 输入框**内**一颗小圆角 chip（本图显示 `2.5 Flash`），点击切换模型 | 能力切换收在输入区，不占导航栏 |
| 隐私态表达 | "Temporary chat" 用**虚线气泡图标 + 居中标题 + 说明卡**，正文里关键词是**蓝色可点链接** | 特殊模式用"一个图标 + 一段说明"，而不是弹窗打断 |
| 图标体系 | **Material Symbols 线性图标**，描边均匀 | 我们 iOS 端若用 Material Symbols 会与 iOS 观感冲突 → 见 D-16 |
| 导航抽屉 | 顶部搜索框、"New chat" 笔形图标、**Gems**（自定义彩色首字母头像 `M`、代码括号 `<>`、gem/闪符号）、Pinned 对话带图钉 | "能力"被做成一排**彩色小图标**，而不是文字列表 |

**关键判断**：Gemini App 的主界面**几乎没有"AI 感"**——它就是聊天 + 一排图标。AI 的存在感来自**输入框右侧那颗闪**和**抽屉里的 Gems 图标**，而不是横幅、标签、"AI 助手"标题。这与"苹果把 AI 藏进系统"的直觉其实一致。

---

### 2.2 Gemini Live：Google 怎么表达"正在听 / 正在想"

**实测来源**：Google 官方博客 *How to use Gemini Live with camera and screen sharing*（2025-04-07，Isha Sheth, Sr. PM Gemini app）https://blog.google/products-and-platforms/products/gemini/gemini-live-android-tips/ + 官方配图视觉解析（`describe_text.txt:49-67`）。

| 观察项 | 实测结果 | 出处 |
|---|---|---|
| 摄像头/屏幕共享态的界面 | **取景器占满上部，底部两角圆角 24–28dp**；取景器右下角一个半透明圆形"切换摄像头"按钮 | `describe_text.txt:49-51` |
| 底部控制 dock | 深色底（#10141D~#000000）+ **一排 4 个圆角胶囊按钮**：① 摄像头（**激活时白底深色图标**）② 屏幕共享 ③ **暂停 `‖`（会话进行中）** ④ **红色挂断 `✕`（#D93025）** | `describe_text.txt:54-58, 63-65` |
| **状态文字** | **完全没有** "Listening…/Thinking…/Speaking…" 这类文字标签 | `describe_text.txt:59-61` |
| **状态波形/光晕** | 该状态下**没有**可见的波形、脉冲圆环、Gemini 光晕 | `describe_text.txt:59-61` |
| 状态如何被感知 | 靠**图标状态**（白底=摄像中、`‖`=会话进行中、红`✕`=结束） | `describe_text.txt:61-62` |
| 排版 | 该状态下**完全没有文字排版**，纯图标沟通 | `describe_text.txt:66-67` |
| 会话能力 | 摄像头/屏幕共享；**45+ 种语言的自由对话** | `p_blog_gemini_live_w.txt:26` |

> **这就是 Google 回答"如何表达正在听/正在想"的方式**：**默认不给文字状态**。状态被压进"按钮长什么样"，只在**看不清上下文的时候**才用文字。
> 对我们的直接结论：**"小栈在听/在想"不该是文字标签**，而应该是**小栈这个角色本身的表情/动画**（它有 320×240 的屏，天然是"脸"）——这是我们比 Gemini 更强的地方：Gemini 没有脸，只能靠图标；小栈有脸。

---

### 2.3 NotebookLM：把"生成物"做成"可播放的内容"，而不是"聊天记录"

**实测来源**：Google 官方博客 *NotebookLM now lets you listen to a conversation about your sources*（2024-09-11）https://blog.google/innovation-and-ai/products/notebooklm-audio-overviews/ ；*New in NotebookLM: Customizing your Audio Overviews and introducing NotebookLM Business*（2024-10-17）https://blog.google/innovation-and-ai/products/notebooklm-update-october-2024/ ；官方配图视觉解析（`describe_text.txt:1-28, 68-87`）。

**① Audio Overview 的产品决策**
- 一次点击，**两个 AI 主持人**就你的资料开始 "deep dive" 对话式讨论；可下载、可在后台听（`p_blog_nlm_audio_w.txt:36`、`p_blog_nlm_oct24_w.txt:35`）
- 生成**需要几分钟**（大笔记本更久），官方明确标注为实验性、会有事实不准、起初只支持英语（`p_blog_nlm_audio_w.txt:28, 43`）
- 用户**可以在生成前给指令"引导对话"**（Guide the conversation：指定 AI 主持人关注什么/以什么身份谈）（`p_blog_nlm_oct24_w.txt:33-36`）
- **Background listening**：一边听音频一边继续查资料、拿引用，**不打断音频**（`p_blog_nlm_oct24_w.txt:35-36`）

**② 界面结构（视觉解析实测）**
| 区域 | 实测细节 |
|---|---|
| 整体 | **左栏源列表（约 22%）+ 右主区（约 78%）**；内容放在**大圆角白卡（~24px 圆角）**上，浮在冷灰底（#F0F4F9）上 —— 典型 M3 容器语言 |
| 左栏 Sources | 标题 + 筛选/排序图标 + `+` 加源；每条 = **按文件类型着色的图标**（Slides/Notes 黄、Docs/Sheets 蓝、PDF 红）+ 截断文件名 + 右侧复选框（全部勾选态） |
| 主卡 "Notebook guide" | 左列：✨ 图标 + 标题 → **"Help me create" 胶囊 chip 行**（Table of contents / Study guide / FAQ / Briefing doc / Timeline）→ "Summary" 小节（正文里**关键词加粗**）<br>右列：**Audio Overview 播放器** → "Help me understand" **预生成问题卡**（浅灰蓝圆角卡，3 张） |
| 播放器 | 圆角 ~12px 白卡 + 1px #E0E3E7 描边；标题左对齐，右上角 👍 👎 ⋮ 三个线性图标；播放键 = **浅蓝圆底 #D3E3FD + 深蓝三角 #0B57D0**；时间戳 11–12px 灰；进度 = 圆角细条，已播 **#1A73E8**、未播淡紫灰 |
| 底部浮动条 | 左：**"View chat" 文字按钮 + 对话气泡图标**（蓝色文字）；中：胶囊输入条内含 **"12 sources" 灰 chip** + "Start typing..." + 右端**圆形蓝底白箭头**提交键；右：**"Notebook guide ∨" 下拉 + 蓝色✨图标** |
| Studio（视频概览） | **2×2 卡片矩阵**，每个卡片一个**低饱和粉彩底 + 主题图标**：Audio 薰衣草蓝（声波）、Video 薄荷绿（播放三角）、Mind Map 淡玫瑰（节点树）、Reports 米色（文档堆）；主视觉是 **#4F6BFF→#A8F5B8 线性渐变** + 中央半透明白播放键（三角顶点带✨）；播放控制为 -10 / 1X / 大号圆形暂停 / +10 / 全屏 |
| Mini player | 源面板底部**常驻迷你播放条**（蓝暂停键 + 标题 + 迷你进度 5:12/7:52 + 👍👎⋮✕），可边听边用 |

> **NotebookLM 的核心不是"AI 聊天"，而是"AI 产物有独立形态"**：音频概览是一种**内容类型**，有自己的播放器、可以后台播放、可以引导、可以下载；视频概览是另一种类型，有 Studio 入口矩阵。
> 对我们：**小栈的"陪伴"应该是多种产物形态**（语音、表情、动作、记忆卡片），而不是一段聊天气泡。

---

### 2.4 Google 的 AI 界面设计原则（官方原话，可直接进作品集）

来自 Google Design `AI Design Roundtable Discussion`（Rachel Been / Öznur Özkurt / Jess Holbrook）（本地 `p_ai_roundtable_w.txt`）：

| 官方原话 | 出处 | 对我们的含义 |
|---|---|---|
| "**It's important to not heroize technology**, and instead see it as a tool that can lead to a better experience for the user." | `:27-28` | **本报告的题眼**：谷歌自己都说"别把技术当主角"。AI 应该是工具，不是主角 |
| "we're reminding people of what we know works, which is to **put people first** and work from there"（Jess Holbrook, PAIR） | `:12-14` | 从人的需求出发，而不是从"我们能调什么 API"出发 |
| "We're setting up the **scaffolding** so our users can understand this new technology"（Rachel Been, Material 创意总监） | `:7-8` | AI 界面是**脚手架**，用来帮人理解技术，不是展示技术 |
| "What if the user gets an error? What if she wants more **transparency into what the AI is doing**? How do you onboard her" | `:14-16` | AI 界面必须自带**失败态**与**透明度**设计 |
| "the algorithm can show the user **what it's thinking by outlining what it sees**" | `:20-22` | 不需要展示算法，要展示**它看到的东西** |
| "It was actually a **terrible user experience because it worked too quickly for the user to comprehend**… should we cater to people's idea of how computation works, and **inhibit speed in order to give the user a moment to understand the action occurring**?"（ML Kit Object Detection 案例） | `:24-27` | **生成中/流式状态的心理学依据**：AI 太快反而让人看不懂；需要"可感知的处理中" |
| "AI allows you to escape the **scale of cause-and-effect relationships that humans are used with**… explaining it so people can actually understand it — that's a fundamental human-centered AI design challenge" | `:17-19` | 陪伴型 AI 更严重：要让人相信"这是小栈在说" |

来自 `Gemini AI Visual Design`（Google 设计团队自述，本地 `p_gemini_visual_design_w.txt`）：

| 官方原话/做法 | 出处 | 对我们的含义 |
|---|---|---|
| 渐变是**"context builder"**：**前缘锐利近乎不透明，尾部弥散**，像箭头一样指向当前最重要的东西 | `:15-17` | 我们的"小栈正在想"渐变应当**有方向**，而不是随便一团彩虹 |
| **"Concentrated and diffused gradients are used when transcribing voice"**（语音转写时用"聚拢→弥散"渐变） | `:17-19` | 语音态的视觉语言：**聚拢 = 在听，弥散 = 在说**，一个形状走完两个状态 |
| 圆形是 Gemini 的**基础形状**（logo 本身由四个圆的负空间构成）；按钮/容器都**回响圆形** | `:19-27` | 小栈的头/屏是圆的 → iOS 端所有主要控件也走圆形语言，与设备形态统一 |
| Material 形状被**软化+模糊**以获得"ethereal"质感；插画要有 **"warm, spatial, rounded quality"** | `:24-25, :30-31` | 我们的插画/表情基调：暖、空间感、圆 |
| "**Movement in Gemini is not merely decorative; it's an essential guiding element.** Each animation has a defined start and end point… **Inner activity within the motion conveys thinking, analysis, and intelligence**" | `:33-36` | **"在想"= 内部运动**，不是外部转圈 |
| "The **speed** of movement gives a sense of **anticipation, then release**. A **rippling motion in a radial gradient** can be used for **voice waves**." | `:36-37` | 语音波形 = **径向渐变的涟漪**；速度 = 期待感 → 释放感 |
| "Gradients guide a user's eye to introduce feature icons. **Icons can be animated** to indicate new features." | `:37` | 动效用来**引导视线**，不是装饰 |
| "**When a system is hard to approach, the design must be soft.**" — 靠"guided, pulsing gradient shapes, clear language, and transparent signaling" | `:44-45` | 陪伴产品对新用户尤其适用：**柔和 + 透明信号** |
| 官方说 Gemini 的目标气质是 "optimistic, delightful, playful, **yet also sophisticated**" | `:30-32` | 和用户要求「简约 + 不堆砌」一致：**playful 但要精致** |

---

## 3. 谷歌 vs 苹果：两种 AI 界面哲学（本报告最重要的一节）

### 3.1 事实对照表

| 维度 | **苹果**：把 AI 藏进系统 | **谷歌**：把 AI 做成主角 | 证据 |
|---|---|---|---|
| AI 的位置 | **App Intents** 把 App 的动作与数据结构化暴露到系统里，让它们"被 Apple Intelligence 发现"；Siri / Spotlight / 快捷指令三处消费 | AI 有**专属入口、专属 App、专属视觉符号**（Gemini App、闪图标、渐变） | Apple DocC `App Intents`："express your app's actions and data in a structured way that makes them **discoverable by Apple Intelligence**… People can interact with your app's content through **Siri** / **Spotlight** / **The Shortcuts app**"（`p_docc_appintents`，本地 JSON）；Google：`describe_text.txt:29-47`（输入框内独立 Live 闪按钮、Gems 图标） |
| 入口 | **没有"AI 入口"**：AI 出现在原有系统位置（搜索栏、通知、写作工具、相册） | **AI 入口是首屏控件**：输入框右侧的麦克风 + 闪按钮；独立 Siri App；Google Labs | apple.com/apple-intelligence（"Write with Siri"、"Visual Intelligence"、"Introducing the Siri app"）；`describe_text.txt:32-33` |
| 等待/生成中的表达 | 系统级进度（活动指示器、Live Activity），**没有"AI 正在思考"的表情符号** | **有专用的"thinking state"视觉**：渐变、涟漪、动效、四色点 | `p_gemini_visual_design_w.txt:17-19, 22-24, 33-37` |
| 打断策略 | **不打断**：后台任务、通知、Live Activity、Siri 在 CarPlay "keeps you informed without taking your hands off the wheel" | **对话式、可打断**：Gemini Live 是持续会话（45+ 语言），NotebookLM 支持"边听边用，不打断音频" | apple DocC `Background Tasks`："run tasks requiring minutes to complete even if your app is in the background"；`p_apple_intelligence_w.txt:17-18`；`p_blog_nlm_oct24_w.txt:35-36` |
| 产物形态 | AI 结果**混在原功能里**（写作工具就地改写、相册生成图） | AI 产物是**独立内容类型**（Audio Overview / Video Overview / Mind Map / Reports），各自有播放器与 Studio 矩阵 | `describe_text.txt:75-78`（Studio 2×2 卡片矩阵） |
| 品牌气质 | 克制、系统化、组件化 | 情绪化、playful、渐变、插画、"warm, spatial, rounded quality" | `p_gemini_visual_design_w.txt:30-32` |
| 官方自述的价值观 | "Integrated into your apps, grounded in your context, and private at every step" | "**not heroize technology**… see it as a tool"；"put people first" | apple.com/apple-intelligence；`p_ai_roundtable_w.txt:12-14, 27-28` |

> ⚠️ **重要发现**：两派的官方表述其实**并不对立**。谷歌自己的设计总监 Rachel Been 明确说 **"It's important to not heroize technology, and instead see it as a tool that can lead to a better experience for the user"**（`p_ai_roundtable_w.txt:27-28`）。也就是说——
> **"谷歌把 AI 做成主角"是产品形态上的表象（Gemini 有专属 App），不是设计价值观；谷歌的设计价值观其实是"人优先、技术做配角"。**
> 真正需要做的选择不是"抄苹果还是抄谷歌"，而是：**AI 的存在感应该放在哪里**——放在**界面 chrome** 上（苹果式），还是放在**角色**上（陪伴式）。

### 3.2 我们的场景判断：这是"陪伴型控制端"，不是"AI 工具"

用户不是来"用 AI"的，是来**陪一只小机器人**。据此逐条判定：

| 我们的界面元素 | 该用哪派 | 理由（带出处） |
|---|---|---|
| 导航结构、列表、表单、设置 | **苹果**（iOS HIG） | 用户要求"嵌入苹果系统"；Google 的 M3 容器语言与 iOS 观感冲突 |
| 日常交互（滑动、返回、长按、震动） | **苹果** | 系统原生手势不可替代 |
| **"小栈在听/在想/在说"** | **谷歌的思路，但载体换成小栈的脸** | 谷歌证明了"过程要可见"（Object Detection 太快反而看不懂，`p_ai_roundtable_w.txt:24-27`），但它的载体是**渐变/涟漪**；我们有**一张 320×240 的脸**，比渐变强得多 |
| **流式回复** | **两者都要**：结构用苹果（原生 TextView 流式打字），过程用谷歌（可感知但低干扰） | 谷歌说渐变"sharp leading edge diffuses at tail"是指向性指针（`p_gemini_visual_design_w.txt:15-17`），我们要的是**低干扰**版本 |
| **主动行为**（小栈定时提醒、自己去做事） | **苹果**（Background Tasks / 通知 / Live Activity） | 陪伴型产品的核心是"它在我不打开 App 时也活着" |
| **能力暴露**（拍照、对话、跳舞、换表情、记忆回顾） | **苹果的 App Intents 范式 + 谷歌的图标语言** | App Intents 让能力**被系统发现**而不是在 app 里堆列表；谷歌把能力做成一排彩色图标（`describe_text.txt:40-42`） |
| **情绪/人格** | **谷歌**（M3 Expressive 的 expressive 预算） | 官方数据：18–24 岁偏好 expressive 达 87%，现代感 +34%（`p_expressive_research_w.txt:23, 34`）；且"expressive 可以很安静"（`p_dn_m3_expressive_w.txt:6`） |
| **设置页、权限、账号** | **苹果** | 功能性信息不能 expressive 化（官方 banking 案例，`p_expressive_research_w.txt:51-53`） |

### 3.3 苹果这一侧：AI 是怎么被"藏起来"的（机制拆解）

| 机制 | 官方定义（可引用） | 界面上的样子 | 对我们的等价物 |
|---|---|---|---|
| **App Intents** | "express your app's actions and data in a structured way that makes them discoverable by Apple Intelligence"；"People can interact with your app's content through **Siri**" / "**Spotlight** helps people navigate to your data directly from search results" / "The **Shortcuts app** helps people configure workflows that include your app's actions" | App 内**不出现** AI 按钮；能力出现在**快捷指令 App / 搜索 / 聚焦**里 | 把"跟小栈聊天""让小栈拍照""让小栈讲个笑话"做成 App Intent → 用户在快捷指令里搭自动化 |
| **Background Tasks** | "keep your app content up to date and run tasks requiring **minutes to complete** even if your app is in the background"；前台任务被打断时可在后台续做 | 没有界面；只有通知 | 小栈的定时提醒/每日回顾/情绪日志更新都在后台跑 |
| **Apple Intelligence 融入既有功能** | "Integrated into your apps, grounded in your context, and private at every step" | 写作工具就地改写；视觉智能在相机/截屏里 | 小栈的 AI 能力**长在已有功能上**（对话页、回忆页），不新开"AI 中心" |
| **Siri 的可调参数** | "**Customize how Siri sounds. Pick a voice, then customize expressivity and pace until it clicks for you.**"（`p_apple_intelligence_w.txt:16-17`） | 声音设置页里调"表达力/语速" | **小栈的性格参数化**：语速、音调、话痨程度、主动性 —— 这是陪伴产品的核心开关，Apple 用系统语音设置做了同样的事 |
| **不打扰的持续告知** | "Siri AI in CarPlay keeps you informed **without taking your hands off the wheel**" | 只用系统通知/Live Activity | 小栈状态变化 → 通知/Live Activity，不弹窗 |

> **一句话结论（苹果侧可抄的）**：**把 AI 的能力做成"系统可发现的结构化动作"，把 AI 的存在感做成"可选的参数"，而不是做成一个必须被看见的界面。**
>
> ⚠️ **与同目录文档的分工**：Apple HIG 与 Liquid Glass 的**官方原文**由 `docs/research/10-AppleHIG官方核实.md` 核实（含"内容层不要用 Liquid Glass"等官方明令），本文不重复抓取 HIG 正文（HIG 页面正文由 JS 渲染，本机抓不到，见 U-08/U-09）。**涉及具体字号/材质/色值时，以 10 号文档为准。**


### 3.4 我们该抄哪一派？（决策）

**结论：以苹果为"壳"，以谷歌为"过程与产物"，以小栈的脸为"AI 的化身"。**

1. **结构层 100% 苹果**：iOS 原生导航、原生控件、原生手势、后台任务、通知、Live Activity。理由：用户明确要求"嵌入苹果系统"，且 Google 自述"not heroize technology"。
2. **AI 的"过程"抄谷歌，但降噪**：谷歌用渐变/涟漪/内层运动表达 thinking；我们改用**小栈的表情与动作**（设备屏就在那儿），把"AI 感"从 UI 移进**角色**。这样既满足"过程可见"，又不破坏 iOS 原生观感。
3. **AI 的"产物"抄谷歌**：小栈的回应不应只有一段文字气泡——它可以是**一句话 + 一个动作 + 一个表情 + 一张记忆卡**（对应 NotebookLM 的"产物有形态"，但形态是机器人行为）。
4. **情绪预算抄谷歌，人格参数抄苹果**：M3 Expressive 的 expressive 用在**小栈人格**上（表情、动作、语音、插画），而不是用在 App 壳上；设置项则按 Apple 方式做成"表达力/语速"这类可调参数。
5. **明确不抄**：Material 动态取色（iOS 无此机制且会破坏原生观感）、Material 容器色阶（iOS 系统已有）、Material Symbols 线性图标（会与 SF Symbols 打架）、Google 的大圆角+厚描边 Material 卡片语言。

---

## 4. 可抄的具体做法清单（25 条，格式：做法 —— 来源 —— 怎么落到我们的 iOS App）

> 每条的"来源"均为本报告已验证的官方文档/官方截图解析；"落地"均对齐我们已有的 apple-minimal 令牌（见 `01-apple-minimal-我们的iOS方向.md:588-625`）。

### 4.1 状态与"生成中"（陪伴产品的生死线）

**D-01｜状态不要做成文字标签，交给小栈的脸** —— 来源：Gemini Live 摄像头态实测**完全没有** "Listening/Thinking/Speaking" 文字、也没有波形或光晕，状态全靠按钮形态表达（`describe_text.txt:59-61, 66-67`） —— 落地：iOS 端**不写**"正在聆听…/正在思考…"。设备在线时状态由小栈屏上的表情承担；设备离线或 App 在前台没有设备画面时，才降级为一行 12pt `secondaryLabel` 文案。

**D-02｜"在想"＝内部运动，不是外部转圈** —— 来源：Gemini 视觉体系"**Inner activity within the motion conveys thinking, analysis, and intelligence**"（`p_gemini_visual_design_w.txt:35-36`） —— 落地：小栈思考时只动**内部元素**（眼睛微眯、腮红轻微起伏、耳朵抖一下），**外部轮廓保持静止**；iOS 端对应只在头像内部做 1–2px 位移/缩放。

**D-03｜语音波形用"径向涟漪"：聚拢 → 弥散** —— 来源："A **rippling motion in a radial gradient** can be used for **voice waves**"与"**Concentrated and diffused gradients** are used when transcribing voice"（`p_gemini_visual_design_w.txt:36-37, 17-19`） —— 落地：设备端做一圈从中心聚拢再散开的涟漪（对应"在听"→"在说"）；iOS 端用同一套语义：麦克风按钮上的环形涟漪，**不做上下跳动的柱状波形**（iOS 原生的 `AVAudioRecorder` 波形是柱状，Material 是涟漪，**抄涟漪**）。

**D-04｜刻意保留一点"可感知的处理时延"** —— 来源：ML Kit Object Detection 案例："It was actually a **terrible user experience because it worked too quickly for the user to comprehend**… should we… **inhibit speed in order to give the user a moment to understand the action occurring**?"（`p_ai_roundtable_w.txt:24-27`） —— 落地：小栈收到语音后先给 **200–400ms 的"接收"反馈**（耳朵动一下 / 屏幕闪一下），再进入思考态，再进入说话态。**不要追求"零延迟到达"**，这正是 Google 用研究证明过的 UX 陷阱。

**D-05｜渐变必须有方向，不能是一团彩虹** —— 来源："Gradients… feature **sharp, almost opaque leading edges that diffuse at the tail**, acting as **visual pointers** to direct user attention toward what’s most important"（`p_gemini_visual_design_w.txt:15-17`） —— 落地：全 App 只保留 **1 个渐变**（设备状态色带），方向统一为**自下而上聚拢到小栈**，指向"正在发生的事"。

**D-06｜把 Material 的"角色化取色"搬到 iOS，seed 换成设备状态** —— 来源：M3 的 `md.sys.color.* → md.ref.palette.*` 角色映射（`tokens_color.txt:28-70, 87-129`）与 0–100 tonal palette（`tokens_palette.txt:19-67`） —— 落地：定义 6 个语义角色 `accent / bg / surface1 / surface2 / labelPrimary / labelSecondary`；**seed = 小栈当前情绪色**（或电量/温度派生色）；用 tonal palette 算法把 seed 展开成 tone 阶梯，再映射到角色。深浅色模式各一套 tone（对应 M3 的 light/dark 两套映射）。iOS 侧用 `UITraitCollection` 的 `.dark` 分支切换，系统控件仍用 `UIColor.label` 等语义色。

**D-07｜把 M3 的 7 档 shape scale 收敛我们的圆角** —— 来源：`corner-none 0 / extra-small 4 / small 8 / medium 12 / large 16 / extra-large 28 / full 9999`（`tokens_shape.txt:17-31`） —— 落地：我们现有圆角是 13/16/22/23/28/9999（`01-...md:600-607`），**建议统一成 M3 的 6 档**：13→12、16→16、22→16 或 28、23→12、28→28、9999 保留。收益：全 App 圆角只有 6 个值，可用 lint 卡死。

**D-08｜字号行高直接对齐 M3 type scale（但字族用 SF Pro）** —— 来源：M3 type scale 实测值（`tokens_typescale.txt`；完整表见 1.3②） —— 落地：正文 **16/24**、次要正文 **14/20**、小字 **12/16**、标题 **22/28**、大标题 **28/36**，字重只用 **Regular 400 / Medium 500 / Semibold 600**（替代 M3 的 700）。**不要引入 Roboto**（`tokens_ref_typeface.txt:16-17` 证明 M3 用的就是 Roboto，但 iOS 上必须用系统字体）。

**D-09｜动效时长只用四档，缓动只用两条** —— 来源：M3 motion tokens（`tokens_motion.txt:17-52`） —— 落地：微交互 **150ms**、组件进出 **300ms**、页面转场 **450ms**、AI 生成进度 **700–1000ms**；进入用 `cubic-bezier(0,0,0,1)`（iOS ≈ `curveEaseOut`），退出用 `cubic-bezier(0.3,0,1,1)`（≈ `curveEaseIn`）。iOS 侧用 `UIViewPropertyAnimator(duration:curve:)` 表达，**不上 spring**（spring 是 Expressive 的事，见 D-24）。

**D-10｜层级靠容器色，不靠堆阴影** —— 来源：M3 用 `surface-container-lowest/low/container/high/highest` 五级色阶替代 M2 阴影（`tokens_color.txt:61-70`；实测 hex 见 1.3④） —— 落地：iOS 用 `secondarySystemGroupedBackground`（≈container）/ `tertiarySystemGroupedBackground`（≈container-high）+ `separator` 细线；阴影只保留**一层**（对应我们的 `--shadow-1`），卡片不再叠 `--shadow-2/3`。

### 4.2 布局与"避免聊天框地狱"

**D-11｜输入区永远是贴底的一条窄带** —— 来源：Gemini App 输入框**紧贴键盘**、框内一行图标（`describe_text.txt:30-33`） —— 落地：iOS 用 `safeAreaInset(edge:.bottom)` 放输入条；聊天区独立滚动；键盘弹出时输入条跟随而不是盖住内容。

**D-12｜语音转文字 与 实时对话 分成两个入口** —— 来源：Gemini 输入框内**麦克风按钮**与**独立圆形闪按钮**并存（`describe_text.txt:32-33`） —— 落地：麦克风 = 语音转文字（转写结果**可编辑再发送**）；圆形"说话"按钮 = 与小栈实时对话（可打断）。两者图标与位置分开，**不要合成一个**。

**D-13｜能力做成一排彩色图标，而不是文字菜单** —— 来源：Gemini 抽屉里的 **Gems**：彩色首字母头像 `M`、代码括号 `<>`、gem/闪符号（`describe_text.txt:40-42`） —— 落地：陪伴页顶部放 4–6 个能力图标（拍照/对话/跳舞/换表情/回忆/定时提醒），每个图标带**自己的粉彩底色**（取自小栈人格色板），点开才进详情。

**D-14｜特殊模式用"一个图标 + 一段说明"，不用弹窗** —— 来源：Gemini Temporary chat 用**虚线气泡图标 + 居中标题 + 说明卡**，关键词做蓝色可点链接（`describe_text.txt:35-38`） —— 落地：离线模式/隐私模式用虚线气泡图标 + 居中说明卡替代 `alert`。

**D-15｜空白输入框永远配 3 张"预生成问题卡"** —— 来源：NotebookLM "**Help me understand**" 预生成问题卡（浅灰蓝圆角卡）（`describe_text.txt:19-21`） —— 落地：对话页空态给 3 张卡（基于时间/天气/最近记忆生成，如"今天有件事想说吗？"），点一下直接发送。

**D-16｜用"引导型胶囊 chip"代替功能菜单** —— 来源：NotebookLM "**Help me create**" 胶囊 chip 行：Table of contents / Study guide / FAQ / Briefing doc / Timeline（`describe_text.txt:16-17`） —— 落地：一排胶囊 chip（讲个笑话 / 陪我安静一会 / 背个单词 / 回顾昨天），**点一下直接触发**，不做二级菜单。

**D-17｜把数字徽标放进输入条内部** —— 来源：NotebookLM 底部胶囊输入条内的 "**12 sources**" chip + 右端圆形蓝箭头提交键（`describe_text.txt:22-24`） —— 落地：输入条左侧放"12 段记忆"chip，点开是记忆抽屉；提交键用圆形蓝底白箭头。

**D-18｜AI 产物有独立形态 + 常驻迷你播放器** —— 来源：NotebookLM 的 Audio/Video Overview 是独立内容类型，源面板底部常驻 mini player（暂停键 + 标题 + 迷你进度 + 👍👎⋮✕）（`describe_text.txt:20-21, 75-83`） —— 落地：小栈的"语音留言"和"今日回忆"是独立卡片形态，各带播放器；回忆页有常驻 mini player，**边听边浏览**（抄 Google 的 Background listening，`p_blog_nlm_oct24_w.txt:35-36`）。

**D-19｜主动行为走通知 / Live Activity，绝不弹 app 内 modal** —— 来源：Apple `Background Tasks`："run tasks requiring minutes to complete even if your app is in the background"（`p_docc_backgroundtasks`）；Apple 官方："Siri AI in CarPlay keeps you informed **without taking your hands off the wheel**"（`p_apple_intelligence_w.txt:17-18`） —— 落地：小栈想说话 → 锁屏通知 + Live Activity（当前心情、正在做的事、语音留言）；**app 打开时不弹窗**，只在陪伴页顶部出现一条可点的横幅。

**D-20｜人格做成可调参数（抄 Apple 的"表达力/语速"）** —— 来源：Apple："**Customize how Siri sounds. Pick a voice, then customize expressivity and pace until it clicks for you.**"（`p_apple_intelligence_w.txt:16-17`） —— 落地：设置里给"小栈性格"四个滑杆：**话痨度 / 主动性 / 语速 / 吐槽度**，直接沿用 Apple 的命名逻辑（expressivity / pace 的中文对应）。

### 4.3 透明、失败与人格

**D-21｜失败态与透明度同权** —— 来源：Rachel Been："What if the user gets an error? What if she wants more **transparency into what the AI is doing**?"（`p_ai_roundtable_w.txt:14-16`）；以及"the algorithm can show the user **what it’s thinking by outlining what it sees**"（`:20-22`） —— 落地：小栈听不懂时，给**"我没听懂" + 2 个候选意图 + 明显可点的"换个说法"**，同时在小栈屏上显示它"听到的片段"（不是原始音频，是转写关键词）。

**D-22｜少用大面积渐变，渐变只给小尺寸元素** —— 来源：Gemini 渐变设计里"a gradient is **a vibe**"（对比 Kare 的图标是"an object"）（`p_gemini_visual_design_w.txt:12-14`） —— 落地：不做渐变卡片；渐变只出现在：设备状态色带、语音涟漪、能力图标底色。

**D-23｜分级回复：即时回应不入历史，完整内容进时间线** —— 来源：Gemini App 与 NotebookLM 都把"生成物"与"对话流"分开呈现（`describe_text.txt:16-24`） —— 落地：聊天气泡里只留 **≤2 行的即时回应**（"嗯嗯，我在听"）；**完整回答进时间线卡片**（可展开、可保存为记忆）。这条直接对治"聊天框地狱"。

**D-24｜Expressive 预算只给小栈，不给功能性信息** —— 来源：官方 banking 反例与"expressive can mean quiet"（`p_expressive_research_w.txt:51-53`、`p_dn_m3_expressive_w.txt:6`） —— 落地：设置 / 连接 / 电量 / 权限页 **100% iOS 原生**；陪伴页允许 playful（表情、插画、语音、卡片形状）；**"说话"入口可用 M3 Expressive 的 wiggle 形状**（加载器/微光标可以"会扭"，抄官方原话）。

**D-25｜正文靠单一强调色 + 关键词加粗做可扫读性** —— 来源：NotebookLM Summary 里关键词**加粗内联**（`describe_text.txt:17-18`）；M3 的 `on-surface` / `on-surface-variant` 层级（`tokens_color.txt:43-44`） —— 落地：正文用 `secondaryLabel` 级灰（不是纯黑），人名/时间/地点等实体用强调色 + Medium 字重；单屏只允许 **1 种强调色**。

---

## 5. 工具与素材

### 5.1 本机实际可用的图像/设计能力（mcode-tools，全部实测）

| 能力 | 命令 | 实测状态 | 说明 |
|---|---|---|---|
| 找参考图 | `mcode-tools connector call connector__matrix__search_images --args-file <json>` | ✅ **实测通过** | 每 query 返回 10 张图，含 `title / image_url / source / link`；本次用它定位到 Google 官方博客配图、design.google 文章配图、Figma 素材 |
| 看图 | `mcode-tools connector call connector__matrix__describe_images --args-file <json>` | ✅ **实测通过**（6 张） | **只接受 HTTPS URL**；本地文件必须先 `mcode-tools upload_temp_url <file>` 拿 temp_url 再传；参数必须用 `image_info[]` 数组 |
| 上传本地文件 | `mcode-tools upload_temp_url <local>` | ✅ **实测通过** | 返回 OSS 临时 URL（实测 `x-oss-expires=3600`，1 小时有效）；webp/jpg 建议带 `--mime-type` |
| 生成插画/表情 | `mcode-tools connector call connector__matrix__generate_image` | 🟡 **已发现，未实测** | 文生图/图生图；成功返回 `success_items[].node_id`，需再 `mcode-tools get_asset_url <node_id>` 取下载地址 |
| 反查图片来源 | `mcode-tools connector call connector__matrix__reverse_image_search` | 🟡 **已发现，未实测** | 仅传 `image_url` |

> 本次研究产出的落地物：Google 官方配图 6 张已存 `D:\AP\AP7000\ai-workspace\stackchan-research\refimages\g01..g06`（M3 Expressive 头图 / NotebookLM 音频概览 UI / Gemini Live 摄像头态 / Gemini App 输入区 / NotebookLM Video Overview / Gemini Live 头图），视觉解析文本存 `...\google-ref\describe_text.txt`。
> 已有的 iOS 26 参考图 10 张在同一目录（`01-ios26-home.jpg` … `10-ios26-tabbar-wa.webp`），本次可直接复用。

### 5.2 Google 官方设计资产（真实 URL + 本机实测状态）

| 资产 | URL | 本机实测 | 我们怎么用 |
|---|---|---|---|
| Material Design 官网 | https://m3.material.io/ | ✅ 可达（SPA） | 查规范正文 |
| M3 Expressive 专页 | https://m3.material.io/blog/building-with-m3-expressive | ✅ 可达（标题实测："M3 Expressive: Engaging UX Design"） | 查 Expressive 组件 |
| **Material Theme Builder** | https://m3.material.io/theme-builder | ✅ **200** | 生成/校对色板 |
| **Material Symbols 图标** | https://fonts.google.com/icons | ⚠️ 超时；但 **Google Fonts API ✅**：`https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200`（实测返回 v380 可变字体，轴：opsz / wght / FILL / GRAD） | **iOS 端不用**（见 5.3）；Android 端或需要 M3 语义时用 |
| **Material 3 Design Kit（Figma）** | https://www.figma.com/community/file/1035203688168086460 | ✅ **200，标题实测 "Material 3 Design Kit \| Figma"** | 看官方组件怎么搭、抄结构不抄样式 |
| **Material Web（npm）** | https://www.npmjs.com/package/@material/web | ✅ npm registry 实测 **2.5.0 / Apache-2.0** | 只取令牌与结构参考，**不引入到 iOS 工程** |
| Material 令牌真源 | https://github.com/material-foundation/material-tokens | ✅ GitHub API 实测：**Apache-2.0 / stars 284 / `archived: true` / 最后 push 2023-08-15** | **只读数值参考，不作为依赖** |
| Google Design（设计官方站） | https://design.google/ | ✅ 可达 | **本文 B/D 节主要来源** |
| Google Blog | https://blog.google/ | ✅ 可达 | 产品功能与官方表态 |
| Apple SF Symbols | https://developer.apple.com/sf-symbols/ | ✅ 200 | **iOS 端图标唯一来源** |
| Apple Design Resources | https://developer.apple.com/design/resources/ | ✅ 200 | 模板/资源 |

### 5.3 图标与字体决策（避免"两套语言"）

- **iOS 端图标：一律 SF Symbols**。理由：Gemini App 用 Material Symbols（`describe_text.txt:39`），但我们要在 iOS 上"嵌入苹果系统"；Material Symbols 的均匀描边与 SF Symbols 的粗细轴不匹配，混用会露馅。
- **Material Symbols 的唯一合法用途**：Android 端小栈屏 UI，或需要和 M3 组件做一一对应时参考。
- **插画/表情**：小栈的 320×240 屏是矢量像素画（见 `01-apple-minimal-我们的iOS方向.md` 的"小栈画法"一节），**不靠 AI 生图做正脸**；AI 生图只用于陪伴页插画、卡面背景、App 图标初稿。
- **字体**：一律 SF Pro / SF Mono，**不引入 Roboto**（M3 的参考字体就是 Roboto，`tokens_ref_typeface.txt:16-17`，但 iOS 上不适用）。

---

## 6. 可复用方案

可复用方案：
  - **Material Web（`@material/web`）**  用途：M3 令牌 + 组件实现（唯一"官方的 M3 代码"）  许可/协议：Apache-2.0（npm registry 实测 2.5.0）  接入成本：低（npm 即可，但仅 Web）  替代自造的：自建 M3 令牌表与组件
  - **material-foundation/material-tokens**  用途：M3 令牌真源（shape/type/motion/elevation/palette 的**权威数值**）  许可/协议：Apache-2.0（GitHub API 实测；⚠️ 仓库 `archived: true`，最后 push 2023-08-15）  接入成本：极低（直接读 raw 文件）  替代自造的：凭印象抄 M3 数值
  - **material-color-utilities（npm: `@material/material-color-utilities`）**  用途：HCT / tonal palette 算法，实现 D-06「设备状态派生主题」  许可/协议：Apache-2.0（raw LICENSE + npm registry 0.4.0 实测）  接入成本：中（需移植到 Swift）  替代自造的：手写 HSL/HSV 色调阶梯
  - **Material Symbols Outlined（Google Fonts）**  用途：M3 语义图标（仅 Android 端或对照用）  许可/协议：Apache-2.0（Google Fonts 提供）  接入成本：极低（一行 CSS/URL）  替代自造的：自画图标
  - **SF Symbols**  用途：iOS 端全部图标  许可/协议：Apple 许可（限 Apple 平台 UI 使用）  接入成本：零（系统自带）  替代自造的：自画图标 / 引入 Material Symbols
  - **Material 3 Design Kit（Figma）**  用途：官方 M3 组件结构参考（Expressive 变体、形状与动效）  许可/协议：Figma Community 免费可查看，Figma Community License（**商用/开源再分发条款未验证**）  接入成本：低  替代自造的：凭空设计组件结构
  - **Apple App Intents / Background Tasks**  用途：把「小栈的能力」暴露给 Siri/快捷指令；让小栈的后台行为不依赖 App 在前台  许可/协议：Apple 官方框架（系统自带）  接入成本：低-中  替代自造的：在 App 内自建"能力中心"与自建定时器
  - **Apple 通知 / Live Activity**  用途：小栈主动表达（不打断）  许可/协议：系统自带  接入成本：低  替代自造的：App 内弹窗打断用户
  - **lottie-ios（airbnb/lottie-ios）**  用途：小栈表情/动作动画的运行时（Lottie JSON）  许可/协议：Apache-2.0（raw LICENSE 实测）  接入成本：中（还需美术产出 JSON 动画）  替代自造的：Core Animation 手写逐帧
  - **style-dictionary**  用途：设计令牌唯一真源 + 多端输出（iOS Swift / CSS）  许可/协议：Apache-2.0  接入成本：中  替代自造的：`:root{}` 手写散落色值
  - **axe-core / pa11y / Playwright（见 04 号文档）**  用途：对比度与令牌外溢的 CI 门禁、视觉回归  许可/协议：MPL-2.0 / LGPL-3.0 / Apache-2.0  接入成本：低  替代自造的：纯人工 review 配色与圆角

采用决策：**混合**（自造令牌体系与角色化主题算法 + 复用 Google 的 M3 数值与 Apple 的系统框架 + 复用开源校验工具链）

理由：
1. **审美不可复用，但数值与机制可以复用**。圆角/字号/行高/动效时长这些"M3 到底是什么数"的问题，官方有 Apache-2.0 的可读源（material-tokens / material-web tokens），直接抄数值比自己拍脑袋强，且**有出处可写进作品集**；但"哪个角色用哪档""情绪怎么表达"必须自造。
2. **M3 的"角色化"必须复用，"Material You 的壁纸取色"必须自造替代**。iOS 没有壁纸取色，我们的 seed 换成**设备状态/小栈情绪**，用 tonal palette 展开成 tone 阶梯再映射角色——这是把 Material You 的骨架（role→tone→palette）搬过来，机制复用、数据源自造。
3. **Material Web 不进 iOS 工程**：它是 Web 组件，做 iOS 原生 App 引入它只会造成两套视觉语言；但它是**读数值的最佳来源**。
4. **图标与字体按平台分开**：iOS 用 SF Symbols（零成本、系统适配），Android/对照用 Material Symbols。这条是"嵌入苹果系统"的硬要求。
5. **苹果侧不走"AI 中心"路线，走系统集成路线**：App Intents + Background Tasks + 通知/Live Activity，把小栈的能力交给系统去暴露（用户的要求是"像原生 App 一样自然"，不是"像 ChatGPT 一样强大"）。
6. **校验工具链沿用 04 号文档结论**（axe-core + stylelint + Playwright 视觉回归），本报告新增一条：**用 M3 的 6 档圆角 + 4 档动效时长 + 7 档字号写成 lint 规则**，杜绝"随手 14px 圆角 / 220ms 动画"。
7. **不采用**：Material 动态取色（iOS 无此机制）、M3 容器色阶（iOS 系统自带语义色更原生）、Material Symbols（iOS 端冲突）、Figma 套件的直接再分发（许可条款未验证，只作参考）。

---

## 7. 未验证清单（必须如实标注的部分）

> 以下内容在本机**拿不到权威正文**，要么是网络不可达，要么是 SPA 抓不到正文。**在作品集/文档里引用它们之前必须自行复核。**

| 编号 | 未验证内容 | 原因（实测） | 影响面 |
|---|---|---|---|
| U-01 | **PAIR / People + AI Guidebook 正文**（`https://pair.google.com/`、`pair.withgoogle.com`） | DNS 解析失败 / 超时；design.google 上的 `/library/people-ai-guidebook` 多次直抓失败 | 本文对 PAIR 的引用全部**转引自 design.google 的 AI roundtable 文章**，未直接读原书 |
| U-02 | **Android Developers 的 M3 / M3 Expressive 官方文档正文** | `developer.android.com` 连接超时（多次） | M3 数值改用官方 token 源码（material-web tokens）替代，结论仍成立 |
| U-03 | **Material You 动态取色的算法细节**（HCT/CAM16、系统壁纸取色实现） | 同上 | 本文只验证"角色→tone→色值"骨架；算法机制未验证 |
| U-04 | **M3 间距系统（是否 4dp 栅格、官方 spacing token）** | 官方 token 源中**不存在 spacing 家族**（实测目录清单），规范正文不可达 | 本文明确写"间距不抄 M3，抄 iOS" |
| U-05 | **M3 surface-container 相邻档位是否强制 2 tone 差** | 只有 token 生成结果，无规范条文 | 我们只把它当"参考梯度"，不作为硬规则 |
| U-06 | **AI Studio / Vertex AI / Firebase AI Logic 的开发者 AI UX 指南正文** | `ai.google.dev`、`cloud.google.com`、`firebase.google.com` 全部超时 | 本文未引用其具体条款；如需引用须另找可达镜像 |
| U-07 | **Google Labs（Whisk / Flow / NotebookLM 生成式界面）** | `labs.google.com` 超时；`notebooklm.google.com`、`gemini.google.com` 超时 | NotebookLM/Gemini 部分结论来自**官方博客发布稿 + 官方配图视觉解析**，不是产品内实测 |
| U-08 | **Apple HIG 正文**（含 Generative AI、App Shortcuts、Live Activity、Materials 各页） | 页面 200 但**正文由 JS 渲染，抓到的正文仅 266 字符** | 苹果侧结论只引用 **apple.com/apple-intelligence（可抓正文）** 与 **Apple DocC JSON（appintents / backgroundtasks，可抓）**；HIG 相关表述**本文未验证** → 同目录 `10-AppleHIG官方核实.md` 已完成 HIG 官方核实，以那份为准 |
| U-09 | **"Liquid Glass" 的具体设计规则** | 本文未抓取 Apple 官方 Liquid Glass 文档正文 | 本文对液态玻璃只做哲学层描述（"克制"），**没有引用任何具体参数**；具体规则见 `10-AppleHIG官方核实.md` 第 2 节（含官方"内容层不要用 Liquid Glass"） |
| U-10 | **Material 3 Design Kit 的许可条款**（能否开源再分发其组件） | Figma 页面 200，但 Community License 条款未逐条核对 | 本文只把它当"结构参考"，不建议搬运其资产 |
| U-11 | **Apple 侧"App Shortcuts / Spotlight 消费 App Intents"在 UI 上的实际呈现** | Apple 官方 API 文档只能证明**能力存在**，不能证明**界面长什么样** | 苹果侧结论限于机制层，界面层需自己看真机 |
| U-12 | **M3 Expressive 的具体新组件清单与 shape 档位扩展** | m3.material.io 为 SPA，正文未渲染 | 本文只写了官方明确点名的 7 项机制（形状/尺寸/动效/色彩/容器/模糊/形状变形），组件清单未列 |
| U-13 | **`generate_image` / `reverse_image_search` 的实际调用** | 仅在 discovery 中列出，未执行 | E 节标注为"已发现未实测" |

---

## 8. 结论：5 条最该抄的做法

| # | 做法 | 为什么是它 | 一句话落地 |
|---|---|---|---|
| 1 | **状态不写字，交给小栈的脸 + 内部运动** | Google 自己把"thinking state"做成渐变与内层运动（`p_gemini_visual_design_w.txt:35-36`），Gemini Live 实测**零文字状态**（`describe_text.txt:59-61`）；我们有 320×240 的真脸，比渐变更强 | 小栈屏上动眼/动腮红表达"在想"，iOS 端不出现"正在聆听…" |
| 2 | **用 M3 的官方数值收敛形状/字号/动效**（7 档圆角、15 档字号、4 档时长） | 这些数字有 Apache-2.0 的官方出处，能写进作品集，也能变成 lint 规则 | 圆角只允许 4/8/12/16/28/9999；字号 12/14/16/22/28；时长 150/300/450/800 |
| 3 | **把 M3 的"角色化取色"搬成"设备状态派生主题"** | M3 的骨架（role→tone→palette，`tokens_color.txt`）可复用；壁纸取色不可复用但**根本不需要** | seed = 小栈当前情绪色，展开 tone 阶梯映射到 6 个语义角色，深浅色各一套 |
| 4 | **AI 产物必须有独立形态，不只是聊天气泡**（抄 NotebookLM） | NotebookLM 把音频/视频/思维导图/报告做成**四种内容类型 + Studio 矩阵 + 常驻 mini player**（`describe_text.txt:75-83`） | 小栈的"语音留言/今日回忆/心情日记"是独立卡片，各带播放器，回忆页有常驻 mini player |
| 5 | **能力交给系统，人格做成参数**（抄 App Intents + Siri 的 expressivity/pace） | Apple 官方："discoverable by **Apple Intelligence**"（DocC）、"customize **expressivity and pace**"（`p_apple_intelligence_w.txt:16-17`）；Google 官方："**not heroize technology**"（`p_ai_roundtable_w.txt:27-28`） | 能力做成 App Intent 交给 Siri/快捷指令；设置里给"话痨度/主动性/语速/吐槽度"四个滑杆 |

**再补两条"不要抄"**：不抄 Material 动态取色（iOS 无此机制、破坏原生观感）、不抄 Material Symbols 线性图标（与 SF Symbols 打架）、不抄 M3 的容器色阶（iOS 系统语义色更原生）。

---

## 9. 验证方式（本文所有结论怎么来的）

| 类型 | 手段 | 覆盖内容 |
|---|---|---|
| **官方源码级** | `web_fetch` / `Invoke-WebRequest` 直接拉 `raw.githubusercontent.com/material-components/material-web/main/tokens/versions/v0_192/*.scss`，本地保存后逐行解析 | M3 的 shape / type / motion / elevation / palette / 语义角色的**全部数值** |
| **官方页面级** | 抓 `design.google/library/*` 与 `blog.google/*`，剥标签取正文，本地留存 `p_*_w.txt` 并按行号引用 | M3 Expressive 动因与量化数据、Gemini 视觉体系、AI 设计原则、NotebookLM/Gemini Live 功能与交互 |
| **官方图像级** | `mcode-tools search_images` 定位官方配图 → 下载到本地 → `upload_temp_url` → `describe_images` 视觉解析 | Gemini App 输入区结构、Gemini Live 摄像头态的**零文字状态**、NotebookLM 播放器与 Studio 矩阵 |
| **仓库元数据级** | GitHub REST API / npm registry（license、stars、archived、version） | 各可复用方案的许可与维护状态 |
| **未覆盖** | 见第 7 节 U-01 ~ U-13 | — |

**引用格式约定**：本文所有本地引用都写明 `文件名:行号`，本地目录统一为
`D:\AP\AP7000\ai-workspace\stackchan-research\google-ref\`（正文与令牌）与
`D:\AP\AP7000\ai-workspace\stackchan-research\refimages\`（官方配图）。
原始 URL 见正文各处。

---
