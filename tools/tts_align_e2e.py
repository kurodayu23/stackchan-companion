#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tts_align_e2e —— TTS → 韵律 → 关键帧 → 音频切片 → 音画对账 的**端到端闭环**。

这是对 `tools/audio_chunk.py` 最硬的一次验证，也是「音画同源」这条架构保证的
**可复现证据**：

    真实 TTS 输出（长度**不是** 40 ms 栅格整数倍）
      → 韵律分析 → 0x14 关键帧（25 fps / durationMs=40）
      → 音频切片（关键帧驱动）
      → 对账：误差必须 **0 ms**；切片字节拼回必须 == 原始 PCM

⚠️ 为什么必须是「真实 TTS」：离线替身（WAV / 合成信号）的长度可以任意选，
   很容易「碰巧」落在栅格上 ⇒ 掩盖真实缺陷。
   实测真实 MiniMax TTS 的音频长度**必然**不是 40 ms 整数倍：
   「今天真开心啊！」→ 2350 ms / 1358 ms，两次都是。

用法::

    py -3.12 tools/tts_align_e2e.py                 # 自动选 provider
    py -3.12 tools/tts_align_e2e.py --provider stub # 强制离线替身
    py -3.12 tools/tts_align_e2e.py --outdir out    # 落盘产物

退出码：0 = 闭环通过；1 = 有失败项。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for _p in (_REPO, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

import numpy as np  # noqa: E402

import audio_chunk as ac        # noqa: E402
import prosody_to_motion as ptm  # noqa: E402


def _build_provider(name: str):
    """按名字构造 provider。

    key **只从环境变量读**（`MINIMAX_API_KEY`），不落盘、不回显。
    """
    from server.providers.registry import build_provider
    from server.stackchan_ai.config import Config

    cfg = Config.from_env()
    if name and name != "auto":
        cfg.provider = name
    return build_provider(cfg.provider, cfg)


def run(text: str, voice: str, provider_name: str, outdir: str = None) -> dict:
    """跑一次闭环，返回结论字典。"""
    from server.stackchan_ai.tts import TTS

    # ── 1) TTS ───────────────────────────────────────────────────
    provider = _build_provider(provider_name)
    tts = TTS(provider, voice=voice)
    audio = tts.synthesize(text)
    pcm = audio.pcm
    sr = audio.sample_rate
    audio_ms = int(round(len(pcm) / ac.BYTES_PER_SAMPLE / sr * 1000.0))

    # ── 2) 韵律 → 关键帧（与 tools/demo_offline.py 同一条路径）─────
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768.0
    feat, track = ptm.extract_prosody(samples, sr)
    params = ptm.build_params("Neutral", feat)
    kfs, _info = ptm.compile_keyframes(track, feat, params, "Neutral")
    kf_ms = len(kfs) * ptm.OUT_DT_MS

    # ── 3) 两种切法 ──────────────────────────────────────────────
    grid = ac.chunk_pcm(pcm, ac.DEFAULT_FRAMES_PER_CHUNK)
    kfc = ac.chunk_pcm(pcm, ac.DEFAULT_FRAMES_PER_CHUNK, keyframes=kfs)
    grid_metas = ac._as_meta_list(grid)
    kfc_metas = ac._as_meta_list(kfc)

    # ── 4) 对账 ──────────────────────────────────────────────────
    rep_grid = ac.verify_against_keyframes(grid, kfs, ac.DEFAULT_FRAMES_PER_CHUNK)
    rep_kf = ac.verify_against_keyframes(kfc, kfs, ac.DEFAULT_FRAMES_PER_CHUNK)

    # ── 5) 字节完整性 ────────────────────────────────────────────
    joined = b"".join(seg for _m, seg in kfc)
    same = joined == pcm

    # ── 6) 落盘 ──────────────────────────────────────────────────
    out = os.path.abspath(outdir) if outdir else None
    if out:
        os.makedirs(out, exist_ok=True)
        ac.write_wav(os.path.join(out, "tts.wav"), pcm, sr)
        with io.open(os.path.join(out, "tts_keyframes.json"), "w",
                     encoding="utf-8", newline="") as f:
            f.write(json.dumps(kfs, ensure_ascii=False, indent=2) + "\n")
        chunk_dir = os.path.join(out, "chunks")
        os.makedirs(chunk_dir, exist_ok=True)
        index = []
        for meta, seg in kfc:
            name = "chunk_%04d.pcm" % meta["index"]
            with io.open(os.path.join(chunk_dir, name), "wb") as f:
                f.write(seg)
            index.append(dict(meta, file=name))
        with io.open(os.path.join(chunk_dir, "index.json"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({
                "sampleRate": sr,
                "bytesPerSample": ac.BYTES_PER_SAMPLE,
                "frameMs": ac.FRAME_MS,
                "framesPerChunk": ac.DEFAULT_FRAMES_PER_CHUNK,
                "totalSamples": len(pcm) // ac.BYTES_PER_SAMPLE,
                "totalMs": kfc_metas[-1]["endMs"],
                "chunks": index,
            }, ensure_ascii=False, indent=2))

    ok = rep_kf["ok"] and same
    return {
        "ok": ok,
        "provider": provider.name,
        "text": text,
        "pcmBytes": len(pcm),
        "sampleRate": sr,
        "audioMs": audio_ms,
        "keyframeCount": len(kfs),
        "keyframeMs": kf_ms,
        "gridChunks": len(grid_metas),
        "gridLastEndMs": grid_metas[-1]["endMs"] if grid_metas else 0,
        "gridOk": rep_grid["ok"],
        "gridReason": rep_grid["reason"],
        "kfChunks": len(kfc_metas),
        "kfLastEndMs": kfc_metas[-1]["endMs"] if kfc_metas else 0,
        "kfOk": rep_kf["ok"],
        "kfReason": rep_kf["reason"],
        "alignErrorMs": rep_kf["errorMs"],
        "bytesRoundTrip": same,
        "outdir": out,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="TTS → 韵律 → 关键帧 → 切片 → 音画对账 端到端闭环")
    ap.add_argument("--text", default="今天真开心啊！")
    ap.add_argument("--voice", default="female-shaonv")
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "minimax", "stub"])
    ap.add_argument("--outdir", help="产物输出目录（不给就不落盘）")
    args = ap.parse_args(argv)

    r = run(args.text, args.voice, args.provider, args.outdir)

    print("=" * 74)
    print("TTS → 韵律 → 关键帧 → 切片 → 音画对账（端到端闭环）")
    print("=" * 74)
    print("  provider        : %s" % r["provider"])
    print("  文本            : %s" % r["text"])
    print("  真实 PCM        : %d B / %d Hz / %d ms"
          % (r["pcmBytes"], r["sampleRate"], r["audioMs"]))
    print("  关键帧          : %d 帧 × %d ms = %d ms"
          % (r["keyframeCount"], ptm.OUT_DT_MS, r["keyframeMs"]))
    print("  纯栅格切法      : %d 片，末片 endMs=%d ⇒ %s（%s）"
          % (r["gridChunks"], r["gridLastEndMs"],
             "PASS" if r["gridOk"] else "FAIL", r["gridReason"]))
    print("  关键帧驱动切法  : %d 片，末片 endMs=%d ⇒ %s（误差 %+d ms）"
          % (r["kfChunks"], r["kfLastEndMs"],
             "PASS" if r["kfOk"] else "FAIL", r["alignErrorMs"]))
    print("  切片字节拼回    : %s"
          % ("== 原始 PCM" if r["bytesRoundTrip"] else "≠ 原始 PCM（失败）"))
    if r["outdir"]:
        print("  产物            : %s" % r["outdir"])
    print()
    print("结论：%s" % ("端到端闭环通过" if r["ok"] else "存在失败项"))
    print("=" * 74)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
