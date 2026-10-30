#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_repo_stats.py —— `docs/spec/09` §二「进度快照」里的仓库规模数字必须与实际一致

为什么需要它
------------
`docs/spec/09` §二 是一张**给人看的资产清单**（多少源文件、多少测试、多少份文档）。
它是求职作品里最容易被追问的一页，**数字错了就是硬伤**。

⚠️ 这条门禁是被一次**独立审计**逼出来的：审计员在报告里明写
「本工作区只有 `docs/`（无 `tools/`、`server/`、`ios/`、`prototype/`），
故 09 §二的『19 个 .py / 28 项门禁 / 67 个测试 / 43 Swift 文件 / 91 个测试函数 /
75 份留痕 / 00–08 共 9 份』等**仓库规模数字无法在本机复核**」
⇒ **审计员能看见这些数字，但核不了** ⇒ 只能由本机来守。

检查项
------
| 资产 | 核什么 |
|---|---|
| `server/` | `.py` 源文件数（不含 `tests/`）、测试文件数 |
| `ios/` | `.swift` 文件数、测试文件数、`func test` 函数数 |
| `tools/` | `.py` 文件数 |
| `docs/spec/` | `.md` 文件数 |
| `docs/research/` | `.md` 文件数（递归，含子目录） |

用法
----
    py -3.12 tools/check_repo_stats.py --root .
    py -3.12 tools/check_repo_stats.py --self-test

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SPEC09_GLOB = os.path.join("docs", "spec", "09-*.md")
#: §二 的小节标题（只认「## 二、」开头的）
RE_H_2 = re.compile(r"^##\s+二\b")
#: `func test` 函数（Swift XCTest）
RE_SWIFT_TEST = re.compile(r"^\s*func\s+test", re.M)

#: 每种资产的「规模」列写法 → (正则, 取哪几组数字)
PATTERNS = {
    "server/": (
        re.compile(r"(\d+)\s*源文件\s*\+\s*(\d+)\s*测试文件"), ("源文件", "测试文件")),
    "ios/": (
        re.compile(r"(\d+)\s*Swift\s*文件\s*/\s*(\d+)\s*测试文件\s*/\s*(\d+)\s*个测试函数"),
        ("Swift 文件", "测试文件", "测试函数")),
    "tools/": (
        re.compile(r"(\d+)\s*个\s*`?\.py`?"), (".py",)),
    "docs/spec/": (
        re.compile(r"共\s*(\d+)\s*份"), ("份",)),
    "docs/research/": (
        re.compile(r"(\d+)\s*份留痕"), ("留痕",)),
}


class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code, severity, where, msg):
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg


def _read(path: str) -> str:
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def _section(md: str, header_re) -> str:
    lines = md.splitlines()
    out = []
    inside = False
    for line in lines:
        if not inside:
            if header_re.match(line):
                inside = True
            continue
        if re.match(r"^#{1,6}\s", line):
            break
        out.append(line)
    return "\n".join(out)


def parse_stats_rows(md: str) -> dict:
    """从 §二 的表里取出 {资产键: 规模列文字}。"""
    sec = _section(md, RE_H_2)
    rows = {}
    for line in sec.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        first = cells[0].strip()
        if first in ("资产", "---") or set(first) <= set("-: "):
            continue
        # 资产键在文档里是写成 `` `server/` `` 的 ⇒ 先去掉反引号再匹配
        first_clean = first.replace("`", "")
        for key in PATTERNS:
            if first_clean.startswith(key):
                rows[key] = cells[1]
                break
    return rows


def actual_counts(repo: str) -> dict:
    """实际清点仓库规模。"""
    out = {}

    # server/
    src = _walk_py(os.path.join(repo, "server"))
    out["server/"] = {
        "源文件": sum(1 for p in src if os.sep + "tests" + os.sep not in p),
        "测试文件": sum(1 for p in src if os.sep + "tests" + os.sep in p),
    }

    # ios/
    swift = [os.path.join(dp, f)
             for dp, _dn, fn in os.walk(os.path.join(repo, "ios"))
             for f in fn if f.endswith(".swift")]
    out["ios/"] = {
        "Swift 文件": len(swift),
        "测试文件": sum(1 for p in swift if "Tests" in p),
        "测试函数": sum(len(RE_SWIFT_TEST.findall(_read(p))) for p in swift),
    }

    # tools/
    out["tools/"] = {
        ".py": sum(1 for f in os.listdir(os.path.join(repo, "tools"))
                   if f.endswith(".py")),
    }

    # docs/spec/
    out["docs/spec/"] = {
        "份": len([f for f in os.listdir(os.path.join(repo, "docs", "spec"))
                   if f.endswith(".md")]),
    }

    # docs/research/（递归）
    n = 0
    for dp, _dn, fn in os.walk(os.path.join(repo, "docs", "research")):
        n += sum(1 for f in fn if f.endswith(".md"))
    out["docs/research/"] = {"留痕": n}

    return out


def _walk_py(root: str) -> list:
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith(".py"):
                out.append(os.path.join(dp, f))
    return out


def scan(repo: str, findings: list) -> dict:
    import glob

    p09 = sorted(glob.glob(os.path.join(repo, SPEC09_GLOB)))
    if not p09:
        findings.append(Finding("RS-01", "FAIL", "docs/spec/09-*", "找不到 09 号文件"))
        return {}
    md = _read(p09[0])
    rel = os.path.relpath(p09[0], repo).replace(os.sep, "/")
    rows = parse_stats_rows(md)
    if not rows:
        findings.append(Finding("RS-02", "FAIL", rel,
                                 "09 号 §二 没解析出任何资产行（小节标题或表格结构变了？）"))
        return {}

    actual = actual_counts(repo)
    checked = 0
    for key, (rx, labels) in PATTERNS.items():
        if key not in rows:
            findings.append(Finding("RS-03", "WARN", rel,
                                   "09 号 §二 没找到「%s」这一行（跳过核对）" % key))
            continue
        m = rx.search(rows[key])
        if not m:
            findings.append(Finding("RS-04", "FAIL", rel,
                                   "09 号 §二「%s」的规模写法变了，解析不出数字：%r"
                                   % (key, rows[key])))
            continue
        claimed = [int(g) for g in m.groups()]
        for label, want in zip(labels, claimed):
            got = actual[key][label]
            checked += 1
            if got != want:
                findings.append(Finding(
                    "RS-05", "FAIL", rel,
                    "09 号 §二写「%s」= %d %s，实际是 %d"
                    % (key, want, label, got)))
    return {"checked": checked}


def run_self_test() -> int:
    import tempfile

    print("[self-test] check_repo_stats.py 门禁自检")
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

    GOOD09 = """# 09 · 施工顺序

## 二、当前进度快照（截至 2026-10-25 06:30）

| 资产 | 规模 | 状态 |
|---|---|---|
| `server/`（Python 替身后端） | 2 源文件 + 1 测试文件 | ✅ |
| `ios/`（SwiftUI 工程） | 2 Swift 文件 / 1 测试文件 / 2 个测试函数 | ✅ |
| `tools/`（取证与门禁工具） | 3 个 `.py` | ✅ |
| `docs/spec/` | 00–09 共 1 份 | ✅ |
| `docs/research/` | 3 份留痕 | ✅ |
"""

    def build(td, s09=GOOD09):
        os.makedirs(os.path.join(td, "docs", "spec"), exist_ok=True)
        os.makedirs(os.path.join(td, "docs", "research"), exist_ok=True)
        os.makedirs(os.path.join(td, "server", "tests"), exist_ok=True)
        os.makedirs(os.path.join(td, "ios", "Tests"), exist_ok=True)
        os.makedirs(os.path.join(td, "tools"), exist_ok=True)
        with io.open(os.path.join(td, "docs", "spec", "09-x.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write(s09)
        for p in ("server/a.py", "server/b.py", "server/tests/t.py"):
            with io.open(os.path.join(td, p.replace("/", os.sep)), "w",
                         encoding="utf-8", newline="") as fh:
                fh.write("# x\n")
        with io.open(os.path.join(td, "ios", "A.swift"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("func testA() {}\nfunc testB() {}\n")
        with io.open(os.path.join(td, "ios", "Tests", "T.swift"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("// nothing\n")
        for p in ("tools/a.py", "tools/b.py", "tools/c.py"):
            with io.open(os.path.join(td, p), "w", encoding="utf-8", newline="") as fh:
                fh.write("# x\n")
        for p in ("docs/research/1.md", "docs/research/2.md"):
            with io.open(os.path.join(td, p), "w", encoding="utf-8", newline="") as fh:
                fh.write("x\n")
        os.makedirs(os.path.join(td, "docs", "research", "sub"), exist_ok=True)
        with io.open(os.path.join(td, "docs", "research", "sub", "x.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("x\n")
        return td

    with tempfile.TemporaryDirectory() as td:
        build(td)
        f = []
        scan(td, f)
        check("健康夹具零 FAIL", not any(x.severity == "FAIL" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        build(td, GOOD09.replace("2 源文件 + 1 测试文件", "3 源文件 + 1 测试文件"))
        f = []
        scan(td, f)
        check("源文件数写错被 RS-05 抓到",
              any(x.code == "RS-05" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        build(td, GOOD09.replace("3 份留痕", "5 份留痕"))
        f = []
        scan(td, f)
        check("留痕份数写错被 RS-05 抓到",
              any(x.code == "RS-05" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        build(td, GOOD09.replace("2 Swift 文件 / 1 测试文件 / 2 个测试函数",
                                 "2 Swift 文件 / 1 测试文件 / 3 个测试函数"))
        f = []
        scan(td, f)
        check("测试函数数写错被 RS-05 抓到",
              any(x.code == "RS-05" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        build(td, GOOD09.replace("| `docs/spec/` | 00–09 共 1 份 |", "| `docs/spec/` | 00–09 共 9 份 |"))
        f = []
        scan(td, f)
        check("spec 份数写错被 RS-05 抓到",
              any(x.code == "RS-05" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        build(td, GOOD09.replace("3 个 `.py`", "3 个 `.py`（看不清）"))
        f = []
        scan(td, f)
        check("规模写法变了被 RS-04 抓到或不误报",
              not any(x.severity == "FAIL" and x.code != "RS-04" for x in f),
              str([(x.code, x.msg) for x in f]))

    print("=" * 64)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="09 号进度快照 ↔ 实际仓库规模 一致性体检")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--self-test", action="store_true", help="门禁自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test()

    root = os.path.abspath(args.root)
    findings = []
    stats = scan(root, findings)
    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]
    print("=" * 70)
    print("check_repo_stats.py —— 进度快照里的规模数字 ↔ 实际仓库")
    print("=" * 70)
    print("仓库根        : %s" % root)
    print("核对项数      : %d" % stats.get("checked", 0))
    print("-" * 70)
    for f in findings:
        print("[%s] %s  %s" % (f.severity, f.where, f.msg))
    print("-" * 70)
    print("FAIL=%d  WARN=%d" % (len(fails), len(warns)))
    if not fails:
        print("ALL PASS —— 进度快照里的规模数字与实际仓库一致。")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
