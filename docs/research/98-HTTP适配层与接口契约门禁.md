# 98 · HTTP 适配层 + 接口契约门禁：让「手机端 ↔ 本仓后端」自己闭环

> **一句话结论**：本仓 `server/` 原本**只有 WebSocket 协议栈、没有 HTTP 面**，
> 和手机端**零交汇点** ⇒ 作品集不能独立运行（这就是 **Q27**）。
> 这轮补上 `/gui/*` HTTP 适配层，并做出一台 **8 判据 + 10 项变异自检**的
> **契约门禁** —— 门禁当场抓到 **6 个真 bug**（字段名对不上、设备参数键名错、
> 屏幕程序只有 3 个、记忆分类缺失、SW 注册 URL 版本落后……），
> 其中前三个会让**手机端静默显示错内容**（不报任何错）。

- **日期**：2026-10-30
- **性质**：工程落地 + 规格机器化（不是调研档案）
- **新增门禁**：`tools/check_mobile_contract.py`（**第 46 / 47 项**）
- **新增真源**：`server/mobile_contract.py`（手机端可见的响应契约，**唯一真源**）
- **Q27**：本轮给出了 **③ → ①** 的**可执行第一步**（最小集已落地），但**合并本身仍待拍板**

---

## 一、起因：一次「端到端 400」的追查

上一轮把手机端搬进作品集仓后，本仓后端（`server/http_api.py`）已经能起，
手机端代理也能把 `/mobile-api/*` 转出去 ⇒ 但**对话这条路走不通**。

### 1.1 一处公开订正

上一轮的交接记录把病因写成了「**载荷字段名不匹配**」：
「代理 `_expect_fields(payload, {"message"}, …)` 取 `payload["message"]`，
而 `handle_chat` 只认 `body["text"]` ⇒ 400」。

**实测结论：这句话是错的。**

* `handle_chat` 当时**已经**同时认 `body["text"]` 和 `body["message"]`；
* 代理转发给上游的载荷是 `_validate_chat()` 的返回值 `{"message": …}`；
* 两边**字段名本来就对得上** ⇒ 直连本仓后端 `POST /gui/mobile-chat {"message":"你好"}`
  实测 **200**（`{"reply":"「你好」—— 嗯，我听着呢，你继续说。", "keyframes":79, "audio_samples":50271}`）。

⇒ 真正的病因在**响应侧**，不在请求侧（见 §三 B-1）。

> 这条订正留在档里，是因为「把猜测当结论写进交接记录」正是本仓库反复出现过的失败形态。

### 1.2 真正的断点在哪

手机端 `prototype/mobile/chat.js:60` 读的是 **`payload.say`**：

```js
function cleanReply(payload) {
  const reply = typeof payload?.say === "string" ? payload.say.trim() : "";
  if (!reply) throw new Error("小栈这次没有返回内容，请再试一次。");
  return reply;
}
```

而本仓后端返回的是 **`reply`** ⇒ 代理净化层（只放行 `say/emotion/face/motion/route/model/latency_ms`）
把 `reply` 丢掉 ⇒ 手机端拿到 `{"emotion":"Happy"}` ⇒ **页面显示「小栈这次没有返回内容」**。

⚠️ **全程 200，全程无异常日志。** 这就是「接口契约」不机器化时的典型故障形态。

---

## 二、⭐ 契约的四方结构

契约不是一句话，是**四个东西必须对齐**：

| 方 | 在哪 | 职责 |
|---|---|---|
| ① 手机端前端 | `prototype/mobile/*.js` | 读哪些字段 |
| ② 代理净化层 | `prototype/mobile/mobile_proxy.py` | `_pick()` **只保留上游已存在的键** |
| ③ 本仓后端 | `server/http_api.py` | 到底产出哪些键 |
| ④ **契约表** | `server/mobile_contract.py`（**新增，唯一真源**） | 声明「每条路由必有哪些字段」 |

关键点在 ②：

```python
def _pick(payload, allowed):
    return {key: value for key, value in payload.items() if key in allowed}
```

⇒ **后端少给一个字段，代理不会补，前端只会拿到 `undefined`。**
⇒ 契约必须写成**机器可查的字段路径**，并且**三方都拿它当准绳**。

### 2.1 契约表长什么样

```python
RouteContract(
    "POST", "/mobile-api/chat", "POST", "/gui/mobile-chat", "mobile",
    fields=("say", "model"),                     # 净化后仍须存在
    backend_fields=("say", "emotion", "model", "latency_ms",
                    "keyframes", "audio_samples"),  # 后端须产出
    non_empty=("say",),                          # 必须非空（空值等于没给）
    js_files=("chat.js",),                       # 哪些 JS 读它
)
```

字段路径支持 `a.b` 与 `items[].b`（数组元素）。

---

## 三、⭐ 门禁当场抓到的 6 个真 bug

| # | bug | 后果 | 修法 |
|---|---|---|---|
| **B-1** | 后端返回 `reply`，手机端读 `say` | **对话页永远显示「小栈这次没有返回内容」**（HTTP 200，无异常） | 后端改产 `say`（`reply` 保留给桌面端） |
| **B-2** | `handle_device_param` 读 `body["field"]/["value"]`，而代理发的是 `{"brightness": N}` / `{"volume": N, "permanent": …}` / `{"red","green","blue"}` | **亮度 / 音量 / 灯光三条接口全部 400** | 拆成三个专用处理器 |
| **B-3** | 屏幕程序只有 3 个（`idle/greet/focus`），而手机端页面有 **8 个按钮**、代理白名单是 `chat/quote/album/mood/pomodoro/fortune/game/settings` | 代理把 8 个程序**全过滤掉** ⇒ 屏幕页**一个按钮都不显示** | 后端补齐 8 个程序（与 `SCREEN_PROGRAM_IDS` 对齐） |
| **B-4** | 记忆接口返回 `{profiles, active, events}`，而手机端读的是**按分类摊平的 9 个键**（`likes/dislikes/…`） | 记忆页永远显示「目前还没有可管理的记忆」 | 后端按 9 类投影（档案透传 + 对话事件归到 `conversation_notes`） |
| **B-5** | 设备状态返回内部字典（`mac/battery/wifi/…`），手机端读的是 `network/music/stage/camera/head` | 状态页、设置页**全是「未上报」** | 后端投影成手机端形状（`DEVICE_STATUS_SHAPE` 模板 + 诚实占位值） |
| **B-6** | `app.js` 里 `serviceWorker.register("./sw.js?v=28")`，而入口版本已是 **v29** | 浏览器**复用旧 SW** ⇒ 新预缓存永不生效 | 改 `v=29`；并把 `sw.js` 纳入 MO-09 的版本号判据 |

> B-1 ~ B-5 的共同点：**都不抛异常、HTTP 全部 200**，页面只是「看起来一直是空的 / 一直显示未上报」。
> ⇒ 这类 bug **只能靠机器判**，靠人眼看 demo 是看不出来的。

---

## 四、⭐ 新门禁 `tools/check_mobile_contract.py`

8 条判据：

| ID | 判据 | 抓的是什么 |
|---|---|---|
| MC-01 | 契约里的每条路由，本仓路由表里必须存在（方法 + 路径 + owner 一致） | 契约指向空路由 |
| MC-02 | 契约里的每条手机端路由，代理白名单必须放行且映射一致 | 手机端直接 404 |
| MC-03 | ⭐ 后端真实响应**过完代理净化层**后，契约字段必须还在 | 字段名对不上 / 代理丢字段 |
| MC-04 | 后端真实响应必须含 `backend_fields` | 后端少产出 |
| MC-05 | `non_empty` 字段必须非空 | 空串等于没给 |
| MC-06 | 记忆分类 / 屏幕程序 id 必须与代理白名单一致 | 8 个按钮被过滤掉 |
| MC-07 | ⭐ 手机端 JS **真正读到**的字段，必须都在契约里 | 契约漏了 ⇒ 前端读到 `undefined` |
| MC-08 | 契约里的字段必须真的在手机端 JS 里出现过 | 契约腐烂（没人发现） |

### 4.1 MC-07 为什么最难：必须**按函数作用域**归属

同一个变量名在不同函数里可能来自**不同接口**。实测踩到的三个坑：

| 坑 | 现象 | 解法 |
|---|---|---|
| 变量名复用 | `settings.js` 里 `response` 被 8 个接口用；`device` 既是设备状态也是固件状态 | **按函数作用域**归属（`addEventListener("click", async () => {…})` 这种**匿名箭头函数也是独立作用域**，必须一并识别） |
| 同名不同方法 | `GET /mobile-api/experience` 与 `POST /mobile-api/experience` 是**两条**契约 | 路由键用 **`METHOD + path`** |
| 别名丢前缀 | `const network = status.network` ⇒ 读 `network.ssid` 的路径是 **`network.ssid`**，不是 `ssid` | 别名传播要**带路径**；`Promise.allSettled` 的 `.value` 才是响应本身 |

⇒ 实现里写了 `_strip_noise()`（屏蔽字符串 / 注释 / 正则，保留大括号结构）+
`_function_scopes()`（按大括号配对 + 函数头判定找作用域）+
`RE_ALIAS` / `RE_ALIAS_PROP`（别名传播，带路径前缀）。

### 4.2 变异自检（10 / 10）

```
真实现件零 FAIL                       ← 健康夹具
MC-03 字段名对不上被抓到
MC-03 代理丢字段被抓到
MC-02 代理漏放行被抓到
MC-01 契约指向不存在的路由被抓到
MC-04 后端少产字段被抓到
MC-05 必填字段为空被抓到
MC-06 记忆分类不一致被抓到
MC-07 前端读到契约外字段被抓到
MC-08 契约腐烂被抓到
────────────────────────
通过 10 / 10
```

> ⚠️ **自检本身踩到的坑**：变异一开始 5/10 不中。
> 根因是 `load_modules()` 只清了 `sys.modules["server.*"]`，**没清顶层 `server` 包**
> ⇒ 已缓存的 `server.__path__` 仍指向**原仓库** ⇒ **临时副本根本没被加载**。
> ⇒ 修法：`sys.modules.pop("server", None)` 一起清。
> ⇒ 这条与 97 号「夹具用字面量会静默失效」是同一族教训：**自检本身也要被审**。

---

## 五、⭐ 顺带把 Q27 推进了一步

Q27（两套后端怎么合并）的建议是 **③ → ①**：先把 `/gui/*` 砍到手机端真正用到的最小集，再并进 `server/`。

**本轮把 ① 的「最小集」落到了地上**：

| | 旧项目电脑后台 | 本仓 `server/http_api.py`（本轮新增） |
|---|---|---|
| 路由数 | 31 条 | **37 条**（15 条 `owner="mobile"` 真实现 + 22 条 `owner="desktop"` 显式 501） |
| 手机端能否独立跑 | ❌ 必须挂旧项目 | ✅ **能**（本仓后端 + 本仓手机端即可） |
| 边界 | 混在一起 | **写死**：`owner="mobile"` 真跑 / `owner="desktop"` 回 **501 + `{"owner":"desktop"}`** |

设备侧动作（舵机 / 灯 / 亮度 / 音量）在本层**只回执**（`applied_to: "state-only"`），
真实下发仍走 WS 的 `0x14` 关键帧通道（见 `docs/research/53` §5）——
**边界写死，不假装成功**。

---

## 五之二、Playwright 回归脚本：修好并**实测 PASS**

> 上一版本文档曾把 `prototype/mobile/tools/verify_v26_ui.js` 记为「陈旧 / 跑不通」——
> **本轮已修好并真跑通过**，此处为**公开订正**。

脚本原本是从旧项目搬过来的 v26 版本，与本仓**已经收敛的 IA 不一致**，四处必挂：

| # | 原状 | 修法 |
|---|---|---|
| 1 | 硬编码端口 `17869` | 改读 `MOBILE_URL` 环境变量（默认仍是 `17877`） |
| 2 | 找 4 个 Tab 按钮 | 本仓 IA 已收敛为 **3 个 Tab**，「屏幕功能」是首页快捷入口 ⇒ 改用 `#home` + `[data-target="screen"]` 导航 |
| 3 | `waitUntil: "networkidle"` | 页面**每 5 s 轮询一次**设备状态 ⇒ 网络永不空闲 ⇒ 改 `domcontentloaded` + 显式 `waitForFunction` |
| 4 | 把 3D 模型 404 记成失败 | 官方 `stack_chan_model.glb` 在无 LICENSE 的 `app/` 目录下，**故意不入库** ⇒ 必然 404 ⇒ 显式过滤（**不是回归失败**） |

**实测结果（本仓手机端 17877 → 本仓后端 17868）**：

```json
{"status":"pass","url":"http://127.0.0.1:17877","viewports":["430x932","390x844"],"programs":8}
```

跑通的内容：两个视口（430×932 / 390×844）各断言**无横向溢出**、**Tab 触控区 ≥ 44 px**、
**屏幕程序恰好 8 个**、**离线时程序按钮禁用**、**对话气泡往返渲染**，并各截 3 张图（home / screen / chat）。

**遗留**：`playwright` 仍**不在** `prototype/mobile/package.json` 依赖里（本机靠
`NODE_PATH=D:\jss18\AI\StackChan\node_modules` 借用旧项目的安装）；截图落点 `prototype/output/`
**已加入 `.gitignore`**（此前 `git add .` 会把 6 张 PNG 带进仓）；需要把产物挪出仓库时用
`MOBILE_SHOT_DIR` 覆盖。

---

## 六、未取得 / 未验证

| 项 | 状态 | 说明 |
|---|---|---|
| Q27 两套后端**合并** | ❌ **未做** | 本轮只落地了「本仓最小集」；**合并方案仍待拍板** |
| 真机设备链路 | ❌ **未验证** | 本仓后端此刻**没有连上真机** ⇒ `connected` 恒为 `False`、`network` 全空（**诚实占位，不是假数据**） |
| 真机 iPhone Safari | ❌ **未测** | safe-area / `backdrop-filter` / 触动手势 / 3D 性能 |
| 摄像头画面 | ❌ **未取得** | 无真机 ⇒ `/gui/device/camera/latest.jpg` 明确 404「no camera frame」，**不给假图** |
| Playwright 回归 | ✅ **已修并实测 PASS** | 见 §五之二；`playwright` 依赖仍未进 `package.json` |
| 逐轮情绪（E-4） | ❌ **未接入** | 本仓 server 仍用**人格基线**情绪 ⇒ 响应里如实标注 `emotion_source: "persona_baseline"` |
| SwiftUI 原生端 | ❌ **未编译** | 本机无 Swift 工具链 |

---

## 七、复现命令

```powershell
$repo='D:\jss18\AI\StackChan-main'
$env:PYTHONIOENCODING='utf-8'
Set-Location $repo

py -3.12 tools\check_mobile_contract.py --root .        # 体检（当前 0 FAIL）
py -3.12 tools\check_mobile_contract.py --self-test      # 变异自检（当前 10/10）
py -3.12 server\run_tests.py --quiet                     # 后端 102 个测试
py -3.12 'D:\AP\AP7000\ai-workspace\stackchan-research\r73\run_all_gates.py'   # 全量门禁

# 本仓后端 + 本仓手机端（自包含闭环）
py -3.12 server\http_api.py --port 17868 --provider stub
$env:STACKCHAN_MOBILE_ACCESS_TOKEN='stackchan-mobile-local'
$env:STACKCHAN_BACKEND_ORIGIN='http://127.0.0.1:17868'
py -3.12 serve.py --port 17877      # WorkingDirectory = prototype\mobile

# 手机端 UI 端到端回归（Playwright）
$env:NODE_PATH='D:\jss18\AI\StackChan\node_modules'   # 本机借用旧项目的 playwright
$env:MOBILE_URL='http://127.0.0.1:17877'
node prototype\mobile\tools\verify_v26_ui.js           # ⇒ {"status":"pass",...,"programs":8}
# 需要把截图挪出仓库：$env:MOBILE_SHOT_DIR='D:\AP\AP7000\ai-workspace\stackchan-research\shots'
```

---

## 八、落点

| 文件 | 改动 |
|---|---|
| `server/mobile_contract.py` | **新增**：手机端可见的响应契约（**唯一真源**）+ 形状模板 + 投影函数 |
| `server/http_api.py` | 改：处理器全部改成**契约形状**；`handle_device_param` 拆成 3 个；屏幕程序补齐 8 个；记忆改 9 类投影；设备状态投影成手机端形状 |
| `server/tests/test_http_api.py` | 改：26 → **35 个测试**（新增 `ContractShapeTests`：过完**真实代理净化层**再验契约） |
| `server/requirements.txt` | +1 行：`cryptography`（契约测试要 import 代理的 RSA 配网） |
| `tools/check_mobile_contract.py` | **新增**：第 46 / 47 项门禁（8 判据 + 10 变异自检） |
| `tools/check_mobile_app.py` | 改：MO-09 纳入 `sw.js`（SW 注册 URL 版本必须 == `CACHE_NAME`）+ +1 项变异自检（18 / 18） |
| `tools/gates.txt` | +2 行 ⇒ **45 → 47 项** |
| `.github/workflows/ci.yml` | +2 步；tooling job 的 pip 补 `cryptography` |
| `prototype/mobile/app.js` | 改：`sw.js?v=28` → `?v=29`（旧项目 `mobile_app/app.js` 同步改） |
| `docs/spec/09` §二 | 资产快照同步（server 21 源文件 / tools 30 个 `.py` / 门禁 47 项 / 测试 102 个） |
| `docs/research/72` | 门禁 45 → **47** 项 |
| `docs/research/README.md` / 根 `README.md` | 份数 97 → **98** |
| `prototype/mobile/tools/verify_v26_ui.js` | 改：端口/URL 走 `MOBILE_URL`；导航修正；`domcontentloaded`；过滤官方 3D 模型 404；落点可用 `MOBILE_SHOT_DIR` 覆盖 ⇒ **实测 PASS** |
| `.gitignore` | +`prototype/output/`（Playwright 截图产物；此前 `git add .` 会带进仓） |
| `prototype/mobile/README.md` | 补「Playwright 回归已修并实测 PASS」章节 |
