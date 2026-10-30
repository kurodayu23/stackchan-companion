# -*- coding: utf-8 -*-
"""run_tests —— 一条命令跑完全部测试（退出码 0 才算过）。

用法::

    py -3.12 server/run_tests.py             # 全部测试
    py -3.12 server/run_tests.py --self-test # 只跑离线自检（端到端，不联网）

输出：每个测试文件一行结果 + 总数；有失败时退出码 = 1。
"""

from __future__ import annotations

import argparse
import importlib
import sys
import unittest
from pathlib import Path
from typing import List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: 全部测试模块（按依赖顺序）
#:
#: ⚠️ **自动发现**：本清单历史上是硬编码的，结果新增的测试文件会被**静默跳过**
#: （2026-10-25 实测踩到：新增 ``test_persona.py`` 后 ``TOTAL`` 仍是 4 modules / 56 tests）。
#: 现在改为扫 ``server/tests/test_*.py`` 自动发现，下面的常量只用来**固定顺序**。
ALL_MODULES: Tuple[str, ...] = (
    "server.tests.test_protocol",
    "server.tests.test_providers",
    "server.tests.test_memory",
    "server.tests.test_persona",
    "server.tests.test_e2e_offline",
)

#: 「离线自检」= 端到端离线闭环（不联网、不需要 API Key）
SELF_TEST_MODULES: Tuple[str, ...] = ("server.tests.test_e2e_offline",)


def discover_modules() -> List[str]:
    """扫 ``server/tests/test_*.py`` 自动发现全部测试模块。

    已列在 ``ALL_MODULES`` 里的按该顺序排在前，其余按文件名排序追加。
    """
    tests_dir = REPO_ROOT / "server" / "tests"
    found = []
    if tests_dir.is_dir():
        for path in sorted(tests_dir.glob("test_*.py")):
            found.append("server.tests.%s" % path.stem)
    known = [m for m in ALL_MODULES if m in found]
    extra = [m for m in found if m not in known]
    return known + extra


class _Recorder(unittest.TextTestResult):
    """收集失败详情（比默认输出更整齐）。"""

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failures.append((test, self._exc_info_to_string(err, test)))

    def addError(self, test, err):
        super().addError(test, err)
        self.errors.append((test, self._exc_info_to_string(err, test)))


def run_module(name: str, verbosity: int = 2) -> Tuple[int, int, int, int, str]:
    """跑一个测试模块，返回 ``(tests, failures, errors, skipped, detail)``。"""
    module = importlib.import_module(name)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(module)
    stream = sys.stdout
    runner = unittest.TextTestRunner(stream=stream, verbosity=verbosity,
                                     resultclass=_Recorder)
    result = runner.run(suite)
    detail = ""
    for test, text in list(result.failures) + list(result.errors):
        detail += "\n--- %s ---\n%s" % (test.id(), text)
    return (result.testsRun, len(result.failures), len(result.errors),
            len(result.skipped), detail)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="server/run_tests.py",
                                     description="Run the StackChan backend test suite")
    parser.add_argument("--self-test", action="store_true",
                        help="only run the offline end-to-end self test")
    parser.add_argument("--quiet", action="store_true", help="less verbose output")
    args = parser.parse_args(argv)

    modules: List[str] = list(SELF_TEST_MODULES if args.self_test else discover_modules())
    verbosity = 1 if args.quiet else 2

    print("=" * 68)
    print("StackChan backend test suite (%s)"
          % ("offline self test" if args.self_test else "all modules"))
    print("=" * 68)

    total_tests = total_failures = total_errors = total_skipped = 0
    failed_modules = []
    for index, name in enumerate(modules, start=1):
        print("\n[%d/%d] %s" % (index, len(modules), name))
        print("-" * 68)
        tests, failures, errors, skipped, detail = run_module(name, verbosity)
        total_tests += tests
        total_failures += failures
        total_errors += errors
        total_skipped += skipped
        status = "PASS" if not (failures or errors) else "FAIL"
        if failures or errors:
            failed_modules.append(name)
        print(">>> %s: %s  tests=%d failures=%d errors=%d skipped=%d"
              % (name, status, tests, failures, errors, skipped))
        if detail:
            print(detail)

    print("\n" + "=" * 68)
    print("TOTAL: modules=%d tests=%d failures=%d errors=%d skipped=%d"
          % (len(modules), total_tests, total_failures, total_errors, total_skipped))
    if failed_modules:
        print("FAILED MODULES: %s" % ", ".join(failed_modules))
        print("RESULT: FAIL")
        print("=" * 68)
        return 1
    print("RESULT: PASS")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
