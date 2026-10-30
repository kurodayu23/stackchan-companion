#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_md_tables.py —— 修 Markdown 表格的「单元格内竖线未转义」与「列数不齐」

为什么需要
----------
本项目的**表格铁律**：
1. 单元格内的 `|` 必须写成 `\\|`，否则 Markdown 解析器会把它当成列分隔符；
2. 每一行的列数必须 == 表头列数；
3. 表格块内不能有空行；
4. 文档 LF + UTF-8 无 BOM。

`tools/check_docs.py` 与 `tools/repo_release_check.py` 都会按这条铁律判 FAIL。
人工修表很慢且容易漏 ⇒ 写个脚本。

⚠️ **它不猜语义**：列数不齐时，它只做「把多出来的列合并回上一格」这种**保内容**的处理，
并把修不了的行报告出来。**内容绝不被删除。**

用法
----
    py -3.12 tools/fix_md_tables.py <文件.md> [...]        # 就地修复
    py -3.12 tools/fix_md_tables.py --check <文件.md> [...] # 只报告不修改
    py -3.12 tools/fix_md_tables.py --self-test

退出码：0 = 全过（或只报告了无法自动修的项）；1 = 有无法自动修的项。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

__version__ = "1.0.0"

# 表格分隔行：|---|---|---| 或 |:--|:--:|--:| 等
_SEP_RE = re.compile(r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$")


def _split_row(line: str) -> list:
    """按**未转义**的 `|` 切分单元格。

    关键：`\\|` 不是分隔符（它是被转义的竖线），所以要先把 `\\|` 保护起来。
    """
    s = line.strip()
    cells = []
    cur = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n and s[i + 1] == "|":
            cur.append("\\|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    cells.append("".join(cur))
    # 首尾若是空（行首/行尾的分隔竖线），去掉
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return cells


def _is_table_row(line: str) -> bool:
    s = line.strip()
    if not s.startswith("|"):
        return False
    return "|" in s[1:]


def _is_sep(line: str) -> bool:
    s = line.strip()
    if "|" not in s:
        return False
    cells = _split_row(s)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells if c.strip() != "") \
        and len(cells) > 0


def find_tables(lines: list) -> list:
    """找出所有表格块，返回 [(start, end_exclusive, header_cols)]。

    表格块 = 连续的「表头行 + 分隔行 + ≥0 个数据行」。
    """
    tables = []
    i = 0
    n = len(lines)
    while i < n - 1:
        if _is_table_row(lines[i]) and _is_sep(lines[i + 1]):
            header_cols = len(_split_row(lines[i]))
            j = i + 2
            while j < n and _is_table_row(lines[j]):
                j += 1
            tables.append((i, j, header_cols))
            i = j
        else:
            i += 1
    return tables


def _escape_cell_pipes(cell: str) -> str:
    """把单元格内**未转义**的 `|` 转成 `\\|`。

    已转义的 `\\|` 保持不变（不能变成 `\\\\|`）。
    """
    out = []
    i = 0
    n = len(cell)
    while i < n:
        ch = cell[i]
        if ch == "\\" and i + 1 < n and cell[i + 1] == "|":
            out.append("\\|")
            i += 2
            continue
        if ch == "|":
            out.append("\\|")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _join_row(cells: list) -> str:
    return "| " + " | ".join(c.strip() for c in cells) + " |"


def fix_table(lines: list, start: int, end: int, header_cols: int) -> tuple:
    """修一个表格块，返回 (新行列表, 未能自动修的行号列表)。

    处理：
    1. 每行单元格内未转义的 `|` → `\\|`；
    2. 列数 > 表头：把多出的列**合并回上一格**（用 `\\|` 连接，不丢内容）；
    3. 列数 < 表头：补空单元格（不丢内容）。
    """
    new = list(lines[start:end])
    unresolved = []
    out = []
    for offset, line in enumerate(new):
        lineno = start + offset + 1
        if _is_sep(line):
            out.append(line.rstrip())
            continue
        cells = _split_row(line)
        # 1) 转义
        cells = [_escape_cell_pipes(c) for c in cells]
        # 2/3) 列数对齐
        if len(cells) > header_cols:
            # 多出的列合并回上一格：保内容优先
            head = cells[:header_cols - 1]
            tail = cells[header_cols - 1:]
            merged = "\\|".join(tail)
            cells = head + [merged]
            unresolved.append(lineno)
        elif len(cells) < header_cols:
            cells = cells + [""] * (header_cols - len(cells))
        out.append(_join_row(cells))
    return out, unresolved


def fix_file(path: str, check_only: bool = False) -> dict:
    with io.open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    had_crlf = "\r\n" in text
    lines = text.replace("\r\n", "\n").split("\n")

    tables = find_tables(lines)
    changed = 0
    unresolved = []
    if tables:
        new_lines = []
        pos = 0
        for (start, end, header_cols) in tables:
            new_lines.extend(lines[pos:start])
            fixed, un = fix_table(lines, start, end, header_cols)
            new_lines.extend(fixed)
            unresolved.extend(un)
            # 统计是否真的变了
            for a, b in zip(lines[start:end], fixed):
                if a.strip() != b.strip():
                    changed += 1
                    break
            pos = end
        new_lines.extend(lines[pos:])
        lines = new_lines

    result = {
        "path": path,
        "tables": len(tables),
        "changed_tables": changed,
        "unresolved": unresolved,
        "modified": changed > 0,
    }
    if changed > 0 and not check_only:
        out = "\n".join(lines)
        # 保持原有的行尾风格
        if had_crlf:
            out = out.replace("\n", "\r\n")
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
    return result


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

SAMPLE = """# T

| a | b | c |
|---|---|---|
| x | y\\|z | w |
| p\\|q | r | s |
| toolong | cell | extra | more |
"""

SAMPLE_FIXED = """# T

| a | b | c |
|---|---|---|
| x | y\\|z | w |
| p\\|q | r | s |
| toolong | cell | extra \\| more |
"""


def self_test() -> int:
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 切分
    cells = _split_row("| a | b\\|c | d |")
    ok("切分：转义竖线不切", len(cells) == 3, "got %d %r" % (len(cells), cells))
    ok("切分：保留转义标记", cells[1].strip() == "b\\|c", repr(cells[1]))

    # 表格识别
    lines = SAMPLE.split("\n")
    tables = find_tables(lines)
    ok("识别 1 个表格", len(tables) == 1, "got %d" % len(tables))
    if tables:
        s, e, hc = tables[0]
        ok("表头 3 列", hc == 3, str(hc))
        ok("表格块含 5 行", e - s == 5, str(e - s))

    # 修复
    fixed, un = fix_table(lines, tables[0][0], tables[0][1], 3)
    # 比较对象是**表格块**（不含 "# T" 标题与空行）
    fixed_block = "\n".join(fixed)
    expect_block = "\n".join(SAMPLE_FIXED.strip("\n").split("\n")[2:])
    ok("修复后与期望一致", fixed_block == expect_block,
       "got %r" % fixed_block)
    ok("多列行被标记为 unresolved", un and un[0] == 7, str(un))

    # 不改内容
    ok("修复不丢内容：extra 与 more 都还在",
       "extra" in "\n".join(fixed) and "more" in "\n".join(fixed))

    # 幂等：再修一次不变
    fixed2, _ = fix_table(fixed, 0, len(fixed), 3)
    ok("幂等：二次修复无变化", fixed2 == fixed)

    # 列数不足 → 补空
    short = ["| a | b | c |", "|---|---|---|", "| x |"]
    fs, _ = fix_table(short, 0, 3, 3)
    ok("列数不足补空", len(_split_row(fs[2])) == 3, fs[2])

    passed = sum(1 for _, c, _ in checks if c)
    failed = [c for c in checks if not c[1]]
    for name, cond, detail in checks:
        print("  %s %s%s" % ("PASS" if cond else "FAIL", name,
                             ("  (%s)" % detail) if detail and not cond else ""))
    print("\nSELF-TEST: %d/%d PASS" % (passed, len(checks)))
    if failed:
        print("FAILED: %s" % ", ".join(f[0] for f in failed))
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="修 Markdown 表格的竖线转义与列数对齐")
    ap.add_argument("files", nargs="*", help="要修的 .md 文件")
    ap.add_argument("--check", action="store_true", help="只报告不修改")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.files:
        ap.error("需要至少一个文件路径")

    total_unresolved = 0
    for path in args.files:
        if not os.path.exists(path):
            print("[skip] 不存在：%s" % path)
            continue
        res = fix_file(path, check_only=args.check)
        status = "已修" if (res["modified"] and not args.check) else (
            "需修" if res["modified"] else "ok")
        print("[%s] %s — 表格 %d 个，%s%s" % (
            status, os.path.relpath(path), res["tables"], res["changed_tables"],
            ("，列数合并行：%s" % res["unresolved"]) if res["unresolved"] else ""))
        total_unresolved += len(res["unresolved"])
    if total_unresolved:
        print("\n⚠️ 有 %d 行的列数超出表头，已把多出的列合并回上一格（内容未删）。"
              "请人工确认合并结果是否可读。" % total_unresolved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
