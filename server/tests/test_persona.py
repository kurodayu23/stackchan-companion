# -*- coding: utf-8 -*-
"""test_persona —— 人格包三层合并（通用包 / 私人层 / 内置兜底）。

断言的边界：
    - 通用人格包 ``personas/enfp.json`` 真的落盘且可被加载器读到；
    - 私人层 ``private/persona.local.json`` 覆盖通用层，且 **personal 逐键合并**；
    - 私人层缺失或语法坏掉 ⇒ **静默跳过**，绝不让机器人变哑巴；
    - ``private/`` 确实被 .gitignore 覆盖 ⇒ 私人数据永不入库。
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from server.stackchan_ai.persona import (
    BUNDLED_PERSONA_DIR,
    DEFAULT_PERSONA_ID,
    PRIVATE_PERSONA_FILENAME,
    REPO_PERSONA_DIR,
    list_personas,
    load_persona,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class RepoPersonaPackTest(unittest.TestCase):
    """通用人格包（开源层）本身。"""

    def test_repo_pack_file_exists(self):
        path = REPO_PERSONA_DIR / ("%s.json" % DEFAULT_PERSONA_ID)
        self.assertTrue(path.exists(), "personas/enfp.json 必须落盘")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_repo_pack_has_required_fields(self):
        data = json.loads((REPO_PERSONA_DIR / ("%s.json" % DEFAULT_PERSONA_ID))
                          .read_text(encoding="utf-8"))
        for key in ("id", "name", "mbti", "summary", "emotion",
                    "voice", "system_prompt", "speech_style", "personal"):
            self.assertIn(key, data, "人格包缺字段: %s" % key)
        self.assertIsInstance(data["speech_style"], list)
        self.assertIsInstance(data["personal"], dict)

    def test_repo_pack_matches_bundled_baseline(self):
        """通用包与内置兜底不应漂移（否则「换包」会悄悄改变行为）。"""
        repo = json.loads((REPO_PERSONA_DIR / ("%s.json" % DEFAULT_PERSONA_ID))
                          .read_text(encoding="utf-8"))
        bundled = json.loads((BUNDLED_PERSONA_DIR / ("%s.json" % DEFAULT_PERSONA_ID))
                              .read_text(encoding="utf-8"))
        for key in ("id", "name", "mbti", "emotion", "voice"):
            self.assertEqual(repo[key], bundled[key], "字段漂移: %s" % key)

    def test_load_persona_reads_repo_pack(self):
        persona = load_persona(apply_private=False)
        self.assertEqual(persona.id, DEFAULT_PERSONA_ID)
        self.assertTrue(persona.system_prompt)
        self.assertIn("personas", persona.source.replace("\\", "/"))

    def test_list_personas_includes_default(self):
        self.assertIn(DEFAULT_PERSONA_ID, list_personas())


class PrivateOverlayTest(unittest.TestCase):
    """私人层（个人定制，**永不入库**）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.private = Path(self._tmp.name) / "private"
        self.private.mkdir(parents=True, exist_ok=True)
        self._old = os.environ.get("STACKCHAN_PRIVATE_DIR")
        os.environ["STACKCHAN_PRIVATE_DIR"] = str(self.private)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("STACKCHAN_PRIVATE_DIR", None)
        else:
            os.environ["STACKCHAN_PRIVATE_DIR"] = self._old
        self._tmp.cleanup()

    def _write(self, data):
        path = self.private / PRIVATE_PERSONA_FILENAME
        with io.open(str(path), "w", encoding="utf-8", newline="") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))
        return path

    def test_private_scalar_overrides_generic(self):
        self._write({"name": "阿灯", "summary": "我的专属人格"})
        persona = load_persona()
        self.assertEqual(persona.name, "阿灯")
        self.assertEqual(persona.summary, "我的专属人格")

    def test_private_personal_merges_per_key(self):
        base = json.loads((REPO_PERSONA_DIR / ("%s.json" % DEFAULT_PERSONA_ID))
                          .read_text(encoding="utf-8"))
        base_key = next(iter(base["personal"]))
        self._write({"personal": {base_key: 0.123}})
        persona = load_persona()
        self.assertAlmostEqual(persona.personal[base_key], 0.123, places=6)
        # 其余键必须保留 ⇒ 逐键合并，不是整表替换
        self.assertEqual(len(persona.personal), len(base["personal"]))

    def test_private_missing_is_silent(self):
        persona = load_persona()
        self.assertTrue(persona.system_prompt)
        self.assertEqual(persona.name, "小灯")

    def test_private_broken_json_is_silent(self):
        self._write("{ this is not json ")
        persona = load_persona()
        self.assertTrue(persona.system_prompt)
        self.assertEqual(persona.name, "小灯")

    def test_apply_private_false_skips_overlay(self):
        self._write({"name": "阿灯"})
        persona = load_persona(apply_private=False)
        self.assertEqual(persona.name, "小灯")

    def test_private_dir_is_gitignored(self):
        """隐私不变量：``private/`` 必须被忽略，私人数据永不入库。"""
        gitignore = REPO_ROOT / ".gitignore"
        with io.open(str(gitignore), "rb") as fh:
            text = fh.read().decode("utf-8-sig", errors="replace")
        self.assertIn("private/", text)


if __name__ == "__main__":
    unittest.main()
