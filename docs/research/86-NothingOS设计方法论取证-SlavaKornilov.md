# 86 · Nothing OS 设计方法论取证：Slava Kornilov 的设计原则与我们的落法

> **一句话**：用户 2026-10-25 指令「学习一下 slava kornilov 的设计」——
> Slava Kornilov 是 **Nothing OS 的设计负责人**（现 Everest AI Chief of Design）。
> 他做的东西里有一条对我们**直接可用**的原则：
> **「状态走一条独立通道（灯），不靠文字复述；每种状态有专属图案。」**
> ⇒ 落到我们产品上 = **设备卡的「身体信号灯带」**（12 颗 RGB LED，每种情绪一枚专属图案）。
> ⚠️ **诚实边界**：本轮取到的是 **Nothing OS 的产品原文与社区 wiki 全文**，
> **没有取到 Slava 本人的访谈/方法论原文**（付费墙 / Cloudflare / 超时，见 §二）。
> ⇒ 本文是**「Nothing OS 的设计事实 + 由它反推的原则」**，**不是**「Slava 本人说的话」。

---

## 一、人物与身份（证据强度分列）

| 项 | 内容 | 证据强度 |
|---|---|---|
| 身份 | Nothing OS 设计负责人；2026-06 起任 **Everest AI Chief of Design** | ⚠️ **仅搜索结果摘要**（https://newsbywire.com/former-nothing-os-designer-joins-everest-ai ，原页未打开） |
| 现职 | Crunchbase 记为「Chief of Design at Everest AI and Creative Director at Geex Arts」 | ⚠️ **仅搜索结果摘要**（https://www.crunchbase.com/person/slava-kornilov ，原页未打开） |
| 作品集 | Dribbble 个人页，**Awwwards Jury 2022** | ⚠️ **仅搜索结果摘要**（https://dribbble.com/slavakornilov ，原页未打开） |
| 事务所 | Geex Arts（Slava Kornilov 页面） | ⚠️ **仅搜索结果摘要**（https://www.geex-arts.com/in/slava-kornilov-95407a90/ru ，原页未打开） |

⚠️ **诚实边界**：以上 4 条**全部只读到搜索引擎摘要**，原页因 Cloudflare / JS 渲染未打开。
⇒ **不能**据此写「他本人说……」；只能写「**他负责 Nothing OS 的设计**」这一层。
⇒ 本文所有**引号内的产品事实**都来自 Nothing OS / nothing.wiki 的**可核原文**（见 §三），
不来自任何二手转述。

---

## 二、取证方法与失败路径（可复核）

| 通道 | 结果 |
|---|---|
| `web_fetch` → `nothing.wiki/_export/raw/...` | ✅ **成功**：DokuWiki 的纯文本导出接口，直接拿到全文，避开 HTML 噪声 |
| `web_fetch` → `nothing.wiki` 普通页 | ✅ 成功但体积极大（HTML + 导航 + 脚本），只作交叉验证用 |
| `web_fetch` → `madegooddesigns.com/nothing-brand-guidelines/` | ❌ **超时** |
| `web_fetch` → `strangelittlething.com/nothing-the-tech-brand...` | ❌ **Cloudflare 挑战页**（返回 “Just a moment…”） |
| `api.github.com` 搜 `nothing design guidelines` | ⚠️ **3 个垃圾仓库**；目标仓库 `one-more-refactor/nothing-focus-suite` **404**（改名或已删） |
| bing 中文版 `cn.bing.com` 查英文人名 | ❌ 返回「Slava ≠ 斯拉瓦」类无关结果（引号被忽略） |
| bing + `setmkt=en-US&ensearch=1` | ✅ 命中（Dribbble / Crunchbase / nothing.wiki） |
| 浏览器（chrome-devtools）直读页面 | ✅ 可用；对 Cloudflare 站点比 `web_fetch` 更有希望 |

⇒ **结论**：本机 `web_fetch` 对**部分站点可用**（GitHub API、nothing.wiki raw 都通了），
之前「工具坏了」的判断**不准确** ⇒ 联网通道本身可用，失败是**站点级**的（Cloudflare / 超时 / 404）。

---

## 三、取到的原文事实（Nothing OS / Glyph）

全部来自可核原文，URL 见每行末。

| # | 原文事实 | 出处 |
|---|---|---|
| F1 | Glyph Interface 是 Nothing 手机的标志性 LED 灯系统；Phone (1) 上是 **5 段灯、12 个可寻址分区、900+ 颗 LED** | https://nothing.wiki/software/glyph_interface |
| F2 | ⭐ **「Nothing OS 内置的每一个铃声与通知音，都有一枚专为其手写的 Glyph 图案」**（bespoke, handcrafted pattern） | 同上 |
| F3 | Phone (3) 起改为 **Glyph Matrix：25×25 圆形 micro-LED 屏、共 489 颗**，可显示动画 / 符号 / 图片 | 同上 |
| F4 | ⭐ **Glyph Toys**：内置 9 个可玩小控件（Glyph Mirror / Digital Clock / Battery / Stopwatch / Solar clock / Spin the Bottle / Rock Paper Scissors / **Leveller** / Magic 8 Ball） | 同上 |
| F5 | **Glyph Developer Kit (GDK)**：第三方 App 可直接驱动 Glyph，做自己的铃声与 Glyph Toys | 同上 |
| F6 | Phone (4a) 的 **Glyph Bar**：7 颗方灯、63 颗 mini-LED，比 3a Pro 亮 40% | 同上 |
| F7 | Nothing OS 2.0 引入**单色图标包**，Phone (3) 起**直接内置进系统** | https://nothing.wiki/software/nothing_icon_pack |
| F8 | ⭐ 该图标包的设计目标是 **“reduce distractions and make interactions with a smartphone more intentional”**；实现上是给**所有图标（含第三方）叠加黑白 overlay**，哪怕它们原本不是为它设计的 | 同上 |
| F9 | Nothing OS 的自我定位：**“a minimalist, modern design aesthetic paired with thoughtful utility”** | https://nothing.wiki/software/nothing_os |
| F10 | Nothing OS 5.0：引入**透明 + 磨砂的新软件材质**、**Geist 作为系统字体**、**壁纸自适应配色引擎**、**重做的设置界面**、新时钟盘「Gooey」「Micrographics」 | 同上 |
| F11 | ⭐ **减法有先例**：Nothing OS 4.0 的 **Lock Glimpse** 被社区指为 “bloatware on an otherwise clean and minimal OS”，**2026-01-09 整个功能被移除**（社区帖 https://nothing.community/d/45213 ） | 同上 |

---

## 四、8 条原则 + 我们的裁决

| # | Nothing 的做法 | 抽象出的原则 | 我们的裁决 | 落点 |
|---|---|---|---|---|
| 1 | F1 / F2：状态走一条**独立灯通道**，每种事件有专属图案 | **状态不要用文字复述；离散状态要有专属可识别图案** | ✅ **采纳** | 设备卡加「身体信号灯带」（本轮已做） |
| 2 | F4：把一个小硬件做成**可玩**的小控件（Leveller / Magic 8 Ball） | **小控件本身要好玩，不是参数面板** | ✅ **与用户拍板同向** | 舵机摇杆 = 玩具，不是滑杆（`00` §4.2 元素 4） |
| 3 | F7 / F8：单色图标包，给**所有**图标叠黑白 overlay | **图标单色，靠形状与填充区分，不靠色相** | ⚠️ **部分采纳** | iOS 用 SF Symbols + 系统 tint 是原生做法 ⇒ **不引入自绘单色图标包**（原生度是硬约束）；但「靠形状不靠色相」这条**写进验收口径** |
| 4 | F10：透明 + 磨砂材质、Geist 系统字、壁纸自适应配色 | **材质表达层级；不引入装饰字体** | ✅ **已一致** | Liquid Glass（`DESIGN.md` §7）；衬线字族仍是待拍板 Q13 |
| 5 | F11：Lock Glimpse 被用户投票移除 | **减法会被用户否决，是产品事实不是审美偏好** | ✅ **强化** | `01` §8 的减法清单 |
| 6 | F1 / F6：Glyph 在**机身上**，不在屏幕里 | ⭐ **Glyph 属于「身体」，不属于 App** | ✅ **采纳为红线** | 点阵 / 灯效语言只放**设备端 320×240**；**禁止**把点阵脸搬进 iOS App |
| 7 | F2：**每种事件一枚专属图案**，不是通用图标 | **离散状态 1:1 专属图案** | ✅ **采纳** | 6 档情绪 = 6 枚专属 12 点图案（本轮已做） |
| 8 | F3 / F5：点阵屏可编程、可被第三方 App 驱动 | **表情/灯效是**数据**，不是贴图** | ✅ **采纳（技术侧）** | 0x14 关键帧通道本来就带 `leftRgbColor` / `rightRgbColor`（见 `../spec/03`）⇒ 灯带图案应当**由关键帧数据生成**，不是画死的图 |

⚠️ **哪些是原文、哪些是我的判断**：第 1/2/3/6/7/8 条**有直接原文支撑**；
第 4/5 条是**从产品事实反推**；第 6 条里「禁止把点阵搬进 iOS」是**我的判断**（理由：我们的 4 套方案是纸感/衬线，点阵脸会与之打架，且 iOS 原生度是硬约束）。

---

## 五、落到产品上的具体改动（本轮已做）

### 5.1 设备卡加「身体信号灯带」

- 文件：`../prototype/ios/ios-light.html` 与 `ios-dark.html`（深色由浅色重新生成）
- 形态：**12 颗 = 左右各 6 颗**，与硬件一致 —— 0x14 关键帧 payload 里 `leftRgbColor` / `rightRgbColor` 分列左右两侧
- ⭐ **每种情绪一枚专属 12 点图案**（6 档，已实测 6/6 命中）：

```
idle      001100 | 001100      平静：中心一对
happy     011110 | 011110      开心：对称弧
excited   111111 | 111111      兴奋：满排
surprised 110011 | 110011      惊讶：两端
sleepy    100000 | 000001      困倦：一端渐弱
cross     111000 | 000111      生气：斜向
```

- 颜色取方案自带 `--accent`（**不写死色值**，8 组方案自动跟随）
- 有 `prefers-reduced-motion` 降级（动画关闭时仍可读）
- 截图：`../../assets/screenshots/ui-control-light.png`、`ui-control-light-servo.png`、`ui-control-dark.png`

### 5.2 规格层新增的约束

| 落点 | 新增内容 |
|---|---|
| `../spec/00` §4.2 | 设备卡**必须**包含「身体信号灯带」（12 颗，左右各 6；每种情绪一枚专属图案） |
| `../spec/01` §7 | **新增 C7「同一状态被两条通道重复表达」** 检测项（情绪只走图案通道，文字只给设备事实） |

---

## 六、诚实边界（这一节不能省）

1. ⛔ **没有取到 Slava 本人的方法论原文** —— 取到的是 Nothing OS 的**产品事实**。
   ⇒ 本文的原则第 1/2/3/6/7/8 条是「**从产品事实反推**」，**不是**「他说的」。
   ⇒ 作品集里**不得**写「Slava Kornilov 说过……」；只能写「我们研究了 Nothing OS 的设计并采纳了其中 X 条」。
2. ⛔ **原型里的 6 枚情绪图案是我设计的**，**不是固件真值** —— 固件里**没有**「情绪 → 灯带图案」的对照表。
3. ⛔ **12 颗 LED 在真机上的实际行为未验证** —— 固件 `DanceSequence` 的 `#RRGGBB` 作用到灯带，
   在 `../research/53` 里就列着「需真机 + 观察灯带」。
4. ⛔ `madegooddesigns.com` 与 `strangelittlething.com` 两篇看起来最相关的二手整理**没取到**（超时 / Cloudflare）
   ⇒ 可能存在本文未覆盖的要点。
5. ⛔ **Nothing OS 是 Android**，它的「单色图标包 / 壁纸自适应配色」等做法**不能直接搬到 iOS**
   —— 本文只搬了**与平台无关**的那几条。

---

## 七、溯源

| 类型 | URL | 取到方式 |
|---|---|---|
| 全文 | https://nothing.wiki/software/glyph_interface | 浏览器直读（HTML） |
| 全文 | https://nothing.wiki/_export/raw/software/nothing_os | `web_fetch`（raw 导出） |
| 全文 | https://nothing.wiki/_export/raw/software/nothing_icon_pack | `web_fetch`（raw 导出） |
| 摘要 | https://newsbywire.com/former-nothing-os-designer-joins-everest-ai | bing 搜索摘要 |
| 摘要 | https://www.crunchbase.com/person/slava-kornilov | bing 搜索摘要 |
| 摘要 | https://dribbble.com/slavakornilov | bing 搜索摘要 |
| 摘要 | https://www.geex-arts.com/in/slava-kornilov-95407a90/ru | bing 搜索摘要 |
| 失败 | https://madegooddesigns.com/nothing-brand-guidelines/ | `web_fetch` 超时 |
| 失败 | https://www.strangelittlething.com/nothing-the-tech-brand-that-made-transparency-a-design-language/ | Cloudflare 挑战 |
| 失败 | https://github.com/one-more-refactor/nothing-focus-suite | 404（仓库不存在） |

---

*生成时间：2026-10-25 12:15 ｜ 门禁 40 项 ｜ 外部取证：3 源全文 + 4 源摘要 + 3 条失败路径*
