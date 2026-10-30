# -*- coding: utf-8 -*-
"""test_memory —— 关系档案读写（临时目录）。

隐私边界的断言：
    - 档案只落在 private/ 下；
    - 档案名非法（含路径穿越）直接拒绝；
    - 疑似密钥的字段写不进去。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.stackchan_ai.memory import PrivacyError, ProfileStore


class ProfileStoreTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.private = Path(self._tmp.name) / "private"
        self.store = ProfileStore(self.private)

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_and_load_round_trip(self):
        path = self.store.save("demo", {"nickname": "阿灯", "likes": ["咖啡"]})
        self.assertTrue(path.exists())
        self.assertTrue(str(path).startswith(str(self.private.resolve())))
        loaded = self.store.load("demo")
        self.assertEqual(loaded["nickname"], "阿灯")
        self.assertEqual(loaded["likes"], ["咖啡"])

    def test_load_missing_returns_default(self):
        self.assertEqual(self.store.load("nobody"), {})
        self.assertEqual(self.store.load("nobody", default={"a": 1}), {"a": 1})

    def test_update_merges(self):
        self.store.save("demo", {"a": 1})
        merged = self.store.update("demo", b=2)
        self.assertEqual(merged["a"], 1)
        self.assertEqual(merged["b"], 2)

    def test_append_event_and_read(self):
        self.store.append_event("demo", {"type": "dialogue", "user": "在吗"})
        self.store.append_event("demo", {"type": "dialogue", "user": "在的"})
        events = self.store.read_events("demo")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["user"], "在吗")
        self.assertIn("ts", events[0])

    def test_list_profiles(self):
        self.store.save("alpha", {"x": 1})
        self.store.save("beta", {"x": 2})
        self.assertEqual(self.store.list_profiles(), ["alpha", "beta"])

    def test_delete(self):
        self.store.save("demo", {"x": 1})
        self.assertTrue(self.store.delete("demo"))
        self.assertFalse(self.store.delete("demo"))

    def test_file_is_valid_json(self):
        path = self.store.save("demo", {"x": 1})
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["x"], 1)


class PrivacyBoundaryTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = ProfileStore(Path(self._tmp.name) / "private")

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_traversal_name_is_rejected(self):
        for bad in ("../evil", "a/b", "", "x" * 100, "a b"):
            with self.assertRaises(PrivacyError):
                self.store.save(bad, {"x": 1})

    def test_secret_field_is_rejected(self):
        with self.assertRaises(PrivacyError):
            self.store.save("demo", {"api_key": "sk-should-never-be-stored"})
        with self.assertRaises(PrivacyError):
            self.store.save("demo", {"profile": {"access_token": "abc"}})

    def test_nested_secret_is_rejected(self):
        with self.assertRaises(PrivacyError):
            self.store.append_event("demo", {"payload": [{"password": "x"}]})

    def test_written_file_is_inside_private(self):
        path = self.store.save("demo", {"x": 1})
        self.assertTrue(str(path.resolve()).startswith(str(self.store.private_dir)))

    def test_describe_does_not_leak_content(self):
        self.store.save("demo", {"note": "私人内容"})
        text = str(self.store.describe())
        self.assertNotIn("私人内容", text)


if __name__ == "__main__":
    unittest.main()
