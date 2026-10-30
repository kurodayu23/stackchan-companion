#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""StackChan 协议规则的**离线复核**（Python 重实现一遍 Swift 侧的规则，跑用例证明能区分对错）。

用法：
    py -3.12 ios/tools/frame_spec_check.py
    py -3.12 ios/tools/frame_spec_check.py --keyframes <keyframes.json>

只依赖 Python 标准库。

为什么要有这个脚本：
    本机（Windows）**没有 Swift 编译器**，协议规则写完也跑不了；
    而协议规则一旦写错（长度字节序、0x14 顶层是不是数组、x/y 是不是必须同时 int、
    舵机限位），后面所有东西都是错的。
    ⇒ 这里用 Python 把同一套规则**重新实现一遍**，拿手写用例 + 真实关键帧语料证伪。

被复核的规则（出处都在注释里）：
    - 帧格式 `[Type(1)][Length(4 BE)][Payload]`，Payload 从 offset 5 开始
      —— docs/spec/03 §2.3
    - 0x14 顶层必须是 JSON 数组，每帧 8 个 key
      —— docs/spec/03 §2.5.3 / docs/research/53 §5.2
    - x/y 必须同时是 int（JSON 数字带小数点即不是 int，与 ArduinoJson `is<int>()` 一致）
      —— docs/research/53 §3.1
    - 舵机限位 yaw ∈ [-1280, 1280]、pitch ∈ [30, 870]（0.1 度）
      —— docs/spec/03 §2.4
    - 表情元素量纲 x/y ∈ [-100,100]、weight ∈ [0,100]、size ∈ [-100,100]
      —— docs/research/53 §3.2
"""
from __future__ import annotations

import argparse
import copy
import json
import struct
import sys
from pathlib import Path

HEADER_SIZE = 5
MAX_PAYLOAD = 16 * 1024 * 1024

# 官方消息类型（docs/spec/03 §2.2 的表内容，共 25 项）
OFFICIAL_MSG_TYPES = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B,
}

YAW_RANGE = (-1280, 1280)
PITCH_RANGE = (30, 870)

AVATAR_KEYS = {"leftEye", "rightEye", "mouth"}
FEATURE_KEYS = {"x", "y", "rotation", "weight", "size"}
MOTION_KEYS = {"yawServo", "pitchServo"}
SERVO_KEYS = {"angle", "speed"}
KEYFRAME_KEYS = {
    "leftEye", "rightEye", "mouth",
    "yawServo", "pitchServo",
    "leftRgbColor", "rightRgbColor", "durationMs",
}


class RuleError(Exception):
    """规则被违反（等价于 Swift 侧的 SchemaError / Frame.DecodeError）。"""


# ---------------------------------------------------------------------------
# 帧编解码（等价于 CoreProtocol/Frame.swift）
# ---------------------------------------------------------------------------
def encode_frame(msg_type: int, payload: bytes = b"") -> bytes:
    """远程 WS 帧：`[type:1][length:4 BE][payload]`。"""
    return bytes([msg_type & 0xFF]) + struct.pack(">I", len(payload)) + payload


def decode_frame(data: bytes):
    """解一帧；不合法就抛 RuleError（等价于 Swift 侧的 throwing decode）。"""
    if len(data) < HEADER_SIZE:
        raise RuleError("headerTooShort(byteCount=%d)" % len(data))
    declared = struct.unpack(">I", data[1:5])[0]
    if declared > MAX_PAYLOAD:
        raise RuleError("payloadTooLarge(declared=%d)" % declared)
    available = len(data) - HEADER_SIZE
    if available < declared:
        raise RuleError("payloadTruncated(declared=%d, available=%d)" % (declared, available))
    if data[0] not in OFFICIAL_MSG_TYPES:
        raise RuleError("unknownType(raw=0x%02X)" % data[0])
    return data[0], data[HEADER_SIZE:HEADER_SIZE + declared]


# ---------------------------------------------------------------------------
# JSON 规则（等价于 CoreProtocol/JSONSchema.swift + DanceSequence.swift）
# ---------------------------------------------------------------------------
def is_int(value) -> bool:
    """JSON 数字带小数点即不是 int（与 ArduinoJson `is<int>()` 判定一致）。"""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return False
    return False


def require_int(container: dict, key: str, path: str) -> int:
    if key not in container:
        raise RuleError("missingKey(%s.%s)" % (path, key))
    value = container[key]
    if not is_int(value):
        raise RuleError("notAnInt(%s.%s)" % (path, key))
    return value


def require_str(container: dict, key: str, path: str) -> str:
    if key not in container:
        raise RuleError("missingKey(%s.%s)" % (path, key))
    value = container[key]
    if not isinstance(value, str):
        raise RuleError("notAString(%s.%s)" % (path, key))
    return value


def reject_unknown_keys(container: dict, allowed: set, path: str) -> None:
    for key in container:
        if key not in allowed:
            raise RuleError("unknownKey(%s, %s)" % (path, key))


def validate_feature(container: dict, key: str, path: str) -> None:
    if key not in container:
        raise RuleError("missingKey(%s)" % path)
    element = container[key]
    if not isinstance(element, dict):
        raise RuleError("notAnObject(%s)" % path)
    reject_unknown_keys(element, FEATURE_KEYS, path)

    x = require_int(element, "x", path)
    y = require_int(element, "y", path)
    rotation = require_int(element, "rotation", path)
    weight = require_int(element, "weight", path)
    size = require_int(element, "size", path)

    if not (-100 <= x <= 100):
        raise RuleError("outOfRange(%s.x)" % path)
    if not (-100 <= y <= 100):
        raise RuleError("outOfRange(%s.y)" % path)
    if not (0 <= rotation <= 3600):
        raise RuleError("outOfRange(%s.rotation)" % path)
    if not (0 <= weight <= 100):
        raise RuleError("outOfRange(%s.weight)" % path)
    if not (-100 <= size <= 100):
        raise RuleError("outOfRange(%s.size)" % path)


def validate_servo(container: dict, key: str, path: str, limits) -> None:
    if key not in container:
        raise RuleError("missingKey(%s)" % path)
    servo = container[key]
    if not isinstance(servo, dict):
        raise RuleError("notAnObject(%s)" % path)
    reject_unknown_keys(servo, SERVO_KEYS, path)
    angle = require_int(servo, "angle", path)
    require_int(servo, "speed", path)
    low, high = limits
    if not (low <= angle <= high):
        raise RuleError("outOfRange(%s.angle)" % path)


def validate_control_avatar(payload: dict) -> None:
    reject_unknown_keys(payload, AVATAR_KEYS, "avatar")
    for key in ("leftEye", "rightEye", "mouth"):
        validate_feature(payload, key, "avatar." + key)


def validate_control_motion(payload: dict) -> None:
    reject_unknown_keys(payload, MOTION_KEYS, "motion")
    validate_servo(payload, "yawServo", "motion.yawServo", YAW_RANGE)
    validate_servo(payload, "pitchServo", "motion.pitchServo", PITCH_RANGE)


def validate_rgb_color(value: str, path: str) -> None:
    """颜色必须是 `#RRGGBB`（`#` 是格式的一部分）。"""
    if not value.startswith("#"):
        raise RuleError("outOfRange(%s)" % path)
    text = value[1:]
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise RuleError("outOfRange(%s)" % path)


def validate_dance_sequence(payload) -> list:
    """校验 0x14：顶层必须是数组，每帧 8 个 key 齐全。"""
    if not isinstance(payload, list):
        raise RuleError("notAnArray(found=%s)" % type(payload).__name__)
    if not payload:
        raise RuleError("emptyPayload")
    frames = []
    for index, element in enumerate(payload):
        path = "sequence[%d]" % index
        if not isinstance(element, dict):
            raise RuleError("notAnObject(%s)" % path)
        reject_unknown_keys(element, KEYFRAME_KEYS, path)
        for key in ("leftEye", "rightEye", "mouth"):
            validate_feature(element, key, "%s.%s" % (path, key))
        validate_servo(element, "yawServo", "%s.yawServo" % path, YAW_RANGE)
        validate_servo(element, "pitchServo", "%s.pitchServo" % path, PITCH_RANGE)
        validate_rgb_color(require_str(element, "leftRgbColor", path), "%s.leftRgbColor" % path)
        validate_rgb_color(require_str(element, "rightRgbColor", path), "%s.rightRgbColor" % path)
        duration = require_int(element, "durationMs", path)
        if duration <= 0:
            raise RuleError("outOfRange(%s.durationMs)" % path)
        frames.append(element)
    return frames


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------
VALID_KEYFRAME = {
    "leftEye": {"x": 13, "y": -1, "rotation": 0, "weight": 100, "size": 0},
    "rightEye": {"x": 13, "y": -1, "rotation": 0, "weight": 100, "size": 0},
    "mouth": {"x": 0, "y": 0, "rotation": 0, "weight": 30, "size": 0},
    "yawServo": {"angle": 14, "speed": 800},
    "pitchServo": {"angle": 762, "speed": 800},
    "leftRgbColor": "#BABABA",
    "rightRgbColor": "#CCCCCC",
    "durationMs": 40,
}

VALID_AVATAR = {
    "leftEye": {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
    "rightEye": {"x": 13, "y": -1, "rotation": 1550, "weight": 72, "size": 0},
    "mouth": {"x": 0, "y": 0, "rotation": 0, "weight": 30, "size": 0},
}

VALID_MOTION = {
    "yawServo": {"angle": -60, "speed": 500},
    "pitchServo": {"angle": 220, "speed": 500},
}


def mutate_frame(**changes):
    frame = copy.deepcopy(VALID_KEYFRAME)
    for path, value in changes.items():
        target = frame
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return frame


def frame_cases():
    """帧级用例：返回 (名称, 是否应当通过, 执行函数)。"""
    cases = []

    def ok(name, fn):
        cases.append((name, True, fn))

    def bad(name, fn):
        cases.append((name, False, fn))

    ok("帧/正常往返：encode→decode 等价", lambda: _roundtrip())
    ok("帧/长度按大端写出", lambda: _big_endian())
    ok("帧/空 payload 合法", lambda: decode_frame(encode_frame(0x10)) == (0x10, b""))
    bad("帧/帧头不足 5 字节被拒", lambda: decode_frame(b"\x07\x00\x00"))
    bad("帧/空数据被拒", lambda: decode_frame(b""))
    bad("帧/截断帧（声明 3 字节只给 1 字节）被拒",
        lambda: decode_frame(bytes([0x07, 0, 0, 0, 3, 0x41])))
    bad("帧/未知类型 0x08 被拒", lambda: _unknown_type())
    bad("帧/超大声明长度被拒", lambda: _oversized())
    return cases


def _roundtrip():
    payload = b"hello-stackchan"
    msg_type, decoded = decode_frame(encode_frame(0x07, payload))
    assert msg_type == 0x07, msg_type
    assert decoded == payload, decoded
    return True


def _big_endian():
    payload = b"\x5a" * 0x0102  # 258 字节
    raw = encode_frame(0x14, payload)
    assert raw[0] == 0x14, raw[0]
    assert raw[1:5] == b"\x00\x00\x01\x02", raw[1:5].hex()
    assert len(raw) == HEADER_SIZE + 258
    return True


def _unknown_type():
    # 0x08 不在官方 25 项之内（docs/spec/03 §2.2）
    decode_frame(bytes([0x08, 0, 0, 0, 0]))


def _oversized():
    head = struct.pack(">I", MAX_PAYLOAD + 1)
    decode_frame(bytes([0x07]) + head)


def json_cases():
    """JSON 规则用例。"""
    cases = []

    def ok(name, fn):
        cases.append((name, True, fn))

    def bad(name, fn):
        cases.append((name, False, fn))

    ok("0x14/顶层数组被接受", lambda: validate_dance_sequence([VALID_KEYFRAME]))
    ok("0x14/多帧数组被接受",
        lambda: validate_dance_sequence([VALID_KEYFRAME, VALID_KEYFRAME]))
    ok("0x03/合法表情被接受", lambda: validate_control_avatar(VALID_AVATAR))
    ok("0x04/合法动作被接受", lambda: validate_control_motion(VALID_MOTION))

    bad("0x14/顶层是对象而非数组被拒",
        lambda: validate_dance_sequence(VALID_KEYFRAME))
    bad("0x14/顶层是数字被拒", lambda: validate_dance_sequence(42))
    bad("0x14/空数组被拒", lambda: validate_dance_sequence([]))
    bad("0x14/缺 durationMs 被拒",
        lambda: validate_dance_sequence([_without(VALID_KEYFRAME, "durationMs")]))
    bad("0x14/多出未知 key 被拒",
        lambda: validate_dance_sequence([_with_extra(VALID_KEYFRAME, "surprise", 1)]))
    bad("0x14/x 是小数被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"leftEye.x": 10.5})]))
    bad("0x14/x 是整数值浮点（10.0）被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"leftEye.x": 10.0})]))
    bad("0x14/y 是小数被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"mouth.y": -1.5})]))
    bad("0x14/x 超出 [-100,100] 被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"leftEye.x": 101})]))
    bad("0x14/weight 超出 [0,100] 被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"rightEye.weight": 101})]))
    bad("0x14/yaw 角度越界（1281）被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"yawServo.angle": 1281})]))
    bad("0x14/pitch 角度越界（29）被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"pitchServo.angle": 29})]))
    bad("0x14/颜色格式错被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"leftRgbColor": "BABABA"})]))
    bad("0x14/durationMs 为 0 被拒",
        lambda: validate_dance_sequence([mutate_frame(**{"durationMs": 0})]))
    bad("0x03/x 是小数被拒",
        lambda: validate_control_avatar(_mutate_nested(VALID_AVATAR, "leftEye", "x", 10.5)))
    bad("0x03/缺 rightEye 被拒",
        lambda: validate_control_avatar(_without(VALID_AVATAR, "rightEye")))
    bad("0x04/pitch 角度越界（900）被拒",
        lambda: validate_control_motion(_mutate_nested(VALID_MOTION, "pitchServo", "angle", 900)))
    return cases


def _without(container: dict, key: str) -> dict:
    copy_ = copy.deepcopy(container)
    copy_.pop(key, None)
    return copy_


def _with_extra(container: dict, key: str, value) -> dict:
    copy_ = copy.deepcopy(container)
    copy_[key] = value
    return copy_


def _mutate_nested(container: dict, outer: str, inner: str, value) -> dict:
    copy_ = copy.deepcopy(container)
    copy_[outer][inner] = value
    return copy_


def mutation_cases():
    """变异用例：把一个**已知合法**的关键帧逐字段改坏，规则必须每一次都抓住。

    这一组是"断言不是恒真"的证据 —— 如果规则写成"永远返回 False"，
    合法用例会挂；如果写成"永远返回 True"，变异用例会挂。
    """
    mutations = [
        ("leftEye.x → 小数", {"leftEye.x": 10.5}),
        ("leftEye.y → 小数", {"leftEye.y": 0.5}),
        ("rightEye.rotation → 越界", {"rightEye.rotation": 3601}),
        ("rightEye.rotation → 负值（不要下发负 rotation）", {"rightEye.rotation": -400}),
        ("rightEye.weight → 越界", {"rightEye.weight": -1}),
        ("mouth.size → 越界", {"mouth.size": 101}),
        ("yawServo.angle → 越界", {"yawServo.angle": 5000}),
        ("pitchServo.angle → 越界", {"pitchServo.angle": 0}),
        ("pitchServo.speed → 小数", {"pitchServo.speed": 200.5}),
        ("leftRgbColor → 非法格式", {"leftRgbColor": "#ZZZZZZ"}),
        ("rightRgbColor → 缺 #", {"rightRgbColor": "CCCCCC"}),
        ("durationMs → 负数", {"durationMs": -1}),
    ]
    return [("变异/" + name,
             False,
             (lambda changes: (lambda: validate_dance_sequence([mutate_frame(**changes)])))(changes))
            for name, changes in mutations]


# ---------------------------------------------------------------------------
def run_case(name: str, should_pass: bool, fn) -> tuple[bool, str]:
    try:
        fn()
    except RuleError as error:
        if should_pass:
            return False, "不该被拒，却拒了：%s" % error
        return True, "按规则拒收：%s" % error
    except Exception as error:  # noqa: BLE001
        return False, "执行异常：%r" % error
    if should_pass:
        return True, "按规则接受"
    return False, "不该被接受，却通过了（规则失效）"


def main() -> int:
    parser = argparse.ArgumentParser(description="StackChan 协议规则离线复核")
    parser.add_argument("--keyframes", default=r"D:\AP\AP7000\ai-workspace\stackchan-research\r59\keyframes.json",
                        help="真实 0x14 关键帧语料路径（存在则整批校验）")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover
            pass

    failures: list[str] = []
    accepted = 0
    rejected = 0

    print("=" * 72)
    print("StackChan 协议规则离线复核（Python 重实现，与 Swift 侧同规则）")
    print("-" * 72)

    groups = [
        ("帧编解码", frame_cases()),
        ("JSON 规则", json_cases()),
        ("变异用例（证明规则不是恒真）", mutation_cases()),
    ]
    for group_name, cases in groups:
        print("【%s】" % group_name)
        for name, should_pass, fn in cases:
            ok, detail = run_case(name, should_pass, fn)
            if ok:
                if should_pass:
                    accepted += 1
                else:
                    rejected += 1
                print("  [OK]   %-52s %s" % (name, detail))
            else:
                failures.append("%s —— %s" % (name, detail))
                print("  [FAIL] %-52s %s" % (name, detail))
        print("")

    # 真实语料
    keyframes_path = Path(args.keyframes)
    if keyframes_path.exists():
        try:
            data = json.loads(keyframes_path.read_text(encoding="utf-8"))
            frames = validate_dance_sequence(data)
            accepted += 1
            print("[OK]   真实关键帧语料整批通过：%s（%d 帧）" % (keyframes_path, len(frames)))
            # 再逐帧变异一遍，证明语料里的每一帧都受同一条规则约束
            sample = frames[0]
            broken = copy.deepcopy(sample)
            broken["leftEye"]["x"] = 10.5
            try:
                validate_dance_sequence([broken])
                failures.append("真实语料变异未被拒（规则失效）")
                print("[FAIL] 真实语料变异未被拒")
            except RuleError as error:
                rejected += 1
                print("[OK]   真实语料变异被拒：%s" % error)
        except RuleError as error:
            failures.append("真实语料校验失败：%s" % error)
            print("[FAIL] 真实语料校验失败：%s" % error)
    else:
        print("[SKIP] 未找到真实关键帧语料：%s（跳过该组，不影响退出码）" % keyframes_path)

    print("-" * 72)
    print("接受 %d 条 / 拒收 %d 条" % (accepted, rejected))
    if failures:
        for item in failures:
            print("[FAIL] %s" % item)
        print("共 %d 项失败" % len(failures))
        return 1
    if rejected == 0:
        print("[FAIL] 没有任何用例被拒收 —— 断言可能是恒真的，规则没被验证到")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
