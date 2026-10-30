# -*- coding: utf-8 -*-
"""check_links —— 文档内部链接门禁（命名空间感知）。

为什么需要它
------------
本仓文档同时引用多种路径命名空间，人读文档时靠上下文分辨，**机器不能**。
GitHub 上读者点一个不存在的路径只会得到 404 —— 对一份求职作品是实打实的减分。

判定模型
--------
**第一步：判定路径归属。** 不靠前缀猜测，而是看**第二段目录是否真实存在于本仓**：

    docs/spec/07-xxx.md   docs/spec 是真目录  ⇒ REPO（我们的，必须存在）
    docs/api.md           docs/api.md 不是目录 ⇒ EXTERNAL（上游仓的）
    server/api/dance/v1   server/api 不是目录 ⇒ EXTERNAL（官方 Go server）
    firmware/main/hal/…   firmware/main 不是目录 ⇒ EXTERNAL（官方固件仓）

**第二步：REPO 路径必须存在**，否则 FAIL。
支持**编号前缀匹配**：``docs/spec/07`` ⇒ 命中 ``docs/spec/07-*.md``。

命名空间
--------
============  ==========================================  ====================
命名空间      含义                                          是否必须在本仓存在
============  ==========================================  ====================
REPO          本仓路径（``tools/xxx.py``）                   ✅ 必须存在
EXTERNAL      上游仓 / 官方 Go server / 第三方项目             ❌ 外部
LEGACY        旧 PWA 项目（``mobile_app/``）                    ❌ 外部（已存档）
LOCALCACHE    本机 Apple 官方文档缓存（``hig-md/`` 等）          ❌ 外部（不入库）
PRIVATE       私人层（``private/``）                            ❌ 永不入库
============  ==========================================  ====================

用法::

    py -3.12 tools/check_links.py --root .              # 全仓体检
    py -3.12 tools/check_links.py --root . --json       # 机读
    py -3.12 tools/check_links.py --root . --verbose    # 带 INFO 明细
    py -3.12 tools/check_links.py --self-test           # 离线自检

退出码：0 = 无 FAIL；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 本仓顶层目录
REPO_TOP_DIRS: Tuple[str, ...] = (
    "docs", "tools", "ios", "prototype", "assets", "personas",
    "server", ".github", "firmware",
)

#: 明确的外部命名空间前缀（不靠目录存在性判定，直接归类）
NAMED_EXTERNAL: Tuple[Tuple[str, str], ...] = (
    ("mobile_app/", "LEGACY"),
    ("hig-md/", "LOCALCACHE"),
    ("ios-docs/", "LOCALCACHE"),
    ("ios-fetch/", "LOCALCACHE"),
    ("private/", "PRIVATE"),
    # firmware/ 在本仓只是**占位目录**（只有 .gitkeep），真实内容在官方固件仓
    ("firmware/", "EXTERNAL"),
)

#: 各顶层目录下**属于本仓**的文件扩展名。
#: 用途：``<顶层目录>/<文件名>`` 这种两段路径，单看目录无法判断归属，
#: 用扩展名亲和度判定 —— 例如 ``tools/gone.py`` 是我们的，
#: 而 ``docs/api.md``（上游 Ollama）靠所在行的「上游」标记降级为 INFO。
REPO_EXT_BY_TOP: Dict[str, Tuple[str, ...]] = {
    "docs": (".md",),
    "tools": (".py", ".md", ".txt"),
    "ios": (".swift", ".md", ".json", ".yml", ".yaml", ".html", ".py", ".plist"),
    "prototype": (".html", ".js", ".css", ".py", ".md", ".json"),
    "assets": (".png", ".jpg", ".jpeg", ".gif", ".svg", ".mp3", ".wav", ".m4a", ".json"),
    "personas": (".json", ".yaml", ".yml", ".md"),
    "server": (".py", ".md", ".json", ".yaml", ".yml"),
    ".github": (".yml", ".yaml", ".md"),
}

#: **已知的设计-实现分歧**（不是坏链接，是有据可查的历史分歧）。
#: 命中即按 INFO 报告，理由写在这里，避免每次都当新问题翻出来。
KNOWN_DIVERGENCES: Dict[str, str] = {
    "personas/enfp.yaml":
        "YAML 设计稿（docs/research/18 §6.1），实现走 JSON —— 见 18 号「公开订正」",
    "personas/index.yaml":
        "YAML 清单设计稿（docs/research/18 §6.2），未实现",
    "personas/voice_profiles.yaml":
        "YAML 设计稿（docs/research/31），未实现",
    "private/persona.local.yaml":
        "YAML 设计稿（docs/research/18 §6.4），实现走 private/persona.local.json",
    "server/providers/local.py":
        "本地推理 provider（Q14 / D5）：尚未实现，排在 D1/D2 之后且在 12 周计划之外",
}

#: 所在行出现这些词 ⇒ 该行路径按外部引用处理
EXTERNAL_MARKERS: Tuple[str, ...] = (
    "上游", "旧项目", "本机缓存", "本地缓存", "官方仓",
    "不在本仓", "外部仓", "不随本仓", "已存档", "第三方",
    # 明确标注「还没做」的路径不是坏链接，是计划
    "计划新增", "尚未实现", "未实现", "建议新增",
)

#: 原始证据目录 —— 由 ``fetch_literature.py`` 生成的**抓取快照**。
#: 这类文件是文献原文记录，内容属于证据，**不可为了迎合门禁而人工编辑**
#: （往里塞「计划新增」这类本项目标记 = 篡改原始证据）。
#: 因此对这些目录只报 INFO，不报 FAIL；真要改就在**派生文件**里改。
SNAPSHOT_DIRS: Tuple[str, ...] = ("docs/research/runs",)

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_PATHY_RE = re.compile(r"^[\w~.][\w./\\+-]*$")
_HAS_SLASH_RE = re.compile(r"[/\\]")
_LINE_SUFFIX_RE = re.compile(r":\d+(-\d+)?$")

#: 引号跨度：落在引号内的路径视为「示例 / 引述外部原文」，不做仓库内存在性检查。
#: ⭐ 与 ``tools/repo_release_check.py`` 的 ``QUOTE_SPAN_RES`` **同一约定**。
QUOTE_SPAN_RES = (
    re.compile(r"「[^」\n]*」"),
    re.compile(r"『[^』\n]*』"),
    re.compile(r"\"[^\"\n]*\""),
)

_SKIP_PREFIXES = ("http://", "https://", "mailto:", "//", "$", "-", "--", "+", "<", ">")
_SKIP_SUBSTRINGS = ("*", "{", "}", "(", ")", "=", "<", ">", "$", "&", "|")


def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _has_external_marker(line: str) -> bool:
    return any(m in line for m in EXTERNAL_MARKERS)


def _in_snapshot(rel: str) -> bool:
    """该文件是否属于原始抓取快照目录（只报 INFO，不报 FAIL）。"""
    norm = rel.replace("\\", "/")
    return any(norm.startswith(d.rstrip("/") + "/") for d in SNAPSHOT_DIRS)


def _is_placeholder(token: str) -> bool:
    """省略号 / C++ 作用域等占位写法，不是真实路径。"""
    if "..." in token or "…" in token:
        return True
    if "::" in token:
        return True
    return False


def _named_namespace(token: str) -> Optional[str]:
    t = _norm(token)
    for prefix, ns in NAMED_EXTERNAL:
        if t == prefix.rstrip("/") or t.startswith(prefix):
            return ns
    return None


def _classify(repo: str, token: str) -> str:
    """判定 token 的命名空间：REPO / EXTERNAL / LEGACY / LOCALCACHE / PRIVATE / OTHER。

    判定顺序：
    1. 命中具名外部前缀 → 直接归类
    2. 首段不在本仓顶层目录 → OTHER（跳过）
    3. 第二段是**真实存在的目录** → REPO
    4. 第二段是**文件**且扩展名属于该顶层目录的亲和集 → REPO
    5. 其余 → EXTERNAL
    """
    t = _norm(token)
    named = _named_namespace(t)
    if named:
        return named
    parts = [p for p in t.split("/") if p]
    if not parts:
        return "OTHER"
    head = parts[0]
    if head not in REPO_TOP_DIRS:
        return "OTHER"
    if len(parts) == 1:
        return "REPO"          # 顶层目录本身
    second = parts[1]
    if os.path.isdir(os.path.join(repo, head, second)):
        return "REPO"
    ext = os.path.splitext(second)[1].lower()
    if ext and ext in REPO_EXT_BY_TOP.get(head, ()):
        return "REPO"
    return "EXTERNAL"


def _quote_spans(line: str):
    """行内被引号包住的跨度（示例 / 引述外部原文）。"""
    spans = []
    for rx in QUOTE_SPAN_RES:
        for m in rx.finditer(line):
            spans.append((m.start(), m.end()))
    return spans


def _is_pathy(token: str) -> bool:
    if not token or len(token) > 300:
        return False
    if token.startswith(_SKIP_PREFIXES):
        return False
    if any(s in token for s in _SKIP_SUBSTRINGS):
        return False
    if " " in token:
        return False
    if not _PATHY_RE.match(token):
        return False
    if not _HAS_SLASH_RE.search(token):
        return False          # 裸文件名噪声太大
    if token.startswith("~"):
        return False
    return True


def _strip_line_suffix(token: str) -> str:
    t = _norm(token)
    m = _LINE_SUFFIX_RE.search(t)
    if m and not t.endswith(":"):
        return t[: m.start()]
    return t


def _exists(base: str, candidate: str) -> bool:
    """在 ``base`` 下解析候选路径（大小写不敏感，Windows / GitHub 语义一致）。"""
    cand = _norm(candidate)
    if not cand:
        return False
    parts = [p for p in cand.split("/") if p and p != "."]
    cur = base
    for idx, part in enumerate(parts):
        cur = os.path.join(cur, part)
        if os.path.exists(cur):
            continue
        parent = os.path.dirname(cur) if idx < len(parts) - 1 else cur
        if not os.path.isdir(parent):
            return False
        try:
            names = os.listdir(parent)
        except OSError:
            return False
        if part not in names:
            lowered = part.lower()
            if not any(n.lower() == lowered for n in names):
                return False
    return True


def _resolve_repo_rel(repo: str, base: str, target: str) -> Optional[str]:
    """把链接目标解析成**仓库相对**路径。

    解析顺序与本仓文档惯例一致：先按所在 ``.md`` 的目录，再按仓库根。
    ⚠️ 必须先解析再判忽略规则 —— 否则 `docs/research/75.md` 里的
    ``runs/xxx.log`` 会被按仓库根解释成 ``<root>/runs/xxx.log``，
    从而误判成「被 `*.log` 排除」（它其实已被 `!docs/research/runs/*.log` 反选）。
    """
    cand = _norm(target)
    if not cand:
        return None
    for root in (base, repo):
        try:
            abs_p = os.path.normpath(os.path.join(root, cand))
            rel = os.path.relpath(abs_p, repo).replace("\\", "/")
        except ValueError:
            continue
        if rel.startswith(".."):
            continue
        if os.path.exists(os.path.join(repo, rel)):
            return rel
    return None


def _is_local_artifact(repo: str, candidate: str, base: Optional[str] = None) -> bool:
    """该路径是否是「本地生成物」（被 .gitignore 排除 ⇒ 克隆后不存在）。

    ⚠️ 这一类**本机测不出来**：路径在本机真实存在（是构建/截图产物），
    但克隆者拿到的是 404。
    2026-10-30 首次公开发布后，GitHub Actions 在 ubuntu 上真抓到一个：
    `STATUS.md` 指向 `prototype/mobile-v2/shots/`（本地生成物，被 .gitignore 排除）。

    处置口径（两种语义分开）：
      * **行内代码里的路径**：提到本地生成物是合法的说明 ⇒ 只记 INFO；
      * **markdown 链接**：指向不入库的路径 ⇒ 读者点开就是 404 ⇒ FAIL。
    """
    if _is_gitignored(repo, candidate):
        return True
    if base is not None and _is_gitignored(repo, candidate, base):
        return True
    return False


def _is_gitignored(repo: str, candidate: str, base: Optional[str] = None) -> bool:
    """该路径是否被 .gitignore 排除（⇒ **新克隆后不存在**）。

    ⚠️ 这一类坏链**本机测不出来**：路径在本机是真实存在的本地生成物，
    但克隆者拿到的是 404。
    2026-10-30 首次公开发布后，GitHub Actions 在 ubuntu 上真抓到一个：
    `STATUS.md` 指向 `prototype/mobile-v2/shots/`（本地生成物，被 .gitignore 排除）。
    ⇒ 本机门禁必须也能判它，否则只能靠 CI 兜底。

    ``base`` 给出时，``candidate`` 按「相对 base 目录」解析（markdown 链接用）。
    """
    cand = _norm(candidate)
    if not cand or cand.startswith("~"):
        return False
    if base is not None:
        try:
            abs_p = os.path.normpath(os.path.join(base, cand))
            rel = os.path.relpath(abs_p, repo).replace("\\", "/")
        except ValueError:
            return False
        if rel.startswith(".."):
            return False
        cand = rel
    try:
        proc = subprocess.run(["git", "-C", repo, "check-ignore", "-q", "--", cand],
                              capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _exists_with_prefix(base: str, candidate: str) -> bool:
    """存在性判定，并支持**编号前缀匹配**（``docs/spec/07`` ⇒ ``docs/spec/07-*.md``）。"""
    if _exists(base, candidate):
        return True
    cand = _norm(candidate)
    parent = os.path.dirname(cand)
    leaf = os.path.basename(cand)
    pdir = os.path.join(base, parent) if parent else base
    if not os.path.isdir(pdir):
        return False
    try:
        names = os.listdir(pdir)
    except OSError:
        return False
    lowered = leaf.lower()
    for n in names:
        if n.lower().startswith(lowered):
            return True
        if fnmatch.fnmatch(n.lower(), lowered + "*"):
            return True
    return False


class Finding(object):
    __slots__ = ("kind", "file", "line", "text", "namespace", "detail")

    def __init__(self, kind: str, file: str, line: int, text: str,
                 namespace: str, detail: str = "") -> None:
        self.kind = kind
        self.file = file
        self.line = line
        self.text = text
        self.namespace = namespace
        self.detail = detail

    def as_dict(self) -> Dict[str, object]:
        return {"kind": self.kind, "file": self.file, "line": self.line,
                "text": self.text, "namespace": self.namespace,
                "detail": self.detail}


def _md_files(repo: str) -> List[str]:
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", "__pycache__", ".pytest_cache")]
        for name in filenames:
            if name.lower().endswith(".md"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def _read_lines(path: str) -> List[str]:
    with io.open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", errors="replace").split("\n")


def check_markdown_links(repo: str, files: Sequence[str]) -> List[Finding]:
    """Check A：``[文字](相对路径)`` 必须能解析到真实文件。

    解析顺序：先按所在 ``.md`` 的目录解析，再按**仓库根**解析
    （本仓文档里两种写法都存在）。
    """
    findings: List[Finding] = []
    for path in files:
        rel = os.path.relpath(path, repo).replace("\\", "/")
        base = os.path.dirname(path)
        for idx, line in enumerate(_read_lines(path), start=1):
            spans = _quote_spans(line)
            for m in MD_LINK_RE.finditer(line):
                if any(st <= m.start() < en for st, en in spans):
                    continue  # 引号内的示例 / 外部引述
                target = m.group(1).strip()
                if not target or target.startswith("#"):
                    continue
                if "://" in target or target.startswith("mailto:"):
                    continue
                if target.startswith("/documentation/"):
                    continue
                if target.startswith("//"):
                    continue
                if _is_placeholder(target):
                    continue
                bare = target.split("#", 1)[0].split("?", 1)[0]
                if not bare:
                    continue
                if "/" not in bare:
                    findings.append(Finding(
                        "INFO", rel, idx, target, "EXTERNAL",
                        "裸文件名链接 —— 属上游仓，无法在本仓解析"))
                    continue
                if _exists_with_prefix(base, bare) or _exists_with_prefix(repo, bare):
                    resolved = _resolve_repo_rel(repo, base, bare)
                    if resolved and _is_gitignored(repo, resolved):
                        findings.append(Finding(
                            "FAIL", rel, idx, target, "REPO-LINK",
                            "链接目标存在但被 .gitignore 排除 ⇒ 新克隆后 404"))
                    continue
                # 明确以 ``./`` / ``../`` 开头 ⇒ 相对本文件目录，解析不到就是坏链
                if bare.startswith("./") or bare.startswith("../"):
                    findings.append(Finding(
                        "INFO" if _in_snapshot(rel) else "FAIL",
                        rel, idx, target, "REPO-LINK",
                        "markdown 链接指向不存在的文件"))
                    continue
                ns = _classify(repo, bare)
                if ns != "REPO":
                    findings.append(Finding(
                        "INFO", rel, idx, target, ns,
                        "外部命名空间（按约定不算失效）"))
                    continue
                findings.append(Finding(
                    "INFO" if _in_snapshot(rel) else "FAIL",
                    rel, idx, target, "REPO-LINK",
                    "markdown 链接指向不存在的文件"))
    return findings


def check_backtick_paths(repo: str, files: Sequence[str]) -> List[Finding]:
    """Check B：行内反引号路径 —— REPO 命名空间必须存在。"""
    findings: List[Finding] = []
    for path in files:
        rel = os.path.relpath(path, repo).replace("\\", "/")
        for idx, line in enumerate(_read_lines(path), start=1):
            marked = _has_external_marker(line)
            spans = _quote_spans(line)
            for m in BACKTICK_RE.finditer(line):
                if any(st <= m.start() < en for st, en in spans):
                    continue  # 引号内的示例 / 外部引述
                raw = m.group(1).strip()
                if not _is_pathy(raw) or _is_placeholder(raw):
                    continue
                token = _strip_line_suffix(raw)
                ns = _classify(repo, token)
                if ns == "OTHER":
                    continue
                if ns != "REPO":
                    findings.append(Finding(
                        "INFO", rel, idx, raw, ns, "外部命名空间（按约定不算失效）"))
                    continue
                if marked:
                    findings.append(Finding(
                        "INFO", rel, idx, raw, ns, "所在行标注为外部引用"))
                    continue
                divergence = KNOWN_DIVERGENCES.get(_norm(token))
                if divergence:
                    findings.append(Finding(
                        "INFO", rel, idx, raw, ns,
                        "已知设计-实现分歧：%s" % divergence))
                    continue
                if _exists_with_prefix(repo, token):
                    if _is_local_artifact(repo, token, os.path.dirname(path)):
                        findings.append(Finding(
                            "INFO", rel, idx, raw, ns,
                            "本地生成物（被 .gitignore 排除，不随仓分发）"))
                    continue
                if _is_local_artifact(repo, token, os.path.dirname(path)):
                    findings.append(Finding(
                        "INFO", rel, idx, raw, ns,
                        "本地生成物（被 .gitignore 排除，不随仓分发）"))
                    continue
                findings.append(Finding(
                    "INFO" if _in_snapshot(rel) else "FAIL",
                    rel, idx, raw, ns, "仓库内路径不存在"))
    return findings


def scan(repo: str) -> Dict[str, object]:
    files = _md_files(repo)
    findings: List[Finding] = []
    findings.extend(check_markdown_links(repo, files))
    findings.extend(check_backtick_paths(repo, files))
    fails = [f for f in findings if f.kind == "FAIL"]
    infos = [f for f in findings if f.kind == "INFO"]
    ns_counts: Dict[str, int] = {}
    for f in findings:
        ns_counts[f.namespace] = ns_counts.get(f.namespace, 0) + 1
    return {
        "root": repo,
        "mdFiles": len(files),
        "findings": [f.as_dict() for f in findings],
        "failCount": len(fails),
        "infoCount": len(infos),
        "namespaceCounts": ns_counts,
    }


def render(result: Dict[str, object], verbose: bool = False) -> str:
    lines: List[str] = []
    findings = result["findings"]  # type: ignore[index]
    fails = [f for f in findings if f["kind"] == "FAIL"]
    infos = [f for f in findings if f["kind"] == "INFO"]
    lines.append("链接体检 —— %s" % result["root"])
    lines.append("  md 文件: %d   FAIL: %d   INFO(外部命名空间): %d"
                 % (result["mdFiles"], result["failCount"], result["infoCount"]))
    if fails:
        lines.append("")
        lines.append("=== FAIL（仓库内路径不存在） ===")
        for f in fails:
            lines.append("  %s:%s  %s" % (f["file"], f["line"], f["text"]))
    if verbose and infos:
        lines.append("")
        lines.append("=== INFO（外部命名空间，按约定不算失效） ===")
        by_ns: Dict[str, int] = {}
        for f in infos:
            by_ns[str(f["namespace"])] = by_ns.get(str(f["namespace"]), 0) + 1
        for ns in sorted(by_ns):
            lines.append("  %-12s %d 处" % (ns, by_ns[ns]))
    return "\n".join(lines)


# ── 自检 ───────────────────────────────────────────────────────────────────

def _self_test() -> int:
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="check_links_selftest_")
    checks: List[Tuple[str, bool]] = []

    def ok(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    try:
        os.makedirs(os.path.join(tmp, "docs", "spec"))
        os.makedirs(os.path.join(tmp, "tools"))
        os.makedirs(os.path.join(tmp, "server", "providers"))
        os.makedirs(os.path.join(tmp, "mobile_app"))
        with io.open(os.path.join(tmp, "tools", "real.py"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("x = 1\n")
        with io.open(os.path.join(tmp, "server", "providers", "minimax.py"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("y = 2\n")
        with io.open(os.path.join(tmp, "docs", "spec", "07-待拍板.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# 07\n")
        with io.open(os.path.join(tmp, "docs", "spec", "a.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# A\n\n`tools/real.py` 与 `tools/gone.py` 与 `docs/spec/07`。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "b.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# B\n\n上游 `docs/api.md` 原文。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "c.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# C\n\n旧项目 `mobile_app/styles.css`。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "d.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# D\n\n`server/api/dance/v1` 与 `server/providers/minimax`。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "e.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# E\n\n省略 `ios/.../CoreProtocol` 与 `std::string_view`。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "f.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# F\n\n[好](../../tools/real.py) [坏](../../tools/nope.py) [裸](LICENSE)\n")
        # 原始抓取快照目录（豁免） vs 普通 spec 目录（不豁免）—— 同一路径对照
        # 用 `server/providers/ghost.py`：它**不在** KNOWN_DIVERGENCES 里，
        # 才能单独测出「快照目录豁免」这条规则本身是否生效。
        os.makedirs(os.path.join(tmp, "docs", "research", "runs"))
        with io.open(os.path.join(tmp, "docs", "research", "runs", "snap.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# 快照\n\n`server/providers/ghost.py` 尚未创建。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "g.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# G\n\n`server/providers/ghost.py` 尚未创建。\n")
        with io.open(os.path.join(tmp, "docs", "spec", "h.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# H\n\n`server/providers/local.py` 尚未实现。\n")

        # ⚠️ 「本机存在、但被 .gitignore 排除 ⇒ 新克隆后 404」的坏链。
        #    这类问题本机门禁原本看不见（路径真的在磁盘上），
        #    是 2026-10-30 由 GitHub Actions 在 ubuntu 上真抓出来的。
        #    ⚠️ 路径必须是**两段以上**（`_classify` 只把第二段存在的当仓库内命名空间）。
        os.makedirs(os.path.join(tmp, "docs", "shots"))
        with io.open(os.path.join(tmp, "docs", "shots", "a.png"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("x")
        with io.open(os.path.join(tmp, ".gitignore"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("docs/shots/\n")
        with io.open(os.path.join(tmp, "docs", "spec", "i.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write("# I\n\n见 `docs/shots/` 与 [图](../../docs/shots/a.png)。\n")
        try:
            subprocess.run(["git", "init", "-q", tmp], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            pass

        res = scan(tmp)
        findings = res["findings"]  # type: ignore[index]
        texts = [(f["text"], f["kind"]) for f in findings]

        ok("真实路径不报 FAIL",
           not any(t == "tools/real.py" and k == "FAIL" for t, k in texts))
        ok("失效路径报 FAIL",
           any(t == "tools/gone.py" and k == "FAIL" for t, k in texts))
        ok("被 .gitignore 排除的路径（行内）记 INFO 而非 FAIL",
           any(t == "docs/shots/" and k == "INFO" for t, k in texts)
           and not any(t == "docs/shots/" and k == "FAIL" for t, k in texts))
        ok("被 .gitignore 排除的路径（markdown 链接）报 FAIL",
           any("docs/shots/a.png" in str(t) and k == "FAIL" for t, k in texts))
        ok("编号前缀匹配不报 FAIL",
           not any(t == "docs/spec/07" and k == "FAIL" for t, k in texts))
        ok("上游标记行不报 FAIL",
           not any(t == "docs/api.md" and k == "FAIL" for t, k in texts))
        ok("旧项目不报 FAIL",
           not any(t == "mobile_app/styles.css" and k == "FAIL" for t, k in texts))
        ok("第二段不存在 ⇒ 外部（server/api）",
           not any(t == "server/api/dance/v1" and k == "FAIL" for t, k in texts))
        ok("第二段是目录 ⇒ 仓库内；带前缀可解析（server/providers/minimax）",
           _classify(tmp, "server/providers/minimax") == "REPO"
           and _exists_with_prefix(tmp, "server/providers/minimax")
           and not any(t == "server/providers/minimax" and k == "FAIL" for t, k in texts))
        ok("第二段是文件且扩展名亲和 ⇒ 仓库内（tools/gone.py）",
           _classify(tmp, "tools/gone.py") == "REPO")
        ok("扩展名不亲和 ⇒ 外部（ios/colors.h）",
           _classify(tmp, "ios/colors.h") == "EXTERNAL")
        ok("firmware/ 恒为外部（占位目录）",
           _classify(tmp, "firmware/repos.json") == "EXTERNAL")
        ok("省略号占位跳过", not any(t == "ios/.../CoreProtocol" for t, k in texts))
        ok("C++ 作用域跳过", not any(t == "std::string_view" for t, k in texts))
        ok("坏 markdown 链接报 FAIL",
           any(t == "../../tools/nope.py" and k == "FAIL" for t, k in texts))
        ok("好 markdown 链接不报 FAIL",
           not any(t == "../../tools/real.py" and k == "FAIL" for t, k in texts))
        ok("裸文件名链接按 INFO",
           any(t == "LICENSE" and k == "INFO" for t, k in texts))
        snap_rel = [f for f in findings if f["file"].startswith("docs/research/runs/")]
        spec_rel = [f for f in findings if f["file"].startswith("docs/spec/")]
        ok("原始快照目录内的失效路径不报 FAIL",
           not any(f["text"] == "server/providers/ghost.py" and f["kind"] == "FAIL" for f in snap_rel))
        ok("原始快照目录内的失效路径按 INFO",
           any(f["text"] == "server/providers/ghost.py" and f["kind"] == "INFO" for f in snap_rel))
        ok("快照目录豁免不外溢（普通目录仍报 FAIL）",
           any(f["text"] == "server/providers/ghost.py" and f["kind"] == "FAIL" for f in spec_rel))
        ok("已知设计-实现分歧不报 FAIL（server/providers/local.py）",
           not any(f["text"] == "server/providers/local.py" and f["kind"] == "FAIL" for f in spec_rel))
        ok("仓库根相对链接可解析",
           _exists_with_prefix(tmp, "docs/spec/07"))
        ok("大小写不敏感命中", _exists(tmp, "TOOLS/REAL.PY"))
        ok("不存在判定", not _exists(tmp, "tools/real.py.bak"))
        ok("分类：mobile_app ⇒ LEGACY",
           _classify(tmp, "mobile_app/styles.css") == "LEGACY")
        ok("分类：private ⇒ PRIVATE",
           _classify(tmp, "private/persona.local.json") == "PRIVATE")
        ok("分类：server/providers/… ⇒ REPO",
           _classify(tmp, "server/providers/minimax.py") == "REPO")
        ok("分类：server/api/… ⇒ EXTERNAL",
           _classify(tmp, "server/api/x") == "EXTERNAL")
        ok("行号后缀剥离", _strip_line_suffix("base.hpp:40-48") == "base.hpp")
        ok("行号后缀剥离单行", _strip_line_suffix("eyes.cpp:63") == "eyes.cpp")

        passed = sum(1 for _n, c in checks if c)
        for name, cond in checks:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        print("self-test: %d/%d" % (passed, len(checks)))
        return 0 if passed == len(checks) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="文档内部链接门禁")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), help="仓库根目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--verbose", action="store_true", help="打印 INFO 明细")
    ap.add_argument("--self-test", action="store_true", help="离线自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("root 不存在: %s" % root)
        return 2
    result = scan(root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result, verbose=args.verbose))
    return 1 if result["failCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
