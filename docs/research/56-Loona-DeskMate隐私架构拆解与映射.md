# 56 · Loona DeskMate（KEYI Tech）隐私与行为边界架构拆解 → 映射到 StackChan

> 状态：**已完成**（2026-10-24 一手取证 + 逐条映射）
> 研究人：Worker（StackChan Research）
> 本文件结论全部标注来源编号 S1–S7（§1.0），三档证据分级：**官方原文** / **官方自述但无法律或技术文件支撑** / **我们的推断**
> 抓取环境：本机无代理出口，`keyirobot.com` 直连可达
> 护城河基线（本文所有判断的锚点）：①设备即档案+可审计来源 ②私人层永不入库 ③逐字出处可见、权重可改原文不可改 ④关系资产可带走、零锁定 ⑤商业模式互斥（我们"关系可带走" vs 巨头"订阅+平台锁定"）

---


## §0 一句话结论

**能抄的是"边界与姿态"，不能抄的是"能力分档与云端归属"。**

- **能抄**（✅/⚠️）：逐能力独立开关且默认关、可撤销（P1/B3）、原始帧不出机（P5）、拉取式感知原则（P2）、提醒不升级为代劳（B1）、不点评用户情绪（B2）、存在一个不依赖 App 的物理断电边界（P4）。
- **不能抄**（❌）：把屏幕感知做成**按订阅分三档**的产品功能（官方 plans 原文：Free `Basic` / Plus `Advanced` / Pro `Full Screen Awareness & Action`）、credits 制订阅档、**用"一键清空"代替"可导出"**、云端记忆作唯一真相源、拿"零订阅"当口号去对标（它自己的官方指南与官方产品页互相打架）。
- **最硬的一条依据**：Loona 的"五条红线"**在法律层面不存在** —— 官方 Privacy Policy 的 `Last updated:` 仍是 **February 05, 2023**（S4），全文**零处**提到记忆存放位置、可导出性或训练数据边界；全站也**从未出现** export / portable 之类的可携带承诺。⇒ **它给的是"承诺"，我们必须给"可验证的实现"**——这正是护城河①「可审计来源」可以长期独占的位置。

---

## §1 官方原文取证

抓取日期：**2026-10-24**（本机无代理出口，`keyirobot.com` 直连可达，UA 伪装 Chrome）。
所有引文均为英文原文（不改写）；若为中文则为本文转述，已单独标注。

### 1.0 来源清单

| 编号 | URL | 抓取日期 | 页面内容特征 | 证据档位 |
| --- | --- | --- | --- | --- |
| S1 | `https://keyirobot.com/products/deskmate` | 2026-10-24 | 产品页 SSR HTML（含完整 i18n 字典、隐私卡片、行为边界、plans 弹窗、JSON-LD 规格） | `r56/deskmate.html` |
| S2 | `https://keyirobot.com/blogs/news/loona-deskmate-an-iphone-powered-ai-desk-robot` | 2026-10-24 | 官方长文：“How an iPhone-Powered AI Desk Robot Works”，页面日期 **August 19, 2026** | `r56/news-iphone.html` |
| S3 | `https://keyirobot.com/blogs/news/meet-loona-deskmate-the-desktop-ai-companion-for-work` | 2026-10-24 | CES 2026 发布帖，页面日期 **September 15, 2026** | `r56/news-meet.html` |
| S4 | `https://keyirobot.com/policies/privacy-policy` | 2026-10-24 | 官方隐私政策，`Last updated: February 05, 2023` | `r56/privacy-policy.html` |
| S5 | `https://keyirobot.com/blogs/buying-guide/loona-deskmate-price-value-guide` | 2026-10-24 | 官方买家指南《Loona DeskMate Price Breakdown》，页面日期 **July 31, 2026**；含 MCP 说明、订阅口径、隐私四条控制、竞品对比表 | `r56/bg-price.html` |
| S6 | `https://keyirobot.com/blogs/buying-guide` | 2026-10-24（前轮枚举） | 官方竞品/选购目录首页。**规模以 S7 为准** | — |
| S7 | `https://keyirobot.com/sitemap.xml`（子表 `sitemap/articles/1.xml` 等 4 个） | 2026-10-24 | 站点机器可读全量：**articles 601 条，其中 `/blogs/buying-guide/` 455 条唯一 slug** | `r56/sm_articles.xml` |

> ⚠️ **S1 的实际正确 URL 是 `/products/loona-deskmate`**（JSON-LD `url` 字段），`/products/deskmate` 也可访问并跳转；任务书写的 `/pages/plans` **不存在**（返回首页），订阅档位实际是嵌在产品页内的 **plans 弹窗**（本文已完整取证）。
> ⚠️ **目录规模修正**：前轮记录的「42 页 / 250 个唯一指南页」是分页枚举口径；**S7 sitemap 实测为 455 条唯一 buying-guide**（详见 §5.1）。

### 1.1 隐私架构五条红线（官方原文，均出自 S1 隐私区）

区标题（官方原文）：

> Privacy / Stay Where You Put It. / Works Where You Need It.
> **Five red lines. Zero compromises. Your data, your device, your rules.**

五张卡片（卡片标题→官方原文描述）：

| 卡 | eyebrow（小标题） | title（机制名） | description（官方原文） |
| --- | --- | --- | --- |
| P1 | EACH TOOL, ITS OWN SWITCH | **Granular Tool Permissions** | Gmail, Calendar, Slack, etc. — each connects independently via the secure MCP ecosystem. Toggle any tool on or off individually. |
| P2 | Sees only what you point out | **Pull-Mode Screen Awareness** | DeskMate never silently watches your screen. It sees only what you explicitly point out. |
| P3 | REVIEW. CLEAR. CONTROL | **Controllable Memory** | Review everything DeskMate remembers. Clear memory with one tap. Full transparency, full control. |
| P4 | EYES OFF. FULLY OFFLINE | **Physical Sleep Mode** | Take off your phone, and DeskMate sleeps — instantly and physically. No listening, no watching, no recording. |
| P5 | Face & attention on-device only | **Sensitive Data Stays Local** | Your facial expressions and attention patterns are processed entirely on your iPhone — never uploaded. Only your explicit task commands go to the cloud |

**关于 MCP 那一条的补充取证**（S1 与 S2 双位，两处原文一致）：

- S1（产品页隐私卡）：“Gmail, Calendar, Slack, etc. — each connects independently via **the secure MCP ecosystem**.”
- S2（官方长文）：“Services such as Gmail, Calendar, and Slack can be connected individually, giving users granular control over which tools DeskMate can access.”
- S3（CES 发布帖）“Encrypted Workflow Integrations：Workspace integrations (Gmail, Slack, Calendly) adhere to **strict end-to-end encryption standards with zero retention of user context data for external AI training**.”
- ⚠️ **MCP 的官方描述尽到此为止**：未说明 MCP server 是不是官方自建、记忆写入是否走 MCP、是否支持用户自带 MCP server。**未取得**（详见 §6）。

### 1.2 行为边界三条（官方原文，出自 S1 行为边界区）

区标题（官方原文）：

> YOUR CONTROL / It Suggests / You Decide. / **Three rules, built into the hardware.**

| 号 | 机制名 | 官方原文 |
| --- | --- | --- |
| B1 | **One Nudge, Then Quiet** | Ignored reminders retry gently or stand down — never escalate to acting for you. |
| B2 | **No Commentary** | It adapts its timing to your pace. It never remarks on your mood or "how you seem." |
| B3 | **Nothing Without Permission** | Every tool is a separate toggle — visible, revocable, off by default. |

### 1.3 产品与价格（官方原文 / JSON-LD，S1）

- 官方定位原文：**"Your AI intern on the desk — it preps, you decide."** / "Embodied AI Workmate at Your Desk"
- 价格：**$299.00**（Obsidian）。JSON-LD `offers`：`"priceCurrency": "USD", "price": "299.0", "availability": "https://schema.org/InStock"`, `sku: LOONA-DESKMATE-001`
- 试用与保证：**30-day trial** / **1-year warranty** / **Lifetime Customer Support** / **Free shipping**
- 订阅原文：**"Loona Deskmate works from day one — no subscription required. More output? See plans →"**

**规格表官方原文（S1 渲染区）**：

| 区 | 行 | 值（官方原文） |
| --- | --- | --- |
| Motion System | Degrees Of Freedom | 3-DoF (Yaw / Pitch / Roll) |
| Motion System | Motor Type | All Brushless Servo Motors |
| Motion System | Motion Generation | AI Real-Time, Not Preset Animation |
| Motion System | Noise Level | Virtually Silent |
| Charging & Power | Total System Power | 165W（页面高亮区写 "165W / GaN Power Delivery"） |
| Charging & Power | USB-C Max Output | 140W（见 JSON-LD "Max Output (Single Port)"） |
| Charging & Power | USB-A Power | —（需交付页面版本，未取得） |
| AI Performance | Response Latency | 0.5s（高亮区 "0.5s / AI Response Latency"） |
| AI Performance | Local Processing | 未取得原文（见 §6） |
| AI Performance | Privacy Modes | 未取得原文（见 §6） |
| AI Performance | Data Policy | 未取得原文（见 §6） |
| AI Performance | App Support | 未取得原文（见 §6） |
| AI Performance | Updates | 未取得原文（见 §6） |

**JSON-LD 额外规格（S1，官方结构化数据，非启发测试版本——但与上表单口不同的是权威取证来源）**：

| 字段 | 值 |
| --- | --- |
| Dimensions | 113 mm (L) × 106 mm (W) × 113 mm (H) |
| Weight | 880 g |
| Actuators | 3 × Outer Rotor Brushless DC Servomotors |
| Neck Movement | Yaw, Pitch, Roll |
| MCU | STM32 Series |
| Connectivity | Bluetooth 5.3 (BLE & BT Dual-mode) |
| Charging Port | 30V / 7A (DC 5.5 × 2.5) |
| Wireless Charging | 15W Magnetic Wireless Charging (MagSafe Compatible) |
| Thermal Management | Active Heat Dissipation |
| Ports | 3 × USB-C + 1 × USB-A |
| Max Output (Single Port) | 140W |
| Max Output (Multi Port) | 180W |
| Charging Capacity | Supports 2 × MacBooks + 1 × Phone simultaneously |

> ⚠️ **功率自相矛盾已用官方原文校正**：规格表高亮区写 **165W**（Total System Power），盒内列写 **180W GaN Charger**，JSON-LD 写 **140W 单端 / 180W 多端**。三个数字各有口径，**不得混用**；引用时必须写明是哪一个。

### 1.4 iPhone 参与算力的边界（官方原文，S2）

S2 给出了一张明确的「职责分工表」（官方原表，逐行引）：

| Function | Where It Comes From |
| --- | --- |
| Visual interface and animated face | iPhone |
| Camera and attention sensing | iPhone |
| Voice interaction interface | iPhone + DeskMate software |
| Physical movement | DeskMate motorized base |
| Wireless phone charging | Qi2, up to 15W |
| Desktop power delivery | Up to 165W GaN |
| Work integrations | DeskMate software ecosystem |
| Physical desk presence | DeskMate hardware |

S2 关于隐私边界的原文（三段）：

> Screen awareness also works on a user-directed basis: instead of continuously monitoring everything displayed on the computer, DeskMate receives relevant screen context when the user intentionally points it out or asks for help with something on screen.

> Facial expressions and attention-related information are processed locally on the iPhone rather than uploaded. Explicit task commands, however, may use cloud services when needed to complete a requested action. This distinction matters because on-device processing does not mean every AI function runs locally; instead, sensitive perception-related information can remain on the phone while connected AI tasks may use cloud infrastructure when the user deliberately requests them.

> There is also a straightforward physical privacy boundary. Removing the iPhone places DeskMate into sleep mode, so the core companion experience is no longer active without the phone attached. For users who prefer clear, visible control over when an AI device is active, that physical boundary can be easier to understand than relying only on software indicators.

S2 FAQ 关于订阅与屏幕观测的原文：

> Does Loona DeskMate require a subscription? DeskMate is designed to work without requiring a subscription from day one, although additional plans may be available for users who want higher usage levels or additional output. Because plan structures can change over time, buyers should check the current product page for the latest details.

> Does DeskMate continuously watch your screen? DeskMate's screen-awareness system is designed around user-directed access rather than continuously watching everything displayed on the computer. Users can intentionally provide relevant screen context when they want AI assistance, while connected tools such as Gmail, Calendar, and Slack have their own individual permissions.

**iOS 兼容性原文（S1）**：`*Compatible with iPhone 12+ with MagSafe.` / `*Device Compatibility: Loona Deskmate exclusively supports iPhone 12+.`
S2 原文：`It is designed for iPhone 12 and later, making the smartphone an integral part of the companion experience rather than simply a remote control for the robot.`

### 1.5 订阅档（官方原文，来自 S1 页内 plans 弹窗 i18n 字典）

弹窗标题原文：`Loona plan options` / `Choose a Free, Plus, or Pro Loona DeskMate plan.` / eyebrow `Coffee Budget` / 主标题 `Every Plan Gets The Job Done`
说明原文：`Loona handles your daily rhythm for free. The more you want it to take on — deeper research, more tools, heavier workloads — the more coffee it needs. Every tier gets the job done. Some just run on espresso.`
脚注原文：`Credits refresh on your billing cycle and do not roll over. Upgrade or downgrade anytime — no hard feelings. Loona will keep doing its best either way.`

| 档 | 人设 | credits | 刷新 | 官方原文功能列 |
| --- | --- | --- | --- | --- |
| **Free** | Senior Intern | 200 credits | 50 refresh daily | Unlimited Chat & Voice Commands / **Basic Screen Awareness** / Calendar & Scheduling X 60 / Email Summaries X 10 / Document Reading X 4 / Web Research X 4 / Standard Response Time / `No credit card required` |
| **Plus** | Team Member | 1,000 credits | 未取得 | Unlimited Chat & Voice Commands / **Advanced Screen Awareness** / Calendar & Scheduling X 300 / Email Summaries & Drafting X 50 / Document Generation X 20 / Web Research X 50 / **Slack / Teams Integration** / Priority Response Time / `Cancel anytime` |
| **Pro** | Senior Partner | 3,000 credits | 100 refresh daily | Unlimited Chat & Voice Commands / **Full Screen Awareness & Action** / Calendar & Scheduling Unlimited / Email Full Management X 150 / Document & PPT Generation X 60 Each / Deep Web Research X 150 / **All Integrations Unlocked** / First Access To New Features / Peak-Hour Priority Queue |

> ⚠️ **三档的具体月价未取得**（页面只有 `/ Month` 单位、没有数字；全站 HTML 中唯三个美元符号字符串与包装活动无关）——见 §6。
> ⚠️ **重要发现（官方原文）**：**屏幕感知分三档**（Basic / Advanced / Full Screen Awareness & Action）——即官方把「看屏」做成了**支付档优先级**，Free 档仅 "Basic Screen Awareness"，Pro 档才是 "Full Screen Awareness & Action"。**这与它自己宣称的「DeskMate never silently watches your screen」不冲突，但意味着「能力深度与会员级绑定」**。这是我们§3「不能拷」清单的核心证据。

### 1.6 全文取证补位（官方原文，S3）

S3（CES 发布帖）的「Enterprise-Grade Privacy for Your Workspace」三条（原文）：

> On-Device Local Processing: Visual attention tracking and presence detection run locally on hardware to minimize cloud data transmission.

> Transparent Sensory Status: Physical status indicators immediately inform you whenever sensory modes (camera/microphone) are active or muted.

> Encrypted Workflow Integrations: Workspace integrations (Gmail, Slack, Calendly) adhere to strict end-to-end encryption standards with zero retention of user context data for external AI training.

S3 对行为边界的补充描述（原文）：`For a desktop robot, this is a big deal: the “best” assistant isn’t the loudest one—it’s the one that knows when not to interrupt.`
S3 对无唤醒词的描述（原文）：`It also claims to reduce interaction friction by eliminating a 300–500 ms silence delay and responding only when you’re actually addressing it.`

### 1.7 官方隐私政策现状（S4，本轮最关键的反证）

> Last updated: **February 05, 2023**
> This policy explains what information KEYi Tech collects, how we use it, and the choices you have when you use our website, products, and related services.
> We may share personal information with trusted service providers such as payment processors, delivery partners, analytics tools, and communication platforms that help us operate our business.
> We keep personal information only as long as reasonably necessary for service, legal, accounting, and dispute-related purposes.
> We apply reasonable safeguards to protect your information, but no method of storage or transmission can be guaranteed to be completely secure.

**读取（本文推断）**：
1. 该政策文件**早于 DeskMate 产品 3 年**，内容围绕“website, products, and related services”的通用口径写，**完全没有提到 DeskMate、面部/注意力数据、记忆、屏幕感知、MCP**。
2. 全文无「记忆存在哪里」「是否可导出」「是否用于训练」、「记忆是否包含私人层原文」的可执行条款。
3. 仅有一句集中的「消费者数据集中保留」表述，且在新文件里而不是在旧文件里。

**结论（本文推断）**：Loona 的「五条红线」是**商品层叙事**，**没有被写成可执行的数据处理规则**。它们可以被我们当作「对外叙事幂等」引用（如「它们都明写了这些」），**但不能当成我们的架构依据**——我们要自己把「可审计来源」写成可验证的实现。
## §2 逐条映射：8 条隐私/行为边界 → 我们的架构

### 2.1 判定速览表

| # | 机制（官方原文标题） | 判定 | 一句话理由（落到我们的护城河） | 落点（我们的哪个组件） |
| --- | --- | --- | --- | --- |
| P1 | Granular Tool Permissions | ⚠️ 抄了要改 | 抄"逐工具独立开关、默认关、可撤销"的**模式**；不抄 MCP **实现**（我们 00 号 §2.2 已把"MCP 接入"列为不做），并加一条 Loona 没有的"开关状态本身可审计可导出" | iOS App 设置 Scene ＋ 后端调用前裁决点 |
| P2 | Pull-Mode Screen Awareness | ✅ 直接抄（原则）／❌ 功能不能抄 | 我们**根本没有屏幕感知通道**，天然满足"看不到你没让它看的"；但 Loona 把屏幕感知做成**付费分档**，说明这条路必然通向锁定 | 无（靠"不做"满足）；iOS App 本地视觉感知（A-1／S-1） |
| P3 | Controllable Memory | ⚠️ 抄了要改 | "一键清空"会把关系资产降格为"一个开关就能抹掉的数据库"；我们必须做**逐条可查出处 + 可导出 + 原始层不可被 AI 改写**，清空只降级为"导出后删除" | iOS App 隐私页 ＋ 后端自托管记忆库（append-only 原始层 + 派生层） |
| P4 | Physical Sleep Mode | ⚠️ 抄了要改 | 抄**"存在一个不依赖 App 的物理断电边界"这个结论**，不抄实现（我们的固件只读）；Loona 的物理边界来自"感知硬件不在机器人身上"，我们的等价物是"感知在 iPhone → iPhone 不在场即无感知" | 设备端实体 POWER 键（官方固件长按 6s 关机）＋ iOS App 不在场即不建感知会话 |
| P5 | Face & attention on-device only | ✅ 直接抄（且我们更强） | 我们 S-1 连**原始帧**都不出本机；Loona 只承诺**派生量**（表情/注意力）本地算，未承诺原始图像不出手机。这是可写进对外叙事的硬差异 | iOS App 本地 Vision 推理 ＋ 后端只收布尔量/置信度 |
| B1 | One Nudge, Then Quiet | ✅ 直接抄 | 我们 E-3 已有"24h 内 ≤ 2 次"+"一键安静"，Loona 多了后半句"never escalate to acting for you"，这句必须抄：主动性不得升级为代劳 | 后端主动开口调度 ＋ iOS 通知/主动话术 |
| B2 | No Commentary | ⚠️ 抄了要改 | 只抄"**不点评用户情绪**"这半条；不抄"不表达自身情绪"的隐含部分，否则砍掉我们的物理化情绪与在场感知（我们 21 号已取证 Loona 转助理后评分掉到 1.82） | 后端人格提示词 ＋ iOS 端不做情绪点评 |
| B3 | Nothing Without Permission | ✅ 直接抄（需扩面） | Loona 只覆盖"工具"；我们要扩成**全域默认关**：任何数据出设备（云端 LLM、通知内容、Live Activity、诊断上报）都要独立开关 + 可审计日志 | iOS App 设置 Scene ＋ 后端出网裁决 |

### 2.2 逐条详解

#### P1 · Granular Tool Permissions

- **官方原文**（S1 `https://keyirobot.com/products/deskmate`）：`Gmail, Calendar, Slack, etc. — each connects independently via the secure MCP ecosystem. Toggle any tool on or off individually.`
- **官方原文**（S1 行为边界区）：`Every tool is a separate toggle — visible, revocable, off by default.`
- **官方原文**（S5 `https://keyirobot.com/blogs/buying-guide/loona-deskmate-price-value-guide`，2026-07-31）：`The platform uses the open-source Model Context Protocol (MCP) to connect workspace tools.` / `Each tool operates through granular permissions, letting you turn individual connections on or off directly without upgrading to enterprise tiers.` / `Each connection starts off by default.`
- **已知实现**：每个第三方应用各自走 MCP server 连接；连接态默认关；关掉即断开该连接。
- **推测（未取证）**：开关 UI 落在 iOS App 内；撤销动作应当吊销该应用的 OAuth token；权限判定点可能在客户端而非服务端，官方未说明。
- **我们的组件**：iOS App（开关 UI + 本地持久化权限集）＋ 后端（每次工具调用前的权限裁决点）。
- **判定**：⚠️ **抄了要改**。
  - 抄：逐工具独立开关、默认关、可撤销、可见。
  - 不抄：MCP 这个实现载体 —— 我们 00 号 §2.2 已把「MCP 接入」列入**明确不做**的功能减法，照抄会直接与自己的减法条款冲突。
  - **必须补一条 Loona 没有的**：Loona 的开关状态是平台侧状态，我们要求开关状态本身属于用户的档案，**可导出、可审计**（护城河①"可审计来源"落到权限维度）。
- **要改的规格**：`00` 号 §7 隐私与安全红线新增 **S-10**（逐能力开关，默认关、可撤销、开关态可导出）；`00` 号 §4.4 设置 Scene 增一条权限清单入口；`04` 号 §3.2 B 可审计来源补"权限也是可审计对象"；`05` 号 §四 增一条落地方案。

#### P2 · Pull-Mode Screen Awareness

- **官方原文**（S1）：`DeskMate never silently watches your screen. It sees only what you explicitly point out.`
- **官方原文**（S2 `https://keyirobot.com/blogs/news/loona-deskmate-an-iphone-powered-ai-desk-robot`）：`Screen awareness also works on a user-directed basis: instead of continuously monitoring everything displayed on the computer, DeskMate receives relevant screen context when the user intentionally points it out or asks for help with something on screen.`
- **官方原文**（S5）：`Pull-mode screen awareness means DeskMate looks only at content the user deliberately points out. It does not scan background windows, open tabs, or desktop activity on its own.`
- **已知实现**：Mac 原生集成，Windows 走「via a related app」；剪贴板实时同步（S3 提「real-time clipboard and screen awareness」）。
- **⚠️ 关键反证（官方自相矛盾，同一官方站）**：产品页 plans 弹窗把屏幕感知**按订阅分档** —— Free `Basic Screen Awareness` / Plus `Advanced Screen Awareness` / Pro `Full Screen Awareness & Action`（S1 i18n 原文）；而 2026-07-31 的官方买家指南却写 `without locked tier add-ons`（S5）。两处官方文本冲突，**以产品页 plans 为准**（它是购买页的实际售卖口径）。
- **我们的组件**：我们**没有屏幕感知通道**（00 号功能表无此项，§2.2 明确不做直播/拍照社交）；最接近的是 iPhone 本地视觉在场感知（A-1／S-1）。
- **判定**：✅ **直接抄"拉取模式"这个原则**（我们靠"不做"天然满足），❌ **不能把屏幕感知做成产品功能再按订阅分档**。
- **依据**：我们要抄的是边界，不是能力。而且 Loona 自己的分档已经证明：**屏幕感知一旦成为卖点，就会被推向订阅增值档** —— 那正是我们护城河的反面。
- **要改的规格**：`00` 号 §7 **S-1** 增补一句"本产品不存在屏幕感知通道（对照 Loona 的 Pull-Mode 及其付费分档）"；`00` 号 §2.2 功能减法增补该条；`04` 号 §八 **P1（是否彻底放弃订阅）** 补一条判据。

#### P3 · Controllable Memory

- **官方原文**（S1）：`Review everything DeskMate remembers. Clear memory with one tap. Full transparency, full control.`
- **官方原文**（S5）：`Memory stored by the system can be reviewed and cleared with one tap, giving full visibility into what the assistant retains.`
- **已知实现**：App 内有记忆列表；一键清空。
- **推测（未取证）**：清空是删除云端条目（因为记忆可被"review"，说明有云端列表）；**未取证**是否有导出、是否有 append-only 原始层、删除是否可恢复。
- **我们的组件**：iOS App 隐私设置页 ＋ 后端自托管记忆库（00 号 C-1 写明"**必须自托管**"）。
- **判定**：⚠️ **抄了要改**。
  - 抄：可查看（review everything）、可逐条删除、透明度。
  - **不抄**"一键清空"作为记忆控制的主手段：清空是把整段关系资产变成一个开关就能抹掉的东西 —— 这与护城河①「关系资产属于用户、可带走」**直接冲突**（关系随时可被平台整体抹除 = 关系其实属于平台）。
  - **正确形态**（比 Loona 更严格，这也是我们可以对外讲的差异）：
    1. 每条记忆可展开看**逐字出处 + 日期**（我们护城河①已有，Loona 没有）；
    2. 逐条可删、可改权重；
    3. **整库导出**（一键导出 JSON/Markdown，含出处与原文）；
    4. "清空"降级为**两步确认的"导出后删除"**；删除只删派生层，append-only 原始层保留至用户显式执行"抹除原始层"。
- **要改的规格**：`00` 号 §7 **S-5**（记忆库可查看/可导出/可逐条删除）扩写为"原始层不可由 AI 修改；清空必须先导出"；`00` 号 §3 **C-1 长期记忆** 加"原始层 append-only + 派生层可重建"；`04` 号 §3.2 **B｜可审计来源** 加"逐条出处与原文是导出物的一部分"；`04` 号 §八 **P2** 补"服务端记忆 = 可导出的派生层，不是真相源"。

#### P4 · Physical Sleep Mode

- **官方原文**（S1）：`Take off your phone, and DeskMate sleeps — instantly and physically. No listening, no watching, no recording.`
- **官方原文**（S2）：`Removing the iPhone places DeskMate into sleep mode, so the core companion experience is no longer active without the phone attached.`
- **官方原文**（S5）：`Removing the iPhone or closing the companion app immediately pauses spatial tracking and active listening.` / `Lift the iPhone off the MagSafe mount and every vision sensor loses power at once.` / `The hardware itself enforces the boundary rather than relying on a software toggle that could fail.`
- **已知实现**：感知硬件（摄像头/麦克风）**在 iPhone 上**，基座没有感知面；磁吸触点断开 → iPhone 掉电/离座 → 感知全停。
- **⚠️ 官方文本内部张力**："physically"（S1）vs S5 同段又写 "**or closing the companion app** immediately pauses spatial tracking" —— 即真正生效的机制是 **iOS 后台规则**（App 不在前台即无采集），"物理"只是必然结果而非独立机制。
- **我们的组件**：设备端 CoreS3（**实体 POWER 键**：官方固件单击开机、**长按 6s 关机**；电源指示 LED）+ iOS App（不在场/后台 → 不建立感知会话、不推流、不录音）。
- **判定**：⚠️ **抄了要改**。
  - 抄：**"存在一个不依赖 App 逻辑的物理断电边界"** 这个结论。
  - 不抄实现：我们的**官方固件只读**，不能新增任何指示灯语义或按键行为，只能使用官方固件**已有**的 POWER 键长按关机行为。
  - 等价映射：Loona 的边界来自"感知硬件不在机器人身上"；我们的感知主力在 iPhone（00 号 S-1），所以我们的等价边界是「**iPhone App 不在场 → 无感知会话**」+「**设备 POWER 键长按 6s → 真关机**」。
  - **必须承认的劣势**：Loona 有"物理状态指示灯明示摄像头/麦克风开/关"（S3 `Transparent Sensory Status`），我们**做不到同等级别**（固件只读，不能新增指示灯语义）→ 这条只能由 App 侧 UI 承担，要在文档里写清楚，不要假装有。
- **要改的规格**：`00` 号 §7 **S-7**（设备摄像头/麦克风工作状态可见）补"固件只读约束下的实现边界"；`00` 号 §3 **A-1 在场感知** 补"App 不在场时感知会话不开启（等价于 Loona 的物理休眠）"；`04` 号 §3.4 硬件事实核正节补 CoreS3 POWER 键与电源 LED 事实。

#### P5 · Face & attention on-device only

- **官方原文**（S1）：`Your facial expressions and attention patterns are processed entirely on your iPhone — never uploaded. Only your explicit task commands go to the cloud`
- **官方原文**（S3 `https://keyirobot.com/blogs/news/meet-loona-deskmate-the-desktop-ai-companion-for-work`）：`On-Device Local Processing: Visual attention tracking and presence detection run locally on hardware to minimize cloud data transmission.`
- **官方原文**（S5）：`Facial detection, attention tracking, and expression analysis run strictly on the docked iPhone's Neural Engine. Those biometric signals never leave the device. Only the explicit task commands a user issues travel to the cloud.`
- **已知实现**：跑在 iPhone 的 **Neural Engine**（S5 明写），因此能到 sub-0.5s 语音响应。
- **我们的组件**：iOS App 本地 Vision 推理（人脸/注意力/在场）＋ 后端只收布尔量与置信度 ＋ 设备端 0.3MP 只做存在性信号（00 号 S-1）。
- **判定**：✅ **直接抄，而且我们更强**。
- **依据（硬差异，可对外讲）**：Loona 只承诺**派生量**（表情、注意力）不上传，**没有承诺原始图像不出手机**；我们 S-1 承诺的是**原始帧默认不出本机**。两边原文一比即可判定，不靠印象。
- **要改的规格**：`00` 号 §7 **S-1** 增加对照句"Loona 仅承诺派生量不上传，我们连原始帧都不出本机"；`04` 号 §3.2 **A｜设备即档案** 补这条差异；`01` 号 §6.2 体现技术实力节可引用。

#### B1 · One Nudge, Then Quiet

- **官方原文**（S1）：`Ignored reminders retry gently or stand down — never escalate to acting for you.`
- **官方原文**（S5）：`Official rules state "one nudge, then quiet" and "nothing without permission." It functions as a prompt-driven assistant, not an unsupervised manager.`
- **已知实现**：提醒被忽略后最多再试一次，然后放弃。
- **⚠️ 官方文本内部张力**：S1 的时间线文案写 `Day 1 … It observes, syncs, and starts sorting.` / `Week 3 … It suggests things before you think of them.`，与 S5 的"prompt-driven assistant, not an unsupervised manager"存在张力。**官方未给出可执行的主动性上限**。
- **我们的组件**：后端主动开口调度 ＋ iOS 通知/主动话术。
- **判定**：✅ **直接抄**。
- **依据**：我们 00 号 **E-3** 已有更硬的版本（`频率上限（默认 24h 内 ≤ 2 次）`、`可一键"安静"`）。但必须吸收 Loona 的**后半句**：`never escalate to acting for you` —— 把它写成**状态机约束**：主动开口只允许产出"话"，**不允许产出"代执行动作"**。这条直接保护护城河①：主动性是关系的表达，不是替用户做决定。
- **要改的规格**：`00` 号 §3 **E-3 主动开口** 加约束"提醒不得升级为代劳"；`04` 号 §四 机制 8 里的 F 低打扰主动性对齐。

#### B2 · No Commentary

- **官方原文**（S1）：`It adapts its timing to your pace. It never remarks on your mood or "how you seem."`
- **已知实现**：不点评用户情绪；**是否也禁止表达自身情绪，官方未明写**（属推测）。
- **我们的组件**：后端人格提示词 ＋ iOS 端不做情绪点评/贴标签/心理分析。
- **判定**：⚠️ **抄了要改**。
  - 抄：**不点评用户情绪**（不评"你今天看起来有点累"）—— 这与我们的 S-9「不做健康诊断」同向，也是保护用户的。
  - **不抄**其隐含的"不表达自身情绪"：我们的护城河里明确有"物理化情绪"（B-3：侧身／前倾／压低）、"久未互动的低落"（A-4）、在场感知。照抄整句会砍掉陪伴本体。
  - **边界怎么划**（可写进提示词）：Loona 禁的是"**评价用户**"（remarks on your mood）；我们要禁的也是"评价用户"，而"**表达自己**"必须保留 —— 区分点写死在人格提示词层，不靠模型自觉。
  - **外部佐证**：我们 21 号文档已取证 Loona Deskmate App Store **1.82 分 / 11 条评分**、分类从 Entertainment 改到 Productivity —— 把"脸"换成"助理面板"是已被市场否决的路径；B2 若整句照抄，等于自己走那条路。
- **要改的规格**：`00` 号 §3 **B-1 情绪 → 表情/动作语义映射** 与 **B-3 物理化情绪** 增加"不点评用户情绪，但允许表达自身状态"的边界；`00` 号 §7 **S-9** 扩写；`04` 号 §3.3 必须诚实写下的四个弱点节补一条风险。

#### B3 · Nothing Without Permission

- **官方原文**（S1）：`Every tool is a separate toggle — visible, revocable, off by default.`
- **已知实现**：每个工具独立开关，默认关。
- **推测（未取证）**：`default off` 是否也覆盖"屏幕感知""云端模型调用"等非工具能力，官方未说明；S1 的 plans 分档暗示屏幕感知**不**是默认关（否则分档无意义）。
- **我们的组件**：iOS App 设置 Scene ＋ 后端出网/调用裁决层。
- **判定**：✅ **直接抄，但必须扩面**。
- **依据**：Loona 的"默认关"只覆盖**工具**。我们要扩成**全域默认关**：任何数据出设备都要有独立开关 ＋ 开关动作写入可审计日志。这里直接给出 `04` 号 §八 **P2** 的裁决方向 —— **默认走本地 provider；切到云端 provider 需要显式开启，并在设置里用可读文案说明"对话原文将离开设备"**。这样"私人层永不入库"才有可验证性，而不是一句口号。
- **要改的规格**：`00` 号 §7 新增 **S-10（逐能力开关）** 与 **S-11（出网即需显式授权 + 授权日志可审计）**；`04` 号 §八 **P2** 写上建议裁决；`05` 号 §2.1 三条不能违反的选型红线补一条。

---

## §3 「不能抄」清单与理由（护城河视角）

判据（来自 `04` 号 §3.2）：我们的护城河是**商业模式互斥型**的 —— 我们走"关系可带走、零锁定"，巨头走"订阅 + 平台锁定"。因此**任何让关系不属于用户、或引入平台锁定的做法，照抄即自毁护城河**。

| # | 不能抄的做法 | 官方证据（Loona 实际怎么做的） | 为什么抄了会毁掉我们的护城河 | 关联护城河条目 |
| --- | --- | --- | --- | --- |
| N-1 | **把屏幕感知做成产品功能，并按订阅分档** | 产品页 plans：Free `Basic Screen Awareness` / Plus `Advanced Screen Awareness` / Pro `Full Screen Awareness & Action`（S1） | 屏幕感知一旦成为卖点，就会被推向付费档 —— 这是"能力深度 = 会费"的直接证据。我们一旦引入屏幕感知，就会被迫回答"免费给多少深度"，从而把能力分级和订阅绑在一起 | ④零锁定 / ⑤商业模式互斥 |
| N-2 | **"一键清空记忆"作为记忆控制的主手段** | `Clear memory with one tap.`（S1）；`Memory stored by the system can be reviewed and cleared with one tap`（S5） | 整段关系可以被一个开关抹掉 = 关系其实属于平台而非用户。且**未取证**任何导出能力 —— 全站官方页面（含 S1/S2/S3/S4/S5）**从未出现**"export / portable / your data（可携带义）"这类承诺（"Your data, your device, your rules." 只是营销标语）。我们必须反过来：**可导出是前提，清空是动作** | ①关系资产可带走 / ③零锁定 |
| N-3 | **云端记忆作为唯一真相源** | 记忆可被"review"并"clear one tap"，指向平台侧存储（S1/S5 推测） | 我们是「设备即档案」：记忆长在用户自己拥有的东西上，可读可改可导出。云端为唯一真相源 = 把护城河的核心资产交出去 | ①设备即档案 / ④可带走 |
| N-4 | **订阅档位分级能力（credits 制）** | `Free 200 credits` / `Plus 1,000 credits` / `Pro 3,000 credits`，`Credits refresh on your billing cycle and do not roll over.`（S1 plans i18n 原文） | `04` 号 §3.2 已裁决：**"订阅收入与'关系可带走'直接互斥"**。credits 还会制造"记忆/能力随付费衰减"的预期 —— 那等于宣告记忆是租用物 | ④零锁定 / ⑤商业模式互斥 |
| N-5 | **"零订阅"当成差异化卖点去对标** | 官方自相矛盾：买家指南称 `Zero-Subscription Model` / `Subscription Fee $0/mo` / `without locked tier add-ons`（S5），产品页同时挂出 Free/Plus/Pro 三档 plans（S1） | 这不是可抄的叙事，是**竞品自相矛盾的窗口期**。我们的"零锁定"必须靠**可验证的架构**（本地档案 + 导出 + 无出网默认）成立，而不是靠承诺。抄它的口号，一旦它改口我们就被打脸 | ④零锁定 |
| N-6 | **跨设备统一记忆作为核心卖点** | `One memory, every device` / `Never Explain Twice`（S1 首页 Highlights） | "跨设备统一记忆"的前提是**一个中心化的账号记忆库**。我们的关系在用户自己的设备/文件里；一旦为了跨设备同步而建中心库，就把档案变成了平台资产 | ①设备即档案 / ④可带走 |
| N-7 | **把"AI 助理能力"（邮件草拟、日程、Slack、预订）当产品主体** | S1 集成清单：Gmail / Google Calendar / Outlook / Teams / Slack / Notion / Drive / Docs / Slides / Sheets / OneDrive；S3 四层能力中的 "Tool ecosystem" | 我们的 21 号文档已取证反面：Loona Deskmate App Store **1.82 分 / 11 条评分**，分类从 Entertainment 改到 **Productivity**。我们把助理能力当主体，就直接进入同一个评价体系 | ⑤商业模式互斥 / 产品定位 |
| N-8 | **用 iPhone 当算力与感知主机（模态定义）** | S2 职责分工表：表情界面、摄像头与注意力感知、语音接口 **全部来自 iPhone** | 这不是隐私问题而是**形态问题**：我们没有"让用户把手机插上去"的硬件，也没有 165W GaN 供电与磁吸结构。它无法抄，也不该抄 —— 抄了等于我们没有自己的产品 | 形态护城河 |
| N-9 | **让"隐私红线条"停留在文案层** | 官方 Privacy Policy `Last updated: February 05, 2023`，全文**没有**提到 DeskMate、面部/注意力数据、记忆、屏幕感知或 MCP；只有 `We may share personal information with trusted service providers…`（S4） | 这是**最值得警惕的一条**：Loona 的"五条红线"没有对应任何可执行条款。**我们必须把红线写成可验证的实现**（否则我们和它一样，只是营销话术） | ②私人层不入库 / ③可审计 |

---

## §4 Loona vs 我们：正面对位

### 4.1 能力 / 价格 / 隐私叙事差异表

| 维度 | Loona DeskMate（官方原文/官方数据） | 我们（StackChan） | 差异性质与结论 |
| --- | --- | --- | --- |
| 价格 | `$299.00 USD (One-time MSRP)`（S1 JSON-LD `price: 299.0`；S5 表格 `Loona DeskMate Price $299.00 USD (One-time MSRP)`） | 我们不是单一成品硬件厂商，**价格未定**（04 号 §八待拍板项未含定价） | ⚠️ **未取得可比价格**。不可写"我们更便宜/更贵" |
| 订阅 | 官方产品页挂 Free / Plus / Pro 三档 credits；官方指南同时宣称 `$0/mo (No recurring software charges)`（S1 vs S5，**官方自相矛盾**） | 零订阅是护城河⑤的**硬约束**（04 号 §3.2：订阅收入与关系可带走直接互斥） | ✅ 我们必须**永久保留**这条差异，且不能拿"我们不订阅"去对打它的宣传口径（它也这么宣称） |
| 形态 | 3-DoF（Yaw/Pitch/Roll）无刷舵机基座 + 磁吸 iPhone 12+（MagSafe/Qi2 15W）（S1/S2/S5） | M5Stack CoreS3 官方成品硬件（固件只读）＋ 原生 iOS App | 我们的优势不在硬件自由度，在**软件与数据归属** |
| 算力在哪 | iPhone 的 **Neural Engine** 跑本地多模态，`sub-0.5 second voice response`（S5）；`Operating through your iPhone's Bionic or M-series Neural Engine` | iPhone 本地视觉/音频推理 ＋ 后端 fork 官方 Go server 接 MiniMax 大脑 | 🔑 **相同点是"端侧感知"，不同点是"云端大脑归谁"** —— Loona 的云端是它的账号体系，我们的云端是用户自托管 |
| 响应延迟 | `0.5s AI Response Latency`（S1 规格表）；`sub-0.5s Multimodal Local AI`（S5） | 未实测（03 号链路已跑通但**无真机**） | ⚠️ 我方数字**未取得**，不可对比 |
| 记忆 | `One memory, every device` / `Never Explain Twice` / `Review everything … Clear memory with one tap`（S1） | 长期记忆**必须自托管**（00 号 C-1）；每条可查**逐字出处 + 日期**；可导出 | 🔑🔑 **最大差异**：我们比它多"**可审计来源**"和"**可带走**"两件它完全没承诺的事 |
| 屏幕 | `Pull-Mode Screen Awareness` + 剪贴板实时同步，但**深度按订阅分档**（S1 plans） | **无屏幕感知通道**（00 号 §2.2） | ✅ 我们的"没有"是护城河，不是功能缺失 |
| 感知出域 | 表情/注意力**派生量**留在 iPhone（S1/S3/S5）；**原始图像是否出手机未承诺** | **原始帧默认不出本机**（00 号 S-1），只上传布尔量与置信度 | ✅ **我们更硬**，可直接写进对外叙事（依据：S1 与 00 号 S-1 原文对比） |
| 工具生态 | 16 个工作集成（Gmail/Outlook/Teams/Slack/Notion/Drive/Docs/Sheets/OneDrive…）+ MCP | 无工作工具生态；`00` 号 §2.2 明确不做 MCP 接入 | ✅ 这是**刻意的减法**，不是落后 |
| 行为边界 | One Nudge Then Quiet / No Commentary / Nothing Without Permission（S1） | E-3 频率上限 + 一键安静；A-4 久未互动低落；B-3 物理化情绪 | ⚠️ 抄边界，**不抄"把陪伴降级成助理"** |
| 数据归属 | 官方站**零处**承诺导出/可携带；Privacy Policy 停留在 2023-02-05（S4） | 关系资产可导出、零锁定（护城河④） | 🔑🔑 **这是我们唯一可以长期独占的位置**，且 Loona 的空档是**结构性的**（订阅+云端记忆必然导向锁定） |

### 4.2 我们的差异化叙事（只基于已取证事实，不编造功能）

**一句话叙事**：
> **Loona 让你的 iPhone 变成一个有身体的助理；我们让关系长在你自己拥有的设备上 —— 它记得你，是因为那天你说了一句什么，你可以当场查、当场改，而且整段关系随时带走。**

四条可对外讲的差异（每条都有原文依据）：

1. **可审计 vs 可清空**：Loona 给你的是"一键清空"（S1）；我们给的是**逐字出处 + 日期 + 可改权重不可改原文 + 整库导出**。前者是删除权，后者是所有权。
2. **原始帧不出机 vs 派生量不上传**：Loona 只承诺表情/注意力派生量留在 iPhone（S1/S5）；我们承诺**原始帧**就不出本机（00 号 S-1）。
3. **边界写进架构 vs 写进文案**：Loona 的"五条红线"在 **2023-02-05** 的 Privacy Policy 里**没有任何对应条款**（S4）；我们的红线必须落成**可验证的实现 + 可审计日志**（00 号 §7 S-1..S-9，建议扩到 S-11）。
4. **零锁定的可验证性**：Loona 同时挂出 Free/Plus/Pro 三档 plans（S1），且其买家指南自称 `Zero-Subscription Model`（S5）—— 官方互相打架，说明"不订阅"在订阅型商业里只是**宣传口径**；我们的零锁定必须靠**架构**（本地档案 + 导出 + 出网默认关）而不是承诺。

**明确不写的**（避免自造）：不写"我们更便宜"（我方价格未定）、不写"我们响应更快"（我方延迟未实测）、不写"我们的记忆更聪明"（无对比数据）、不写任何我方未取证的硬件参数。

---
## §5 竞品雷达维护建议（官方 buying-guide 目录怎么持续跟）

> 规模修正见 §5.1：前轮记「42 页 / 250 篇」，**sitemap 实测为 455 篇唯一 buying-guide**。

### 5.1 ⭐ 本轮实测修正：官方竞品目录比前轮记录大得多

前一轮（`50` 号 §三）记录的官方目录规模是「**42 页、250 个唯一指南页**，产品级 slug 约 139 个」。本轮用**站点 sitemap** 实测（权威全量口径）：

| 指标 | 实测值（2026-10-24） | 口径 |
| --- | --- | --- |
| `https://keyirobot.com/sitemap.xml` | sitemapindex，4 个子表：blogs / articles / routes / products | 机器可读权威入口 |
| `sitemap/articles/1.xml` 全部文章 | **601** 条 | 全站文章 |
| 其中 `/blogs/buying-guide/**` | **455** 条（唯一 slug 也是 455，无重复） | 官方竞品/选购目录全量 |
| 其中 `/blogs/news/**` | 14 条 | 官方发布/评测 |
| 其中其他 `/blogs/**` | 132 条 | 教程/使用指南 |
| buying-guide 中「产品级」slug（含 robot/pet/deskmate/pup/companion/avatar/buddy/friend/bot） | **399** 个 | 启发式分类 |
| buying-guide 中「通用/how-to」slug | 56 个 | 非产品页 |

> ⚠️ **两者口径不同，不是矛盾**：前轮的「42 页 / 250 篇」是**按站点分页逐页枚举**得到的（有枚举上限），sitemap 是全量。**今后一律以 sitemap 为准。**

### 5.2 更新节奏（决定复查频率）

按 `lastmod` 统计 2026 年逐月（articles 全量）：

| 月份 | 更新文章数 |
| --- | --- |
| 2026-01 | 40 |
| 2026-02 | 21 |
| 2026-03 | 28 |
| 2026-04 | 26 |
| 2026-05 | 30 |
| 2026-06 | 24 |
| 2026-07 | 30 |
| 2026-08 | 23 |
| 2026-09 | 24 |
| 2026-10（截至 10-24） | 12 |

→ **月均 20–40 篇**，且 2026-10 已更新 12 篇。**建议：每月 1 次 sitemap diff，优先看 `lastmod` 变化的页。**

### 5.3 落地做法（可直接执行）

1. **基线文件**：存一份 `sitemap/articles/1.xml` 快照 + 一份 455 条 slug 清单（含 `lastmod`）。下月再取一次，`Compare-Object` 即得新增/改动清单。**不要靠翻分页页面**（分页会漏、会变）。
2. **每篇固定抽 8 个字段**，形成一张竞品对比表（这是我们自己的雷达表，不是复述它的目录）：
   ① 品牌/型号 ② 价格 + 订阅口径（一次性 / 月费 / 分档 / credits） ③ 是否屏幕感知 + **是否按订阅分档** ④ 记忆是否**可导出**（关键字段） ⑤ **Privacy Policy 的 `Last updated` 日期** ⑥ 算力/感知跑在哪个端 ⑦ DoF / 供电 ⑧ **官方自己是否前后矛盾**。
3. **最便宜的高信噪比指标 = `Privacy Policy` 的 `Last updated` 日期**。本轮实测 Loona = **2023-02-05**（早于 DeskMate 三年）→ 一行就判定"它的隐私承诺没有法律文件兜底"。这个指标对每个竞品都能一键查。
4. **专门记录"官方自相矛盾"**：本轮在 Loona 官方站内部就抓到两处（① 产品页挂 Free/Plus/Pro 三档 plans vs 官方指南宣称 `Zero-Subscription Model` / `without locked tier add-ons`；② `physically` 断电 vs 同段又写 `closing the companion app immediately pauses spatial tracking`）。**竞品自相矛盾 = 它没想清楚的地方 = 我们可以做得更硬的地方。**
5. **优先级排序**（最像我们的几篇，优先深读）：
   `loona-deskmate-price-value-guide`（本轮已读，2026-07-31）、`desk-robot-pet`、`razer-project-ava`、`aibi-pocket-pet`、`pophie-robot`、`miko-mini`、`mirumi-robot`、`eilik-robot`、`looi-robot-charger-review`、`emo-vs-vector-2-0`、`sony-aibo-vs-loona-petbot`。
6. **产品 sitemap 也盯**：`sitemap/products/1.xml` 目前 12 条（`deskmate`、`petbot`、`snowy-whimsy`、`space-explorer`、`charging-dock` 及配件）—— 配件 SKU（钥匙扣、围巾、球）也是**情感绑定/复购**的观察点。

---

## §6 未取得清单（附试过的路径与失败原因）

| # | 未取得项 | 试过的路径 | 失败原因 / 备注 |
| --- | --- | --- | --- |
| U-1 | **Free / Plus / Pro 三档的具体月价** | S1 产品页 SSR HTML 全量扫描 `$` 数字；页内 plans 弹窗 i18n 全量（462 键） | 页面只有 `/ Month` 单位串，**没有金额**；S1 页面内仅 7 个 `$` 串（`$0.00` 购物车、`$25` 邮件订阅折扣、`$299.00` 商品价、`$30`/`$50`/`$59` Halloween 活动、`$350` 活动门槛），**均与订阅档价无关** |
| U-2 | 规格表 Charging & Power 段 row3/row4 值、**AI Performance 段的 Local Processing / Privacy Modes / Data Policy / App Support / Updates** 五行值** | S1 SSR HTML 扫描；i18n 字典全量解析 | 这五行**只有 label 在 i18n 里，value 是客户端组件渲染**；本机无 JS 渲染环境。**这五行本应是"隐私架构"最硬的字段，恰好没取到** |
| U-3 | 官方隐私专页 / 隐私 FAQ | `/blogs/buying-guide/loona-deskmate-privacy-guide` | **404**（返回 74,034 字节的站点 404 页，与本轮其他 404 同尺寸） |
| U-4 | MCP 生态的细节：server 是官方自建还是第三方？是否支持用户自带 MCP server？记忆写入是否走 MCP？ | S1/S2/S5 三处官方文本全读 | 官方只说 `the secure MCP ecosystem`（S1）与 `the open-source Model Context Protocol (MCP)`（S5），**到此为止** |
| U-5 | **记忆实际存在哪、是否可导出、能否逐条查看出处** | S1/S2/S3/S4/S5 全文检索 `export` / `portable` / `your data` | **官方全站零处承诺可导出**；`Your data, your device, your rules.` 只是营销标语；Privacy Policy 无相关条款。**"未取得"本身就是结论** |
| U-6 | 屏幕感知的技术边界（Mac 原生具体做了什么？剪贴板是否整段上传？） | S1/S3 提及 "real-time clipboard and screen awareness"、"Mac 原生 / Windows via a related app" | 官方**未给出机制细节**，只有能力声明 |
| U-7 | 除"explicit task commands"之外，音频/视频流是否离开设备 | S1/S2/S3/S5 | 官方只承诺表情/注意力派生量本地；**语音流路径未说明** |
| U-8 | 隐私条款与产品页口径的官方澄清 | 官方无公开说明页 | 未取得 |
| U-9 | 165W / 180W / 140W 三个功率口径的统一说明 | S1 规格表 + 盒内清单 + JSON-LD + S5 | 三个数字各有出处（Total System Power / 盒内充电器 / 单端口与多端口），**官方未统一说明**，引用时必须写明是哪个口径 |
| U-10 | `/pages/plans` | `https://keyirobot.com/pages/plans` | **不存在**，返回首页内容；订阅档实际嵌在产品页弹窗内 |
| U-11 | Loona App（iOS）内的权限界面实况 | 未抓 App Store 页 | 本轮未做（只做官方站取证） |
| U-12 | CES 2026 官方新闻稿 / KEYI 官方发布材料 | `keyi-tech.com` 家族域名 | 前轮已记录 DNS 解析失败；本轮未重试（`keyirobot.com` 已足够覆盖产品事实） |
| U-13 | Loona Petbot 现价 | S5 写 `$499`，前轮 `50` 号记 `$429 / $529` | **两处官方数据冲突**；本轮不采用任何一方，Petbot 价格不进入结论 |

---

## §7 文末自查

### 7.1 取证纪律自查

| 检查项 | 结果 |
| --- | --- |
| 每条结论是否带来源 URL + 抓取日期 | ✅ 全部结论标注 S1–S7 编号（§1.0），S1–S5、S7 附完整 URL，抓取日期统一 2026-10-24 |
| 是否只用官方页面 / 官方指南原文取数字 | ✅ 价格/延迟/功率/积分全部来自 S1 JSON-LD、S1 页面文本、S1 i18n、S5 官方指南；**未使用任何媒体转述做数字来源** |
| 是否区分「官方原文 / 媒体转述 / 我们的推断」 | ✅ §1 全为官方原文；§2.2 每条实现描述内用「**已知实现**」「**推测（未取证）**」显式分隔；§4.2 推理段落均回指我方已有文档 |
| 抓不到的是否写「未取得」并附失败路径 | ✅ §6 共 13 条，含 404、SSR 无值、域名不可达等具体原因 |
| 是否编造未取证功能 | ✅ §4.2 末尾显式列出「明确不写的 4 条」；全文未出现我方价格、延迟、硬件参数的臆测数字 |

### 7.2 冲突与自相矛盾登记（引用时必须带）

| # | 冲突 | 冲突双方 | 处理 |
| --- | --- | --- | --- |
| X-1 | 是否订阅 | S1 产品页挂 Free/Plus/Pro 三档 credits **vs** S5 指南称 `Zero-Subscription Model` / `Subscription Fee $0/mo` / `without locked tier add-ons` | **以 S1 为准**（购买页实际售卖口径）；两者同时记录 |
| X-2 | 屏幕感知是否付费 | S1 plans 把屏幕感知分三档 **vs** S5 称不锁档 | 同上，以 S1 为准 |
| X-3 | 物理断电还是 App 后台 | S1 `instantly and physically` **vs** S5 同段 `or closing the companion app immediately pauses` | 判定：**真正生效机制是 iOS 后台规则**，"物理"是结果不是独立机制 |
| X-4 | 功率口径 | 规格表 `165W` **vs** 盒内 `180W GaN Charger` **vs** JSON-LD `140W 单端口 / 180W 多端口` | 三个口径各有出处，引用必须注明是哪一个 |
| X-5 | 官网文章日期 | 首页博客卡标 `January 7, 2026` **vs** 文章页标 `August 19, 2026`（S2 同一篇 iPhone 解析文） | 记录两者；**不推断**哪个是真发布日 |
| X-6 | Loona Petbot 价格 | S5 `$499` **vs** 前轮 `50` 号 `$429 / $529` | 不采用，不进入结论 |
| X-7 | 我方文档内部 | `01` 号 §6.1 列的 6 条护城河（★6 = 三通道同步反馈）**vs** `04` 号 §3.2 的第 6 条（设备即档案 + 可审计来源） | 本文件以 `04` 号 §3.2 为准（总纲裁决）。**这是我们内部文档的口径冲突，建议主会话裁决后统一**（本任务不代改） |

### 7.3 表格与格式自查

- 表格列数 == 表头列数；单元格内 `|` 均已转义为 `\|`；表格块内无空行。
- 文件编码 UTF-8 **无 BOM**；换行 **LF**。
- 本文件只新建，未修改任何已有文件；未执行 git commit / push。
- 临时产物全部落在 `D:\AP\AP7000\ai-workspace\stackchan-research\r56\`，未污染仓库目录。

### 7.4 一句话交付

> **能抄的是"边界与姿态"**（逐能力开关默认关、拉取式感知、原始帧不出机、提醒不升级为代劳、不点评用户情绪、物理断电边界的存在），**不能抄的是"能力分档与云端归属"**（屏幕感知按订阅分三档、credits 制订阅档、一键清空代替导出、云端记忆为唯一真相源、"零订阅"当口号）—— 因为后者会直接把我们"关系可带走、零锁定"的护城河换成"能力按会费解锁、关系存在别人数据库里"。
