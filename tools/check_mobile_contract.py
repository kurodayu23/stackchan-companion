# -*- coding: utf-8 -*-
"""check_mobile_contract.py —— 手机端接口契约的三方对齐门禁。

问题
----
手机端（``prototype/mobile/``）读的是 ``/mobile-api/*``；代理（``mobile_proxy.py``）
用 ``_pick()`` **只保留上游已经存在的键**；本仓后端（``server/http_api.py``）
决定到底给了哪些键。

三者只要有一处对不齐，页面就**静默出错**，不报任何错：

* 后端给 ``reply``、手机端读 ``say`` ⇒ 聊天页永远显示「小栈这次没有返回内容」
* 后端少给 ``network.ssid`` ⇒ 状态页永远显示「未上报」
* 代理漏放行一条路由 ⇒ 直接 404
* 屏幕程序 id 对不上 ⇒ 手机端 8 个按钮**全被隐藏**

判据清单
--------
====  ==========================================================
ID    判据
====  ==========================================================
MC-01 契约里的每条路由，本仓路由表里必须存在（方法 + 路径 + owner 一致）
MC-02 契约里的每条手机端路由，代理白名单必须放行，且映射到契约写的后端路径
MC-03 ⭐ 后端真实响应**过完代理净化层**后，契约字段必须全部还在
MC-04 后端真实响应必须含 ``backend_fields``（净化前就必须产出）
MC-05 ``non_empty`` 字段必须非空（空值等于没给）
MC-06 记忆分类 / 屏幕程序 id 必须与代理里的白名单一致
MC-07 ⭐ 手机端 JS 真正读到的字段，必须都在契约里（契约漏了 ⇒ 前端读到 undefined）
MC-08 契约里的字段必须真的在手机端 JS 里出现过（契约腐烂 ⇒ 没人发现）
====  ==========================================================

用法
----
    py -3.12 tools/check_mobile_contract.py --root .
    py -3.12 tools/check_mobile_contract.py --self-test
"""

from __future__ import annotations

import argparse
import importlib
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MOBILE_REL = "prototype/mobile"

#: JS 里常见的内建方法/属性（不是接口字段，别当契约要求）
JS_BUILTINS = {
    "length", "trim", "map", "filter", "find", "forEach", "some", "every",
    "push", "pop", "shift", "unshift", "slice", "splice", "concat", "join",
    "includes", "indexOf", "startsWith", "endsWith", "split", "replace",
    "toUpperCase", "toLowerCase", "toFixed", "padStart", "padEnd", "repeat",
    "charAt", "substring", "substr", "match", "test", "sort", "reverse",
    "keys", "values", "entries", "flat", "reduce", "count", "size", "type",
    "value", "status", "reason", "message", "name", "id", "href", "src",
    "alt", "title", "className", "dataset", "textContent", "innerText",
    "innerHTML", "disabled", "hidden", "value", "checked", "selected",
    "style", "parentNode", "children", "childNodes", "remove", "append",
    "getAttribute", "setAttribute", "hasAttribute", "focus", "click",
    "scrollHeight", "scrollWidth", "clientWidth", "clientHeight",
    "getBoundingClientRect", "toLocaleString", "at", "flatMap",
}

#: ``const X = await api.get("/xxx")`` / ``api.post``
RE_ASSIGN_API = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+api\.(get|post)\(\s*[\"'`](/[^\"'`]*)")
#: ``const [A, B] = await Promise.all([...])`` / ``Promise.allSettled([...])``
RE_ARRAY_API = re.compile(
    r"(?:const|let|var)\s*\[([^\]]+)\]\s*=\s*await\s*Promise\.all(Settled)?\s*\(\s*\[(.*?)\]\s*\)",
    re.S)
#: ``render(await api.get("/xxx"))`` —— 响应直接当参数传给函数
RE_INLINE_API = re.compile(
    r"\b(\w+)\(\s*await\s*api\.(get|post)\(\s*[\"'`](/[^\"'`]*)")
#: 函数定义（用来把「内联调用」映射到形参名）
RE_FUNC_DEF = re.compile(
    r"(?:function\s+(\w+)\s*\(([^)]*)\)|(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>)")
#: 变量上的属性读取
RE_PROP = re.compile(r"\b(\w+)\s*(?:\?\.)?\.(\w+)(?:\s*(?:\?\.)?\.(\w+))?")
#: 别名赋值：``current = status``（RHS 必须是**裸标识符**）
RE_ALIAS = re.compile(r"\b(\w+)\s*=\s*([A-Za-z_$][\w$]*)(?![.\w(])")
#: 属性别名：``const network = status.network``
RE_ALIAS_PROP = re.compile(r"\b(\w+)\s*=\s*([A-Za-z_$][\w$]*)\s*(?:\?\.|\.)(\w+)")

#: 契约字段路径 → 手机端 JS 里出现过的「叶子词」
RE_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class Finding:
    """一条判据结果。"""

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg

    def __repr__(self) -> str:  # pragma: no cover
        return "<Finding %s %s %s: %s>" % (self.code, self.severity, self.where, self.msg)


# ---------------------------------------------------------------------------
# 模块加载（自检时要用「临时副本」里的实现，所以必须能按 root 重新加载）
# ---------------------------------------------------------------------------
def load_modules(repo_root: Path) -> Tuple[Any, Any, Any, Any, Any]:
    """按 ``repo_root`` 重新加载契约 / 后端 / 代理 / provider。

    返回 ``(mobile_contract, http_api, mobile_proxy, backend, routes)``。
    """
    for name in list(sys.modules):
        # NOTE: 顶层 ``server`` 包也要一起清掉；只清 ``server.*`` 时，
        #       已缓存的 ``server.__path__`` 还指向**原仓库** ⇒ 临时副本根本不生效
        if name in ("mobile_proxy", "server") or name.startswith("server."):
            sys.modules.pop(name, None)
    for path in (str(repo_root), str(repo_root / MOBILE_REL)):
        while path in sys.path:
            sys.path.remove(path)
    sys.path.insert(0, str(repo_root / MOBILE_REL))
    sys.path.insert(0, str(repo_root))

    mobile_contract = importlib.import_module("server.mobile_contract")
    http_api = importlib.import_module("server.http_api")
    mobile_proxy = importlib.import_module("mobile_proxy")
    stub = importlib.import_module("server.providers.stub")
    config_mod = importlib.import_module("server.stackchan_ai.config")
    server_mod = importlib.import_module("server.stackchan_ai.server")

    config = config_mod.Config.from_env()
    config.provider = "stub"
    backend = http_api.MobileBackend(
        config, server=server_mod.StackChanServer(config, provider=stub.StubProvider(),
                                                  verbose=False))
    return mobile_contract, http_api, mobile_proxy, backend, http_api.ROUTES


#: 每条路由的最小合法请求体（与 ``server/tests/test_http_api.py`` 保持一致）
SAMPLE_BODIES: Dict[str, Dict[str, Any]] = {
    "POST /gui/mobile-chat": {"message": "你好"},
    "GET /gui/device/status": {},
    "GET /gui/screen-programs": {},
    "POST /gui/screen-programs/control": {"program_id": "chat", "action": "open"},
    "GET /gui/memory": {},
    "POST /gui/memory/remove": {"key": "likes", "value": "咖啡"},
    "POST /gui/memory/clear": {"key": "likes"},
    "POST /gui/device/head": {"yaw": 10, "pitch": 20},
    "POST /gui/device/brightness": {"brightness": 50},
    "POST /gui/device/volume": {"volume": 50, "permanent": False},
    "POST /gui/device/led": {"red": 1, "green": 2, "blue": 3},
    "POST /gui/device/camera-preview/start": {},
    "POST /gui/device/camera-preview/stop": {},
    "GET /gui/device/camera/latest": {},
}


# ---------------------------------------------------------------------------
# JS 侧：手机端到底读了哪些字段
# ---------------------------------------------------------------------------
#: 关键字（后面跟 ``(...)`` 的是控制流，不是函数）
JS_CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch", "return",
                       "function", "do", "else", "try", "new", "typeof", "await"}


def _strip_noise(text: str) -> str:
    """把字符串 / 注释 / 正则替换成等长空白。

    目的是**只保留大括号结构**，让后面的作用域分析不被字符串里的括号带偏。
    """
    out = list(text)
    i = 0
    n = len(text)
    state: Optional[str] = None
    while i < n:
        ch = text[i]
        if state is None:
            if ch in "'\"`":
                state = ch
                out[i] = " "
            elif ch == "/" and i + 1 < n and text[i + 1] == "/":
                state = "//"
                out[i] = " "
                i += 1
                if i < n:
                    out[i] = " "
            elif ch == "/" and i + 1 < n and text[i + 1] == "*":
                state = "/*"
                out[i] = " "
                i += 1
                if i < n:
                    out[i] = " "
            elif ch == "/" and _regex_can_start(text, i):
                state = "regex"
                out[i] = " "
            else:
                i += 1
                continue
        elif state == "//":
            if ch == "\n":
                state = None
            else:
                out[i] = " "
        elif state == "/*":
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                out[i] = " "
                i += 1
                if i < n:
                    out[i] = " "
                state = None
            elif ch != "\n":
                out[i] = " "
        elif state == "regex":
            if ch == "\\":
                out[i] = " "
                i += 1
                if i < n:
                    out[i] = " "
            elif ch == "/":
                out[i] = " "
                state = None
            elif ch == "\n":
                state = None
            else:
                out[i] = " "
        else:
            if ch == "\\":
                out[i] = " "
                i += 1
                if i < n:
                    out[i] = " "
            elif ch == state:
                out[i] = " "
                state = None
            elif ch != "\n":
                out[i] = " "
        i += 1
    return "".join(out)


def _regex_can_start(text: str, index: int) -> bool:
    """粗判 ``/`` 是正则还是除号。"""
    for j in range(index - 1, -1, -1):
        ch = text[j]
        if ch.isspace():
            continue
        return ch in "(,=:[!&|?{};+-*%~^"
    return True


def _matching_brace(masked: str, open_pos: int) -> int:
    """返回与 ``masked[open_pos] == '{'`` 匹配的 ``}`` 位置。"""
    depth = 0
    for i in range(open_pos, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(masked) - 1


def _is_function_header(header: str) -> bool:
    """判断一段 ``{`` 之前的内容是不是「函数头」。"""
    header = header.rstrip()
    if not header:
        return False
    if re.search(r"function\s*\*?\s*\w*\s*\([^()]*\)\s*$", header):
        return True
    if re.search(r"\)\s*=>\s*$", header):
        return True
    match = re.search(r"([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*$", header)
    if match and match.group(1) not in JS_CONTROL_KEYWORDS:
        return True
    return False


def _function_scopes(text: str) -> Tuple[List[Tuple[int, int]], Dict[str, Tuple[int, int]]]:
    """找出所有**函数体**的范围。

    ⚠️ 不能只认 ``function foo() {}`` / ``foo = () => {}``：
    回调里的匿名箭头函数（``addEventListener("click", async () => { ... })``）
    同样是独立作用域 ⇒ 漏掉它会把不同接口的响应混进同一个变量
    （2026-10-30 实测踩过：``result`` 同时被 4 个接口用）。

    返回 ``(scopes, name_to_scope)``：
    * ``scopes`` —— ``[(起点, 终点), ...]``（按起点升序）
    * ``name_to_scope`` —— ``{函数名: (起点, 终点)}``
    """
    masked = _strip_noise(text)
    scopes: List[Tuple[int, int]] = []
    for index, ch in enumerate(masked):
        if ch != "{":
            continue
        header = masked[max(0, index - 400):index]
        if _is_function_header(header):
            scopes.append((index, _matching_brace(masked, index)))
    scopes.sort()
    name_to_scope: Dict[str, Tuple[int, int]] = {}
    for match in RE_FUNC_DEF.finditer(masked):
        name = match.group(1) or match.group(3)
        if not name or name in name_to_scope:
            continue
        open_pos = masked.find("{", match.end())
        if open_pos < 0:
            continue
        name_to_scope[name] = (open_pos, _matching_brace(masked, open_pos))
    return scopes, name_to_scope


def _function_params(text: str) -> Dict[str, List[str]]:
    """``{函数名: [形参名...]}``。"""
    out: Dict[str, List[str]] = {}
    for match in RE_FUNC_DEF.finditer(text):
        if match.group(1):
            name, raw = match.group(1), match.group(2)
        else:
            name, raw = match.group(3), match.group(4)
        params = []
        for part in raw.split(","):
            token = part.split("=")[0].strip()
            token = token.lstrip("...").strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", token or ""):
                params.append(token)
        if name:
            out.setdefault(name, params)
    return out


def js_response_reads(mobile_dir: Path) -> Dict[str, Set[str]]:
    """扫手机端 JS ⇒ ``{"METHOD /mobile-api/x": 被读到的字段路径}``。

    ★ **按函数作用域归属**：同一个变量名（``response`` / ``payload`` / ``device``）
    在不同函数里可能来自不同接口 ⇒ 必须按「哪个函数读它」来归属，
    否则会把 ``/gui/firmware/status`` 的 ``device.current_version``
    误算到 ``/gui/device/status`` 上（2026-10-30 实测踩过）。

    ★ **别名要带路径**：``const network = status.network`` ⇒ 读 ``network.ssid``
    时的路径是 ``network.ssid``（不是 ``ssid``），否则契约比对会误判。
    """
    reads: Dict[str, Set[str]] = {}
    for path in sorted(mobile_dir.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="replace")
        scopes, name_to_scope = _function_scopes(text)

        def innermost(pos: int) -> Optional[Tuple[int, int]]:
            best: Optional[Tuple[int, int]] = None
            for scope in scopes:
                if scope[0] <= pos <= scope[1]:
                    if best is None or scope[0] > best[0]:
                        best = scope
            return best

        # ── 1) 作用域 ⇒ 响应变量 ⇒ (路由键, 相对路径) ─────────────────
        # scope ⇒ {变量名: (路由键, 路径前缀)}
        scope_vars: Dict[Tuple[int, int], Dict[str, Tuple[str, str]]] = {}
        # 作用域 ⇒ 属于 ``Promise.allSettled`` 的变量（真正的响应在 ``.value`` 里）
        scope_settled: Dict[Tuple[int, int], Set[str]] = {}

        def register(scope: Optional[Tuple[int, int]], var: str,
                     route_key: str, prefix: str = "") -> None:
            if scope is None:
                return
            scope_vars.setdefault(scope, {})[var] = (route_key, prefix)

        for match in RE_ASSIGN_API.finditer(text):
            register(innermost(match.start()), match.group(1),
                     "%s /mobile-api%s" % (match.group(2).upper(), match.group(3)))

        for match in RE_ARRAY_API.finditer(text):
            names = [n.strip() for n in match.group(1).split(",") if n.strip()]
            settled = bool(match.group(2))
            calls = re.findall(
                r"api\.(get|post)\(\s*[\"'`](/[^\"'`]*)", match.group(3))
            scope = innermost(match.start())
            for index, name in enumerate(names):
                if index < len(calls):
                    method, api_path = calls[index]
                    route_key = "%s /mobile-api%s" % (method.upper(), api_path)
                    register(scope, name, route_key)
                    if settled:
                        # ``Promise.allSettled`` ⇒ 真正的响应在 ``.value`` 里
                        register(scope, name + ".value", route_key)
                        scope_settled.setdefault(scope, set()).add(name)

        for match in RE_INLINE_API.finditer(text):
            func, method, api_path = match.group(1), match.group(2), match.group(3)
            callee = name_to_scope.get(func)
            if callee is None:
                continue
            params = _function_params(text).get(func) or []
            if not params:
                continue
            register(callee, params[0], "%s /mobile-api%s" % (method.upper(), api_path))

        # ── 1b) 别名传播：``current = status`` / ``network = status.network`` ──
        for scope, variables in scope_vars.items():
            for match in RE_ALIAS_PROP.finditer(text):
                if not (scope[0] <= match.start() <= scope[1]):
                    continue
                if innermost(match.start()) != scope:
                    continue
                lhs, rhs, prop = match.group(1), match.group(2), match.group(3)
                if rhs not in variables or lhs in variables:
                    continue
                # ``y`` 是 ``Promise.allSettled`` 的结果 ⇒ 真正的响应在 ``y.value`` 里
                # （源码常写成 ``y.status === "fulfilled" ? y.value : null`` ⇒ 取 ``.value``）
                if "%s.value" % rhs in variables:
                    variables[lhs] = variables["%s.value" % rhs]
                    continue
                # ``x = y.someField``
                if "%s.%s" % (rhs, prop) in variables:
                    variables[lhs] = variables["%s.%s" % (rhs, prop)]
                    continue
                route_key, prefix = variables[rhs]
                variables[lhs] = (route_key, "%s.%s" % (prefix, prop) if prefix else prop)
            for match in RE_ALIAS.finditer(text):
                if not (scope[0] <= match.start() <= scope[1]):
                    continue
                if innermost(match.start()) != scope:
                    continue
                lhs, rhs = match.group(1), match.group(2)
                if rhs not in variables or lhs in variables:
                    continue
                variables[lhs] = variables[rhs]

        # ── 2) 作用域内读到的属性 ───────────────────────────────────
        for scope, variables in scope_vars.items():
            for match in RE_PROP.finditer(text):
                if not (scope[0] <= match.start() <= scope[1]):
                    continue
                inner = innermost(match.start())
                if inner != scope:
                    continue          # 属于更内层的函数 ⇒ 不算在这个作用域
                var, first, second = match.group(1), match.group(2), match.group(3)
                entry = variables.get(var)
                if entry is None:
                    continue
                route_key, prefix = entry
                settled_here = scope_settled.get(scope, set())
                if first == "value" and var in settled_here:
                    first = second          # ``.value`` 是响应本身
                    second = None
                if second:
                    name = ("%s.%s.%s" % (prefix, first, second) if prefix
                            else "%s.%s" % (first, second))
                elif first:
                    name = "%s.%s" % (prefix, first) if prefix else first
                else:
                    continue
                reads.setdefault(route_key, set()).add(name)
    return reads


def js_words(mobile_dir: Path) -> Dict[str, Set[str]]:
    """``{js 文件名: 出现过的词}``（用于 MC-08 契约防腐烂）。"""
    out: Dict[str, Set[str]] = {}
    for path in sorted(mobile_dir.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="replace")
        out[path.name] = set(RE_WORD.findall(text))
    return out


def contract_leaf(path: str) -> str:
    """契约路径的叶子字段名。"""
    cleaned = path.replace("[]", "")
    return cleaned.split(".")[-1]


def contract_prefixes(path: str) -> List[str]:
    """契约路径的各级前缀（``a.b.c`` ⇒ ``a`` / ``a.b`` / ``a.b.c``）。"""
    parts = path.replace("[]", "").split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def _normalize_field(path: str) -> str:
    """字段名归一化：去掉 ``[]``、转小写、去掉下划线。

    手机端故意同时读驼峰和下划线两种写法
    （``network.otaSupported || network.ota_supported``）⇒ 比对时按同一字段处理。
    """
    return path.replace("[]", "").replace("_", "").lower()


def covers(contract_path: str, read_path: str) -> bool:
    """契约路径是否覆盖前端读到的路径。

    * 完全相同 ⇒ 覆盖
    * 前端读的是契约路径的前缀（``network`` ⊆ ``network.ssid``）⇒ 覆盖
    * 契约路径是前端读的前缀（``network.ssid`` ⊆ 前端读的 ``network.ssid.rssi``）⇒ 覆盖
    """
    left = _normalize_field(contract_path)
    right = _normalize_field(read_path)
    return left == right or right.startswith(left + ".") or left.startswith(right + ".")


# ---------------------------------------------------------------------------
# 判据
# ---------------------------------------------------------------------------
def check_contract(mobile_contract: Any, http_api: Any, mobile_proxy: Any,
                   backend: Any, routes: Sequence[Any],
                   mobile_dir: Path, findings: List[Finding]) -> None:
    contracts = mobile_contract.CONTRACTS
    route_index = {(r.method, r.path): r for r in routes}

    # ── MC-01 契约 ⇄ 本仓路由表 ────────────────────────────────────────
    for contract in contracts:
        key = (contract.backend_method, contract.backend_path)
        route = route_index.get(key)
        if route is None:
            findings.append(Finding("MC-01", "FAIL", contract.backend_key,
                                     "契约指向的路由在本仓路由表里不存在"))
            continue
        if route.owner != contract.owner:
            findings.append(Finding("MC-01", "FAIL", contract.backend_key,
                                     "owner 不一致：契约写 %s，路由表写 %s"
                                     % (contract.owner, route.owner)))
        if contract.owner == "mobile" and not route.implemented:
            findings.append(Finding("MC-01", "FAIL", contract.backend_key,
                                     "契约说本仓实现，但路由没有 handler"))

    # ── MC-02 契约 ⇄ 代理白名单 ────────────────────────────────────────
    for contract in contracts:
        key = (contract.mobile_method, contract.mobile_path)
        upstream = mobile_proxy.ALLOWED_ROUTES.get(key)
        if upstream is None:
            findings.append(Finding("MC-02", "FAIL", contract.mobile_key,
                                     "代理白名单没放行这条路径 ⇒ 手机端直接 404"))
            continue
        if upstream != contract.backend_path:
            findings.append(Finding("MC-02", "FAIL", contract.mobile_key,
                                     "代理映射到 %s，契约写的是 %s" % (upstream, contract.backend_path)))

    # ── MC-03 / MC-04 / MC-05 真实响应 ─────────────────────────────────
    for contract in contracts:
        if contract.owner != "mobile":
            continue
        route = route_index.get((contract.backend_method, contract.backend_path))
        if route is None or not route.implemented:
            continue
        body = SAMPLE_BODIES.get(contract.backend_key)
        if body is None:
            findings.append(Finding("MC-03", "FAIL", contract.backend_key,
                                     "门禁没有这条路由的样例请求体 ⇒ 测不到"))
            continue
        status, raw = route.handler(backend, body)

        # MC-04：后端必须产出
        for path in contract.backend_fields:
            if not mobile_contract.path_exists(raw, path):
                findings.append(Finding("MC-04", "FAIL", contract.backend_key,
                                         "后端响应缺字段 %s" % path))

        # MC-03：过完代理净化层，契约字段必须还在
        sanitized = raw
        if status == 200 and isinstance(raw, dict):
            sanitized = mobile_proxy._sanitize_response(contract.mobile_path, raw)
        for path in contract.fields:
            if not mobile_contract.path_exists(sanitized, path):
                findings.append(Finding("MC-03", "FAIL", contract.mobile_key,
                                         "手机端看不到字段 %s（后端少给了，或代理没放行）" % path))

        # MC-05：必填字段非空
        for path in contract.non_empty:
            if not mobile_contract.path_non_empty(sanitized, path):
                findings.append(Finding("MC-05", "FAIL", contract.mobile_key,
                                         "必填字段 %s 是空的（空值等于没给）" % path))

    # ── MC-06 白名单常量一致 ──────────────────────────────────────────
    proxy_text = (mobile_dir / "mobile_proxy.py").read_text(encoding="utf-8", errors="replace")
    mem_block = re.search(r"MEMORY_KEYS\s*=\s*\{(.*?)\n\}", proxy_text, re.S)
    if mem_block is None:
        findings.append(Finding("MC-06", "FAIL", "mobile_proxy.py",
                                 "找不到 MEMORY_KEYS ⇒ 记忆分类无法核对"))
    else:
        proxy_keys = set(re.findall(r'"([^"]+)"', mem_block.group(1)))
        if proxy_keys != set(mobile_contract.MEMORY_CATEGORIES):
            findings.append(Finding("MC-06", "FAIL", "mobile_proxy.py",
                                     "记忆分类与契约不一致：代理 %s / 契约 %s"
                                     % (sorted(proxy_keys), sorted(mobile_contract.MEMORY_CATEGORIES))))
    prog_block = re.search(r"SCREEN_PROGRAM_IDS\s*=\s*\{(.*?)\n\}", proxy_text, re.S)
    if prog_block is None:
        findings.append(Finding("MC-06", "FAIL", "mobile_proxy.py",
                                 "找不到 SCREEN_PROGRAM_IDS ⇒ 屏幕程序无法核对"))
    else:
        proxy_ids = set(re.findall(r'"([^"]+)"', prog_block.group(1)))
        if proxy_ids != set(mobile_contract.SCREEN_PROGRAM_IDS):
            findings.append(Finding("MC-06", "FAIL", "mobile_proxy.py",
                                     "屏幕程序 id 与契约不一致：代理 %s / 契约 %s"
                                     % (sorted(proxy_ids), sorted(mobile_contract.SCREEN_PROGRAM_IDS))))

    # ── MC-07 前端读到的字段必须在契约里 ──────────────────────────────
    reads = js_response_reads(mobile_dir)
    by_mobile = {c.mobile_key: c for c in contracts}
    for route_key, fields in sorted(reads.items()):
        contract = by_mobile.get(route_key)
        if contract is None:
            # 契约里没写这条路由 ⇒ 前端读到了契约没覆盖的东西
            findings.append(Finding("MC-07", "FAIL", route_key,
                                     "手机端读了这条路由，但契约里没有它"))
            continue
        covered = list(contract.fields)
        uncovered = []
        for field in sorted(fields):
            if field.split(".")[-1] in JS_BUILTINS:
                continue
            if not any(covers(path, field) for path in covered):
                uncovered.append(field)
        if uncovered:
            findings.append(Finding("MC-07", "FAIL", route_key,
                                     "手机端读了契约里没有的字段：%s" % uncovered))

    # ── MC-08 契约不能腐烂 ────────────────────────────────────────────
    words = js_words(mobile_dir)
    for contract in contracts:
        for path in contract.fields:
            leaf = contract_leaf(path)
            if leaf in JS_BUILTINS:
                continue
            hit = False
            for name in contract.js_files:
                if leaf in words.get(name, set()):
                    hit = True
                    break
            if not hit:
                findings.append(Finding("MC-08", "FAIL", contract.mobile_key,
                                         "契约字段 %s 在手机端 JS 里从没出现过（契约已腐烂）" % path))


def scan(repo_root: Path) -> List[Finding]:
    """跑一遍全部判据，返回 findings（空列表 = 全绿）。"""
    findings: List[Finding] = []
    mobile_dir = repo_root / MOBILE_REL
    if not mobile_dir.is_dir():
        findings.append(Finding("MC-00", "FAIL", MOBILE_REL, "找不到手机端目录"))
        return findings
    try:
        mobile_contract, http_api, mobile_proxy, backend, routes = load_modules(repo_root)
    except Exception as exc:  # noqa: BLE001 - 导入失败也要报出来，不能静默通过
        findings.append(Finding("MC-00", "FAIL", "server", "模块导入失败：%s" % exc))
        return findings
    check_contract(mobile_contract, http_api, mobile_proxy, backend, routes,
                   mobile_dir, findings)
    return findings


# ---------------------------------------------------------------------------
# 自检：把真实现件复制一份，逐条改坏 ⇒ 对应判据必须变红
# ---------------------------------------------------------------------------
def _fixture(repo_root: Path, td: str) -> Path:
    """复制出「server/ + prototype/mobile/」的临时副本。"""
    dst = Path(td) / "repo"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_root / "server", dst / "server",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(repo_root / MOBILE_REL, dst / MOBILE_REL,
                    ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    return dst


def _mutate(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
    return True


def _mutate_re(path: Path, pattern: str, repl: str, count: int = 1) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text, n = re.subn(pattern, repl, text, count=count)
    if n == 0:
        return False
    path.write_text(new_text, encoding="utf-8", newline="")
    return True


def run_self_test(repo_root: Path) -> int:
    print("[self-test] check_mobile_contract.py 门禁自检")
    print("=" * 68)
    passed = failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    def codes_of(root: Path) -> Set[str]:
        return {f.code for f in scan(root) if f.severity == "FAIL"}

    if not (repo_root / MOBILE_REL).is_dir():
        print("  SKIP  找不到 %s" % MOBILE_REL)
        return 1

    baseline = scan(repo_root)
    check("真实现件零 FAIL",
          not baseline, str([(f.code, f.msg) for f in baseline]))

    # 1) MC-03：后端把 `say` 改名 ⇒ 手机端读不到
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / "server" / "http_api.py", '"say": reply,', '"sayxx": reply,')
        check("MC-03 字段名对不上被抓到", "MC-03" in codes_of(root))

    # 2) MC-03：代理的 chat 白名单去掉 `say`
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / MOBILE_REL / "mobile_proxy.py",
                '{"say", "emotion", "face", "motion", "route", "model", "latency_ms"}',
                '{"emotion", "face", "motion", "route", "model", "latency_ms"}')
        check("MC-03 代理丢字段被抓到", "MC-03" in codes_of(root))

    # 3) MC-02：代理白名单删掉一条路由
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate_re(root / MOBILE_REL / "mobile_proxy.py",
                   r'\n\s*\("GET", "/mobile-api/memory"\): "/gui/memory",', "")
        check("MC-02 代理漏放行被抓到", "MC-02" in codes_of(root))

    # 4) MC-01：契约指向一个不存在的后端路由
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / "server" / "mobile_contract.py",
                '"/gui/mobile-chat", "mobile"', '"/gui/nope-chat", "mobile"')
        check("MC-01 契约指向不存在的路由被抓到", "MC-01" in codes_of(root))

    # 5) MC-04：后端不再产出 `model`
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / "server" / "http_api.py",
                '"model": str(getattr(provider, "name", "") or "unknown"),', "")
        check("MC-04 后端少产字段被抓到", "MC-04" in codes_of(root))

    # 6) MC-05：`say` 变成空串
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / "server" / "http_api.py", '"say": reply,', '"say": "",')
        check("MC-05 必填字段为空被抓到", "MC-05" in codes_of(root))

    # 7) MC-06：代理的记忆分类少一个
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / MOBILE_REL / "mobile_proxy.py",
                '    "insights",\n}', '}')
        check("MC-06 记忆分类不一致被抓到", "MC-06" in codes_of(root))

    # 8) MC-07：手机端开始读一个契约里没有的字段
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / MOBILE_REL / "chat.js",
                "payload.model ?", "payload.undeclared_field ?")
        check("MC-07 前端读到契约外字段被抓到", "MC-07" in codes_of(root))

    # 9) MC-08：契约字段改名 ⇒ 手机端 JS 里再也找不到
    with tempfile.TemporaryDirectory() as td:
        root = _fixture(repo_root, td)
        _mutate(root / "server" / "mobile_contract.py",
                'fields=("say", "model"),', 'fields=("say", "model_renamed"),')
        check("MC-08 契约腐烂被抓到", "MC-08" in codes_of(root))

    print("=" * 68)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/check_mobile_contract.py",
                                     description="手机端接口契约三方对齐门禁")
    parser.add_argument("--root", default=".", help="仓库根目录")
    parser.add_argument("--self-test", action="store_true", help="跑变异自检")
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()
    if args.self_test:
        return run_self_test(repo_root)

    print("=" * 68)
    print("check_mobile_contract.py —— 手机端接口契约 ↔ 代理 ↔ 后端 一致性体检")
    print("=" * 68)
    print("仓库根目录  : %s" % repo_root)
    print("手机端目录  : %s" % MOBILE_REL)
    print("-" * 68)
    findings = scan(repo_root)
    for finding in findings:
        print("%-5s %-8s %s" % (finding.severity, finding.code, finding.where))
        print("      %s" % finding.msg)
    fails = sum(1 for f in findings if f.severity == "FAIL")
    warns = sum(1 for f in findings if f.severity == "WARN")
    print("-" * 68)
    print("FAIL=%d  WARN=%d" % (fails, warns))
    if fails:
        print("存在不一致 —— 手机端会静默显示错内容。")
        return 1
    print("ALL PASS —— 契约、代理、后端三者一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
