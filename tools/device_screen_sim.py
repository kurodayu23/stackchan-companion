#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备屏 320×240 仿真器 —— **严格按官方固件的几何与极性**逐像素渲染。

它不是「美术稿」，是**可与真机对拍的证据件**：每一个像素位置都能追到固件源码行。

几何/极性出处（官方固件，只读不 fork）：
    <fw>/stackchan/avatar/skins/default/default.cpp        面板 320×240 居中
    <fw>/stackchan/avatar/skins/default/eyes.cpp           眼：圆眼白 + 正方形眼睑
    <fw>/stackchan/avatar/skins/default/mouth.cpp          嘴：weight → 尺寸/圆角
    <fw>/stackchan/avatar/skins/default/speech_bubble.cpp   气泡：胶囊 + 箭头
    <fw>/apps/common/status_bar/status_bar.cpp             顶栏：Wi-Fi / 时间 / 电量
    <fw>/apps/common/toast/toast.cpp                       通知：顶部胶囊 + 堆叠
    <fw>/stackchan/modifiers/breath.h                      呼吸：正弦整体位移
    <fw>/stackchan/addons/neon_light/neon_light.cpp        12 灯（左 6 + 右 6）

用法：
    py -3.12 tools/device_screen_sim.py                 # 出全部图到 assets/screenshots/device-screen/
    py -3.12 tools/device_screen_sim.py --selftest      # 只跑判据（可作门禁）
    py -3.12 tools/device_screen_sim.py --self-test     # 同上；**门禁清单与 CI 用的规范写法**
    py -3.12 tools/device_screen_sim.py --measure       # 只打印测量，不出图

⭐ 官方几何的实测结论（判据全部锚定固件解析真值，见 §实测）：
   1. 眼睑是**容器内绝对定位**的正方形（eyes.cpp:68/77 的 setY(offset)），
      而眼白居中于 32×32 容器 ⇒ 两者**并不同心**。
      weight=0 时眼睑盖住眼白上部、露出**下缘月牙 25.2%**（不是四角）；
      weight=100 时眼睑整体上移出容器 ⇒ 眼睛**完全睁开**（露出 100%）。
      ⚠ 早期版本按「同心」建模，据此得出的「四角漏白 27.3%」是**错的**，已订正；
   2. 气泡容器底边在 y=246，气泡底边也在 y=246 —— **超出 240 屏高 6 px**；
      气泡最大宽 340 > 屏宽 320 ⇒ 左右各溢出 10 px。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    print("[FAIL] 需要 Pillow：py -3.12 -m pip install pillow", file=sys.stderr)
    raise

# ---------------------------------------------------------------------------
# 屏幕与颜色真值
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 320, 240          # default.cpp:15  _pannel->setSize(320, 240)
BG = (0, 0, 0)                          # default.cpp:18  setBgColor(secondaryColor) = 黑
FG = (255, 255, 255)                    # primaryColor = 白
PANEL_CX, PANEL_CY = SCREEN_W // 2, SCREEN_H // 2

# 官方 6 情绪 → (眼 weight, 眼 rotation[原始值, 0.1°])   eyes.cpp:102-123
EMOTIONS: Dict[str, Tuple[int, int]] = {
    "Neutral": (100, 0),
    "Happy":   (72, 1550),
    "Angry":   (70, 450),
    "Sad":     (70, -400),   # ⚠️ 存储被钳到 0，视觉用原始 -400（spec/06 §0.1 C-3）
    "Doubt":   (75, 0),
    "Sleepy":  (35, -50),
}

# eyes.cpp:12-16
EYE_SIZE_BASE = 16
EYE_POS = (-70, -16)
EYE_MIN_OFFSET = (-16, -16)
EYE_MAX_OFFSET = (16, 16)
EYE_SIZE_LIMIT = (8, 32)     # 眼白直径范围 8..32（eyes.cpp:16）
EYE_CONTAINER_SIZE = 32      # 眼容器 32×32（eyes.cpp:30），pivot (16,16) = 眼白圆心

# mouth.cpp:12-18
MOUTH_POS = (0, 26)
MOUTH_MIN_SIZE = (90, 6)
MOUTH_MAX_SIZE = (60, 50)
MOUTH_MIN_RADIUS = 0
MOUTH_MAX_RADIUS = 16

# speech_bubble.cpp:12-20
BUBBLE_CONTAINER_POS = (0, 89)
BUBBLE_CONTAINER_SIZE = (320, 74)
BUBBLE_ARROW_OFFSET = (40, -15)
BUBBLE_TEXT_MARGIN_X = 20
BUBBLE_MIN_WIDTH = 90
BUBBLE_MAX_WIDTH = 340
BUBBLE_HEIGHT = 52
BUBBLE_MIN_OFFSET_X = 66
BUBBLE_MAX_OFFSET_X = 0

# status_bar.cpp:101-129 / :203-230 / :232+
STATUS_BAR_FONT_PX = 16
BATTERY_BAR_W, BATTERY_BAR_H = 30, 12
BATTERY_NUB = 4

# toast.cpp:19-39
TOAST_COLORS: Dict[str, Tuple[int, int, int]] = {
    "info":    (0xE6F1FE, 0xAFD1F9, 0x005BC4),
    "warning": (0xFEFCE8, 0xDBD38B, 0xC4841D),
    "error":   (0xFEE7EF, 0xFCB5CD, 0xC20E4D),
    "success": (0xE8FAF0, 0xA2E8C1, 0x12A150),
    "orange":  (0xFFDCD1, 0xFFBFAA, 0xF84C13),
    "gray":    (0xFFFFFF, 0xD9D9D9, 0x11181C),
    "rose":    (0xFFE9F4, 0xFFBFDF, 0xFF339A),
    "dark":    (0x383838, 0x222222, 0xF4F3F3),
}
TOAST_OPEN_Y = 12
TOAST_OPEN_W = 296
TOAST_H = 60
TOAST_RADIUS = 18
TOAST_BORDER = 2

# breath.h:26  —— 官方默认
BREATH_AMPLITUDE = 16
BREATH_CYCLE_MS = 6600

# neon_light.cpp:81-97  —— 左 6 + 右 6 = 12
LED_COUNT_PER_SIDE = 6


# ---------------------------------------------------------------------------
# LVGL 语义复刻
# ---------------------------------------------------------------------------
def map_range(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> int:
    """LVGL / uitk 的 map_range：整数截断（向零）。"""
    if in_max == in_min:
        return int(out_min)
    scaled = (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return int(scaled)  # Python 的 int() 向零截断，与 C 一致


def eye_size_px(size: int) -> int:
    """eyes.cpp:137  眼白直径 = map(size, -100..100 → 8..32)。"""
    return map_range(size, -100, 100, EYE_SIZE_LIMIT[0], EYE_SIZE_LIMIT[1])


def eye_offset(position: Tuple[int, int]) -> Tuple[int, int]:
    """eyes.cpp:63-65  位置偏移 = map(pos, -100..100 → ±16)。"""
    return (
        map_range(position[0], -100, 100, EYE_MIN_OFFSET[0], EYE_MAX_OFFSET[0]),
        map_range(position[1], -100, 100, EYE_MIN_OFFSET[1], EYE_MAX_OFFSET[1]),
    )


def eyelid_offset_y(weight: int, size_px: int) -> int:
    """eyes.cpp:75  眼睑 y 偏移 = -(眼高 × weight / 100)，**向上为负**。

    ⇒ weight 越大越上移越睁；weight=0 时眼睑与眼白同心。
    """
    return -map_range(weight, 0, 100, 0, size_px)


def mouth_geometry(weight: int) -> Tuple[int, int, int]:
    """mouth.cpp:52-54  (宽, 高, 圆角)。"""
    w = map_range(weight, 0, 100, MOUTH_MIN_SIZE[0], MOUTH_MAX_SIZE[0])
    h = map_range(weight, 0, 100, MOUTH_MIN_SIZE[1], MOUTH_MAX_SIZE[1])
    r = map_range(weight, 0, 100, MOUTH_MIN_RADIUS, MOUTH_MAX_RADIUS)
    return w, h, r


def bubble_geometry(text_width: int) -> Tuple[int, int]:
    """speech_bubble.cpp:85-89  返回 (气泡宽, 气泡 x 偏移)。

    宽 = clamp(文字宽 + 40, 90, 340)；x 偏移 = map(宽, 90..340 → 66..0)
    ⇒ 短气泡偏右、长气泡居中。
    """
    w = min(text_width + BUBBLE_TEXT_MARGIN_X * 2, BUBBLE_MAX_WIDTH)
    w = max(w, BUBBLE_MIN_WIDTH)
    off_x = map_range(w, BUBBLE_MIN_WIDTH, BUBBLE_MAX_WIDTH, BUBBLE_MIN_OFFSET_X, BUBBLE_MAX_OFFSET_X)
    return w, off_x


def breath_offset(phase: float, amplitude: int = BREATH_AMPLITUDE) -> int:
    """breath.h:57-61  正弦整体上下位移（相位 0..1）。"""
    return int(math.sin(phase * 2.0 * math.pi) * amplitude)


# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------
_FONT_CANDIDATES = {
    16: [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"],
    20: [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"],
}
_font_cache: Dict[int, ImageFont.FreeTypeFont] = {}
# 注释用中文标签，需要中文字形；屏幕内文字仍用拉丁字体（官方 Montserrat）。
_LABEL_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]
_label_font_cache: Dict[int, ImageFont.FreeTypeFont] = {}


def get_label_font(px: int) -> ImageFont.FreeTypeFont:
    """图上注释的字体：中文标签必须用中文字体，否则会渲染成豆腐块。

    ⚠ 绝不能用它测屏幕内文字宽度 —— 官方是 Montserrat（拉丁），
    换中文字体会让气泡宽度测量偏大，DS-07 判据就废了。
    """
    if px in _label_font_cache:
        return _label_font_cache[px]
    for path in _LABEL_FONT_CANDIDATES:
        if os.path.exists(path):
            f = ImageFont.truetype(path, px)
            _label_font_cache[px] = f
            return f
    f = get_font(px)
    _label_font_cache[px] = f  # type: ignore[assignment]
    return f


def get_font(px: int) -> ImageFont.FreeTypeFont:
    """官方用 Montserrat 16 / 20（**只有拉丁字母**，固件零中文命中）。

    本机无 Montserrat，用 Arial 同磅值近似 —— 字宽偏差约 -5%（Arial 略窄）。
    """
    if px in _font_cache:
        return _font_cache[px]
    for path in _FONT_CANDIDATES.get(px, []):
        if os.path.exists(path):
            f = ImageFont.truetype(path, px)
            _font_cache[px] = f
            return f
    f = ImageFont.load_default()
    _font_cache[px] = f  # type: ignore[assignment]
    return f


def text_width(text: str, px: int) -> int:
    if not text:
        return 0
    font = get_font(px)
    return int(font.getbbox(text)[2] - font.getbbox(text)[0])


# ---------------------------------------------------------------------------
# 绘制原语
# ---------------------------------------------------------------------------
def _rotated_square(img: Image.Image, cx: float, cy: float, side: int, angle_deg: float,
                    fill: Tuple[int, int, int]) -> None:
    """正方形眼睑，绕 (cx,cy) 旋转 angle_deg。"""
    if side <= 0:
        return
    half = side / 2.0
    layer = Image.new("RGBA", (side * 3, side * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([side, side, side + side - 1, side + side - 1], fill=fill + (255,))
    layer = layer.rotate(-angle_deg, resample=Image.BICUBIC, center=(side + half, side + half))
    img.alpha_composite(layer, (int(cx - side * 1.5), int(cy - side * 1.5)))


def draw_eye(img: Image.Image, cx: float, cy: float, size_px: int, weight: int,
             angle_deg: float, color: Tuple[int, int, int] = FG) -> None:
    """眼睛 = 圆眼白 + 正方形眼睑（眼睑盖在上面）—— eyes.cpp:32-44。

    ⚠ 固件里眼睑是**容器内绝对定位**：align CENTER 之后 `setY(offset)`（eyes.cpp:68/77），
    而眼白居中于 32×32 容器 ⇒ 眼睑相对眼白圆心的位移 = offset - (容器-直径)/2。
    早期版本按「同心」建模，会让 weight=0 变成全闭眼 —— 与固件不符。
    """
    if size_px <= 0:
        return
    r = size_px / 2.0
    d = ImageDraw.Draw(img)
    # 眼白（圆）：与容器中心同心，也是整个眼睛的旋转枢轴（eyes.cpp:29）
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # 眼睑（正方形）：容器内绝对 y = offset ⇒ 相对眼白圆心的位移
    shift = eyelid_offset_y(weight, size_px) - (EYE_CONTAINER_SIZE - size_px) / 2.0
    _rotated_square(img, cx, cy + shift, size_px, angle_deg, BG)


def draw_mouth(img: Image.Image, cx: float, cy: float, weight: int,
               angle_deg: float = 0.0, color: Tuple[int, int, int] = FG) -> None:
    """嘴 = 圆角矩形，weight → 尺寸/圆角 —— mouth.cpp:20-31, 52-54。"""
    w, h, r = mouth_geometry(weight)
    if w <= 0 or h <= 0:
        return
    layer = Image.new("RGBA", (w + 4, h + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([2, 2, 2 + w - 1, 2 + h - 1], radius=r, fill=color + (255,))
    if angle_deg:
        layer = layer.rotate(-angle_deg, resample=Image.BICUBIC, center=(2 + w / 2, 2 + h / 2))
    img.alpha_composite(layer, (int(cx - w / 2 - 2), int(cy - h / 2 - 2)))


def draw_bubble(img: Image.Image, text: str, font_px: int = 16) -> Dict[str, int]:
    """官方气泡 —— speech_bubble.cpp。返回溢出测量。"""
    tw = text_width(text, font_px)
    bw, off_x = bubble_geometry(tw)
    ccx = PANEL_CX + BUBBLE_CONTAINER_POS[0]
    ccy = PANEL_CY + BUBBLE_CONTAINER_POS[1]
    bcx = ccx + off_x
    bcy = ccy + 11
    d = ImageDraw.Draw(img)

    # 箭头（指向脸的小三角）：官方是图片资源，这里用等效三角
    ax, ay = ccx + BUBBLE_ARROW_OFFSET[0], ccy + BUBBLE_ARROW_OFFSET[1]
    d.polygon([(ax - 7, ay + 5), (ax + 7, ay + 5), (ax, ay - 5)], fill=FG)

    # 气泡胶囊（LV_RADIUS_CIRCLE ⇒ 圆角 = 半高）
    x0, y0 = bcx - bw / 2, bcy - BUBBLE_HEIGHT / 2
    x1, y1 = bcx + bw / 2, bcy + BUBBLE_HEIGHT / 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=BUBBLE_HEIGHT / 2, fill=FG)

    # 文字（黑，居中）
    font = get_font(font_px)
    bbox = font.getbbox(text)
    d.text((bcx - (bbox[2] - bbox[0]) / 2 - bbox[0], bcy - (bbox[3] - bbox[1]) / 2 - bbox[1]),
           text, font=font, fill=BG)

    return {
        "text_width": tw,
        "bubble_width": bw,
        "bubble_left": int(round(x0)),
        "bubble_right": int(round(x1)),
        "bubble_top": int(round(y0)),
        "bubble_bottom": int(round(y1)),
        "overflow_left": max(0, int(-round(x0))),
        "overflow_right": max(0, int(round(x1) - SCREEN_W)),
        "overflow_bottom": max(0, int(round(y1) - SCREEN_H)),
    }


def draw_status_bar(img: Image.Image, time_text: str = "10:24 AM", battery: int = 86,
                    charging: bool = False, wifi: int = 3) -> None:
    """官方顶栏 —— status_bar.cpp。wifi: 0=无 1=低 2=中 3=高 4=断线。"""
    d = ImageDraw.Draw(img)
    font = get_font(STATUS_BAR_FONT_PX)

    # Wi-Fi 图标（左对齐 +11）
    wx, wy = 11, 10
    if wifi == 0:
        pass
    elif wifi == 4:
        d.line([(wx, wy + 10), (wx + 13, wy)], fill=FG, width=2)
    else:
        bars = {1: 1, 2: 2, 3: 3}[wifi]
        for i in range(3):
            h = 4 + i * 3
            if i < bars:
                d.rectangle([wx + i * 5, wy + 11 - h, wx + i * 5 + 3, wy + 11], fill=FG)
            else:
                d.rectangle([wx + i * 5, wy + 9, wx + i * 5 + 3, wy + 11], fill=(90, 90, 90))

    # 时间（居中）
    bbox = font.getbbox(time_text)
    d.text((PANEL_CX - (bbox[2] - bbox[0]) / 2 - bbox[0], 8 - bbox[1]),
           time_text, font=font, fill=FG)

    # 电量百分比（右 -41）
    pct = f"{battery}%"
    bbox = font.getbbox(pct)
    d.text((SCREEN_W - 41 - (bbox[2] - bbox[0]), 8 - bbox[1]), pct, font=font, fill=FG)

    # 电池图标（右 -7）：30×12 条 + 4×4 端子 + 1px 描边
    bx1 = SCREEN_W - 7
    bx0 = bx1 - BATTERY_BAR_W
    by0, by1 = 10, 10 + BATTERY_BAR_H
    d.rectangle([bx0, by0, bx1, by1], outline=FG, width=1)
    d.rectangle([bx1 + 1, by0 + 4, bx1 + 1 + BATTERY_NUB - 1, by1 - 4], outline=FG, width=1)
    fill_w = int((bx1 - bx0 - 2) * battery / 100)
    if fill_w > 0:
        color = (0x19, 0xC2, 0x5F) if charging else FG
        d.rectangle([bx0 + 1, by0 + 1, bx0 + 1 + fill_w, by1 - 1], fill=color)
    if charging:
        d.polygon([(bx0 + 13, by0 + 1), (bx0 + 9, by0 + 7), (bx0 + 13, by0 + 7),
                   (bx0 + 11, by0 + 11), (bx0 + 16, by0 + 5), (bx0 + 12, by0 + 5)],
                  fill=(0x19, 0xC2, 0x5F))


def draw_toast(img: Image.Image, msg: str, kind: str = "info") -> None:
    """官方 toast —— toast.cpp:65-92。"""
    bg, border, msgc = TOAST_COLORS.get(kind, TOAST_COLORS["info"])
    d = ImageDraw.Draw(img)
    x0 = PANEL_CX - TOAST_OPEN_W / 2
    y0 = TOAST_OPEN_Y
    d.rounded_rectangle([x0, y0, x0 + TOAST_OPEN_W, y0 + TOAST_H],
                        radius=TOAST_RADIUS, fill=bg, outline=border, width=TOAST_BORDER)
    font = get_font(20)
    bbox = font.getbbox(msg)
    d.text((PANEL_CX - (bbox[2] - bbox[0]) / 2 - bbox[0],
            y0 + TOAST_H / 2 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
           msg, font=font, fill=msgc)


# ---------------------------------------------------------------------------
# 组合
# ---------------------------------------------------------------------------
@dataclass
class FaceState:
    emotion: str = "Neutral"
    eye_weight: Optional[int] = None       # 覆盖情绪默认值
    eye_rotation_raw: Optional[int] = None
    eye_size: int = 0                      # -100..100
    eye_position: Tuple[int, int] = (0, 0)
    mouth_weight: int = 0
    breath_phase: float = 0.0
    show_bubble: str = ""
    bubble_font_px: int = 16
    show_toast: str = ""
    toast_kind: str = "info"
    show_status_bar: bool = False
    time_text: str = "10:24 AM"
    battery: int = 86
    charging: bool = False
    wifi: int = 3


def render_face(state: FaceState) -> Tuple[Image.Image, Dict[str, object]]:
    img = Image.new("RGBA", (SCREEN_W, SCREEN_H), BG + (255,))

    ew, erot = EMOTIONS.get(state.emotion, EMOTIONS["Neutral"])
    if state.eye_weight is not None:
        ew = state.eye_weight
    if state.eye_rotation_raw is not None:
        erot = state.eye_rotation_raw
    angle = erot / 10.0            # 0.1° → 度（原始值，spec/06 §0.1 C-3）

    size_px = eye_size_px(state.eye_size)
    off = eye_offset(state.eye_position)
    dy = breath_offset(state.breath_phase)

    # 眼（eyes.cpp:63-67）：左眼 x = EYE_POS.x + off.x；右眼镜像
    lx = PANEL_CX + EYE_POS[0] + off[0]
    rx = PANEL_CX - EYE_POS[0] - off[0]
    ey = PANEL_CY + EYE_POS[1] + off[1] + dy
    draw_eye(img, lx, ey, size_px, ew, angle)
    draw_eye(img, rx, ey, size_px, ew, -angle)     # eyes.cpp:93-99 右眼镜像

    # 嘴（mouth.cpp:42-45）
    moff = eye_offset(state.eye_position)
    mx = PANEL_CX + MOUTH_POS[0] + moff[0]
    my = PANEL_CY + MOUTH_POS[1] + moff[1] + dy
    draw_mouth(img, mx, my, state.mouth_weight)

    info: Dict[str, object] = {
        "eye_size_px": size_px,
        "eye_weight": ew,
        "eye_rotation_deg": angle,
        "eye_left_center": [lx, ey],
        "eye_right_center": [rx, ey],
        "mouth_center": [mx, my],
        "mouth_geometry": mouth_geometry(state.mouth_weight),
    }

    if state.show_bubble:
        info["bubble"] = draw_bubble(img, state.show_bubble, state.bubble_font_px)
    if state.show_toast:
        draw_toast(img, state.show_toast, state.toast_kind)
    if state.show_status_bar:
        draw_status_bar(img, state.time_text, state.battery, state.charging, state.wifi)
    return img.convert("RGB"), info


def face_coverage(img: Image.Image) -> float:
    """非背景像素占比（屏幕亮度 > 阈值）。用于判「脸占屏 ≥ 60%」。"""
    px = img.load()
    w, h = img.size
    lit = 0
    for y in range(h):
        for x in range(w):
            if px[x, y][0] > 24:
                lit += 1
    return lit / float(w * h)


def eyelid_leak(eye_size_px_: int, weight: int, model: str = "firmware") -> Dict[str, float]:
    """算「眼白被眼睑遮住后仍露出的比例」。

    固件真值（model="firmware"）：
        眼白 = 圆，半径 r，居中于 32×32 容器；
        眼睑 = 正方形，边长 = 眼白直径，**在容器内绝对定位** y = offset；
        ⇒ 眼睑只从上方压下来，露出的一定是**下缘月牙**，不会出现四角。
        盖板下边相对圆心 = shift + r，shift = offset - (32 - 直径)/2；
        露出帽高 h = -shift。

    model="concentric" 是**故意写错的旧模型**（眼睑以眼白圆心为基准平移），
    留着当负向对照：同一判据必须能把它判掉（见 DS-11）。
    """
    r = eye_size_px_ / 2.0
    circle_area = math.pi * r * r
    if model == "concentric":
        shift = float(eyelid_offset_y(weight, eye_size_px_))
    elif model == "firmware":
        shift = eyelid_offset_y(weight, eye_size_px_) - (EYE_CONTAINER_SIZE - eye_size_px_) / 2.0
    else:
        raise ValueError(f"unknown model: {model}")
    # 帽高 h = 盖板下边以上、圆顶以下的剩余高度
    h = -shift
    visible = _circle_cap_area(r, h)
    return {
        "model": model,
        "eye_size_px": float(eye_size_px_),
        "weight": float(weight),
        "shift_px": round(shift, 3),
        "circle_area": round(circle_area, 2),
        "leak_area_px": round(visible, 2),
        "leak_ratio": round(visible / circle_area, 4),
    }


def _circle_cap_area(r: float, h: float) -> float:
    """圆被水平切线切出的帽形面积（h = 帽高，0..2r）。"""
    if h <= 0:
        return 0.0
    if h >= 2 * r:
        return math.pi * r * r
    return r * r * math.acos((r - h) / r) - (r - h) * math.sqrt(max(0.0, 2 * r * h - h * h))


def _circle_band_covered(r: float, d: float) -> float:
    """（已废弃）同心模型的带状覆盖估算。

    保留只为让旧版判据可追溯：早期版本据此得出「四角漏白 27.3%」，
    那是**同心误模型**的结果，与固件的绝对定位不符，已由 eyelid_leak 取代。
    """
    if d <= 0:
        return math.pi * r * r
    if d >= r:
        return 0.0
    y0 = -(r - d)
    if y0 <= -r:
        return math.pi * r * r
    if y0 >= r:
        return 0.0

    def f(y: float) -> float:
        return 2.0 * math.sqrt(max(0.0, r * r - y * y))

    n = 4000
    h = (r - y0) / n
    total = 0.0
    for i in range(n):
        y = y0 + (i + 0.5) * h
        total += f(y) * h
    return total


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def out_dir(repo: Path) -> Path:
    return repo / "assets" / "screenshots" / "device-screen"


def save(img: Image.Image, path: Path, scale: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(path)


def build_sheet(tiles: List[Tuple[Image.Image, str]], cols: int, scale: int = 2,
                pad: int = 10, bg=(18, 18, 20)) -> Image.Image:
    """对照板：并排贴图 + 标题（**不是设备屏内容**，是给评审看的对照表）。"""
    tw, th = tiles[0][0].size
    rows = (len(tiles) + cols - 1) // cols
    cell_w, cell_h = tw * scale, th * scale
    label_h = 22
    W = cols * cell_w + (cols + 1) * pad
    H = rows * (cell_h + label_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(sheet)
    font = get_label_font(16)
    for i, (tile, title) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = pad + r * (cell_h + label_h + pad)
        sheet.paste(tile.resize((cell_w, cell_h), Image.NEAREST), (x, y))
        d.text((x + 2, y + cell_h + 3), title, font=font, fill=(235, 235, 235))
    return sheet


def render_all(repo: Path) -> Dict[str, object]:
    od = out_dir(repo)
    report: Dict[str, object] = {"files": [], "measurements": {}}

    # 1) 六情绪（纯设备屏）
    for name in EMOTIONS:
        img, info = render_face(FaceState(emotion=name))
        p = od / f"screen-emotion-{name.lower()}.png"
        save(img, p)
        report["files"].append(str(p.relative_to(repo)))
        report["measurements"][f"emotion_{name}"] = {
            **info,
            "face_coverage": round(face_coverage(img), 4),
        }

    # 2) 眼睑阶梯对照板 —— 回答 spec/06 §9.1 #2（未验证项）
    ladder_tiles = []
    for w in (0, 25, 50, 72, 100):
        img, info = render_face(FaceState(emotion="Neutral", eye_weight=w))
        leak = eyelid_leak(info["eye_size_px"], w)
        report["measurements"][f"eyelid_w{w}"] = leak
        ladder_tiles.append((img, f"weight={w}  漏白 {leak['leak_ratio']*100:.1f}%"))
    save(build_sheet(ladder_tiles, cols=5), od / "sheet-eyelid-ladder.png")
    report["files"].append("assets/screenshots/device-screen/sheet-eyelid-ladder.png")

    # 3) 气泡溢出
    bubble_cases = [
        ("Ok!", 16),
        ("Ready to Configure ~", 16),
        ("Done! Reboot in 3s.", 16),
        ("This is a very long sentence that will definitely overflow", 16),
    ]
    btiles = []
    for text, px in bubble_cases:
        img, info = render_face(FaceState(show_bubble=text, bubble_font_px=px))
        report["measurements"][f"bubble::{text[:24]}"] = info.get("bubble", {})
        btiles.append((img, f'"{text[:26]}"'))
    save(build_sheet(btiles, cols=4), od / "sheet-bubble-overflow.png")
    report["files"].append("assets/screenshots/device-screen/sheet-bubble-overflow.png")

    # 4) 完整屏态（顶栏 + 表情 + 气泡 / toast）
    combos = [
        (FaceState(emotion="Neutral", show_status_bar=True), "常态（顶栏 + 脸）"),
        (FaceState(emotion="Happy", show_status_bar=True, show_bubble="I'm back!"),
         "开心 + 气泡"),
        (FaceState(emotion="Neutral", show_status_bar=True, show_toast="Verifying...",
                   toast_kind="info"), "配网中（toast info）"),
        (FaceState(emotion="Neutral", show_status_bar=True, show_toast="Reboot in 3s.",
                   toast_kind="warning"), "升级（toast warning）"),
    ]
    ctiles = []
    for st, title in combos:
        img, _ = render_face(st)
        ctiles.append((img, title))
    save(build_sheet(ctiles, cols=4), od / "sheet-screen-states.png")
    report["files"].append("assets/screenshots/device-screen/sheet-screen-states.png")

    # 5) 呼吸相位
    rtiles = []
    for ph, label in ((0.0, "t=0s"), (0.25, "t=1.65s"), (0.5, "t=3.3s")):
        img, _ = render_face(FaceState(emotion="Neutral", breath_phase=ph, show_status_bar=True))
        rtiles.append((img, f"呼吸 {label}"))
    save(build_sheet(rtiles, cols=3), od / "sheet-breath.png")
    report["files"].append("assets/screenshots/device-screen/sheet-breath.png")

    # 6) 12 灯带对照板（物理灯带，不在屏上）
    strip = Image.new("RGB", (LED_COUNT_PER_SIDE * 2 * 30 + 30, 60), (12, 12, 14))
    sd = ImageDraw.Draw(strip)
    for i in range(LED_COUNT_PER_SIDE):
        sd.ellipse([10 + i * 30, 20, 34 + i * 30, 44], fill=(90, 90, 100))
    for i in range(LED_COUNT_PER_SIDE):
        sd.ellipse([10 + (LED_COUNT_PER_SIDE + i) * 30, 20, 34 + (LED_COUNT_PER_SIDE + i) * 30, 44],
                   fill=(90, 90, 100))
    save(strip, od / "sheet-led-strip.png")
    report["files"].append("assets/screenshots/device-screen/sheet-led-strip.png")

    return report


# ---------------------------------------------------------------------------
# 判据（自检 / 可作门禁）
# ---------------------------------------------------------------------------
def run_selftest() -> Tuple[bool, List[str]]:
    fails: List[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            fails.append(f"[FAIL] {name} {detail}")

    # DS-01 面板尺寸
    check("DS-01 面板 320×240", (SCREEN_W, SCREEN_H) == (320, 240))
    # DS-02 默认眼直径 = map(0) = 20
    check("DS-02 默认眼直径 20px", eye_size_px(0) == 20, f"got {eye_size_px(0)}")
    # DS-03 极性：weight↑ ⇒ 眼睑上移（越睁）。真值直接来自固件公式。
    off100 = eyelid_offset_y(100, 20)
    off0 = eyelid_offset_y(0, 20)
    check("DS-03 眼睑极性 weight↑ = 上移",
          off100 == -20 and off0 == 0 and off100 < off0,
          f"w100={off100} w0={off0}")
    # DS-04 weight=0 不是闭眼：固件绝对定位 ⇒ 露出下缘月牙 25.23%（解析真值）
    leak0 = eyelid_leak(20, 0)["leak_ratio"]
    check("DS-04 weight=0 露出下缘月牙 25.2%",
          abs(leak0 - 0.2523) < 0.02,
          f"leak={leak0} (解析真值 0.2523)")
    # DS-05 嘴 weight=0 是 90×6 细线
    check("DS-05 嘴 weight0 = 90×6", mouth_geometry(0)[:2] == (90, 6), f"got {mouth_geometry(0)}")
    # DS-06 气泡底边超出屏高
    img, info = render_face(FaceState(show_bubble="Ok!"))
    bub = info["bubble"]
    check("DS-06 气泡底边溢出 6px", bub["overflow_bottom"] == 6, f"got {bub['overflow_bottom']}")
    # DS-07 气泡最大宽 340 ⇒ 左右各溢出 10px
    img2, info2 = render_face(FaceState(show_bubble="x" * 60))
    bub2 = info2["bubble"]
    check("DS-07 气泡左右溢出", bub2["overflow_left"] >= 9 and bub2["overflow_right"] >= 9,
          f"L={bub2['overflow_left']} R={bub2['overflow_right']}")
    # DS-08 脸占屏比例：解析真值 =（两圆 2×π·10² + 嘴 90×6）/ (320×240) = 1.52%
    img3, _ = render_face(FaceState(emotion="Neutral"))
    cov = face_coverage(img3)
    cov_true = (2 * math.pi * 100 + 90 * 6) / (SCREEN_W * SCREEN_H)
    check("DS-08 脸占屏 ≈1.52%（屏全黑+小脸，非 30%/60%）",
          abs(cov - cov_true) < 0.004,
          f"cov={cov:.4f} 真值={cov_true:.4f}")
    # DS-09 眼距：两眼中心距 = 2×70 = 140
    _, i9 = render_face(FaceState(emotion="Neutral"))
    dist = i9["eye_right_center"][0] - i9["eye_left_center"][0]
    check("DS-09 两眼中心距 140", dist == 140, f"got {dist}")
    # DS-10 呼吸周期 6600ms = 0.151Hz（高于 HIG 敏感区 0.125Hz）⇒ 需修订
    hz = 1000.0 / BREATH_CYCLE_MS
    check("DS-10 呼吸 6600ms 确实 >0.125Hz（说明必须改）", hz > 0.125, f"{hz:.4f}Hz")
    # DS-11 极性单调不减：weight↑ ⇒ 眼睑上移 ⇒ 露出↑ ⇒ 越睁。
    # ⚠ 眼睑只有一格高（= 眼白直径）。眼白直径 20 px 时，
    #    h = int(weight/5) + 6 ≥ 2r = 20 ⇒ int(weight/5) ≥ 14 ⇒ **weight ≥ 70 即饱和 100%**。
    #    （实测扫描 0..100 的首次饱和点 = 70；早期注释写 74 是错的，已订正）
    #    之后露出饱和在 100%，所以只能要求「单调不减」而非「严格递增」。
    leaks = [eyelid_leak(20, w)["leak_ratio"] for w in (0, 25, 50, 75, 100)]
    check("DS-11 露出随 weight 单调不减（越睁）且末端完全睁开",
          all(leaks[i] <= leaks[i + 1] for i in range(len(leaks) - 1))
          and leaks[0] < 0.30 and leaks[-1] > 0.99,
          f"leaks={leaks}")
    # DS-12 负向对照：同心误模型必须被 DS-04 判据判掉 —— 否则判据对实现错误不敏感
    wrong = eyelid_leak(20, 0, model="concentric")["leak_ratio"]
    check("DS-12 同心误模型被 DS-04 判据拒绝",
          abs(wrong - 0.2523) >= 0.02,
          f"同心模型 leak={wrong}，与真值 0.2523 的差必须 ≥0.02 才算有分辨力")

    for f in fails:
        print(f)
    print(f"判定：{'全部通过' if not fails else f'{len(fails)} 条失败'}")
    return (not fails), fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="设备屏 320×240 仿真器（按官方固件几何逐像素渲染）")
    ap.add_argument("--repo", default=r"D:\jss18\AI\StackChan-main")
    # ⚠ `--self-test` 是**门禁清单与 CI 的规范写法**（tools/check_ci.py 的 CI-11/CI-12
    #   按这个字面量判定「脚本真支持」+「必须出现在 workflow 里」）。
    #   `--selftest` 保留为手敲时的历史别名，两者等价。
    ap.add_argument("--selftest", "--self-test", dest="selftest",
                    action="store_true", help="只跑判据（--self-test 为门禁规范写法）")
    ap.add_argument("--measure", action="store_true", help="只打印测量，不出图")
    args = ap.parse_args(argv)

    if args.selftest:
        ok, _ = run_selftest()
        return 0 if ok else 1

    repo = Path(args.repo)
    if args.measure:
        for name in EMOTIONS:
            _, info = render_face(FaceState(emotion=name))
            print(json.dumps({"emotion": name, **info}, ensure_ascii=False))
        for w in (0, 25, 50, 72, 100):
            print(json.dumps(eyelid_leak(20, w), ensure_ascii=False))
        _, bi = render_face(FaceState(show_bubble="Ok!"))
        print(json.dumps({"bubble": bi["bubble"]}, ensure_ascii=False))
        return 0

    report = render_all(repo)
    od = out_dir(repo)
    print(f"[OK] 输出目录 {od}")
    for f in report["files"]:
        print(f"  - {f}")
    print(json.dumps(report["measurements"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
