#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_keyframes.py —— 把真实 0x14 关键帧抽 60 帧内联进渲染器 HTML。

数据来源
--------
`D:\\AP\\AP7000\\ai-workspace\\stackchan-research\\r59\\keyframes.json`
= MiniMax TTS（11.68 s）经韵律→关键帧编译器产出的 **292 帧真实 0x14 关键帧**
（`docs/research/59-韵律到身体可运行原型与关键帧编译器.md`）。

抽样规则
--------
在 0..N-1 上**等距取 60 个下标**（`round(i*(N-1)/59)`）⇒ 覆盖整条时间轴的头尾，
而不是只取前 60 帧。选中的帧**原样保留**（不裁字段、不改数值）。

写入位置
--------
`prototype/components/expression-renderer.html` 里
`<!-- KEYFRAMES:BEGIN -->` 与 `<!-- KEYFRAMES:END -->` 之间的整块。
**幂等**：重复跑结果一致。

用法：py -3.12 prototype/tools/extract_keyframes.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML_PATH = REPO / "prototype" / "components" / "expression-renderer.html"
SRC_DEFAULT = Path(r"D:\AP\AP7000\ai-workspace\stackchan-research\r59\keyframes.json")

FRAME_COUNT = 60
BEGIN_MARK = "<!-- KEYFRAMES:BEGIN -->"
END_MARK = "<!-- KEYFRAMES:END -->"


def pick_indices(total: int, want: int):
    if total <= want:
        return list(range(total))
    last = total - 1
    return [round(i * last / (want - 1)) for i in range(want)]


def build_block(frames, src_path: Path, total_frames: int, indices) -> str:
    payload = json.dumps(frames, ensure_ascii=False, indent=2)
    span_ms = sum(int(f.get("durationMs") or 40) for f in frames)
    full_ms = sum(int(f.get("durationMs") or 40) for f in frames)
    note = (
        '<p class="note" id="kfSource">时间轴数据：来源 '
        '<span class="mono">%s</span>，共 <b>%d</b> 帧真实 0x14 关键帧；'
        '本页等距抽取 <b>%d</b> 帧（下标 %d..%d，覆盖整条时间轴），'
        '这 %d 帧总时长 <b>%d ms</b>。设备端播放是<b>硬切</b>，帧间那段平滑是我们自己写的。'
        '</p>'
        % (
            src_path.as_posix(),
            total_frames,
            len(frames),
            indices[0],
            indices[-1],
            len(frames),
            span_ms,
        )
    )
    return (
        BEGIN_MARK
        + "\n"
        + note
        + "\n"
        + '<script id="timeline-data" type="application/json">\n'
        + payload
        + "\n</script>\n"
        + END_MARK
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass

    src = SRC_DEFAULT
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])

    if not src.exists():
        print("FAIL 找不到关键帧源文件: %s" % src)
        return 1
    if not HTML_PATH.exists():
        print("FAIL 找不到 HTML: %s" % HTML_PATH)
        return 1

    raw = src.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        print("FAIL 关键帧源文件不是非空数组: %s" % src)
        return 1

    total = len(data)
    indices = pick_indices(total, FRAME_COUNT)
    frames = [data[i] for i in indices]

    html = HTML_PATH.read_text(encoding="utf-8")
    if BEGIN_MARK not in html or END_MARK not in html:
        print("FAIL HTML 里找不到 KEYFRAMES:BEGIN / KEYFRAMES:END 标记")
        return 1

    block = build_block(frames, src, total, indices)
    new_html = re.sub(
        re.escape(BEGIN_MARK) + r".*?" + re.escape(END_MARK),
        lambda m: block,
        html,
        count=1,
        flags=re.S,
    )

    HTML_PATH.write_text(new_html, encoding="utf-8", newline="")

    span_ms = sum(int(f.get("durationMs") or 40) for f in frames)
    print("源文件      : %s" % src)
    print("总帧数      : %d" % total)
    print("抽取帧数    : %d（等距，下标 %d..%d）" % (len(frames), indices[0], indices[-1]))
    print("抽取总时长  : %d ms" % span_ms)
    print("注入字节    : %d" % len(block.encode("utf-8")))
    print("已写入      : %s" % HTML_PATH.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
