# 62 BLE 直连通道与真机驱动

## 一、结论先行

1. **BLE 直连在协议层完全可行**：Motion / Avatar / RGB 三个特征的 UUID、特征属性、JSON 字段语义，已从 1.5.1 与 1.6.0 两份源码逐一核对，**1.5.1 与 1.6.0 在这三条通道上字节级相同**（差异只在 Wi-Fi 配网通道）。
2. **但真机当前不广播**：实测 `tools/stackchan_ble.py scan` 三次（8 s / 15 s / 25 s），环境内 44~50 个 BLE 设备中**没有任何 StackChan**（无 `StackChan` 名字、无 `e2e5e5e0…`/`e2e5e5ff…` service UUID、无 `E5 02 <MAC>` manufacturer data）。直接连 `68:ee:8f:d7:36:68` 报 `BleakDeviceNotFoundError`。
3. **根因已定位到源码级**：BLE 外设**只在 DANCE 应用打开时才启动**（`app_dance/app_dance.cpp:48` → `GetHAL().startBleServer()`）。设备当前停在 Launcher 的「Welcome! Let's get started.」开机页（`app_launcher/app_launcher.cpp:32-34`，因为 NVS `app_config/is_configed` 为 false），所以 BLE 压根没起来。
4. **已交付 `tools/stackchan_ble.py`**：scan / connect / send_motion / send_avatar / send_rgb / play_keyframes / set_wifi 全部实现，载荷构造按固件真实格式，离线自检 22/22 通过。
5. **只差一个物理动作**：在设备屏幕上点 **Skip** → 在启动器里点 **DANCE** 图标，BLE 立即起来，工具可直接跑 `demo` / `play`。详见第八节。

---

## 二、BLE 通道事实表

### 2.1 服务与特征

服务 UUID 二选一，由 `ble_prph_init(use_alt_uuid)` 决定：

| 服务 UUID | 何时启用 | 源码位置 |
| --- | --- | --- |
| e2e5e5e0-1234-5678-1234-56789abcdef0 | `Hal::startBleServer()` → `ble_init(false)`，DANCE 应用 | hal_ble.cpp:328-332 |
| e2e5e5ff-1234-5678-1234-56789abcdef0 | `Hal::startAppConfigServer()` → `ble_init(true)`，配网流程 | hal_ble.cpp:599-608 |

特征 UUID 定义在 firmware/main/hal/utils/bleprph/bleprph.h:43-65。

| 通道 | UUID | 特征属性 | 固件写入回调 | 固件 JSON 解析位置 |
| --- | --- | --- | --- | --- |
| Motion | e2e5e5e1-1234-5678-1234-56789abcdef0 | READ \| WRITE \| NOTIFY | hal_ble.cpp:237-251 | stackchan/json/json_helper.cpp:117-139 |
| Avatar | e2e5e5e2-1234-5678-1234-56789abcdef0 | READ \| WRITE \| NOTIFY | hal_ble.cpp:253-267 | stackchan/json/json_helper.cpp:41-68 |
| Config | e2e5e5e3-1234-5678-1234-56789abcdef0 | READ \| WRITE \| NOTIFY | hal_ble.cpp:269-283 | hal_ble.cpp:458-476 |
| RGB | e2e5e5e4-1234-5678-1234-56789abcdef0 | READ \| WRITE \| NOTIFY | hal_ble.cpp:285-299 | stackchan/json/json_helper.cpp:236-262 |
| Battery | 0x2A19 | READ \| NOTIFY | 不适用 | 固定返回 96（hal_ble.cpp:301-305） |

特征属性来源：firmware/main/hal/utils/bleprph/gatt_svr.c:91 / 98 / 105 / 112 / 128。
四个特征都**没有** `WRITE_NO_RSP`，写入必须走「写请求 + 写响应」往返。

### 2.2 各通道 JSON 格式（固件真实解析结果）

Motion（json_helper.cpp:117-139 `motion::update_from_json`）：

```json
{"type":"bleMotion","pitchServo":{"angle":450,"speed":500},"yawServo":{"angle":-300,"speed":500}}
```

- 顶层 `type` 由 App 写死为 `bleMotion`（app/lib/model/expression_data.dart:87），**固件不读 `type`**，只认 `yawServo` / `pitchServo` 两个对象（json_helper.cpp:130-138）。
- `update_servo`（json_helper.cpp:74-115）解析优先级：
  1. 有 `rotate` → `servo.rotate(rotate)`，直接返回；
  2. 有 `angle` 且有 `speed` → `servo.moveWithSpeed(angle, speed)`；
  3. 有 `angle` 且有 `spring` 对象 → `servo.moveWithSpringParams(angle, stiffness, damping)`，stiffness 默认 170.0、damping 默认 26.0；
  4. 其它 → `servo.move(angle)`（默认弹簧参数）。
- `angle` 单位 0.1 度。App 侧 `MotionDataItem.toJson()` 有个坑：`angle==0 && rotate!=0` 时输出 `{"rotate":..,"speed":..}` 而不是 `angle`（expression_data.dart:128-136）。

Avatar（json_helper.cpp:41-68 `avatar::update_from_json`）：

```json
{"type":"bleAvatar","leftEye":{"x":0,"y":0,"rotation":0,"weight":100,"size":100},"rightEye":{},"mouth":{}}
```

- 固件只认 `leftEye` / `rightEye` / `mouth` 三个对象（json_helper.cpp:54-67），不读 `type`。
- 每个元素的字段：`x`、`y`、`rotation`、`weight`、`size`，全部是 int，缺省就不改该属性（json_helper.cpp:16-39）。
- `x` / `y` 必须**同时**是 int 才 `setPosition`（json_helper.cpp:18）。
- `weight` 语义：**越大越睁开**（0 = 全闭，100 = 全开）。

RGB（json_helper.cpp:236-262 `addon::update_neon_light_from_json`）：

```json
{"leftRgbColor":"#FF0000","leftRgbDuration":0.3,"rightRgbColor":"#00FF00","rightRgbDuration":0.3}
```

- 固件只认 `leftRgbDuration` / `leftRgbColor` / `rightRgbDuration` / `rightRgbColor`。
- duration 判的是 `is<float>()`（json_helper.cpp:249 / 256），所以 duration 必须是**浮点**；写成整数 JSON 数字有被忽略的风险。App 侧默认 `0.0`（expression_data.dart:141/143）。
- RGB 的 JSON **没有 `type` 字段**（App 的 `RgbData.toJson()` 就不写 type，expression_data.dart:160-167）。
- `leftRgbColor` 判的是 `is<std::string>()`，`#RRGGBB` 形式。

Config（hal_ble.cpp:458-476 `process_config_data`）：

```json
{"cmd":"setWifi","data":{"ssid":"xxx","password":"yyy"}}
```

- `cmd` 取值：`setWifi` / `getWifiStatus` / `handshake`（hal_ble.cpp:468-475）。
- `setWifi` 的 `data` 必须含 `ssid` 与 `password` 两个字符串，否则回失败（1.6.0：hal_ble.cpp:500-505；1.5.1 同逻辑但错误串不同）。
- 设备用 `cmd:"notifyState"` 回报，格式 `{"cmd":"notifyState","data":{"type":N,"state":"..."}}`（hal_ble.cpp:541-568）。

### 2.3 广播内容

| 项 | 值 | 位置 |
| --- | --- | --- |
| 设备名 | `StackChan`（放在**扫描响应**包，不在广播包） | bleprph.c:698、bleprph.c:282-287 |
| 广播包 service UUID | 1 个 128 位 UUID：非 alt 模式 e2e5e5e0…，alt 模式 e2e5e5ff… | bleprph.c:261-272 |
| 扫描响应 manufacturer data | 8 字节 `E5 02 <MAC[6]>` | bleprph.c:242-247、bleprph.c:294-295 |
| 广播可连接性 | `BLE_GAP_CONN_MODE_UND`（不可重连广播） | bleprph.c:305 |

=> 扫描时可以靠 manufacturer data 里的 `E5 02` 前缀 + 后 6 字节 MAC 精确识别设备。

### 2.4 运行时门控（本次最关键的发现）

BLE 收到的 motion / avatar / rgb **只有 DANCE 应用在前台时才会被消费**：

- `AppDance::onOpen()` 才调用 `GetHAL().startBleServer()`（app_dance/app_dance.cpp:48）——**DANCE 应用不打开，BLE 外设根本不启动，设备不会广播**。
- 消费点在 `AppDance::onRunning()`（app_dance/app_dance.cpp:99-116）：`updateAvatarFromJson` / `updateMotionFromJson` / `updateNeonLightFromJson`。
- Avatar 应用里 BLE 相关代码被注释掉了（app_avatar/app_avatar.cpp:79 `// GetHAL().startBleServer();`），它仍然连了 `onBleAvatarData` / `onBleMotionData`（app_avatar/app_avatar.cpp:93-109），消费在 app_avatar/app_avatar.cpp:237-244——但外设没启动，收不到东西。
- 另一条会启动 BLE 的路径是配网：`AppSetup` 的 `WifiSetupWorker` 在 `State::WaitAppConnection` 调 `GetHAL().startAppConfigServer()`（app_setup/workers/connectivity.cpp:142-150），用的是**配网用**的 alt UUID 与 config 特征，**不带** motion/avatar/rgb 消费逻辑。

固件对 BLE 数据还有一道「丢帧」保护：`AppDance` 用 `update_flag` 守卫，上一帧没被消费掉时新写入**直接丢弃**（app_dance/app_dance.cpp:99-116）。⇒ 主机侧发帧不能无脑连发，必须按 `durationMs` 节流。

### 2.5 载荷长度与分包

| 项 | 值 | 位置 |
| --- | --- | --- |
| 单条 JSON 最大长度 | 2048 字节（`STACKCHAN_MAX_JSON_LEN`） | bleprph.h:68 |
| GATT 写入实际截断 | `gatt_svr_write(ctxt->om, 0, STACKCHAN_MAX_JSON_LEN, ...)` | gatt_svr.c:199 / 212 / 225 / 237 |
| 分包魔数 | `AA 55 C3 01` + idx(2) + total(2) + total_len(2) | hal_ble.cpp:18-22、hal_ble.cpp:68-86 |
| 分包头长度 | 10 字节 | hal_ble.cpp:22 |

固件对**写入方向**同样支持分包：`BleFragmentAssembler` 先看魔数，不匹配就当整包 JSON 处理（hal_ble.cpp:101-106、185-194）。
motion / avatar / rgb 的 JSON 实际只有 100~250 字节，正常不会触发分包。

---

## 三、1.5.1 与 1.6.0 的差异

对比基准：`94856a7^` = **PROJECT_VER 1.5.1**（`git show 94856a7^:firmware/CMakeLists.txt`），`origin/main` = **1.6.0**。
真机启动日志确认固件版本就是 1.5.1（见第五节）。

`git diff 94856a7^ origin/main` 在 BLE 相关路径上**只有两个文件变化**：

| 文件 | 变化 | 对我们的影响 |
| --- | --- | --- |
| firmware/main/hal/hal_ble.cpp | 122 行，全在 `WifiConfigServer`（配网）内部 | 无影响 |
| firmware/main/hal/utils/bleprph/gatt_svr.c | 1 行日志：不再打印 config 载荷原文 | 无影响 |
| firmware/main/apps/app_dance/ | **无变化** | 无影响 |
| firmware/main/stackchan/json/ | **无变化** | 无影响 |
| firmware/main/hal/utils/bleprph/bleprph.c / .h | **无变化** | 无影响 |

结论：**Motion / Avatar / RGB 三条通道的 UUID、特征属性、JSON 格式、分包协议、运行时门控，在 1.5.1 与 1.6.0 上完全一致**。本文第二节的所有 file:line 对 1.5.1 真机同样成立（`app_dance.cpp` 与 `json_helper.cpp` 两版逐字节相同；`hal_ble.cpp` 的四个写入回调行号 237/249、253/265、269/281、285/297 在两版也一致，只有 `process_config_data` 458→425、`startAppConfigServer` 599→543 位移）。

配网通道的具体差异（仅供参考，我们默认不碰）：

| 项 | 1.5.1 | 1.6.0 |
| --- | --- | --- |
| setWifi 失败回执 | `notify_state(2,"wifiConnectFailed")` | `notify_state(2,"wifiConnectFailed", &failure, ssid)`，多带 errorCode/errorMessage/reason/sdkError/ssid（hal_ble.cpp:536-568） |
| 忙碌时回执 | `"wifiConnectFailed: Busy"` | `"wifiConnectFailed"` + errorCode=`busy` |
| ssid/password 缺失 | `wifiConnectFailed` | `wifiConnectFailed` + errorCode=`invalid_configuration` |
| 额外字段 | 不支持 | 支持 `frequency` / `currentNetwork` 提示 5 GHz |
| config 日志 | 打印载荷原文（含明文口令） | 不再打印原文 |

---

## 四、我们的实现

文件：`tools/stackchan_ble.py`（Python 3.12，唯一第三方依赖 `bleak`，UTF-8 / LF）。

### 4.1 API

| API | 说明 |
| --- | --- |
| `scan(timeout=5.0)` | 扫描并列出所有设备：名字、地址、RSSI、广播的 service UUID、manufacturer data、service data、TX power，按 RSSI 排序 |
| `find_device(timeout=10.0)` | 自动找出 StackChan：按设备名 `StackChan`、service UUID、manufacturer data 前缀 `E5 02` 三重匹配；找不到返回 `None` |
| `connect(address)` | 连接后列出所有 service/characteristic 及其属性（read / write / notify / indicate），返回清单字典 |
| `send_motion(yaw_deg, pitch_deg, speed=500)` | 写 motion 特征；入参是**度**，内部换算成固件的 0.1 度并按 yaw ±1280、pitch 30~870 限位 |
| `send_avatar(left_eye, right_eye, mouth)` | 写 avatar 特征；三个 dict，各含 x, y, rotation, weight, size |
| `send_rgb(left_hex, right_hex, duration=0.3)` | 写 rgb 特征；duration 强制 float |
| `play_keyframes(keyframes_json_path, fps=25)` | 核心：读 `prosody_to_motion.py` 产出的关键帧数组，按 `durationMs` 逐帧写 motion/avatar/rgb |
| `set_wifi(ssid, password)` | 写 config 特征；**默认不执行**，只有显式调用或 `wifi` 子命令才会写 |
| `disconnect()` | 断开连接 |

### 4.2 载荷构造规则（全部带固件 file:line 注释）

- Motion：`{"type":"bleMotion","pitchServo":{"angle":N,"speed":N},"yawServo":{"angle":N,"speed":N}}`，**绝不**发 `rotate`（否则固件走 rotate 分支，json_helper.cpp:77-81）。
- Avatar：`{"type":"bleAvatar","leftEye":{x,y,rotation,weight,size},...}`，字段全部转 int（x/y 必须同时是 int 才生效，json_helper.cpp:18）。
- RGB：`{"leftRgbColor","leftRgbDuration","rightRgbColor","rightRgbDuration"}`，无 `type`，duration 用 float（json_helper.cpp:249/256）。
- Config：`{"cmd":"setWifi","data":{"ssid","password"}}`（hal_ble.cpp:468-475）。

### 4.3 关键帧播放语义

`play_keyframes` 做的事就是把 `0x14` 的「一整段数组」拆成逐帧下发：

1. 一帧 = motion + avatar + rgb 三次写，顺序与 App 一致（app/lib/util/blue_util.dart:950-983）。
2. 每次写都等响应（特征无 `WRITE_NO_RSP`，gatt_svr.c:91/98/105/112）。
3. 帧间 sleep `durationMs / 1000`，且不小于 12 ms，避免撞上固件 `update_flag` 丢帧保护（app_dance/app_dance.cpp:99-116）。
4. `durationMs` 缺失时用 `1000 / fps` 兜底。

### 4.4 命令行

```text
py -3.12 tools/stackchan_ble.py scan [--timeout 10]
py -3.12 tools/stackchan_ble.py connect [address]
py -3.12 tools/stackchan_ble.py demo [address]
py -3.12 tools/stackchan_ble.py play [--address <addr>] <keyframes.json> [--fps 25]
py -3.12 tools/stackchan_ble.py wifi [--address <addr>] <ssid> <password>
py -3.12 tools/stackchan_ble.py selftest
```

`address` 可以省略：省略时自动扫描并按 StackChan 特征匹配；扫不到会直接打印「请去设备上点 DANCE」并以退出码 3 结束。
`play` / `wifi` 的地址用 `--address` 选项而不是位置参数，避免和「关键帧文件」「SSID」抢位置（实测踩过：位置参数会被先吃掉）。

`demo` 发一组固定动作：左转 25° → 右转 25° → 回中并抬头 → 闭眼 → 睁眼 → 左红右蓝，每步间隔 1~2 s。

### 4.5 离线自检

`py -3.12 tools/stackchan_ble.py selftest`：**22 项全部 PASS**（顶层字段集合、`type` 取值、0.1 度换算、无 `rotate`、限位钳位、avatar 3 元素 × 5 字段且全 int、weight 语义、rgb 无 `type` 且 duration 为 float、config cmd/data、关键帧到三通道的映射、载荷 ≤ 2048 B）。

自检中发现并修掉一个真实缺陷：Windows 控制台默认 GBK，设备名含 `U+207A`（`iKF-King Pro⁺ APP`）时 `print` 抛 `UnicodeEncodeError`，扫描直接崩。已在模块导入处把 stdout/stderr 改为 UTF-8 + `errors="replace"`。

---

## 五、真机实测记录

### 5.1 设备身份（COM3 启动日志，115200 8N1）

用 DTR/RTS 对 COM3 复位（`rst:0x15 (USB_UART_CHIP_RESET)`），抓到完整启动日志：

```text
ESP-ROM:esp32s3-20210327
rst:0x15 (USB_UART_CHIP_RESET),boot:0x2a (SPI_FAST_FLASH_BOOT)
I (24) boot: ESP-IDF v5.5.4 2nd stage bootloader
I (703) app_init: Project name:     stack-chan
I (711) app_init: App version:      1.5.1
I (715) app_init: Compile time:     Oct 11 2026 12:16:28
I (720) app_init: ELF file SHA256:  2c9acb2da...
I (831) Board: UUID=0572eadc-1f88-4c71-9c08-ce9c7d02e040 SKU=m5stack-stack-chan
I (841) M5Stack-StackChan-Board: Init power save timer: sleep=300 s, shutdown=600 s, allow_shutdown_when_charging=0
[1792837825434] [info] [Launcher] on create
[1792837825436] [info] [Launcher] on open
[1792837825440] [info] [Launcher] app not configured, start startup worker
[1792837825453] [info] [AI.AGENT] on create
[1792837825453] [info] [AVATAR] on create
[1792837825457] [info] [ESPNOW.REMOTE] on create
[1792837825462] [info] [APP.CENTER] on create
[1792837825467] [info] [EZDATA] on create
[1792837825472] [info] [DANCE] on create
[1792837825476] [info] [SETUP] on create
```

要点：

- 固件版本 **1.5.1**，UUID `0572eadc-1f88-4c71-9c08-ce9c7d02e040`，SKU `m5stack-stack-chan`——与任务书给的完全一致。
- 休眠 300 s / 关机 600 s 确认。
- **启动全程没有 `HAL-BLE init` / `start ble server`**，即 BLE 外设未启动。
- `[Launcher] app not configured, start startup worker`：NVS `app_config/is_configed` = false，设备停在开机欢迎页（`app_setup/workers/startup.cpp:17-50`，画面 "Welcome! Let's get started." + Skip / Start 两个按钮）。
- assets 分区是空的：`[Assets] get image asset icon_dance.bin failed: not found`（图标缺失不影响应用启动）。

### 5.2 BLE 扫描（三次，均未发现设备）

```text
$ py -3.12 tools/stackchan_ble.py scan --timeout 25
...
共 44 个设备
★ 未发现 StackChan 广播（设备未开 BLE 外设时就是这样，见文档第 2.4 节）
```

前两次扫描（临时脚本 `r62_scan.py`）分别 8 s / 15 s，命中 50 个设备，逐条检查：

- 无一个设备名是 `StackChan`；
- 无一个设备广播 `e2e5e5e0-1234-5678-1234-56789abcdef0`；
- 无一个设备广播 `e2e5e5ff-1234-5678-1234-56789abcdef0`；
- 无一个设备的 manufacturer data 以 `E5 02` 开头。

扫描到的都是环境里的其它设备（`XN-xxxxxxx` 音箱、`iKF-*` 门锁、`0000ff12` / `0000fdaa` / `0000fcc0` 等标准服务）。

### 5.3 直连尝试

```text
$ py -3.12 tools/stackchan_ble.py connect 68:ee:8f:d7:36:68
  File "...\bleak\backends\winrt\client.py", line 225, in connect
    raise BleakDeviceNotFoundError(
bleak.exc.BleakDeviceNotFoundError: Device with address 68:ee:8f:d7:36:68 was not found.
```

同一次尝试期间 COM3 串口日志（40 s 采样）：

```text
I (610791) SystemInfo: free sram: 176195 minimal sram: 175163
I (620791) SystemInfo: free sram: 176195 minimal sram: 175163
I (630791) SystemInfo: free sram: 176195 minimal sram: 175163
I (640791) SystemInfo: free sram: 176195 minimal sram: 175163
```

=> 设备活着、没休眠，但没有任何 BLE 活动（没有 `NimBLE_BLE_PRPH` 日志、没有 `BLE Host Task Started`）。

### 5.4 自动发现路径（省略地址）

```text
$ py -3.12 tools/stackchan_ble.py demo
未指定地址，正在自动扫描 StackChan ...
未发现 StackChan 广播。
原因：固件只在 DANCE 应用打开时才启动 BLE 外设（app_dance/app_dance.cpp:48）。
请在设备屏幕上点 Skip 进入启动器，再点 DANCE 图标，然后重跑本命令。
（退出码 3）
```

工具自身已把「为什么扫不到、该做什么」写进报错文本，不需要再查文档。

### 5.5 未能取得的实测项

- **特征清单（读到的 service/characteristic 及属性）**：未取得。设备不广播，无法连接。
- **真机可见动作（转头 / 闭眼睁眼 / RGB 变色）**：未取得。原因同上是 DANCE 应用未打开。
- **串口佐证设备收到指令**：未取得（没有写入发生，故无 `Stack-Chan characteristic write` 日志；该日志在 gatt_svr.c:195 打印）。

### 5.6 已取得的实测项

- 设备身份、固件版本、UUID、休眠策略、启动应用顺序、设备当前所处应用、NVS 配置状态：**全部已取得**（5.1）。
- BLE 不广播的事实与根因：**已取得**（5.2 / 5.3 + 2.4）。
- 工具本身的扫描链路：能正常驱动 Windows BLE 栈、正确解析 44~50 个设备的完整广播字段：**已取得**。

---

## 六、与 0x14 云通道的对比

| 维度 | 0x14 云通道（WebSocket / LAN） | BLE 直连 |
| --- | --- | --- |
| 传输 | WebSocket（hal_ws_avatar.cpp）或局域网（local_network_protocol.h:18） | BLE GATT write |
| 前提 | 需要 Wi-Fi + 服务器在线 | **不需要 Wi-Fi、不需要服务器**，只需要 DANCE 应用在前台 |
| 载荷形态 | 一整段关键帧数组，设备端 `parse_sequence_from_json` 自己排时间轴（json_helper.cpp:178-230） | **没有时间轴**，必须主机逐帧下发 |
| 单帧上限 | WS 256 KB（hal_ws_avatar.cpp:146）；LAN 65535 B | 单条 JSON 2048 B（bleprph.h:68），超长走 `AA 55 C3 01` 分包 |
| 每帧网络开销 | 1 次（整段一次推完） | 3 次 ATT 写往返（motion + avatar + rgb），每条特征都是 write-with-response |
| 时序精度 | 设备端 Timeline 逐帧 apply（animation.cpp:70-100） | 主机端 sleep 节流，受 BLE 连接间隔与 ATT 往返影响，抖动更大 |
| 脸部插值 | 硬切，无插值（animation.cpp:12-34） | 同样硬切（每帧一次 avatar 写） |
| 舵机动力学 | 弹簧低通，speed → 刚度/阻尼，落点比脸部滞后数百毫秒 | 同左（同走 `moveWithSpeed`） |
| 舵机卸力 | 静止 200 ms 自动释放扭矩（servo.cpp:58-64） | 同左 |
| 表情寿命 | 关键帧里带 `durationMs`，设备自己保持 | 设备不记时，**主机不发下一帧就一直保持最后一次表情** |
| 灯效寿命 | 同上 | 同上（duration 由主机给，固件只认 `leftRgbDuration` 等字段） |
| 丢帧保护 | 无 | 有：固件 `update_flag` 守卫会丢掉上一帧未消费时的新写入（app_dance/app_dance.cpp:99-116） |
| 断线后果 | 服务器可达性 | BLE 断开后设备保持最后姿态，且 DANCE 应用退出后 BLE 直接关闭 |
| 适合场景 | 长音频、连续韵律、需要精确排程 | 离线、无网、单次或短片段动作、机器人本体自带控制端 |

一句话：**0x14 是「把整段戏法一次交给设备自己演」，BLE 是「主机一帧一帧地现场指挥」。** 韵律→身体的编译器产物在 BLE 通道上照样能用，但要主机承担排程与丢帧兜底。

---

## 七、未取得项

1. **BLE 特征清单（真机实读）**：未取得——设备未广播。
2. **真机可见动作（转头 / 眨眼 / 变色）**：未取得——同上，且 DANCE 应用未打开时固件根本没有消费 BLE 数据的代码路径在跑。
3. **串口佐证「设备收到指令」**：未取得——无写入事件。
4. **1.5.1 真机上的 `notifyState` 回执内容**：未取得（要连上 config 特征才行）。
5. **BLE 实测 MTU**：未取得。
6. **BLE 实测连接间隔 / 每帧往返耗时**：未取得。
7. **DANCE 应用在 1.5.1 上的实际界面与图标位置**：未取得（只从源码推出启动器图标条里有一个名为 "DANCE" 的条目，app_dance.cpp:20）。

---

## 八、后续动作建议

### 8.1 立刻可做（只差一次物理点击）

设备现在停在开机欢迎页，按下面两步就能让 BLE 起来：

1. 点屏幕左下角 **Skip** 按钮（坐标约为屏幕 (88, 187)，startup.cpp:26-34）→ 进入启动器图标条。
2. 在图标条上滑到 **DANCE** 图标并点它 → DANCE 应用打开，BLE 外设启动（app_dance/app_dance.cpp:48）。

然后一条命令就能拿到全部证据（地址可省略，工具会自动扫描识别）：

```text
py -3.12 tools/stackchan_ble.py demo
```

（转头 ±25°、闭眼、睁眼、左红右蓝，各步间隔 1~2 s，窗口里能直接看见动作。）

真机跑关键帧：

```text
py -3.12 tools\prosody_to_motion.py --wav voice.wav --out kf.json
py -3.12 tools\stackchan_ble.py play kf.json
```

串口佐证同时开一个窗口：

```text
py -3.12 -c "import serial,time;s=serial.Serial('COM3',115200,timeout=1);[print(s.read(s.in_waiting or 1).decode('utf-8','replace'),end='') for _ in iter(int,1)]"
```

预期能看到 `Stack-Chan characteristic write; conn_handle=1 attr_handle=N`（gatt_svr.c:195）。

### 8.2 工具侧待补（不影响本轮结论）

1. `play_keyframes` 增加「发完最后一帧后补发一帧静止姿态」，避免舵机因 200 ms 无动作被卸力（servo.cpp:58-64）。
2. 增加 `--no-rgb` / `--no-avatar` 开关，减少每帧 3 次 ATT 往返，压低 BLE 占用。
3. 增加断线自动重连（当前连接断开后 `write_gatt_char` 会直接抛异常）。

### 8.3 产品侧建议

1. **把 DANCE 应用做成「一进 BLE 模式」**：固件侧可考虑在 AppLauncher 也常驻 `startBleServer()`，让 BLE 不再依赖某个应用被打开。
2. **给 BLE 通道补一个「整段关键帧」写入方式**：固件已支持 `AA 55 C3 01` 分包（hal_ble.cpp:97-220），可以在其上再加一个 `cmd:"danceSequence"` 的自研载荷，把整段数组一次性推给设备，避开逐帧往返与丢帧问题。**这是把 BLE 做到和 0x14 同等能力的最小改动**。
3. **表情寿命**：BLE 下设备不记时，主机必须持续保活，否则设备停在最后一帧。

---

## 附录：本文引用的源码位置

| 文件 | 关键位置 |
| --- | --- |
| firmware/main/hal/hal_ble.cpp | 237-251 motion 写入回调；253-267 avatar；269-283 config；285-299 rgb；301-305 battery；307-326 ble_init；328-332 startBleServer；458-476 config 解析；541-568 notifyState；599-608 startAppConfigServer |
| firmware/main/hal/utils/bleprph/bleprph.h | 43-65 服务与特征 UUID；68 STACKCHAN_MAX_JSON_LEN |
| firmware/main/hal/utils/bleprph/bleprph.c | 229-313 bleprph_advertise；242-247 mfg data；282-287 扫描响应名字；305 conn_mode；698 设备名 |
| firmware/main/hal/utils/bleprph/gatt_svr.c | 36-45 UUID 实例；81-117 特征表；91/98/105/112/128 特征属性；164-240 access_cb（195 写日志） |
| firmware/main/stackchan/json/json_helper.cpp | 16-39 update_feature；41-68 avatar 解析；74-115 update_servo；117-139 motion 解析；178-230 0x14 序列解析；236-262 rgb 解析 |
| firmware/main/stackchan/stackchan.h | 152-179 三个 update_*FromJson 分发 |
| firmware/main/apps/app_dance/app_dance.cpp | 48 startBleServer；61-86 BLE 信号订阅；93-122 onRunning 消费；140 requestWarmReboot(5) |
| firmware/main/apps/app_avatar/app_avatar.cpp | 79 startBleServer 被注释；93-109 信号订阅；237-244 消费；288 requestWarmReboot(1) |
| firmware/main/apps/app_launcher/app_launcher.cpp | 23-38 onLauncherOpen（未配置 → StartupWorker）；77-80 onAppClicked → openApp |
| firmware/main/apps/app_setup/workers/startup.cpp | 17-50 欢迎页与 Skip / Start 按钮坐标 |
| firmware/main/apps/app_setup/workers/connectivity.cpp | 142-150 配网 BLE（alt UUID）启动点 |
| firmware/main/hal/hal.cpp | 325-345 warm reboot（NVS `warm_boot/app_index`） |
| app/lib/model/expression_data.dart | 33-38 avatar toJson；72-78 元素字段；87-107 motion toJson；128-136 rotate 坑；139-173 rgb toJson |
| app/lib/util/blue_util.dart | 114-121 特征 UUID；950-983 sendDanceData 拆三次写；985-1083 _sendData（分包与长写） |
