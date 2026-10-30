# -*- coding: utf-8 -*-
"""test_http_api —— HTTP 适配层（`/gui/*`）的测试。

覆盖三件事：
    1. **路由表自洽**：唯一、owner 合法、实现与 owner 一致；
    2. **核心路由真的能用**（对话 / 记忆 / 状态 / 屏幕程序 / 设备参数）；
    3. ⭐ **契约**：手机端（`prototype/mobile/`）实际调用的**每一条**路径
       都必须在本仓路由表里有对应项（`owner` 可以是 `mobile` 或 `desktop`）
       ⇒ 否则手机端会撞 404 ⇒ **这是 Q27「两套后端」的门禁版**。

全部离线：用 `StubProvider`，不联网、不需要 API Key。
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.http_api import (  # noqa: E402
    ROUTES,
    MobileBackend,
    route_table,
    serve,
)
from server.mobile_contract import (  # noqa: E402
    CONTRACTS,
    MEMORY_CATEGORIES,
    SCREEN_PROGRAM_IDS,
    path_exists,
    path_non_empty,
)
from server.providers.stub import StubProvider  # noqa: E402
from server.stackchan_ai.config import Config  # noqa: E402
from server.stackchan_ai.server import StackChanServer  # noqa: E402

MOBILE_DIR = REPO_ROOT / "prototype" / "mobile"


def _backend() -> MobileBackend:
    config = Config.from_env()
    config.provider = "stub"
    server = StackChanServer(config, provider=StubProvider(), verbose=False)
    return MobileBackend(config, server=server)


class RouteTableTests(unittest.TestCase):
    """路由表的自洽性。"""

    def test_routes_not_empty(self):
        self.assertGreater(len(ROUTES), 20)

    def test_method_path_unique(self):
        seen = set()
        for r in ROUTES:
            key = (r.method, r.path)
            self.assertNotIn(key, seen, "重复路由 %s" % (key,))
            seen.add(key)

    def test_owner_legal(self):
        for r in ROUTES:
            self.assertIn(r.owner, ("mobile", "desktop"), r.path)

    def test_owner_matches_implementation(self):
        """owner=mobile ⇒ 必须有 handler；owner=desktop ⇒ 必须没有。"""
        for r in ROUTES:
            if r.owner == "mobile":
                self.assertIsNotNone(r.handler, "%s 标成 mobile 但没有实现" % r.path)
            else:
                self.assertIsNone(r.handler, "%s 标成 desktop 却有实现" % r.path)

    def test_all_paths_are_gui(self):
        for r in ROUTES:
            self.assertTrue(r.path.startswith("/gui/"), r.path)

    def test_route_table_summary(self):
        table = route_table()
        self.assertEqual(table["count"], len(ROUTES))
        self.assertEqual(table["implemented"] + table["desktop_only"], table["count"])


class MobileContractTests(unittest.TestCase):
    """⭐ 契约：手机端调用的路径必须能被代理转出去，且本仓路由表里必须有对应项。"""

    @staticmethod
    def _called_paths():
        """扫手机端 JS，取出实际调用的**手机端**路径（去重）。"""
        if not MOBILE_DIR.is_dir():
            return set()
        pat_api = re.compile(r"api\.(?:get|post|put|patch)\s*\(\s*[\"'`]([^\"'`]+)")
        pat_fetch = re.compile(r"fetch\s*\(\s*[`\"']?(/mobile-api/[^`\"'\s]*)")
        called = set()
        for path in sorted(MOBILE_DIR.glob("*.js")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in pat_api.finditer(text):
                called.add("/mobile-api" + m.group(1))
            for m in pat_fetch.finditer(text):
                called.add(m.group(1))
        return called

    @staticmethod
    def _proxy_map():
        """{(method, mobile_path): gui_path} —— 代理白名单。"""
        proxy = MOBILE_DIR / "mobile_proxy.py"
        if not proxy.is_file():
            return {}
        text = proxy.read_text(encoding="utf-8", errors="replace")
        block = re.search(r"ALLOWED_ROUTES\s*=\s*\{(.*?)\n\}", text, re.S)
        if not block:
            return {}
        pairs = re.findall(
            r'\(\s*"(GET|POST|PUT|PATCH)"\s*,\s*"([^"]+)"\s*\)\s*:\s*"([^"]+)"',
            block.group(1))
        return {(m, mob): gui for m, mob, gui in pairs}

    def test_every_called_path_is_whitelisted_by_proxy(self):
        """手机端调的每条路径，代理都必须放行 ⇒ 否则代理层直接 404。"""
        proxy_map = self._proxy_map()
        if not proxy_map:
            self.skipTest("代理白名单解析不到")
        whitelisted = {mob for (_m, mob) in proxy_map}
        called = self._called_paths()
        self.assertTrue(called, "没扫到任何调用（正则失效？）")
        missing = []
        for path in sorted(called):
            if "${" in path:          # 模板路径 ⇒ 单独处理
                continue
            if path not in whitelisted:
                missing.append(path)
        self.assertEqual(missing, [], "手机端调用了代理没放行的路径：%s" % missing)

    def test_every_called_path_has_a_route(self):
        """手机端调用的每条路径 ⇒ 代理能转 ⇒ 本仓路由表里必须有对应项。"""
        proxy_map = self._proxy_map()
        have_paths = {r.path for r in ROUTES}
        missing = []
        for path in sorted(self._called_paths()):
            if "${" in path:
                parts = re.split(r"\$\{[^}]+\}", path)
                pattern = re.compile("^" + "([^/]+)".join(re.escape(p) for p in parts) + "$")
                targets = [gui for (_m, mob), gui in proxy_map.items()
                           if pattern.match(mob)]
                if not targets:
                    missing.append(path + " （代理也没对应白名单）")
                    continue
                for gui in targets:
                    if gui not in have_paths:
                        missing.append("%s -> %s" % (path, gui))
                continue
            guis = [gui for (_m, mob), gui in proxy_map.items() if mob == path]
            if not guis:
                missing.append(path + " （代理白名单里没有）")
                continue
            for gui in guis:
                if gui not in have_paths:
                    missing.append("%s -> %s" % (path, gui))
        self.assertEqual(missing, [], "手机端调用的路径在本仓没有对应路由：%s" % missing)

    def test_proxy_whitelist_matches_route_table(self):
        """代理白名单里的每一条，本仓路由表里都必须有（方法 + 路径）。"""
        proxy_map = self._proxy_map()
        self.assertTrue(proxy_map)
        have = {(r.method, r.path) for r in ROUTES}
        missing = []
        for (method, _mobile), gui in sorted(proxy_map.items()):
            if (method, gui) not in have:
                missing.append("%s %s" % (method, gui))
        self.assertEqual(missing, [], "代理白名单里有本仓没有的路由：%s" % missing)


class HandlerTests(unittest.TestCase):
    """核心路由的行为。"""

    @classmethod
    def setUpClass(cls):
        cls.backend = _backend()

    def test_device_status(self):
        """设备状态必须是**手机端形状**（不是内部状态字典）。"""
        status, payload = self.backend.handle_device_status({})
        self.assertEqual(status, 200)
        self.assertIn("connected", payload)
        self.assertIn("network", payload)
        self.assertIn("music", payload)
        self.assertIn("stage", payload)
        self.assertIn("camera", payload)
        self.assertIn("head", payload)
        self.assertNotIn("mac", payload, "内部字段不应直接透给手机端")

    def test_chat_requires_text(self):
        status, payload = self.backend.handle_chat({})
        self.assertEqual(status, 400)
        self.assertIn("detail", payload)

    def test_chat_uses_mobile_contract_field_names(self):
        """⭐ 手机端读的是 ``say``（不是 ``reply``）⇒ 字段名对不上就白屏。"""
        status, payload = self.backend.handle_chat({"message": "你好呀"})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload.get("say"), "say 为空 ⇒ 手机端会提示「没有返回内容」")
        self.assertIn("model", payload)
        self.assertIn("emotion", payload)
        self.assertIn("latency_ms", payload)

    def test_chat_runs_full_pipeline(self):
        """真跑 LLM→TTS→韵律→关键帧（stub provider，离线）。"""
        status, payload = self.backend.handle_chat({"text": "你好呀"})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["reply"], "回复为空")
        self.assertEqual(payload["emotion_source"], "persona_baseline")
        self.assertGreater(payload["keyframes"], 0, "关键帧数为 0 ⇒ 闭环没跑通")
        self.assertGreater(payload["audio_samples"], 0, "音频样本数为 0 ⇒ TTS 没跑")

    def test_memory_list(self):
        status, payload = self.backend.handle_memory_list({"profile": "unit-test"})
        self.assertEqual(status, 200)
        self.assertIn("profiles", payload)
        self.assertIn("events", payload)
        for key in MEMORY_CATEGORIES:
            self.assertIn(key, payload, "缺少记忆分类 %s ⇒ 手机端记忆页永远空" % key)
            self.assertIsInstance(payload[key], list)

    def test_memory_clear(self):
        status, payload = self.backend.handle_memory_clear({"profile": "unit-test"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("changed", payload)

    def test_memory_remove_reports_changed(self):
        status, payload = self.backend.handle_memory_remove(
            {"profile": "unit-test", "key": "likes", "value": "咖啡"})
        self.assertEqual(status, 200)
        self.assertIn("changed", payload)

    def test_screen_programs(self):
        status, payload = self.backend.handle_screen_programs({})
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["programs"]), len(SCREEN_PROGRAM_IDS))
        self.assertIn("status", payload, "代理会用 status 字段渲染设备态")

    def test_screen_program_control(self):
        status, payload = self.backend.handle_screen_programs_control(
            {"program_id": "chat", "action": "open"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["program"]["id"], "chat")
        self.assertTrue(payload["program"]["name"])
        self.assertIn("device", payload)
        status, _ = self.backend.handle_screen_programs_control({"program_id": "nope"})
        self.assertEqual(status, 404)

    def test_device_head_updates_state(self):
        status, payload = self.backend.handle_device_head({"yaw": 30, "pitch": 60})
        self.assertEqual(status, 200)
        self.assertEqual(payload["yaw"], 30)
        self.assertEqual(payload["pitch"], 60)
        self.assertEqual(payload["applied_to"], "state-only")

    def test_device_params_use_mobile_field_names(self):
        """代理转发的是 ``{"brightness": N}`` / ``{"volume": N}`` / ``{"red","green","blue"}``。"""
        status, payload = self.backend.handle_device_brightness({"brightness": 42})
        self.assertEqual(status, 200)
        self.assertEqual(payload["brightness"], 42)
        self.assertTrue(payload["ok"])

        status, payload = self.backend.handle_device_volume({"volume": 30, "permanent": False})
        self.assertEqual(status, 200)
        self.assertEqual(payload["volume"], 30)

        status, payload = self.backend.handle_device_led({"red": 10, "green": 20, "blue": 30})
        self.assertEqual(status, 200)
        self.assertEqual((payload["red"], payload["green"], payload["blue"]), (10, 20, 30))

    def test_device_params_reject_out_of_range(self):
        self.assertEqual(self.backend.handle_device_brightness({"brightness": 0})[0], 400)
        self.assertEqual(self.backend.handle_device_volume({"volume": 999})[0], 400)
        self.assertEqual(
            self.backend.handle_device_led({"red": 1, "green": 2, "blue": 999})[0], 400)

    def test_camera_start_stop(self):
        status, _ = self.backend.handle_camera_start({})
        self.assertEqual(status, 200)
        status, payload = self.backend.handle_camera_frame({})
        self.assertEqual(status, 404, "没有真机时必须明确说没有画面")
        self.assertIn("detail", payload)
        status, _ = self.backend.handle_camera_stop({})
        self.assertEqual(status, 200)

    def test_desktop_only_returns_501(self):
        status, payload = self.backend.handle_desktop_only({})
        self.assertEqual(status, 501)
        self.assertEqual(payload["owner"], "desktop")


class ContractShapeTests(unittest.TestCase):
    """⭐ 契约形状：**每个** ``owner=mobile`` 的契约字段，后端真实响应里必须存在。

    这是 ``tools/check_mobile_contract.py`` 的 in-process 版本；
    门禁那条还会再过一遍**代理净化层**（手机端真正看到的那一层）。
    """

    #: 每条路由的最小合法请求体
    SAMPLE_BODIES = {
        "POST /gui/mobile-chat": {"message": "你好"},
        "GET /gui/device/status": {},
        "GET /gui/screen-programs": {},
        "POST /gui/screen-programs/control": {"program_id": "chat", "action": "open"},
        "GET /gui/memory": {},
        "POST /gui/memory/remove": {"key": "likes", "value": "咖啡"},
        "POST /gui/memory/clear": {"key": "likes"},
        "POST /gui/device/head": {"yaw": 10, "pitch": 20},
        "POST /gui/device/brightness": {"brightness": 50},
        "POST /gui/device/volume": {"volume": 50, "permanent": False},
        "POST /gui/device/led": {"red": 1, "green": 2, "blue": 3},
        "POST /gui/device/camera-preview/start": {},
        "POST /gui/device/camera-preview/stop": {},
        "GET /gui/device/camera/latest": {},
    }

    @classmethod
    def setUpClass(cls):
        cls.backend = _backend()
        cls.route_by_key = {(r.method, r.path): r for r in ROUTES}
        sys.path.insert(0, str(MOBILE_DIR))
        import mobile_proxy  # noqa: E402 - 真实代理净化层
        cls.proxy = mobile_proxy

    def _raw(self, contract):
        route = self.route_by_key[(contract.backend_method, contract.backend_path)]
        return route.handler(self.backend, self.SAMPLE_BODIES[contract.backend_key])

    def _sanitized(self, contract):
        """过完**真实代理净化层**之后，手机端真正看到的那份数据。"""
        status, payload = self._raw(contract)
        if status != 200 or not isinstance(payload, dict):
            return payload
        return self.proxy._sanitize_response(contract.mobile_path, payload)

    def test_every_mobile_contract_has_a_sample_body(self):
        for contract in CONTRACTS:
            if contract.owner != "mobile":
                continue
            self.assertIn(contract.backend_key, self.SAMPLE_BODIES,
                          "契约 %s 没有样例请求体 ⇒ 测不到" % contract.backend_key)

    def test_sanitized_response_contains_contract_fields(self):
        """⭐ 过完代理净化层，契约字段必须还在（净化层只删不增 ⇒ 后端少给就消失）。"""
        missing = []
        for contract in CONTRACTS:
            if contract.owner != "mobile":
                continue
            payload = self._sanitized(contract)
            for path in contract.fields:
                if not path_exists(payload, path):
                    missing.append("%s → %s" % (contract.mobile_key, path))
        self.assertEqual(missing, [], "手机端看不到的契约字段：%s" % missing)

    def test_backend_response_contains_backend_fields(self):
        missing = []
        for contract in CONTRACTS:
            if contract.owner != "mobile":
                continue
            _status, payload = self._raw(contract)
            for path in contract.backend_fields:
                if not path_exists(payload, path):
                    missing.append("%s → %s" % (contract.backend_key, path))
        self.assertEqual(missing, [], "后端响应缺字段：%s" % missing)

    def test_non_empty_fields_are_not_empty(self):
        empty = []
        for contract in CONTRACTS:
            if contract.owner != "mobile" or not contract.non_empty:
                continue
            payload = self._sanitized(contract)
            for path in contract.non_empty:
                if not path_non_empty(payload, path):
                    empty.append("%s → %s" % (contract.mobile_key, path))
        self.assertEqual(empty, [], "必填字段为空：%s" % empty)

    def test_desktop_only_contracts_are_501(self):
        for contract in CONTRACTS:
            if not contract.desktop_only:
                continue
            route = self.route_by_key.get((contract.backend_method, contract.backend_path))
            self.assertIsNotNone(route, contract.backend_key)
            self.assertEqual(route.owner, "desktop", contract.backend_key)
            self.assertFalse(route.implemented, contract.backend_key)

    def test_screen_program_ids_match_proxy(self):
        """后端的屏幕程序 id 必须与代理白名单一致 ⇒ 否则手机端 8 个按钮全被隐藏。"""
        proxy = MOBILE_DIR / "mobile_proxy.py"
        text = proxy.read_text(encoding="utf-8", errors="replace")
        block = re.search(r"SCREEN_PROGRAM_IDS\s*=\s*\{(.*?)\n\}", text, re.S)
        self.assertIsNotNone(block, "代理里找不到 SCREEN_PROGRAM_IDS")
        proxy_ids = set(re.findall(r'"([^"]+)"', block.group(1)))
        self.assertEqual(proxy_ids, set(SCREEN_PROGRAM_IDS))


class HttpLayerTests(unittest.TestCase):
    """真起一个 HTTP 服务打几个请求。"""

    @classmethod
    def setUpClass(cls):
        cls.httpd = serve(host="127.0.0.1", port=0, backend=_backend())
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        import threading
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _post(self, path, payload=None):
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_health(self):
        status, body = self._get("/gui/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_routes_endpoint(self):
        status, body = self._get("/gui/routes")
        self.assertEqual(status, 200)
        table = json.loads(body)
        self.assertEqual(table["count"], len(ROUTES))

    def test_unknown_route_is_404(self):
        status, body = self._get("/gui/nope")
        self.assertEqual(status, 404)
        self.assertIn("detail", json.loads(body))

    def test_device_status_over_http(self):
        status, body = self._get("/gui/device/status")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("connected", payload)
        self.assertIn("network", payload)

    def test_chat_over_http(self):
        status, body = self._post("/gui/mobile-chat", {"message": "在吗"})
        self.assertEqual(status, 200, body)
        payload = json.loads(body)
        self.assertTrue(payload["say"], "say 为空 ⇒ 手机端显示不出回复")

    def test_desktop_only_over_http_is_501(self):
        status, body = self._get("/gui/firmware/status")
        self.assertEqual(status, 501)
        self.assertEqual(json.loads(body)["owner"], "desktop")


if __name__ == "__main__":
    unittest.main()
