# 31 — 后端改造设计：Fork 官方 server 接 MiniMax

> 基线：`m5stack/StackChan` @ `origin/main` = `eff0d6b`（2026-10-22），本地 HEAD `1b57655`（v1.5.1）
> 取数纪律：本文所有代码结论来自本地 git clone `D:\jss18\AI\StackChan\StackChan2` 的 `origin/main` 版本 `server/` 树（已解包到 `D:\AP\AP7000\ai-workspace\stackchan-server-extract\server`），行号与 `git show origin/main:server/<路径>` 完全一致。MiniMax 端点以 `18` 号文档 §四 实测为准，本文未联网复测。

---

## §一 官方 server 现状测绘

### 1.1 目录与分层

官方 `server/` 是一个 **GoFrame v2 单体应用**，module 名 `stackChan`（`server/go.mod:1`），Go 1.26.3。

| 目录 | 职责 | 关键证据 |
|---|---|---|
| `server/main.go` | 进程入口。空导入 MySQL driver 以注册 `gdb` 适配器 | `server/main.go:12`（`_ "github.com/gogf/gf/contrib/drivers/mysql/v2"`）、`server/main.go:17`（`cmd.Main.Run(gctx.GetInitCtx())`） |
| `server/api/<group>/<ver>/*.go` | **纯 DTO + 路由元数据**。每个请求/响应一个 struct，`g.Meta` 里带 `path`/`method`/`tags`/`summary`。不含任何逻辑 | `server/api/user/v2/user.go:14-37`、`server/api/device/v2/device.go:14-56` |
| `server/internal/controller/<group>/*_new.go` | 控制器构造函数 `NewV1()` / `NewV2()` | `server/internal/controller/device/device_new.go` 等 |
| `server/internal/controller/<group>/*_vN_<action>.go` | 每个 API 一个控制器方法，方法名即处理函数名 | `server/internal/controller/device/device_v2_activate_and_bind_device.go:15`（`func (c *ControllerV2) ActivateAndBindDevice`） |
| `server/internal/service/*.go` | **业务逻辑层**。注意：GoFrame 惯例的 `logic` 层是空的（`server/internal/logic/.gitkeep`），真正的业务全写在 `service` | `server/internal/service/user.go:34`（`Login`）、`server/internal/service/device.go:78`（`ActivateAndBindDevice`）、`server/internal/service/agent.go:19`（`RestoreDefaultAgent`） |
| `server/internal/dao/` + `server/internal/dao/internal/` | GoFrame `gf gen dao` 生成的 DAO | `server/internal/dao/device.go`、`server/internal/dao/internal/device.go` |
| `server/internal/model/`、`model/do/`、`model/entity/` | 生成出的 model / do / entity 三件套 | `server/internal/model/entity/device.go` 等 |
| `server/internal/model/xiaozhi/` | **手写**的小智云端 DTO（agent / device / conversation） | `server/internal/model/xiaozhi/agent.go`、`device.go`、`conversation.go` |
| `server/internal/xiaozhi/xiaozhi.go` | **小智云端代理层**（唯一出网到 xiaozhi.me 的地方） | `server/internal/xiaozhi/xiaozhi.go:43`（`baseUrl = "https://xiaozhi.me/"`） |
| `server/internal/web_socket/` | WS 入口（`web_socket.go`）+ 心跳/清理定时任务（`socket_task.go`） | `server/internal/web_socket/web_socket.go:112`、`server/internal/web_socket/socket_task.go:28` |
| `server/internal/model/web_socket_model.go` | WS 客户端模型（`AppClient` / `StackChanClient`） | `server/internal/model/web_socket_model.go:22`、`:34` |
| `server/internal/middleware/middleware.go` | 3 个中间件 + 统一响应结构 | `server/internal/middleware/middleware.go:21`（`DefaultHandlerResponse`） |
| `server/internal/boot/cron.go` | 心跳(5s) / 过期连接清理(15s) 定时器 | `server/internal/boot/cron.go:35`、`:70` |
| `server/utility/rsa.go` | RSA-OAEP 加解密 + 四把钥匙的加载/校验 | `server/utility/rsa.go:57`（`loadRSAKeySet`）、`:201`（`RSAEncryptWithKey`） |
| `server/manifest/config/config.yaml` | **唯一配置模板**（GoFrame 默认搜 `manifest/config`） | `server/manifest/config/config.yaml:1-41` |
| `server/manifest/deploy/kustomize/` | K8s 部署（base + develop overlay） | `server/manifest/deploy/kustomize/overlays/develop/configmap.yaml:6-14` |
| `server/manifest/docker/Dockerfile` | 容器镜像 | `server/manifest/docker/Dockerfile` |
| `server/manifest/i18n/`、`manifest/protobuf/` | **空占位**（仅 `.gitkeep` / `.keep-if-necessary`），无实际内容 | 目录清单实测 |
| `server/resource/public/...` | 前端静态资源目录，**全部是 `.gitkeep`，实际内容不入库** | 目录清单实测 |
| `server/check_list/create_mysql_database.sql` | **唯一建表 SQL** | `server/check_list/create_mysql_database.sql:1` |
| `server/hack/hack.mk`、`hack-cli.mk`、`hack/config.yaml` | Makefile 片段 + 本地调试用配置 | `server/hack/config.yaml` |
| `server/internal/packed/packed.go` | GoFrame 打包资源入口（`gf build` 生成），把 `resource/` 打成二进制内嵌 | `server/internal/packed/packed.go` |
| `server/file/music/stackchan_music.mp3` | 唯一入库的静态媒体（舞蹈背景音乐） | 目录清单实测 |

**管理后台前端不在本仓库**：`s.SetServerRoot("web/management")`（`server/internal/cmd/cmd.go:79`）指向一个仓外的 `web/management` 目录，`resource/` 里只有空的 `public/` 占位。→ **fork 后管理后台需要我们自己做**（§六）。

### 1.2 GoFrame 怎么用

**Server**：`g.Server()`（GoFrame 默认 `ghttp` server）→ `server/internal/cmd/cmd.go:38`。
- `s.SetClientMaxBodySize(100 * 1024 * 1024)`（`cmd.go:39`）
- `s.SetServerRoot("web/management")`（`cmd.go:79`）
- `s.Run()`（`cmd.go:81`）

**路由注册**（`server/internal/cmd/cmd.go:43-76`）：

```go
s.BindHandler("/stackChan/ws", web_socket.Handler)              // cmd.go:43  WS 裸 handler

s.Group("/stackChan/v2", func(group *ghttp.RouterGroup) {        // cmd.go:63
    group.Middleware(middleware.V2TokenAuthMiddleware, ghttp.MiddlewareHandlerResponse)
    group.Bind(user.NewV2(), dance.NewV2(), device.NewV2())
})

s.Group("/stackChan", func(group *ghttp.RouterGroup) {            // cmd.go:68
    group.Middleware(middleware.TokenAuthMiddleware, ghttp.MiddlewareHandlerResponse)
    group.Bind(device.NewV1(), friend.NewV1(), dance.NewV1(), file.NewV1(),
               post.NewV1(), pano.NewV1(), appstore.NewV1(), xiaozhi.NewV1(), stackchandevice.NewV2())
})

s.Group("/admin/stackChan", func(group *ghttp.RouterGroup) {      // cmd.go:73
    group.Middleware(middleware.AdminTokenAuthMiddleware, ghttp.MiddlewareHandlerResponse)
    group.Bind(admin.NewV1(), file.NewV1())
})
```

`g.Meta` 的 `path` 是**相对 group 前缀**的：`server/api/user/v2/user.go:15` 的 `path:"user/login"` → 实际路由 `POST /stackChan/v2/user/login`。

**中间件**（`server/internal/middleware/middleware.go`）：
- `CORS`（`middleware.go:95`，`r.Response.CORSDefault()`）—— 全局 `s.Use`（`cmd.go:41`）
- `TokenAuthMiddleware`（`middleware.go:28`）—— `/stackChan` 组。**它不做任何鉴权**，只是尝试从 header 解出 MAC 并塞进 ctx var（`middleware.go:29-37`），解不出就放行
- `V2TokenAuthMiddleware`（`middleware.go:40`）—— `/stackChan/v2` 组，真鉴权（见下）
- `AdminTokenAuthMiddleware`（`middleware.go:101`）—— `/admin/stackChan` 组
- 每组都挂 `ghttp.MiddlewareHandlerResponse` → 统一 `{code,message,data}` 包装（`middleware.go:21-25`）

**JWT 签发与校验**：
- 签发（用户）：`service.generateToken`（`server/internal/service/user.go:122-146`），HS256，claims = `jti`(guid)/`id`(uid)/`iss`/`aud`/`iat`/`exp`；有效期 `TokenExpire = 365 * 24 * time.Hour`（`server/internal/service/user.go:28`）；密钥 `jwt.secret`（`server/internal/service/admin_user.go:26-30`），长度必须 ≥16 否则报错（`server/internal/service/user.go:138`）
- 校验（用户）：`V2TokenAuthMiddleware`（`middleware.go:53-91`）—— 读 HTTP header **`token`**（不是 `Authorization`），剥 `Bearer ` 前缀，强制 `*jwt.SigningMethodHMAC`（`middleware.go:67`），取 `claims["id"]` 写入 ctx var `uid`（`middleware.go:90`）
- 签发（管理员）：`service.AdminLogin`（`server/internal/service/admin_user.go:32-64`）—— **账号密码明文比对**（`admin_user.go:39`），来自配置 `admin.users`（`admin_user.go:69`），claims 只有 `username` 和 `Exp`
- 校验（管理员）：`AdminTokenAuthMiddleware`（`middleware.go:101-135`）—— 读 header `Authorization` 且**不剥 `Bearer ` 前缀**（`middleware.go:107`），且**不校验签名算法类型**（对比 `middleware.go:67`）

> ⚠️ **实读发现的官方缺陷（我们 fork 时必须修）**：管理员 token 的过期声明键名是大写 `"Exp"`（`server/internal/service/admin_user.go:49`，`model.Exp = "Exp"` 见 `server/internal/model/value_constant.go:11`），而 `golang-jwt/jwt/v5` 只认小写 `"exp"` → **admin token 实际上永不过期**。

**错误码**：**没有自定义错误码表**，全部用 GoFrame `gcode` 内置码 + `gerror.NewCode/NewCodef` 包装。实际用到的：`CodeNotAuthorized`、`CodeInternalError`、`CodeMissingParameter`、`CodeInvalidParameter`、`CodeBusinessValidationFailed`、`CodeDbOperationError`（见 `server/internal/service/user.go:37`、`:409`；`server/internal/service/device.go:63`、`:200`、`:204`）。

**配置从哪读 —— `manifest/` 配置键全清单**（全量 grep `MustGet(ctx, "...")` 实测）：

| 键 | 读取位置 | 说明 |
|---|---|---|
| `server.address` | `manifest/config/config.yaml:3` | `:12800` |
| `server.openapiPath` | `config.yaml:4` | `/api.json` |
| `server.swaggerPath` | `config.yaml:5` | `/swagger` |
| `logger.path/file/level/stdout/rotateExpire/rotateBackup/rotateSize` | `config.yaml:9-15` | 日志 |
| `database.default.link` | `config.yaml:20` | MySQL 连接串 |
| `jwt.secret` | `server/internal/service/admin_user.go:28` | JWT HS256 密钥 |
| `admin.users[].username` / `admin.users[].password` | `server/internal/service/admin_user.go:69` | 后台账号（明文） |
| `rsa.server.public` / `rsa.server.private` | `server/utility/rsa.go:59-60` | 服务端钥匙对 |
| `rsa.client.public` / `rsa.client.private` | `server/utility/rsa.go:61-62` | 客户端钥匙对 |
| `xiaozhi.secret_key` | `server/internal/xiaozhi/xiaozhi.go:590` | 小智开发者密钥 |
| `xiaozhi.generate_license_token` | `server/internal/xiaozhi/xiaozhi.go:312` | 生成 license 用 |
| `m5stack.loginUrl` | `server/internal/service/user.go:61` | 远端登录 |
| `m5stack.registrationUrl` | `server/internal/service/user.go:190` | 远端注册 |
| `m5stack.queryUsernameUrl` | `server/internal/service/user.go:166` | 用户名查重 |
| `m5stack.registrationToken` | `server/internal/service/user.go:167`、`:189` | 注册/查重鉴权头 |
| `m5stack.issuer` | `server/internal/service/user.go:125` | JWT iss |
| `m5stack.audience` | `server/internal/service/user.go:126` | JWT aud |
| `m5stack.queryMacAddressUrl` | `server/internal/service/device.go:154` | 校验 MAC 是否 M5Stack 官方设备 |
| `m5stack.queryMacAddressToken` | `server/internal/service/device.go:155` | 上述请求的 header |

> ⚠️ **`m5stack.*` 这一整段在 `server/manifest/config/config.yaml` 里根本不存在**。该文件只有 `server` / `logger` / `database` / `jwt` / `admin` / `rsa` / `xiaozhi` 七段（`config.yaml:2-41`）。K8s develop overlay 的 ConfigMap 也只有 `server` + `logger` 两段（`server/manifest/deploy/kustomize/overlays/develop/configmap.yaml:6-14`）。→ 官方靠部署侧注入，我们 fork 必须自己写全。

### 1.3 数据库

- **驱动**：`github.com/gogf/gf/contrib/drivers/mysql/v2 v2.10.0`（`server/go.mod:6`），在 `server/main.go:12` 空导入注册；底层 `github.com/go-sql-driver/mysql v1.9.3`（`server/go.mod:24`）
- **连接池**：GoFrame `gdb` 默认池，配置项只有 `database.default.link`（`config.yaml:20`），**没有显式 maxIdle/maxOpen 配置**
- **访问方式**：`g.DB()` / `dao.Xxx.Ctx(ctx)`；事务 `g.DB().Transaction(ctx, func(ctx context.Context, tx gdb.TX) error {...})`（`server/internal/service/device.go:242`）
- **建表 SQL 在哪**：`server/check_list/create_mysql_database.sql` —— **没有 migration 框架**（go.mod 里无 golang-migrate / goose / gf-migration），就是一份手写 DDL，库名固定 `stackChan`（`create_mysql_database.sql:6`）

**8 张表**（`server/check_list/create_mysql_database.sql`）：

| 表 | 关键列 | 行号 |
|---|---|---|
| `stackChan.app_store` | id, app_name, app_icon_url, description, firmware_url, create_at, update_at, is_deleted | `:6-18` |
| `stackChan.device_dance` | id, mac, dance_name, `dance_data JSON`, music_url, created_at, updated_at | `:20-30` |
| `stackChan.device_friend` | mac_a, mac_b（复合主键） | `:32-40` |
| `stackChan.user` | **uid PK**（注释明写"remote platform primary key"）, username(unique), userslug, display_name, icon_text, icon_bg_color, email_confirmed, join_date, last_online, user_status, create_at, update_at, is_deleted | `:42-61` |
| `stackChan.device` | **mac PK**, name, uid FK→user.uid, bind_time | `:63-76` |
| `stackChan.device_pano` | id, mac FK→device.mac, pano_url, created_at, updated_at | `:78-92` |
| `stackChan.device_post` | id, mac FK, content_text, content_image, created_at | `:94-104` |
| `stackChan.device_post_comment` | id, post_id FK→device_post.id, mac FK, content, created_at | `:106-119` |

> ⭐ **两条决定性的表结构事实**：
> 1. **`user` 表没有 password 列**。本地只存从远端 M5Stack 账号服务同步回来的资料（`server/internal/service/user.go:101-119` `saveUserToLocal`），密码校验 100% 发生在远端。
> 2. **没有任何 agent / persona 相关表**。agent 实体完全住在小智云端（`xiaozhi.GetDevices` / `GetAgentTemplate`），server 不落库。→ 我们要把人格包放进 server，需要**自己新建表**（或走文件系统，见 §四）。

### 1.4 `xiaozhi` 代理层到底做了什么

全部集中在 `server/internal/xiaozhi/xiaozhi.go`（22 KB）。

**读了哪些小智接口**（常量表 `server/internal/xiaozhi/xiaozhi.go:43-55`）：

| 常量 | 实际路径 | 用途 | 函数 |
|---|---|---|---|
| `baseUrl` | `https://xiaozhi.me/` | 根 | `:43` |
| `tokenPath` | `api/developers/token` | 用 `secret_key` 换 developer token | `refreshToken` `:589` |
| `agentTemplatesList` | `api/developers/agent-templates/list` | agent 模板 | `GetAgentTemplate` `:245` |
| `ttsList` | `api/user/tts-list` | TTS 音色表 | `GetTTSList` `:274` |
| `devices` | `api/developers/devices` | 设备列表 | `GetDevices` `:433` |
| `generateLicense` | `api/developers/generate-license` | 生成设备 license | `GenerateLicense` `:311` |
| `deviceActivate` | `api/agents/devices/activate` | 激活设备 | `ActivateDevice` `:408` |
| `deviceUnbind` | `api/developers/unbind-device` | 解绑 | `UnbindDevice` `:644` |
| `agentsDelete` | `api/agents/delete` | 删 agent | `DeleteAgent` `:220` |
| `createAgent` / `agents` | `api/agents` | 建/列 agent | `CreateAgent` `:234` / `GetAgents` `:496` |
| `chats` | `api/chats/list` | 会话列表 | — |
| （动态拼接） | `api/agents/{id}/config` | 改 agent 配置 | `SetAgentSetting` `:290-308` |

**认证模型**：单一 developer token，24 小时有效（`tokenExpiry = 24 * time.Hour`，`:54`），进程内全局变量缓存 + `sync.Mutex`（`:26-35`）；`init()` 起 24h ticker 强制清空（`:65-77`）；`doRequest` 收到 `"Session expired or logged out"` 时清 token 并**递归重试一次**（`:123-132`）。HTTP 客户端超时 10s（`:61`）。

> ⭐⭐ **最重要的发现：官方 server 与"语音"完全解耦。**
> `server/internal/xiaozhi/xiaozhi.go` 全文**没有任何音频流/PCM/Opus/TTS 合成代码**——它只转发元数据和配置。音频链路是**设备直连小智的 MQTT/WS**，server 从不经手。
> 推论：**我们接 MiniMax 不能"改一下 xiaozhi 代理层"，必须新建整条音频链路**（§三）。

**TTS 音色怎么解析**（`server/internal/service/agent.go`，与"从 XiaoZhi 音色表解析、不假设英语"的既有结论一致）：

- `getTemplateTtsVoiceAndLanguage`（`agent.go:107-126`）：先试模板的 `DefaultTtsVoice`，再遍历 `TtsVoices[]`，优先返回 language=="en"，否则取第一个非空作 fallback
- `parseTtsVoice`（`agent.go:221-238`）：解析 `"lang:voiceId"` 形式，**默认语言写死 `"en"`**
- `resolveTemplateTtsVoice`（`agent.go:174-219`）：拿 `GetTTSList()` 的 `voiceID`/`voiceName` 反查真正的 voiceId
- `getFirstAvailableTtsVoice`（`agent.go:128-170`）：兜底，按 `Languages` 顺序再按 `TTSVoices` key 排序，取第一个有 `voiceID` 的
- 最终写入 `AgentConfig{TtsVoice, Language, ...}` 并 POST 到 `api/agents/{id}/config`（`agent.go:82-99`）

**`License` 是什么机制**：小智"设备授权码"，用来把一台实体设备绑到某个 agent 实例上。

- `GenerateLicense(seed)`（`xiaozhi.go:311-324`）：用配置里的 `xiaozhi.generate_license_token` + MAC 作 seed 调 `api/developers/generate-license`，返回 `serial_number`/`product_name`/`board_name`
- **幂等**：`findLicenseByMACSeedVariants`（`xiaozhi.go:326-343`）先把 MAC 归一化成 4 种写法（大写 / 小写 / 大写带冒号 / 小写带冒号，`licenseMACSeedVariants` `:543-557`），逐个查 `api/developers/devices`，命中已有 license 就复用（`firstLicenseFromDevices` `:389-405`），避免重复生成
- `ActivateDevice(serialNumber, mac)`（`xiaozhi.go:408-430`）→ `api/agents/devices/activate`
- 解绑走 `api/developers/unbind-device`
- 对外还暴露 `GET /stackChan/xiaozhi/generateLicenseToken`，**把 license token 明文返给任意客户端**（`server/api/xiaozhi/v1/xiaozhi.go:22-26` + `server/internal/controller/xiaozhi/xiaozhi_v1_get_xiao_zhi_generate_license_token.go:19-23`）→ **官方安全弱点，我们 fork 必剥**（§二/§六）

**激活-绑定主流程**（`server/internal/service/device.go:78-151` `ActivateAndBindDevice`）：
1. `validateM5StackDevice`（`device.go:153-193`）→ GET `m5stack.queryMacAddressUrl + mac`，header 带 `queryMacAddressToken`，**响应体必须严格等于字符串 `"OK"`**（`device.go:31`、`device.go:188`），否则报 "This main controller is not from StackChan..."（`device.go:33`、`device.go:190`）
2. `xiaozhi.GetDevices` 查是否已激活（`device.go:98`）；没有则 `GenerateLicense` → `ActivateDevice` → 再查一次确认（`device.go:106-134`）
3. `RestoreDefaultAgentByAgentID` 恢复默认 agent（`device.go:138`，实现在 `service/agent.go:40-100`）
4. `BindDeviceToUser` 事务写 `device.uid` + `bind_time`（`device.go:241-256`）

### 1.5 WS 入口

**Handler 位置**：`server/internal/web_socket/web_socket.go:112` `func Handler(r *ghttp.Request)`，在 `server/internal/cmd/cmd.go:43` 用 `s.BindHandler("/stackChan/ws", web_socket.Handler)` 绑定（裸 handler，不走 RouterGroup）。

**连接鉴权**：`web_socket.GetMac(r)`（`web_socket.go:79-109`）
1. 读 HTTP header `Authorization`（`web_socket.go:80`，常量 `model.Authorization = "Authorization"`，`server/internal/model/value_constant.go:9`）
2. base64 解码（`:81`）→ `utility.RSADecrypt`（服务端私钥，`:86`）
3. 明文按 `"|"` 切，**至少 3 段**：`parts[0]`=MAC，`parts[2]`=时间戳（`:92-101`）
4. 时间戳与服务器时钟差 **±10 秒**才算有效（`:103`），否则报错
5. 失败 → `401 Unauthorized: invalid or missing MAC`（`web_socket.go:114-119`）

> ⭐ **这套"鉴权"不提供身份认证**。`rsa.server.public` 是**公开**的（任何客户端都要拿它加密请求），任何人都能用它构造 `mac|xxx|ts` 伪造任意 MAC 的连接。token 只保证"这段明文是我用私钥解出来的"，**不保证发送者是谁**。真正的身份绑定发生在后面的 `device.uid`（`server/internal/service/device.go:241`）。

**`deviceType` 分流**（`web_socket.go:120-124`、`:132`、`:203`）：
- `deviceType == "StackChan"` → 设备分支：查 `stackChanClientPool`（key=MAC）复用旧连接（`:136-160`）或新建（`:162-165`）；连上后广播 `DeviceOnline (0x17)` 给该 MAC 的所有 App（`:168-174`）；然后进读循环（`:184-202`）
- `deviceType == "App"` → App 分支：额外要求 query 参数 `deviceId`（`:204-208`），存进 `appClientPool`（key=MAC，value 是 `[]*AppClient` 切片，`web_socket.go:277-289`）；连上后按设备在线状态回 `DeviceOnline (0x17)` 或 `DeviceOffline (0x16)`（`:229-236`）
- **未知 deviceType 没有 else 分支** → 既不 Upgrade 也不报错，函数直接返回，连接悬空

**消息分发**：
- 二进制帧格式：`[type:1][len:4 大端][payload]`，`parseBinaryMessage`（`web_socket.go:308-324`）；长度不符直接丢弃（`:318-321`）
- 设备→server：`readStackChanMessage`（`web_socket.go:327-486`），按 `msgType` switch：`pong` 忽略、`ControlAvatar/ControlMotion/OnCamera/OffCamera` 直接忽略（`:336-337`）、`RefuseCall/AgreeCall/HangupCall` 通话状态机（`:338-403`）、`GetDeviceName` 查库回填（`:404-416`）、`Opus` 转发给订阅 App（`:417-435`）、`Jpeg` 同理（`:436-454`）、`GetAvatarPosture` 广播给 App（`:455-460`）、`AimedTakePhoto` 单播（`:461-466`）、default 广播给所有 App（`:467-475`）
- App→server：`readAppClientMessage`（`web_socket.go:489-`），payload **前 12 字节是 MAC**，后面才是数据（`:528-530`、`:538-540`、`:554-556`、`:570-572`、`:590-592`）
- 文本帧：设备端发来的 TextMessage 直接广播给 App（`web_socket.go:476-482`）

**帧类型全表**（`server/internal/web_socket/web_socket.go:29-63`）：

```
0x01 Opus          0x02 Jpeg          0x03 ControlAvatar  0x04 ControlMotion
0x05 OnCamera      0x06 OffCamera     0x07 TextMessage    0x09 RequestCall
0x0A RefuseCall    0x0B AgreeCall     0x0C HangupCall     0x0D UpdateDeviceName
0x0E GetDeviceName 0x0F inCall        0x10 ping           0x11 pong
0x12 OnPhoneScreen 0x13 OffPhoneScreen 0x14 Dance         0x15 GetAvatarPosture
0x16 DeviceOffline 0x17 DeviceOnline  0x18 OnAudio        0x19 OffAudio
0x1A AimedTakePhoto
```

> ⭐ **协议空洞（对我们最关键的一条）**：
> 1. `0x01 Opus` 在现有代码里**只用于 device↔App 的通话音频**（设备→App：`web_socket.go:417-435`；App→设备：`web_socket.go:523-536`）。**没有任何一条路径让 server 把 server 合成的语音推给设备**。
> 2. 没有"server→设备 下发表情/舵机"的帧。`ControlAvatar (0x03)` / `ControlMotion (0x04)` 是 **App→设备** 的（`web_socket.go:553-568`），server 端只是转发（`web_socket.go:336-337` 里 server 收到后直接忽略）。
> 3. 设备→server 方向也没有"我要说话/我要唤醒"的状态帧（`0x09 RequestCall` 是**通话**，不是唤醒）。
>
> → **要让设备"说话 → MiniMax → 设备表情 + 语音"，必须扩展设备侧协议（新增唤醒/请求帧 + server→设备 的音频帧与表情帧），并改固件。**（§三、§八）

**心跳与保活**：`server/internal/boot/cron.go` —— 每 5 秒 `web_socket.StartPingTime`（`cron.go:35`、`:55`），每 15 秒 `web_socket.CheckExpiredLinks`（`cron.go:70`、`:90`）。

---

## §二 ⭐ 认证层：换什么、留什么

### 2.1 逐条评估（保留 / 修改 / 移除）

| # | 配置键 | 官方用途（代码位置） | 处置 | 理由 |
|---|---|---|---|---|
| 1 | `m5stack.loginUrl` | 远端登录入口（`server/internal/service/user.go:61`） | **修改** | 改为**本地查库**（§2.2 方案 B），不再是远端 HTTP |
| 2 | `m5stack.registrationUrl` | 远端注册入口（`server/internal/service/user.go:190`） | **修改** | 同上 |
| 3 | `m5stack.queryUsernameUrl` | 用户名查重，**用户名直接拼在 base 后面**（`server/internal/service/user.go:166`） | **修改** | 改本地唯一索引查重（`user.username` 已有 unique 约束，`server/check_list/create_mysql_database.sql:58-59`） |
| 4 | `m5stack.registrationToken` | 查重/注册的 `Authorization` 头（`server/internal/service/user.go:167`、`:189`） | **移除** | 本地查库不需要对外鉴权头 |
| 5 | `m5stack.queryMacAddressUrl` | 工厂 MAC 校验，**MAC 拼在 base 后面**（`server/internal/service/device.go:154`、`:164`） | **移除** | 我们不做"是不是 M5Stack 出厂主板"这件事（`server/internal/service/device.go:33`） |
| 6 | `m5stack.queryMacAddressToken` | 上述请求的 `Authorization: Bearer` 头（`server/internal/service/device.go:155`、`:169`） | **移除** | 同上 |
| 7 | `m5stack.issuer` | JWT `iss`（`server/internal/service/user.go:125`） | **保留** | 值 `stackChan`（`26` 号 §5.1 实测原文），本来就该是我们的标识 |
| 8 | `m5stack.audience` | JWT `aud`（`server/internal/service/user.go:126`） | **保留** | 值 `stackChan_user`（同上） |
| 9 | `rsa.server.public` | 分发给设备/App 的公钥，设备用它加密 WS 握手凭证（`server/utility/rsa.go:59`、`server/internal/web_socket/web_socket.go:86`） | **保留** | 官方固件依赖它；**不改固件就不能删** |
| 10 | `rsa.server.private` | 服务端解密 WS 握手凭证（`server/utility/rsa.go:60`、`:197`） | **保留** | 同上 |
| 11 | `rsa.client.public` | 分发给客户端的公钥（`server/utility/rsa.go:61`） | **保留但不使用** | ⚠️ **server 侧从未调用 `RSAEncrypt`**（`server/utility/rsa.go:183-189` 无任何调用点，全仓 grep 确认）→ 官方 server **不加密响应**。保留配置项是因为 `loadRSAKeySet` 缺键会直接返回错误并被 `init()` panic（`server/utility/rsa.go:78-82`、`:34-38`） |
| 12 | `rsa.client.private` | 客户端解密响应用（`server/utility/rsa.go:62`） | **保留但不使用** | 同上。我们**不实现响应加密**，与官方行为一致 → 固件侧不需要任何改动 |
| 13 | `jwt.secret` | HS256 密钥（`server/internal/service/admin_user.go:28`） | **修改** | 值改由环境变量注入；长度下限 16 → 32（`server/internal/service/user.go:138` 现为 16） |
| 14 | `admin.users[].password` | **明文**比对（`server/internal/service/admin_user.go:39`） | **修改** | 改存哈希；改由环境变量注入 |
| 15 | `xiaozhi.secret_key` / `xiaozhi.generate_license_token` | 小智云端鉴权（`server/internal/xiaozhi/xiaozhi.go:590`、`:312`） | **移除** | 整个 `internal/xiaozhi/` 随 §六 剥离 |

**一句话结论**：**保留 7 项（`issuer`/`audience`/RSA 四把/`jwt.secret` 形态），修改 6 项（3 个账号 URL + 2 个 MAC 校验 + JWT 密钥强度），移除 4 项（`registrationToken` + 2 个 MAC 校验 + 2 个 xiaozhi 密钥）。账号体系从"远端 HTTP"改为"本地库"是唯一有结构影响的一条。**

### 2.2 ⭐ 账号体系我们怎么做

**三个候选方案**：

| 维度 | **A. 保留官方"远端账号服务"接口形态，指向我们自己的实现** | **B. 改成自建本地账号表** | **C. 完全去掉远端账号，只做设备绑定** |
|---|---|---|---|
| 改动量 | 中：保留 `callRemoteLogin` / `callRemoteRegister` / 全部远端响应防御代码，只换 URL | 小：删 8 个远端函数（约 140 行），新增本地查库 + 哈希 | 大：JWT 无 uid 可签，绑定关系无处安放 |
| 密码流向 | **明文 POST 到我们自己的服务**（`server/internal/service/user.go:63-66`、`:192-198`） | 只进哈希函数，**不落盘** | — |
| 维护成本 | 要同时维护两套协议（`status.code == "ok"`、`response.uid` 结构、`[[error:` 字符串） | 一套 | — |
| 内网/离线部署 | ❌ 要跑第二个服务 | ✅ 单进程 | ✅ |
| 未来搬到独立账号服务 | 容易 | 容易（只换查库实现，**API 契约不变**） | — |
| 与隐私红线（PRODUCT.md §6 原则 7） | ⚠️ 存疑：server 算不算"MiniMax 之外的其他服务" | ✅ 结构性成立 | — |

**⭐ 推荐：方案 B（自建本地账号表）。** 理由五条：

1. **方案 A 的全部复杂度来自"我们没有账号服务"这个前提** —— 我们自建后端后这个前提不成立，A 退化成纯开销：多一跳网络、多一套协议、多 140 行防御代码。
2. **A 会让"明文密码被 POST 出去"这件事通过审查**，与 PRODUCT.md §6 原则 7「数据在用户手里」相悖。官方这段代码把明文密码发给 `m5stack.loginUrl`（`server/internal/service/user.go:63-66`）。
3. **C 不成立**：`device.uid` 是外键指向 `user.uid`（`server/check_list/create_mysql_database.sql:68`、`:70-72`）；JWT 的 `claims["id"]` 就是 uid（`server/internal/middleware/middleware.go:85-90`）；iOS 端需要一个账号来表达"这只小栈是谁的"。没有账号 = 没有归属。
4. **B 的迁移成本为零**：将来要把账号搬到独立服务，只需把 `Login`/`Registration` 里的查库换成 HTTP 调用，`server/api/user/v2/user.go` 的 API 契约**一字不改**。
5. **B 让"密码不落盘"成为结构性保证，而不是纪律**。

**方案 B 的具体改造点**（文件 + 函数）：

| 文件 | 函数 | 动作 |
|---|---|---|
| `server/internal/service/user.go` | `Login`（`:34`） | **改**：本地查 `dao.User`，比对哈希，签发 JWT |
| 同上 | `callRemoteLogin`（`:60`） | **删** |
| 同上 | `saveUserToLocal`（`:101`） | **删**（注册时直接写库） |
| 同上 | `Registration`（`:149`） | **改**：本地唯一索引查重 + 写库 |
| 同上 | `callRemoteUsernameQuery`（`:165`）、`callRemoteRegister`（`:185`） | **删** |
| 同上 | `getRemoteAccount`（`:230`）、`postRemoteAccount`（`:250`） | **删** |
| 同上 | `validateRemoteUsernameQueryResponse`（`:270`）、`isRemoteAccountUnexpectedResponse`（`:316`）、`isRemoteUsernameNotFoundResponse`（`:327`）、`remoteUsernameQueryIndicatesDuplicate`（`:340`）、`hasTrueBoolValue`（`:362`）、`hasFalseBoolValue`（`:375`）、`stringValueEquals`（`:388`）、`hasNonZeroNumericValue`（`:398`） | **删**（这 8 个函数全是"猜测 M5Stack 账号服务会返回什么形状"的防御代码，共约 140 行） |
| 同上 | `newRemoteAccountUnavailableError`（`:408`）、`newUsernameCheckFailedError`（`:412`） | **改**（合并成一个本地错误构造） |
| 同上 | `generateToken`（`:122`） | **改**：有效期、密钥来源、加 `kid`（`jti` 字段官方已预留但从未使用，`server/internal/service/user.go:129`） |
| `server/internal/service/admin_user.go` | `AdminLogin`（`:32`）、`LoadUserConfig`（`:66`） | **改**：比对哈希；配置改环境变量注入 |
| `server/internal/service/device.go` | `validateM5StackDevice`（`:153`） | **删**；`ActivateAndBindDevice`（`:78`）第 1 步改为本地白名单/绑定态检查 |
| `server/api/user/v2/user.go` | `RegistrationReq.Email`（`:33`） | **改**：`v:"required"` → 可选（陪伴产品不该强制邮箱） |
| `server/check_list/create_mysql_database.sql` | `user` 表（`:42-61`） | **改**：加 `password_hash varchar(255) null`、`password_updated_at datetime null`、`email varchar(128) null` |

### 2.3 ⭐ RSA 双向加密留不留

**先纠正一处事实**（这是本次实读最重要的纠偏之一）：

> ⚠️ **官方 server 的 RSA 是"单向实现"，不是双向。**
> `server/utility/rsa.go` 里 `RSAEncrypt`（用 `rsa.client.public`）**全仓无调用点**；`RSADecrypt`（用 `rsa.server.private`）**只有一处调用**：`server/internal/web_socket/web_socket.go:86`，用于解密 WS 握手 header `Authorization` 里的 MAC 凭证。
> → **官方 server 不加密任何 HTTP 响应体。** `26` 号 §5.2 引的那句 `encryptedResponse, err := utility.RSAEncrypt(response)` 是 `server/README.MD` 的**协议设计说明**，server 代码里没有实现。
> → 这也是为什么官方固件必须能处理**明文响应**。我们不实现响应加密 = 与官方行为一致 = **固件零改动**。

**它到底防什么？**（逐项实读判定）

| 威胁 | RSA 挡得住吗 | 依据 |
|---|---|---|
| 中间人看请求内容 | ✅ 挡得住 | 只有服务端私钥能解（`server/utility/rsa.go:216-228`） |
| **设备请求被伪造** | ❌ **挡不住** | `rsa.server.public` 是**公开分发**的，任何人都能拿它加密 `mac\|xxx\|ts` 伪造任意 MAC。校验逻辑只验"能解密成功 + ±10 秒时间窗 + MAC 字段存在"（`server/internal/web_socket/web_socket.go:91-106`），**不验 MAC 是否已登记、不验签名** |
| **重放** | ❌ **挡不住** | 同一个 token 在 10 秒窗口内可无限重放（`server/internal/web_socket/web_socket.go:103`） |
| 中间人看响应内容 | ❌ 官方根本没加密响应 | 见上 |
| 中间人篡改请求 | ❌ 挡不住 | RSA-OAEP 无会话绑定，无 MAC/HMAC |
| 别人连上我们的 server 建 WS 连接 | ❌ **挡不住** | `addStackChenClient` → `service.CreateMacIfNotExists` **自动建档**（`server/internal/web_socket/web_socket.go:271-274`、`server/internal/service/device.go:36-48`）→ **任何人都能在 `device` 表插一行** |

**⭐ 明确建议（三层）**

**第 1 层 —— 保留四把钥匙，但只当"传输层机密性"用**（短期、不刷固件）

- `rsa.server.public` / `rsa.server.private`：**必须保留**。官方固件用它加密 WS 握手凭证，删了 = 设备连不上。
- `rsa.client.public` / `rsa.client.private`：**保留配置项、明确不实现响应加密**。理由：`loadRSAKeySet` 缺键会 `return error` → `init()` 直接 `panic`（`server/utility/rsa.go:78-82`、`:34-38`），删配置项 = 服务起不来。
- **每套部署独立生成四把钥匙**，绝不沿用官方或任何公开仓库里的；私钥永不进 Git（§七）。

**第 2 层 —— 把 TLS 作为硬前提（纯 server 侧，立刻可做）**

官方 `server/manifest/config/config.yaml` **没有任何 TLS 配置**，`s.Run()` 走明文 HTTP（`server/internal/cmd/cmd.go:81`）。RSA 只保护了 header 里那一个字段，其余（HTTP 头、WS 帧、路径）全是明文。
→ **必须**：前置 Caddy / Nginx / cloudflared 做 TLS 终止，设备端连 `wss://`、HTTP API 走 `https://`。这是 RSA 给不了的（RSA 不覆盖 header、不覆盖 WS 帧体、不做服务端身份认证）。

**第 3 层 —— 补真正的设备身份认证（⭐ 最大的安全洞，纯 server 侧可先堵一半）**

- **立刻可做（零固件改动）**：在 `service.CreateMacIfNotExists`（`server/internal/service/device.go:36-48`）之前加**准入检查** —— 只有 `device` 表中**已存在且 `uid` 非空**（或在我们自己的白名单表里）的 MAC 才允许建立 WS 连接。改动点：`server/internal/web_socket/web_socket.go:271-274`（`addStackChenClient`）+ `server/internal/web_socket/web_socket.go:114-119`（`Handler` 的 401 分支）。
  → 这一条把"任何人连上就建档"堵住，**不需要动固件**，是本次 fork 性价比最高的安全改动。
- **后续（需刷固件）**：设备首次激活时服务端下发**设备专属 secret**，后续 WS 握手用 `HMAC-SHA256(timestamp || nonce || mac)` 代替 RSA 凭证。**这与 PRODUCT.md §8「官方 WS 协议正文不改」硬冲突 → 必须由用户拍板**（§九 R-3）。

**简化方案与风险**：如果坚持"四把钥匙全砍掉、只靠 TLS"，风险是**设备侧必须改固件**（官方 HAL 用 `rsa.server.public` 加密握手头），且**账号鉴权与设备鉴权完全混同**。→ **不建议现在做**。结论：**保留 + 加固，而不是删除。**

### 2.4 JWT

| 项 | 官方现状 | 我们的处置 |
|---|---|---|
| 签发方 `iss` | `m5stack.issuer`（`server/internal/service/user.go:125`），值 `stackChan` | **保留** |
| 受众 `aud` | `m5stack.audience`（`server/internal/service/user.go:126`），值 `stackChan_user` | **保留** |
| 算法 | HS256（`server/internal/service/user.go:136`），校验端强制 `*jwt.SigningMethodHMAC`（`server/internal/middleware/middleware.go:67`） | **保留**（强制算法校验这点官方做对了） |
| 有效期 | `TokenExpire = 365 * 24 * time.Hour`（`server/internal/service/user.go:28`） | **修改** → 访问令牌 30 天 + 独立的 refresh token（表 `refresh_token`，存哈希） |
| 唯一标识 | `jti` = `guid.S()`（`server/internal/service/user.go:129`），**但从未被使用**（无黑名单表） | **启用**：加 `token_revoke` 表支持登出/踢下线 |
| 密钥管理 | `jwt.secret` 在 `config.yaml:24` 明文占位，靠部署侧注入 | **改**：环境变量 `STACKCHAN_JWT_SECRET` 注入，**32 字节以上随机**（官方下限 16，`server/internal/service/user.go:138`），**永不进 Git** |
| 密钥轮换 | 无 | **加**：`kid` 头 + 双密钥并存（当前签名 + 上一把），轮换窗口内两者都验 |
| 载荷 | `id`（uid）→ ctx var `uid`（`server/internal/middleware/middleware.go:85-90`） | **保留** |
| 传递方式 | HTTP header `token`（`server/internal/middleware/middleware.go:53`），WS 侧靠 header `Authorization` 的 RSA 凭证 | **保留**（iOS 端按官方 App 的方式实现） |

> ⚠️ **必须一并修的官方缺陷**：管理员 token 的过期声明键名是**大写 `"Exp"`**（`server/internal/service/admin_user.go:49`，常量 `model.Exp = "Exp"` 见 `server/internal/model/value_constant.go:11`），而 `golang-jwt/jwt/v5` 只认小写 `"exp"` → **admin token 实际永不过期**。同时 `AdminTokenAuthMiddleware` 读 header `Authorization` 时**不剥 `Bearer ` 前缀**（`server/internal/middleware/middleware.go:107`），也**不校验签名算法类型**（对比 `middleware.go:67`）→ 三个问题一起修。

### 2.5 ⚠️ 安全红线：密码不落盘

| 对象 | 官方现状 | 我们的做法 |
|---|---|---|
| 用户密码 | **根本不存本地**（`user` 表无 password 列，`server/check_list/create_mysql_database.sql:42-61`）；校验在远端，明文 POST 出去（`server/internal/service/user.go:63-66`） | **Argon2id 哈希**存 `user.password_hash`，格式 `$argon2id$v=19$m=65536,t=3,p=2$<salt>$<hash>`；校验用 `golang.org/x/crypto/argon2`（**新增依赖**）。**禁止**明文 / MD5 / SHA1 / 可逆加密 |
| 用户邮箱 | `RegistrationReq.Email` 是必填（`server/api/user/v2/user.go:33`） | **改为可选**。陪伴产品不该拿邮箱做门槛（PRODUCT.md §6 原则 7） |
| 管理员密码 | **明文存配置**（`config.yaml:28-29`）+ 明文比对（`server/internal/service/admin_user.go:39`） | 改存 **Argon2id 哈希**；配置项由环境变量注入；**启动时若检测到明文格式则拒绝启动** |
| RSA 私钥 | `config.yaml:33-37` 四个明文字段 | 环境变量注入（`STACKCHAN_RSA_SERVER_PRIVATE` 等），**文件不入 Git**，`hack/config.yaml` 里也不放真值 |
| 日志泄漏 | `g.Log().Debugf(ctx, "Remote login raw response: %s", respBody)`（`server/internal/service/user.go:71`）会打原始账号响应；`callRemoteRegister` 打了 username/email（`server/internal/service/user.go:187`） | **删除这两条日志**；新代码遵循"不打印密码、token、serial number、prompt 原文"（官方在小智侧已做到，见 `server/internal/xiaozhi/xiaozhi.go:154-157` 的注释与 `logXiaoZhiRequest` 实现 —— 这个好习惯我们照抄） |
| 日志里的 prompt / 私人层 | 官方无（官方没有 AI 层） | **硬规则**：`system_prompt`、对话原文、记忆片段**一律不进日志**（§三、§四） |

---

## §三 ⭐ AI 层：MiniMax 怎么接进去

### 3.1 ⭐ 架构前提（修正）：设备上有**两条独立的 WebSocket**

这是本次设计里最关键、也最容易搞错的一条。**官方 server 从来不做 TTS** —— 它只是控制面。

| 通道 | 代码归属 | 对端 | 职责 | 证据 |
|---|---|---|---|---|
| **控制面** | `firmware/main/hal/hal_ws_avatar.cpp` | **M5Stack 官方 server**（我们 fork 的 GoFrame） | 表情 `0x03` / 舵机 `0x04` / 摄像头 JPEG `0x02` / 通话信令 / 设备名 / `appLanAddress 0x1B` | `firmware/main/hal/hal_ws_avatar.cpp:88`（URL 拼接 `"{}/stackChan/ws?deviceType=StackChan"`）；`:233`/`:242`/`:375` |
| **语音面** | `firmware/xiaozhi-esp32/main/protocols/websocket_protocol.cc` | **小智服务器**（我们要换成自己） | Opus 音频上下行 + ASR/TTS 对话 | `firmware/xiaozhi-esp32/main/protocols/websocket_protocol.cc:117-152`（`OnData` 分发二进制音频）、`:221-226`（hello 声明 `audio_params`） |

**⚠️ 控制面没有音频下行路径（实读确认）**：
- `DataType::Opus = 0x01` 枚举存在（`firmware/main/hal/hal_ws_avatar.cpp:50`），但**接收分支整段被注释掉**：
  ```
  firmware/main/hal/hal_ws_avatar.cpp:212   // Opus handled in OnData Fast Path
  firmware/main/hal/hal_ws_avatar.cpp:213   // case DataType::Opus: {
  ```
  注释提到的 "OnData Fast Path" **并不存在** —— `OnData` 只是把原始字节塞进 `enqueueMessage` 队列。
- `StartAudioStream (0x18)` / `StopAudioStream (0x19)` 只切标志位（`hal_ws_avatar.cpp:383`、`:386`），**不接任何音频管线**。
- 控制面唯一的上行媒体是 `DataType::Jpeg`（`hal_ws_avatar.cpp:333`、`:451`）。

**⇒ 三条直接推论（贯穿本节）**
1. **不要把语音塞进控制面。** 控制面是给 iOS App 遥控设备用的（表情/舵机/文本），语音是另一条隧道。
2. **我们的 GoFrame server 继续只做控制面**（server→设备推表情/舵机/文本），**语音面需要一个独立的 WS 端点**，由我们的 server（或一个伴生服务）实现小智的语音协议。
3. **官方 server 的 WS 代码一行都不用改就能承载表情与舵机**（`0x03`/`0x04` 在固件侧是"收到就执行"，无方向概念）；**新增的只是"server 主动推"的那一侧**。

**固件依赖来源**：`firmware/repos.json` 声明 `https://github.com/78/xiaozhi-esp32.git` branch `v2.2.4` → path `xiaozhi-esp32`，并打 `firmware/patches/xiaozhi-esp32.patch`。**该目录不在 git 里，是构建时 fetch 的**；本文引用的 xiaozhi-esp32 行号来自本机工作树 `D:\jss18\AI\StackChan\StackChan2\firmware\xiaozhi-esp32`（v2.2.4 + 官方 patch）。官方 patch 实测**没有动协议层**（保留了 `mqtt_protocol.h` 与 `websocket_protocol.h` 两个 include），它改的是：删掉激活码显示改为"必须 App 绑定"（`ota.cc` 的 `requires_app_binding_`）、注释掉 emote 资源策略、i2c 重试、省电策略。→ **协议层是干净的上游代码，我们可以基于它做自己的实现。**

### 3.2 改造点定位

#### Server 侧（Go，我们 fork 的 `server/`）

| 动作 | 文件 | 函数 / 位置 | 说明 |
|---|---|---|---|
| 新增 | `server/internal/minimax/config.go` | 新增 | 读 `minimax.*` 配置 + 环境变量（`api_key` / `chat_model` / `tts_model` / `base_url` / `tts_url` / `sample_rate` / `language_boost`） |
| 新增 | `server/internal/minimax/chat.go` | `ChatStream(ctx, req) (*ChatStreamer, error)`、`(*ChatStreamer).Next() (delta string, done bool, err error)` | SSE 解析器；`delta` 直接喂 TTS |
| 新增 | `server/internal/minimax/tts.go` | `DialTTS(ctx, cfg, req) (*TTSConn, error)`、`(*TTSConn).Start()` / `.Continue(text)` / `.Finish()` / `.NextAudio() (pkt []byte, sampleRate int, err error)` | TTS WS 客户端；`NextAudio` 返回**已拆好的裸 Opus 包** |
| 新增 | `server/internal/minimax/emotion.go` | `ResolveTTSEmotion(model, want string) string` | `whisper`/`fluent` 在 `speech-2.8-*` 不支持 → 显式降级（§3.7） |
| 新增 | `server/internal/minimax/errors.go` | `MapBaseResp(code int) error` | `base_resp.status_code` → Go 错误（§3.3 错误码表） |
| 新增 | `server/internal/voice/ogg.go` | `OggOpusParser` + `(*OggOpusParser).Feed(chunk []byte) ([]OpusPacket, error)` | **Ogg de-mux**（§3.4 核心） |
| 新增 | `server/internal/voice/opus_toc.go` | `OpusFrameDuration(pkt []byte) (ms int, ok bool)` | 从 Opus 包 TOC 读真实帧长（§3.4） |
| 新增 | `server/internal/service/conversation.go` | `StartConversation(ctx, req)`, `StreamConversation(ctx, ...)` | 对话编排：Chat → 情绪抽取 → TTS → 推设备 |
| 新增 | `server/internal/service/persona.go` | `LoadPersona`, `WatchPersona` | 人格包加载/热更新（§四） |
| 新增 | `server/internal/service/emotion.go` | `EmotionStateMachine` | 情绪状态机（§五） |
| 新增 | `server/internal/model/emotion_frame.go` | `EmotionFrame` | 情绪 → 表情几何 + 舵机 + 灯色的帧模型（复用官方 `DefaultDanceData` 关键帧结构） |
| 新增 | `server/internal/voiceplane/` | `handler.go` | **⭐ 语音面 WS 端点**：实现小智 `BinaryProtocol2/3` 帧 + hello 握手 + JSON 控制消息（§3.5） |
| 改 | `server/internal/cmd/cmd.go` | 路由区（`:43-76`） | 加 `s.BindHandler("/stackChan/voice", voiceplane.Handler)`；加 `/stackChan/ai` 组（供 iOS 端走"设备不在手边"场景） |
| 改 | `server/internal/web_socket/web_socket.go` | 帧常量块（`:29-63`） | 加 `RequestChat 0x1E`（设备→server 文本请求） |
| 改 | 同上 | `readStackChanMessage`（`:327`） | 加 `case RequestChat:` 分支 → 转 `service.Conversation` |
| 改 | 同上 | `Handler`（`:112`）、`addStackChenClient`（`:271`） | 加设备白名单准入（§2.3 第 3 层） |
| 改 | `server/internal/service/user.go` | 见 §2.2 表 | 账号本地化 + 删 8 个远端函数 |
| 改 | `server/internal/service/device.go` | `validateM5StackDevice`（`:153`） | 删；改本地白名单 |
| 改 | `server/manifest/config/config.yaml` | 追加 `minimax:` / `persona:` / `voice_plane:` 段 | 新增配置键 |

#### 设备侧（固件，我们自己的分支，patch 形式）

| 动作 | 文件 | 说明 |
|---|---|---|
| 新增 | `firmware/main/protocols/minimax_protocol.{cc,h}` | **新的 MiniMax 协议层**：WS 客户端（连我们的 server）、`task_start`/`task_continue`/`task_finish`、`task_continued` → Ogg 拆包 → 裸 Opus 包 → 复用 `BinaryProtocol3` 帧发给 server |
| 改 | `firmware/main/application.cc` | 把 `protocol_` 从 `WebsocketProtocol` 换成 `MiniMaxProtocol`（或按 `STACKCHAN_SERVER_URL` 二选一） |
| 改 | `firmware/main/hal/hal_ws_avatar.cpp` | 控制面**只加** `RequestChat` 出站 + 表情/舵机入站处理；**不动音频** |
| 改 | `firmware/main/Kconfig.projbuild` | `OTA_URL` 默认值改掉（`:16-18` 现为 `https://api.tenclass.net/xiaozhi/ota/`）；`STACKCHAN_SERVER_URL`（`:3-5` 现为 `http://47.113.125.164:12800`）改指我们的 server |

> ⚠️ **`STACKCHAN_SERVER_URL` 默认值现在是官方 server 的公网 IP**（`firmware/main/Kconfig.projbuild:5`）。我们必须在自己的分支改默认值，或用 `sdkconfig.defaults.local` 覆盖（官方 `firmware/CMakeLists.txt` 注释明确支持这个 overlay 机制）。
> ⚠️ **`OTA_URL` 也必须一起改** —— 否则设备开机仍会去小智拉固件（PRODUCT.md §8 已列为硬约束）。

### 3.3 Chat

| 项 | 决定 | 依据 |
|---|---|---|
| 端点 | `POST https://api.minimax.io/v1/text/chatcompletion_v2` | `18` 号 §4.2（官方 OpenAPI 原文）；**不**用 OpenAI 兼容 `/v1/chat/completions`，**不**用 Anthropic 兼容 `/v1/messages`（官方推荐但我们的 SDK 侧只需一套） |
| 模型 | `MiniMax-M3.1-Flash`（默认） | `18` 号 §4.2 模型枚举只有 `MiniMax-M3.1-Flash` / `MiniMax-M3`；Flash 延迟低、陪伴场景够用。⚠️ `M2-her`（角色扮演专用）**已退役**（`18` 号 §4.5）→ 人格引擎必须自己扛 |
| 鉴权 | `Authorization: Bearer <API_KEY>` | `18` 号 §4.2 |
| 流式 | `stream: true` → SSE，`Content-Type: text/event-stream`；chunk 形如 `chat.completion.chunk`，取 `choices[0].delta.content` | `18` 号 §4.2 |
| `max_completion_tokens` | **512**（`max_tokens` 已 deprecated） | 陪伴场景短句为主（PRODUCT.md §7 "短句为主"）。上限防 runaway |
| `temperature` | **0.8** | 官方范围 `(0, 1]`；0.8 兼顾稳定与不呆板 |
| `top_p` | 默认 0.95 | 官方默认 |
| `mask_sensitive_info` | `true` | §3.6 |
| `tools` | **只挂一个**：`report_emotion`（参数 `{emotion, intensity}`） | §3.3 下方"情绪抽取" |
| `tool_choice` | 不传（官方仅支持 `auto`） | `18` 号 §4.2 |
| `stream_options.include_usage` | `true` | 用于计费统计，不影响内容 |

**⭐ 流式 SSE → 设备能消费的帧（文本→设备这条链自己搭）**

Chat 的文本流**不直接给设备**。设备要的是"声音 + 表情"。文本流有两个消费者：

```
MiniMax Chat (SSE)
   │  choices[0].delta.content  逐段增量
   ├─► ① TTS 的 task_continue（增量喂文本，边生成边合成）
   │      └─► TTS task_continued.data.audio (hex, Ogg/Opus)
   │            └─► Ogg de-mux → 裸 Opus 包 → BinaryProtocol3 → 语音面 WS → 设备播放
   │
   ├─► ② 情绪抽取（tools 的 tool_calls 增量，或首行标记剥离）
   │      └─► EmotionStateMachine → 决定表情/舵机/灯色帧
   │            └─► 控制面 WS：0x03 ControlAvatar（几何 JSON）+ 0x04 ControlMotion（舵机 JSON）
   │
   └─► ③ 文本本体 → 设备端嘴型/字幕（可选）+ 推给 iOS App（0x07 TextMessage）
```

**情绪抽取方式（确定）**：**优先用 `tools` 的 tool call**。
- 在 Chat 请求里挂一个函数工具 `report_emotion`，参数 `{"emotion": "<枚举>", "intensity": 0.0-1.0}`。模型在生成回复的过程中调用它 → server 从流式 chunk 的 `tool_calls` 增量里解析参数。
- 好处：情绪标签**不会混进回复文本**，因此**不会进 TTS**（TTS 只吃 `delta.content`）。这是"可以考虑"变"确定方案"的关键点。
- **兜底**：若模型这一轮没调用工具（`tool_choice` 只能 `auto`），server 从回复首行剥离一个可选的 `[[emotion:xxx]]` 标记后再送 TTS。两条路径都不污染语音。

**SSE → TTS 的时序控制**：
- **不缓冲全文**。收到第一个非空 `delta.content` 立刻发 `task_continue`。
- 建议按**句读切分**（`。`/`。`/`！`/`？`/换行）后按标点送 `task_continue`，避免把整段中文塞一次导致 TTS 首包慢。
- `task_continue` 可以发多次（官方原文明确"可多次，逐句"）。

**错误码映射**（`base_resp.status_code`，官方原文）：
`1000` 未知 / `1001` 超时 / `1002` 限流 / `1004` 鉴权失败 / `1008` 余额不足 / `1013` 内部错误 / `1027` 输出内容非法 / `1039` 超 token 限制 / `2013` 参数非法。
→ server 侧映射成 GoFrame `gcode`，其中 `1002`→可重试、`1004`→告警（key 错）、`1008`→告警（余额）、`1027`→重试一次（换 seed 或降温度）。

### 3.4 ⭐ TTS：事件时序 → 设备协议（确定方案）

#### 3.4.1 端点与请求（官方文档原文已复核）

> **地址：`wss://api.minimax.io/ws/v1/t2a_v2`**（官方 AsyncAPI `address: /ws/v1/t2a_v2`；官方 Python 示例 `url = "wss://api.minimax.io/ws/v1/t2a_v2"`）。
> ⚠️ **纠正一处流传的错误**：曾有 "`wss://api.minimax.io/v1/t2a_v2`"（漏 `/ws`）的说法 —— 本次已从官方文档原文核实，**正确路径带 `/ws`**。

**`task_start` 请求体（我们的取值）**：
```json
{
  "event": "task_start",
  "model": "speech-2.8-turbo",
  "voice_setting": {
    "voice_id": "<人格包指定>",
    "speed": 1.0, "vol": 1.0, "pitch": 0,
    "emotion": "calm",
    "text_normalization": false
  },
  "audio_setting": {
    "sample_rate": 16000,
    "format": "opus",
    "channel": 1
  },
  "language_boost": "Chinese",
  "subtitle_enable": true,
  "subtitle_type": "word_streaming",
  "continuous_sound": false
}
```
- `model`：`speech-2.8-turbo`（首选，低延迟）/ `speech-2.8-hd`（音质优先）。⚠️ `speech-01-*` 是遗留兼容，不作首选（`18` 号 §4.5）。
- `audio_setting.bitrate` **只对 mp3 生效**（官方原文），opus 下不设。
- `voice_modify`（pitch/intensity/timbre 音效）**在 opus 下不可用** —— 官方原文限定"非流式支持 mp3/wav/flac，流式支持 mp3"。→ 音色变化只能靠 `voice_setting.pitch`（-12..12）/ `speed`（0.5..2）/ `vol`（0,10] / `timbre_weights`。
- `continuous_sound: false`（默认）= 切句并发推理，**延迟更低**；`true` = 不切句连续推理，韵律更好但更慢。→ 陪伴场景选 `false`。
- `subtitle_enable: true` + `subtitle_type: "word_streaming"` → 每个 chunk 带累计字幕（`text_begin` 变了 = 新段落开始）。⚠️ `is_final: true` 的消息**不带字幕**。

#### 3.4.2 ⭐⭐ 核心核实结论：MiniMax 的 opus 输出格式 vs 设备解码器期望格式

| | MiniMax TTS `format:"opus"` | 设备解码器期望 |
|---|---|---|
| **容器** | **Ogg/Opus**（官方原文："`opus` is Ogg/Opus encoded; in streaming mode, audio chunks must be reassembled in arrival order before decoding."） | **裸 Opus 包**（无容器） |
| **证据** | 官方 AsyncAPI `audio_setting.format` 枚举含 `opus`；同段说明 Ogg/Opus 编码 | `firmware/xiaozhi-esp32/main/protocols/protocol.h:26-31`（`BinaryProtocol3.payload`）、`:17-24`（`BinaryProtocol2.payload`）；`firmware/xiaozhi-esp32/main/audio/audio_service.cc:361-374`（payload 直接喂 `esp_opus_dec_decode`） |
| **帧结构** | Ogg page 序列，每 page 含 27 字节头 + segment table + body | `[type:1][reserved:1][payload_size:2 BE][payload]`（v3）或 `[version:2][type:2][reserved:4][timestamp:4][payload_size:4 BE][payload]`（v2） |
| **采样率** | `audio_setting.sample_rate`（我们设 16000）；`extra_info.audio_sample_rate` 回传实际值 | hello 里声明 `sample_rate: 16000, channels: 1, frame_duration: 60`（`firmware/xiaozhi-esp32/main/protocols/websocket_protocol.cc:221-226`） |
| **帧长** | 不保证固定；由 Opus TOC 决定 | `SetDecodeSampleRate(packet->sample_rate, packet->frame_duration)`（`firmware/xiaozhi-esp32/main/audio/audio_service.cc:358`）→ **逐包声明**，且 `frame_duration` 必须落在 `{5,10,20,40,60,80,100,120}`（`firmware/xiaozhi-esp32/main/audio/audio_service.h:57-65`），否则 `AS_OPUS_GET_FRAME_DRU_ENUM` 返回 -1 |

**⇒ 结论：两者不一致，中间必须做 Ogg de-mux。** 这正是整条语音链路最可能出错的点，展开说清楚：

1. **必须做 Ogg 拆包**。官方明说流式下"必须按到达顺序重新组装后再解码"。拆包算法：
   - 累积 hex 解码后的字节流（一个 Ogg page 可能跨多个 `task_continued`）
   - 扫 `OggS` magic 定位 page 起点 → 读 27 字节头 → 读 segment table（`page_segments` 个 lacing value）
   - 按 lacing 切 packet：lacing < 255 = packet 结束，= 255 = 继续
   - 跨 page 的 packet 要拼接
2. **拆包后不得改动 Opus 包内容**。不做 repacketize（多帧 packet 无法在不重新编码的情况下拆成单帧；改 TOC 帧计数会破坏码流）。
3. **⭐ 帧长必须从 Opus TOC 读，不能猜**。Opus 包首字节 TOC：`config = TOC >> 3`（帧长表：0-3 → 2.5/5/10/20 ms，4-7 → 40/60/80/120 ms），`s = (TOC>>2)&1`，`code = TOC&3`（帧数 0/1/2/任意）。server 实现 `OpusFrameDuration(pkt)`。
4. **⭐ 采样率用 MiniMax 回传的 `extra_info.audio_sample_rate`，不用猜**。官方 `extra_info` 明确含 `audio_sample_rate` 字段 → 这是权威值。
5. **拆包放在 server 侧，不放设备侧**。设备仓库里**已有** `OggDemuxer`（`firmware/xiaozhi-esp32/main/audio/demuxer/ogg_demuxer.{cc,h}`），但它目前**只用于播放本地 OGG 提示音**（`firmware/xiaozhi-esp32/main/audio/audio_service.cc:657-667` 的 `PlaySound`），且内部有 `uint8_t packet_buf[8192]`（`ogg_demuxer.h:30`）。放到 server 侧的理由：① ESP32-S3 只有 8MB PSRAM，别在 MCU 上多跑一个 Ogg 解析器；② server 侧拆包能顺手算准 TOC 帧长、填好 `sample_rate`/`frame_duration`；③ server 侧还能做"与设备声明帧长不一致时的兜底"。
6. **解码器会被反复重开**：`SetDecodeSampleRate` 的实现是 `esp_opus_dec_close` + `esp_opus_dec_open`（`firmware/xiaozhi-esp32/main/audio/audio_service.cc:462-470`）→ **每个包都重开一次解码器**。这既说明"逐包声明帧长/采样率是设计允许的"，也是**性能热点**（每包重开 opus 解码器）。→ 我们的 MiniMax 协议层应**尽量把相同 (sample_rate, frame_duration) 的包聚在一起、按段声明**，减少重开次数。
   （⚠️ 这是从代码读出的**推论**，不是官方文档承诺 —— 登记为需实测项。）

#### 3.4.3 ⭐ 事件时序 → 设备协议映射表（确定方案）

| MiniMax 事件 | 方向 | server 动作 | 发给设备 |
|---|---|---|---|
| `connected_success` | 收 | 建会话，记 `session_id` / `trace_id` / `base_resp.status_code` | — |
| `task_start` | 发 | 带 `voice_setting` / `audio_setting` / `language_boost` / `subtitle_enable` | — |
| `task_started` | 收 | 标记"可送文本"；`status_code != 0` → 失败处理 | — |
| `task_continue` | 发 | 送入 Chat 的增量文本（按句切分，可多次） | — |
| `task_continued` | 收 | `data.audio`(hex) → hex decode → **Ogg de-mux** → 裸 Opus 包；读 `extra_info.audio_sample_rate`；从 TOC 读帧长 | **语音面 WS**：`BinaryProtocol3{type=0, reserved=0, payload_size(BE16), payload=裸 Opus 包}`；`sample_rate`/`frame_duration` 随包元数据传给设备 |
| `task_continue`（下一句） | 发 | 继续送文本 | — |
| `task_finish` | 发 | 结束文本输入 | — |
| `task_continued{is_final:true}` | 收 | 最后一包音频（⚠️ **不带字幕**） | 同上 |
| `task_finished` | 收 | 关闭会话 | — |
| `task_failed` | 收 | **必须关闭连接**（官方原文） | 播放队列清空；设备显示"没听清"表情 |

**设备侧完整链路（一条线读完）**：
```
MiniMax TTS WS  wss://api.minimax.io/ws/v1/t2a_v2
   └ task_continued.data.audio (hex: Ogg/Opus)
      └ server: hex decode
         └ server: Ogg de-mux  →  []裸 Opus 包
            └ server: 逐包封 BinaryProtocol3 → 语音面 WS (server ↔ 设备)
               └ device websocket_protocol.cc:117-152 OnData(binary)
                  └ AudioStreamPacket{sample_rate, frame_duration, timestamp, payload}
                     └ device audio_service.cc:335-401 OpusCodecTask
                        └ esp_opus_dec_decode → PCM → 播放
```

**为什么不用 `0x01 Opus` 走控制面**：控制面固件的 `DataType::Opus` 接收分支是死的（§3.1），且控制面 payload 语义是"device↔App 通话音频"（`server/internal/web_socket/web_socket.go:417-435`、`:523-536`）。**语音走独立通道，控制面保持干净。**

### 3.5 语音上行与 ASR（必须自己搭的一段）

设备上行链路是现成的：
```
麦克风 → PCM → esp_opus_enc（16000 Hz / 60ms / 单声道 / BITRATE_AUTO）
   → BinaryProtocol3{type=0, payload=裸 Opus 包}
   → 语音面 WS 上行
```
证据：`firmware/xiaozhi-esp32/main/audio/audio_service.cc:81`（`encoder_sample_rate_ = 16000`）、`:409-411`（`frame_duration = 60`、`sample_rate = 16000`）、`firmware/xiaozhi-esp32/main/audio/audio_service.h:40`（`OPUS_FRAME_DURATION_MS 60`）、`:67-73`（编码器配置）；发送侧 `firmware/xiaozhi-esp32/main/protocols/websocket_protocol.cc:30-58`（`SendAudio` → `BinaryProtocol3`）。

**问题：ASR 谁做？**

| 方案 | 可行性 | 结论 |
|---|---|---|
| server 侧 ASR（server 收 Opus → 解码 PCM → 送 STT） | MiniMax STT 端点 `/v1/audio/transcriptions` 在 `18` 号 §4.1 被标为"⚠️ 路径待确认"，**本轮未取得** | **可行但依赖一个未核实的端点** → §九 登记 |
| 设备端 ASR | `managed_components/espressif__esp-sr` 在树里，但 xiaozhi 用它只做**唤醒词**（`firmware/xiaozhi-esp32/main/audio/wake_words/afe_wake_word.cc`），**没有通用 ASR** | 需要自己接 ESP-SR 的 MultiNet，**工作量与可行性未评估** → §九 登记 |
| 沿用小智 ASR | 违背"不接小智" | ❌ |

**⭐ MVP 决策（绕开 ASR，先跑通闭环）**：
- **MVP 阶段的"设备说话"不经过 ASR**：由**设备本地事件**触发（触摸区 / 唤醒词 / 定时 cue）→ 设备发一条 `RequestChat (0x1E)`（含一段触发上下文，如"用户叫了你"或"用户按了触摸区"）→ server 调 Chat + TTS → 设备表情 + 语音。
- 这样 **"设备说话 → MiniMax → 设备表情 + 语音"** 的纵切**完全不需要 ASR**，可以先跑通。
- **ASR 是第二步**：在 §八 里单列为 M5.2 里程碑。

**server 侧语音面 WS 端点要实现的最小集**（`server/internal/voiceplane/`）：
1. WS 升级 + 鉴权（用设备 MAC + 时间戳，机制见 §2.3）
2. hello 握手：下发 `audio_params{format:"opus", sample_rate:16000, channels:1, frame_duration:60}`（照抄 `firmware/xiaozhi-esp32/main/protocols/websocket_protocol.cc:221-226` 的格式，设备端 `ParseServerHello` 会解析，`:248-254`）
3. 收 `BinaryProtocol3` 音频包 → 解 Opus → PCM（server 侧需要一个 Opus decoder）
4. 下发 `BinaryProtocol3` 音频包（裸 Opus 包，server 侧做 Ogg de-mux 后直接填 payload）
5. JSON 控制消息（`type:"hello"` / `"stt"` / `"tts"` / `"stop"`），供 ASR 结果与状态回传

> ⚠️ **server 侧需要一个 Opus decoder**（把设备上行的 Opus 解成 PCM 送 ASR）。Go 侧：`github.com/hraban/opus` 是 cgo（构建复杂），纯 Go 实现质量不足。**建议：MVP 阶段 server 侧不做 ASR → 不需要 decoder**；等 ASR 落地时再评估（或者把 ASR 放到设备侧）。→ §九 登记。

### 3.6 ⭐ `mask_sensitive_info` 怎么用

**官方原文**（`18` 号 §4.2）：Chat 的 `mask_sensitive_info`（默认 false）会把输出里的**邮箱 / 域名 / 链接 / 证件号 / 住址**等私密信息替换成 `***`。响应体还带 `input_sensitive` / `output_sensitive` / `*_sensitive_type` 字段。

**与"个人定制数据永不入库"的配合（三层）**：

| 层 | 机制 | 保证 |
|---|---|---|
| **① 结构层（主防线）** | 私人层永不入 server（§四）→ **模型侧根本没有私人数据** | 私人记忆、昵称、生日、私密话题**从未离开设备**（除拼进 prompt 的那一段） |
| **② API 层（本次要做）** | Chat 请求带 `mask_sensitive_info: true` | 模型**输出**里形似隐私的内容（编造的邮箱、域名、工号、链接、住址）被替换成 `***` → **不编造事实**（PRODUCT.md §6 原则 5、原则 7） |
| **③ 审计层** | 读响应里的 `output_sensitive` / `output_sensitive_type` | 命中时记一条**不含原文**的审计事件（"本次回复触发敏感信息屏蔽，类型=X"）→ 可查、可统计，**不存原文** |

**⚠️ 必须实测的副作用**：陪伴场景里模型会自然提到"域名 / 链接"（解释一个词、引用一个概念），会被误伤成 `***`。→ **做成 per-session 开关**：默认开；当用户明确说"帮我查一下 X"这类**检索意图**时，临时关掉一帧。
**⚠️ `mask_sensitive_info` 只管输出，不管输入** —— 但按 §四，输入也不含私人数据，所以这条不构成额外风险。

### 3.7 音色策略 + ⭐ 三方映射表

#### 3.7.1 情绪 → MiniMax emotion → 官方表情枚举 → 舵机 / 灯色

> 前两列来自 `18` 号 §7.3（三方对齐表，已核对）；后两列是**我们的设计**，初值待实机标定。官方关键帧锚点取自 `server/internal/model/value_constant.go:15` 的 `DefaultDanceData` 第 1 个关键帧：`yawServo{angle:0, speed:910}`、`pitchServo{angle:450, speed:910}`、`leftRgbColor:"#AAAAAA"`、`rightRgbColor:"#AAAAAA"`、`durationMs:1648`。
> ⚠️ **未取得**：334 256 字符的 `DefaultDanceData` **只读到第 2 个关键帧**，完整的官方动作库**未逐帧读完** → 舵机/灯色初值不是从官方库抄的，是设计初值。

| 我们的情绪维度 | MiniMax `emotion` | 官方 mood 串 | 固件枚举 | 设备通道 | 舵机初值 yaw/pitch (°, speed) | 灯色初值 (左/右) | 备注 |
|---|---|---|---|---|---|---|---|
| `neutral` 常态 | `calm` | `neutral` | `Neutral` | 情绪串 | 0 / 0 (600) | `#AAAAAA` / `#AAAAAA` | 默认档，官方锚点值 |
| `happy` 开心 | `happy` | `happy` | `Happy` | 情绪串 | -8 / +6 (800) | `#F2C14E` / `#F2C14E` | 主力档 |
| `excited` 兴奋 | `happy` | `laughing` | `Happy` | 情绪串 + 几何 | -14 / +12 (1000) | `#F2A93B` / `#F2A93B` | 与 happy 同枚举，靠几何+舵机区分 |
| `soft` 温柔 | `whisper`→降级 `calm` | `relaxed` | ⚠️ `Neutral` | **几何路径** | 4 / -4 (500) | `#8FB8DE` / `#8FB8DE` | `whisper` 仅 `speech-2.6-*` 支持（官方原文）→ 用 2.8 必须降级 |
| `thinking` 思考 | `fluent`→降级 `calm` | `thinking` | ⚠️ `Neutral` | **几何路径** | -6 / +2 (450) | `#9AA0A6` / `#9AA0A6` | `fluent` 仅 `speech-2.6-*` 支持（官方原文） |
| `sad` 难过 | `sad` | `sad` | `Sad` | 情绪串 | 2 / +10 (450) | `#6B7A8F` / `#6B7A8F` | — |
| `comfort` 委屈 | `sad` | `crying` | `Sad` | 情绪串 | 2 / +12 (420) | `#6B7A8F` / `#6B7A8F` | 与 sad 同枚举 |
| `angry` 生气 | `angry` | `angry` | `Angry` | 情绪串 | 0 / -8 (900) | `#C0392B` / `#C0392B` | 陪伴场景极少用 |
| `fearful` 害怕 | `fearful` | `shocked` | ⚠️ `Neutral` | **几何路径** | -6 / -6 (700) | `#7A5C8E` / `#7A5C8E` | — |
| `disgusted` 嫌弃 | `disgusted` | `confused` | ⚠️ `Neutral` | **几何路径** | 8 / -4 (600) | `#7D8B6A` / `#7D8B6A` | 语义勉强 |
| `surprised` 惊讶 | `surprised` | `surprised` | ⚠️ `Neutral` | **几何路径** | -2 / -10 (850) | `#E8C547` / `#E8C547` | **陪伴高频情绪但固件不支持** → 必须几何 |
| `silly` 俏皮 | `fluent`→降级 `calm` | `silly` | ⚠️ `Neutral` | **几何路径** | 12 / +4 (700) | `#D98CB3` / `#D98CB3` | 靠几何 + 歪头 |
| `shy` 害羞 | `calm` | `embarrassed` | ⚠️ `Neutral` | **几何路径** | 6 / +8 (520) | `#E0A9A9` / `#E0A9A9` | — |
| `doubt` 疑惑 | `calm` | `confused` | `Doubt` | 情绪串（`"doubtful"`） | -10 / 0 (600) | `#B0A08C` / `#B0A08C` | `doubtful` 是固件独有串，不在 21 mood 词表 |
| `sleepy` 困倦 | `calm` | `sleepy` | `Sleepy` | 情绪串 | 0 / +14 (400) | `#5C6B7A` / `#5C6B7A` | ⚠️ **有副作用**：显示 "Zzz…" + 停 idle motion + 舵机归位 → 只在真要说晚安时用 |
| `affection` 亲昵 | `happy` | `loving`/`kissy` | ⚠️ `Neutral` | **几何路径** | -6 / +10 (550) | `#F2A2B8` / `#F2A2B8` | — |
| `playful` 玩闹 | `happy`（MiniMax **无** `funny` 值） | `funny`/`winking` | ⚠️ `Neutral` | **几何路径** | 14 / -6 (900) | `#F2C14E` / `#F2C14E` | 只能靠 happy + 文本 + 动作 |
| `confident` 得意 | `happy` | `confident` | ⚠️ `Neutral` | **几何路径** | -12 / -4 (700) | `#C9A227` / `#C9A227` | — |
| `delicious` 满足 | `happy` | `delicious` | ⚠️ `Neutral` | **几何路径** | 4 / +6 (600) | `#E0A458` / `#E0A458` | — |

**这张表的四条硬约束**（与 `18` 号 §7.3 一致）：
1. MiniMax 的 9 个 `emotion` 与我们的情绪维度**不是一一对应**：`fluent`/`whisper` 是语用标签（不对应表情）；`playful` 在 MiniMax 侧**根本没有值**。
2. ⚠️ **`speech-2.8-*` 不支持 `whisper`**，`fluent` 只在 `speech-2.6-*` 有（官方原文）→ **`soft` 与 `thinking` 两档必须显式降级，不能默默发模型不认的值**。→ `server/internal/minimax/emotion.go` 的 `ResolveTTSEmotion` 负责这件事。
3. 官方固件 6 个枚举只覆盖 21 个 mood 中的 8 个；`surprised`/`thinking`/`embarrassed`/`confused` 这类陪伴高频情绪**固件全不支持** → **必须实现 `ControlAvatar (0x03)` 几何路径**，否则表情永远只有 6 种。
4. `sleepy` 有副作用 → 只在真要说晚安时用。

**舵机/灯色的承载格式**：官方关键帧 JSON 里已经同时带 `leftEye/rightEye/mouth`（几何）、`yawServo/pitchServo`（角度+速度）、`leftRgbColor/rightRgbColor`（灯色）、`durationMs`（时长）——**官方 server 的 `DefaultDanceData` 就是这套模型的现成样本**（`server/internal/model/value_constant.go:15`）。Go 侧的 `model.DanceData`（`server/internal/model/expressionData.go:35-42`）只有几何 + 舵机 + 时长，**缺灯色**；`model.MotionData`（`:23-27`）只有舵机。→ 我们新建 `model.EmotionFrame` 时**补上灯色字段**，并直接沿用官方 JSON 字段名（设备端已经认这套名字）。

#### 3.7.2 音色策略

- **音色是数据驱动的，不能硬编码** —— 这是官方自己踩过的坑并修掉的（`26` 号 §5.4 原文 "resolve TTS voices from the XiaoZhi voice list instead of assuming English"；官方实现在 `server/internal/service/agent.go:174-219` 的 `resolveTemplateTtsVoice`，用 `voiceID`/`voiceName` 反查真实 voiceId）。
- **我们的做法**：人格包只声明**音色配方名**（`expression.voice.profile`，例如 `qiqi_warm`），**不直接写 MiniMax 的 voice_id**。server 侧有一张 `voice_profiles.yaml` 把配方名翻译成 MiniMax 参数。
- **配方表要能从 MiniMax 拉**：官方文档明确说音色全集可在 "System Voice ID List" 页查看，或用 **Get Voice API**（`/api-reference/voice-management-get`）程序化获取。→ **该 API 的完整路径本轮未逐字读取，记为"未取得"**。
- **⭐ MVP 决策：不依赖未取得的端点**。MVP 阶段**手工维护** `voice_profiles.yaml`（音色 id 从官方 System Voice ID List 抄，示例 id 见 §3.4.1 官方原文：`Chinese (Mandarin)_Lyrical_Voice`、`Chinese (Mandarin)_HK_Flight_Attendant`、`male-qn-qingse`、`female-chengshu`、`female-tianmei` 等）。→ 把"音色表拉取"列为后续增强。
- **命名不带英语假设**：官方 `parseTtsVoice` 的默认语言写死 `"en"`（`server/internal/service/agent.go:221-238`）—— 这是我们要**避免**的。我们的 `voice_profiles.yaml` 显式带 `language_boost`，不靠猜。

### 3.8 `timbre_weights`：人格包怎么指定音色

**官方原文**：`voice_setting.timbre_weights` 是数组，每项 `{voice_id, weight}`；`weight` 范围 `[1, 100]`；**最多混 4 个音色**；权重越高越像该音色。⚠️ **关键细节**：官方原文写"To apply mixed voices, configure the `timbre_weights` parameter and **leave `voice_id` empty**" —— **混音时 `voice_setting.voice_id` 要留空**。

**人格包侧**（`personas/enfp.json`）：
```yaml
expression:
  voice:
    profile: qiqi_warm        # 配方名，不直接写 voice_id
    emotion_enabled: true
```
**server 侧配方表**（`personas/voice_profiles.yaml` 或 server 配置，随人格包热更新）：
```yaml
qiqi_warm:
  voice_setting:
    voice_id: ""                    # 混音时留空
    timbre_weights:
      - {voice_id: "Chinese (Mandarin)_Lyrical_Voice", weight: 70}
      - {voice_id: "female-chengshu", weight: 20}
      - {voice_id: "female-tianmei", weight: 10}
    speed: 1.0
    vol: 1.0
    pitch: 0
  audio_setting:
    sample_rate: 16000
    format: opus
    channel: 1
  language_boost: Chinese
```
**server 侧硬校验**（`server/internal/minimax/emotion.go` 或独立的 `voice.go`）：
- `len(timbre_weights) <= 4` → 超了直接拒绝并记日志
- 每个 `weight` ∈ [1, 100]
- 混音时 `voice_id` 必须为空；不混音时 `voice_id` 必须非空
- `emotion` 必须在九值枚举内，且与当前 `model` 兼容（2.8 不给 `whisper`/`fluent`）

### 3.9 不做 Realtime 的后果与补偿

**决定**：**不接 MiniMax Realtime**（端点本身在 `18` 号 §4.4 记为"未取得"，官方 API Reference 索引里也没有 realtime 页）。走 **Chat（`/v1/text/chatcompletion_v2`）+ TTS WS（`/ws/v1/t2a_v2`）两段式**。

| 后果 | 严重度 | 补偿 |
|---|---|---|
| **首字延迟 = Chat TTFT + TTS 首包**，比 Realtime 多一跳 | 中 | ① Chat SSE **首个 delta 立刻** `task_continue`（不等全文）；② `continuous_sound: false`（切句并发，官方明说 lower latency）；③ **TTS WS 连接预热**：设备连上 server 时，server 保持 1 条 MiniMax TTS WS 常连，省掉握手 + `task_start` 往返 |
| **不能真正打断（barge-in）** | 中 | 设备端**本地**做：播放中再次触发唤醒 → **本地立刻静音**（不等网络）+ 发 `RequestChat`；server 侧收到新的 `RequestChat` → 主动 close 当前 TTS WS（官方原文：失败时必须关连接，正常结束也 `task_finish` + close）→ 设备收到"流结束"标记后清播放队列。**本地静音是零延迟的，用户感知不到打断延迟。** |
| **无原生 ASR** | **高** | §3.5：MVP 先不做 ASR（本地事件触发）；ASR 单列里程碑（server 侧 STT 端点未取得 / 设备端 ESP-SR 未评估） |
| **两段式更容易"话说到一半被切断"** | 低 | Chat 侧用 `max_completion_tokens: 512` 限长；TTS 侧按句 `task_continue`，保证每句独立完整 |

**为什么仍然够用（对着 PRODUCT.md 的硬指标算）**：

| 指标（PRODUCT.md §6 原则 4） | Realtime | 两段式 | 结论 |
|---|---|---|---|
| 唤醒 → 第一个表情变化 ≤ 300ms | 网络往返 | **本地产生，不等网络**（唤醒瞬间本地切"在听"表情 + LED + 小偏头） | ✅ **本地 0ms**，网络无关 |
| 用户说完 → 它回应 ≤ 700ms | 一跳 | Chat TTFT + TTS 首包 + 网络 | ⚠️ **有风险**。缓解：Flash 模型 + SSE 立即送 TTS + WS 预热 + `continuous_sound: false`。**必须在真机实测**，达不到就要改用"先出一个'我听着呢'的表情 + 语音稍后到"的策略（表情先到，语音跟上） |
| ASR 成功率 ≥ 90%，失败不沉默 > 1.5s | 内建 | 我们自己做 | ⚠️ ASR 未落地前无法验证 |

> ⭐ **关键洞察**：陪伴产品对延迟的敏感点是**"我说了话它多久有反应"**，不是"它说话多快"。**第一段反馈（表情 + LED）由设备本地产生 → 300ms 指标与网络无关地达标**；语音本身慢 200ms 不影响"在场感"。而 ASR 在本地/服务端的具体落点，是唯一还没解决的关键路径。

---

## §四 人格包运行时（放 server 侧还是设备侧？）

### 4.1 ⭐ 结论：**合并必须在设备端；server 侧只做分发与缓存**

| 组件 | 放哪 | 为什么 |
|---|---|---|
| **通用人格包 `personas/enfp.yaml`** | **server 侧托管**（Git 仓库 + 运行时目录），**设备端缓存副本** | 要能被社区 fork、要热更新、要版本回滚 → 需要一个可分发的源。server 是唯一能把"新版人格包"推给所有设备的节点 |
| **个人定制数据 `private/persona.local.yaml`** | **只在设备端**（或 App 端，见下） | `18` 号 §6.4 硬规则第 1 条原文：「`private/` 目录**不接后端、不接 Git、不进任何日志**。我们的 VPS 上，私人层只存在于**小栈本机**」 |
| **三段合并（private > personas > DEFAULT_*）** | **设备端做** | ⭐ server 根本看不到 `private/` → 在 server 侧合并只能得到 `personas + DEFAULT`，**覆盖优先级失效** |
| **MiniMax 调用（Chat / TTS）** | **server 侧** | API key 不能放设备端（设备会丢、会被拆、会被刷写） |
| **对话上下文 / 私人记忆的拼装** | **设备端** | 同上：记忆在设备端（`private/memory/`） |

**⭐ 由此推出的关键链路（server 不持有私人数据）**：

```
设备端                              server                        MiniMax
──────                              ──────                        ───────
1. 拉 personas/enfp.yaml  ◄──────── GET /stackChan/v2/persona  （带 version/etag）
2. 读 private/persona.local.yaml
3. 三段合并 → system_prompt
4. 读 private/memory/* → 拼上下文
5. POST /stackChan/ai/chat
   { system_prompt, messages, ... } ─────►  6. 不落盘、不进日志
                                          7. Chat SSE ─────────►  /v1/text/chatcompletion_v2
                                          8. TTS WS   ◄─────────  /ws/v1/t2a_v2
                                          9. Ogg de-mux → 裸 Opus 包
                                             │ 语音面 WS
                                             ▼
10. 收到 Opus 包 → 解码 → 播放
11. 收到 0x03 / 0x04 → 变脸 / 动舵机
```

**⚠️ 必须说清的一个边界**：第 5 步把 `system_prompt` 和上下文**发给了 server**（进而发给 MiniMax）。
- 这**不违反** `18` 号 §6.4 第 2 条 —— 该条原文允许「私人层内容**只在本地拼接进 prompt**，不作为独立字段发给 **MiniMax 之外的任何服务**。我们只用 MiniMax」。server 是**我们自己的**服务，不是第三方。
- 但要守住两条硬规则：① **server 不落盘**（不进数据库、不进日志、不进缓存文件）；② **prompt 与上下文不经过任何会记录 body 的组件**（官方 server 的 `g.Log().Debugf` 打原始响应那种习惯不能带过来 —— 见 §2.5）。
- 如果要做到"连自己的 server 都不看"，就只能把 MiniMax key 放设备端 → **不可接受**（安全与可维护性）。→ **这是本架构里唯一无法做到端到端私密的环节，明确登记在 §九 R-6。**

### 4.2 人格包在 server 侧的形态（加载 / 热更新 / 版本 / 回滚）

| 机制 | server 侧落法 | 依据 |
|---|---|---|
| **存放** | `server/resource/personas/index.yaml` + `enfp.yaml`（随 server 仓库走，可被社区 fork） | `18` 号 §6.1 的目录组织 |
| **加载** | server 启动时读 `index.yaml` → 按 `entrypoint` 加载 `enfp.yaml` → 校验 `schema_version` | `18` 号 §6.2 |
| **热更新** | 每 60 秒比对 `personas/*.yaml` 的 `mtime + hash`；变了就重新加载 | `18` 号 §6.2 原文（"人格包是产品配置，改完不该重启服务"） |
| **版本** | `version: 1.0.0`（语义化）+ `schema_version: 1`（字段结构版本）；**`schema_version` 变了才需要迁移代码** | `18` 号 §6.2 原文 |
| **回滚** | 内存保留上一份快照；热更新加载失败（YAML 语法错 / schema 不符）→ **回滚到上一份并记日志，绝不半加载** | `18` 号 §6.2 原文：「人格包是"机器人的人格"，加载坏了不能让机器人变哑巴」 |
| **生效边界** | 人格包**只影响 system prompt 组装与表现参数**，**不改写已存的记忆** | `18` 号 §6.2 原文（mem0 的 ADD-only 原则） |
| **分发给设备** | `GET /stackChan/v2/persona` 返回 YAML 原文 + `version` + `etag`；设备侧同样保留上一份并可回滚 | 我们新增 |
| **后台操作** | 管理后台能"查看当前版本 / 手动回滚到 v1.0.0 / 灰度到某台设备" | 我们新增（§六） |

### 4.3 场景 D（设备不在手边，App 直接说话）的私人层归属

PRODUCT.md §4 场景 D 要求「设备不在线，但 App 里的它还在，人格、记忆、说话方式一致」。这与"私人层只在设备端"冲突。

**三个候选**：

| 方案 | 做法 | 代价 |
|---|---|---|
| **A. 设备是唯一真源**（**推荐起步**） | App 端的人格/记忆是**只读缓存**，设备在线时同步；设备离线时 App 只能回看历史，不能新建对话 | 放弃"离线时 App 直接说话"的部分能力 |
| B. 私人层点对点同步 | 设备与 App 在同一局域网时直连同步（不经 server） | 要写一套 LAN 同步协议（我们已有 LAN 帧协议可复用，`26` 号 §六） |
| C. 私人层上 server（端到端加密） | 违反"永不入库" | ❌ 与 PRODUCT.md §6 原则 7 直接冲突 |

**推荐 A 起步**。理由：场景 E（修完之后关系不断）才是我们的独占承诺（PRODUCT.md §9-5），而场景 D 是"体验更好"不是"承诺"。→ 登记为 §九 待拍板项。

### 4.4 "人格包必须开源可 fork"的落地

| # | 机制 | 落法 |
|---|---|---|
| 1 | **仓库层面** | `personas/` 在**公开仓库**；`private/` 写进 `.gitignore`；CI 加一条断言（`git ls-files private/` 必须为空）→ **"永不入库"从纪律变成 CI 检查** |
| 2 | **许可层面** | fork 官方 server 必须保留 `Copyright (c) 2026 M5Stack Technology CO LTD` 与 MIT 文本（`26` 号 §十一 原文要求）；我们自己的 `personas/` 另声明许可 |
| 3 | **格式互操作** | 人格包带 `card_v2_compatible: true`，可一键导出 **Persona Card V2 JSON**（`18` 号 §6.5）→ 社区可导入 SillyTavern 使用；也能导出 MiniMax system prompt |
| 4 | **资产许可** | `assets_manifest` 逐条记 `{path, license, source, commercial_use, attribution_required}`（`18` 号 §6.6）；⚠️ **Twemoji 是 CC-BY 4.0，使用必须署名**（`18` 号 §7.2 原文） |
| 5 | **schema 演进** | server 只接受 `schema_version` 匹配的包；未知字段忽略；`schema_version` 变更走迁移 |
| 6 | **社区分叉** | `personas/index.yaml` 声明 `id / name / version / entrypoint` → 第三方可以提交自己的包，server 侧只需把它放进 `personas/` 目录 |

---

## §五 情绪状态机 + 表情映射（server 侧）

### 5.1 情绪从哪来

| 来源 | 具体信号 | 采集位置 |
|---|---|---|
| **① 对话轮次** | Chat 的 tool call `report_emotion{emotion, intensity}`（§3.3）；兜底是回复首行的 `[[emotion:xxx]]` 标记 | `server/internal/minimax/chat.go` 的流式解析 |
| **② 时间** | `quiet_hours`（23:00–07:00，默认）→ 强制 `calm`/`sleepy`；长时间无交互 → `sleepy` → `neutral` | `server/internal/service/emotion.go` 的定时衰减 |
| **③ 设备状态** | 三区触摸、NFC、电量、固件上报的 idle/在听/在说状态 | 设备 → 控制面 WS（`0x1E RequestChat` 或新增状态帧）→ server |
| **④ 用户行为** | 对话频率、连续追问次数、长静默时长、连续多轮无回应 | server 从会话记录统计 |

### 5.2 状态机在哪跑

**⭐ 在 server 侧**（`server/internal/service/emotion.go`，类型 `EmotionStateMachine`）。理由：
- server 是唯一同时看得到「对话轮次 + TTS 情绪 + 设备状态」的汇聚点。
- 设备端**只做第一段本地反馈**（唤醒瞬间本地切"在听"表情 + LED + 小偏头）—— 这是为了满足"唤醒 → 第一个表情变化 ≤ 300ms"（PRODUCT.md §6 原则 4）而**必须本地化**的一段，**不是**状态机。
- 状态机在 server 侧还有一个好处：**iOS 端能看到"它现在什么心情"**（场景 D 也要这个状态）。

### 5.3 状态机的判定规则

```
优先级（高 → 低）：
  用户显式指令  >  当前话语情绪（tool call）  >  上一帧情绪（保持 + 衰减）  >  时间/环境基线

迟滞（hysteresis）：
  最小驻留 800ms          —— 防止每帧跳
  同档不重发              —— 表情帧不重复推
  强度线性衰减            —— 情绪随时间回到基线（半衰期 ~20s）

硬约束：
  不产生任何可量化指标    —— 不输出"连续 N 次""情绪值 87"（PRODUCT.md §6 原则 2）
  sleepy 有副作用          —— 只在真要说晚安时用（会关掉 idle motion、归位舵机）
  angry / disgusted 克制   —— 陪伴场景极少用，避免"说教"感
```

### 5.4 怎么决定下一帧表情

```
状态机输出 (mood, intensity, hold_ms)
        ↓
查 EmotionFrame 表（server/internal/model/emotion_frame.go + personas 覆盖）
        ↓
得到三份载荷：
  ① 几何 JSON（表情）  → model.ExpressionData   → 0x03 ControlAvatar
  ② 舵机 JSON（姿态）  → model.MotionData(+rgb) → 0x04 ControlMotion
  ③ 灯色（情绪第二通道）→ 同一份 0x04 载荷里的 leftRgbColor/rightRgbColor
        ↓
server 经控制面 WS 推给设备（stackChanSendMessage，server/internal/web_socket/web_socket.go:790）
```

**载荷格式直接复用官方的字段名**（设备端已经认这套名字）：
- 几何：`model.ExpressionData`（`server/internal/model/expressionData.go:8-21`）—— `type` / `leftEye` / `rightEye` / `mouth`，每项 `x/y/rotation/weight/size`
- 舵机：`model.MotionData`（`:23-27`）—— `type` / `pitchServo` / `yawServo`，每项 `angle/speed/rotate`
- 灯色：**官方 Go 结构体里没有**，但官方 `DefaultDanceData` 的实际 JSON 里有 `leftRgbColor` / `rightRgbColor`（`server/internal/model/value_constant.go:15`）→ 说明**设备端是逐字段读 cJSON 的**。→ **我们照抄这两个字段名加进 `0x04` 载荷**，设备端做一个小 patch 读它们。

> ⚠️ **协议缺口（需固件 patch）**：**官方协议里没有独立的"灯色"帧**。灯色只能搭 `0x04 ControlMotion` 的 JSON 走（字段名照抄官方关键帧）。设备端固件需要新增"读 `leftRgbColor`/`rightRgbColor` 并驱动 12 颗 RGB LED"的逻辑（12 灯分两排，左右各 6 颗 —— `17` 号 §3.7 硬件原文「two rows totaling 12 RGB LEDs」）。

### 5.5 与舵机动作、灯色的协同

| 通道 | 物理载体 | 硬件事实 | 我们的用法 |
|---|---|---|---|
| 表情 | 320×240 LCD 的脸 | 6 个参数化情绪 + 5 个装饰器位图（`17` 号 M2-1 实测） | 几何路径覆盖枚举外的 mood |
| 舵机 | 2 颗 Feetech SCS0009，**半双工串行总线**（不是 PWM） | ⭐ **yaw ±128° / pitch 3°~87°**（`37` 号源码实测 `hal_servo.cpp:340,349`；⚠️ **官方 README 的「水平 360° 连续 / 垂直 90°」是营销口径，以源码为准**） | 姿态：歪头、点头、归位 |
| 灯 | 2 排共 12 颗 RGB LED | `17` 号 §3.7 原文 | 情绪第二通道（`17` 号 §3.8：官方 `animation.cpp` 已把 `leftRgbColor/rightRgbColor` 放进关键帧） |

**协同三原则**：
1. **表情先于动作**：先变脸（0x03），再动身（0x04），间隔 ~80ms → 观感是"先有反应，再有姿态"。
2. **动作幅度随强度缩放**：`intensity=0.3` → 舵机角度 × 0.3、速度 × 0.7 → 陪伴产品的动作应该是"轻轻偏一下头"，不是"大幅摇摆"。
3. **灯色不抢戏**：灯色是**第二通道**，饱和度低、亮度随情绪强度轻微变化；不与脸部表情矛盾（脸 sad 时灯不暖）。

**不做**：3D 姿态、连续路径动画、舞蹈库编排（PRODUCT.md §5.2 明确不做 3D 与舞蹈）。

---

## §六 ⭐ 功能减法：剥离官方 server 的哪些模块

### 6.1 逐组裁定

| 组 | 官方路由 | 裁定 | 理由 | 连带影响 |
|---|---|---|---|---|
| **`user` (v2)** | `/stackChan/v2/user/login`、`/user/registration`、`/user` | **保留 + 改造** | 账号是我们自己的（§2.2 方案 B） | 删 8 个远端函数（~140 行）；`user` 表加 `password_hash`；邮箱改可选 |
| **`device` (v2)** | `/stackChan/v2/device/activate_bind`、`/device/bind`、`/device/unbind`、`/device/update`、`/devices`、`/device/agent/restore` | **保留 + 改造** | 设备绑定是我们的核心资产关系 | 删 `validateM5StackDevice`（工厂 MAC 校验，改为本地白名单）；`/device/agent/restore` **失去意义**（没有小智 agent 了）→ **剥离该端点**，改绑到"人格包重置"语义（重置为默认人格包，不是恢复小智 agent） |
| **`device` (v1)** | `/stackChan/device/...` | **剥离** | v2 已覆盖全部能力 | 删 `api/device/v1` + `internal/controller/device/device_v1_*` + `dao/device` 的 v1 用途 |
| **`stackchandevice` (v2)** | `/stackChan/stackchandevice/...` | **保留**（或并入 device v2） | 设备↔用户信息查询 | 可合并到 `device` v2，减少 API 面 |
| **`admin`** | `/admin/stackChan/login` + app CRUD | **降级** | 后台是我们自己做的，只保留真需要的 | 删 app 商店 CRUD（`admin_v1_add_app` / `delete_app` / `get_app_list` / `update_app`）；保留登录 + 设备/用户/人格包/资源管理 |
| **`file`** | `POST /stackChan/file`（上传）、`GET /file/*filepath`（静态服务） | **降级保留** | 表情包与固件分发要用 | ⚠️ **必须保留官方的 `os.Root` 穿越/符号链接防护**（`server/internal/service/file_path.go:21-53`、`:91-115`、`:128-158`）——**不要自己重写这段**；只改存储根目录与鉴权 |
| **`appstore`** | `GET /stackChan/apps` | **降级**（**保留空实现**） | PRODUCT.md §5.2 说"不做应用商店"指的是 App 页面；但**设备启动流程可能请求这个端点**（`26` 号 §八 列出 HAL 拼装端点含 `/stackChan/apps`） | ⚠️ **剥离会让设备启动异常** → 保留端点，**固定返回空数组**，不建 `app_store` 表、不做 CRUD。成本 ≈ 20 行 |
| **`dance` (v1, v2)** | `/stackChan/dance`、`/stackChan/v2/dance`、`/danceData` | **降级** | 舞蹈不做，但**关键帧数据模型要留着** | ⚠️ **剥离对设备无影响**（我们不做 `0x14 Dance` 帧，设备不会请求）；但 **`model.DefaultDanceData`（`server/internal/model/value_constant.go:15`，334 256 字符）是我们表情/动作/灯色关键帧的格式范本 → 不能删，要迁到 `emotion_frame` 模块** |
| **`post`** | `/stackChan/post`、`/postComment` | **剥离** | 社区动态不做 | 删 `device_post`、`device_post_comment` 两张表（DDL 同步删）+ 6 个 controller |
| **`friend`** | `/stackChan/friend` | **剥离** | 附近设备不做 | 删 `device_friend` 表 + controller |
| **`pano`** | `/stackChan/pano` | **剥离** | 全景图不做 | 删 `device_pano` 表 + controller |
| **`xiaozhi`** | `/stackChan/xiaozhi/token`、`/token/refresh`、`/generateLicenseToken` | **整组剥离** | 彻底不接小智 | 删 `server/internal/xiaohi/`（22 KB 代理层 + 3 个测试）、`server/internal/model/xiaozhi/`、`server/api/xiaozhi/`、2 张配置键。⚠️ **`generateLicenseToken` 是官方明文吐 license token 的接口**（`server/internal/controller/xiaozhi/xiaozhi_v1_get_xiao_zhi_generate_license_token.go:19-23`）→ 剥离即消除该弱点 |

### 6.2 剥离后的 API 面

**保留（改造后）**：
```
POST   /stackChan/v2/user/login
POST   /stackChan/v2/user/registration          （email 可选）
GET    /stackChan/v2/user
GET    /stackChan/v2/devices
POST   /stackChan/v2/device/activate_bind       （本地白名单，不再查工厂）
POST   /stackChan/v2/device/bind
POST   /stackChan/v2/device/unbind
PUT    /stackChan/v2/device/update
GET    /stackChan/v2/persona                    （新增：人格包分发）
POST   /stackChan/ai/chat                       （新增：iOS 端"设备不在手边"）
WS     /stackChan/ws?deviceType=StackChan       （控制面）
WS     /stackChan/ws?deviceType=App             （控制面）
WS     /stackChan/voice                         （新增：语音面）
GET    /stackChan/apps                          （降级：恒定空数组）
POST   /stackChan/file                          （保留）
GET    /file/*filepath                          （保留）
POST   /admin/stackChan/login
（+ 我们自己的管理后台 API）
```

**删除**：`/stackChan/v2/dance*`、`/stackChan/post*`、`/stackChan/friend`、`/stackChan/pano`、`/stackChan/xiaozhi/*`、`/stackChan/v2/device/agent/restore`、`/stackChan/device/*`（v1）、admin 的 app CRUD。

**数据库最终表**：`user`（+`password_hash`/`email`/`password_updated_at`）、`device`、（可选）`persona_version`（人格包版本记录）。
**删表**：`app_store`、`device_dance`、`device_friend`、`device_pano`、`device_post`、`device_post_comment`。

### 6.3 管理后台还剩什么

**原则**：后台只服务"让这台设备正常工作"，**不做运营位、不做社区、不做指标面板**（PRODUCT.md §6 原则 2、§5.2）。

| 模块 | 功能 | 说明 |
|---|---|---|
| **设备** | 列表（MAC / 名称 / 绑定用户 / 在线状态 / 固件版本）、解绑、改名 | 在线状态来自 `stackChanClientPool`（`server/internal/web_socket/web_socket.go:73`） |
| **用户** | 列表、停用、解绑其设备 | 停用 = 拒绝签发新 JWT |
| **人格包** | 当前版本、历史版本、回滚、灰度到指定设备、schema 校验结果 | 对应 §4.2 的版本/回滚机制 |
| **模型与音色** | MiniMax key（**只显示后 4 位**）、模型选择、`voice_profiles.yaml` 编辑（带 ≤4 音色 + 权重 1–100 校验）、`emotion_frames` 编辑 | 对应 §3.8、§3.7 |
| **资源** | 表情包 / 固件上传与发布（走 `file` 模块 + 静态服务） | 对应 `OTA_URL` 指向的目录 |
| **运维** | 在线连接数、MiniMax 调用量与计费字符数、错误计数、**日志查看** | ⚠️ 日志**必须已过滤** prompt / 私人数据（§2.5） |

**明确不做**：社区内容审核、app 商店、舞蹈库、全景图、附近设备、用户行为分析、任何"陪伴天数 / 对话次数 / 亲密度"面板。

---

## §七 部署形态

### 7.1 拓扑候选与评估

| 拓扑 | 延迟 | 稳定性 | 成本 | 复杂度 | 与"陪伴要低延迟"的匹配 |
|---|---|---|---|---|---|
| **A. 公网 VPS**（一台便宜 VPS + Docker Compose） | 设备→VPS 单程 ~30–80ms（就近地域）；VPS→MiniMax ~50–150ms | 高（我们自己控制版本与重启） | 低（3C4G 足够，~¥30–60/月） | 低（官方已有 `manifest/docker/Dockerfile` + `manifest/deploy/kustomize/`） | ⭐ **推荐主线**。语音链路是"设备→VPS→MiniMax→VPS→设备"，两跳，但两跳都很短 |
| **B. 云托管**（Cloud Run / Fly.io / Railway） | 同 A（托管商有边缘区域） | 中高（冷启动、平台配额） | 中（按量 + 常驻实例） | **高**（WS 长连接 + 定时任务 + MySQL 外置，托管平台的约束多） | 次选。GoFrame 的 `g.Server()` + `sync.Map` 连接池 + `os.Root` 文件服务在容器托管下要额外适配 |
| **C. 家里机器 + cloudflared 隧道** | 家里设备→家里机器 ~5ms；家里机器→MiniMax ~150–250ms（取决于家里上行） | **低**（家里断电/断网 = 服务不可用；公网 IP 靠隧道保活） | 最低（家里电费） | 中（要维护隧道进程 + 家里机器常开） | ⚠️ **不适合做主服务**，适合做**家里设备的本地回落**或**内网优先部署** |
| **D. 局域网直连** | <5ms | 高（无公网依赖） | 0 | 低 | ⭐ **只适合控制类指令**（§7.3），不能承担对话类 |

**⭐ 推荐拓扑**：

```
                    ┌──────────────────────────────┐
   iPhone (App) ───┤  VPS: our-stackchan-server    │──► MiniMax (api.minimax.io)
        │          │   ├─ control WS  /stackChan/ws │
        │          │   ├─ voice   WS  /stackChan/voice
        │          │   ├─ HTTP API  /stackChan/v2/*
        │          │   └─ static    /file/*
        │          └──────────────┬───────────────┘
        │  (LAN, <30ms)           │ (公网, ~50ms)
        │                         │
        └──── 0x03/0x04 控制优先 ──┴──► 设备（StackChan）
                                       │
                                  LAN fallback:
                                  cloudflared 隧道 → 家里机器上的 server
```

- **主线 A**：VPS 跑我们的 server + MySQL，前面挂 Caddy 自动签 Let's Encrypt → `https://api.stackchan.xxx`（`wss://` 同源）。
- **回落 C**：家里那台设备如果不想把家里网络暴露，直接连 VPS 即可（公网出站）；**cloudflared 的价值在于"我们想在屋里跑 server"** —— 那时用隧道把家里的 `localhost:12800` 暴露成一个公网域名。→ **不作为主线**。
- **D（LAN）不是独立拓扑，是路由策略**（下节）。

### 7.2 数据库选型

| 选项 | 评价 |
|---|---|
| **VPS 上 Docker 跑 MySQL 8** | ⭐ **推荐**。官方 DDL 就是 MySQL 方言（`server/check_list/create_mysql_database.sql`：`bigint auto_increment`、`tinyint(1)`、`on update CURRENT_TIMESTAMP`、`json` 列），换 SQLite/PG 要改 DDL + 换 GoFrame driver + 重测。容器化（有现成 Dockerfile），数据不出 VPS |
| 容器 vs 裸装 | 容器。`server/manifest/docker/Dockerfile` 已有基础；数据库同样容器化，加 `mysqldump` 定时任务 |
| 托管 MySQL | ❌ 不推荐：出网延迟、成本、数据出境；而且**我们的数据量极小**（设备 + 用户 + 人格包版本），托管是浪费 |

**备份**：每日 `mysqldump` → 对象存储或另一台机器，保留 7 天。⚠️ 备份含 `user.password_hash` → **备份文件按敏感数据对待**（加密 + 限制访问）。

### 7.3 ⭐ 路由策略：控制类走 LAN，对话类走云端

依据 `26` 号 §8.3 原文：「`controlMotion (0x04)` **官方已有**……v1.6.0 新增 LAN 二进制协议 + `appLanAddress (0x1B)` → iPhone 可告知自身局域网地址给设备。官方自己把视频/远控改成 **LAN 优先 + 云回落**，等于**官方承认云端往返延迟不可接受**。」

**设备端怎么知道 App 的局域网地址（`0x1B appLanAddress`）**：
1. App 与设备都连着控制面 WS（`server/internal/web_socket/web_socket.go:203-225` 的 App 分支）。
2. App 发 `0x1B`（payload = 自己的局域网 IP:端口）→ **server 原样转发给设备**（`readAppClientMessage` 里加一个 `case AppLanAddress:` 分支，与 `ControlAvatar/ControlMotion` 同款，参照 `web_socket.go:553-568`）。
3. 设备收到后**缓存**该地址（nvs / `secret_logic`）→ 之后的控制类指令**直连 App 的 LAN 地址**，不再绕云。
4. LAN 帧格式用官方现成的：20 字节头、magic `0x53`、大端、payload ≤ 65535、头含 session 8 字节 + sequence 4 字节（PRODUCT.md §8 / `26` 号 §六）。
5. 云端作为回落：LAN 不可达（不在同一网段 / App 不在线）→ 退回控制面 WS。

**分类结果**：

| 指令类别 | 帧 | 通道 | 延迟目标 |
|---|---|---|---|
| **手势控舵机**（App 推 `0x04`） | `0x04 ControlMotion` | ⭐ **LAN 优先**，云端回落 | <30ms（`26` 号 §8.3） |
| **表情控制**（App 推 `0x03`） | `0x03 ControlAvatar` | LAN 优先，云端回落 | <30ms |
| **设备名 / 在线状态** | `0x0D`/`0x0E`/`0x16`/`0x17` | 云端（控制面 WS） | 无所谓 |
| **对话链路**（唤醒→ASR→Chat→TTS→播放） | 语音面 WS + `0x1E` | ⭐ **只能走云端**（MiniMax 在公网） | 见 §3.9 |
| **对话中的情绪表情**（server 推 `0x03`/`0x04`） | 同上 | 云端 | ⚠️ 有网络延迟 |
| **固件 OTA** | HTTP | 云端（`OTA_URL` 独立 CDN） | 无所谓 |

⭐ **⭐ 关键设计（把 300ms 指标与网络解耦）**：
> 对话链路里的**第一段表情由设备本地产生** —— 唤醒瞬间本地切"在听"表情 + LED + 小偏头，**不等到 server**。
> server 回来的情绪表情（"开心""难过"）是**第二段**，走云端，延迟可接受。
> → **"唤醒到第一个表情变化 ≤ 300ms"（PRODUCT.md §6 原则 4）由本地逻辑保证，与网络无关。**

### 7.4 配置与密钥

**原则**：**配置进 Git（占位），密钥永不进 Git。**

| 文件/机制 | 内容 | 是否进 Git |
|---|---|---|
| `server/manifest/config/config.yaml` | 只有占位与结构（官方就是空值模板，`server/manifest/config/config.yaml:2-41`） | ✅ 进 |
| `server/hack/config.yaml` | 本地调试用，**不放真值** | ✅ 进（本地覆盖文件应 gitignore） |
| `.env`（部署机） | 全部真值 | ❌ **不进**（`.gitignore`） |
| Docker/K8s Secret | 全部真值 | ❌ 不进 |

**注入方式（确定）**：⚠️ **GoFrame v2 的 `g.Cfg()` 是否支持环境变量覆盖 —— 本轮未核实**。→ **不依赖框架特性**：我们自己在 `server/internal/config/env.go` 实现一个 `envOverride(key string) (string, bool)`，在**所有读配置的地方**优先读 `os.Getenv`：
- `service.GetJwtSecret()`（`server/internal/service/admin_user.go:26-30`）
- `utility.loadRSAKeySet()`（`server/utility/rsa.go:57-67`）
- 新的 `minimax.Config`

**环境变量清单（我们的 fork）**：
```
STACKCHAN_JWT_SECRET              # ≥32 字节随机
STACKCHAN_RSA_SERVER_PRIVATE      # PEM
STACKCHAN_RSA_SERVER_PUBLIC       # PEM
STACKCHAN_RSA_CLIENT_PRIVATE      # PEM
STACKCHAN_RSA_CLIENT_PUBLIC       # PEM
STACKCHAN_ADMIN_USERS             # "username:argon2id_hash" 逗号分隔
STACKCHAN_MINIMAX_API_KEY
STACKCHAN_DB_LINK                 # mysql:root:pass@tcp(...)/stackChan
STACKCHAN_SERVER_URL              # 公网地址，写进固件配置
STACKCHAN_OTA_URL                 # 固件/资源地址
```

**TLS**：优先**前置 Caddy/Nginx 终止 TLS**（自动 Let's Encrypt），GoFrame 只跑明文 HTTP 在本地端口。→ 设备连 `wss://` / `https://`。
⚠️ `ghttp` 自身的证书配置键名**未核实** → 不依赖。

---

## §八 工作量拆解与里程碑

> ⚠️ **不给精确人天**。难度用 S / M / L；规模用"小 / 中 / 大"两档，避免编数字。

### 8.1 模块拆解

| # | 模块 | 做什么 | 产出物 | 依赖 | 难度 | 主要风险 |
|---|---|---|---|---|---|---|
| 1 | **fork 基座** | 拉 `server/` 到我们仓库、保留 MIT 版权声明、跑通 `go build` + 本地 MySQL + `check_list/create_mysql_database.sql` | 可运行的 server 二进制 + DDL | Go 1.26.3 环境、MySQL | **S** | 无（官方代码质量高，测试都在） |
| 2 | **配置与密钥层** | `server/internal/config/env.go`：`os.Getenv` 覆盖；`.env` 模板；密钥生成脚本 | env 读取层 + `.env.example` | 模块 1 | **S** | 漏改一处读取点 → 密钥仍从 config.yaml 读 |
| 3 | **认证层** | 账号本地化（删 8 个远端函数、~140 行）；`user` 表加 `password_hash`；Argon2id；JWT 有效期 30 天 + refresh + `kid` + 轮换；admin 密码改哈希；修 `Exp` 大写键与 `Bearer` 前缀 | 改造后的 `service/user.go`、`service/admin_user.go`、`middleware.go`、新 DDL | 模块 1、2；新增 `golang.org/x/crypto` | **M** | 删远端代码时误删共用函数；JWT 兼容性影响 iOS 端 |
| 4 | **设备绑定与白名单** | 删工厂 MAC 校验；改本地白名单；**WS 准入检查**（只放行已登记且已绑定的 MAC） | `service/device.go` 改造 + `web_socket.go` 准入 | 模块 3 | **S–M** | 准入太严 → 设备连不上；太松 → 没修掉"任意人建档" |
| 5 | **MiniMax Chat 客户端** | SSE 解析、`max_completion_tokens`/`temperature`、`tools` 情绪工具、错误码映射 | `internal/minimax/chat.go` | 模块 2 | **S–M** | SSE 分帧边界；工具参数增量解析 |
| 6 | **MiniMax TTS 客户端 + Ogg de-mux + Opus TOC** | TTS WS 客户端；**Ogg page 解析 → 裸 Opus 包**；TOC 帧长解析；`extra_info.audio_sample_rate` 采用 | `internal/minimax/tts.go`、`internal/voice/ogg.go`、`internal/voice/opus_toc.go` | 模块 2、5 | **M**（⭐ 最易出错的一段） | Ogg 跨包/跨 page 的 packet 拼接；TOC 帧长表错 → 设备解码器重开失败 |
| 7 | **语音面 WS 端点（server 侧）** | 实现 `BinaryProtocol2/3` 帧、hello 握手、音频收发、JSON 控制消息 | `internal/voiceplane/` | 模块 6 | **M–L** | 要与设备端协议逐字节对齐；WS 长连接并发模型 |
| 8 | **设备侧 MiniMax 协议层** | 固件 patch：新的协议层实现（连我们的 server、`task_start/continue/finish`、`task_continued` → Ogg 拆包 → 裸 Opus 包 → `BinaryProtocol3`）；`application.cc` 切换；`hal_ws_avatar.cpp` 加 `0x1E` | 固件分支 + patch 文件 + 编译产物 | 模块 6、7；IDF 5.5.4 | **L** | MCU 内存/时序；刷机风险；与官方后续版本冲突 |
| 9 | **对话编排** | Chat → 情绪抽取 → TTS → 推设备（音频走语音面、表情走控制面）；并发会话管理；打断处理 | `internal/service/conversation.go` | 模块 5、6、8 | **M** | 延迟叠加；并发设备的状态隔离 |
| 10 | **人格包运行时** | server 侧加载/热更新/版本/回滚/分发；设备侧三段合并；`private/` 隔离（CI 检查） | `internal/service/persona.go` + `personas/` + `private/` 结构 + CI 规则 | 模块 1、9 | **M** | 私人层泄露（最高优先级红线）；热更新半加载 |
| 11 | **情绪状态机 + 帧模型** | `EmotionStateMachine`；`EmotionFrame`（几何 + 舵机 + 灯色）；三方映射表落地；迟滞与衰减 | `internal/service/emotion.go`、`internal/model/emotion_frame.go` | 模块 9 | **M** | 表情抖动；`sleepy` 副作用；灯色字段设备端不认 |
| 12 | **功能减法落地** | 剥离 7 组 + 降级 3 组；DDL 同步；`appstore` 空实现；`DefaultDanceData` 迁移 | 裁剪后的 server 树 + 新 DDL | 模块 1 | **S–M** | 删多了导致设备启动失败（`/stackChan/apps`） |
| 13 | **管理后台** | 设备/用户/人格包版本/音色配方/情绪帧/资源/运维 7 个模块 | 后台（技术栈待定） | 模块 2、3、10、11 | **M–L** | 范围膨胀成"官方后台的复刻" → 违背减法 |
| 14 | **部署** | VPS + Docker Compose（server + MySQL + Caddy）+ 备份 + 监控 | 部署脚本 + 运维手册 | 模块 1、2 | **S–M** | 密钥进 Git；备份泄露密码哈希 |
| 15 | **ASR（第二阶段）** | server 侧 STT 或设备端 ESP-SR | ASR 模块 | ⚠️ **依赖一个未取得的端点** | **L** | ⭐ **最高风险**：MiniMax STT 路径未取得 |
| 16 | **iOS 端对接（他组）** | 登录、设备列表、对话、回看、App↔设备 LAN | SwiftUI App | 模块 3、4、9、13 | **L** | ⚠️ **Mac 未解决 → iOS 端目前只能停在设计稿**（PRODUCT.md §11-3） |

### 8.2 ⭐ MVP 纵切（"设备说话 → MiniMax → 设备表情 + 语音"）

**MVP 定义**：不需要 ASR、不需要 iOS 端、不需要后台完整版，只要一条端到端的纵切跑通。

| # | MVP 必做 | 属于哪个模块 | 完成判据 |
|---|---|---|---|
| 1 | fork 官方 server，跑起来（MySQL + DDL + 配置） | 1、2 | `curl /api.json` 出 Swagger；`/stackChan/v2/user/login` 能注册+登录 |
| 2 | 账号本地化 + Argon2id + JWT 修好 | 3 | 注册→登录→拿 token→带 token 访问 `/stackChan/v2/user` 通 |
| 3 | 设备白名单准入 + activate-and-bind 改本地 | 4 | 设备能带 RSA 凭证连上 WS，未登记 MAC 被拒 |
| 4 | MiniMax Chat（SSE）+ `report_emotion` 工具 | 5 | server 能拿到完整回复 + 情绪标签 |
| 5 | MiniMax TTS WS + **Ogg de-mux** + Opus TOC + 帧长声明 | 6 | 拿到一串裸 Opus 包，能在 PC 上用 `opusdec`/ffplay 播放出正确音频 |
| 6 | 语音面 WS 端点（server 侧，BinaryProtocol2/3） | 7 | PC 上的测试客户端能按帧收发 Opus |
| 7 | 设备侧 MiniMax 协议层 patch（最小版：只做下行播放 + 上行一个固定 cue） | 8 | **设备能播出一句话** |
| 8 | 设备本地"唤醒即变脸"（"在听"表情 + LED） | 8、11 | 唤醒后 300ms 内脸变了（**本地产生，不等网络**） |
| 9 | server 推情绪表情（`0x03` 几何 + `0x04` 舵机） | 11 | 设备在说话时同步变脸 |
| 10 | 功能减法落地（剥离 post/friend/pano/xiaozhi/dance CRUD；appstore 空实现） | 12 | 裁剪后 server 仍能编译、设备仍能启动 |

**MVP 明确不含**：ASR、iOS 端、完整后台、人格包热更新、灯色（固件 patch 未做时先留几何+舵机）、场景 D。

> ⭐ **MVP 的意义**：它把"设备说话 → MiniMax → 设备表情 + 语音"这条链的**每一个未知点**都变成可验证的：
> Ogg 拆包对不对（PC 上听）、设备解码器吃不吃（设备上听）、控制面推帧设备认不认（脸上看）、本地 300ms 达不达标（测）。

### 8.3 依赖尚未拍板的事项

| # | 待拍板 | 本文给的推荐 | 影响面 | 阻塞什么 |
|---|---|---|---|---|
| 1 | **账号方案** | **本地账号表**（§2.2 方案 B） | 认证层、DDL、iOS 登录 | 模块 3、MVP 2 |
| 2 | **RSA 四把钥匙去留** | **保留 + 加固**（TLS + WS 白名单准入），不做设备级 HMAC（§2.3） | 认证层、部署 | 模块 4 |
| 3 | **设备协议是否允许扩展** | ⭐ **必须扩展**（新增 `0x1E RequestChat`；灯色字段加进 `0x04`）→ 与 PRODUCT.md §8「协议正文不改」**硬冲突** | 固件、iOS、server | 模块 8、MVP 7/9 |
| 4 | **固件基线** | 先把本地 v1.5.1 同步到 v1.6.0（`26` 号 §九-2 推荐） | 全部固件工作 | 模块 8 |
| 5 | **Mac 怎么办** | 先按原生 iOS 出设计稿与 HTML 原型，不因 Mac 阻塞（PRODUCT.md §11-3） | iOS 端 | 模块 16 |
| 6 | **部署形态** | **公网 VPS + 前置 Caddy**；家里设备用 cloudflared 作为"家里跑 server"的方案（§7.1） | 运维、延迟 | 模块 14 |
| 7 | **ASR 落点** | MVP 不做；第二阶段先验证 MiniMax STT 端点，再决定 server 侧 vs 设备侧（§3.5） | 完整对话体验 | 模块 15 |
| 8 | **人格包 `private/` 跨端同步** | **设备是唯一真源**，App 只读缓存（§4.3 方案 A） | 场景 D、隐私 | 模块 10 |
| 9 | **管理后台技术栈** | 与 iOS 端一致用原生 SwiftUI？后台是 Web → **待定** | 模块 13 | 模块 13 |

---

## §九 风险与未核实（如实登记）

### 9.1 风险登记

| # | 风险 | 影响 | 概率 | 缓解 |
|---|---|---|---|---|
| **R-1** | ⭐ **ASR 落点未定** —— MiniMax STT 端点路径未取得；设备端 ESP-SR 只做过唤醒词、未评估通用 ASR | 完整对话体验做不出来 | 高 | MVP 先不做 ASR（§8.2）；第二阶段先验证端点（一次抓取即可） |
| **R-2** | ⭐ **协议扩展与"协议正文不改"冲突** —— 新增 `0x1E`、灯色字段进 `0x04` | 与 PRODUCT.md §8 硬约束直接抵触 | 高 | 列为待拍板第 3 条；灯色可先不做（只做几何+舵机） |
| **R-3** | ⭐ **设备身份认证缺失** —— 任何人都能拿公开的 `rsa.server.public` 伪造 MAC 连上 WS；官方 `CreateMacIfNotExists` 自动建档 | 陌生人可连我们的 server、可占我们的设备记录 | 高 | **纯 server 侧可先堵**：WS 准入白名单（§2.3 第 3 层）；设备级 HMAC 需固件 |
| **R-4** | **端到端私密性有上限** —— system prompt 与私人记忆必须过我们的 server 才能到 MiniMax | 与"永不入库"不是一回事，需在隐私说明里讲清 | 中 | server 不落盘/不进日志（§2.5）；隐私说明写明（P-3） |
| **R-5** | **Ogg de-mux 是整条语音链最易错点** —— 跨 page 的 packet 拼接、TOC 帧长表 | 设备播不出声或播错 | 中 | MVP 第 5 步先在 PC 上用 `opusdec` 验证拆包结果 |
| **R-6** | **设备端 `esp_opus_dec_decode` 对变长 Opus 包的行为未实测** | 变长帧可能解错 | 中 | 代码按 `decoded_size` resize（`audio_service.cc:377`），风险低；实测为准 |
| **R-7** | **表情只有 6 个枚举** —— `surprised`/`thinking`/`embarrassed`/`confused` 固件全不支持 | 表情贫乏 | 中 | 走 `ControlAvatar` 几何路径（§5.4）——**必须实现，否则功能减法白做** |
| **R-8** | **`sleepy` 有副作用** —— 显示 Zzz + 停 idle motion + 舵机归位 | 误用会让设备"睡着" | 低 | 状态机里只在"要说晚安"时用（§5.3 硬约束） |
| **R-9** | **300ms 指标依赖固件本地实现** —— 唤醒即变脸必须设备本地做 | 不达标则违反 PRODUCT.md §6 原则 4 | 中 | MVP 第 8 步专门验它 |
| **R-10** | **官方 server 不加密响应** —— `RSAEncrypt` 全仓无调用点 | 内容在链路上明文（TLS 后可解） | 中 | TLS 作为硬前提（§2.3 第 2 层） |
| **R-11** | **官方 admin token 永不过期**（`Exp` 大写键）+ 不剥 `Bearer` + 不校验算法 | 后台 token 泄露即长期有效 | 中 | 模块 3 一并修（§2.4） |
| **R-12** | **官方 `m5stack.*` 配置段整个缺失**（`config.yaml` 里没有） | 漏配 → 登录/注册 500 | 低 | 我们自己写全配置（§2.1） |
| **R-13** | **单点依赖 MiniMax** | 价格/限流/下线 → 陪伴体验断供 | 中 | Chat 端点抽象成接口，可换 OpenAI 兼容端点（MiniMax 同时提供 `/v1/chat/completions`） |
| **R-14** | **备份含密码哈希** | 备份泄露 = 撞库素材 | 低 | 备份加密 + 限制访问（§7.2） |
| **R-15** | **fork 与上游的冲突维护成本** | 官方继续更新 → 我们 cherry-pick 成本上升 | 中 | 我们的改动集中在 6 个文件（§3.2 表），其余保持上游原样 |

### 9.2 未取得 / 未核实清单（逐条登记）

**A. 网络/端点类**
1. **MiniMax STT（语音转文字）端点的完整路径与请求体** —— `18` 号 §4.1 标"⚠️ 路径待确认"，**本轮未取得**。（§3.5、R-1）
2. **MiniMax Get Voice API 的完整路径** —— 官方文档只给了页路径 `/api-reference/voice-management-get`，**实际 URL 与请求体未取得**。→ MVP 用手工维护的 `voice_profiles.yaml` 绕过。（§3.7.2）
3. **MiniMax 音色全集** —— 只拿到官方举例的几个 id（`Chinese (Mandarin)_Lyrical_Voice`、`Chinese (Mandarin)_HK_Flight_Attendant`、`male-qn-qingse`、`female-chengshu`、`female-tianmei`、`English_*`、`Japanese_*`、`moss_audio_*`），**完整表未取得**。
4. **MiniMax Realtime 端点** —— **未取得**（`18` 号 §4.4：官方 API Reference 索引无此页，`/docs/api-reference/realtime` 实测 404）。本设计不依赖它。
5. **MiniMax Chat 端点的完整字段表** —— 本轮只复核了 TTS 端点原文（`https://platform.minimax.io/docs/api-reference/speech-t2a-websocket.md` 抓取成功）；Chat 端点仍以 `18` 号 §4.2 的 OpenAPI 摘录为准，**本轮未逐字复核**。

**B. 固件类**
6. ⭐ **MiniMax `audio_setting.sample_rate=16000` 时，输出的 Ogg Opus 包的原始带宽是否真为 16 kHz** —— **未实测**。Opus 内部恒 48 kHz，原始带宽由 TOC config 决定；MiniMax 内部实现未知。→ server 用 `extra_info.audio_sample_rate`（官方权威字段）声明，**不做假设**。
7. **`DefaultDanceData` 的完整内容** —— 该常量是 334 256 字符的单行 JSON（`server/internal/model/value_constant.go:15`），**只读到第 2 个关键帧**。→ 舵机/灯色初值是设计初值，不是官方库抄来的。
8. **设备 codec 的 `output_sample_rate` 具体值** —— 未核实（`firmware/xiaozhi-esp32/main/boards/m5stack-core-s3/cores3_audio_codec.cc` 由构造参数决定，调用点未追）。→ 影响"声明 16000 时是否触发重采样"（`audio_service.cc:378`）。
9. **`SetDecodeSampleRate` 每包重开 Opus 解码器的性能代价** —— 从代码读出的**推论**（`audio_service.cc:462-470`），**未实测**。
10. **固件启动流程是否请求 `/stackChan/apps`** —— **未核实** → 这正是 `appstore` 选择"降级保留空实现"而非直接剥离的原因（§6.1）。
11. **固件是否请求 `/stackChan/xiaozhi/*`** —— **未核实**（按"该组是给 App 用的"推断可剥离，但未验证）。
12. **设备端 `esp-sr` 能否做通用 ASR** —— **未评估**（树里有 `espressif__esp-sr`，但 xiaozhi 只用它做唤醒词）。
13. **`hal_ws_avatar.cpp` 注释提到的 "OnData Fast Path"** —— 已确认**不存在**（整段被注释，`OnData` 只是入队）。✅ 已核实，不是遗留问题。

**C. Go / 框架类**
14. **GoFrame v2.10 的 `g.Cfg()` 是否支持环境变量覆盖** —— **未核实** → 我们自己实现 `env.go` 覆盖，不依赖框架特性（§7.4）。
15. **`ghttp` 自身的 TLS 证书配置键名** —— **未核实** → 用前置 Caddy/Nginx。
16. **`server/README.MD` 全文** —— **未读**（`26` 号 §十-9 也记为未逐字重读）。
17. **`server/internal/dao/internal/*.go` 生成的 SQL 细节** —— 未逐行读（结构由 `gf gen dao` 产出，我们不改）。
18. **`server/manifest/deploy/kustomize/base/*`** —— 未读（只读了 `overlays/develop/configmap.yaml`）。

**D. 一处已纠正的流传错误**
19. **TTS WebSocket 地址**：曾流传 `wss://api.minimax.io/v1/t2a_v2`（漏 `/ws`）。**本轮从官方文档原文核实：正确是 `wss://api.minimax.io/ws/v1/t2a_v2`**（官方 Python 示例 + AsyncAPI `address: /ws/v1/t2a_v2`）。`18` 号 §4.3 是对的。

### 9.3 本文与父任务前提的两处纠偏（结论方向不变）

| # | 父任务前提 | 实读结论 |
|---|---|---|
| 1 | 「RSA **双向加密**……响应 `rsa.client.public` 加密、客户端 `rsa.client.private` 解密」 | **官方 server 只实现了单向**：`utility.RSAEncrypt` 全仓**无调用点**；只有 `RSADecrypt` 被用一次（WS 握手凭证）。→ 我们**不实现响应加密**，与官方行为一致 = 固件零改动（§2.3、§3.4） |
| 2 | 「TTS WebSocket `wss://api.minimax.io/v1/t2a_v2`」 | **正确路径带 `/ws`**：`wss://api.minimax.io/ws/v1/t2a_v2`（官方原文核实，§3.4.1、§9.2-D19） |

---

## 收尾自查

| 项 | 值 |
|---|---|
| 文件 | `docs/research/31-后端改造设计-fork官方server接MiniMax.md` |
| 字节数 | **118 587** |
| 编码 | UTF-8 |
| BOM | **无**（实测 `EF BB BF` 不存在） |
| 换行 | **纯 LF**（CRLF = 0，CR 总数 = 0，LF = 1 186） |
| NUL 字节 | **0** |
| U+FFFD 替换字符 | **0** |
| 行数 | 1 187 |
| CJK 汉字数 | **15 047** |
| 章节完整性 | §一 ~ §九 + 收尾自查，**9 个主章节全部落地** |

**取数来源声明**：
- `server/` 全部代码结论来自本地 git clone `D:\jss18\AI\StackChan\StackChan2` 的 **`origin/main`（`eff0d6b`）**，解包到 `D:\AP\AP7000\ai-workspace\stackchan-server-extract\server` 后逐行读；行号与 `git show origin/main:server/<路径>` 一致。
- `firmware/main/` 结论来自 **`origin/main`**（`git show`）；`firmware/xiaozhi-esp32/` 结论来自**本机工作树的 v2.2.4 + 官方 patch**（该目录由 `firmware/repos.json` 在构建时 fetch，**不在 git 里**）→ 相关行号标注方式与 `server/` 不同。
- MiniMax 端点：本轮**成功抓取**官方 `https://platform.minimax.io/docs/api-reference/speech-t2a-websocket.md` 原文（**修正了 TTS WebSocket 路径**，见 §9.2-D19）；Chat 端点仍以 `18` 号 §4.2 的 OpenAPI 摘录为准（未逐字复核）。
- 全程**未调用** `api.github.com`（配额已耗尽）。

