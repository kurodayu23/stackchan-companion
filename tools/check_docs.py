#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档完整性自检（仓库内版，可在 CI 里跑）。

检查项：

* 表格块内**无空行**
* 表格每行**列数 == 表头列数**
* 单元格内的竖线必须转义成 `\\|`（只按「未转义」的 | 分列）
* **UTF-8 无 BOM**
* **LF 行尾**（无 CRLF）
* ⭐ **无乱码**（U+FFFD 替换字符 = 0 处）

⭐ **乱码检查的由来（2026-10-25）**：实测全仓有 **5 份文档、10 处 U+FFFD**
（例：`换个␦␦␦台机器`、`「镜␦␦␦」`、`判␦␦用户`）。
成因是某些字符在工具链里被错误解码后**写回文件**。
用户明确要求「严禁出现乱码」⇒ 这条现在是硬门禁。

用法::

    py -3.12 tools/check_docs.py                 # 自动扫描 docs/ + 根目录 md
    py -3.12 tools/check_docs.py a.md b.md ...   # 指定文件

退出码：0 = 全过；1 = 有 FAIL；2 = 没找到任何文件
"""

from __future__ import annotations

import io
import os
import re
import sys

FENCE = chr(96) * 3
SEP = re.compile(r"^\|[\s:|-]+\|$")
UNESC_PIPE = re.compile(r"(?<!\\)\|")

#: U+FFFD = Unicode 替换字符，出现即说明**有字节被错误解码**
REPLACEMENT_CHAR = "\ufffd"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "DerivedData", "build", ".build"}


def ncols(line: str) -> int:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return len(UNESC_PIPE.split(s))


def discover(root: str):
    out = []
    for base in (os.path.join(root, "docs"), root):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if not name.lower().endswith(".md"):
                    continue
                p = os.path.join(dirpath, name)
                if base == root and os.path.dirname(os.path.abspath(p)) != os.path.abspath(root):
                    continue          # 根目录只收顶层 md
                out.append(p)
    return sorted(set(out))


def check(path: str) -> bool:
    with io.open(path, "rb") as f:
        raw = f.read()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    bom = raw[:3] == b"\xef\xbb\xbf"
    txt = raw.decode("utf-8-sig", "replace")
    lines = txt.replace("\r\n", "\n").split("\n")

    tables = 0
    bad_blank = 0
    bad_col = 0
    offenders = []
    infence = False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith(FENCE):
            infence = not infence
            i += 1
            continue
        if ((not infence) and s.startswith("|")
                and i + 1 < len(lines)
                and SEP.match(lines[i + 1].strip())):
            tables += 1
            ncol = ncols(lines[i])
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                if lines[j].strip() == "":
                    bad_blank += 1
                c = ncols(lines[j])
                if c != ncol:
                    bad_col += 1
                    if len(offenders) < 4:
                        offenders.append((j + 1, ncol, c, lines[j][:90]))
                j += 1
            i = j
            continue
        i += 1

    name = os.path.basename(path)

    # ⭐ 乱码检查：U+FFFD = 有字节被错误解码（硬门禁）
    mojibake = []
    for ln, text in enumerate(lines, start=1):
        if REPLACEMENT_CHAR in text:
            mojibake.append((ln, text.count(REPLACEMENT_CHAR),
                             text[max(0, text.index(REPLACEMENT_CHAR) - 24):
                                  text.index(REPLACEMENT_CHAR) + 30]))

    ok = (bad_blank == 0 and bad_col == 0 and not bom and crlf == 0
          and not mojibake)
    print("%s %-52s tables=%2d badBlank=%d badCol=%d CRLF=%-3d LF=%-5d BOM=%s mojibake=%d"
          % ("OK  " if ok else "FAIL", name[:52], tables, bad_blank, bad_col,
             crlf, lf, bom, len(mojibake)))
    for ln, a, b, raw_line in offenders:
        print("        L%-5d 期望%d列 实得%d列 | %s" % (ln, a, b, raw_line))
    for ln, cnt, ctx in mojibake[:4]:
        print("        L%-5d 乱码 x%d | ...%s..." % (ln, cnt, ctx.replace("\n", " ")))
    return ok


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        files = list(argv)
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = discover(root)
    if not files:
        print("❌ 没找到任何 .md 文件")
        return 2
    ok = True
    for p in files:
        try:
            ok = check(p) and ok
        except Exception as e:  # noqa: BLE001
            print("ERR  %s  %s" % (p, e))
            ok = False
    print("\n%s（%d 份）" % ("ALL PASS" if ok else "HAS FAILURE", len(files)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
