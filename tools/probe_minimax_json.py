#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_minimax_json.py —— 实测 MiniMax 云端能否一次产出结构化输出（E-4 的前置条件）

为什么需要它
------------
`docs/spec/00` §9 的 **O-3** 是一个开放项：
「E-4 结构化输出在 MiniMax 云端是否可用？」（情绪状态机能否实现）。

`docs/spec/00` §3 E-4 写着一条**待复核**的约束：
「MiniMax 云端 `response_format: json_schema` 仅 `MiniMax-Text-01` 支持，
而我们主力是 `MiniMax-M3.1-Flash` / `MiniMax-M3` ⇒ 云端结构化输出可能没有现成实现」。

⇒ 这条是**别人文档里的待复核结论**，不是我们自己测出来的。
⇒ 本工具把它变成**实测**：三种模式各跑 N 次，看**真的能不能一次拿到
reply + emotion + motion + intensity**。

三种模式
--------
| 模式 | 请求里加什么 | 问的是 |
|---|---|---|
| `plain` | 什么都不加，只在 system prompt 里要求输出 JSON | **纯靠提示词**能不能稳定出 JSON（最兜底） |
| `json_object` | `response_format: {"type": "json_object"}` | 云端 JSON 模式是否被支持 |
| `json_schema` | `response_format: {"type": "json_schema", "json_schema": {...}}` | 云端 schema 模式是否被支持 |

判定口径
--------
一次调用算「通过」要同时满足：
1. HTTP 200 且 `base_resp.status_code == 0`（⚠️ MiniMax 失败时可能也返回 HTTP 200）
2. 剥掉 `<think>…</think>` 后，`content` 能解析成 JSON 对象
3. 四个字段齐全且类型正确：`reply`(str) / `emotion`(str) / `motion`(str) / `intensity`(float 0..1)
4. `emotion` / `motion` 落在枚举内（与 `docs/spec/06` 的情绪表对齐）

🔒 key 纪律：key **只**从环境变量 `MINIMAX_API_KEY` 读，
构造完 Authorization 头之后**不落盘、不回显**；任何异常信息在抛出前用 `config.mask_secret` 抹掉。

用法
----
    py -3.12 tools/probe_minimax_json.py --self-test
    py -3.12 tools/probe_minimax_json.py --mode all --repeat 3

退出码：0 = 至少有一种模式通过率 ≥ 阈值（默认 80%）；1 = 都不达标或出错。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 默认 base URL（60 号 §1/§2 实测：必须是 api.minimaxi.com）
DEFAULT_BASE_URL = "https://api.minimaxi.com"
#: 默认 chat 模型（`server/stackchan_ai/config.py` 的 DEFAULT_CHAT_MODEL）
DEFAULT_MODEL = "MiniMax-M3.1-Flash"
#: key 的环境变量名
ENV_KEY = "MINIMAX_API_KEY"

#: E-4 要的四个字段
REQUIRED_FIELDS = ("reply", "emotion", "motion", "intensity")

#: 允许的情绪枚举（与 `docs/spec/06` §9.2b.2 的固件情绪表对齐）
ALLOWED_EMOTIONS = ("neutral", "happy", "angry", "sad", "doubt", "sleepy")
#: 允许的动作/身体表达枚举（粗粒度原型级 —— 见 `docs/research/78` §跨主题观察第 1 条）
ALLOWED_MOTIONS = ("idle", "nod", "shake", "lean", "tilt", "bounce", "still")

#: 内联推理块（M3 系列会把推理塞进 content）
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

#: 模型偶尔会用 ```json 包裹
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

SYSTEM_PROMPT = (
    "你是一个桌面陪伴机器人的人格引擎。"
    "请**只输出一个 JSON 对象**，不要输出任何解释、不要用 markdown 代码块包裹。"
    "字段固定为四个："
    '"reply"（字符串，你要说出口的话）、'
    '"emotion"（只能是 neutral/happy/angry/sad/doubt/sleepy 之一）、'
    '"motion"（只能是 idle/nod/shake/lean/tilt/bounce/still 之一）、'
    '"intensity"（0.0 到 1.0 之间的数字，表示情绪强度）。'
)

JSON_SUFFIX = """

【输出格式硬要求】上面的人格设定与说话方式照旧，但**这一次**你只输出一个 JSON 对象，
不要输出任何其他内容（包括思考过程、解释、markdown 代码块）：
{"reply": "...", "emotion": "neutral|happy|angry|sad|doubt|sleepy", "motion": "idle|nod|shake|lean|tilt|bounce|still", "intensity": 0.0~1.0}
其中 reply 就是你本来要说出口的话（中文口语、短句、先共情），intensity 是此刻情绪的强度。
"""

JSON_SCHEMA = {
    "name": "companion_turn",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "emotion": {"type": "string", "enum": list(ALLOWED_EMOTIONS)},
            "motion": {"type": "string", "enum": list(ALLOWED_MOTIONS)},
            "intensity": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": list(REQUIRED_FIELDS),
    },
}

#: 三种模式的请求差异
MODES = ("plain", "json_object", "json_schema")

#: ⭐ 冲突探针用的「诱导 schema」：故意与提示词**矛盾**
#:   · emotion 枚举只允许 neutral，而提示词让模型从 6 个里挑
#:   · 多要求一个提示词里**根本没提**的字段 must_be_present
#: ⇒ 若输出全部塌成 neutral 且带上 must_be_present ⇒ schema 被**真正执行**
#: ⇒ 若 emotion 仍随输入变化 ⇒ API 只是**接受**了 response_format，实际忽略
CONFLICT_SCHEMA = {
    "name": "conflict_probe",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "emotion": {"type": "string", "enum": ["neutral"]},
            "motion": {"type": "string", "enum": ["idle"]},
            "intensity": {"type": "number", "minimum": 0, "maximum": 1},
            "must_be_present": {"type": "string"},
        },
        "required": list(REQUIRED_FIELDS) + ["must_be_present"],
    },
}

#: 实测用的 prompt（要覆盖不同情绪，避免只在一种情绪上通过）
PROMPTS = [
    ("用户说：今天真开心啊，见到你真好。", "happy"),
    ("用户说：我有点难过，不太想说话。", "sad"),
    ("用户说：你怎么这么慢！我都等半天了。", "angry"),
]


# ── 纯函数（可自检） ──────────────────────────────────────────────────────

def strip_think(text: str) -> str:
    """剥掉内联 `<think>…</think>`，只留正文。"""
    if not text:
        return ""
    return _THINK_RE.sub("", text).strip()


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """从模型输出里抠出 JSON 对象；抠不出返回 None。

    处理三种常见形态：裸 JSON、```json 包裹、前后有闲聊。
    """
    if not text:
        return None
    body = strip_think(text)
    if not body:
        return None
    body = _FENCE_RE.sub("", body).strip()

    # ① 直接解析
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # ② 抠出第一个 {...} 平衡括号块
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(body):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                chunk = body[start:i + 1]
                try:
                    obj = json.loads(chunk)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    start = -1
    return None


def validate_turn(obj: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """校验一次结构化输出是否合格。返回 ``(是否通过, 原因)``。"""
    if obj is None:
        return False, "content 里抠不出 JSON 对象"
    for f in REQUIRED_FIELDS:
        if f not in obj:
            return False, "缺字段 %s" % f
    if not isinstance(obj["reply"], str) or not obj["reply"].strip():
        return False, "reply 不是非空字符串"
    if obj["emotion"] not in ALLOWED_EMOTIONS:
        return False, "emotion=%r 不在枚举内" % (obj["emotion"],)
    if obj["motion"] not in ALLOWED_MOTIONS:
        return False, "motion=%r 不在枚举内" % (obj["motion"],)
    inten = obj["intensity"]
    if isinstance(inten, bool) or not isinstance(inten, (int, float)):
        return False, "intensity 不是数字"
    if not (0.0 <= float(inten) <= 1.0):
        return False, "intensity=%r 越界" % (inten,)
    return True, "ok"


def build_payload(mode: str, user_text: str, model: str,
                  system: Optional[str] = None) -> Dict[str, Any]:
    """按模式构造请求体。``system`` 缺省用内置的 JSON 指令提示词。"""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system if system is not None else SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 512,
        "temperature": 0.6,
    }
    if mode == "json_object":
        payload["response_format"] = {"type": "json_object"}
    elif mode == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": JSON_SCHEMA,
        }
    return payload


def load_persona_system(persona_path: str) -> str:
    """加载**生产环境真实人格包**的 system_prompt，并追加 JSON 硬要求。

    为什么必须用真的人格包测：人格提示词是「中文口语、短句、先共情、不要念思考过程」，
    风格上**鼓励**自然对话输出 ⇒ 它可能和「只输出 JSON」的要求打架
    ⇒ 只用一段通用 JSON 指令测出来的 100% 说服力不够。
    """
    with io.open(persona_path, encoding="utf-8") as fh:
        data = json.load(fh)
    prompt = str(data.get("system_prompt") or "").strip()
    if not prompt:
        raise ValueError("人格包里没有 system_prompt：%s" % persona_path)
    return prompt + JSON_SUFFIX


def build_conflict_payload(user_text: str, model: str) -> Dict[str, Any]:
    """构造「诱导 schema」的请求体：schema 与提示词故意冲突。"""
    payload = build_payload("json_schema", user_text, model)
    payload["response_format"] = {
        "type": "json_schema",
        "json_schema": CONFLICT_SCHEMA,
    }
    return payload


def call_conflict_once(base_url: str, api_key: str, user_text: str,
                       model: str, timeout: float = 90.0) -> Dict[str, Any]:
    """打一次「冲突探针」，返回观测到的 emotion / 有没有 must_be_present。"""
    payload = build_conflict_payload(user_text, model)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=data, method="POST",
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
    )
    out: Dict[str, Any] = {"http": 0, "base_ok": False, "emotion": None,
                           "has_extra": False, "why": ""}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out["http"] = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        out["http"] = exc.code
        try:
            raw = exc.read()
        except Exception:
            raw = b""
    except Exception as exc:
        out["why"] = _mask(str(exc), api_key)
        return out

    try:
        parsed = json.loads(raw.decode("utf-8", "ignore"))
    except Exception:
        out["why"] = "响应不是 JSON"
        return out

    base_resp = parsed.get("base_resp") if isinstance(parsed, dict) else None
    code = int(base_resp.get("status_code") or 0) if isinstance(base_resp, dict) else 0
    out["base_ok"] = (code == 0)
    if not out["base_ok"]:
        out["why"] = "base_resp.status_code=%s" % code
        return out

    choices = parsed.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    obj = extract_json_object(str(message.get("content") or ""))
    if obj is None:
        out["why"] = "抠不出 JSON"
        return out
    out["emotion"] = obj.get("emotion")
    out["has_extra"] = "must_be_present" in obj
    out["motion"] = obj.get("motion")
    return out


# ── 网络（实测） ─────────────────────────────────────────────────────────

def _mask(text: str, key: str) -> str:
    if not text:
        return text
    if key and len(key) >= 8 and key in text:
        return text.replace(key, "***")
    return text


def call_once(base_url: str, api_key: str, mode: str, user_text: str,
              model: str, timeout: float = 90.0,
              system: Optional[str] = None) -> Dict[str, Any]:
    """打一次 chat，返回判定结果字典（**不含 key**）。"""
    payload = build_payload(mode, user_text, model, system)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=data, method="POST",
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
    )
    out: Dict[str, Any] = {"mode": mode, "http": 0, "base_ok": False,
                           "json_ok": False, "pass": False, "why": ""}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out["http"] = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        out["http"] = exc.code
        try:
            raw = exc.read()
        except Exception:
            raw = b""
    except Exception as exc:
        out["why"] = _mask(str(exc), api_key)
        return out

    try:
        parsed = json.loads(raw.decode("utf-8", "ignore"))
    except Exception:
        out["why"] = "响应不是 JSON"
        return out

    base_resp = parsed.get("base_resp") if isinstance(parsed, dict) else None
    code = int(base_resp.get("status_code") or 0) if isinstance(base_resp, dict) else 0
    out["base_ok"] = (code == 0)
    if not out["base_ok"]:
        out["why"] = "base_resp.status_code=%s %s" % (
            code, _mask(str((base_resp or {}).get("status_msg") or ""), api_key))
        return out

    choices = parsed.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    content = str(message.get("content") or "")
    obj = extract_json_object(content)
    out["json_ok"] = obj is not None
    ok, why = validate_turn(obj)
    out["pass"] = ok
    out["why"] = why
    if ok:
        out["turn"] = obj
    return out


# ── 自检（无网络） ───────────────────────────────────────────────────────

def run_self_test() -> int:
    print("[self-test] probe_minimax_json.py 门禁自检")
    print("=" * 64)
    passed = failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    # ① 剥 think
    check("剥掉 <think> 内联推理",
          strip_think("<think>我想想</think>你好") == "你好",
          strip_think("<think>我想想</think>你好"))

    # ② 裸 JSON
    obj = extract_json_object('{"reply":"hi","emotion":"happy","motion":"nod","intensity":0.7}')
    check("裸 JSON 能抠出对象", obj is not None and obj.get("emotion") == "happy")

    # ③ ```json 包裹
    obj = extract_json_object('```json\n{"reply":"hi","emotion":"sad","motion":"tilt","intensity":0.3}\n```')
    check("```json 包裹能抠出对象", obj is not None and obj.get("emotion") == "sad")

    # ④ 前后有闲聊
    obj = extract_json_object('好的，这是结果：\n{"reply":"hi","emotion":"angry","motion":"shake","intensity":0.9}\n希望有帮助！')
    check("带闲聊的 JSON 能抠出对象", obj is not None and obj.get("emotion") == "angry")

    # ⑤ <think> + JSON 组合
    obj = extract_json_object('<think>思考</think>{"reply":"hi","emotion":"neutral","motion":"idle","intensity":0.1}')
    check("<think> + JSON 组合能抠出对象", obj is not None and obj.get("motion") == "idle")

    # ⑥ 不是 JSON
    check("非 JSON 返回 None", extract_json_object("今天天气不错呢") is None)

    # ⑦ 校验器：缺字段
    ok, why = validate_turn({"reply": "hi", "emotion": "happy"})
    check("缺字段判不合格", not ok, why)

    # ⑧ 校验器：emotion 越界
    ok, why = validate_turn({"reply": "hi", "emotion": "excited",
                             "motion": "nod", "intensity": 0.5})
    check("emotion 不在枚举判不合格", not ok, why)

    # ⑨ 校验器：motion 越界
    ok, why = validate_turn({"reply": "hi", "emotion": "happy",
                             "motion": "wiggle", "intensity": 0.5})
    check("motion 不在枚举判不合格", not ok, why)

    # ⑩ 校验器：intensity 越界
    ok, why = validate_turn({"reply": "hi", "emotion": "happy",
                             "motion": "nod", "intensity": 1.7})
    check("intensity 越界判不合格", not ok, why)

    # ⑪ 校验器：bool 不算数字
    ok, why = validate_turn({"reply": "hi", "emotion": "happy",
                             "motion": "nod", "intensity": True})
    check("bool 不算 intensity 判不合格", not ok, why)

    # ⑫ 校验器：合格样本
    ok, why = validate_turn({"reply": "嗨", "emotion": "happy",
                             "motion": "nod", "intensity": 0.8})
    check("合格样本判通过", ok, why)

    # ⑬ payload：plain 模式不带 response_format
    p = build_payload("plain", "hi", "m")
    check("plain 模式不带 response_format", "response_format" not in p)

    # ⑭ payload：json_object 模式
    p = build_payload("json_object", "hi", "m")
    check("json_object 模式带 response_format",
          p.get("response_format", {}).get("type") == "json_object")

    # ⑮ payload：json_schema 模式带四个必需字段
    p = build_payload("json_schema", "hi", "m")
    rs = p.get("response_format", {}).get("json_schema", {})
    check("json_schema 模式 schema 覆盖四个必需字段",
          set(REQUIRED_FIELDS) <= set(rs.get("schema", {}).get("required", [])))

    print("=" * 64)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


# ── 主流程 ───────────────────────────────────────────────────────────────

def run_probe(base_url: str, api_key: str, mode: str, repeat: int,
              model: str, threshold: float,
              system: Optional[str] = None) -> int:
    modes = [m for m in MODES if mode == "all" or m == mode]
    rows: List[Dict[str, Any]] = []
    print("=" * 74)
    print("probe_minimax_json —— MiniMax 云端结构化输出（E-4）实测")
    print("=" * 74)
    print("base_url = %s ｜ model = %s ｜ 每种模式 %d 次" % (base_url, model, repeat))
    print("system = %s" % ("生产人格包（personas/enfp.json）+ JSON 硬要求"
                            if system else "内置通用 JSON 指令"))
    print("")

    for m in modes:
        results = []
        for i in range(repeat):
            user_text, _want = PROMPTS[i % len(PROMPTS)]
            res = call_once(base_url, api_key, m, user_text, model, system=system)
            results.append(res)
            flag = "PASS" if res["pass"] else "FAIL"
            print("  [%s] %-12s #%d  http=%s base_ok=%s  %s  %s"
                  % (flag, m, i + 1, res["http"], res["base_ok"],
                     res["why"], "" if res["pass"] else ""))
        n = len(results)
        p = sum(1 for r in results if r["pass"])
        rows.append({
            "mode": m,
            "n": n,
            "http_ok": sum(1 for r in results if r["http"] == 200),
            "base_ok": sum(1 for r in results if r["base_ok"]),
            "json_ok": sum(1 for r in results if r["json_ok"]),
            "pass": p,
            "rate": (p / n) if n else 0.0,
            "why": sorted({r["why"] for r in results if r["why"]}),
        })

    print("")
    print("=" * 74)
    print("| 模式 | 次数 | HTTP 200 | base_resp=0 | 抠出 JSON | 四字段齐全 | 通过率 |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print("| %s | %d | %d | %d | %d | %d | **%.0f%%** |"
              % (r["mode"], r["n"], r["http_ok"], r["base_ok"],
                 r["json_ok"], r["pass"], r["rate"] * 100))
    print("=" * 74)

    best = max(rows, key=lambda r: r["rate"]) if rows else None
    if best is None:
        print("没有任何结果")
        return 1
    print("最佳模式：%s（%.0f%%，阈值 %.0f%%）" % (best["mode"], best["rate"] * 100, threshold * 100))
    if best["rate"] >= threshold:
        print("⇒ ✅ E-4 可行：至少有一种模式稳定产出 reply+emotion+motion+intensity")
        return 0
    print("⇒ ❌ E-4 按现状不可行：需要在 pipeline 里加「提示词 + 解析 + 重试」兜底")
    return 1


def run_conflict_probe(base_url: str, api_key: str, repeat: int, model: str) -> int:
    """⭐ 冲突探针：判断 `response_format: json_schema` 到底是**被执行**还是**被忽略**。

    为什么必须做这一步：三种模式都 100% 通过，但 `plain`（纯提示词）也 100%
    ⇒ 「输出是合法 JSON」这件事**证明不了** schema 起了作用
    ⇒ 只能靠**故意冲突**来分辨：
      · schema 说 emotion 只能是 neutral，提示词说从 6 个里挑 ⇒ 看输出塌不塌
      · schema 多要求一个提示词没提的字段 ⇒ 看它会不会自己补上
    """
    print("=" * 74)
    print("probe_minimax_json —— ⭐ 冲突探针（schema 到底被执行还是被忽略）")
    print("=" * 74)
    print("model = %s ｜ 跑 %d 次" % (model, repeat))
    print("")
    emotions: List[Any] = []
    extra_hits = 0
    http_ok = 0
    for i in range(repeat):
        user_text, _want = PROMPTS[i % len(PROMPTS)]
        res = call_conflict_once(base_url, api_key, user_text, model)
        if res["http"] == 200:
            http_ok += 1
        emotions.append(res.get("emotion"))
        if res.get("has_extra"):
            extra_hits += 1
        print("  #%d  http=%s base_ok=%s emotion=%r must_be_present=%s  %s"
              % (i + 1, res["http"], res["base_ok"], res.get("emotion"),
                 res.get("has_extra"), res.get("why", "")))
    print("")
    print("=" * 74)
    print("| 观测 | 值 |")
    print("|---|---|")
    print("| HTTP 200 | %d / %d |" % (http_ok, repeat))
    print("| 观测到的 emotion 分布 | %s |" % (emotions,))
    print("| 出现 must_be_present 的次数 | %d / %d |" % (extra_hits, repeat))
    print("=" * 74)

    all_neutral = bool(emotions) and all(e == "neutral" for e in emotions)
    varied = len({e for e in emotions if e is not None}) > 1
    if all_neutral and extra_hits == repeat:
        print("⇒ ✅ **schema 被真正执行**：emotion 全被压成 neutral、"
              "提示词没提的字段也被补上 ⇒ `response_format: json_schema` 在 %s 上可用。" % model)
        print("   ⇒ E-4 可以直接用 schema 约束，**不需要**自己写解析兜底。")
        return 0
    if varied:
        print("⇒ ⚠️ **schema 被接受但未生效**：emotion 仍随提示词变化 ⇒ "
              "API 只是容忍了 `response_format`，实际由提示词决定输出。")
        print("   ⇒ E-4 仍可行，但**必须**自己写「解析 + 重试 + 兜底」，不能依赖 schema 约束。")
        return 0
    print("⇒ ❓ 结论不明确：既没全塌成 neutral，emotion 也没变化 ⇒ 需加大样本再判。")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MiniMax 云端结构化输出（E-4）实测")
    ap.add_argument("--self-test", action="store_true", help="门禁自检（无网络）")
    ap.add_argument("--mode", default="all", choices=list(("all",) + MODES),
                    help="要测的模式")
    ap.add_argument("--conflict", action="store_true",
                    help="只跑冲突探针（判断 schema 是被执行还是被忽略）")
    ap.add_argument("--persona", default="",
                    help="人格包路径（如 personas/enfp.json）⇒ 用**生产真实人格提示词**测")
    ap.add_argument("--repeat", type=int, default=3, help="每种模式跑几次")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="chat 模型")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="base URL")
    ap.add_argument("--threshold", type=float, default=0.8, help="通过率阈值")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test()

    api_key = os.environ.get(ENV_KEY, "")
    if not api_key:
        print("缺少环境变量 %s（key 只从环境变量读，不落盘）" % ENV_KEY)
        return 2
    if args.conflict:
        return run_conflict_probe(args.base_url, api_key, max(1, args.repeat), args.model)
    system = None
    if args.persona:
        try:
            system = load_persona_system(args.persona)
        except Exception as exc:
            print("读人格包失败：%s" % exc)
            return 2
    return run_probe(args.base_url, api_key, args.mode, max(1, args.repeat),
                     args.model, args.threshold, system)


if __name__ == "__main__":
    sys.exit(main())
