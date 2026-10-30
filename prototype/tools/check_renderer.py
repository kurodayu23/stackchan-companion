#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_renderer.py —— 小栈表情渲染器 / 参数规范 一致性校验

Python 3.12，**只用标准库**。

校验项
------
1. functions   HTML 里引用的每个 JS 函数都存在
2. defaults    渲染器 15 个参数默认值 == docs/spec/06 §3 的默认值表
3. polarity    眼睛 / 嘴的 weight 极性 == 规范（断言能区分「极性写反」）
4. coefficient x/y 换算系数 6.25 在渲染器与规范里一致
5. geometry    元素基准位置（眼 90/230/104、嘴 160/146）== 规范 §2.3
6. mutations   三个变异用例必须被抓到：
               极性写反 / 系数写成 1.0 / 改掉一个默认值

做法：不靠字符串匹配猜语义，而是把渲染器里那几个**纯数学函数**抽出来，
用一个内置的极小 JS 表达式求值器**实际求值**，再和固件推导出的期望值比对。

用法：py -3.12 prototype/tools/check_renderer.py
退出码：0 = ALL PASS；1 = 有 FAIL
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML_PATH = REPO / "prototype" / "components" / "expression-renderer.html"
SPEC_PATH = REPO / "docs" / "spec" / "06-表情参数模型.md"

JS_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "function", "return",
    "typeof", "new", "do", "else", "in", "of", "await", "async", "delete", "void",
}
JS_BUILTINS = {
    "setTimeout", "setInterval", "clearInterval", "clearTimeout",
    "requestAnimationFrame", "parseInt", "parseFloat", "isNaN", "isFinite",
    "String", "Number", "Boolean", "Array", "Object",
}


class JsError(Exception):
    pass


# --------------------------------------------------------------------------
# 极小 JS 子集求值器（只支持本渲染器实际用到的语法）
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<num>\d+\.\d+|\d+)
    | (?P<str>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
    | (?P<ident>[A-Za-z_$][A-Za-z0-9_$]*)
    | (?P<op>===|!==|==|!=|<=|>=|&&|\|\||[-+*/%<>=!?:.,()\[\]{};])
    """,
    re.X,
)


def tokenize(text: str):
    toks = []
    i = 0
    n = len(text)
    while i < n:
        m = _TOKEN_RE.match(text, i)
        if not m:
            raise JsError("无法分词: %r" % text[i:i + 20])
        i = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        toks.append((kind, m.group()))
    return toks


def strip_js(text: str) -> str:
    """去掉注释与字符串字面量，避免误判函数调用点。"""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " ", text)
    return text


def truthy(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return len(v) > 0
    return bool(v)


def loose_eq(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return truthy(a) == truthy(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


class JsEnv:
    """保存常量与函数定义。"""

    def __init__(self, functions, constants):
        self.functions = functions
        self.constants = constants

    # -- 内置成员 --
    def call_member(self, obj: str, member: str, args):
        if obj == "Math":
            if member == "trunc":
                return math.trunc(args[0])
            if member == "floor":
                return math.floor(args[0])
            if member == "ceil":
                return math.ceil(args[0])
            if member == "round":
                return math.floor(args[0] + 0.5)
            if member == "abs":
                return abs(args[0])
            if member in ("min", "max"):
                vals = args[0] if len(args) == 1 and isinstance(args[0], list) else args
                return min(vals) if member == "min" else max(vals)
            raise JsError("未知 Math.%s" % member)
        if obj == "JSON" and member == "parse":
            import json
            return json.loads(args[0])
        if obj == "Array" and member == "isArray":
            return isinstance(args[0], list)
        raise JsError("未知成员 %s.%s" % (obj, member))

    def get_member(self, obj: str, member: str):
        if obj == "Math":
            return getattr(math, member, None)
        raise JsError("未知成员 %s.%s" % (obj, member))

    # -- 调用 --
    def call(self, name: str, args):
        if name in self.functions:
            params, body = self.functions[name]
            local = {}
            for idx, p in enumerate(params):
                local[p] = args[idx] if idx < len(args) else None
            return self.eval_body(body, local)
        raise JsError("调用了不存在的函数: %s" % name)

    def eval_body(self, body: str, local: dict):
        parser = Parser(tokenize(body), self, local)
        parser.exec_block()
        return parser.ret


class Parser:
    def __init__(self, toks, env, local):
        self.toks = toks
        self.pos = 0
        self.env = env
        self.local = dict(local or {})
        self.ret = None

    # -- 词法 --
    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else (None, None)

    def next(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def expect(self, text):
        kind, val = self.next()
        if val != text:
            raise JsError("期望 %r，实际 %r" % (text, val))

    # -- 语句 --
    def exec_block(self):
        while self.pos < len(self.toks):
            self.exec_stmt()

    def exec_stmt(self):
        kind, text = self.peek()
        if text == "if":
            self.next()
            self.expect("(")
            cond = self.expr()
            self.expect(")")
            block = self.parse_block()
            if truthy(cond):
                sub = Parser(block, self.env, self.local)
                sub.exec_block()
                if sub.ret is not None:
                    self.ret = sub.ret
            return None
        if text == "return":
            self.next()
            val = self.expr()
            if self.peek()[1] == ";":
                self.next()
            self.ret = val
            return val
        if text == "var":
            self.next()
            name = self.next()[1]
            self.expect("=")
            val = self.expr()
            if self.peek()[1] == ";":
                self.next()
            self.local[name] = val
            return None
        val = self.expr()
        if self.peek()[1] == ";":
            self.next()
        return None

    def parse_block(self):
        self.expect("{")
        toks = []
        depth = 0
        while True:
            kind, text = self.peek()
            if kind is None:
                break
            if text == "}" and depth == 0:
                self.next()
                break
            if text == "{":
                depth += 1
            elif text == "}":
                depth -= 1
            toks.append(self.next())
        return toks

    # -- 表达式 --
    def expr(self):
        return self.ternary()

    def ternary(self):
        cond = self.logical_or()
        if self.peek()[1] == "?":
            self.next()
            a = self.ternary()
            self.expect(":")
            b = self.ternary()
            return a if truthy(cond) else b
        return cond

    def logical_or(self):
        left = self.logical_and()
        while self.peek()[1] == "||":
            self.next()
            right = self.logical_and()
            left = truthy(left) or truthy(right)
        return left

    def logical_and(self):
        left = self.equality()
        while self.peek()[1] == "&&":
            self.next()
            right = self.equality()
            left = truthy(left) and truthy(right)
        return left

    def equality(self):
        left = self.relational()
        while self.peek()[1] in ("===", "!==", "==", "!="):
            op = self.next()[1]
            right = self.relational()
            if op == "===":
                left = left == right
            elif op == "!==":
                left = left != right
            elif op == "==":
                left = loose_eq(left, right)
            else:
                left = not loose_eq(left, right)
        return left

    def relational(self):
        left = self.additive()
        while self.peek()[1] in ("<", ">", "<=", ">="):
            op = self.next()[1]
            right = self.additive()
            if op == "<":
                left = left < right
            elif op == ">":
                left = left > right
            elif op == "<=":
                left = left <= right
            else:
                left = left >= right
        return left

    def additive(self):
        left = self.multiplicative()
        while self.peek()[1] in ("+", "-"):
            op = self.next()[1]
            right = self.multiplicative()
            left = left + right if op == "+" else left - right
        return left

    def multiplicative(self):
        left = self.unary()
        while self.peek()[1] in ("*", "/", "%"):
            op = self.next()[1]
            right = self.unary()
            if op == "*":
                left = left * right
            elif op == "/":
                left = left / right
            else:
                left = left % right
        return left

    def unary(self):
        kind, text = self.peek()
        if text == "-":
            self.next()
            return -self.unary()
        if text == "+":
            self.next()
            return self.unary()
        if text == "!":
            self.next()
            return not truthy(self.unary())
        return self.primary()

    def primary(self):
        kind, text = self.next()
        if kind == "num":
            return float(text) if "." in text else int(text)
        if kind == "str":
            return text[1:-1]
        if text == "(":
            val = self.expr()
            self.expect(")")
            return val
        if kind == "ident":
            if self.peek()[1] == ".":
                self.next()
                member = self.next()[1]
                if self.peek()[1] == "(":
                    self.next()
                    args = self.parse_args()
                    return self.env.call_member(text, member, args)
                return self.env.get_member(text, member)
            if self.peek()[1] == "(":
                self.next()
                args = self.parse_args()
                return self.env.call(text, args)
            return self.lookup(text)
        raise JsError("意外 token: %r" % (text,))

    def parse_args(self):
        args = []
        if self.peek()[1] != ")":
            while True:
                args.append(self.expr())
                if self.peek()[1] == ",":
                    self.next()
                    continue
                break
        self.expect(")")
        return args

    def lookup(self, name):
        if name in self.local:
            return self.local[name]
        if name in self.env.constants:
            return self.env.constants[name]
        raise JsError("未定义的标识符: %s" % name)


# --------------------------------------------------------------------------
# 从 HTML 里抽取 JS
# --------------------------------------------------------------------------

def extract_script(html: str) -> str:
    blocks = []
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.S | re.I):
        attrs = m.group(1).lower()
        if "application/json" in attrs:
            continue
        blocks.append(m.group(2))
    return "\n".join(blocks)


def extract_constants(script: str):
    consts = {}
    for m in re.finditer(r"\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(-?\d+(?:\.\d+)?)\s*;", script):
        raw = m.group(2)
        consts[m.group(1)] = float(raw) if "." in raw else int(raw)
    return consts


def extract_functions(script: str):
    funcs = {}
    for m in re.finditer(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", script):
        name = m.group(1)
        if name in funcs:
            continue
        pm = re.match(r"\s*([^)]*)\)", script[m.end():])
        params = [p.strip() for p in pm.group(1).split(",") if p.strip()]
        start = script.find("{", m.end())
        if start < 0:
            continue
        depth = 0
        idx = start
        while idx < len(script):
            if script[idx] == "{":
                depth += 1
            elif script[idx] == "}":
                depth -= 1
                if depth == 0:
                    break
            idx += 1
        funcs[name] = (params, script[start + 1:idx])
    return funcs


def find_call_sites(script: str):
    stripped = strip_js(script)
    return set(re.findall(r"(?<![.\w$])([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", stripped))


def find_const_functions(script: str):
    """`const NAME = function (...) {...}` 也算一个已定义的函数名。"""
    return set(re.findall(r"\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function\s*\(", script))


def parse_html_defaults(script: str):
    m = re.search(r"\bconst\s+DEFAULT_PARAMS\s*=\s*\{(.*?)\};", script, flags=re.S)
    if not m:
        return None
    body = m.group(1)
    out = {}
    for em in re.finditer(r"(leftEye|rightEye|mouth)\s*:\s*\{([^}]*)\}", body):
        fields = {}
        for fm in re.finditer(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*(-?\d+)", em.group(2)):
            fields[fm.group(1)] = int(fm.group(2))
        out[em.group(1)] = fields
    return out


def parse_spec_defaults(spec: str):
    if "## §3 " not in spec:
        return None
    sec = spec.split("## §3 ")[1].split("## §4 ")[0]
    out = {}
    for elem in ("leftEye", "rightEye", "mouth"):
        m = re.search(r"^\|\s*`%s`\s*\|([^\n]*)$" % elem, sec, flags=re.M)
        if not m:
            return None
        nums = [int(c) for c in (x.strip() for x in m.group(1).split("|"))
                if re.fullmatch(r"-?\d+", c)]
        if len(nums) != 5:
            return None
        out[elem] = dict(zip(["x", "y", "rotation", "weight", "size"], nums))
    return out


def extract_json_schemas(spec: str):
    """取规范里的 ```json 代码块，返回能解析成 JSON Schema 的那些。"""
    out = []
    for m in re.finditer(r"```json\s*\n(.*?)\n```", spec, flags=re.S):
        raw = m.group(1)
        if '"$schema"' not in raw:
            continue
        try:
            out.append((raw, json.loads(raw)))
        except json.JSONDecodeError as exc:
            out.append((raw, exc))
    return out


def check_schemas(spec: str):
    """规范里的 JSON Schema 必须合法且自洽。返回 [(category, message)]。"""
    fails = []
    blocks = extract_json_schemas(spec)
    if len(blocks) != 2:
        fails.append(("schema", "规范里应恰好有 2 个 JSON Schema 代码块，实际 %d" % len(blocks)))
        return fails

    parsed = []
    for raw, obj in blocks:
        if isinstance(obj, Exception):
            fails.append(("schema", "JSON Schema 无法解析: %s" % obj))
            continue
        parsed.append(obj)

    if len(parsed) != 2:
        return fails

    by_title = {}
    for obj in parsed:
        by_title[obj.get("title", "")] = obj

    avatar = next((o for o in parsed if o.get("type") == "object"), None)
    seq = next((o for o in parsed if o.get("type") == "array"), None)

    if avatar is None:
        fails.append(("schema", "找不到 0x03 的对象型 Schema"))
    if seq is None:
        fails.append(("schema", "找不到 0x14 的数组型 Schema"))

    for obj in parsed:
        if obj.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fails.append(("schema", "$schema 必须是 Draft 2020-12：%s" % obj.get("$schema")))
        # $ref 目标必须存在
        defs = obj.get("$defs", {})
        for ref in re.findall(r'"\$ref"\s*:\s*"#/\$defs/([A-Za-z0-9_]+)"', json.dumps(obj, ensure_ascii=False)):
            if ref not in defs:
                fails.append(("schema", "$ref 指向不存在的 $defs/%s" % ref))

    if avatar is not None:
        if set(avatar.get("properties", {}).keys()) != {"leftEye", "rightEye", "mouth"}:
            fails.append(("schema", "0x03 的顶层属性必须恰好是 leftEye/rightEye/mouth"))
        if avatar.get("additionalProperties") is not False:
            fails.append(("schema", "0x03 必须 additionalProperties: false"))
        dr = avatar.get("dependentRequired", {})
        if dr.get("x") != ["y"] or dr.get("y") != ["x"]:
            fails.append(("schema", "0x03 必须用 dependentRequired 表达 x/y 同生共死"))

    if seq is not None:
        kf = seq.get("$defs", {}).get("keyframe", {})
        keys = set(kf.get("properties", {}).keys())
        want8 = {"leftEye", "rightEye", "mouth", "yawServo", "pitchServo",
                 "leftRgbColor", "rightRgbColor", "durationMs"}
        if keys != want8:
            fails.append(("schema", "0x14 关键帧必须恰好 8 个 key，实际 %s" % sorted(keys)))
        if kf.get("additionalProperties") is not False:
            fails.append(("schema", "0x14 关键帧必须 additionalProperties: false"))

    # 特征字段：5 个、全部 integer、范围正确
    for obj in parsed:
        feat = obj.get("$defs", {}).get("feature", {})
        props = feat.get("properties", {})
        if set(props.keys()) != {"x", "y", "rotation", "weight", "size"}:
            fails.append(("schema", "feature 必须恰好 5 个字段"))
            continue
        ranges = {"x": (-100, 100), "y": (-100, 100), "rotation": (0, 3600),
                  "weight": (0, 100), "size": (-100, 100)}
        for field, (lo, hi) in ranges.items():
            p = props[field]
            if p.get("type") != "integer":
                fails.append(("schema", "feature.%s 必须是 integer" % field))
            if p.get("minimum") != lo or p.get("maximum") != hi:
                fails.append(("schema", "feature.%s 范围应为 %s..%s" % (field, lo, hi)))

    return fails


# --------------------------------------------------------------------------
# 校验主体
# --------------------------------------------------------------------------

def check(html: str, spec: str):
    """返回 [(category, message)]，空列表 = 全过。"""
    fails = []
    script = extract_script(html)
    if not script.strip():
        return [("functions", "HTML 里找不到 <script> 块")]

    consts = extract_constants(script)
    funcs = extract_functions(script)
    env = JsEnv(funcs, consts)

    # ---- 1. 引用的每个 JS 函数都存在 ----
    defined = set(funcs) | find_const_functions(script)
    for name in sorted(find_call_sites(script)):
        if name in JS_KEYWORDS or name in JS_BUILTINS:
            continue
        if name not in defined:
            fails.append(("functions", "引用的 JS 函数不存在: %s" % name))

    # ---- 2. 15 个默认值与规范一致 ----
    html_defaults = parse_html_defaults(script)
    spec_defaults = parse_spec_defaults(spec)
    if html_defaults is None:
        fails.append(("defaults", "HTML 里解析不到 DEFAULT_PARAMS"))
    if spec_defaults is None:
        fails.append(("defaults", "docs/spec/06 里解析不到 §3 默认值表"))
    if html_defaults and spec_defaults:
        for elem in ("leftEye", "rightEye", "mouth"):
            for field in ("x", "y", "rotation", "weight", "size"):
                hv = html_defaults.get(elem, {}).get(field)
                sv = spec_defaults.get(elem, {}).get(field)
                if hv is None:
                    fails.append(("defaults", "HTML 默认值缺 %s.%s" % (elem, field)))
                elif hv != sv:
                    fails.append(("defaults", "%s.%s 默认值不一致：渲染器 %s vs 规范 %s"
                                  % (elem, field, hv, sv)))

    # ---- 3. 极性（行为级，能区分「极性写反」）----
    try:
        eye_d = env.call("eyeDiameter", [0])
        if eye_d != 20:
            fails.append(("polarity", "eyeDiameter(0) 应为 20，实际 %s" % eye_d))
        if env.call("eyeDiameter", [-100]) != 8:
            fails.append(("polarity", "eyeDiameter(-100) 应为 8"))
        if env.call("eyeDiameter", [100]) != 32:
            fails.append(("polarity", "eyeDiameter(100) 应为 32"))

        # weight=0 ⇒ 眼睑正好盖满（偏移 0）；weight=100 ⇒ 眼睑上移一个眼高（偏移 = -眼径）
        if env.call("eyeLidOffsetY", [20, 0]) != 0:
            fails.append(("polarity", "eyeLidOffsetY(20,0) 应为 0（全闭）"))
        if env.call("eyeLidOffsetY", [20, 100]) != -20:
            fails.append(("polarity", "eyeLidOffsetY(20,100) 应为 -20（全睁，眼睑上移一个眼高）"))
        # 越往上（越负）= 越睁开 ⇒ 眼睑偏移必须**单调不增**。
        # 注意固件是整数除法（截断），weight 0..4 时偏移都为 0 ⇒ 逐点只能要求「不增」，
        # 「严格递增」在每 10 个单位一档上校验。
        prev = None
        for w in range(0, 101):
            v = env.call("eyeLidOffsetY", [20, w])
            if prev is not None and v > prev:
                fails.append(("polarity", "眼睑偏移未随 weight 单调不增（weight=%s 时 %s）" % (w, v)))
                break
            prev = v
        # 睁眼程度 = -lid/eyeD，端点必须是 0 / 1，且每 10 单位严格递增
        opens = [-env.call("eyeLidOffsetY", [20, w]) / 20.0 for w in range(0, 101)]
        if abs(opens[0]) > 1e-9 or abs(opens[-1] - 1.0) > 1e-9:
            fails.append(("polarity", "睁眼程度端点不对：weight0=%s weight100=%s" % (opens[0], opens[-1])))
        coarse = [opens[w] for w in range(0, 101, 10)]
        if any(coarse[i + 1] <= coarse[i] for i in range(len(coarse) - 1)):
            fails.append(("polarity", "睁眼程度未随 weight 严格递增（每 10 单位一档）（极性写反？）"))

        # 嘴：weight 越大越高、越圆；但越窄
        if env.call("mouthHeight", [0]) != 6:
            fails.append(("polarity", "mouthHeight(0) 应为 6（闭嘴细线）"))
        if env.call("mouthHeight", [100]) != 50:
            fails.append(("polarity", "mouthHeight(100) 应为 50（大开口）"))
        if env.call("mouthWidth", [0]) != 90:
            fails.append(("polarity", "mouthWidth(0) 应为 90"))
        if env.call("mouthWidth", [100]) != 60:
            fails.append(("polarity", "mouthWidth(100) 应为 60"))
        if env.call("mouthRadius", [0]) != 0:
            fails.append(("polarity", "mouthRadius(0) 应为 0"))
        if env.call("mouthRadius", [100]) != 16:
            fails.append(("polarity", "mouthRadius(100) 应为 16"))
        prev_h = None
        for w in range(0, 101):
            v = env.call("mouthHeight", [w])
            if prev_h is not None and v < prev_h:
                fails.append(("polarity", "嘴高未随 weight 单调不减（weight=%s 时 %s）" % (w, v)))
                break
            prev_h = v
        prev_w = None
        for w in range(0, 101):
            v = env.call("mouthWidth", [w])
            if prev_w is not None and v > prev_w:
                fails.append(("polarity", "嘴宽未随 weight 单调不增（weight=%s 时 %s）" % (w, v)))
                break
            prev_w = v
        heights = [env.call("mouthHeight", [w]) for w in range(0, 101, 10)]
        widths = [env.call("mouthWidth", [w]) for w in range(0, 101, 10)]
        if any(heights[i + 1] <= heights[i] for i in range(len(heights) - 1)):
            fails.append(("polarity", "嘴高未随 weight 严格递增（每 10 单位一档）"))
        if any(widths[i + 1] >= widths[i] for i in range(len(widths) - 1)):
            fails.append(("polarity", "嘴宽未随 weight 严格递减（每 10 单位一档）"))
    except JsError as exc:
        fails.append(("polarity", "求值失败: %s" % exc))

    # ---- 4. 换算系数 6.25 ----
    try:
        upp = consts.get("UNITS_PER_PX")
        if upp != 6.25:
            fails.append(("coefficient", "UNITS_PER_PX 应为 6.25，实际 %s" % upp))
        if env.call("unitToPx", [100]) != 16:
            fails.append(("coefficient", "unitToPx(100) 应为 16"))
        if env.call("unitToPx", [-100]) != -16:
            fails.append(("coefficient", "unitToPx(-100) 应为 -16"))
        if env.call("pxToUnit", [16]) != 100:
            fails.append(("coefficient", "pxToUnit(16) 应为 100"))
        # 关键：固件整数映射必须与连续换算一致 ⇒ 系数是「承重」的
        for unit in (-100, -50, 0, 37, 50, 100):
            exact = env.call("positionOffsetPx", [unit])
            cont = math.trunc(env.call("unitToPx", [unit]))
            if exact != cont:
                fails.append(("coefficient", "positionOffsetPx(%s)=%s 与 trunc(unitToPx)=%s 不一致"
                              % (unit, exact, cont)))
    except JsError as exc:
        fails.append(("coefficient", "求值失败: %s" % exc))

    # ---- 5. 元素基准位置（规范 §2.3）----
    try:
        expect = [
            ("eyeCenterX", [True, 0], 90, "左眼中心 x"),
            ("eyeCenterX", [False, 0], 230, "右眼中心 x"),
            ("eyeCenterY", [0], 104, "眼睛中心 y"),
            ("mouthCenterX", [0], 160, "嘴中心 x"),
            ("mouthCenterY", [0], 146, "嘴中心 y"),
            ("eyeCenterX", [True, 100], 106, "左眼中心 x（+100 偏移）"),
            ("eyeCenterX", [True, -100], 74, "左眼中心 x（-100 偏移）"),
        ]
        for fn, args, want, label in expect:
            got = env.call(fn, args)
            if got != want:
                fails.append(("geometry", "%s 应为 %s，实际 %s" % (label, want, got)))
    except JsError as exc:
        fails.append(("geometry", "求值失败: %s" % exc))

    # ---- 6. 规范文本本身必须写清极性（防止规范与实现漂移）----
    if "越大越睁开" not in spec:
        fails.append(("polarity", "规范 §2.1 缺少「越大越睁开」"))
    if "越大越张开" not in spec:
        fails.append(("polarity", "规范 §2.1 缺少「越大越张开」"))
    if not re.search(r"方向是.{0,6}相同", spec):
        fails.append(("polarity", "规范 §2.1 缺少「眼睛与嘴的 weight 方向相同」的结论"))
    if "6.25" not in spec:
        fails.append(("coefficient", "规范里找不到换算系数 6.25"))
    if not re.search(r"1 px = 6\.25", spec):
        fails.append(("coefficient", "规范里找不到「1 px = 6.25 JSON 单位」"))

    # ---- 7. 规范里的 JSON Schema 合法且自洽 ----
    fails.extend(check_schemas(spec))

    return fails


# --------------------------------------------------------------------------
# 变异用例
# --------------------------------------------------------------------------

MUTATIONS = [
    {
        "name": "极性写反（眼睑偏移去掉负号）",
        "category": "polarity",
        "old": "return -mapRange(weight, 0, 100, 0, eyeD);",
        "new": "return mapRange(weight, 0, 100, 0, eyeD);",
    },
    {
        "name": "换算系数写成 1.0",
        "category": "coefficient",
        "old": "const UNITS_PER_PX = 6.25;",
        "new": "const UNITS_PER_PX = 1.0;",
    },
    {
        "name": "改掉一个默认值（leftEye.weight 100 → 72）",
        "category": "defaults",
        "old": "leftEye:  { x: 0, y: 0, rotation: 0, weight: 100, size: 0 },",
        "new": "leftEye:  { x: 0, y: 0, rotation: 0, weight: 72, size: 0 },",
    },
]


def run_mutations(html: str, spec: str):
    results = []
    for mut in MUTATIONS:
        if mut["old"] not in html:
            results.append((mut["name"], False, "变异锚点没找到，测试本身失效: %r" % mut["old"]))
            continue
        mutated = html.replace(mut["old"], mut["new"], 1)
        fails = check(mutated, spec)
        cats = {c for c, _ in fails}
        caught = mut["category"] in cats
        detail = "; ".join(m for c, m in fails if c == mut["category"])[:160]
        results.append((mut["name"], caught, detail or "（未抓到）"))
    return results


# --------------------------------------------------------------------------

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass

    for path in (HTML_PATH, SPEC_PATH):
        if not path.exists():
            print("FAIL 找不到文件: %s" % path)
            return 1

    html = HTML_PATH.read_text(encoding="utf-8")
    spec = SPEC_PATH.read_text(encoding="utf-8")

    fails = check(html, spec)
    print("校验目标: %s" % HTML_PATH.relative_to(REPO))
    print("规范目标: %s" % SPEC_PATH.relative_to(REPO))
    print("")
    groups = [
        ("functions", "1. 引用的 JS 函数都存在"),
        ("defaults", "2. 15 个默认值与 docs/spec/06 §3 一致"),
        ("polarity", "3. 眼睛 / 嘴的 weight 极性一致"),
        ("coefficient", "4. x/y 换算系数 6.25 一致"),
        ("geometry", "5. 元素基准位置与规范 §2.3 一致"),
        ("schema", "6. 规范里的 JSON Schema 合法且自洽"),
    ]
    ok = True
    for cat, label in groups:
        cat_fails = [m for c, m in fails if c == cat]
        if cat_fails:
            ok = False
            print("FAIL  %s" % label)
            for m in cat_fails:
                print("        - %s" % m)
        else:
            print("PASS  %s" % label)

    print("")
    print("变异用例（必须全部被抓到）：")
    mut_results = run_mutations(html, spec)
    for name, caught, detail in mut_results:
        if caught:
            print("PASS  抓到：%s" % name)
            if detail:
                print("        - %s" % detail)
        else:
            ok = False
            print("FAIL  没抓到：%s" % name)
            print("        - %s" % detail)

    print("")
    if ok:
        print("ALL PASS")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
