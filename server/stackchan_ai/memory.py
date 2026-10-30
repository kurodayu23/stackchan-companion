# -*- coding: utf-8 -*-
"""memory —— 关系档案存储（本地 JSON）。

隐私边界（硬性）：
    - 档案**只**落在 ``private/`` 下；每次写盘前都校验路径确实在 private 里；
    - ``private/`` 已在仓库根 ``.gitignore``（第 11 行 ``private/``）⇒ **永不入库**；
    - 档案名只允许 ``[A-Za-z0-9_-]`` ⇒ 杜绝 ``../`` 穿越；
    - 写入前会扫描「疑似密钥」的键名（api_key / token / secret / password …），
      命中直接抛错 ⇒ **密钥不可能被写进档案**。

目录布局::

    private/
      profiles/<name>.json     关系档案（画像、偏好、里程碑）
      events/<name>.jsonl      事件流（一行一条 JSON）
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

#: 档案名允许的字符（杜绝路径穿越）
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

#: 疑似密钥的键名（写入前拦截）
SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|"
    r"secret|password|passwd|credential|authorization|bearer)",
    re.IGNORECASE,
)


class PrivacyError(RuntimeError):
    """违反隐私边界（路径不在 private 下 / 档案名非法 / 试图写入密钥）。"""


class ProfileStore:
    """关系档案存储。

    Args:
        private_dir: private/ 目录（默认仓库根下的 ``private/``）
    """

    def __init__(self, private_dir: Optional[Path] = None) -> None:
        if private_dir is None:
            from .config import repo_root
            private_dir = repo_root() / "private"
        self.private_dir = Path(private_dir).resolve()

    # ── 路径 ───────────────────────────────────────────────────────────────
    @property
    def profiles_dir(self) -> Path:
        return self.private_dir / "profiles"

    @property
    def events_dir(self) -> Path:
        return self.private_dir / "events"

    def _check_name(self, name: str) -> str:
        name = (name or "").strip()
        if not NAME_RE.match(name):
            raise PrivacyError(
                "invalid profile name %r (allowed: letters/digits/_/- , 1..64 chars)"
                % name)
        return name

    def _assert_private(self, path: Path) -> Path:
        """确认目标路径确实在 private/ 下，否则拒绝。"""
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.private_dir)
        except ValueError:
            raise PrivacyError(
                "refusing to touch %s: outside private dir %s"
                % (resolved, self.private_dir)) from None
        return resolved

    # ── 写前检查 ───────────────────────────────────────────────────────────
    @staticmethod
    def _assert_no_secrets(payload: Any, trail: str = "") -> None:
        """递归扫描 payload，发现疑似密钥的键名就抛错。"""
        if isinstance(payload, dict):
            for key, value in payload.items():
                here = "%s.%s" % (trail, key) if trail else str(key)
                if SECRET_KEY_RE.search(str(key)):
                    raise PrivacyError(
                        "refusing to store secret-looking field %r" % here)
                ProfileStore._assert_no_secrets(value, here)
        elif isinstance(payload, (list, tuple)):
            for index, item in enumerate(payload):
                ProfileStore._assert_no_secrets(item, "%s[%d]" % (trail, index))

    # ── 读写 ───────────────────────────────────────────────────────────────
    def profile_path(self, name: str) -> Path:
        return self.profiles_dir / ("%s.json" % self._check_name(name))

    def event_path(self, name: str) -> Path:
        return self.events_dir / ("%s.jsonl" % self._check_name(name))

    def exists(self, name: str) -> bool:
        return self.profile_path(name).exists()

    def load(self, name: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """读档案；不存在返回 ``default`` 的副本。"""
        path = self.profile_path(name)
        self._assert_private(path)
        if not path.exists():
            return dict(default or {})
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default or {})
        return data if isinstance(data, dict) else dict(default or {})

    def save(self, name: str, profile: Dict[str, Any]) -> Path:
        """写档案。

        Raises:
            PrivacyError: 路径不在 private 下 / 档案名非法 / 含疑似密钥字段
        """
        path = self.profile_path(name)
        self._assert_private(path)
        self._assert_no_secrets(profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(profile)
        payload.setdefault("updatedAt", time.time())
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(path)
        return path

    def update(self, name: str, **fields: Any) -> Dict[str, Any]:
        """读-改-写；返回合并后的档案。"""
        profile = self.load(name)
        profile.update(fields)
        self.save(name, profile)
        return profile

    def append_event(self, name: str, event: Dict[str, Any]) -> Path:
        """追加一条事件（JSONL）。"""
        path = self.event_path(name)
        self._assert_private(path)
        self._assert_no_secrets(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(event)
        record.setdefault("ts", time.time())
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    def read_events(self, name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """读最近若干条事件（按时间倒序取，再翻正）。"""
        path = self.event_path(name)
        self._assert_private(path)
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out[-limit:]

    def list_profiles(self) -> List[str]:
        """列出档案名（按名字排序）。"""
        directory = self.profiles_dir
        if not directory.exists():
            return []
        return sorted(p.stem for p in directory.glob("*.json"))

    def delete(self, name: str) -> bool:
        """删除档案（只允许删 private/ 下的）。"""
        path = self.profile_path(name)
        self._assert_private(path)
        if path.exists():
            path.unlink()
            return True
        return False

    def describe(self) -> Dict[str, Any]:
        """自述（**不含档案内容**，避免把个人数据打进日志）。"""
        return {
            "privateDir": str(self.private_dir),
            "profilesDir": str(self.profiles_dir),
            "eventsDir": str(self.events_dir),
            "profileCount": len(self.list_profiles()),
        }


__all__ = ["ProfileStore", "PrivacyError", "NAME_RE"]
