# -*- coding: utf-8 -*-
"""providers.stub —— 离线桩 provider：**没有 API Key 也能跑通全链路**。

chat：固定句式 + 确定性挑选（同样的输入 → 同样的输出）。
tts ：⭐ **不是静音**。用 numpy 合成一段带
        - F0 轮廓（基频 + 下倾 declination + 重音凸起 + 轻微抖动）
        - 能量包络（音节级 amplitude modulation）
        - 停顿（标点处静音段）
        - 辅音噪声（音节起点的 fricative）
      的**类语音信号**，让韵律提取器能跑出非平凡结果
      （F0 均值、能量、语速、重音峰、停顿数都要有值）。

合成参数刻意落在韵律提取器的有效区间（tools/prosody_to_motion.py）：
    F0 ∈ [60, 400] Hz（YIN 的搜索范围），基频取 200~215 Hz；
    音节 120~260 ms ⇒ 语速代理（能量峰计数 / 浊音时长）落在 3~8 Hz；
    标点停顿 ≥ 150 ms ⇒ VAD 的停顿阈值（≥120 ms）能检出。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .base import ChatReply, Provider, ProviderKind, TtsAudio

#: 标点 → 停顿长度（秒）。句末停最长。
PAUSE_BY_PUNCT: Dict[str, float] = {
    "，": 0.22, ",": 0.22,
    "、": 0.18,
    "；": 0.28, ";": 0.28,
    "：": 0.22, ":": 0.22,
    "。": 0.34, ".": 0.34,
    "！": 0.34, "!": 0.34,
    "？": 0.38, "?": 0.38,
    "…": 0.30,
}

#: 句首欢迎语（确定性挑选）
_REPLY_TEMPLATES: Tuple[str, ...] = (
    "我在呢，你说的话我记下了。",
    "嗯，我听着呢，你继续说。",
    "收到！这句我先替你记着。",
    "好的，我把它放进我们的小档案里了。",
)


def _split_phrases(text: str) -> List[Tuple[str, float]]:
    """把文本切成 ``(片段, 之后的停顿秒数)`` 序列。"""
    phrases: List[Tuple[str, float]] = []
    buf = ""
    pause = 0.0
    for ch in text:
        if ch in PAUSE_BY_PUNCT:
            phrases.append((buf, PAUSE_BY_PUNCT[ch]))
            buf = ""
            pause = 0.0
            continue
        if ch.isspace():
            continue
        buf += ch
    phrases.append((buf, pause))
    return [(seg, ps) for seg, ps in phrases if seg or ps > 0]


def _synth_speech(text: str, sr: int = 16000,
                  base_f0: float = 208.0, seed: int = 7) -> np.ndarray:
    """合成类语音信号（单声道 float32，值域 [-1, 1]）。

    结构：标点 → 停顿；停顿之间是若干音节；
    每个音节 = 谐波堆（基频 + 5 个泛音）+ 音节包络 + 起首辅音噪声。
    """
    rng = np.random.default_rng(seed)
    phrases = _split_phrases(text)
    if not phrases:
        phrases = [("嗯", 0.25)]

    chunks: List[np.ndarray] = []
    total_syllables = 0
    syllable_plan: List[Tuple[str, int]] = []
    for seg, pause in phrases:
        # 一个汉字 ≈ 一个音节；连续 ASCII 字母按 2 个字符一个音节
        n_syll = max(1, len(re.findall(r"[一-鿿]", seg)) +
                     max(0, len(re.findall(r"[A-Za-z]+", seg)) * 2))
        for i in range(n_syll):
            dur = int(sr * rng.uniform(0.12, 0.26))
            syllable_plan.append((seg if len(seg) == 1 else seg[i % len(seg)], dur))
        total_syllables += n_syll

    # 重音位置：句中偏前的几个音节（让 F0 重音峰有得可检）
    accent_idx = set()
    if total_syllables >= 3:
        accent_idx = {max(0, int(total_syllables * 0.15)),
                      max(0, int(total_syllables * 0.55))}

    out_len_hint = sum(d for _, d in syllable_plan) + int(sr * 1.2)
    out = np.zeros(max(out_len_hint, sr // 2), dtype=np.float64)
    pos = 0

    # 全局 F0 下倾（declination）：句首高、句尾低
    n_total = max(1, total_syllables)

    for s_idx, (_, dur) in enumerate(syllable_plan):
        # ── 音节级参数 ──────────────────────────────────────────────
        decl = 1.06 - 0.16 * (s_idx / float(n_total))     # 下倾
        accent = 1.0
        if s_idx in accent_idx:
            accent = 1.22                                # 重音：F0 上抬
        f0_mid = base_f0 * decl * accent
        f0_spread = base_f0 * 0.06 * rng.uniform(-1.0, 1.0)
        amp = 0.30 + 0.35 * rng.random() + (0.15 if s_idx in accent_idx else 0.0)
        amp = float(min(amp, 0.85))

        n = dur
        t = np.arange(n) / float(sr)
        # F0 轮廓：音节内先扬后抑（自然的音节内下倾）+ 轻微抖动
        f0_curve = f0_mid + f0_spread * t / max(1e-6, n / float(sr))
        f0_curve *= 1.0 - 0.08 * (t / max(1e-6, n / float(sr)))
        f0_curve += 0.6 * np.sin(2.0 * np.pi * 5.0 * t)     # 5 Hz 抖动
        phase = 2.0 * np.pi * np.cumsum(f0_curve) / float(sr)

        # 谐波堆：基频 + 泛音（幅度 1/h）
        sig = np.zeros(n, dtype=np.float64)
        for h in range(1, 7):
            sig += (1.0 / h) * np.sin(h * phase + 0.3 * h)

        # 音节包络：升 - 保持 - 降
        env = np.sin(np.pi * np.clip(t / max(1e-6, n / float(sr)), 0.0, 1.0)) ** 0.65
        sig = sig * env * amp * 0.32

        # 起首辅音噪声（20~35 ms）
        fric_n = min(n, int(sr * rng.uniform(0.02, 0.035)))
        if fric_n > 8:
            noise = rng.normal(0.0, 1.0, fric_n)
            # 高通一点的噪声更像 /s/ /sh/
            noise = np.diff(noise, prepend=0.0)
            sig[:fric_n] += noise * 0.10 * env[:fric_n] / max(env.max(), 1e-6)

        end = pos + n
        if end > len(out):
            out = np.pad(out, (0, end - len(out)))
        out[pos:end] += sig
        pos = end

        # 音节间轻微气声（非静音，避免 VAD 把整段判成连续浊音）
        gap_n = int(sr * rng.uniform(0.008, 0.035))
        if gap_n > 0:
            end = pos + gap_n
            if end > len(out):
                out = np.pad(out, (0, end - len(out)))
            out[pos:end] += rng.normal(0.0, 0.004, gap_n)
            pos = end

    # 标点停顿：真正的静音段 ⇒ VAD 能检出「停顿」
    for _, pause in phrases:
        if pause <= 0:
            continue
        gap_n = int(sr * pause)
        end = pos + gap_n
        if end > len(out):
            out = np.pad(out, (0, end - len(out)))
        pos = end

    out = out[:pos]
    if len(out) == 0:
        out = np.zeros(int(sr * 0.2), dtype=np.float64)
    peak = float(np.max(np.abs(out)))
    if peak > 1e-6:
        out = out / peak * 0.82
    return out.astype(np.float32)


class StubProvider(Provider):
    """离线桩：chat 给固定句式，tts 给 numpy 合成的类语音。"""

    kind = ProviderKind.STUB
    name = "stub"

    def __init__(self, seed: int = 7, sample_rate: int = 16000) -> None:
        self.seed = seed
        self.sample_rate = sample_rate

    # ── chat ───────────────────────────────────────────────────────────────
    def chat(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> ChatReply:
        last = ""
        for msg in reversed(list(messages)):
            if msg.get("role") == "user":
                last = str(msg.get("content") or "")
                break
        idx = sum(ord(c) for c in last) % len(_REPLY_TEMPLATES)
        text = _REPLY_TEMPLATES[idx]
        if last:
            text = "「%s」—— %s" % (last[:24], text)
        return ChatReply(text=text, reasoning="", model="stub",
                         raw={"stub": True, "seed": self.seed})

    # ── tts ────────────────────────────────────────────────────────────────
    def tts(self, text: str, **kwargs: Any) -> TtsAudio:
        voice = str(kwargs.get("voice") or "stub-default")
        samples = _synth_speech(text or "嗯", sr=self.sample_rate, seed=self.seed)
        pcm = np.clip(np.asarray(samples, dtype=np.float32) * 32767.0,
                      -32768.0, 32767.0).astype("<i2").tobytes()
        return TtsAudio(pcm=pcm, sample_rate=self.sample_rate, channels=1,
                        encoding="pcm_s16le", voice=voice, provider=self.name)

    def asr(self, pcm: bytes, sample_rate: int = 16000, **kwargs: Any) -> str:
        """桩不做识别（仓库里没有 ASR 的实测依据）⇒ 明确报 UNSUPPORTED，不静默返回空串。"""
        return super().asr(pcm, sample_rate, **kwargs)

    @property
    def supports_asr(self) -> bool:
        return False


__all__ = ["StubProvider"]
