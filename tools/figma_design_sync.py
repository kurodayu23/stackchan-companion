#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figma_design_sync.py —— Figma 设计稿 <-> iOS DesignSystem token 漂移体检

为什么需要它
------------
2026-10-27 用户接入 Figma Connector 之后，本仓库第一次有了「设计稿 = 机器可读输入」的能力。
Connector 只提供两个**只读**工具：

  - ``connector__figma__get_figma_data``         读布局 / 样式 / 文本 / 资源引用
  - ``connector__figma__download_figma_images``  导出 PNG/SVG/GIF（返回 1 小时有效签名 URL）

两者都**不能替我们画稿、不能改用户文件**（实测，见 ``docs/research/89``）。
所以本工具的定位是「把用户的设计稿变成**可判的漂移报告**」，不是「让 AI 画设计稿」。

输入格式（自动识别，认不出就 FAIL，不静默通过）：
  1. **Figma 文档** —— REST ``GET /v1/files/:key`` 形状（``document.children`` 递归）
  2. **Figma Variables** 导出（``variables`` 字典，``valuesByMode`` / ``values``）
  3. **DTCG / Tokens Studio**（``$value`` + ``$type``）

判据
----
  FD-01  输入形状可识别                     认不出 -> FAIL（fail loud）
  FD-02  Swift 侧 token 提取非空            圆角 >= 6 且调色板 >= 4 -> 否则 FAIL
  FD-03  圆角漂移：设计稿圆角值必须落在 ``Shapes.swift`` 已登记的圆角档
  FD-04  字号下限：所有 TEXT 节点 fontSize >= 11（HIG ``accessibility.md:40``）
  FD-05  触控目标：所有 FRAME/COMPONENT 短边 >= 44（HIG ``accessibility.md:135``）—— WARN
  FD-06  颜色白名单：设计稿纯色必须能在 4 套调色板 12 槽位里找到（RGB 各分量差 <= 0.03）—— WARN

用法
----
    py -3.12 tools/figma_design_sync.py --figma <design.json> [--root .] [--json]
    py -3.12 tools/figma_design_sync.py --figma <design.json> --emit-tokens <out.json>
    py -3.12 tools/figma_design_sync.py --self-test [--root .]

退出码：0 = 无 FAIL（WARN 不影响退出码）；1 = 有 FAIL；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: Swift 侧文件（相对仓库根）
SHAPES_REL = os.path.join("ios", "StackChanCompanion", "DesignSystem", "Shapes.swift")
TOKENS_REL = os.path.join("ios", "StackChanCompanion", "DesignSystem", "Tokens.swift")

#: ``Shapes.swift`` 里的圆角槽位
CORNER_SLOTS = ["icon", "control", "tile", "card", "sheet", "capsule"]
#: ``Shapes.swift`` 里的间距槽位
SPACING_SLOTS = [
    "spacingXS", "spacingS", "spacingM", "spacingL", "spacingXL", "spacingXXL",
]

#: HIG 下限（真值来源见 ``docs/spec/02`` 与 ``Typography.swift`` 头部注释）
MIN_FONT_SIZE = 11.0
MIN_TOUCH_TARGET = 44.0

#: 颜色比对容差（RGB 各分量绝对差）
COLOR_EPS = 0.03

RE_SHAPE_TOKEN = re.compile(
    r"public\s+static\s+let\s+(\w+)\s*:\s*CGFloat\s*=\s*([0-9]*\.?[0-9]+)")
RE_PALETTE_STRUCT = re.compile(
    r"public\s+struct\s+(\w+)Palette\s*:\s*ThemePalette\s*\{")
RE_PALETTE_ID = re.compile(r'identifier:\s*String\s*\{\s*"([^"]+)"\s*\}')
RE_TOKEN_CASE = re.compile(
    r"case\s+\.(\w+)\s*:\s*return\s+Color\(\s*red:\s*([0-9.]+)\s*,\s*"
    r"green:\s*([0-9.]+)\s*,\s*blue:\s*([0-9.]+)\s*\)\s*"
    r"(?:\.opacity\(\s*([0-9.]+)\s*\))?")


class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "where": self.where, "msg": self.msg}


# ---------------------------------------------------------------------------
# 读文件
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _read_json(path: str) -> dict:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Swift 侧提取
# ---------------------------------------------------------------------------

def extract_swift_shapes(path: str) -> dict:
    """从 ``Shapes.swift`` 提取 ``名字 -> 数值``。"""
    text = _read(path)
    out = {}
    for m in RE_SHAPE_TOKEN.finditer(text):
        out[m.group(1)] = float(m.group(2))
    return out


def extract_swift_palettes(path: str) -> dict:
    """从 ``Tokens.swift`` 提取 ``方案 -> 槽位 -> (r, g, b, opacity)``。"""
    text = _read(path)
    palettes = {}
    marks = list(RE_PALETTE_STRUCT.finditer(text))
    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mk.start():end]
        ident = RE_PALETTE_ID.search(body)
        key = ident.group(1) if ident else mk.group(1)
        slots = {}
        for cm in RE_TOKEN_CASE.finditer(body):
            r, g, b = (float(cm.group(2)), float(cm.group(3)), float(cm.group(4)))
            op = float(cm.group(5)) if cm.group(5) else 1.0
            slots[cm.group(1)] = (r, g, b, op)
        palettes[key] = slots
    return palettes


# ---------------------------------------------------------------------------
# Figma 侧提取
# ---------------------------------------------------------------------------

def detect_shape(obj) -> str:
    """识别输入形状；认不出返回 ``""``。"""
    if not isinstance(obj, dict):
        return ""
    if isinstance(obj.get("document"), dict):
        return "figma_document"
    if isinstance(obj.get("variables"), dict):
        return "figma_variables"
    # DTCG：至少一个 group，且某个叶子带 $value
    for key, group in obj.items():
        if isinstance(group, dict) and any(
                isinstance(v, dict) and "$value" in v for v in group.values()):
            return "dtcg"
    # 顶层本身就是文档节点
    if obj.get("type") == "DOCUMENT" and "children" in obj:
        return "figma_document"
    return ""


def _find_document_node(obj, depth: int = 0):
    """在未知外层包装里找 Figma 文档节点（最多 3 层）。"""
    if depth > 3 or not isinstance(obj, dict):
        return None
    if isinstance(obj.get("document"), dict):
        return obj["document"]
    if obj.get("type") == "DOCUMENT" and "children" in obj:
        return obj
    for v in obj.values():
        if isinstance(v, dict):
            got = _find_document_node(v, depth + 1)
            if got is not None:
                return got
    return None


def _iter_nodes(node):
    if not isinstance(node, dict):
        return
    yield node
    for ch in (node.get("children") or []):
        for sub in _iter_nodes(ch):
            yield sub


def _hex_to_rgb(text: str):
    s = text.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16) / 255.0,
                int(s[2:4], 16) / 255.0,
                int(s[4:6], 16) / 255.0)
    except ValueError:
        return None


def extract_figma(obj, shape: str) -> dict:
    """把设计稿压成一份可比较的数值集合。"""
    info = {
        "corner_radii": [],
        "text_font_sizes": [],
        "frame_sides": [],
        "colors": [],
        "token_values": {},
        "node_count": 0,
    }
    if shape == "figma_document":
        doc = _find_document_node(obj)
        if doc is None:
            return info
        for node in _iter_nodes(doc):
            info["node_count"] += 1
            name = node.get("name") or node.get("id") or "?"
            r = node.get("cornerRadius")
            if isinstance(r, (int, float)):
                info["corner_radii"].append((float(r), name))
            radii = node.get("rectangleCornerRadii")
            if isinstance(radii, list):
                for rr in radii:
                    if isinstance(rr, (int, float)):
                        info["corner_radii"].append((float(rr), name))
            box = node.get("absoluteBoundingBox")
            if isinstance(box, dict) and node.get("type") in (
                    "FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE"):
                try:
                    info["frame_sides"].append(
                        (float(box.get("width", 0)), float(box.get("height", 0)), name))
                except (TypeError, ValueError):
                    pass
            if node.get("type") == "TEXT":
                st = node.get("style") or {}
                fs = st.get("fontSize")
                if isinstance(fs, (int, float)):
                    info["text_font_sizes"].append((float(fs), name))
            for fill in (node.get("fills") or []):
                if not isinstance(fill, dict) or fill.get("type") != "SOLID":
                    continue
                col = fill.get("color") or {}
                try:
                    info["colors"].append((
                        float(col.get("r", 0)), float(col.get("g", 0)),
                        float(col.get("b", 0)), float(fill.get("opacity", 1)),
                        name))
                except (TypeError, ValueError):
                    pass
    elif shape == "figma_variables":
        for vid, v in (obj.get("variables") or {}).items():
            if not isinstance(v, dict):
                continue
            name = v.get("name") or vid
            rtype = v.get("resolvedType") or ""
            values = v.get("valuesByMode")
            if isinstance(values, dict):
                vals = list(values.values())
            else:
                vals = v.get("values")
                vals = list(vals.values()) if isinstance(vals, dict) else (
                    [vals] if vals is not None else [])
            for val in vals:
                if isinstance(val, (int, float)):
                    info["token_values"][name] = float(val)
                    if rtype == "FLOAT":
                        info["corner_radii"].append((float(val), name))
                elif isinstance(val, str) and val.strip().startswith("#"):
                    rgb = _hex_to_rgb(val)
                    if rgb:
                        info["colors"].append((rgb[0], rgb[1], rgb[2], 1.0, name))
    elif shape == "dtcg":
        for group, items in obj.items():
            if not isinstance(items, dict):
                continue
            for leaf_name, leaf in items.items():
                if not isinstance(leaf, dict) or "$value" not in leaf:
                    continue
                full = "%s.%s" % (group, leaf_name)
                val = leaf["$value"]
                if isinstance(val, (int, float)):
                    info["token_values"][full] = float(val)
                    info["corner_radii"].append((float(val), full))
                elif isinstance(val, str):
                    txt = val.strip()
                    if txt.startswith("#"):
                        rgb = _hex_to_rgb(txt)
                        if rgb:
                            info["colors"].append(
                                (rgb[0], rgb[1], rgb[2], 1.0, full))
                    elif txt.endswith("px"):
                        try:
                            px = float(txt[:-2])
                        except ValueError:
                            continue
                        info["token_values"][full] = px
                        info["corner_radii"].append((px, full))
    return info


# ---------------------------------------------------------------------------
# 判据
# ---------------------------------------------------------------------------

def _near(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) <= eps


def _radius_registered(value: float, corner_values: set) -> bool:
    """圆角是否已登记。

    两条豁免（都不是「放水」，是 iOS 的真实语义）：
      - ``0``：直角容器（整屏 / 满幅底板）—— 本仓库 ``Shapes.swift`` 没登记
        「屏幕」这个槽位，但直角容器在 iOS 里完全合法 ⇒ 不算漂移。
      - ``>= 100``：完全圆角（胶囊）⇒ 视作已登记的 ``capsule = 999`` 档。
    """
    if _near(value, 0.0):
        return True
    if value >= 100.0:
        return True
    for cv in corner_values:
        if _near(value, cv):
            return True
    return False


def run_checks(info: dict, shapes: dict, palettes: dict, where: str) -> list:
    findings = []

    # FD-02：Swift 侧 token 提取非空
    corner_slots = {k: shapes.get(k) for k in CORNER_SLOTS}
    missing = [k for k, v in corner_slots.items() if v is None]
    if missing or len(palettes) < 4:
        findings.append(Finding(
            "FD-02", "FAIL", where,
            "Swift 侧 token 提取不完整：缺失圆角槽位 %s，调色板 %d 套（应 >= 4）"
            % (missing or "无", len(palettes))))

    corner_values = {v for v in corner_slots.values() if v is not None}

    # FD-03：圆角漂移
    seen_radius = set()
    for value, name in info["corner_radii"]:
        key = round(value, 4)
        if key in seen_radius:
            continue
        seen_radius.add(key)
        if not _radius_registered(value, corner_values):
            findings.append(Finding(
                "FD-03", "FAIL", where,
                "设计稿圆角 %g pt（节点 `%s`）不在 `Shapes.swift` 登记的圆角档 %s 内"
                % (value, name, sorted(corner_values))))

    # FD-04：字号下限
    for size, name in info["text_font_sizes"]:
        if size < MIN_FONT_SIZE:
            findings.append(Finding(
                "FD-04", "FAIL", where,
                "设计稿文本字号 %g pt（节点 `%s`）低于 HIG 下限 %g pt"
                % (size, name, MIN_FONT_SIZE)))

    # FD-05：触控目标（启发式 -> WARN）
    for w, h, name in info["frame_sides"]:
        if min(w, h) < MIN_TOUCH_TARGET:
            findings.append(Finding(
                "FD-05", "WARN", where,
                "设计稿容器 %gx%g pt（节点 `%s`）短边 < %g pt（HIG 触控目标下限）"
                % (w, h, name, MIN_TOUCH_TARGET)))

    # FD-06：颜色白名单
    palette_slots = []
    for scheme, slots in palettes.items():
        for slot, (r, g, b, _op) in slots.items():
            palette_slots.append((scheme, slot, r, g, b))
    seen_color = set()
    for r, g, b, op, name in info["colors"]:
        key = (round(r, 3), round(g, 3), round(b, 3))
        if key in seen_color:
            continue
        seen_color.add(key)
        hit = None
        for scheme, slot, pr, pg, pb in palette_slots:
            if (abs(pr - r) <= COLOR_EPS and abs(pg - g) <= COLOR_EPS
                    and abs(pb - b) <= COLOR_EPS):
                hit = "%s/%s" % (scheme, slot)
                break
        if hit is None:
            findings.append(Finding(
                "FD-06", "WARN", where,
                "设计稿颜色 rgb(%g, %g, %g) opacity=%g（节点 `%s`）在 4 套调色板 12 槽位里"
                "找不到对应项（容差 %g）" % (r, g, b, op, name, COLOR_EPS)))

    return findings


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def analyze(figma_path: str, root: str) -> dict:
    obj = _read_json(figma_path)
    shape = detect_shape(obj)
    where = os.path.basename(figma_path)

    shapes_path = os.path.join(root, SHAPES_REL)
    tokens_path = os.path.join(root, TOKENS_REL)
    swift_shapes = extract_swift_shapes(shapes_path)
    swift_palettes = extract_swift_palettes(tokens_path)

    findings = []
    if not shape:
        findings.append(Finding(
            "FD-01", "FAIL", where,
            "输入形状无法识别：既不是 Figma 文档（`document.children`），"
            "也不是 Figma Variables（`variables`），也不是 DTCG（`$value`）。"
            "本工具**不会**在认不出输入时静默通过"))
        info = {"corner_radii": [], "text_font_sizes": [], "frame_sides": [],
                "colors": [], "token_values": {}, "node_count": 0}
    else:
        info = extract_figma(obj, shape)
        findings.extend(run_checks(info, swift_shapes, swift_palettes, where))

    return {
        "source_shape": shape,
        "source_path": figma_path,
        "figma": {
            "node_count": info["node_count"],
            "corner_radii": sorted({round(v, 4) for v, _ in info["corner_radii"]}),
            "text_font_sizes": sorted({round(v, 4) for v, _ in info["text_font_sizes"]}),
            "frame_count": len(info["frame_sides"]),
            "color_count": len(info["colors"]),
            "token_values": info["token_values"],
        },
        "swift": {
            "shapes": swift_shapes,
            "palettes": {k: {s: list(v) for s, v in slots.items()}
                        for k, slots in swift_palettes.items()},
        },
        "findings": [f.as_dict() for f in findings],
        "fail_count": sum(1 for f in findings if f.severity == "FAIL"),
        "warn_count": sum(1 for f in findings if f.severity == "WARN"),
    }


def print_report(report: dict) -> None:
    print("[figma_design_sync] 输入形状: %s" % (report["source_shape"] or "<未识别>"))
    fg = report["figma"]
    print("  设计稿：节点 %d / 圆角 %d 种 / 字号 %d 种 / 容器 %d / 纯色 %d"
          % (fg["node_count"], len(fg["corner_radii"]),
             len(fg["text_font_sizes"]), fg["frame_count"], fg["color_count"]))
    if fg["corner_radii"]:
        print("  设计稿圆角值: %s" % fg["corner_radii"])
    if fg["text_font_sizes"]:
        print("  设计稿字号值: %s" % fg["text_font_sizes"])
    if not report["findings"]:
        print("[figma_design_sync] PASS：未发现漂移")
    for f in report["findings"]:
        print("  %s [%s] %s: %s" % (f["code"], f["severity"], f["where"], f["msg"]))
    print("[figma_design_sync] FAIL=%d WARN=%d"
          % (report["fail_count"], report["warn_count"]))


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def _fixture_clean() -> dict:
    """干净稿：圆角/字号/尺寸/颜色全部命中 Swift 已登记值。"""
    return {
        "name": "clean",
        "document": {
            "id": "0:0", "name": "Document", "type": "DOCUMENT",
            "children": [{
                "id": "1:1", "name": "Screen", "type": "FRAME",
                "absoluteBoundingBox": {"x": 0, "y": 0, "width": 390, "height": 844},
                "backgroundColor": {"r": 0.980, "g": 0.973, "b": 0.961},
                "cornerRadius": 0,
                "fills": [{"type": "SOLID", "opacity": 1,
                           "color": {"r": 0.980, "g": 0.973, "b": 0.961}}],
                "children": [
                    {"id": "1:2", "name": "Card", "type": "FRAME",
                     "absoluteBoundingBox": {"x": 16, "y": 60, "width": 358, "height": 120},
                     "cornerRadius": 16,
                     "fills": [{"type": "SOLID", "opacity": 1,
                                "color": {"r": 0.141, "g": 0.122, "b": 0.106}}],
                     "children": [
                         {"id": "1:3", "name": "Title", "type": "TEXT",
                          "style": {"fontSize": 17, "lineHeightPx": 22,
                                    "fontFamily": "SF Pro Text", "fontWeight": 600},
                          "characters": "小栈"}]},
                    {"id": "1:4", "name": "Button", "type": "FRAME",
                     "absoluteBoundingBox": {"x": 16, "y": 200, "width": 120, "height": 44},
                     "cornerRadius": 10,
                     "fills": [{"type": "SOLID", "opacity": 1,
                                "color": {"r": 0.686, "g": 0.298, "b": 0.216}}],
                     "children": []},
                ]}]}}


def _fixture_drift() -> dict:
    """漂移稿：未登记圆角 24 / 字号 9 / 30x30 容器 / 未登记颜色。"""
    return {
        "name": "drift",
        "document": {
            "id": "0:0", "name": "Document", "type": "DOCUMENT",
            "children": [{
                "id": "2:1", "name": "Screen", "type": "FRAME",
                "absoluteBoundingBox": {"x": 0, "y": 0, "width": 390, "height": 844},
                "fills": [{"type": "SOLID", "opacity": 1,
                           "color": {"r": 0.5, "g": 0.1, "b": 0.9}}],
                "children": [
                    {"id": "2:2", "name": "Card", "type": "FRAME",
                     "absoluteBoundingBox": {"x": 16, "y": 60, "width": 358, "height": 120},
                     "cornerRadius": 24, "fills": [], "children": []},
                    {"id": "2:3", "name": "Small", "type": "FRAME",
                     "absoluteBoundingBox": {"x": 16, "y": 200, "width": 30, "height": 30},
                     "cornerRadius": 10, "fills": [], "children": []},
                    {"id": "2:4", "name": "Tiny", "type": "TEXT",
                     "style": {"fontSize": 9, "lineHeightPx": 11},
                     "characters": "小"},
                ]}]}}


def _write_tmp(obj: dict, path: str) -> str:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2))
    return path


def self_test(root: str) -> int:
    import tempfile
    failures = []
    tmpdir = tempfile.mkdtemp(prefix="figma_sync_selftest_")

    # --- 0. Swift 侧提取必须真的提取到东西（否则整套判据没有比较对象）---
    shapes = extract_swift_shapes(os.path.join(root, SHAPES_REL))
    palettes = extract_swift_palettes(os.path.join(root, TOKENS_REL))
    if len([k for k in CORNER_SLOTS if k in shapes]) != len(CORNER_SLOTS):
        failures.append("自检前提失败：Shapes.swift 圆角槽位提取不全 -> %s" % shapes)
    if len(palettes) < 4:
        failures.append("自检前提失败：Tokens.swift 调色板提取 %d 套（应 >= 4）" % len(palettes))
    else:
        for scheme, slots in palettes.items():
            if len(slots) < 12:
                failures.append("自检前提失败：调色板 %s 只有 %d 个槽位（应 12）"
                                % (scheme, len(slots)))

    clean_path = _write_tmp(_fixture_clean(), os.path.join(tmpdir, "clean.json"))
    drift_path = _write_tmp(_fixture_drift(), os.path.join(tmpdir, "drift.json"))
    bad_path = _write_tmp({"hello": "world"}, os.path.join(tmpdir, "bad.json"))

    clean = analyze(clean_path, root)
    drift = analyze(drift_path, root)
    bad = analyze(bad_path, root)

    # --- 1. 干净稿必须 0 FAIL ---
    if clean["fail_count"] != 0:
        failures.append("干净稿出现 %d 个 FAIL（应为 0）：%s"
                        % (clean["fail_count"], clean["findings"]))

    # --- 2. 阴性夹具必须**真的改变指标**（否则等于恒等置换，什么都没测）---
    if drift["fail_count"] == clean["fail_count"]:
        failures.append("阴性夹具无效：漂移稿与干净稿的 FAIL 数相同（%d）"
                        % drift["fail_count"])
    if drift["fail_count"] == 0:
        failures.append("阴性夹具无效：漂移稿 0 个 FAIL（等于恒等置换）")

    # --- 3. 目标检查码必须各自触发 ---
    drift_codes = {f["code"] for f in drift["findings"]}
    for code in ("FD-03", "FD-04", "FD-05", "FD-06"):
        if code not in drift_codes:
            failures.append("漂移稿未触发 %s（实际触发 %s）" % (code, sorted(drift_codes)))

    # --- 4. 认不出的输入必须 FAIL（fail loud，绝不静默通过）---
    if bad["fail_count"] != 1 or {f["code"] for f in bad["findings"]} != {"FD-01"}:
        failures.append("未识别输入未按预期报 FD-01：%s" % bad["findings"])

    # --- 5. 干净稿的圆角/字号必须被正确提取（证明解析器没空转）---
    if 16.0 not in clean["figma"]["corner_radii"]:
        failures.append("解析器空转：干净稿未提取到圆角 16 -> %s"
                        % clean["figma"]["corner_radii"])
    if 17.0 not in clean["figma"]["text_font_sizes"]:
        failures.append("解析器空转：干净稿未提取到字号 17 -> %s"
                        % clean["figma"]["text_font_sizes"])

    total = 6
    if failures:
        print("[figma_design_sync/selftest] FAIL %d/%d" % (len(failures), total))
        for f in failures:
            print("  - %s" % f)
        return 1
    print("[figma_design_sync/selftest] PASS %d/%d" % (total, total))
    print("  干净稿 FAIL=0；漂移稿 FAIL=%d 且触发 %s；未识别输入报 FD-01"
          % (drift["fail_count"], sorted(drift_codes)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Figma 设计稿 <-> iOS DesignSystem token 漂移体检")
    ap.add_argument("--figma", help="Figma 设计稿 JSON（文档 / Variables / DTCG）")
    ap.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--emit-tokens", help="把提取到的设计 token 归一化后写到该 JSON")
    ap.add_argument("--self-test", action="store_true", help="跑自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test(args.root)

    if not args.figma:
        print("用法：--figma <design.json> 或 --self-test", file=sys.stderr)
        return 2
    if not os.path.isfile(args.figma):
        print("找不到文件：%s" % args.figma, file=sys.stderr)
        return 2

    report = analyze(args.figma, args.root)

    if args.emit_tokens:
        payload = {
            "source_shape": report["source_shape"],
            "source_path": report["source_path"],
            "extracted": report["figma"],
            "swift": report["swift"],
        }
        with io.open(args.emit_tokens, "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, indent=2))
        print("[figma_design_sync] token 已写出：%s" % args.emit_tokens)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report["fail_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
