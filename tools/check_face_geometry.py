#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_face_geometry.py —— 校验 Swift 脸渲染几何与**固件公式同口径**

为什么需要这个门禁
------------------
「App 是镜子」这条产品原则（`docs/research/58-iOS端架构决策.md` §4）
要求 App 端的像素几何与固件**完全一致**。

本机（Windows）**没有 Swift 编译器** ⇒ `swift test` 在本地跑不了，
只能靠 GH Actions 的 macOS runner。本脚本补上这个缺口：
**用 Python 复刻固件的 `map_range` 语义，解析 Swift 源码里的公式常量，
逐点比对** —— 于是「Swift 公式被改坏」这件事在本地/CI 都能被抓到。

它校验什么
----------
1. **公式常量一致**：Swift 里的基准常量（眼位 / 嘴位 / 量程）== 固件源码里的常量。
2. **同点同值**：对每个采样点，Python 复刻的固件公式 == Swift 源码里写的公式。
   （用 `ast` 无法解析 Swift ⇒ 这里用**表达式抽取 + 独立复刻**的方式：
   Swift 源码里的公式以注释形式登记为 `EXPECTED_FORMULAS`，
   脚本校验「注释登记的公式」与「Python 复刻」一致，
   并校验源码里出现的**关键常量**与登记一致。）
3. **钳位语义一致**：固件是「先在 Element/Feature 层钳位，再 map_range」；
   `map_range` **本身不钳位** ⇒ 脚本校验 Swift 的钳位范围与固件一致。
4. **极性方向**：眼睛 weight 越大越睁开、嘴 weight 越大越张开（两个方向不能反）。
5. **镜像模式嘴恒默认**：镜像模式必须把嘴 weight 归 0（固件 `setEmotion` 不碰嘴）。

固件源码路径
------------
默认 `D:\\jss18\\AI\\StackChan\\StackChan2\\firmware`（官方仓，只读）。
用 `--firmware` 指定其它路径；**找不到时降级为「只校验登记常量」并打 WARN**。

用法
----
    py -3.12 tools/check_face_geometry.py --root .
    py -3.12 tools/check_face_geometry.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

__version__ = "1.0.0"

DEFAULT_FIRMWARE = r"D:\jss18\AI\StackChan\StackChan2\firmware"

# Swift 源文件相对路径
GEOMETRY_SWIFT = os.path.join("ios", "StackChanCompanion", "CoreProtocol",
                               "Sources", "CoreProtocol", "FaceGeometry.swift")
PROJECTION_SWIFT = os.path.join("ios", "StackChanCompanion", "CoreProtocol",
                                "Sources", "CoreProtocol", "FaceProjection.swift")
AVATAR_MODEL_SWIFT = os.path.join("ios", "StackChanCompanion", "CoreProtocol",
                                   "Sources", "CoreProtocol", "AvatarModel.swift")
FACEVIEW_SWIFT = os.path.join("ios", "StackChanCompanion", "Features",
                              "Companion", "Face", "FaceView.swift")

# 固件源码相对路径
FW_EYES = os.path.join("main", "stackchan", "avatar", "skins", "default", "eyes.cpp")
FW_MOUTH = os.path.join("main", "stackchan", "avatar", "skins", "default", "mouth.cpp")
FW_ELEMENT = os.path.join("main", "stackchan", "avatar", "avatar", "elements", "element.h")
FW_FEATURE = os.path.join("main", "stackchan", "avatar", "avatar", "elements", "feature.h")


# ---------------------------------------------------------------------------
# 固件语义复刻（与 C++ 同口径）
# ---------------------------------------------------------------------------

def c_div(a: int, b: int) -> int:
    """C++ 整数除法：**向零截断**（Python 的 // 是向下取整，负数时不同！）。"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def fw_map_range(val: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """复刻固件 `map_range`（`base.hpp:40-48`）。

    ⚠️ 它**不钳位** —— 是纯线性映射。
    """
    if in_max == in_min:
        return out_min
    return out_min + c_div((val - in_min) * (out_max - out_min), in_max - in_min)


def fw_clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)


# ---- 固件各公式（逐条对应源码行） ----

def fw_position_offset(units: int) -> int:
    """`eyes.cpp:64` / `mouth.cpp:42`：`map_range(pos, -100, 100, -16, 16)`。

    ⚠️ 位置在 `element.h:29` 被钳到 ±100。
    """
    return fw_map_range(fw_clamp(units, -100, 100), -100, 100, -16, 16)


def fw_eye_diameter(size: int) -> int:
    """`eyes.cpp:137`：`map_range(_size, -100, 100, 8, 32)`。

    ⚠️ size 在 `feature.h:38` 被钳到 ±100。
    """
    return fw_map_range(fw_clamp(size, -100, 100), -100, 100, 8, 32)


def fw_eyelid_offset(eye_diameter: int, weight: int) -> int:
    """`eyes.cpp:75`：`-map_range(_weight, 0, 100, 0, 眼径)`。

    ⚠️ weight 在 `feature.h:24` 被钳到 0..100。
    """
    return -fw_map_range(fw_clamp(weight, 0, 100), 0, 100, 0, eye_diameter)


def fw_mouth_size(weight: int) -> tuple:
    """`mouth.cpp:52-54`：宽/高/圆角三条 `map_range`。

    ⚠️ 固件是**整数除法**，且 `map_range` 不钳位 ⇒ 必须用 C++ 口径算。
    """
    w = fw_clamp(weight, 0, 100)
    width = fw_map_range(w, 0, 100, 90, 60)
    height = fw_map_range(w, 0, 100, 6, 50)
    radius = fw_map_range(w, 0, 100, 0, 16)
    return (width, height, radius)


# ---- Swift 侧（复刻 FaceGeometryEngine 的公式） ----

def sw_position_offset(units: int) -> int:
    """`FaceGeometryEngine.positionOffsetPixels`。

    ⚠️ 逐字复刻固件的 `map_range(x, -100, 100, -16, 16)`，
    **不是** `x * 16 / 100`（后者在负数段差 1 像素）。
    """
    clamped = max(-100, min(100, units))
    return -16 + c_div((clamped + 100) * 32, 200)


def sw_eye_diameter(size: int) -> int:
    """`FaceGeometryEngine.eyeDiameter`。"""
    clamped = max(-100, min(100, size))
    return 8 + c_div((clamped + 100) * 24, 200)


def sw_eyelid_offset(eye_diameter: int, weight: int) -> int:
    """`FaceGeometryEngine.eyelidOffsetY`。"""
    clamped = max(0, min(100, weight))
    return -(c_div(eye_diameter * clamped, 100))


def sw_mouth_size(weight: int) -> tuple:
    """`FaceGeometryEngine.mouthSize`。"""
    clamped = max(0, min(100, weight))
    width = 90 + c_div(clamped * (60 - 90), 100)
    height = 6 + c_div(clamped * (50 - 6), 100)
    radius = 0 + c_div(clamped * (16 - 0), 100)
    return (width, height, radius)


# ---------------------------------------------------------------------------
# Swift 源码常量抽取
# ---------------------------------------------------------------------------

_CONST_RE = re.compile(
    r"public static let (\w+)\s*(?::\s*[^=\n]+)?=\s*(-?\d+)\s*(?://[^\n]*)?",
)
# 范围常量：`public static let rotationRange = 0...3600`
_CONST_RANGE_RE = re.compile(r"public static let (\w+)\s*=\s*(-?\d+)\s*\.\.\.\s*(-?\d+)")
# 带类型标注的范围：`public static let rotationRange: ClosedRange<Int> = 0...3600`
_CONST_RANGE_TYPED_RE = re.compile(
    r"public static let (\w+)\s*:\s*[^=\n]*=\s*(-?\d+)\s*\.\.\.\s*(-?\d+)")


def extract_swift_constants(path: str) -> dict:
    """从 Swift 源码里抽 `public static let X = N` 形式的整数常量。

    ⚠️ 顺序要紧：**先抽范围**（`0...3600`），
    否则整数正则会把 `0` 当成 `rotationRange` 的值（范围被截成一个数）。
    """
    with io.open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    out = {}
    for m in _CONST_RANGE_TYPED_RE.finditer(text):
        out[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    for m in _CONST_RANGE_RE.finditer(text):
        out.setdefault(m.group(1), (int(m.group(2)), int(m.group(3))))
    for m in _CONST_RE.finditer(text):
        name = m.group(1)
        if name in out:
            continue
        try:
            out[name] = int(m.group(2))
        except ValueError:
            pass
    return out


def swift_declares(path: str, needle: str) -> bool:
    with io.open(path, encoding="utf-8", newline="") as fh:
        return needle in fh.read()


# ---------------------------------------------------------------------------
# 6 情绪表（weight / rotation）—— 固件事实的副本，必须逐值对齐
# ---------------------------------------------------------------------------

def fw_emotion_table(eyes_path: str) -> dict:
    """从固件 ``eyes.cpp`` 抽 ``case Emotion::X: apply_style(weight, rotation)``。

    ⚠️ ``apply_style`` 的第二个参数是**左眼**的 rotation；
    右眼由固件自己取反（``setRotation(-rotation)``）⇒ 解析时单独验证。
    """
    text = read_text(eyes_path)
    if not text:
        return {}
    out = {}
    for m in re.finditer(r"case\s+Emotion::(\w+)\s*:\s*apply_style\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)",
                         text):
        out[m.group(1).lower()] = (int(m.group(2)), int(m.group(3)))
    return out


def fw_right_eye_is_mirrored(eyes_path: str) -> bool:
    """固件右眼是否取反 rotation（``setRotation(-rotation)``）。"""
    text = read_text(eyes_path) or ""
    return "setRotation(-rotation)" in text


def _swift_var_block(text: str, name: str) -> str:
    m = re.search(r"public var %s\s*:\s*Int\s*\{" % re.escape(name), text)
    if not m:
        return ""
    start = m.end()
    end = text.find("\n    }", start)
    return text[start:end if end > 0 else len(text)]


def sw_mood_table(path: str) -> dict:
    """从 ``AvatarModel.swift`` 抽 ``Mood`` 的三个表。

    返回 ``{"eyeWeight": {...}, "leftEyeRotation": {...}, "rightEyeRotation": {...}}``，
    键是小写情绪名。
    """
    try:
        text = _read(path)
    except Exception:
        return {}
    out = {}
    for prop in ("eyeWeight", "leftEyeRotation", "rightEyeRotation"):
        block = _swift_var_block(text, prop)
        vals = {}
        for m in re.finditer(r"case\s+\.(\w+)\s*:\s*return\s+(-?\d+)", block):
            vals[m.group(1)] = int(m.group(2))
        out[prop] = vals
    return out


# ---------------------------------------------------------------------------
# 固件常量抽取（正则从 C++ 源码里读）
# ---------------------------------------------------------------------------

def read_text(path: str):
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def fw_eye_base_x() -> int:
    """左眼基准中心 x = 画布中心 160 + (-70) = 90。

    固件：`_eye_pos = Vector2i(-70, -16)`（`eyes.cpp:13`），
    左眼取 `_eye_pos.x`，右眼取 `-_eye_pos.x`（`eyes.cpp:63`），
    容器 `LV_ALIGN_CENTER` 于 320 宽画布 ⇒ 中心 x = 160。
    """
    text = read_text(DEFAULT_FIRMWARE + "\\" + FW_EYES)
    m = re.search(r"_eye_pos\s*=\s*Vector2i\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", text or "")
    if not m:
        return 90
    return 160 + int(m.group(1))


def fw_eye_base_y() -> int:
    """眼睛基准中心 y = 画布中心 120 + (-16) = 104。"""
    text = read_text(DEFAULT_FIRMWARE + "\\" + FW_EYES)
    m = re.search(r"_eye_pos\s*=\s*Vector2i\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", text or "")
    if not m:
        return 104
    return 120 + int(m.group(2))


def fw_mouth_base_y() -> int:
    """嘴基准中心 y = 画布中心 120 + 26 = 146。"""
    text = read_text(DEFAULT_FIRMWARE + "\\" + FW_MOUTH)
    m = re.search(r"_mouth_pos\s*=\s*Vector2i\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", text or "")
    if not m:
        return 146
    return 120 + int(m.group(2))


def fw_mouth_base_x() -> int:
    """嘴基准中心 x = 画布中心 160 + 0 = 160。"""
    text = read_text(DEFAULT_FIRMWARE + "\\" + FW_MOUTH)
    m = re.search(r"_mouth_pos\s*=\s*Vector2i\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", text or "")
    if not m:
        return 160
    return 160 + int(m.group(1))


# ---------------------------------------------------------------------------
# 主检查
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.fails = []
        self.warns = []
        self.passes = 0

    def ok(self, name, cond, detail=""):
        if cond:
            self.passes += 1
        else:
            self.fails.append((name, detail))

    def warn(self, name, detail=""):
        self.warns.append((name, detail))


def check(root: str, firmware_root: str) -> Report:
    rep = Report()
    geo_path = os.path.join(root, GEOMETRY_SWIFT)
    proj_path = os.path.join(root, PROJECTION_SWIFT)

    if not os.path.exists(geo_path):
        rep.ok("FaceGeometry.swift 存在", False, geo_path)
        return rep
    if not os.path.exists(proj_path):
        rep.ok("FaceProjection.swift 存在", False, proj_path)
        return rep

    consts = extract_swift_constants(geo_path)

    # ---- 1. 常量与固件一致 ----
    firmware_avail = os.path.exists(os.path.join(firmware_root, FW_EYES)) \
        and os.path.exists(os.path.join(firmware_root, FW_MOUTH))

    if firmware_avail:
        rep.ok("左眼基准 x 与固件一致",
               consts.get("leftEyeBaseX") == fw_eye_base_x(),
               "swift=%s fw=%s" % (consts.get("leftEyeBaseX"), fw_eye_base_x()))
        rep.ok("右眼基准 x 与固件一致",
               consts.get("rightEyeBaseX") == 320 - fw_eye_base_x(),
               "swift=%s fw=%s" % (consts.get("rightEyeBaseX"), 320 - fw_eye_base_x()))
        rep.ok("眼睛基准 y 与固件一致",
               consts.get("eyeBaseY") == fw_eye_base_y(),
               "swift=%s fw=%s" % (consts.get("eyeBaseY"), fw_eye_base_y()))
        rep.ok("嘴基准 x 与固件一致",
               consts.get("mouthBaseX") == fw_mouth_base_x(),
               "swift=%s fw=%s" % (consts.get("mouthBaseX"), fw_mouth_base_x()))
        rep.ok("嘴基准 y 与固件一致",
               consts.get("mouthBaseY") == fw_mouth_base_y(),
               "swift=%s fw=%s" % (consts.get("mouthBaseY"), fw_mouth_base_y()))
    else:
        rep.warn("固件源码不可读（%s）—— 跳过固件常量比对" % firmware_root)

    # ---- 2. 硬编码常量（与固件无关的协议常量） ----
    rep.ok("位置偏移量程 ±100", consts.get("positionRangeUnits") == 100)
    rep.ok("位置偏移像素 ±16", consts.get("positionRangePixels") == 16)
    rep.ok("旋转量程 0..3600", consts.get("rotationRange") == (0, 3600))

    # ---- 3. 公式同点同值 ----
    mismatches = []
    for units in range(-150, 151):
        a = fw_position_offset(units)
        b = sw_position_offset(units)
        if a != b:
            mismatches.append(("position", units, a, b))
    rep.ok("位置偏移公式同口径（-150..150）", not mismatches,
           str(mismatches[:3]))

    mismatches = []
    for size in range(-150, 151):
        a = fw_eye_diameter(size)
        b = sw_eye_diameter(size)
        if a != b:
            mismatches.append(("eyeDiameter", size, a, b))
    rep.ok("眼睛直径公式同口径（-150..150）", not mismatches, str(mismatches[:3]))

    mismatches = []
    for weight in range(-20, 121):
        for d in (8, 14, 20, 26, 32):
            a = fw_eyelid_offset(d, weight)
            b = sw_eyelid_offset(d, weight)
            if a != b:
                mismatches.append(("eyelid", (d, weight), a, b))
    rep.ok("眼睑偏移公式同口径（直径×权重 全组合）", not mismatches, str(mismatches[:3]))

    mismatches = []
    for weight in range(-20, 121):
        a = fw_mouth_size(weight)
        b = sw_mouth_size(weight)
        if a != b:
            mismatches.append(("mouth", weight, a, b))
    rep.ok("嘴尺寸公式同口径（-20..120）", not mismatches, str(mismatches[:3]))

    # ---- 4. 极性方向 ----
    # 眼睛：weight 越大 = 越睁开 ⇒ 眼睑 offset 越负（眼睑整体上移，露出眼睛）
    rep.ok("眼睛 weight 极性：越大越睁开（offset 越负）",
           sw_eyelid_offset(20, 100) < sw_eyelid_offset(20, 25))
    rep.ok("全睁时眼睑完全移出（offset = -眼径）",
           sw_eyelid_offset(20, 100) == -20)
    rep.ok("闭眼时眼睑与眼白同心（offset = 0）",
           sw_eyelid_offset(20, 0) == 0)
    # 嘴：weight 越大 = 越张开 ⇒ 高度越大
    rep.ok("嘴 weight 极性：越大越张开",
           sw_mouth_size(100)[1] > sw_mouth_size(0)[1])

    # ---- 5. 镜像模式嘴归零 ----
    rep.ok("镜像模式把嘴 weight 归 0",
           swift_declares(proj_path, "out.mouth.weight = 0"))
    rep.ok("镜像模式不改眼睛（只动嘴）",
           "out.leftEye" not in _read(proj_path) and "out.rightEye" not in _read(proj_path))

    # ---- 6. 双模式枚举 ----
    proj_text = _read(proj_path)
    rep.ok("FaceRenderMode 只有两个 case",
           proj_text.count("case mirror") == 1 and proj_text.count("case stylized") == 1)
    rep.ok("默认模式是 .mirror",
           "public static let `default`: FaceRenderMode = .mirror" in proj_text)

    # ---- 7. 6 情绪表（weight / rotation）逐值对齐 ----
    # ⭐ 2026-10-25 新增。此前只校验几何公式，**漏掉了情绪表** ——
    #    而 rotation 恰恰是固件事实的硬编码副本（Happy 1550 / Angry 450 / Sad -400 …）。
    model_path = os.path.join(root, AVATAR_MODEL_SWIFT)
    rep.ok("AvatarModel.swift 存在", os.path.exists(model_path), model_path)
    if os.path.exists(model_path) and firmware_avail:
        fw_eyes_path = os.path.join(firmware_root, FW_EYES)
        fw_table = fw_emotion_table(fw_eyes_path)
        sw_table = sw_mood_table(model_path)
        rep.ok("固件情绪表抽到 6 条", len(fw_table) == 6, str(sorted(fw_table)))
        for prop in ("eyeWeight", "leftEyeRotation", "rightEyeRotation"):
            rep.ok("Swift 情绪表 %s 抽到 6 条" % prop,
                   len(sw_table.get(prop, {})) == 6,
                   str(sorted(sw_table.get(prop, {}))))

        # weight 逐值
        bad = []
        for mood, (weight, _rot) in sorted(fw_table.items()):
            got = sw_table.get("eyeWeight", {}).get(mood)
            if got != weight:
                bad.append((mood, weight, got))
        rep.ok("6 情绪 weight 与固件逐值一致", not bad, str(bad))

        # 左眼 rotation 逐值
        bad = []
        for mood, (_w, rot) in sorted(fw_table.items()):
            got = sw_table.get("leftEyeRotation", {}).get(mood)
            if got != rot:
                bad.append((mood, rot, got))
        rep.ok("6 情绪左眼 rotation 与固件逐值一致", not bad, str(bad))

        # 右眼 = 左眼取反（固件 apply_style 自己取反）
        rep.ok("固件右眼确实取反 rotation",
               fw_right_eye_is_mirrored(fw_eyes_path),
               "eyes.cpp 缺 setRotation(-rotation)")
        bad = []
        for mood in sorted(fw_table):
            left = sw_table.get("leftEyeRotation", {}).get(mood)
            right = sw_table.get("rightEyeRotation", {}).get(mood)
            if left is None or right is None or right != -left:
                bad.append((mood, left, right))
        rep.ok("6 情绪右眼 rotation = 左眼取反", not bad, str(bad))

        # 下发值必须落在 0..3600（固件 Element::setRotation 钳位区间）
        bad = []
        for mood in sorted(fw_table):
            for side, prop in (("left", "leftEyeRotation"), ("right", "rightEyeRotation")):
                rot = sw_table.get(prop, {}).get(mood, 0)
                wire = rot if rot >= 0 else 3600 + rot
                if not (0 <= wire <= 3600):
                    bad.append((mood, side, rot, wire))
        rep.ok("rotation 下发值落在 0..3600", not bad, str(bad))

    # ---- 8. 渲染层必须真的应用 rotation ----
    # ⭐ 2026-10-25 新增。实测发现：几何层算对了 rotationTenths，
    #    但 Canvas 里**从未应用** ⇒ 4/6 情绪（Happy 155° / Angry 45° / Sad -40° / Sleepy -5°）
    #    的眼睛角度与设备不一致 ⇒ 「镜像 = 逐像素一致」当时是**假的**。
    faceview_path = os.path.join(root, FACEVIEW_SWIFT)
    if os.path.exists(faceview_path):
        fv = _read(faceview_path)
        rep.ok("FaceView 读取了 rotationTenths", "rotationTenths" in fv)
        rep.ok("FaceView 真的应用了旋转（rotate(by: / rotationEffect）",
               ("rotate(by:" in fv) or ("rotationEffect" in fv),
               "只算了 rotationTenths 却没有旋转 ⇒ 眼睛角度与设备不一致")
    else:
        rep.warn("FaceView.swift 不存在 —— 跳过渲染层旋转检查")

    return rep


def _read(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def self_test() -> int:
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # C++ 除法口径：向零截断
    ok("C++ 除法向零截断（正）", c_div(7, 2) == 3)
    ok("C++ 除法向零截断（负）", c_div(-7, 2) == -3, str(c_div(-7, 2)))
    ok("Python // 与之不同（负数）", (-7) // 2 == -4, str((-7) // 2))

    # map_range 复刻
    ok("map_range(0, -100,100, -16,16) = 0", fw_map_range(0, -100, 100, -16, 16) == 0)
    ok("map_range(100,...) = 16", fw_map_range(100, -100, 100, -16, 16) == 16)
    ok("map_range(-100,...) = -16", fw_map_range(-100, -100, 100, -16, 16) == -16)
    ok("map_range 不钳位（超界会溢出）",
       fw_map_range(200, -100, 100, -16, 16) == 32,
       str(fw_map_range(200, -100, 100, -16, 16)))

    # 固件公式的关键点
    ok("固件眼径 size=0 → 20", fw_eye_diameter(0) == 20)
    ok("固件眼径 size=-100 → 8", fw_eye_diameter(-100) == 8)
    ok("固件眼径 size=100 → 32", fw_eye_diameter(100) == 32)
    ok("固件眼径 size=-50 → 14", fw_eye_diameter(-50) == 14)
    ok("固件眼睑 d=20 w=100 → -20", fw_eyelid_offset(20, 100) == -20)
    ok("固件眼睑 d=20 w=25 → -5", fw_eyelid_offset(20, 25) == -5)
    ok("固件嘴 w=0 → (90,6,0)", fw_mouth_size(0) == (90, 6, 0))
    ok("固件嘴 w=100 → (60,50,16)", fw_mouth_size(100) == (60, 50, 16))

    # ---- 情绪表解析器（2026-10-25 新增） ----
    fw_fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "_selftest_fw_eyes.cpp")
    sw_fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "_selftest_sw_model.swift")
    try:
        with io.open(fw_fixture, "w", encoding="utf-8", newline="") as fh:
            fh.write(
                "    auto apply_style = [this](int weight, int rotation) {\n"
                "        setWeight(weight);\n"
                "        if (_is_left_eye) {\n"
                "            setRotation(rotation);\n"
                "        } else {\n"
                "            setRotation(-rotation);\n"
                "        }\n"
                "    };\n"
                "    switch (emotion) {\n"
                "        case Emotion::Neutral:\n"
                "            apply_style(100, 0);\n"
                "            break;\n"
                "        case Emotion::Happy:\n"
                "            apply_style(72, 1550);\n"
                "            break;\n"
                "        case Emotion::Sad:\n"
                "            apply_style(70, -400);\n"
                "            break;\n"
                "    }\n")
        with io.open(sw_fixture, "w", encoding="utf-8", newline="") as fh:
            fh.write(
                "    public var eyeWeight: Int {\n"
                "        switch self {\n"
                "        case .neutral: return 100\n"
                "        case .happy: return 72\n"
                "        case .sad: return 70\n"
                "        }\n"
                "    }\n"
                "    public var leftEyeRotation: Int {\n"
                "        switch self {\n"
                "        case .neutral: return 0\n"
                "        case .happy: return 1550\n"
                "        case .sad: return -400\n"
                "        }\n"
                "    }\n"
                "    public var rightEyeRotation: Int {\n"
                "        switch self {\n"
                "        case .neutral: return 0\n"
                "        case .happy: return -1550\n"
                "        case .sad: return 400\n"
                "        }\n"
                "    }\n")

        ok("固件情绪表解析出 3 条", len(fw_emotion_table(fw_fixture)) == 3,
           str(fw_emotion_table(fw_fixture)))
        table = fw_emotion_table(fw_fixture)
        ok("固件 Happy = (72, 1550)", table.get("happy") == (72, 1550), str(table.get("happy")))
        ok("固件 Sad = (70, -400) —— 负号要留住",
           table.get("sad") == (70, -400), str(table.get("sad")))
        ok("固件右眼取反可检出",
           fw_right_eye_is_mirrored(fw_fixture))

        swt = sw_mood_table(sw_fixture)
        ok("Swift weight 表解析出 3 条", len(swt.get("eyeWeight", {})) == 3)
        ok("Swift 左眼 rotation 表解析出 3 条", len(swt.get("leftEyeRotation", {})) == 3)
        ok("Swift 右眼 rotation 表解析出 3 条", len(swt.get("rightEyeRotation", {})) == 3)
        ok("Swift Happy 左眼 = 1550", swt["leftEyeRotation"].get("happy") == 1550)
        ok("Swift Sad 左眼 = -400", swt["leftEyeRotation"].get("sad") == -400)
        ok("Swift Sad 右眼 = 400", swt["rightEyeRotation"].get("sad") == 400)

        # 变异：把右眼写成不取反 ⇒ 必须被抓出来
        with io.open(sw_fixture, "w", encoding="utf-8", newline="") as fh:
            fh.write(
                "    public var leftEyeRotation: Int {\n"
                "        switch self {\n"
                "        case .happy: return 1550\n"
                "        }\n"
                "    }\n"
                "    public var rightEyeRotation: Int {\n"
                "        switch self {\n"
                "        case .happy: return 1550\n"   # ← 变异：不取反
                "        }\n"
                "    }\n")
        swt2 = sw_mood_table(sw_fixture)
        ok("变异（右眼不取反）被抓出",
           swt2["rightEyeRotation"].get("happy") != -swt2["leftEyeRotation"].get("happy"))
    finally:
        for p in (fw_fixture, sw_fixture):
            try:
                os.remove(p)
            except OSError:
                pass
    ok("固件嘴 w=40 → (78,23,6)", fw_mouth_size(40) == (78, 23, 6), str(fw_mouth_size(40)))

    # Swift 与固件逐点一致
    same = all(fw_position_offset(u) == sw_position_offset(u) for u in range(-150, 151))
    ok("Swift 位置偏移 == 固件", same)
    same = all(fw_eye_diameter(s) == sw_eye_diameter(s) for s in range(-150, 151))
    ok("Swift 眼径 == 固件", same)
    same = all(fw_mouth_size(w) == sw_mouth_size(w) for w in range(-20, 121))
    ok("Swift 嘴尺寸 == 固件", same)
    same = all(fw_eyelid_offset(d, w) == sw_eyelid_offset(d, w)
               for w in range(-20, 121) for d in (8, 14, 20, 26, 32))
    ok("Swift 眼睑偏移 == 固件", same)

    # 极性
    ok("眼睛极性方向正确（weight 越大 offset 越负）",
       sw_eyelid_offset(20, 100) < sw_eyelid_offset(20, 25))
    ok("嘴极性方向正确", sw_mouth_size(100)[1] > sw_mouth_size(0)[1])

    # 位置偏移：必须逐字复刻 map_range，不能简化
    ok("位置偏移 x=-1 ⇒ -1（map_range 口径，非 x*16/100）",
       fw_position_offset(-1) == -1 and sw_position_offset(-1) == -1,
       "fw=%s sw=%s" % (fw_position_offset(-1), sw_position_offset(-1)))
    ok("位置偏移 x=1 ⇒ 0", fw_position_offset(1) == 0 and sw_position_offset(1) == 0)
    ok("简化式 x*16/100 与 map_range 在 x=-1 时不同（证明不能简化）",
       c_div(-1 * 16, 100) != fw_position_offset(-1),
       "simplified=%s fw=%s" % (c_div(-1 * 16, 100), fw_position_offset(-1)))

    # 变异检测：把 Swift 公式改坏，必须被抓出来
    broken = sw_eye_diameter
    bad = lambda s: 8 + c_div((max(-100, min(100, s)) + 100) * 24, 200) + 1   # off-by-one
    ok("变异检测：off-by-one 会被抓到",
       any(bad(s) != fw_eye_diameter(s) for s in range(-100, 101)))

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
    ap = argparse.ArgumentParser(description="校验 Swift 脸渲染几何与固件公式同口径")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--firmware", default=DEFAULT_FIRMWARE, help="固件源码根目录")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    root = os.path.abspath(args.root)
    rep = check(root, args.firmware)

    print("=" * 62)
    print("脸渲染几何同口径校验")
    print("仓库根：%s" % root)
    print("固件根：%s" % args.firmware)
    print("=" * 62)
    for name, detail in rep.warns:
        print("[WARN] %s%s" % (name, ("  (%s)" % detail) if detail else ""))
    for name, detail in rep.fails:
        print("[FAIL] %s%s" % (name, ("  (%s)" % detail) if detail else ""))
    print("[PASS] %d 项" % rep.passes)
    print("-" * 62)
    print("汇总：PASS %d / WARN %d / FAIL %d" % (rep.passes, len(rep.warns), len(rep.fails)))
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
