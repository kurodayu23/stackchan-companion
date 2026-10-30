#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StackChan 协议模拟器（Protocol Simulator）
=========================================
按官方仓库 `m5stack/StackChan`（origin/main = eff0d6b, 2026-10-22）的**真实协议**实现，
在没有真机的情况下验证 App ↔ 设备 ↔ 云 的完整链路。

实现的三件事（全部按官方源码实读，不猜）：
1. 远程 WebSocket 帧格式：5 字节头 `[type:1][length:4 BE][payload]`
   —— 出处 app/lib/app_state.dart:275-279
2. 局域网帧格式：20 字节头 `[0x53 0x43][ver:1][type:1][...][session:8][seq:4][len:2]`
   —— 出处 firmware/main/hal/utils/local_network/local_network_protocol.h
3. 24 个 MsgType 与 payload 契约（MAC(12B) + JSON）
   —— 出处 app/lib/model/msg_type.dart、app/lib/view/home/avatar.dart:712-729

角色：
  --role device   扮演小栈设备（连服务器，等 App 下发控制）
  --role app      扮演 iOS App（连服务器，把自己的局域网地址告诉设备）
  --role lan      扮演设备反向连入 App 开的局域网 WebSocket 服务（路径 /ws）

用法：
  py -3.12 tools/protocol_sim.py --role device --port 12800
  py -3.12 tools/protocol_sim.py --role app    --port 12800 --device-mac 68:ee:8f:d7:36:68
  py -3.12 tools/protocol_sim.py --role lan    --connect ws://127.0.0.1:9001/ws
"""
import argparse
import asyncio
import json
import struct
import sys

try:
    import websockets
except ImportError:
    print("需要 websockets：py -3.12 -m pip install websockets")
    sys.exit(1)

# ── MsgType（app/lib/model/msg_type.dart 全文） ────────────────────────
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
    CONTROL_MOTION: "controlMotion", ON_CAMERA: "onCamera", OFF_CAMERA: "offCamera",
    TEXT_MESSAGE: "textMessage", REQUEST_CALL: "requestCall", REFUSE_CALL: "refuseCall",
    AGREE_CALL: "agreeCall", HANGUP_CALL: "hangupCall", UPDATE_DEVICE_NAME: "updateDeviceName",
    GET_DEVICE_NAME: "getDeviceName", PING: "ping", PONG: "pong",
    ON_PHONE_SCREEN: "onPhoneScreen", OFF_PHONE_SCREEN: "offPhoneScreen", DANCE: "dance",
    GET_AVATAR_POSTURE: "getAvatarPosture", DEVICE_OFFLINE: "deviceOffline",
    DEVICE_ONLINE: "deviceOnline", ON_AUDIO: "onAudio", OFF_AUDIO: "offAudio",
    AIMED_TAKE_PHOTO: "aimedTakePhoto", APP_LAN_ADDRESS: "appLanAddress",
}

# 官方云 readAppClientMessage **只对这几类**剥 12 字节 MAC 前缀
# （web_socket.go:523 Opus / :537 Jpeg / :553 ControlAvatar,ControlMotion
#   / :569 TextMessage / :588 RequestCall）
# ⭐ Dance(0x14) **不剥**（:740 `case Dance:` 原样转发）
CLOUD_STRIP_MAC = {OPUS, JPEG, CONTROL_AVATAR, CONTROL_MOTION,
                   TEXT_MESSAGE, REQUEST_CALL}

# 舵机真实限幅（firmware/main/hal/hal_servo.cpp servo_init）
#   yaw   angleLimit = Vector2i(-1280, 1280)  → ±128.0°
#   pitch angleLimit = Vector2i(30, 870)     →  3.0° ~ 87.0°
# 线上传输单位是 0.1 度（angle=1280 表示 128°）。
# 固件在 json_helper.cpp update_servo 里拿到 angle 后交给 servo.moveWithSpeed，
# 限幅由 ScsServo 内部按 angleLimit 执行 —— 所以限幅必须在线上单位上做。
YAW_MIN_RAW, YAW_MAX_RAW = -1280, 1280      # 0.1 度
PITCH_MIN_RAW, PITCH_MAX_RAW = 30, 870      # 0.1 度
YAW_MIN, YAW_MAX = YAW_MIN_RAW / 10.0, YAW_MAX_RAW / 10.0
PITCH_MIN, PITCH_MAX = PITCH_MIN_RAW / 10.0, PITCH_MAX_RAW / 10.0


# ── 帧编解码 ───────────────────────────────────────────────────────────
def encode_remote(msg_type: int, payload: bytes = b"") -> bytes:
    """远程 WS 帧：[type:1][length:4 BE][payload]"""
    return bytes([msg_type & 0xFF]) + struct.pack(">I", len(payload)) + payload


def decode_remote(data: bytes):
    """返回 (type, payload) 或 None"""
    if len(data) < 5:
        return None
    t = data[0]
    (ln,) = struct.unpack(">I", data[1:5])
    if len(data) < 5 + ln:
        return None
    return t, data[5:5 + ln]


def encode_lan(msg_type: int, payload: bytes = b"", session: int = 0, seq: int = 0) -> bytes:
    """LAN 帧 20 字节头：[0x53 0x43][ver:1][type:1][pad:3][session:8][seq:4][len:2][payload]"""
    head = bytearray(20)
    head[0] = 0x53
    head[1] = 0x43
    head[2] = 1
    head[3] = msg_type & 0xFF
    head[6:14] = session.to_bytes(8, "big")
    head[14:18] = seq.to_bytes(4, "big")
    head[18:20] = len(payload).to_bytes(2, "big")
    return bytes(head) + payload


def decode_lan(data: bytes):
    if len(data) < 20:
        return None
    if data[0] != 0x53 or data[1] != 0x43:
        return None
    t = data[3]
    (ln,) = struct.unpack(">H", data[18:20])
    if len(data) < 20 + ln:
        return None
    return t, data[20:20 + ln]


# ── payload 契约 ─────────────────────────────────────────────────────────
# 【实测自官方源码，非推测】
#
# ① App → 云 → 设备（控制类）：
#    payload = MAC(12 字节 ASCII) + JSON
#    官方 App：app/lib/view/home/avatar.dart
#        final motionJsonString = widget.deviceMac + motionData.toString();
#        final motionMessageData = motionJsonString.toUint8List();
#      → deviceMac 是 12 字符十六进制串（无冒号），前缀恒为 12 字节 ASCII。
#    官方云：server/internal/web_socket/web_socket.go readAppClientMessage
#        macAddrBytes := payload[:12]; data := payload[12:]
#        macAddr := string(macAddrBytes)          // ← 证明是 ASCII 字符串，不是二进制
#        newMsg := createMessage(msgType, data)   // ← 云剥掉 12 字节，只把 JSON 转给设备
#
# ② JSON 结构（app/lib/model/expression_data.dart + firmware json_helper.cpp）：
#    Motion:  {"type":"bleMotion","pitchServo":{"angle":N,"speed":500},
#                              "yawServo":{"angle":N,"speed":500}}
#      固件 update_servo 读 angle / speed / rotate / spring，不是标量！
#    Avatar:  {"type":"bleAvatar","leftEye":{"x":..,"y":..,"rotation":..,"weight":..,"size":..},
#                              "rightEye":{...},"mouth":{...}}
#
# ③ 舵机单位 = 0.1 度（firmware hal_servo.cpp servo_init）
#    yaw   angleLimit = Vector2i(-1280, 1280)  → ±128.0°
#    pitch angleLimit = Vector2i(30, 870)     →  3.0° ~ 87.0°
def build_control(mac: str, obj: dict) -> bytes:
    m = mac.replace(":", "").replace("-", "").lower().encode("ascii")
    return m + json.dumps(obj, separators=(",", ":")).encode("utf-8")


def parse_control(mac_expected: str, payload: bytes):
    """解析控制 JSON。

    注意：官方 server 在转发给设备前**已经剥掉 12 字节 MAC 前缀**
    （web_socket.go readAppClientMessage: data := payload[12:]），
    所以设备侧收到的就是纯 JSON。这里做兼容：能直接解析就用，
    不能就剥掉 12 字节再试。
    """
    raw = payload
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        pass
    if len(raw) >= 12:
        try:
            return json.loads(raw[12:].decode("utf-8"))
        except Exception:
            pass
    return None


def build_motion(yaw_deg: float, pitch_deg: float) -> dict:
    """MotionData.toJson() 的真实结构（angle 单位 0.1 度）。"""
    return {
        "type": "bleMotion",
        "pitchServo": {"angle": int(round(pitch_deg * 10)), "speed": 500},
        "yawServo": {"angle": int(round(yaw_deg * 10)), "speed": 500},
    }


def build_avatar(left_eye: dict, right_eye: dict, mouth: dict) -> dict:
    """ExpressionData.toJson() 的真实结构。"""
    def item(x=0, y=0, rotation=0, weight=0, size=0):
        return {"x": x, "y": y, "rotation": rotation, "weight": weight, "size": size}
    return {
        "type": "bleAvatar",
        "leftEye": item(**left_eye),
        "rightEye": item(**right_eye),
        "mouth": item(**mouth),
    }


# ── 设备状态机 ─────────────────────────────────────────────────────────
class DeviceState:
    def __init__(self, mac: str):
        self.mac = mac
        self.yaw = 0.0
        self.pitch = 42.0
        self.expression = {"leftEye": 0.0, "rightEye": 0.0, "mouth": 0.0}
        self.audio_on = True
        self.camera_on = False
        self.phone_screen = False
        self.name = "小栈"
        self.left_rgb = None
        self.right_rgb = None

    def snapshot(self):
        return {
            "mac": self.mac,
            "yaw": round(self.yaw, 1),
            "pitch": round(self.pitch, 1),
            "expression": self.expression,
            "audioOn": self.audio_on,
            "cameraOn": self.camera_on,
            "phoneScreen": self.phone_screen,
            "name": self.name,
            "leftRgb": self.left_rgb,
            "rightRgb": self.right_rgb,
        }


class DeviceSim:
    """扮演小栈设备：处理来自 App / 云的指令，并把状态变化广播回 App。"""

    def __init__(self, mac: str, lan: bool = False):
        self.state = DeviceState(mac)
        self.lan = lan
        self.apps = []          # 已连接的 App（远程模式）
        self.seq = 0

    def handle(self, msg_type: int, payload: bytes, sender=None):
        """返回要回发的帧列表 [(type, payload)]"""
        out = []
        name = MSG_NAMES.get(msg_type, "0x%02X" % msg_type)

        if msg_type == PING:
            out.append((PONG, b""))
        elif msg_type == GET_DEVICE_NAME:
            out.append((UPDATE_DEVICE_NAME, build_control(self.state.mac, {"name": self.state.name})))
        elif msg_type == CONTROL_MOTION:
            obj = parse_control(self.state.mac, payload)
            if obj:
                # 固件 json_helper.cpp update_servo 读的是嵌套对象
                yaw_obj = obj.get("yawServo") or {}
                pitch_obj = obj.get("pitchServo") or {}
                yaw_raw = float(yaw_obj.get("angle", self.state.yaw * 10))
                pitch_raw = float(pitch_obj.get("angle", self.state.pitch * 10))
                # 固件限幅：yaw ±1280，pitch 30~870（单位 0.1 度）
                self.state.yaw = max(YAW_MIN_RAW, min(YAW_MAX_RAW, yaw_raw)) / 10.0
                self.state.pitch = max(PITCH_MIN_RAW, min(PITCH_MAX_RAW, pitch_raw)) / 10.0
                print("  [device] controlMotion -> yaw=%.1f° pitch=%.1f° (限幅后)"
                      % (self.state.yaw, self.state.pitch))
            else:
                print("  [device] controlMotion payload 解析失败")
        elif msg_type == CONTROL_AVATAR:
            obj = parse_control(self.state.mac, payload)
            if obj:
                # 固件 update_feature 读 rotation/weight/size
                def feat(key):
                    it = obj.get(key) or {}
                    return {
                        "rotation": it.get("rotation", 0),
                        "weight": it.get("weight", 0),
                        "size": it.get("size", 0),
                    }
                self.state.expression = {
                    "leftEye": feat("leftEye"),
                    "rightEye": feat("rightEye"),
                    "mouth": feat("mouth"),
                }
                print("  [device] controlAvatar -> %s" % self.state.expression)
        elif msg_type == DANCE:
            # 固件 json_helper.cpp parse_sequence_from_json：顶层是**数组**，每元素一个关键帧
            try:
                seq = json.loads(payload.decode("utf-8"))
            except Exception:
                seq = parse_control(self.state.mac, payload)
            if not isinstance(seq, list) or not seq:
                print("  [device] dance payload 不是关键帧数组，忽略")
                return out
            total = sum(int(k.get("durationMs", 0)) for k in seq)
            # 固件 Keyframe::apply() 直接 set（绕过 modify lock），Timeline::update() 硬切无插值
            yaws = [float(k.get("yawServo", {}).get("angle", 0)) for k in seq]
            pitches = [float(k.get("pitchServo", {}).get("angle", 0)) for k in seq]
            # servo.cpp:126-161 —— speed 实为弹簧刚度：stiffness = 10 + (speed/1000)^2*640
            speeds = sorted({int(k.get("yawServo", {}).get("speed", 0)) for k in seq})
            stiff = [10.0 + (s / 1000.0) ** 2 * 640.0 for s in speeds]
            print("  [device] dance 收到 %d 个关键帧 / 总时长 %d ms" % (len(seq), total))
            print("         yaw   %.1f° ~ %.1f°  （物理限位 ±%.1f°）"
                  % (min(yaws) / 10.0, max(yaws) / 10.0, YAW_MAX))
            print("         pitch %.1f° ~ %.1f°  （物理限位 %.1f°~%.1f°）"
                  % (min(pitches) / 10.0, max(pitches) / 10.0, PITCH_MIN, PITCH_MAX))
            print("         speed 档位 %s → 弹簧刚度 %s（speed 到不了舵机速度寄存器）"
                  % (speeds, [round(s, 1) for s in stiff]))
            print("         前 3 帧: %s" % json.dumps(seq[:3], ensure_ascii=False)[:240])
            # 播完：DanceModifier 销毁（dance.h:104-106 requestDestroy），
            # 随后内置 Breath/Blink/Idle modifier 接管脸与头；
            # 舵机静止 200 ms 后自动释放扭矩（servo.cpp:59-66）
            last = seq[-1]
            self.state.yaw = max(YAW_MIN_RAW, min(YAW_MAX_RAW,
                              float(last.get("yawServo", {}).get("angle", 0)))) / 10.0
            self.state.pitch = max(PITCH_MIN_RAW, min(PITCH_MAX_RAW,
                              float(last.get("pitchServo", {}).get("angle", 0)))) / 10.0
            self.state.left_rgb = last.get("leftRgbColor")
            self.state.right_rgb = last.get("rightRgbColor")
            self.state.expression = {
                "leftEye": {"weight": last.get("leftEye", {}).get("weight", 0)},
                "rightEye": {"weight": last.get("rightEye", {}).get("weight", 0)},
                "mouth": {"weight": last.get("mouth", {}).get("weight", 0)},
            }
        elif msg_type == TEXT_MESSAGE:
            # ⚠️ 官方云对 TextMessage **会**剥 12 字节 MAC 前缀（web_socket.go:569）
            #    ⇒ 设备侧收到的就是纯文本，不能再切 12 字节
            text = payload.decode("utf-8", "ignore")
            print("  [device] textMessage <- %r" % text[:60])
        elif msg_type == ON_CAMERA:
            self.state.camera_on = True
        elif msg_type == OFF_CAMERA:
            self.state.camera_on = False
        elif msg_type == ON_AUDIO:
            self.state.audio_on = True
        elif msg_type == OFF_AUDIO:
            self.state.audio_on = False
        elif msg_type == ON_PHONE_SCREEN:
            self.state.phone_screen = True
        elif msg_type == OFF_PHONE_SCREEN:
            self.state.phone_screen = False
        elif msg_type == APP_LAN_ADDRESS:
            # 官方格式：纯 JSON {port, path, ip:[...]}，无 MAC 前缀
            try:
                info = json.loads(payload.decode("utf-8"))
            except Exception:
                info = parse_control(self.state.mac, payload) or {}
            print("  [device] appLanAddress <- %s（可切 LAN 直连）" % info)
        elif msg_type == GET_AVATAR_POSTURE:
            # ⚠️ 实测：官方固件**没有实现** GetAvatarPosture 的响应
            # （firmware/main/hal/hal_ws_avatar.cpp 的 DataType 枚举里根本没有 0x15，
            #   switch 落到 default: break）→ 官方 App 的 3D 预览是「发出即乐观显示」，
            #   不是设备真值回读。我们要做真值回读必须自己加固件分支或走 BLE。
            print("  [device] getAvatarPosture -> 官方固件未实现，"
                  "仅本地快照（乐观值）: %s" % self.state.snapshot())
        elif msg_type == REQUEST_CALL:
            print("  [device] requestCall（设备主动呼叫 App）")
        else:
            print("  [device] 未处理的类型 %s" % name)
        return out


def load_dance_payload(source: str):
    """加载 0x14 关键帧。

    source 可以是:
      - 一个 JSON 文件路径 (原有行为, 不变)
      - 一段 JSON 数组文本本身 (方便直接命令行联调)

    返回解析后的 list。
    """
    stripped = source.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return json.loads(stripped)
    with open(source, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 服务端：同时扮演「云」 ──────────────────────────────────────────────
class CloudSim:
    def __init__(self, device_mac: str):
        self.device = DeviceSim(device_mac)
        self.app_conns = []
        self.device_conn = None
        self.lan_endpoint = None      # 设备侧收到的 App 局域网地址
        self.session = 0

    @staticmethod
    def _request_path(ws, legacy_path=None) -> str:
        """websockets >= 14 的 asyncio 实现：路径在 ws.request.path；
        旧版 legacy 实现：路径在 handler 的第二个参数 / ws.path。三处都兜住。"""
        for cand in (
            getattr(getattr(ws, "request", None), "path", None),
            legacy_path,
            getattr(ws, "path", None),
        ):
            if cand:
                return str(cand)
        return ""

    async def handler(self, ws, path=None):
        # 从 query 取 deviceType
        try:
            from urllib.parse import urlparse, parse_qs
            p = urlparse(self._request_path(ws, path))
            q = parse_qs(p.query)
        except Exception:
            q = {}
        dtype = (q.get("deviceType") or [""])[0]
        did = (q.get("deviceId") or [""])[0]
        print("[cloud] 连接接入 deviceType=%s deviceId=%s" % (dtype or "?", did or "-"))

        if dtype == "StackChan":
            self.device_conn = ws
            print("[cloud] 设备已上线，MAC=%s" % self.device.state.mac)
            # 通知所有 App：设备在线
            await self._broadcast_to_apps(DEVICE_ONLINE, self.device.state.mac.encode())
        else:
            self.app_conns.append(ws)
            # 通知 App：设备在线
            await ws.send(encode_remote(DEVICE_ONLINE, self.device.state.mac.encode()))

        try:
            async for raw in ws:
                frame = decode_remote(bytes(raw))
                if not frame:
                    continue
                t, payload = frame
                if dtype == "StackChan":
                    # 设备侧消息：广播给所有 App（云只做中转，不改语义）
                    await self._broadcast_to_apps(t, payload)
                else:
                    # App → 设备：官方 server **只对这几类**剥掉 12 字节 MAC 前缀
                    # （server/internal/web_socket/web_socket.go readAppClientMessage）
                    #   :523 Opus / :537 Jpeg / :553 ControlAvatar,ControlMotion
                    #   :569 TextMessage / :588 RequestCall
                    # ⭐ **Dance(0x14) 不剥**（:740 `case Dance:` 直接原样转发）
                    #   —— 官方 App 也不加前缀（app/lib/view/home/dance.dart:193）
                    # 而 AppLanAddress 例外：它没有 MAC 前缀，是纯 JSON。
                    if t == APP_LAN_ADDRESS:
                        try:
                            self.lan_endpoint = json.loads(payload.decode("utf-8"))
                            print("[cloud] 记录 appLanAddress=%s" % self.lan_endpoint)
                        except Exception:
                            pass
                        forward = payload
                    elif t in CLOUD_STRIP_MAC and len(payload) >= 12:
                        forward = payload[12:]
                    else:
                        forward = payload
                    if self.device_conn:
                        await self.device_conn.send(encode_remote(t, forward))
                    else:
                        await ws.send(encode_remote(DEVICE_OFFLINE, b""))
        except Exception as e:
            print("[cloud] 连接异常：%s" % e)
        finally:
            if dtype == "StackChan":
                self.device_conn = None
                print("[cloud] 设备离线")
            elif ws in self.app_conns:
                self.app_conns.remove(ws)

    async def _virtual_device_loop(self):
        """内置一个虚拟设备：像真机一样以 deviceType=StackChan 连进来。
        这样没有真机也能完整演示「设备 ↔ 云 ↔ App」三段链路。
        设备自己处理指令并把结果回给云，云再广播给所有 App。"""
        await asyncio.sleep(0.6)
        url = "ws://127.0.0.1:%d/stackChan/ws?deviceType=StackChan&deviceId=%s" % (
            self.port, self.device.state.mac)
        try:
            async with websockets.connect(url) as ws:
                print("[virtual-device] 已上线（模拟真机）")
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        await ws.send(encode_remote(PING, b""))
                        continue
                    frame = decode_remote(bytes(raw))
                    if not frame:
                        continue
                    t, payload = frame
                    replies = self.device.handle(t, payload, ws)
                    for rt, rp in replies:
                        await ws.send(encode_remote(rt, rp))
                    # 状态变化也回传给云（云会广播给 App）
                    await ws.send(encode_remote(GET_AVATAR_POSTURE,
                                               json.dumps(self.device.state.snapshot()).encode()))
        except Exception as e:
            print("[virtual-device] 退出：%s" % e)

    async def _broadcast_to_apps(self, msg_type: int, payload: bytes):
        for app in list(self.app_conns):
            try:
                await app.send(encode_remote(msg_type, payload))
            except Exception:
                pass

    async def run(self, port):
        self.port = port
        asyncio.create_task(self._virtual_device_loop())
        async with websockets.serve(self.handler, "0.0.0.0", port,
                                    ping_interval=20, ping_timeout=20):
            print("[cloud] 监听 ws://0.0.0.0:%d/stackChan/ws" % port)
            print("[cloud] 设备 MAC=%s（虚拟设备将自动上线）" % self.device.state.mac)
            await asyncio.Future()


# ── App 角色（连服务器 + 可选起 LAN 服务） ──────────────────────────────
class AppSim:
    def __init__(self, port, device_mac, lan_port=None, lan_addr=None, dance=None):
        self.port = port
        self.device_mac = device_mac
        self.lan_port = lan_port
        self.lan_addr = lan_addr
        self.dance = dance      # 0x14 关键帧 JSON 文件路径
        self.device = DeviceSim(device_mac)

    async def run(self):
        url = "ws://127.0.0.1:%d/stackChan/ws?deviceType=App&deviceId=sim-app" % self.port
        async with websockets.connect(url) as ws:
            print("[app] 已连 %s" % url)
            # 告知设备自己的局域网地址
            # 官方格式（app/lib/network/local_area_network_service.dart LanServerEndpoint.encode）：
            #   纯 JSON，**无 MAC 前缀**，字段为 {port, path, ip:[...]}
            if self.lan_addr:
                ep = {"port": self.lan_port, "path": "/ws", "ip": self.lan_addr}
                await ws.send(encode_remote(APP_LAN_ADDRESS,
                                            json.dumps(ep).encode("utf-8")))
                print("[app] 已发送 appLanAddress %s" % ep)

            async def sender():
                # 演示：先 ping，再把 yaw 推到 -60°，再推表情
                await asyncio.sleep(1.0)
                await ws.send(encode_remote(PING, b""))
                await asyncio.sleep(0.5)
                await ws.send(encode_remote(CONTROL_MOTION,
                          build_control(self.device_mac, build_motion(-60, 22))))
                await asyncio.sleep(0.5)
                await ws.send(encode_remote(CONTROL_AVATAR,
                          build_control(self.device_mac,
                                        build_avatar({"rotation": 10}, {"rotation": 10},
                                                     {"rotation": -20, "weight": 60, "size": 80}))))
                await asyncio.sleep(0.5)
                await ws.send(encode_remote(GET_AVATAR_POSTURE, b""))
                if self.dance:
                    await asyncio.sleep(0.5)
                    seq = load_dance_payload(self.dance)
                    # ⭐ **0x14 不加 MAC 前缀**：官方云 readAppClientMessage 对 Dance
                    #    **不剥**前缀（web_socket.go:740），官方 App 也不加
                    #    （app/lib/view/home/dance.dart:193）
                    blob = json.dumps(seq, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8")
                    print("[app] 发送 0x14 dance：%d 关键帧 / %d B（无 MAC 前缀）"
                          % (len(seq), len(blob)))
                    await ws.send(encode_remote(DANCE, blob))
                    await asyncio.sleep(1.0)
                    await ws.send(encode_remote(GET_AVATAR_POSTURE, b""))
                await asyncio.sleep(3)
                await ws.send(encode_remote(CONTROL_MOTION,
                          build_control(self.device_mac, build_motion(100, 80))))
                await asyncio.sleep(3)
                await ws.close()

            task = asyncio.create_task(sender())
            async for raw in ws:
                frame = decode_remote(bytes(raw))
                if not frame:
                    continue
                t, payload = frame
                print("[app] 收到 %s %s" % (MSG_NAMES.get(t, "0x%02X" % t),
                                           payload[:120].decode("utf-8", "ignore")))
            try:
                await task
            except Exception:
                pass


# ── LAN 角色：设备反向连入 App 的局域网 WS 服务 ─────────────────────────
class LanSim:
    def __init__(self, target, device_mac):
        self.target = target
        self.device = DeviceSim(device_mac, lan=True)

    async def run(self):
        async with websockets.connect(self.target) as ws:
            print("[lan-device] 已连入 App 的局域网服务 %s" % self.target)
            await ws.send(encode_lan(PING))
            async for raw in ws:
                data = bytes(raw)
                frame = decode_lan(data) or decode_remote(data)
                if not frame:
                    continue
                t, payload = frame
                replies = self.device.handle(t, payload, ws)
                for rt, rp in replies:
                    await ws.send(encode_lan(rt, rp))


def main():
    ap = argparse.ArgumentParser(description="StackChan 协议模拟器")
    ap.add_argument("--role", choices=["device", "app", "lan"], required=True)
    ap.add_argument("--port", type=int, default=12800)
    ap.add_argument("--device-mac", default="68:ee:8f:d7:36:68")
    ap.add_argument("--connect", default="ws://127.0.0.1:9001/ws")
    ap.add_argument("--lan-port", type=int, default=9001)
    ap.add_argument("--lan-addr", default="192.168.2.100")
    ap.add_argument("--dance", help="0x14 关键帧 JSON 文件（由 prosody_to_motion.py 生成），"
                                   "也可直接传一段 JSON 数组文本")
    args = ap.parse_args()

    if args.role == "device":
        asyncio.run(CloudSim(args.device_mac).run(args.port))
    elif args.role == "app":
        asyncio.run(AppSim(args.port, args.device_mac, args.lan_port,
                           [args.lan_addr], args.dance).run())
    else:
        asyncio.run(LanSim(args.connect, args.device_mac).run())


if __name__ == "__main__":
    main()
