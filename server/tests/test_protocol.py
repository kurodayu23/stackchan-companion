# -*- coding: utf-8 -*-
"""test_protocol —— 帧编解码 + 0x14 校验（含变异用例）。

协议事实出处见 stackchan_ai/protocol.py 的模块文档。
"""

from __future__ import annotations

import json
import unittest

from server.stackchan_ai import protocol


class FrameCodecTest(unittest.TestCase):
    """帧格式 [Type(1)][Length(4 BE)][Payload]。"""

    def test_frame_layout(self):
        frame = protocol.encode_frame(protocol.DANCE, b"[]")
        self.assertEqual(len(frame), 7)
        self.assertEqual(frame[0], protocol.DANCE)
        self.assertEqual(frame[1:5], b"\x00\x00\x00\x02")
        self.assertEqual(frame[5:], b"[]")

    def test_round_trip(self):
        payload = json.dumps([{"durationMs": 40}]).encode("utf-8")
        frame = protocol.encode_frame(protocol.DANCE, payload)
        decoded = protocol.decode_frame(frame)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded[0], protocol.DANCE)
        self.assertEqual(decoded[1], payload)
        self.assertEqual(protocol.frame_length(payload), len(frame))

    def test_decode_rejects_truncated(self):
        frame = protocol.encode_frame(protocol.DANCE, b"[]")
        self.assertIsNone(protocol.decode_frame(frame[:-1]))
        self.assertIsNone(protocol.decode_frame(b""))
        self.assertIsNone(protocol.decode_frame(b"\x14\x00"))

    def test_empty_payload_ok(self):
        decoded = protocol.decode_frame(protocol.encode_frame(protocol.PING))
        self.assertEqual(decoded, (protocol.PING, b""))


class MacPrefixTest(unittest.TestCase):
    """只有 6 类剥 12 字节 MAC；0x14 不剥。"""

    MAC = "68ee8fd73668"

    def test_normalize_mac(self):
        self.assertEqual(protocol.normalize_mac("68:EE:8F:D7:36:68"), self.MAC)
        self.assertEqual(protocol.normalize_mac("68-ee-8f-d7-36-68"), self.MAC)
        self.assertEqual(protocol.normalize_mac("nope"), "")
        self.assertEqual(protocol.normalize_mac("68ee8fd7366"), "")

    def test_strip_for_prefixed_types(self):
        body = b'{"type":"avatar"}'
        payload = protocol.build_control_payload(self.MAC, {"type": "avatar"})
        mac, stripped = protocol.split_mac_prefix(protocol.CONTROL_AVATAR, payload)
        self.assertEqual(mac, self.MAC)
        self.assertEqual(stripped, body)

    def test_dance_is_not_stripped(self):
        sequence = [protocol.sample_keyframe()]
        payload = protocol.build_dance_payload(sequence)
        mac, body = protocol.split_mac_prefix(protocol.DANCE, payload)
        self.assertIsNone(mac)
        self.assertEqual(body, payload)
        # 顶层必须是 JSON 数组，**不能**有 MAC 前缀
        self.assertTrue(payload.startswith(b"["))

    def test_text_payload_has_mac_prefix(self):
        payload = protocol.build_text_payload(self.MAC, "你好")
        mac, body = protocol.split_mac_prefix(protocol.TEXT_MESSAGE, payload)
        self.assertEqual(mac, self.MAC)
        self.assertEqual(body.decode("utf-8"), "你好")

    def test_parse_text_body_tolerates_plain_and_json(self):
        self.assertEqual(protocol.parse_text_body("你好呀".encode("utf-8")), "你好呀")
        self.assertEqual(
            protocol.parse_text_body(json.dumps({"msg": "hi"}).encode("utf-8")), "hi")
        self.assertEqual(protocol.parse_text_body(b""), "")


class DanceValidationTest(unittest.TestCase):
    """0x14 校验（对照固件 json_helper.cpp）。"""

    def setUp(self):
        self.sequence = [protocol.sample_keyframe()]

    def test_valid_sequence_passes(self):
        self.assertEqual(protocol.validate_dance_sequence(self.sequence), [])

    def test_mutation_top_level_object_is_rejected(self):
        """⭐ 变异用例：把 0x14 包成对象 → 固件 json_helper.cpp:192-195 会直接 return。"""
        wrapped = {"frames": self.sequence}
        errors = protocol.validate_dance_sequence(wrapped)
        self.assertTrue(errors)
        self.assertIn("array", errors[0])

    def test_mutation_missing_key_is_rejected(self):
        broken = dict(self.sequence[0])
        broken.pop("mouth")
        errors = protocol.validate_dance_sequence([broken])
        self.assertTrue(errors)
        self.assertIn("mouth", errors[0])

    def test_mutation_float_xy_is_rejected(self):
        """x/y 必须是 int（json_helper.cpp:18 两者都必须是 int 才 setPosition）。"""
        broken = json.loads(json.dumps(self.sequence[0]))
        broken["leftEye"]["x"] = 1.5
        broken["leftEye"]["y"] = 2.5
        errors = protocol.validate_dance_sequence([broken])
        self.assertTrue(errors)
        self.assertIn("must be an int", errors[0])

    def test_mutation_bool_is_not_int(self):
        broken = json.loads(json.dumps(self.sequence[0]))
        broken["mouth"]["weight"] = True
        errors = protocol.validate_dance_sequence([broken])
        self.assertTrue(errors)

    def test_mutation_yaw_out_of_limit_is_rejected(self):
        broken = json.loads(json.dumps(self.sequence[0]))
        broken["yawServo"]["angle"] = 2000          # 固件限位 ±1280
        errors = protocol.validate_dance_sequence([broken])
        self.assertTrue(errors)
        self.assertIn("out of firmware limit", errors[0])

    def test_mutation_pitch_out_of_limit_is_rejected(self):
        broken = json.loads(json.dumps(self.sequence[0]))
        broken["pitchServo"]["angle"] = 900         # 固件限位 30..870
        errors = protocol.validate_dance_sequence([broken])
        self.assertTrue(errors)
        self.assertIn("out of firmware limit", errors[0])

    def test_mutation_duration_float_is_rejected(self):
        broken = json.loads(json.dumps(self.sequence[0]))
        broken["durationMs"] = 40.0
        errors = protocol.validate_dance_sequence([broken])
        self.assertTrue(errors)

    def test_empty_array_is_rejected(self):
        self.assertTrue(protocol.validate_dance_sequence([]))

    def test_avatar_object_validation(self):
        obj = {"leftEye": protocol.sample_keyframe()["leftEye"],
               "rightEye": protocol.sample_keyframe()["rightEye"],
               "mouth": protocol.sample_keyframe()["mouth"]}
        self.assertEqual(protocol.validate_avatar_object(obj), [])
        obj["mouth"]["x"] = 0.5
        self.assertTrue(protocol.validate_avatar_object(obj))


class SummaryTest(unittest.TestCase):
    def test_frames_summary(self):
        kfs = [protocol.sample_keyframe(yaw=100, pitch=400),
               protocol.sample_keyframe(yaw=-100, pitch=800)]
        stats = protocol.frames_summary(kfs)
        self.assertEqual(stats["frameCount"], 2)
        self.assertEqual(stats["durationMsTotal"], 1600)
        self.assertEqual(stats["yawRange"], [-100, 100])
        self.assertEqual(stats["pitchRange"], [400, 800])

    def test_eye_and_mouth_polarity(self):
        """眼睛 weight 越大越睁开；嘴 weight 越大越张开。"""
        self.assertGreater(protocol.eye_openness(100), protocol.eye_openness(0))
        self.assertGreater(protocol.mouth_openness(100), protocol.mouth_openness(0))


if __name__ == "__main__":
    unittest.main()
