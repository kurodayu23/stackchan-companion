#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""StackChan iOS 工程的**离线静态校验**（Windows / 无 Swift 编译器可跑）。

用法：
    py -3.12 ios/tools/validate_project.py
    py -3.12 ios/tools/validate_project.py --root D:\\path\\to\\repo

只依赖 Python 标准库。

检查项：
    1. Swift 静态检查：括号配对、声明块闭合、禁项、**视觉字面量清零**、占位标记齐全
    2. project.yml 里列的每个源文件路径都真实存在；每个 .swift 都归属某个 target 或被显式排除
    3. CoreProtocol 的消息类型数值与 docs/spec/03 §2.2 表一致
    4. 视觉 token 全部是占位（DesignSystem 里不得出现真实色值 / 字号 / 圆角 / 动效）
    5. Tests/ 里每个测试函数名唯一
    6. 手写 pbxproj 内部自洽（引用的 UUID 都有定义、括号配对）

退出码：0 = 全过；非 0 = 有不一致项（逐条打印）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

PLACEHOLDER = "TODO_PENDING_DESIGN_DECISION"
TODO_MARK = "TODO(pending design decision)"

# ---------------------------------------------------------------------------
# 视觉字面量禁项
#
# 视觉方向尚未拍板（docs/research/63 §3.4；DESIGN.md §14），
# 所以整个 Swift 树里不允许出现任何具体的视觉数值 —— 一旦出现就是一次
# 没被拍板的视觉决策，拍板时必须返工。
# ---------------------------------------------------------------------------
VISUAL_LITERAL_PATTERNS = [
    (r"(?<![\w.])Color\s*\(", "颜色字面量 Color(...)"),
    (r"\.system\(size\s*:", "手写字号 .system(size:)"),
    (r"cornerRadius\s*:\s*[0-9]", "圆角字面量 cornerRadius:<数字>"),
    (r"\.padding\(\s*[0-9]", "间距字面量 .padding(<数字>)"),
    (r"\.padding\(\s*\.[A-Za-z]+\s*,\s*[0-9]", "间距字面量 .padding(.edge, <数字>)"),
    (r"cubic-bezier", "自定义缓动曲线 cubic-bezier"),
    (r"Animation\.timingCurve", "自定义缓动 Animation.timingCurve"),
    (r"\.spring\(response\s*:", "手写 spring 参数"),
    (r"duration\s*:\s*[0-9]", "动效时长字面量 duration:<数字>"),
    (r"\.shadow\(radius\s*:\s*[0-9]", "阴影字面量 .shadow(radius:<数字>)"),
    (r"0x[0-9A-Fa-f]{6}\b", "6 位十六进制色值"),
    (r"\bspacing\s*:\s*[0-9]", "间距字面量 spacing:<数字>"),
    (r"\bcornerRadius\s*:\s*[0-9]", "圆角字面量"),
]

# 结构性禁项（与视觉无关）
BANNED_PATTERNS = [
    (r"\bfatalError\s*\(", "fatalError 占位"),
    (r"\bpreconditionFailure\s*\(", "preconditionFailure 占位"),
]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def fail(self, where: str, message: str) -> None:
        self.errors.append("%s: %s" % (where, message))

    def note(self, message: str) -> None:
        self.notes.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Swift 词法：剥掉注释与字符串后做括号配对
# ---------------------------------------------------------------------------
def strip_swift(source: str) -> str:
    """去掉注释与字符串字面量，只留结构性字符。"""
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            depth = 1
            i += 2
            while i < n and depth > 0:
                if source[i] == "/" and i + 1 < n and source[i + 1] == "*":
                    depth += 1
                    i += 2
                    continue
                if source[i] == "*" and i + 1 < n and source[i + 1] == "/":
                    depth -= 1
                    i += 2
                    continue
                i += 1
            out.append(" ")
            continue
        if source.startswith('"""', i):
            i += 3
            while i < n and not source.startswith('"""', i):
                i += 1
            i += 3
            out.append(' "" ')
            continue
        if ch == '"':
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == '"':
                    i += 1
                    break
                if source[i] == "\n":
                    break
                i += 1
            out.append(' "" ')
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def check_swift_file(path: Path, report: Report) -> None:
    rel = path.as_posix()
    raw = path.read_text(encoding="utf-8")

    # 换行符必须是 LF
    if "\r\n" in raw:
        report.fail(rel, "包含 CRLF 换行（约定：LF）")
    # UTF-8 无 BOM
    if raw.startswith("\ufeff"):
        report.fail(rel, "包含 UTF-8 BOM（约定：无 BOM）")

    stripped = strip_swift(raw)

    if stripped.count("{") != stripped.count("}"):
        report.fail(rel, "花括号不配对（{ = %d, } = %d）"
                    % (stripped.count("{"), stripped.count("}")))
    if stripped.count("(") != stripped.count(")"):
        report.fail(rel, "圆括号不配对（( = %d, ) = %d）"
                    % (stripped.count("("), stripped.count(")")))

    # 声明关键字后必须跟 {（粗粒度：每个声明行都要有开括号）
    decl_re = re.compile(r"^\s*(?:public\s+|internal\s+|private\s+|fileprivate\s+)?"
                          r"(?:final\s+)?(?:indirect\s+)?"
                          r"(?:struct|enum|protocol|extension|class|actor)\s+\w+")
    for line_no, line in enumerate(stripped.splitlines(), start=1):
        if decl_re.match(line) and "{" not in line and ":" not in line:
            report.fail(rel, "第 %d 行声明缺少代码块（可能漏了 `}`）" % line_no)

    # 视觉字面量禁项
    #
    # ⭐ 2026-10-25 用户已拍板「4 套方案全做」⇒ 真实色值**允许**出现在
    #    DesignSystem 里（那是 token 的**唯一**合法住所）。
    #    但 **DesignSystem 之外仍然一律禁止** —— 否则视觉会散落到各个 Feature，
    #    换方案时就得全仓改一遍（正是本门禁要防的返工）。
    #
    # ⚠️ 判定基于**剥离注释与字符串后的**代码文本（`stripped`）：
    #    否则「本文件不得出现 `.system(size:)`」这类**说明性注释**会被自己判 FAIL。
    in_design_system = "/DesignSystem/" in "/" + rel
    # ⭐ 固件**几何事实**的豁免目录。
    #    `CoreProtocol` 的 `FaceGeometry.swift` 里那些「数字」（眼径、位置偏移、嘴宽高）
    #    不是视觉决策，而是**固件行为的移植**（`docs/spec/06` §6.2 逐行带 file:line）。
    #    它们必须出现在那里，否则 App 就不再是设备的「镜子」。
    #    ⇒ 这里只豁免「几何量」，不豁免「颜色 / 字号 / 时长 / 阴影」。
    in_geometry_facts = ("/CoreProtocol/Sources/CoreProtocol/FaceGeometry.swift"
                         in "/" + rel.replace(os.sep, "/"))
    for pattern, label in VISUAL_LITERAL_PATTERNS:
        if in_design_system:
            # DesignSystem 内只禁「手写系统语义色」与「自定义缓动曲线」——
            # 这两类是「绕过 token 直接写死」的真隐患。
            # （时长 / 字号 / 圆角 / 间距在 DesignSystem 内**正是 token 的值**，必须允许：
            #   `duration:` 在 Motion.swift、`CGFloat = 16` 在 Shapes.swift、
            #   `Color(red:...)` 在 Tokens.swift —— 全都是 token 的合法取值。）
            if label in ("颜色字面量 Color(...)", "自定义缓动曲线 cubic-bezier",
                         "自定义缓动 Animation.timingCurve"):
                continue
            # `duration:` 字面量在 DesignSystem 内合法（Motion 的档位时长），
            # 但**手写 spring 参数**仍禁止（禁 bounce/elastic 回弹）。
            if label == "动效时长字面量 duration:<数字>" and in_design_system:
                continue
        if in_geometry_facts and label in ("圆角字面量 cornerRadius:<数字>", "圆角字面量"):
            # 固件嘴的圆角是**算出来的**（`mouth.cpp:54`：`map_range(weight,0,100,0,16)`），
            # 不是设计师选的圆角 token ⇒ 豁免。
            continue
        for match in re.finditer(pattern, stripped):
            line_no = stripped.count("\n", 0, match.start()) + 1
            where = "DesignSystem 内" if in_design_system else "视觉 token 必须集中在 DesignSystem"
            report.fail(rel, "第 %d 行出现%s —— %s（%s）"
                        % (line_no, label, where, match.group(0)[:40]))

    # 结构性禁项
    for pattern, label in BANNED_PATTERNS:
        for match in re.finditer(pattern, raw):
            line_no = raw.count("\n", 0, match.start()) + 1
            report.fail(rel, "第 %d 行出现%s（%s）" % (line_no, label, match.group(0)[:40]))

    # TODO 必须是显式的待拍板标记
    for match in re.finditer(r"\bTODO\b", raw):
        line_no = raw.count("\n", 0, match.start()) + 1
        line = raw.splitlines()[line_no - 1]
        if TODO_MARK not in line:
            report.fail(rel, "第 %d 行的 TODO 不是显式待拍板标记（应写成 `%s`）" % (line_no, TODO_MARK))


# ---------------------------------------------------------------------------
# project.yml 的最小解析（只取 sources / resources 的 path 与 excludes）
# ---------------------------------------------------------------------------
def parse_project_yaml(text: str) -> tuple[list[str], list[str], list[str]]:
    paths: list[str] = []
    excludes: list[str] = []
    package_paths: list[str] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if stripped == "packages:":
            i += 1
            while i < n:
                l2 = lines[i]
                s2 = l2.strip()
                if not s2 or s2.startswith("#"):
                    i += 1
                    continue
                ind2 = len(l2) - len(l2.lstrip())
                if ind2 <= indent:
                    break
                if s2.startswith("path:"):
                    package_paths.append(s2.split(":", 1)[1].strip().strip('"'))
                i += 1
            continue
        if stripped in ("sources:", "resources:"):
            block_indent = indent
            i += 1
            while i < n:
                l2 = lines[i]
                s2 = l2.strip()
                if not s2 or s2.startswith("#"):
                    i += 1
                    continue
                ind2 = len(l2) - len(l2.lstrip())
                if ind2 <= block_indent:
                    break
                if s2.startswith("- path:"):
                    paths.append(s2.split(":", 1)[1].strip().strip('"'))
                    i += 1
                    continue
                if s2 == "excludes:":
                    i += 1
                    while i < n:
                        l3 = lines[i]
                        s3 = l3.strip()
                        if not s3 or s3.startswith("#"):
                            i += 1
                            continue
                        ind3 = len(l3) - len(l3.lstrip())
                        if ind3 <= ind2:
                            break
                        if s3.startswith("- "):
                            excludes.append(s3[2:].strip().strip('"'))
                        i += 1
                    continue
                i += 1
            continue
        i += 1
    return paths, excludes, package_paths


def glob_match(rel: str, pattern: str) -> bool:
    """把 `a/**` / `a/*.swift` 这类模式转成前缀/后缀匹配。"""
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel == prefix or rel.startswith(prefix + "/")
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        return rel.startswith(prefix + "/") and "/" not in rel[len(prefix) + 1:]
    return rel == pattern


# ---------------------------------------------------------------------------
# docs/spec/03 §2.2 的消息类型表
# ---------------------------------------------------------------------------
def parse_doc_msg_types(doc_text: str) -> dict[str, int]:
    """解析 docs/spec/03 §2.2 的消息类型表。

    表里有一行写多个类型（`` `0x05` / `0x06` `` | `` `onCamera` / `offCamera` ``），
    所以两列都要按 "/" 拆开再配对。
    """
    table: dict[str, int] = {}
    section = doc_text.split("### 2.2")[-1].split("### 2.3")[0]
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        hexes = re.findall(r"0x[0-9A-Fa-f]{2}", cells[0])
        names = re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", cells[1])
        if not hexes or not names:
            continue
        for hex_value, name in zip(hexes, names):
            table[name] = int(hex_value, 16)
    return table


def parse_swift_msg_types(swift_text: str) -> dict[str, int]:
    table: dict[str, int] = {}
    for match in re.finditer(r"^\s*case\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]{2})\s*$",
                             swift_text, re.MULTILINE):
        table[match.group(1)] = int(match.group(2), 16)
    return table


# ---------------------------------------------------------------------------
# pbxproj 自洽检查
# ---------------------------------------------------------------------------
def check_pbxproj(path: Path, report: Report) -> None:
    if not path.exists():
        report.fail(path.as_posix(), "pbxproj 不存在")
        return
    text = path.read_text(encoding="utf-8")
    rel = path.as_posix()
    if text.count("{") != text.count("}"):
        report.fail(rel, "花括号不配对（{ = %d, } = %d）" % (text.count("{"), text.count("}")))
    defined = set(re.findall(r"^\t\t([0-9A-F]{24})\b", text, re.MULTILINE))
    referenced = set(re.findall(r"\b([0-9A-F]{24})\b", text))
    missing = sorted(referenced - defined)
    if missing:
        report.fail(rel, "引用了未定义的对象 UUID：%s" % ", ".join(missing[:8]))
    if len(defined) < 50:
        report.fail(rel, "定义的对象数量异常（%d）" % len(defined))


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="StackChan iOS 工程离线校验")
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--root", default=str(default_root), help="仓库根目录")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    ios = root / "ios"
    report = Report()

    # Windows 控制台默认不是 UTF-8，强制一下，避免中文报错信息变乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - 老 Python 没有 reconfigure
            pass

    if not ios.exists():
        print("[FAIL] 找不到 ios 目录：%s" % ios)
        return 1

    swift_files = sorted(ios.rglob("*.swift"))
    if not swift_files:
        print("[FAIL] 没有找到任何 .swift 文件")
        return 1
    for swift_file in swift_files:
        check_swift_file(swift_file, report)

    # -- 2. project.yml 的路径 -------------------------------------------------
    project_yml = ios / "project.yml"
    if not project_yml.exists():
        report.fail(project_yml.as_posix(), "project.yml 不存在")
    else:
        paths, excludes, package_paths = parse_project_yaml(project_yml.read_text(encoding="utf-8"))
        if not paths:
            report.fail(project_yml.as_posix(), "没有解析到任何 sources/resources 路径")
        for rel_path in paths:
            target = ios / rel_path
            if not target.exists():
                report.fail(project_yml.as_posix(), "列出的路径不存在：%s" % rel_path)
        for rel_path in package_paths:
            target = ios / rel_path
            if not target.exists():
                report.fail(project_yml.as_posix(), "本地 Package 路径不存在：%s" % rel_path)
            elif not (target / "Package.swift").exists():
                report.fail(project_yml.as_posix(), "本地 Package 缺少 Package.swift：%s" % rel_path)
        for pattern in excludes:
            # exclude 是相对所属 source path 的，要按那个 path 解析
            base = ios
            for candidate in paths:
                probe = ios / candidate / pattern
                if probe.exists() or any(glob_match(p.as_posix().replace("\\", "/"), probe.as_posix().replace("\\", "/"))
                                         for p in ios.rglob("*")):
                    base = ios / candidate
                    break
            probe = base / pattern[:-3] if pattern.endswith("/**") else base / pattern
            if not probe.exists():
                report.fail(project_yml.as_posix(), "exclude 指向的路径不存在：%s" % pattern)

        # 每个 .swift 都必须被某个 target 收录，或被显式排除且归属别的 target，或属于本地 Package
        package_roots = [(ios / p).as_posix().replace("\\", "/") for p in package_paths]
        # exclude 相对它所属的 source path
        excluded_rel = set()
        for source_path in paths:
            for pattern in excludes:
                excluded_rel.add((source_path.rstrip("/") + "/" + pattern).replace("\\", "/"))
        # 被显式列成单文件 source 的（归属某个 target）
        explicit_file_sources = {p.replace("\\", "/") for p in paths if p.endswith(".swift")}

        for swift_file in swift_files:
            rel_posix = swift_file.as_posix()
            rel_to_ios = swift_file.relative_to(ios).as_posix().replace("\\", "/")
            in_package = any(rel_posix.startswith(root_posix + "/") for root_posix in package_roots)
            excluded = any(glob_match(rel_to_ios, pattern) for pattern in excluded_rel)
            covered = any(rel_to_ios.startswith(p.replace("\\", "/") + "/") for p in paths) and not excluded
            if in_package:
                continue
            if excluded:
                # 被主 target 排除掉的文件，必须由别的 target 显式收录，否则就是孤儿文件
                if rel_to_ios not in explicit_file_sources:
                    report.fail(rel_posix,
                                "被 exclude 掉，又没有被任何 target 显式收录（孤儿文件）")
                continue
            if not covered:
                report.fail(rel_posix, "没有被任何 target 收录，也没有被显式排除（工程漏文件）")

    # -- 3. 消息类型表对照 -----------------------------------------------------
    doc_path = root / "docs" / "spec" / "03-通信链路预设与数据契约.md"
    msg_type_path = ios / "StackChanCompanion" / "CoreProtocol" / "Sources" / "CoreProtocol" / "MsgType.swift"
    if not doc_path.exists():
        report.fail(doc_path.as_posix(), "找不到 docs/spec/03")
    if not msg_type_path.exists():
        report.fail(msg_type_path.as_posix(), "找不到 MsgType.swift")
    else:
        doc_table = parse_doc_msg_types(doc_path.read_text(encoding="utf-8"))
        swift_table = parse_swift_msg_types(msg_type_path.read_text(encoding="utf-8"))
        if len(doc_table) != len(swift_table):
            report.fail(doc_path.as_posix(),
                        "文档表 %d 项 vs 代码 %d 项，数量不一致" % (len(doc_table), len(swift_table)))
        elif len(doc_table) == 25:
            # ⚠️ 文档小节标题写「24 个」，但表里实际列了 25 项（0x01–0x1B 去掉 0x08 / 0x0F）。
            #    这里以**表内容**为准，标题口径的差异记为 NOTE（属于 docs/ 的所有权范围，本仓库不改）。
            report.note("docs/spec/03 §2.2 小节标题写「24 个」，表里实际是 25 项 —— 以表内容为准")
        for name, value in sorted(doc_table.items()):
            if name not in swift_table:
                report.fail(msg_type_path.as_posix(), "缺少文档里的类型 %s (0x%02X)" % (name, value))
            elif swift_table[name] != value:
                report.fail(msg_type_path.as_posix(),
                            "类型 %s 的数值是 0x%02X，文档是 0x%02X" % (name, swift_table[name], value))
        for name in sorted(swift_table):
            if name not in doc_table:
                report.fail(msg_type_path.as_posix(), "代码里多出文档没有的类型 %s" % name)

    # -- 4. 视觉 token 检查 ---------------------------------------------------
    #
    # ⭐ 2026-10-25 用户拍板「4 套方案全做 + 强调色各方案自带」后，
    #    这里从「必须全是占位」改成「**4 套方案齐全 + 槽位无遗漏 + 色值合法**」。
    #    仍然要守的底线：**视觉 token 只允许出现在 DesignSystem**（上面第 3 项已强制）。
    design_dir = ios / "StackChanCompanion" / "DesignSystem"
    expected_files = ["Tokens.swift", "Theme.swift", "Typography.swift",
                      "Motion.swift", "Shapes.swift", "Glass.swift"]
    for name in expected_files:
        target = design_dir / name
        if not target.exists():
            report.fail(target.as_posix(), "DesignSystem 缺少 %s" % name)

    tokens_path = design_dir / "Tokens.swift"
    theme_path = design_dir / "Theme.swift"
    if tokens_path.exists():
        tokens_text = tokens_path.read_text(encoding="utf-8")
        # 4 套方案必须都在
        for palette in ("PaperTerracottaPalette", "PureWhiteBlankPalette",
                        "WarmPaperSerifPalette", "TuckDarkCalmPalette"):
            if "struct %s" % palette not in tokens_text:
                report.fail(tokens_path.as_posix(), "缺少视觉方案实现 %s" % palette)
        # 槽位必须全部有实现（每个 ThemeToken 都要在每个 palette 里被处理）
        theme_token_src = design_dir / "Tokens.swift"
        slot_names = re.findall(r"case\s+(\w+)\s*\n", theme_token_src.read_text(encoding="utf-8"))
        for slot in ("canvas", "surface", "surfaceElevated", "textPrimary",
                     "textSecondary", "textTertiary", "separator", "accent",
                     "onAccent", "success", "warning", "danger", "online"):
            hits = len(re.findall(r"case\s+\.%s\s*:" % slot, tokens_text))
            if hits < 4:
                report.fail(tokens_path.as_posix(),
                            "槽位 .%s 只在 %d 套方案里实现（应 ≥ 4）" % (slot, hits))
        if PLACEHOLDER in tokens_text:
            report.fail(tokens_path.as_posix(),
                        "仍有占位标记 %s —— 视觉已拍板，应填真值" % PLACEHOLDER)

    if theme_path.exists():
        theme_text = theme_path.read_text(encoding="utf-8")
        for choice in ("paperTerracotta", "pureWhiteBlank",
                       "warmPaperSerif", "tuckDarkCalm"):
            if "case %s" % choice not in theme_text:
                report.fail(theme_path.as_posix(), "缺少方案 case .%s" % choice)
        if PLACEHOLDER in theme_text:
            report.fail(theme_path.as_posix(),
                        "仍有占位标记 %s —— 视觉已拍板，应填真值" % PLACEHOLDER)

    # 排版必须是系统 text style（不许手写 .system(size:)）—— 由上面的禁项覆盖；
    # 这里额外确认 Typography 用了语义样式。
    typo_path = design_dir / "Typography.swift"
    if typo_path.exists():
        typo_text = typo_path.read_text(encoding="utf-8")
        for style in ("Font.body", "Font.largeTitle", "Font.headline",
                      "Font.caption", "Font.footnote", "Font.subheadline",
                      "Font.callout", "Font.title2", "Font.title3"):
            if style not in typo_text:
                report.fail(typo_path.as_posix(), "排版未使用系统样式 %s" % style)
        if PLACEHOLDER in typo_text:
            report.fail(typo_path.as_posix(),
                        "仍有占位标记 %s —— 排版已定，应填真值" % PLACEHOLDER)

    # 动效：必须 3 档，且不许 bounce/elastic（dampingFraction < 0.85 的 spring）
    motion_path = design_dir / "Motion.swift"
    if motion_path.exists():
        motion_text = motion_path.read_text(encoding="utf-8")
        for tier in ("instant", "standard", "narrative", "reduced"):
            if not re.search(r"\blet\s+%s\b" % tier, motion_text):
                report.fail(motion_path.as_posix(), "动效缺少档位 %s" % tier)
        if ".spring(" in motion_text:
            report.fail(motion_path.as_posix(),
                        "用了 .spring —— 禁 bounce/elastic 回弹（docs/spec/02 §3.2）")
        if PLACEHOLDER in motion_text:
            report.fail(motion_path.as_posix(),
                        "仍有占位标记 %s —— 动效已定，应填真值" % PLACEHOLDER)

    # 形状：触控目标下限必须是 44（HIG T1 数值）
    shapes_path = design_dir / "Shapes.swift"
    if shapes_path.exists():
        shapes_text = shapes_path.read_text(encoding="utf-8")
        if not re.search(r"minimumTouchTarget\s*:\s*CGFloat\s*=\s*44\b", shapes_text):
            report.fail(shapes_path.as_posix(),
                        "触控目标下限必须是 44pt（HIG accessibility.md:135，T1 官方数值）")
        if PLACEHOLDER in shapes_text:
            report.fail(shapes_path.as_posix(),
                        "仍有占位标记 %s —— 形状已定，应填真值" % PLACEHOLDER)

    features_dir = ios / "StackChanCompanion" / "Features"
    for swift_file in sorted(features_dir.rglob("*.swift")):
        text = swift_file.read_text(encoding="utf-8")
        if TODO_MARK not in text and PLACEHOLDER not in text:
            # 界面骨架要么还有待拍板标记，要么已经用上了 token（不再需要占位标记）
            # ⭐ 2026-10-25：脸渲染器落地后，DesignSystem 的引用面扩展到
            #    `FaceStyle`（脸画布尺寸 / 风格化圆角）与 `DeviceFaceColors`（设备原色）。
            if "ThemeToken" not in text and "ThemeChoice" not in text \
                    and "Typography." not in text and "Shapes." not in text \
                    and "Motion." not in text \
                    and "FaceStyle" not in text and "DeviceFaceColors" not in text:
                report.note("%s 既无待拍板标记也未引用 DesignSystem token"
                            % swift_file.as_posix())

    # -- 5. 测试函数名唯一 -----------------------------------------------------
    test_names: dict[str, str] = {}
    test_files = sorted(ios.rglob("*Tests.swift"))
    if not test_files:
        report.fail(ios.as_posix(), "没有找到任何测试文件")
    for test_file in test_files:
        text = test_file.read_text(encoding="utf-8")
        for match in re.finditer(r"^\s*func\s+(test[A-Za-z0-9_]*)\s*\(", text, re.MULTILINE):
            name = match.group(1)
            if name in test_names:
                report.fail(test_file.as_posix(),
                            "测试函数名 %s 与 %s 重复" % (name, test_names[name]))
            else:
                test_names[name] = test_file.as_posix()

    # -- 6. pbxproj 自洽 -------------------------------------------------------
    check_pbxproj(ios / "StackChanCompanion.xcodeproj" / "project.pbxproj", report)

    # ---------------------------------------------------------------- 输出
    print("=" * 72)
    print("StackChan iOS 工程离线校验")
    print("仓库根目录：%s" % root)
    print("Swift 文件：%d 个" % len(swift_files))
    print("测试文件：%d 个，测试函数：%d 个" % (len(test_files), len(test_names)))
    print("-" * 72)
    if report.errors:
        for error in report.errors:
            print("[FAIL] %s" % error)
        print("-" * 72)
        print("共 %d 项不一致" % len(report.errors))
        return 1
    for note in report.notes:
        print("[NOTE] %s" % note)
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
