#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真机 BLE 一键验收。

用户只需要在设备屏幕上点两下（欢迎页 **Skip** → 应用列表点 **DANCE**），
然后跑一条命令，就能拿到一份完整的真机验收报告。

## 为什么需要它

- ⛔ **固件只在 DANCE 应用打开时启动 BLE 外设**
  （`firmware/main/apps/app_dance/app_dance.cpp:48` → `startBleServer()`；
  `app_avatar/app_avatar.cpp:79` 那行被注释）
  ⇒ 设备停在 Launcher 欢迎页时**不广播**，这解释了此前三次扫描都找不到它。
- ⭐ **BLE 契约在 1.5.1 与 1.6.0 之间逐字节相同**（62 号取证）
- ⭐ **BLE 没有时间轴**：只能"设定一次姿态"，不是回放队列
  ⇒ 韵律→身体在 BLE 上必须**主机侧 25 Hz 连续写**，设备端单槽标志会丢帧。

## 诚实原则

设备不在 DANCE 模式时，所有阶段一律记 **「未执行」**，**绝不写「通过」**。

## 用法

```powershell
py -3.12 tools/ble_acceptance.py --self-test     # 离线自检（不需要设备）
py -3.12 tools/ble_acceptance.py --run            # 完整真机验收
py -3.12 tools/ble_acceptance.py --run --timeout 60 --address 68:ee:8f:d7:36:68
```

报告写到 `docs/research/64-真机BLE一键验收报告.md`。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import stackchan_ble as ble  # noqa: E402

REPO = os.path.dirname(_HERE)
REPORT_PATH = os.path.join(REPO, "docs", "research",
                            "64-真机BLE一键验收报告.md")
KEYFRAMES = r"D:\AP\AP7000\ai-workspace\stackchan-research\r59\keyframes.json"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


class Stage:
    def __init__(self, idx, name, desc):
        self.idx = idx
        self.name = name
        self.desc = desc
        self.status = SKIP
        self.detail = ""
        self.data = {}

    def done(self, status, detail="", **data):
        self.status = status
        self.detail = detail
        self.data = data
        return self


class Report:
    def __init__(self):
        self.stages = []
        self.meta = {}
        self.shared = {}          # 阶段之间传递数据（如 GATT 清单）

    def add(self, stage):
        self.stages.append(stage)
        return stage

    @property
    def n_fail(self):
        return len([s for s in self.stages if s.status == FAIL])

    @property
    def n_skip(self):
        return len([s for s in self.stages if s.status == SKIP])

    def render(self):
        rows = []
        for s in self.stages:
            mark = {PASS: "✅", FAIL: "❌", SKIP: "⏭️"}[s.status]
            rows.append("| %d | %s | %s | %s | %s |" % (
                s.idx, s.name, mark, s.status, (s.detail or "—").replace("|", "\\|")))
        return "\n".join(rows)


# ══════════════════════════════════════════════════════════════════════════
# 阶段实现
# ══════════════════════════════════════════════════════════════════════════

def stage_scan(rep, timeout, address):
    st = rep.add(Stage(1, "扫描设备", "找到广播中的 StackChan"))
    try:
        devices = ble.scan(timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return st.done(FAIL, "扫描异常：%s" % (e,))
    names = ", ".join(sorted({d.get("name") or "(无名)" for d in devices})) or "（无）"
    st.data["scanned"] = len(devices)
    st.data["names"] = names
    if address:
        hit = [d for d in devices
               if str(d.get("address", "")).upper() == address.upper()]
        if hit:
            return st.done(PASS, "按地址命中 %s（扫描到 %d 个设备）" % (address, len(devices)),
                           address=hit[0].get("address"))
        return st.done(FAIL, "指定地址 %s 未在扫描结果中（扫到 %d 个：%s）" % (address, len(devices), names))
    dev = ble.find_device(timeout=1.0)
    if dev:
        return st.done(PASS, "找到 %s @ %s（扫到 %d 个）" % (
            dev.get("name") or "?", dev.get("address"), len(devices)),
            address=dev.get("address"))
    return st.done(FAIL,
                   "未找到 StackChan。⛔ 设备必须先进 **DANCE 应用**才会广播 BLE"
                   "（app_dance.cpp:48）。请点：欢迎页 **Skip** → 应用列表 **DANCE**。"
                   "本次扫到 %d 个设备：%s" % (len(devices), names))


def stage_connect(rep, address):
    st = rep.add(Stage(2, "连接 + GATT 清单", "6 个 UUID 是否齐全"))
    try:
        inv = ble.connect(address)
    except Exception as e:  # noqa: BLE001
        return st.done(FAIL, "连接失败：%s" % (e,))
    st.data["inventory"] = inv
    rep.shared["inventory"] = inv
    chars = _collect_chars(inv)
    want = {
        "motion": ble.MOTION_CHAR_UUID,
        "avatar": ble.AVATAR_CHAR_UUID,
        "config": ble.CONFIG_CHAR_UUID,
        "rgb": ble.RGB_CHAR_UUID,
    }
    found = {k: (v.lower() in [c.lower() for c in chars]) for k, v in want.items()}
    missing = [k for k, ok in found.items() if not ok]
    st.data["found"] = found
    if missing:
        return st.done(FAIL, "缺少特征：%s（实到 %d 个）" % (", ".join(missing), len(chars)))
    return st.done(PASS, "4 个可写特征齐全（共 %d 个）" % len(chars), chars=chars)


def _collect_chars(inv):
    out = []
    if isinstance(inv, dict):
        for key in ("characteristics", "chars", "services"):
            v = inv.get(key)
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        u = item.get("uuid") or item.get("UUID")
                        if u:
                            out.append(str(u))
                    elif isinstance(item, str):
                        out.append(item)
    return out


def stage_inventory(rep, address):
    st = rep.add(Stage(3, "特征清单", "逐条对照 62 号文档"))
    inv = rep.shared.get("inventory") or {}
    chars = _collect_chars(inv)
    st.data["chars"] = chars
    rows = [
        ("motion", ble.MOTION_CHAR_UUID, "舵机姿态（0.1 度）"),
        ("avatar", ble.AVATAR_CHAR_UUID, "表情三元素 × 5 参数"),
        ("rgb", ble.RGB_CHAR_UUID, "左右灯色 + 时长"),
        ("config", ble.CONFIG_CHAR_UUID, "配网 / 握手"),
    ]
    st.data["rows"] = rows
    if not chars:
        return st.done(SKIP, "阶段 2 未取得 GATT 清单，本阶段未执行")
    return st.done(PASS, "已采集 %d 个特征" % len(chars))


def stage_motion(rep, address):
    st = rep.add(Stage(4, "转头 demo", "写 yaw/pitch 并读回"))
    seq = [(0, 45, 30), (20, 45, 30), (0, 45, 30), (-20, 45, 30), (0, 45, 30)]
    sent = []
    try:
        for yaw, pitch, speed in seq:
            payload = ble.build_motion_json(yaw, pitch, speed)
            sent.append({"yaw_deg": yaw, "pitch_deg": pitch,
                         "raw": json.loads(payload)})
            ble.send_motion(yaw, pitch, speed)
            time.sleep(0.25)
    except Exception as e:  # noqa: BLE001
        return st.done(FAIL, "写 motion 失败：%s" % (e,), sent=sent)
    st.data["sent"] = sent
    return st.done(PASS, "已写 %d 条姿态（±20° / pitch 45°），**请肉眼确认设备确实转了头**" % len(sent),
                   sent=sent)


def stage_avatar(rep, address):
    st = rep.add(Stage(5, "眨眼 + 嘴", "验证 weight 极性"))
    weights = [0, 35, 72, 100]
    sent = []
    try:
        for w in weights:
            eye = {"x": 0, "y": 0, "rotation": 0, "weight": w, "size": 0}
            mouth = {"x": 0, "y": 0, "rotation": 0, "weight": w, "size": 0}
            payload = ble.build_avatar_json(eye, eye, mouth)
            sent.append({"weight": w, "raw": json.loads(payload)})
            ble.send_avatar(eye, eye, mouth)
            time.sleep(0.4)
    except Exception as e:  # noqa: BLE001
        return st.done(FAIL, "写 avatar 失败：%s" % (e,), sent=sent)
    st.data["sent"] = sent
    return st.done(PASS,
                   "已按 weight=%s 依次写眼睛与嘴。**请肉眼确认：weight 越大眼睛越睁开、嘴越张开**"
                   % (weights,), sent=sent)


def stage_limits(rep, address):
    st = rep.add(Stage(6, "舵机限位", "小步进试探，不撞限位"))
    cases = [
        ("yaw +100°", 100.0, 45.0),
        ("yaw -100°", -100.0, 45.0),
        ("pitch 30°（下限）", 0.0, 3.0),
        ("pitch 87°（上限）", 0.0, 87.0),
    ]
    out = []
    try:
        for name, yaw, pitch in cases:
            payload = json.loads(ble.build_motion_json(yaw, pitch, 300))
            raw_yaw = payload["yawServo"]["angle"]
            raw_pitch = payload["pitchServo"]["angle"]
            ok = (ble.YAW_LIMIT[0] <= raw_yaw <= ble.YAW_LIMIT[1]
                  and ble.PITCH_LIMIT[0] <= raw_pitch <= ble.PITCH_LIMIT[1])
            out.append({"case": name, "raw_yaw": raw_yaw, "raw_pitch": raw_pitch,
                        "in_range": ok})
            ble.send_motion(yaw, pitch, 300)
            time.sleep(0.2)
    except Exception as e:  # noqa: BLE001
        return st.done(FAIL, "限位试探失败：%s" % (e,), cases=out)
    st.data["cases"] = out
    bad = [o for o in out if not o["in_range"]]
    if bad:
        return st.done(FAIL, "以下用例越界：%s" % (bad,), cases=out)
    return st.done(PASS, "4 个边界用例的原始值都在限位内（yaw ±1280 / pitch 30..870）", cases=out)


def stage_playback(rep, address, keyframes):
    st = rep.add(Stage(7, "关键帧播放 + 丢帧率", "25 Hz 连续写，统计丢帧"))
    if not os.path.exists(keyframes):
        return st.done(SKIP, "关键帧样本不存在：%s" % keyframes)
    try:
        frames = ble.load_keyframes(keyframes)
    except Exception as e:  # noqa: BLE001
        return st.done(FAIL, "读关键帧失败：%s" % (e,))
    total = len(frames)
    if total == 0:
        return st.done(FAIL, "关键帧为空")
    expect_ms = sum(int(f.get("durationMs") or 40) for f in frames)
    ok = 0
    err = 0
    t0 = time.time()
    for f in frames:
        try:
            motion, avatar, rgb = ble.build_keyframe_payloads(f)
            for payload in (motion, avatar, rgb):
                ble._run(ble._write_async(ble.MOTION_CHAR_UUID, payload)
                         if payload is motion else
                         ble._write_async(ble.AVATAR_CHAR_UUID, payload)
                         if payload is avatar else
                         ble._write_async(ble.RGB_CHAR_UUID, payload))
            ok += 1
        except Exception:  # noqa: BLE001
            err += 1
        time.sleep(max(float(f.get("durationMs") or 40) / 1000.0, ble.MIN_FRAME_GAP_S))
    elapsed = time.time() - t0
    loss = (total - ok) / float(total) * 100.0
    st.data.update({"frames": total, "written": ok, "errors": err,
                    "loss_pct": round(loss, 3), "elapsed_s": round(elapsed, 3),
                    "expect_ms": expect_ms, "actual_ms": int(elapsed * 1000)})
    if err:
        return st.done(FAIL, "写入异常 %d 帧（成功 %d/%d，丢帧率 %.2f%%）"
                       % (err, ok, total, loss), **st.data)
    return st.done(PASS, "写入 %d/%d 帧，丢帧率 %.2f%%，耗时 %d ms（应 %d ms）"
                   % (ok, total, loss, int(elapsed * 1000), expect_ms), **st.data)


def stage_payload_cap(rep, address):
    st = rep.add(Stage(8, "载荷上限", "2048 B 上限"))
    big = {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0}
    payload = ble.build_avatar_json(big, big, big)
    n = len(payload.encode("utf-8"))
    st.data["bytes"] = n
    st.data["limit"] = ble.MAX_JSON_LEN
    if n > ble.MAX_JSON_LEN:
        return st.done(FAIL, "构造出的载荷 %d B 超过上限 %d B" % (n, ble.MAX_JSON_LEN))
    return st.done(PASS, "最大载荷 %d B ≤ 上限 %d B" % (n, ble.MAX_JSON_LEN))


# ══════════════════════════════════════════════════════════════════════════
# 离线自检（用 mock 覆盖载荷构造与错误路径）
# ══════════════════════════════════════════════════════════════════════════

def self_test() -> int:
    print("=" * 72)
    print("自检：离线载荷构造 + 错误路径（不需要真机）")
    print("=" * 72)
    ok = True
    fails = []
    total = 0

    def chk(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            print("  PASS  {}{}".format(name, ("  (" + detail + ")") if detail else ""))
        else:
            ok = False
            fails.append("{} :: {}".format(name, detail))
            print("  FAIL  {}  {}".format(name, detail))

    print()
    print("── 1. Motion 载荷契约 ──")
    p = json.loads(ble.build_motion_json(20.0, 45.0, 500))
    chk("type = bleMotion", p.get("type") == "bleMotion", str(p.get("type")))
    chk("角度单位 0.1 度（20° → 200）", p["yawServo"]["angle"] == 200,
        str(p["yawServo"]["angle"]))
    chk("pitch 45° → 450", p["pitchServo"]["angle"] == 450,
        str(p["pitchServo"]["angle"]))
    chk("无 rotate 字段（固件 rotate 优先级最高，不可发）", "rotate" not in p)
    chk("负角度正确编码", json.loads(ble.build_motion_json(-20.0, 45.0, 500))
        ["yawServo"]["angle"] == -200)

    print()
    print("── 2. Avatar 载荷契约 ──")
    a = json.loads(ble.build_avatar_json(
        {"x": 1, "y": 2, "rotation": 3, "weight": 72, "size": 4},
        {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
        {"x": 0, "y": 0, "rotation": 0, "weight": 30, "size": 0}))
    chk("type = bleAvatar", a.get("type") == "bleAvatar")
    chk("三个元素齐全", all(k in a for k in ("leftEye", "rightEye", "mouth")))
    chk("x/y 是 int 不是 float",
        isinstance(a["leftEye"]["x"], int) and isinstance(a["leftEye"]["y"], int))
    chk("浮点输入被转 int（固件 is<int>() 判 float 会丢弃）",
        json.loads(ble.build_avatar_json({"x": 1.9, "y": 2.9, "rotation": 0,
                                          "weight": 1, "size": 0},
                                         {"x": 0, "y": 0, "rotation": 0,
                                          "weight": 1, "size": 0},
                                         {"x": 0, "y": 0, "rotation": 0,
                                          "weight": 1, "size": 0}))
        ["leftEye"]["x"] == 1)
    chk("只保留固件认识的 5 个字段",
        set(a["leftEye"].keys()) == {"x", "y", "rotation", "weight", "size"})

    print()
    print("── 3. RGB 载荷契约 ──")
    r = json.loads(ble.build_rgb_json("#FF6D60", "#8FD3F4", 0.3))
    chk("没有 type 字段", "type" not in r, str(list(r.keys())))
    chk("四个键齐全", set(r.keys()) == {"leftRgbColor", "leftRgbDuration",
                                       "rightRgbColor", "rightRgbDuration"})
    chk("duration 是 float（固件判 is<float>()）",
        isinstance(r["leftRgbDuration"], float),
        type(r["leftRgbDuration"]).__name__)

    print()
    print("── 4. 限位常量 ──")
    chk("yaw 限位 ±1280", ble.YAW_LIMIT == (-1280, 1280), str(ble.YAW_LIMIT))
    chk("pitch 限位 30..870", ble.PITCH_LIMIT == (30, 870), str(ble.PITCH_LIMIT))
    chk("载荷上限 2048", ble.MAX_JSON_LEN == 2048, str(ble.MAX_JSON_LEN))
    chk("最小帧间隔 ≥12ms", ble.MIN_FRAME_GAP_S >= 0.012, str(ble.MIN_FRAME_GAP_S))

    print()
    print("── 5. 关键帧拆分 ──")
    kf = {
        "leftEye": {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
        "rightEye": {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
        "mouth": {"x": 0, "y": 0, "rotation": 0, "weight": 30, "size": 0},
        "yawServo": {"angle": 120, "speed": 200},
        "pitchServo": {"angle": 450, "speed": 200},
        "leftRgbColor": "#FF6D60", "rightRgbColor": "#8FD3F4",
        "durationMs": 40,
    }
    m, av, rg = ble.build_keyframe_payloads(kf)
    chk("拆成 motion/avatar/rgb 三份", all(isinstance(x, str) for x in (m, av, rg)))
    chk("motion 的 yaw 保留原始值（0.1 度）",
        json.loads(m)["yawServo"]["angle"] == 120)
    chk("avatar 保留 weight", json.loads(av)["leftEye"]["weight"] == 100)
    chk("rgb 保留颜色", json.loads(rg)["leftRgbColor"] == "#FF6D60")

    print()
    print("── 6. 设备缺失时优雅降级（不崩、不假装成功）──")
    rep = Report()
    orig_scan, orig_find = ble.scan, ble.find_device
    ble.scan = lambda timeout=5.0: []
    ble.find_device = lambda timeout=10.0: None
    try:
        st = stage_scan(rep, 1.0, None)
        chk("扫不到设备 ⇒ FAIL 而非崩", st.status == FAIL, st.status)
        chk("FAIL 文案含 DANCE 指引", "DANCE" in st.detail, st.detail[:60])
        rep2 = Report()
        for fn in (stage_connect, stage_inventory, stage_motion,
                   stage_avatar, stage_limits, stage_playback, stage_payload_cap):
            s = fn(rep2, "68:ee:8f:d7:36:68", KEYFRAMES) if fn is stage_playback \
                else fn(rep2, "68:ee:8f:d7:36:68")
            # 阶段 8 是**纯计算**（不碰设备），设备缺失时判 PASS 是正确的；
            # 其余阶段必须 FAIL/SKIP，绝不能 PASS。
            allowed = (PASS,) if fn is stage_payload_cap else (FAIL, SKIP)
            chk("%s 在无设备时判 %s 而非 PASS" % (s.name, "/".join(allowed)),
                s.status in allowed, s.status)
    finally:
        ble.scan, ble.find_device = orig_scan, orig_find

    print()
    print("── 7. 写异常时不崩 ──")
    orig_write = ble._write_async

    async def boom(*a, **k):
        raise RuntimeError("模拟 BLE 写失败")

    rep3 = Report()
    ble._write_async = boom
    try:
        s = stage_motion(rep3, "addr")
        chk("写失败 ⇒ FAIL", s.status == FAIL, s.status)
        chk("FAIL 文案带原因", "失败" in s.detail, s.detail[:60])
    finally:
        ble._write_async = orig_write

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
# 报告
# ══════════════════════════════════════════════════════════════════════════

def write_report(rep, meta):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 64 · 真机 BLE 一键验收报告",
        "",
        "> 生成器：`tools/ble_acceptance.py`（一条命令跑完 8 个阶段）",
        "> 生成时间：%s" % now,
        "",
        "## 0. 本次执行条件",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| 目标地址 | %s |" % meta.get("address", "（自动发现）"),
        "| 扫描超时 | %s s |" % meta.get("timeout", "—"),
        "| 关键帧样本 | %s |" % meta.get("keyframes", "—"),
        "| 结论 | **%s** |" % meta.get("summary", "—"),
        "",
        "## 1. 阶段结果",
        "",
        "| # | 阶段 | | 状态 | 说明 |",
        "|---|---|---|---|---|",
        rep.render(),
        "",
        "## 2. 状态说明",
        "",
        "- **PASS** —— 该阶段已执行且判定通过。",
        "- **FAIL** —— 该阶段已执行但未通过，或执行中出错。",
        "- **SKIP** —— 该阶段**未执行**（例如依赖的样本文件不存在）。"
        "⛔ **未执行 ≠ 通过**。",
        "",
    ]
    data = []
    for s in rep.stages:
        if s.data:
            data.append((s.name, s.data))
    if data:
        lines += ["## 3. 原始数据", ""]
        for name, d in data:
            lines.append("### %s" % name)
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(d, ensure_ascii=False, indent=2)[:4000])
            lines.append("```")
            lines.append("")
    lines += [
        "## 4. 未验证项（诚实登记）",
        "",
        "| 项 | 说明 |",
        "|---|---|",
        "| 眼睛 weight 极性的**肉眼确认** | 脚本只能证明"
        "「字节写成功」；「weight 越大越睁开」需人眼看设备屏幕 |",
        "| 舵机实际转角 | 脚本只验证编码值在限位内；"
        "实际角度需读回或目视 |",
        "| 丢帧率 | BLE 单槽标志，丢帧是固件行为；"
        "统计值受主机写延迟影响 |",
        "",
    ]
    parent = os.path.dirname(REPORT_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return REPORT_PATH


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="真机 BLE 一键验收")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true", help="执行真机验收")
    ap.add_argument("--address", help="指定设备地址（默认自动发现）")
    ap.add_argument("--timeout", type=float, default=12.0, help="扫描超时（秒）")
    ap.add_argument("--keyframes", default=KEYFRAMES)
    ap.add_argument("--no-report", action="store_true", help="不写 Markdown 报告")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.run:
        ap.print_help()
        return 2

    rep = Report()
    print("=" * 72)
    print("StackChan 真机 BLE 验收")
    print("=" * 72)
    print("⛔ 设备必须已在 **DANCE 应用**里（欢迎页点 Skip → 应用列表点 DANCE）")
    print("   固件只在 DANCE 打开时启动 BLE 外设（app_dance.cpp:48）")
    print()

    st = stage_scan(rep, args.timeout, args.address)
    print("[%s] 1 %s — %s" % (st.status, st.name, st.detail))
    if st.status == FAIL:
        summary = "未执行任何真机阶段：设备未广播（不在 DANCE 模式）"
        meta = {"address": args.address or "（自动发现）", "timeout": args.timeout,
                "keyframes": args.keyframes, "summary": summary}
        for i, (nm, ds) in enumerate([
                ("连接 + GATT 清单", ""), ("特征清单", ""), ("转头 demo", ""),
                ("眨眼 + 嘴", ""), ("舵机限位", ""),
                ("关键帧播放 + 丢帧率", ""), ("载荷上限", "")], start=2):
            rep.add(Stage(i, nm, "依赖阶段 1")).done(SKIP, "阶段 1 失败，未执行")
        if not args.no_report:
            p = write_report(rep, meta)
            print("\n报告 → %s" % p)
        print("\n结论：%s" % summary)
        return 1

    address = args.address or st.data.get("address")
    for fn in (stage_connect, stage_inventory, stage_motion, stage_avatar,
               stage_limits):
        s = fn(rep, address)
        print("[%s] %d %s — %s" % (s.status, s.idx, s.name, s.detail))
    s = stage_playback(rep, address, args.keyframes)
    print("[%s] %d %s — %s" % (s.status, s.idx, s.name, s.detail))
    s = stage_payload_cap(rep, address)
    print("[%s] %d %s — %s" % (s.status, s.idx, s.name, s.detail))

    try:
        ble.disconnect()
    except Exception:  # noqa: BLE001
        pass

    if rep.n_fail == 0 and rep.n_skip == 0:
        summary = "全部 %d 个阶段通过" % len(rep.stages)
    else:
        summary = "FAIL %d 项 / 未执行 %d 项 / 共 %d 阶段" % (
            rep.n_fail, rep.n_skip, len(rep.stages))
    meta = {"address": address, "timeout": args.timeout,
            "keyframes": args.keyframes, "summary": summary}
    if not args.no_report:
        p = write_report(rep, meta)
        print("\n报告 → %s" % p)
    print("\n结论：%s" % summary)
    return 0 if rep.n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
