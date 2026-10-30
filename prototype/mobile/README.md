# 小栈 · 手机端（Web/PWA）

> 这是**桌面陪伴机器人的手机控制端**。不是「概念稿」——
> 每个像素都能追到规格，规格由机器门禁守着（[`tools/check_mobile_app.py`](../../tools/check_mobile_app.py)，15 条判据 + 18 项变异自检）；
> 接口契约另有一道门禁（[`tools/check_mobile_contract.py`](../../tools/check_mobile_contract.py)，8 判据 + 10 项变异自检）。

---

## 一、它长什么样

| 屏幕 | 作用 | 截图 |
|---|---|---|
| **对话主屏**（默认落屏） | 说话、看小栈的反应 | [`mobile-01-chat.png`](../../assets/screenshots/mobile/mobile-01-chat.png) |
| **遥控屏** | 摇杆转头 + 速度档位 | [`mobile-02-remote.png`](../../assets/screenshots/mobile/mobile-02-remote.png) |
| 遥控屏（拖动中） | 读数与 3D 同步 | [`mobile-03-remote-drag.png`](../../assets/screenshots/mobile/mobile-03-remote-drag.png) |
| 摄像头面板 | 看小栈现在看到的 | [`mobile-04-camera.png`](../../assets/screenshots/mobile/mobile-04-camera.png) |
| **设置屏** | 二级页入口 | [`mobile-05-settings.png`](../../assets/screenshots/mobile/mobile-05-settings.png) |
| **小栈控制台**（首页） | 设备状态 + 功能入口 | [`mobile-06-console.png`](../../assets/screenshots/mobile/mobile-06-console.png) |

> 设备屏（320×240）上的那张小脸**不是手机端画的**，是官方固件渲染的。
> 它的逐像素仿真与几何真值见 [`docs/research/96`](../../docs/research/96-设备屏表情几何真值订正与weight两档发现.md) 与
> [`assets/screenshots/device-screen/`](../../assets/screenshots/device-screen/)。

---

## 二、跑起来

### 组合 A（推荐）：本仓手机端 + **本仓后端**（自闭环，不依赖旧项目）

```powershell
# 1) 起本仓后端（提供 /gui/* HTTP 适配层）
py -3.12 server\http_api.py --port 17868 --provider stub   # --provider minimax 走真实 MiniMax 大脑
# 2) 起手机端静态服务（默认端口 17866）
$env:STACKCHAN_MOBILE_ACCESS_TOKEN='stackchan-mobile-local'
$env:STACKCHAN_BACKEND_ORIGIN='http://127.0.0.1:17868'
py -3.12 serve.py --port 17866
```

### 组合 B：本仓手机端 + **旧项目电脑后台**

不设 `STACKCHAN_BACKEND_ORIGIN` 即可（默认就是 `http://127.0.0.1:17865`）。

### 打开方式

`http://127.0.0.1:<手机端端口>/?pair=<STACKCHAN_MOBILE_ACCESS_TOKEN>`

- 配对 token 只走 **query**，服务端校验后换成 **HttpOnly + SameSite=Strict** 的 Cookie（[`mobile_proxy.py`](mobile_proxy.py)）。
- 手机端**只访问同源 `/mobile-api/*`**；真实后端路径由代理白名单映射，浏览器永远看不到内网路径。
- **手机同一 Wi-Fi 下打开**：把 `127.0.0.1` 换成电脑的局域网 IP，例如 `http://10.21.184.118:17866/?pair=stackchan-mobile-local`（`serve.py` 监听 `0.0.0.0`，局域网可达）。

### ⚠️ 一个必须说清的事实

**本仓 `server/` 现在有两套后端**：

| | 用途 | 状态 |
|---|---|---|
| `server/http_api.py` | **HTTP `/gui/*` 适配层**（手机端要的那一面） | ✅ 已实现：37 条路由 = 15 条真实现 + 22 条显式 501；契约见 [`server/mobile_contract.py`](../../server/mobile_contract.py) |
| `server/` 其余部分（韵律 → 关键帧 → WS 设备通道） | 设备侧控制面 | ✅ 可用，但**与 HTTP 层尚未并成一套进程** |

⇒ 手机端**已经可以脱离旧项目后台**、只靠本仓两个服务自闭环（组合 A，实测通过）。
⇒ 但**「两套后端要不要合并成一套」本身仍待拍板** —— 登记为 **Q27**
（见 [`docs/spec/07`](../../docs/spec/07-待拍板清单与防返工机制.md) §3.5）。

---

### ⚠️ 3D 模型**不入库**（许可原因）

遥控屏与控制台首页的那个 3D 小栈，模型文件是官方的 `stack_chan_model.glb`（**3.16 MB**），
路径在官方仓的 **`app/assets/`** 下。

⚠️ **官方 `app/` 目录没有 LICENSE 文件**（只有 SPDX 头；`firmware/` `server/` `remote/` 才是 MIT）
⇒ 按 [`docs/research/33`](../../docs/research/33-许可与商标边界.md) 的「**我们不碰 `app/`**」结论，
**这个模型不随仓库分发**。

⇒ 克隆本仓后 3D 会 404（`/model-assets/stack_chan_model.glb`），
**其余功能不受影响**（对话 / 遥控摇杆 / 设置 / 摄像头 / PWA 全部可用）。
⇒ 要本地看 3D：自行从官方仓取该文件，放到 `vendor/m5stack-StackChan/app/assets/`。

---

## 三、屏幕结构：Tab 只有 3 个

```
对话  ·  遥控  ·  设置
```

首页（控制台）、屏幕功能、功能测试、更新小栈 **全部降级为二级页**。
理由：舵机只有 yaw + pitch 两轴、屏幕 95% 是脸，**「更多」不该占一级位置**。

---

## 四、⭐ 签名元素：小栈的眼睛

全站唯一的记忆点，其余一律克制。

- **白圆眼 + 黑色眼皮**，纯 CSS 眨眼动画 5.4 s；
- 两眼**错开 0.07 s**，右眼额外上移 1.5 px（好奇感）；
- 高光用径向渐变，不用图片。

**机制照抄官方固件**（`eyes.cpp`）：眼白圆 → 眼睑方块**后建** ⇒ 压在上面。
所以「思考中」不是转圈，而是**眼皮压到 62%**（`chat.js` 的 `setPending()` 切 `.chat-screen.is-thinking`）。

> ⚠️ 这里有个我们**自己踩过的坑**，已订正并写成规格：
> 固件里眼睑是**容器内绝对定位**（`align(CENTER)` 后 `setY(offset)`），与眼白**并不同心** ⇒
> weight=0 时露出的是**下缘月牙 25.23%**、**不会露角**。见 [`docs/research/96`](../../docs/research/96-设备屏表情几何真值订正与weight两档发现.md) §二。

---

## 五、遥控屏：没有滑块，也没有数字输入框

| 设计 | 取值 | 依据 |
|---|---|---|
| 摇杆直径 | **132 px**（窄屏 116 px），球 40 px | 拇指可达 + 视觉克制 |
| 外圈虚线 | 小栈的**视场** | 语义，不是装饰 |
| 死区 | **8%** | 太小会抖，太大会「不跟手」 |
| 俯仰 | **摇杆纵向拖动**，中心 45°，满量程 3–87° | 舵机行程 `map_range` 口径 |
| 速度 | **4 个圆圈点选**（安静 / 轻柔 / 自然 / 活泼） | 数字与滑块都会破坏「玩具感」 |
| 初始俯仰 | **45°**（不是固件默认 6°） | 球在正中 = 平视微仰的自然对视姿态 |

球心带**瞳孔**，随拖动偏移（`--look-x` / `--look-y`）⇒ 小栈在「看你」。

---

## 六、摄像头面板：静默自启，按需出现

- 进 App **静默** `POST /device/camera-preview/start`（失败全吞，6 s 超时）；
- 面板**默认隐藏**，点右上角相机按钮才 `open()`；
- 每 900 ms 拉一帧 `/mobile-api/device/camera/latest.jpg`（blob URL，关闭时 `revokeObjectURL`）。

> ⚠️ 面板挂在 **`.app-shell` 直接子级**，不是 `.screen` 里面。
> 因为 `.screen.is-active` 带 animation ⇒ 会创建 stacking context ⇒ 放在里面的 fixed 浮层**会被 Tab 栏压住**（实测踩过）。
> 这条写成了门禁 **MO-10**。

---

## 七、规格怎么被守住（机器可判的部分）

散文规格会烂掉，所以能机器判的都做成了门禁判据
（[`tools/check_mobile_app.py`](../../tools/check_mobile_app.py)）：

| ID | 判据 |
|---|---|
| MO-01 | 全仓无 U+FFFD（乱码硬门禁） |
| MO-02 | Tab 恰好 3 个，且是 对话 / 遥控 / 设置 |
| MO-03 | 不得再有 `pitchSlider` / `speedSlider`（规格已删） |
| MO-04 | 速度必须是 4 个圆圈，且恰好 1 个默认选中 |
| MO-05 | 初始俯仰 = 45°（JS 与 DOM 初始值必须一致） |
| MO-06 | 摇杆死区 = 8% |
| MO-07 | 摇杆 132 px、球 40 px |
| MO-08 | PWA 主题色必须是暗色，且不得回退到旧浅色 `#f7f7fa` |
| MO-09 | 入口代码版本号三处一致（`index.html` / `*.js` / `sw.js`） |
| MO-10 | 摄像头面板必须是 `.app-shell` 直接子元素 |
| MO-11 | **静态模块闭包 ⊆ `serve.py` 白名单**（漏一个文件手机端就白屏） |
| MO-12 | 图标按钮触控热区 ≥ 44 px |
| MO-13 | CSS 变量无未定义且无兜底的引用 |
| MO-14 | 摄像头面板默认 `hidden` |
| MO-15 | **SW 预缓存键必须与页面实际请求的 URL 完全一致（含查询串）** |

每条判据都配了**变异用例**（把实现改坏 ⇒ 该判据必须变红），共 18 项自检：

```powershell
py -3.12 tools/check_mobile_app.py --root .       # 体检
py -3.12 tools/check_mobile_app.py --self-test     # 变异自检
```

### 这条门禁当场抓到的 3 个真 bug

| # | bug | 后果 |
|---|---|---|
| 1 | `styles.css` 用了 `var(--text)`，但**从未定义** `--text` | 计算值阶段非法 ⇒ 那条声明直接失效（浅色主题下拉框文字色丢失） |
| 2 | `robot_3d.js` 引用 `GLTFLoader.js?v=27`，全局版本却是 `v=28` | SW 预缓存的那份**永远命中不了**，每次加载都走网络 |
| 3 | SW 预缓存写 `./styles.css`，页面请求 `./styles.css?v=29` | **缓存键不同** ⇒ 预缓存形同虚设 |
| 4 | `app.js` 里 `serviceWorker.register("./sw.js?v=28")`，入口版本已是 v29 | 浏览器**复用旧 SW** ⇒ 新预缓存永不生效 |

四个都已修，并把入口版本统一升到 **v29**（`CACHE_NAME` 同步）。
第 4 条是后来补的：MO-09 的版本号正则**原本没把 `sw.js` 算进去** ⇒ 漏判，
现已把「SW 注册 URL 的版本必须 == `CACHE_NAME`」写成硬判据。

---

## 七之二、接口契约也由机器判（`tools/check_mobile_contract.py`）

手机端读的是 `/mobile-api/*`，代理用 `_pick()` **只保留上游已经存在的键** ⇒
**后端少给一个字段，前端只会拿到 `undefined`，页面静默显示错内容，全程不报错。**

⇒ 契约写成**机器可查的字段路径**（[`server/mobile_contract.py`](../../server/mobile_contract.py)，唯一真源），
由门禁核对三方：**手机端 JS 读到什么 ⇄ 代理放行什么 ⇄ 本仓后端产出什么**。

| ID | 判据 |
|---|---|
| MC-01 | 契约里的路由必须在本仓路由表里存在（方法 + 路径 + owner 一致） |
| MC-02 | 契约里的手机端路由必须被代理白名单放行且映射一致 |
| MC-03 | 后端响应**过完代理净化层**后，契约字段必须还在 |
| MC-04 | 后端响应必须含 `backend_fields` |
| MC-05 | `non_empty` 字段必须非空 |
| MC-06 | 记忆分类 / 屏幕程序 id 必须与代理白名单一致 |
| MC-07 | 手机端 JS **真正读到**的字段必须都在契约里 |
| MC-08 | 契约里的字段必须真的在手机端 JS 里出现过（防腐烂） |

```powershell
py -3.12 tools/check_mobile_contract.py --root .        # 体检
py -3.12 tools/check_mobile_contract.py --self-test      # 变异自检（10/10）
```

它当场抓到 **5 个会让手机端静默显示错内容**的真 bug：
`reply` vs `say` 字段名对不上（对话页永远「没有返回内容」）、
设备参数键名错（亮度/音量/灯光全 400）、
屏幕程序只有 3 个（代理把 8 个按钮**全过滤掉**）、
记忆接口形状不对（记忆页永远空）、
设备状态是内部字典（状态页全「未上报」）。
详见 [`docs/research/98`](../../docs/research/98-HTTP适配层与接口契约门禁.md)。

---

## 七之三、UI 端到端回归：Playwright 脚本**已修，实测 PASS**

> 上一版文档把 `tools/verify_v26_ui.js` 记成「陈旧 / 跑不通」——**已订正**。

脚本是从旧项目搬来的 v26 版，与本仓**已收敛的 IA（3 个 Tab）**对不上，四处必挂，已全部修掉：

| # | 原状 | 修法 |
|---|---|---|
| 1 | 硬编码端口 `17869` | 读 `MOBILE_URL` 环境变量 |
| 2 | 找 4 个 Tab | 本仓「屏幕功能」是首页快捷入口 ⇒ 改用 `#home` + `[data-target="screen"]` |
| 3 | `waitUntil: "networkidle"` | 页面**每 5 s 轮询**设备状态 ⇒ 永不空闲 ⇒ 改 `domcontentloaded` |
| 4 | 3D 模型 404 记成失败 | 官方 GLB **故意不入库**（无 LICENSE）⇒ 显式过滤 |

实测（`MOBILE_URL=http://127.0.0.1:17877`，本仓手机端 ↔ 本仓后端）：

```json
{"status":"pass","url":"http://127.0.0.1:17877","viewports":["430x932","390x844"],"programs":8}
```

断言内容：两个视口**无横向溢出**、**Tab 触控区 ≥ 44 px**、**屏幕程序恰好 8 个**、
**离线时程序按钮禁用**、**对话气泡往返渲染**，各截 home / screen / chat 三张图。

截图落点 `prototype/output/`（**已加进 `.gitignore`**）；要挪出仓库用 `MOBILE_SHOT_DIR` 覆盖。
`playwright` 依赖**仍未进 `package.json`**（本机靠 `NODE_PATH` 借用旧项目的安装）—— 这是**已知遗留**，不是已解决项。

---

## 八、PWA

- `manifest.webmanifest`：`display: standalone`、`theme_color: #0e1117`、`background_color: #0b0e13`；
- Service Worker：文档/样式/脚本**网络优先**、失败回退缓存；设备接口**永不读缓存**（离线时不能用旧响应伪装实时状态）；
- 版本化缓存 `stackchan-mobile-v29`，激活时清理旧版本 ⇒ 旧脚本与新页面不会混用。

---

## 九、已验证 / 未验证

**已验证**（本机实测）：

- 6 条路由（对话 / 遥控 / 设置 / 控制台 / 屏幕 / 更新）**全通**；
- 默认落对话屏、面板默认隐藏、速度 4 圆圈、`pitchSlider` 已消失；
- 拖动摇杆后读数 **左右 95° · 俯仰 63°**，3D 模型同步跟随；
- `manifest` 读出 `theme=#0e1117, bg=#0b0e13, display=standalone, icons=2`；
- 手机端 U+FFFD = 0；
- Playwright UI 端到端回归 **PASS**（2 视口 × 3 场景，程序数 8）—— 见 §七之三。

**未验证**（不粉饰）：

- **真机 iPhone Safari 未测**（safe-area、`backdrop-filter`、触动手势、3D 性能）；
- 摄像头「自动启动」在**设备离线**时走 409/404 静默失败 —— 属预期，但**未在真机在线态验证过**；
- 两套后端**尚未合并**（**Q27**，见 §二）—— 但本仓已自带 `/gui/*` HTTP 适配层，
  本仓手机端**可以不再挂旧项目后台**就自己闭环（`STACKCHAN_BACKEND_ORIGIN` 指到本仓后端即可）；
- SwiftUI 原生端**从未编译**（本机无 Swift 工具链）。

---

## 十、文件

| 路径 | 作用 |
|---|---|
| `index.html` | 7 个屏（对话主屏 + 6 个二级页）+ 3 Tab + 摄像头面板 |
| `styles.css` | 全部样式（含小栈眼睛、摇杆、速度圆圈、毛玻璃面板） |
| `app.js` | 应用装配、路由、Tab |
| `chat.js` | 对话主屏 + `setPending()`（眼皮压到 62%） |
| `remote_control.js` | 摇杆 / 速度圆圈 / 俯仰映射 |
| `camera_panel.js` | 摄像头面板（静默自启 + 按需拉帧） |
| `robot_3d.js` | three.js 实时模型跟随 |
| `settings.js` / `update.js` / `screen_programs.js` / `actions_music.js` | 二级页逻辑 |
| `api.js` | 同源 API 客户端（超时 / 错误 / 配对态） |
| `mobile_proxy.py` | 代理：路由白名单 + 配对 Cookie + CSRF |
| `serve.py` | 静态服务 + 配对 + `/mobile-health` |
| `sw.js` / `manifest.webmanifest` | PWA |
| `tools/verify_v26_ui.js` | Playwright 端到端回归（**已修并实测 PASS**，见 §七之三） |
