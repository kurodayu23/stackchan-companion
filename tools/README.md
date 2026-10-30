# tools/

StackChan 项目的开发/联调工具。依赖见 `tools/requirements.txt`
（numpy / scipy / websockets 为必需，bleak / pillow 按需）；
**不要额外装包**，`py -3.12` 环境里已装好。

| 脚本 | 作用 | 自检 |
| --- | --- | --- |
| `stackchan_server.py` | **真服务端替身**：让真机（ESP32-S3 / 固件 1.5.1、1.6.0）连上本机并接受 0x14 DanceSequence 控制 | `--self-test` |
| `protocol_sim.py` | 协议模拟器：`--role device` / `--role app` / `--role lan` 三种角色，用于无真机时打通链路 | –（交互式） |
| `prosody_to_motion.py` | 语音韵律 → 舵机/表情关键帧（生成 `protocol_sim.py --dance` 的输入） | `--self-test` |
| `stackchan_ble.py` | BLE 通道工具 | `selftest`（**子命令**） |
| `dance_chunk.py` | 0x14 分段下发器（单段 ≤64 帧 / ≤16 KB，按 `Σ durationMs` 定时调度） | `--self-test` |
| `ble_acceptance.py` | 真机 BLE 一键验收（设备不在 DANCE 时优雅降级） | `--self-test` |
| `demo_offline.py` | 全链路离线 Demo（文本 → 韵律 → 关键帧 → 帧 → 终端画脸 + 音画对齐） | `--self-test` |
| `audio_chunk.py` | PCM 音频按帧栅格切片，与 0x14 关键帧**同源对齐** | `--self-test` |
| `tts_align_e2e.py` | TTS → 韵律 → 关键帧 → 切片 → 音画对账**端到端闭环** | 直接跑（退出码即结论） |
| `repo_release_check.py` | 发布前体检（LICENSE / NOTICE / 商标 / `private/` / 密钥扫描） | `--self-test` |
| `check_docs.py` | 文档体检（自动扫描 + CRLF 判 FAIL） | 自动 |
| `fetch_literature.py` | 文献抓取器（arXiv + Semantic Scholar API，可复现检索留痕） | `--self-test` |
| `check_contrast.py` | 4 套视觉方案的对比度实算（WCAG 公式，读原型色值） | `--self-test` |
| `fix_md_tables.py` | Markdown 表格修复（竖线转义 + 列数对齐，内容不删） | `--self-test` |
| `check_face_geometry.py` | 脸渲染几何**同口径**校验（Swift 公式 vs 固件 `map_range` 逐点比对） | `--self-test` |
| `check_links.py` | 文档内部链接体检（命名空间感知，仓库内路径必须存在） | `--self-test` |
| `check_ci.py` | **CI 自身的体检**（workflow 引用的脚本必须存在、`--self-test` 必须真支持、注释与命令一致） | `--self-test` |
| `check_css_vars.py` | 原型 CSS 变量体检（**被引用但未定义** / 方案 token 集合不一致 / 与 Swift token 漂移） | `--self-test` |
| `check_decisions.py` | **待拍板清单 ↔ 施工顺序依赖图**一致性（新增决策忘了登记依赖 ⇒ CI 变红） | `--self-test` |
| `make_readme_hero.py` | 生成 README 用的「小栈的脸」**真实动图**（真实 TTS → 韵律 → 关键帧 → 固件几何 → 像素） | `--self-test` |

## audio_chunk.py —— 音画同源对齐（关键保证）

架构裁决（`docs/research/64-固件音频通道取证与谁出声架构裁决.md`）：
**手机出声，设备做身体**。声音由 iOS App 播，设备只执行 0x14 关键帧。
⇒ 音频轴与动作轴必须对齐，而两轴**唯一的公共点是同一段 PCM**
（关键帧就是从这段 PCM 推出来的）。

本工具把这个对齐从口头承诺变成**机器可判**：

```bash
# 自检（49 项断言）
py -3.12 tools/audio_chunk.py --self-test

# 与真实关键帧对账（自动选切法）
py -3.12 tools/audio_chunk.py --wav voice.wav --keyframes kf.json --verify

# 显式指定切法
py -3.12 tools/audio_chunk.py --wav voice.wav --keyframes kf.json --plan grid --verify

# 切片落盘（chunk_%04d.pcm + index.json）
py -3.12 tools/audio_chunk.py --wav voice.wav --outdir chunks --frames-per-chunk 4
```

### 两种切法（`--plan`）

| 切法 | 边界规则 | 何时用 |
| --- | --- | --- |
| `grid` | 片边界固定落在 `N × 40 ms` 整数倍 | 音频长度**恰好**是 40 ms 整数倍 |
| `keyframes`（auto 默认） | 片边界对齐到**关键帧分组边界**，末组按真实音频尾截断 | **真实 TTS**（实测 1358 ms / 2350 ms 都不是 40 ms 整数倍） |

⚠️ 实测依据（两次真实 MiniMax TTS）：

| 文本 | 真实音频 | 关键帧 | 栅格余数 | `grid` | `keyframes` |
|---|---|---|---|---|---|
| 「今天真开心啊！」（离线替身 WAV） | 2350 ms | 59 帧 = 2360 ms | −10 ms | ❌ 末片错位 | ✅ 误差 0 ms |
| 「今天真开心啊！」（server 实时合成） | 1358 ms | 34 帧 = 1360 ms | −2 ms | ❌ 末片错位 | ✅ 误差 0 ms |

⇒ **生产路径一律用 `keyframes` 模式**（`--plan auto` 时给了 `--keyframes` 就自动走它）。
真实闭环实测：TTS → 韵律 → 关键帧 → 切片 → 对账，
**切片字节拼回 == 原始 PCM**、关键帧驱动误差 **+0 ms** ⇒ 通过。

## fetch_literature.py —— 可复现的文献检索留痕

手工搜文献的问题：换个台机器、换个时间，搜出来的不一样 ⇒ 无法复现，也无法进 CI。

本工具把检索**登记成表**（主题键 + 检索式 + 理由），
然后按登记的检索式去 **arXiv API** 与 **Semantic Scholar Graph API** 抓，
去重（arXiv ID / DOI / 规范化标题三路）、逐字段择优合并、排序、渲染成 Markdown。

```bash
# 列出全部主题与检索式（先看清楚再抓）
py -3.12 tools/fetch_literature.py --list

# 抓全部主题并写文档
py -3.12 tools/fetch_literature.py --all --out docs/research/68-陪伴机器人文献综述.md

# 校验文档里的 arXiv ID 是否仍可解析（引用还在不在）
py -3.12 tools/fetch_literature.py --all --out out.md --verify-ids

# 离线自检（不联网，CI 跑这个）
py -3.12 tools/fetch_literature.py --self-test
```

**17 个主题**（第三轮夜间扩充批二，加了 8 个）：

| 批 | 主题键 | 主题 |
|---|---|---|
| 批一（6） | `voice-latency` | 语音交互延迟与人类对话轮次容忍度 |
| | `tts-streaming` | 流式 TTS 的首包延迟与分段播放 |
| | `llm-companion` | LLM 陪伴机器人的拟人化、依恋与再互动 |
| | `robot-face` | 机器人屏幕脸 / 表情渲染与可辨识度 |
| | `embodied-hri` | 具身代理与 HRI 的信任校准 |
| | `privacy-companion` | AI 陪伴的隐私、依赖与伦理争议 |
| 批二（3） | `prosocial-robot` | 社交机器人与亲社会行为 / 幸福感效应 |
| | `memory-persona-consistency` | 长期记忆、人格一致性与跨会话连续性 |
| | `voice-barge-in` | 语音对话的打断处理、重叠语音与轮次管理 |
| 批三（8） | `edge-on-device-llm` | 端侧小模型推理、量化与本地 provider 可行性（Q14 的外部依据） |
| | `affective-computing` | 情感计算：语音韵律的情绪特征与识别（韵律→动作的学理依据） |
| | `robot-motion-expression` | 机器人肢体动作的情绪表达与感染效应 |
| | `wake-word-vad` | 唤醒词、端侧 VAD 与始终在线语音链路 |
| | `parametric-face-animation` | 参数化 2D 表情动画：情绪强度与表情混合 |
| | `local-first-architecture` | local-first 架构、端云协同与离线可用性 |
| | `companion-retention` | AI 陪伴的留存、习惯养成与长期参与 |
| | `llm-persona-control` | LLM 人格控制、角色一致性与角色卡工程 |

⚠️ **产出的记录一律标 T4，不是 T1**：一条 arXiv 摘要说明的是「论文声称了什么」，
不等于「事实已被独立验证」。要用于对外结论，必须回源读原文后**自己写**取证记录。

实测（2026-10-25）：
6 主题去重后 **135 条**（68 号）→ 扩充 3 主题另出 69 号 →
9 主题**并集** 206 条（71 号）→ **扩充批二 8 主题 252 条** →
**17 主题并集 458 条**（74 号，当前权威留痕）。

⚠️ Semantic Scholar 仍常年 429：批三抓取时 **10 条检索降级**（已显式列进日志，不静默吞）。
⇒ 这正是「必须能跨次取并集」的另一条理由：**429 的那几次，别的机器别的时刻能补上。**

### ⭐ 跨次并集：为什么「只留最后一次跑的结果」是错的

arXiv 与 Semantic Scholar 的可用性是**波动的**（S2 常年 HTTP 429），
同一条检索式在不同时间跑出来的结果集**互不包含**：

- S2 正常那次 —— 有 S2 的正式出处（带引用数），但缺 arXiv 的补充命中；
- S2 被限流那次 —— 有 arXiv 的命中，但丢了 S2 的正式出处。

⇒ 「只保留最后一次跑的结果」等于**主动丢弃**已经抓到的文献。

所以留痕文件必须能**跨次取并集**。`--merge` 把已生成的留痕**反向解析**回结构，
与新抓的结果合并去重后重新渲染（合并是**无损**的：同一 arXiv ID 跨文件出现时
按字段择优合并，与 `dedupe()` 同一套规则）。

```bash
# 取并集并落盘
py -3.12 tools/fetch_literature.py --merge \
  "docs/research/68-陪伴机器人文献综述.md" \
  "docs/research/69-陪伴机器人文献综述-扩充三主题.md" \
  "docs/research/runs/20261025-0454-lit-all9.md" \
  --out "docs/research/71-陪伴机器人文献综述-九主题合并留痕.md"

# 只比对不写盘：并集与已落盘文件是否漂移（CI 用这个）
py -3.12 tools/fetch_literature.py --merge <同上> --out <同上> --check
```

`--check` 的判据是**规范化标题集合**（不是逐字节 —— 落盘文件头部带「取证时间」，
重算必然不同，但**条目集合**必须一致）：少一条 = 有人删了证据，多一条 = 并集没重算。
负向实测：拿只含 3 主题的 69 号当「已落盘文件」⇒ 报出 **7 个主题不一致**并 exit 1。

`docs/research/runs/` 目录存放**每次抓取的原始留痕快照** —— 并集的三份来源全在仓内，
所以任何人都能在本地重算出同一个 206 条。

### ⭐ 它抓到的真 bug：arXiv 的「引号短语」会静默吞掉结果

2026-10-25 扩充主题时，`prosocial-robot` **一条都没抓到**，而工具**不报错**。

实测根因（同一时刻同一 API）：

| 检索式 | 结果 |
|---|---|
| `all:"prosocial"` | 5 条 |
| `all:robot AND all:prosocial` | 5 条 |
| `all:"social robot" AND all:"prosocial"` | **0 条** ← 明明该有 |

⇒ **arXiv 对 `all:"多词短语"` + AND 的处理有坑**：引号里的短语被当成精确短语，
与另一项 AND 时交集为空，**且不返回错误**。

修法（`arxiv_query_variants`）：原式命中 0 条 ⇒ 自动用**去引号拆分变体**重试
（`all:"social robot"` ⇒ `all:"social" AND all:"robot"`）。
本工具是**召回优先**的文献检索，短语的精确匹配没有价值。

配套：**主题命中 0 条时打显式警告** —— 静默 0 条是最危险的失败模式
（分不清「真的没文献」还是「检索式被吞了」）。

自检 32 → **39/39**（新增 4 项变体逻辑断言 + 3 个主题登记断言）。

## check_contrast.py —— 4 套方案的对比度实算

「强调色 = 各方案自带」这个拍板有个前提：**每套方案的强调色在自己的底色上都站得住**。
这不能靠眼睛看 ⇒ 实算。

```bash
py -3.12 tools/check_contrast.py --root .          # 读原型色值 + WCAG 公式实算
py -3.12 tools/check_contrast.py --json            # 机器可读
py -3.12 tools/check_contrast.py --self-test       # 离线自检（含 WCAG 已知答案）
```

- **色值来源**：`prototype/variants/*.html` 的 `:root` CSS 变量（**直接读，不手抄**）
- **算法**：WCAG 2.x 相对亮度公式
- **阈值**（T1，HIG）：正文 ≥ 4.5:1；大字 / 非文本 ≥ 3:1

实测结论：**4 套方案全部正文级合格**（强调色对比度 5.06 / 5.44 / 5.43 / 8.99）。
⇒ 并据此**公开订正**了 `docs/spec/07` §3.3 里「纸感陶土 ≈ 4.3:1 只用于大字」的错误记录
（那是目测估的，实算 5.06:1）。详见 `docs/research/67-四套视觉方案token提取与对比度复核.md`。

## fix_md_tables.py —— 表格格式修复

本项目的**表格铁律**：单元格内 `|` 必须转义成 `\|`；每行列数 == 表头列数；
表格块内无空行；文档 LF + UTF-8 无 BOM。`check_docs.py` 与 `repo_release_check.py` 都按这条判 FAIL。

```bash
py -3.12 tools/fix_md_tables.py --check docs/**/*.md   # 只报告
py -3.12 tools/fix_md_tables.py docs/research/xx.md    # 就地修
py -3.12 tools/fix_md_tables.py --self-test
```

⚠️ **它不猜语义、不删内容**：列数超出表头时，把多出的列**合并回上一格**（用 `\|` 连接）
并报告行号，请人工确认合并结果是否可读。

## check_face_geometry.py —— 脸渲染几何的「同口径」校验

「App 是镜子」（`docs/research/58` §4）要求 App 端像素几何与固件**完全一致**。

本机**没有 Swift 编译器** ⇒ `swift test` 本地跑不了（只能靠 GH Actions 的 macOS runner）。
本脚本补这个缺口：**用 Python 复刻固件的 `map_range` 语义，解析 Swift 源码，
逐点比对** ⇒ 「Swift 公式被改坏」在本地/CI 都能被抓到。

```bash
py -3.12 tools/check_face_geometry.py --root .        # 比对
py -3.12 tools/check_face_geometry.py --self-test     # 离线自检
```

### 它抓到的两个真 bug（2026-10-25 首次运行时）

| # | 缺陷 | 症状 | 修法 |
|---|---|---|---|
| 1 | **位置偏移公式被简化** | 我写的是 `units * 16 / 100`；固件是 `map_range(x,-100,100,-16,16)` = `-16 + (x+100)*32/200`。**负数段差 1 像素**（`x=-1` ⇒ 固件 −1、简化式 0） | 逐字复刻 `map_range` |
| 2 | **眼睑极性注释写反** | 我写「weight 越大眼睑越靠下」；实际是眼睑**整体上移**（offset 越负）⇒ 越睁 | 改注释 + 改断言方向 |

⇒ **这两个都是「差 1 像素 / 差一个方向」级别的错，肉眼和普通单测都看不出来**，
   只有同口径逐点比对能抓到。这正是「镜子原则」必须配机器门禁的原因。

### ⭐ 第三个真 bug（2026-10-25 深夜回源发现）：**眼睛的旋转从未被渲染**

回源固件 `eyes.cpp` 时才发现：**眼睛不是不旋转，而是大幅旋转**。

| 事实 | 出处 |
|---|---|
| rotation 施加在 **eye 容器**上（`_container->setRotation`），容器里装着眼白与眼睑 ⇒ **两者一起转** | `eyes.cpp:80-85` |
| 容器 pivot = 容器中心 = 眼睛中心 | `eyes.cpp:29-30` |
| 6 情绪里 **4 个带非零旋转**：Happy `1550`(155°) / Angry `450`(45°) / Sad `-400`(−40°) / Sleepy `-50`(−5°) | `eyes.cpp:103-122` |
| **左右眼镜像**：右眼 `setRotation(-rotation)` | `eyes.cpp:93-98` |

⇒ **我的 `FaceView` 几何层算对了 `rotationTenths`，但 Canvas 里从未应用** ⇒
   4/6 情绪的眼睛角度与设备不一致 ⇒「镜像 = 逐像素一致」当时是**假的**。

已修（两种模式都 `context.rotate(by:)` 绕眼睛中心），并加门禁守住：

- 新增 **6 情绪表逐值比对**（weight / 左眼 rotation / 右眼取反 / 下发值区间）⇒ **10 项**
- 新增 **渲染层旋转检查**（`FaceView.swift` 必须出现 `rotate(by:` 且读取 `rotationTenths`）⇒ **2 项**
- 校验项从 **20 → 32**，自检从 **26 → 37**

### 关键口径

- **C++ 整数除法向零截断**（Python 的 `//` 是向下取整，负数时不同 ⇒ 脚本自带 `c_div`）
- **`map_range` 不钳位**（`base.hpp:40-48` 是纯线性映射）⇒ 钳位发生在
  `Element::setPosition`（±100）/ `Feature::setWeight`（0..100）/ `Feature::setSize`（±100）/ `Element::setRotation`（0..3600）
- ⚠️ **`Element::setRotation` 的钳位只影响「存储值」**：
  `DefaultEyes::setRotation` 随后把**原始未钳位**的值交给 `_container->setRotation`
  ⇒ **渲染照常生效**（负角也生效），只是 `getRotation()` 读数失真。
  这正是协议层「负角用 `3600 + θ` 表达」的原因。
- **固件源码路径**：`D:\jss18\AI\StackChan\StackChan2\firmware`（官方仓，只读）；
  读不到时降级为 WARN 并跳过常量比对，不阻断 CI

## check_links.py —— 文档内部链接体检

GitHub 上读者点一个不存在的路径只会得到 404。对一份**求职作品**，这是实打实的减分。
但人读文档时能靠上下文分辨「这是我们仓的路径」还是「这是官方上游仓的路径」，
**机器不能** ⇒ 本工具把这件事变成门禁。

### 命名空间模型

判定「是不是我们的路径」**不靠前缀猜**，而是看**第二段目录是否真实存在于本仓**：

| 例子 | 判定 | 理由 |
| --- | --- | --- |
| 「`docs/spec/07-xxx.md`」 | REPO | `docs/spec/` 是真目录 ⇒ 必须存在 |
| `docs/api.md` | EXTERNAL | `docs/api.md` 不是目录 ⇒ 上游 Ollama 的文档 |
| `server/api/dance/v1` | EXTERNAL | `server/api/` 不存在 ⇒ 官方 Go server |
| `firmware/main/hal/…` | EXTERNAL | `firmware/` 在本仓只是占位目录 |
| 「`tools/gone.py`」 | REPO | `tools/` + `.py` 扩展名亲和 ⇒ 必须存在 |

### 命名空间清单

| 命名空间 | 含义 | 必须在本仓存在 |
| --- | --- | --- |
| REPO | 本仓路径 | ✅ |
| EXTERNAL | 上游固件仓 / 官方 Go server / 第三方项目 | ❌ |
| LEGACY | 旧 PWA 项目（`mobile_app/`） | ❌ |
| LOCALCACHE | 本机 Apple 官方文档缓存（`hig-md/` 等） | ❌ |
| PRIVATE | 私人层（`private/`） | ❌ 永不入库 |

### 两种检查

- **Check A —— Markdown 相对链接**：「`[文字](../../docs/spec/00-x.md)`」按所在 `.md` 的目录解析，
  再按仓库根解析（本仓两种写法都存在）⇒ 解析不到就 FAIL。
- **Check B —— 行内反引号路径**：`` `tools/xxx.py` `` ⇒ REPO 命名空间必须存在。

支持**编号前缀匹配**：`docs/spec/07` ⇒ 命中 `docs/spec/07-*.md`。

### 两条豁免（都写死在代码里，不藏）

- **外部标记词**：行内出现「上游 / 旧项目 / 本机缓存 / 第三方 / 计划新增 / 尚未实现」等
  ⇒ 该行路径按外部引用处理。**标注了「还没做」的计划不是坏链接。**
- **已知设计-实现分歧**：`KNOWN_DIVERGENCES` 显式登记（例如 `personas/enfp.yaml`
  是 18 号的 YAML 设计稿，实现走 JSON），命中即 INFO 并附理由。

### 实测（2026-10-25）

本工具**第一版误报 225 条**（把「仓库根相对路径」和「上游路径」都算失效）。
精修命名空间模型后 **真 FAIL = 22 条**，逐条核实后**全是真问题**，修完 **FAIL = 0**：

| 类别 | 条数 | 处理 |
| --- | --- | --- |
| 人格包 `.yaml` ↔ `.json` 合同不一致 | 12 | 落盘 `personas/enfp.json` + 18 号公开订正 |
| 错名引用（`08-iOS原生界面规范摘录.md`） | 2 | 改为真名 `08-iOS官方规范事实层.md` |
| 图标路径（「`ios/prototype/icon-180.png`」→ `assets/icons/icon-180.png`） | 1 | 改为真路径 `assets/icons/icon-180.png` |
| 计划中未实现（`server/providers/local` 等） | 4 | 行内标注「计划新增 / 尚未实现」 |
| 上游文档（`docs/device_affection_api.md`） | 1 | 行内标注「上游」 |

### 用法

```bash
py -3.12 tools/check_links.py --root .            # 全仓体检（退出码 0 = 无 FAIL）
py -3.12 tools/check_links.py --root . --verbose  # 带 INFO 命名空间分布
py -3.12 tools/check_links.py --root . --json     # 机读
py -3.12 tools/check_links.py --self-test         # 离线自检（24 项）
```

## check_ci.py —— CI 自身的体检

`.github/workflows/` 下的两个 workflow **从未在真实 runner 上跑过**
（本机是 Windows、没有 Swift、没有 macOS）。于是「CI 能不能过」没有任何本地证据。

这类风险有典型形态：**workflow 里引用的脚本路径写错了 / 脚本被改名了 /
`--self-test` 这个 flag 根本不存在** —— YAML 依然合法 ⇒ 流水线第一次真跑才炸，
而那时人已经推上去了。

本门禁把「workflow 声明的东西在仓库里真的存在且自洽」变成**可本地执行**的判定。

| 检查码 | 判什么 |
|---|---|
| CI-01 | YAML 可解析 |
| CI-02 | `run:` 里 `python <path>` 指向的脚本必须存在 |
| CI-03 | 命令带 `--self-test` 时，被调脚本源码里必须真的有这个 flag |
| CI-04 | `working-directory:` 指向的目录必须存在 |
| CI-05 | `run:` 块里出现的仓库内路径字面量必须存在（**中文文件名也覆盖**） |
| CI-06 | 同一 job 内 step `name:` 不得重复（重名会让日志定位失效） |
| CI-07 | 「本地复现：」注释必须与实际 `run` 命令一致（防注释过期） |
| CI-08 | `on.push.paths` 里的目录必须存在（通配取静态前缀判定） |
| CI-09 | 同一 workflow 内 `python-version` 必须唯一 |
| CI-10 | 每个 job 必须声明 `runs-on` |

CI-07 是按**原始文本**扫的 —— 「本地复现：」是 YAML 注释，PyYAML 会把注释丢掉。

自检 **11/11**：用 10 个故意做坏的夹具（坏 YAML / 脚本不存在 / flag 不支持 /
working-directory 不存在 / 路径不存在 / step 重名 / 注释与命令不符 / paths 目录不存在 /
缺 runs-on / python-version 不唯一）逐项证明都能抓到，
再加一个「健康夹具必须零 FAIL」的反向断言。

```bash
py -3.12 tools/check_ci.py --root .
py -3.12 tools/check_ci.py --self-test
```

实测：当前两个 workflow 共 **9 个 job / 58 个 step / 28 处 python 调用**，
声明与仓库**全部对得上**（FAIL=0）。

## make_readme_hero.py —— README 首页那张脸是真的

README 首页需要一张「一眼看懂产品在干嘛」的图。此前只有终端 ASCII 字符画，说服力不够。
而本项目最硬的技术主张是「**App 是设备脸的镜子**」—— 那就该直接放**设备脸上真实发生的那张脸**。

这份动图**不是装饰**：每一帧都是

```
真实 MiniMax TTS → 韵律提取(7 维) → 42 参数 → 0x14 关键帧 → 固件几何 → 320×240 像素
```

手画的动画骗不了人，但**真实关键帧**能证明「韵律→身体」这条链路真的跑得通。

### 几何逐条对应固件（不另算一套比例）

| 元素 | 固件出处 | 口径 |
|---|---|---|
| 画布 | 设备屏 | 320×240，纯黑底（`FaceStyle.DeviceFaceColors`） |
| 眼容器 | `eyes.cpp:21-27` | 32×32，`LV_ALIGN_CENTER`，transform pivot = 容器中心 (16,16) |
| 眼圆 | `eyes.cpp:134-137` | 直径 `map_range(size, -100, 100, 8, 32)`，纯白 |
| 眼睑 | `eyes.cpp:37-44` + `73-77` | 与眼圆同尺寸的**方块**，**背景色**（黑）；`setY(-map_range(weight,0,100,0,眼径))` |
| 眼位 | `eyes.cpp:13,63-66` | 左 `(160-70+off, 120-16+off)`，右 `(160+70+off, …)` |
| 眼旋转 | `eyes.cpp:81-85` | 施加在**容器**上 ⇒ 眼白与眼睑**一起转**；右眼取反 |
| 嘴 | `mouth.cpp:14-18,41-54` | 宽 `map_range(w,0,100,90,60)`、高 `map_range(w,0,100,6,50)`、圆角 `map_range(w,0,100,0,16)` |

⚠️ **眼睑极性最容易搞反**：weight 越大 → 偏移越负 → 眼睑越往上 ⇒ **越睁开**
（weight=0 全闭、100 全睁）。自检里专门断言了这条。

### 几何复用而非复制

工具**直接 import `tools/check_face_geometry.py`** 的固件复刻函数（`fw_eye_diameter` /
`fw_eyelid_offset` / `fw_mouth_size` / `fw_position_offset` …），**不另写一份** ——
那份已经过「同口径校验」（逐条对过 `map_range`、C++ 整数除法、眼睑极性），
复制一份就等于多一个可能漂移的副本。

### 用法

```bash
py -3.12 tools/make_readme_hero.py                       # 有 key 用真实 TTS
py -3.12 tools/make_readme_hero.py --provider stub       # 离线合成音
py -3.12 tools/make_readme_hero.py --self-test           # 离线自检（CI 用）
```

自检 **14/14**（几何口径断言 + 眼睑极性两态 + 「相邻帧真的在变」+ 「画面不是全黑」
+ GIF 写出后**回读帧数**一致）。

产物：`assets/hero/stackchan-hero.gif`（循环）+ `assets/hero/stackchan-hero.png`（静帧）。

> 💡 GIF 写盘时 PIL 会**合并相邻的相同帧**（脸不会每 40 ms 都变）⇒ 文件里的帧数
> 少于渲染帧数，但**总时长不变**。这是对的，不是 bug。

## check_css_vars.py —— 原型 CSS 变量体检

2026-10-25 深夜给 4 套方案**出图**时，肉眼抓到一张不对劲的图：
**深色方案下 Tab Bar 的选中项几乎看不见**。回源定位到根因：

```css
.tab-item[aria-selected="true"]{color:var(--tint)}   /* --tint 从未被定义 */
```

`--tint` 没定义 ⇒ 这条声明在 **CSS 计算值阶段非法** ⇒ `color` 退回**继承值**（黑）。
**浏览器不报错、不警告、DOM 里也看不出来** —— 只是「有个元素颜色不对」。
对浅色方案只是「不显眼」，对深色方案就是**深底黑字 = 不可读**。

而这能溜过去是有原因的：原有的 `check_contrast.py` **只读 `prototype/variants/`**，
**根本没看 iOS 原型**；而且它做的是「两个**有值**的变量之间的比值」，
压根不关心「被引用的变量有没有定义」。

### 三个检查码

| 检查码 | 判什么 |
|---|---|
| CSV-01 | **被引用但从未定义**的 CSS 变量 → FAIL |
| CSV-02 | 4 套方案的 token **集合不一致**（某套少定义一个 ⇒ 该方案渲染不同） → FAIL |
| CSV-03 | iOS 原型的方案强调色与 `prototype/variants/` 的 `--accent` **漂移** → FAIL |

### 它当场抓到的 4 个真问题

1. `ios-light.html` 与 `ios-dark.html` 各有一处 `--tint` 未定义（⇒ 7 条声明失效）
2. `prototype/variants/01` 的 `--on-accent:#FFF8F4` 与 Swift `Tokens.swift` / iOS 原型的 `#FFFFFF` 漂移

### 修法（命名统一到 Swift，不新造一套）

| 旧 | 新 |
|---|---|
| `--tint`（未定义） | `--accent`（**Swift token 就叫 accent**） |
| 方案块里的 `--bubble-out` | `--accent` |
| 方案块里的 `--bubble-out-text` | `--on-accent` |
| `:root` 的 `--bubble-out:var(--tint)` | `--bubble-out:var(--accent)` |

⇒ 每个方案只声明**一对**强调色 token，冒泡色与标签色自动跟随，**不会再漂移**。

自检 **4/4**（用 4 个故意做坏的夹具：未定义变量 / 方案 token 不一致 / 健康文件零 FAIL /
`@property` 注册过的变量不算未定义）。

```bash
py -3.12 tools/check_css_vars.py --root .
py -3.12 tools/check_css_vars.py --self-test
```

## check_decisions.py —— 决策清单 ↔ 施工顺序依赖图 一致性体检

`docs/spec/07` §3.5 管「**有哪些**待拍板项」，
`docs/spec/09` §四 管「每个项**解锁什么 / 不拍板怎么办**」。

两份文档都是**人写的**，都会漂。漂了的后果不是「文档不好看」，而是**真的漏工**：
新增一个决策却没登记依赖 ⇒ 没人知道它卡住了哪条任务；拍完板也不知道从哪一步动手。

### 十一个检查码

| 检查码 | 判什么 |
|---|---|
| DEC-01 | 07 §3.5 的每个 Q 在 09 依赖表里都有登记 → FAIL |
| DEC-02 | 09 依赖表出现的每个 Q 在 07 §3.5 存在 → FAIL（防凭空造决策） |
| DEC-03 | 09 的 D 系列编号从 D1 连续到 Dn（无跳号） → FAIL |
| DEC-04 | 依赖表每行的「建议 / 阻塞 / 降级路径」三列不得为空 → FAIL |
| DEC-05 | 09 必须有「未验证」小节且至少 3 条（防边界声明被悄悄删掉） → FAIL |
| DEC-06 | 09 声称由本工具守门 ⇒ 正文必须出现本工具名 → FAIL（防文档说谎） |
| DEC-07 | 09 号写的「07 号 §3.5（N 项）」必须等于实际条目数 → FAIL |
| DEC-08 | 72 号写的「N 个真缺陷」必须等于其清单实际条目数 → FAIL |
| DEC-09 | 00 号 §9 的每个开放项必须与 07 号 §3.5 跨表登记（O↔Q 互查，编号不得悬空） → FAIL |
| DEC-10 | 音频分片大小在 07 号与 72 号之间必须口径一致 → FAIL |
| DEC-11 | 05 号 §八 的每个技术侧待拍板项（T-）必须与 07/00 跨表登记 → FAIL |
> 💡 Q 编号要扫**整行**（不只「编号」列）：09 号里 `D2`–`D6` 这几行是**决策别名**，
> Q 号写在「事项」列里（例：「视觉终选（Q15）」）。这是第一版自检 FAIL 查出来的真 bug。

### 它当场抓到的 1 个真问题

第一版自检里 **DEC-05 报 FAIL**：真仓库的「未验证」小节明明有 12 行，却只数出 0 行。
根因是 `_section()` 的终止条件写成了「下一个标题」——
它从**第一个标题**（H1）开始取，于是取到的只是引言段 ⇒ 表头和表体一个都没进去。
⇒ 修法：单独写一个「从含『未验证』的标题开始、到下一个标题为止」的取段函数。
**教训**：自检 FAIL 先分流「脚本错 / 被测物错」——这次是脚本错。

### 后面 5 条检查码是怎么来的：独立审计

DEC-07…DEC-11 全部是 **DeepSeek 独立审计**在我自己的文档里查出真矛盾之后加的。
每一条对应一类**会真的漏工**的漂移：

| 检查码 | 审计查出的原话（简） | 加了它以后会怎样 |
|---|---|---|
| DEC-07 | 09 号说「07 号 §3.5（14 项）」，实际 15 项 | 集合对、**计数错** ⇒ 变红 |
| DEC-08 | 72 号首段写「5 个真缺陷」、标题写「4 个」、正文列 6 条 | 三数互斥 ⇒ 变红 |
| DEC-09 | 00 号 §9 的 12 个开放项与 07 号的 15 个 Q **互不登记**；被 09 号称为「唯二关键路径」的 D2(=Q10) 在 00 号 §9 里**根本不是一条开放项** | 只看 00 号拍板会漏掉唯一阻塞项 ⇒ 变红 |
| DEC-10 | 07 号方案表说「20~100 ms/片」，同文件 §3.6.1 写死「160 ms」 | 用户按前者拍板、照后者实现 ⇒ 变红 |
| DEC-11 | 05 号 §八 的 T1（iOS 编译环境）与 T5（端侧检测路线）**不在任何待拍板清单里** | 用户按 07/09 拍板会漏掉它们 ⇒ 变红 |

> ⚠️ 审计员读的是**暂存仓快照**，不是真仓 ⇒ 它报的 2 条是**快照过期**导致的误报
> （真仓早已修好）⇒ **派单前必须刷新暂存仓**，否则审计结论要自己回源核验，不能照单全收。

```bash
py -3.12 tools/check_decisions.py --root .
py -3.12 tools/check_decisions.py --self-test
```

## check_repo_stats.py —— 进度快照里的规模数字不许过期

`docs/spec/09` §二 是一张**给人看的资产清单**（多少源文件、多少测试、多少份文档），
求职作品里最容易被追问的一页，**数字错了就是硬伤**。

⚠️ 这条门禁是被一次**独立审计**逼出来的：审计员在报告里明写
「本工作区只有 `docs/`（无 `tools/`、`server/`、`ios/`、`prototype/`），
故 09 §二的『19 个 .py / 28 项门禁 / 67 个测试 / 43 Swift 文件 / 91 个测试函数 /
75 份留痕 / 00–08 共 9 份』等**仓库规模数字无法在本机复核**」
⇒ **审计员能看见这些数字，但核不了** ⇒ 只能由本机来守。

| 资产 | 核什么 |
|---|---|
| `server/` | `.py` 源文件数（不含 `tests/`）、测试文件数 |
| `ios/` | `.swift` 文件数、测试文件数、`func test` 函数数 |
| `tools/` | `.py` 文件数 |
| `docs/spec/` | `.md` 文件数 |
| `docs/research/` | `.md` 文件数（递归，含子目录） |

**上线当场就抓到 4 处过期数字**（`server/` 源文件 28→19、`tools/` 22→23、
`docs/spec/` 9→10、`docs/research/` 75→82）⇒ 这条门禁不是装饰。

```bash
py -3.12 tools/check_repo_stats.py --root .
py -3.12 tools/check_repo_stats.py --self-test     # 6/6
```

## probe_minimax_json.py —— E-4 结构化输出（云端到底行不行）

`docs/spec/00` §9 的 **O-3** 是个开放项：「E-4 结构化输出在 MiniMax 云端是否可用？」。
规格 §3 里还留着一句**待复核**的话：「云端 `response_format: json_schema` 仅 `MiniMax-Text-01` 支持
⇒ 云端结构化输出可能没有现成实现」。

⇒ 本工具把它变成**实测**（真实 API，非 mock）。

### 它测三种模式

| 模式 | 请求里加什么 | 问的是 |
|---|---|---|
| `plain` | 什么都不加，只在 system prompt 里要求输出 JSON | **纯靠提示词**能不能稳定出 JSON |
| `json_object` | `response_format: {"type":"json_object"}` | 云端 JSON 模式是否被支持 |
| `json_schema` | `response_format: {"type":"json_schema", ...}` | 云端 schema 模式是否被支持 |

### ⭐ 关键设计：**冲突探针**

三种模式都 100% 通过，但这**证明不了** schema 起了作用 ——
因为 `plain` 也 100%。⇒ 必须**故意让 schema 与提示词冲突**：

- schema 说 `emotion` 只能是 `neutral`，提示词却让模型从 6 个里挑；
- schema 多要求一个提示词里**根本没提**的字段。

⇒ 若输出全塌成 `neutral` 且带上额外字段 ⇒ schema 被**真正执行**；
若 emotion 仍随提示词变化 ⇒ **schema 被接受但未生效**。

### 实测结论（2026-10-25 07:20）

- ⛔ **schema 被接受但未生效**（6/6 次 emotion 仍随提示词变、额外字段 0/6）
  ⇒ **不能把服务端 schema 当护栏**，护栏必须在自己这一侧
  （`extract_json_object` + `validate_turn`，都在本文件里，且有自检覆盖）。
- ✅ **E-4 可行**：用**生产 ENFP 人格提示词**（`personas/enfp.json`）实测 **8/8** 稳定产出四字段齐全的合法 JSON。
- ⭐ 顺带暴露：**`emotion` 指谁的**（实测给的是「小灯自己的情绪」）⇒ 已登记 **Q20**。

```bash
py -3.12 tools/probe_minimax_json.py --self-test                    # 15/15
py -3.12 tools/probe_minimax_json.py --mode all --repeat 3           # 三模式
py -3.12 tools/probe_minimax_json.py --conflict --repeat 6           # 冲突探针
py -3.12 tools/probe_minimax_json.py --mode plain --repeat 8 --persona personas/enfp.json
```

🔒 key 只从环境变量 `MINIMAX_API_KEY` 读，不落盘、不回显。

## tts_align_e2e.py —— 音画同源的可复现证据
把「音画对齐」从口头承诺变成**一条能跑的命令**：

```bash
# 真实 MiniMax（需要 MINIMAX_API_KEY 在环境变量里）
py -3.12 tools/tts_align_e2e.py

# 离线替身（不需要 key，CI 里跑这个）
py -3.12 tools/tts_align_e2e.py --provider stub

# 落盘产物（tts.wav / tts_keyframes.json / chunks/）
py -3.12 tools/tts_align_e2e.py --outdir out
```

退出码 0 = 闭环通过。它断言三件事：

1. 关键帧驱动切法对账误差 **0 ms**；
2. 切片字节拼回 **== 原始 PCM**（不丢帧、不重复）；
3. 纯栅格切法在**同一段音频上必须失败**（末片边界不在关键帧栅格上）
   ⇒ 反向证明对账器不是摆设。

实测（2026-10-25 夜间）：

| provider | 真实 PCM | 关键帧 | `grid` | `keyframes` | 字节拼回 |
|---|---|---|---|---|---|
| `minimax`（真实 TTS） | 43468 B / 1358 ms | 34 帧 = 1360 ms | ❌ 末片 1358 ms | ✅ 误差 +0 ms | ✅ == |
| `stub`（离线替身） | 53568 B / 1674 ms | 42 帧 = 1680 ms | ❌ 末片 1674 ms | ✅ 误差 +0 ms | ✅ == |

⚠️ **两种 provider 的长度都不是 40 ms 整数倍** ⇒ 这不是偶然，是
「量化到 25 fps 必然产生 ≤1 帧尾部差」的结构性结果（见 `docs/spec/03` §2.7.4）。

## stackchan_server.py —— 真服务端替身

固件用**编译期常量**的服务器地址连接，没有运行期覆盖：

```
ws://<server>/stackChan/ws?deviceType=StackChan
```

出处 `firmware/main/hal/hal_ws_avatar.cpp:88`；服务器基址
`http://47.113.125.164:12800` 出处 `firmware/main/Kconfig.projbuild:5`。
所以本工具是**同路径同协议**的替身；部署时靠网络层（DNS / hosts / iptables
DNAT）把那个 IP 劫持到本机。

### 用法

```bash
# 起服务端
py -3.12 tools/stackchan_server.py --serve --port 12800

# 起服务端并预置一份 0x14 舞蹈 (设备上线即下发)
py -3.12 tools/stackchan_server.py --serve --port 12800 --dance keyframes.json

# 从 stdin 读关键帧
py -3.12 tools/stackchan_server.py --serve --port 12800 --dance-stdin < keyframes.json

# 自检 (必须 ALL PASS, 退出码 0)
py -3.12 tools/stackchan_server.py --self-test
```

常用参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--serve` | – | 启动服务端 |
| `--port` | `12800` | 监听端口 |
| `--mac` | `68ee8fd73668` | 设备默认 MAC（固件 URL 不带 MAC，只能这样指定） |
| `--dance` / `--dance-stdin` | – | 0x14 关键帧 JSON（**顶层必须是数组**） |
| `--strict-mac` | 关 | 关掉「只有一台设备在线时的 MAC 兜底投递」 |
| `--self-test` | – | 跑自检并退出 |

### 与 protocol_sim.py 联调

`protocol_sim.py --role app` 是 **App 侧**，本服务端是 **云侧**，两者可以在
同一个端口对上（App 会连 `ws://127.0.0.1:<port>/stackChan/ws?deviceType=App&deviceId=sim-app`）：

```bash
# 终端 1：起服务端
py -3.12 tools/stackchan_server.py --serve --port 12800

# 终端 2：App 侧，把 0x14 舞蹈发出去
py -3.12 tools/protocol_sim.py --role app --port 12800 --dance keyframes.json
```

注意 `--role app` 需要一份**关键帧 JSON 文件路径**（不是 JSON 字符串本身）。

### 协议要点（全部实读官方仓 `origin/main`，未改动官方仓）

完整事实表见 `stackchan_server.py` 顶部 docstring，这里只列最容易搞错的：

- **帧格式** `[Type:1][Length:4 BE][Payload]`（固件 `hal_ws_avatar.cpp:234`，
  云 `web_socket.go:308-323`）。**不是** 1 字节 type + 3 字节 MAC。
- **12 字节 MAC 前缀**在 payload **内部**，只有 6 类带：
  `0x01 Opus`、`0x02 Jpeg`、`0x03 ControlAvatar`、`0x04 ControlMotion`、
  `0x07 TextMessage`、`0x09 RequestCall`（云 `web_socket.go:523/537/553/569/588`）。
  **`0x14 Dance` 不带、也不剥**（云 `web_socket.go:740-746`；官方 App
  `dance.dart:193` 也不加前缀）。
- **0x14 payload 顶层必须是 JSON 数组**（固件 `json_helper.cpp:192-195`）。
- **每帧 8 个 key**：`leftEye` `rightEye` `mouth` `yawServo` `pitchServo`
  `leftRgbColor` `rightRgbColor` `durationMs`（固件 `json_helper.cpp:201-224`）。
- **舵机 angle 单位 0.1 度**，yaw ±1280、pitch 30..870
  （固件 `hal_servo.cpp:340` / `:349`）。
- **表情字段必须是 int**（固件判 `is<int>()`，`json_helper.cpp:145-164`）。
  写成 float 会被固件静默丢弃。
- **眼睛 weight 越大 = 越睁开**（固件 `eyes.cpp:71-78`）；官方情绪基线
  `eyes.cpp:102-123`：Neutral=100 / Happy=72 / Angry=70 / Sad=70 / Doubt=75 /
  Sleepy=35。
- **嘴 weight 越大 = 越张开**（固件 `mouth.cpp:48-58`）。
- **固件没有 0x15 GetAvatarPosture**（`hal_ws_avatar.cpp:49-72` 的枚举里没有），
  所以不要发 0x15 期待回复。
- **心跳**：官方云每 5 秒发 0x10（`cron.go:35` + `socket_task.go:36`），固件
  收到回 0x11（`hal_ws_avatar.cpp:287-294`）；固件 10 秒收不到任何帧会报
  Heartbeat Timeout（`hal_ws_avatar.cpp:171-174`）。本服务端照做。

### 与官方云的一处刻意差异

`split_mac_prefix()` 只在**确认前 12 字节确实是 MAC 时**才剥。官方云是无条件
切 `payload[:12]`（`web_socket.go:528`），MAC-less 的控制帧会被切成乱码；
本服务端保留原样透传。JSON payload 一定以 `{` 开头，不是十六进制字符，
所以判定无歧义。

另外真机连上来的 URL 里**没有 MAC**（`hal_ws_avatar.cpp:88`），官方云是从
`Authorization` 头解 RSA token 取的（`web_socket.go:78-99`），替身服务端解不了
RSA，所以真机只能登记成 `--mac` 指定的值；而官方 App 发控制帧时前缀里是
**真机的真实 MAC**。为此默认开启「只有一台设备在线时的兜底投递」
（`--strict-mac` 可关闭），否则真机的表情/舵机控制会被静默丢弃。

---

## check_citations.py —— 引用可溯源性体检（禁止凭记忆编造引用）

**为什么要有**：项目硬约束写着「所有结论必须有**实际抓取的来源**（给 URL）；**禁止凭记忆编造**」。
在此之前这条**只靠自觉** —— 任何人在文档里写一个 `arXiv:2501.99999` 都查不出来。

**怎么判**（全部机械可判）：

| 集合 | 定义 |
|---|---|
| **溯源池** | `docs/research/` 下带 `**主题键**：` 标记的**文献留痕快照**（当前 8 份：68/69/71/74/83 号 + `runs/` 3 份）⇒ 池里每个 ID 都是**抓取工具真实返回过**的 |
| **登记表** | `tools/citation_sources.txt` ⇒ 早期（49/51/54/55/37 号）**直接检索**得到的引用不在快照里，逐条登记（规范 URL + arXiv API 校验状态 + 首次出现文档）⇒ **登记即审计** |
| **被引集合** | `docs/spec/**.md` 与 `docs/research/**.md`（**排除池文件本身**）里出现的全部 arXiv ID 与 DOI |

判定：被引标识 ∈ 池 ∪ 登记表 ⇒ OK；否则 **FAIL**（= 可能是凭记忆写的）。

⚠️ **本门禁不联网** —— arXiv 真实性在**登记表生成时**已用 API 逐个校验并把状态落盘。

**实测基线**（2026-10-25）：全仓被引 **703** 个唯一标识（arXiv 611 + DOI 92）⇒
其中 **161 个**在窄池外，**全部 62 个 arXiv 经 arXiv API 校验存在（62/62）**。

**命令**：

```powershell
py -3.12 tools/check_citations.py --root .
py -3.12 tools/check_citations.py --self-test     # 4/4
```

**踩过的坑（写工具时踩的）**：

| 坑 | 现象 | 修法 |
|---|---|---|
| **URL 就近抓** | 把 A 论文的 ID 配上 B 论文的链接（`1607.05327` → `abs/2002.01869`） | arXiv 规范 URL **可推导**（`https://arxiv.org/abs/<id>`），不要从文档里抓 |
| **`max_results=1`** | 批量查 50 个 ID 只回 1 条 ⇒ **60/62 被误判「失效」** | `max_results` 必须 = **批大小** |
| 池边界用宽松正则 | `### 1. 标题` 这种编号标题在 74 份文档里都有 ⇒ 池不干净 | 用 `**主题键**：` 这个**渲染器写入**的标记 |

---

## check_quotes.py —— 引文保真机械校验（抄引文不许靠人眼）

**为什么要有**：2026-10-25 实测（`docs/research/80` §7，DeepSeek 员工池自己做的机械比对）——
人眼抄引文的错误率约 **10%**，且**几乎全部是「读起来没错」的错**：

| 错法 | 为什么危险 |
|---|---|
| 把主语**缩写**（`SLMs (1-12B)…` ← 原文 `Small language models (SLMs; 1-12B params…)`） | 读起来完全通顺，但已不是原文 |
| U+2010 连字符写成 ASCII `-` | 肉眼几乎不可见 |
| 把表格**两列**用箭头拼成一句 | 改变了原文结构 |
| 省略号跨行合并且未标注 | 读者以为是一句 |
| 把竖线换成全角竖线 | 改了就比对不上 ⇒ 被误当成「自己的措辞」放过 |
| 把括号改成逗号 | 同上 |
| **凭空给原文加粗** | 改变了原文的强调结构 |

**怎么判**（全部机械可判，不含主观判断）：

- **FAIL**：`docs/spec/` 里的**英文长句**引文（≥6 个英文词），在全仓所有 .md 里**找不到**
- **WARN**：中英混排引文（≥3 个英文词）找不到 ⇒ 需人眼判定
- **不报**：纯中文自有措辞（我们自己的话本就不该在别处出现）
- **登记豁免**：`tools/quote_sources.txt` —— 仓外引文（官方固件 README / Apple HIG 本机缓存 等），
  **登记即审计**（每条写明出处标签）

**命令**：

```powershell
py -3.12 tools/check_quotes.py --root .
py -3.12 tools/check_quotes.py --self-test     # 10/10
```

**首轮实检**：987 条引文 · `FAIL=0` · `WARN=146` · research 仓外英文引文 204 条（只统计）。

**⚠️ 两个我自己踩过的坑（都写进了自检夹具）**：

1. **假绿** —— haystack 若包含被检查文档**自己**，那任何引文都能在它自己所在处找到
   ⇒ 门禁恒绿。第一版实现就是这么写的，实测 `FAIL=0` 全绿，
   直到自检里「改一个词」的用例抓出来才发现。⇒ **必须排除自身**。
2. **规则静默失效** —— 原本要求「**连续** 6 个 ≥3 字母的英文词」，
   而真实引文里的 `if` / `at` / `on` 这类 2 字母词会**打断连续性**
   ⇒ 英文引用全被降级成中文软判 ⇒ 硬判形同虚设。⇒ 改为**统计整句英文词总数**。

**已知盲区**：**表格单元格内**的引文，若原文用竖线分隔而我们换成了全角竖线，
归一化后子串比对会失败 ⇒ 落 WARN 而非 FAIL ⇒ **WARN 必须人眼看**。
（这个坑连做自校验的 worker 自己也踩了 ⇒ 已由主会话修正。）

---

## check_prosody.py —— 韵律→身体 管线的离线标定体检

**为什么需要它**：`server/stackchan_ai/prosody.py` 是护城河②
（「唯一空位 = 韵律→舵机/关键帧」）的算法层。它以前**只有人读代码，没有机器判据** ⇒
答不出三个问题：情绪会不会被音频淹没、管线有没有自己造出来的伪影、输出会不会越界/超带宽。

**做法**：合成韵律语料（谐波 + 三共振峰，4 种受控变体：平/升/落/重音）离线跑**真实管线**，
把结果变成阈值。

### 它当场抓到的真缺陷（2026-10-27）

```python
env_smooth = np.convolve(env, np.ones(k_env) / k_env, mode="same")   # ← 边界补零
```

`env` 是 **dB 域（负值）**，而 `mode="same"` 在首尾**补零** ⇒ 等于把边界往 0 dB 拉
⇒ 凭空造出 **7~12 dB** 的假能量峰 ⇒ `e_norm` 首帧饱和到 1.0 ⇒
**机器人每次开口的第一个 40 ms 都会「瞪眼张嘴」再收回去**（静音时也张嘴，跨度 9）。

⚠️ **这类缺陷不报错**：自检全绿、`audit` 0 问题、67 个测试全绿、门禁全绿 —— 只在真机上看得出来。

修法 = 边界改**复制**（edge replicate，内部逐点与 `same` 一致）：

```python
env_pad = np.pad(env, (k_env // 2, k_env - 1 - k_env // 2), mode="edge")
env_smooth = np.convolve(env_pad, np.ones(k_env) / k_env, mode="valid")
```

⇒ 边界偏差 11.8 dB → **≤ 0.32 dB**；静音嘴跨度 9 → **0**；67 个后端测试全绿。
⚠️ 两份实现（`server/...prosody.py` 与 `tools/prosody_to_motion.py`）**同步**修改，否则就是新的分叉。

⚠️ **诚实说明**：修复让跨韵律变体可辨识度从 91.7% 降到 **83.3%** ——
因为伪影此前在提供**虚假**区分度 ⇒ **83.3% 才是真数字**。

### 十项判据

| 码 | 判据 | 阈值 | 实测 |
|---|---|---|---|
| PR-01 | `env` 边界不得出现补零伪影 | 首帧偏差 ≤ 1.0 dB | 0.32 dB |
| PR-02 | 静音不得张嘴 | 嘴跨度 ≤ 1 | 0 |
| PR-03 | 编译必须逐字节可复现 | 两次 JSON 相同 | True |
| PR-04 | `audit()` + 越界检查必须干净 | 0 / 0 | 0 / 0 |
| PR-05 | 42 个标量参数 | 键数 = 42 | 42 |
| PR-06 | 情绪必须可辨识（跨韵律变体留一） | 均值 ≥ 75%、最差 ≥ 60% | 83.3% / 66.7% |
| PR-07 | 情绪不得被音频淹没 | 韵律/情绪 中位距离比 < 1.0 | 0.409 |
| PR-08 | `expressiveness` 必须单调 | pitch_span / yaw_span / mouth_mean 单调不减 | 单调 |
| PR-09 | 单帧不得超 WS 上限 | ≤ 262 144 B，且一个 WS 帧 ≥ 4 帧 | 320 B / 819 帧 |
| PR-10 | 输出不得越界 | pitch / yaw / weight 全在硬限内 | 0 越界 |

### 六项自检（证明判据不是恒真）

健康仓库零 FAIL · `env` 改回补零 ⇒ PR-01 · 静音张嘴 ⇒ PR-02 · 编译不确定 ⇒ PR-03 ·
6 个情绪基线被抹平 ⇒ PR-06。

⚠️ **自检夹具踩过的坑**：第一版「静音张嘴」夹具把**所有**帧的嘴设成同一个值 90
⇒ 跨度反而是 0 ⇒ 测不出东西 ⇒ 必须让首帧 90 / 其余 30 才有「跨度」。

### 用法

```powershell
py -3.12 tools/check_prosody.py --root .        # 体检
py -3.12 tools/check_prosody.py --self-test     # 自检（6/6）
```

⚠️ 本门禁测的是**输出空间的可分性**，**不等于**「人能认出」—— 后者需要主观评测。
详见 [`docs/research/87`](../docs/research/87-韵律身体离线标定探针-可辨识度与淹没指标.md)。

---

## figma_design_sync.py —— Figma 设计稿 ⇄ iOS DesignSystem 数值漂移体检

2026-10-27 用户接入 Figma Connector 后新增。**它不是画图工具**（Connector 只有 2 个只读/导出工具，
没有写接口）—— 它的作用是**把用户的设计稿变成可判的数值漂移报告**。

### 六条判据

| 码 | 判据 | 口径 |
|---|---|---|
| FD-01 | 输入形状可识别 | 认不出就 FAIL（**fail loud，绝不静默通过**） |
| FD-02 | Swift 侧 token 提取非空 | 圆角槽位 6 个齐全 **且** 调色板 ≥ 4 套 |
| FD-03 | 圆角漂移 | 设计稿圆角值必须落在 `Shapes.swift` 登记档；`0`（直角容器）与 `≥100`（胶囊 999）豁免 |
| FD-04 | 字号下限 | 所有 TEXT 节点 `fontSize ≥ 11`（HIG `accessibility.md:40`） |
| FD-05 | 触控目标 | 所有 FRAME/COMPONENT 短边 `≥ 44`（HIG `accessibility.md:135`）—— WARN（启发式） |
| FD-06 | 颜色白名单 | 设计稿纯色必须能在 4 套调色板 12 槽位里找到（RGB 各分量差 ≤ 0.03）—— WARN |

### 输入格式（自动识别）

1. **Figma 文档** —— REST `GET /v1/files/:key` 形状（`document.children` 递归）
2. **Figma Variables** 导出（`variables` 字典，`valuesByMode` / `values`）
3. **DTCG / Tokens Studio**（`$value` + `$type`）

### 用法

```powershell
py -3.12 tools/figma_design_sync.py --figma <design.json> --root .   # 体检
py -3.12 tools/figma_design_sync.py --figma <design.json> --json      # 机器可读
py -3.12 tools/figma_design_sync.py --figma <design.json> --emit-tokens <out.json>
py -3.12 tools/figma_design_sync.py --self-test                       # 自检（6/6）
```

### 六项自检（证明判据不是恒真）

干净稿 0 FAIL · 漂移稿（圆角 24 / 字号 9pt / 容器 30×30 / 未登记色）**FAIL 数必须比干净稿多**
且 FD-03/04/05/06 全触发 · 乱输入只报 FD-01 · 解析器必须真的提取到圆角 16 与字号 17。

⚠️ **自检夹具踩过的坑**：第一版干净稿里整屏容器 `cornerRadius: 0` 被误判成「圆角漂移」。
查证后确认 **0 是合法的直角容器**（本仓库 `Shapes.swift` 只是没登记「屏幕」这个槽位）
⇒ 已加豁免并把**豁免理由写进代码注释**，不是悄悄放宽阈值。

⚠️ **本轮不接进门禁**：`tools/gates.txt` 是门禁唯一真值，而本轮**没有任何可读的 Figma 文件**
⇒ 接上去只会得到一个「永远报无输入」的空门禁。等拿到第一个可读文件、并把一份快照入库后，
再作为**第 43 项门禁**接入（届时同步改 `tools/gates.txt` + `.github/workflows/ci.yml`）。

详见 [`docs/research/89`](../docs/research/89-Figma接入实测与AI落地管线.md)。
