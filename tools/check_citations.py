#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_citations.py —— **每个被引用的 arXiv ID / DOI 都必须能溯源**

为什么需要它
------------
项目硬约束写着：「所有结论必须有**实际抓取的来源**（给 URL）；**禁止凭记忆编造**」。
在此之前这条**只靠自觉** —— 任何人在文档里写一个 `arXiv:2501.99999` 都查不出来。

本门禁把它变成**机器可判**：

* **溯源池** = `docs/research/` 下带 `**主题键**：` 标记的**文献留痕快照**
  （当前 8 份：68 / 69 / 71 / 74 / 83 号 + `runs/` 3 份）
  ⇒ 池里的每个 ID 都是**抓取工具真实返回过**的。
* **登记表** = `tools/citation_sources.txt`
  ⇒ 早期（49 / 51 / 54 / 55 / 37 号等）**直接检索**得到的引用不在留痕快照里，
  逐条登记（带规范 URL + arXiv API 校验状态 + 首次出现的文档）⇒ **登记即审计**。
* **被引集合** = `docs/spec/**.md` 与 `docs/research/**.md`（**排除池文件本身**）里出现的
  全部 arXiv ID 与 DOI。

判定：被引标识 ∈ 池 ∪ 登记表 ⇒ OK；否则 **FAIL**（= 可能是凭记忆编的）。

⚠️ 本门禁**不联网**（arXiv 真实性在登记表生成时已用 API 校验过并落盘状态）。

用法
----
    py -3.12 tools/check_citations.py --root .
    py -3.12 tools/check_citations.py --self-test

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 文献留痕快照的机械识别标记（`fetch_literature.py` 渲染时写入）
POOL_MARK = "**主题键**："
#: 登记表
REGISTRY = os.path.join("tools", "citation_sources.txt")

RX_ARXIV = re.compile(r"(?:arXiv:`?|\b)(\d{4}\.\d{4,5})(?:v\d+)?`?", re.I)
RX_DOI = re.compile(
    r"(?:DOI:`?|doi:\s*|\bdoi\.org/)(10\.\d{4,9}/[^\s`\)\]<>\"'，。；、]+)", re.I)
TAIL = ".,;)]}'\"，。；、）】》"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "DerivedData", "build", ".build"}


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def md_files(root: str) -> list:
    out = []
    for base in (os.path.join(root, "docs"), root):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.lower().endswith(".md"):
                    out.append(os.path.join(dirpath, name))
    return sorted(set(out))


def ids_in(text: str) -> set:
    out = set()
    for m in RX_ARXIV.finditer(text):
        out.add(m.group(1))
    for m in RX_DOI.finditer(text):
        out.add(m.group(1).rstrip(TAIL).lower())
    return out


def load_registry(path: str) -> set:
    if not os.path.isfile(path):
        return set()
    out = set()
    for line in read(path).split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.split("\t")[0].strip().lower())
    return out


def scan(root: str) -> list:
    """返回 [(level, where, msg)]。"""
    findings = []
    files = md_files(root)
    pool, others = [], []
    for p in files:
        t = read(p)
        (pool if POOL_MARK in t else others).append((p, t))

    pool_ids = set()
    for _p, t in pool:
        pool_ids |= ids_in(t)
    registry = load_registry(os.path.join(root, REGISTRY))

    known = pool_ids | registry
    for p, t in others:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        miss = sorted(ids_in(t) - known)
        if miss:
            findings.append((
                "FAIL", rel,
                "引用了 %d 个**无法溯源**的标识（既不在文献留痕快照里，也不在 %s 里）：\n"
                "         %s\n"
                "         ⇒ 要么它其实被检索到过（补进登记表并核对 URL），"
                "要么它是凭记忆写的（删掉）"
                % (len(miss), REGISTRY, ", ".join(miss[:12])
                   + (" …" if len(miss) > 12 else ""))))
    return findings


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def self_test() -> int:
    import tempfile

    POOL_FILE = (
        "# 留痕\n\n**主题键**：`demo`\n\n"
        "### demo.1 Real Paper\n\n- arXiv:`2401.00001` ｜ 引用数：1\n")
    DOC_OK = "# 分析\n\n我们引用 arXiv:`2401.00001` 的结论。\n"
    DOC_REG = "# 分析\n\n我们引用 arXiv:`2401.00002`（已登记）。\n"
    DOC_BAD = "# 分析\n\n我们引用 arXiv:`2401.99999`（疑似编造）。\n"
    REG = ("# 登记表\n\n"
           "2401.00002\thttps://arxiv.org/abs/2401.00002\tverified\tdocs/research/x.md\n")

    def build(td, doc):
        os.makedirs(os.path.join(td, "docs", "research"), exist_ok=True)
        os.makedirs(os.path.join(td, "tools"), exist_ok=True)
        with io.open(os.path.join(td, "docs", "research", "pool.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write(POOL_FILE)
        with io.open(os.path.join(td, "docs", "research", "doc.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write(doc)
        with io.open(os.path.join(td, REGISTRY), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write(REG)

    checks = []
    with tempfile.TemporaryDirectory() as td:
        build(td, DOC_OK)
        checks.append(("留痕池里的引用不误报", not scan(td)))
    with tempfile.TemporaryDirectory() as td:
        build(td, DOC_REG)
        checks.append(("登记表里的引用不误报", not scan(td)))
    with tempfile.TemporaryDirectory() as td:
        build(td, DOC_BAD)
        checks.append(("无法溯源的引用被 DEC-CIT-01 抓到",
                       any(f[0] == "FAIL" for f in scan(td))))
    with tempfile.TemporaryDirectory() as td:
        # 池文件自身被排除：它引用自己池里的 ID 不该报
        build(td, DOC_OK)
        with io.open(os.path.join(td, "docs", "research", "pool.md"), "a",
                     encoding="utf-8", newline="") as fh:
            fh.write("\n补充：另见 arXiv:`2401.00001`。\n")
        checks.append(("留痕文件自身不被当成被引文档", not scan(td)))

    print("[self-test] check_citations.py 门禁自检")
    print("=" * 62)
    ok = 0
    for name, passed in checks:
        print("  %-42s %s" % (name, "PASS" if passed else "FAIL"))
        ok += bool(passed)
    print("=" * 62)
    print("[self-test] 通过 %d / %d" % (ok, len(checks)))
    return 0 if ok == len(checks) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="引用可溯源性体检：每个被引 arXiv ID / DOI 都必须能在"
                    "文献留痕快照或登记表里找到")
    ap.add_argument("--root", default=".", help="仓库根")
    ap.add_argument("--self-test", action="store_true", help="离线自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    root = os.path.abspath(args.root)
    findings = scan(root)
    print("=" * 70)
    print("check_citations.py —— 引用可溯源性体检")
    print("=" * 70)
    print("仓库根        : %s" % root)
    if findings:
        for level, where, msg in findings:
            print("[%s] %s" % (level, where))
            print("       %s" % msg)
        print("-" * 70)
        print("FAIL=%d" % len(findings))
        return 1
    print("ALL PASS —— 每个被引用的 arXiv ID / DOI 都能溯源")
    return 0


if __name__ == "__main__":
    sys.exit(main())
