#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""calibrate_energy_gain.py —— 韵律→身体「能量通道 + 情绪基线」的**联合标定器**。

为什么需要它
------------
护城河那一格是「韵律 → 舵机/关键帧」，而这条链路里有一处**互相打架的耦合**：

  * 情绪身份住在**嘴**通道（6 个情绪各有一个嘴基线）；
  * 说话能量也想住在**嘴**通道（能量越大嘴越开）；
  * 真实 TTS 有 **40%~60%** 的时间是静音 ⇒ 停顿时嘴怎么闭合，直接决定
    `mouth_mean` 到底在测「情绪」还是「说话时长占比」。

`docs/research/88` 把 SNR 0.19 归因于「能量增益过大」，**本轮实测推翻了它**：
`energyEyeGain` 从 0.30 扫到 0.01，组内扰动几乎不变（10.37 → 10.23）。
真正的杠杆是**停顿闭合口径**与**情绪基线间隔**。

本工具把这两个量变成**可扫描、可回归**的参数，并守住标定成果：

| 模式 | 作用 | 谁用 |
|---|---|---|
| `--root .`（默认） | 检查**生产模块的当前配置是否仍等于选定工作点**（配置漂移检测）+ 输出实测四指标 | 门禁 |
| `--scan` | 扫候选网格，打印取舍面（口径 × 增益 × 基线方案） | 人（离线） |
| `--self-test` | 变异夹具：证明「漂移检测」与「扫描器」都有分辨力 | 门禁自检 |

四指标（全部用**仓内真实 TTS 语料** `assets/prosody-corpus`，18 条，离线不联网）：

| 指标 | 定义 | 阈值 |
|---|---|---|
| `snr` | 情绪基线最小间隔 ÷ 组内韵律扰动 | ≥ 0.50 |
| `cv` | 跨文本留一可辨识度 | ≥ 50% |
| `energy_span` | 浊音帧 `e_norm` 的 p90−p10（能量通道活性） | ≥ 0.60 |
| `mouth_floor` | 真实语料上嘴 weight 的最小值（停顿不塌成 0） | ≥ 3 |

用法
----
    py -3.12 tools/calibrate_energy_gain.py                 # 体检 + 漂移检测
    py -3.12 tools/calibrate_energy_gain.py --scan          # 扫取舍面
    py -3.12 tools/calibrate_energy_gain.py --self-test     # 自检
    py -3.12 tools/calibrate_energy_gain.py --json          # 机器可读

⚠️ 本工具测的是**输出空间的可分性**，**不等于**「人能认出」——
   后者需要主观评测（真机 + 人评），本轮**未验证**。
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
EMOTIONS = ("Neutral", "Happy", "Angry", "Sad", "Doubt", "Sleepy")
#: 跨文本留一用的特征（与 check_prosody 的 PR-12 保持同一批）
FEAT_KEYS = ("pitch_mean", "yaw_range", "eye_mean", "eye_min",
             "mouth_mean", "mouth_max", "mouth_min")

# ══════════════════════════════════════════════════════════════════════════
# 选定工作点（docs/research/102 §四 的扫描结论）—— **单一真值**
# ══════════════════════════════════════════════════════════════════════════

#: 能量定标口径
CAL_ENERGY_MIN_MODE = "voiced_p20"
#: 嘴的能量调制口径
CAL_MOUTH_ENERGY_MODE = "absolute"
#: 停顿时嘴的闭合比（= 基线的比例，不是绝对归零）
CAL_MOUTH_PAUSE_CLOSE_RATIO = 0.35
#: 能量 → 眼睛/嘴 的增益（⭐ **标定后没有下调**，见 102 号 §三的订正）
CAL_ENERGY_EYE_GAIN = 0.30
#: 6 个情绪的嘴基线（最小间隔 6，两端量级不变）
CAL_MOUTH_BASELINES = {
    "Sleepy": 14.0, "Sad": 20.0, "Angry": 26.0,
    "Doubt": 32.0, "Neutral": 38.0, "Happy": 52.0,
}

#: 验收阈值
TH_SNR = 0.50
TH_CV = 0.50
TH_ENERGY_SPAN = 0.60
TH_MOUTH_FLOOR = 3
WEIGHT_MAX = 100


# ── 仓库装载 ─────────────────────────────────────────────────────────────
def load_prosody(repo_root):
    server = os.path.join(repo_root, "server")
    if server not in sys.path:
        sys.path.insert(0, server)
    from stackchan_ai import prosody  # noqa: WPS433
    return prosody


def load_corpus(repo_root):
    d = os.path.join(repo_root, "assets", "prosody-corpus")
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


# ── 测量 ─────────────────────────────────────────────────────────────────
def _feat(kfs):
    mouth = np.array([k["mouth"]["weight"] for k in kfs], dtype=float)
    eye = np.array([k["leftEye"]["weight"] for k in kfs], dtype=float)
    pitch = np.array([k["pitchServo"]["angle"] / 10.0 for k in kfs])
    yaw = np.array([k["yawServo"]["angle"] / 10.0 for k in kfs])
    return {"mouth_mean": float(mouth.mean()), "mouth_max": float(mouth.max()),
            "mouth_min": float(mouth.min()), "eye_mean": float(eye.mean()),
            "eye_min": float(eye.min()), "pitch_mean": float(pitch.mean()),
            "yaw_range": float(yaw.max() - yaw.min())}


def measure(P, items):
    """在给定（当前）生产配置上测四指标。"""
    samples = []
    spans = []
    for it in items:
        feat, track = P.extract_prosody(it["pcm"], SR)
        p = P.build_params(it["emo"], feat)
        kfs, _ = P.compile_keyframes(track, feat, p, it["emo"])
        f = _feat(kfs)
        f["emo"], f["txt"] = it["emo"], it["txt"]
        samples.append(f)
        # 能量通道活性：用**生产模块的定标口径** + **输出帧时间轴**，
        # 与 check_prosody 的 PR-13 同一套算法 ⇒ 两个工具不会各说各话
        e_ref, e_min = P._energy_reference(track)
        out_t = np.arange(len(kfs)) / P.OUT_FPS
        env_i = np.interp(out_t, track["times"], track["env"])
        en = np.clip((env_i - e_min) / max(e_ref - e_min, 1.0), 0.0, 1.0)
        voiced = np.interp(out_t, track["times"],
                           np.asarray(track["voiced"], dtype=float)) > 0.5
        if voiced.any():
            spans.append(float(np.percentile(en[voiced], 90) - np.percentile(en[voiced], 10)))

    sil = np.zeros(SR)
    base = {}
    for e in EMOTIONS:
        f0, t0 = P.extract_prosody(sil, SR)
        pp = P.build_params(e, f0)
        kk, _ = P.compile_keyframes(t0, f0, pp, e)
        base[e] = _feat(kk)["mouth_mean"]
    es = sorted(base, key=lambda e: base[e])
    gaps = [base[es[i + 1]] - base[es[i]] for i in range(len(es) - 1)]
    min_gap = min(gaps) if gaps else 0.0

    within = []
    for e in EMOTIONS:
        vals = [s["mouth_mean"] for s in samples if s["emo"] == e]
        if len(vals) > 1:
            within.append(max(vals) - min(vals))
    max_within = max(within) if within else 0.0

    # 能量通道活性已在上面的主循环里算好（避免第二次编译，把成本减半）

    txts = sorted({s["txt"] for s in samples})
    accs = {}
    for held in txts:
        train = [s for s in samples if s["txt"] != held]
        test = [s for s in samples if s["txt"] == held]
        if not test or not train:
            continue
        Xtr = np.array([[s[k] for k in FEAT_KEYS] for s in train])
        Xte = np.array([[s[k] for k in FEAT_KEYS] for s in test])
        mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
        sd[sd < 1e-9] = 1.0
        Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
        cents = {}
        for e in EMOTIONS:
            idx = [i for i, s in enumerate(train) if s["emo"] == e]
            if idx:
                cents[e] = Ztr[idx].mean(axis=0)
        ok = 0
        for i, s in enumerate(test):
            dd = {e: float(np.linalg.norm(Zte[i] - c)) for e, c in cents.items()}
            ok += (min(dd, key=dd.get) == s["emo"])
        accs[held] = ok / float(len(test))

    return {
        "min_gap": round(min_gap, 3),
        "max_within": round(max_within, 3),
        "snr": round(min_gap / max(max_within, 1e-9), 4),
        "cv": round((float(np.mean(list(accs.values()))) if accs else 0.0) * 100, 1),
        "energy_span": round(float(np.median(spans)) if spans else 0.0, 4),
        "mouth_floor": round(min(s["mouth_min"] for s in samples), 2),
        "mouth_ceiling": round(max(s["mouth_max"] for s in samples), 2),
        "baselines": {e: round(base[e], 1) for e in es},
        "n": len(samples),
    }


# ── 配置漂移检测 ─────────────────────────────────────────────────────────
def config_drift(P):
    """生产模块的当前配置 vs 选定工作点。返回漂移列表（空 = 没漂移）。"""
    drift = []
    if getattr(P, "ENERGY_MIN_MODE", None) != CAL_ENERGY_MIN_MODE:
        drift.append("ENERGY_MIN_MODE=%r（应为 %r）"
                     % (getattr(P, "ENERGY_MIN_MODE", None), CAL_ENERGY_MIN_MODE))
    if getattr(P, "MOUTH_ENERGY_MODE", None) != CAL_MOUTH_ENERGY_MODE:
        drift.append("MOUTH_ENERGY_MODE=%r（应为 %r）"
                     % (getattr(P, "MOUTH_ENERGY_MODE", None), CAL_MOUTH_ENERGY_MODE))
    if abs(float(getattr(P, "MOUTH_PAUSE_CLOSE_RATIO", -1)) - CAL_MOUTH_PAUSE_CLOSE_RATIO) > 1e-9:
        drift.append("MOUTH_PAUSE_CLOSE_RATIO=%r（应为 %r）"
                     % (getattr(P, "MOUTH_PAUSE_CLOSE_RATIO", None),
                        CAL_MOUTH_PAUSE_CLOSE_RATIO))
    gain = float(P.PROSODY_MOD.get("energyEyeGain", -1))
    if abs(gain - CAL_ENERGY_EYE_GAIN) > 1e-9:
        drift.append("energyEyeGain=%r（应为 %r）" % (gain, CAL_ENERGY_EYE_GAIN))
    for emo, want in CAL_MOUTH_BASELINES.items():
        got = float(P.EMOTION_BASELINE.get("%s_mouthWeight" % emo, -1))
        if abs(got - want) > 1e-9:
            drift.append("%s_mouthWeight=%r（应为 %r）" % (emo, got, want))
    return drift


# ── 取舍面扫描（人用） ───────────────────────────────────────────────────
def scan_grid(P, items, quick=False):
    """扫 (能量口径 × 增益 × 停顿比 × 基线方案)，输出取舍表。

    ``quick=True`` 用**缩减网格**（自检用）⇒ CI 里的自检不会跑满整个面。
    """
    base_variants = {
        "旧值": {"Sleepy": 18.0, "Sad": 20.0, "Angry": 22.0,
                 "Doubt": 26.0, "Neutral": 30.0, "Happy": 52.0},
        "选定": dict(CAL_MOUTH_BASELINES),
    }
    if quick:
        modes = ("all_p20", "voiced_p20")
        gains = (0.30, 0.10)
        pauses = (0.0, 0.35)
    else:
        modes = ("all_p20", "voiced_p20")
        gains = (0.30, 0.18, 0.10)
        pauses = (0.0, 0.35, 0.50)
    rows = []
    saved = (P.ENERGY_MIN_MODE, P.MOUTH_ENERGY_MODE, P.MOUTH_PAUSE_CLOSE_RATIO,
             P.PROSODY_MOD["energyEyeGain"],
             {k: v for k, v in P.EMOTION_BASELINE.items() if k.endswith("_mouthWeight")})
    try:
        for tag, bases in base_variants.items():
            for mode in modes:
                for gain in gains:
                    for pr in pauses:
                        P.ENERGY_MIN_MODE = mode
                        P.MOUTH_PAUSE_CLOSE_RATIO = pr
                        P.PROSODY_MOD["energyEyeGain"] = gain
                        for e, v in bases.items():
                            P.EMOTION_BASELINE["%s_mouthWeight" % e] = v
                        m = measure(P, items)
                        rows.append({"baseline": tag, "energy_min_mode": mode,
                                     "gain": gain, "pause": pr,
                                     "snr": m["snr"], "cv": m["cv"],
                                     "energy_span": m["energy_span"],
                                     "mouth_floor": m["mouth_floor"]})
    finally:
        P.ENERGY_MIN_MODE, P.MOUTH_ENERGY_MODE = saved[0], saved[1]
        P.MOUTH_PAUSE_CLOSE_RATIO = saved[2]
        P.PROSODY_MOD["energyEyeGain"] = saved[3]
        for k, v in saved[4].items():
            P.EMOTION_BASELINE[k] = v
    return rows


# ── 自检 ─────────────────────────────────────────────────────────────────
def run_self_test(repo_root=".") -> int:
    repo_root = os.path.abspath(repo_root)
    P = load_prosody(repo_root)
    items = load_corpus(repo_root)
    passed = failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    print("[self-test] calibrate_energy_gain.py 门禁自检")
    print("=" * 68)

    if not items:
        print("  SKIP  真实语料不在（无法自检）")
        return 1

    # ── 阳性：干净仓没有漂移，且四指标达标 ──
    drift = config_drift(P)
    check("干净仓库无配置漂移", not drift, "; ".join(drift))
    m = measure(P, items)
    check("四指标全部达标",
          m["snr"] >= TH_SNR and m["cv"] >= TH_CV * 100
          and m["energy_span"] >= TH_ENERGY_SPAN and m["mouth_floor"] >= TH_MOUTH_FLOOR,
          str(m))

    # ── 阴性 1：停顿闭合比被改回 0 ⇒ 必须报漂移 ──
    old = P.MOUTH_PAUSE_CLOSE_RATIO
    P.MOUTH_PAUSE_CLOSE_RATIO = 0.0
    try:
        d = config_drift(P)
    finally:
        P.MOUTH_PAUSE_CLOSE_RATIO = old
    check("停顿闭合比被改坏后报出漂移", len(d) >= 1, str(d))

    # ── 阴性 2：某个情绪基线被改 ⇒ 必须报漂移 ──
    old = P.EMOTION_BASELINE["Happy_mouthWeight"]
    P.EMOTION_BASELINE["Happy_mouthWeight"] = 30.0
    try:
        d = config_drift(P)
    finally:
        P.EMOTION_BASELINE["Happy_mouthWeight"] = old
    check("情绪基线被改坏后报出漂移", len(d) >= 1, str(d))

    # ── 阴性 3：能量增益被改 ⇒ 必须报漂移 ──
    old = P.PROSODY_MOD["energyEyeGain"]
    P.PROSODY_MOD["energyEyeGain"] = 0.9
    try:
        d = config_drift(P)
    finally:
        P.PROSODY_MOD["energyEyeGain"] = old
    check("能量增益被改坏后报出漂移", len(d) >= 1, str(d))

    # ── 阴性 4：能量定标口径被改 ⇒ 必须报漂移 ──
    old = P.ENERGY_MIN_MODE
    P.ENERGY_MIN_MODE = "all_p20"
    try:
        d = config_drift(P)
    finally:
        P.ENERGY_MIN_MODE = old
    check("能量定标口径被改坏后报出漂移", len(d) >= 1, str(d))

    # ── 阴性 5：扫描器必须能分辨出「好配置」与「坏配置」 ──
    rows = scan_grid(P, items, quick=True)
    best = max(rows, key=lambda r: r["snr"])
    worst = min(rows, key=lambda r: r["snr"])
    check("扫描面存在可分辨的差异", best["snr"] > worst["snr"] + 0.2,
          "best=%.3f worst=%.3f" % (best["snr"], worst["snr"]))

    # ── 阴性 6：扫描器必须可复现（同一输入两次结果一致） ──
    rows2 = scan_grid(P, items, quick=True)
    check("扫描结果可复现", rows == rows2)

    print("=" * 68)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


# ── 主流程 ───────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="韵律→身体 联合标定器")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--scan", action="store_true", help="扫描取舍面（离线，人用）")
    ap.add_argument("--self-test", action="store_true", help="门禁自检")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if args.self_test:
        return run_self_test(root)

    P = load_prosody(root)
    items = load_corpus(root)
    if not items:
        print("真实语料不在：%s/assets/prosody-corpus" % root)
        return 1

    if args.scan:
        rows = scan_grid(P, items)
        print("=" * 96)
        print("calibrate_energy_gain —— 取舍面扫描（真实 TTS 语料 %d 条）" % len(items))
        print("=" * 96)
        print("%-8s %-12s %6s %6s | %6s %6s %8s %8s"
              % ("基线", "能量口径", "增益", "停顿比", "SNR", "CV%", "能量动态", "嘴下限"))
        for r in rows:
            print("%-8s %-12s %6.2f %6.2f | %6.3f %6.1f %8.3f %8.1f"
                  % (r["baseline"], r["energy_min_mode"], r["gain"], r["pause"],
                     r["snr"], r["cv"], r["energy_span"], r["mouth_floor"]))
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    drift = config_drift(P)
    m = measure(P, items)
    print("=" * 70)
    print("calibrate_energy_gain —— 标定体检（真实 TTS 语料 %d 条）" % m["n"])
    print("=" * 70)
    print("生产配置：")
    print("  能量定标口径      %s" % P.ENERGY_MIN_MODE)
    print("  嘴能量调制口径    %s" % P.MOUTH_ENERGY_MODE)
    print("  停顿闭合比        %.2f" % P.MOUTH_PAUSE_CLOSE_RATIO)
    print("  energyEyeGain     %.2f" % P.PROSODY_MOD["energyEyeGain"])
    print("  情绪嘴基线        %s" % " / ".join(
        "%s=%g" % (e, P.EMOTION_BASELINE["%s_mouthWeight" % e])
        for e in ("Sleepy", "Sad", "Angry", "Doubt", "Neutral", "Happy")))
    print("-" * 70)
    checks = [
        ("SNR（基线间隔 ÷ 组内扰动）", m["snr"], TH_SNR, ">="),
        ("跨文本留一可辨识度 %", m["cv"], TH_CV * 100, ">="),
        ("能量通道活性（浊音 e_norm 跨度）", m["energy_span"], TH_ENERGY_SPAN, ">="),
        ("嘴 weight 下限（停顿不塌成 0）", m["mouth_floor"], TH_MOUTH_FLOOR, ">="),
    ]
    bad = 0
    for name, got, want, op in checks:
        ok = got >= want
        bad += 0 if ok else 1
        print("  [%s] %-34s %8.3f %s %.3f" % ("PASS" if ok else "FAIL", name, got, op, want))
    ok_ceiling = m["mouth_ceiling"] <= WEIGHT_MAX
    bad += 0 if ok_ceiling else 1
    print("  [%s] %-34s %8.1f <= %d"
          % ("PASS" if ok_ceiling else "FAIL", "嘴 weight 上限（不越界）",
             m["mouth_ceiling"], WEIGHT_MAX))
    drift_bad = len(drift)
    bad += drift_bad
    print("  [%s] %-34s %8d 条" % ("PASS" if drift_bad == 0 else "FAIL",
                                   "配置漂移（与选定工作点一致）", drift_bad))
    for d in drift:
        print("        - %s" % d)
    print("-" * 70)
    print("FAIL=%d" % bad)
    if args.json:
        print(json.dumps({"metrics": m, "drift": drift}, ensure_ascii=False, indent=2))
    if not bad:
        print("ALL PASS —— 标定成果仍然成立。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
