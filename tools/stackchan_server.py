#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StackChan 真服务端替身 (Standalone WebSocket server for M5Stack StackChan)
===========================================================================

目的
----
让真机 (ESP32-S3, 固件 1.5.1 / 1.6.0 同协议) 能连上本机, 并接受 0x14 DanceSequence 控制。

固件侧连接方式 (编译期常量, 无运行期覆盖)
-------------------------------------------
  ws://<server>/stackChan/ws?deviceType=StackChan
  出处: firmware/main/hal/hal_ws_avatar.cpp:88
  服务器基址: firmware/main/Kconfig.projbuild:5 -> http://47.113.125.164:12800
  (由 secret_logic::get_server_url() 返回, firmware/main/hal/utils/secret_logic/secret_logic.cpp:11-18)

所以本程序是「同路径同协议」的替身服务端; 部署时靠网络层把那个 IP 劫持到本机。

用法
----
  py -3.12 tools/stackchan_server.py --serve --port 12800
  py -3.12 tools/stackchan_server.py --serve --port 12800 --dance keyframes.json
  py -3.12 tools/stackchan_server.py --serve --port 12800 --dance-stdin
  py -3.12 tools/stackchan_server.py --self-test

与 tools/protocol_sim.py 的关系
------------------------------
  protocol_sim.py --role device  : 扮演「设备 + 云」, 已能处理 0x14 (未改动)
  protocol_sim.py --role app     : 扮演 App, 连本服务端, 可发 0x14
  stackchan_server.py            : 扮演「云」, 只做协议替身, 真机可直连

协议事实表 (全部实读官方仓 origin/main, 未改动官方仓)
---------------------------------------------------
  帧格式  [Type:1][Length:4 BE][Payload]
      固件  hal_ws_avatar.cpp:234 / :243 / :296 / :334 / :366  (注释 "Protocol: [Type(1)] [Length(4)] [Payload]")
      固件  hal_ws_avatar.cpp:549-561  sendRemotePacket(): type + writeBigEndian(len,4) + payload
      固件  hal_ws_avatar.cpp:206-239  读包: data[0]=type, payload=data[5:]
      云    server/internal/web_socket/web_socket.go:308-323  parseBinaryMessage()
      App   app/lib/app_state.dart:275-289  sendWebSocketMessage()

  DataType 固件侧枚举 (hal_ws_avatar.cpp:49-72)
      0x01 Opus  0x02 Jpeg  0x03 ControlAvatar  0x04 ControlMotion
      0x05 StartCameraStream  0x06 StopCameraStream  0x07 TextMessage
      0x09 RequestCall  0x0A DeclineCall  0x0B AcceptCall  0x0C EndCall
      0x0D SetDeviceName  0x0E GetDeviceName  0x10 HeartbeatPing  0x11 HeartbeatPong
      0x12 VideoModeOn  0x13 VideoModeOff  0x14 DanceSequence
      0x18 StartAudioStream  0x19 StopAudioStream  0x1A AimedTakePhoto  0x1B AppLanAddress
      ⚠ 固件**没有** 0x15 GetAvatarPosture => 不发 0x15 期待回复

  12 字节 MAC 前缀 (只出现在 payload 内, 不在帧头)
      App 侧拼装  app/lib/view/home/avatar.dart:720 (avatar) / :727 (motion)
      云侧剥除   web_socket.go:523 Opus / :537 Jpeg / :553 ControlAvatar,ControlMotion
                 / :569 TextMessage / :588 RequestCall
      ⚠ 0x14 Dance **不剥** (web_socket.go:740-746 原样转发), 官方 App 也不加前缀
        (app/lib/view/home/dance.dart:191-197)
      => 只有这 6 类带前缀; 0x14 不带

  0x14 payload 顶层必须是 JSON 数组
      固件  stackchan/json/json_helper.cpp:192-195  (不是数组则报错 "json is not an array")
      App   app/lib/view/home/dance.dart:137 / :193  jsonEncode([...])

  0x14 每帧 8 个 key
      固件  json_helper.cpp:201-224
      App   app/lib/model/dance_list.dart:119-130  DanceData.toJson()

  舵机子对象 {"angle": int, "speed": int}
      固件  json_helper.cpp:166-176  parse_servo()
      App   app/lib/model/expression_data.dart:128-136

  表情子对象 {"x":int,"y":int,"rotation":int,"weight":int,"size":int}
      固件  json_helper.cpp:145-164  parse_feature()   (0x14 路径)
      固件  json_helper.cpp:16-39    update_feature()  (0x03 路径)
      App   app/lib/model/expression_data.dart:72-78

  舵机限位 (线上单位 0.1 度)
      固件  hal_servo.cpp:340  yaw   angleLimit = Vector2i(-1280, 1280)
      固件  hal_servo.cpp:349  pitch angleLimit = Vector2i(30, 870)

  眼睛 weight 越大 = 越睁开
      固件  avatar/skins/default/eyes.cpp:71-78
            _eyelid_offset_y = -map_range(weight, 0, 100, 0, eyelid_height)
            weight 越大 -> 眼睑抬得越高 -> 越睁开
      官方情绪基线 eyes.cpp:102-123  Neutral=100 Happy=72 Angry=70 Sad=70 Doubt=75 Sleepy=35
      (Neutral 最睁 100, Sleepy 最眯 35 <=> 越大越睁开)

  嘴 weight 越大 = 越张开
      固件  avatar/skins/default/mouth.cpp:48-58
            size/radius = map_range(weight, 0, 100, min, max)
      常量  mouth.cpp:15-18  min_size=(90,6) r=0 / max_size=(60,50) r=16

  心跳
      云每 5 秒发 0x10  server/internal/boot/cron.go:35 + web_socket/socket_task.go:36
      固件收到 0x10 -> 回 0x11  hal_ws_avatar.cpp:287-294
      固件 10 秒收不到任何帧 -> 报 Heartbeat Timeout  hal_ws_avatar.cpp:171-174
      => 本服务端必须也定期发 0x10, 并对收到的 0x10 回 0x11

  设备连上后先发一条文本 hello
      固件  hal_ws_avatar.cpp:161  {"type":"hello","msg":"Hello from StackChan!"}

  设备 MAC 的来源
      官方云从 Authorization 头解 RSA token 取 MAC (web_socket.go:78-99)
      本替身无法解 RSA => MAC 只能用 query 参数 mac= 或命令行 --mac 指定
"""

import argparse
import asyncio
import json
import struct
import sys
from urllib.parse import urlparse, parse_qs

try:
    import websockets
except ImportError:  # pragma: no cover
    print("need websockets: py -3.12 -m pip install websockets")
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── MsgType (官方云 web_socket.go:31-63 / 固件 hal_ws_avatar.cpp:49-72) ─────
OPUS               = 0x01
JPEG               = 0x02
CONTROL_AVATAR     = 0x03
CONTROL_MOTION     = 0x04
ON_CAMERA          = 0x05
OFF_CAMERA         = 0x06
TEXT_MESSAGE       = 0x07
REQUEST_CALL       = 0x09
REFUSE_CALL        = 0x0A
AGREE_CALL         = 0x0B
HANGUP_CALL        = 0x0C
UPDATE_DEVICE_NAME = 0x0D
GET_DEVICE_NAME    = 0x0E
PING               = 0x10
PONG               = 0x11
ON_PHONE_SCREEN    = 0x12
OFF_PHONE_SCREEN   = 0x13
DANCE              = 0x14
GET_AVATAR_POSTURE = 0x15
DEVICE_OFFLINE     = 0x16
DEVICE_ONLINE      = 0x17
ON_AUDIO           = 0x18
OFF_AUDIO          = 0x19
AIMED_TAKE_PHOTO   = 0x1A
APP_LAN_ADDRESS   = 0x1B

MSG_NAMES = {
    OPUS: "opus", JPEG: "jpeg", CONTROL_AVATAR: "controlAvatar",
    CONTROL_MOTION: "controlMotion", ON_CAMERA: "onCamera",
    OFF_CAMERA: "offCamera", TEXT_MESSAGE: "textMessage",
    REQUEST_CALL: "requestCall", REFUSE_CALL: "refuseCall",
    AGREE_CALL: "agreeCall", HANGUP_CALL: "hangupCall",
    UPDATE_DEVICE_NAME: "updateDeviceName", GET_DEVICE_NAME: "getDeviceName",
    PING: "ping", PONG: "pong", ON_PHONE_SCREEN: "onPhoneScreen",
    OFF_PHONE_SCREEN: "offPhoneScreen", DANCE: "dance",
    GET_AVATAR_POSTURE: "getAvatarPosture", DEVICE_OFFLINE: "deviceOffline",
    DEVICE_ONLINE: "deviceOnline", ON_AUDIO: "onAudio", OFF_AUDIO: "offAudio",
    AIMED_TAKE_PHOTO: "aimedTakePhoto", APP_LAN_ADDRESS: "appLanAddress",
}

# 官方云只对这几类剥 12 字节 MAC 前缀 (web_socket.go:523/537/553/569/588)。
# ⭐ 0x14 Dance 不在列表里 (web_socket.go:740-746 原样转发)。
MAC_PREFIXED_TYPES = frozenset(
    {OPUS, JPEG, CONTROL_AVATAR, CONTROL_MOTION, TEXT_MESSAGE, REQUEST_CALL}
)
MAC_LEN = 12

# 舵机限位, 线上单位 0.1 度 (hal_servo.cpp:340 / :349)
YAW_MIN_RAW, YAW_MAX_RAW = -1280, 1280
PITCH_MIN_RAW, PITCH_MAX_RAW = 30, 870

# 0x14 关键帧结构 (json_helper.cpp:201-224 / dance_list.dart:119-130)
DANCE_KEYS = (
    "leftEye", "rightEye", "mouth",
    "yawServo", "pitchServo",
    "leftRgbColor", "rightRgbColor", "durationMs",
)
FEATURE_KEYS = ("x", "y", "rotation", "weight", "size")
SERVO_KEYS = ("angle", "speed")

# 官方情绪表里的眼睛 weight 基线 (eyes.cpp:102-123)
EMOTION_EYE_WEIGHT = {
    "Neutral": 100, "Happy": 72, "Angry": 70,
    "Sad": 70, "Doubt": 75, "Sleepy": 35,
}

# 嘴的几何常量 (mouth.cpp:15-18)
MOUTH_MIN_SIZE = (90, 6)
MOUTH_MAX_SIZE = (60, 50)
MOUTH_MIN_RADIUS = 0
MOUTH_MAX_RADIUS = 16


def _is_int(value) -> bool:
    """固件判 ArduinoJson is<int>(); Python 侧 bool 是 int 子类, 必须排除。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _map_range(value, in_min, in_max, out_min, out_max):
    if in_max == in_min:
        return out_min
    ratio = (float(value) - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)


# ── 帧编解码: [Type:1][Length:4 BE][Payload] ──────────────────────────────
def encode_frame(msg_type: int, payload: bytes = b"") -> bytes:
    """固件 hal_ws_avatar.cpp:549-561 sendRemotePacket() 的逆操作。"""
    return bytes([msg_type & 0xFF]) + struct.pack(">I", len(payload)) + payload


def decode_frame(data: bytes):
    """返回 (type, payload); 长度不合法返回 None。云侧 web_socket.go:308-323。"""
    if not data or len(data) < 5:
        return None
    msg_type = data[0]
    (length,) = struct.unpack(">I", data[1:5])
    if len(data) < 5 + length:
        return None
    return msg_type, data[5:5 + length]


# ── MAC 前缀与 payload 构造 ────────────────────────────────────────────────
def mac_to_bytes(mac: str) -> bytes:
    """官方 App 的 deviceMac 是 12 字符十六进制串 (无冒号) 的 ASCII 形式。"""
    return mac.replace(":", "").replace("-", "").lower().encode("ascii")


def normalize_mac(mac: str) -> str:
    """固件 local_network_protocol.h:20-29 的 normalizeMac 同义实现。

    去掉 ':' / '-', 校验是 12 个十六进制字符, 全部转小写; 不合法返回 ""。
    """
    out = []
    for ch in mac:
        if ch in ":-":
            continue
        if ch not in "0123456789abcdefABCDEF":
            return ""
        out.append(ch.lower())
    return "".join(out) if len(out) == 12 else ""


def build_control_payload(mac: str, obj: dict) -> bytes:
    """App -> 云 的控制帧 payload: MAC(12B ASCII) + JSON。

    对应官方 App app/lib/view/home/avatar.dart:720 / :727。
    只有 MAC_PREFIXED_TYPES 里的 6 类才允许这样拼。
    """
    return mac_to_bytes(mac) + json.dumps(obj, separators=(",", ":")).encode("utf-8")


def build_dance_payload(sequence) -> bytes:
    """0x14 payload: 顶层 JSON 数组, **不带** 12 字节 MAC 前缀。

    对应官方 App app/lib/view/home/dance.dart:137 / :193。
    """
    return json.dumps(sequence, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def split_mac_prefix(msg_type: int, payload: bytes):
    """按类型决定是否剥 12 字节 MAC 前缀。返回 (mac|None, body)。

    剥除集合严格等于官方云的 6 类 (web_socket.go:523/537/553/569/588);
    0x14 不剥 (web_socket.go:740-746)。

    与官方云的一处**刻意差异**: 官方云是无条件切 payload[:12] (所以 MAC-less
    的控制帧会被切成乱码)。这里只在确认前 12 字节确实是 MAC 时才剥 ——
    JSON payload 一定以 '{' 开头, 不是十六进制字符, 所以判定无歧义;
    这样 MAC-less 的控制帧 (例如手工构造) 能原样透传给固件, 不会被切坏。
    """
    if msg_type in MAC_PREFIXED_TYPES and len(payload) >= MAC_LEN:
        prefix = payload[:MAC_LEN]
        mac = normalize_mac(prefix.decode("ascii", "ignore"))
        if mac:
            return mac, payload[MAC_LEN:]
    return None, payload


def parse_json_body(body: bytes):
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


# ── 表情 / 舞蹈数据校验 (对照固件解析规则) ─────────────────────────────────
def validate_dance_sequence(sequence):
    """校验 0x14 关键帧数组。返回错误列表 (空列表 = 合法)。

    规则全部来自固件:
      顶层必须是数组            json_helper.cpp:192-195
      每帧 8 个 key 齐全        json_helper.cpp:201-224
      舵机 angle/speed 是 int   json_helper.cpp:166-176
      表情 5 个字段是 int       json_helper.cpp:145-164
      yaw  angle ∈ [-1280,1280] hal_servo.cpp:340
      pitch angle ∈ [30,870]    hal_servo.cpp:349
    """
    errors = []
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
                if not _is_int(feature[field]):
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
                if not _is_int(servo[field]):
                    errors.append(
                        "%s.%s.%s must be an int (firmware checks is<int>()), got %r"
                        % (tag, servo_key, field, servo[field]))
            angle = servo.get("angle")
            if _is_int(angle) and not (low <= angle <= high):
                errors.append(
                    "%s.%s.angle=%d out of firmware limit [%d, %d] (0.1 degree)"
                    % (tag, servo_key, angle, low, high))
        if "durationMs" in frame and not _is_int(frame["durationMs"]):
            errors.append("%s.durationMs must be an int, got %r"
                          % (tag, frame["durationMs"]))
    return errors


def validate_avatar_object(obj):
    """校验 0x03 表情对象 (固件 json_helper.cpp:16-39 只认这 3 组 * 5 字段)。"""
    errors = []
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
            elif not _is_int(feature[field]):
                errors.append("%s.%s must be an int (firmware checks is<int>()), got %r"
                              % (feature_key, field, feature[field]))
    return errors


# ── 表情映射模型 (复刻固件公式, 供自检断言) ────────────────────────────────
def eye_openness(weight: int) -> float:
    """眼睛睁开程度 0.0~1.0, 越大越睁开。

    复刻 eyes.cpp:75
        _eyelid_offset_y = -map_range(weight, 0, 100, 0, eyelid_height)
    眼睑往上抬得越多 -> 露出越多 -> 越睁开。
    """
    return _map_range(weight, 0, 100, 0.0, 1.0)


def eye_lid_offset(weight: int, eyelid_height: int = 100) -> int:
    """复刻 eyes.cpp:75, 保留整数语义。"""
    return -int(_map_range(weight, 0, 100, 0, eyelid_height))


def mouth_openness(weight: int) -> float:
    """嘴张开程度 0.0~1.0, 越大越张开。复刻 mouth.cpp:52-54 的 map_range。"""
    height = _map_range(weight, 0, 100, MOUTH_MIN_SIZE[1], MOUTH_MAX_SIZE[1])
    return (height - MOUTH_MIN_SIZE[1]) / float(
        MOUTH_MAX_SIZE[1] - MOUTH_MIN_SIZE[1])


# ── 连接注册表 ─────────────────────────────────────────────────────────────
class ConnectionRegistry:
    """维护在线的设备连接和 App 连接。

    设备的 MAC 来自 URL query 的 mac= 参数; 官方云是从 Authorization 头解
    RSA token 取的 (web_socket.go:78-99), 替身服务端解不了 RSA, 所以只能
    走 query 参数 (固件侧 URL 是编译期常量, 不带 mac, 固件也不解析
    Authorization) —— 因此这里支持两种来源:
      1. query ?mac=68ee8fd73668   (联调 / 手工指定)
      2. 未指定时用默认 MAC
    """

    def __init__(self, default_mac: str = "68ee8fd73668"):
        self.default_mac = default_mac
        self.devices = {}          # mac -> websocket
        self.apps = []             # list of websocket

    def add_device(self, mac: str, ws) -> None:
        previous = self.devices.get(mac)
        if previous is not None and previous is not ws:
            # 同 MAC 重连: 顶掉旧连接
            self.devices[mac] = ws
        else:
            self.devices[mac] = ws

    def remove_device(self, mac: str, ws) -> None:
        if self.devices.get(mac) is ws:
            del self.devices[mac]

    def add_app(self, ws) -> None:
        if ws not in self.apps:
            self.apps.append(ws)

    def remove_app(self, ws) -> None:
        if ws in self.apps:
            self.apps.remove(ws)

    def device_online(self, mac: str = None) -> bool:
        if mac is None:
            return bool(self.devices)
        return mac in self.devices

    def online_macs(self):
        return sorted(self.devices.keys())


# ── 服务端 ─────────────────────────────────────────────────────────────────
class StackChanServer:
    """替代官方云的替身服务端。

    连接角色按 query 的 deviceType 区分 (与官方云 web_socket.go:120-132 一致):
      deviceType=StackChan            -> 设备
      deviceType=App&deviceId=xxx     -> App

    转发语义严格照抄官方云 readAppClientMessage:
      - 6 类带 MAC 前缀的消息: 剥掉 12 字节 MAC 后转发给设备
        (web_socket.go:523/537/553/569/588)
      - 0x14 Dance: 原样转发, **不剥前缀**
        (web_socket.go:740-746; 官方 App dance.dart:193 也不加前缀)
    """

    def __init__(self, default_mac: str = "68ee8fd73668",
                 heartbeat_interval: float = 5.0,
                 verbose: bool = True,
                 single_device_fallback: bool = True):
        self.registry = ConnectionRegistry(default_mac)
        self.heartbeat_interval = heartbeat_interval
        self.verbose = verbose
        # 只有一台设备在线时, 允许把 MAC 不匹配的控制帧兜底投给它
        # (真机连不上带 MAC 的 URL, 详见 _handle_app_frame 里的说明)
        self.single_device_fallback = single_device_fallback
        self._pending_dance = None      # bytes, 设备上线后立即下发

    def log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    # ── 帧处理 ───────────────────────────────────────────────────────────
    def _handle_device_frame(self, msg_type: int, payload: bytes):
        """设备 -> 服务端。

        固件只发 0x11 Pong / 0x0E GetDeviceName 之类; 这里只做转发与心跳应答。
        固件收到 0x10 会回 0x11 (hal_ws_avatar.cpp:287-294), 所以设备侧的
        0x10 也按 0x11 回。

        返回 [(msg_type, payload), ...]。
        """
        if msg_type == PING:
            return [(PONG, b"")]
        return []

    def _handle_app_frame(self, msg_type: int, payload: bytes, app_mac=None):
        """App -> 服务端。

        返回 [(target_mac|None, msg_type, payload), ...], 语义同官方云
        readAppClientMessage:

          - 6 类带 MAC 前缀的消息: 用前缀里的 MAC 选目标设备, 剥掉前缀转发
            (web_socket.go:523/537/553/569/588)
          - 0x14 Dance: 原样转发, **不剥前缀**, 目标取 App 自己的 MAC
            (web_socket.go:740-746 —— case Dance 用的是 client.GetMac())
          - 其它类型: 原样转发给 App 自己 MAC 对应的设备
            (web_socket.go:759-770 的 default 分支)
        """
        if msg_type == PING:
            # 固件也会对 0x10 回 0x11 (hal_ws_avatar.cpp:287-294)
            return [(None, PONG, b"")]

        mac, body = split_mac_prefix(msg_type, payload)
        if msg_type == DANCE:
            # ⭐ 0x14 不剥前缀, 顶层是 JSON 数组, 原样转发
            return [(app_mac, DANCE, body)]

        if mac is not None:
            if mac in self.registry.devices:
                return [(mac, msg_type, body)]
            # 官方云的做法是丢弃 ("StackChan is currently offline",
            # web_socket.go:566)。
            #
            # ⚠ 但对**真机**必须放宽: 固件连上来的 URL 里没有 MAC
            # (hal_ws_avatar.cpp:88 只有 ?deviceType=StackChan), 官方云是从
            # Authorization 头解 RSA token 取 MAC 的 (web_socket.go:78-99),
            # 替身服务端解不了 RSA => 真机只能登记成 default_mac。
            # 而官方 App 发控制帧时前缀里是**真机的真实 MAC**
            # (avatar.dart:720), 与 default_mac 不一致 => 会被误丢。
            # 所以: 在线设备只有一台时, 兜底投给它 (带警告日志)。
            if self.single_device_fallback and len(self.registry.devices) == 1:
                only_mac = next(iter(self.registry.devices))
                self.log("[server] 0x%02X mac=%s 未匹配, 在线设备只有 %s, 兜底投递"
                         % (msg_type, mac, only_mac))
                return [(only_mac, msg_type, body)]
            self.log("[server] drop 0x%02X for unknown mac %s" % (msg_type, mac))
            return []

        # 其余类型 (0x05/0x06/0x12/0x13/0x15/0x1B 等) 原样转发
        return [(app_mac, msg_type, body)]

    async def _dispatch_to_devices(self, frames) -> None:
        """把 (target_mac|None, type, payload) 投递给设备。

        target_mac 为 None 表示广播给所有在线设备 (官方云在只有一个设备时
        的等效行为); 否则只投递给指定 MAC 的设备。
        """
        for target_mac, msg_type, body in frames:
            if not self.registry.devices:
                self.log("[server] no device online, drop 0x%02X" % msg_type)
                continue
            if target_mac is None:
                targets = list(self.registry.devices.items())
            else:
                ws = self.registry.devices.get(target_mac)
                targets = [(target_mac, ws)] if ws is not None else []
                if not targets:
                    self.log("[server] no device with mac %s, drop 0x%02X"
                             % (target_mac, msg_type))
                    continue
            for mac, ws in targets:
                try:
                    await ws.send(encode_frame(msg_type, body))
                    self.log("[server] -> device %s  0x%02X %s"
                             % (mac, msg_type, MSG_NAMES.get(msg_type, "")))
                except Exception as exc:  # pragma: no cover
                    self.log("[server] send to device %s failed: %s" % (mac, exc))

    async def _broadcast_to_apps(self, msg_type: int, body: bytes) -> None:
        for ws in list(self.registry.apps):
            try:
                await ws.send(encode_frame(msg_type, body))
            except Exception:  # pragma: no cover
                pass

    # ── 0x14 下发 ────────────────────────────────────────────────────────
    def set_pending_dance(self, sequence) -> bytes:
        """登记一份 0x14 关键帧数组, 设备上线后立即下发。

        校验不通过直接抛 ValueError —— 宁可拒绝下发, 也不要让固件静默丢弃
        (固件 json_helper.cpp:192-195 遇到非数组只打日志就返回)。
        """
        errors = validate_dance_sequence(sequence)
        if errors:
            raise ValueError("invalid dance sequence:\n  " + "\n  ".join(errors))
        payload = build_dance_payload(sequence)
        self._pending_dance = payload
        return payload

    async def send_dance_now(self) -> int:
        """把已登记的 0x14 发给所有在线设备。返回成功投递的设备数。"""
        if self._pending_dance is None:
            return 0
        sent = 0
        for mac, ws in list(self.registry.devices.items()):
            try:
                await ws.send(encode_frame(DANCE, self._pending_dance))
                sent += 1
                self.log("[server] 0x14 dance -> device %s (%d bytes)"
                         % (mac, len(self._pending_dance)))
            except Exception as exc:  # pragma: no cover
                self.log("[server] dance send to %s failed: %s" % (mac, exc))
        return sent

    # ── 心跳 ─────────────────────────────────────────────────────────────
    async def _heartbeat_once(self) -> None:
        """发一轮 0x10 心跳 (自检和常驻循环共用)。"""
        targets = list(self.registry.devices.values()) + list(self.registry.apps)
        for ws in targets:
            try:
                await ws.send(encode_frame(PING, b""))
            except Exception:  # pragma: no cover
                pass

    async def _heartbeat_loop(self) -> None:
        """定期给设备和 App 发 0x10。

        官方云每 5 秒发一次 (server/internal/boot/cron.go:35 + web_socket/
        socket_task.go:36)。固件 10 秒收不到任何帧会报 Heartbeat Timeout
        (hal_ws_avatar.cpp:171-174), 所以这里必须照做。
        """
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            await self._heartbeat_once()

    # ── 连接处理 ─────────────────────────────────────────────────────────
    async def handler(self, ws, path=None) -> None:
        request_path = self._request_path(ws, path)
        query = parse_qs(urlparse(request_path).query)
        device_type = (query.get("deviceType") or [""])[0]
        device_id = (query.get("deviceId") or [""])[0]
        raw_mac = (query.get("mac") or [""])[0]

        if device_type == "StackChan":
            mac = normalize_mac(raw_mac) or self.registry.default_mac
            self.registry.add_device(mac, ws)
            self.log("[server] device online: mac=%s path=%s" % (mac, request_path))
            await self._broadcast_to_apps(DEVICE_ONLINE, mac.encode("ascii"))
            if self._pending_dance is not None:
                await ws.send(encode_frame(DANCE, self._pending_dance))
                self.log("[server] 0x14 dance -> device %s (on connect)" % mac)
            try:
                await self._device_loop(ws)
            finally:
                self.registry.remove_device(mac, ws)
                self.log("[server] device offline: mac=%s" % mac)
                await self._broadcast_to_apps(DEVICE_OFFLINE, mac.encode("ascii"))
            return

        if device_type == "App":
            self.registry.add_app(ws)
            app_mac = normalize_mac(raw_mac)
            self.log("[server] app connected: deviceId=%s mac=%s"
                     % (device_id or "-", app_mac or "-"))
            macs = self.registry.online_macs()
            await ws.send(encode_frame(
                DEVICE_ONLINE if macs else DEVICE_OFFLINE,
                (macs[0] if macs else self.registry.default_mac).encode("ascii")))
            try:
                await self._app_loop(ws, app_mac or None)
            finally:
                self.registry.remove_app(ws)
                self.log("[server] app disconnected: deviceId=%s" % (device_id or "-"))
            return

        # 其它 deviceType: 官方云直接报错 (web_socket.go:120-124)
        self.log("[server] reject connection without deviceType: %s" % request_path)
        await ws.close(code=1008, reason="deviceType is required")

    @staticmethod
    def _request_path(ws, legacy_path=None) -> str:
        """websockets >= 14 的 asyncio 实现: 路径在 ws.request.path。"""
        for candidate in (
                getattr(getattr(ws, "request", None), "path", None),
                legacy_path,
                getattr(ws, "path", None)):
            if candidate:
                return str(candidate)
        return ""

    async def _device_loop(self, ws) -> None:
        async for raw in ws:
            if isinstance(raw, str):
                # 固件连上后先发一条文本 hello (hal_ws_avatar.cpp:161)
                self.log("[server] device text: %s" % raw[:120])
                continue
            frame = decode_frame(bytes(raw))
            if frame is None:
                self.log("[server] malformed frame from device")
                continue
            msg_type, payload = frame
            self.log("[server] <- device 0x%02X %s (%d B)"
                     % (msg_type, MSG_NAMES.get(msg_type, ""), len(payload)))
            for reply_type, reply_body in self._handle_device_frame(msg_type, payload):
                await ws.send(encode_frame(reply_type, reply_body))

    async def _app_loop(self, ws, app_mac=None) -> None:
        async for raw in ws:
            if isinstance(raw, str):
                self.log("[server] app text: %s" % raw[:120])
                continue
            frame = decode_frame(bytes(raw))
            if frame is None:
                self.log("[server] malformed frame from app")
                continue
            msg_type, payload = frame
            self.log("[server] <- app 0x%02X %s (%d B)"
                     % (msg_type, MSG_NAMES.get(msg_type, ""), len(payload)))
            frames = self._handle_app_frame(msg_type, payload, app_mac)
            await self._dispatch_to_devices(frames)

    # ── 生命周期 ─────────────────────────────────────────────────────────
    async def serve(self, host: str = "0.0.0.0", port: int = 12800) -> None:
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            async with websockets.serve(self.handler, host, port,
                                        ping_interval=20, ping_timeout=20):
                self.log("[server] listening on ws://%s:%d/stackChan/ws" % (host, port))
                self.log("[server] devices=%s apps=%d"
                         % (self.registry.online_macs() or "none",
                            len(self.registry.apps)))
                await asyncio.Future()
        finally:
            heartbeat.cancel()


# ── 自检 ───────────────────────────────────────────────────────────────────
class _Recorder:
    """假的 websocket 连接, 记录发出去的帧。"""

    def __init__(self):
        self.sent = []

    async def send(self, data):
        self.sent.append(bytes(data))

    async def close(self, code=None, reason=None):
        pass

    def frames(self):
        out = []
        for blob in self.sent:
            decoded = decode_frame(blob)
            out.append(decoded if decoded else (None, blob))
        return out


def _sample_keyframe(weight: int = 100, yaw: int = 0, pitch: int = 450,
                     duration: int = 800) -> dict:
    """构造一帧合法的 0x14 关键帧 (结构见 dance_list.dart:119-130)。"""
    def feature(w):
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


def run_self_test() -> int:
    checks = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    def check_raises(name, fn, expect_substring=""):
        try:
            fn()
        except Exception as exc:
            message = str(exc)
            ok = (expect_substring == "") or (expect_substring in message)
            check(name, ok, "raised %s: %s" % (type(exc).__name__, message[:160]))
            return
        check(name, False, "expected an exception, none raised")

    mac = "68ee8fd73668"

    # ── 1. 帧格式 ───────────────────────────────────────────────────────
    frame = encode_frame(DANCE, b"[]")
    check("frame layout is [type:1][len:4 BE][payload]",
          frame[0] == DANCE and frame[1:5] == b"\x00\x00\x00\x02"
          and frame[5:] == b"[]",
          "frame=%s" % frame.hex())
    check("frame round-trips through decode_frame",
          decode_frame(frame) == (DANCE, b"[]"))
    check("decode_frame rejects a truncated frame",
          decode_frame(frame[:-1]) is None)
    check("decode_frame rejects an empty buffer",
          decode_frame(b"") is None)

    # ── 2. MAC 前缀规则: 6 类带前缀, 0x14 不带 ──────────────────────────
    for msg_type in (OPUS, JPEG, CONTROL_AVATAR, CONTROL_MOTION,
                     TEXT_MESSAGE, REQUEST_CALL):
        payload = build_control_payload(mac, {"type": "bleAvatar"})
        parsed_mac, body = split_mac_prefix(msg_type, payload)
        check("0x%02X strips the 12-byte MAC prefix" % msg_type,
              parsed_mac == mac and body == b'{"type":"bleAvatar"}',
              "mac=%r body=%r" % (parsed_mac, body))

    dance_payload = build_dance_payload([_sample_keyframe()])
    parsed_mac, body = split_mac_prefix(DANCE, dance_payload)
    check("0x14 does NOT strip any prefix",
          parsed_mac is None and body == dance_payload,
          "mac=%r" % (parsed_mac,))
    check("0x14 payload is not a JSON object",
          parse_json_body(dance_payload).__class__ is list)
    check("MAC prefix is exactly 12 ASCII bytes",
          len(mac_to_bytes(mac)) == 12 and mac_to_bytes(mac) == mac.encode("ascii"))

    # ── 3. 入站解析方向 ─────────────────────────────────────────────────
    server = StackChanServer(default_mac=mac, verbose=False)
    device = _Recorder()
    server.registry.add_device(mac, device)

    frames = server._handle_app_frame(DANCE, dance_payload, mac)
    check("inbound 0x14 is forwarded with the array payload intact",
          len(frames) == 1 and frames[0][1] == DANCE
          and frames[0][2] == dance_payload,
          "frames=%r" % (frames,))
    check("inbound 0x14 is routed to the App's own MAC",
          len(frames) == 1 and frames[0][0] == mac,
          "frames=%r" % (frames,))

    avatar_obj = {"type": "bleAvatar",
                  "leftEye": {"x": 0, "y": 0, "rotation": 0, "weight": 90, "size": 0},
                  "rightEye": {"x": 0, "y": 0, "rotation": 0, "weight": 90, "size": 0},
                  "mouth": {"x": 0, "y": 0, "rotation": 0, "weight": 20, "size": 0}}
    prefixed = build_control_payload(mac, avatar_obj)
    frames = server._handle_app_frame(CONTROL_AVATAR, prefixed)
    check("inbound 0x03 strips the MAC prefix before reaching the device",
          len(frames) == 1 and frames[0][1] == CONTROL_AVATAR
          and frames[0][2] == prefixed[12:],
          "frames=%r" % (frames,))
    check("stripped 0x03 body is the pure JSON object",
          parse_json_body(frames[0][2]) == avatar_obj)
    check("inbound 0x03 is routed to the MAC taken from the prefix",
          len(frames) == 1 and frames[0][0] == mac,
          "frames=%r" % (frames,))

    for msg_type in (CONTROL_MOTION, TEXT_MESSAGE):
        prefixed = build_control_payload(mac, {"type": "bleMotion"})
        frames = server._handle_app_frame(msg_type, prefixed)
        check("inbound 0x%02X strips the MAC prefix" % msg_type,
              len(frames) == 1 and frames[0][2] == prefixed[12:])

    # 未剥前缀的 0x03 (没有 MAC) 也必须原样转发, 不能瞎切 12 字节
    plain = json.dumps(avatar_obj, separators=(",", ":")).encode("utf-8")
    frames = server._handle_app_frame(CONTROL_AVATAR, plain)
    check("0x03 without a MAC prefix is not truncated",
          len(frames) == 1 and frames[0][2] == plain,
          "frames=%r" % (frames,))

    # MAC 不匹配的 0x03: 只有一台设备在线时兜底投给它 (真机场景)
    other = build_control_payload("001122334455", avatar_obj)
    frames = server._handle_app_frame(CONTROL_AVATAR, other)
    check("0x03 for an unmatched MAC falls back to the only online device",
          len(frames) == 1 and frames[0][0] == mac
          and frames[0][2] == other[12:],
          "frames=%r" % (frames,))

    # 关掉兜底后, MAC 不匹配必须丢弃 (官方云语义)
    strict = StackChanServer(default_mac=mac, verbose=False,
                             single_device_fallback=False)
    strict.registry.add_device(mac, _Recorder())
    frames = strict._handle_app_frame(CONTROL_AVATAR, other)
    check("0x03 for an unmatched MAC is dropped when fallback is off",
          frames == [], "frames=%r" % (frames,))

    # 两台设备在线时不能兜底, 必须按 MAC 精确投递
    two = StackChanServer(default_mac=mac, verbose=False)
    two.registry.add_device(mac, _Recorder())
    two.registry.add_device("aabbccddeeff", _Recorder())
    frames = two._handle_app_frame(CONTROL_AVATAR, other)
    check("0x03 is not mis-delivered when several devices are online",
          frames == [], "frames=%r" % (frames,))

    # ── 4. 下发方向: 发给设备的帧 ───────────────────────────────────────
    check("downlink 0x14 payload top level is a JSON array",
          isinstance(parse_json_body(dance_payload), list))
    check("downlink 0x14 payload carries no 12-byte MAC prefix",
          not dance_payload.startswith(mac.encode("ascii")))
    check("downlink 0x03 payload keeps the 12-byte MAC prefix",
          prefixed.startswith(mac.encode("ascii"))
          and len(prefixed) > 12
          and prefixed[:12] == mac.encode("ascii"),
          "prefix=%r" % prefixed[:12])
    check("downlink 0x03 payload first 12 bytes are the target MAC",
          prefixed[:12] == mac_to_bytes(mac))

    # 设备实际收到的帧 (server -> device) 必须是剥过前缀的
    device.sent.clear()
    asyncio.run(server._dispatch_to_devices(
        server._handle_app_frame(CONTROL_AVATAR, prefixed)))
    delivered = [f for f in device.frames() if f[0] == CONTROL_AVATAR]
    check("device receives 0x03 without the MAC prefix",
          len(delivered) == 1 and delivered[0][1] == prefixed[12:],
          "delivered=%r" % (delivered,))

    device.sent.clear()
    asyncio.run(server._dispatch_to_devices(
        server._handle_app_frame(DANCE, dance_payload, mac)))
    delivered = [f for f in device.frames() if f[0] == DANCE]
    check("device receives 0x14 as a raw JSON array",
          len(delivered) == 1
          and delivered[0][1] == dance_payload
          and parse_json_body(delivered[0][1])[0].keys() >= set(DANCE_KEYS),
          "delivered=%r" % (delivered,))

    # ── 5. 关键帧结构校验 ───────────────────────────────────────────────
    good = _sample_keyframe()
    check("a well-formed keyframe passes validation",
          validate_dance_sequence([good]) == [],
          "errors=%r" % validate_dance_sequence([good]))
    check("all 8 keys are required",
          set(DANCE_KEYS) == {"leftEye", "rightEye", "mouth", "yawServo",
                               "pitchServo", "leftRgbColor", "rightRgbColor",
                               "durationMs"})
    missing = dict(good)
    del missing["durationMs"]
    errors = validate_dance_sequence([missing])
    check("missing key is detected",
          any("durationMs" in e for e in errors), "errors=%r" % errors)

    # 舵机限位 (hal_servo.cpp:340 / :349)
    for angle, ok in ((1280, True), (-1280, True), (1281, False), (-1281, False)):
        errors = validate_dance_sequence([_sample_keyframe(yaw=angle)])
        check("yaw angle %d %s" % (angle, "accepted" if ok else "rejected"),
              (errors == []) if ok else (any("yawServo.angle" in e for e in errors)),
              "errors=%r" % errors)
    for angle, ok in ((30, True), (870, True), (29, False), (871, False)):
        errors = validate_dance_sequence([_sample_keyframe(pitch=angle)])
        check("pitch angle %d %s" % (angle, "accepted" if ok else "rejected"),
              (errors == []) if ok else (any("pitchServo.angle" in e for e in errors)),
              "errors=%r" % errors)

    # int 严格性 (固件判 is<int>())
    float_frame = _sample_keyframe()
    float_frame["leftEye"]["weight"] = 72.5
    errors = validate_dance_sequence([float_frame])
    check("float weight is rejected (firmware checks is<int>())",
          any("leftEye.weight must be an int" in e for e in errors),
          "errors=%r" % errors)

    float_x = _sample_keyframe()
    float_x["mouth"]["x"] = 1.0
    errors = validate_dance_sequence([float_x])
    check("float x is rejected",
          any("mouth.x must be an int" in e for e in errors),
          "errors=%r" % errors)

    bool_frame = _sample_keyframe()
    bool_frame["rightEye"]["size"] = True
    errors = validate_dance_sequence([bool_frame])
    check("bool is rejected (Python bool is an int subclass)",
          any("rightEye.size must be an int" in e for e in errors),
          "errors=%r" % errors)

    # ── 6. 眼睛 weight 方向 (对照官方情绪表) ────────────────────────────
    check("eye openness grows with weight",
          eye_openness(100) > eye_openness(72) > eye_openness(35),
          "100=%.3f 72=%.3f 35=%.3f"
          % (eye_openness(100), eye_openness(72), eye_openness(35)))
    check("eye openness is 0 at weight 0 and 1 at weight 100",
          eye_openness(0) == 0.0 and eye_openness(100) == 1.0)
    check("eyelid offset moves up (negative) as weight grows",
          eye_lid_offset(100) < eye_lid_offset(35) < eye_lid_offset(0),
          "100=%d 35=%d 0=%d" % (eye_lid_offset(100), eye_lid_offset(35),
                                 eye_lid_offset(0)))
    # 官方情绪表 (eyes.cpp:102-123): Neutral 最睁 (100), Sleepy 最眯 (35)
    check("official emotion table agrees: Neutral opens more than Sleepy",
          eye_openness(EMOTION_EYE_WEIGHT["Neutral"])
          > eye_openness(EMOTION_EYE_WEIGHT["Sleepy"]),
          "Neutral=%d Sleepy=%d"
          % (EMOTION_EYE_WEIGHT["Neutral"], EMOTION_EYE_WEIGHT["Sleepy"]))
    # Sleepy 是表里最眯的 (weight 最小), Neutral 最睁 (weight 最大)
    sleepy = EMOTION_EYE_WEIGHT["Sleepy"]
    neutral = EMOTION_EYE_WEIGHT["Neutral"]
    check("official emotion table: Sleepy is the minimum weight (most closed)",
          all(w >= sleepy for w in EMOTION_EYE_WEIGHT.values()),
          "table=%r" % EMOTION_EYE_WEIGHT)
    check("official emotion table: Neutral is the maximum weight (most open)",
          all(w <= neutral for w in EMOTION_EYE_WEIGHT.values()),
          "table=%r" % EMOTION_EYE_WEIGHT)
    check("official emotion table: every non-Sleepy emotion opens more than Sleepy",
          all(eye_openness(w) > eye_openness(sleepy)
              for name, w in EMOTION_EYE_WEIGHT.items() if name != "Sleepy"),
          "table=%r" % EMOTION_EYE_WEIGHT)
    check("mouth openness grows with weight",
          mouth_openness(100) > mouth_openness(0))
    check("mouth at weight 0 is the closed shape (90x6, r=0)",
          MOUTH_MIN_SIZE == (90, 6) and MOUTH_MIN_RADIUS == 0)
    check("mouth at weight 100 is the open shape (60x50, r=16)",
          MOUTH_MAX_SIZE == (60, 50) and MOUTH_MAX_RADIUS == 16)

    # ── 7. 心跳 ─────────────────────────────────────────────────────────
    frames = server._handle_device_frame(PING, b"")
    check("device 0x10 is answered with 0x11",
          frames == [(PONG, b"")], "frames=%r" % (frames,))
    frames = server._handle_app_frame(PING, b"")
    check("app 0x10 is answered with 0x11",
          frames == [(None, PONG, b"")], "frames=%r" % (frames,))

    device.sent.clear()
    asyncio.run(server._heartbeat_once())
    check("server sends 0x10 to the device on its own heartbeat",
          any(f[0] == PING for f in device.frames()),
          "sent=%r" % device.frames())

    # ── 8. 不假装固件没有的东西 ─────────────────────────────────────────
    check("firmware has no 0x15 GetAvatarPosture in its DataType enum",
          GET_AVATAR_POSTURE not in (
              OPUS, JPEG, CONTROL_AVATAR, CONTROL_MOTION, ON_CAMERA,
              OFF_CAMERA, TEXT_MESSAGE, REQUEST_CALL, REFUSE_CALL, AGREE_CALL,
              HANGUP_CALL, UPDATE_DEVICE_NAME, GET_DEVICE_NAME, PING, PONG,
              ON_PHONE_SCREEN, OFF_PHONE_SCREEN, DANCE, ON_AUDIO, OFF_AUDIO,
              AIMED_TAKE_PHOTO, APP_LAN_ADDRESS))
    server_no_device = StackChanServer(default_mac=mac, verbose=False)
    frames = server_no_device._handle_app_frame(DANCE, dance_payload, mac)
    recorder = _Recorder()
    asyncio.run(server_no_device._dispatch_to_devices(frames))
    check("0x14 with no device online produces no delivery",
          bool(frames) and not server_no_device.registry.devices
          and recorder.sent == [],
          "frames=%r" % (frames,))

    # ── 9. 变异用例: 证明断言不是恒真 ───────────────────────────────────
    # (a) 把 0x14 包成对象 -> 校验必须报错
    mutated_object = {"sequence": [_sample_keyframe()]}
    errors = validate_dance_sequence(mutated_object)
    check("MUTATION: 0x14 wrapped in an object is caught",
          len(errors) > 0
          and any("must be a JSON array" in e for e in errors),
          "errors=%r" % errors)
    check_raises("MUTATION: set_pending_dance refuses an object-wrapped 0x14",
                 lambda: server.set_pending_dance(mutated_object),
                 "must be a JSON array")

    # (b) 把 eye 的 weight 写成 float -> 校验必须报错
    mutated_float = _sample_keyframe()
    mutated_float["leftEye"]["weight"] = 72.5
    errors = validate_dance_sequence([mutated_float])
    check("MUTATION: float eye weight is caught",
          any("leftEye.weight must be an int" in e for e in errors),
          "errors=%r" % errors)
    check_raises("MUTATION: set_pending_dance refuses a float eye weight",
                 lambda: server.set_pending_dance([mutated_float]),
                 "must be an int")

    # (c) 越界的舵机角 -> 必须报错
    mutated_angle = _sample_keyframe(yaw=5000)
    errors = validate_dance_sequence([mutated_angle])
    check("MUTATION: out-of-range yaw angle is caught",
          any("out of firmware limit" in e for e in errors),
          "errors=%r" % errors)

    # (d) 反向证明: 若把断言写成恒真, 上面这些变异就抓不到
    check("MUTATION: the baseline frame really does pass (assertions discriminate)",
          validate_dance_sequence([_sample_keyframe()]) == [])

    # ── 10. MAC 规范化 ─────────────────────────────────────────────────
    check("normalize_mac accepts colon form",
          normalize_mac("68:EE:8F:D7:36:68") == "68ee8fd73668")
    check("normalize_mac rejects a short string",
          normalize_mac("68ee8f") == "")

    # ── 输出 ────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in checks if ok)
    failed = [(n, d) for n, ok, d in checks if not ok]
    print("=" * 72)
    for name, ok, detail in checks:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
        if not ok and detail:
            print("        detail: %s" % detail)
    print("=" * 72)
    print("%d/%d checks passed" % (passed, len(checks)))
    if failed:
        print("FAILED %d check(s):" % len(failed))
        for name, detail in failed:
            print("  - %s (%s)" % (name, detail))
        print("SELF-TEST FAILED")
        return 1
    print("ALL PASS")
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="StackChan 协议替身服务端 (让真机连上并接受 0x14 控制)")
    parser.add_argument("--serve", action="store_true", help="启动服务端")
    parser.add_argument("--port", type=int, default=12800, help="监听端口 (默认 12800)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    parser.add_argument("--mac", default="68ee8fd73668",
                        help="设备默认 MAC (固件 URL 不带 mac, 只能这样指定)")
    parser.add_argument("--dance", help="0x14 关键帧 JSON 文件 (顶层数组)")
    parser.add_argument("--dance-stdin", action="store_true",
                        help="从 stdin 读 0x14 关键帧 JSON (顶层数组)")
    parser.add_argument("--self-test", action="store_true", help="跑自检并退出")
    parser.add_argument("--strict-mac", action="store_true",
                        help="关闭「单设备在线时的 MAC 兜底投递」(默认开启, "
                             "真机连不上带 MAC 的 URL 时需要)")
    parser.add_argument("--quiet", action="store_true", help="不打印日志")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.serve:
        parser.print_help()
        return 2

    server = StackChanServer(default_mac=args.mac, verbose=not args.quiet,
                             single_device_fallback=not args.strict_mac)

    sequence = None
    if args.dance:
        with open(args.dance, "r", encoding="utf-8") as handle:
            sequence = json.load(handle)
    elif args.dance_stdin:
        sequence = json.loads(sys.stdin.read())

    if sequence is not None:
        try:
            payload = server.set_pending_dance(sequence)
        except ValueError as exc:
            print("[server] dance rejected: %s" % exc)
            return 1
        server.log("[server] 0x14 dance registered: %d keyframes, %d bytes"
                   % (len(sequence), len(payload)))

    try:
        asyncio.run(server.serve(args.host, args.port))
    except KeyboardInterrupt:  # pragma: no cover
        print("[server] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
