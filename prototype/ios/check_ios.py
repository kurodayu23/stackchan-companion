#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iOS 原生感机器判定器。

解决的问题：用户判定「之前那 20 个原型太安卓味，不像 iOS App」。
**「像不像」不该靠眼睛吵架** ⇒ 把它变成可复现的检查。

判定分四类：

* **IOS_FEATURE** —— iOS 原生特征必须齐全（缺一个就 FAIL）
* **ANDROID_SMELL** —— Android 味必须**零命中**
* **IOS_VALUE** —— 关键数值与出处对账（**每条标注出处等级 T1/T4**）
* **IOS_T1** —— **Apple 官方明文数值**硬指标（T1，须带出处）

⚠️ 出处等级（详见 `docs/spec/08-iOS官方规范事实层.md` §一）：

* **T1** = Apple 官方文档正文**明文写出**的数值（可当官方引用）
* **T4** = **本项目自研设定**（HIG 正文根本没给这个数值）

本轮核对结论：**9 条登记数值里 8 条是 T4 自研、1 条是 T1 但我们用错了版本**（systemBlue）。
⇒ 登记表不许再写「HIG：xxx」这种假出处。

用法::

    py -3.12 prototype/ios/check_ios.py            # 判定真实文件
    py -3.12 prototype/ios/check_ios.py --self-test # 自检（用故意做坏的夹具）

退出码：0 = 全过；1 = 有 FAIL；2 = 用法错误
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

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = ("ios-light.html", "ios-dark.html")
VARIANTS = {"ios-light.html": "light", "ios-dark.html": "dark"}


# ══════════════════════════════════════════════════════════════════════════
# 1. iOS 特征清单（缺一即 FAIL）
#    每条：key → (说明, 判定函数(html) -> bool)
# ══════════════════════════════════════════════════════════════════════════

def _has(hay: str, *needles: str) -> bool:
    return all(n in hay for n in needles)


IOS_FEATURES = {
    "dynamic_island": (
        "灵动岛（Dynamic Island）",
        lambda h: "island" in h.lower()),
    "status_bar": (
        "状态栏：时间 + 信号 + Wi-Fi + 电池四件套",
        lambda h: re.search(r"class=[\"'][^\"']*status-?bar", h, re.I) is not None
        and _has(h, "i-cellular", "i-wifi", "i-battery")),
    "home_indicator": (
        "Home Indicator（底部横条）",
        lambda h: "home-indicator" in h.lower() or "home_indicator" in h.lower()),
    "tab_bar_glass": (
        "Tab Bar 是毛玻璃材质（backdrop-filter blur + saturate）",
        lambda h: "backdrop-filter" in h and "saturate(180%)" in h.replace(" ", "")),
    "tab_bar_floating": (
        "Tab Bar 是浮动胶囊（左右留边距 + 大圆角），不是通栏",
        lambda h: re.search(r"\.tabbar\s*\{[^}]*left:\s*(\d+)px[^}]*right:\s*(\d+)px", h) is not None
        and re.search(r"\.tabbar\s*\{[^}]*border-radius:\s*(\d+)px", h) is not None),
    "nav_stack": (
        "导航栈（push / pop 存在）",
        lambda h: _has(h, "function push", "function pop")),
    "edge_swipe_back": (
        "边缘右滑返回（pointerdown + 左侧阈值判定）",
        lambda h: "pointerdown" in h and "pointermove" in h
        and re.search(r"clientX\s*-\s*\w+\.left\s*>\s*\d+", h) is not None),
    "large_title_collapse": (
        "大标题 + 滚动收起（large-title + scrolled 改导航栏与小标题）",
        lambda h: ("large-title" in h.lower())
        and ("scrolled" in h.lower())
        and ("nav-title-small" in h or "nav_title_small" in h)),
    "sheet_present": (
        "Sheet 存在（含 grabber 与下滑关闭）",
        lambda h: "sheet" in h.lower() and "grabber" in h.lower()),
    "inset_grouped": (
        "Inset Grouped 列表（组圆角 10~12px + 0.5px 分割线 + 左缩进 16px + 行高 ≥44px）",
        lambda h: re.search(r"--r-group:\s*1[0-2]px", h) is not None
        and (re.search(r"height:\s*0?\.5px", h) is not None
             or re.search(r"border-(?:top|bottom):\s*0?\.5px", h) is not None)
        and re.search(r"left:\s*16px", h) is not None
        and re.search(r"min-height:\s*4[4-9]px|min-height:\s*5[0-2]px", h) is not None),
    "switch_51x31": (
        "开关 51×31pt 胶囊",
        lambda h: re.search(r"width:\s*51px", h) is not None
        and re.search(r"height:\s*31px", h) is not None),
    "chevron_ratio": (
        "chevron.right 比例 8×14",
        lambda h: re.search(r'viewBox="0 0 8 14"', h) is not None),
    "system_colors": (
        "系统语义色（label / secondaryLabel / systemBackground / separator / systemBlue）",
        lambda h: _has(h, "--label", "--secondary-label", "--separator", "--system-blue")),
    "sf_symbols_svg": (
        "SF Symbols 风格内联 SVG（symbol 定义 ≥ 8 个）",
        lambda h: len(re.findall(r"<symbol\s+id=", h)) >= 8),
    "no_emoji_icon": (
        "不以 emoji 当图标",
        lambda h: not re.search(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", h)),
    "press_feedback": (
        "触感反馈的视觉模拟（press 状态，非 ripple）",
        lambda h: "pressed" in h and "scale(" in h),
}


# ══════════════════════════════════════════════════════════════════════════
# 2. Android 味黑名单（命中即 FAIL）
# ══════════════════════════════════════════════════════════════════════════

ANDROID_SMELLS = {
    "smell_ripple": (
        "Material 波纹反馈（ripple / md-ripple）",
        [r"\bripple\b", r"md-ripple", r"material-ripple"]),
    "smell_fab": (
        "FAB 悬浮大按钮",
        [r"floating-action", r"\bfab\b", r"class=[\"'][^\"']*\bfab\b"]),
    "smell_snackbar": (
        "Snackbar / Android Toast",
        [r"snackbar", r"class=[\"'][^\"']*\btoast\b"]),
    "smell_material_font": (
        "Material 图标字体",
        [r"material-symbols", r"material-icons", r"Material Icons"]),
    "smell_elevation": (
        "Material elevation 属性",
        [r"\belevation\s*:"]),
    "smell_android_nav": (
        "Android 药丸式三键导航",
        [r"android-nav", r"nav-pill", r"three-button"]),
    "smell_md_card": (
        "Material 卡片类名（md-card / material-card）",
        [r"\bmd-card\b", r"\bmaterial-card\b"]),
    "smell_transition_all": (
        "transition: all（性能与风格都扣分）",
        [r"transition\s*:\s*all"]),
    "smell_bounce": (
        "bounce / elastic 曲线",
        [r"\bbounce\b", r"\belastic\b", r"overshoot"]),
    "smell_remote_font": (
        "外链字体（http(s) font-src）",
        [r"@font-face[^}]*src:[^;}]*https?://"]),
    "smell_android_color": (
        "Material 主色（#6200ee 等）",
        [r"#6200ee", r"#03dac6", r"#bb86fc"]),
}


# ══════════════════════════════════════════════════════════════════════════
# 3. 关键数值与出处对账
#
#    ⚠️ 每条必须标出处等级（见 `docs/spec/08` §一）：
#       T1 = Apple 官方文档正文明文写出的数值
#       T4 = 本项目自研设定（HIG 正文根本没有这个数值）
#       本轮核对：9 条里 8 条是 T4、1 条是 T1 但用错版本。
# ══════════════════════════════════════════════════════════════════════════

IOS_VALUES = [
    # (说明, 期望正则, 等级, 出处)
    ("Tab Bar 浮动边距 12px",
     r"\.tabbar\s*\{[^}]*left:\s*12px", "T4",
     "自研设定：HIG 只说 floating，未给边距数值（spec/08 §十三）"),
    ("Tab Bar 圆角 26px（连续曲率观感）",
     r"\.tabbar\s*\{[^}]*border-radius:\s*26px", "T4",
     "自研设定：HIG 未给圆角数值（spec/08 §十三）"),
    ("Tab Bar 高 56px",
     r"\.tabbar\s*\{[^}]*height:\s*56px", "T4",
     "自研设定：HIG 的 68pt 是 tvOS，iOS 无此数值（spec/08 §十三）"),
    ("chevron 8×14",
     r'viewBox="0 0 8 14"', "T4",
     "自研设定：照 SF Symbols 描摹；08 号文档自述为像素估算（spec/08 §十二 #4）"),
    ("开关 51×31",
     r"width:\s*51px", "T4",
     "自研设定：HIG toggles.md 未给尺寸（spec/08 §十二 #5）"),
    ("分割线 0.5px",
     r"height:\s*0?\.5px|border-(?:top|bottom):\s*0?\.5px", "T4",
     "自研设定：HIG lists-and-tables.md 未给粗细（spec/08 §十二 #6）"),
    ("列表组圆角 11px",
     r"--r-group:\s*11px", "T4",
     "自研设定：HIG 未给组圆角（spec/08 §十二 #7）"),
    ("Tab 标签字号 10px",
     r"--fs-tab:\s*10px", "T4",
     "自研设定：Tab 标签不是 Dynamic Type 样式，不在官方字号表里（spec/08 §七）"),
]


# ══════════════════════════════════════════════════════════════════════════
# 3b. T1 硬指标（Apple 官方明文数值，出处见 `docs/spec/08`）
#     这三条能进 CI 门禁；T4 的不能。
# ══════════════════════════════════════════════════════════════════════════

def _css_var(html: str, name: str):
    """取 CSS 变量里的 6 位 hex 值（没有就返回 None）。"""
    m = re.search(r"--%s\s*:\s*(#[0-9A-Fa-f]{6})\b" % re.escape(name), html)
    return m.group(1) if m else None


def _rel_lum(hex_color: str) -> float:
    def ch(v: int) -> float:
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r = ch(int(hex_color[1:3], 16))
    g = ch(int(hex_color[3:5], 16))
    b = ch(int(hex_color[5:7], 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    """WCAG 对比度。"""
    l1, l2 = _rel_lum(fg), _rel_lum(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


# (规则 ID, 说明, 出处, 判定函数(html, variant) -> (ok, detail))
IOS_T1_RULES = [
    ("IOS-COL-03",
     "systemBlue 用 iOS 26 官方值（浅 #0088FF / 深 #0091FF）",
     "HIG color.md:225-243（spec/08 §6.3）",
     lambda h, v: (
         (_css_var(h, "system-blue") or "").upper()
         == ("#0088FF" if v == "light" else "#0091FF"),
         "期望 " + ("#0088FF" if v == "light" else "#0091FF")
         + "，实际 " + str(_css_var(h, "system-blue")))),

    ("IOS-A11Y-01",
     "正文对比度 ≥ 4.5:1（label vs systemBackground）",
     "HIG accessibility.md:60（spec/08 §八）",
     lambda h, v: (
         _css_var(h, "label") is not None
         and _css_var(h, "system-background") is not None
         and _contrast(_css_var(h, "label"), _css_var(h, "system-background")) >= 4.5,
         "实测 %.2f:1" % _contrast(
             _css_var(h, "label") or "#000000",
             _css_var(h, "system-background") or "#FFFFFF"))),

    ("IOS-A11Y-03",
     "触控目标 ≥ 44×44pt",
     "HIG accessibility.md:135（spec/08 §八）",
     lambda h, v: (
         re.search(r"min-height:\s*44px", h) is not None,
         "未找到 min-height:44px" if re.search(r"min-height:\s*44px", h) is None
         else "已声明 min-height:44px")),

    ("IOS-TYP-01",
     "正文字号 ≥ 17px（默认 17pt）且 Caption 不低于 11pt",
     "HIG accessibility.md:40（spec/08 §七）",
     lambda h, v: (
         re.search(r"--fs-title:\s*17px", h) is not None
         and re.search(r"--fs-caption:\s*1[1-9]px", h) is not None,
         ("--fs-title=17px、--fs-caption≥11px" if re.search(r"--fs-title:\s*17px", h)
          and re.search(r"--fs-caption:\s*1[1-9]px", h)
          else "--fs-title 或 --fs-caption 不合规"))),

    ("IOS-TYP-02",
     "大标题 34px（Large Title 34pt）",
     "HIG typography.md Large(default) 表（spec/08 §七）",
     lambda h, v: (
         re.search(r"--fs-large-title:\s*34px", h) is not None,
         ("--fs-large-title=34px" if re.search(r"--fs-large-title:\s*34px", h)
          else "--fs-large-title 不是 34px"))),
]


# ══════════════════════════════════════════════════════════════════════════
# 4. 判定
# ══════════════════════════════════════════════════════════════════════════

class Result:
    def __init__(self):
        self.rows = []          # (kind, name, ok, detail)

    def add(self, kind, name, ok, detail=""):
        self.rows.append((kind, name, ok, detail))

    @property
    def fails(self):
        return [r for r in self.rows if not r[2] and r[0] in
                ("IOS_FEATURE", "ANDROID_SMELL", "IOS_VALUE", "IOS_T1")]

    def report(self, title):
        print("=" * 74)
        print(title)
        print("=" * 74)
        groups = {}
        for kind, name, ok, detail in self.rows:
            groups.setdefault(kind, []).append((name, ok, detail))
        for kind, label in (("IOS_FEATURE", "iOS 原生特征（缺一即 FAIL）"),
                            ("ANDROID_SMELL", "Android 味（命中即 FAIL）"),
                            ("IOS_VALUE", "关键数值与出处对账（T4 自研 / T1 官方）"),
                            ("IOS_T1", "T1 官方硬指标（Apple 明文数值）")):
            items = groups.get(kind, [])
            if not items:
                continue
            print("\n【%s】" % label)
            for name, ok, detail in items:
                mark = "PASS" if ok else "FAIL"
                line = "  %s  %s" % (mark, name)
                if detail:
                    line += "  — " + detail
                print(line)
        nf = len(self.fails)
        print("\n汇总：检查 {} 项，FAIL {} 项".format(len(self.rows), nf))
        return nf


def check_file(path: str, res: Result, label: str, variant: str = "light"):
    if not os.path.exists(path):
        res.add("IOS_FEATURE", "文件存在：%s" % label, False, path)
        return
    with io.open(path, encoding="utf-8") as f:
        html = f.read()

    for key, (desc, fn) in IOS_FEATURES.items():
        try:
            ok = bool(fn(html))
            detail = ""
        except Exception as e:  # noqa: BLE001
            ok, detail = False, "判定异常：%s" % (e,)
        res.add("IOS_FEATURE", desc, ok, detail)

    for key, (desc, pats) in ANDROID_SMELLS.items():
        hits = []
        for p in pats:
            for m in re.finditer(p, html, re.I):
                line = html.count("\n", 0, m.start()) + 1
                hits.append("L%d:%s" % (line, m.group(0)[:28]))
        res.add("ANDROID_SMELL", desc, not hits,
                ("命中 " + ", ".join(hits[:4])) if hits else "零命中")

    for desc, pat, tier, src in IOS_VALUES:
        ok = re.search(pat, html) is not None
        res.add("IOS_VALUE", desc, ok,
                ("[%s] %s" % (tier, src)) if ok else ("未匹配：" + pat + "（%s）" % src))

    for rid, desc, src, fn in IOS_T1_RULES:
        try:
            ok, detail = fn(html, variant)
        except Exception as e:  # noqa: BLE001
            ok, detail = False, "判定异常：%s" % (e,)
        res.add("IOS_T1", "%s  %s" % (rid, desc), ok,
                ("%s｜%s" % (src, detail)) if detail else src)


# ══════════════════════════════════════════════════════════════════════════
# 5. 自检（用故意做坏的夹具证明每类都能抓到）
# ══════════════════════════════════════════════════════════════════════════

def self_test() -> int:
    print("=" * 74)
    print("自检：故意做坏的夹具 ⇒ 每类缺陷都必须被抓到")
    print("=" * 74)
    ok = True
    fails = []

    def chk(name, cond, detail=""):
        nonlocal ok
        if cond:
            print("  PASS  {}{}".format(name, ("  (" + detail + ")") if detail else ""))
        else:
            ok = False
            fails.append(name)
            print("  FAIL  {}  {}".format(name, detail))

    good_path = os.path.join(HERE, TARGETS[0])
    if not os.path.exists(good_path):
        print("❌ 找不到真实文件，先跑一次真实判定：", good_path)
        return 2
    with io.open(good_path, encoding="utf-8") as f:
        good = f.read()

    res = Result()
    check_file(good_path, res, TARGETS[0], VARIANTS[TARGETS[0]])
    n_fail = len(res.fails)
    chk("真实文件本身不该有 FAIL", n_fail == 0,
        "FAIL 项：" + "; ".join(r[1] for r in res.fails[:3]) if n_fail else "全过")

    # 逐类注入缺陷，验证能被抓到
    # (类别, key, 注入片段 or None, 说明)
    mutations = [
        ("ANDROID_SMELL", "smell_ripple", '<div class="ripple"></div>', "ripple"),
        ("ANDROID_SMELL", "smell_fab", '<button class="floating-action-button">+</button>', "fab"),
        ("ANDROID_SMELL", "smell_material_font", '<link href="material-symbols">', "material"),
        ("ANDROID_SMELL", "smell_transition_all", "transition: all 200ms;", "transition:all"),
        ("ANDROID_SMELL", "smell_elevation", "elevation: 4px;", "elevation"),
        ("IOS_FEATURE", "dynamic_island", None, None),      # 删掉 island
        ("IOS_FEATURE", "home_indicator", None, None),      # 删掉 home indicator
        ("IOS_FEATURE", "switch_51x31", None, None),        # 改坏开关尺寸
        ("IOS_FEATURE", "no_emoji_icon", None, None),        # 塞 emoji
        ("IOS_VALUE", "Tab Bar 高 56px", None, None),        # 改坏 Tab Bar 高度
        ("IOS_T1", "IOS-COL-03", None, None),                # systemBlue 退回旧值
        ("IOS_T1", "IOS-A11Y-01", None, None),               # 正文对比度不足
        ("IOS_T1", "IOS-A11Y-03", None, None),               # 触控目标不够大
        ("IOS_T1", "IOS-TYP-01", None, None),                # 正文字号不达标
    ]

    # key → 期望被命中的行名
    expect_name = {}
    for k, v in IOS_FEATURES.items():
        expect_name[k] = v[0]
    for k, v in ANDROID_SMELLS.items():
        expect_name[k] = v[0]
    for desc, _pat, _tier, _src in IOS_VALUES:
        expect_name[desc] = desc
    for rid, desc, _src, _fn in IOS_T1_RULES:
        expect_name[rid] = "%s  %s" % (rid, desc)

    for kind, key, inject, _ in mutations:
        if inject:
            bad = good.replace("</body>", inject + "\n</body>")
        elif key == "dynamic_island":
            bad = re.sub(r"dynamic-island|island", "gone", good, flags=re.I)
        elif key == "home_indicator":
            bad = re.sub(r"home-indicator|home_indicator", "gone", good, flags=re.I)
        elif key == "switch_51x31":
            # 原文可能是 `width:51px` 或 `width: 51px`，两种都要改掉
            bad = re.sub(r"width:\s*51px", "width:33px", good)
            bad = re.sub(r"height:\s*31px", "height:19px", bad)
        elif key == "Tab Bar 高 56px":
            bad = re.sub(r"height:\s*56px", "height:44px", good)
        elif key == "IOS-COL-03":
            bad = re.sub(r"--system-blue:\s*#0088FF", "--system-blue:#007AFF", good)
        elif key == "IOS-A11Y-01":
            # 把正文色改成深灰 ⇒ 对比度掉到 4.5:1 以下
            bad = re.sub(r"--label:\s*#000000", "--label:#777777", good)
        elif key == "IOS-A11Y-03":
            bad = re.sub(r"min-height:\s*44px", "min-height:30px", good)
        elif key == "IOS-TYP-01":
            bad = re.sub(r"--fs-title:\s*17px", "--fs-title:14px", good)
        else:
            bad = good.replace("</body>", "<div>\U0001F600</div>\n</body>")

        tmp = os.path.join(os.environ.get("TEMP", "."), "_ios_bad.html")
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(bad)
        r = Result()
        check_file(tmp, r, "mutant", VARIANTS[TARGETS[0]])
        want = expect_name.get(key)
        caught = [x for x in r.fails if x[1] == want]
        chk("变异被 %s 抓到" % key, bool(caught),
            caught[0][1] if caught else "没抓到 —— 检查器有盲区")
        try:
            os.remove(tmp)
        except OSError:
            pass

    print()
    print("=" * 74)
    if ok:
        print("自检结果：ALL PASS")
        print("=" * 74)
        return 0
    print("自检结果：FAIL {} 项：{}".format(len(fails), fails))
    print("=" * 74)
    return 1


# ══════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="iOS 原生感机器判定")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("files", nargs="*", help="要检查的 HTML（默认浅色+深色）")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    files = args.files or [os.path.join(HERE, t) for t in TARGETS]
    res = Result()
    for p in files:
        base = os.path.basename(p)
        check_file(p, res, base, VARIANTS.get(base, "light"))
    n_fail = res.report("StackChan iOS 原生感判定（%d 个文件）" % len(files))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
