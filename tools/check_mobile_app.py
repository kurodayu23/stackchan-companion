#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_mobile_app.py —— 手机端 UI 规格 ↔ 实现 一致性体检

为什么需要它
------------
手机端（``prototype/mobile/``）的每一版交互规格都是**手写的散文**：

    「Tab 收敛为 3 个」「俯仰靠摇杆纵向拖动」「速度用 4 个圆圈」
    「触控热区 ≥ 44pt」「摄像头面板默认隐藏」「PWA 主题色必须是暗色」

散文**不能机器判** ⇒ 改一版 UI 就会悄悄破掉上一版的规格，而且没人会发现。
更糟的是「破掉了规格但门禁全绿」—— 这正是这份仓库反复出现过的失败形态。

这条门禁把**能机器判的那部分规格**变成判据，
并对每条判据都配一个**变异用例**（把实现改坏 ⇒ 该判据必须变红），
以证明这些判据不是摆设。

判据清单
--------
====  ==========================================================
ID    判据
====  ==========================================================
MO-01 全仓无 U+FFFD（乱码硬门禁）
MO-02 Tab 恰好 3 个，且是 对话 / 遥控 / 设置
MO-03 不得再有 pitchSlider / speedSlider（规格已删）
MO-04 速度必须是 4 个圆圈，且恰好 1 个默认选中
MO-05 初始俯仰 = 45°（JS 与 DOM 初始值必须一致）
MO-06 摇杆死区 = 8%
MO-07 摇杆直径 132px、球 40px
MO-08 PWA 主题色/背景色必须是暗色，且不得回退到旧浅色
MO-09 版本号一致（index.html ``?v=`` / sw.js CACHE_NAME / SW 注册 URL）
MO-10 摄像头面板必须是 ``.app-shell`` 直接子元素（不能困在 ``.screen`` 的 stacking context 里）
MO-11 **静态模块闭包 ⊆ serve.py 白名单**（漏一个文件手机端就白屏）
MO-12 图标按钮触控热区 ≥ 44px
MO-13 CSS 变量无未定义引用
MO-14 摄像头面板默认 hidden
MO-15 sw.js 的 APP_FILES 覆盖全部入口模块
====  ==========================================================

用法
----
    py -3.12 tools/check_mobile_app.py --root .
    py -3.12 tools/check_mobile_app.py --self-test

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MOBILE_REL = os.path.join("prototype", "mobile")

#: 需要扫描乱码的文本后缀
TEXT_SUFFIXES = (".html", ".css", ".js", ".py", ".md", ".json", ".webmanifest", ".yaml", ".yml")

#: 官方最小触控目标（Apple HIG / WCAG 2.5.5）
MIN_TOUCH_TARGET_PX = 44

#: 旧版浅色 PWA 主题色（与实际暗色 UI 不符 ⇒ 启动闪白）
LEGACY_LIGHT_THEME = "#f7f7fa"


class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.code} {self.severity} {self.where} {self.msg}>"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# MO-01 乱码
# ---------------------------------------------------------------------------
def check_no_replacement_char(mobile: Path, findings: list) -> None:
    for path in sorted(mobile.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        text = _read(path)
        count = text.count("\ufffd")
        if count:
            findings.append(Finding(
                "MO-01", "FAIL", path.relative_to(mobile.parent.parent).as_posix(),
                f"文件里有 {count} 个 U+FFFD（乱码硬门禁）"))


# ---------------------------------------------------------------------------
# MO-02 / MO-04 Tab 与速度圆圈
# ---------------------------------------------------------------------------
RE_TAB_BUTTON = re.compile(r'class="[^"]*\btab-button\b[^"]*"[^>]*data-target="([^"]+)"')
RE_SPEED_DOT = re.compile(r'class="[^"]*\bspeed-dot\b[^"]*"[^>]*data-speed-level="(\d+)"')
RE_SPEED_ACTIVE = re.compile(r'class="[^"]*\bspeed-dot is-active\b[^"]*"')


def check_tabs_and_speed(html: str, findings: list) -> None:
    tabs = RE_TAB_BUTTON.findall(html)
    if len(tabs) != 3:
        findings.append(Finding("MO-02", "FAIL", "index.html",
                                 f"Tab 应恰好 3 个，实际 {len(tabs)} 个：{tabs}"))
    else:
        if sorted(tabs) != ["chat", "remote", "settings"]:
            findings.append(Finding("MO-02", "FAIL", "index.html",
                                     f"Tab 集合应为 对话/遥控/设置，实际 {tabs}"))

    dots = RE_SPEED_DOT.findall(html)
    if len(dots) != 4:
        findings.append(Finding("MO-04", "FAIL", "index.html",
                                 f"速度应为 4 个圆圈，实际 {len(dots)} 个"))
    if len(RE_SPEED_ACTIVE.findall(html)) != 1:
        findings.append(Finding("MO-04", "FAIL", "index.html",
                                 "速度圆圈必须恰好 1 个默认选中"))


# ---------------------------------------------------------------------------
# MO-03 旧控件必须消失
# ---------------------------------------------------------------------------
FORBIDDEN_IDS = ("pitchSlider", "speedSlider", "pitchValue", "speedValue")


def check_forbidden_controls(files: dict, findings: list) -> None:
    for name in ("index.html", "styles.css", "remote_control.js"):
        text = files.get(name, "")
        hit = [fid for fid in FORBIDDEN_IDS if fid in text]
        if hit:
            findings.append(Finding("MO-03", "FAIL", name,
                                     f"规格已删除的控件还在：{hit}"))


# ---------------------------------------------------------------------------
# MO-05 / MO-06 初始俯仰与死区
# ---------------------------------------------------------------------------
RE_CURRENT_PITCH = re.compile(r"let\s+currentPitch\s*=\s*(-?\d+)")
RE_PREVIEW_PITCH = re.compile(r"let\s+previewStartPitch\s*=\s*(-?\d+)")
RE_DEAD_ZONE = re.compile(r"JOYSTICK_DEAD_ZONE\s*=\s*([0-9.]+)")
RE_DATA_PITCH = re.compile(r'id="robotPreviewCanvas"[^>]*data-pitch="(-?\d+)"')

EXPECTED_PITCH = 45
EXPECTED_DEAD_ZONE = 0.08


def check_pitch_and_deadzone(files: dict, findings: list) -> None:
    rc = files.get("remote_control.js", "")
    html = files.get("index.html", "")

    m = RE_CURRENT_PITCH.search(rc)
    if not m or int(m.group(1)) != EXPECTED_PITCH:
        findings.append(Finding("MO-05", "FAIL", "remote_control.js",
                                 f"currentPitch 应为 {EXPECTED_PITCH}，实际 {m.group(1) if m else '未找到'}"))
    m = RE_PREVIEW_PITCH.search(rc)
    if not m or int(m.group(1)) != EXPECTED_PITCH:
        findings.append(Finding("MO-05", "FAIL", "remote_control.js",
                                 f"previewStartPitch 应为 {EXPECTED_PITCH}，实际 {m.group(1) if m else '未找到'}"))
    m = RE_DATA_PITCH.search(html)
    if not m or int(m.group(1)) != EXPECTED_PITCH:
        findings.append(Finding("MO-05", "FAIL", "index.html",
                                 f"3D canvas 的 data-pitch 应为 {EXPECTED_PITCH}，实际 {m.group(1) if m else '未找到'}"))

    m = RE_DEAD_ZONE.search(rc)
    if not m or abs(float(m.group(1)) - EXPECTED_DEAD_ZONE) > 1e-9:
        findings.append(Finding("MO-06", "FAIL", "remote_control.js",
                                 f"摇杆死区应为 {EXPECTED_DEAD_ZONE}，实际 {m.group(1) if m else '未找到'}"))


# ---------------------------------------------------------------------------
# MO-07 摇杆几何
# ---------------------------------------------------------------------------
RE_JOYSTICK_SIZE = re.compile(r"\.joystick\s*\{[^}]*?width:\s*(\d+)px[^}]*?height:\s*(\d+)px", re.S)
RE_KNOB_SIZE = re.compile(r"\.joystick-knob\s*\{[^}]*?width:\s*(\d+)px[^}]*?height:\s*(\d+)px", re.S)

EXPECTED_JOYSTICK_PX = 132
EXPECTED_KNOB_PX = 40


def check_joystick_geometry(css: str, findings: list) -> None:
    m = RE_JOYSTICK_SIZE.search(css)
    if not m or (int(m.group(1)), int(m.group(2))) != (EXPECTED_JOYSTICK_PX, EXPECTED_JOYSTICK_PX):
        findings.append(Finding("MO-07", "FAIL", "styles.css",
                                 f"摇杆应为 {EXPECTED_JOYSTICK_PX}×{EXPECTED_JOYSTICK_PX}px，实际 {m.groups() if m else '未找到'}"))
    m = RE_KNOB_SIZE.search(css)
    if not m or (int(m.group(1)), int(m.group(2))) != (EXPECTED_KNOB_PX, EXPECTED_KNOB_PX):
        findings.append(Finding("MO-07", "FAIL", "styles.css",
                                 f"摇杆球应为 {EXPECTED_KNOB_PX}×{EXPECTED_KNOB_PX}px，实际 {m.groups() if m else '未找到'}"))


# ---------------------------------------------------------------------------
# MO-08 PWA 主题色
# ---------------------------------------------------------------------------
def check_manifest_theme(manifest: dict, raw: str, findings: list) -> None:
    theme = str(manifest.get("theme_color", "")).lower()
    bg = str(manifest.get("background_color", "")).lower()
    if theme != "#0e1117":
        findings.append(Finding("MO-08", "FAIL", "manifest.webmanifest",
                                 f"theme_color 应为 #0e1117，实际 {theme or '未设置'}"))
    if bg != "#0b0e13":
        findings.append(Finding("MO-08", "FAIL", "manifest.webmanifest",
                                 f"background_color 应为 #0b0e13，实际 {bg or '未设置'}"))
    if LEGACY_LIGHT_THEME in raw.lower():
        findings.append(Finding("MO-08", "FAIL", "manifest.webmanifest",
                                 f"manifest 里还留着旧的浅色主题 {LEGACY_LIGHT_THEME}（与暗色 UI 不符 ⇒ 启动闪白）"))


# ---------------------------------------------------------------------------
# MO-09 版本号一致
# ---------------------------------------------------------------------------
#: 只有「入口代码资源」共用一个版本号；图片等资源各自计数（?v=6），不参与判定。
#:
#: ⚠️ ``sw.js`` 也要算进来：Service Worker 的**注册 URL** 带不带 ``?v=``
#:    决定了浏览器会不会重新拉 SW。不带 ⇒ 用户永远吃旧 SW。
#:    （2026-10-30 实测踩过：入口升到 v29，``app.js`` 里注册还写着 ``sw.js?v=28``。）
RE_ENTRY_QUERY_V = re.compile(
    r'(?:\./)?((?:styles\.css|app\.js|robot_3d\.js|sw\.js|vendor/[A-Za-z0-9_./-]+\.js))\?v=(\d+)')
RE_CACHE_NAME = re.compile(r'CACHE_NAME\s*=\s*["\'][^"\']*?-v(\d+)["\']')
#: SW 注册 URL（``navigator.serviceWorker.register("./sw.js?v=29")``）
RE_SW_REGISTER = re.compile(r'serviceWorker\.register\(\s*["\'`]\./?sw\.js\?v=(\d+)["\'`]')


def check_version_sync(html: str, sw: str, js_text: str, findings: list) -> None:
    versions = set(RE_ENTRY_QUERY_V.findall(html))
    versions |= set(RE_ENTRY_QUERY_V.findall(js_text))
    if not versions:
        findings.append(Finding("MO-09", "FAIL", "index.html",
                                 "找不到入口代码的 ?v= 版本号（缓存 bust 参数丢了 ⇒ 改了 CSS 用户看不到）"))
        return
    used = {v for _f, v in versions}
    if len(used) > 1:
        files = sorted({f for f, v in versions})
        findings.append(Finding("MO-09", "FAIL", "index.html + *.js",
                                 f"入口代码出现多个版本号 {sorted(used)}（{files}）"
                                 " ⇒ 改了部分文件用户看不到，且 SW 预缓存的键对不上"))
    m = RE_CACHE_NAME.search(sw)
    if not m:
        findings.append(Finding("MO-09", "FAIL", "sw.js",
                                 "sw.js 里找不到 CACHE_NAME 的版本号"))
        return
    if m.group(1) not in used:
        findings.append(Finding("MO-09", "FAIL", "sw.js",
                                 f"sw.js 缓存版本 v{m.group(1)} 与入口代码的 ?v={sorted(used)} 不一致"
                                 "（⇒ 改了前端但 Service Worker 还吐旧缓存）"))
        return
    # SW 注册 URL 的版本必须 == CACHE_NAME 版本 ⇒ 否则浏览器复用旧 SW
    registered = RE_SW_REGISTER.findall(js_text)
    if not registered:
        findings.append(Finding("MO-09", "FAIL", "app.js",
                                 "找不到 serviceWorker.register(\"./sw.js?v=N\")"
                                 "（⇒ SW 注册 URL 没有版本号，改了 sw.js 用户拿不到新版）"))
        return
    for version in registered:
        if version != m.group(1):
            findings.append(Finding("MO-09", "FAIL", "app.js",
                                     f"Service Worker 注册 URL 是 ?v={version}，"
                                     f"但 sw.js 的 CACHE_NAME 是 v{m.group(1)}"
                                     "（⇒ 浏览器复用旧 SW，新预缓存永远不生效）"))


# ---------------------------------------------------------------------------
# MO-10 摄像头面板的层级
# ---------------------------------------------------------------------------
def check_camera_panel_level(html: str, findings: list) -> None:
    """camera-panel 必须挂在 .app-shell 上，不能落在 .screen 内部。

    ``.screen.is-active`` 带 animation ⇒ 会创建 stacking context ⇒
    放在 .screen 里的 fixed 浮层会被 Tab 栏压住（实测踩过）。
    """
    lines = html.splitlines()
    depth = 0
    panel_line = None
    for idx, line in enumerate(lines, start=1):
        if 'id="cameraPanel"' in line:
            panel_line = idx
            break
        depth += len(re.findall(r"<section\b", line))
        depth -= len(re.findall(r"</section>", line))
    if panel_line is None:
        findings.append(Finding("MO-10", "FAIL", "index.html", "找不到 #cameraPanel"))
        return
    if depth != 0:
        findings.append(Finding(
            "MO-10", "FAIL", "index.html",
            f"#cameraPanel 在第 {panel_line} 行，位于 <section> 内部（层级深度 {depth}）"
            "⇒ 会被 .screen 的 stacking context 困住，Tab 栏会压住它"
            "⇒ 必须是 .app-shell 的直接子元素"))


# ---------------------------------------------------------------------------
# MO-11 静态模块闭包 ⊆ serve.py 白名单
# ---------------------------------------------------------------------------
RE_SCRIPT_SRC = re.compile(r'<script[^>]+src="([^"]+)"')
RE_LINK_HREF = re.compile(r'<link[^>]+href="([^"]+)"')
RE_JS_IMPORT = re.compile(r"""(?:^|[\s;])(?:import\s[^'"]*?from\s*|import\s*\(\s*|export\s[^'"]*?from\s*)['"]([^'"]+)['"]""", re.M)
RE_IMPORTMAP = re.compile(r'<script[^>]+type="importmap"[^>]*>(.*?)</script>', re.S)


def _parse_importmap(html: str) -> dict:
    """读 index.html 的 importmap ⇒ 裸模块名 → 实际文件。"""
    m = RE_IMPORTMAP.search(html)
    if not m:
        return {}
    try:
        import json
        data = json.loads(m.group(1))
    except ValueError:
        return {}
    imports = data.get("imports") if isinstance(data, dict) else None
    return imports if isinstance(imports, dict) else {}


def collect_local_refs(mobile: Path) -> dict:
    """返回 {相对路径: [引用它的文件]}，只收本地相对引用。

    裸模块名（``import ... from "three"``）先过 importmap 解析成实际文件。
    """
    return {path: srcs for (path, _q), srcs in collect_requests(mobile).items()}


def collect_requests(mobile: Path) -> dict:
    """返回 {(相对路径, 查询串): [引用它的文件]}。

    ★ 必须带**查询串**：Service Worker 的预缓存键是完整 URL，
    页面请求 ``./styles.css?v=29`` 而预缓存写 ``./styles.css``
    ⇒ 两个键不同 ⇒ 预缓存那一份永远用不上（这坑踩过）。
    """
    refs: dict = {}
    seen = set()
    html = _read(mobile / "index.html") if (mobile / "index.html").is_file() else ""
    importmap = _parse_importmap(html)

    def add(target: str, source: str) -> None:
        if not target:
            return
        if target.startswith(("http:", "https:", "data:", "//", "#")):
            return
        if target.startswith("/"):
            return  # 绝对路径（服务端路由），不是仓库内文件
        if target in importmap:
            target = importmap[target]
            if not isinstance(target, str):
                return
        clean, _, query = target.partition("?")
        clean = clean.split("#", 1)[0]
        if not clean or clean.endswith("/"):
            return
        rel = os.path.normpath(clean).replace("\\", "/")
        if rel.startswith(".."):
            return
        refs.setdefault((rel, query), []).append(source)

    queue = ["index.html"]
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        path = mobile / rel
        if not path.is_file():
            continue
        if path.suffix == ".html":
            text = _read(path)
            for m in RE_SCRIPT_SRC.finditer(text):
                add(m.group(1), rel)
            for m in RE_LINK_HREF.finditer(text):
                add(m.group(1), rel)
        elif path.suffix == ".js":
            text = _read(path)
            for m in RE_JS_IMPORT.finditer(text):
                add(m.group(1), rel)

    # 递归把新发现的文件也加进来
    for (rel, _q) in list(refs):
        if rel in seen:
            continue
        seen.add(rel)
        path = mobile / rel
        if path.is_file() and path.suffix == ".js":
            text = _read(path)
            for m in RE_JS_IMPORT.finditer(text):
                add(m.group(1), rel)
    return refs


RE_STATIC_PATHS = re.compile(r'"(/[^"]*)"')


def check_static_closure(mobile: Path, files: dict, findings: list) -> None:
    serve = files.get("serve.py", "")
    allowed = set(RE_STATIC_PATHS.findall(serve))
    refs = collect_local_refs(mobile)
    for rel, sources in sorted(refs.items()):
        if not (mobile / rel).is_file():
            findings.append(Finding("MO-11", "FAIL", rel,
                                     f"被引用但文件不存在（引用方：{sorted(set(sources))}）"))
            continue
        url = "/" + rel
        if url in allowed:
            continue
        if url.startswith("/assets/"):
            continue  # serve.py 对 /assets/ 走动态放行
        findings.append(Finding("MO-11", "FAIL", "serve.py",
                                 f"静态白名单里没有 {url}（引用方：{sorted(set(sources))}）"
                                 " ⇒ serve.py 会回 404 ⇒ 手机端直接白屏"))


# ---------------------------------------------------------------------------
# MO-12 触控热区
# ---------------------------------------------------------------------------
RE_ICON_BUTTON = re.compile(r"\.icon-button\s*\{([^}]*)\}")
RE_ICON_BUTTON_AFTER = re.compile(r"\.icon-button::after\s*\{([^}]*)\}")


def _px(rule: str, prop: str) -> int:
    m = re.search(prop + r":\s*(\d+)px", rule)
    return int(m.group(1)) if m else 0


def _inset(rule: str) -> int:
    m = re.search(r"inset:\s*-(\d+)px", rule)
    return int(m.group(1)) if m else 0


def check_touch_target(css: str, findings: list) -> None:
    m = RE_ICON_BUTTON.search(css)
    if not m:
        findings.append(Finding("MO-12", "FAIL", "styles.css", "找不到 .icon-button 规则"))
        return
    size = _px(m.group(1), "width")
    after = RE_ICON_BUTTON_AFTER.search(css)
    grow = _inset(after.group(1)) if after else 0
    reach = size + 2 * grow
    if reach < MIN_TOUCH_TARGET_PX:
        findings.append(Finding(
            "MO-12", "FAIL", "styles.css",
            f"图标按钮触控热区 {reach}px < {MIN_TOUCH_TARGET_PX}px"
            f"（视觉 {size}px + ::after 扩展 {grow}px×2）"))


# ---------------------------------------------------------------------------
# MO-13 CSS 变量未定义引用
# ---------------------------------------------------------------------------
RE_VAR_DEF = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
#: 只认**没有兜底值**的引用：``var(--x, 0px)`` 是合法写法（运行时可注入），不算缺陷。
RE_VAR_USE_NOFALLBACK = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)")


def check_css_vars(css: str, findings: list) -> None:
    defined = set(RE_VAR_DEF.findall(css))
    used = set(RE_VAR_USE_NOFALLBACK.findall(css))
    missing = sorted(used - defined)
    if missing:
        findings.append(Finding("MO-13", "FAIL", "styles.css",
                                 f"引用了未定义且无兜底的 CSS 变量：{missing}"
                                 " ⇒ 计算值阶段非法 ⇒ 那条声明直接失效"))


# ---------------------------------------------------------------------------
# MO-14 摄像头面板默认隐藏
# ---------------------------------------------------------------------------
def check_camera_panel_hidden(html: str, findings: list) -> None:
    m = re.search(r'<div[^>]*id="cameraPanel"[^>]*>', html)
    if not m:
        findings.append(Finding("MO-14", "FAIL", "index.html", "找不到 #cameraPanel 元素"))
        return
    if "hidden" not in m.group(0):
        findings.append(Finding("MO-14", "FAIL", "index.html",
                                 "#cameraPanel 必须默认 hidden（进 App 不该抢注意力）"))


# ---------------------------------------------------------------------------
# MO-15 sw.js 缓存清单
# ---------------------------------------------------------------------------
RE_APP_FILES_BLOCK = re.compile(r"APP_FILES\s*=\s*\[(.*?)\]", re.S)
RE_QUOTED = re.compile(r"[\"']([^\"']+)[\"']")


def check_sw_precache(sw: str, mobile: Path, findings: list) -> None:
    m = RE_APP_FILES_BLOCK.search(sw)
    if not m:
        findings.append(Finding("MO-15", "FAIL", "sw.js", "找不到 APP_FILES 清单"))
        return

    listed = set()
    for raw in RE_QUOTED.findall(m.group(1)):
        clean, _, query = raw.partition("?")
        rel = clean.lstrip("./")
        if not rel or rel.startswith("model-assets/"):
            continue  # "/" 是根、model-assets 由服务端专门路由提供
        listed.add((rel, query))

    # ★ 键必须与「页面实际请求的 URL」完全一致（含查询串）
    requested = collect_requests(mobile)
    for (rel, query), sources in sorted(requested.items()):
        if (rel, query) in listed:
            continue
        findings.append(Finding(
            "MO-15", "FAIL", "sw.js",
            f"预缓存清单里没有 {rel}" + (f"?{query}" if query else "")
            + f"（请求方：{sorted(set(sources))}）"
            " ⇒ 预缓存的那一份永远命中不了（键不同）"))

    for rel, _query in sorted(listed):
        if not (mobile / rel).is_file():
            findings.append(Finding("MO-15", "FAIL", "sw.js",
                                     f"APP_FILES 里 {rel} 不存在"))


# ---------------------------------------------------------------------------
# 主扫描
# ---------------------------------------------------------------------------
def scan(repo_root: Path, findings: list) -> dict:
    mobile = repo_root / MOBILE_REL
    if not mobile.is_dir():
        findings.append(Finding("MO-00", "FAIL", MOBILE_REL, "手机端目录不存在"))
        return {}

    files = {}
    for name in ("index.html", "styles.css", "remote_control.js", "serve.py", "sw.js"):
        path = mobile / name
        if path.is_file():
            files[name] = _read(path)
    for name in ("index.html", "styles.css", "serve.py", "sw.js"):
        if name not in files:
            findings.append(Finding("MO-00", "FAIL", name, "文件缺失"))

    check_no_replacement_char(mobile, findings)

    html = files.get("index.html", "")
    css = files.get("styles.css", "")

    if html:
        check_tabs_and_speed(html, findings)
        check_forbidden_controls(files, findings)
        check_pitch_and_deadzone(files, findings)
        check_camera_panel_level(html, findings)
        check_camera_panel_hidden(html, findings)

    if css:
        check_joystick_geometry(css, findings)
        check_touch_target(css, findings)
        check_css_vars(css, findings)

    manifest_path = mobile / "manifest.webmanifest"
    if manifest_path.is_file():
        raw = _read(manifest_path)
        try:
            import json
            manifest = json.loads(raw)
        except ValueError:
            manifest = {}
            findings.append(Finding("MO-08", "FAIL", "manifest.webmanifest", "JSON 解析失败"))
        check_manifest_theme(manifest, raw, findings)

    if "index.html" in files and "sw.js" in files:
        js_text = ""
        for name in ("app.js", "robot_3d.js"):
            path = mobile / name
            if path.is_file():
                js_text += _read(path)
        check_version_sync(files["index.html"], files["sw.js"], js_text, findings)

    if "serve.py" in files:
        check_static_closure(mobile, files, findings)

    if "sw.js" in files:
        check_sw_precache(files["sw.js"], mobile, findings)

    return {"mobile": MOBILE_REL}


# ---------------------------------------------------------------------------
# 自检：把真实现件复制一份，逐条改坏 ⇒ 对应判据必须变红
# ---------------------------------------------------------------------------
def _fixture(repo_root: Path, td: str) -> Path:
    src = repo_root / MOBILE_REL
    dst = Path(td) / MOBILE_REL
    shutil.copytree(src, dst)
    return dst


def _mutate(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
    return True


def _mutate_re(path: Path, pattern: str, repl: str, count: int = 1) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text, n = re.subn(pattern, repl, text, count=count)
    if n == 0:
        return False
    path.write_text(new_text, encoding="utf-8", newline="")
    return True


def run_self_test(repo_root: Path) -> int:
    print("[self-test] check_mobile_app.py 门禁自检")
    print("=" * 68)
    passed = failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    def scan_of(mobile: Path) -> list:
        findings: list = []
        with tempfile.TemporaryDirectory() as td2:
            tmp_repo = Path(td2)
            target = tmp_repo / MOBILE_REL
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(mobile, target)
            scan(tmp_repo, findings)
        return findings

    def codes(findings: list) -> set:
        return {f.code for f in findings if f.severity == "FAIL"}

    mobile = repo_root / MOBILE_REL
    if not mobile.is_dir():
        print("  SKIP  找不到 %s，无法做变异自检" % MOBILE_REL)
        return 1

    # 0) 健康夹具：真实现件必须零 FAIL
    baseline = scan_of(mobile)
    check("真实现件零 FAIL", not baseline,
          str([(f.code, f.msg) for f in baseline]))

    # 1) MO-01 注入 U+FFFD
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "styles.css", ":root", ":root /* \ufffd */")
        check("MO-01 乱码被抓到", "MO-01" in codes(scan_of(m)))

    # 2) MO-02 加第 4 个 Tab
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        idx = (m / "index.html").read_text(encoding="utf-8")
        marker = '<button class="tab-button" type="button" data-target="settings">'
        extra = ('<button class="tab-button" type="button" data-target="chat">'
                 '<span>多余</span></button>\n')
        (m / "index.html").write_text(idx.replace(marker, extra + marker, 1),
                                      encoding="utf-8", newline="")
        check("MO-02 Tab 数写错被抓到", "MO-02" in codes(scan_of(m)))

    # 3) MO-03 把删掉的滑块加回来
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "index.html", "</section>", '<input id="pitchSlider" /></section>')
        check("MO-03 旧滑块复活被抓到", "MO-03" in codes(scan_of(m)))

    # 4) MO-04 速度圆圈改成 3 个（删掉最后一档）
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate_re(m / "index.html",
                   r'\n\s*<button type="button" class="speed-dot"[^>]*data-speed-level="3"[^>]*>.*?</button>',
                   "")
        check("MO-04 速度档数写错被抓到", "MO-04" in codes(scan_of(m)))

    # 5) MO-05 初始俯仰改掉
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "remote_control.js", "let currentPitch = 45", "let currentPitch = 10")
        check("MO-05 初始俯仰写错被抓到", "MO-05" in codes(scan_of(m)))

    # 6) MO-06 死区改掉
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "remote_control.js", "JOYSTICK_DEAD_ZONE = 0.08",
                "JOYSTICK_DEAD_ZONE = 0.02")
        check("MO-06 死区写错被抓到", "MO-06" in codes(scan_of(m)))

    # 7) MO-07 摇杆尺寸改掉
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "styles.css", "width: 132px; height: 132px", "width: 96px; height: 96px")
        check("MO-07 摇杆尺寸写错被抓到", "MO-07" in codes(scan_of(m)))

    # 8) MO-08 主题色改回浅色
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "manifest.webmanifest", '"theme_color": "#0e1117"',
                '"theme_color": "#f7f7fa"')
        check("MO-08 主题色写错被抓到", "MO-08" in codes(scan_of(m)))

    # 9) MO-09 版本号漂移（把 index.html 的入口版本号改成别的值）
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate_re(m / "index.html", r"(\./styles\.css\?v=)\d+", r"\g<1>999")
        check("MO-09 版本号漂移被抓到", "MO-09" in codes(scan_of(m)))

    # 9b) MO-09 Service Worker **注册 URL** 的版本落后
    # （2026-10-30 实测踩过：入口升到 v29，app.js 里注册还写着 sw.js?v=28
    #   ⇒ 浏览器复用旧 SW，新预缓存永远不生效）
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate_re(m / "app.js",
                   r'(serviceWorker\.register\("\./sw\.js\?v=)\d+', r"\g<1>1")
        check("MO-09 SW 注册 URL 版本落后被抓到", "MO-09" in codes(scan_of(m)))

    # 10) MO-10 摄像头面板挪进 .screen（在面板**之前**插一行 section，深度才会真的 +1）
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate_re(m / "index.html",
                   r"(\n)(\s*<div id=\"cameraPanel\")",
                   r"\1      <section class=\"screen\">\1\2")
        check("MO-10 面板层级下沉被抓到", "MO-10" in codes(scan_of(m)))

    # 11) MO-11 白名单漏文件
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "serve.py", '"/chat.js",\n', "")
        check("MO-11 白名单漏文件被抓到", "MO-11" in codes(scan_of(m)))

    # 12) MO-12 触控热区缩到 32px
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "styles.css", ".icon-button::after { content: \"\"; position: absolute; inset: -4px;",
                ".icon-button::after { content: \"\"; position: absolute; inset: 0px;")
        check("MO-12 触控热区过小被抓到", "MO-12" in codes(scan_of(m)))

    # 13) MO-13 未定义 CSS 变量
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "styles.css", ".joystick {", ".joystick { color: var(--nope-not-defined);")
        check("MO-13 未定义变量被抓到", "MO-13" in codes(scan_of(m)))

    # 14) MO-14 面板默认不隐藏
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate(m / "index.html", 'id="cameraPanel" class="camera-panel" hidden',
                'id="cameraPanel" class="camera-panel"')
        check("MO-14 面板默认可见被抓到", "MO-14" in codes(scan_of(m)))

    # 15) MO-15 预缓存键与请求 URL 不一致（去掉 app.js 那一项）
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate_re(m / "sw.js", r'"\./app\.js[^"]*",\n', "")
        check("MO-15 预缓存缺件被抓到", "MO-15" in codes(scan_of(m)))

    # 16) MO-15 预缓存键少了查询串（键不同 ⇒ 永远命中不了）
    with tempfile.TemporaryDirectory() as td:
        m = _fixture(repo_root, td)
        _mutate_re(m / "sw.js", r'"\./styles\.css\?v=\d+"', '"./styles.css"')
        check("MO-15 预缓存键缺查询串被抓到", "MO-15" in codes(scan_of(m)))

    print("=" * 68)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="手机端 UI 规格 ↔ 实现 一致性体检")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--self-test", action="store_true", help="门禁自检（变异夹具）")
    args = ap.parse_args(argv)

    root = Path(os.path.abspath(args.root))
    if args.self_test:
        return run_self_test(root)

    findings: list = []
    scan(root, findings)
    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]
    print("=" * 70)
    print("check_mobile_app.py —— 手机端 UI 规格 ↔ 实现 一致性体检")
    print("=" * 70)
    print("手机端目录    : %s" % MOBILE_REL)
    print("-" * 70)
    for f in findings:
        print("[%s] %s  %s" % (f.severity, f.where, f.msg))
    print("-" * 70)
    print("FAIL=%d  WARN=%d" % (len(fails), len(warns)))
    if not fails:
        print("ALL PASS —— 手机端实现与规格一致。")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
