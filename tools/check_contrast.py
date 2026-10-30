#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_contrast.py —— 对比度实算器（WCAG 2.x 相对亮度公式）

为什么需要单独一个脚本
--------------------
本项目对「强调色能不能当正文色用」「深色方案在浅色系统外观下能不能用」
这类问题，**必须给数字**，不能靠眼睛看。本脚本：

1. 从 `prototype/variants/*.html` 的 CSS 变量里**直接读取真实色值**（不手抄）；
2. 按 WCAG 相对亮度公式实算对比度；
3. 按 HIG 的三档阈值判定：
   - 正文文字 ≥ **4.5:1**
   - 大字（≥ 18pt 或 ≥ 14pt 粗体）≥ **3:1**
   - 非文本元素（图标、边框、分隔线）≥ **3:1**
4. 输出机器可读结果（可被 CI 门禁引用）。

出处等级：**T4 自研实算** —— 算法是 WCAG 公开公式（可引 T1 的 HIG 阈值），
但「哪个色配哪个底」是本项目的选择，不是官方规定。

用法
----
    py -3.12 tools/check_contrast.py                 # 跑全部方案
    py -3.12 tools/check_contrast.py --json          # 机器可读
    py -3.12 tools/check_contrast.py --self-test     # 离线自检

退出码：0 = 没有低于阈值的**已知违规**；1 = 有违规。
⚠️ 注意：`--strict` 会把「条件性通过」（如强调色只用于大字）也判为违规。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

__version__ = "1.0.0"

# HIG accessibility.md:60-62（T1）
THRESHOLD_BODY = 4.5      # 正文
THRESHOLD_LARGE = 3.0     # 大字 / 非文本

# 需要检查的配色对（前景, 背景, 用途, 阈值）
# 用途决定用哪档阈值：body=正文，large=大字，nontext=非文本
PAIRS = [
    ("text", "bg", "body", "正文 / 背景"),
    ("text", "surface", "body", "正文 / 卡片"),
    ("accent", "bg", "body", "强调色 / 背景（正文级）"),
    ("on-accent", "accent", "body", "强调色上的文字"),
    ("accent", "surface", "nontext", "强调色 / 卡片（图标级）"),
    ("text", "surface2", "body", "正文 / 次级面"),
    ("text2", "bg", "body", "次级文字 / 背景"),
]

# 已知「条件性通过」：色值在正文级不合格，但**设计上只用于大字/图标**
CONDITIONAL_OK = {
    ("paperTerracotta", "accent", "bg"): "强调色 #AF4C37 浅底 ≈4.3:1，"
                                         "只可用于粗体/大字号与图标",
    ("paperTerracotta", "accent", "surface"): "同上（卡片底更亮，比值更低）",
}


def _hex_to_rgb(value: str):
    """'#AF4C37' / '#AF4' → (r,g,b) 0..255。解析失败返回 None。"""
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        return None
    try:
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        return None


def _relative_luminance(rgb) -> float:
    """WCAG 2.x 相对亮度。"""
    def chan(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str):
    """返回 (比值, None) 或 (None, 原因)。"""
    f = _hex_to_rgb(fg)
    b = _hex_to_rgb(bg)
    if f is None:
        return None, "前景色无法解析：%r" % fg
    if b is None:
        return None, "背景色无法解析：%r" % bg
    lf = _relative_luminance(f)
    lb = _relative_luminance(b)
    lighter, darker = max(lf, lb), min(lf, lb)
    return (lighter + 0.05) / (darker + 0.05), None


# ---------------------------------------------------------------------------
# 从 HTML 读色值
# ---------------------------------------------------------------------------

_CSS_VAR_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*(#[0-9A-Fa-f]{3,8})\s*;")


def read_css_vars(path: str) -> dict:
    """从一个 HTML 文件里读出所有 `--name: #hex;` 定义。

    取**第一次**出现（`:root` 里的基础值）—— 方案覆盖值（`html[data-scheme=...]`）
    会是同一文件里的第二份，基础值才是「这个方案的主色板」。
    """
    with io.open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    out = {}
    for m in _CSS_VAR_RE.finditer(text):
        name = m.group(1)
        if name not in out:      # 先到先得 = :root 的基础值
            out[name] = m.group(2).upper()
    return out


def discover_variants(root: str) -> list:
    """找出 4 个方案原型文件。"""
    d = os.path.join(root, "prototype", "variants")
    names = [
        ("paperTerracotta", "01-paper-terracotta.html"),
        ("pureWhiteBlank", "03-pure-white-blank.html"),
        ("warmPaperSerif", "17-warm-paper-serif.html"),
        ("tuckDarkCalm", "18-tuck-dark-calm.html"),
    ]
    out = []
    for key, fname in names:
        p = os.path.join(d, fname)
        if os.path.exists(p):
            out.append((key, p))
    return out


# ---------------------------------------------------------------------------
# 计算
# ---------------------------------------------------------------------------

def evaluate(root: str) -> dict:
    results = {}
    for key, path in discover_variants(root):
        vars_ = read_css_vars(path)
        pairs = []
        for fg_name, bg_name, kind, label in PAIRS:
            fg = vars_.get("--" + fg_name)
            bg = vars_.get("--" + bg_name)
            if not fg or not bg:
                pairs.append({
                    "fg": fg, "bg": bg, "kind": kind, "label": label,
                    "ratio": None, "verdict": "SKIP",
                    "note": "该方案未定义 --%s 或 --%s" % (fg_name, bg_name),
                })
                continue
            ratio, err = contrast_ratio(fg, bg)
            if err:
                pairs.append({"fg": fg, "bg": bg, "kind": kind, "label": label,
                              "ratio": None, "verdict": "SKIP", "note": err})
                continue
            th = THRESHOLD_BODY if kind == "body" else THRESHOLD_LARGE
            verdict = "PASS" if ratio >= th else "FAIL"
            note = ""
            if verdict == "FAIL":
                cond = CONDITIONAL_OK.get((key, fg_name, bg_name))
                if cond:
                    verdict = "CONDITIONAL"
                    note = cond
            pairs.append({
                "fg": fg, "bg": bg, "kind": kind, "label": label,
                "ratio": round(ratio, 2), "threshold": th,
                "verdict": verdict, "note": note,
            })
        results[key] = {
            "file": os.path.relpath(path, root).replace(os.sep, "/"),
            "vars": vars_,
            "pairs": pairs,
        }
    return results


def summarize(results: dict) -> dict:
    fail = cond = pass_ = skip = 0
    for res in results.values():
        for p in res["pairs"]:
            v = p["verdict"]
            if v == "FAIL":
                fail += 1
            elif v == "CONDITIONAL":
                cond += 1
            elif v == "PASS":
                pass_ += 1
            else:
                skip += 1
    return {"fail": fail, "conditional": cond, "pass": pass_, "skip": skip}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def self_test() -> int:
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # WCAG 已知答案：黑对白 = 21:1
    r, err = contrast_ratio("#000000", "#FFFFFF")
    ok("黑对白 = 21:1", err is None and abs(r - 21.0) < 0.01, "%s %s" % (r, err))
    r, _ = contrast_ratio("#FFFFFF", "#000000")
    ok("对比度对称", abs(r - 21.0) < 0.01, str(r))

    # 白对白 = 1:1
    r, _ = contrast_ratio("#FFFFFF", "#FFFFFF")
    ok("同色 = 1:1", abs(r - 1.0) < 0.0001, str(r))

    # #767676 对 #FFFFFF ≈ 4.54（WCAG 常用边界样例）
    r, _ = contrast_ratio("#767676", "#FFFFFF")
    ok("#767676/白 ≈ 4.54（正文阈值边界）", abs(r - 4.54) < 0.03, str(r))

    # #777777 对白 ≈ 4.48（略低于 4.5）
    r, _ = contrast_ratio("#777777", "#FFFFFF")
    ok("#777777/白 < 4.5（低于正文阈值）", r < 4.5, str(r))

    # 十六进制解析
    ok("三位hex展开", _hex_to_rgb("#AF4C37") == (0xAF, 0x4C, 0x37))
    ok("三位简写展开", _hex_to_rgb("#ABC") == (0xAA, 0xBB, 0xCC))
    ok("非法输入返回 None", _hex_to_rgb("nope") is None)
    ok("长度不对返回 None", _hex_to_rgb("#12345") is None)

    # 相对亮度：纯白 = 1.0，纯黑 = 0.0
    ok("白亮度 = 1.0", abs(_relative_luminance((255, 255, 255)) - 1.0) < 1e-9)
    ok("黑亮度 = 0.0", abs(_relative_luminance((0, 0, 0))) < 1e-9)

    # CSS 变量读取（用临时文件）
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "_cc_test_vars.html")
    with io.open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(":root{--bg:#FAF8F5;--accent:#AF4C37;}\n"
                 "html[data-scheme=x]{--bg:#000000;}\n")
    v = read_css_vars(tmp)
    ok("读到 CSS 变量", v.get("--bg") == "#FAF8F5", str(v))
    ok("取 :root 基础值（非覆盖值）", v.get("--bg") == "#FAF8F5", str(v.get("--bg")))
    ok("读到 accent", v.get("--accent") == "#AF4C37")
    try:
        os.remove(tmp)
    except OSError:
        pass

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="4 套视觉方案的对比度实算")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="条件性通过也算违规")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    root = os.path.abspath(args.root)
    results = evaluate(root)
    if not results:
        print("未找到任何方案原型（prototype/variants/）")
        return 1

    summary = summarize(results)

    if args.json:
        print(json.dumps({"results": results, "summary": summary},
                         ensure_ascii=False, indent=2))
    else:
        for key, res in results.items():
            print("\n=== %s  (%s) ===" % (key, res["file"]))
            print("%-28s %-9s %-9s %-8s %-11s %s" %
                  ("配色对", "前景", "背景", "比值", "判定", "备注"))
            for p in res["pairs"]:
                ratio = ("%.2f" % p["ratio"]) if p.get("ratio") is not None else "-"
                thr = p.get("threshold", "-")
                print("%-28s %-9s %-9s %-8s %-11s %s" % (
                    p["label"], p.get("fg") or "-", p.get("bg") or "-",
                    ratio, p["verdict"], p.get("note", "")))
        print("\n汇总：PASS %d / CONDITIONAL %d / FAIL %d / SKIP %d" % (
            summary["pass"], summary["conditional"], summary["fail"], summary["skip"]))

    if summary["fail"]:
        return 1
    if args.strict and summary["conditional"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
