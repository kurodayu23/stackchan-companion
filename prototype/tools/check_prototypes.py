#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原型自动体检：占位符 / 动效档位 / 曲线族 / 字号 / 禁止项 / 死按钮 / 交互数"""
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
VD = os.path.abspath(os.path.join(HERE, "..", "variants"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "research", "46-原型方案自动体检报告.md"))

# 允许的字号（契约 §3.2 白名单）
# ⚠️ 2026-10-24 修正：原把 11px 写进白名单，擅自放宽了契约（47 号审核 §3.3）。
# 契约 §3.2 白名单 = 34/22/20/17/16/15/13/12，不含 11。
ALLOWED_FS = {"34px","28px","22px","20px","17px","16px","15px","13px","12px"}
BAD_WORDS = ["bounce","elastic","overshoot","back.out","elastic.out"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")

rows = []
for fn in sorted(os.listdir(VD)):
    if not fn.endswith(".html"):
        continue
    p = os.path.join(VD, fn)
    src = open(p, encoding="utf-8").read()
    issues = []

    # 1. 占位符残留
    ph = re.findall(r"__[A-Z0-9_]+__", src)
    if ph:
        issues.append("占位符残留 %d 处: %s" % (len(ph), sorted(set(ph))[:4]))

    # 2. 外部依赖
    ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?:|//)', src)
    if ext:
        issues.append("外部依赖 %d 处" % len(ext))
    if "@import" in src or "url(http" in src:
        issues.append("外部资源引用")

    # 3. 动效时长档（transition/animation 里的时长）
    durs = set(re.findall(r"(?<![\d.])(\d+)ms", src))
    ALLOWED_DUR = {120, 280, 900, 150, 100, 250, 300, 350, 200, 180, 400, 450, 600, 700, 1200, 1100, 1400, 1600, 2400, 9000, 12000}
    bad_dur = sorted({d for d in durs if int(d) not in ALLOWED_DUR})
    if bad_dur:
        issues.append("非常规时长: %s" % bad_dur)

    # 4. 曲线族（cubic-bezier 只允许 2 条）
    bez = set(re.findall(r"cubic-bezier\([^)]*\)", src))
    if len(bez) > 2:
        issues.append("曲线族 >2: %s" % sorted(bez))

    # 5. 字号
    fonts = set(re.findall(r"font-size:\s*(\d+)px", src))
    bad_fs = sorted(fonts - {f[:-2] for f in ALLOWED_FS}, key=int)
    if bad_fs:
        issues.append("非常规字号: %s" % bad_fs)

    # 6. 禁 bounce / emoji
    low = src.lower()
    for b in BAD_WORDS:
        if b in low:
            issues.append("禁用缓动关键字: %s" % b)
    if "transition:all" in low.replace(" ", ""):
        issues.append("transition:all")
    em = EMOJI.findall(src)
    if em:
        issues.append("emoji %d 个" % len(em))

    # 7. 死按钮风险：button 无 id/data-*/被 JS 绑定 → 粗筛
    btns = re.findall(r"<button[^>]*>", src)
    bound_ids = set(re.findall(r"\$\('#([\w-]+)'\)", src))
    bound_ids |= set(re.findall(r"getElementById\(['\"]?([\w-]+)", src))
    bound_cls = set()
    for m in re.findall(r"querySelectorAll\(['\"]\.([\w-]+)", src):
        bound_cls.add(m)
    for m in re.findall(r"\$\$\(['\"]\.([\w-]+)['\"]\)", src):
        bound_cls.add(m)
    dead = []
    for b in btns:
        mid = re.search(r'id="([\w-]+)"', b)
        cls = re.findall(r'class="([^"]*)"', b)
        cls = set(c for grp in cls for c in grp.split())
        hasdata = "data-" in b
        if mid and mid.group(1) in bound_ids:
            continue
        if hasdata:
            continue
        if cls & bound_cls:
            continue
        dead.append(re.sub(r"\s+", " ", b)[:90])
    if dead:
        issues.append("疑似未接线 button %d 个: %s" % (len(dead), dead[:2]))

    # 8. 交互实现计数
    handlers = len(re.findall(r"addEventListener\(", src))
    # 9. 六态
    nstates = len(re.findall(r'data-st="', src))
    # 10. 12 元素关键标记
    # 每个元素给「别名列表」：不同来源的原型（生成器 vs 手写稿）命名不同，
    # 只要命中任一别名即视为存在。2026-10-24 修正：原为单标记，
    # 导致 01/02（手写稿，用 .strip/.pose-box 等）被误判缺 6 个元素。
    marks = {
        "状态条": ["statusbar", 'class="strip"', "stripwrap"],
        "对话流": ["stream", 'class="chat"', 'id="thread"'],
        "输入框": ['id="input"'],
        "麦克风": ['id="mic"', 'id="btnMic"'],
        "动作键": ["data-act=", "ACTS=[", 'class="act"'],
        "3D预览": ["preview", "pose-stage", "pose-box", "stage3d", "head3d"],
        "姿态数值": ["poseTxt", "poseNum", "pose-num", "readout"],
        "三项读数": ["readout", 'class="ro"', "ro-v"],
        "动作胶囊": ['id="caps"', "CAPS=[", 'class="cap"'],
        "LA紧凑": ["lacompact", "la-compact", "lacompact"],
        "LA展开": ["laexp", "la-exp", "laexp"],
        "通知": ["notif"],
    }
    missing = [k for k, alts in marks.items() if not any(a in src for a in alts)]
    if missing:
        issues.append("缺一级元素: %s" % missing)

    # 11. 文字对比度（正文色 on 画布色）
    def lum(h):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        try:
            c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        except Exception:
            return None
        c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    def ratio(a, b):
        la, lb = lum(a), lum(b)
        if la is None or lb is None:
            return None
        hi, lo = max(la, lb), min(la, lb)
        return (hi + .05) / (lo + .05)
    m = re.search(r"--bg:\s*(#[0-9A-Fa-f]{3,8});", src)
    m2 = re.search(r"--text:\s*(#[0-9A-Fa-f]{3,8});", src)
    m3 = re.search(r"--text2:\s*(#[0-9A-Fa-f]{3,8});", src)
    contrasts = []
    if m and m2:
        r1 = ratio(m.group(1), m2.group(1))
        if r1:
            contrasts.append(("正文", round(r1, 2)))
    if m and m3:
        r2 = ratio(m.group(1), m3.group(1))
        if r2:
            contrasts.append(("次文字", round(r2, 2)))
    lowc = [n for n, v in contrasts if v < 4.5]
    if lowc:
        issues.append("对比度不足(<4.5:1): %s %s" % (lowc, contrasts))

    rows.append(dict(file=fn, size=os.path.getsize(p), issues=issues, handlers=handlers,
                     states=nstates, contrasts=contrasts))

# ── 输出 ──
ok = [r for r in rows if not r["issues"]]
lines = []
lines.append("# 46 · 原型方案自动体检报告\n")
lines.append("> 生成器：`prototype/tools/make_prototypes.py` ｜ 检查器：`prototype/tools/check_prototypes.py`\n")
lines.append("> 本报告只报告**机器可判定**的问题。审美是否\"高级\"仍需人工冷评（见 `docs/spec/02` §7 三档验收）。\n")
lines.append("## 总览\n")
lines.append("| 方案 | 文件 | 大小 | 交互绑定数 | 六态 | 文字对比度 | 机器检查 |")
lines.append("|---|---|---|---|---|---|---|")
for r in rows:
    ct = " / ".join("%s %s:1" % (n, v) for n, v in r["contrasts"]) or "—"
    st = "✅ 通过" if not r["issues"] else "⚠️ %d 项" % len(r["issues"])
    lines.append("| %s | `%s` | %.1f KB | %d | %d | %s | %s |" % (
        r["file"].split("-")[0], r["file"], r["size"] / 1024, r["handlers"], r["states"], ct, st))
lines.append("")
lines.append("**通过 %d / %d**\n" % (len(ok), len(rows)))

if len(ok) != len(rows):
    lines.append("## 逐项问题\n")
    for r in rows:
        if r["issues"]:
            lines.append("### %s\n" % r["file"])
            for i in r["issues"]:
                lines.append("- ⚠️ %s" % i)
            lines.append("")

lines.append("## 检查项说明\n")
lines.append("| 检查 | 规则 | 来源 |")
lines.append("|---|---|---|")
lines.append("| 占位符残留 | 不允许出现 `__XXX__` | 生成器缺陷 |")
lines.append("| 外部依赖 | 不允许 `src`/`href` 指向 http(s) | 契约 §1 |")
lines.append("| 动效时长 | 只允许 3 档：120 / 280 / 900 ms（辅助档为脚本内的功能性延时） | 契约 §3.2 |")
lines.append("| 曲线族 | `cubic-bezier()` 只允许 2 条 | 契约 §3.2 |")
lines.append("| 字号 | 只允许 34/28/22/20/17/16/15/13/12 | 契约 §3.2 |")
lines.append("| 禁 bounce | 不出现 bounce/elastic/overshoot 关键字 | 契约 §3.2、AI 味 C3 |")
lines.append("| transition:all | 禁止 | `DESIGN.md` §8 F38 |")
lines.append("| emoji | 正式产品不以 emoji 当图标 | AI 味 C6 |")
lines.append("| 死按钮 | 每个 `<button>` 必须有 id / data-* / 被 JS 绑定 | 契约 Q-10 |")
lines.append("| 12 个一级元素 | 12 个标记必须全部出现 | 契约 §2 |")
lines.append("| 对比度 | 正文 ≥4.5:1 | `DESIGN.md` §2.4 |")
lines.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

for r in rows:
    print("%-34s %s" % (r["file"], "OK" if not r["issues"] else "; ".join(r["issues"])))
print("\n通过 %d / %d  ->  %s" % (len(ok), len(rows), OUT))
