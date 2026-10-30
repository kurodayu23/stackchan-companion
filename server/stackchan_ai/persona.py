# -*- coding: utf-8 -*-
"""persona —— 人格包加载。

人格包是**通用产品资产**（开源、可入库），个人定制档案是**私人数据**（永不入库），
两者边界如下：

    通用人格包   优先读仓库根 ``personas/``（只读）；找不到时用
                 ``server/stackchan_ai/personas/`` 里的内置通用包。
    个人定制档案 只在 ``private/``（见 memory.py），**永不写进人格包、绝不入库**。

人格包 JSON 字段::

    {
      "id": "enfp",
      "name": "小灯",
      "mbti": "ENFP",
      "summary": "一句话介绍",
      "emotion": "Happy",              # 韵律情绪基线（prosody.EMOTION_BASELINE 的键）
      "voice": "female-shaonv",        # TTS 音色 id（stub 会忽略）
      "system_prompt": "……",           # 交给 LLM 的人格提示词
      "speech_style": ["短句", "口语"],
      "personal": {                    # 个性化 7 参数（覆盖 prosody.PERSONAL_DEFAULTS）
        "expressiveness": 0.7, "blinkRate": 0.4, "gazeLead": 0.5
      }
    }

三层合并优先级（本模块实现）::

    private/persona.local.json   ← 最高（个人定制，永不入库，只读）
    personas/<id>.json           ← 通用人格包（开源，可社区 fork）
    server/stackchan_ai/personas/<id>.json  ← 内置兜底（保证永远有人格可用）

⚠️ **扩展名是 ``.json``**。`docs/research/18` §6.1 / `31` 号最初的设计稿用的是
YAML + ``index.yaml`` 清单，那套设计**没有实现**；实现走 JSON。详见 `personas/README.md`。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import repo_root

#: 内置通用人格包目录（随 server/ 一起部署）
BUNDLED_PERSONA_DIR = Path(__file__).resolve().parent / "personas"

#: 仓库根的通用人格包目录（**只读**；本仓另有同事在维护该目录）
REPO_PERSONA_DIR = repo_root() / "personas"

DEFAULT_PERSONA_ID = "enfp"

#: 私人层覆盖包文件名（**永不入库**；`private/` 已在 .gitignore）
PRIVATE_PERSONA_FILENAME = "persona.local.json"


@dataclass
class Persona:
    """一份人格包。"""

    id: str = DEFAULT_PERSONA_ID
    name: str = "小灯"
    mbti: str = "ENFP"
    summary: str = ""
    emotion: str = "Happy"
    voice: str = "female-shaonv"
    system_prompt: str = ""
    speech_style: List[str] = field(default_factory=list)
    personal: Dict[str, float] = field(default_factory=dict)
    source: str = "builtin"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "mbti": self.mbti,
            "summary": self.summary, "emotion": self.emotion,
            "voice": self.voice, "system_prompt": self.system_prompt,
            "speech_style": list(self.speech_style),
            "personal": dict(self.personal),
            "source": self.source,
        }


def _persona_from_dict(data: Dict[str, Any], source: str) -> Persona:
    personal_raw = data.get("personal") or {}
    personal: Dict[str, float] = {}
    if isinstance(personal_raw, dict):
        for key, value in personal_raw.items():
            try:
                personal[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
    return Persona(
        id=str(data.get("id") or DEFAULT_PERSONA_ID),
        name=str(data.get("name") or "小灯"),
        mbti=str(data.get("mbti") or "ENFP"),
        summary=str(data.get("summary") or ""),
        emotion=str(data.get("emotion") or "Happy"),
        voice=str(data.get("voice") or "female-shaonv"),
        system_prompt=str(data.get("system_prompt") or ""),
        speech_style=[str(s) for s in (data.get("speech_style") or [])],
        personal=personal,
        source=source,
    )


def _candidate_dirs(search_dirs: Optional[List[Path]] = None) -> List[Path]:
    if search_dirs is not None:
        return [Path(d) for d in search_dirs]
    return [REPO_PERSONA_DIR, BUNDLED_PERSONA_DIR]


def _private_dir() -> Path:
    """私人层目录（``private/``）—— 环境变量可覆盖，默认仓库根下。"""
    raw = (os.environ.get("STACKCHAN_PRIVATE_DIR") or "").strip()
    if raw:
        return Path(raw)
    return repo_root() / "private"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _merge_data(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """私人层覆盖通用层。

    - 标量 / 列表字段：上层有值即覆盖
    - ``personal``：**逐键合并**（上层只覆盖同名字键）
    - 其余未知字段：原样保留（向前兼容）
    """
    merged = dict(base)
    for key, value in overlay.items():
        if key == "personal" and isinstance(value, dict):
            personal = dict(merged.get("personal") or {})
            personal.update(value)
            merged["personal"] = personal
        elif value is not None:
            merged[key] = value
    return merged


def load_persona(persona_id: str = DEFAULT_PERSONA_ID,
                 search_dirs: Optional[List[Path]] = None,
                 apply_private: bool = True) -> Persona:
    """按 id 加载人格包。

    查找顺序：仓库根 ``personas/``（只读） → ``server/stackchan_ai/personas/``（内置）。
    找不到就退回内置的 ENFP 通用人格（保证服务端永远有人格可用）。

    ``apply_private=True`` 时再叠加私人层 ``private/persona.local.json``
    （个人定制，**永不入库**）；私人层只读，缺文件或语法错都**静默跳过**，
    绝不让一份坏掉的个人档案把整个机器人变哑巴。
    """
    persona_id = (persona_id or DEFAULT_PERSONA_ID).strip()
    data: Optional[Dict[str, Any]] = None
    source = ""
    for directory in _candidate_dirs(search_dirs):
        path = Path(directory) / ("%s.json" % persona_id)
        found = _read_json(path)
        if found is not None:
            data = found
            source = str(path)
            break
    if data is None:
        fallback = BUNDLED_PERSONA_DIR / ("%s.json" % DEFAULT_PERSONA_ID)
        found = _read_json(fallback)
        if found is not None:
            data = found
            source = str(fallback)
    if data is None:
        return Persona(source="builtin-fallback")

    if apply_private:
        private_path = _private_dir() / PRIVATE_PERSONA_FILENAME
        overlay = _read_json(private_path)
        if overlay is not None:
            data = _merge_data(data, overlay)
            source = "%s + %s" % (source, private_path)

    persona = _persona_from_dict(data, source=source)
    if persona.id == DEFAULT_PERSONA_ID and persona_id != DEFAULT_PERSONA_ID:
        persona.id = persona_id
    return persona


def list_personas(search_dirs: Optional[List[Path]] = None) -> List[str]:
    """列出可用的人格包 id（去重，按名字排序）。"""
    found = set()
    for directory in _candidate_dirs(search_dirs):
        directory = Path(directory)
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            found.add(path.stem)
    return sorted(found)


__all__ = ["Persona", "load_persona", "list_personas",
           "BUNDLED_PERSONA_DIR", "REPO_PERSONA_DIR", "DEFAULT_PERSONA_ID",
           "PRIVATE_PERSONA_FILENAME"]
