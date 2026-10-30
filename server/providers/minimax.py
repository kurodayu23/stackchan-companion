# -*- coding: utf-8 -*-
"""providers.minimax —— MiniMax provider（chat + tts）。

🔒 key 纪律：key **只**从环境变量读，构造完 Authorization 头之后不再落盘、不回显；
任何异常信息在抛出前都会用 `config.mask_secret` 把 key 片段替换成 ``***``。

接口形状（**全部来自实测**，不是记忆）：

  chat —— OpenAI 兼容端点
      POST {base}/v1/chat/completions
      body  {"model": ..., "messages": [{"role","content"}], "max_tokens": N}
      200   choices[0].message.content（可能内联 <think>…</think>）
            可选字段 reasoning_content（实测存在，但**非必现**）
      失败  HTTP 404 + base_resp.status_code（如 2069）——**不能只看 HTTP 状态码**
      出处  docs/research/60 §1/§2/§3；探测脚本
            ai-workspace/stackchan-research/r60/probe_new_key.py:63-85

  tts —— /v1/t2a_v2
      POST {base}/v1/t2a_v2
      body  {"model": "speech-02-hd", "text": ..., "stream": false,
             "voice_setting": {"voice_id","speed","vol","pitch"},
             "audio_setting": {"sample_rate","bitrate","format","channel"}}
      200   base_resp.status_code == 0 → data.audio（十六进制串）
            ⚠ 音色无效时**也返回 HTTP 200**，成功判据必须读 base_resp.status_code
      出处  docs/research/60 §6；探测脚本
            ai-workspace/stackchan-research/r60/probe_tts.py:27-32

  base URL 必须是 https://api.minimaxi.com（60 号 §1/§2 实测；
  海外域 api.minimax.io 对大陆账号返回 2049）。

本机 HTTP 客户端用标准库 urllib —— 与探测脚本同款（stdlib，零额外依赖）。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base import (
    ChatReply,
    ErrorKind,
    Provider,
    ProviderError,
    ProviderKind,
    TtsAudio,
    classify_http_status,
    classify_status,
)

#: <think>…</think> 内联块（M3 / M2.7 会把推理直接塞进 content，60 号 §1）
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> Tuple[str, str]:
    """把 content 里内联的 ``<think>…</think>`` 拆出来。

    返回 ``(干净正文, 推理内容)``。TTS **绝不能**把推理念出来。
    """
    if not text:
        return "", ""
    match = _THINK_RE.search(text)
    if not match:
        return text.strip(), ""
    reasoning = match.group(0)
    body = _THINK_RE.sub("", text).strip()
    return body, reasoning.strip()


class MiniMaxProvider(Provider):
    """MiniMax provider。"""

    kind = ProviderKind.MINIMAX
    name = "minimax"

    def __init__(self, base_url: str, api_key: str,
                 chat_model: str = "MiniMax-M3.1-Flash",
                 tts_model: str = "speech-02-hd",
                 tts_voice: str = "female-shaonv",
                 chat_timeout: float = 60.0,
                 tts_timeout: float = 180.0) -> None:
        if not api_key:
            raise ValueError("MiniMaxProvider requires an API key")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.chat_model = chat_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.chat_timeout = chat_timeout
        self.tts_timeout = tts_timeout

    # ── HTTP ───────────────────────────────────────────────────────────────
    def _mask(self, text: str) -> str:
        """把 key 片段从文本里抹掉。"""
        if not text:
            return text
        if len(self._api_key) >= 8 and self._api_key in text:
            return text.replace(self._api_key, "***")
        return text

    def _post(self, path: str, payload: Dict[str, Any],
              timeout: float) -> Tuple[int, bytes]:
        """POST JSON，返回 ``(http_status, body_bytes)``；网络异常转成 ProviderError。"""
        url = self.base_url + path
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read()
            except Exception:
                return exc.code, b""
        except urllib.error.URLError as exc:
            raise ProviderError(
                ErrorKind.NETWORK,
                self._mask("cannot reach %s: %s" % (url, exc.reason)),
                provider=self.name) from exc
        except Exception as exc:  # pragma: no cover - 防御
            raise ProviderError(
                ErrorKind.NETWORK, self._mask(str(exc)), provider=self.name) from exc

    def _raise_for_payload(self, status: int, body: bytes) -> None:
        """按 base_resp / error 字段抛出分类后的异常。"""
        parsed: Any = None
        try:
            parsed = json.loads(body.decode("utf-8", "ignore"))
        except Exception:
            parsed = None

        code = 0
        message = ""
        if isinstance(parsed, dict):
            base_resp = parsed.get("base_resp")
            if isinstance(base_resp, dict):
                code = int(base_resp.get("status_code") or 0)
                message = str(base_resp.get("status_msg") or "")
            err = parsed.get("error")
            if not message and isinstance(err, dict):
                message = str(err.get("message") or err.get("msg") or "")
                if not code:
                    try:
                        code = int(err.get("code") or 0)
                    except (TypeError, ValueError):
                        code = 0
            if not message:
                message = str(parsed.get("message") or parsed.get("msg") or "")
        if not message:
            message = "HTTP %d %s" % (status, body[:200].decode("utf-8", "ignore"))

        kind = classify_status(code) if code else classify_http_status(status)
        if kind is ErrorKind.UNKNOWN and code:
            kind = ErrorKind.UNKNOWN
        raise ProviderError(kind, self._mask(message), code=code,
                            provider=self.name, http_status=status)

    # ── chat ───────────────────────────────────────────────────────────────
    def chat(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> ChatReply:
        """OpenAI 兼容对话补全。"""
        payload: Dict[str, Any] = {
            "model": str(kwargs.get("model") or self.chat_model),
            "messages": [{"role": str(m.get("role", "user")),
                          "content": str(m.get("content", ""))}
                         for m in messages],
        }
        max_tokens = kwargs.get("max_tokens")
        if max_tokens is None:
            max_tokens = 512
        payload["max_tokens"] = int(max_tokens)
        temperature = kwargs.get("temperature")
        if temperature is not None:
            payload["temperature"] = float(temperature)

        status, body = self._post("/v1/chat/completions", payload, self.chat_timeout)
        if status != 200:
            self._raise_for_payload(status, body)
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise ProviderError(ErrorKind.UNKNOWN,
                                self._mask("bad chat response: %s" % exc),
                                http_status=status, provider=self.name) from exc

        # ⚠ 判定失败必须读 base_resp.status_code，不能只看 HTTP 状态码（60 号 §3）
        base_resp = data.get("base_resp")
        if isinstance(base_resp, dict) and int(base_resp.get("status_code") or 0) != 0:
            self._raise_for_payload(status, body)

        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        raw_content = str(message.get("content") or "")
        content, inline_reasoning = strip_think(raw_content)
        reasoning = str(message.get("reasoning_content") or "") or inline_reasoning
        return ChatReply(text=content, reasoning=reasoning,
                         model=str(data.get("model") or payload["model"]),
                         raw=data)

    # ── tts ────────────────────────────────────────────────────────────────
    def tts(self, text: str, **kwargs: Any) -> TtsAudio:
        """语音合成 → 16 kHz 单声道裸 PCM。"""
        voice = str(kwargs.get("voice") or self.tts_voice)
        payload: Dict[str, Any] = {
            "model": str(kwargs.get("model") or self.tts_model),
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": float(kwargs.get("speed", 1.0)),
                "vol": float(kwargs.get("vol", 1.0)),
                "pitch": int(kwargs.get("pitch", 0)),
            },
            "audio_setting": {
                "sample_rate": int(kwargs.get("sample_rate", 16000)),
                "bitrate": int(kwargs.get("bitrate", 128000)),
                "format": "pcm",
                "channel": 1,
            },
        }
        status, body = self._post("/v1/t2a_v2", payload, self.tts_timeout)
        try:
            data = json.loads(body.decode("utf-8", "ignore"))
        except Exception:
            data = None

        code = 0
        if isinstance(data, dict):
            base_resp = data.get("base_resp")
            if isinstance(base_resp, dict):
                code = int(base_resp.get("status_code") or 0)
        # ⚠ 成功判据是 base_resp.status_code == 0（音色无效时也是 HTTP 200）
        if status != 200 or code != 0:
            self._raise_for_payload(status, body)

        audio_field = ""
        data_field = (data.get("data") or {}) if isinstance(data, dict) else {}
        for key in ("audio", "data"):
            value = data_field.get(key)
            if isinstance(value, str) and value:
                audio_field = value
                break
        if not audio_field:
            raise ProviderError(ErrorKind.UNKNOWN,
                                self._mask("tts response has no audio field"),
                                code=code, http_status=status, provider=self.name)
        try:
            pcm = bytes.fromhex(audio_field)
        except ValueError as exc:
            raise ProviderError(ErrorKind.UNKNOWN,
                                self._mask("tts audio is not hex: %s" % exc),
                                code=code, http_status=status, provider=self.name) from exc
        sample_rate = int(payload["audio_setting"]["sample_rate"])
        return TtsAudio(pcm=pcm, sample_rate=sample_rate, channels=1,
                        encoding="pcm_s16le", voice=voice, provider=self.name)

    # ── asr ────────────────────────────────────────────────────────────────
    @property
    def supports_asr(self) -> bool:
        """仓库里**没有**任何 ASR 接口的实测依据（60 号只覆盖 chat 与 t2a_v2）。"""
        return False

    def __repr__(self) -> str:  # pragma: no cover
        return ("<MiniMaxProvider base=%s model=%s voice=%s key=***>"
                % (self.base_url, self.chat_model, self.tts_voice))


__all__ = ["MiniMaxProvider", "strip_think"]
