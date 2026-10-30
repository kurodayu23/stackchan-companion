#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""StackChan BLE 直连工具：没有服务器、没有 Wi-Fi，直接驱动真机。

用途
----
把 ``tools/prosody_to_motion.py`` 产出的「韵律 -> 身体」关键帧数组，
通过 BLE 逐帧写进真机的 Motion / Avatar / RGB 三个特征值，
等价于把「关键帧编译器 + 播放器」跑在真机侧闭环。

固件契约（全部来自 1.6.0 公开源码，file:line 见各常量注释）
----------------------------------------------------------
Motion  : {"type":"bleMotion","pitchServo":{"angle","speed"},"yawServo":{"angle","speed"}}
Avatar  : {"type":"bleAvatar","leftEye":{x,y,rotation,weight,size},"rightEye":{...},"mouth":{...}}
RGB     : {"leftRgbColor","leftRgbDuration","rightRgbColor","rightRgbDuration"}（无 type）
Config  : {"cmd":"setWifi","data":{"ssid","password"}}

依赖
----
仅 ``bleak``（Python 3.12）::

    py -3.12 -m pip install bleak

安全边界
--------
* 只写运行时状态，不写 flash / 不 OTA / 不碰 bootloader。
* ``set_wifi()`` 默认不执行，必须显式调用（或 ``--wifi`` 子命令）才会写 config 特征。

用法
----
    py -3.12 tools/stackchan_ble.py scan
    py -3.12 tools/stackchan_ble.py connect 68:ee:8f:d7:36:68
    py -3.12 tools/stackchan_ble.py demo 68:ee:8f:d7:36:68
    py -3.12 tools/stackchan_ble.py play 68:ee:8f:d7:36:68 keyframes.json
    py -3.12 tools/stackchan_ble.py selftest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Windows 控制台默认 GBK，设备名里可能带 U+207A 之类字符 ⇒ 强制 UTF-8 且不抛异常
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover
    print("缺少依赖 bleak，请执行: py -3.12 -m pip install bleak", file=sys.stderr)
    raise SystemExit(2)

# ---------------------------------------------------------------------------
# BLE 常量
# ---------------------------------------------------------------------------

# Service UUID (常规)：DANCE 应用启动 BLE 外设时使用
# firmware/main/hal/hal_ble.cpp:328-332  Hal::startBleServer() -> ble_init(false)
SERVICE_UUID = "e2e5e5e0-1234-5678-1234-56789abcdef0"
# Service UUID (配网)：AppSetup 启动 app config server 时使用
# firmware/main/hal/hal_ble.cpp:599-608  Hal::startAppConfigServer() -> ble_init(true)
SERVICE_UUID_ALT = "e2e5e5ff-1234-5678-1234-56789abcdef0"

# 特征 UUID：firmware/main/hal/utils/bleprph/bleprph.h:51-65
MOTION_CHAR_UUID = "e2e5e5e1-1234-5678-1234-56789abcdef0"
AVATAR_CHAR_UUID = "e2e5e5e2-1234-5678-1234-56789abcdef0"
CONFIG_CHAR_UUID = "e2e5e5e3-1234-5678-1234-56789abcdef0"
RGB_CHAR_UUID = "e2e5e5e4-1234-5678-1234-56789abcdef0"

# 四个特征的属性都是 READ | WRITE | NOTIFY（没有 WRITE_NO_RSP，写入必须等响应）
# firmware/main/hal/utils/bleprph/gatt_svr.c:91 / 98 / 105 / 112
CHAR_PROPERTIES = "read,write,notify"

# 单条 JSON 最大 2048 字节：firmware/main/hal/utils/bleprph/bleprph.h:68
MAX_JSON_LEN = 2048

# 广播设备名 "StackChan" 放在扫描响应包：firmware/main/hal/utils/bleprph/bleprph.c:698
DEVICE_NAME = "StackChan"
# 扫描响应里的 manufacturer data = E5 02 <MAC[6]>：firmware/main/hal/utils/bleprph/bleprph.c:242-247
MFG_PREFIX = "e502"

# 舵机限位（0.1 度单位）
# yaw ±128.0°、pitch 3.0°~87.0°，来自固件实测语义
YAW_LIMIT = (-1280, 1280)
PITCH_LIMIT = (30, 870)

# 舵机默认速度：App 侧 MotionDataItem.speed 默认 500
# app/lib/model/expression_data.dart:115
DEFAULT_SERVO_SPEED = 500

# App 写 RGB 时用的时长：app/lib/util/blue_util.dart:977-980
DEFAULT_RGB_DURATION = 0.3

# 固件丢弃「上一帧还没被消费就又来一帧」的写入
# firmware/main/apps/app_dance/app_dance.cpp:99-116（update_flag 守卫）
MIN_FRAME_GAP_S = 0.012


# ---------------------------------------------------------------------------
# 纯函数：按固件真实格式构造 JSON（可离线自测）
# ---------------------------------------------------------------------------


def _deg_to_raw(deg: float) -> int:
    """度 -> 固件的 0.1 度整数单位。"""
    return int(round(float(deg) * 10.0))


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def build_motion_json(yaw_deg: float, pitch_deg: float, speed: int = DEFAULT_SERVO_SPEED) -> str:
    """构造 Motion 特征 JSON。

    固件解析：firmware/main/stackchan/json/json_helper.cpp:117-139
    update_servo 的优先级是 rotate > (angle+speed) > (angle+spring) > angle，
    所以这里只发 angle + speed，绝不发 rotate。
    """
    yaw = _clamp(_deg_to_raw(yaw_deg), *YAW_LIMIT)
    pitch = _clamp(_deg_to_raw(pitch_deg), *PITCH_LIMIT)
    payload = {
        "type": "bleMotion",
        "pitchServo": {"angle": pitch, "speed": int(speed)},
        "yawServo": {"angle": yaw, "speed": int(speed)},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _avatar_element(item: Dict[str, Any]) -> Dict[str, int]:
    """单个表情元素：只保留固件认的 5 个字段。

    固件解析：firmware/main/stackchan/json/json_helper.cpp:16-39
    x/y 必须同时是 int 才生效（json_helper.cpp:18），所以一律转 int。
    weight 越大越睁开（0 全闭，100 全开）。
    """
    return {
        "x": int(item.get("x", 0)),
        "y": int(item.get("y", 0)),
        "rotation": int(item.get("rotation", 0)),
        "weight": int(item.get("weight", 0)),
        "size": int(item.get("size", 0)),
    }


def build_avatar_json(
    left_eye: Dict[str, Any],
    right_eye: Dict[str, Any],
    mouth: Dict[str, Any],
) -> str:
    """构造 Avatar 特征 JSON。

    固件解析：firmware/main/stackchan/json/json_helper.cpp:41-68
    只读 leftEye / rightEye / mouth 三个对象，不读 type。
    """
    payload = {
        "type": "bleAvatar",
        "leftEye": _avatar_element(left_eye),
        "rightEye": _avatar_element(right_eye),
        "mouth": _avatar_element(mouth),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_rgb_json(left_hex: str, right_hex: str, duration: float = DEFAULT_RGB_DURATION) -> str:
    """构造 RGB 特征 JSON。

    固件解析：firmware/main/stackchan/json/json_helper.cpp:236-262
    只认 leftRgbColor / leftRgbDuration / rightRgbColor / rightRgbDuration，
    没有 type 字段。duration 判的是 is<float>()（json_helper.cpp:249/256），
    所以这里强制转 float，避免写成整数 JSON 数字。
    """
    payload = {
        "leftRgbColor": str(left_hex),
        "leftRgbDuration": float(duration),
        "rightRgbColor": str(right_hex),
        "rightRgbDuration": float(duration),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_wifi_json(ssid: str, password: str) -> str:
    """构造 Config 特征 JSON（Wi-Fi 配网）。

    固件解析：firmware/main/hal/hal_ble.cpp:458-476
    cmd 取值 setWifi / getWifiStatus / handshake；data 必须含 ssid 与 password 字符串。
    """
    payload = {"cmd": "setWifi", "data": {"ssid": str(ssid), "password": str(password)}}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_keyframe_payloads(frame: Dict[str, Any], rgb_duration: float = DEFAULT_RGB_DURATION):
    """把一帧关键帧拆成 (motion_json, avatar_json, rgb_json)。

    帧结构来自 tools/prosody_to_motion.py 的 0x14 关键帧：
    leftEye/rightEye/mouth（x,y,rotation,weight,size）、
    yawServo/pitchServo（angle 单位 0.1 度 + speed）、
    leftRgbColor/rightRgbColor（#RRGGBB）、durationMs。
    """
    yaw = frame.get("yawServo") or {}
    pitch = frame.get("pitchServo") or {}
    motion = build_motion_json(
        yaw.get("angle", 0) / 10.0,
        pitch.get("angle", 0) / 10.0,
        int(yaw.get("speed", DEFAULT_SERVO_SPEED)),
    )
    avatar = build_avatar_json(
        frame.get("leftEye") or {},
        frame.get("rightEye") or {},
        frame.get("mouth") or {},
    )
    rgb = build_rgb_json(
        frame.get("leftRgbColor", "#FFFFFF"),
        frame.get("rightRgbColor", "#FFFFFF"),
        rgb_duration,
    )
    return motion, avatar, rgb


def load_keyframes(path: str) -> List[Dict[str, Any]]:
    """读关键帧数组。兼容裸数组与 {"keyframes": [...]} 两种形态。"""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("keyframes") or data.get("frames") or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: 顶层不是关键帧数组")
    return data


# ---------------------------------------------------------------------------
# 异步底层
# ---------------------------------------------------------------------------

_LOOP: Optional[asyncio.AbstractEventLoop] = None
_CLIENT: Optional[BleakClient] = None
_CHARS: Dict[str, Any] = {}


def _loop() -> asyncio.AbstractEventLoop:
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


def _run(coro):
    return _loop().run_until_complete(coro)


def _norm_uuid(value: Any) -> str:
    return str(value).lower()


async def _scan_async(timeout: float) -> List[Dict[str, Any]]:
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    out: List[Dict[str, Any]] = []
    for key, value in found.items():
        if isinstance(value, tuple):
            dev, adv = value
        elif isinstance(value, str):
            dev, adv = None, None
        else:
            dev, adv = None, value
        address = dev.address if dev is not None and hasattr(dev, "address") else str(key)
        name = getattr(adv, "local_name", None)
        if not name and dev is not None:
            name = getattr(dev, "name", None)
        out.append(
            {
                "address": address,
                "name": name,
                "rssi": getattr(adv, "rssi", None),
                "service_uuids": [str(u).lower() for u in (getattr(adv, "service_uuids", None) or [])],
                "manufacturer_data": {
                    str(k): v.hex() for k, v in (getattr(adv, "manufacturer_data", None) or {}).items()
                },
                "service_data": {
                    str(k): v.hex() for k, v in (getattr(adv, "service_data", None) or {}).items()
                },
                "tx_power": getattr(adv, "tx_power", None),
            }
        )
    out.sort(key=lambda d: (d["rssi"] is None, -(d["rssi"] or -999)))
    return out


async def _connect_async(address: str, timeout: float = 20.0) -> Dict[str, Any]:
    client = BleakClient(address, timeout=timeout)
    await client.connect()
    global _CLIENT, _CHARS
    _CLIENT = client
    _CHARS = {}

    inventory: Dict[str, Any] = {"address": address, "services": []}
    for service in client.services:
        svc = {
            "uuid": _norm_uuid(service.uuid),
            "handle": service.handle,
            "characteristics": [],
        }
        for char in service.characteristics:
            props = ",".join(sorted(char.properties or []))
            svc["characteristics"].append(
                {
                    "uuid": _norm_uuid(char.uuid),
                    "handle": char.handle,
                    "properties": props,
                    "description": char.description,
                }
            )
            _CHARS[_norm_uuid(char.uuid)] = char
        inventory["services"].append(svc)
    return inventory


async def _write_async(char_uuid: str, payload: str) -> None:
    if _CLIENT is None:
        raise RuntimeError("尚未连接，请先调用 connect(address)")
    char = _CHARS.get(_norm_uuid(char_uuid))
    if char is None:
        raise RuntimeError(f"设备上没有特征 {char_uuid}（当前可用: {sorted(_CHARS)}）")
    data = payload.encode("utf-8")
    if len(data) > MAX_JSON_LEN:
        raise ValueError(f"载荷 {len(data)} B 超过单条上限 {MAX_JSON_LEN} B")
    # 特征没有 WRITE_NO_RSP（gatt_svr.c:91/98/105/112），必须用带响应的写
    await _CLIENT.write_gatt_char(char, data, response=True)


async def _disconnect_async() -> None:
    global _CLIENT, _CHARS
    if _CLIENT is not None:
        try:
            await _CLIENT.disconnect()
        finally:
            _CLIENT = None
            _CHARS = {}


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def scan(timeout: float = 5.0) -> List[Dict[str, Any]]:
    """扫描并列出所有设备（名字、地址、RSSI、广播的 service UUID、manufacturer data）。"""
    return _run(_scan_async(timeout))


def find_device(timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """自动找出 StackChan：按名字 / service UUID / manufacturer data 三重匹配。

    manufacturer data = ``E5 02 <MAC[6]>``（bleprph.c:242-247），
    service UUID 只有开了 BLE 外设的 DANCE / 配网两种模式才会广播（bleprph.c:261-272）。
    """
    for dev in scan(timeout):
        if dev["name"] == DEVICE_NAME:
            return dev
        if SERVICE_UUID in dev["service_uuids"] or SERVICE_UUID_ALT in dev["service_uuids"]:
            return dev
        if any(v.startswith(MFG_PREFIX) for v in dev["manufacturer_data"].values()):
            return dev
    return None


def connect(address: str) -> Dict[str, Any]:
    """连接设备并列出所有 service/characteristic 及其属性（read/write/notify/indicate）。"""
    return _run(_connect_async(address))


def disconnect() -> None:
    """断开连接。"""
    _run(_disconnect_async())


def send_motion(yaw_deg: float, pitch_deg: float, speed: int = DEFAULT_SERVO_SPEED) -> None:
    """写 motion 特征：左右转头。角度单位为度，内部换算成固件的 0.1 度。"""
    payload = build_motion_json(yaw_deg, pitch_deg, speed)
    _run(_write_async(MOTION_CHAR_UUID, payload))


def send_avatar(
    left_eye: Dict[str, Any],
    right_eye: Dict[str, Any],
    mouth: Dict[str, Any],
) -> None:
    """写 avatar 特征：三个 dict，各含 x, y, rotation, weight, size。"""
    payload = build_avatar_json(left_eye, right_eye, mouth)
    _run(_write_async(AVATAR_CHAR_UUID, payload))


def send_rgb(left_hex: str, right_hex: str, duration: float = DEFAULT_RGB_DURATION) -> None:
    """写 rgb 特征：左右灯颜色与持续时间。"""
    payload = build_rgb_json(left_hex, right_hex, duration)
    _run(_write_async(RGB_CHAR_UUID, payload))


def play_keyframes(keyframes_json_path: str, fps: int = 25) -> None:
    """核心：读关键帧数组，按 durationMs 逐帧写 motion/avatar/rgb。

    这是我们自己的「关键帧编译器 + 播放器」跑在真机上：
    BLE 没有 0x14 那样的整段关键帧时间轴，必须自己按帧发。
    """
    frames = load_keyframes(keyframes_json_path)
    fallback = 1000.0 / max(1, fps)
    for index, frame in enumerate(frames):
        motion, avatar, rgb = build_keyframe_payloads(frame)
        _run(_write_async(MOTION_CHAR_UUID, motion))
        _run(_write_async(AVATAR_CHAR_UUID, avatar))
        _run(_write_async(RGB_CHAR_UUID, rgb))
        duration_ms = frame.get("durationMs") or fallback
        time.sleep(max(float(duration_ms) / 1000.0, MIN_FRAME_GAP_S))


def set_wifi(ssid: str, password: str) -> None:
    """写 config 特征（默认不执行，只在用户明确要求时才调用）。"""
    payload = build_wifi_json(ssid, password)
    _run(_write_async(CONFIG_CHAR_UUID, payload))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_scan(devices: Sequence[Dict[str, Any]]) -> None:
    print(f"{'ADDRESS':<20} {'NAME':<24} {'RSSI':>5}  SERVICE UUIDS / MFG")
    print("-" * 100)
    for dev in devices:
        uuids = ",".join(dev["service_uuids"]) or "-"
        mfg = ",".join(f"{k}:{v}" for k, v in dev["manufacturer_data"].items()) or "-"
        print(f"{dev['address']:<20} {str(dev['name'] or '-'):<24} {str(dev['rssi']):>5}  {uuids} | mfg {mfg}")
    print(f"\n共 {len(devices)} 个设备")
    hit = [d for d in devices if d["name"] == DEVICE_NAME
           or SERVICE_UUID in d["service_uuids"]
           or SERVICE_UUID_ALT in d["service_uuids"]
           or any(v.startswith(MFG_PREFIX) for v in d["manufacturer_data"].values())]
    if hit:
        print(f"★ 疑似 StackChan: {[d['address'] for d in hit]}")
    else:
        print("★ 未发现 StackChan 广播（设备未开 BLE 外设时就是这样，见文档第 2.4 节）")


def _print_inventory(inventory: Dict[str, Any]) -> None:
    print(f"已连接: {inventory['address']}")
    for svc in inventory["services"]:
        print(f"\nService {svc['uuid']}  (handle {svc['handle']})")
        for char in svc["characteristics"]:
            print(f"  - {char['uuid']}  handle={char['handle']}  [{char['properties']}]")


def _selftest() -> int:
    """离线自测：验证构造出来的 JSON 与固件解析规则一致。"""
    failures: List[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  :: ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    print("=" * 72)
    print("自检：BLE 载荷构造")
    print("=" * 72)

    motion = json.loads(build_motion_json(30.0, 45.0))
    check("motion 顶层字段 = type/pitchServo/yawServo",
          set(motion) == {"type", "pitchServo", "yawServo"}, str(sorted(motion)))
    check("motion type = bleMotion", motion["type"] == "bleMotion", motion["type"])
    check("motion angle 单位 = 0.1 度",
          motion["yawServo"]["angle"] == 300 and motion["pitchServo"]["angle"] == 450,
          f"yaw={motion['yawServo']['angle']} pitch={motion['pitchServo']['angle']}")
    check("motion 不含 rotate（否则固件走 rotate 分支）",
          "rotate" not in motion["yawServo"] and "rotate" not in motion["pitchServo"])
    check("motion speed 是 int", isinstance(motion["yawServo"]["speed"], int))

    clamped = json.loads(build_motion_json(999.0, -50.0))
    check("yaw 限位 ±1280", clamped["yawServo"]["angle"] == 1280, str(clamped["yawServo"]["angle"]))
    check("pitch 限位 30..870", clamped["pitchServo"]["angle"] == 30, str(clamped["pitchServo"]["angle"]))

    avatar = json.loads(build_avatar_json({"x": 1, "y": 2, "rotation": 0, "weight": 90, "size": 5},
                                           {"x": 0, "y": 0, "rotation": 0, "weight": 0, "size": 0},
                                           {"x": 0, "y": 0, "rotation": 0, "weight": 30, "size": 0}))
    check("avatar type = bleAvatar", avatar["type"] == "bleAvatar", avatar["type"])
    check("avatar 恰好 3 个元素", set(avatar) == {"type", "leftEye", "rightEye", "mouth"},
          str(sorted(avatar)))
    check("avatar 每个元素恰好 5 个字段",
          all(set(e) == {"x", "y", "rotation", "weight", "size"} for e in
              (avatar["leftEye"], avatar["rightEye"], avatar["mouth"])))
    check("avatar 字段都是 int（x/y 必须同时是 int 才生效）",
          all(isinstance(v, int) for e in (avatar["leftEye"], avatar["rightEye"], avatar["mouth"])
              for v in e.values()))
    check("weight 越大越睁开（0 全闭 / 100 全开）",
          avatar["leftEye"]["weight"] == 90 and avatar["rightEye"]["weight"] == 0)

    rgb = json.loads(build_rgb_json("#FF0000", "#00FF00", 0.3))
    check("rgb 无 type 字段", "type" not in rgb, str(sorted(rgb)))
    check("rgb 恰好 4 个字段",
          set(rgb) == {"leftRgbColor", "leftRgbDuration", "rightRgbColor", "rightRgbDuration"},
          str(sorted(rgb)))
    check("rgb duration 是浮点（固件判 is<float>）",
          isinstance(rgb["leftRgbDuration"], float) and isinstance(rgb["rightRgbDuration"], float),
          f"{rgb['leftRgbDuration']!r}")

    wifi = json.loads(build_wifi_json("ssid", "pw"))
    check("config cmd = setWifi", wifi["cmd"] == "setWifi", wifi["cmd"])
    check("config data 含 ssid/password 字符串",
          isinstance(wifi["data"]["ssid"], str) and isinstance(wifi["data"]["password"], str))

    frame = {
        "leftEye": {"x": 0, "y": 0, "rotation": 0, "weight": 80, "size": 0},
        "rightEye": {"x": 0, "y": 0, "rotation": 0, "weight": 80, "size": 0},
        "mouth": {"x": 0, "y": 0, "rotation": 0, "weight": 20, "size": 0},
        "yawServo": {"angle": -250, "speed": 500},
        "pitchServo": {"angle": 450, "speed": 500},
        "leftRgbColor": "#FFAA00",
        "rightRgbColor": "#00AAFF",
        "durationMs": 40,
    }
    m, a, r = build_keyframe_payloads(frame)
    mj, aj, rj = json.loads(m), json.loads(a), json.loads(r)
    check("关键帧 -> motion 的 yaw 换算正确", mj["yawServo"]["angle"] == -250, str(mj["yawServo"]))
    check("关键帧 -> motion 的 pitch 换算正确", mj["pitchServo"]["angle"] == 450, str(mj["pitchServo"]))
    check("关键帧 -> avatar 的 weight 透传", aj["leftEye"]["weight"] == 80)
    check("关键帧 -> rgb 的颜色透传",
          rj["leftRgbColor"] == "#FFAA00" and rj["rightRgbColor"] == "#00AAFF")

    check("所有载荷 <= 2048 B",
          all(len(p.encode("utf-8")) <= MAX_JSON_LEN for p in (m, a, r)))

    print()
    print(f"自检结果：{'全部通过' if not failures else '失败 ' + str(len(failures)) + ' 项: ' + ', '.join(failures)}")
    return 0 if not failures else 1


def _resolve_address(address: Optional[str], timeout: float = 10.0) -> str:
    """没给地址就自动扫，扫不到就明确告诉用户去开 DANCE 应用。"""
    if address:
        return address
    print("未指定地址，正在自动扫描 StackChan ...")
    dev = find_device(timeout)
    if dev is None:
        print(
            "未发现 StackChan 广播。\n"
            "原因：固件只在 DANCE 应用打开时才启动 BLE 外设（app_dance/app_dance.cpp:48）。\n"
            "请在设备屏幕上点 Skip 进入启动器，再点 DANCE 图标，然后重跑本命令。",
            file=sys.stderr,
        )
        raise SystemExit(3)
    print(f"找到 StackChan: {dev['address']}  rssi={dev['rssi']}  name={dev['name']}")
    return dev["address"]


def _cmd_demo(address: str) -> int:
    """发一组固定动作，让设备做出可见反应。"""
    connect(address)
    print("\n[1/6] 转头：yaw -25°")
    send_motion(-25.0, 45.0)
    time.sleep(1.0)
    print("[2/6] 转头：yaw +25°")
    send_motion(25.0, 45.0)
    time.sleep(1.0)
    print("[3/6] 回到中位并抬低头")
    send_motion(0.0, 60.0)
    time.sleep(1.0)
    print("[4/6] 闭眼（weight=0）")
    send_avatar({"x": 0, "y": 0, "rotation": 0, "weight": 0, "size": 0},
                {"x": 0, "y": 0, "rotation": 0, "weight": 0, "size": 0},
                {"x": 0, "y": 0, "rotation": 0, "weight": 0, "size": 0})
    time.sleep(1.0)
    print("[5/6] 睁眼（weight=100）")
    send_avatar({"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
                {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0},
                {"x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0})
    time.sleep(1.0)
    print("[6/6] RGB：左红右蓝")
    send_rgb("#FF0000", "#0000FF", 2.0)
    time.sleep(2.0)
    disconnect()
    print("\n完成")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="StackChan BLE 直连工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描设备")
    p_scan.add_argument("--timeout", type=float, default=10.0)

    p_conn = sub.add_parser("connect", help="连接并列出特征")
    p_conn.add_argument("address", nargs="?", help="省略则自动扫描查找")

    p_demo = sub.add_parser("demo", help="发一组固定动作")
    p_demo.add_argument("address", nargs="?", help="省略则自动扫描查找")

    p_play = sub.add_parser("play", help="播放关键帧")
    p_play.add_argument("--address", help="省略则自动扫描查找")
    p_play.add_argument("keyframes")
    p_play.add_argument("--fps", type=int, default=25)

    p_wifi = sub.add_parser("wifi", help="写 config 特征配 Wi-Fi（需显式调用）")
    p_wifi.add_argument("--address", help="省略则自动扫描查找")
    p_wifi.add_argument("ssid")
    p_wifi.add_argument("password")

    sub.add_parser("selftest", help="离线自测载荷构造")

    args = ap.parse_args(argv)

    if args.cmd == "scan":
        _print_scan(scan(args.timeout))
        return 0

    if args.cmd == "selftest":
        return _selftest()

    if args.cmd == "connect":
        inventory = connect(_resolve_address(args.address))
        _print_inventory(inventory)
        disconnect()
        return 0

    if args.cmd == "demo":
        return _cmd_demo(_resolve_address(args.address))

    if args.cmd == "play":
        connect(_resolve_address(args.address))
        play_keyframes(args.keyframes, args.fps)
        disconnect()
        return 0

    if args.cmd == "wifi":
        connect(_resolve_address(args.address))
        set_wifi(args.ssid, args.password)
        time.sleep(3.0)
        disconnect()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
