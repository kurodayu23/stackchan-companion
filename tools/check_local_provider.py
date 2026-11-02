#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""check_local_provider.py —— 「个人数据永不出网」的执行判据（M-05 护城河项）

为什么要有这个门禁
------------------
本仓把「个人数据永不入库」这条产品承诺的**执行体**放在
`server/providers/local.py` —— 一个**只允许指向回环地址**的本地推理 provider。

但**光有实现不够**：代码会被改、默认值会被改、base URL 会被「顺手改成云地址」、
采样率会被写死 ⇒ **承诺会悄悄退化成文案**。

⇒ 把不变式写成**机械可判**的门禁（本门禁**零第三方依赖**，纯标准库）：

| 码 | 判据 | 判法 |
|---|---|---|
| LP-01 | 非回环地址在**构造时**被拒（`allow_remote` 也必须环境变量双保险） | 行为 |
| LP-02 | 请求形状：chat → `/v1/chat/completions`（`stream:false`）；tts → `/v1/audio/speech`（`response_format:"wav"`） | 行为（起真回环假服务器） |
| LP-03 | 配置认得 `STACKCHAN_LOCAL_*`；`STACKCHAN_PROVIDER=local` ⇒ `provider_name == "local"` | 行为 |
| LP-04 | **默认 base URL 常量必须解析到回环地址**（防默认值被改成云地址） | 源码 |
| LP-05 | `local.py` **不得硬编码采样率 24000**（官方文档写本地是 24 kHz ⇒ 必须从 WAV 头取真值） | 源码 |
| LP-06 | 注册表必须认 `local`（`available_providers()` + `build_provider` 分支） | 源码 |

⚠️ **接口形状的依据**（官方文档原文，不是记忆）：
    Ollama    https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
    llama.cpp https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

用法：
    python tools/check_local_provider.py --root .
    python tools/check_local_provider.py --self-test
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import sys
import threading
import types
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEV_FAIL, SEV_WARN, SEV_PASS = "FAIL", "WARN", "PASS"


class Finding(object):
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg


# ── 源码加载（零第三方依赖：绕开 server/providers/__init__.py 的 numpy 依赖） ──

def _load_local_module(root: str, tag: str):
    """加载 ``<root>/server/providers/local.py``，**不触发** 包的 ``__init__``。

    ⚠️ 为什么绕开：``server/providers/__init__.py`` 会 import ``.stub`` ⇒ numpy。
       本门禁必须**零第三方依赖**（CI 的 docs-gate job 不装 numpy）。
       ⇒ 造一个合成包，把 ``base`` / ``local`` 挂进去，相对导入照常工作。
    """
    providers_dir = os.path.join(root, "server", "providers")
    pkg_name = "lpcheck_%s" % tag
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [providers_dir]          # type: ignore[attr-defined]
    sys.modules[pkg_name] = pkg

    def _load(mod_name: str, filename: str):
        spec = importlib.util.spec_from_file_location(
            "%s.%s" % (pkg_name, mod_name), os.path.join(providers_dir, filename))
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["%s.%s" % (pkg_name, mod_name)] = mod
        spec.loader.exec_module(mod)
        return mod

    _load("base", "base.py")
    return _load("local", "local.py")


def _load_config_module(root: str, tag: str):
    """加载 ``<root>/server/stackchan_ai/config.py``（无相对导入，可独立加载）。"""
    path = os.path.join(root, "server", "stackchan_ai", "config.py")
    spec = importlib.util.spec_from_file_location("lpcheck_cfg_%s" % tag, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(path: str) -> str:
    with io.open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig", errors="replace")


# ── 假的「本地 OpenAI 兼容服务器」 ───────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # pragma: no cover
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _blob(self, blob):
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        self.server.requests.append({"path": self.path, "body": raw})  # type: ignore[attr-defined]
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            payload = {}
        if self.path.endswith("/chat/completions"):
            self._json({"model": payload.get("model", "m"),
                        "choices": [{"message": {"role": "assistant", "content": "ok"}}]})
            return
        if self.path.endswith("/audio/speech"):
            self._blob(self.server.wav_bytes)  # type: ignore[attr-defined]
            return
        self._json({"error": {"message": "not found"}}, 404)


class _FakeServer(object):
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.requests = []              # type: ignore[attr-defined]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x00\x01" * 240)
        self.httpd.wav_bytes = buf.getvalue()  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return "http://%s:%d" % (self.httpd.server_address[0], self.httpd.server_address[1])

    @property
    def requests(self):
        return self.httpd.requests

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# ── 判据 ────────────────────────────────────────────────────────────────────

def check_lp01_loopback_guard(root: str) -> List[Finding]:
    """LP-01：非回环地址在构造时被拒。"""
    out: List[Finding] = []
    local_mod = _load_local_module(root, "lp01")
    where = "server/providers/local.py"
    try:
        local_mod.LocalProvider(base_url="http://example.com/v1")
        out.append(Finding("LP-01", SEV_FAIL, where,
                           "非回环地址 http://example.com/v1 **没有被拒绝** ⇒ "
                           "「个人数据永不出网」这条不变式已破"))
    except ValueError:
        out.append(Finding("LP-01", SEV_PASS, where, "非回环地址在构造时被拒"))
    except Exception as exc:
        out.append(Finding("LP-01", SEV_FAIL, where,
                           "拒绝非回环地址时抛的不是 ValueError：%r" % (exc,)))

    # allow_remote 也必须环境变量双保险
    saved = os.environ.pop("STACKCHAN_LOCAL_ALLOW_REMOTE", None)
    try:
        try:
            local_mod.LocalProvider(base_url="http://example.com/v1", allow_remote=True)
            out.append(Finding("LP-01", SEV_FAIL, where,
                               "allow_remote=True 在**没有**环境变量放行时也放行了 ⇒ 双保险失效"))
        except ValueError:
            out.append(Finding("LP-01", SEV_PASS, where,
                               "allow_remote 需要环境变量双保险"))
        os.environ["STACKCHAN_LOCAL_ALLOW_REMOTE"] = "1"
        try:
            local_mod.LocalProvider(base_url="http://example.com/v1", allow_remote=True)
            out.append(Finding("LP-01", SEV_PASS, where,
                               "环境变量放行后可以指向外网（显式逃生口存在）"))
        except ValueError as exc:
            out.append(Finding("LP-01", SEV_FAIL, where,
                               "环境变量放行后仍然被拒：%s" % exc))
    finally:
        os.environ.pop("STACKCHAN_LOCAL_ALLOW_REMOTE", None)
        if saved is not None:
            os.environ["STACKCHAN_LOCAL_ALLOW_REMOTE"] = saved
    return out


def check_lp02_request_shape(root: str) -> List[Finding]:
    """LP-02：chat / tts 的请求路径与请求体形状。"""
    out: List[Finding] = []
    local_mod = _load_local_module(root, "lp02")
    where = "server/providers/local.py"
    server = _FakeServer()
    try:
        provider = local_mod.LocalProvider(base_url=server.base_url,
                                           tts_model="speech-model")
        provider.chat([{"role": "user", "content": "hi"}])
        chat_req = server.requests[-1]
        if not chat_req["path"].endswith("/v1/chat/completions"):
            out.append(Finding("LP-02", SEV_FAIL, where,
                               "chat 请求路径是 %r，不是 /v1/chat/completions"
                               % chat_req["path"]))
        else:
            out.append(Finding("LP-02", SEV_PASS, where,
                               "chat 请求路径 = /v1/chat/completions"))
        body = json.loads(chat_req["body"].decode("utf-8"))
        if body.get("stream") is not False:
            out.append(Finding("LP-02", SEV_FAIL, where,
                               "chat 请求体缺少 \"stream\": false（后端读不到完整回复）"))
        else:
            out.append(Finding("LP-02", SEV_PASS, where,
                               "chat 请求体带 \"stream\": false"))

        provider.tts("你好")
        tts_req = server.requests[-1]
        if not tts_req["path"].endswith("/v1/audio/speech"):
            out.append(Finding("LP-02", SEV_FAIL, where,
                               "tts 请求路径是 %r，不是 /v1/audio/speech"
                               % tts_req["path"]))
        else:
            out.append(Finding("LP-02", SEV_PASS, where,
                               "tts 请求路径 = /v1/audio/speech"))
        tbody = json.loads(tts_req["body"].decode("utf-8"))
        if tbody.get("response_format") != "wav":
            out.append(Finding("LP-02", SEV_FAIL, where,
                               "tts 请求体 response_format=%r，不是 wav"
                               % tbody.get("response_format")))
        else:
            out.append(Finding("LP-02", SEV_PASS, where,
                               "tts 请求体 response_format = wav（取真实采样率）"))
    finally:
        server.close()
    return out


def check_lp03_config(root: str) -> List[Finding]:
    """LP-03：配置认得本地 provider。"""
    out: List[Finding] = []
    cfg_mod = _load_config_module(root, "lp03")
    where = "server/stackchan_ai/config.py"
    env = {
        "STACKCHAN_PROVIDER": "local",
        "STACKCHAN_LOCAL_BASE_URL": "http://127.0.0.1:9999/v1",
        "STACKCHAN_LOCAL_MODEL": "my-model",
        "STACKCHAN_LOCAL_TTS_MODEL": "my-tts",
    }
    cfg = cfg_mod.Config.from_env(env=env)
    if cfg.provider_name != "local":
        out.append(Finding("LP-03", SEV_FAIL, where,
                           "STACKCHAN_PROVIDER=local 时 provider_name=%r，不是 'local'"
                           % cfg.provider_name))
    else:
        out.append(Finding("LP-03", SEV_PASS, where,
                           "STACKCHAN_PROVIDER=local ⇒ provider_name = local"))
    problems = []
    if getattr(cfg, "local_base_url", "") != env["STACKCHAN_LOCAL_BASE_URL"]:
        problems.append("local_base_url")
    if getattr(cfg, "local_model", "") != env["STACKCHAN_LOCAL_MODEL"]:
        problems.append("local_model")
    if getattr(cfg, "local_tts_model", "") != env["STACKCHAN_LOCAL_TTS_MODEL"]:
        problems.append("local_tts_model")
    if problems:
        out.append(Finding("LP-03", SEV_FAIL, where,
                           "配置没读全：%s" % "、".join(problems)))
    else:
        out.append(Finding("LP-03", SEV_PASS, where,
                           "STACKCHAN_LOCAL_* 变量都被读到了"))
    return out


def check_lp04_default_base_url(root: str) -> List[Finding]:
    """LP-04：默认 base URL 常量必须解析到回环地址。"""
    out: List[Finding] = []
    where = "server/providers/local.py"
    local_mod = _load_local_module(root, "lp04")
    default = getattr(local_mod, "DEFAULT_LOCAL_BASE_URL", "")
    host = ""
    try:
        from urllib.parse import urlsplit
        host = urlsplit(default).hostname or ""
    except Exception:
        pass
    if not local_mod.is_loopback_host(host):
        out.append(Finding("LP-04", SEV_FAIL, where,
                           "默认 base URL %r 的主机 %r **不是回环地址** ⇒ "
                           "默认配置会把对话发到外网" % (default, host)))
    else:
        out.append(Finding("LP-04", SEV_PASS, where,
                           "默认 base URL = %r（回环）" % default))
    return out


def check_lp05_no_hardcoded_rate(root: str) -> List[Finding]:
    """LP-05：不得硬编码采样率。"""
    out: List[Finding] = []
    where = "server/providers/local.py"
    src = _read(os.path.join(root, "server", "providers", "local.py"))
    # 去掉注释与文档串后再找 24000（文档里提到 24 kHz 是允许的）
    code_lines = []
    in_doc = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if in_doc:
                in_doc = False
                continue
            if stripped.count('"""') < 2:
                in_doc = True
                continue
            continue
        if in_doc:
            continue
        if stripped.startswith("#"):
            continue
        code_lines.append(line.split("#", 1)[0])
    code = "\n".join(code_lines)
    if re.search(r"\b24000\b", code):
        out.append(Finding("LP-05", SEV_FAIL, where,
                           "代码里出现硬编码采样率 24000 ⇒ 本地 TTS 的真实采样率"
                           "必须从 WAV 头取（官方文档写的是 24 kHz，但那只是某一版的实现）"))
    else:
        out.append(Finding("LP-05", SEV_PASS, where, "没有硬编码采样率"))
    return out


def check_lp06_registry(root: str) -> List[Finding]:
    """LP-06：注册表认得 local。"""
    out: List[Finding] = []
    where = "server/providers/registry.py"
    src = _read(os.path.join(root, "server", "providers", "registry.py"))
    if re.search(r'["\']local["\']', src) is None:
        out.append(Finding("LP-06", SEV_FAIL, where,
                           "registry.py 里找不到 'local' ⇒ provider 注册表漏了本地推理"))
    elif re.search(r'name\s*==\s*["\']local["\']', src) is None:
        out.append(Finding("LP-06", SEV_FAIL, where,
                           "registry.py 没有 `name == \"local\"` 的分支"))
    else:
        out.append(Finding("LP-06", SEV_PASS, where, "注册表认得 local"))
    return out


ALL_CHECKS = (
    ("LP-01", check_lp01_loopback_guard),
    ("LP-02", check_lp02_request_shape),
    ("LP-03", check_lp03_config),
    ("LP-04", check_lp04_default_base_url),
    ("LP-05", check_lp05_no_hardcoded_rate),
    ("LP-06", check_lp06_registry),
)


def run_all(root: str) -> List[Finding]:
    findings: List[Finding] = []
    for _code, fn in ALL_CHECKS:
        try:
            findings.extend(fn(root))
        except Exception as exc:
            findings.append(Finding(_code, SEV_FAIL, "-",
                                    "判据执行失败：%s: %s" % (type(exc).__name__, exc)))
    return findings


# ── 自检（变异夹具：证明每条判据都有分辨力） ────────────────────────────────

_MUTATIONS = (
    ("LP-01",
     "构造非回环地址时不再拒绝",
     "server/providers/local.py",
     "        if not allow_remote:\n            assert_loopback_base_url(self.base_url)\n",
     "        if not allow_remote:\n            pass\n"),
    ("LP-02",
     "chat 路径改成非 OpenAI 兼容",
     "server/providers/local.py",
     '"/chat/completions"',
     '"/api/chat"'),
    ("LP-02",
     "tts 请求体不再要 wav",
     "server/providers/local.py",
     '            "response_format": "wav",\n            "speed": float(kwargs.get("speed", 1.0)),\n',
     '            "response_format": "mp3",\n            "speed": float(kwargs.get("speed", 1.0)),\n'),
    ("LP-04",
     "默认 base URL 指向外网",
     "server/providers/local.py",
     'DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"',
     'DEFAULT_LOCAL_BASE_URL = "http://api.example.com/v1"'),
    ("LP-05",
     "硬编码采样率 24000",
     "server/providers/local.py",
     "    def _normalize_base_url(base_url: str) -> str:",
     "    HARDCODE_RATE = 24000\n\n    def _normalize_base_url(base_url: str) -> str:"),
    ("LP-06",
     "注册表漏掉 local",
     "server/providers/registry.py",
     '    if name == "local":',
     '    if name == "local-disabled":'),
)


def _make_fixture(tmp: str) -> str:
    """把真实仓库里需要的 3 个源文件拷到临时目录当夹具。"""
    import shutil
    root = os.path.join(tmp, "repo")
    for rel in ("server/providers/local.py", "server/providers/base.py",
                "server/providers/registry.py", "server/stackchan_ai/config.py"):
        src = os.path.join(REPO_ROOT, rel.replace("/", os.sep))
        dst = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    return root


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def self_test() -> int:
    import shutil
    import tempfile
    failures = 0
    tmp = tempfile.mkdtemp(prefix="lpcheck-")
    try:
        base_root = _make_fixture(tmp)
        findings = run_all(base_root)
        bad = [f for f in findings if f.severity == SEV_FAIL]
        if bad:
            print("[FAIL] 干净夹具上就有 %d 条 FAIL：%s"
                  % (len(bad), [(f.code, f.msg[:60]) for f in bad]))
            failures += 1
        else:
            print("[PASS] 干净夹具 —— 0 FAIL")

        for code, desc, rel, old, new in _MUTATIONS:
            root = _make_fixture(tmp)
            path = os.path.join(root, rel.replace("/", os.sep))
            text = _read(path)
            if old not in text:
                print("[FAIL] 变异夹具 %s 找不到待替换文本（判据可能已失效）：%r"
                      % (code, old[:50]))
                failures += 1
                continue
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text.replace(old, new, 1))
            got = run_all(root)
            hit = [f for f in got if f.severity == SEV_FAIL and f.code == code]
            if hit:
                print("[PASS] 变异夹具被抓住 —— %s（%s）" % (code, desc))
            else:
                print("[FAIL] 变异夹具**没被抓住** —— %s（%s）" % (code, desc))
                failures += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = 1 + len(_MUTATIONS)
    print("-" * 60)
    print("自检结果：%d/%d PASS" % (total - failures, total))
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    findings = run_all(os.path.abspath(args.root))
    print("=" * 68)
    print("check_local_provider —— 「个人数据永不出网」执行判据")
    print("=" * 68)
    fails = 0
    for code, _fn in ALL_CHECKS:
        rows = [f for f in findings if f.code == code]
        for f in rows:
            if f.severity == SEV_FAIL:
                fails += 1
                print("[FAIL] %s  %s —— %s" % (code, f.where, f.msg))
    for code, _fn in ALL_CHECKS:
        rows = [f for f in findings if f.code == code]
        if rows and all(f.severity == SEV_PASS for f in rows):
            print("[PASS] %s  %s —— %s" % (code, rows[0].where, rows[0].msg))
    print("-" * 68)
    print("FAIL=%d  （判据 %d 条）" % (fails, len(ALL_CHECKS)))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
