# STATUS · mobile-v2 单屏遥控台（今夜交付）

> 更新：2026-10-30 05:00 · 会话：用户睡觉期间自主推进
> 结论：**新版手机 Web 遥控台已完整可用**（官方 3D 模型 + 摇杆 + 聊天 + 状态），
> 设备屏遥控反馈态模拟器已交付；真机 Wi-Fi 联调差一步需要你在场操作。

---

## 一、做了什么（一句话）

以你喜欢的 3D 模型（17865 控制台 motionControlView 的**官方原厂 GLB**）为视觉核心，
把手机端重做成**单屏遥控台**：`prototype/mobile-v2/`（与旧 `prototype/mobile/` 并存，不覆盖）。

## 二、交付清单（全部可运行）

| 文件 | 作用 | 状态 |
|---|---|---|
| `prototype/mobile-v2/index.html` | 单屏遥控台：状态条 + 3D 舞台 + 摇杆 + 速度档 + 聊天 FAB | ✅ |
| `prototype/mobile-v2/styles.css` | 深色 · 琥珀强调 · 弹性动效（对齐 iOS 原型 tuck-dark-calm） | ✅ |
| `prototype/mobile-v2/preview3d.js` | ⭐ 官方原厂 GLB 渲染（浅色舞台 · ACES 色调映射 · 带阴影 · 阻尼驱动） | ✅ |
| `prototype/mobile-v2/remote.js` | 摇杆 + 舞台拖动 + 四档速度 + 真机 head 下发（双轨） | ✅ |
| `prototype/mobile-v2/chat.js` | 聊天抽屉（收发 / 思考态 / 错误态 / 快捷提问） | ✅ |
| `prototype/mobile-v2/app.js` | 装配 + 状态轮询 + 模式切换 | ✅ |
| `prototype/mobile-v2/api.js` | 同源代理访问层 | ✅ |
| `prototype/mobile-v2/serve2.py` | 静态托管 + `/mobile-api/*` 白名单代理（安全边界） | ✅ |
| `prototype/mobile-v2/device-screen.html` | ⭐ 设备屏（320×240）遥控反馈态模拟器 | ✅ |
| `prototype/mobile-v2/README.md` | 完整说明 + 验收方法 | ✅ |
| `prototype/mobile-v2/manifest.webmanifest` | PWA 清单 | ✅ |
| `prototype/mobile-v2/shot_ui.py` | Playwright 截图自查脚本 | ✅ |

## 三、验证结果

| 项 | 结果 |
|---|---|
| 官方 3D 模型加载 | ✅ `原厂模型已加载：模型与实体 1:1 同步` |
| 摇杆拖动 → 3D 跟随 | ✅ 拖动后 yaw 102° / pitch 70°（截图 `shots/02-joystick.png`） |
| 聊天收发 | ✅ 「你好」→「你好呀，我在。」（截图 `shots/05-reply.png`） |
| 聊天抽屉开关 | ✅ aria-hidden false，正常浮起 |
| 设备屏模拟器拖动 | ✅ yaw 60° / pitch 3°，四角读数正常（截图 `shots/device-screen.png`） |
| 全部 console 报错 | ✅ **NO CONSOLE ERRORS** |
| 仓库门禁 | ✅ check_links / check_ci / check_repo_stats / check_docs 全绿（顺手修了 2 处文档门禁计数漂移 44→45） |

## 四、跑起来（明早你只需 3 步）

```powershell
# 1) 起旧后端 17865（提供 /gui/* 接口）
py -3.12 'D:\jss18\AI\StackChan\run_stackchan_backend.py'

# 2) 起 mobile-v2 同源服务（页面 + 代理同端口）
$env:STACKCHAN_MOBILE2_PORT='17867'
py -3.12 prototype\mobile-v2\serve2.py
```

打开：**`http://127.0.0.1:17867/`**（手机与电脑同 Wi-Fi 时，用电脑 IP 访问）

另外两个程序**当前也在跑**（如果你的电脑没重启）：17863 桥接 / 17865 后端 / 17867 mobile-v2。

## 五、⭐ 真机 Wi-Fi 联调——只差你一步

**现状**：真机（ESP32）通过 USB 串口（COM3）**在线**（uptime≈40h 心跳正常），
但固件里**写死了服务器地址 `10.21.17.208:17863`**（旧局域网地址），而本机当前 WLAN IP 是
`10.21.184.118`，所以设备连不上后端（串口日志持续 `Failed to connect to 10.21.17.208:17863`）。

**明天二选一（需你在场）**：
1. **改电脑 IP**（最简单）：把 WLAN 的 IPv4 改成 `10.21.17.208`（子网掩码 255.255.0.0），
   然后确认 17863 桥接在跑（已写成脚本 `D:\jss18\AI\StackChan\scripts\stackchan_port_bridge.py`，17863→17865）。
   改完等 1 分钟，设备重试就会连上，状态条变绿「在线」。
2. **重配设备 Wi-Fi**：用 17865 控制台的「网络设置」页（或官方配网）把设备指向当前电脑 IP，
   并对齐端口 17863（桥接）或改固件端口。

连上后：摇杆 → 3D 模型 + 真机头部同步转，「演示/真机」芯片自动切换，聊天照常。

> 我试过 `New-NetIPAddress` 加辅助 IP，但**非管理员被拒**（WinError 5），所以这一步必须你来做。

## 六、设计决策留痕（为什么这么做）

| 决策 | 理由 |
|---|---|
| 保留官方 GLB 3D 而非旧 mobile_app 的简化模型 | 你明确说「17865 那个 3D 模型我喜欢，其他不行」，旧 mobile 是深色布景+抽象模型，观感差 |
| 单屏（无 Tab）+ 聊天放抽屉 | 摇杆遥控是主交互，聊天是低频；同一屏共存会互相干扰（键盘/手势冲突） |
| 摇杆死区 8%、四档速度、±128/3–87 | 与 17865 控制台 / 旧 mobile 数值完全一致（真机机械范围），不重新发明 |
| 深色 #121316 + 琥珀 #E3A857 | 对齐仓库 iOS 原型 tuck-dark-calm 深色系 + 琥珀强调（且 17865 控制台也是深色配琥珀） |
| 同源代理（页面与 /mobile-api 同端口） | 避免混合内容问题；浏览器永远不碰后端地址；白名单最小集只留 8 条手机端真正用的路由 |
| 设备屏只做「遥控反馈态」不做菜单 | 你拍板「设备屏第一版只做遥控反馈态」；固件屏 95% 是脸，遥控时显眼睛跟随+角度读数即可 |

## 七、已知限制（诚实清单）

- **真机 Wi-Fi 未实连**：卡在固件写死旧 IP（见 §五），程序侧全部就绪。
- **3D 模型固定**：未做表情包切换 / LED 色 / 表情驱动（只是头部姿态），聊天不驱动表情。
- **聊天纯文字**：无 TTS 播报（音频承载 D2 待拍板）。
- **未做移动端真机手势实测**：用的是 Playwright 桌面模拟 390×844 视口，真机触摸手感需你上手试。

## 八、明早你来了之后

1. 先按 §四 打开页面看效果（仓内定性截图见 [`assets/screenshots/mobile/`](assets/screenshots/mobile/)；Playwright 自查截图是**本地生成物**，被 `.gitignore` 排除，克隆后不存在）；
2. 按 §五 处理真机联调（改 IP 或配网），我这边桥接+后端+mobile-v2 都还开着；
3. 不满意的地方直接指出来（颜色 / 布局 / 摇杆大小 / 速度档），我照着改。