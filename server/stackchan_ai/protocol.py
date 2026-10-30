# -*- coding: utf-8 -*-
"""protocol —— StackChan 帧协议：编解码 + 消息类型 + 0x14 校验。

本模块是 **协议替身** 的地基，逻辑与已交付的 `tools/stackchan_server.py`
（第 123~412 行）逐条对齐，但**代码在本目录内独立可跑**（不 import tools/），
以便将来把 Python 实现换成官方 Go 实现时，协议层不变。

协议事实（出处为官方固件 / 官方云源码，行号见 tools/stackchan_server.py 头注释）：

    帧格式  [Type(1)][Length(4 BE)][Payload]
        固件  hal_ws_avatar.cpp:549-561 sendRemotePacket()
        固件  hal_ws_avatar.cpp:206-239  读包：data[0]=type, payload=data[5:]
        云    server/internal/web_socket/web_socket.go:308-323 parseBinaryMessage()

    消息类型（固件 hal_ws_avatar.cpp:49-72）
        0x01 Opus / 0x02 Jpeg / 0x03 ControlAvatar / 0x04 ControlMotion
        0x07 TextMessage / 0x10 HeartbeatPing / 0x11 Pong / 0x14 DanceSequence
        ⚠ 固件**没有** 0x15 GetAvatarPosture ⇒ 不发 0x15 期待回复

    12 字节 MAC 前缀（只在 payload 内，不在帧头）
        App 拼装  app/lib/view/home/avatar.dart:720 (avatar) / :727 (motion)
        云剥除    web_socket.go:523 Opus / :537 Jpeg / :553 ControlAvatar,ControlMotion
                  / :569 TextMessage / :588 RequestCall
        ⭐ **只有这 6 类带前缀**；0x14 Dance 不带也不剥
           (web_socket.go:740-746 原样转发；官方 App dance.dart:191-197 也不加前缀)

    0x14 payload 顶层必须是 JSON 数组
        固件  stackchan/json/json_helper.cpp:192-195（不是数组直接 return）
        App   app/lib/view/home/dance.dart:137 / :193  jsonEncode([...])

    0x14 每帧 8 个 key
        固件  json_helper.cpp:201-224
        App   app/lib/model/dance_list.dart:119-130 DanceData.toJson()

    舵机子对象 {"angle":Int,"speed":Int}，单位 0.1 度
        固件  json_helper.cpp:166-176 parse_servo()
        限位  hal_servo.cpp:340 yaw (-1280, 1280)；:349 pitch (30, 870)

    表情子对象 {"x":Int,"y":Int,"rotation":Int,"weight":Int,"size":Int}
        固件  json_helper.cpp:145-164 parse_feature()
        ⚠ x 与 y 必须**同时是 int** 才 setPosition（json_helper.cpp:18）

    眼睛 weight 越大越睁开（eyes.cpp:71-78）；嘴 weight 越大越张开（mouth.cpp:48-58）
"""

from __future__ import annotations

import json
import struct
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ── MsgType ────────────────────────────────────────────────────────────────
OPUS = 0x01
JPEG = 0x02
CONTROL_AVATAR = 0x03
CONTROL_MOTION = 0x04
ON_CAMERA = 0x05
OFF_CAMERA = 0x06
TEXT_MESSAGE = 0x07
REQUEST_CALL = 0x09
REFUSE_CALL = 0x0A
AGREE_CALL = 0x0B
HANGUP_CALL = 0x0C
UPDATE_DEVICE_NAME = 0x0D
GET_DEVICE_NAME = 0x0E
PING = 0x10
PONG = 0x11
ON_PHONE_SCREEN = 0x12
OFF_PHONE_SCREEN = 0x13
DANCE = 0x14
GET_AVATAR_POSTURE = 0x15
DEVICE_OFFLINE = 0x16
DEVICE_ONLINE = 0x17
ON_AUDIO = 0x18
OFF_AUDIO = 0x19
AIMED_TAKE_PHOTO = 0x1A
APP_LAN_ADDRESS = 0x1B

MSG_NAMES: Dict[int, str] = {
    OPUS: "opus", JPEG: "jpeg", CONTROL_AVATAR: "controlAvatar",
    CONTROL_MOTION: "controlMotion", ON_CAMERA: "onCamera",
    OFF_CAMERA: "offCamera", TEXT_MESSAGE: "textMessage",
    REQUEST_CALL: "requestCall", REFUSE_CALL: "declineCall",
    AGREE_CALL: "acceptCall", HANGUP_CALL: "endCall",
    UPDATE_DEVICE_NAME: "setDeviceName", GET_DEVICE_NAME: "getDeviceName",
    PING: "ping", PONG: "pong", ON_PHONE_SCREEN: "phoneScreenOn",
    OFF_PHONE_SCREEN: "phoneScreenOff", DANCE: "dance",
    GET_AVATAR_POSTURE: "getAvatarPosture",
    DEVICE_OFFLINE: "deviceOffline", DEVICE_ONLINE: "deviceOnline",
    ON_AUDIO: "audioOn", OFF_AUDIO: "audioOff",
    AIMED_TAKE_PHOTO: "aimedTakePhoto", APP_LAN_ADDRESS: "appLanAddress",
}

#: 官方云只对这几类剥 12 字节 MAC 前缀（web_socket.go:523/537/553/569/588）。
#: ⭐ 0x14 不在列表里（web_socket.go:740-746 原样转发）。
MAC_PREFIXED_TYPES = frozenset(
    {OPUS, JPEG, CONTROL_AVATAR, CONTROL_MOTION, TEXT_MESSAGE, REQUEST_CALL}
)
MAC_LEN = 12

#: 舵机限位，线上单位 0.1 度（hal_servo.cpp:340 / :349）
YAW_MIN_RAW, YAW_MAX_RAW = -1280, 1280
PITCH_MIN_RAW, PITCH_MAX_RAW = 30, 870

#: 0x14 关键帧的 8 个 key（json_helper.cpp:201-224 / dance_list.dart:119-130）
DANCE_KEYS: Tuple[str, ...] = (
    "leftEye", "rightEye", "mouth",
    "yawServo", "pitchServo",
    "leftRgbColor", "rightRgbColor", "durationMs",
)
FEATURE_KEYS: Tuple[str, ...] = ("x", "y", "rotation", "weight", "size")
SERVO_KEYS: Tuple[str, ...] = ("angle", "speed")

#: 官方情绪表里的眼睛 weight 基线（eyes.cpp:102-123）
EMOTION_EYE_WEIGHT: Dict[str, int] = {
    "Neutral": 100, "Happy": 72, "Angry": 70,
    "Sad": 70, "Doubt": 75, "Sleepy": 35,
}

#: 嘴的几何常量（mouth.cpp:15-18）
MOUTH_MIN_SIZE = (90, 6)
MOUTH_MAX_SIZE = (60, 50)
MOUTH_MIN_RADIUS = 0
MOUTH_MAX_RADIUS = 16


def is_int(value: Any) -> bool:
    """固件判 ArduinoJson ``is<int>()``；Python 侧 bool 是 int 子类，必须排除。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _map_range(value: float, in_min: float, in_max: float,
               out_min: float, out_max: float) -> float:
    if in_max == in_min:
        return out_min
    ratio = (float(value) - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)


# ── 帧编解码 ───────────────────────────────────────────────────────────────
def encode_frame(msg_type: int, payload: bytes = b"") -> bytes:
    """``[Type(1)][Length(4 BE)][Payload]``（hal_ws_avatar.cpp:549-561 的逆操作）。"""
    return bytes([msg_type & 0xFF]) + struct.pack(">I", len(payload)) + payload


def decode_frame(data: bytes) -> Optional[Tuple[int, bytes]]:
    """返回 ``(type, payload)``；长度不合法返回 ``None``（web_socket.go:308-323）。"""
    if not data or len(data) < 5:
        return None
    msg_type = data[0]
    (length,) = struct.unpack(">I", data[1:5])
    if len(data) < 5 + length:
        return None
    return msg_type, data[5:5 + length]


def frame_length(payload: bytes) -> int:
    """帧总字节数 = 5 + len(payload)。"""
    return 5 + len(payload)


# ── MAC 前缀与 payload 构造 ────────────────────────────────────────────────
def mac_to_bytes(mac: str) -> bytes:
    """官方 App 的 deviceMac 是 12 字符十六进制串（无冒号）的 ASCII 形式。"""
    return mac.replace(":", "").replace("-", "").lower().encode("ascii")


def normalize_mac(mac: str) -> str:
    """固件 local_network_protocol.h:20-29 normalizeMac 的同义实现。

    去掉 ':' / '-'，校验是 12 个十六进制字符并转小写；不合法返回 ""。
    """
    out: List[str] = []
    for ch in mac:
        if ch in ":-":
            continue
        if ch not in "0123456789abcdefABCDEF":
            return ""
        out.append(ch.lower())
    return "".join(out) if len(out) == 12 else ""


def build_control_payload(mac: str, obj: Any) -> bytes:
    """App → 云 的控制帧 payload：MAC(12B ASCII) + JSON。

    对应官方 App app/lib/view/home/avatar.dart:720 / :727。
    只有 MAC_PREFIXED_TYPES 里的 6 类才允许这样拼。
    """
    return mac_to_bytes(mac) + json.dumps(obj, separators=(",", ":")).encode("utf-8")


def build_text_payload(mac: str, text: str) -> bytes:
    """App → 云 的 0x07 TextMessage payload：MAC(12B ASCII) + 纯文本 UTF-8。

    官方云对 TextMessage 剥前缀（web_socket.go:569），剥完剩下的按纯文本处理
    （tools/protocol_sim.py:328-332 的设备侧同样按纯文本解码）。
    """
    return mac_to_bytes(mac) + text.encode("utf-8")


def build_dance_payload(sequence: Sequence[Dict[str, Any]]) -> bytes:
    """0x14 payload：顶层 JSON 数组，**不带** 12 字节 MAC 前缀。

    对应官方 App app/lib/view/home/dance.dart:137 / :193。
    """
    return json.dumps(list(sequence), ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def split_mac_prefix(msg_type: int, payload: bytes) -> Tuple[Optional[str], bytes]:
    """按类型决定是否剥 12 字节 MAC 前缀，返回 ``(mac|None, body)``。

    剥除集合严格等于官方云的 6 类；0x14 不剥。

    与官方云的一处**刻意差异**（tools/stackchan_server.py:265-281 同款）：
    官方云是无条件切 ``payload[:12]``；这里只在确认前 12 字节确实是 MAC 时才剥 ——
    JSON payload 一定以 '{' 开头，不是十六进制字符，判定无歧义；
    这样 MAC-less 的控制帧能原样透传给固件，不会被切坏。
    """
    if msg_type in MAC_PREFIXED_TYPES and len(payload) >= MAC_LEN:
        prefix = payload[:MAC_LEN]
        mac = normalize_mac(prefix.decode("ascii", "ignore"))
        if mac:
            return mac, payload[MAC_LEN:]
    return None, payload


def parse_json_body(body: bytes) -> Any:
    """尽量把 body 解析成 JSON；失败返回 ``None``。"""
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def parse_text_body(body: bytes) -> str:
    """把 0x07 的 body 解析成一句用户文本。

    官方 App 的 0x07 body 具体形态**未取证**；官方云剥完 MAC 后按文本转发
    （web_socket.go:569 + tools/protocol_sim.py:328-332），所以这里以纯文本为主，
    同时容忍 JSON 包装（取常见文本字段）。
    """
    raw = body.decode("utf-8", "ignore").strip()
    if not raw:
        return ""
    if raw[0] in "{[":
        obj = parse_json_body(body)
        if isinstance(obj, dict):
            for key in ("msg", "text", "content", "message", "data"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""
    return raw


# ── 0x14 / 0x03 校验 ──────────────────────────────────────────────────────
def validate_dance_sequence(sequence: Any) -> List[str]:
    """校验 0x14 关键帧数组，返回错误列表（空列表 = 合法）。

    规则全部来自固件：
      顶层必须是数组            json_helper.cpp:192-195
      每帧 8 个 key 齐全        json_helper.cpp:201-224
      舵机 angle/speed 是 int   json_helper.cpp:166-176
      表情 5 个字段是 int       json_helper.cpp:145-164
      yaw  angle ∈ [-1280,1280] hal_servo.cpp:340
      pitch angle ∈ [30,870]    hal_servo.cpp:349
    """
    errors: List[str] = []
    if not isinstance(sequence, list):
        errors.append(
            "top level payload must be a JSON array "
            "(firmware json_helper.cpp:192-195 rejects objects)")
        return errors
    if not sequence:
        errors.append("keyframe array is empty")
        return errors

    for index, frame in enumerate(sequence):
        tag = "frame[%d]" % index
        if not isinstance(frame, dict):
            errors.append("%s is not a JSON object (got %s)"
                          % (tag, type(frame).__name__))
            continue
        for key in DANCE_KEYS:
            if key not in frame:
                errors.append("%s missing key %s (firmware json_helper.cpp:201-224)"
                              % (tag, key))
        for feature_key in ("leftEye", "rightEye", "mouth"):
            feature = frame.get(feature_key)
            if feature is None:
                continue
            if not isinstance(feature, dict):
                errors.append("%s.%s is not a JSON object" % (tag, feature_key))
                continue
            for field in FEATURE_KEYS:
                if field not in feature:
                    errors.append("%s.%s missing field %s "
                                  "(firmware json_helper.cpp:145-164)"
                                  % (tag, feature_key, field))
                    continue
                if not is_int(feature[field]):
                    errors.append(
                        "%s.%s.%s must be an int (firmware checks is<int>()), got %r"
                        % (tag, feature_key, field, feature[field]))
        for servo_key, low, high in (
                ("yawServo", YAW_MIN_RAW, YAW_MAX_RAW),
                ("pitchServo", PITCH_MIN_RAW, PITCH_MAX_RAW)):
            servo = frame.get(servo_key)
            if servo is None:
                continue
            if not isinstance(servo, dict):
                errors.append("%s.%s is not a JSON object" % (tag, servo_key))
                continue
            for field in SERVO_KEYS:
                if field not in servo:
                    errors.append("%s.%s missing field %s "
                                  "(firmware json_helper.cpp:166-176)"
                                  % (tag, servo_key, field))
                    continue
                if not is_int(servo[field]):
                    errors.append(
                        "%s.%s.%s must be an int (firmware checks is<int>()), got %r"
                        % (tag, servo_key, field, servo[field]))
            angle = servo.get("angle")
            if is_int(angle) and not (low <= angle <= high):
                errors.append(
                    "%s.%s.angle=%d out of firmware limit [%d, %d] (0.1 degree)"
                    % (tag, servo_key, angle, low, high))
        if "durationMs" in frame and not is_int(frame["durationMs"]):
            errors.append("%s.durationMs must be an int, got %r"
                          % (tag, frame["durationMs"]))
    return errors


def validate_avatar_object(obj: Any) -> List[str]:
    """校验 0x03 表情对象（固件 json_helper.cpp:16-39 只认 3 组 × 5 字段）。"""
    errors: List[str] = []
    if not isinstance(obj, dict):
        return ["avatar payload is not a JSON object"]
    for feature_key in ("leftEye", "rightEye", "mouth"):
        feature = obj.get(feature_key)
        if feature is None:
            errors.append("missing %s (firmware json_helper.cpp:54-67)" % feature_key)
            continue
        if not isinstance(feature, dict):
            errors.append("%s is not a JSON object" % feature_key)
            continue
        for field in FEATURE_KEYS:
            if field not in feature:
                errors.append("%s missing field %s" % (feature_key, field))
            elif not is_int(feature[field]):
                errors.append("%s.%s must be an int (firmware checks is<int>()), got %r"
                              % (feature_key, field, feature[field]))
    return errors


# ── 表情映射模型（复刻固件公式，供自检断言） ───────────────────────────────
def eye_openness(weight: int) -> float:
    """眼睛睁开程度 0.0~1.0，越大越睁开。复刻 eyes.cpp:75。"""
    return _map_range(weight, 0, 100, 0.0, 1.0)


def eye_lid_offset(weight: int, eyelid_height: int = 100) -> int:
    """复刻 eyes.cpp:75，保留整数语义。"""
    return -int(_map_range(weight, 0, 100, 0, eyelid_height))


def mouth_openness(weight: int) -> float:
    """嘴张开程度 0.0~1.0，越大越张开。复刻 mouth.cpp:52-54 的 map_range。"""
    height = _map_range(weight, 0, 100, MOUTH_MIN_SIZE[1], MOUTH_MAX_SIZE[1])
    return (height - MOUTH_MIN_SIZE[1]) / float(
        MOUTH_MAX_SIZE[1] - MOUTH_MIN_SIZE[1])


# ── 小工具 ─────────────────────────────────────────────────────────────────
def sample_keyframe(weight: int = 100, yaw: int = 0, pitch: int = 450,
                    duration: int = 800) -> Dict[str, Any]:
    """构造一帧合法的 0x14 关键帧（结构见 dance_list.dart:119-130）。"""

    def feature(w: int) -> Dict[str, int]:
        return {"x": 0, "y": 0, "rotation": 0, "weight": w, "size": 0}

    return {
        "leftEye": feature(weight),
        "rightEye": feature(weight),
        "mouth": feature(0),
        "yawServo": {"angle": yaw, "speed": 500},
        "pitchServo": {"angle": pitch, "speed": 500},
        "leftRgbColor": "#000000",
        "rightRgbColor": "#000000",
        "durationMs": duration,
    }


def frames_summary(sequence: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """统计关键帧序列：帧数 / 总时长 / yaw·pitch 范围（设备侧模拟器用）。"""
    kfs = list(sequence)
    yaw_values: List[int] = []
    pitch_values: List[int] = []
    total_ms = 0
    for frame in kfs:
        yaw = frame.get("yawServo", {})
        pitch = frame.get("pitchServo", {})
        if isinstance(yaw, dict) and is_int(yaw.get("angle")):
            yaw_values.append(int(yaw["angle"]))
        if isinstance(pitch, dict) and is_int(pitch.get("angle")):
            pitch_values.append(int(pitch["angle"]))
        if is_int(frame.get("durationMs")):
            total_ms += int(frame["durationMs"])
    return {
        "frameCount": len(kfs),
        "durationMsTotal": total_ms,
        "durationSecTotal": round(total_ms / 1000.0, 3),
        "yawRange": [min(yaw_values), max(yaw_values)] if yaw_values else [],
        "pitchRange": [min(pitch_values), max(pitch_values)] if pitch_values else [],
    }


__all__ = [
    "OPUS", "JPEG", "CONTROL_AVATAR", "CONTROL_MOTION", "TEXT_MESSAGE",
    "PING", "PONG", "DANCE", "DEVICE_ONLINE", "DEVICE_OFFLINE",
    "MSG_NAMES", "MAC_PREFIXED_TYPES", "MAC_LEN",
    "YAW_MIN_RAW", "YAW_MAX_RAW", "PITCH_MIN_RAW", "PITCH_MAX_RAW",
    "DANCE_KEYS", "FEATURE_KEYS", "SERVO_KEYS",
    "EMOTION_EYE_WEIGHT", "MOUTH_MIN_SIZE", "MOUTH_MAX_SIZE",
    "is_int", "encode_frame", "decode_frame", "frame_length",
    "mac_to_bytes", "normalize_mac", "build_control_payload", "build_text_payload",
    "build_dance_payload", "split_mac_prefix", "parse_json_body", "parse_text_body",
    "validate_dance_sequence", "validate_avatar_object",
    "eye_openness", "eye_lid_offset", "mouth_openness",
    "sample_keyframe", "frames_summary",
]
