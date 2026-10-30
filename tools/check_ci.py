#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ci.py —— GitHub Actions workflow 静态体检器（不需要联网、不需要 runner）

为什么需要它
------------
本仓库的两个 workflow（``ci.yml`` / ``ios.yml``）**从未在真实 runner 上跑过** ——
本机是 Windows、没有 Swift、没有 macOS。于是"CI 能不能过"这件事没有任何本地证据。

这类风险有个典型形态：**workflow 里引用的脚本路径写错了 / 脚本被改名了 /
``--self-test`` 这个 flag 根本不存在**，但 YAML 依然合法 ⇒ 流水线在第一次真跑时
才会炸，而那时人已经推上去了。

本门禁把"workflow 声明的东西在仓库里真的存在且自洽"变成**可本地执行的**判定，
在推之前就能抓到。

检查项
------
CI-01  YAML 可解析（两个 workflow 都要）
CI-02  ``run:`` 里 ``python <path>`` 指向的脚本必须存在
CI-03  命令行若带 ``--self-test``，被调脚本源码必须真的支持这个 flag
CI-04  ``working-directory:`` 指向的目录必须存在
CI-05  ``run:`` 块里出现的仓库内路径字面量必须存在
CI-06  同一 job 内 ``name:`` 不得重复（重名会让日志定位失效）
CI-07  ``本地复现：`` 注释必须与紧邻的 ``run:`` 命令语义一致（防止注释过期）
CI-08  ``on.push.paths`` / ``on.pull_request.paths`` 里写的目录必须存在
CI-09  ``python-version`` 在同一 workflow 内必须唯一
CI-10  每个 job 必须声明 ``runs-on``
CI-11  ``tools/gates.txt``（门禁清单唯一真值）每行脚本必须存在；用 ``--self-test`` 的必须真支持
CI-12  ``gates.txt`` 里的自检门禁必须出现在某个 workflow 里
CI-13  门禁项数（``gates.txt`` 行数）必须与文档里写的数字一致

用法
----
    py -3.12 tools/check_ci.py                      # 体检当前仓库
    py -3.12 tools/check_ci.py --root <dir>         # 指定仓库根
    py -3.12 tools/check_ci.py --self-test          # 门禁自检（用故意做坏的夹具）

退出码：0 = 全过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 文档里「N 项门禁」的写法（09 号 / 72 号）
RE_GATE_COUNT_09 = re.compile(r"(\d+)\s*项门禁")
# ⚠️ 必须容许 markdown 粗体标记：72 号写的是「门禁 22 → **33** 项」
#    旧正则 `(\d+)\s*项` 匹配不到「**32** 项」⇒ **CI-13 对 72 号一直是静默失效的**
RE_GATE_COUNT_72 = re.compile(r"门禁[^。\n]{0,20}?(\d+)\s*\*{0,2}\s*项")

WORKFLOW_DIR = ".github/workflows"

# 仓库内路径字面量（出现在 run 块里、必须真实存在）
# 只匹配"看起来像路径"且带已知顶层目录前缀的，避免把 shell 变量误判成路径。
# 字符类用 `\w`（Python 3 默认 Unicode）⇒ 中文文件名也能被覆盖
# （本仓文档大量用中文名，例如 `docs/research/68-陪伴机器人文献综述.md`）。
REPO_PATH_LITERAL = re.compile(
    r"(?<![\w./-])((?:ios|tools|server|docs|prototype|assets|personas|\.github)/"
    r"[\w./-]+\.[A-Za-z0-9]{1,6})"
)

# ``python <path>`` / ``py -3.12 <path>``
PY_SCRIPT = re.compile(
    r"(?:^|[\s|;&(])(?:python3?|py\s+-3\.\d+)\s+([A-Za-z0-9_./-]+\.py)\b"
)

# 本地复现注释里形如 ``py -3.12 tools/foo.py --self-test``
# 路径字符集收窄到「字母数字 / _ . -」⇒ 遇到全角括号等自然截断，不会把中文吞进路径。
REPRO_CMD = re.compile(r"(?:py\s+-3\.\d+|python3?)\s+([A-Za-z0-9_./-]+\.py)")

SELF_TEST_FLAG = "--self-test"


class Finding:
    __slots__ = ("code", "severity", "where", "msg")

    def __init__(self, code: str, severity: str, where: str, msg: str) -> None:
        self.code = code
        self.severity = severity
        self.where = where
        self.msg = msg

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<{self.code} {self.severity} {self.where} {self.msg}>"


def load_yaml_text(path: Path):
    """返回 (data, error)。error 非 None 表示解析失败。"""
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, "PyYAML 未安装（py -3.12 -m pip install pyyaml）"
    try:
        with io.open(path, "r", encoding="utf-8", newline="") as fh:
            return yaml.safe_load(fh), None
    except Exception as exc:  # pragma: no cover - 解析失败路径
        return None, f"{type(exc).__name__}: {exc}"


def iter_steps(data):
    """产出 (job_name, step_index, step_dict)。"""
    jobs = (data or {}).get("jobs") or {}
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for idx, step in enumerate(job.get("steps") or []):
            if isinstance(step, dict):
                yield job_name, idx, step


def step_label(job_name: str, idx: int, step: dict) -> str:
    name = step.get("name")
    if not name:
        name = step.get("uses") or f"step#{idx}"
    return f"{job_name}/{name}"


def check_workflow(root: Path, wf_path: Path, findings: list) -> dict:
    """检查单个 workflow 文件。返回统计。"""
    stats = {"workflows": 0, "jobs": 0, "steps": 0, "py_calls": 0}
    rel = wf_path.relative_to(root).as_posix()

    data, err = load_yaml_text(wf_path)
    if err is not None:
        findings.append(Finding("CI-01", "FAIL", rel, f"YAML 解析失败：{err}"))
        return stats
    stats["workflows"] = 1

    jobs = (data or {}).get("jobs") or {}
    if not jobs:
        findings.append(Finding("CI-01", "FAIL", rel, "没有任何 jobs 定义"))
        return stats

    # ---- CI-09 python-version 唯一性 -------------------------------------
    versions = set()
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            with_ = step.get("with") or {}
            if isinstance(with_, dict) and "python-version" in with_:
                versions.add(str(with_["python-version"]))
    if len(versions) > 1:
        findings.append(
            Finding(
                "CI-09",
                "FAIL",
                rel,
                f"同一 workflow 内 python-version 不唯一：{sorted(versions)}",
            )
        )

    # ---- CI-08 paths 过滤器里的目录必须存在 ------------------------------
    on = (data or {}).get("on") or (data or {}).get(True) or {}
    if isinstance(on, dict):
        for trigger in ("push", "pull_request"):
            paths = (on.get(trigger) or {}).get("paths") or []
            for p in paths:
                # 通配路径取其**静态前缀目录**判定：
                #   "nosuchdir/**"  →  "nosuchdir" 必须存在
                #   "server/**"     →  "server" 必须存在
                #   "a/b/c.py"      →  "a/b/c.py" 必须存在（文件）
                base = p
                for marker in ("**", "*", "?"):
                    idx = base.find(marker)
                    if idx != -1:
                        base = base[:idx]
                        break
                base = base.rstrip("/")
                if not base:
                    continue
                cand = root / base
                if not cand.exists():
                    findings.append(
                        Finding(
                            "CI-08",
                            "FAIL",
                            rel,
                            f"on.{trigger}.paths 里的目录不存在：{p}（静态前缀 {base}）",
                        )
                    )

    # ---- 逐 step 检查 -----------------------------------------------------
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        stats["jobs"] += 1

        # ---- CI-10 runs-on -------------------------------------------------
        if not job.get("runs-on"):
            findings.append(
                Finding("CI-10", "FAIL", rel, f"job `{job_name}` 没有声明 runs-on")
            )

        seen_names: dict[str, int] = {}
        for idx, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            stats["steps"] += 1
            label = step_label(job_name, idx, step)

            # ---- CI-06 step name 唯一 ---------------------------------------
            nm = step.get("name")
            if nm:
                if nm in seen_names:
                    findings.append(
                        Finding(
                            "CI-06",
                            "FAIL",
                            label,
                            f"step name 重复（另一个在 #{seen_names[nm]}）：{nm}",
                        )
                    )
                else:
                    seen_names[nm] = idx

            # ---- CI-04 working-directory ------------------------------------
            wd = step.get("working-directory")
            if wd:
                d = root / wd
                if not d.is_dir():
                    findings.append(
                        Finding(
                            "CI-04",
                            "FAIL",
                            label,
                            f"working-directory 不存在：{wd}",
                        )
                    )

            run = step.get("run")
            if not isinstance(run, str):
                continue
            run_lines = run.splitlines()

            # ---- CI-02 / CI-03 python 脚本存在 & flag 支持 -----------------
            for m in PY_SCRIPT.finditer(run):
                script = m.group(1)
                stats["py_calls"] += 1
                sp = root / script
                if not sp.is_file():
                    findings.append(
                        Finding(
                            "CI-02",
                            "FAIL",
                            label,
                            f"run 里引用的脚本不存在：{script}",
                        )
                    )
                    continue
                if SELF_TEST_FLAG in m.group(0) or SELF_TEST_FLAG in run:
                    try:
                        with io.open(sp, "r", encoding="utf-8", errors="replace") as fh:
                            src = fh.read()
                    except Exception:  # pragma: no cover
                        src = ""
                    if SELF_TEST_FLAG not in src:
                        findings.append(
                            Finding(
                                "CI-03",
                                "FAIL",
                                label,
                                f"{script} 被以 --self-test 调用，但源码里没有这个 flag",
                            )
                        )

            # ---- CI-05 run 块里的仓库内路径字面量 --------------------------
            for line in run_lines:
                if line.strip().startswith("#"):
                    continue
                for m in REPO_PATH_LITERAL.finditer(line):
                    lit = m.group(1)
                    if not (root / lit).exists():
                        findings.append(
                            Finding(
                                "CI-05",
                                "FAIL",
                                label,
                                f"run 里引用的仓库路径不存在：{lit}",
                            )
                        )

    # ---- CI-07 「本地复现」注释 vs 实际 run 命令 --------------------------
    # 「本地复现：」是 YAML 注释（PyYAML 会丢弃），所以在**原始文本**上扫。
    # 判定：注释里点名的脚本，必须在同一 workflow 的某个 run 里真的被调用。
    raw_text = ""
    try:
        with io.open(wf_path, "r", encoding="utf-8", newline="") as fh:
            raw_text = fh.read()
    except Exception:  # pragma: no cover
        pass
    if raw_text:
        called = set()
        for _jn, _i, step in iter_steps(data):
            run = step.get("run")
            if isinstance(run, str):
                for m in PY_SCRIPT.finditer(run):
                    called.add(m.group(1))
        for lineno, line in enumerate(raw_text.splitlines(), start=1):
            if "本地复现" not in line:
                continue
            m = REPRO_CMD.search(line)
            if not m:
                continue
            script = m.group(1).split()[0]
            if script not in called:
                findings.append(
                    Finding(
                        "CI-07",
                        "FAIL",
                        f"{rel}:{lineno}",
                        f"「本地复现」注释点名 `{script}`，但 workflow 里没有任何 run 调用它"
                        f"（实际调用：{sorted(called) or '无'}）",
                    )
                )

    return stats


def check_gates_manifest(repo_root: Path, findings: list) -> dict:
    """检查 `tools/gates.txt`（门禁清单的唯一真值）。

    CI-11  每一行的脚本必须存在；用 `--self-test` 的行，脚本必须**真支持**该 flag
    CI-12  带 `--self-test` 的门禁必须出现在某个 workflow 里
    CI-13  门禁项数（gates.txt 的行数）必须与文档里写的数字一致
            —— 这一条是被一次**独立审计**逼出来的：同一时刻的「门禁项数」
               在不同文档里被写成 28 / 32 / 31 三个数，且没有任何一个可核对。
    """
    stats = {"gates": 0, "selftests": 0}
    manifest = repo_root / "tools" / "gates.txt"
    if not manifest.is_file():
        findings.append(Finding("CI-11", "FAIL", "tools/gates.txt", "门禁清单不存在"))
        return stats

    rows = []
    for lineno, raw in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            findings.append(
                Finding(
                    "CI-11",
                    "FAIL",
                    f"tools/gates.txt:{lineno}",
                    f"行格式不对（应为「名称<TAB>命令」）：{line}",
                )
            )
            continue
        name, cmd = parts[0].strip(), parts[1].strip()
        rows.append((name, cmd, lineno))

    stats["gates"] = len(rows)
    wf_text = ""
    wf_dir = repo_root / WORKFLOW_DIR
    if wf_dir.is_dir():
        for wf in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
            wf_text += wf.read_text(encoding="utf-8", errors="replace")

    for name, cmd, lineno in rows:
        toks = cmd.split()
        script = toks[1] if toks and toks[0] in ("python", "py") else toks[0]
        sp = repo_root / script
        if not sp.is_file():
            findings.append(
                Finding(
                    "CI-11",
                    "FAIL",
                    f"tools/gates.txt:{lineno}",
                    f"门禁 `{name}` 指向的脚本不存在：{script}",
                )
            )
            continue
        if "--self-test" in toks:
            stats["selftests"] += 1
            try:
                src = sp.read_text(encoding="utf-8", errors="replace")
            except Exception:  # pragma: no cover
                src = ""
            if SELF_TEST_FLAG not in src:
                findings.append(
                    Finding(
                        "CI-11",
                        "FAIL",
                        f"tools/gates.txt:{lineno}",
                        f"门禁 `{name}` 用了 --self-test，但 {script} 里没有 {SELF_TEST_FLAG}",
                    )
                )
            if sp.name not in wf_text:
                findings.append(
                    Finding(
                        "CI-12",
                        "FAIL",
                        f"tools/gates.txt:{lineno}",
                        f"门禁 `{name}` 是自检，但 {script} 没有出现在任何 workflow 里",
                    )
                )

    # ---- CI-13 文档里的门禁项数必须与清单行数一致 --------------------------
    n = len(rows)
    doc_checks = [
        ("docs/spec/09-施工顺序与决策依赖图.md", RE_GATE_COUNT_09),
        ("docs/research/72-晨会拍板速览-20261025.md", RE_GATE_COUNT_72),
    ]
    for rel, rx in doc_checks:
        p = repo_root / rel
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for m in rx.finditer(txt):
            claimed = int(m.group(1))
            if claimed != n:
                findings.append(
                    Finding(
                        "CI-13",
                        "FAIL",
                        rel,
                        f"文档写「{claimed} 项门禁」，但 tools/gates.txt 里有 {n} 项"
                        f"（{m.group(0)}）",
                    )
                )
    return stats


def collect(repo_root: Path) -> list:
    findings: list = []
    total = {"workflows": 0, "jobs": 0, "steps": 0, "py_calls": 0}
    wf_dir = repo_root / WORKFLOW_DIR
    if not wf_dir.is_dir():
        findings.append(
            Finding("CI-01", "FAIL", WORKFLOW_DIR, "找不到 .github/workflows 目录")
        )
        return findings, total
    for wf in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        st = check_workflow(repo_root, wf, findings)
        for k in total:
            total[k] += st.get(k, 0)
    if total["workflows"] == 0:
        findings.append(Finding("CI-01", "FAIL", WORKFLOW_DIR, "没有任何 workflow 文件"))
    gt = check_gates_manifest(repo_root, findings)
    total["gates"] = gt.get("gates", 0)
    return findings, total


# ---------------------------------------------------------------------------
# 自检：用故意做坏的夹具证明每一类都能抓到
# ---------------------------------------------------------------------------

FIXTURES = {
    "bad-yaml": "name: x\njobs:\n  a:\n    steps:\n     - name: 'unclosed\n",
    "missing-script": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: run\n        run: python tools/definitely_missing.py\n"
    ),
    "bad-selftest": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: run\n        run: python tools/check_ci.py --self-test\n"
    ),
    "missing-wd": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: run\n        working-directory: nope\n"
        "        run: echo hi\n"
    ),
    "missing-literal": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: run\n        run: cat ios/NoSuchFile.txt\n"
    ),
    "dup-name": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: same\n        run: echo 1\n"
        "      - name: same\n        run: echo 2\n"
    ),
    "repro-mismatch": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: run\n"
        "        run: |\n          # 本地复现：py -3.12 tools/other_thing.py\n"
        "          echo hi\n"
    ),
    "bad-paths": (
        "name: x\non:\n  push:\n    paths:\n      - \"nosuchdir/**\"\n"
        "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - name: run\n"
        "        run: echo hi\n"
    ),
    "no-runson": (
        "name: x\non: push\njobs:\n  a:\n    steps:\n      - name: run\n        run: echo hi\n"
    ),
    "multi-version": (
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/setup-python@v5\n"
        "        with:\n          python-version: \"3.12\"\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n          python-version: \"3.11\"\n"
    ),
}


def run_self_test(repo_root: Path) -> int:
    import tempfile

    print("[self-test] check_ci.py 门禁自检")
    print("=" * 64)
    passed = failed = 0
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        # 造一个"健康"的最小仓库，用来验证坏夹具**确实**会 FAIL
        good = tdir / "good"
        (good / "tools").mkdir(parents=True)
        (good / ".github" / "workflows").mkdir(parents=True)
        (good / "tools" / "ok.py").write_text(
            "import sys\nif '--self-test' in sys.argv:\n    print('ok')\n",
            encoding="utf-8",
        )
        # CI-11/12 要求「门禁清单存在且指向的脚本在 workflow 里出现」
        # ⚠️ 这条夹具之前漏了 gates.txt ⇒ 健康夹具自己就报 CI-11 FAIL
        #    ⇒ 自检 10/11 —— 也就是**门禁自己坏了却没人发现**（32 项那次全量回归漏跑）
        (good / "tools" / "gates.txt").write_text(
            "ok\ttools/ok.py --self-test\n", encoding="utf-8"
        )
        (good / ".github" / "workflows" / "ci.yml").write_text(
            "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - name: run\n        run: python tools/ok.py --self-test\n",
            encoding="utf-8",
        )
        fs, ts = collect(good)
        if any(f.severity == "FAIL" for f in fs):
            print(f"  FAIL  健康夹具竟然报错：{fs}")
            failed += 1
        else:
            print("  PASS  健康夹具零 FAIL")
            passed += 1

        for name, content in FIXTURES.items():
            bad = tdir / name
            (bad / ".github" / "workflows").mkdir(parents=True)
            (bad / ".github" / "workflows" / "ci.yml").write_text(content, encoding="utf-8")
            # bad-selftest 夹具需要 tools/check_ci.py 存在但不支持 --self-test
            if name == "bad-selftest":
                (bad / "tools").mkdir(parents=True, exist_ok=True)
                (bad / "tools" / "check_ci.py").write_text("print('no flag here')\n", encoding="utf-8")
            fs2, _ = collect(bad)
            if any(f.severity == "FAIL" for f in fs2):
                codes = sorted({f.code for f in fs2 if f.severity == "FAIL"})
                print(f"  PASS  {name:<16} 被抓到（{','.join(codes)}）")
                passed += 1
            else:
                print(f"  FAIL  {name:<16} **没被抓到** —— 门禁形同虚设")
                failed += 1

    print("=" * 64)
    print(f"[self-test] 通过 {passed} / {passed + failed}")
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GitHub Actions workflow 静态体检器")
    ap.add_argument("--root", default=None, help="仓库根目录（默认按本文件位置推断）")
    ap.add_argument("--self-test", action="store_true", help="门禁自检")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if args.self_test:
        repo_root = Path(__file__).resolve().parent.parent
        return run_self_test(repo_root)

    repo_root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    findings, total = collect(repo_root)

    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "root": str(repo_root),
                    "workflows": total["workflows"],
                    "jobs": total["jobs"],
                    "steps": total["steps"],
                    "py_calls": total["py_calls"],
                    "fail": len(fails),
                    "warn": len(warns),
                    "findings": [
                        {"code": f.code, "severity": f.severity, "where": f.where, "msg": f.msg}
                        for f in findings
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if fails else 0

    print("=" * 68)
    print("check_ci.py —— GitHub Actions workflow 静态体检")
    print("=" * 68)
    print(f"仓库根      : {repo_root}")
    print(
        f"workflow    : {total['workflows']} 个   job: {total['jobs']}   "
        f"step: {total['steps']}   python 调用: {total['py_calls']}"
    )
    print("-" * 68)
    if not findings:
        print("ALL PASS —— 两个 workflow 的声明在仓库里全部对得上。")
    for f in findings:
        print(f"[{f.severity}] {f.code}  {f.where}")
        print(f"        {f.msg}")
    print("-" * 68)
    print(f"FAIL={len(fails)}  WARN={len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
