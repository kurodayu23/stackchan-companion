#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_latency.py —— 「文字进 → 关键帧可下发」的端到端延迟实测

为什么需要它
------------
`docs/spec/00` §8 的 **M1 里程碑完成判据**写着：

    说话 → 它答 → **开始出声** < 2.5 s

这个数字**从来没被测过** —— 仓库里所有证据都是「链路跑通了」，没有一份是「链路够快」。
求职作品里，「跑通」是及格线，「**跑通而且有实测数字**」才是加分项；
而且这个数字会直接决定产品形态（要不要做流式、要不要预生成、能不能接受长思考）。

本工具按 `server/stackchan_ai/server.py::run_pipeline` **完全相同的顺序与组件**测三段：

    LLM（出文本） → TTS（出 PCM） → 关键帧编译（PCM → 0x14）

⚠️ **口径要说清楚**：本工具测的是**服务端侧的下限**
（文字进 → 关键帧算好可下发），**不含**：App 端首片播放、WS 传输、设备收帧。
所以它是「用户感知延迟」的**下界**，不是上界。

用法
----
    py -3.12 tools/bench_latency.py --provider stub              # 离线，不联网
    py -3.12 tools/bench_latency.py --provider minimax --repeat 3 # 真实 API
    py -3.12 tools/bench_latency.py --self-test                  # 离线自检（CI 跑这个）
    py -3.12 tools/bench_latency.py --json                       # 机器可读

退出码：0 = 跑完；1 = 报错。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 默认测的 3 句话（覆盖短 / 中 / 长三种长度）
DEFAULT_TEXTS = [
    "今天真开心啊，见到你真好。",
    "我刚才下班回来路上看到一只橘猫，蹲在便利店门口不肯走，你猜它是不是在等谁。",
    "有点累了，今天加班到很晚，明天想在家躺一天，做什么都行，就是不想见人。",
]

#: M1 里程碑的硬判据（docs/spec/00 §8）
M1_BUDGET_MS = 2500.0


def _pct(values: list, q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    # 线性插值分位数
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def run_once(server, text: str) -> dict:
    """跑一次三段计时（顺序与 run_pipeline 完全一致）。"""
    t0 = time.perf_counter()
    reply = server.llm.reply(text)
    t1 = time.perf_counter()
    audio = server.tts.synthesize(reply.text)
    t2 = time.perf_counter()
    from server.stackchan_ai.prosody import pcm_to_keyframes
    result = pcm_to_keyframes(
        audio.pcm, audio.sample_rate,
        emotion=server.persona.emotion, personal=server.persona.personal)
    t3 = time.perf_counter()
    return {
        "llm_ms": (t1 - t0) * 1000.0,
        "tts_ms": (t2 - t1) * 1000.0,
        "compile_ms": (t3 - t2) * 1000.0,
        "total_ms": (t3 - t0) * 1000.0,
        "reply_chars": len(reply.text or ""),
        "audio_s": round(float(getattr(audio, "duration_s", 0.0)), 3),
        "frames": len(result.keyframes),
    }


def build_server(provider: str):
    from server.stackchan_ai.config import Config
    from server.stackchan_ai.server import StackChanServer
    cfg = Config.from_env()
    cfg.provider = provider
    return StackChanServer(cfg, verbose=False)


def _fmt_table(rows: list) -> str:
    out = ["| # | LLM ms | TTS ms | 编译 ms | **合计 ms** | 音频 s | 帧数 |",
           "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        out.append("| %d | %.0f | %.0f | %.0f | **%.0f** | %.3f | %d |" % (
            i, r["llm_ms"], r["tts_ms"], r["compile_ms"], r["total_ms"],
            r["audio_s"], r["frames"]))
    return "\n".join(out)


def summarize(rows: list) -> dict:
    totals = [r["total_ms"] for r in rows]
    return {
        "n": len(rows),
        "llm_p50": round(_pct([r["llm_ms"] for r in rows], 0.5), 1),
        "tts_p50": round(_pct([r["tts_ms"] for r in rows], 0.5), 1),
        "compile_p50": round(_pct([r["compile_ms"] for r in rows], 0.5), 1),
        "total_p50": round(_pct(totals, 0.5), 1),
        "total_p95": round(_pct(totals, 0.95), 1),
        "total_max": round(max(totals), 1) if totals else 0.0,
        "budget_ms": M1_BUDGET_MS,
        "within_budget": all(t <= M1_BUDGET_MS for t in totals),
    }


def run_self_test() -> int:
    print("[self-test] bench_latency.py 门禁自检")
    print("=" * 64)
    passed = failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    # 1) stub provider 离线可跑通
    server = build_server("stub")
    r = run_once(server, DEFAULT_TEXTS[0])
    check("stub 下三段计时都 > 0",
          r["llm_ms"] > 0 and r["tts_ms"] > 0 and r["compile_ms"] > 0, str(r))
    check("总耗时 ≥ 三段之和（误差 1 ms 内）",
          abs(r["total_ms"] - (r["llm_ms"] + r["tts_ms"] + r["compile_ms"])) < 1.0,
          "total=%.3f sum=%.3f" % (r["total_ms"],
                                   r["llm_ms"] + r["tts_ms"] + r["compile_ms"]))
    check("产出了关键帧", r["frames"] > 0, str(r["frames"]))
    check("音频时长 > 0", r["audio_s"] > 0, str(r["audio_s"]))

    # 2) 汇总统计
    rows = [r, run_once(server, DEFAULT_TEXTS[1])]
    s = summarize(rows)
    check("汇总 n 正确", s["n"] == 2, str(s))
    check("p50 ≤ max", s["total_p50"] <= s["total_max"], str(s))
    check("budget 判据存在", s["budget_ms"] == M1_BUDGET_MS, str(s))

    # 3) 表格渲染
    md = _fmt_table(rows)
    lines = [l for l in md.splitlines() if l.strip()]
    check("表格行数 = 2 + 表头 + 分隔行", len(lines) == 4, str(len(lines)))
    widths = set(len(l.split("|")) for l in lines)
    check("表格列数一致", len(widths) == 1, str(widths))

    # 4) JSON 可序列化
    js = json.dumps({"rows": rows, "summary": s}, ensure_ascii=False)
    check("JSON 可序列化", len(js) > 0)

    print("=" * 64)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="端到端延迟实测")
    ap.add_argument("--provider", default="stub",
                    choices=["stub", "minimax", "auto"], help="provider")
    ap.add_argument("--repeat", type=int, default=1, help="每句话跑几轮")
    ap.add_argument("--texts", default="", help="分号分隔的测试句；留空用默认 3 句")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--self-test", action="store_true", help="离线自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test()

    texts = [t.strip() for t in args.texts.split(";") if t.strip()] or list(DEFAULT_TEXTS)
    provider = args.provider
    if provider == "auto":
        from server.stackchan_ai.config import Config
        provider = "minimax" if Config.from_env().api_key_present else "stub"

    server = build_server(provider)
    rows = []
    print("=" * 78)
    print("bench_latency —— 文字进 → 关键帧可下发（服务端侧下界，不含播放/传输/设备收帧）")
    print("provider = %s ｜ 重复 %d 轮 ｜ %d 句话" % (provider, args.repeat, len(texts)))
    print("=" * 78)
    for t in texts:
        for _ in range(max(1, args.repeat)):
            rows.append(run_once(server, t))

    if args.json:
        print(json.dumps({"rows": rows, "summary": summarize(rows)},
                         ensure_ascii=False, indent=2))
        return 0

    print(_fmt_table(rows))
    s = summarize(rows)
    print("-" * 78)
    print("LLM p50      : %.0f ms" % s["llm_p50"])
    print("TTS p50      : %.0f ms" % s["tts_p50"])
    print("编译 p50     : %.0f ms" % s["compile_p50"])
    print("合计 p50/p95/max : %.0f / %.0f / %.0f ms"
          % (s["total_p50"], s["total_p95"], s["total_max"]))
    print("M1 判据 %.0f ms  ⇒ %s"
          % (M1_BUDGET_MS, "全部达标 ✅" if s["within_budget"]
             else "有超标 ❌（这是服务端侧下界）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
