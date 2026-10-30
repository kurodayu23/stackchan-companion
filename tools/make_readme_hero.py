#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_readme_hero.py —— 生成 README 用的「小栈的脸」真实动图（GIF + 静帧 PNG）。

为什么要有它
------------
README 首页需要一张**一眼看懂产品在干嘛**的图。此前只有终端 ASCII 字符画
（`tools/demo_offline.py`），说服力不够 —— 而项目最硬的技术主张是
「**App 是设备脸的镜子**」，那就该直接放**设备脸上真实发生的那张脸**。

这份动图不是装饰：**每一帧都是真实关键帧渲染出来的**
（真实 TTS → 韵律提取 → 42 参数 → 关键帧 → 固件级几何 → 像素），
不是手画的动画。

几何口径（**与固件逐条对应，不另算一套比例**）
-------------------------------------------------
| 元素 | 固件出处 | 口径 |
|---|---|---|
| 画布 | `320x240`（设备屏） | 纯黑底 |
| 眼容器 | `eyes.cpp:21-27` | 32×32，`LV_ALIGN_CENTER`，transform pivot = 容器中心 (16,16) |
| 眼圆 | `eyes.cpp:134-137` | 直径 `map_range(size, -100, 100, 8, 32)`，白色（primaryColor） |
| 眼睑 | `eyes.cpp:37-44` + `73-77` | 与眼圆同尺寸的**方块**，**背景色**（黑）；`setY(-map_range(weight,0,100,0,眼径))` |
| 眼位 | `eyes.cpp:13,63-66` | 左 `(160-70+off, 120-16+off)`，右 `(160+70+off, …)` |
| 眼旋转 | `eyes.cpp:81-85` | 施加在**容器**上 ⇒ 眼白与眼睑**一起转**；右眼取反 |
| 嘴 | `mouth.cpp:14-18,41-54` | 宽 `map_range(w,0,100,90,60)`、高 `map_range(w,0,100,6,50)`、圆角 `map_range(w,0,100,0,16)` |
| 嘴位 | `mouth.cpp:14` | `(160+off, 120+26+off)` |

⚠️ **眼睑极性**：weight 越大 → 偏移越负 → 眼睑越往上 ⇒ **越睁开**（weight=0 全闭、100 全睁）。
这是最容易搞反的一条，`tools/check_face_geometry.py` 有同口径校验。

用法
----
    py -3.12 tools/make_readme_hero.py                    # 有 key 就用真实 TTS
    py -3.12 tools/make_readme_hero.py --provider stub    # 离线合成音
    py -3.12 tools/make_readme_hero.py --self-test        # 离线自检（CI 用）

产物（默认 `assets/hero/`）：
    stackchan-hero.gif   循环动图
    stackchan-hero.png   静帧（第一帧）
"""

from __future__ import annotations

import argparse
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

#: 设备画布（固件屏 320x240）
CANVAS_W, CANVAS_H = 320, 240
#: 设备原色（FaceStyle.DeviceFaceColors）：纯黑背景 + 纯白前景
BG = (0, 0, 0)
FG = (255, 255, 255)

DEFAULT_TEXT = "今天真开心啊！"
DEFAULT_EMOTION = "Happy"


# ---------------------------------------------------------------------------
# 几何：直接复用 check_face_geometry.py 的**固件复刻**（单一事实源）
# ---------------------------------------------------------------------------

def load_geometry():
    """导入 check_face_geometry 的几何函数。

    复用而不是复制 —— 因为那份已经过「同口径校验」：
    它逐条对过固件 `map_range` / C++ 整数除法 / 眼睑极性，
    复制一份就等于多一个可能漂移的副本。
    """
    import check_face_geometry as cfg
    return cfg


# ---------------------------------------------------------------------------
# 关键帧 → 像素
# ---------------------------------------------------------------------------

def render_face_frame(kf: dict, cfg, scale: int = 2) -> "Image.Image":
    """把一帧关键帧渲染成 PIL 图像（设备级像素，再按 scale 放大）。"""
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(canvas)

    # ---- 嘴（先画，眼在上层）----
    mo = kf["mouth"]
    mw, mh, mr = cfg.fw_mouth_size(int(mo["weight"]))
    mx = cfg.fw_mouth_base_x() + cfg.fw_position_offset(int(mo["x"]))
    my = cfg.fw_mouth_base_y() + cfg.fw_position_offset(int(mo["y"]))
    _rounded_rect(draw, mx - mw // 2, my - mh // 2, mw, mh, mr, FG)

    # ---- 眼（白圆 + 黑眼睑，整体按固件做旋转）----
    for side, key in (("left", "leftEye"), ("right", "rightEye")):
        el = kf[key]
        diameter = cfg.fw_eye_diameter(int(el.get("size", 0)))
        # weight 越大越睁开 ⇒ 偏移越负（眼睑往上）
        lid_offset = cfg.fw_eyelid_offset(diameter, int(el["weight"]))
        base_x = cfg.fw_eye_base_x() if side == "left" else (320 - cfg.fw_eye_base_x())
        cx = base_x + cfg.fw_position_offset(int(el["x"]))
        cy = cfg.fw_eye_base_y() + cfg.fw_position_offset(int(el["y"]))

        # 容器 32×32，pivot 在中心；眼白与眼睑都在容器里（一起转）
        cont = Image.new("RGB", (32, 32), BG)
        cd = ImageDraw.Draw(cont)
        r = diameter / 2.0
        cd.ellipse([16 - r, 16 - r, 16 + r - 1, 16 + r - 1], fill=FG)
        # 眼睑：与眼圆同尺寸的方块，向下偏移 lid_offset（负数 ⇒ 向上）
        cd.rectangle([16 - r, 16 - r + lid_offset, 16 + r - 1, 16 + r - 1 + lid_offset],
                     fill=BG)

        # 旋转：固件把 rotation 施加在容器上（眼白与眼睑一起转），单位 0.1 度
        rot = int(el.get("rotation", 0)) / 10.0
        if abs(rot) > 1e-6:
            cont = cont.rotate(rot, resample=Image.BICUBIC, center=(16, 16))

        canvas.paste(cont, (int(cx) - 16, int(cy) - 16))

    if scale != 1:
        canvas = canvas.resize((CANVAS_W * scale, CANVAS_H * scale), Image.NEAREST)
    return canvas


def _rounded_rect(draw, x, y, w, h, r, color):
    """LVGL 的圆角矩形。radius 会被 LVGL 限制为不超过 min(w,h)/2。"""
    from PIL import ImageDraw
    r = max(0, min(int(r), min(w, h) // 2))
    if r <= 0:
        draw.rectangle([x, y, x + w - 1, y + h - 1], fill=color)
        return
    draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=r, fill=color)


# ---------------------------------------------------------------------------
# 关键帧来源：真实 TTS → 韵律 → 关键帧
# ---------------------------------------------------------------------------

def build_keyframes(text: str, emotion: str, provider: str = "auto"):
    """产出关键帧序列。provider='tts' 用真实 MiniMax TTS；'stub' 用合成音。"""
    import numpy as np
    import prosody_to_motion as ptm

    sr = 16000
    if provider in ("auto", "tts"):
        try:
            import demo_offline
            # ⚠️ tts_minimax 返回 **(samples, meta)** 元组，不是裸数组
            #    （当数组用会报 "inhomogeneous shape"）
            samples, meta = demo_offline.tts_minimax(text)
            samples = np.asarray(samples, dtype=np.float32)
            if samples.ndim > 1:
                samples = samples.mean(axis=1)
            peak = float(np.max(np.abs(samples))) or 1.0
            samples = samples / peak * 0.9
            print("[hero] 真实 TTS：%s，%s s" % (meta.get("voice_id"), meta.get("duration_s")))
            return _compile(ptm, samples, sr, emotion), "tts"
        except Exception as exc:      # 无 key / 网络问题 ⇒ 降级到合成音
            if provider == "tts":
                raise
            print("[hero] 真实 TTS 不可用（%s），降级为离线合成音" % exc)

    samples = ptm._demo_signal(sr)
    return _compile(ptm, samples, sr, emotion), "stub"


def _compile(ptm, samples, sr, emotion):
    feat, track = ptm.extract_prosody(samples, sr)
    params = ptm.build_params(emotion, feat)
    kfs, _info = ptm.compile_keyframes(track, feat, params, emotion)
    return kfs


# ---------------------------------------------------------------------------
# 产物
# ---------------------------------------------------------------------------

def write_outputs(kfs, cfg, out_dir: str, scale: int, fps: int, max_frames: int):
    from PIL import Image

    os.makedirs(out_dir, exist_ok=True)
    frames = kfs[:max_frames] if max_frames > 0 else kfs
    imgs = [render_face_frame(kf, cfg, scale) for kf in frames]

    gif_path = os.path.join(out_dir, "stackchan-hero.gif")
    png_path = os.path.join(out_dir, "stackchan-hero.png")

    duration = int(round(1000.0 / max(1, fps)))
    imgs[0].save(gif_path, save_all=True, append_images=imgs[1:], loop=0,
                 duration=duration, optimize=True)
    imgs[0].save(png_path, "PNG", optimize=True)
    return gif_path, png_path, len(imgs), duration


# ---------------------------------------------------------------------------
# 自检（离线，不联网）
# ---------------------------------------------------------------------------

def self_test() -> int:
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    cfg = load_geometry()
    ok("几何模块可用", cfg is not None)

    # 眼睑极性：weight 越大越睁开（偏移越负）
    d = cfg.fw_eye_diameter(0)   # size=0 → 直径 20
    off_closed = cfg.fw_eyelid_offset(d, 0)
    off_open = cfg.fw_eyelid_offset(d, 100)
    ok("眼睑极性：weight=0 偏移为 0（全闭）", off_closed == 0, str(off_closed))
    ok("眼睑极性：weight=100 偏移为 -眼径（全睁）",
       off_open == -d, "%s vs %s" % (off_open, -d))

    # 基准位置
    ok("左眼基准 x=90", cfg.fw_eye_base_x() == 90, str(cfg.fw_eye_base_x()))
    ok("右眼基准 x=230", 320 - cfg.fw_eye_base_x() == 230, str(cfg.fw_eye_base_x()))
    ok("眼基准 y=104", cfg.fw_eye_base_y() == 104, str(cfg.fw_eye_base_y()))
    ok("嘴基准 (160,146)",
       cfg.fw_mouth_base_x() == 160 and cfg.fw_mouth_base_y() == 146,
       "%s,%s" % (cfg.fw_mouth_base_x(), cfg.fw_mouth_base_y()))

    # 渲染：闭眼 / 睁眼 / 张嘴 三帧，断言**画面真的不一样**
    import numpy as np
    import prosody_to_motion as ptm
    samples = ptm._demo_signal(16000)
    kfs = _compile(ptm, samples, 16000, DEFAULT_EMOTION)
    ok("关键帧序列非空", len(kfs) > 3, str(len(kfs)))

    imgs = [render_face_frame(kf, cfg, 2) for kf in kfs[:8]]
    ok("帧尺寸 = 画布×scale", imgs[0].size == (CANVAS_W * 2, CANVAS_H * 2),
       str(imgs[0].size))
    arrs = [np.asarray(im, dtype=np.int16) for im in imgs]
    diffs = [int(np.abs(a - b).sum()) for a, b in zip(arrs, arrs[1:])]
    ok("相邻帧有变化（不是静止图）", all(d > 0 for d in diffs), str(diffs[:5]))
    nonblack = int((arrs[0].sum(axis=2) > 0).sum())
    ok("画面里有前景像素（不是全黑）", nonblack > 100, str(nonblack))

    # 产物：真的写出来并能回读
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        gif, png, n, dur = write_outputs(kfs[:6], cfg, td, 2, 25, 6)
        ok("GIF 已生成", os.path.isfile(gif) and os.path.getsize(gif) > 0)
        ok("PNG 已生成", os.path.isfile(png) and os.path.getsize(png) > 0)
        from PIL import Image
        with Image.open(gif) as g:
            cnt = 0
            try:
                while True:
                    g.seek(cnt)
                    cnt += 1
            except EOFError:
                pass
        ok("GIF 可回读且帧数正确", cnt == n, "%d vs %d" % (cnt, n))

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
    ap = argparse.ArgumentParser(description="生成 README 用的小栈脸动图")
    ap.add_argument("--text", default=DEFAULT_TEXT, help="驱动动的台词")
    ap.add_argument("--emotion", default=DEFAULT_EMOTION, help="情绪（Happy/Neutral/…）")
    ap.add_argument("--provider", default="auto", choices=["auto", "tts", "stub"])
    ap.add_argument("--out", default=os.path.join("assets", "hero"), help="输出目录")
    ap.add_argument("--scale", type=int, default=2, help="放大倍数（2 ⇒ 640x480）")
    ap.add_argument("--fps", type=int, default=25, help="帧率（关键帧栅格 25 fps）")
    ap.add_argument("--max-frames", type=int, default=90, help="最多渲染多少帧")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    cfg = load_geometry()
    kfs, used = build_keyframes(args.text, args.emotion, args.provider)
    print("[hero] 关键帧 %d 帧（来源：%s，情绪：%s）" % (len(kfs), used, args.emotion))
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(
        os.path.dirname(HERE), args.out)
    gif, png, n, dur = write_outputs(kfs, cfg, out_dir, args.scale, args.fps,
                                     args.max_frames)
    print("[hero] 写出 %s（%d 帧 × %d ms）" % (gif, n, dur))
    print("[hero] 写出 %s" % png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
