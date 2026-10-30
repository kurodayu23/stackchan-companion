#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_decisions.py —— 待拍板清单与「施工顺序/依赖图」的一致性体检

为什么需要它
------------
本仓库有两份文档各管一半，都靠人维护就会漂：

    docs/spec/07-待拍板清单与防返工机制.md   §3.5 —— **有哪些**待拍板项（Q 清单）
    docs/spec/09-施工顺序与决策依赖图.md     §四   —— 每个项**解锁什么 / 不拍板怎么办**

漂移的后果不是「文档不好看」，而是**真的漏工**：
新增一个决策项却没登记依赖 ⇒ 没人知道它卡住了哪条任务，
拍完板也不知道该从哪一步开始动手。

所以本门禁做五件事：

    DEC-01  07 §3.5 的每个 Q 在 09 的依赖表里都有对应行 → FAIL
    DEC-02  09 依赖表里出现的每个 Q 在 07 §3.5 存在 → FAIL（防凭空造决策）
    DEC-03  09 的 D 系列编号必须从 D1 连续到 Dn（无跳号）→ FAIL
    DEC-04  09 依赖表每行的「建议 / 阻塞 / 降级路径」三列不得为空 → FAIL
    DEC-05  09 必须有「未验证」小节且至少 3 条（防止边界声明被悄悄删掉）→ FAIL
    DEC-06  09 声称由本工具守门 ⇒ 文档里必须出现本工具名 → FAIL（防文档说谎）
    DEC-07  09 号写的「07 号 §3.5（N 项）」必须等于实际条目数 → FAIL
    DEC-08  72 号写的「N 个真缺陷」必须等于清单实际条目数 → FAIL
    DEC-09  00 号 §9 的每个开放项必须与 07 号 §3.5 跨表登记（O↔Q 互查）→ FAIL
    DEC-10  音频分片大小在 07 号与 72 号之间必须口径一致 → FAIL
    DEC-11  05 号 §八 的每个技术侧待拍板项（T-）必须与 07/00 跨表登记 → FAIL

用法
----
    py -3.12 tools/check_decisions.py --root .
    py -3.12 tools/check_decisions.py --self-test

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 07 号（待拍板清单）相对路径前缀
SPEC07_GLOB = os.path.join("docs", "spec", "07-*.md")
#: 09 号（施工顺序与决策依赖图）相对路径前缀
SPEC09_GLOB = os.path.join("docs", "spec", "09-*.md")

#: 07 §3.5 的小节标题
RE_H_35 = re.compile(r"^###\s+3\.5\b")
#: 表格行
RE_TABLE_ROW = re.compile(r"^\s*\|")
#: 09 §四 的小节标题
RE_H_4 = re.compile(r"^##\s+四")
#: 编号列里的 Q / D 编号
RE_QIDS = re.compile(r"^Q(\d+)$")
RE_DIDS = re.compile(r"^D(\d+)$")
#: 行内任意位置出现的 Q 编号（Q4/Q5/Q6 会拆成三个）
#: 用前后瞻防止匹配到标识符内部（例：MQ1 / Q10x）
RE_QTOKEN = re.compile(r"(?<![A-Za-z0-9_])Q\d+(?![A-Za-z0-9_])")


#: 09 号溯源表里「§3.5（N 项）」的计数
RE_07_COUNT = re.compile(r"§3\.5[（(]\**\s*(\d+)\s*项")
#: 72 号里「N 个真缺陷」的两种写法
RE_DEFECT = re.compile(r"(\d+)\s*个真缺陷")
RE_DEFECT_ITEM = re.compile(r"^\s*(\d+)\.\s+\S", re.M)
#: 晨会拍板速览（**两版都要锁**）
#:   ⚠️ 2026-10-25 夜新增 82 号 v2 后才发现：只锁 72 号 ⇒
#:      新版速览里的分片口径可以随便写而不被发现 ⇒ 同一个坑开两次。
SPEC72_GLOB = os.path.join("docs", "research", "72-*.md")
SPEC82_GLOB = os.path.join("docs", "research", "82-*.md")
#: 00 号（产品规格与技术规格）—— §9 开放项清单
SPEC00_GLOB = os.path.join("docs", "spec", "00-*.md")
#: 05 号（技术选型与功能实施方案）—— §八 技术侧待拍板
SPEC05_GLOB = os.path.join("docs", "spec", "05-*.md")
#: 05 号 §八 的小节标题
RE_H_8 = re.compile(r"^##\s+八")
#: 编号列里的 T 编号
RE_TIDS = re.compile(r"^T(\d+)$")
#: 行内任意位置出现的 O 编号
RE_OTOKEN = re.compile(r"(?<![A-Za-z0-9_])O-(\d+)(?![0-9])")
#: 00 号 §9 的小节标题
RE_H_9 = re.compile(r"^##\s+§9\b")
#: 编号列里的 O 编号
RE_OIDS = re.compile(r"^O-(\d+)$")
#: 正文里「O-1～O-N」的写法（含全角波浪号）
RE_ORANGE = re.compile(r"O-1\s*[～~\-—]\s*O-(\d+)")
#: 07 号 §3.6.1（方案 A 的具体规格）—— 分片大小的**权威来源**
RE_H_361 = re.compile(r"^####\s+3\.6\.1")
#: 含「二进制分片」字样的行 = 方案表里承载分片参数的那一行
RE_BINARY_CHUNK = re.compile(r"二进制分片")


def _defect_counts(md: str) -> list:
    """抽出 72 号里所有「N 个真缺陷」的表述。"""
    return [(m.start(), int(m.group(1))) for m in RE_DEFECT.finditer(md)]


def _defect_items(md: str) -> int:
    """数 72 号 §五 清单里的条目数（形如 "1. xxx" 的编号行）。"""
    sec = _section(md, re.compile(r"^##\s+五"))
    if not sec:
        return -1
    n = 0
    for line in sec.splitlines():
        if RE_DEFECT_ITEM.match(line):
            n += 1
    return n


class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg


def _read(path: str) -> str:
    return io.open(path, encoding="utf-8").read()


def _cells(line: str) -> list:
    """把一行 markdown 表格切成单元格（去掉首尾空 cell）。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _clean(cell: str) -> str:
    c = cell.strip()
    c = c.replace("**", "").replace("`", "").replace("*", "")
    return c.strip()


def _section(md: str, header_re) -> str:
    """取出某个标题到下一个同级/更高级标题之间的正文。"""
    lines = md.splitlines()
    out = []
    inside = False
    for line in lines:
        if not inside:
            if header_re.match(line):
                inside = True
            continue
        # 下一个标题（同为 # 或更深）=> 结束
        if re.match(r"^#{1,6}\s", line):
            break
        out.append(line)
    return "\n".join(out)


def parse_spec07_qids(md: str) -> list:
    """从 07 号 §3.5 表格里取出全部 Q 编号（按出现顺序，去重）。"""
    sec = _section(md, RE_H_35)
    ids = []
    for line in sec.splitlines():
        if not RE_TABLE_ROW.match(line):
            continue
        cells = _cells(line)
        if len(cells) < 2:
            continue
        first = _clean(cells[0])
        m = RE_QIDS.match(first)
        if m:
            ids.append(first)
    return ids


def parse_spec09_rows(md: str) -> list:
    """从 09 号 §四 表格里取出数据行（跳过表头与分隔行）。"""
    sec = _section(md, RE_H_4)
    rows = []
    for line in sec.splitlines():
        if not RE_TABLE_ROW.match(line):
            continue
        cells = _cells(line)
        if len(cells) < 5:
            continue
        first = _clean(cells[0])
        if first in ("编号", "---"):
            continue
        # 分隔行：|---|---|---|...
        if set(first) <= set("-: "):
            continue
        rows.append((first, cells))
    return rows


def parse_spec00_open_items(md: str) -> list:
    """从 00 号 §9 开放项表里取出全部 O 编号与整行单元格。"""
    sec = _section(md, RE_H_9)
    if not sec:
        return []
    items = []
    for line in sec.splitlines():
        if not RE_TABLE_ROW.match(line):
            continue
        cells = _cells(line)
        if len(cells) < 2:
            continue
        first = _clean(cells[0])
        if RE_OIDS.match(first):
            items.append((first, cells))
    return items


def parse_spec05_titems(md: str) -> list:
    """从 05 号 §八 表格里取出全部 T 编号与整行单元格。"""
    sec = _section(md, RE_H_8)
    if not sec:
        return []
    items = []
    for line in sec.splitlines():
        if not RE_TABLE_ROW.match(line):
            continue
        cells = _cells(line)
        if len(cells) < 2:
            continue
        first = _clean(cells[0])
        if RE_TIDS.match(first):
            items.append((first, cells))
    return items


def _chunk_spec_value(md: str):
    """从 07 号 §3.6.1 的「分片大小」行取**权威**毫秒数。"""
    sec = _section(md, RE_H_361)
    if not sec:
        return None
    m = re.search(r"分片大小\s*\|[^\n]{0,80}?(\d+)\s*ms", sec)
    return int(m.group(1)) if m else None


def _chunk_table_values(md: str) -> set:
    """从「方案表里那一行」抽毫秒值（含『二进制分片』字样的行）。

    ⚠️ 为什么只认这一行：文档里**引用历史矛盾**时也会写出旧的毫秒数
    （例如 72 号的审计对照表写着「分片『20~100 ms/片』」），
    那不是现行规格 ⇒ 扫全文会把**引用**误判成**口径不一致**。
    """
    vals = set()
    for line in md.splitlines():
        if not RE_BINARY_CHUNK.search(line):
            continue
        for m in re.finditer(r"(\d+)\s*ms", line):
            vals.add(int(m.group(1)))
    return vals


def _unverified_rows(md: str) -> int:
    """统计「未验证」小节里的表格数据行数。

    ⚠️ 这里**不能**复用 `_section`：它的终止条件是「下一个标题」，
    而我们要的正是**从那个含「未验证」的标题开始**到下一个标题之间的内容。
    """
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"^#{1,6}\s", line):
            continue
        if "未验证" not in line:
            continue
        n = 0
        for ln in lines[i + 1:]:
            if re.match(r"^#{1,6}\s", ln):
                break
            if not RE_TABLE_ROW.match(ln):
                continue
            cells = _cells(ln)
            if len(cells) < 2:
                continue
            first = _clean(cells[0])
            if first in ("项", "---"):
                continue
            if first and set(first) <= set("-: "):
                continue
            n += 1
        return n
    return -1


def scan(repo: str, findings: list) -> dict:
    """跑一遍体检，把 Finding 塞进 findings，返回统计信息。"""
    import glob

    p07 = sorted(glob.glob(os.path.join(repo, SPEC07_GLOB)))
    p09 = sorted(glob.glob(os.path.join(repo, SPEC09_GLOB)))

    stats = {"q_in_07": 0, "rows_in_09": 0, "o_in_00": 0, "t_in_05": 0}

    if not p07:
        findings.append(Finding("DEC-01", "FAIL", "docs/spec/07-*",
                                "找不到 07 号（待拍板清单）文件"))
        return stats
    if not p09:
        findings.append(Finding("DEC-01", "FAIL", "docs/spec/09-*",
                                "找不到 09 号（施工顺序与决策依赖图）文件"))
        return stats

    md07 = _read(p07[0])
    md09 = _read(p09[0])
    rel07 = os.path.relpath(p07[0], repo).replace(os.sep, "/")
    rel09 = os.path.relpath(p09[0], repo).replace(os.sep, "/")

    qids = parse_spec07_qids(md07)
    stats["q_in_07"] = len(qids)
    if not qids:
        findings.append(Finding("DEC-01", "FAIL", rel07,
                                "07 号 §3.5 没解析出任何 Q 编号（小节标题或表格结构变了？）"))
        return stats

    rows = parse_spec09_rows(md09)
    stats["rows_in_09"] = len(rows)
    if not rows:
        findings.append(Finding("DEC-01", "FAIL", rel09,
                                "09 号 §四 没解析出任何依赖表数据行"))

    # 09 里出现过的 Q / D 编号
    # ⚠️ Q 编号要扫**整行**（不只编号列）——
    #    09 号里 D2/D3/D4/D5/D6 这几行是「决策别名」，Q 号写在「事项」列里
    #    （例如「视觉终选（Q15）」「App↔云音频承载（Q10）」）。
    seen_q = []
    seen_d = []
    for first, cells in rows:
        for cell in cells:
            for q in RE_QTOKEN.findall(cell):
                if q not in seen_q:
                    seen_q.append(q)
        m = RE_DIDS.match(first)
        if m:
            d = "D%s" % m.group(1)
            if d not in seen_d:
                seen_d.append(d)

    # DEC-07：09 号正文里写的「07 号 §3.5（N 项）」必须等于实际条目数
    #   ⚠️ 这条是被一次**独立审计**逼出来的：Q15 补登进 §3.5 之后，
    #      09 号的溯源表还写着「（14 项）」⇒ 集合对了、**计数错了**。
    #      DEC-01/02 只管「集合对应」，管不了「正文里写的个数」。
    m = RE_07_COUNT.search(md09)
    if m:
        claimed = int(m.group(1))
        if claimed != len(qids):
            findings.append(Finding(
                "DEC-07", "FAIL", rel09,
                "09 号写「07 号 §3.5（%d 项）」，但实际是 %d 项（%s）"
                % (claimed, len(qids), "、".join(qids))))
    else:
        findings.append(Finding(
            "DEC-07", "WARN", rel09,
            "09 号里找不到「§3.5（N 项）」的计数表述（无法核对项数）"))

    # DEC-08：72 号的「N 个真缺陷」必须等于其清单条目数
    #   ⚠️ 同样是审计逼出来的：首段写 5、§五 标题写 4、正文列了 6 条。
    p72 = sorted(glob.glob(os.path.join(repo, SPEC72_GLOB)))
    if p72:
        md72 = _read(p72[0])
        rel72 = os.path.relpath(p72[0], repo).replace(os.sep, "/")
        claimed_list = _defect_counts(md72)
        actual = _defect_items(md72)
        for where, n in claimed_list:
            if actual is not None and n != actual:
                findings.append(Finding(
                    "DEC-08", "FAIL", rel72,
                    "%s 写「%d 个真缺陷」，但清单里实际列了 %d 条"
                    % (where, n, actual)))

    # DEC-09：00 号 §9 的开放项必须与 07 号 §3.5 跨表登记
    #   ⚠️ 这条是**第二次**独立审计逼出来的：三份规格各管一套编号
    #      （00 用 O-、07 用 Q-、05 用 T-、09 又用 D-），互不登记。
    #      后果很具体：被 09 号认定为「唯二关键路径」的 D2(=Q10) 在 00 号 §9 里
    #      **根本不是一条开放项** ⇒ 只看 00 号拍板会漏掉唯一阻塞项。
    p00 = sorted(glob.glob(os.path.join(repo, SPEC00_GLOB)))
    if p00:
        md00 = _read(p00[0])
        rel00 = os.path.relpath(p00[0], repo).replace(os.sep, "/")
        items = parse_spec00_open_items(md00)
        stats["o_in_00"] = len(items)
        if not items:
            findings.append(Finding(
                "DEC-09", "FAIL", rel00,
                "00 号 §9 没解析出任何开放项（O-1～O-N）—— 小节标题或表格结构变了？"))
        else:
            # (a) O 编号必须连续 O-1..O-N
            nums = sorted(int(o[1:].split("-")[1]) for o, _ in items)
            if nums != list(range(1, len(nums) + 1)):
                findings.append(Finding(
                    "DEC-09", "FAIL", rel00,
                    "00 号 §9 的 O 编号不连续：实际 %s，期望 1..%d"
                    % (nums, len(nums))))
            # (b) 每个 O 行必须有「跨表登记」列且非空
            blank = [o for o, cells in items if len(cells) < 5 or not _clean(cells[4])]
            if blank:
                findings.append(Finding(
                    "DEC-09", "FAIL", rel00,
                    "00 号 §9 有 %d 个开放项没填「对应 docs/spec/07 §3.5」列：%s"
                    % (len(blank), "、".join(blank))))
            # (c) 登记列里引用的 Q 必须真的存在于 07 号 §3.5
            bad_q = []
            for o, cells in items:
                if len(cells) < 5:
                    continue
                for q in RE_QTOKEN.findall(cells[4]):
                    if q not in qids:
                        bad_q.append("%s→%s" % (o, q))
            if bad_q:
                findings.append(Finding(
                    "DEC-09", "FAIL", rel00,
                    "00 号 §9 登记了 07 号 §3.5 里不存在的决策编号：%s"
                    % "、".join(bad_q)))
            # (d) 正文里写的「O-1～O-N」必须等于实际条目数
            for m in RE_ORANGE.finditer(md00):
                claimed = int(m.group(1))
                if claimed != len(items):
                    findings.append(Finding(
                        "DEC-09", "FAIL", rel00,
                        "00 号写「O-1～O-%d」，但 §9 实际有 %d 项开放项"
                        % (claimed, len(items))))
    else:
        findings.append(Finding("DEC-09", "FAIL", "docs/spec/00-*",
                                "找不到 00 号（产品规格与技术规格）文件"))

    # DEC-10：音频分片大小的口径必须一致
    #   ⚠️ 审计发现：07 号 §3.6 的方案表说「建议 20~100 ms/片」，
    #      同文件 §3.6.1 的具体规格却写死「160 ms」⇒ 用户按前者拍板、照后者实现。
    #   判据：**§3.6.1 的「分片大小」行是权威值**，
    #         07 号与 72 号的**方案表那一行**必须与它一致。
    spec = _chunk_spec_value(md07)
    if spec is not None:
        chunk_docs = []
        tvals = set()
        v = _chunk_table_values(md07)
        if v:
            tvals |= v
            chunk_docs.append((rel07, sorted(v)))
        for brief_glob in (SPEC72_GLOB, SPEC82_GLOB):
            for brief_path in sorted(glob.glob(os.path.join(repo, brief_glob))):
                mdb = _read(brief_path)
                relb = os.path.relpath(brief_path, repo).replace(os.sep, "/")
                v = _chunk_table_values(mdb)
                if v:
                    tvals |= v
                    chunk_docs.append((relb, sorted(v)))
        if tvals and tvals != {spec}:
            findings.append(Finding(
                "DEC-10", "FAIL", "docs/spec/07-* + docs/research/72-*/82-*",
                "音频分片大小口径不一致：权威值（07 号 §3.6.1「分片大小」）= %d ms，"
                "方案表里写的是 %s"
                % (spec, "；".join("%s=%s" % (d, vs) for d, vs in chunk_docs))))

    # DEC-11：05 号 §八 的技术侧待拍板项必须与 07/00 跨表登记
    #   ⚠️ 审计逼出来的：05 §八 自称「需要用户拍板」，但 T1（iOS 编译环境）
    #      与 T5（端侧检测路线）**不在 07 §3.5、也不在 00 §9** ⇒
    #      用户按 07/09 拍板会漏掉它们，而 CI 当时不会报警。
    p05 = sorted(glob.glob(os.path.join(repo, SPEC05_GLOB)))
    if p05:
        md05 = _read(p05[0])
        rel05 = os.path.relpath(p05[0], repo).replace(os.sep, "/")
        titems = parse_spec05_titems(md05)
        stats["t_in_05"] = len(titems)
        if not titems:
            findings.append(Finding(
                "DEC-11", "FAIL", rel05,
                "05 号 §八 没解析出任何技术侧待拍板项（T-）"))
        else:
            oids = set()
            if p00:
                oids = set(o for o, _ in parse_spec00_open_items(md00))
            blank = [tid for tid, cells in titems
                     if len(cells) < 4 or not _clean(cells[3])]
            if blank:
                findings.append(Finding(
                    "DEC-11", "FAIL", rel05,
                    "05 号 §八 有 %d 项没填「对应 docs/spec/07 §3.5 / docs/spec/00 §9」列：%s"
                    % (len(blank), "、".join(blank))))
            bad = []
            for tid, cells in titems:
                if len(cells) < 4:
                    continue
                col = cells[3]
                for q in RE_QTOKEN.findall(col):
                    if q not in qids:
                        bad.append("%s→%s" % (tid, q))
                for m in RE_OTOKEN.finditer(col):
                    o = "O-%s" % m.group(1)
                    if o not in oids:
                        bad.append("%s→%s" % (tid, o))
            if bad:
                findings.append(Finding(
                    "DEC-11", "FAIL", rel05,
                    "05 号 §八 登记了不存在的编号：%s" % "、".join(bad)))
    else:
        findings.append(Finding("DEC-11", "FAIL", "docs/spec/05-*",
                                "找不到 05 号（技术选型与功能实施方案）文件"))

    # DEC-01：07 的每个 Q 在 09 都有登记
    missing = [q for q in qids if q not in seen_q]
    if missing:
        findings.append(Finding(
            "DEC-01", "FAIL", rel09,
            "07 号 §3.5 的 %d 个决策项未登记到 09 号依赖表：%s"
            % (len(missing), "、".join(missing))))

    # DEC-02：09 里不能出现 07 没有的 Q
    ghost = [q for q in seen_q if q not in qids]
    if ghost:
        findings.append(Finding(
            "DEC-02", "FAIL", rel09,
            "09 号依赖表出现 07 号 §3.5 没有的决策编号（凭空造决策）：%s"
            % "、".join(ghost)))

    # DEC-03：D 编号连续
    if seen_d:
        nums = sorted(int(d[1:]) for d in seen_d)
        expect = list(range(1, len(nums) + 1))
        if nums != expect:
            findings.append(Finding(
                "DEC-03", "FAIL", rel09,
                "D 系列编号不连续：实际 %s，期望 %s"
                % (["D%d" % n for n in nums], ["D%d" % n for n in expect])))

    # DEC-04：依赖表三列不得为空
    empty_rows = []
    for first, cells in rows:
        for idx, label in ((2, "建议"), (3, "阻塞"), (4, "降级路径")):
            if idx < len(cells) and not _clean(cells[idx]):
                empty_rows.append("%s 的「%s」列空" % (first, label))
    if empty_rows:
        findings.append(Finding(
            "DEC-04", "FAIL", rel09,
            "依赖表有 %d 处必填列为空：%s"
            % (len(empty_rows), "；".join(empty_rows[:6]))))

    # DEC-05：未验证小节
    n = _unverified_rows(md09)
    if n < 0:
        findings.append(Finding("DEC-05", "FAIL", rel09,
                                "09 号缺少「未验证」小节（边界声明被删掉了？）"))
    elif n < 3:
        findings.append(Finding("DEC-05", "FAIL", rel09,
                                "09 号「未验证」小节只有 %d 条（至少 3 条）" % n))

    # DEC-06：文档不得声称一个不存在的门禁
    if "check_decisions.py" not in md09:
        findings.append(Finding("DEC-06", "FAIL", rel09,
                                "09 号声称由 check_decisions.py 守门，但正文里找不到该文件名"))

    return stats


def run_self_test() -> int:
    import tempfile

    print("[self-test] check_decisions.py 门禁自检")
    print("=" * 64)
    passed = failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS  %s" % name)
        else:
            failed += 1
            print("  FAIL  %s%s" % (name, ("  (%s)" % detail) if detail else ""))

    GOOD07 = """# 07 · 待拍板

### 3.5 其余待拍板

| 编号 | 事项 | 影响面 |
|---|---|---|
| Q1 | 固件基线 | 固件派生起点 |
| Q2 | 是否写 flash | 真机连通 |
| Q15 | 视觉终选 | 主题锁 |

### 3.6 音频承载方式

| 方案 | 做法 |
|---|---|
| **A. WS 二进制分片** | 分片大小取 160 ms |

#### 3.6.1 方案 A 的具体规格

| 项 | 规格 |
|---|---|
| 分片大小 | **160 ms = 4 帧 = 5120 B** |
"""

    GOOD09 = """# 09 · 施工顺序

## 四、决策依赖图

| 编号 | 事项 | 我的建议 | 阻塞的具体任务 | 不拍板的降级路径 |
|---|---|---|---|---|
| **D1** | 视觉终选（Q15） | 01 | Theme 锁 | 默认值 |
| **Q1** | 固件基线 | 1.6.0 | 刷机 | 已按 1.6.0 取证 |
| **Q2** | 写 flash | 接受 | 真机 | 走官方 App |

## 十、溯源

| 项 | 来源 |
|---|---|
| 待拍板原始清单 | `docs/spec/07` §3.5（3 项） |

## 九、未验证清单

| 项 | 状态 |
|---|---|
| Swift 编译 | 未验证 |
| 真机 BLE | 未验证 |
| workflow | 未验证 |

（本文由 check_decisions.py 守门）
"""

    GOOD00 = """# 00 · 规格

## §9 开放项清单（O-1～O-2，含已销账与跨表登记）

| # | 问题 | 影响 | 建议 | 对应 `docs/spec/07` §3.5 |
|---|---|---|---|---|
| **O-1** | 固件基线 | 固件 | 1.6.0 | **Q1** |
| **O-2** | 视觉终选 | 主题 | 纸感陶土 | **Q15** |

- O-1～O-2 两项开放问题已列出。
"""

    GOOD05 = """# 05 · 技术选型

## 八、需要用户拍板（技术侧）

| # | 事项 | 我的建议 | 对应 `docs/spec/07` §3.5 / `docs/spec/00` §9 |
|---|---|---|---|
| T1 | 固件基线 | 1.6.0 | **Q1** |
| T2 | 后端基座 | fork | **O-1** |
"""

    GOOD72 = """# 72 · 晨会拍板速览

> 一句话：昨夜抓到 **2 个真缺陷**。

## 五、昨夜抓到的 2 个真缺陷

1. 缺陷一
2. 缺陷二
"""

    def build(td, s07, s09, s72=None, s00=None, s05=None, s82=None):
        os.makedirs(os.path.join(td, "docs", "spec"), exist_ok=True)
        os.makedirs(os.path.join(td, "docs", "research"), exist_ok=True)
        with io.open(os.path.join(td, "docs", "spec", "07-x.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write(s07)
        with io.open(os.path.join(td, "docs", "spec", "09-x.md"), "w",
                     encoding="utf-8", newline="") as fh:
            fh.write(s09)
        if s00 is not None:
            with io.open(os.path.join(td, "docs", "spec", "00-x.md"), "w",
                         encoding="utf-8", newline="") as fh:
                fh.write(s00)
        if s05 is not None:
            with io.open(os.path.join(td, "docs", "spec", "05-x.md"), "w",
                         encoding="utf-8", newline="") as fh:
                fh.write(s05)
        if s72 is not None:
            with io.open(os.path.join(td, "docs", "research", "72-x.md"), "w",
                         encoding="utf-8", newline="") as fh:
                fh.write(s72)
        if s82 is not None:
            with io.open(os.path.join(td, "docs", "research", "82-x.md"), "w",
                         encoding="utf-8", newline="") as fh:
                fh.write(s82)
        return td

    with tempfile.TemporaryDirectory() as td:
        # 1) 健康夹具 → 零 FAIL
        build(td, GOOD07, GOOD09, s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("健康夹具零 FAIL", not any(x.severity == "FAIL" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1f) 05 §八 某项没填「对应」列 → DEC-11
        build(td, GOOD07, GOOD09, s00=GOOD00, s05=GOOD05.replace(
            "| T2 | 后端基座 | fork | **O-1** |",
            "| T2 | 后端基座 | fork |  |"))
        f = []
        scan(td, f)
        check("技术侧待拍板项没做跨表登记被 DEC-11 抓到",
              any(x.code == "DEC-11" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1g) 05 §八 登记了不存在的编号 → DEC-11
        build(td, GOOD07, GOOD09, s00=GOOD00, s05=GOOD05.replace(
            "| T2 | 后端基座 | fork | **O-1** |",
            "| T2 | 后端基座 | fork | **Q77** |"))
        f = []
        scan(td, f)
        check("技术侧登记了不存在的编号被 DEC-11 抓到",
              any(x.code == "DEC-11" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1b) 00 号 §9 开放项没填「跨表登记」列 → DEC-09
        build(td, GOOD07, GOOD09, s00=GOOD00.replace(
            "| **O-2** | 视觉终选 | 主题 | 纸感陶土 | **Q15** |",
            "| **O-2** | 视觉终选 | 主题 | 纸感陶土 |  |"))
        f = []
        scan(td, f)
        check("开放项没做跨表登记被 DEC-09 抓到",
              any(x.code == "DEC-09" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1c) 00 号登记了 07 里没有的 Q → DEC-09
        build(td, GOOD07, GOOD09, s00=GOOD00.replace(
            "| **O-2** | 视觉终选 | 主题 | 纸感陶土 | **Q15** |",
            "| **O-2** | 视觉终选 | 主题 | 纸感陶土 | **Q99** |"))
        f = []
        scan(td, f)
        check("登记了不存在的决策编号被 DEC-09 抓到",
              any(x.code == "DEC-09" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1d) 00 号文末写「O-1～O-3」但实际 2 项 → DEC-09
        build(td, GOOD07, GOOD09, s00=GOOD00.replace(
            "- O-1～O-2 两项开放问题已列出。", "- O-1～O-3 两项开放问题已列出。"))
        f = []
        scan(td, f)
        check("开放项个数写错被 DEC-09 抓到",
              any(x.code == "DEC-09" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1e) 方案表与 §3.6.1 权威规格不一致（表里写 100 ms）→ DEC-10
        s07x = GOOD07.replace("分片大小取 160 ms", "分片大小取 100 ms")
        build(td, s07x, GOOD09, s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("分片大小口径不一致被 DEC-10 抓到",
              any(x.code == "DEC-10" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1f2) 文档里**引用**旧的毫秒数不该被误判（72 号审计对照表就是这个情形）
        s72y = GOOD72 + "\n| 历史对照 | 分片「20~100 ms/片」 vs 「160 ms」 |\n"
        build(td, GOOD07, GOOD09, s72=s72y, s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("引用历史毫秒数不误报 DEC-10",
              not any(x.code == "DEC-10" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1f3) **新版速览**（82 号）里的分片口径写错 → DEC-10
        #   ⚠️ 2026-10-25 夜新增：只锁 72 号时，新版速览可以随便写而不被发现
        s82bad = ("| 编号 | 事项 | 选项 |\n|---|---|---|\n"
                  "| Q10 | 音频承载 | A. WS 二进制分片 `0x1C`（分片 **80 ms**） |\n")
        build(td, GOOD07, GOOD09, s82=s82bad, s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("新版速览分片口径写错被 DEC-10 抓到",
              any(x.code == "DEC-10" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 1f4) 新版速览里**引用**历史毫秒数不该被误判
        s82ok = ("| 编号 | 事项 | 选项 |\n|---|---|---|\n"
                 "| Q10 | 音频承载 | A. WS 二进制分片 `0x1C`（分片 **160 ms**） |\n"
                 "\n| 历史对照 | 分片「20~100 ms/片」 vs 「160 ms」 |\n")
        build(td, GOOD07, GOOD09, s82=s82ok, s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("新版速览引用历史毫秒数不误报 DEC-10",
              not any(x.code == "DEC-10" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 2) 09 漏登记 Q2 → DEC-01
        build(td, GOOD07, GOOD09.replace("| **Q2** | 写 flash | 接受 | 真机 | 走官方 App |\n", ""), s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("09 漏登记决策项被 DEC-01 抓到",
              any(x.code == "DEC-01" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 3) 09 凭空造 Q99 → DEC-02
        build(td, GOOD07, GOOD09.replace(
            "| **Q2** | 写 flash | 接受 | 真机 | 走官方 App |",
            "| **Q2** | 写 flash | 接受 | 真机 | 走官方 App |\n| **Q99** | 凭空造的 | 随便 | 随便 | 随便 |"),
            s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("凭空造决策被 DEC-02 抓到",
              any(x.code == "DEC-02" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 4) D 编号跳号 → DEC-03
        build(td, GOOD07, GOOD09.replace(
            "| **D1** | 视觉终选（Q15） | 01 | Theme 锁 | 默认值 |",
            "| **D2** | 视觉终选（Q15） | 01 | Theme 锁 | 默认值 |"),
            s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("D 编号跳号被 DEC-03 抓到",
              any(x.code == "DEC-03" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 5) 必填列为空 → DEC-04
        build(td, GOOD07, GOOD09.replace(
            "| **Q2** | 写 flash | 接受 | 真机 | 走官方 App |",
            "| **Q2** | 写 flash | 接受 |  | 走官方 App |"),
            s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("必填列为空被 DEC-04 抓到",
              any(x.code == "DEC-04" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 6) 未验证小节被删 → DEC-05
        build(td, GOOD07, GOOD09.split("## 九、未验证清单")[0], s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("未验证小节缺失被 DEC-05 抓到",
              any(x.code == "DEC-05" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 7) 文档声称了一个不存在的门禁 → DEC-06
        build(td, GOOD07, GOOD09.replace("check_decisions.py", "check_nothing.py"), s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("文档说谎（声称不存在的门禁）被 DEC-06 抓到",
              any(x.code == "DEC-06" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 8) 09 号溯源表里的「N 项」与实际条目数不符 → DEC-07
        build(td, GOOD07, GOOD09.replace("§3.5（3 项）", "§3.5（14 项）"), s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("项数写错被 DEC-07 抓到",
              any(x.code == "DEC-07" and x.severity == "FAIL" for x in f),
              str([(x.code, x.severity, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 9) 72 号「N 个真缺陷」与清单条目数不符 → DEC-08
        build(td, GOOD07, GOOD09, GOOD72.replace("**2 个真缺陷**", "**5 个真缺陷**")
              .replace("抓到的 2 个真缺陷", "抓到的 3 个真缺陷"), s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("缺陷个数写错被 DEC-08 抓到",
              any(x.code == "DEC-08" for x in f),
              str([(x.code, x.msg) for x in f]))

    with tempfile.TemporaryDirectory() as td:
        # 10) 72 号个数正确 ⇒ 不报 DEC-08
        build(td, GOOD07, GOOD09, GOOD72, s00=GOOD00, s05=GOOD05)
        f = []
        scan(td, f)
        check("72 号个数正确时不误报 DEC-08",
              not any(x.code == "DEC-08" for x in f),
              str([(x.code, x.msg) for x in f]))

    print("=" * 64)
    print("[self-test] 通过 %d / %d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="待拍板清单 ↔ 决策依赖图 一致性体检")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--self-test", action="store_true", help="门禁自检")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test()

    root = os.path.abspath(args.root)
    findings: list = []
    stats = scan(root, findings)

    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]

    print("=" * 68)
    print("check_decisions.py —— 待拍板清单 ↔ 决策依赖图 一致性体检")
    print("=" * 68)
    print("仓库根            : %s" % root)
    print("07 号 §3.5 决策项 : %d 个" % stats["q_in_07"])
    print("09 号 §四 依赖行  : %d 行" % stats["rows_in_09"])
    print("-" * 68)
    if not findings:
        print("ALL PASS —— 决策清单与依赖图一一对应，依赖表必填列齐全，"
              "未验证小节在位。")
    for f in findings:
        print("[%s] %s  %s" % (f.severity, f.code, f.where))
        print("        %s" % f.msg)
    print("-" * 68)
    print("FAIL=%d  WARN=%d" % (len(fails), len(warns)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
