#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""StackChan 发布前体检器 (release-readiness checker)。

用途：GitHub 开源发布前，一次跑完六类检查并给出可门禁化的结论：
    文档规范 / 链接 / 发布合规 / 密钥隐私 / 一致性 / git 状态

设计约束：
  * Python 3.12，纯标准库（不使用 numpy / requests 等第三方依赖）。
  * 只读：绝不修改被检仓库的任何文件；--json 只写调用方指定的输出路径。
  * 健壮：单文件读取或解析失败不中断整体扫描，记 DOC_UNREADABLE(WARN) 后继续。
  * 隐私：疑似密钥只输出掩码（如 sk-abcd****wxyz），绝不打印原文。
  * 性能：整仓扫描（~80 份 md / 数 MB）应在 3 秒内完成。

用法：
    py -3.12 tools/repo_release_check.py --root "D:\\jss18\\AI\\StackChan-main"
    py -3.12 tools/repo_release_check.py --root "<path>" --json out.json
    py -3.12 tools/repo_release_check.py --self-test

退出码：
    0 = 无 FAIL（可含 WARN / INFO）
    1 = 存在 FAIL
    2 = 用法或环境错误

固定检查码（供门禁引用）：
    文档规范  DOC_TABLE_COLS / DOC_TABLE_BLANK / DOC_TABLE_PIPE / DOC_BOM / DOC_CRLF / DOC_UNREADABLE
    链接      MD_LINK_BROKEN / MD_ASSET_MISSING
    发布合规  RELEASE_LICENSE_MISSING / RELEASE_NOTICE_MISSING / RELEASE_TRADEMARK_STMT / RELEASE_LICENSE_CLAUSE
    密钥隐私  SECRET_API_KEY / SECRET_WIFI_PASSWORD / SECRET_IN_PRIVATE
    资产来源  OFFICIAL_ASSET_IN_REPO（官方 `app/` 无 LICENSE ⇒ 其资产不得进仓）
    一致性    DOC_COUNT_STALE / GIT_UNTRACKED / GIT_DIRTY_PRIVATE

规则来源：表格列数 / 表格空行 / 单元格竖线 / BOM / 行尾 的判定口径移植自
`D:\\AP\\AP7000\\ai-workspace\\stackchan-research\\check_docs.py`（表头识别、
分隔行识别、未转义竖线分列的算法与参考实现逐字一致；参考实现里
`bad_blank` 因 while 条件不可达而恒为 0，本文件按同一意图补齐了可达实现，
见 `_check_tables` 的注释）。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

try:  # Windows 控制台兜底：中文 + 掩码输出不因编码报错而崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - 旧解释器 / 无 stdout
    pass


# ---------------------------------------------------------------------------
# 常量：规则表
# ---------------------------------------------------------------------------

FENCE = chr(96) * 3
SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
UNESC_PIPE_RE = re.compile(r"(?<!\\)\|")

SEV_FAIL, SEV_WARN, SEV_INFO, SEV_PASS = "FAIL", "WARN", "INFO", "PASS"
SEV_ORDER = {SEV_FAIL: 0, SEV_WARN: 1, SEV_INFO: 2, SEV_PASS: 3}

# 每个检查码「出问题时的严重级别」。PASS 级别只在少数原子检查上产生。
CODE_SEVERITY = {
    "DOC_TABLE_COLS": SEV_FAIL,
    "DOC_TABLE_BLANK": SEV_FAIL,
    "DOC_TABLE_PIPE": SEV_FAIL,
    "DOC_BOM": SEV_FAIL,
    "DOC_CRLF": SEV_WARN,
    "DOC_UNREADABLE": SEV_WARN,
    "MD_LINK_BROKEN": SEV_FAIL,
    "MD_ASSET_MISSING": SEV_FAIL,
    "RELEASE_LICENSE_MISSING": SEV_FAIL,
    "RELEASE_NOTICE_MISSING": SEV_FAIL,
    "RELEASE_TRADEMARK_STMT": SEV_FAIL,
    "RELEASE_LICENSE_CLAUSE": SEV_WARN,
    "SECRET_API_KEY": SEV_FAIL,
    "SECRET_WIFI_PASSWORD": SEV_FAIL,
    "SECRET_IN_PRIVATE": SEV_FAIL,
    "DOC_COUNT_STALE": SEV_WARN,
    "GIT_UNTRACKED": SEV_INFO,
    "GIT_DIRTY_PRIVATE": SEV_FAIL,
    "OFFICIAL_ASSET_IN_REPO": SEV_FAIL,
}

# 目录黑名单：不进入（构建产物 / 依赖 / 工具缓存）
PRUNE_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".cache",
    "node_modules", ".pnpm-store", "build", "dist", "out", "target",
    "DerivedData", "coverage", "htmlcov", ".next", ".gradle",
}

# 二进制扩展名：不做文本扫描
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff",
    ".heic", ".icns", ".mp4", ".mov", ".avi", ".webm", ".mkv", ".mp3", ".wav", ".pcm",
    ".ogg", ".m4a", ".aac", ".flac", ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2",
    ".xz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib", ".a", ".lib", ".o",
    ".obj", ".class", ".jar", ".whl", ".pyc", ".pyo", ".pkl", ".bin", ".dat",
    ".db", ".sqlite", ".ttf", ".otf", ".woff", ".woff2", ".eot", ".wasm",
    ".node", ".lock",
}

# 视为「图片 / 附件」的扩展名（docs/** 下引用缺失时记 MD_ASSET_MISSING）
ASSET_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tif",
    ".tiff", ".heic", ".pdf", ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar",
    ".mp4", ".mov", ".webm", ".mp3", ".wav", ".pcm", ".ogg", ".m4a",
    ".xlsx", ".xls", ".docx", ".pptx", ".csv", ".json", ".yaml", ".yml",
    ".html", ".htm", ".ttf", ".otf", ".woff", ".woff2", ".key", ".pem", ".p12",
    ".bin", ".csv", ".txt",
}

# ⚠️ 官方 `app/` 目录下的资产：**许可未取得，永不入库**
#    官方 m5stack/StackChan 的 `app/` 只有 SPDX 头、**没有 LICENSE 文件**
#    （见 docs/research/33）⇒ 按 docs/spec/00 的 O-12 决策（已定：不用），
#    `stack_chan_model.glb` 等官方资产**不得随本仓分发**。
#    ⚠️ 这条是 2026-10-30 首次公开发布前**真实踩到**的漏：
#       `prototype/mobile-v2/assets/` 里躺着一份 3.3 MB 的官方模型，
#       而当时的门禁只查密钥 / private/ / 商标，**没人查资产来源**。
OFFICIAL_ASSET_NAMES = {
    "stack_chan_model.glb",
}
#: 3D 模型扩展名 —— 本仓的 3D 预览一律用**程序化几何体**（three.js MIT），
#: 所以仓内出现任何 3D 模型文件都应当是误入。
MODEL_EXTS = {".glb", ".gltf", ".fbx", ".obj"}
#: 官方 App 目录名（`app/assets/`）—— 出现在仓内即说明抄了官方资产目录
OFFICIAL_APP_DIR_RE = re.compile(r"(^|/)app/assets/")

# 计数声明的判定：正则 `(\d+)\s*份` + 同行须出现下列关键词之一
COUNT_CLAIM_RE = re.compile(r"(\d+)\s*份")
COUNT_KEYWORDS = (
    "研究档案", "调研档案", "设计情报", "情报库", "档案", "取证",
    "research", "Research", "文档", "证据",
)
# 参与「研究档案 N 份」一致性核对的文件
COUNT_STALE_FILES = ("README.md", "docs/research/README.md")

# 商标声明：按「概念分组」匹配，命中任意 2 组即视为声明到位。
# （brief 给的是 6 个字面关键词；这里按概念分组并补齐等价说法，
#   避免把「社区第三方项目 / 无隶属关系 / 未获其背书」这类合规写法误判为缺失。）
TRADEMARK_GROUPS = (
    ("non_official", ("unofficial", "非官方", "not affiliated", "无隶属关系",
                      "非 m5stack 官方", "不隶属于")),
    ("trademark", ("trademark", "商标")),
    ("no_endorsement", ("未获背书", "未获其背书", "no endorsement",
                        "未获官方背书", "背书")),
    ("third_party", ("第三方项目", "社区第三方", "third-party", "third party")),
)

# 疑似密钥规则：只报「疑似」，输出掩码
SECRET_PATTERNS = (
    ("sk-key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{16,}")),
    ("env-assign", re.compile(
        r"(?<![A-Za-z0-9_])MINIMAX_API_KEY[ \t]*[:=][ \t]*[\"']?([A-Za-z0-9_\-]{20,})")),
    ("tencent-akid", re.compile(r"(?<![A-Za-z0-9])AKID[A-Za-z0-9]{12,}")),
)
# 长 Base64 / 高熵串（≥40 字符）。
# 字符集刻意只收 [A-Za-z0-9]（可带尾部 '='）：这样 snake_case / kebab-case 的
# 标识符（GitHub feature flag 名、变量名）不会命中，避免几百条噪声。
LONG_B64_RE = re.compile(
    r"(?<![A-Za-z0-9+/=_\-])([A-Za-z0-9]{40,}={0,2})(?![A-Za-z0-9+/=_\-])")
PLACEHOLDER_HINTS = (
    "example", "placeholder", "changeme", "yourkey", "your_key",
    "yourpassword", "your_password", "your-api", "xxxx", "redacted",
    "dummy", "sample", "fakekey", "testkey", "notreal", "insert",
    "aaaaaaaa", "1234567890", "abcdefghijklmnop",
)

# Wi-Fi 口令
WIFI_RE = re.compile(
    r"(?i)\b(ssid\d*|password\d*|passwd|pwd|psk|wifi_?password)\b"
    r"[ \t]*[:=][ \t]*[\"']?([^\s\"'`,;]{8,})")
#: **成员访问表达式**（`passwordInput.value` / `selectedNetwork.ssid`）。
#: ⚠️ 这类值是**运行时读取**，不是写死的口令 ⇒ 必须放过。
#:   实测 2026-10-30：手机端 `settings.js` 的 `passwordInput.value` 与
#:   `selectedNetwork.ssid` 被误报成「疑似真实 Wi-Fi 口令」⇒ 整仓 2 条假 FAIL。
#:   注意：**带引号的字面量不受影响**（真口令在源码里一定带引号），
#:   配置文件里的裸值也仍然会被扫到。
MEMBER_ACCESS_RE = re.compile(
    r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+")
WIFI_STOPWORDS = {
    "str", "int", "float", "bool", "bytes", "none", "optional", "list", "dict",
    "strnone", "string", "password", "yourpassword", "your_password",
}

# markdown 行内链接 / 图片 / 引用式定义
MD_INLINE_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
MD_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]\n]+\]:[ \t]*(\S+)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

# 引号跨度：链接若落在引号内，视为「引用外部仓库/上游原文」，不做仓库内存在性检查。
QUOTE_SPAN_RES = (
    re.compile(r"「[^」\n]*」"),
    re.compile(r"『[^』\n]*』"),
    re.compile(r"\"[^\"\n]*\""),
)

# 扫描器自身文件名：自检夹具里故意写了假密钥，扫描时跳过自己。
SELF_FILENAME = "repo_release_check.py"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    code: str
    severity: str
    file: str
    line: int | None
    message: str

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def ncols(line: str) -> int:
    """表格行分列数：只按「未转义」的 | 分列（\\| 是合法的单元格内竖线）。

    与参考实现 check_docs.py 的 ncols() 逐字一致。
    """
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return len(UNESC_PIPE_RE.split(s))


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in Counter(text).values())


def mask_secret(token: str) -> str:
    """密钥掩码：保留头 4 尾 4，中间打码。"""
    token = token.strip()
    if len(token) <= 8:
        return token[:2] + "****"
    return token[:4] + "****" + token[-4:]


def is_placeholder(value: str) -> bool:
    low = value.lower()
    return any(hint in low for hint in PLACEHOLDER_HINTS)


# 代码标识符形态的长串（**不是**密钥）。
#
# ⚠️ 实测 2026-10-25：Swift 测试函数名
#    `testPositionOffsetIsClampedToPlusMinus16Pixels`（46 字符纯驼峰）
#    被长 Base64 正则命中并报成「疑似高熵长密钥」⇒ 假阳性。
#
#    判据（比「是不是驼峰」更严，避免误伤真密钥）：
#    1) 长度 ≥ 40；
#    2) 按**驼峰边界**切出的每个词段都必须是「首字母大写的词」或「全小写词」；
#       ⚠️ 切词要按**驼峰边界**切，不能按「字母块 / 数字块」切 ——
#          后者会把 `PlusMinus16Pixels` 里的 `16` 单独切出来当词段，直接误判。
#    3) 不含连续 3 位以上的数字串（真密钥常有）。
#
# ⇒ 判为「标识符」则跳过；但**只跳过长串本身**，不放过同行的真密钥。
_CAMEL_WORD_RE = re.compile(r"^[A-Z][a-z]*$|^[a-z]+$")
_CAMEL_SPLIT_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|[0-9]+")
_DIGIT_RUN_RE = re.compile(r"[0-9]{3,}")


def looks_like_code_identifier(token: str) -> bool:
    """判断一个长串是否更像「代码标识符」而不是「密钥」。

    ⚠️ 这是**假阳性过滤**，不是「安全判定」——
    判定为标识符只意味着「不值得报」，不意味着「一定是安全的」。
    """
    if len(token) < 40:
        return False
    # 真密钥常含 3 位以上连续数字
    if _DIGIT_RUN_RE.search(token):
        return False
    # 按驼峰边界切词：`testPositionOffsetIsClampedToPlusMinus16Pixels`
    #   → ['test','Position','Offset','Is','Clamped','To','Plus','Minus','16','Pixels']
    parts = [p for p in _CAMEL_SPLIT_RE.findall(token) if p]
    if len(parts) < 3:
        return False
    # 每个词段都必须是「首字母大写的词」或「全小写词」或「纯数字段」
    return all(_CAMEL_WORD_RE.match(p) or p.isdigit() for p in parts)


def strip_fenced_blocks(lines: list[str]) -> list[str]:
    """把围栏代码块内容置空（保留行号），用于「正文」关键字匹配。"""
    out = list(lines)
    infence = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(FENCE):
            infence = not infence
            out[i] = ""
            continue
        if infence:
            out[i] = ""
    return out


# ---------------------------------------------------------------------------
# 体检器
# ---------------------------------------------------------------------------

class RepoChecker:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.findings: list[Finding] = []
        self.md_files: list[Path] = []
        self.text_files: list[Path] = []
        self.bytes_scanned = 0
        self.started = time.monotonic()
        self.ignored_paths: set[str] = self._load_git_ignored()

    def _load_git_ignored(self) -> set[str]:
        """列出被 .gitignore 忽略的文件（相对路径，POSIX 分隔）。

        ⛔ **被忽略的文件不会进库，所以它们不该参与发布体检** ——
        否则像 `docs/research/_tmp_*` 这类临时下载物会持续产生假 FAIL。
        非 git 仓库 / git 不可用时返回空集（不跳过任何文件，保持严格）。
        """
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.root), "ls-files", "--others",
                 "--ignored", "--exclude-standard", "-z"],
                capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return set()
        if proc.returncode != 0:
            return set()
        raw = proc.stdout.decode("utf-8", "replace")
        return {p for p in raw.split("\0") if p}

    def _is_ignored(self, path: Path) -> bool:
        if not self.ignored_paths:
            return False
        try:
            rel = path.relative_to(self.root).as_posix()
        except ValueError:
            return False
        return rel in self.ignored_paths

    # -- 基础设施 ---------------------------------------------------------

    def rel(self, path: Path) -> str:
        try:
            p = Path(path).resolve().relative_to(self.root)
        except Exception:
            return str(path)
        s = p.as_posix()
        return s if s else "."

    def add(self, code: str, severity: str, file: str, line: int | None,
            message: str) -> None:
        self.findings.append(Finding(code, severity, file, line, message))

    def _walk_files(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
            for name in filenames:
                yield Path(dirpath) / name

    def _collect(self) -> None:
        for path in self._walk_files():
            if self._is_ignored(path):
                continue          # 被 .gitignore 忽略 ⇒ 不会进库 ⇒ 不体检
            try:
                if path.suffix.lower() == ".md":
                    self.md_files.append(path)
                    self.text_files.append(path)
                    continue
                if path.suffix.lower() in BINARY_EXTS:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size > 2 * 1024 * 1024:
                    continue
                with path.open("rb") as fh:
                    head = fh.read(8192)
                if b"\x00" in head:
                    continue
                self.text_files.append(path)
            except OSError:
                continue
        self.md_files.sort()
        self.text_files.sort()

    # -- 文档规范（表格 / BOM / 行尾）-------------------------------------

    def _check_md_file(self, path: Path) -> None:
        rel = self.rel(path)
        try:
            raw = path.read_bytes()
        except Exception as exc:
            self.add("DOC_UNREADABLE", SEV_WARN, rel, None,
                     f"读取失败：{exc}")
            return
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            self.add("DOC_UNREADABLE", SEV_WARN, rel, None,
                     f"非 UTF-8 编码，无法解析：{exc}")
            return

        if raw[:3] == b"\xef\xbb\xbf":
            self.add("DOC_BOM", SEV_FAIL, rel, 1,
                     "文件带 UTF-8 BOM（应去掉 BOM）")
        crlf = raw.count(b"\r\n")
        if crlf:
            self.add("DOC_CRLF", SEV_WARN, rel, 1,
                     f"文件含 {crlf} 处 CRLF 行尾（仓库约定 LF）")

        lines = text.replace("\r\n", "\n").split("\n")
        self._check_tables(rel, lines)
        self._check_links(rel, path, lines)

    def _report_in_cell_pipes(self, rel: str, lineno: int, line: str) -> None:
        """单元格内未转义的竖线。

        判定：表格行去掉首尾竖线后，剩余内部竖线若「左右两邻都不是空白、
        也不是另一个竖线」，即认为它是写在单元格内容里的裸竖线（应写成 \\|）。
        只在一侧邻接非空白的（如 `|内容| `）是 GFM 允许的紧凑写法，不算缺陷。
        分隔行（|---|---|）不参与判定。
        """
        s = line.strip()
        if SEP_RE.match(s):
            return
        body = s
        if body.startswith("|"):
            body = body[1:]
        if body.endswith("|"):
            body = body[:-1]
        for m in UNESC_PIPE_RE.finditer(body):
            i = m.start()
            prev = body[i - 1] if i > 0 else ""
            nxt = body[i + 1] if i + 1 < len(body) else ""
            if prev in ("", "|") or nxt in ("", "|"):
                continue
            if prev.isspace() or nxt.isspace():
                continue
            self.add("DOC_TABLE_PIPE", SEV_FAIL, rel, lineno,
                     "表格单元格内出现未转义的竖线 |，应写成 \\|")
            return

    def _check_tables(self, rel: str, lines: list[str]) -> None:
        """表格块检查（口径移植自参考实现 check_docs.py）。

        参考实现的 `bad_blank` 分支因 while 条件（必须以 | 开头）而不可达，
        这里按同一意图给出可达实现：表格块之后若紧跟空行、且空行之后
        又出现「没有重新声明表头/分隔行」的表格续行，说明同一张表被空行
        截断 ⇒ DOC_TABLE_BLANK。两张各自带表头的独立表格不算缺陷。
        """
        infence = False
        i = 0
        n = len(lines)
        while i < n:
            s = lines[i].strip()
            if s.startswith(FENCE):
                infence = not infence
                i += 1
                continue
            if (not infence) and s.startswith("|") and i + 1 < n \
                    and SEP_RE.match(lines[i + 1].strip()):
                header_cols = ncols(lines[i])
                self._report_in_cell_pipes(rel, i + 1, lines[i])
                j = i + 2
                while j < n and lines[j].strip().startswith("|"):
                    self._report_in_cell_pipes(rel, j + 1, lines[j])
                    row_cols = ncols(lines[j])
                    if row_cols != header_cols:
                        self.add("DOC_TABLE_COLS", SEV_FAIL, rel, j + 1,
                                 f"表格行列数 {row_cols} != 表头 {header_cols} 列")
                    j += 1
                # 空行截断检测
                if j < n and lines[j].strip() == "":
                    k = j + 1
                    while k < n and lines[k].strip() == "":
                        k += 1
                    resumes = (
                        k < n
                        and lines[k].strip().startswith("|")
                        and not (k + 1 < n and SEP_RE.match(lines[k + 1].strip()))
                    )
                    if resumes:
                        self.add("DOC_TABLE_BLANK", SEV_FAIL, rel, j + 1,
                                 "表格块内出现空行（同一张表被空行截断）")
                i = j
                continue
            i += 1

    # -- 链接 -------------------------------------------------------------

    def _link_target(self, raw: str) -> str | None:
        """从 markdown 链接目标里抽出仓库内相对路径；不可查的返回 None。"""
        t = raw.strip()
        if t.startswith("<") and ">" in t:
            t = t[1:t.index(">")]
        else:
            m = re.match(r"^(\S+)", t)
            t = m.group(1) if m else ""
        t = t.strip()
        if not t:
            return None
        if t.startswith("#"):
            return None
        if t.startswith("//") or t.startswith("/"):
            return None
        if "\\" in t:
            return None  # Windows 路径写法，跳过
        if SCHEME_RE.match(t):
            return None  # http/https/mailto/... 跳过
        t = t.split("#", 1)[0]
        t = t.split("?", 1)[0]
        if not t:
            return None
        try:
            t = unquote(t)
        except Exception:
            pass
        return t or None

    def _check_links(self, rel: str, path: Path, lines: list[str]) -> None:
        in_docs = rel.startswith("docs/")
        infence = False
        for idx, line in enumerate(lines):
            s = line.strip()
            if s.startswith(FENCE):
                infence = not infence
                continue
            if infence:
                continue
            spans = []
            for rx in QUOTE_SPAN_RES:
                for m in rx.finditer(line):
                    spans.append((m.start(), m.end()))
            for m in MD_INLINE_LINK_RE.finditer(line):
                if any(st <= m.start() < en for st, en in spans):
                    continue  # 引号内的外部引用，不查仓库内存在性
                self._check_one_link(rel, path, idx + 1, m.group(1), in_docs)
            mdef = MD_REF_DEF_RE.match(line)
            if mdef:
                self._check_one_link(rel, path, idx + 1, mdef.group(1), in_docs)

    def _check_one_link(self, rel: str, path: Path, lineno: int,
                        raw: str, in_docs: bool) -> None:
        t = self._link_target(raw)
        if not t:
            return
        resolved = os.path.normpath(os.path.join(str(path.parent), t))
        if os.path.exists(resolved):
            return
        suffix = Path(t).suffix.lower()
        if in_docs and suffix in ASSET_EXTS:
            self.add("MD_ASSET_MISSING", SEV_FAIL, rel, lineno,
                     f"引用的图片/附件不存在：{t}")
        else:
            self.add("MD_LINK_BROKEN", SEV_FAIL, rel, lineno,
                     f"相对链接指向不存在的路径：{t}")

    # -- 发布合规 ---------------------------------------------------------

    def _read_text(self, path: Path) -> str | None:
        try:
            return path.read_bytes().decode("utf-8-sig", errors="replace")
        except Exception:
            return None

    def _check_release(self) -> None:
        lic = self.root / "LICENSE"
        if lic.is_file():
            self.add("RELEASE_LICENSE_MISSING", SEV_PASS, ".", None,
                     "LICENSE 存在")
            text = self._read_text(lic) or ""
            has_mit = re.search(r"\bMIT\b", text, re.IGNORECASE) is not None
            has_m5 = "m5stack technology co ltd" in text.lower()
            if not has_mit:
                self.add("RELEASE_LICENSE_CLAUSE", SEV_WARN, "LICENSE", None,
                         "LICENSE 正文缺少 MIT 字样")
            elif not has_m5:
                self.add("RELEASE_LICENSE_CLAUSE", SEV_WARN, "LICENSE", None,
                         "LICENSE 正文缺少 M5Stack Technology CO LTD 署名行")
            else:
                self.add("RELEASE_LICENSE_CLAUSE", SEV_PASS, "LICENSE", None,
                         "LICENSE 含 MIT 与 M5Stack Technology CO LTD 署名")
        else:
            self.add("RELEASE_LICENSE_MISSING", SEV_FAIL, ".", None,
                     "根目录缺少 LICENSE（发布合规必备项）")

        notice = self.root / "NOTICE"
        if notice.is_file():
            self.add("RELEASE_NOTICE_MISSING", SEV_PASS, ".", None,
                     "NOTICE 存在")
        else:
            self.add("RELEASE_NOTICE_MISSING", SEV_FAIL, ".", None,
                     "根目录缺少 NOTICE（第三方署名必备项）")

        readme = self.root / "README.md"
        if not readme.is_file():
            self.add("RELEASE_TRADEMARK_STMT", SEV_FAIL, ".", None,
                     "缺少 README.md，无法确认商标声明")
            return
        text = self._read_text(readme) or ""
        body = "\n".join(strip_fenced_blocks(text.replace("\r\n", "\n").split("\n")))
        low = body.lower()
        hits = [name for name, kws in TRADEMARK_GROUPS
                if any(kw in low for kw in kws)]
        if len(hits) >= 2:
            self.add("RELEASE_TRADEMARK_STMT", SEV_PASS, "README.md", None,
                     "商标与非官方声明到位（命中 " + "、".join(hits) + "）")
        else:
            self.add("RELEASE_TRADEMARK_STMT", SEV_FAIL, "README.md", None,
                     "README 正文缺少「非官方第三方 / 商标属于 M5Stack / 未获背书」声明"
                     f"（仅命中 {len(hits)} 类：{'、'.join(hits) or '无'}，需 ≥2 类）")

    # -- 官方未授权资产 ---------------------------------------------------

    def _check_official_assets(self) -> None:
        """官方 `app/` 目录下的资产不得进仓（许可未取得）。

        依据：`docs/research/33`（官方 `app/` 无 LICENSE）+ `docs/spec/00` O-12
        （已定：官方 3D 模型**不用**，改用程序化几何体）。
        本仓的 3D 预览**一律**是代码，不是模型文件 ⇒ 仓内出现 `.glb` 就是误入。
        """
        hits: list[tuple[str, str]] = []
        for path in self._walk_files():
            if self._is_ignored(path):
                continue  # 被 .gitignore 挡住 ⇒ 不会进库 ⇒ 不体检
            rel = self.rel(path)
            if path.name in OFFICIAL_ASSET_NAMES:
                hits.append((rel, "官方 3D 模型文件名（`app/` 无 LICENSE ⇒ 不分发）"))
            elif path.suffix.lower() in MODEL_EXTS:
                hits.append((rel, "3D 模型文件（本仓只用程序化几何体，模型文件不应进仓）"))
            elif OFFICIAL_APP_DIR_RE.search(rel):
                hits.append((rel, "官方 `app/assets/` 路径下的资产"))
        if hits:
            for rel, why in sorted(hits)[:10]:
                self.add("OFFICIAL_ASSET_IN_REPO", SEV_FAIL, rel, None,
                         f"仓内出现官方未授权资产：{why}")
        else:
            self.add("OFFICIAL_ASSET_IN_REPO", SEV_PASS, ".", None,
                     "仓内没有官方 `app/` 目录下的未授权资产")

    # -- 密钥与隐私 -------------------------------------------------------

    def _check_secrets(self) -> None:
        for path in self.text_files:
            if path.name == SELF_FILENAME:
                continue  # 扫描器自身：自检夹具里故意写了假密钥
            rel = self.rel(path)
            try:
                raw = path.read_bytes()
            except Exception:
                continue
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
            self.bytes_scanned += len(raw)
            seen_tokens: set[tuple[str, str]] = set()

            for name, pat in SECRET_PATTERNS:
                for m in pat.finditer(text):
                    token = m.group(1) if m.lastindex else m.group(0)
                    if (name, token) in seen_tokens:
                        continue
                    seen_tokens.add((name, token))
                    line = text.count("\n", 0, m.start()) + 1
                    self.add("SECRET_API_KEY", SEV_FAIL, rel, line,
                             f"疑似真实 API 密钥（{name}，已掩码）：{mask_secret(token)}")

            for m in LONG_B64_RE.finditer(text):
                token = m.group(1)
                if len(token) < 40:
                    continue
                if re.fullmatch(r"[0-9a-fA-F]+", token):
                    continue  # 十六进制哈希
                if not (any(c.isupper() for c in token)
                        and any(c.islower() for c in token)
                        and any(c.isdigit() for c in token)):
                    continue
                if is_placeholder(token):
                    continue
                if looks_like_code_identifier(token):
                    # ⚠️ 代码标识符（长驼峰函数名等）⇒ 假阳性，跳过。
                    #   实测 2026-10-25：Swift 测试函数名曾被报成「疑似密钥」。
                    continue
                if shannon_entropy(token) < 3.2:
                    continue
                if ("long", token) in seen_tokens:
                    continue
                seen_tokens.add(("long", token))
                line = text.count("\n", 0, m.start()) + 1
                self.add("SECRET_API_KEY", SEV_FAIL, rel, line,
                         f"疑似高熵长密钥（Base64 类，已掩码）：{mask_secret(token)}")

            for m in WIFI_RE.finditer(text):
                value = m.group(2)
                if len(value) < 8:
                    continue
                # 成员访问（`passwordInput.value`）⇒ 运行时取值，不是字面量口令
                quoted = text[m.start(2) - 1] in "\"'"
                if not quoted and MEMBER_ACCESS_RE.fullmatch(value):
                    continue
                if value.lower() in WIFI_STOPWORDS or is_placeholder(value):
                    continue
                if any(ch in value for ch in "[](){}<>=:;\"'"):
                    continue
                if not any(ch.isalpha() for ch in value):
                    continue
                if not (any(ch.isdigit() for ch in value)
                        or (any(ch.isupper() for ch in value)
                            and any(ch.islower() for ch in value))):
                    continue
                if len(set(value)) <= 2:
                    continue
                if ("wifi", value) in seen_tokens:
                    continue
                seen_tokens.add(("wifi", value))
                line = text.count("\n", 0, m.start()) + 1
                self.add("SECRET_WIFI_PASSWORD", SEV_FAIL, rel, line,
                         f"疑似真实 Wi-Fi 口令（已掩码）：{mask_secret(value)}")

        self._check_private()

    def _git(self, args: list[str]):
        try:
            return subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None

    def _check_private(self) -> None:
        private = self.root / "private"
        if not private.exists():
            self.add("SECRET_IN_PRIVATE", SEV_PASS, ".", None,
                     "private/ 不存在（无个人数据需要保护）")
            return
        hit = False
        for probe in ("private/", "private"):
            proc = self._git(["check-ignore", "-q", "--", probe])
            if proc is not None and proc.returncode == 0:
                hit = True
                break
        if hit:
            self.add("SECRET_IN_PRIVATE", SEV_PASS, "private", None,
                     "private/ 已被 .gitignore 覆盖（git check-ignore 命中）")
        else:
            self.add("SECRET_IN_PRIVATE", SEV_FAIL, "private", None,
                     "private/ 下有文件，但未被 .gitignore 覆盖（git check-ignore 未命中）")

    # -- 一致性 -----------------------------------------------------------

    def _research_counts(self) -> set[int]:
        """`docs/research/` 下的 md 份数（可接受的「声称值」集合）。

        ⚠️ **必须递归子目录**：`docs/research/apple-docs-evidence/` 下还放着
        2 份取证档案（89 KB + 82 KB）。只数顶层会低估 2 份 ⇒
        README 里写「68 份」就会被判「与实际不符」。

        返回值是一个**集合**（不同文档可能用不同口径：含/不含 README、
        含/不含子目录），只要声称值命中其中之一就不算 stale。
        """
        rd = self.root / "docs" / "research"
        if not rd.is_dir():
            return {0}
        top = [p for p in rd.glob("*.md") if p.is_file()]
        recursive = [p for p in rd.rglob("*.md") if p.is_file()]

        out: set[int] = set()
        for mds in (top, recursive):
            total = len(mds)
            archives = len([p for p in mds if p.name.lower() != "readme.md"])
            out.add(archives)
            out.add(total)
        return out

    def _check_counts(self) -> None:
        baselines = self._research_counts()
        for rel in COUNT_STALE_FILES:
            path = self.root / rel
            if not path.is_file():
                continue
            text = self._read_text(path) or ""
            lines = text.replace("\r\n", "\n").split("\n")
            for idx, line in enumerate(lines):
                if not COUNT_CLAIM_RE.search(line):
                    continue
                low = line.lower()
                if not any(kw.lower() in low for kw in COUNT_KEYWORDS):
                    continue
                for m in COUNT_CLAIM_RE.finditer(line):
                    n = int(m.group(1))
                    if n in baselines:
                        continue
                    self.add("DOC_COUNT_STALE", SEV_WARN, rel, idx + 1,
                             f"声称「{n} 份」与 docs/research/ 实际 "
                             f"{sorted(baselines)} 份不符")

    def _check_git(self) -> None:
        proc = self._git(["status", "--porcelain", "-z"])
        if proc is None or proc.returncode != 0:
            self.add("GIT_UNTRACKED", SEV_INFO, ".", None,
                     "根目录不是 git 仓库或 git 不可用，跳过 git 状态检查")
            return
        tokens = [t for t in proc.stdout.split("\0") if t]
        entries: list[str] = []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            i += 1
            if len(t) < 4:
                continue
            entries.append(t[3:])
            if t[0] in "RC":
                i += 1  # rename/copy 的旧路径字段
        dirty_private = [e for e in entries
                         if e == "private" or e.startswith("private/")]
        if dirty_private:
            self.add("GIT_DIRTY_PRIVATE", SEV_FAIL, ".", None,
                     "git status 里出现 private/ 路径（红线）："
                     + "、".join(sorted(dirty_private)[:5]))
        if entries:
            self.add("GIT_UNTRACKED", SEV_INFO, ".", None,
                     f"git status 有 {len(entries)} 条未跟踪/未提交条目"
                     "（发布前需 git add + commit；非门禁项）")

    # -- 主流程 -----------------------------------------------------------

    def run(self) -> list[Finding]:
        self._collect()
        for path in self.md_files:
            try:
                self._check_md_file(path)
            except Exception as exc:  # 单文件异常不得中断整体扫描
                self.add("DOC_UNREADABLE", SEV_WARN, self.rel(path), None,
                         f"解析异常：{type(exc).__name__}: {exc}")
        self._check_release()
        try:
            self._check_official_assets()
        except Exception as exc:
            self.add("OFFICIAL_ASSET_IN_REPO", SEV_WARN, ".", None,
                     f"官方资产扫描异常（已跳过）：{type(exc).__name__}: {exc}")
        try:
            self._check_secrets()
        except Exception as exc:
            self.add("SECRET_API_KEY", SEV_WARN, ".", None,
                     f"密钥扫描异常（已跳过）：{type(exc).__name__}: {exc}")
        self._check_counts()
        try:
            self._check_git()
        except Exception as exc:
            self.add("GIT_UNTRACKED", SEV_INFO, ".", None,
                     f"git 状态检查异常：{type(exc).__name__}: {exc}")
        return self.findings

    # -- 汇总 -------------------------------------------------------------

    def summary(self) -> dict:
        counts = {SEV_FAIL: 0, SEV_WARN: 0, SEV_INFO: 0, SEV_PASS: 0}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        counts["exit_code"] = 1 if counts[SEV_FAIL] else 0
        return counts

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings,
                       key=lambda f: (SEV_ORDER.get(f.severity, 9), f.code,
                                      f.file, f.line or 0))


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def format_location(f: Finding) -> str:
    if f.line:
        return f"{f.file}:{f.line}"
    return f.file


def render_report(checker: RepoChecker) -> str:
    findings = checker.sorted_findings()
    counts = checker.summary()
    elapsed = time.monotonic() - checker.started
    out: list[str] = []
    out.append("=" * 72)
    out.append("StackChan 发布前体检报告 (repo_release_check)")
    out.append(f"仓库根：{checker.root}")
    out.append(f"扫描：md {len(checker.md_files)} 份 / 文本 {len(checker.text_files)} 份 "
               f"/ {checker.bytes_scanned / 1024.0:.0f} KB / 用时 {elapsed:.2f}s")
    out.append("=" * 72)
    for sev in (SEV_FAIL, SEV_WARN, SEV_INFO, SEV_PASS):
        group = [f for f in findings if f.severity == sev]
        if not group:
            continue
        out.append(f"[{sev}] {len(group)} 项")
        for f in group:
            out.append(f"  [{f.code}] {format_location(f)} — {f.message}")
        out.append("")
    out.append("-" * 72)
    out.append(f"汇总：FAIL={counts[SEV_FAIL]}  WARN={counts[SEV_WARN]}  "
               f"INFO={counts[SEV_INFO]}  PASS={counts[SEV_PASS]}  "
               f"→ 退出码 {counts['exit_code']}")
    return "\n".join(out)


def build_json(checker: RepoChecker) -> dict:
    counts = checker.summary()
    return {
        "tool": "repo_release_check",
        "version": "1.0.0",
        "root": str(checker.root),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "duration_seconds": round(time.monotonic() - checker.started, 3),
        "scanned": {
            "markdown_files": len(checker.md_files),
            "text_files": len(checker.text_files),
            "bytes": checker.bytes_scanned,
        },
        "summary": {
            "FAIL": counts[SEV_FAIL],
            "WARN": counts[SEV_WARN],
            "INFO": counts[SEV_INFO],
            "PASS": counts[SEV_PASS],
            "exit_code": counts["exit_code"],
        },
        "findings": [f.to_dict() for f in checker.sorted_findings()],
    }


# ---------------------------------------------------------------------------
# 自检（--self-test）
# ---------------------------------------------------------------------------

def _write_bytes(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def _git_init(path: Path) -> None:
    try:
        subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q",
                        str(path)], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass


def _build_fixture_defects(base: Path) -> Path:
    """故意含各类缺陷的小假仓库。"""
    root = base / "fixture_defects"
    _write_bytes(root / "README.md",
                 "# Fixture（故意含缺陷）\n\n"
                 "[缺失文档](missing.md)\n"
                 "![缺失图片](../assets/nope.png)\n\n"
                 "研究档案共 3 份。\n")
    _write_bytes(root / "docs" / "broken.md",
                 "# broken\n\n"
                 "[缺失文档](./nope.md)\n"
                 "![缺失图片](../assets/nope.png)\n")
    _write_bytes(root / "docs" / "bad_cols.md",
                 "# bad cols\n\n"
                 "| a | b | c |\n"
                 "|---|---|---|\n"
                 "| 1 | 2 |\n")
    _write_bytes(root / "docs" / "bad_blank.md",
                 "# bad blank\n\n"
                 "| a | b |\n"
                 "|---|---|\n"
                 "| 1 | 2 |\n"
                 "\n"
                 "| 3 | 4 |\n"
                 "| 5 | 6 |\n")
    _write_bytes(root / "docs" / "bad_pipe.md",
                 "# bad pipe\n\n"
                 "| a|b | c | d |\n"
                 "|---|---|---|---|\n"
                 "| e | f | g | h |\n")
    _write_bytes(root / "docs" / "bom_crlf.md",
                 b"\xef\xbb\xbf# bom + crlf\r\n\r\nbody line\r\n")
    _write_bytes(root / "docs" / "secrets.md",
                 "# secrets\n\n"
                 "API key: sk-Zx91kQp7Lm3Nv8Rt2Wy6Hb\n"
                 'MINIMAX_API_KEY = "9fKq2LmZx71RpWv8Ty6Bd3"\n'
                 'wifi password = "SuperSecret123"\n')
    _write_bytes(root / "private" / "secret.txt",
                 "personal data\n")
    # ⚠️ 官方 `app/assets/` 下的 3D 模型（许可未取得 ⇒ 不得进仓）
    _write_bytes(root / "assets" / "stack_chan_model.glb", b"GLB-fixture")
    _write_bytes(root / ".gitignore", "*.log\n")
    _git_init(root)
    return root


def _build_fixture_private_ignored(base: Path) -> Path:
    root = base / "fixture_private_ignored"
    _write_bytes(root / "README.md", "# Fixture（private 已忽略）\n")
    _write_bytes(root / ".gitignore", "private/\n")
    _write_bytes(root / "private" / "secret.txt", "personal data\n")
    _git_init(root)
    return root


def _build_fixture_clean(base: Path) -> Path:
    root = base / "fixture_clean"
    _write_bytes(root / "README.md",
                 "# Clean fixture\n\n"
                 "本项目为**非官方第三方项目**，与 M5Stack Technology CO LTD 无隶属关系；\n"
                 '"StackChan" 是 M5Stack Technology CO LTD 的**商标**，本项目**未获其背书**。\n\n'
                 "许可见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。\n")
    _write_bytes(root / "LICENSE",
                 "MIT License\n\n"
                 "Copyright (c) 2026 StackChan Companion Contributors\n"
                 "Portions Copyright (c) 2026 M5Stack Technology CO LTD\n")
    _write_bytes(root / "NOTICE", "Third-party notices\n")
    _write_bytes(root / ".gitignore", "private/\n")
    # ⚠️ 成员访问**不得**被当成写死的 Wi-Fi 口令（2026-10-30 实测误报）。
    #    放在「干净夹具」里 ⇒ 扫描器一回归就变红。
    _write_bytes(root / "app.js",
                 "const password = passwordInput.value;\n"
                 "await api.post('/device/network/connect', { ssid: selectedNetwork.ssid });\n")
    _write_bytes(root / "private" / ".gitkeep", "")
    _git_init(root)
    return root


EXPECTED_DEFECT_CODES = {
    "DOC_TABLE_COLS": SEV_FAIL,
    "DOC_TABLE_BLANK": SEV_FAIL,
    "DOC_TABLE_PIPE": SEV_FAIL,
    "DOC_BOM": SEV_FAIL,
    "DOC_CRLF": SEV_WARN,
    "MD_LINK_BROKEN": SEV_FAIL,
    "MD_ASSET_MISSING": SEV_FAIL,
    "RELEASE_LICENSE_MISSING": SEV_FAIL,
    "RELEASE_NOTICE_MISSING": SEV_FAIL,
    "RELEASE_TRADEMARK_STMT": SEV_FAIL,
    "SECRET_API_KEY": SEV_FAIL,
    "SECRET_WIFI_PASSWORD": SEV_FAIL,
    "SECRET_IN_PRIVATE": SEV_FAIL,
    "DOC_COUNT_STALE": SEV_WARN,
    "GIT_UNTRACKED": SEV_INFO,
    "GIT_DIRTY_PRIVATE": SEV_FAIL,
    "OFFICIAL_ASSET_IN_REPO": SEV_FAIL,
}

EXPECTED_DEFECT_FILES = {
    "DOC_TABLE_COLS": "docs/bad_cols.md",
    "DOC_TABLE_BLANK": "docs/bad_blank.md",
    "DOC_TABLE_PIPE": "docs/bad_pipe.md",
    "DOC_BOM": "docs/bom_crlf.md",
    "DOC_CRLF": "docs/bom_crlf.md",
    "MD_ASSET_MISSING": "docs/broken.md",
    "SECRET_API_KEY": "docs/secrets.md",
    "SECRET_WIFI_PASSWORD": "docs/secrets.md",
    "OFFICIAL_ASSET_IN_REPO": "assets/stack_chan_model.glb",
    "DOC_COUNT_STALE": "README.md",
}


def _codes_by_severity(checker: RepoChecker) -> dict:
    out: dict[str, set[str]] = {}
    for f in checker.findings:
        out.setdefault(f.severity, set()).add(f.code)
    return out


def _run_self_test(real_root: Path | None) -> int:
    print("=" * 72)
    print("自检（--self-test）：故意含缺陷的夹具仓库 + 真实仓库根")
    print("=" * 72)

    # 夹具仓库默认放系统临时目录（自检结束即删，不污染仓库）。
    # 需要落到固定位置时用环境变量 STACKCHAN_CHECK_TMPDIR 指定（会自动清理）。
    tmp_base = os.environ.get("STACKCHAN_CHECK_TMPDIR") or None
    tmp_root = Path(tempfile.mkdtemp(prefix="stackchan_repo_release_check_",
                                      dir=tmp_base))
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name} — {detail}")

    try:
        # 1) 全缺陷夹具：期望每个检查码都命中，且严重级别一致
        fixture = _build_fixture_defects(tmp_root)
        checker = RepoChecker(fixture)
        checker.run()
        by_sev = _codes_by_severity(checker)
        fail_codes = by_sev.get(SEV_FAIL, set())
        warn_codes = by_sev.get(SEV_WARN, set())
        info_codes = by_sev.get(SEV_INFO, set())
        actual = {}
        for sev, codes in by_sev.items():
            for code in codes:
                actual[code] = sev
        missing = sorted(set(EXPECTED_DEFECT_CODES) - set(actual))
        extra = sorted(set(actual) - set(EXPECTED_DEFECT_CODES))
        sev_mismatch = sorted(
            f"{c}: 期望 {EXPECTED_DEFECT_CODES[c]} 实际 {actual[c]}"
            for c in set(EXPECTED_DEFECT_CODES) & set(actual)
            if EXPECTED_DEFECT_CODES[c] != actual[c])
        wrong_file = []
        for code, want_file in EXPECTED_DEFECT_FILES.items():
            hit = [f for f in checker.findings if f.code == code]
            if not hit or all(f.file != want_file for f in hit):
                wrong_file.append(f"{code} 未在 {want_file} 命中")
        ok = not missing and not extra and not sev_mismatch and not wrong_file
        detail = (f"命中 {len(actual)}/{len(EXPECTED_DEFECT_CODES)} 个检查码"
                  f"（FAIL {len(fail_codes)} / WARN {len(warn_codes)} / INFO {len(info_codes)}）")
        if missing:
            detail += f"；漏检={missing}"
        if extra:
            detail += f"；多报={extra}"
        if sev_mismatch:
            detail += f"；级别不符={sev_mismatch}"
        if wrong_file:
            detail += f"；定位不符={wrong_file}"
        record("fixture_all_defects", ok, detail)

        # 2) private/ 被 .gitignore 覆盖 ⇒ SECRET_IN_PRIVATE 为 PASS、无红线
        fx2 = _build_fixture_private_ignored(tmp_root)
        c2 = RepoChecker(fx2)
        c2.run()
        priv = [f for f in c2.findings if f.code == "SECRET_IN_PRIVATE"]
        dirty = [f for f in c2.findings if f.code == "GIT_DIRTY_PRIVATE"]
        ok2 = (len(priv) == 1 and priv[0].severity == SEV_PASS and not dirty)
        record("fixture_private_ignored", ok2,
               f"SECRET_IN_PRIVATE={priv[0].severity if priv else '缺失'}，"
               f"GIT_DIRTY_PRIVATE={'有' if dirty else '无'}")

        # 3) 干净夹具 ⇒ 0 FAIL
        fx3 = _build_fixture_clean(tmp_root)
        c3 = RepoChecker(fx3)
        c3.run()
        s3 = c3.summary()
        ok3 = s3[SEV_FAIL] == 0
        record("fixture_clean", ok3,
               f"FAIL={s3[SEV_FAIL]} WARN={s3[SEV_WARN]} "
               f"PASS={s3[SEV_PASS]}（干净夹具不应有 FAIL）")

        # 4) CLI 退出码语义
        script = Path(__file__).resolve()
        rc1 = subprocess.run([sys.executable, str(script), "--root", str(fixture)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").returncode
        rc0 = subprocess.run([sys.executable, str(script), "--root", str(fx3)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").returncode
        ok4 = rc1 == 1 and rc0 == 0
        record("exit_codes", ok4, f"有 FAIL 的夹具退出码={rc1}（应 1），"
                                  f"干净夹具退出码={rc0}（应 0）")

        # 5) 真实仓库根跑一遍，确认不崩
        if real_root is None or not Path(real_root).is_dir():
            record("real_repo_no_crash", True,
                   f"真实仓库根不存在（{real_root}），跳过")
        else:
            try:
                c5 = RepoChecker(Path(real_root))
                c5.run()
                s5 = c5.summary()
                record("real_repo_no_crash", True,
                       f"扫描未崩溃：FAIL={s5[SEV_FAIL]} WARN={s5[SEV_WARN]} "
                       f"INFO={s5[SEV_INFO]} PASS={s5[SEV_PASS]}")
            except Exception as exc:
                record("real_repo_no_crash", False,
                       f"扫描真实仓库时抛异常：{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    print("-" * 72)
    print(f"自检结果：{passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def default_root() -> Path:
    """默认仓库根 = 本脚本所在 tools/ 的上一级。"""
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo_release_check.py",
        description="StackChan 发布前体检器（纯标准库）")
    parser.add_argument("--root", default=None,
                        help="被检仓库根目录（默认：脚本所在仓库）")
    parser.add_argument("--json", dest="json_out", default=None,
                        help="额外输出 JSON 报告到该路径")
    parser.add_argument("--self-test", action="store_true",
                        help="运行自检（造缺陷夹具仓库并核对各检查码）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else default_root()

    if args.self_test:
        return _run_self_test(root)

    if not root.is_dir():
        print(f"用法/环境错误：仓库根不存在 —— {root}", file=sys.stderr)
        return 2

    checker = RepoChecker(root)
    try:
        checker.run()
    except Exception as exc:  # 顶层兜底：环境错误
        print(f"用法/环境错误：体检过程异常 —— {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2

    print(render_report(checker))

    if args.json_out:
        try:
            out_path = Path(args.json_out)
            if out_path.parent and str(out_path.parent) not in ("", "."):
                out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(build_json(checker), ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"JSON 报告已写入：{out_path}")
        except Exception as exc:
            print(f"用法/环境错误：JSON 写入失败 —— {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            return 2

    return checker.summary()["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
