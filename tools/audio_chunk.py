#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audio_chunk —— 把 PCM 音频切成与 0x14 关键帧**共用同一时间栅格**的片段。

为什么需要这个工具
==================

架构裁决（`docs/research/64-固件音频通道取证与谁出声架构裁决.md`）：
**手机出声，设备做身体**。声音由 iOS App 播，设备只执行 0x14 关键帧。

⇒ 两条时间轴必须对齐：

* **音频轴**：PCM 采样点 → 毫秒（App 的 `AVAudioPlayerNode` 播放时钟）
* **动作轴**：0x14 关键帧 → `durationMs`（设备的动作时间轴）

两轴的**唯一可靠公共点**是：**同一段 PCM**（关键帧就是从这段 PCM 推出来的）。
本工具把这个"对齐"从口头承诺变成**机器可判**：

1. `plan_chunks()` —— 按**帧栅格**（默认 40 ms = 0x14 的 `durationMs`）切音频，
   保证每个片段的边界**正好落在关键帧边界上**；
2. `verify_against_keyframes()` —— 拿真实关键帧 JSON 反查：
   音频片段 i 的时间窗 == 关键帧 [i×N, (i+1)×N) 的时间窗；
3. `align_error_ms()` —— 音频总时长与关键帧总时长的误差（应 ≤ 一帧）。

用法::

    py -3.12 tools/audio_chunk.py --self-test
    py -3.12 tools/audio_chunk.py --pcm pcm.bin --outdir chunks --frames-per-chunk 4
    py -3.12 tools/audio_chunk.py --keyframes keyframes.json --wav voice.wav --verify

约定
====

* **PCM 格式**：16 kHz、单声道、16-bit 小端（= MiniMax TTS `format=pcm` 的原生输出，
  也是 `server/stackchan_ai/tts.py` 的输出约定）。
* **帧栅格**：默认 40 ms（= `tools/prosody_to_motion.py` 的 `OUT_DT_MS`，
  = 固件 0x14 的 `durationMs`）。**不要**改这个默认值去迁就别的栅格 ——
  两边必须同栅格，否则嘴和声音会错位。
* **一片 = N 帧**（默认 N=4，即 160 ms / 2560 采样 / 5120 字节）。
  N=1 ⇒ 每帧一片（最稳、延时最低、包最多）；N 越大 ⇒ 包越少、延时越大。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import struct
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

# ── 协议常量（与 tools/prosody_to_motion.py、server/stackchan_ai/prosody.py 同源）────
SAMPLE_RATE = 16000          # Hz
BYTES_PER_SAMPLE = 2         # PCM16
FRAME_MS = 40                # 0x14 的 durationMs（帧栅格）
DEFAULT_FRAMES_PER_CHUNK = 4 # 一片 = 4 帧 = 160 ms

#: 一帧对应的采样数（= 40 ms @ 16 kHz）
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000        # 640
#: 一帧对应的字节数
BYTES_PER_FRAME = SAMPLES_PER_FRAME * BYTES_PER_SAMPLE    # 1280


# ══════════════════════════════════════════════════════════════════════════
# 1. 切片计划
# ══════════════════════════════════════════════════════════════════════════

def plan_chunks(total_samples: int, frames_per_chunk: int = DEFAULT_FRAMES_PER_CHUNK,
                sample_rate: int = SAMPLE_RATE, keyframes: list = None) -> list:
    """把整段音频切成与帧栅格对齐的片段。

    两种切法（``keyframes`` 给了就走关键帧驱动，否则走纯时间栅格）：

    A. **纯时间栅格**（``keyframes=None``）
       片边界固定落在 ``N × 40 ms`` 的整数倍上。
       隐患：真实 TTS 的 PCM 长度**常常不是 40 ms 的整数倍**
       （实测 MiniMax TTS「今天真开心啊！」= 2350 ms），
       于是**末片的 endMs 会落在关键帧栅格之外** ⇒ 对账失败。

    B. **关键帧驱动**（给了 ``keyframes``）
       片边界对齐到**关键帧分组边界**：第 i 片对应关键帧
       ``[i×N, (i+1)×N)``，音频字节按该组关键帧的时间窗裁剪，
       末组若超出音频尾部则按**真实音频尾**截断。
       ⇒ 每片的「音频窗 ↔ 关键帧组」是**精确一一对应**的，
       这是 App 侧唯一需要的映射关系。

    Returns:
        [{"index", "startMs", "endMs", "durationMs", "offsetBytes", "lengthBytes",
          "samples", "frames", "remainderSamples", "partial",
          "keyframeStart", "keyframeEnd"}]
        ``keyframeStart`` / ``keyframeEnd``（**闭区间**）只在 B 模式下有值。

        字段语义（**别混**）：

        * ``frames`` —— 本片包含的**完整帧**数（A 模式）或**关键帧**数（B 模式）；
        * ``remainderSamples`` —— 本片尾部**不足一帧**的零头采样数（>0 ⇒ 音频长度没落在帧栅格上）；
        * ``partial`` —— 本片**不是**满 N 帧 **或** 带零头。
          ⇒ 「最后一片是残片」与「音频没对齐帧栅格」两种情况都会被它标出来。
    """
    if frames_per_chunk < 1:
        raise ValueError("frames_per_chunk must be >= 1")
    if total_samples < 0:
        raise ValueError("total_samples must be >= 0")

    if keyframes is not None:
        return _plan_by_keyframes(total_samples, keyframes, frames_per_chunk, sample_rate)

    samples_per_frame = int(sample_rate * FRAME_MS / 1000)
    samples_per_chunk = samples_per_frame * frames_per_chunk
    bytes_per_chunk = samples_per_chunk * BYTES_PER_SAMPLE

    chunks = []
    offset = 0
    index = 0
    while offset < total_samples:
        remaining = total_samples - offset
        take = min(remaining, samples_per_chunk)
        frames = take // samples_per_frame
        rest = take % samples_per_frame
        chunks.append({
            "index": index,
            "startMs": int(round(offset / sample_rate * 1000.0)),
            "endMs": int(round((offset + take) / sample_rate * 1000.0)),
            "durationMs": int(round(take / sample_rate * 1000.0)),
            "offsetBytes": offset * BYTES_PER_SAMPLE,
            "lengthBytes": take * BYTES_PER_SAMPLE,
            "samples": take,
            "frames": frames,
            "remainderSamples": rest,
            # 残片 = 不足满 N 帧 **或** 尾部带非整帧零头
            "partial": bool(rest) or frames < frames_per_chunk,
        })
        offset += take
        index += 1
    return chunks


def _plan_by_keyframes(total_samples: int, keyframes: list,
                       frames_per_chunk: int, sample_rate: int) -> list:
    """关键帧驱动的切片（模式 B）。

    第 i 片对应关键帧 ``[i×N, min((i+1)×N, K)-1]``（闭区间），
    音频字节取该组关键帧时间窗，**并按真实音频尾部截断**。
    """
    tl = keyframe_timeline(keyframes)
    if not tl:
        return []
    total_samples = int(total_samples)
    out = []
    for g0 in range(0, len(tl), frames_per_chunk):
        g1 = min(g0 + frames_per_chunk, len(tl)) - 1      # 闭区间
        start_ms = tl[g0]["startMs"]
        end_ms = tl[g1]["endMs"]
        s0 = int(round(start_ms / 1000.0 * sample_rate))
        s1 = min(int(round(end_ms / 1000.0 * sample_rate)), total_samples)
        if s1 <= s0:
            # 该组关键帧已经完全落在音频尾部之外（量化补齐出来的空转）⇒ 不再产片
            break
        take = s1 - s0
        n_kf = g1 - g0 + 1
        out.append({
            "index": len(out),
            "startMs": start_ms,
            "endMs": end_ms,
            "durationMs": end_ms - start_ms,
            "offsetBytes": s0 * BYTES_PER_SAMPLE,
            "lengthBytes": take * BYTES_PER_SAMPLE,
            "samples": take,
            "frames": n_kf,
            "remainderSamples": take % SAMPLES_PER_FRAME,
            "partial": n_kf < frames_per_chunk or (take % SAMPLES_PER_FRAME) != 0,
            "keyframeStart": g0,
            "keyframeEnd": g1,
        })
    return out


def chunk_pcm(pcm: bytes, frames_per_chunk: int = DEFAULT_FRAMES_PER_CHUNK,
              sample_rate: int = SAMPLE_RATE, keyframes: list = None) -> list:
    """按 ``plan_chunks`` 的计划切 PCM。返回 ``[(meta, bytes), ...]``。

    传了 ``keyframes`` 就走**关键帧驱动**切法（模式 B）。
    """
    if len(pcm) % BYTES_PER_SAMPLE != 0:
        raise ValueError("pcm length %d is not a multiple of %d bytes"
                         % (len(pcm), BYTES_PER_SAMPLE))
    total_samples = len(pcm) // BYTES_PER_SAMPLE
    out = []
    for meta in plan_chunks(total_samples, frames_per_chunk, sample_rate, keyframes):
        seg = pcm[meta["offsetBytes"]:meta["offsetBytes"] + meta["lengthBytes"]]
        out.append((meta, seg))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 2. 与 0x14 关键帧对账
# ══════════════════════════════════════════════════════════════════════════

def load_keyframes(path: str) -> list:
    """读关键帧 JSON（数组，或含 ``keyframes`` 键的对象）。"""
    with io.open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("keyframes", "sequence", "frames"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("keyframes file must contain an array")
    return data


def keyframe_timeline(keyframes: list) -> list:
    """关键帧 → 时间窗列表 ``[{index, startMs, endMs, durationMs}]``。"""
    out = []
    t = 0
    for i, kf in enumerate(keyframes):
        d = int(kf.get("durationMs", 0) or 0)
        out.append({"index": i, "startMs": t, "endMs": t + d, "durationMs": d})
        t += d
    return out


def _as_meta_list(chunks) -> list:
    """把片段列表统一成「meta dict 列表」。

    ``chunk_pcm()`` 返回的是 ``[(meta, bytes), ...]``，而 ``plan_chunks()``
    返回的是 ``[meta, ...]``。对账函数必须**两种都吃** —— 否则 CLI 的
    ``--verify``（传 ``chunk_pcm`` 的结果）会在 dict 索引上直接崩。
    """
    out = []
    for c in chunks or []:
        if isinstance(c, dict):
            out.append(c)
        elif isinstance(c, (tuple, list)) and c and isinstance(c[0], dict):
            out.append(c[0])
        else:
            raise TypeError("无法从 %r 提取片段元数据" % (type(c).__name__,))
    return out


def verify_against_keyframes(chunks: list, keyframes: list,
                             frames_per_chunk: int = None) -> dict:
    """核对音频片段与关键帧是否落在**同一时间栅格**上。

    判定：
    * 音频总时长与关键帧总时长的误差 ≤ 一帧（FRAME_MS）；
    * 每个片段的起止时间都能在关键帧时间轴上找到**对应边界**；
    * 片段数 == ceil(关键帧数 / frames_per_chunk)。

    ``chunks`` 可以是 ``plan_chunks()`` 的 dict 列表，也可以是
    ``chunk_pcm()`` 的 ``(meta, bytes)`` 元组列表。

    Returns:
        {"ok", "reason", "audioMs", "keyframesMs", "errorMs", "chunkCount",
         "keyframesCount", "expectedChunks", "framesPerChunk", "mismatches": [...]}
    """
    metas = _as_meta_list(chunks)
    tl = keyframe_timeline(keyframes)
    kf_ms = tl[-1]["endMs"] if tl else 0
    audio_ms = metas[-1]["endMs"] if metas else 0
    error_ms = audio_ms - kf_ms

    if frames_per_chunk is None:
        # 由片段里**满片**的帧数反推（首片通常满；用 max 更稳）
        frames_per_chunk = max((m.get("frames", 0) for m in metas), default=0)
        if frames_per_chunk <= 0:
            frames_per_chunk = DEFAULT_FRAMES_PER_CHUNK
    expected = (len(tl) + frames_per_chunk - 1) // frames_per_chunk if frames_per_chunk else 0

    mismatches = []
    # 关键帧边界集合（毫秒）
    boundaries = {0}
    for e in tl:
        boundaries.add(e["endMs"])
    for c in metas:
        if c["startMs"] not in boundaries:
            mismatches.append({"chunk": c["index"], "field": "startMs",
                               "value": c["startMs"]})
        if c["endMs"] not in boundaries:
            mismatches.append({"chunk": c["index"], "field": "endMs",
                               "value": c["endMs"]})

    # 关键帧驱动模式：额外核对「每片对应的关键帧区间」是否首尾相接、且覆盖全部关键帧
    if any("keyframeStart" in c for c in metas):
        for i, c in enumerate(metas):
            if c["keyframeStart"] != (0 if i == 0 else metas[i - 1]["keyframeEnd"] + 1):
                mismatches.append({"chunk": c["index"], "field": "keyframeStart",
                                   "value": c["keyframeStart"]})
            if c["keyframeEnd"] < c["keyframeStart"]:
                mismatches.append({"chunk": c["index"], "field": "keyframeEnd",
                                   "value": c["keyframeEnd"]})
        if metas and metas[-1]["keyframeEnd"] != len(tl) - 1:
            mismatches.append({"chunk": metas[-1]["index"], "field": "keyframeEnd",
                               "value": metas[-1]["keyframeEnd"]})

    ok = (abs(error_ms) <= FRAME_MS
          and not mismatches
          and len(metas) == expected)
    reason = ""
    if not ok:
        if abs(error_ms) > FRAME_MS:
            reason = "音画时长误差 %d ms 超过一帧（%d ms）" % (error_ms, FRAME_MS)
        elif mismatches:
            reason = "有 %d 个片段边界不落在关键帧栅格上" % len(mismatches)
        else:
            reason = "片段数 %d != 期望 %d" % (len(metas), expected)
    return {
        "ok": ok,
        "reason": reason,
        "audioMs": audio_ms,
        "keyframesMs": kf_ms,
        "errorMs": error_ms,
        "chunkCount": len(metas),
        "keyframesCount": len(tl),
        "expectedChunks": expected,
        "framesPerChunk": frames_per_chunk,
        "mismatches": mismatches,
    }


def align_error_ms(pcm_len_bytes: int, keyframes: list, sample_rate: int = SAMPLE_RATE) -> int:
    """音频总时长 − 关键帧总时长（毫秒）。"""
    audio_ms = int(round(pcm_len_bytes / BYTES_PER_SAMPLE / sample_rate * 1000.0))
    tl = keyframe_timeline(keyframes)
    kf_ms = tl[-1]["endMs"] if tl else 0
    return audio_ms - kf_ms


# ══════════════════════════════════════════════════════════════════════════
# 3. WAV 读写（标准库）
# ══════════════════════════════════════════════════════════════════════════

def read_wav(path: str):
    """读 16-bit PCM WAV，返回 ``(pcm_bytes, sample_rate, channels)``。"""
    with io.open(path, "rb") as f:
        data = f.read()
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file: %s" % path)
    pos = 12
    fmt = None
    pcm = None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            pcm = body
        pos += 8 + size + (size & 1)
    if fmt is None or pcm is None:
        raise ValueError("WAV missing fmt/data chunk: %s" % path)
    audio_fmt, channels, rate, _brate, _align, bits = fmt
    if audio_fmt != 1:
        raise ValueError("only PCM (format=1) supported, got %d" % audio_fmt)
    if bits != 16:
        raise ValueError("only 16-bit supported, got %d" % bits)
    if channels != 1:
        raise ValueError("only mono supported, got %d channels" % channels)
    return pcm, rate, channels


def write_wav(path: str, pcm: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    """写 16-bit 单声道 WAV。"""
    data_size = len(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate,
                                     sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_size)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "wb") as f:
        f.write(header + pcm)


# ══════════════════════════════════════════════════════════════════════════
# 4. 自检
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
            fails.append("%s :: %s" % (name, detail))
            print("  FAIL  {}  {}".format(name, detail))

    print("=" * 74)
    print("自检 1：帧栅格常量")
    print("=" * 74)
    chk("采样率 16 kHz", SAMPLE_RATE == 16000, str(SAMPLE_RATE))
    chk("帧栅格 40 ms（= 0x14 durationMs）", FRAME_MS == 40, str(FRAME_MS))
    chk("一帧 640 采样", SAMPLES_PER_FRAME == 640, str(SAMPLES_PER_FRAME))
    chk("一帧 1280 字节", BYTES_PER_FRAME == 1280, str(BYTES_PER_FRAME))
    chk("一帧 = 40 ms @16k（自洽）",
        SAMPLES_PER_FRAME == SAMPLE_RATE * FRAME_MS // 1000,
        "%d samples" % SAMPLES_PER_FRAME)

    print()
    print("=" * 74)
    print("自检 2：切片计划")
    print("=" * 74)
    # 1 秒音频 = 16000 采样 = 25 帧（整除）
    ch = plan_chunks(SAMPLE_RATE, DEFAULT_FRAMES_PER_CHUNK)
    chk("1 s 音频切成 7 片（4 帧/片，最后 1 帧残片）", len(ch) == 7, "%d 片" % len(ch))
    chk("片 0 覆盖 0~160 ms", ch[0]["startMs"] == 0 and ch[0]["endMs"] == 160,
        "%d~%d ms" % (ch[0]["startMs"], ch[0]["endMs"]))
    chk("片 0 是 4 帧", ch[0]["frames"] == 4, str(ch[0]["frames"]))
    chk("最后一片标记为残片", ch[-1]["partial"] is True, str(ch[-1]["partial"]))
    chk("最后一片覆盖 960~1000 ms",
        ch[-1]["startMs"] == 960 and ch[-1]["endMs"] == 1000,
        "%d~%d ms" % (ch[-1]["startMs"], ch[-1]["endMs"]))
    chk("片段首尾相接、无空洞",
        all(ch[i]["endMs"] == ch[i + 1]["startMs"] for i in range(len(ch) - 1)))
    chk("片段总时长 == 音频总时长",
        ch[-1]["endMs"] == 1000, "%d ms" % ch[-1]["endMs"])
    chk("字节偏移连续",
        all(ch[i]["offsetBytes"] + ch[i]["lengthBytes"] == ch[i + 1]["offsetBytes"]
            for i in range(len(ch) - 1)))
    chk("空音频 ⇒ 0 片", plan_chunks(0) == [])
    chk("frames_per_chunk=1 ⇒ 每帧一片",
        len(plan_chunks(SAMPLE_RATE, 1)) == 25, str(len(plan_chunks(SAMPLE_RATE, 1))))
    try:
        plan_chunks(100, 0)
        chk("frames_per_chunk=0 应报错", False, "没报错")
    except ValueError:
        chk("frames_per_chunk=0 应报错", True)
    # 音频长度**不落在帧栅格上** ⇒ 末片带非整帧零头，必须被标出来
    ragged = plan_chunks(SAMPLE_RATE + 10)
    chk("非栅格音频末片带零头", ragged[-1]["remainderSamples"] == 10,
        "%d 采样" % ragged[-1]["remainderSamples"])
    chk("非栅格音频末片标为残片", ragged[-1]["partial"] is True,
        str(ragged[-1]["partial"]))
    chk("整栅格音频末片无零头", ch[-1]["remainderSamples"] == 0,
        "%d 采样" % ch[-1]["remainderSamples"])

    print()
    print("=" * 74)
    print("自检 3：切片字节与原始 PCM 对得上")
    print("=" * 74)
    pcm = bytes((i * 7 + 3) % 256 for i in range(SAMPLE_RATE * 2 * BYTES_PER_SAMPLE))
    pieces = chunk_pcm(pcm, DEFAULT_FRAMES_PER_CHUNK)
    chk("切片数 == 计划数", len(pieces) == len(plan_chunks(SAMPLE_RATE * 2)),
        "%d 片" % len(pieces))
    chk("拼回去 == 原始 PCM", b"".join(seg for _meta, seg in pieces) == pcm)
    chk("每片字节长度 == meta.lengthBytes",
        all(len(seg) == meta["lengthBytes"] for meta, seg in pieces))
    try:
        chunk_pcm(b"\x01\x02\x03", DEFAULT_FRAMES_PER_CHUNK)
        chk("非偶数长度 PCM 应报错", False, "没报错")
    except ValueError:
        chk("非偶数长度 PCM 应报错", True)

    print()
    print("=" * 74)
    print("自检 4：与 0x14 关键帧对账（音画同源）")
    print("=" * 74)
    # 造 25 帧（1 秒）的关键帧，与 1 秒 PCM 逐片对账
    pcm1 = pcm[:SAMPLE_RATE * BYTES_PER_SAMPLE]
    pieces1 = chunk_pcm(pcm1, DEFAULT_FRAMES_PER_CHUNK)
    kfs = [{"durationMs": FRAME_MS} for _ in range(25)]
    tl = keyframe_timeline(kfs)
    chk("关键帧时间轴累计 1000 ms", tl[-1]["endMs"] == 1000, str(tl[-1]["endMs"]))
    rep = verify_against_keyframes(pieces1, kfs)
    chk("1 s 音频 vs 25 帧 ⇒ 对齐通过", rep["ok"], rep["reason"])
    chk("误差 0 ms", rep["errorMs"] == 0, "%d ms" % rep["errorMs"])
    chk("期望片数 7", rep["expectedChunks"] == 7, str(rep["expectedChunks"]))
    chk("每片 4 帧被正确反推", rep["framesPerChunk"] == 4,
        str(rep["framesPerChunk"]))
    # 回归：CLI 的 --verify 传的是 (meta, bytes) 元组列表，不是 dict 列表
    # ⇒ 对账函数必须两种都吃，否则 CLI 直接崩（2026-10-25 夜间实测）
    rep_tup = verify_against_keyframes(pieces1, kfs)
    chk("元组形式入参也能对账（CLI --verify 路径）", rep_tup["ok"], rep_tup["reason"])
    chk("元组形式与 dict 形式结果一致",
        rep_tup["chunkCount"] == rep["chunkCount"]
        and rep_tup["errorMs"] == rep["errorMs"])

    # 关键帧比音频短 1 帧 ⇒ 误差 -40 ms，仍在一帧内
    rep2 = verify_against_keyframes(pieces1, [{"durationMs": FRAME_MS} for _ in range(24)])
    chk("差一帧仍在容差内", abs(rep2["errorMs"]) <= FRAME_MS,
        "误差 %d ms" % rep2["errorMs"])
    # 关键帧比音频短 3 帧 ⇒ 误差 -120 ms，超容差
    rep3 = verify_against_keyframes(pieces1, [{"durationMs": FRAME_MS} for _ in range(22)])
    chk("差三帧应判失败", not rep3["ok"], rep3["reason"])
    chk("失败原因写明误差", "误差" in rep3["reason"], rep3["reason"])

    # 边界不落在栅格上 ⇒ 失败
    bad = [dict(m) for m in _as_meta_list(pieces1)]
    bad[3]["startMs"] = 121
    rep4 = verify_against_keyframes(bad, kfs)
    chk("边界错位应判失败", not rep4["ok"], rep4["reason"])
    chk("错位被点名", len(rep4["mismatches"]) >= 1, str(len(rep4["mismatches"])))

    print()
    print("=" * 74)
    print("自检 6：关键帧驱动切法（真实 TTS 长度不是栅格整数倍）")
    print("=" * 74)
    # 模拟真实情况：音频 2350 ms（不是 40 ms 的整数倍），关键帧 59 个 = 2360 ms
    # 实测依据：MiniMax TTS「今天真开心啊！」→ 2350 ms 音频 / 59 帧关键帧
    ragged_samples = 2350 * SAMPLE_RATE // 1000          # 37600 采样
    pcm_ragged = bytes((i * 11 + 5) % 256 for i in range(ragged_samples * BYTES_PER_SAMPLE))
    kfs_ragged = [{"durationMs": FRAME_MS} for _ in range(59)]
    grid_chunks = _as_meta_list(chunk_pcm(pcm_ragged, DEFAULT_FRAMES_PER_CHUNK))
    kf_chunks = _as_meta_list(chunk_pcm(pcm_ragged, DEFAULT_FRAMES_PER_CHUNK,
                                        keyframes=kfs_ragged))

    chk("音频 2350 ms 切成 15 片（纯栅格）", len(grid_chunks) == 15,
        "%d 片" % len(grid_chunks))
    chk("纯栅格末片不在关键帧栅格上（这正是它失败的原因）",
        grid_chunks[-1]["endMs"] == 2350, str(grid_chunks[-1]["endMs"]))
    rep_grid = verify_against_keyframes(grid_chunks, kfs_ragged)
    chk("纯栅格模式在非栅格音频上判失败", not rep_grid["ok"], rep_grid["reason"])

    chk("关键帧驱动也切成 15 片", len(kf_chunks) == 15, "%d 片" % len(kf_chunks))
    rep_kf = verify_against_keyframes(kf_chunks, kfs_ragged)
    chk("关键帧驱动模式通过", rep_kf["ok"], rep_kf["reason"])
    chk("关键帧驱动误差 0 ms", rep_kf["errorMs"] == 0, "%d ms" % rep_kf["errorMs"])
    chk("关键帧驱动每片带关键帧区间",
        all("keyframeStart" in m and "keyframeEnd" in m for m in kf_chunks))
    chk("关键帧区间首尾相接且覆盖全部 59 帧",
        kf_chunks[0]["keyframeStart"] == 0 and kf_chunks[-1]["keyframeEnd"] == 58)
    chk("关键帧驱动的音频字节拼回 == 原始 PCM",
        b"".join(seg for _m, seg in chunk_pcm(pcm_ragged, DEFAULT_FRAMES_PER_CHUNK,
                                              keyframes=kfs_ragged)) == pcm_ragged)
    # 关键帧驱动下总片数 = ceil(59/4) = 15
    chk("关键帧驱动期望片数 15", rep_kf["expectedChunks"] == 15,
        str(rep_kf["expectedChunks"]))
    # 关键帧驱动的片边界必须**全在**关键帧栅格上（纯栅格末片不在）
    kf_bounds = {i * FRAME_MS for i in range(60)}
    chk("关键帧驱动片边界全落在栅格上",
        all(c["startMs"] in kf_bounds and c["endMs"] in kf_bounds for c in kf_chunks))

    print()
    print("=" * 74)
    print("自检 5：WAV 读写往返")
    print("=" * 74)
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "_audio_chunk_test.wav")
    write_wav(tmp, pcm)
    back, rate, chn = read_wav(tmp)
    chk("往返字节一致", back == pcm, "%d B" % len(back))
    chk("采样率读回 16000", rate == SAMPLE_RATE, str(rate))
    chk("声道读回 1", chn == 1, str(chn))
    try:
        os.remove(tmp)
    except OSError:
        pass

    print()
    print("=" * 74)
    if ok:
        print("自检结果：ALL PASS（%d 项断言）" % total)
        print("=" * 74)
        return 0
    print("自检结果：FAIL %d 项：%s" % (len(fails), fails))
    print("=" * 74)
    return 1


# ══════════════════════════════════════════════════════════════════════════
# 5. 命令行
# ══════════════════════════════════════════════════════════════════════════

def _read_pcm(args) -> bytes:
    if args.wav:
        pcm, rate, _ch = read_wav(args.wav)
        if rate != SAMPLE_RATE:
            raise SystemExit("采样率 %d != %d，本工具只处理 16 kHz" % (rate, SAMPLE_RATE))
        return pcm
    if args.pcm:
        with io.open(args.pcm, "rb") as f:
            return f.read()
    raise SystemExit("需要 --wav 或 --pcm")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PCM 音频按帧栅格切片（与 0x14 关键帧同栅格）")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--wav", help="16 kHz 单声道 16-bit WAV")
    ap.add_argument("--pcm", help="原始 PCM（16 kHz 单声道 16-bit LE）")
    ap.add_argument("--keyframes", help="关键帧 JSON（用于 --verify 对账）")
    ap.add_argument("--outdir", help="切片输出目录（写 chunk_%04d.pcm + index.json）")
    ap.add_argument("--frames-per-chunk", type=int, default=DEFAULT_FRAMES_PER_CHUNK)
    ap.add_argument("--verify", action="store_true", help="与关键帧对账并打印结论")
    ap.add_argument("--plan", choices=["auto", "grid", "keyframes"], default="auto",
                    help="切法：grid=纯时间栅格；keyframes=关键帧驱动；"
                         "auto=给了 --keyframes 就用关键帧驱动")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    pcm = _read_pcm(args)

    # 决定切法
    kfs = None
    if args.keyframes:
        kfs = load_keyframes(args.keyframes)
    if args.plan == "grid":
        use_kf = None
    elif args.plan == "keyframes":
        if kfs is None:
            raise SystemExit("--plan keyframes 需要 --keyframes")
        use_kf = kfs
    else:  # auto
        use_kf = kfs

    pieces = chunk_pcm(pcm, args.frames_per_chunk, keyframes=use_kf)

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        index = []
        for meta, seg in pieces:
            name = "chunk_%04d.pcm" % meta["index"]
            with io.open(os.path.join(args.outdir, name), "wb") as f:
                f.write(seg)
            index.append(dict(meta, file=name))
        with io.open(os.path.join(args.outdir, "index.json"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({
                "sampleRate": SAMPLE_RATE,
                "bytesPerSample": BYTES_PER_SAMPLE,
                "frameMs": FRAME_MS,
                "framesPerChunk": args.frames_per_chunk,
                "totalSamples": len(pcm) // BYTES_PER_SAMPLE,
                "totalMs": pieces[-1]["endMs"] if pieces else 0,
                "chunks": index,
            }, ensure_ascii=False, indent=2))
        print("切片 %d 片 → %s" % (len(pieces), os.path.abspath(args.outdir)))

    if args.verify:
        if not args.keyframes:
            raise SystemExit("--verify 需要 --keyframes")
        kfs_v = load_keyframes(args.keyframes)
        rep = verify_against_keyframes(pieces, kfs_v, args.frames_per_chunk)
        print("对齐校验：%s" % ("✅ 通过" if rep["ok"] else "❌ " + rep["reason"]))
        print("  音频 %d ms ｜ 关键帧 %d ms ｜ 误差 %+d ms（容差 ±%d ms）"
              % (rep["audioMs"], rep["keyframesMs"], rep["errorMs"], FRAME_MS))
        print("  片段 %d ｜ 关键帧 %d ｜ 期望片段 %d ｜ 每片 %d 帧"
              % (rep["chunkCount"], rep["keyframesCount"], rep["expectedChunks"],
                 rep["framesPerChunk"]))
        if rep["mismatches"]:
            print("  错位片段：")
            for m in rep["mismatches"][:10]:
                print("    - 片段 %d 的 %s = %d" % (m["chunk"], m["field"], m["value"]))
        return 0 if rep["ok"] else 1

    if not args.outdir:
        print("音频 %d ms ｜ 切成 %d 片（每片 %d 帧 = %d ms）"
              % (pieces[-1]["endMs"] if pieces else 0, len(pieces),
                 args.frames_per_chunk, args.frames_per_chunk * FRAME_MS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
