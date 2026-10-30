#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_css_vars.py —— 原型 CSS 变量体检（引用了但没定义 / 方案之间不一致 / 与 Swift token 漂移）

为什么需要它
------------
本仓库的原型与 iOS DesignSystem 共享同一套「方案级 token」。
2026-10-25 深夜出图时肉眼抓到：**深色方案下 Tab Bar 的选中项文字几乎看不见**。
回源发现根因是 CSS 自定义属性的一个**静默失败模式**：

    .tab-item[aria-selected="true"]{color:var(--tint)}   /* --tint 从未被定义 */

`--tint` 没定义 ⇒ 这条声明在**计算值阶段非法** ⇒ `color` 退回**继承值**（黑）。
**浏览器不报错、不警告、DOM 里也看不出来** —— 只是「有个元素颜色不对」。

而这类错误对**深色方案是致命的**（深底黑字 = 不可读），对浅色方案只是「不显眼」。

所以本门禁做三件事：

CSV-01  **被引用但未定义**的 CSS 变量 → FAIL
CSV-02  4 套方案的 token **集合不一致**（某套少定义一个）→ FAIL
CSV-03  iOS 原型的方案强调色与 `prototype/variants/` 的 `--accent` **漂移** → FAIL
         （原型与 Swift `Tokens.swift` 同源 ⇒ 两边必须一致）

用法
----
    py -3.12 tools/check_css_vars.py --root .
    py -3.12 tools/check_css_vars.py --self-test

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 被扫描的 HTML（相对仓库根）
HTML_GLOBS = [
    os.path.join("prototype", "ios", "ios-light.html"),
    os.path.join("prototype", "ios", "ios-dark.html"),
    os.path.join("ios", "prototype", "index.html"),
    os.path.join("prototype", "index.html"),
]

#: 4 套方案 ↔ variants 原型 ↔ Swift token 名
SCHEME_MAP = [
    ("paper-terracotta", "paperTerracotta", "01-paper-terracotta.html"),
    ("pure-white-blank", "pureWhiteBlank", "03-pure-white-blank.html"),
    ("warm-paper-serif", "warmPaperSerif", "17-warm-paper-serif.html"),
    ("tuck-dark-calm", "tuckDarkCalm", "18-tuck-dark-calm.html"),
]

#: var(--x) 引用
RE_VAR_USE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*(?:[,)]|$)")
#: --x : value 定义（只认「自定义属性定义」，值可以是任意非分号内容）
RE_VAR_DEF = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]*);")
#: 方案块 html[data-scheme="xxx"]{...}
RE_SCHEME_BLOCK = re.compile(
    r'html\[data-scheme\s*=\s*"([^"]+)"\]\s*\{(.*?)\n\}', re.S)
#: @property 注册（注册过的变量即使没显式赋值也算已定义）
RE_AT_PROPERTY = re.compile(r"@property\s+(--[A-Za-z0-9_-]+)")

#: 这两个变量是「派生别名」，允许指向另一个变量
DERIVED_OK = {
    "--bubble-out", "--bubble-out-text",
}


class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg


def _read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def scan_file(path: str, rel: str, findings: list) -> dict:
    """检查单个 HTML：CSV-01（未定义引用）+ CSV-02（方案 token 集合一致）。"""
    text = _read(path)
    defined = set(m.group(1) for m in RE_VAR_DEF.finditer(text))
    defined |= set(m.group(1) for m in RE_AT_PROPERTY.finditer(text))
    used = set(m.group(1) for m in RE_VAR_USE.finditer(text))

    undefined = sorted(used - defined)
    for name in undefined:
        # 统计被引用了几处，便于判断严重度
        n = len(RE_VAR_USE.findall(text))
        findings.append(Finding(
            "CSV-01", "FAIL", rel,
            "CSS 变量 `%s` 被引用但**从未定义** —— 相关声明在计算值阶段非法，"
            "颜色/尺寸会静默退回继承值（深色方案下表现为不可读）" % name))

    # CSV-02：各方案块定义的 token 集合必须一致
    blocks = {m.group(1): m.group(2) for m in RE_SCHEME_BLOCK.finditer(text)}
    if len(blocks) > 1:
        sets = {}
        for sid, body in blocks.items():
            sets[sid] = set(m.group(1) for m in RE_VAR_DEF.finditer(body))
        base_id = list(sets.keys())[0]
        base = sets[base_id]
        for sid, s in sets.items():
            if sid == base_id:
                continue
            missing = sorted(base - s)
            extra = sorted(s - base)
            if missing:
                findings.append(Finding(
                    "CSV-02", "FAIL", rel,
                    "方案 `%s` 比 `%s` **少定义** %d 个 token：%s"
                    % (sid, base_id, len(missing), ", ".join(missing))))
            if extra:
                findings.append(Finding(
                    "CSV-02", "WARN", rel,
                    "方案 `%s` 比 `%s` 多定义 %d 个 token：%s"
                    % (sid, base_id, len(extra), ", ".join(extra))))

    return {"defined": defined, "used": used, "undefined": undefined,
            "blocks": blocks}


def _scheme_block_vars(text: str, sid: str) -> dict:
    """取某个方案块 `html[data-scheme="sid"]{...}` 里定义的变量。"""
    for m in RE_SCHEME_BLOCK.finditer(text):
        if m.group(1) == sid:
            return dict((x.group(1), x.group(2).strip())
                        for x in RE_VAR_DEF.finditer(m.group(2)))
    return {}


def _first_defs(text: str) -> dict:
    """取每个变量的**第一次**定义（= `:root` 里的基础值，与 check_contrast.py 同口径）。"""
    out = {}
    for m in RE_VAR_DEF.finditer(text):
        if m.group(1) not in out:
            out[m.group(1)] = m.group(2).strip()
    return out


def _norm_hex(value: str) -> str:
    """把 #rgb / #rrggbb 统一成大写 6 位；非 hex 原样返回。"""
    v = (value or "").strip().upper()
    if not v.startswith("#"):
        return v
    h = v[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:
        h = h[:6]
    return "#" + h


def check_accent_drift(root: str, findings: list) -> int:
    """CSV-03：iOS 原型的方案强调色 vs variants 的 --accent / --on-accent。

    variants 是**每个方案一个独立文件**（`:root` 里直接定义 `--accent`），
    iOS 原型是**一个文件四套方案**（`html[data-scheme=...]` 覆盖）⇒ 两边读法不同。
    """
    checked = 0
    for ios_rel in (os.path.join("prototype", "ios", "ios-light.html"),
                    os.path.join("prototype", "ios", "ios-dark.html")):
        ios_path = os.path.join(root, ios_rel)
        if not os.path.isfile(ios_path):
            continue
        ios_text = _read(ios_path)
        for sid, swift_name, variant_file in SCHEME_MAP:
            var_path = os.path.join(root, "prototype", "variants", variant_file)
            if not os.path.isfile(var_path):
                continue
            v_vars = _first_defs(_read(var_path))
            v_accent = v_vars.get("--accent")
            v_on = v_vars.get("--on-accent")
            if not v_accent:
                findings.append(Finding(
                    "CSV-03", "FAIL", variant_file,
                    "variants 里方案 `%s` 没有 `--accent` 定义" % sid))
                continue
            i_vars = _scheme_block_vars(ios_text, sid)
            i_accent = i_vars.get("--accent") or i_vars.get("--bubble-out")
            if not i_accent:
                findings.append(Finding(
                    "CSV-03", "FAIL", ios_rel,
                    "iOS 原型里方案 `%s` 没有强调色定义（`--accent` / `--bubble-out` 都缺）" % sid))
                continue
            if _norm_hex(i_accent) != _norm_hex(v_accent):
                findings.append(Finding(
                    "CSV-03", "FAIL", ios_rel,
                    "方案 `%s` 强调色**漂移**：iOS 原型 `%s` ≠ variants `%s`"
                    % (sid, i_accent, v_accent)))
            else:
                checked += 1
            i_on = i_vars.get("--on-accent") or i_vars.get("--bubble-out-text")
            if v_on and i_on and _norm_hex(i_on) != _norm_hex(v_on):
                findings.append(Finding(
                    "CSV-03", "FAIL", ios_rel,
                    "方案 `%s` 强调色上的文字色**漂移**：iOS 原型 `%s` ≠ variants `%s`"
                    % (sid, i_on, v_on)))
    return checked


def run_self_test() -> int:
    import tempfile

    print("[self-test] check_css_vars.py 门禁自检")
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

    with tempfile.TemporaryDirectory() as td:
        # 夹具 1：引用了未定义变量 → CSV-01 必须 FAIL
        p1 = os.path.join(td, "bad1.html")
        with io.open(p1, "w", encoding="utf-8", newline="") as fh:
            fh.write(":root{--a:#111;}\n.x{color:var(--tint);}\n")
        f1 = []
        scan_file(p1, "bad1.html", f1)
        check("未定义变量被 CSV-01 抓到",
              any(x.code == "CSV-01" for x in f1),
              str([(x.code, x.msg) for x in f1]))

        # 夹具 2：两个方案块 token 集合不同 → CSV-02 必须 FAIL
        p2 = os.path.join(td, "bad2.html")
        with io.open(p2, "w", encoding="utf-8", newline="") as fh:
            fh.write(":root{--a:#111;--b:#222;}\n"
                     'html[data-scheme="one"]{\n--a:#111;\n--b:#222;\n}\n'
                     'html[data-scheme="two"]{\n--a:#333;\n}\n')
        f2 = []
        scan_file(p2, "bad2.html", f2)
        check("方案 token 集合不一致被 CSV-02 抓到",
              any(x.code == "CSV-02" and x.severity == "FAIL" for x in f2),
              str([(x.code, x.msg) for x in f2]))

        # 夹具 3：健康文件 → 零 FAIL
        p3 = os.path.join(td, "good.html")
        with io.open(p3, "w", encoding="utf-8", newline="") as fh:
            fh.write(":root{--a:#111;--accent:#AF4C37;}\n"
                     'html[data-scheme="one"]{\n--a:#111;\n--accent:#AF4C37;\n}\n'
                     'html[data-scheme="two"]{\n--a:#222;\n--accent:#B74332;\n}\n'
                     ".x{color:var(--a);border-color:var(--accent);}\n")
        f3 = []
        scan_file(p3, "good.html", f3)
        check("健康文件零 FAIL", not any(x.severity == "FAIL" for x in f3),
              str([(x.code, x.msg) for x in f3]))

        # 夹具 4：@property 注册过的变量算已定义
        p4 = os.path.join(td, "prop.html")
        with io.open(p4, "w", encoding="utf-8", newline="") as fh:
            fh.write("@property --registered{syntax:'<color>';inherits:true;}\n"
                     ":root{--a:#111;}\n.x{color:var(--registered);}\n")
        f4 = []
        scan_file(p4, "prop.html", f4)
        check("@property 注册的变量不算未定义",
              not any(x.code == "CSV-01" for x in f4),
              str([(x.msg) for x in f4]))

    print("=" * 64)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="原型 CSS 变量体检")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--self-test", action="store_true", help="门禁自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test()

    root = os.path.abspath(args.root)
    findings: list = []
    scanned = 0

    for rel in HTML_GLOBS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        scanned += 1
        scan_file(path, rel.replace(os.sep, "/"), findings)

    drift_checked = check_accent_drift(root, findings)

    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]

    print("=" * 68)
    print("check_css_vars.py —— 原型 CSS 变量体检")
    print("=" * 68)
    print("仓库根        : %s" % root)
    print("扫描 HTML     : %d 个（prototype/ios + ios/prototype + prototype/）" % scanned)
    print("强调色一致性  : 比对 %d 组（iOS 原型 ↔ variants）" % drift_checked)
    print("-" * 68)
    if not findings:
        print("ALL PASS —— 被引用的 CSS 变量全部有定义，4 套方案 token 集合一致。")
    for f in findings:
        print("[%s] %s  %s" % (f.severity, f.code, f.where))
        print("        %s" % f.msg)
    print("-" * 68)
    print("FAIL=%d  WARN=%d" % (len(fails), len(warns)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
