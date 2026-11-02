# mobile-v2 · 小栈单屏遥控台（**旧版原型，已被 `../mobile/` 取代**）

> ⚠️ **状态：legacy。** 当前主线手机端在 [`../mobile/`](../mobile/)（3 Tab / 8 个屏幕程序 / PWA）。
> 本目录保留作**历史留痕**与实现参照（单屏遥控台的交互方案在此定型），
> 但**不再维护**；它依赖旧项目后端 17865，且部分引用的是本机绝对路径（对克隆者无效）。
>
> ⛔ **官方 3D 模型不随本仓分发**：官方 `app/` 目录无 LICENSE（见 `docs/research/33`），
> 按 `docs/spec/00` 的 O-12 决策（已定：不用）⇒ `assets/stack_chan_model.glb`
> **已从版本控制移除并被 `.gitignore` 挡住** ⇒ 克隆后 3D 会 404，
> 要本地看 3D 请自行从官方仓取该文件放回原位。

> 以**你喜欢的 3D 模型**（17865 控制台 motionControlView 的官方原厂 GLB + 浅色舞台）为视觉核心，
> 把手机端重做成**单屏遥控台**：3D 模型 + 摇杆 + 速度档 + 聊天抽屉 + 状态条。
> 演示模式（无真机）与真机双轨，同一控制通道。

---

## 一、它长什么样

| 组成 | 说明 |
|---|---|
| **3D 模型** | 官方原厂 `stack_chan_model.glb`（3.3MB，**不入库**：官方 `app/` 无 LICENSE ⇒ 本仓不分发；克隆后 3D 会 404），浅色舞台、ACES 色调映射、带阴影；`setPose(yaw,pitch)` 阻尼驱动，与 17865 控制台同源实现 |
| **摇杆** | 半透明环形，死区 8%，yaw ±128°，pitch 3–87°，松手回中；直接拖动 3D 舞台也可控制 |
| **速度档** | 安静 / 轻柔 / 自然 / 活泼 四档圆点（100 / 220 / 520 / 850），无滑块无数字 |
| **状态条** | 顶部薄条：在线（真机）/ 离线（演示模式）/ 未连接后台三态；右侧「演示/真机」模式芯片 |
| **聊天抽屉** | 右下角 FAB 按钮，底部半屏抽屉：收发消息、思考态、错误态、快捷提问；无干扰，摇杆为主 |

## 二、运行

```powershell
# 依赖：Python 3.12 + 旧项目后端 17865（提供 /gui/* 接口）
# 1) 先起旧后端
py -3.12 'D:\jss18\AI\StackChan\run_stackchan_backend.py'

# 2) 起 mobile-v2 同源服务（页面与 /mobile-api/* 同端口）
$env:STACKCHAN_MOBILE2_PORT='17867'
py -3.12 prototype\mobile-v2\serve2.py
```

打开：`http://127.0.0.1:17867/`

> ⚠️ **本仓库 `prototype/mobile-v2/` 是独立目录**，与旧项目 `mobile_app/` 并存。
> mobile-v2 依赖旧后端 17865 的 `/gui/*` 接口（通过同源代理白名单转发），这是 Q27 的落地第一步：
> 手机端只依赖**最小白名单**，将来把 `/gui/*` 砍到最小集并进本仓 `server/` 时，只改代理映射。

## 三、真机双轨说明

| 模式 | 表现 | 何时 |
|---|---|---|
| **演示模式** | 摇杆只驱动 3D 模型，状态条「设备离线 · 演示模式可用」 | 无真机 / 登不上 |
| **真机模式** | 摇杆 → `/mobile-api/device/head` → 后端 → Wi-Fi 直连真机；状态条「在线」 | 真机与后台同 Wi-Fi |

两者共用同一套摇杆 → `setPose` → 节流 → 网络请求管线，**切换零改造**。

**当前真机联调受限**：你的真机（ESP32，串口 COM3 心跳正常，uptime≈40h）固件里**写死了服务器地址**
`10.21.17.208:17863`（旧地址），而本机现在 WLAN IP 是 `10.21.184.118`，17863 桥接脚本也未在跑。
要真机上线需二选一（需你在场操作）：
1. 把本机 WLAN IP 改成 `10.21.17.208`（需管理员/改 Wi-Fi 设置）并起 `scripts/stackchan_port_bridge.py`（17863→17865）；
2. 或用官方配网流程重配设备 Wi-Fi 指向当前电脑 IP。

## 四、设备屏（320×240）遥控反馈态

固件屏幕在**被遥控时**应呈现「眼睛看向摇杆 + 四角实时角度读数 + 空闲深色」。
现提供 **`device-screen.html`**（纯前端演示模拟器，639 行 / 拖动即动），复刻这套约定。
接入真机固件时，把 yaw/pitch 换算成眼睛偏移 + 角落读数即可，规格见
[`docs/spec/02`](../../docs/spec/02-交付感与质感规范.md) §5 与 [`docs/spec/06`](../../docs/spec/06-表情参数模型.md) §7。

## 五、文件清单

| 文件 | 作用 |
|---|---|
| `index.html` | 单屏遥控台骨架（importmap + 布局） |
| `styles.css` | 全部样式（深色 · 琥珀强调 · 弹性动效） |
| `preview3d.js` | 官方 GLB 3D 渲染（复用 17865 同源实现） |
| `remote.js` | 摇杆 + 舞台拖动 + 速度档 + 真机 head 下发 |
| `chat.js` | 聊天抽屉（收发 / 思考 / 错误 / 快捷提问） |
| `app.js` | 装配 + 状态轮询 + 模式切换 |
| `api.js` | 同源代理访问层 |
| `serve2.py` | 静态托管 + /mobile-api/* 白名单代理转发 |
| `device-screen.html` | 设备屏遥控反馈态模拟器 |
| `manifest.webmanifest` | PWA 清单 |
| `shot_ui.py` | Playwright 截图自查脚本 |

## 六、验收方法

```powershell
# 1) 打开 http://127.0.0.1:17867/ ，确认：
#   - 官方 3D 模型加载（浅色舞台、带阴影、头部居中）
#     ⚠️ 模型文件不入库 ⇒ 克隆后此处 3D 必然 404；
#        要看 3D 请自行从官方仓取 stack_chan_model.glb 放到 assets/ 根目录。
#   - 拖动摇杆 → 头跟随、读数变化、松手回中，拖动舞台同样生效
#   - 四档速度圆点切换生效
#   - 点 FAB → 聊天抽屉浮起，发消息能收到回复（需旧后端 17865 在跑）
#   - 状态条：旧后端在线时「已连接后台」；离线时「设备离线 · 演示模式」

# 2) 截图自查
py -3.12 prototype\mobile-v2\shot_ui.py   # 生成 shots/01-main.png… 05-reply.png
```

## 七、借鉴与复用来源（都有出处，不引入黑盒）

| 来源 | 复用了什么 | 出处 |
|---|---|---|
| 旧项目 17865 控制台 `gui_console.py` `motionControlView` | 官方原厂 GLB 3D 渲染（浅色舞台 / ACES / 阴影 / `setPose` 阻尼 / `_00_stackchan450_*` 轴绑定） | `D:\jss18\AI\StackChan\stackchan_ai\gui_console.py:5390-5760` |
| 旧项目 `mobile_app/remote_control.js` | 摇杆手势（死区 8% / 节流 100ms / 松手回中 / 舞台拖动 / 键盘） | `D:\jss18\AI\StackChan\mobile_app\remote_control.js` |
| 旧项目 `mobile_app/mobile_proxy.py` | 同源代理安全模型（CSRF / Origin 校验 / 白名单 / 超时分级） | `D:\jss18\AI\StackChan\mobile_app\mobile_proxy.py` |
| 旧项目 `mobile_app/chat.js` | 聊天交互（思考态 / 错误态 / 文本防注入 / 输入法防误发） | `D:\jss18\AI\StackChan\mobile_app\chat.js` |
| three.js 官方 | GLTFLoader / BufferGeometryUtils / 色调映射 / 阴影管线 | `vendor/three/*`（three@0.160.0） |
| 本仓库 DESIGN.md / iOS 原型 | 深色基调 + 琥珀强调色（tuck-dark-calm）、「唯一主角」原则 | `prototype/ios/`、`DESIGN.md` |

> ⚠️ `web-search` 工具本轮不可用（搜索 API key 401），检索全部走 **GitHub REST API + raw.githubusercontent.com**（本机网络直连，2026-10-30 实取）。

### 7.2 ⭐ 开源生态调研（2026-10-30 实取，全文见 [`docs/research/100`](../../docs/research/100-StackChan开源生态调研与可接入点.md)）

| 项目 | ★ | 拿到的 | 落地状态 |
|---|---|---|---|
| [`stack-chan/stack-chan`](https://github.com/stack-chan/stack-chan) `web/simulator/geometry.mjs` | 1832 | **官方真实几何**（脸 54×54×54mm / 圆角 4 / 脚 24×8×48×2 / CoreS3 54×54×16 / 前开口 51.6mm） | ✅ 已接入 `device-screen.html` |
| 同上 `web/local-peer/ble-local-peer.mjs`（555 行） | 1832 | **浏览器 BLE 直连协议**（Nordic UART UUID、`SLB1`/`SLP1` 分片、MTU 244/60/20 回退、FNV-1a 认证） | 📋 二期兜底通道（iOS Safari 不支持 Web Bluetooth，故不作主线） |
| [`zziying/stackchan-openapi`](https://github.com/zziying/stackchan-openapi) | 91 | **架构同构验证**：ESP32 只做硬件、AI/ML 全在主机，Wi-Fi HTTP 暴露 servo/face/camera/audio | ✅ 佐证「主机当 server」路线是社区验证过的 |
| [`BrettKinny/dotty-stackchan`](https://github.com/BrettKinny/dotty-stackchan) | 121 | 6 状态机（idle/talk/story/security/sleep/dance）+ 12 LED 环；**privacy sleep = 关传感器不关机**；回复首字符即表情编码 | 📋 状态机与降级通道待做 |
| [`uezo/AIAvatarStackChan`](https://github.com/uezo/AIAvatarStackChan) | 64 | 表情 + 自动眨眼 + **口型随语音同步（lip sync）** | 📋 与 `docs/research/88`「能量→嘴」通道互补 |
| [`kisaragi-mochi/stackchan-mcp`](https://github.com/kisaragi-mochi/stackchan-mcp) / [`migratorywhale/stackchan-mcp`](https://github.com/migratorywhale/stackchan-mcp) | 167 / 98 | **MCP 网关**：让 AI agent 直接驱动机器人（say / set_head / face） | 💡 新机会：给 `server/` 加 MCP 接口 ≈ 1 天 |

## 八、已知限制

- **3D 模型固定**：未做表情/表情包切换（仅头部姿态）；聊天回复只影响状态条与思考态，不驱动模型表情（后续可加）。
- **真机 Wi-Fi 联调**：需你在场改 IP 或重配网（见 §三），今晚未能实机验证。
- **代理白名单最小集**：只含手机端真正用到的 8 条路由，其余 `/gui/*` 未开放（安全边界）。
- **聊天音频**：纯文字，无 TTS 播报（D2 音频承载待拍板）。