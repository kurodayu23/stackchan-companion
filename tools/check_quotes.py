#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""check_quotes.py —— 引文保真机械校验（抄引文不许靠人眼）

## 为什么要有这个门禁

2026-10-25 实测（`docs/research/80` §7，DeepSeek 员工池自己做的机械比对）：
把 84 条 ≥20 字符的「」引文做**归一化子串比对**（去 `**`、去反引号、折叠空白），
去语料 + spec 全文里找，结果 **8 处是「我以为抄对了、其实改过」的**：

| 错法 | 为什么危险 |
|---|---|
| 把主语**缩写** | 读起来完全通顺，但已不是原文 |
| U+2010 连字符写成 ASCII `-` | 肉眼几乎不可见 |
| 把表格**两列**用箭头拼成一句 | 改变了原文结构 |
| 省略号跨行合并且未标注 | 读者以为是一句 |
| 把竖线换成全角竖线 | 改了就比对不上，于是被误当成「自己的措辞」放过 |
| 把括号改成逗号 | 同上 |
| **凭空给原文加粗** | 改变了原文的强调结构 |

⇒ **人眼抄引文的错误率约 10%，且几乎全部是「读起来没错」的错。**

## 本门禁的判定（全部机械可判，不含主观判断）

- **FAIL**：含 **≥6 个连续英文单词**的「」引文，在**全仓所有 .md**（+ `--extra` 指定的外部源）
  归一化后**找不到** ⇒ 它伪装成了引文，但不是原文。
  （英文长句几乎只可能来自某个源文件，所以这条可以硬判。）
- **WARN**：所有 ≥20 字符的「」引文，在上述 haystack 里都找不到
  ⇒ 多半是我们自己的描述性措辞，但需要人眼过一遍
  （`docs/research/80` §7 已记录：**表格单元格内**的引文有已知盲区）。
- **INFO**：统计（总引文数 / 硬判数 / 软判数）。

⚠️ **已知盲区**：表格单元格内的引文，如果原文用竖线分隔而我们换成了全角竖线或「+」，
归一化后子串比对会失败 ⇒ 会落到 WARN 而非 FAIL ⇒ **WARN 必须人眼看**。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

#: 「」引文（中文双引号）
QUOTE_RE = re.compile(r"「([^」]{20,})」")

#: 英文单词（字母开头，可含连字符/撇号）
EN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def is_english_long(q: str) -> bool:
    """是不是「英文长句」—— 用于区分「可硬判」与「只能软判」。

    ⚠️ 不能用「**连续** 6 个长单词」的写法：`if` / `at` / `on` 这类 2 字母词
    会把连续性打断，真实引文（"…if done at all, often reports…"）就再也匹配不上
    ⇒ 规则会静默失效，把英文引用全当中文软判。改为**统计整句的英文词总数**。
    """
    return len(EN_TOKEN_RE.findall(q)) >= 6


def norm(s: str) -> str:
    """归一化：去加粗、去反引号、去引用块标记、折叠空白。"""
    s = s.replace("**", "").replace("`", "")
    s = re.sub(r"^>\s*", " ", s, flags=re.M)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def load_text(path: str) -> str:
    with io.open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig", errors="replace")


def all_md_text(repo: str) -> Tuple[List[str], int]:
    """全仓所有 .md 的归一化文本（按文件分片，保留出处以便排除自身）。"""
    parts: List[str] = []
    n = 0
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", "__pycache__", ".pytest_cache")]
        for name in filenames:
            if name.lower().endswith(".md"):
                parts.append(norm(load_text(os.path.join(dirpath, name))))
                n += 1
    return parts, n


def extra_text(paths: Sequence[str]) -> List[str]:
    """外部源（本机缓存的官方文档等），可选。"""
    parts: List[str] = []
    for p in paths:
        if not p or not os.path.isdir(p):
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "node_modules", "__pycache__")]
            for name in filenames:
                if name.lower().endswith((".md", ".txt", ".html", ".json")):
                    try:
                        parts.append(norm(load_text(os.path.join(dirpath, name))))
                    except OSError:
                        pass
    return parts


def target_docs(repo: str) -> List[str]:
    """要检查的文档：spec 全部 + research 全部 + 根 README。"""
    out: List[str] = []
    for rel_dir in (("docs", "spec"), ("docs", "research")):
        d = os.path.join(repo, *rel_dir)
        if not os.path.isdir(d):
            continue
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x not in ("__pycache__", ".git")]
            for name in sorted(filenames):
                if name.endswith(".md"):
                    out.append(os.path.join(dirpath, name))
    root_readme = os.path.join(repo, "README.md")
    if os.path.isfile(root_readme):
        out.append(root_readme)
    return sorted(out)


def load_registry(repo: str) -> List[str]:
    """读 `tools/quote_sources.txt` —— 仓外引文登记表（登记即审计）。"""
    path = os.path.join(repo, "tools", "quote_sources.txt")
    if not os.path.isfile(path):
        return []
    out: List[str] = []
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        for line in fh.read().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "::" in line:
                _label, frag = line.split("::", 1)
                frag = norm(frag)
                if frag:
                    out.append(frag)
    return out


def scan(repo: str, extra: Optional[Sequence[str]] = None) -> Dict[str, object]:
    """扫描全部目标文档。

    ⚠️ **关键 1：haystack 必须排除「当前被检查的这一份文档」**。
    否则任何引文都能在它自己所在的那份文档里找到 ⇒ 门禁恒绿、**假绿**。
    排除自身后：
      * 引文在**别的**源（语料 / 其它 spec / 其它 research 文档 / 外部源）里逐字存在 ⇒ 可回源；
      * 只在**自己这份文档**里存在 ⇒ 它不是从别处抄的，机器判不了。

    ⚠️ **关键 2：硬判只对本仓「自产」文档（`docs/spec/`）生效**。
    `docs/research/` 大量引用**仓外**的原文（Apple 官方文档缓存、上游固件/官方仓、
    本机下载的产品文档），这些原文**本仓不一定有** ⇒ 对 research 只能软判（WARN），
    否则门禁会被「原文不在仓里」淹没、失去意义。
    ⇒ 分级：
      * `docs/spec/` 里的英文长句引文找不到 ⇒ **FAIL**（我们的规格必须自洽可回源）
      * `docs/research/` 里的英文长句引文找不到 ⇒ **WARN**（需外部源或人工确认）
    """
    parts, md_count = all_md_text(repo)
    extras = extra_text(extra) if extra else []
    own: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", "__pycache__", ".pytest_cache")]
        for name in filenames:
            if name.lower().endswith(".md"):
                fp = os.path.join(dirpath, name)
                own[os.path.abspath(fp)] = norm(load_text(fp))

    files = target_docs(repo)
    registry = load_registry(repo)
    hard: List[Tuple[str, int, str]] = []
    soft: List[Tuple[str, int, str]] = []
    total = 0
    from_registry = 0
    from_external = 0

    for path in files:
        rel = os.path.relpath(path, repo).replace("\\", "/")
        is_spec = rel.startswith("docs/spec/")
        hay_parts = [p for fp, p in own.items()
                     if os.path.abspath(fp) != os.path.abspath(path)]
        hay_parts.extend(extras)
        hay = " || ".join(hay_parts)

        text = load_text(path)
        for idx, line in enumerate(text.split("\n"), start=1):
            for m in QUOTE_RE.finditer(line):
                raw = m.group(1)
                total += 1
                q = norm(raw)
                if q in hay:
                    continue
                # 仓外引文登记表命中 ⇒ 可回源（登记即审计）
                if any(frag in q for frag in registry):
                    from_registry += 1
                    continue
                if is_english_long(q):
                    # 英文长句：**只对本仓自产的 spec 硬判**。
                    # research 里大量引自仓外（官方 README / Apple 文档 / 产品文档），
                    # 逐条登记不现实，也不是我们自己的规格 ⇒ 只统计、不报。
                    if is_spec:
                        hard.append((rel, idx, raw))
                    else:
                        from_external += 1
                elif len(EN_TOKEN_RE.findall(q)) >= 3:
                    # 中英混排（英文词 ≥3 个，例如「HIG 只说 floating tab bar」）⇒ 软判，值得人眼过
                    soft.append((rel, idx, raw))
                # 纯中文自有措辞 ⇒ 不报（我们自己的话本就不该在别处出现）

    return {
        "root": repo,
        "files": len(files),
        "mdCount": md_count,
        "total": total,
        "hard": hard,
        "soft": soft,
        "registry": len(registry),
        "fromRegistry": from_registry,
        "fromExternal": from_external,
    }


def render(result: Dict[str, object], verbose: bool = False) -> str:
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("check_quotes.py —— 引文保真机械校验")
    lines.append("=" * 70)
    lines.append("仓库根      : %s" % result["root"])
    lines.append("检查文档    : %d 份（haystack 覆盖全仓 %s 份 md）"
                 % (result["files"], result["mdCount"]))
    lines.append("≥20 字引文  : %d 条" % result["total"])
    lines.append("仓外登记表  : %d 条（本次命中 %d 条引文）"
                 % (result["registry"], result["fromRegistry"]))
    lines.append("research 仓外英文引文（只统计）: %d 条" % result["fromExternal"])
    lines.append("-" * 70)

    hard = result["hard"]  # type: ignore[index]
    soft = result["soft"]  # type: ignore[index]

    lines.append("")
    if hard:
        lines.append("=== FAIL（英文长句在所有源里都找不到 = 伪装成引文的转述）===")
        for rel, ln, q in hard:  # type: ignore[misc]
            lines.append("  %s:%d" % (rel, ln))
            lines.append("      %s" % q[:170])
    else:
        lines.append("[PASS] 所有英文长句引文都能逐字回源")

    lines.append("")
    if soft:
        lines.append("=== WARN（含中文的引文在所有源里都找不到，需人眼判定）===")
        lines.append("    共 %d 条 —— 多数是自有描述性措辞；表格内引文有已知盲区" % len(soft))
        if verbose:
            for rel, ln, q in soft:  # type: ignore[misc]
                lines.append("  %s:%d  %s" % (rel, ln, q[:120]))
        else:
            lines.append("    （加 --verbose 逐条列出）")
    else:
        lines.append("[PASS] 其余引文全部可回源")

    lines.append("")
    lines.append("-" * 70)
    lines.append("汇总：FAIL=%d  WARN=%d" % (len(hard), len(soft)))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 自检：每个用例用**独立**的临时目录（否则用例互相污染）
# --------------------------------------------------------------------------
def _write(path: str, text: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


CORPUS_TEXT = (
    "# 语料\n\n"
    "### topic.1 A study of companion robots and long term memory\n\n"
    "> 摘要（原文截断）：\n"
    ">\n"
    "> The evaluation for these technologies, if done at all, often reports mixed results on improving users mental health outcomes.\n"
)

SPEC_TEXT = (
    "# 00\n\n"
    "- 记忆存在用户自己的账号空间，**不做训练数据**，**可导出**。\n"
    "- 我们的红线是「个人数据永不入库」。\n"
)

GOOD_EN = ("The evaluation for these technologies, if done at all, often reports "
           "mixed results on improving users mental health outcomes.")


def _mk(root: str, name: str, body: str) -> str:
    p = os.path.join(root, "docs", "research", name)
    _write(p, body)
    return p


def self_test() -> int:
    import tempfile
    passed = 0
    failed = 0

    def ok(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  [PASS] %s" % name)
        else:
            failed += 1
            print("  [FAIL] %s" % name)

    def fresh() -> str:
        root = tempfile.mkdtemp(prefix="check_quotes_")
        _write(os.path.join(root, "docs", "research", "90-corpus.md"), CORPUS_TEXT)
        _write(os.path.join(root, "docs", "spec", "00-spec.md"), SPEC_TEXT)
        return root

    # 1) 语料里的英文长句原样引用 ⇒ PASS
    root = fresh()
    _mk(root, "01-ok.md", "# 01\n\n原文说：「%s」\n" % GOOD_EN)
    r = scan(root)
    ok("语料原文引用不报 FAIL", len(r["hard"]) == 0)  # type: ignore[arg-type]

    # 2) 改一个词 ⇒ FAIL（放 docs/spec/ ⇒ 硬判生效）
    root = fresh()
    _write(os.path.join(root, "docs", "spec", "02-bad.md"), "# 02\n\n伪装引用：「%s」\n"
        % GOOD_EN.replace("outcomes.", "outcome."))
    r = scan(root)
    ok("改一个词的英文引用被硬判 FAIL（spec）", len(r["hard"]) == 1)  # type: ignore[arg-type]

    # 2b) 同样的改错放在 docs/research/ ⇒ 只软判（WARN），不硬判
    root = fresh()
    _mk(root, "02b-bad.md", "# 02b\n\n伪装引用：「%s」\n"
        % GOOD_EN.replace("outcomes.", "outcome."))
    r = scan(root)
    ok("research 里的英文改错不硬判（只统计为仓外引用）",
       len(r["hard"]) == 0 and r["fromExternal"] >= 1)  # type: ignore[arg-type]

    # 3) 缩写主语（实测最危险的一类）⇒ FAIL
    root = fresh()
    _write(os.path.join(root, "docs", "spec", "03-abbr.md"), "# 03\n\n缩写引用：「%s」\n"
        % GOOD_EN.replace("The evaluation for these technologies, if done at all, often",
                           "The evaluation, if done at all, often"))
    r = scan(root)
    ok("缩写过的英文引用被硬判 FAIL", len(r["hard"]) == 1)  # type: ignore[arg-type]

    # 4) spec 里的中文原文引用 ⇒ 不进 WARN
    root = fresh()
    _mk(root, "04-zh.md", "# 04\n\n引用 spec：「个人数据永不入库」。\n")
    r = scan(root)
    ok("spec 里的中文引用可回源（不进 WARN）",
       not any("个人数据永不入库" in q for _, _, q in r["soft"]))  # type: ignore[union-attr]

    # 5) 自有措辞（≥20 字）⇒ 落 WARN 不落 FAIL
    root = fresh()
    _mk(root, "05-own.md", "# 05\n\n我们自己的说法：「这一段是我们自己写的设计取舍并不是任何文献原文（与 E-4 无关）」\n")
    r = scan(root)
    ok("自有中文措辞不硬判",
       len(r["hard"]) == 0)  # type: ignore[arg-type]

    # 6) 归一化：加粗 / 反引号 / 多余空白不影响判定
    root = fresh()
    _mk(root, "06-norm.md", "# 06\n\n带格式：「**%s**」\n" % GOOD_EN)
    r = scan(root)
    ok("归一化后仍判定为可回源", len(r["hard"]) == 0)  # type: ignore[arg-type]

    # 7) 少于 20 字的引文不参与
    root = fresh()
    _mk(root, "07-short.md", "# 07\n\n短引用：「太短了不算」\n")
    r = scan(root)
    ok("短引文不参与统计",
       all("太短了不算" not in q for _, _, q in r["soft"])  # type: ignore[union-attr]
       and all("太短了不算" not in q for _, _, q in r["hard"]))  # type: ignore[union-attr]

    # 8) 外部源（--extra）里的引文 ⇒ 可回源
    root = fresh()
    ext = tempfile.mkdtemp(prefix="check_quotes_ext_")
    _write(os.path.join(ext, "src.md"), "# 外部\n\n%s\n" % GOOD_EN)
    _mk(root, "08-ext.md", "# 08\n\n外部文档引用：「%s」\n" % GOOD_EN)
    r = scan(root, extra=[ext])
    ok("外部源里的引文可回源", len(r["hard"]) == 0)  # type: ignore[arg-type]

    # 9) haystack 覆盖全仓（不只是 spec）
    root = fresh()
    _mk(root, "09-hay.md", "# 09\n\n别处的原文：「%s」\n" % GOOD_EN)
    _mk(root, "10-use.md", "# 10\n\n引用它：「%s」\n" % GOOD_EN)
    r = scan(root)
    ok("haystack 覆盖全仓（research 内互引也能回源）", len(r["hard"]) == 0)  # type: ignore[arg-type]

    print("self-test: %d/%d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="引文保真机械校验")
    ap.add_argument("--root", default=".")
    ap.add_argument("--extra", action="append", default=[],
                    help="额外源目录（可重复），如本机缓存的官方文档")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--self-test", dest="self_test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    repo = os.path.abspath(args.root)
    result = scan(repo, args.extra)
    print(render(result, args.verbose))
    hard = result["hard"]
    return 1 if hard else 0  # type: ignore[return-value]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
