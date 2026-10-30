#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""0x14 关键帧的**分段 + 定时调度**器。

## 为什么需要它

真实 MiniMax TTS（11.68 s）编译出 **292 帧 / 94 042 B** 的 0x14 载荷，
超过局域网单帧上限 **65 535 B**（`local_network_protocol.h:18` `UINT16_MAX`）。
且固件**不接受**稀疏/差分编码（缺字段会回到默认值，见下）⇒ 只能**切成多段**。

## 固件行为（决定调度策略的三个事实）

1. `app_avatar.cpp:205-214`：`onWsDanceData` 回调里
   **先 `removeModifier(_dance_modifier_id)` 再 `addModifier(DanceModifier)`**
   ⇒ **新段顶掉旧段，没有队列**。
2. `modifiers/dance.h:96-99`：`DanceModifier` 构造即 `_timeline.start()`
   ⇒ 新段到达瞬间，第 0 帧**立刻 apply**，姿态硬切。
3. `animation.cpp:17-37`：`Keyframe::apply()` **无条件**应用全部字段
   ⇒ 缺字段不是「保持上一帧」，而是默认 `angle=0` / `weight=0`，
   且 `FeatureKeyframe::size` 构造函数里**没初始化**（未定义值）
   ⇒ ⛔ **每帧必须带全 8 键**，差分编码不可行。

⇒ **调度规则**：第 k+1 段必须在第 k 段的**播放窗口结束的瞬间**到达。
早到 ⇒ 硬切；晚到 ⇒ 停顿。

## 用法

```powershell
py -3.12 tools/dance_chunk.py --self-test
py -3.12 tools/dance_chunk.py --in kf.json --outdir chunks --max-bytes 16384 --max-frames 64
```

产物：`chunks/chunk-00.json` …（每段一个 0x14 payload）+ `chunks/plan.json`（发送时刻表）。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 默认参数（**自研设定，非官方值**）
DEFAULT_MAX_BYTES = 16 * 1024     # 单段载荷上限（远小于 65535，为 ArduinoJson 解析留余量）
DEFAULT_MAX_FRAMES = 64           # 单段帧数上限（控制 WS 收包线程里的反序列化耗时）

# 局域网单帧上限（local_network_protocol.h:18 UINT16_MAX）
LAN_FRAME_MAX = 65535


class ChunkError(Exception):
    """分段失败。"""


# ══════════════════════════════════════════════════════════════════════════
# 1. 序列化（必须与 stackchan_server.build_dance_payload 字节级一致）
# ══════════════════════════════════════════════════════════════════════════

def serialize(sequence) -> bytes:
    """0x14 payload：顶层 JSON 数组，**不带** 12 字节 MAC 前缀。

    与 `tools/stackchan_server.py:build_dance_payload` 完全一致
    （`separators=(",", ":")` + `ensure_ascii=False`）。
    """
    return json.dumps(sequence, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════
# 2. 分段
# ══════════════════════════════════════════════════════════════════════════

def chunk_keyframes(sequence, max_bytes: int = DEFAULT_MAX_BYTES,
                    max_frames: int = DEFAULT_MAX_FRAMES):
    """把关键帧序列切成若干段，每段的**真实序列化字节数** ≤ max_bytes。

    切分只发生在**帧边界**上 ⇒ 段与段之间的姿态过渡 = 正常的帧间过渡。

    约束与失败条件：

    * 单帧本身就 > max_bytes ⇒ `ChunkError`（帧不可再切）
    * 空序列 ⇒ `ChunkError`
    * max_bytes > LAN_FRAME_MAX ⇒ `ChunkError`（否则切了也过不了局域网）
    """
    if not sequence:
        raise ChunkError("关键帧序列为空")
    if max_bytes <= 0:
        raise ChunkError("max_bytes 必须为正")
    if max_bytes > LAN_FRAME_MAX:
        raise ChunkError("max_bytes=%d 超过局域网单帧上限 %d" % (max_bytes, LAN_FRAME_MAX))
    if max_frames <= 0:
        raise ChunkError("max_frames 必须为正")

    chunks = []
    cur = []
    cur_bytes = 0
    # 顶层数组的 '[' 与 ']' 各占 1 字节，元素之间用 ',' 分隔
    for kf in sequence:
        one = len(serialize([kf]))
        # 单帧的完整贡献 = 元素本身 + 逗号（若不是第一个元素）
        add = one + (1 if cur else 0)
        if cur and (cur_bytes + add > max_bytes or len(cur) >= max_frames):
            chunks.append(cur)
            cur = []
            cur_bytes = 0
            add = one
        if add > max_bytes:
            raise ChunkError(
                "单帧序列化后 %d B，超过 max_bytes=%d B，帧不可再切"
                % (add, max_bytes))
        cur.append(kf)
        cur_bytes += add
    if cur:
        chunks.append(cur)
    return chunks


# ══════════════════════════════════════════════════════════════════════════
# 3. 调度
# ══════════════════════════════════════════════════════════════════════════

def chunk_duration_ms(chunk) -> int:
    """一段的总时长 = 该段所有帧 durationMs 之和。"""
    return sum(int(kf.get("durationMs", 0)) for kf in chunk)


def plan_schedule(chunks, lead_ms: int = 0):
    """生成发送时刻表。

    * `offset_ms[i]` = 第 i 段应当**到达设备**的时刻（相对第 0 段）
    * `lead_ms` = 提前量（补偿网络单程延迟；取值靠实测，默认 0）

    不变式：`offset_ms[i+1] == offset_ms[i] + duration_ms[i]`
    ⇒ 段与段之间**不留缝也不重叠**。
    """
    if lead_ms < 0:
        raise ChunkError("lead_ms 不能为负")
    plan = []
    t = 0
    for i, c in enumerate(chunks):
        dur = chunk_duration_ms(c)
        plan.append({
            "index": i,
            "offset_ms": t - lead_ms if i == 0 else t - lead_ms,
            "duration_ms": dur,
            "frames": len(c),
            "bytes": len(serialize(c)),
        })
        t += dur
    return plan


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
            fails.append("{} :: {}".format(name, detail))
            print("  FAIL  {}  {}".format(name, detail))

    def mkframe(i):
        """造一帧合法的 0x14 关键帧（8 键齐全）。"""
        return {
            "leftEye": {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
            "rightEye": {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
            "mouth": {"x": 0, "y": 0, "rotation": 0, "weight": 30, "size": 0},
            "yawServo": {"angle": i % 400 - 200, "speed": 200},
            "pitchServo": {"angle": 450, "speed": 200},
            "leftRgbColor": "#FF6D60",
            "rightRgbColor": "#8FD3F4",
            "durationMs": 40,
        }

    print("=" * 72)
    print("自检 1：序列化与 stackchan_server 字节级一致")
    print("=" * 72)
    try:
        import stackchan_server as scs
        seq = [mkframe(0), mkframe(1)]
        chk("与 build_dance_payload 完全一致",
            serialize(seq) == scs.build_dance_payload(seq),
            "%d B" % len(serialize(seq)))
        chk("不带 MAC 前缀（首字节是 '['）",
            serialize(seq)[:1] == b"[", repr(serialize(seq)[:1]))
    except ImportError:
        print("  SKIP  stackchan_server 不在同目录，跳过交叉验证")

    print()
    print("=" * 72)
    print("自检 2：分段 —— 字节上限、帧数守恒、时长守恒")
    print("=" * 72)
    seq = [mkframe(i) for i in range(292)]
    total_bytes = len(serialize(seq))
    chunks = chunk_keyframes(seq, max_bytes=16384, max_frames=64)
    chk("原始单帧载荷超局域网上限", total_bytes > LAN_FRAME_MAX,
        "%d B > %d B" % (total_bytes, LAN_FRAME_MAX))
    chk("分成了多段", len(chunks) > 1, "%d 段" % len(chunks))
    chk("每段真实字节 ≤ 上限",
        all(len(serialize(c)) <= 16384 for c in chunks),
        "max=%d B" % max(len(serialize(c)) for c in chunks))
    chk("每段帧数 ≤ 上限", all(len(c) <= 64 for c in chunks),
        "max=%d 帧" % max(len(c) for c in chunks))
    chk("帧数守恒", sum(len(c) for c in chunks) == len(seq),
        "%d == %d" % (sum(len(c) for c in chunks), len(seq)))
    chk("帧内容守恒（顺序不变）",
        [kf for c in chunks for kf in c] == seq)
    chk("总时长守恒",
        sum(chunk_duration_ms(c) for c in chunks) == sum(kf["durationMs"] for kf in seq),
        "%d ms" % sum(chunk_duration_ms(c) for c in chunks))

    print()
    print("=" * 72)
    print("自检 3：切分是按字节，不是按帧数蒙的")
    print("=" * 72)
    small = chunk_keyframes(seq, max_bytes=8192, max_frames=64)
    large = chunk_keyframes(seq, max_bytes=32768, max_frames=64)
    chk("上限变小 ⇒ 段数变多", len(small) > len(large),
        "%d 段 > %d 段" % (len(small), len(large)))
    chk("无论怎么切，帧数守恒",
        sum(len(c) for c in small) == sum(len(c) for c in large) == len(seq))
    chk("切分结果与上限无关地稳定（同样输入同样输出）",
        chunk_keyframes(seq, 16384, 64) == chunks)

    print()
    print("=" * 72)
    print("自检 4：调度表")
    print("=" * 72)
    plan = plan_schedule(chunks)
    chk("段数一致", len(plan) == len(chunks))
    chk("offset 单调不减", all(plan[i]["offset_ms"] <= plan[i + 1]["offset_ms"]
                                for i in range(len(plan) - 1)))
    chk("offset[i+1] == offset[i] + duration[i]（不留缝不重叠）",
        all(plan[i + 1]["offset_ms"] == plan[i]["offset_ms"] + plan[i]["duration_ms"]
            for i in range(len(plan) - 1)))
    chk("最后一段 offset + duration == 总时长",
        plan[-1]["offset_ms"] + plan[-1]["duration_ms"]
        == sum(kf["durationMs"] for kf in seq),
        "%d ms" % (plan[-1]["offset_ms"] + plan[-1]["duration_ms"]))
    chk("每段 offset 与 frames/bytes 与实际一致",
        all(p["frames"] == len(chunks[p["index"]])
            and p["bytes"] == len(serialize(chunks[p["index"]]))
            for p in plan))

    print()
    print("=" * 72)
    print("自检 5：错误路径")
    print("=" * 72)
    try:
        chunk_keyframes([])
        chk("空序列应报错", False, "没抛")
    except ChunkError as e:
        chk("空序列报错", True, str(e))
    try:
        chunk_keyframes([mkframe(0)], max_bytes=10)
        chk("单帧超限应报错", False, "没抛")
    except ChunkError as e:
        chk("单帧超限报错", True, str(e))
    try:
        chunk_keyframes([mkframe(0)], max_bytes=LAN_FRAME_MAX + 1)
        chk("超过局域网上限应报错", False, "没抛")
    except ChunkError as e:
        chk("超过局域网上限报错", True, str(e))
    try:
        plan_schedule(chunks, lead_ms=-1)
        chk("负 lead_ms 应报错", False, "没抛")
    except ChunkError as e:
        chk("负 lead_ms 报错", True, str(e))

    print()
    print("=" * 72)
    print("自检 6：真实 292 帧样本（若存在）")
    print("=" * 72)
    real = r"D:\AP\AP7000\ai-workspace\stackchan-research\r59\keyframes.json"
    if os.path.exists(real):
        with io.open(real, encoding="utf-8") as f:
            rk = json.load(f)
        rb = len(serialize(rk))
        rc = chunk_keyframes(rk, max_bytes=16384, max_frames=64)
        chk("真实样本帧数 = 292", len(rk) == 292, str(len(rk)))
        chk("真实样本确实超限", rb > LAN_FRAME_MAX, "%d B" % rb)
        chk("真实样本切分后每段在限内",
            all(len(serialize(c)) <= 16384 for c in rc),
            "%d 段, max=%d B" % (len(rc), max(len(serialize(c)) for c in rc)))
        chk("真实样本帧数守恒", sum(len(c) for c in rc) == len(rk))
        chk("真实样本总时长守恒",
            sum(chunk_duration_ms(c) for c in rc)
            == sum(int(k.get("durationMs", 0)) for k in rk),
            "%d ms" % sum(chunk_duration_ms(c) for c in rc))
    else:
        print("  SKIP  真实样本不存在：", real)

    print()
    print("=" * 72)
    if ok:
        print("自检结果：ALL PASS（{} 项断言）".format(total))
        print("=" * 72)
        return 0
    print("自检结果：FAIL {} 项".format(len(fails)))
    for f in fails:
        print("   - " + f)
    print("=" * 72)
    return 1


# ══════════════════════════════════════════════════════════════════════════
# 5. CLI
# ══════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="0x14 关键帧分段 + 定时调度")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--in", dest="inp", help="输入：0x14 关键帧 JSON 数组")
    ap.add_argument("--outdir", help="输出目录（每段一个 payload + plan.json）")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    ap.add_argument("--lead-ms", type=int, default=0,
                    help="提前量：补偿网络单程延迟（实测后填）")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.inp:
        ap.print_help()
        return 2

    with io.open(args.inp, encoding="utf-8") as f:
        seq = json.load(f)
    if not isinstance(seq, list):
        print("❌ 输入必须是 JSON 数组（固件强制，json_helper.cpp:192-195）", file=sys.stderr)
        return 2

    try:
        chunks = chunk_keyframes(seq, args.max_bytes, args.max_frames)
        plan = plan_schedule(chunks, args.lead_ms)
    except ChunkError as e:
        print("❌ {}".format(e), file=sys.stderr)
        return 1

    total = len(serialize(seq))
    print("输入 {} 帧 / {} B（局域网上限 {} B）".format(len(seq), total, LAN_FRAME_MAX))
    print("切成 {} 段：".format(len(chunks)))
    for p in plan:
        print("  段{}  offset={:6d} ms  时长={:5d} ms  帧数={:3d}  载荷={:6d} B".format(
            p["index"], p["offset_ms"], p["duration_ms"], p["frames"], p["bytes"]))
    print("总时长 {} ms".format(plan[-1]["offset_ms"] + plan[-1]["duration_ms"]))

    if args.outdir:
        outdir = os.path.abspath(args.outdir)
        os.makedirs(outdir, exist_ok=True)
        for p in plan:
            path = os.path.join(outdir, "chunk-%02d.json" % p["index"])
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(chunks[p["index"]], f, ensure_ascii=False,
                          separators=(",", ":"))
                f.write("\n")
        with io.open(os.path.join(outdir, "plan.json"), "w",
                     encoding="utf-8", newline="\n") as f:
            json.dump({
                "source_frames": len(seq),
                "source_bytes": total,
                "max_bytes": args.max_bytes,
                "max_frames": args.max_frames,
                "lead_ms": args.lead_ms,
                "total_duration_ms": plan[-1]["offset_ms"] + plan[-1]["duration_ms"],
                "schedule": plan,
            }, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("产物 → {}".format(outdir))

    return 0


if __name__ == "__main__":
    sys.exit(main())
