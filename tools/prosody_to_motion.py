# -*- coding: utf-8 -*-
"""
prosody_to_motion.py —— 护城河②「韵律 → 身体」可运行原型

输入：TTS 下行 PCM（WAV，单声道）
输出：设备可直接收的 0x14 DanceSequence 关键帧序列（JSON 数组）+ 0x03 ControlAvatar

为什么信号源在服务端（54 号裁决）：
    服务端同时握有「用户上行 PCM」与「TTS 下行 PCM」。
    我们合成的语音，其韵律就是设备该表达的身体语言
    ⇒ 零固件改动 / 零 App 改动 / 零协议改动。

固件事实约束（全部实测自官方源码，非推测）：
    firmware/main/stackchan/json/json_helper.cpp:41-68  update_from_json
        0x03 ControlAvatar 只解析 3 元素 × 5 字段（共 15 key）：
        leftEye / rightEye / mouth ∈ {x,y,rotation,weight,size}
        speechBubble / visible / emotion / ignoreEmotion **都不被解析**
        任何未知 key **静默忽略** ⇒ 必须本地 schema 校验
        ⚠️ json_helper.cpp:18 —— x 与 y 必须**同时**是 int 才 setPosition
    firmware/main/hal/hal_ws_avatar.cpp:49-72  DataType 枚举
        ControlAvatar = 0x03；VideoModeOff = 0x13；DanceSequence = 0x14
    firmware/main/stackchan/json/json_helper.cpp:192-195
        0x14 DanceSequence 顶层**强制是数组**（`if (!doc.is<JsonArray>()) return`）
    firmware/main/stackchan/json/json_helper.cpp:201-224
        0x14 每帧读 8 个 key：leftEye/rightEye/mouth/yawServo/pitchServo/
        leftRgbColor/rightRgbColor/durationMs；servo 只认 angle + speed
    firmware/main/stackchan/avatar/avatar/elements/element.h:26-30 / :41-44
        x,y ∈ [-100,100]（setPosition）；rotation ∈ [0,3600]（setRotation，0.1 度）
    firmware/main/stackchan/avatar/avatar/elements/feature.h:22-25 / :36-39
        weight ∈ [0,100]（setWeight）；size ∈ [-100,100]（setSize）
    firmware/main/stackchan/avatar/skins/default/eyes.cpp:12-16 / :59-69
        眼位基准 (-70,-16)；偏移限幅 ±16 **像素**
        ⚠️ JSON 的 x/y ∈ [-100,100] 经 map_range 线性映射到 **像素 ±16**
        ⇒ JSON 16 实际只有 2.56 px（差 6.25 倍）
    firmware/main/hal/hal_servo.cpp:340 / :349  servo_init 的 angleLimit
        yaw   angleLimit = (-1280, 1280) → ±128.0°
        pitch angleLimit = (30, 870)     →  3.0° ~ 87.0°
    firmware/main/hal/hal_servo.cpp:86
        物理写入恒为 WritePos(id, pos, Time=20, Speed=0)
    firmware/main/stackchan/motion/servo.cpp:84-88 / :133-136
        moveWithSpeed(angle, speed) → moveWithSpringParams
        stiffness = 10 + (speed/1000)² × 640   （k_min=10, k_max=650）
        ⇒ JSON 的 speed 到不了舵机速度寄存器，**只能间接影响刚度**
    firmware/main/stackchan/motion/servo.cpp:141-142
        damping = 2√(m·k)  ⇒ 临界阻尼；ω=√k ⇒ 稳态时间常数 ≈ 4/ω
        speed=200→k=35.6→ω=5.97→≈670 ms；500→170/13.04/≈307 ms；800→419.6/20.48/≈195 ms
        ⇒ **头部实际是弹簧低通，比脸部滞后数百毫秒**
    firmware/main/stackchan/animation/animation.cpp:12-34 / :82-94
        Keyframe::apply() **绕过 modify lock**；脸部是**硬切无插值**
        但舵机走 moveWithSpeed → 弹簧 ⇒ **舵机不是硬切**
        Timeline::update() 每次只前进 1 帧且 _start_time = now（不累加）
        ⇒ 实际帧周期 = max(durationMs, 主循环周期)；主循环频率未取得
    firmware/main/stackchan/motion/servo.cpp:59-66
        静止 200 ms 后**自动释放扭矩**（舵机卸力）
    firmware/main/hal/hal_ws_avatar.cpp:146
        远端 WS 单帧上限 256 KB
    firmware/main/hal/utils/local_network/local_network_protocol.h:18
        LAN 单帧上限 65535 B（UINT16_MAX）

⭐ 眼睛 weight 的极性（**2026-10-24 复核更正，原实现反了**）：
    firmware/main/stackchan/avatar/skins/default/eyes.cpp:47  构造函数 setWeight(100)
    firmware/main/stackchan/avatar/skins/default/eyes.cpp:71-78
        _eyelid_offset_y = -map_range(_weight, 0, 100, 0, eyelid_height)
        ⇒ weight=100 ⇒ 眼睑上移一个身位 ⇒ **眼全开**；weight=0 ⇒ **全闭**
    firmware/main/stackchan/avatar/skins/default/eyes.cpp:103-122  官方情绪表
        Neutral=100 / Happy=72 / Angry=70 / Sad=70 / Doubt=75 / Sleepy=35
    ⇒ **weight 越大 = 越睁开**（嘴相反：weight 0=闭嘴，100=张嘴）
    ⇒ 本原型的情绪眼基线**直接采用官方情绪表**，不再自造

插值器选型（55 号）：
    舵机主插值 = PCHIP（单调三次 Hermite / Fritsch–Carlson）——保形不过冲
    脸部参数   = Catmull-Rom（必须钳位）
    落定/停顿  = cubic-bezier
    微动作     = smoothstep

已发表参数（引用 arXiv:2403.12670，非自定）：
    25 Hz 帧率 / Δt = 40 ms、320 ms 滑窗、8 Hz 5 阶 Butterworth 平滑

自研软限位（55 号，**不是固件事实**）：
    yaw 裕量 5.0°（落点 ≤ ±115.0°）；pitch 裕量 2.0°（落点 ∈ [5.0°, 85.0°]）

用法：
    py -3.12 tools/prosody_to_motion.py --self-test
    py -3.12 tools/prosody_to_motion.py --wav voice.wav --out kf.json --report r.md
    py -3.12 tools/prosody_to_motion.py --demo --out kf.json
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.io import wavfile
from scipy.signal import butter, filtfilt, find_peaks, medfilt

# ══════════════════════════════════════════════════════════════════════════
# 0. 固件事实常量（改这里 = 改对设备的认知，必须有 file:line 依据）
# ══════════════════════════════════════════════════════════════════════════

YAW_LIMIT_DEG = 128.0          # hal_servo.cpp:340  angleLimit (-1280, 1280)
PITCH_LIMIT_DEG = (3.0, 87.0)  # hal_servo.cpp:349  angleLimit (30, 870)

YAW_SOFT = 115.0                       # 55 号：软限位裕量 5.0°（**自研，非固件事实**）
PITCH_SOFT = (5.0, 85.0)               # 55 号：软限位裕量 2.0°（**自研，非固件事实**）

ELEMENT_XY = (-100, 100)
ROTATION_RANGE = (0, 3600)     # 0.1 度
WEIGHT_RANGE = (0, 100)
SIZE_RANGE = (-100, 100)

# 眼睛位置：JSON x/y ∈ [-100,100] 经 map_range 映射到 **像素 ±16**
# （eyes.cpp:12-16 常量、eyes.cpp:59-69 映射）⇒ JSON 16 实际只有 2.56 px
EYE_PX_MAX = 16.0
EYE_JSON_PER_PX = ELEMENT_XY[1] / EYE_PX_MAX   # 6.25

# 舵机速度通道上限
REMOTE_FRAME_MAX = 256 * 1024      # hal_ws_avatar.cpp:146
LAN_FRAME_MAX = 65535              # local_network_protocol.h:18  UINT16_MAX

AVATAR_ELEMENTS = ("leftEye", "rightEye", "mouth")
AVATAR_FIELDS = ("x", "y", "rotation", "weight", "size")
# 固件只解析这 15 个 key（3 元素 × 5 字段）。多一个都会被静默丢弃。
AVATAR_ALLOWED = {f"{e}.{f}" for e in AVATAR_ELEMENTS for f in AVATAR_FIELDS}

DANCE_FIELDS = {
    "leftEye", "rightEye", "mouth",
    "yawServo", "pitchServo",
    "leftRgbColor", "rightRgbColor",
    "durationMs",
}

# ── 输出帧率与滤波（arXiv:2403.12670） ─────────────────────────────────
OUT_FPS = 25
OUT_DT_MS = 40                  # 1000/25
ANALYSIS_HOP_MS = 10.0          # 100 Hz 分析
ANALYSIS_WIN_MS = 40.0
PITCH_SMOOTH_WIN_MS = 320.0     # 论文里的等效滑窗长度（频响等价参考）
PITCH_MEDIAN_POINTS = 5         # 实际用 5 点中值（50 ms）：只去抖，保留 200 ms 级重音
PITCH_LP_HZ = 8.0               # 8 Hz 5 阶 Butterworth（施加于 100 Hz 的 F0 轮廓）
PITCH_LP_ORDER = 5

F0_MIN, F0_MAX = 60.0, 400.0
YIN_THRESHOLD = 0.15
YIN_VOICED_MAX = 0.55

# ── 设备常量（4 个） ──────────────────────────────────────────────────
DEVICE_CONSTANTS = {
    "yawSoftLimit": YAW_SOFT,
    "pitchSoftMin": PITCH_SOFT[0],
    "pitchSoftMax": PITCH_SOFT[1],
    "yawPhysicalLimit": YAW_LIMIT_DEG,
}

# ══════════════════════════════════════════════════════════════════════════
# 1. 42 个参数（55 号：情绪基线 22 + 韵律调制 9 + 个性化 7 + 设备常量 4）
# ══════════════════════════════════════════════════════════════════════════

# 情绪基线 22 = 6 情绪 × 3 + 4 全局
#   pitch 单位度（⚠️ 舵机物理范围 3.0°~87.0°，软限位 5.0°~85.0°；
#   所有基线必须落在软限位内，否则会被钳位 ⇒ 情绪差异被吃掉）
#   ⚠️ pitch 角度语义（越大=抬得越高）**未经真机验证**，待接设备后校准
#
# ⭐ 眼睛 weight 极性（2026-10-24 复核更正）：**越大 = 越睁开**
#    eyes.cpp:47  构造函数 setWeight(100)（默认睁眼）
#    eyes.cpp:71-78  _eyelid_offset_y = -map_range(_weight, 0, 100, 0, eyelid_height)
#    ⇒ weight=100 眼睑上移一个身位（眼全开）；weight=0 全闭
#    下面的眼基线**直接取固件官方情绪表**（eyes.cpp:103-122），不自造
#    嘴相反：weight 0 = 闭嘴（细线 90x6, r=0），100 = 张嘴（大椭圆 60x50, r=16）
#    ⚠️ 固件**没有嘴部情绪表**（eyes.cpp 有、mouth.cpp 没有）⇒ 下面 6 个嘴基线是自设计值
EMOTION_BASELINE: Dict[str, float] = {
    "Neutral_eyeWeight": 100.0, "Neutral_mouthWeight": 30.0, "Neutral_pitch": 76.0,
    "Happy_eyeWeight": 72.0,    "Happy_mouthWeight": 52.0,   "Happy_pitch": 80.0,
    "Angry_eyeWeight": 70.0,    "Angry_mouthWeight": 22.0,   "Angry_pitch": 70.0,
    "Sad_eyeWeight": 70.0,      "Sad_mouthWeight": 20.0,     "Sad_pitch": 58.0,
    "Doubt_eyeWeight": 75.0,    "Doubt_mouthWeight": 26.0,   "Doubt_pitch": 72.0,
    "Sleepy_eyeWeight": 35.0,   "Sleepy_mouthWeight": 18.0,  "Sleepy_pitch": 52.0,
    # 4 个全局
    "eyeSize": 0.0,
    "yawBias": 0.0,
    "lightWarm": 0.55,
    "lightBright": 0.55,
}

# 韵律调制 9
PROSODY_MOD: Dict[str, float] = {
    "f0PitchGain": 0.55,       # F0 均值 → 俯仰基线（半音 → 度）
    "f0AccentNodGain": 7.5,    # F0 重音峰 → 点头幅度（度）
    "energyEyeGain": 0.30,     # 能量 → 眼睛 weight
    "energyLightGain": 0.45,   # 能量 → 灯亮度
    "rateTimeScale": 1.00,     # 语速 → 时间轴缩放（**不映射角度**）
    "pauseSettleGain": 6.0,    # 停顿 → 落定幅度
    "hnrSoftnessGain": 0.22,   # HNR → 眼睑柔和度
    "centroidWarmGain": 0.35,  # 谱质心 → 灯色冷暖
    "prosodyIntensity": 1.00,  # 总强度
}

# 个性化 7（用户可调，默认值）
PERSONAL_DEFAULTS: Dict[str, float] = {
    "gestureGain": 1.00,
    "expressiveness": 0.70,
    "blinkRate": 0.40,          # 每秒眨眼期望次数
    "idleAmount": 0.25,
    "lightBrightnessBias": 0.00,
    "colorWarmBias": 0.00,
    "gazeLead": 0.50,           # 目光领先于语音的程度
}

PARAM_COUNT_EXPECT = 22 + 9 + 7 + 4

# ── 项目已确认配色（浅色强调 #ff6d60 / 深色强调 #8fd3f4） ───────────────
COLOR_WARM = "#FF6D60"
COLOR_COOL = "#8FD3F4"

# ══════════════════════════════════════════════════════════════════════════
# 2. 韵律提取（7 维）
# ══════════════════════════════════════════════════════════════════════════

class ProsodyFeatures:
    """一整段语音的 7 维韵律特征 + 时间轴。"""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def as_dict(self) -> dict:
        keys = [
            "f0_mean_hz", "f0_mean_semitone_rel", "f0_accent_peak_semitone",
            "f0_accent_count", "energy_mean_dbfs", "energy_dynamic_db",
            "speech_rate_hz", "pause_total_ms", "pause_count",
            "longest_pause_ms", "hnr_mean_db", "centroid_mean_hz",
            "voiced_ratio", "duration_s",
        ]
        return {k: round(float(getattr(self, k)), 4) for k in keys}


def _frame_signal(x: np.ndarray, sr: int, win_ms: float, hop_ms: float):
    win = int(round(sr * win_ms / 1000.0))
    hop = int(round(sr * hop_ms / 1000.0))
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    n_frames = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = x[idx]
    return frames, win, hop


def _yin_frame(frame: np.ndarray, sr: int) -> Tuple[float, float, float]:
    """返回 (f0_hz, hnr_db, cmnd_min)。f0=0 表示未浊音。"""
    n = len(frame)
    size = 1
    while size < 2 * n:
        size <<= 1
    spec = np.fft.rfft(frame, size)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]

    tau_min = max(2, int(sr / F0_MAX))
    tau_max = min(n - 1, int(sr / F0_MIN))
    if tau_max <= tau_min:
        return 0.0, 0.0, 1.0

    x2 = frame.astype(np.float64) ** 2
    energy = x2.sum()
    if energy <= 1e-12:
        return 0.0, 0.0, 1.0
    # suffix[k] = sum(x2[k:])，length N+1，suffix[N] = 0
    suffix = np.concatenate((np.cumsum(x2[::-1])[::-1], [0.0]))
    # head[τ] = sum(x2[0:τ])，length N+1
    head = np.concatenate(([0.0], np.cumsum(x2)))

    taus = np.arange(0, tau_max + 1)
    # d(τ) = Σ_{j=0..N-1-τ} (x[j]-x[j+τ])² = S1 + S2 - 2·S3
    s1 = energy - suffix[n - taus]   # Σ x[j]² ,  j=0..N-1-τ
    s2 = energy - head[taus]         # Σ x[j+τ]², j=0..N-1-τ
    s3 = ac[taus]                    # Σ x[j]·x[j+τ]
    diff = s1 + s2 - 2.0 * s3
    diff = np.maximum(diff, 0.0)
    diff[0] = 0.0

    cmnd = np.ones_like(diff)
    cs = np.cumsum(diff)
    idx = np.arange(1, tau_max + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cmnd[1:] = np.where(cs[1:] > 0, diff[1:] * idx / cs[1:], 1.0)

    seg = cmnd[tau_min:tau_max + 1]
    below = np.where(seg < YIN_THRESHOLD)[0]
    if len(below):
        tau = tau_min + int(below[0])
        while tau > tau_min and cmnd[tau] > cmnd[tau - 1]:
            tau -= 1
    else:
        tau = tau_min + int(np.argmin(seg))
        if cmnd[tau] > YIN_VOICED_MAX:
            return 0.0, 0.0, float(cmnd[tau])

    cm = float(cmnd[tau])
    hnr = 10.0 * math.log10(max(1.0 - cm, 1e-6) / max(cm, 1e-6))

    shift = 0.0
    if 0 < tau < len(cmnd) - 1:
        a, b, c = cmnd[tau - 1], cmnd[tau], cmnd[tau + 1]
        den = a - 2.0 * b + c
        if abs(den) > 1e-12:
            shift = 0.5 * (a - c) / den
    tau_ref = tau + shift
    if tau_ref <= 0:
        return 0.0, hnr, cm
    f0 = sr / tau_ref
    if not (F0_MIN <= f0 <= F0_MAX):
        return 0.0, hnr, cm
    return f0, hnr, cm


def extract_prosody(samples: np.ndarray, sr: int) -> Tuple[ProsodyFeatures, dict]:
    """从 PCM 提取 7 维韵律 + 时间轴。

    返回 (features, track)；track 含逐帧数组，供关键帧编译器使用。
    """
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 1.5:            # 16-bit 整数残留
        x = x / 32768.0
    elif peak > 1.0:
        x = x / peak
    x = np.clip(x, -1.0, 1.0)

    # 预加重
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])

    frames, win, hop = _frame_signal(x, sr, ANALYSIS_WIN_MS, ANALYSIS_HOP_MS)
    hop_sec = hop / float(sr)
    times = (np.arange(len(frames)) * hop + win / 2.0) / sr

    n = len(frames)
    f0 = np.zeros(n)
    hnr = np.zeros(n)
    energy = np.zeros(n)
    centroid = np.zeros(n)
    cmnd_min = np.ones(n)

    hamming = np.hamming(win)
    freqs = np.fft.rfftfreq(win, 1.0 / sr)

    for i in range(n):
        fr = frames[i]
        rms = float(np.sqrt(np.mean(fr ** 2)))
        energy[i] = 20.0 * math.log10(rms + 1e-12)
        sp = np.abs(np.fft.rfft(fr * hamming))
        tot = sp.sum()
        centroid[i] = float((sp * freqs).sum() / tot) if tot > 1e-12 else 0.0
        f, h, cm = _yin_frame(fr, sr)
        f0[i] = f
        hnr[i] = h
        cmnd_min[i] = cm

    # ── F0 中值滤波 + 8 Hz 5 阶 Butterworth（arXiv:2403.12670） ────────
    # ⚠️ 未浊音帧必须先插值填掉再滤波：直接对含 0 的数组做 medfilt/Butterworth
    #    会把中位数与滤波状态一起污染（实测导致 F0 掉到 0.007 Hz）。
    # ⚠️⚠️ Butterworth 的归一化截止频率必须用**帧率**（100 Hz），不是音频采样率（16 kHz）。
    #    误用 16000 时归一化截止 = 0.001 ⇒ 截止 0.08 Hz ⇒ 滤波时间常数 > 整段时长
    #    ⇒ 输出恒等于全段直流（F0 全变成一个值）。已实测复现。
    voiced = f0 > 0
    f0_log = np.full(n, np.nan)
    f0_log[voiced] = np.log2(np.maximum(f0[voiced], 1e-6))
    idx_all = np.arange(n)
    if voiced.any():
        f0_fill = np.interp(idx_all, idx_all[voiced], f0_log[voiced])
    else:
        f0_fill = np.zeros(n)
    # 中值窗口 5 点（50 ms）—— 只去抖，不抹掉 200 ms 级的重音峰
    k = PITCH_MEDIAN_POINTS
    if len(f0_fill) >= k:
        f0_fill = medfilt(f0_fill, k)
    frame_rate = 1.0 / hop_sec          # F0 轮廓的采样率 = 100 Hz
    b, a = butter(PITCH_LP_ORDER, PITCH_LP_HZ / (frame_rate / 2.0), btype="low")
    if len(f0_fill) > 3 * len(a):
        f0_fill = filtfilt(b, a, f0_fill)
    f0_smooth = np.where(voiced, np.exp2(f0_fill), 0.0)

    # ── VAD ────────────────────────────────────────────────────────────
    noise_floor = float(np.percentile(energy, 10))
    speech_thr = max(noise_floor + 8.0, -50.0)
    voiced_mask = voiced & (energy > speech_thr)
    if voiced_mask.any():
        voiced_mask = medfilt(voiced_mask.astype(np.float64), 3) > 0.5

    # ── 静音段（停顿） ─────────────────────────────────────────────────
    voiced_idx = np.where(voiced_mask)[0]
    pauses: List[Tuple[float, float]] = []
    if len(voiced_idx):
        gaps = np.diff(voiced_idx)
        for g_i, gap in enumerate(gaps):
            if gap > 1:
                t0 = times[voiced_idx[g_i] + 1]
                t1 = times[voiced_idx[g_i + 1]]
                if (t1 - t0) >= 0.12:
                    pauses.append((float(t0), float(t1)))
        if voiced_idx[0] > 0:
            t0 = 0.0
            t1 = times[voiced_idx[0]]
            if t1 - t0 >= 0.20:
                pauses.append((float(t0), float(t1)))
        if voiced_idx[-1] < n - 1:
            t0 = times[voiced_idx[-1]]
            t1 = float(times[-1])
            if t1 - t0 >= 0.20:
                pauses.append((float(t0), float(t1)))

    # ── 重音峰（F0 半音相对中位数） ─────────────────────────────────────
    rel = np.full(n, np.nan)
    if voiced.any():
        med = float(np.median(f0_smooth[voiced]))
        rel[voiced] = 12.0 * np.log2(np.maximum(f0_smooth[voiced], 1e-6) / max(med, 1e-6))
    rel_filled = rel.copy()
    if np.isnan(rel_filled).any():
        valid = np.where(~np.isnan(rel_filled))[0]
        if len(valid):
            rel_filled = np.interp(np.arange(n), valid, rel_filled[valid])
        else:
            rel_filled = np.zeros(n)
    accent_peaks, _ = find_peaks(rel_filled, prominence=1.5,
                                  distance=max(1, int(round(0.15 / hop_sec))))
    accent_peaks = accent_peaks[rel_filled[accent_peaks] > 1.0] if len(accent_peaks) else accent_peaks

    # ── 语速代理（能量包络峰计数 / 浊音时长） ───────────────────────────
    env = energy.copy()
    k_env = max(3, int(round(0.050 / hop_sec)))
    # ⚠️ 边界必须**复制**而不是补零：env 是 dB 域（负值），
    #    `mode="same"` 的补零等于把首尾往 0 dB 拉 ⇒ 凭空造出 ~7~12 dB 的
    #    假能量峰 ⇒ 每句话第 1 帧的 e_norm 饱和到 1.0，
    #    嘴/眼/灯在第一帧被推到满量程（实测，见 docs/research/87）。
    #    edge replicate 的语义 = 「信号在 t=0 之前是恒定的」，内部逐点与 `same` 一致。
    env_pad = np.pad(env, (k_env // 2, k_env - 1 - k_env // 2), mode="edge")
    env_smooth = np.convolve(env_pad, np.ones(k_env) / k_env, mode="valid")
    pk, _ = find_peaks(env_smooth, distance=max(1, int(round(0.12 / hop_sec))),
                       prominence=3.0)
    voiced_dur = float(voiced_mask.sum() * hop_sec)
    speech_rate = float(len(pk) / voiced_dur) if voiced_dur > 0.05 else 0.0

    # F0 中位参考 = 220 Hz（典型会话基频）；相对值驱动俯仰基线
    F0_REF_HZ = 220.0
    e_lo = float(np.percentile(energy[voiced_mask], 5)) if voiced_mask.any() else float(np.percentile(energy, 5))
    e_hi = float(np.percentile(energy[voiced_mask], 95)) if voiced_mask.any() else float(np.percentile(energy, 95))

    feat = ProsodyFeatures(
        f0_mean_hz=float(np.median(f0_smooth[voiced])) if voiced.any() else 0.0,
        f0_mean_semitone_rel=0.0,
        f0_accent_peak_semitone=float(np.max(rel_filled[accent_peaks])) if len(accent_peaks) else 0.0,
        f0_accent_count=int(len(accent_peaks)),
        energy_mean_dbfs=float(np.mean(energy[voiced_mask])) if voiced_mask.any() else float(np.mean(energy)),
        energy_dynamic_db=float(e_hi - e_lo),
        speech_rate_hz=speech_rate,
        pause_total_ms=float(sum((b - a) * 1000.0 for a, b in pauses)),
        pause_count=len(pauses),
        longest_pause_ms=float(max(((b - a) * 1000.0 for a, b in pauses), default=0.0)),
        hnr_mean_db=float(np.mean(hnr[voiced])) if voiced.any() else 0.0,
        centroid_mean_hz=float(np.mean(centroid[voiced_mask])) if voiced_mask.any() else float(np.mean(centroid)),
        voiced_ratio=float(voiced_mask.mean()),
        duration_s=float(len(x) / sr),
    )
    if voiced.any():
        feat.f0_mean_semitone_rel = float(
            12.0 * math.log2(max(feat.f0_mean_hz, 1e-6) / F0_REF_HZ))

    track = dict(
        times=times, f0=f0_smooth, f0_rel=rel_filled, energy=energy, env=env_smooth,
        hnr=hnr, centroid=centroid, voiced=voiced_mask,
        pauses=pauses, accents=[float(times[i]) for i in accent_peaks],
        accent_strength=[float(rel_filled[i]) for i in accent_peaks],
        syllables=[float(times[i]) for i in pk],
        hop_s=hop_sec, sr=sr, n=n,
    )
    return feat, track


# ══════════════════════════════════════════════════════════════════════════
# 3. Oklab 颜色插值（CSS Color 4 §13.5：H 通道必须显式 shortest / longer）
# ══════════════════════════════════════════════════════════════════════════

def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def hex_to_oklab(h: str) -> np.ndarray:
    h = h.lstrip("#")
    rgb = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    lin = _srgb_to_linear(rgb)
    lms = np.cbrt(_M1 @ lin)
    return _M2 @ lms


def oklab_to_hex(lab: np.ndarray) -> str:
    lms = np.clip(lab, 0.0, None) ** 3
    lin = np.linalg.solve(_M2, lms)
    rgb = np.clip(_linear_to_srgb(lin), 0.0, 1.0)
    return "#" + "".join("%02X" % int(round(v * 255)) for v in rgb)


def mix_oklab(a: str, b: str, t: float) -> str:
    t = float(np.clip(t, 0.0, 1.0))
    return oklab_to_hex(hex_to_oklab(a) * (1.0 - t) + hex_to_oklab(b) * t)


# ══════════════════════════════════════════════════════════════════════════
# 4. 参数装配（42 个标量）
# ══════════════════════════════════════════════════════════════════════════

def build_params(emotion: str, feat: ProsodyFeatures,
                 personal: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    personal = dict(PERSONAL_DEFAULTS, **(personal or {}))
    p: Dict[str, float] = {}
    p.update(EMOTION_BASELINE)
    p.update(PROSODY_MOD)
    p.update(personal)
    p.update(DEVICE_CONSTANTS)
    p["_emotion"] = emotion
    p["_paramCount"] = PARAM_COUNT_EXPECT
    return p


# ══════════════════════════════════════════════════════════════════════════
# 5. 关键帧编译器：韵律 → 语义锚点 → PCHIP → 密集 0x14 关键帧
# ══════════════════════════════════════════════════════════════════════════

def _clamp(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


def _interp_anchors(times: np.ndarray, vals: np.ndarray,
                    query: np.ndarray) -> np.ndarray:
    """PCHIP 插值（保形不过冲）；节点不足时退化为最近邻/线性。"""
    if len(times) == 0:
        return np.zeros_like(query)
    if len(times) == 1:
        return np.full_like(query, vals[0])
    order = np.argsort(times)
    t = np.asarray(times)[order].astype(float)
    v = np.asarray(vals)[order].astype(float)
    # 去重时间点
    keep = np.concatenate(([True], np.diff(t) > 1e-6))
    t, v = t[keep], v[keep]
    if len(t) == 1:
        return np.full_like(query, v[0])
    q = np.clip(np.asarray(query, dtype=float), t[0], t[-1])
    return PchipInterpolator(t, v, extrapolate=False)(q)


def compile_keyframes(track: dict, feat: ProsodyFeatures, p: Dict[str, float],
                       emotion: str = "Neutral") -> Tuple[List[dict], dict]:
    """把韵律编译成设备可直接收的 0x14 关键帧序列。

    返回 (关键帧列表, 编译信息)。信息里含锚点统计，供自检验证
    「语速只映射时间轴、不映射角度」。
    """
    dur = feat.duration_s
    n_out = max(1, int(math.ceil(dur * OUT_FPS)))
    out_t = np.arange(n_out) * (1.0 / OUT_FPS)
    last_t = float(out_t[-1])

    base_eye = p[f"{emotion}_eyeWeight"]
    base_mouth = p[f"{emotion}_mouthWeight"]
    base_pitch = p[f"{emotion}_pitch"]
    gain = p["gestureGain"] * p["expressiveness"] * p["prosodyIntensity"]

    # ── 语义锚点（结构轴：yaw / pitch / eyeWeight） ─────────────────────
    anchor_t: List[float] = [0.0]
    anchor_yaw: List[float] = [p["yawBias"]]
    anchor_pitch: List[float] = [base_pitch]
    anchor_eye: List[float] = [base_eye]

    # 停顿 = 落定（不是「不动」）：头部缓缓回到中位、眼神放松
    for (t0, t1) in track["pauses"]:
        mid = 0.5 * (t0 + t1)
        settle_pitch = _clamp(base_pitch + p["pauseSettleGain"] * 0.5,
                              PITCH_SOFT[0], PITCH_SOFT[1])
        anchor_t.append(max(0.0, mid - 0.12))
        anchor_yaw.append(p["yawBias"] * 0.5)
        anchor_pitch.append(settle_pitch)
        anchor_eye.append(_clamp(base_eye - p["hnrSoftnessGain"] * 20.0, *WEIGHT_RANGE))
        anchor_t.append(min(last_t, mid + 0.12))
        anchor_yaw.append(p["yawBias"])
        anchor_pitch.append(base_pitch)
        anchor_eye.append(base_eye)

    # 重音峰 = 点头（pitch 变小 = 低头），同时眼神更用力
    accent_nod: List[Tuple[float, float]] = []
    for t_ac, strength in zip(track["accents"], track["accent_strength"]):
        nod = _clamp(base_pitch - p["f0AccentNodGain"] * gain * min(strength / 3.0, 2.0),
                     PITCH_SOFT[0], PITCH_SOFT[1])
        yaw_jit = _clamp(p["yawBias"] + 4.0 * math.sin(t_ac * 7.0) * gain,
                         -YAW_SOFT, YAW_SOFT)
        anchor_t.append(float(t_ac))
        anchor_yaw.append(yaw_jit)
        anchor_pitch.append(nod)
        anchor_eye.append(_clamp(base_eye + p["energyEyeGain"] * 30.0 * gain, *WEIGHT_RANGE))
        accent_nod.append((float(t_ac), nod))

    # ── 语速 → **只压缩时间轴**（角度值一律不变） ──────────────────────
    # 语义（55 号）：语速只映射时间轴缩放，**不映射角度**。
    # 实现：锚点时刻整体按 `1 / rateTimeScale` 压缩 ⇒ 同样的动作、同样的角度，
    #       但更早到达；音频总时长不变（末尾保持最后姿态）⇒ 不失同步。
    # ⚠️ 2026-10-24 复核更正：旧实现用「音节微锚点」表达语速，
    #    那个微锚点带非中性 pitch ⇒ **实际改了角度**，与文档/自检的断言矛盾。
    #    现改为纯时间压缩，锚点的 pitch/yaw/eye **一个值都不变**。
    time_scale = 1.0 / max(0.25, p["rateTimeScale"])

    # 收尾回到中性
    anchor_t.append(last_t)
    anchor_yaw.append(p["yawBias"])
    anchor_pitch.append(base_pitch)
    anchor_eye.append(base_eye)

    at = np.asarray(anchor_t, dtype=float) * time_scale
    ayaw = np.asarray(anchor_yaw, dtype=float)
    apitch = np.asarray(anchor_pitch, dtype=float)
    aeye = np.asarray(anchor_eye, dtype=float)

    yaw = _interp_anchors(at, ayaw, out_t)
    pitch = _interp_anchors(at, apitch, out_t)
    eye_w = _interp_anchors(at, aeye, out_t)

    # 缓慢「张望」漂移：音频只给强度/音高，不给方向
    # ⇒ yaw 的方向感只能来自缓慢漂移 + 重音抖动，且幅度必须克制
    drift = 3.0 * p["expressiveness"] * np.sin(2.0 * np.pi * out_t / 2.5 + 0.7)
    yaw = yaw + drift

    # F0 均值 → 俯仰基线偏移（半音 → 度）
    pitch = pitch + p["f0PitchGain"] * feat.f0_mean_semitone_rel * gain

    # ── 眨眼（0x14 绕过 modify lock ⇒ 设备自眨眼会被我们盖掉，必须自己排） ──
    blink_rate = max(0.05, p["blinkRate"])
    n_blink = max(1, int(round(dur * blink_rate)))
    if dur > 0.5:
        blink_times = list(np.linspace(dur * 0.15,
                                       max(dur * 0.15 + 0.25, dur * 0.92), n_blink))
    else:
        blink_times = []
    eye_w = np.asarray(eye_w, dtype=float).copy()
    for bt in blink_times:
        i_pre = int(round((bt - 0.05) * OUT_FPS))
        i_close = int(round(bt * OUT_FPS))
        i_open = int(round((bt + 0.10) * OUT_FPS))
        if i_pre < 0 or i_close >= len(eye_w) or i_open >= len(eye_w):
            continue
        base_pre = float(eye_w[i_pre])
        target = float(eye_w[i_open])
        n1 = max(1, i_close - i_pre)
        n2 = max(1, i_open - i_close)
        # ⭐ 眼睛 weight 越大 = 越睁开（eyes.cpp:71-78）⇒ **眨眼是降到 0**，不是升到 100
        seg = np.concatenate([
            np.linspace(base_pre, 0.0, n1 + 1)[:-1],     # 闭眼（weight → 0）
            np.linspace(0.0, target, n2 + 1),            # 睁眼（weight 回到原值）
        ])
        end = min(len(eye_w), i_pre + len(seg))
        eye_w[i_pre:end] = seg[:end - i_pre]

    # ── 快通道（逐帧）：能量 → 嘴/眼/灯；谱质心 → 色温 ────────────────
    env_t = track["times"]
    env = track["env"]
    cen = track["centroid"]
    e_ref = float(np.percentile(env, 90)) if len(env) else 0.0
    e_min = float(np.percentile(env, 20)) if len(env) else 0.0
    e_rng = max(e_ref - e_min, 1.0)
    c_ref = feat.centroid_mean_hz

    env_i = np.interp(out_t, env_t, env)
    cen_i = np.interp(out_t, env_t, cen)
    e_norm = np.clip((env_i - e_min) / e_rng, 0.0, 1.0)
    c_norm = np.clip((cen_i - max(c_ref * 0.55, 1.0)) / max(c_ref * 0.9, 1.0), 0.0, 1.0)

    mouth_w = base_mouth + p["energyEyeGain"] * 45.0 * e_norm * gain
    # ⭐ 眼睛 weight 越大 = 越睁开（eyes.cpp:71-78）
    #    能量高 ⇒ 眼睛更睁开 ⇒ weight **变大**（与嘴相反：嘴 weight 越大越张开）
    eye_w = eye_w + p["energyEyeGain"] * 12.0 * e_norm * gain
    bright = np.clip(p["lightBright"] + p["energyLightGain"] * e_norm * gain
                     + p["lightBrightnessBias"], 0.0, 1.0)

    warm_base = _clamp(p["lightWarm"] + p["colorWarmBias"], 0.0, 1.0)
    warm = np.clip(warm_base + (c_norm - 0.5) * p["centroidWarmGain"] * 1.6, 0.0, 1.0)

    # ── 组装关键帧 ────────────────────────────────────────────────────
    arousal = float(np.clip(0.5 + 0.5 * (feat.f0_accent_peak_semitone / 6.0), 0.0, 1.0))
    speed = 200 if arousal < 0.34 else (500 if arousal < 0.7 else 800)

    kfs: List[dict] = []
    for i in range(n_out):
        t = float(out_t[i])
        in_pause = any(t0 <= t <= t1 for (t0, t1) in track["pauses"])

        yv = _clamp(float(yaw[i]), -YAW_SOFT, YAW_SOFT)
        pv = _clamp(float(pitch[i]), PITCH_SOFT[0], PITCH_SOFT[1])

        ew = _clamp(float(eye_w[i]), *WEIGHT_RANGE)
        mw = _clamp(0.0 if in_pause else float(mouth_w[i]), *WEIGHT_RANGE)
        size = _clamp(p["eyeSize"], *SIZE_RANGE)

        # 眼睛位置偏移：JSON x/y ∈ [-100,100] 经 map_range 映射到**像素 ±16**
        # （eyes.cpp:12-16 常量、eyes.cpp:59-69 映射）
        # ⇒ 我们按**像素**设计，再换算回 JSON 值（系数 6.25）
        ex_px = _clamp((yv - p["yawBias"]) * 1.5, -EYE_PX_MAX, EYE_PX_MAX)
        ey_px = _clamp(-(pv - 76.0) * 1.2 * p["gazeLead"], -EYE_PX_MAX, EYE_PX_MAX)
        ex = _clamp(round(ex_px * EYE_JSON_PER_PX), *ELEMENT_XY)
        ey = _clamp(round(ey_px * EYE_JSON_PER_PX), *ELEMENT_XY)

        warm_i = float(warm[i])
        light_l = mix_oklab(COLOR_COOL, COLOR_WARM, warm_i)
        light_r = mix_oklab(COLOR_WARM, COLOR_COOL, warm_i)
        # 亮度调制：整体往白/灰方向推一点
        light_l = mix_oklab(light_l, "#FFFFFF", bright[i] * 0.35)
        light_r = mix_oklab(light_r, "#FFFFFF", bright[i] * 0.35)

        kfs.append({
            "leftEye": {"x": int(round(ex)), "y": int(round(ey)), "rotation": 0,
                        "weight": int(round(ew)), "size": int(round(size))},
            "rightEye": {"x": int(round(ex)), "y": int(round(ey)), "rotation": 0,
                         "weight": int(round(ew)), "size": int(round(size))},
            "mouth": {"x": 0, "y": 0, "rotation": 0,
                      "weight": int(round(mw)), "size": 0},
            "yawServo": {"angle": int(round(yv * 10)), "speed": speed},
            "pitchServo": {"angle": int(round(pv * 10)), "speed": speed},
            "leftRgbColor": light_l,
            "rightRgbColor": light_r,
            "durationMs": OUT_DT_MS,
        })

    info = {
        "anchorCount": len(at),
        "accentAnchors": len(accent_nod),
        "timeScale": time_scale,
        # 锚点的**角度值集合**（用于自检「语速不改角度」）
        "anchorPitchValues": sorted({round(float(v), 4) for v in apitch}),
        "anchorYawValues": sorted({round(float(v), 4) for v in ayaw}),
        "anchorEyeValues": sorted({round(float(v), 4) for v in aeye}),
        "anchorTimes": [round(float(v), 4) for v in at],
        "accentNodDegrees": [(t, round(base_pitch - nod, 3)) for (t, nod) in accent_nod],
        "frameCount": n_out,
        "outputFps": OUT_FPS,
        "frameMs": OUT_DT_MS,
    }
    return kfs, info


def build_avatar(kfs: List[dict], emotion: str = "Neutral") -> dict:
    """取最后一帧生成 0x03 ControlAvatar（保活通道用）。"""
    last = kfs[-1]
    return {
        "type": "bleAvatar",
        "leftEye": dict(last["leftEye"]),
        "rightEye": dict(last["rightEye"]),
        "mouth": dict(last["mouth"]),
    }


# ══════════════════════════════════════════════════════════════════════════
# 6. 审计（不靠"看起来对"）
# ══════════════════════════════════════════════════════════════════════════

def audit(kfs: List[dict]) -> dict:
    rep = {"keyframeCount": len(kfs), "problems": [], "warnings": [],
           "ranges": {}, "durationMs_total": 0}

    total = 0
    for i, k in enumerate(kfs):
        extra = set(k.keys()) - DANCE_FIELDS
        if extra:
            rep["problems"].append(f"kf[{i}] 未知字段（固件会静默忽略）: {sorted(extra)}")
        for el in AVATAR_ELEMENTS:
            if el not in k:
                rep["problems"].append(f"kf[{i}] 缺元素 {el}")
                continue
            sub = k[el]
            bad = set(sub.keys()) - set(AVATAR_FIELDS)
            if bad:
                rep["problems"].append(f"kf[{i}].{el} 未知字段: {sorted(bad)}")
            if not (ELEMENT_XY[0] <= sub["x"] <= ELEMENT_XY[1]):
                rep["problems"].append(f"kf[{i}].{el}.x 越界 {sub['x']}")
            if not (ELEMENT_XY[0] <= sub["y"] <= ELEMENT_XY[1]):
                rep["problems"].append(f"kf[{i}].{el}.y 越界 {sub['y']}")
            if not (ROTATION_RANGE[0] <= sub["rotation"] <= ROTATION_RANGE[1]):
                rep["problems"].append(f"kf[{i}].{el}.rotation 越界 {sub['rotation']}")
            if not (WEIGHT_RANGE[0] <= sub["weight"] <= WEIGHT_RANGE[1]):
                rep["problems"].append(f"kf[{i}].{el}.weight 越界 {sub['weight']}")
            if not (SIZE_RANGE[0] <= sub["size"] <= SIZE_RANGE[1]):
                rep["problems"].append(f"kf[{i}].{el}.size 越界 {sub['size']}")
        ya = k["yawServo"]["angle"]
        pa = k["pitchServo"]["angle"]
        if not (-int(YAW_LIMIT_DEG * 10) <= ya <= int(YAW_LIMIT_DEG * 10)):
            rep["problems"].append(f"kf[{i}] yaw {ya} 越过物理限位 ±1280")
        if not (30 <= pa <= 870):
            rep["problems"].append(f"kf[{i}] pitch {pa} 越过物理限位 30..870")
        if abs(ya) > int(YAW_SOFT * 10):
            rep["warnings"].append(f"kf[{i}] yaw {ya} 越过软限位 ±{int(YAW_SOFT*10)}")
        if not (int(PITCH_SOFT[0] * 10) <= pa <= int(PITCH_SOFT[1] * 10)):
            rep["warnings"].append(f"kf[{i}] pitch {pa} 越过软限位")
        for c in ("leftRgbColor", "rightRgbColor"):
            v = k[c]
            if not (isinstance(v, str) and v.startswith("#") and len(v) == 7):
                rep["problems"].append(f"kf[{i}].{c} 颜色格式非法 {v}")
        total += k["durationMs"]

    rep["durationMs_total"] = total

    # ── 载荷体积 vs 通道上限（I2） ─────────────────────────────────────
    blob = json.dumps(kfs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    rep["payloadBytes"] = len(blob)
    rep["payloadBytesPerFrame"] = round(len(blob) / max(1, len(kfs)), 1)
    if len(blob) > LAN_FRAME_MAX:
        rep["problems"].append(
            f"载荷 {len(blob)} B 超过 LAN 单帧上限 {LAN_FRAME_MAX} B"
            f"（local_network_protocol.h:18）⇒ LAN 通道会被丢弃；"
            f"约可承载 {LAN_FRAME_MAX * 1000 // max(1, rep['payloadBytesPerFrame']) } ms 音频")
    elif len(blob) > LAN_FRAME_MAX * 0.8:
        rep["warnings"].append(
            f"载荷 {len(blob)} B 已达 LAN 上限 {LAN_FRAME_MAX} B 的 "
            f"{len(blob) * 100 // LAN_FRAME_MAX}%")
    if len(blob) > REMOTE_FRAME_MAX:
        rep["problems"].append(f"载荷 {len(blob)} B 超过远端上限 {REMOTE_FRAME_MAX} B")

    # ── 舵机弹簧参数（speed → 刚度/阻尼/时间常数）（S4） ───────────────
    speeds = sorted({int(k["yawServo"].get("speed", 0)) for k in kfs})
    rep["servoSpring"] = []
    for s in speeds:
        k_stiff = 10.0 + (s / 1000.0) ** 2 * 640.0
        omega = math.sqrt(k_stiff)
        rep["servoSpring"].append({
            "speed": s, "stiffness": round(k_stiff, 1),
            "omega_rad_s": round(omega, 2),
            "settle_ms": int(round(4000.0 / omega)),
        })

    def rng(path):
        vals = []
        for k in kfs:
            v = k
            for pth in path.split("."):
                v = v[pth]
            vals.append(v)
        return [min(vals), max(vals)] if vals else [0, 0]

    for path in ("yawServo.angle", "pitchServo.angle", "leftEye.weight",
                 "rightEye.weight", "mouth.weight", "leftEye.x", "leftEye.y",
                 "durationMs"):
        rep["ranges"][path] = rng(path)
    return rep


def schema_check_avatar(av: dict) -> List[str]:
    """模拟固件 update_from_json：只接受 15 个 key，其余静默忽略。"""
    bad = []
    for el in AVATAR_ELEMENTS:
        if el not in av:
            bad.append(f"缺 {el}")
            continue
        for f in av[el]:
            if f not in AVATAR_FIELDS:
                bad.append(f"{el}.{f} 会被静默忽略")
    for k in av:
        if k not in AVATAR_ELEMENTS and k != "type":
            bad.append(f"顶层 {k} 不会被固件解析")
    return bad


# ══════════════════════════════════════════════════════════════════════════
# 7. 自检：合成已知信号 → 验证提取精度 + 限位 + 不过冲
# ══════════════════════════════════════════════════════════════════════════

def _synth(sr: int, segments: Sequence[Tuple[float, float, float, float]],
           silence: Sequence[Tuple[float, float]] = (),
           syll_hz: float = 0.0) -> np.ndarray:
    """segments: (t0, t1, f0_hz, amp)；silence: (t0, t1) 强制静音段；
    syll_hz > 0 时叠加该频率的音节幅度调制（模拟真实语音的音节核）。

    淡入淡出只用 15 ms —— 整段 Hanning 会人为制造长静音，污染停顿检测。
    """
    total = max([s[1] for s in segments] + [s[1] for s in silence] + [1.0])
    n = int(total * sr)
    x = np.zeros(n)
    t = np.arange(n) / sr
    for (t0, t1, f0, amp) in segments:
        i0, i1 = int(t0 * sr), int(t1 * sr)
        seg_t = t[i0:i1] - t0
        ph = 2 * np.pi * f0 * seg_t
        wav = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)) / 1.75
        env = np.ones(len(seg_t))
        fl = int(round(0.015 * sr))
        if fl * 2 < len(env):
            ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fl)))
            env[:fl] = ramp
            env[-fl:] = ramp[::-1]
        if syll_hz > 0:
            env = env * (0.62 + 0.38 * np.cos(2.0 * np.pi * syll_hz * seg_t))
        x[i0:i1] += amp * wav * env
    for (t0, t1) in silence:
        x[int(t0 * sr):int(t1 * sr)] = 0.0
    return x.astype(np.float32)


def _demo_signal(sr: int = 16000) -> np.ndarray:
    """演示信号：150 Hz 基准 + 220 Hz 重音 + 200 Hz 后半段 + 350 ms 停顿，
    并叠加 4 Hz 音节幅度调制（让语速落在真实语音的 3~6 音节/秒区间）。"""
    return _synth(sr,
                  [(0.05, 0.55, 150.0, 0.6),
                   (0.55, 0.75, 220.0, 0.6),     # 重音
                   (0.75, 1.05, 150.0, 0.6),
                   (1.40, 2.35, 200.0, 0.6)],
                  silence=[(1.05, 1.40)],
                  syll_hz=4.0)


def self_test(verbose: bool = True) -> int:
    sr = 16000
    ok = True
    fails = []

    def chk(name, cond, detail=""):
        nonlocal ok
        if cond:
            if verbose:
                print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
        else:
            ok = False
            fails.append(f"{name} :: {detail}")
            print(f"  FAIL  {name}  {detail}")

    print("=" * 72)
    print("自检 1：合成信号 → 韵律提取精度")
    print("=" * 72)
    x = _demo_signal(sr)
    feat, track = extract_prosody(x, sr)
    print(f"  提取结果: {json.dumps(feat.as_dict(), ensure_ascii=False)}")

    chk("F0 均值在语音带内 (140~210 Hz)", 140.0 <= feat.f0_mean_hz <= 210.0,
        f"f0_mean_hz={feat.f0_mean_hz:.2f}")
    chk("检测到停顿 ≥ 1 段", feat.pause_count >= 1, f"pause_count={feat.pause_count}")
    chk("最长停顿落在 250~560 ms", 250.0 <= feat.longest_pause_ms <= 560.0,
        f"longest_pause_ms={feat.longest_pause_ms:.1f}")
    chk("浊音占比合理 (0.5~0.95)", 0.5 <= feat.voiced_ratio <= 0.95,
        f"voiced_ratio={feat.voiced_ratio:.3f}")
    chk("谱质心在语音典型带 (300~2500 Hz)", 300.0 <= feat.centroid_mean_hz <= 2500.0,
        f"centroid={feat.centroid_mean_hz:.1f}")
    chk("检出重音峰 ≥ 1", feat.f0_accent_count >= 1,
        f"count={feat.f0_accent_count} peak={feat.f0_accent_peak_semitone:.2f}")
    if track["accents"]:
        in_win = [t for t in track["accents"] if 0.45 <= t <= 0.90]
        chk("重音峰落在 220 Hz 段 (0.45~0.90 s)", len(in_win) >= 1,
            f"accents={['%.3f' % a for a in track['accents']]}")
    chk("语速在 0.5~8 音节/秒", 0.5 <= feat.speech_rate_hz <= 8.0,
        f"rate={feat.speech_rate_hz:.2f}")

    # 逐段 F0 精度
    t = track["times"]
    f0 = track["f0"]
    m1 = (t > 0.15) & (t < 0.50)
    m2 = (t > 1.55) & (t < 2.25)
    f1 = float(np.median(f0[m1]))
    f2 = float(np.median(f0[m2]))
    chk("段1 F0 ≈ 150 Hz (±8)", abs(f1 - 150.0) <= 8.0, f"f1={f1:.2f}")
    chk("段2 F0 ≈ 200 Hz (±8)", abs(f2 - 200.0) <= 8.0, f"f2={f2:.2f}")

    print()
    print("=" * 72)
    print("自检 2：关键帧编译 → 限位 / schema / 不过冲")
    print("=" * 72)
    kfs, info = compile_keyframes(track, feat, build_params("Happy", feat), "Happy")
    rep = audit(kfs)
    print(f"  关键帧数={rep['keyframeCount']}  总时长={rep['durationMs_total']} ms")
    print(f"  锚点: {json.dumps({k: v for k, v in info.items() if k != 'accentNodDegrees'}, ensure_ascii=False)}")
    print(f"  范围: {json.dumps(rep['ranges'], ensure_ascii=False)}")
    chk("无 schema/限位问题", len(rep["problems"]) == 0, "; ".join(rep["problems"][:5]))
    chk("无软限位告警", len(rep["warnings"]) == 0, "; ".join(rep["warnings"][:5]))
    # ⚠️ 旧写法 `abs(count - round(dur*25)) <= 1` 是**同义反复**（count 就是这么算的）
    # ⇒ 改为两条真断言：帧数由音频时长独立算出；总时长与音频时长对齐（±1 帧）
    chk("帧数 == ceil(音频时长 × 25)",
        rep["keyframeCount"] == math.ceil(feat.duration_s * OUT_FPS),
        f"{rep['keyframeCount']} vs {math.ceil(feat.duration_s * OUT_FPS)}")
    chk("关键帧总时长与音频时长对齐（±1 帧）",
        abs(rep["durationMs_total"] - feat.duration_s * 1000.0) <= OUT_DT_MS,
        f"{rep['durationMs_total']} ms vs {feat.duration_s*1000:.0f} ms")
    chk("yaw 在软限位内", abs(rep["ranges"]["yawServo.angle"][1]) <= int(YAW_SOFT * 10),
        f"{rep['ranges']['yawServo.angle']}")
    chk("pitch 在软限位内",
        int(PITCH_SOFT[0] * 10) <= rep["ranges"]["pitchServo.angle"][0]
        and rep["ranges"]["pitchServo.angle"][1] <= int(PITCH_SOFT[1] * 10),
        f"{rep['ranges']['pitchServo.angle']}")
    chk("情绪基线 pitch 全部落在软限位内",
        all(PITCH_SOFT[0] <= v <= PITCH_SOFT[1] for k, v in EMOTION_BASELINE.items()
            if k.endswith("_pitch")),
        str({k: v for k, v in EMOTION_BASELINE.items() if k.endswith("_pitch")}))

    # ⚠️ 旧写法「yaw 有变化」是弱断言（漂移项与音频无关，静音也能过）
    # ⇒ 改为与**纯静音输入**对照：语音输入的 yaw 变化必须显著大于静音输入
    yaw_vals = {k["yawServo"]["angle"] for k in kfs}
    chk("yaw 有变化（不是恒定）", len(yaw_vals) > 1, f"unique={len(yaw_vals)}")
    silent = np.zeros(int(sr * 1.0), dtype=np.float32)
    f_sil, t_sil = extract_prosody(silent, sr)
    kfs_sil, _ = compile_keyframes(t_sil, f_sil, build_params("Happy", f_sil), "Happy")
    sil_span = (max(k["yawServo"]["angle"] for k in kfs_sil)
                - min(k["yawServo"]["angle"] for k in kfs_sil))
    voice_span = (max(k["yawServo"]["angle"] for k in kfs)
                  - min(k["yawServo"]["angle"] for k in kfs))
    chk("yaw 变化幅度：语音输入显著大于静音输入",
        voice_span > sil_span,
        f"voice_span={voice_span} silent_span={sil_span}")

    # ⚠️ 眼睛位置：JSON ±100 ↔ 像素 ±16（eyes.cpp:59-69，系数 6.25）
    # 旧写法断言「JSON ≤ 16」是同义反复（代码里已 clamp）且单位错
    chk("眼睛 JSON 偏移在 [-100,100]",
        all(ELEMENT_XY[0] <= k["leftEye"]["x"] <= ELEMENT_XY[1]
            and ELEMENT_XY[0] <= k["leftEye"]["y"] <= ELEMENT_XY[1] for k in kfs),
        f"x={rep['ranges'].get('leftEye.x')} y={rep['ranges'].get('leftEye.y')}")
    px = [abs(k["leftEye"]["x"]) / EYE_JSON_PER_PX for k in kfs]
    py = [abs(k["leftEye"]["y"]) / EYE_JSON_PER_PX for k in kfs]
    chk("换算回像素后不超过设备限幅 ±16",
        max(px + py) <= EYE_PX_MAX + 1e-6,
        f"max_px={max(px+py):.2f}")
    chk("JSON 100 恰好对应像素 16（换算系数正确）",
        abs(100 / EYE_JSON_PER_PX - 16.0) < 1e-9, f"{100/EYE_JSON_PER_PX}")

    # ⭐ 眼睛 weight 极性（eyes.cpp:71-78）：weight 越大 = 越睁开
    #    ⇒ 眨眼必须把 weight **压到 0**；常态应当是睁眼（高 weight）
    eye_vals = [k["leftEye"]["weight"] for k in kfs]
    chk("常态眼睛是睁开的（weight 高）",
        float(np.median(eye_vals)) >= 50.0,
        f"median={np.median(eye_vals)}")
    chk("眨眼时 weight 压到接近 0（闭眼）",
        min(eye_vals) <= 20,
        f"min={min(eye_vals)}")
    # ⭐ 固件官方情绪表（eyes.cpp:103-122）：Neutral=100/Happy=72/Angry=70/Sad=70/Doubt=75/Sleepy=35
    #    断言「值 == 固件表」比断言「大小顺序」更强：顺序对了但值漂了照样会被抓出来
    FW_EYE_TABLE = {"Neutral": 100.0, "Happy": 72.0, "Angry": 70.0,
                     "Sad": 70.0, "Doubt": 75.0, "Sleepy": 35.0}
    chk("眼睛基线 == 固件官方情绪表（eyes.cpp:103-122，值不漂移）",
        all(EMOTION_BASELINE[f"{k}_eyeWeight"] == v for k, v in FW_EYE_TABLE.items()),
        str({k: EMOTION_BASELINE[f"{k}_eyeWeight"] for k in FW_EYE_TABLE}))
    # 极性顺序：weight 越大 = 越睁开 ⇒ 睁眼程度 Sleepy(35) < Happy(72) < Neutral(100)
    chk("眼睛 weight 极性 = 固件（越大越睁开：Sleepy<Happy<Neutral）",
        EMOTION_BASELINE["Sleepy_eyeWeight"] < EMOTION_BASELINE["Happy_eyeWeight"]
        < EMOTION_BASELINE["Neutral_eyeWeight"],
        f"Sleepy={EMOTION_BASELINE['Sleepy_eyeWeight']} "
        f"Happy={EMOTION_BASELINE['Happy_eyeWeight']} "
        f"Neutral={EMOTION_BASELINE['Neutral_eyeWeight']}")
    # ⭐ 嘴部极性（mouth.cpp:19-21 / 55-59）：
    #    weight 0   → size(90,  6) radius  0  ⇒ 细线 = 闭嘴
    #    weight 100 → size(60, 50) radius 16  ⇒ 大椭圆 = 张嘴
    #    固件**没有嘴部情绪表**（只有眼睛有 eyes.cpp:103-122）⇒ 嘴基线是自设计的
    def _mouth_geom(w):
        return (6.0 + (50.0 - 6.0) * w / 100.0,   # size_y
                0.0 + (16.0 - 0.0) * w / 100.0)    # radius

    _sy_s, _r_s = _mouth_geom(EMOTION_BASELINE["Sleepy_mouthWeight"])
    _sy_h, _r_h = _mouth_geom(EMOTION_BASELINE["Happy_mouthWeight"])
    chk("嘴 weight 极性 = 固件（越大越张开：嘴高与圆角半径随 weight 增大）",
        _sy_s < _sy_h and _r_s < _r_h,
        f"Sleepy(size_y={_sy_s:.1f},r={_r_s:.1f}) "
        f"Happy(size_y={_sy_h:.1f},r={_r_h:.1f})")
    chk("嘴 weight=0 闭嘴 / =100 张嘴（固件映射端点）",
        _mouth_geom(0.0) == (6.0, 0.0) and _mouth_geom(100.0) == (50.0, 16.0),
        f"w0={_mouth_geom(0.0)} w100={_mouth_geom(100.0)}")

    chk("重音锚点产生了点头",
        any(d > 0.5 for (_, d) in info["accentNodDegrees"]),
        str(info["accentNodDegrees"]))

    # 载荷体积 vs 通道上限
    chk("载荷未超 LAN 单帧上限 65535 B",
        rep["payloadBytes"] <= LAN_FRAME_MAX,
        f"{rep['payloadBytes']} B ({rep['payloadBytesPerFrame']} B/帧)")

    # 语速只压缩时间轴，角度值一律不变
    print()
    print("=" * 72)
    print("自检 3：语速只映射时间轴，不改变角度语义")
    print("=" * 72)
    p_a = build_params("Happy", feat)
    p_b = build_params("Happy", feat)
    p_b["rateTimeScale"] = 3.0
    kfs_a, info_a = compile_keyframes(track, feat, p_a, "Happy")
    kfs_b, info_b = compile_keyframes(track, feat, p_b, "Happy")
    chk("帧数与音频时长绑定（语速不改总时长）",
        len(kfs_a) == len(kfs_b), f"{len(kfs_a)} vs {len(kfs_b)}")
    # ⭐ 核心断言：**锚点的角度值集合必须完全一致**（语速不改角度）
    chk("锚点 pitch 取值集合完全一致（角度语义未变）",
        info_a["anchorPitchValues"] == info_b["anchorPitchValues"],
        f"{info_a['anchorPitchValues']} vs {info_b['anchorPitchValues']}")
    chk("锚点 yaw 取值集合完全一致",
        info_a["anchorYawValues"] == info_b["anchorYawValues"])
    chk("锚点 eye 取值集合完全一致",
        info_a["anchorEyeValues"] == info_b["anchorEyeValues"])
    # 而**时间轴**必须真的被压缩（否则这条断言就是空转）
    chk("锚点到达时间被压缩（时间轴确实变了）",
        info_b["anchorTimes"] != info_a["anchorTimes"]
        and info_b["anchorTimes"][-1] <= info_a["anchorTimes"][-1] + 1e-6,
        f"scale {info_a['timeScale']} → {info_b['timeScale']}")
    chk("重音点头深度不受语速影响",
        info_a["accentNodDegrees"] == info_b["accentNodDegrees"],
        f"{info_a['accentNodDegrees']} vs {info_b['accentNodDegrees']}")

    print()
    print("=" * 72)
    print("自检 4：0x03 avatar schema")
    print("=" * 72)
    av = build_avatar(kfs, "Happy")
    bad = schema_check_avatar(av)
    chk("avatar 只含固件可解析字段", len(bad) == 0, "; ".join(bad))
    print(f"  avatar = {json.dumps(av, ensure_ascii=False)}")

    print()
    print("=" * 72)
    print("自检 5：参数数量 = 42")
    print("=" * 72)
    p = build_params("Happy", feat)
    n_scalar = (len(EMOTION_BASELINE) + len(PROSODY_MOD)
                + len(PERSONAL_DEFAULTS) + len(DEVICE_CONSTANTS))
    chk("22 + 9 + 7 + 4 = 42", n_scalar == 42, f"got {n_scalar}")
    chk("基线 22", len(EMOTION_BASELINE) == 22, str(len(EMOTION_BASELINE)))
    chk("韵律调制 9", len(PROSODY_MOD) == 9, str(len(PROSODY_MOD)))
    chk("个性化 7", len(PERSONAL_DEFAULTS) == 7, str(len(PERSONAL_DEFAULTS)))
    chk("设备常量 4", len(DEVICE_CONSTANTS) == 4, str(len(DEVICE_CONSTANTS)))

    print()
    print("=" * 72)
    if ok:
        print("SELF-TEST: ALL PASS")
    else:
        print(f"SELF-TEST: {len(fails)} FAIL")
        for f in fails:
            print("  -", f)
    print("=" * 72)
    return 0 if ok else 1


# ══════════════════════════════════════════════════════════════════════════
# 8. CLI
# ══════════════════════════════════════════════════════════════════════════

def _write_text(path: str, text: str):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="韵律 → 舵机/关键帧 编译器原型")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--wav", help="TTS 下行 PCM（WAV，单声道）")
    ap.add_argument("--demo", action="store_true", help="生成合成演示音频")
    ap.add_argument("--emotion", default="Neutral")
    ap.add_argument("--out", help="输出 0x14 关键帧 JSON")
    ap.add_argument("--report", help="输出 Markdown 报告")
    ap.add_argument("--frames", help="输出逐帧 CSV")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.demo:
        sr = 16000
        x = _demo_signal(sr)
        # ⚠️ 写到**系统临时目录**，不要写回仓库：
        #    工具产物落进源码目录 ⇒ 会被 git 当成待提交文件（真实踩过：
        #    `_demo_tts.wav` 75 KB 出现在 `git status` 的未跟踪列表里）。
        #    需要固定位置就显式给 --wav。
        out_dir = os.path.join(tempfile.gettempdir(), "stackchan-prosody")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "_demo_tts.wav")
        wavfile.write(path, sr, (x * 32767).astype(np.int16))
        print(f"demo wav -> {path}")
        args.wav = path

    if not args.wav:
        ap.print_help()
        return 2

    sr, data = wavfile.read(args.wav)
    if data.ndim > 1:
        data = data.mean(axis=1)
    feat, track = extract_prosody(data, sr)
    p = build_params(args.emotion, feat)
    kfs, info = compile_keyframes(track, feat, p, args.emotion)
    av = build_avatar(kfs, args.emotion)
    rep = audit(kfs)

    print(json.dumps(feat.as_dict(), ensure_ascii=False, indent=2))
    print(f"keyframes={rep['keyframeCount']} duration={rep['durationMs_total']}ms")
    print(f"anchors={json.dumps({k: v for k, v in info.items() if k != 'accentNodDegrees'}, ensure_ascii=False)}")
    print(f"ranges={json.dumps(rep['ranges'], ensure_ascii=False)}")
    if rep["problems"]:
        print("PROBLEMS:", *rep["problems"], sep="\n  ")
    if rep["warnings"]:
        print("WARNINGS:", *rep["warnings"], sep="\n  ")

    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(kfs, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"0x14 keyframes -> {args.out}")

    if args.frames:
        lines = ["t_ms,yaw_raw,pitch_raw,eye_w,mouth_w,left_rgb,right_rgb"]
        for i, k in enumerate(kfs):
            lines.append("{},{},{},{},{},{},{}".format(
                i * OUT_DT_MS, k["yawServo"]["angle"], k["pitchServo"]["angle"],
                k["leftEye"]["weight"], k["mouth"]["weight"],
                k["leftRgbColor"], k["rightRgbColor"]))
        _write_text(args.frames, "\n".join(lines) + "\n")
        print(f"frames csv -> {args.frames}")

    if args.report:
        fd = feat.as_dict()
        rows = "\n".join("| `{}` | {} |".format(k, v) for k, v in fd.items())
        rng_rows = "\n".join("| `{}` | {} | {} |".format(k, v[0], v[1])
                              for k, v in rep["ranges"].items())
        md = "\n".join([
            "# 韵律 → 关键帧 编译报告",
            "",
            "## 韵律特征（7 维）",
            "",
            "| 特征 | 值 |",
            "|---|---|",
            rows,
            "",
            "## 输出范围",
            "",
            "| 字段 | min | max |",
            "|---|---|---|",
            rng_rows,
            "",
            "## 审计",
            "",
            "- 关键帧数：{}".format(rep["keyframeCount"]),
            "- 总时长：{} ms".format(rep["durationMs_total"]),
            "- 问题数：{}".format(len(rep["problems"])),
            "- 告警数：{}".format(len(rep["warnings"])),
            "",
        ])
        _write_text(args.report, md)
        print(f"report -> {args.report}")

    return 0 if not rep["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
