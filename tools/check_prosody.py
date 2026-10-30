#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_prosody.py —— 韵律→身体 管线的离线标定体检（门禁）

为什么需要它
------------
`server/stackchan_ai/prosody.py` 是本项目护城河「唯一空位 = 韵律→舵机/关键帧」
的算法层：YIN 基频 → 7 维韵律 → 42 个标量参数 → PCHIP 插值 → 0x14 关键帧。
它以前**只有人读代码，没有机器判据** ⇒ 任何改动都答不出三个问题：

  ① 情绪会不会被音频淹没（韵律一变，6 种情绪还分得开吗？）
  ② 这条管线有没有自己造出来的伪影（自己骗自己）
  ③ 输出会不会越界 / 不可复现 / 超带宽

本门禁**用合成韵律语料**（谐波合成 + 共振峰包络，4 种受控变体）离线跑真实管线，
把上面三件事变成可判阈值。全部离线、不联网、不碰真机。

检查项
------
| 码 | 判据 | 阈值（实测来源：docs/research/87） |
|---|---|---|
| PR-01 | env 边界不得出现补零伪影 | 首帧 `env−energy` 偏差 ≤ 1.0 dB（实测 ≤ 0.3） |
| PR-02 | 静音不得张嘴 | mouth 跨度 ≤ 1（实测 0） |
| PR-03 | 编译必须逐字节可复现 | 两次编译的 JSON 相同 |
| PR-04 | `audit()` 不得报问题 | problems = warnings = 0 |
| PR-05 | 42 个标量参数 | `build_params` 的参数键数 = 42 |
| PR-06 | 情绪必须可辨识（跨韵律变体留一） | 全特征均值 ≥ 75%、最差变体 ≥ 60%（实测 83.3% / 67%） |
| PR-07 | 情绪不得被音频淹没 | 韵律间/情绪间 中位距离比 < 1.0（实测 0.41） |
| PR-08 | `expressiveness` 必须单调 | pitch_span / yaw_span / mouth_mean 单调不减 |
| PR-09 | 单帧不得超 WS 上限 | ≤ 262144 B，且一个 WS 帧至少装 4 帧 |
| PR-10 | 输出不得越界 | pitch / yaw / weight 全在硬限内 |
| PR-11 | 情绪基线 SNR（**WARN**） | 基线最小间隔 ÷ 韵律扰动 ≥ 0.50（实测 0.19 ⇒ 需重新标定 `energyEyeGain`） |
| PR-12 | 真实 TTS 语料上「跨文本留一」可辨识度 | ≥ 50%（实测 61.1%） |
| PR-13 | 真实 TTS 上能量通道必须还活着 | 浊音帧 e_norm 跨度 ≥ 0.10（实测 0.242） |

⚠️ 本门禁测的是**输出空间的可分性**，**不等于**「人能认出」—— 后者需要主观评测。
   判据的适用范围写在这里，别把它当成人因结论。

用法
----
    py -3.12 tools/check_prosody.py --root .
    py -3.12 tools/check_prosody.py --self-test

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SR = 16000
FORMANTS = ((700.0, 120.0, 1.0), (1220.0, 160.0, 0.55), (2600.0, 240.0, 0.28))
EMOTIONS = ("Neutral", "Happy", "Angry", "Sad", "Doubt", "Sleepy")
KINDS = ("flat", "rise", "fall", "accent")

#: PR-01 边界伪影容忍度（dB）。实测修复后 ≤ 0.3，留 3 倍余量。
EDGE_TOL_DB = 1.0
#: PR-02 静音嘴跨度上限
SILENCE_MOUTH_SPAN_MAX = 1
#: PR-06 可辨识度阈值
CV_MEAN_MIN = 0.75
CV_WORST_MIN = 0.60
#: PR-07 淹没比上限（< 1 才算情绪没被盖过）
DROWNING_RATIO_MAX = 1.0
#: PR-09 一个 WS 帧至少要装几帧 0x14（160 ms / 4 帧 = 5120 B 的设计值）
FRAMES_PER_WS_MIN = 4

FEAT_KEYS = ("pitch_mean", "pitch_min", "pitch_max", "pitch_range", "yaw_range",
             "eye_mean", "eye_min", "mouth_mean", "mouth_max", "nod_max")


# ---------------------------------------------------------------------------
# 合成韵律语料（与 docs/research/87 的探针同一套配方）
# ---------------------------------------------------------------------------
def _synth(f0_curve, env, sr=SR, formants=FORMANTS):
    n = len(f0_curve)
    ph = 2.0 * np.pi * np.cumsum(f0_curve) / sr
    f0_mean = float(np.mean(f0_curve[f0_curve > 0])) if np.any(f0_curve > 0) else 200.0
    kmax = int(min(60, np.ceil(sr / 2.0 / max(f0_mean, 50.0))))
    sig = np.zeros(n)
    for k in range(1, kmax + 1):
        fk = k * f0_mean
        g = 0.0
        for (F, BW, A) in formants:
            g += A / (1.0 + ((fk - F) / BW) ** 2)
        if g < 1e-3:
            continue
        sig += g * np.sin(k * ph)
    peak = float(np.max(np.abs(sig))) or 1.0
    return (sig / peak) * env


def make_utterance(kind, dur=2.0, sr=SR):
    """4 种受控韵律变体：平 / 升 / 落(含停顿) / 重音(含停顿)。"""
    n = int(dur * sr)
    t = np.arange(n) / sr
    f0 = np.full(n, 200.0)
    env = np.full(n, 0.35)
    if kind == "flat":
        pass
    elif kind == "rise":
        f0 = 190.0 + 70.0 * (t / dur)
        env = 0.25 + 0.5 * (t / dur)
    elif kind == "fall":
        f0 = 240.0 - 90.0 * (t / dur)
        env = 0.7 - 0.45 * (t / dur)
        s = int(0.55 * dur * sr)
        env[s:s + int(0.35 * sr)] = 0.0
    elif kind == "accent":
        env = 0.3 + 0.35 * np.sin(2 * np.pi * 1.7 * t) ** 2
        for c in (0.25, 0.5, 0.75):
            i = int(c * dur * sr)
            w = int(0.12 * sr)
            bump = 3.0 * np.exp(-0.5 * ((np.arange(-w, w) / (0.45 * w)) ** 2))
            f0[i:i + len(bump)] *= (2.0 ** (bump / 12.0))
        s = int(0.42 * dur * sr)
        env[s:s + int(0.3 * sr)] = 0.0
    else:
        raise ValueError(kind)
    return _synth(f0, env, sr)


# ---------------------------------------------------------------------------
# 门禁骨架
# ---------------------------------------------------------------------------
class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code, severity, where, msg):
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg


class Shim:
    """把 prosody 模块的三个关键函数包一层，便于自检注入缺陷。"""

    def __init__(self, module):
        self.m = module
        self.extract = module.extract_prosody
        self.build_params = module.build_params
        self.compile_keyframes = module.compile_keyframes


def load_prosody(repo_root):
    server = os.path.join(repo_root, "server")
    if server not in sys.path:
        sys.path.insert(0, server)
    from stackchan_ai import prosody  # noqa: WPS433
    return prosody


def _features(kfs, info):
    pitch = np.array([k["pitchServo"]["angle"] / 10.0 for k in kfs])
    yaw = np.array([k["yawServo"]["angle"] / 10.0 for k in kfs])
    eye = np.array([k["leftEye"]["weight"] for k in kfs], dtype=float)
    mouth = np.array([k["mouth"]["weight"] for k in kfs], dtype=float)
    nod = [d for (_t, d) in info["accentNodDegrees"]]
    return {
        "pitch_mean": float(pitch.mean()),
        "pitch_min": float(pitch.min()),
        "pitch_max": float(pitch.max()),
        "pitch_range": float(pitch.max() - pitch.min()),
        "yaw_range": float(yaw.max() - yaw.min()),
        "eye_mean": float(eye.mean()),
        "eye_min": float(eye.min()),
        "mouth_mean": float(mouth.mean()),
        "mouth_max": float(mouth.max()),
        "nod_max": float(max(nod)) if nod else 0.0,
    }


def _vec(d):
    return np.array([d[k] for k in FEAT_KEYS], dtype=float)


# ---------------------------------------------------------------------------
# 各项检查
# ---------------------------------------------------------------------------
def check_edge(shim, P, findings, stats):
    """PR-01：env 的边界不得因「补零」凭空造出能量峰。

    背景：env 是 dB 域（负值），`np.convolve(mode="same")` 在首尾补零
    ⇒ 等于把边界往 0 dB 拉 ⇒ 假峰 ⇒ 每句话第 1 帧 e_norm 饱和。
    """
    worst = 0.0
    worst_kind = ""
    for kind in KINDS:
        samples = make_utterance(kind)
        feat, track = shim.extract(samples, SR)
        env, energy = track["env"], track["energy"]
        k = max(3, int(round(0.050 / (track["times"][1] - track["times"][0]))))
        bias = float(np.max(np.abs(env[:k - 1] - energy[:k - 1]))) if k > 1 else 0.0
        if bias > worst:
            worst, worst_kind = bias, kind
    stats["edge_max_db"] = round(worst, 4)
    stats["edge_worst_kind"] = worst_kind
    if worst > EDGE_TOL_DB:
        findings.append(Finding(
            "PR-01", "FAIL", "server/stackchan_ai/prosody.py",
            "env 边界出现补零伪影：%s 变体首帧偏差 %.2f dB > 容忍 %.1f dB"
            % (worst_kind, worst, EDGE_TOL_DB)))
    return findings


def check_silence(shim, P, findings, stats):
    """PR-02：全静音输入不得张嘴（也不得有明显俯仰）。"""
    samples = np.zeros(int(1.0 * SR))
    feat, track = shim.extract(samples, SR)
    p = shim.build_params("Neutral", feat)
    kfs, _info = shim.compile_keyframes(track, feat, p, "Neutral")
    mouth = [k["mouth"]["weight"] for k in kfs]
    pitch = [k["pitchServo"]["angle"] / 10.0 for k in kfs]
    span = float(max(mouth) - min(mouth))
    pspan = float(max(pitch) - min(pitch))
    stats["silence_mouth_span"] = span
    stats["silence_pitch_span"] = pspan
    if span > SILENCE_MOUTH_SPAN_MAX:
        findings.append(Finding(
            "PR-02", "FAIL", "server/stackchan_ai/prosody.py",
            "静音输入下嘴 weight 跨度 %.1f > %d（静音不该张嘴）"
            % (span, SILENCE_MOUTH_SPAN_MAX)))
    return findings


def check_reproducible(shim, P, findings, stats):
    """PR-03：同一输入编译两次必须逐字节相同。"""
    samples = make_utterance("accent")
    out = []
    for _ in range(2):
        feat, track = shim.extract(samples, SR)
        p = shim.build_params("Happy", feat)
        kfs, _info = shim.compile_keyframes(track, feat, p, "Happy")
        out.append(json.dumps(kfs, sort_keys=True))
    ok = out[0] == out[1]
    stats["reproducible"] = ok
    if not ok:
        findings.append(Finding(
            "PR-03", "FAIL", "server/stackchan_ai/prosody.py",
            "同一输入两次编译结果不一致（不可复现）"))
    return findings


def check_audit(shim, P, findings, stats):
    """PR-04 + PR-10：audit 不报问题，且输出不越界。"""
    problems = warnings = 0
    for kind in KINDS:
        samples = make_utterance(kind)
        feat, track = shim.extract(samples, SR)
        for emo in EMOTIONS:
            p = shim.build_params(emo, feat)
            kfs, _info = shim.compile_keyframes(track, feat, p, emo)
            rep = P.audit(kfs)
            problems += len(rep["problems"])
            warnings += len(rep["warnings"])
            for k in kfs:
                if not (P.PITCH_SOFT[0] <= k["pitchServo"]["angle"] / 10.0 <= P.PITCH_SOFT[1]):
                    problems += 1
                if abs(k["yawServo"]["angle"] / 10.0) > P.YAW_SOFT + 1e-6:
                    problems += 1
                for el in ("leftEye", "rightEye", "mouth"):
                    w = k[el]["weight"]
                    if not (P.WEIGHT_RANGE[0] <= w <= P.WEIGHT_RANGE[1]):
                        problems += 1
    stats["audit_problems"] = problems
    stats["audit_warnings"] = warnings
    if problems or warnings:
        findings.append(Finding(
            "PR-04", "FAIL", "server/stackchan_ai/prosody.py",
            "audit/越界检查不干净：problems=%d warnings=%d" % (problems, warnings)))
    return findings


def check_params(shim, P, findings, stats):
    """PR-05：42 个标量参数（情绪基线 22 + 韵律调制 9 + 个性化 7 + 设备常量 4）。"""
    feat, _track = shim.extract(make_utterance("flat"), SR)
    p = shim.build_params("Neutral", feat)
    n = len([k for k in p if not k.startswith("_")])
    stats["param_count"] = n
    stats["param_count_expect"] = P.PARAM_COUNT_EXPECT
    if n != P.PARAM_COUNT_EXPECT:
        findings.append(Finding(
            "PR-05", "FAIL", "server/stackchan_ai/prosody.py",
            "参数键数 = %d，应为 %d（22+9+7+4）" % (n, P.PARAM_COUNT_EXPECT)))
    return findings


def _collect_features(shim, P):
    data = {}
    for kind in KINDS:
        samples = make_utterance(kind)
        for emo in EMOTIONS:
            feat, track = shim.extract(samples, SR)
            p = shim.build_params(emo, feat)
            kfs, info = shim.compile_keyframes(track, feat, p, emo)
            data[(kind, emo)] = _features(kfs, info)
    return data


def check_discriminability(shim, P, data, findings, stats):
    """PR-06：跨韵律变体留一类别交叉验证。

    ⚠️ 每类只有 1 个样本时，留一最近邻**结构性全错** ⇒ 必须用
    「留一韵律变体」：训练集 = 其余 3 个变体的 18 个样本，测试 = 留出变体的 6 个样本。
    """
    accs = {}
    for held in KINDS:
        train = [(k, e) for k in KINDS if k != held for e in EMOTIONS]
        test = [(held, e) for e in EMOTIONS]
        Xtr = np.array([_vec(data[key]) for key in train])
        Xte = np.array([_vec(data[key]) for key in test])
        mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
        sd[sd < 1e-9] = 1.0
        Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
        cents = {e: Ztr[[i for i, (_k, ee) in enumerate(train) if ee == e]].mean(axis=0)
                 for e in EMOTIONS}
        ok = 0
        for i, (_k, e) in enumerate(test):
            d = {ee: float(np.linalg.norm(Zte[i] - c)) for ee, c in cents.items()}
            if min(d, key=d.get) == e:
                ok += 1
        accs[held] = ok / float(len(test))
    mean_acc = float(np.mean(list(accs.values())))
    worst = min(accs.values())
    stats["cv_acc"] = {k: round(v * 100, 1) for k, v in accs.items()}
    stats["cv_mean"] = round(mean_acc * 100, 1)
    stats["cv_worst"] = round(worst * 100, 1)
    if mean_acc < CV_MEAN_MIN:
        findings.append(Finding(
            "PR-06", "FAIL", "server/stackchan_ai/prosody.py",
            "6 情绪跨韵律变体可辨识度均值 %.1f%% < %.0f%%"
            % (mean_acc * 100, CV_MEAN_MIN * 100)))
    if worst < CV_WORST_MIN:
        findings.append(Finding(
            "PR-06", "FAIL", "server/stackchan_ai/prosody.py",
            "最差韵律变体的可辨识度 %.1f%% < %.0f%%"
            % (worst * 100, CV_WORST_MIN * 100)))
    return findings


def check_drowning(shim, P, data, findings, stats):
    """PR-07：淹没指标 = 韵律间中位距离 / 情绪间中位距离。> 1 ⇒ 韵律盖过情绪。"""
    emo_d, pros_d = [], []
    for kind in KINDS:
        for a in range(len(EMOTIONS)):
            for b in range(a + 1, len(EMOTIONS)):
                emo_d.append(float(np.linalg.norm(
                    _vec(data[(kind, EMOTIONS[a])]) - _vec(data[(kind, EMOTIONS[b])]))))
    for e in EMOTIONS:
        for k1 in range(len(KINDS)):
            for k2 in range(k1 + 1, len(KINDS)):
                pros_d.append(float(np.linalg.norm(
                    _vec(data[(KINDS[k1], e)]) - _vec(data[(KINDS[k2], e)]))))
    pm, em = float(np.median(pros_d)), float(np.median(emo_d))
    ratio = pm / max(em, 1e-9)
    stats["drowning_prosody_med"] = round(pm, 3)
    stats["drowning_emotion_med"] = round(em, 3)
    stats["drowning_ratio"] = round(ratio, 3)
    if ratio >= DROWNING_RATIO_MAX:
        findings.append(Finding(
            "PR-07", "FAIL", "server/stackchan_ai/prosody.py",
            "韵律间距离 %.2f ≥ 情绪间距离 %.2f（比值 %.2f）⇒ 情绪被音频淹没"
            % (pm, em, ratio)))
    return findings


def check_monotonic(shim, P, findings, stats):
    """PR-08：expressiveness 是「表现力总量」旋钮，输出必须随它单调不减。"""
    samples = make_utterance("accent")
    rows = []
    for v in (0.0, 0.35, 0.70, 1.0, 1.5):
        feat, track = shim.extract(samples, SR)
        p = shim.build_params("Neutral", feat, {"expressiveness": v})
        kfs, _info = shim.compile_keyframes(track, feat, p, "Neutral")
        pitch = np.array([k["pitchServo"]["angle"] / 10.0 for k in kfs])
        yaw = np.array([k["yawServo"]["angle"] / 10.0 for k in kfs])
        mouth = np.array([k["mouth"]["weight"] for k in kfs], dtype=float)
        rows.append({
            "expressiveness": v,
            "pitch_span": float(pitch.max() - pitch.min()),
            "yaw_span": float(yaw.max() - yaw.min()),
            "mouth_mean": float(mouth.mean()),
            "pitch_mean": float(pitch.mean()),
        })
    stats["monotonic"] = {k: [round(r[k], 3) for r in rows]
                           for k in ("pitch_span", "yaw_span", "mouth_mean", "pitch_mean")}
    for key in ("pitch_span", "yaw_span", "mouth_mean"):
        seq = [r[key] for r in rows]
        if any(b < a - 1e-6 for a, b in zip(seq, seq[1:])):
            findings.append(Finding(
                "PR-08", "FAIL", "server/stackchan_ai/prosody.py",
                "expressiveness 增大时 %s 非单调：%s" % (key, [round(x, 3) for x in seq])))
    return findings


def check_bandwidth(shim, P, findings, stats):
    """PR-09：单帧 0x14 的体积与 WS 分片容量。"""
    samples = make_utterance("accent")
    feat, track = shim.extract(samples, SR)
    p = shim.build_params("Neutral", feat)
    kfs, _info = shim.compile_keyframes(track, feat, p, "Neutral")
    one = len(json.dumps(kfs[0], separators=(",", ":")).encode("utf-8"))
    per_ws = P.REMOTE_FRAME_MAX // max(one, 1)
    stats["frame_json_bytes"] = one
    stats["bytes_per_sec"] = one * P.OUT_FPS
    stats["frames_per_ws"] = per_ws
    if one > P.REMOTE_FRAME_MAX:
        findings.append(Finding(
            "PR-09", "FAIL", "server/stackchan_ai/prosody.py",
            "单帧 JSON %d B > 上限 %d B" % (one, P.REMOTE_FRAME_MAX)))
    if per_ws < FRAMES_PER_WS_MIN:
        findings.append(Finding(
            "PR-09", "FAIL", "server/stackchan_ai/prosody.py",
            "一个 WS 帧只能装 %d 帧 0x14 < 设计的 %d 帧" % (per_ws, FRAMES_PER_WS_MIN)))
    return findings


#: 入库的真实 TTS 语料目录（MiniMax speech-02-hd / female-shaonv）
REAL_CORPUS_DIRNAME = os.path.join("assets", "prosody-corpus")
#: PR-12 跨文本留一可辨识度下限（实测 61.1%）
REAL_CV_MIN = 0.50
#: PR-13 能量通道活性下限：浊音帧 e_norm 的 p90−p10（实测 0.242）
REAL_ENERGY_SPAN_MIN = 0.10
#: PR-11 情绪基线 SNR 的告警阈值（实测 0.19）
REAL_SNR_WARN = 0.50


def load_real_corpus(repo_root):
    """读入库的真实 TTS 语料；语料不在（未随仓分发）⇒ 返回 None（判据跳过）。"""
    d = os.path.join(repo_root, REAL_CORPUS_DIRNAME)
    mpath = os.path.join(d, "manifest.json")
    if not os.path.isfile(mpath):
        return None
    with io.open(mpath, encoding="utf-8") as f:
        man = json.load(f)
    items = []
    for it in man.get("items", []):
        p = os.path.join(d, it.get("file", ""))
        if not os.path.isfile(p):
            continue
        raw = np.fromfile(p, dtype="<i2").astype(np.float32) / 32768.0
        items.append({"id": it["id"], "emo": it.get("system_emotion", "Neutral"),
                      "txt": it.get("text_id", "t1"), "pcm": raw})
    return items or None


def check_real_corpus(shim, P, repo_root, findings, stats, label_override=None):
    """PR-11 / PR-12 / PR-13：真实 TTS 语料口径（离线，语料已入库）。

    口径说明：
      * **PR-12** 用「跨文本留一」—— 训练 = 另 2 个文本 × 6 情绪，测试 = 留出文本 × 6 情绪，
        最近类心分类器 ⇒ 测的是**跨文本泛化**，不是同一条音频自己认自己。
      * 每条用**自己情绪标签的基线**编译（= 我们系统的真实用法：LLM 给标签 → 基线 + 韵律调制）。
    """
    items = load_real_corpus(repo_root)
    if not items:
        stats["real_corpus"] = "absent（跳过 PR-11/12/13）"
        return findings

    samples = []
    for it in items:
        emo = it["emo"]
        if label_override:
            emo = label_override.get(it["id"], emo)
        feat, track = shim.extract(it["pcm"], 16000)
        p = shim.build_params(emo, feat)
        kfs, info = shim.compile_keyframes(track, feat, p, emo)
        fv = _features(kfs, info)
        env = track["env"]
        out_t = np.arange(len(kfs)) / P.OUT_FPS
        env_i = np.interp(out_t, track["times"], env)
        voiced = np.interp(out_t, track["times"], track["voiced"].astype(float)) > 0.5
        e_ref = float(np.percentile(env, 90))
        e_min = float(np.percentile(env, 20))
        en = np.clip((env_i - e_min) / max(e_ref - e_min, 1.0), 0.0, 1.0)
        span = 0.0
        if voiced.any():
            span = float(np.percentile(en[voiced], 90) - np.percentile(en[voiced], 10))
        samples.append({"id": it["id"], "emo": emo, "txt": it["txt"],
                        "f": _vec(fv), "en_span": span, "mouth": fv["mouth_mean"]})

    emos = sorted({s["emo"] for s in samples})
    txts = sorted({s["txt"] for s in samples})

    # ── PR-12：跨文本留一可辨识度 ──
    accs = {}
    for held in txts:
        train = [s for s in samples if s["txt"] != held]
        test = [s for s in samples if s["txt"] == held]
        if not test or not train:
            continue
        Xtr = np.array([s["f"] for s in train])
        Xte = np.array([s["f"] for s in test])
        mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
        sd[sd < 1e-9] = 1.0
        Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
        # ⚠️ 训练集里缺某个标签时，空切片均值 = NaN ⇒ `NaN < 阈值` 恒为 False
        #    ⇒ **静默通过**（最坏的失败模式）⇒ 必须显式跳过缺失标签，
        #    并在下面把「算不出结果」判成 FAIL 而不是放过。
        cents = {}
        for e in emos:
            idx = [i for i, s in enumerate(train) if s["emo"] == e]
            if not idx:
                continue
            cents[e] = Ztr[idx].mean(axis=0)
        if not cents:
            continue
        ok = 0
        for i, s in enumerate(test):
            dd = {e: float(np.linalg.norm(Zte[i] - c)) for e, c in cents.items()}
            ok += (min(dd, key=dd.get) == s["emo"])
        accs[held] = ok / float(len(test))
    mean_acc = float(np.mean(list(accs.values()))) if accs else 0.0
    if not np.isfinite(mean_acc):
        findings.append(Finding(
            "PR-12", "FAIL", "assets/prosody-corpus",
            "跨文本留一可辨识度算出 NaN（语料标签分布不完整）⇒ 判据无法生效"))
        mean_acc = 0.0
    stats["real_cv"] = {k: round(v * 100, 1) for k, v in accs.items()}
    stats["real_cv_mean"] = round(mean_acc * 100, 1)
    stats["real_corpus_n"] = len(samples)
    if mean_acc < REAL_CV_MIN:
        findings.append(Finding(
            "PR-12", "FAIL", "assets/prosody-corpus",
            "真实 TTS 语料上「跨文本留一」可辨识度 %.1f%% < %.0f%%"
            % (mean_acc * 100, REAL_CV_MIN * 100)))

    # ── PR-13：能量通道活性（嘴必须会动） ──
    spans = [s["en_span"] for s in samples]
    med_span = float(np.median(spans)) if spans else 0.0
    stats["real_energy_span"] = round(med_span, 4)
    if med_span < REAL_ENERGY_SPAN_MIN:
        findings.append(Finding(
            "PR-13", "FAIL", "assets/prosody-corpus",
            "真实 TTS 上能量通道的动态跨度 %.3f < %.2f ⇒ 能量几乎不驱动嘴/眼/灯"
            % (med_span, REAL_ENERGY_SPAN_MIN)))

    # ── PR-11：情绪基线 SNR（能量通道是否在冲掉情绪区分） ──
    sil = np.zeros(16000)
    base = {}
    for e in emos:
        f0, t0 = shim.extract(sil, 16000)
        pp = shim.build_params(e, f0)
        kk, ii = shim.compile_keyframes(t0, f0, pp, e)
        base[e] = _features(kk, ii)["mouth_mean"]
    gaps = []
    es = sorted(base)
    for i in range(len(es)):
        for j in range(i + 1, len(es)):
            gaps.append(abs(base[es[i]] - base[es[j]]))
    min_gap = min(gaps) if gaps else 0.0
    within = []
    for e in emos:
        vals = [s["mouth"] for s in samples if s["emo"] == e]
        if len(vals) > 1:
            within.append(max(vals) - min(vals))
    max_within = max(within) if within else 0.0
    snr = min_gap / max(max_within, 1e-9)
    stats["real_base_min_gap"] = round(min_gap, 3)
    stats["real_within_max"] = round(max_within, 3)
    stats["real_snr"] = round(snr, 4)
    if snr < REAL_SNR_WARN:
        findings.append(Finding(
            "PR-11", "WARN", "assets/prosody-corpus",
            "情绪基线 SNR = %.2f（基线最小间隔 %.1f ÷ 韵律扰动 %.1f）< %.2f "
            "⇒ 能量→嘴的增益可能在冲掉情绪区分 ⇒ 需要重新标定 `energyEyeGain`"
            % (snr, min_gap, max_within, REAL_SNR_WARN)))
    return findings


# ---------------------------------------------------------------------------
# 总入口
# ---------------------------------------------------------------------------
def scan(repo_root, shim=None, label_override=None) -> tuple:
    P = load_prosody(repo_root)
    if shim is None:
        shim = Shim(P)
    findings = []
    stats = {}
    check_edge(shim, P, findings, stats)
    check_silence(shim, P, findings, stats)
    check_reproducible(shim, P, findings, stats)
    check_audit(shim, P, findings, stats)
    check_params(shim, P, findings, stats)
    data = _collect_features(shim, P)
    check_discriminability(shim, P, data, findings, stats)
    check_drowning(shim, P, data, findings, stats)
    check_monotonic(shim, P, findings, stats)
    check_bandwidth(shim, P, findings, stats)
    check_real_corpus(shim, P, repo_root, findings, stats, label_override)
    return findings, stats


# ---------------------------------------------------------------------------
# 自检：用故意做坏的夹具证明每一类都能抓到（判据不是恒真）
# ---------------------------------------------------------------------------
def run_self_test(repo_root=".") -> int:
    P = load_prosody(os.path.abspath(repo_root))
    print("[self-test] check_prosody.py 门禁自检")
    print("=" * 68)
    passed = failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    # ── 阳性：健康仓库必须零 FAIL ──
    f, _ = scan(repo_root)
    check("健康仓库零 FAIL", not any(x.severity == "FAIL" for x in f),
          str([(x.code, x.msg) for x in f]))

    # ── 阴性 1：把 env 边界改回「补零」⇒ PR-01 必须报 ──
    orig_extract = P.extract_prosody

    def zero_pad_extract(samples, sr):
        feat, track = orig_extract(samples, sr)
        energy = track["energy"]
        k = max(3, int(round(0.050 / (track["times"][1] - track["times"][0]))))
        env = np.convolve(energy, np.ones(k) / k, mode="same")
        t2 = dict(track)
        t2["env"] = env
        return feat, t2

    shim = Shim(P)
    shim.extract = zero_pad_extract
    f, _ = scan(repo_root, shim)
    check("env 补零伪影被 PR-01 抓到",
          any(x.code == "PR-01" for x in f), str([(x.code, x.msg) for x in f]))

    # ── 阴性 2：静音也张嘴 ⇒ PR-02 必须报 ──
    orig_compile = P.compile_keyframes

    def mouthy_compile(track, feat, p, emotion="Neutral"):
        # 模拟「静音也弹一下」：首帧嘴张开，其余闭合 ⇒ 跨度必须 > 1
        # （⚠️ 不能把**所有**帧设成同一个值 —— 那样跨度反而是 0，测不出东西）
        kfs, info = orig_compile(track, feat, p, emotion)
        for i, k in enumerate(kfs):
            k["mouth"]["weight"] = 90 if i == 0 else 30
        return kfs, info

    shim = Shim(P)
    shim.compile_keyframes = mouthy_compile
    f, _ = scan(repo_root, shim)
    check("静音张嘴被 PR-02 抓到",
          any(x.code == "PR-02" for x in f), str([(x.code, x.msg) for x in f]))

    # ── 阴性 3：编译不确定 ⇒ PR-03 必须报 ──
    counter = {"n": 0}

    def flaky_compile(track, feat, p, emotion="Neutral"):
        kfs, info = orig_compile(track, feat, p, emotion)
        counter["n"] += 1
        if counter["n"] % 2 == 1:
            kfs[0]["mouth"]["weight"] = int(kfs[0]["mouth"]["weight"]) + 1
        return kfs, info

    shim = Shim(P)
    shim.compile_keyframes = flaky_compile
    f, _ = scan(repo_root, shim)
    check("编译不可复现被 PR-03 抓到",
          any(x.code == "PR-03" for x in f), str([(x.code, x.msg) for x in f]))

    # ── 阴性 4：抹平 6 个情绪的基线 ⇒ PR-06 必须报（可辨识度塌成随机） ──
    orig_build = P.build_params

    def flat_build(emotion, feat, personal=None):
        p = dict(orig_build(emotion, feat, personal))
        for key in ("eyeWeight", "mouthWeight", "pitch"):
            p["%s_%s" % (emotion, key)] = p["Neutral_%s" % key]
        return p

    shim = Shim(P)
    shim.build_params = flat_build
    f, st = scan(repo_root, shim)
    check("情绪被抹平后 PR-06 报错",
          any(x.code == "PR-06" for x in f), str([(x.code, x.msg) for x in f]))
    check("情绪被抹平后可辨识度显著下降",
          st.get("cv_mean", 100) < 60.0, "cv_mean=%s" % st.get("cv_mean"))

    # ── 阴性 5：真实语料的情绪标签被打乱 ⇒ PR-12 必须报 ──
    items = load_real_corpus(os.path.abspath(repo_root))
    if items:
        # ⚠️「打乱」必须让**标签集合本身**变化，否则等于恒等置换：
        #    逐条轮换 ⇒ 跨文本标签仍相关；按文本整体轮换 ⇒ 两个文本的标签集合本来就相同
        #    （都是 6 个情绪）⇒ 轮换后一模一样 ⇒ 什么也没打乱。
        #    这里把每个文本块压成一个**固定的错误单标签**：
        #    6 类坍缩成 3 类，且留出文本的标签在训练集里根本不存在
        #    ⇒ 最近类心只能瞎选 ⇒ 准确率必然塌 ⇒ PR-12 必报。
        by_txt = {}
        for it in items:
            by_txt.setdefault(it["txt"], []).append(it)
        wrong = ["Angry", "Happy", "Sad", "Doubt", "Sleepy", "Neutral"]
        shuffled = {}
        for k, t in enumerate(sorted(by_txt)):
            for it in by_txt[t]:
                shuffled[it["id"]] = wrong[k % len(wrong)]
        f, st = scan(repo_root, Shim(P), label_override=shuffled)
        check("真实语料标签被打乱后 PR-12 报错",
              any(x.code == "PR-12" for x in f),
              str([(x.code, x.msg) for x in f]))
        check("标签打乱后可辨识度显著下降",
              st.get("real_cv_mean", 100) < 40.0,
              "real_cv_mean=%s" % st.get("real_cv_mean"))
    else:
        print("  SKIP  真实语料不在（PR-11/12/13 未参与自检）")

    print("=" * 68)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="韵律→身体 管线离线标定体检")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--self-test", action="store_true", help="门禁自检")
    ap.add_argument("--json", action="store_true", help="额外输出实测数字（JSON）")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test(args.root)

    root = os.path.abspath(args.root)
    findings, stats = scan(root)
    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]
    print("=" * 70)
    print("check_prosody.py —— 韵律→身体 管线离线标定体检")
    print("=" * 70)
    print("仓库根 : %s" % root)
    print("-" * 70)
    for f in findings:
        print("[%s] %s  %s" % (f.severity, f.where, f.msg))
    if not fails:
        print("-" * 70)
        print("实测数字：")
        for k in ("edge_max_db", "silence_mouth_span", "reproducible", "audit_problems",
                  "audit_warnings", "param_count", "cv_mean", "cv_worst",
                  "drowning_ratio", "frame_json_bytes", "bytes_per_sec", "frames_per_ws",
                  "real_corpus_n", "real_cv_mean", "real_energy_span",
                  "real_base_min_gap", "real_within_max", "real_snr"):
            if k in stats:
                print("  %-22s %s" % (k, stats[k]))
    print("-" * 70)
    print("FAIL=%d  WARN=%d" % (len(fails), len(warns)))
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not fails:
        print("ALL PASS —— 韵律→身体 管线的标定判据全部成立。")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
