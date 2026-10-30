# -*- coding: utf-8 -*-
"""prosody —— 韵律 → 身体：TTS 音频 → 0x14 DanceSequence 关键帧。

本模块是 `tools/prosody_to_motion.py` 的**可独立运行移植版**：
算法逐行对齐参考实现（参考实现行号标在每个块的注释里），
但代码落在 `server/stackchan_ai/` 内，**不依赖 tools/ 存在**，
以便后端基座能单独部署。

管线（docs/research/59 §1 / 54 号裁决）：

    TTS 下行 PCM（16 kHz 单声道）
      → 预加重
      → 40 ms 窗 / 10 ms 跳（100 Hz 分析）
      → YIN 基频 + 能量 + HNR + 谱质心
      → VAD + 停顿检出
      → 7 维韵律特征
      → 42 个标量（情绪基线 22 + 韵律调制 9 + 个性化 7 + 设备常量 4）
      → 语义锚点（停顿落定 / 重音点头）
      → PCHIP 插值（保形不过冲）
      → 0x14 关键帧（25 Hz，durationMs = 40）

固件事实约束（全部实读官方源码；行号为官方仓库路径）：

    stackchan/json/json_helper.cpp:192-195  0x14 顶层**强制是数组**
    stackchan/json/json_helper.cpp:201-224  0x14 每帧 8 个 key
    stackchan/json/json_helper.cpp:166-176  servo 只认 angle + speed
    stackchan/json/json_helper.cpp:145-164  feature 认 x/y/rotation/weight/size
    stackchan/json/json_helper.cpp:18       x 与 y 必须**同时是 int**
    stackchan/avatar/avatar/elements/element.h:26-30 / :41-44
                                           x,y ∈ [-100,100]；rotation ∈ [0,3600]（0.1 度）
    stackchan/avatar/avatar/elements/feature.h:22-25 / :36-39
                                           weight ∈ [0,100]；size ∈ [-100,100]
    stackchan/avatar/skins/default/eyes.cpp:12-16 / :59-69
                                           眼位基准 (-70,-16)，偏移限幅 ±16 **像素**
    stackchan/avatar/skins/default/eyes.cpp:71-78
                                           ⭐ weight 越大 = 越睁开
    stackchan/avatar/skins/default/eyes.cpp:102-123
                                           官方情绪表 Neutral=100 / Happy=72 / ...
    stackchan/avatar/skins/default/mouth.cpp:48-58
                                           ⭐ 嘴 weight 越大 = 越张开
    hal/hal_servo.cpp:340 / :349            yaw (-1280,1280)；pitch (30,870)，单位 0.1 度
    hal/hal_ws_avatar.cpp:146               远端 WS 单帧上限 256 KB
    hal/utils/local_network/local_network_protocol.h:18  LAN 单帧上限 65535 B
    stackchan/motion/servo.cpp:133-136      speed → 弹簧刚度 = 10 + (speed/1000)²×640
    stackchan/motion/servo.cpp:59-66        静止 200 ms 自动卸力

已发表参数（arXiv:2403.12670）：25 Hz 帧率 / Δt = 40 ms、320 ms 滑窗、8 Hz 5 阶 Butterworth。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.signal import butter, filtfilt, find_peaks, medfilt

# ══════════════════════════════════════════════════════════════════════════
# 0. 固件事实常量（改这里 = 改对设备的认知，必须有 file:line 依据）
# ══════════════════════════════════════════════════════════════════════════

YAW_LIMIT_DEG = 128.0          # hal_servo.cpp:340  angleLimit (-1280, 1280)
PITCH_LIMIT_DEG = (3.0, 87.0)  # hal_servo.cpp:349  angleLimit (30, 870)

YAW_SOFT = 115.0                       # 自研软限位裕量 5.0°（**非固件事实**）
PITCH_SOFT = (5.0, 85.0)               # 自研软限位裕量 2.0°（**非固件事实**）

ELEMENT_XY = (-100, 100)
ROTATION_RANGE = (0, 3600)     # 0.1 度
WEIGHT_RANGE = (0, 100)
SIZE_RANGE = (-100, 100)

#: 眼睛位置：JSON x/y ∈ [-100,100] 经 map_range 映射到**像素 ±16**
#: （eyes.cpp:12-16 常量、eyes.cpp:59-69 映射）⇒ JSON 16 实际只有 2.56 px
EYE_PX_MAX = 16.0
EYE_JSON_PER_PX = ELEMENT_XY[1] / EYE_PX_MAX   # 6.25

#: 通道上限
REMOTE_FRAME_MAX = 256 * 1024      # hal_ws_avatar.cpp:146
LAN_FRAME_MAX = 65535              # local_network_protocol.h:18  UINT16_MAX

AVATAR_ELEMENTS = ("leftEye", "rightEye", "mouth")
AVATAR_FIELDS = ("x", "y", "rotation", "weight", "size")
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
PITCH_MEDIAN_POINTS = 5         # 5 点中值（50 ms）：只去抖，保留 200 ms 级重音
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
# 1. 42 个参数（情绪基线 22 + 韵律调制 9 + 个性化 7 + 设备常量 4）
# ══════════════════════════════════════════════════════════════════════════

#: 情绪基线 22 = 6 情绪 × 3 + 4 全局
#: 眼睛 weight 基线**直接取固件官方情绪表**（eyes.cpp:102-123），不自造；
#: 嘴基线是自设计值（固件没有嘴部情绪表）。
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

#: 韵律调制 9
PROSODY_MOD: Dict[str, float] = {
    "f0PitchGain": 0.55,        # F0 均值 → 俯仰基线（半音 → 度）
    "f0AccentNodGain": 7.5,     # F0 重音峰 → 点头幅度（度）
    "energyEyeGain": 0.30,      # 能量 → 眼睛 weight
    "energyLightGain": 0.45,    # 能量 → 灯亮度
    "rateTimeScale": 1.00,      # 语速 → 时间轴缩放（**不映射角度**）
    "pauseSettleGain": 6.0,     # 停顿 → 落定幅度
    "hnrSoftnessGain": 0.22,    # HNR → 眼睑柔和度
    "centroidWarmGain": 0.35,   # 谱质心 → 灯色冷暖
    "prosodyIntensity": 1.00,   # 总强度
}

#: 个性化 7（用户可调，默认值；个人定制值只在 private/，永不入库）
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
    """YIN 单帧基频估计，返回 ``(f0_hz, hnr_db, cmnd_min)``；f0=0 表示未浊音。

    移植自 tools/prosody_to_motion.py:253-317（数值行为一致）。
    """
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
    suffix = np.concatenate((np.cumsum(x2[::-1])[::-1], [0.0]))
    head = np.concatenate(([0.0], np.cumsum(x2)))

    taus = np.arange(0, tau_max + 1)
    diff = (energy - suffix[n - taus]) + (energy - head[taus]) - 2.0 * ac[taus]
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

    返回 ``(features, track)``；``track`` 含逐帧数组，供关键帧编译器使用。

    移植自 tools/prosody_to_motion.py:320-475（数值行为一致）。
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

    # ── F0 中值滤波 + 8 Hz 5 阶 Butterworth ───────────────────────────
    # ⚠ 未浊音帧必须先插值填掉再滤波（否则中位数与滤波状态一起被污染）。
    # ⚠ Butterworth 的归一化截止频率必须用**帧率**（100 Hz），不是采样率。
    voiced = f0 > 0
    f0_log = np.full(n, np.nan)
    f0_log[voiced] = np.log2(np.maximum(f0[voiced], 1e-6))
    idx_all = np.arange(n)
    if voiced.any():
        f0_fill = np.interp(idx_all, idx_all[voiced], f0_log[voiced])
    else:
        f0_fill = np.zeros(n)
    k = PITCH_MEDIAN_POINTS
    if len(f0_fill) >= k:
        f0_fill = medfilt(f0_fill, k)
    frame_rate = 1.0 / hop_sec
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

    F0_REF_HZ = 220.0
    if voiced_mask.any():
        e_lo = float(np.percentile(energy[voiced_mask], 5))
        e_hi = float(np.percentile(energy[voiced_mask], 95))
    else:
        e_lo = float(np.percentile(energy, 5))
        e_hi = float(np.percentile(energy, 95))

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
    """装配 42 个标量（情绪基线 22 + 韵律调制 9 + 个性化 7 + 设备常量 4）。"""
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
    keep = np.concatenate(([True], np.diff(t) > 1e-6))
    t, v = t[keep], v[keep]
    if len(t) == 1:
        return np.full_like(query, v[0])
    q = np.clip(np.asarray(query, dtype=float), t[0], t[-1])
    return PchipInterpolator(t, v, extrapolate=False)(q)


def compile_keyframes(track: dict, feat: ProsodyFeatures, p: Dict[str, float],
                      emotion: str = "Neutral") -> Tuple[List[dict], dict]:
    """把韵律编译成设备可直接收的 0x14 关键帧序列。

    返回 ``(关键帧列表, 编译信息)``。信息里含锚点统计，
    供断言「语速只映射时间轴、不映射角度」。

    移植自 tools/prosody_to_motion.py:563-755（数值行为一致）。
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
        # ⭐ 眼睛 weight 越大 = 越睁开 ⇒ **眨眼是降到 0**
        seg = np.concatenate([
            np.linspace(base_pre, 0.0, n1 + 1)[:-1],
            np.linspace(0.0, target, n2 + 1),
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
    # ⭐ 眼睛 weight 越大 = 越睁开（与嘴相反）
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

        # 眼睛位置偏移：按**像素**设计，再换算回 JSON 值（系数 6.25）
        ex_px = _clamp((yv - p["yawBias"]) * 1.5, -EYE_PX_MAX, EYE_PX_MAX)
        ey_px = _clamp(-(pv - 76.0) * 1.2 * p["gazeLead"], -EYE_PX_MAX, EYE_PX_MAX)
        ex = _clamp(round(ex_px * EYE_JSON_PER_PX), *ELEMENT_XY)
        ey = _clamp(round(ey_px * EYE_JSON_PER_PX), *ELEMENT_XY)

        warm_i = float(warm[i])
        light_l = mix_oklab(COLOR_COOL, COLOR_WARM, warm_i)
        light_r = mix_oklab(COLOR_WARM, COLOR_COOL, warm_i)
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
# 6. 审计（不靠「看起来对」）
# ══════════════════════════════════════════════════════════════════════════
def audit(kfs: List[dict]) -> dict:
    """审计关键帧序列：越界 / 载荷体积 / 舵机弹簧参数 / 各字段取值范围。"""
    rep = {"keyframeCount": len(kfs), "problems": [], "warnings": [],
           "ranges": {}, "durationMs_total": 0}

    total = 0
    for i, k in enumerate(kfs):
        extra = set(k.keys()) - DANCE_FIELDS
        if extra:
            rep["problems"].append("kf[%d] 未知字段（固件会静默忽略）: %s"
                                   % (i, sorted(extra)))
        for el in AVATAR_ELEMENTS:
            if el not in k:
                rep["problems"].append("kf[%d] 缺元素 %s" % (i, el))
                continue
            sub = k[el]
            bad = set(sub.keys()) - set(AVATAR_FIELDS)
            if bad:
                rep["problems"].append("kf[%d].%s 未知字段: %s" % (i, el, sorted(bad)))
            if not (ELEMENT_XY[0] <= sub["x"] <= ELEMENT_XY[1]):
                rep["problems"].append("kf[%d].%s.x 越界 %s" % (i, el, sub["x"]))
            if not (ELEMENT_XY[0] <= sub["y"] <= ELEMENT_XY[1]):
                rep["problems"].append("kf[%d].%s.y 越界 %s" % (i, el, sub["y"]))
            if not (ROTATION_RANGE[0] <= sub["rotation"] <= ROTATION_RANGE[1]):
                rep["problems"].append("kf[%d].%s.rotation 越界 %s"
                                       % (i, el, sub["rotation"]))
            if not (WEIGHT_RANGE[0] <= sub["weight"] <= WEIGHT_RANGE[1]):
                rep["problems"].append("kf[%d].%s.weight 越界 %s"
                                       % (i, el, sub["weight"]))
            if not (SIZE_RANGE[0] <= sub["size"] <= SIZE_RANGE[1]):
                rep["problems"].append("kf[%d].%s.size 越界 %s" % (i, el, sub["size"]))
        ya = k["yawServo"]["angle"]
        pa = k["pitchServo"]["angle"]
        if not (-int(YAW_LIMIT_DEG * 10) <= ya <= int(YAW_LIMIT_DEG * 10)):
            rep["problems"].append("kf[%d] yaw %d 越过物理限位 ±1280" % (i, ya))
        if not (30 <= pa <= 870):
            rep["problems"].append("kf[%d] pitch %d 越过物理限位 30..870" % (i, pa))
        if abs(ya) > int(YAW_SOFT * 10):
            rep["warnings"].append("kf[%d] yaw %d 越过软限位 ±%d"
                                   % (i, ya, int(YAW_SOFT * 10)))
        if not (int(PITCH_SOFT[0] * 10) <= pa <= int(PITCH_SOFT[1] * 10)):
            rep["warnings"].append("kf[%d] pitch %d 越过软限位" % (i, pa))
        for c in ("leftRgbColor", "rightRgbColor"):
            v = k[c]
            if not (isinstance(v, str) and v.startswith("#") and len(v) == 7):
                rep["problems"].append("kf[%d].%s 颜色格式非法 %s" % (i, c, v))
        total += k["durationMs"]

    rep["durationMs_total"] = total

    blob = json.dumps(kfs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    rep["payloadBytes"] = len(blob)
    rep["payloadBytesPerFrame"] = round(len(blob) / max(1, len(kfs)), 1)
    if len(blob) > LAN_FRAME_MAX:
        rep["problems"].append(
            "载荷 %d B 超过 LAN 单帧上限 %d B（local_network_protocol.h:18）"
            % (len(blob), LAN_FRAME_MAX))
    elif len(blob) > LAN_FRAME_MAX * 0.8:
        rep["warnings"].append("载荷 %d B 已达 LAN 上限 %d B 的 %d%%"
                               % (len(blob), LAN_FRAME_MAX,
                                  len(blob) * 100 // LAN_FRAME_MAX))
    if len(blob) > REMOTE_FRAME_MAX:
        rep["problems"].append("载荷 %d B 超过远端上限 %d B"
                               % (len(blob), REMOTE_FRAME_MAX))

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

    def rng(path: str):
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


# ══════════════════════════════════════════════════════════════════════════
# 7. 服务端门面：PCM → 关键帧
# ══════════════════════════════════════════════════════════════════════════
@dataclass
class ProsodyResult:
    """一次编译的完整结果。"""
    keyframes: List[dict] = field(default_factory=list)
    features: Optional[ProsodyFeatures] = None
    info: Dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0
    sample_rate: int = 16000

    @property
    def frame_count(self) -> int:
        return len(self.keyframes)

    def summary(self) -> Dict[str, Any]:
        """给日志/测试用的摘要（不含任何敏感信息）。"""
        return {
            "durationS": round(self.duration_s, 3),
            "frameCount": self.frame_count,
            "expectedFrameCount": max(1, int(math.ceil(self.duration_s * OUT_FPS))),
            "payloadBytes": len(json.dumps(self.keyframes, ensure_ascii=False,
                                           separators=(",", ":")).encode("utf-8")),
            "features": self.features.as_dict() if self.features else {},
        }


def pcm_to_samples(pcm: bytes, channels: int = 1) -> np.ndarray:
    """16-bit little-endian PCM → float64 数组（值域约 [-1, 1]）。"""
    data = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    if channels > 1:
        usable = (len(data) // channels) * channels
        data = data[:usable].reshape(-1, channels).mean(axis=1)
    return data / 32768.0


def samples_to_keyframes(samples: np.ndarray, sample_rate: int,
                         emotion: str = "Neutral",
                         personal: Optional[Dict[str, float]] = None) -> ProsodyResult:
    """PCM 浮点数组 → 0x14 关键帧。"""
    feat, track = extract_prosody(samples, sample_rate)
    params = build_params(emotion, feat, personal)
    keyframes, info = compile_keyframes(track, feat, params, emotion)
    return ProsodyResult(keyframes=keyframes, features=feat, info=info,
                          duration_s=feat.duration_s, sample_rate=sample_rate)


def pcm_to_keyframes(pcm: bytes, sample_rate: int = 16000, channels: int = 1,
                     emotion: str = "Neutral",
                     personal: Optional[Dict[str, float]] = None) -> ProsodyResult:
    """16-bit PCM 字节流 → 0x14 关键帧（服务端主入口）。"""
    samples = pcm_to_samples(pcm, channels)
    return samples_to_keyframes(samples, sample_rate, emotion, personal)


__all__ = [
    "YAW_LIMIT_DEG", "PITCH_LIMIT_DEG", "YAW_SOFT", "PITCH_SOFT",
    "ELEMENT_XY", "ROTATION_RANGE", "WEIGHT_RANGE", "SIZE_RANGE",
    "EYE_PX_MAX", "EYE_JSON_PER_PX", "REMOTE_FRAME_MAX", "LAN_FRAME_MAX",
    "AVATAR_ELEMENTS", "AVATAR_FIELDS", "DANCE_FIELDS",
    "OUT_FPS", "OUT_DT_MS", "ANALYSIS_HOP_MS", "ANALYSIS_WIN_MS",
    "F0_MIN", "F0_MAX", "YIN_THRESHOLD", "YIN_VOICED_MAX",
    "EMOTION_BASELINE", "PROSODY_MOD", "PERSONAL_DEFAULTS",
    "PARAM_COUNT_EXPECT", "DEVICE_CONSTANTS", "COLOR_WARM", "COLOR_COOL",
    "ProsodyFeatures", "ProsodyResult",
    "extract_prosody", "build_params", "compile_keyframes", "build_avatar",
    "audit", "mix_oklab", "hex_to_oklab", "oklab_to_hex",
    "pcm_to_samples", "samples_to_keyframes", "pcm_to_keyframes",
]
