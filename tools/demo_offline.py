#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""StackChan Companion —— 一条命令跑通全链路 Demo。

    文本 ──▶ 音频 ──▶ 韵律 7 维 ──▶ 42 标量 ──▶ 0x14 关键帧 ──▶ WS 帧 ──▶ 设备侧解析 ──▶ 脸

设计目标（按重要性排序）：

1. **诚实**：离线模式用「合成音频」代替 TTS，报告里明确标注音频来源；
   真实 TTS 用 ``--tts``，key 只从环境变量 ``MINIMAX_API_KEY`` 读，**不落盘、不回显**。
2. **可跑**：默认零依赖（除 numpy/scipy），不联网，不需要任何密钥。
3. **看得见**：终端里把关键帧渲染成一张会动的脸 —— 这是"韵律→身体"最直接的证据。
4. **可验证**：``--self-test`` 断言链路每一环的字节级与语义级不变量。

用法::

    py -3.12 tools/demo_offline.py --text "今天真开心啊！"
    py -3.12 tools/demo_offline.py --tts --text "今天真开心啊！"      # 真实 MiniMax TTS
    py -3.12 tools/demo_offline.py --wav some.wav
    py -3.12 tools/demo_offline.py --self-test
    py -3.12 tools/demo_offline.py --outdir out --frames-shown 20

依赖事实（全部有出处，不凭记忆）：

* 帧格式 ``[Type(1)][Length(4 BE)][Payload]`` —— ``firmware/main/hal/hal_ws_avatar.cpp:234``
  注释与 ``payload(msg.data.begin() + 5, msg.data.end())``；实现见 ``tools/stackchan_server.py``。
* 0x14 DANCE 的 8 个键 —— ``tools/stackchan_server.py:176`` ``DANCE_KEYS``，
  对应固件 ``json_helper.cpp:201-224``。
* 0x14 **不带也不剥** MAC 前缀 —— ``tools/stackchan_server.py:166`` ``MAC_PREFIXED_TYPES`` 不含 0x14；
  官方 App ``app/lib/view/home/dance.dart:193`` 同样不加前缀。
* 眼睛 weight 越大越睁开、嘴 weight 越大越张开 —— 固件 ``eyes.cpp:71-78`` / ``mouth.cpp:48-59``。
* MiniMax TTS 端点与参数 —— ``docs/research/60-MiniMax账号与模型可用性实测.md`` §6：
  ``POST https://api.minimaxi.com/v1/t2a_v2``，``model=speech-02-hd``、``format=pcm``、
  ``sample_rate=16000``、``channel=1``、``bitrate=128000``、``stream=false``；
  成功判据是 ``base_resp.status_code == 0``（**不是** HTTP 状态码）。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - 老解释器兜底
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402
from scipy.io import wavfile  # noqa: E402

import prosody_to_motion as ptm  # noqa: E402
import stackchan_server as scs  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════
# 0. 常量
# ══════════════════════════════════════════════════════════════════════════

MINIMAX_BASE = "https://api.minimaxi.com"
MINIMAX_TTS_PATH = "/v1/t2a_v2"
MINIMAX_TTS_MODEL = "speech-02-hd"
# docs/research/60 §6 实测可用音色（其余 id 返回 2054 voice id not exist）
TTS_VOICES = (
    "female-shaonv",
    "presenter_female",
    "male-qn-qingse",
    "audiobook_female_1",
    "Chinese (Mandarin)_Warm_Girl",
    "female-chengshu",
)

SR = 16000
# 局域网单帧上限 65535（local_network_protocol.h:18 UINT16_MAX）
LAN_FRAME_MAX = 65535
# 远端上限 256 KB（hal_ws_avatar.cpp:146）
REMOTE_FRAME_MAX = 256 * 1024

DEFAULT_TEXT = "你好呀，今天过得怎么样？"


# ══════════════════════════════════════════════════════════════════════════
# 1. 音频源
# ══════════════════════════════════════════════════════════════════════════

def _synth_speech_like(text: str, sr: int = SR) -> np.ndarray:
    """把文本合成成一段"像语音"的信号（**演示替身，不是 TTS**）。

    做法：逐字符一个音节，按四声近似给出基频轮廓，标点处插入停顿。
    目的不是好听，而是让下游的**韵律分析有真实的音节结构可测**
    （音节核 + 基频曲线 + 停顿），否则"韵律→身体"演示就退化成噪声驱动。

    四声近似（相对基频倍数）：
      1 声 平 → 1.25 恒定
      2 声 升 → 0.82 → 1.42
      3 声 降升 → 1.00 → 0.70 → 1.18
      4 声 降 → 1.48 → 0.78
    每 4 个字给一个重音（幅度更大），让"强调"在下游可见。
    """
    base_f0 = 185.0
    per_char = 0.185           # 每字时长（秒）
    pause_map = {"，": 0.22, "、": 0.18, "。": 0.40, "！": 0.40, "？": 0.42,
                 "；": 0.26, "：": 0.22, "…": 0.35, "—": 0.20}
    tones = [1, 4, 2, 3]

    segs = []                  # (t0, t1, f0_start, f0_end, amp)
    t = 0.05
    idx = 0
    for ch in text:
        if ch.isspace():
            continue
        if ch in pause_map:
            t += pause_map[ch]
            continue
        tone = tones[idx % len(tones)]
        accent = (idx % 4 == 0)
        idx += 1
        dur = per_char * (1.25 if ch in "你我她他" else 1.0)
        if tone == 1:
            f0a, f0b = base_f0 * 1.25, base_f0 * 1.25
        elif tone == 2:
            f0a, f0b = base_f0 * 0.82, base_f0 * 1.42
        elif tone == 3:
            f0a, f0b = base_f0 * 1.00, base_f0 * 0.70
        else:
            f0a, f0b = base_f0 * 1.48, base_f0 * 0.78
        amp = 0.85 if accent else 0.55
        segs.append((t, t + dur, f0a, f0b, amp))
        t += dur

    if not segs:
        segs = [(0.05, 0.6, base_f0, base_f0, 0.6)]
        t = 0.65
    total = t + 0.25

    n = int(total * sr)
    x = np.zeros(n, dtype=np.float64)
    ts = np.arange(n) / sr

    for (t0, t1, f0a, f0b, amp) in segs:
        i0, i1 = int(t0 * sr), int(t1 * sr)
        seg_t = ts[i0:i1] - t0
        dur = max(t1 - t0, 1e-6)
        # 基频轮廓 → 相位积分
        f0 = f0a + (f0b - f0a) * (seg_t / dur)
        phase = 2 * np.pi * np.cumsum(f0) / sr
        wav = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)) / 1.75
        # 音节核：3.5 Hz 幅度调制（真实中文语速约 3~6 音节/秒）
        env = 0.62 + 0.38 * np.cos(2 * np.pi * 3.5 * seg_t)
        # 15 ms 淡入淡出（整段 Hanning 会人为制造长静音，污染停顿检测）
        fl = int(round(0.015 * sr))
        if fl * 2 < len(env):
            ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fl)))
            env[:fl] = ramp
            env[-fl:] = ramp[::-1]
        x[i0:i1] = amp * wav * env

    peak = float(np.max(np.abs(x))) or 1.0
    return (x / peak * 0.9).astype(np.float32)


def tts_minimax(text: str, voice_id: str = "female-shaonv",
                key: str = "", timeout: int = 120):
    """调 MiniMax TTS 拿 16 kHz 单声道 PCM。

    返回 ``(samples_float32, meta)``；失败抛 ``RuntimeError``（消息里**不含** key）。
    """
    key = (key or os.environ.get("MINIMAX_API_KEY", "")).strip()
    if not key:
        raise RuntimeError(
            "缺少 MINIMAX_API_KEY：请设置用户级环境变量，或改用离线模式（不加 --tts）")
    payload = {
        "model": MINIMAX_TTS_MODEL,
        "text": text,
        "stream": False,
        "voice_setting": {"voice_id": voice_id, "speed": 1.0, "vol": 1.0, "pitch": 0},
        "audio_setting": {"sample_rate": SR, "bitrate": 128000, "format": "pcm",
                          "channel": 1},
    }
    req = urllib.request.Request(
        MINIMAX_BASE + MINIMAX_TTS_PATH,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError("TTS HTTP %s：%s" % (e.code, e.read()[:200].decode("utf-8", "replace")))
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("TTS 网络失败：%s" % (e,))

    try:
        d = json.loads(body)
    except Exception:  # noqa: BLE001
        raise RuntimeError("TTS 返回非 JSON：%r" % (body[:200],))

    base = d.get("base_resp") or {}
    if base.get("status_code") != 0:
        # 2054 = voice id not exist；1008 = 余额不足。两者必须分开判（60 号 §6.1）
        raise RuntimeError("TTS 失败 base_resp=%s" % json.dumps(base, ensure_ascii=False))

    hexs = ((d.get("data") or {}).get("audio")) or ""
    raw = bytes.fromhex(hexs)
    if not raw:
        raise RuntimeError("TTS 返回空音频")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    meta = {
        "source": "minimax-tts",
        "model": MINIMAX_TTS_MODEL,
        "voice_id": voice_id,
        "sample_rate": SR,
        "channels": 1,
        "bytes": len(raw),
        "duration_s": round(len(raw) / 2 / SR, 3),
    }
    return samples, meta


# ══════════════════════════════════════════════════════════════════════════
# 2. 链路上的一环：设备侧解析（复刻固件行为）
# ══════════════════════════════════════════════════════════════════════════

def device_side_parse(frame: bytes) -> dict:
    """模拟固件收到一帧后的处理，返回解析结果。

    复刻点（依据固件源码）：
      * 帧头 ``[Type(1)][Length(4 BE)]``，payload 从 offset 5 开始
        —— ``hal_ws_avatar.cpp:234/243``。
      * 0x14 的 payload 必须是**数组**，否则固件拒绝
        —— ``json_helper.cpp:192-195``（强制数组）。
      * 每帧必须含 8 个键，缺一个固件就跳过该帧
        —— ``json_helper.cpp:201-224``。
    """
    out = {"ok": False, "type": None, "reason": "", "keyframes": 0}
    if len(frame) < 5:
        out["reason"] = "帧长不足 5 字节"
        return out
    mtype = frame[0]
    length = int.from_bytes(frame[1:5], "big")
    out["type"] = mtype
    if len(frame) - 5 != length:
        out["reason"] = "长度字段 %d 与实际载荷 %d 不符" % (length, len(frame) - 5)
        return out
    body = frame[5:]
    try:
        obj = json.loads(body.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        out["reason"] = "JSON 解析失败：%s" % (e,)
        return out
    if not isinstance(obj, list):
        out["reason"] = "0x14 payload 不是数组（固件会拒绝）"
        return out
    good = 0
    for kf in obj:
        if not isinstance(kf, dict):
            continue
        if set(kf.keys()) != set(scs.DANCE_KEYS):
            continue
        good += 1
    out["keyframes"] = good
    out["accepted"] = good
    out["ok"] = good > 0
    if good == 0:
        out["reason"] = "没有任何一帧含全部 8 个键"
    return out


# ══════════════════════════════════════════════════════════════════════════
# 3. 脸渲染（终端）
# ══════════════════════════════════════════════════════════════════════════

def _eye_glyph(weight: int) -> str:
    """眼睛 weight 越大越睁开（固件 eyes.cpp:71-78）。"""
    o = max(0, min(100, int(weight))) / 100.0
    if o >= 0.85:
        return "●"
    if o >= 0.60:
        return "◕"
    if o >= 0.35:
        return "◔"
    if o > 0.0:
        return "◡"
    return "─"


def _mouth_glyph(weight: int) -> str:
    """嘴 weight 越大越张开（固件 mouth.cpp:48-59）。"""
    w = max(0, min(100, int(weight)))
    if w >= 70:
        return "◯"
    if w >= 45:
        return "○"
    if w >= 20:
        return "◡"
    return "‿"


def _rgb(hexcolor: str):
    h = (hexcolor or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        return (255, 255, 255)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def _colorize(text: str, hexcolor: str, enabled: bool) -> str:
    if not enabled:
        return text
    r, g, b = _rgb(hexcolor)
    return "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (r, g, b, text)


def render_face(kf: dict, color: bool = True, box: bool = True) -> list:
    """把一帧关键帧渲染成几行终端字符。

    映射依据：
      * 眼睛/嘴的 x、y 是 JSON 单位 ±100（对应固件像素 ±16，系数 6.25）
        —— 这里按 ±100 → ±4 列 / ±1 行的比例缩放到字符画布。
      * yawServo.angle 是 0.1 度，限位 ±1280 —— 映射成头部水平偏移 ±3 列。
      * pitchServo.angle 限位 30..870，中位 450 —— 映射成垂直偏移 ±1 行。
    """
    le = kf["leftEye"]
    re_ = kf["rightEye"]
    mo = kf["mouth"]

    yaw = int(kf["yawServo"]["angle"]) / 10.0       # 度
    pitch = int(kf["pitchServo"]["angle"]) / 10.0   # 度

    shift_x = int(round(max(-3.0, min(3.0, yaw / 128.0 * 3.0))))
    lift_y = int(round(max(-1.0, min(1.0, (450.0 - pitch) / 420.0))))

    left_col = 7 + int(round(le["x"] / 100.0 * 4.0)) + shift_x
    right_col = 7 + 10 + int(round(re_["x"] / 100.0 * 4.0)) + shift_x
    eye_row = max(0, 1 + int(round(le["y"] / 100.0)) + lift_y)
    mouth_row = max(0, 3 + int(round(mo["y"] / 100.0)) + lift_y)
    mouth_col = max(0, 12 + int(round(mo["x"] / 100.0 * 4.0)) + shift_x // 2)

    width = 26
    lines = []
    for r in range(5):
        buf = [" "] * width
        if r == eye_row:
            buf[left_col] = _eye_glyph(le["weight"])
            buf[right_col] = _eye_glyph(re_["weight"])
        if r == mouth_row:
            buf[mouth_col] = _mouth_glyph(mo["weight"])
        lines.append("".join(buf).rstrip())

    # 上色：眼睛用左右 RGB 灯色，嘴用白色
    out = []
    for idx, ln in enumerate(lines):
        painted = ln
        if idx == eye_row:
            painted = (painted[:left_col]
                       + _colorize(painted[left_col], kf["leftRgbColor"], color)
                       + painted[left_col + 1:right_col]
                       + _colorize(painted[right_col], kf["rightRgbColor"], color)
                       + painted[right_col + 1:])
        elif idx == mouth_row:
            painted = (painted[:mouth_col]
                       + _colorize(painted[mouth_col], "#FFFFFF", color)
                       + painted[mouth_col + 1:])
        out.append(painted)

    if not box:
        return out

    framed = ["┌" + "─" * width + "┐"]
    for ln in out:
        framed.append("│" + ln.ljust(width) + "│")
    framed.append("└" + "─" * width + "┘")
    return framed


# ══════════════════════════════════════════════════════════════════════════
# 4. 主流程
# ══════════════════════════════════════════════════════════════════════════

def run_chain(samples: np.ndarray, sr: int, emotion: str = "Neutral"):
    """韵律 → 关键帧 → 载荷 → WS 帧 → 设备侧解析。返回一份结果字典。

    ⭐ 同时给出**音画对齐误差**：关键帧总时长 vs 音频时长。
    这是「手机出声 + 设备做身体」架构（docs/research/64 号）成立的前提 ——
    音频与动作必须**同源**，否则嘴和声音会错位。
    """
    feat, track = ptm.extract_prosody(samples, sr)
    params = ptm.build_params(emotion, feat)
    kfs, info = ptm.compile_keyframes(track, feat, params, emotion)
    avatar = ptm.build_avatar(kfs, emotion)
    rep = ptm.audit(kfs)

    payload = scs.build_dance_payload(kfs)
    frame = scs.encode_frame(scs.DANCE, payload)
    parsed = device_side_parse(frame)

    audio_ms = int(round(len(samples) / float(sr) * 1000.0))
    total_ms = int(rep["durationMs_total"])
    align_ms = total_ms - audio_ms

    return {
        "features": feat.as_dict(),
        "params": params,
        "anchors": {k: v for k, v in info.items() if k != "accentNodDegrees"},
        "keyframes": kfs,
        "avatar": avatar,
        "audit": rep,
        "payload_bytes": len(payload),
        "frame_bytes": len(frame),
        "frame_hex_head": frame[:9].hex(),
        "device": parsed,
        "audio_duration_ms": audio_ms,
        "align_error_ms": align_ms,
    }


def _write_text(path: str, text: str):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _fmt_metrics(res: dict) -> list:
    a = res["audit"]
    rows = [
        ("关键帧数", str(a["keyframeCount"])),
        ("总时长", "%d ms（%.2f s）" % (a["durationMs_total"], a["durationMs_total"] / 1000.0)),
        ("输出帧率", "%d fps（durationMs=%d）" % (ptm.OUT_FPS, ptm.OUT_DT_MS)),
        ("音画对齐", "%+d ms（关键帧总时长 − 音频时长；容差 ±1 帧 = ±%d ms）"
            % (res.get("align_error_ms", 0), ptm.OUT_DT_MS)),
        ("0x14 载荷", "%d B" % res["payload_bytes"]),
        ("WS 帧总长", "%d B（头 5 B + 载荷）" % res["frame_bytes"]),
        ("局域网上限", "%d B ⇒ %s" % (LAN_FRAME_MAX,
                                     "✅ 在限内" if res["payload_bytes"] <= LAN_FRAME_MAX
                                     else "⚠️ 超限，需分片")),
        ("远端上限", "%d B ⇒ %s" % (REMOTE_FRAME_MAX,
                                    "✅ 在限内" if res["payload_bytes"] <= REMOTE_FRAME_MAX
                                    else "⚠️ 超限")),
        ("设备侧解析", "%s（接受 %d/%d 帧）" % (
            "✅ 通过" if res["device"]["ok"] else "❌ " + res["device"]["reason"],
            res["device"].get("accepted", 0), a["keyframeCount"])),
        ("审计问题", "%d 项" % len(a["problems"])),
        ("审计告警", "%d 项" % len(a["warnings"])),
    ]
    return rows


def _report_markdown(text: str, audio_meta: dict, res: dict, emotion: str) -> str:
    a = res["audit"]
    feat_rows = "\n".join("| `{}` | {} |".format(k, v)
                          for k, v in res["features"].items())
    rng = a.get("ranges", {})
    rng_rows = "\n".join("| `{}` | {} | {} |".format(k, v[0], v[1])
                         for k, v in rng.items())
    met_rows = "\n".join("| {} | {} |".format(k, v) for k, v in _fmt_metrics(res))
    src = audio_meta.get("source", "unknown")
    src_note = {
        "offline-synth": "离线合成音频（**演示替身，不是 TTS**）",
        "minimax-tts": "MiniMax TTS 真实音频",
        "wav-file": "本地 WAV 文件",
    }.get(src, src)
    return "\n".join([
        "# 全链路 Demo 报告",
        "",
        "## 输入",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| 文本 | {} |".format(text.replace("|", "\\|")),
        "| 情绪 | {} |".format(emotion),
        "| 音频来源 | {} |".format(src_note),
        "| 采样率 | {} Hz |".format(audio_meta.get("sample_rate", SR)),
        "| 音频时长 | {} s |".format(audio_meta.get("duration_s", 0)),
        "",
        "## 韵律特征（7 维）",
        "",
        "| 特征 | 值 |",
        "|---|---|",
        feat_rows,
        "",
        "## 输出范围",
        "",
        "| 字段 | min | max |",
        "|---|---|---|",
        rng_rows,
        "",
        "## 链路指标",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        met_rows,
        "",
        "## 审计",
        "",
        "- 问题：{} 项".format(len(a["problems"])),
        "- 告警：{} 项".format(len(a["warnings"])),
        "",
    ])


def cmd_demo(args) -> int:
    text = args.text
    sr = SR

    # ── 1. 取音频 ───────────────────────────────────────────────────────
    if args.wav:
        sr, data = wavfile.read(args.wav)
        if data.ndim > 1:
            data = data.mean(axis=1)
        samples = data.astype(np.float32) / (32768.0 if data.dtype == np.int16 else 1.0)
        audio_meta = {"source": "wav-file", "sample_rate": int(sr),
                      "duration_s": round(len(samples) / float(sr), 3),
                      "path": os.path.abspath(args.wav)}
    elif args.tts:
        samples, audio_meta = tts_minimax(text, args.voice)
    else:
        samples = _synth_speech_like(text, sr)
        audio_meta = {"source": "offline-synth", "sample_rate": sr,
                      "duration_s": round(len(samples) / float(sr), 3)}

    # ── 2. 跑链路 ───────────────────────────────────────────────────────
    res = run_chain(samples, sr, args.emotion)
    a = res["audit"]

    # ── 3. 终端输出 ─────────────────────────────────────────────────────
    color = not args.no_color and sys.stdout.isatty()
    print("=" * 74)
    print("StackChan Companion · 全链路 Demo")
    print("=" * 74)
    print("文本      : {}".format(text))
    print("音频来源  : {}".format({
        "offline-synth": "离线合成（演示替身，非 TTS）",
        "minimax-tts": "MiniMax TTS（{}）".format(audio_meta.get("voice_id", "")),
        "wav-file": os.path.basename(audio_meta.get("path", "")),
    }[audio_meta["source"]]))
    print("音频      : {:.2f} s @ {} Hz".format(audio_meta["duration_s"],
                                                audio_meta["sample_rate"]))
    print("-" * 74)
    for k, v in _fmt_metrics(res):
        print("  {:<12}: {}".format(k, v))
    print("-" * 74)
    print("韵律 7 维 :")
    for k, v in res["features"].items():
        print("    {:<12}: {}".format(k, v))
    print("-" * 74)

    # 画脸
    kfs = res["keyframes"]
    n_show = max(1, min(args.frames_shown, len(kfs)))
    step = max(1, len(kfs) // n_show)
    shown = list(range(0, len(kfs), step))[:n_show]
    if shown[-1] != len(kfs) - 1:
        shown.append(len(kfs) - 1)
    print("设备脸上的脸（每帧 {} ms，抽样 {} 帧）：".format(ptm.OUT_DT_MS, len(shown)))
    for idx in shown:
        kf = kfs[idx]
        t_ms = idx * ptm.OUT_DT_MS
        lines = render_face(kf, color=color)
        print("  [t={:6.2f}s] eyeW={:3d} mouthW={:3d} yaw={:5d} pitch={:4d}".format(
            t_ms / 1000.0, kf["leftEye"]["weight"], kf["mouth"]["weight"],
            kf["yawServo"]["angle"], kf["pitchServo"]["angle"]))
        for ln in lines:
            print("    " + ln)
    print("=" * 74)

    if a["problems"]:
        print("❌ 审计问题：")
        for p in a["problems"]:
            print("   - " + p)
    if a["warnings"]:
        print("⚠️ 审计告警：")
        for w in a["warnings"]:
            print("   - " + w)

    # ── 4. 落盘 ─────────────────────────────────────────────────────────
    if args.outdir:
        outdir = os.path.abspath(args.outdir)
        os.makedirs(outdir, exist_ok=True)
        _write_text(os.path.join(outdir, "demo_keyframes.json"),
                    json.dumps(kfs, ensure_ascii=False, indent=2) + "\n")
        _write_text(os.path.join(outdir, "demo_report.md"),
                    _report_markdown(text, audio_meta, res, args.emotion))
        lines = ["t_ms,yaw_raw,pitch_raw,left_eye_w,right_eye_w,mouth_w,"
                 "left_rgb,right_rgb"]
        for i, k in enumerate(kfs):
            lines.append("{},{},{},{},{},{},{},{}".format(
                i * ptm.OUT_DT_MS, k["yawServo"]["angle"], k["pitchServo"]["angle"],
                k["leftEye"]["weight"], k["rightEye"]["weight"], k["mouth"]["weight"],
                k["leftRgbColor"], k["rightRgbColor"]))
        _write_text(os.path.join(outdir, "demo_frames.csv"), "\n".join(lines) + "\n")
        # 画脸逐帧留档（纯文本，含 ANSI 需 --no-color 才可读，这里写无色版）
        flip = []
        for i, k in enumerate(kfs):
            flip.append("[t={:6.2f}s]".format(i * ptm.OUT_DT_MS / 1000.0))
            flip.extend(render_face(k, color=False))
        _write_text(os.path.join(outdir, "demo_face.txt"), "\n".join(flip) + "\n")
        print("产物 → {}".format(outdir))
        for fn in ("demo_keyframes.json", "demo_report.md", "demo_frames.csv",
                   "demo_face.txt"):
            print("   - {}".format(fn))

    if args.json:
        _write_text(args.json, json.dumps({
            "text": text,
            "audio": audio_meta,
            "features": res["features"],
            "metrics": {k: v for k, v in _fmt_metrics(res)},
            "audit": {"problems": a["problems"], "warnings": a["warnings"]},
        }, ensure_ascii=False, indent=2) + "\n")
        print("JSON → {}".format(os.path.abspath(args.json)))

    return 0 if (not a["problems"] and res["device"]["ok"]) else 1


# ══════════════════════════════════════════════════════════════════════════
# 5. 自检
# ══════════════════════════════════════════════════════════════════════════

def self_test(verbose: bool = True) -> int:
    ok = True
    fails = []
    total = 0

    def chk(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            if verbose:
                print("  PASS  {}{}".format(name, ("  (" + detail + ")") if detail else ""))
        else:
            ok = False
            fails.append("{} :: {}".format(name, detail))
            print("  FAIL  {}  {}".format(name, detail))

    print("=" * 74)
    print("自检 1：离线合成音频 → 韵律提取")
    print("=" * 74)
    text = "今天真开心啊！"
    x = _synth_speech_like(text, SR)
    chk("音频非空", x.size > 0, "{} samples".format(x.size))
    chk("无 NaN/Inf", bool(np.all(np.isfinite(x))))
    chk("幅度在 [-1,1]", float(np.max(np.abs(x))) <= 1.0)

    feat, track = ptm.extract_prosody(x, SR)
    fd = feat.as_dict()
    chk("基频被检出", fd.get("f0_mean_hz", 0) > 0,
        "f0_mean_hz={}".format(fd.get("f0_mean_hz")))
    chk("语速落在 2~8 音节/秒", 2.0 <= fd.get("speech_rate_hz", 0) <= 8.0,
        "speech_rate_hz={}".format(fd.get("speech_rate_hz")))
    chk("检出停顿", fd.get("pause_count", 0) >= 1,
        "pause_count={}".format(fd.get("pause_count")))
    chk("有声占比合理", 0.3 <= fd.get("voiced_ratio", 0) <= 1.0,
        "voiced_ratio={}".format(fd.get("voiced_ratio")))

    print()
    print("=" * 74)
    print("自检 2：关键帧 → 0x14 载荷 → WS 帧 → 设备侧解析")
    print("=" * 74)
    res = run_chain(x, SR, "Neutral")
    a = res["audit"]
    chk("关键帧数 > 0", a["keyframeCount"] > 0, "n={}".format(a["keyframeCount"]))
    chk("审计无问题", not a["problems"], str(a["problems"][:2]))
    chk("每帧 8 个键", all(set(k.keys()) == set(scs.DANCE_KEYS) for k in res["keyframes"]))
    chk("载荷非空", res["payload_bytes"] > 0, "{} B".format(res["payload_bytes"]))
    chk("帧长 = 5 + 载荷", res["frame_bytes"] == res["payload_bytes"] + 5)
    chk("帧头 type=0x14", res["frame_hex_head"][:2] == "14",
        res["frame_hex_head"][:2])
    chk("长度字段大端正确",
        int(res["frame_hex_head"][2:10], 16) == res["payload_bytes"],
        res["frame_hex_head"][2:10])
    chk("设备侧接受全部帧",
        res["device"]["accepted"] == a["keyframeCount"],
        "{}/{}".format(res["device"]["accepted"], a["keyframeCount"]))

    print()
    print("=" * 74)
    print("自检 2b：音画同源与对齐（手机出声 + 设备做身体 的前提）")
    print("=" * 74)
    # 关键帧与音频来自**同一段 PCM** ⇒ 时间轴天然同源；
    # 关键帧被量化到 25 fps 栅格（durationMs=40）⇒ 误差应在一帧以内。
    err_ms = res["align_error_ms"]
    chk("音画对齐误差 ≤ 1 帧（%d ms）" % ptm.OUT_DT_MS,
        abs(err_ms) <= ptm.OUT_DT_MS,
        "误差 %+d ms（音频 %d ms vs 关键帧 %d ms）"
        % (err_ms, res["audio_duration_ms"], a["durationMs_total"]))
    chk("关键帧总时长 = 帧数 × durationMs",
        a["durationMs_total"] == a["keyframeCount"] * ptm.OUT_DT_MS,
        "{} 帧 × {} ms = {} ms".format(a["keyframeCount"], ptm.OUT_DT_MS,
                                       a["durationMs_total"]))
    # 音频越长误差占比越小：验证「时长是解析出来的、不是写死的」
    long_x = _synth_speech_like(text * 3, SR)
    long_res = run_chain(long_x, SR, "Neutral")
    chk("加长文本后误差仍在 1 帧内",
        abs(long_res["align_error_ms"]) <= ptm.OUT_DT_MS,
        "误差 %+d ms" % long_res["align_error_ms"])
    chk("加长文本后总时长确实变长",
        long_res["audit"]["durationMs_total"] > a["durationMs_total"],
        "%d ms > %d ms" % (long_res["audit"]["durationMs_total"], a["durationMs_total"]))

    print()
    print("=" * 74)
    print("自检 3：0x14 不带 MAC 前缀（与官方 App 一致）")
    print("=" * 74)
    chk("0x14 不在剥 MAC 名单里", scs.DANCE not in scs.MAC_PREFIXED_TYPES)
    # 0x14 的 payload 是 JSON **数组**（固件 json_helper.cpp:192-195 强制数组），
    # 所以首字节是 '[' (0x5b)；若带 MAC 前缀，首字节会是 12 字节 MAC 的第 1 字节。
    chk("payload 首字节是 '['（数组，不是 MAC）",
        res["frame_hex_head"][10:12] == "5b", res["frame_hex_head"][10:12])

    print()
    print("=" * 74)
    print("自检 4：载荷上限")
    print("=" * 74)
    chk("局域网载荷在 65535 内", res["payload_bytes"] <= LAN_FRAME_MAX,
        "{} B".format(res["payload_bytes"]))

    print()
    print("=" * 74)
    print("自检 5：脸渲染")
    print("=" * 74)
    kf = res["keyframes"][0]
    lines = render_face(kf, color=False)
    chk("渲染出 5+2 行", len(lines) == 7, "{} 行".format(len(lines)))
    joined = "\n".join(lines)
    chk("画布里能找到嘴", any(ch in joined for ch in "◯○◡‿"))
    chk("满权重眼睛是 ●", _eye_glyph(100) == "●")
    chk("闭眼是 ─", _eye_glyph(0) == "─")
    chk("张嘴是 ◯", _mouth_glyph(100) == "◯")
    chk("闭嘴是 ‿", _mouth_glyph(0) == "‿")

    print()
    print("=" * 74)
    print("自检 6：设备侧拒绝非法载荷")
    print("=" * 74)
    bad = scs.encode_frame(scs.DANCE, b'{"not":"an array"}')
    p = device_side_parse(bad)
    chk("对象载荷被拒", not p["ok"], p["reason"])
    bad2 = scs.encode_frame(scs.DANCE, b'[]')
    p2 = device_side_parse(bad2)
    chk("空数组被拒", not p2["ok"], p2["reason"])
    short = scs.encode_frame(scs.DANCE, b"x" * 10)[:8]
    p3 = device_side_parse(short)
    chk("截断帧被拒", not p3["ok"], p3["reason"])

    print()
    print("=" * 74)
    if ok:
        print("自检结果：ALL PASS（{} 项断言）".format(total))
        print("=" * 74)
        return 0
    print("自检结果：FAIL {} 项".format(len(fails)))
    for f in fails:
        print("   - " + f)
    print("=" * 74)
    return 1


# ══════════════════════════════════════════════════════════════════════════
# 6. CLI
# ══════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="StackChan Companion 全链路 Demo：文本 → 韵律 → 关键帧 → 脸")
    ap.add_argument("--text", default=DEFAULT_TEXT, help="要说的文本")
    ap.add_argument("--emotion", default="Neutral",
                    help="情绪（Neutral/Happy/Angry/Sad/Doubt/Sleepy）")
    ap.add_argument("--tts", action="store_true",
                    help="用 MiniMax TTS 生成真实音频（需 MINIMAX_API_KEY）")
    ap.add_argument("--voice", default="female-shaonv", help="TTS 音色 id")
    ap.add_argument("--wav", help="直接用本地 WAV（16k/单声道最佳）")
    ap.add_argument("--outdir", help="产物输出目录")
    ap.add_argument("--json", help="把摘要写到 JSON 文件")
    ap.add_argument("--frames-shown", type=int, default=10,
                    help="终端画多少帧（默认 10）")
    ap.add_argument("--no-color", action="store_true", help="关闭 ANSI 颜色")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.wav and args.tts:
        print("⚠️ --wav 与 --tts 不能同时给", file=sys.stderr)
        return 2

    try:
        return cmd_demo(args)
    except RuntimeError as e:
        print("❌ {}".format(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
