#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_literature.py —— 陪伴机器人项目的文献抓取器（可复现、可入 CI）

为什么是脚本而不是手工搜
------------------------
本项目要引用的文献必须**可复现**：任何人在任何时间跑同一条命令，都应拿到同一批
arXiv / Semantic Scholar 记录（含 ID、日期、URL）。手工搜索结果无法复现，也无法
在 CI 里做「引用还在不在」的回归。

数据源
------
1. **arXiv API**（`export.arxiv.org/api/query`）—— 全文可得、ID 稳定、免鉴权。
   对 cs.RO / cs.HC / cs.CL 这几个与本项目直接相关的领域覆盖足够。
2. **Semantic Scholar API**（`api.semanticscholar.org/graph/v1`）—— 补充被 arXiv
   漏掉的正式出版物（ACL/EMPL/CHI 论文常有 arXiv 预印本，但引用数、会议信息更全）。

用法
----
    py -3.12 tools/fetch_literature.py --list
    py -3.12 tools/fetch_literature.py --topics voice-latency,tts-streaming
    py -3.12 tools/fetch_literature.py --all --out docs/research/68-文献综述.md
    py -3.12 tools/fetch_literature.py --all --out xxx.md --verify-ids
    py -3.12 tools/fetch_literature.py --self-test

`--self-test` **不联网**（用内置 fixture），所以能进 CI；联网模式失败只降级不中断
（单条 query 挂掉不影响其余 query 的产出）。

出处等级
--------
本项目沿用 T1/T2/T3/T4 分级（见 `docs/spec/08`）。本工具产出的记录一律标 **T4**
（第三方来源 / 检索所得），**不是 T1**：一条 arXiv 摘要说明的是「论文声称了什么」，
不等于「事实已被独立验证」。使用前仍需回源读原文。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Windows 控制台默认 GBK，输出含特殊字符会抛 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - 非 Windows / 老 Python
    pass

__version__ = "1.0.0"

ARXIV_API = "http://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

# arXiv 官方要求：连续请求之间至少间隔 3 秒，否则返回 429 / 403
ARXIV_MIN_INTERVAL_S = 3.0
# Semantic Scholar 匿名限流很紧：官方建议 429 后退避 ≥ 5s
RATE_LIMIT_BACKOFF_S = 5.0
HTTP_TIMEOUT_S = 30
HTTP_RETRIES = 4
USER_AGENT = "StackChanCompanion/1.0 (literature harvester; +https://github.com/)"


# ---------------------------------------------------------------------------
# 主题登记表
# ---------------------------------------------------------------------------
# 每个主题 = 一组检索式 + 一句「为什么要查这个」。
# 检索式是**可复现的关键**：换一个人跑必须拿到同一批结果，所以不许写「随便搜点」。
# ---------------------------------------------------------------------------

TOPICS = {
    "voice-latency": {
        "title": "语音交互延迟与人类对话轮次容忍度",
        "why": "本项目的陪伴体验成败在「按下麦克风到出声」这段。人类对话里超过某个阈值就"
               "会感觉「卡」而不是「慢」。要找的是**可引用的阈值证据**，不是厂商宣传。",
        "arxiv": [
            'all:"turn taking" AND all:"speech" AND all:"latency"',
            'all:"conversational latency"',
            'all:"speech" AND all:"response delay" AND all:"user experience"',
        ],
        "semantic": [
            "conversational latency speech turn taking user experience",
            "voice assistant response delay perception",
        ],
    },
    "tts-streaming": {
        "title": "流式 TTS 的首包延迟与分段播放",
        "why": "决定「小栈开口」要等多久。流式合成 vs 整段合成差一个量级；且分段播放会"
               "引入拼接断点。本项目已实测「关键帧驱动切法」（tools/audio_chunk.py），需要"
               "文献佐证分段策略的代价。",
        "arxiv": [
            'all:"text-to-speech" AND all:"streaming" AND all:"latency"',
            'all:"streaming speech synthesis"',
            'all:"first byte" AND all:"speech synthesis"',
        ],
        "semantic": [
            "streaming text-to-speech first packet latency",
            "chunked speech synthesis concatenation artifacts",
        ],
    },
    "llm-companion": {
        "title": "LLM 陪伴机器人的拟人化、依恋与再互动",
        "why": "产品定位是「陪伴」。要找的是：拟人化到什么程度会让人愿意反复回来，"
               "以及哪些设计会踩「creepy」红线。这是护城河论证（spec/04）的外部证据。",
        "arxiv": [
            'all:"social robot" AND all:"anthropomorphism"',
            'all:"LLM" AND all:"companion" AND all:"attachment"',
            'all:"social chatbot" AND all:"anthropomorphic"',
            'all:"re-engagement" AND all:"social robot"',
        ],
        "semantic": [
            "LLM companion chatbot anthropomorphism attachment re-engagement",
            "social robot conversational quality re-engagement intention",
        ],
    },
    "robot-face": {
        "title": "机器人屏幕脸 / 表情渲染与可辨识度",
        "why": "StackChan 的脸是 320×240 单色屏。本项目要决定 App 端的脸是「逐像素镜像设备」"
               "还是「风格化」。要找的是：低分辨率、单色条件下，表情的可辨识度受什么约束。",
        "arxiv": [
            'all:"facial expression" AND all:"robot" AND all:"display"',
            'all:"emotive" AND all:"robot face"',
            'all:"simplified" AND all:"facial expression" AND all:"recognition"',
        ],
        "semantic": [
            "robot face display emotional expression rendering",
            "low resolution line drawing facial expression recognition",
        ],
    },
    "embodied-hri": {
        "title": "具身代理与 HRI 的信任校准",
        "why": "小栈是「设备当身体、手机当大脑」的分裂式具身。要找的是：具身程度对信任"
               "的影响，以及「非人但有人格」的设定会不会引发不适。",
        "arxiv": [
            'all:"trust" AND all:"anthropomorphic agent"',
            'all:"embodied agent" AND all:"trust calibration"',
            'all:"human-robot interaction" AND all:"social presence"',
        ],
        "semantic": [
            "trust anthropomorphic agent calibration robot",
            "embodied conversational agent social presence",
        ],
    },
    "privacy-companion": {
        "title": "AI 陪伴的隐私、依赖与伦理争议",
        "why": "本项目硬约束是「个人定制数据永不入库」。同时要诚实面对：陪伴型 AI 的"
               "依赖风险、情感操纵风险是已知争议。求职作品里这一块写清楚反而加分。",
        "arxiv": [
            'all:"social robot" AND all:"privacy" AND all:"concerns"',
            'all:"AI companion" AND all:"ethics"',
            'all:"emotional manipulation" AND all:"chatbot"',
        ],
        "semantic": [
            "domestic social robot privacy security concerns",
            "AI companion emotional dependency ethics",
        ],
    },
    # ── 2026-10-25 扩充批：3 个新主题 ────────────────────────────────────
    "prosocial-robot": {
        "title": "社交机器人与亲社会行为 / 幸福感效应",
        "why": "护城河论证不能只说「聊天像人」。要找的是**机器人陪伴带来的可测收益**"
               "（亲社会行为、孤独感、幸福感）—— 这决定「陪伴型机器人」是不是真需求，"
               "还是只是新鲜感。也决定功能取舍该往「让人变好」还是「让人离不开」倾斜。",
        "arxiv": [
            'all:"social robot" AND all:"prosocial"',
            'all:"social robot" AND all:"wellbeing" AND all:"loneliness"',
            'all:"robot" AND all:"prosocial behavior" AND all:"children"',
        ],
        "semantic": [
            "social robot prosocial behavior children empathy",
            "social robot loneliness wellbeing older adults intervention",
        ],
    },
    "memory-persona-consistency": {
        "title": "长期记忆、人格一致性与跨会话连续性",
        "why": "本项目的人格包 + 记忆是三层结构，核心主张是「人格跨会话稳定」。"
               "要找的是：什么条件下用户能感知到「还是同一个人」、记忆一致性的评价方法、"
               "以及长期记忆引入的**矛盾/遗忘**风险。这直接约束记忆合并策略与回滚设计。",
        "arxiv": [
            'all:"long-term memory" AND all:"conversational agent"',
            'all:"persona consistency" AND all:"dialogue"',
            'all:"narrative consistency" AND all:"LLM" AND all:"memory"',
        ],
        "semantic": [
            "long-term memory conversational agent persona consistency",
            "LLM chatbot memory consistency evaluation multi-session",
        ],
    },
    "voice-barge-in": {
        "title": "语音对话的打断处理、重叠语音与轮次管理",
        "why": "iOS 端已定音频 category = Play and record（要同时播和收）。真正的难点是"
               "**barge-in**（用户抢话）与**重叠语音**（自己说话时把自己的声音收进来）。"
               "要找的是回声消除、VAD 门限、抢话判定阈值的可引用做法 —— 这是 App 侧音频链路的"
               "真实风险点，之前只做了 TTS 播放侧，**收音侧还没设计**。",
        "arxiv": [
            'all:"barge-in" AND all:"voice assistant"',
            'all:"speech separation" AND all:"self-echo" AND all:"full-duplex"',
            'all:"voice activity detection" AND all:"overlap" AND all:"dialogue"',
        ],
        "semantic": [
            "barge-in voice assistant interruption full duplex speech",
            "acoustic echo cancellation self speech detection microphone",
        ],
    },
    # ── 2026-10-25 扩充批二：8 个新主题（第三轮夜间） ───────────────────────
    "edge-on-device-llm": {
        "title": "端侧小模型推理、量化与本地 provider 的可行性",
        "why": "Q14「做不做 server/providers/local.py」需要外部依据而不是拍脑袋。"
               "要找的是：在什么硬件预算下本地能跑多小的模型、能撑住什么交互；"
               "以及端侧推理对延迟、隐私、离线可用性的实际收益与代价。"
               "本项目已定「手机出声、设备做身体」的分裂式架构 ⇒ 本地推理天然落在手机上。",
        "arxiv": [
            'all:"on-device" AND all:"large language model" AND all:"quantization"',
            'all:"edge inference" AND all:"language model" AND all:"latency"',
            'all:"small language model" AND all:"local deployment"',
        ],
        "semantic": [
            "on-device LLM quantization edge inference latency",
            "small language model local deployment privacy offline",
        ],
    },
    "affective-computing": {
        "title": "情感计算：语音韵律的情绪特征与识别",
        "why": "本项目的「韵律 → 动作」链路（tools/prosody_to_motion.py）目前是自研启发式。"
               "要找的是学界常用的韵律特征维度（valence/arousal 等）与情绪识别的可靠性边界，"
               "以便说明我们抽取的 7 维特征是站在什么基础上、有哪些已知失效模式。",
        "arxiv": [
            'all:"affective computing" AND all:"speech" AND all:"emotion recognition"',
            'all:"prosody" AND all:"emotion" AND all:"acoustic features"',
            'all:"valence" AND all:"arousal" AND all:"speech"',
        ],
        "semantic": [
            "affective computing speech emotion recognition valence arousal",
            "speech prosody features emotion detection reliability",
        ],
    },
    "robot-motion-expression": {
        "title": "机器人肢体动作的情绪表达与感染效应",
        "why": "小栈有舵机（身体），不只有脸（表情）。要找的是：动作幅度/速度与情绪的可辨识度关系，"
               "以及运动表达能否放大或干扰面部表情。这是 spec/06「风格化脸是否允许超 40% 面积」"
               "和身体动作参数化的直接依据。",
        "arxiv": [
            'all:"robot motion" AND all:"emotion" AND all:"expression"',
            'all:"embodied" AND all:"expression" AND all:"motion generation"',
            'all:"social robot" AND all:"gesture" AND all:"engagement"',
        ],
        "semantic": [
            "robot motion emotion expression recognition",
            "embodied agent gesture animation engagement",
        ],
    },
    "wake-word-vad": {
        "title": "唤醒词、端侧 VAD 与始终在线语音链路",
        "why": "真机语音链路还缺「收音侧」设计：唤醒词、VAD 门限、始终在线的功耗。"
               "ESP32 官方固件是否带音频通道尚未验证 ⇒ 若要 App 侧全权收音，"
               "唤醒与 VAD 必须在手机上做。找可引用的门限与功耗做法。",
        "arxiv": [
            'all:"wake word" AND all:"detection" AND all:"on-device"',
            'all:"voice activity detection" AND all:"noise" AND all:"robustness"',
            'all:"always-on" AND all:"speech" AND all:"power"',
        ],
        "semantic": [
            "wake word detection on-device low power",
            "voice activity detection noise robustness threshold",
        ],
    },
    "parametric-face-animation": {
        "title": "参数化 2D 表情动画：情绪强度与表情混合",
        "why": "App 端脸是参数化模型（CoreProtocol/AvatarModel 的 eyeWeight / rotation / "
               "mouth 尺寸等）。要找的是：单色低分辨率下参数化表情的可辨识度上限、"
               "情绪强度该映射到哪个参数、表情之间的混合是否会让观众读错。"
               "这直接约束我们「几何一致 / 风格化」的边界。",
        "arxiv": [
            'all:"facial expression" AND all:"parameterization" AND all:"animation"',
            'all:"avatar" AND all:"expression" AND all:"parametric"',
            'all:"emotion intensity" AND all:"facial expression" AND all:"animation"',
        ],
        "semantic": [
            "parametric facial expression animation emotion intensity",
            "2D avatar expression blending recognizability low resolution",
        ],
    },
    "local-first-architecture": {
        "title": "local-first 架构、端云协同与离线可用性",
        "why": "硬约束是「个人定制数据永不入库」⇒ 架构上必须 local-first。"
               "要找的是 local-first 语料里对同步/冲突/离线降级的共识做法，"
               "以及「云端大脑 + 本地身体」这种分裂式架构有没有已知失败模式。"
               "这是 spec/07 §3.6 方案 A 的架构正当性来源。",
        "arxiv": [
            'all:"local-first" AND all:"software" AND all:"collaboration"',
            'all:"edge cloud" AND all:"collaboration" AND all:"latency"',
            'all:"offline" AND all:"assistant" AND all:"reliability"',
        ],
        "semantic": [
            "local-first software sync conflict offline",
            "edge cloud collaborative inference latency reliability",
        ],
    },
    "companion-retention": {
        "title": "AI 陪伴的留存、习惯养成与长期参与",
        "why": "产品成败看留存而非首日惊艳。要找的是：什么机制让用户回来"
               "（提醒、连续性、成长感、仪式感），以及哪些机制属于「成瘾式留存」"
               "（伦理风险，本项目明确不做）。这决定 spec/04 的功能取舍排序。",
        "arxiv": [
            'all:"chatbot" AND all:"user engagement" AND all:"retention"',
            'all:"AI companion" AND all:"habit" AND all:"engagement"',
            'all:"social robot" AND all:"long-term engagement" AND all:"home"',
        ],
        "semantic": [
            "chatbot engagement retention long-term usage",
            "AI companion habit formation engagement design",
        ],
    },
    # ------------------------------------------------------------------
    # 第四轮新增（2026-10-25 夜间）：每个主题都对应一个**尚未销账的决策项**，
    # 不是泛泛补充。
    # ------------------------------------------------------------------
    "llm-first-token-latency": {
        "title": "LLM 首 token 延迟与流式输出的感知阈值",
        "why": "M1 的「开始出声 < 2.5 s」实测不达标（Q16），瓶颈在上游 API。"
               "要找的是：流式首 token 到「可以开始合成」这段能不能救，"
               "以及「先说一句短的」在感知上是否真的更快（还是只是错觉）。",
        "arxiv": [
            'all:"first token" AND all:"latency" AND all:"language model"',
            'all:"streaming" AND all:"language model" AND all:"time to first token"',
            'all:"progressive" AND all:"response generation" AND all:"latency"',
        ],
        "semantic": [
            "LLM time to first token streaming latency perception",
            "streaming generation perceived responsiveness user study",
        ],
    },
    "llm-sycophancy": {
        "title": "LLM 谄媚、迎合与真实性",
        "why": "81 号实证：**谄媚是 ENFP 热情人格的头号风险**（谄媚已被基准化："
               "418 陈述 / 11 选举 / 6 LLM，方法是角色扮演实验 ⇒ 与我们 E-4 同构）。"
               "E-4 的「不谄媚」护栏必须挂文献，否则只是我们自己的偏好。",
        "arxiv": [
            'all:"sycophancy" AND all:"language model"',
            'all:"sycophantic" AND all:"chatbot" AND all:"behavior"',
            'all:"user" AND all:"agreeability" AND all:"truthfulness" AND all:"language model"',
        ],
        "semantic": [
            "sycophancy LLM benchmark roleplay chat assistant",
            "flattery agreement bias language model persona",
        ],
    },
    "presence-attention-detection": {
        "title": "在场感知、注意力与走神检测",
        "why": "Q18（在场感知边界）与 Q19（端侧检测技术路线）都还是空的。"
               "要找的是：哪些信号能机器可判地区分「在 / 不在 / 专注 / 走神 / 低落」，"
               "以及在手机上做（无摄像头？摄像头？）各自的代价与隐私边界。",
        "arxiv": [
            'all:"attention detection" AND all:"human" AND all:"signal"',
            'all:"activity recognition" AND all:"mobile phone" AND all:"on-device"',
            'all:"presence detection" AND all:"ambient" AND all:"sensor"',
        ],
        "semantic": [
            "on-device attention distraction detection mobile",
            "human presence detection privacy sensor design",
        ],
    },
    "anthropomorphism-feedback-loop": {
        "title": "拟人化反馈回路、社交反馈放大与过度依附",
        "why": "81 号第四波：⭐⭐⭐ **情绪表达会被社交反馈放大到 4 倍**"
               "（Hawkes 自激点过程）⇒ Q17「小栈不永远甜」是**机制问题**不是措辞问题。"
               "要找的是：反馈回路怎么装制动，以及过度依附（over-attachment）"
               "在文献里的可观测指标。",
        "arxiv": [
            'all:"anthropomorphism" AND all:"feedback" AND all:"amplification"',
            'all:"social feedback" AND all:"self-disclosure" AND all:"reciprocity"',
            'all:"parasocial" AND all:"attachment" AND all:"over-reliance" AND all:"chatbot"',
        ],
        "semantic": [
            "anthropomorphic agent feedback loop amplification emotional expression",
            "parasocial relationship chatbot overattachment withdrawal",
        ],
    },
    "ai-companion-wellbeing": {
        "title": "AI 陪伴 / 社交机器人的心理健康效果与风险",
        "why": "81 号第四波：**「陪伴机器人能改善心理健康」本身不确定**"
               "（同行评议项目只报 mixed results）⇒ 里程碑与作品集**不得承诺疗效**。"
               "要找的是：哪些效果有证据、哪些是「混合结果」，以及风险侧（依赖、替代人类支持）。",
        "arxiv": [
            'all:"social robot" AND all:"mental health" AND all:"systematic review"',
            'all:"AI companion" AND all:"well-being" AND all:"longitudinal"',
            'all:"chatbot" AND all:"psychological" AND all:"effect" AND all:"randomized"',
        ],
        "semantic": [
            "social robot mental health intervention mixed evidence review",
            "AI companion loneliness wellbeing longitudinal study",
        ],
    },
    "privacy-data-lifecycle": {
        "title": "数据最小化、生命周期管理与用户数据可导出",
        "why": "Q5「个人数据永不入库」有两种读法（不外发第三方 / 不进运营方库+不进训练集+可导出），"
               "81 号给出的正解是按**敏感值的生命周期**五段切（存/取/用/展示/导出）。"
               "要找的是：隐私工程里「数据生命周期」「数据最小化」「可携带性」的既有做法与术语。",
        "arxiv": [
            'all:"data minimization" AND all:"privacy" AND all:"lifecycle"',
            'all:"privacy by design" AND all:"personal data" AND all:"data protection"',
            'all:"data portability" AND all:"user" AND all:"personal data" AND all:"right"',
        ],
        "semantic": [
            "privacy by design data minimization personal data lifecycle",
            "data portability user export control GDPR personal data",
        ],
    },
    "edge-cloud-routing": {
        "title": "端云模型路由、级联与延迟/成本取舍",
        "why": "Q14（要不要做本地 provider）+ Q16（延迟优化）+ D5 互为牵扯。"
               "要找的是：按置信度/难度在端与云之间路由的既有做法，"
               "以及「按置信度路由若不校准就是错的」这条风险的出处。",
        "arxiv": [
            'all:"model routing" AND all:"edge" AND all:"cloud" AND all:"latency"',
            'all:"cascade" AND all:"large language model" AND all:"small model"',
            'all:"confidence" AND all:"calibration" AND all:"routing" AND all:"LLM"',
        ],
        "semantic": [
            "LLM cascading edge cloud routing latency cost tradeoff",
            "selective prediction confidence calibration abstain LLM routing",
        ],
    },
    "realtime-audio-streaming-protocol": {
        "title": "实时音频流式传输协议与低延迟音频通道",
        "why": "Q10（App↔云音频承载方式 A/B/C）待拍板，方案 A = WS 二进制分片 `0x1C`。"
               "要找的是：WebSocket / RTP 这类承载在二进制音频上的已知代价"
               "（抖动缓冲、分片边界、乱序、时钟漂移），让拍板有外部依据而不是拍脑袋。",
        "arxiv": [
            'all:"WebSocket" AND all:"audio" AND all:"streaming" AND all:"latency"',
            'all:"real-time" AND all:"audio" AND all:"transport" AND all:"jitter"',
            'all:"low latency" AND all:"audio streaming" AND all:"packetization"',
        ],
        "semantic": [
            "websocket binary audio streaming low latency packetization",
            "real time audio transport jitter buffer reordering network",
        ],
    },
    "llm-persona-control": {
        "title": "LLM 人格控制、角色一致性与角色卡工程",
        "why": "人格包（personas/enfp.json + persona.py）是三层结构的中间层。"
               "要找的是：系统提示词/角色卡怎么做才能跨会话稳定、不漂移、不人格分裂；"
               "以及「一致性」该怎么量化评测。这直接约束人格层的实现与回归测试。",
        "arxiv": [
            'all:"persona" AND all:"language model" AND all:"role"',
            'all:"character consistency" AND all:"LLM" AND all:"generation"',
            'all:"persona" AND all:"controlled generation" AND all:"dialogue"',
        ],
        "semantic": [
            "LLM persona consistent role playing dialogue",
            "character consistency language model evaluation persona drift",
        ],
    },
}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class FetchError(Exception):
    """单条检索失败（网络/限流/解析）。调用方应降级处理而不是中断整轮。"""


def _http_get(url: str, headers: dict | None = None) -> bytes:
    """带指数退避的 GET。

    Semantic Scholar 对匿名请求限流很紧（429），且官方建议退避到 5s+。
    这里对 429/403/503 用**更长的**退避（5s → 10s → 20s），
    对其它错误用短退避。超过重试上限就抛 FetchError，由调用方降级。
    """
    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:  # 429/403 需要退避
            last = FetchError("HTTP %s" % exc.code)
            if exc.code in (429, 403, 503):
                time.sleep(RATE_LIMIT_BACKOFF_S * (attempt + 1))
                continue
            raise FetchError("HTTP %s" % exc.code) from exc
        except Exception as exc:  # noqa: BLE001 - 网络异常种类多，统一包装
            last = FetchError(str(exc))
            time.sleep(1.0 * (attempt + 1))
    raise last if last else FetchError("unknown")


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _arxiv_summary(entry) -> str:
    node = entry.find(_ATOM + "summary")
    if node is None or not node.text:
        return ""
    return " ".join(node.text.split())


def _arxiv_authors(entry) -> list:
    names = []
    for a in entry.findall(_ATOM + "author"):
        n = a.find(_ATOM + "name")
        if n is not None and n.text:
            names.append(n.text.strip())
    return names


def _arxiv_primary_id(entry) -> str:
    """取不带版本号的 arXiv ID（v1/v2 → 基础 ID），用于去重与 URL 规范化。"""
    raw = (entry.findtext(_ATOM + "id") or "").strip()
    m = re.search(r"arxiv\.org/abs/([^\s/]+)", raw)
    if not m:
        return ""
    return re.sub(r"v\d+$", "", m.group(1))


def _arxiv_published(entry) -> str:
    return (entry.findtext(_ATOM + "published") or "").strip()[:10]


_QUOTED_FIELD_RE = re.compile(r'(all|ti|abs|cat|co|jr|au):"([^"]+)"')


def arxiv_query_variants(query: str) -> list:
    """给一条 arXiv 检索式生成兜底变体。

    ⭐ **实测（2026-10-25）**：arXiv API 对 ``all:"多词短语"`` 的处理有坑 ——
    ``all:"social robot" AND all:"prosocial"`` 返回 **0 条**，
    而 ``all:robot AND all:"prosocial"`` 返回 5 条、
    ``all:"social robot"`` 单独也能返回 5 条。
    ⇒ **引号短语 + AND 会静默吞掉结果**，且工具不会报错 ⇒ 整个主题变成 0 条。

    修法：原式命中 0 条时，用**去引号拆分变体**重试
    （``all:"social robot"`` ⇒ ``all:social AND all:robot``）。
    本工具是**召回优先**的文献检索，短语的精确匹配没有价值。

    返回 ``[(原式), (变体1), ...]``，原式永远排第一。
    """
    variants = [query]

    def _split(m):
        field, phrase = m.group(1), m.group(2)
        words = [w for w in re.split(r"[\s\-]+", phrase) if w]
        if len(words) < 2:
            return m.group(0)
        return " AND ".join('%s:"%s"' % (field, w) for w in words)

    expanded = _QUOTED_FIELD_RE.sub(_split, query)
    if expanded != query:
        variants.append(expanded)
    return variants


def fetch_arxiv(query: str, max_results: int = 12) -> list:
    """按一条 arXiv 检索式取记录。失败抛 FetchError（调用方降级）。

    ⭐ 原式返回 0 条时自动用**去引号拆分变体**重试（见 ``arxiv_query_variants``），
    避免 arXiv 的引号短语坑把整个主题静默清零。
    """
    last_error = None
    for variant in arxiv_query_variants(query):
        params = {
            "search_query": variant,
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        url = ARXIV_API + "?" + urllib.parse.urlencode(params)
        try:
            raw = _http_get(url, {"User-Agent": USER_AGENT})
        except FetchError as exc:
            last_error = exc
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            last_error = FetchError("arXiv XML parse: %s" % exc)
            continue
        out = []
        for entry in root.findall(_ATOM + "entry"):
            aid = _arxiv_primary_id(entry)
            if not aid:
                continue
            title = " ".join((entry.findtext(_ATOM + "title") or "").split())
            if not title:
                continue
            comment = entry.findtext(_ARXIV_NS + "comment") or ""
            out.append({
                "source": "arXiv",
                "id": aid,
                "title": title,
                "authors": _arxiv_authors(entry),
                "published": _arxiv_published(entry),
                "venue": "arXiv preprint",
                "url": "https://arxiv.org/abs/%s" % aid,
                "abstract": _arxiv_summary(entry),
                "note": comment.strip(),
                "citation_count": None,
                "doi": None,
                "query": query,
            })
        if out:
            return out
        # 原式 0 条 ⇒ 试下一个变体（引号短语坑）
    if last_error is not None:
        raise last_error
    return []


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

def fetch_semantic(query: str, limit: int = 8) -> list:
    """按一条检索式取 S2 记录。失败抛 FetchError。"""
    params = {
        "query": query,
        "limit": str(limit),
        "fields": "title,abstract,year,authors,venue,externalIds,url,citationCount",
    }
    url = S2_API + "?" + urllib.parse.urlencode(params)
    raw = _http_get(url, {"User-Agent": USER_AGENT})
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise FetchError("S2 json: %s" % exc) from exc

    out = []
    for rec in data.get("data") or []:
        title = (rec.get("title") or "").strip()
        if not title:
            continue
        ext = rec.get("externalIds") or {}
        s2id = rec.get("paperId") or ""
        aid = ext.get("ArXiv") or ""
        doi = ext.get("DOI") or ""
        year = rec.get("year")
        out.append({
            "source": "Semantic Scholar",
            "id": s2id,
            "arxiv_id": aid,
            "doi": doi,
            "title": title,
            "authors": [a.get("name", "") for a in (rec.get("authors") or []) if a.get("name")],
            "published": str(year) if year else "",
            "venue": rec.get("venue") or "",
            "url": rec.get("url") or ("https://arxiv.org/abs/%s" % aid if aid else ""),
            "abstract": " ".join((rec.get("abstract") or "").split()),
            "note": "",
            "citation_count": rec.get("citationCount"),
            "query": query,
        })
    return out


# ---------------------------------------------------------------------------
# 去重 / 排序
# ---------------------------------------------------------------------------

def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


# arXiv 的 venue 固定是 "arXiv preprint"，信息量低于 S2 给的正式会议/期刊名。
# 去重时不能「先到先得」，否则正式出处会被 preprint 字样盖掉。
_ARXIV_VENUE = "arxiv preprint"


def _venue_specificity(venue: str) -> int:
    """venue 的信息量评分：越大越具体。"""
    v = (venue or "").strip()
    if not v:
        return 0
    if v.lower() == _ARXIV_VENUE:
        return 1
    return 2


def dedupe(records: list) -> list:
    """按 arXiv ID / DOI / 规范化标题三路去重。

    同一篇论文常同时出现在 arXiv 与 S2（后者还多出引用数与会议名），
    这时**逐字段择优合并**：谁的信息量更大用谁，而不是「先到先得」。
    """
    best: dict = {}
    order: list = []

    def key_for(rec):
        aid = rec.get("arxiv_id") or (rec.get("id") if rec.get("source") == "arXiv" else "")
        if aid:
            return "arxiv:" + aid.lower()
        if rec.get("doi"):
            return "doi:" + rec["doi"].lower()
        return "title:" + _norm_title(rec.get("title", ""))

    for rec in records:
        k = key_for(rec)
        if k not in best:
            best[k] = dict(rec)
            order.append(k)
            continue
        cur = best[k]
        # 合并：缺失字段从对方补；citation_count 取有值的那个
        for field in ("abstract", "doi", "arxiv_id", "url", "note"):
            if not cur.get(field) and rec.get(field):
                cur[field] = rec[field]
        # venue 取更具体的那条（"arXiv preprint" < "CHI"）
        if _venue_specificity(rec.get("venue", "")) > _venue_specificity(cur.get("venue", "")):
            cur["venue"] = rec["venue"]
        if cur.get("citation_count") is None and rec.get("citation_count") is not None:
            cur["citation_count"] = rec["citation_count"]
        if len(rec.get("authors") or []) > len(cur.get("authors") or []):
            cur["authors"] = rec["authors"]
        # arXiv 有稳定 ID，S2 没有的场合保留 S2 原 id 便于追溯
        if cur.get("source") == "Semantic Scholar" and rec.get("source") == "arXiv":
            cur.setdefault("arxiv_id", rec.get("id"))

    return [best[k] for k in order]


def rank(records: list) -> list:
    """排序：引用数优先，其次年份新的优先。同分时保持抓取顺序（= 相关性序）。"""
    def key(rec):
        cc = rec.get("citation_count")
        cc = -1 if cc is None else int(cc)
        year = rec.get("published") or "0000"
        return (-cc, _neg_year(year))
    return sorted(records, key=key)


def _neg_year(year: str) -> str:
    """让「年份越大越靠前」。对 'YYYY' 与 'YYYY-MM-DD' 都成立。"""
    digits = "".join(ch for ch in (year or "") if ch.isdigit())
    if not digits:
        return "00000000"
    return ("00000000" + digits)[-8:]


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """转义表格/引用会破坏结构的字符。

    `|` 在 Markdown 表格里会分列，在正文里也可能被误读成表格分隔符，
    统一转成 `\\|`。换行压成空格。
    """
    if not text:
        return ""
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# 反向解析 + 跨次并集合并
# ---------------------------------------------------------------------------
#
# 为什么必须有这个能力（2026-10-25 实测）：
#   arXiv 与 Semantic Scholar 的可用性是**波动的**（S2 常年 HTTP 429），
#   同一条检索式在不同时间跑出来的结果集**互不包含**：
#     * S2 正常那次 —— 有 S2 的正式出处（带引用数），但缺 arXiv 的补充命中；
#     * S2 被限流那次 —— 有 arXiv 的命中，但丢了 S2 的正式出处。
#   ⇒ 「只保留最后一次跑的结果」等于**主动丢弃**已经抓到的文献。
#
# 所以留痕文件要能**跨次取并集**：本节把已生成的留痕反向解析回结构，
# 与新抓的结果合并去重后重新渲染。合并是**无损**的：同一 arXiv ID 跨文件
# 出现时按字段择优合并（与 dedupe() 同一套规则）。

_META_SEP = "｜"   # 全角竖线（渲染时用它分隔元信息位）

_ENTRY_RE = re.compile(r"^### ([A-Za-z0-9_\-]+)\.(\d+) (.*)$")
_AUTHORS_MORE_RE = re.compile(r"\s*等\s*\d+\s*人$")


def _unescape(text: str) -> str:
    """_escape 的逆运算。

    _escape 的顺序是「先转义反斜杠、再转义竖线」⇒ 逆运算必须**反过来**：
    先把 `\\|` 还原成 `|`，再把 `\\\\` 还原成 `\\`。
    """
    out = text.replace("\\|", "|")
    out = out.replace("\\\\", "\\")
    return out


def _parse_meta_line(body: str) -> dict:
    """解析 `- arXiv:`x` ｜ 引用数：3 ｜ … ｜ 来源：arXiv` 这一行。"""
    rec = {}
    parts = [p.strip() for p in body.split(_META_SEP)]
    if not parts or not parts[-1].startswith("来源："):
        return {}
    for part in parts:
        if part.startswith("arXiv:"):
            rec["arxiv_id"] = part[len("arXiv:"):].strip().strip("`")
        elif part.startswith("DOI:"):
            rec["doi"] = part[len("DOI:"):].strip().strip("`")
        elif part.startswith("引用数："):
            try:
                rec["citation_count"] = int(part[len("引用数："):].strip())
            except ValueError:
                pass
        elif part.startswith("日期："):
            rec["published"] = part[len("日期："):].strip()
        elif part.startswith("出处："):
            rec["venue"] = _unescape(part[len("出处："):].strip())
        elif part.startswith("来源："):
            rec["source"] = part[len("来源："):].strip()
    return rec


def parse_markdown_groups(path: str) -> tuple:
    """把一份留痕文件反向解析成 {topic_key: [record, ...]}。

    返回 (groups, header)。header 含「取证时间」、文件路径、坏条目数。
    解析不抛异常：坏条目跳过，保证单份坏文件不会毁掉整次合并。
    """
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    groups: dict = {}
    header = {"path": path, "generated_at": "", "skipped": 0, "count": 0}
    cur = None
    abs_parts: list = []
    in_abs = False

    def flush():
        nonlocal cur, abs_parts, in_abs
        if cur is None:
            return
        if in_abs and abs_parts:
            cur["abstract"] = " ".join(abs_parts)
        if cur.get("source") == "arXiv" and cur.get("arxiv_id"):
            cur["id"] = cur["arxiv_id"]
        if not cur.get("title"):
            header["skipped"] += 1
        else:
            groups.setdefault(cur["_key"], []).append(cur)
        cur = None
        abs_parts = []
        in_abs = False

    for raw in text.splitlines():
        line = raw.rstrip("\r")
        m = _ENTRY_RE.match(line)
        if m:
            flush()
            cur = {"_key": m.group(1), "title": _unescape(m.group(3)),
                   "source": "", "authors": []}
            continue
        if cur is None:
            if "取证时间：" in line and not header["generated_at"]:
                header["generated_at"] = line.split("取证时间：", 1)[1].split(_META_SEP)[0].strip()
            continue
        if line.startswith("> 摘要"):
            in_abs = True
            abs_parts = []
            continue
        if in_abs:
            if line.startswith(">"):
                body = line[1:]
                if body.startswith(" "):
                    body = body[1:]
                if body:
                    abs_parts.append(body)
                continue
            flush()
            continue
        if line.startswith("- "):
            body = line[2:].strip()
            tail = body.rsplit(_META_SEP, 1)[-1].strip()
            is_meta = (_META_SEP in body) and tail.startswith("来源：")
            if is_meta:
                meta = _parse_meta_line(body)
                if meta:
                    cur.update(meta)
                    continue
            if body.startswith("链接："):
                cur["url"] = body[len("链接："):].strip()
            elif body.startswith("作者："):
                raw_a = _unescape(body[len("作者："):].strip())
                raw_a = _AUTHORS_MORE_RE.sub("", raw_a)
                cur["authors"] = [a.strip() for a in raw_a.split(", ") if a.strip()]
            elif body.startswith("备注："):
                cur["note"] = _unescape(body[len("备注："):].strip())
    flush()
    header["count"] = sum(len(v) for v in groups.values())
    return groups, header


def merge_markdown_files(paths: list) -> tuple:
    """把多份留痕文件取并集。返回 (groups, headers)。"""
    merged: dict = {}
    headers = []
    for p in paths:
        g, h = parse_markdown_groups(p)
        headers.append(h)
        for key, recs in g.items():
            merged.setdefault(key, []).extend(recs)
    out = {}
    for key, recs in merged.items():
        out[key] = rank(dedupe(recs))
    return out, headers


def render_markdown(groups: dict, meta: dict) -> str:
    """groups: {topic_key: [record, ...]}；meta: 生成元信息。"""
    lines = []
    lines.append("# %s" % meta["title"])
    lines.append("")
    lines.append("> **本文件由 `tools/fetch_literature.py` 自动生成，请勿手改。**")
    lines.append("> 重新生成：`py -3.12 tools/fetch_literature.py %s`"
                 % meta.get("regen_cmd", "--all --out %s" % meta["out_hint"]))
    lines.append(">")
    lines.append("> 取证时间：%s ｜ 数据源：arXiv API + Semantic Scholar Graph API ｜ 出处等级：**T4**" % meta["generated_at"])
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 〇、怎么用这份文件")
    lines.append("")
    lines.append("**它是什么**：一份**可复现的检索留痕**。每条记录都带 arXiv ID / DOI / URL，"
                 "任何人点开就能核对。")
    lines.append("")
    lines.append("**它不是什么**：")
    lines.append("")
    lines.append("- ❌ **不是 T1 证据**。本项目 T1 = 官方明文（Apple HIG / 固件源码）。"
                 "一条 arXiv 摘要说明的是「论文声称了什么」，**不等于事实已被独立验证**。")
    lines.append("- ❌ 不是综述结论。真正的结论必须回源读原文后**自己写**，本文件只负责「有哪些东西可读」。")
    lines.append("- ❌ 不是完整检索。arXiv + S2 只覆盖预印本与部分正式出版物，"
                 "付费墙内的期刊论文会有缺口。")
    lines.append("")
    lines.append("**引用纪律**：本项目任何一条对外结论，若依据来自本文件，"
                 "必须回源读原文 → 在本仓库另写一份带 `file:行号` 或 `arXiv ID` 的取证记录 → 才可用于交付文档。")
    lines.append("")
    lines.append("---")
    lines.append("")

    total = sum(len(v) for v in groups.values())
    lines.append("## 一、总量")
    lines.append("")
    lines.append("- 主题数：%d" % len(groups))
    lines.append("- 去重后记录数：%d" % total)
    lines.append("")
    lines.append("| 主题 | 记录数 | 一句话说明 |")
    lines.append("|---|---|---|")
    for key, gmeta in TOPICS.items():
        if key not in groups:
            continue
        lines.append("| `%s` | %d | %s |" % (key, len(groups[key]), _escape(gmeta["title"])))
    lines.append("")

    srcs = meta.get("merge_sources")
    if srcs:
        lines.append("### 本文件由 %d 份留痕**取并集**而成" % len(srcs))
        lines.append("")
        lines.append("> arXiv 与 Semantic Scholar 的可用性是波动的（S2 常年 HTTP 429），"
                     "同一检索式在不同时间跑出来的结果**互不包含**。"
                     "只留最后一次跑的结果 = 主动丢弃已抓到的文献 ⇒ 留痕必须可跨次合并。")
        lines.append("")
        lines.append("| 来源留痕 | 它的取证时间 | 它自己的记录数 |")
        lines.append("|---|---|---|")
        for h in srcs:
            lines.append("| `%s` | %s | %d |" % (
                _escape(h.get("display_path") or h.get("path") or "?"),
                h.get("generated_at") or "?", h.get("count", 0)))
        lines.append("")
    lines.append("---")
    lines.append("")

    for key, gmeta in TOPICS.items():
        if key not in groups:
            continue
        recs = groups[key]
        lines.append("## 二、%s" % gmeta["title"])
        lines.append("")
        lines.append("**主题键**：`%s`" % key)
        lines.append("")
        lines.append("**为什么要查**：%s" % _escape(gmeta["why"]))
        lines.append("")
        lines.append("**检索式（可复现）**：")
        lines.append("")
        for q in gmeta["arxiv"]:
            lines.append("- arXiv：`%s`" % _escape(q))
        for q in gmeta["semantic"]:
            lines.append("- Semantic Scholar：`%s`" % _escape(q))
        lines.append("")
        if not recs:
            lines.append("> 本次检索**没有返回记录**。这本身就是一条事实（该检索式在该时点无命中），"
                         "不是「跳过」。")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        for i, rec in enumerate(recs, 1):
            lines.append("### %s.%d %s" % (key, i, _escape(rec["title"])))
            lines.append("")
            meta_bits = []
            if rec.get("arxiv_id") or (rec.get("source") == "arXiv" and rec.get("id")):
                aid = rec.get("arxiv_id") or rec.get("id")
                meta_bits.append("arXiv:`%s`" % aid)
            if rec.get("doi"):
                meta_bits.append("DOI:`%s`" % rec["doi"])
            if rec.get("citation_count") is not None:
                meta_bits.append("引用数：%d" % rec["citation_count"])
            if rec.get("published"):
                meta_bits.append("日期：%s" % rec["published"])
            if rec.get("venue"):
                meta_bits.append("出处：%s" % _escape(rec["venue"]))
            meta_bits.append("来源：%s" % rec["source"])
            lines.append("- " + " ｜ ".join(meta_bits))
            if rec.get("url"):
                lines.append("- 链接：%s" % rec["url"])
            authors = rec.get("authors") or []
            if authors:
                shown = ", ".join(authors[:8])
                if len(authors) > 8:
                    shown += " 等 %d 人" % len(authors)
                lines.append("- 作者：%s" % _escape(shown))
            if rec.get("note"):
                lines.append("- 备注：%s" % _escape(rec["note"]))
            lines.append("")
            if rec.get("abstract"):
                abstract = rec["abstract"]
                if len(abstract) > 700:
                    abstract = abstract[:700].rsplit(" ", 1)[0] + " …"
                lines.append("> 摘要（原文截断，完整内容请点链接）：")
                lines.append(">")
                for chunk in _wrap_quote(abstract, 96):
                    lines.append("> " + chunk)
                lines.append("")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 附、复现与校验")
    lines.append("")
    lines.append("```powershell")
    lines.append("# 列出全部主题")
    lines.append("py -3.12 tools/fetch_literature.py --list")
    lines.append("")
    lines.append("# 抓取全部主题并生成本文件")
    lines.append("py -3.12 tools/fetch_literature.py --all --out docs/research/68-陪伴机器人文献综述.md")
    lines.append("")
    lines.append("# 校验本文件里的 arXiv ID 是否仍可解析（引用还在不在）")
    lines.append("py -3.12 tools/fetch_literature.py --all --out xxx.md --verify-ids")
    lines.append("")
    lines.append("# 离线自检（不联网，CI 用这个）")
    lines.append("py -3.12 tools/fetch_literature.py --self-test")
    lines.append("```")
    lines.append("")
    lines.append("**已知缺口（诚实声明）**：")
    lines.append("")
    lines.append("- 只覆盖 arXiv + Semantic Scholar 两个源；ACM DL / IEEE / 期刊付费墙内的论文可能缺。")
    lines.append("- 检索式是**相关性排序的前 N 条**，不是穷举；`max_results` 可调。")
    lines.append("- Semantic Scholar 的引用数会随时间变化 ⇒ **重跑本文件内容会变**。"
                 "已生成的文件视为快照，日期以文件头「取证时间」为准。")
    lines.append("- arXiv API 要求请求间隔 ≥ 3 秒，全量抓取需要数分钟。")
    lines.append("")
    return "\n".join(lines) + "\n"


def _wrap_quote(text: str, width: int) -> list:
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------------------
# 校验：arXiv ID 是否仍可解析
# ---------------------------------------------------------------------------

def verify_arxiv_ids(ids: list) -> dict:
    """批量校验 arXiv ID 是否仍存在（一次请求查 ≤ 50 个）。

    返回 {'ok': [...], 'missing': [...]}。
    """
    ok, missing = [], []
    uniq = sorted({i for i in ids if i})
    for start in range(0, len(uniq), 50):
        batch = uniq[start:start + 50]
        params = {"id_list": ",".join(batch), "max_results": str(len(batch))}
        url = ARXIV_API + "?" + urllib.parse.urlencode(params)
        try:
            raw = _http_get(url, {"User-Agent": USER_AGENT})
            root = ET.fromstring(raw)
            found = set()
            for entry in root.findall(_ATOM + "entry"):
                aid = _arxiv_primary_id(entry)
                if aid:
                    found.add(aid)
            for aid in batch:
                (ok if aid in found else missing).append(aid)
        except FetchError as exc:
            missing.extend("%s (查询失败: %s)" % (aid, exc) for aid in batch)
        time.sleep(ARXIV_MIN_INTERVAL_S)
    return {"ok": ok, "missing": missing}


# ---------------------------------------------------------------------------
# 抓取主流程
# ---------------------------------------------------------------------------

def harvest(topic_keys: list, max_arxiv: int = 12, max_s2: int = 8,
            verbose: bool = True) -> dict:
    """按主题抓取全部记录并去重排序。

    单条 query 失败 → 记入 errors 并继续（不中断整轮）。
    """
    groups: dict = {}
    errors: list = []

    for key in topic_keys:
        meta = TOPICS.get(key)
        if not meta:
            errors.append(("unknown-topic", key, "主题不存在"))
            continue
        if verbose:
            print("[lit] 主题 %s ..." % key, flush=True)
        recs = []

        for q in meta["arxiv"]:
            try:
                recs.extend(fetch_arxiv(q, max_results=max_arxiv))
            except FetchError as exc:
                errors.append(("arXiv", key, "%s | %s" % (q, exc)))
            time.sleep(ARXIV_MIN_INTERVAL_S)

        for q in meta["semantic"]:
            try:
                recs.extend(fetch_semantic(q, limit=max_s2))
            except FetchError as exc:
                errors.append(("SemanticScholar", key, "%s | %s" % (q, exc)))
            # S2 限流紧：两条检索式之间多歇一会儿，别把后面的也拖垮
            time.sleep(RATE_LIMIT_BACKOFF_S)

        groups[key] = rank(dedupe(recs))
        if verbose:
            print("[lit]   -> %d 条" % len(groups[key]), flush=True)
            if not groups[key]:
                # ⚠️ 静默 0 条是**危险失败模式**：分不清「真的没文献」还是「检索式被 API 吞了」。
                #    实测：arXiv 的 `all:"多词短语" AND …` 会静默返回 0（见 arxiv_query_variants）。
                print("[lit]   ⚠️ 警告：主题 %s 命中 0 条 —— 请核对检索式是否被 arXiv 静默吞掉" % key,
                      flush=True)

    return {"groups": groups, "errors": errors}


# ---------------------------------------------------------------------------
# 自检（离线）
# ---------------------------------------------------------------------------

FIXTURE_ARXIV = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2503.16449v2</id>
    <title>Sample: Re-Engagement in Human-Robot Interactions</title>
    <summary>Perceived interestingness and naturalness predict re-engagement.</summary>
    <published>2025-02-18T12:53:41Z</published>
    <author><name>Test Author</name></author>
    <author><name>Second Author</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2306.02694v2</id>
    <title>Social Robots As Companions | with a pipe</title>
    <summary>Loneliness and anthropomorphism.</summary>
    <published>2023-06-05T08:36:30Z</published>
    <author><name>Solo Author</name></author>
  </entry>
</feed>
"""

FIXTURE_S2 = json.dumps({
    "data": [
        {
            "paperId": "s2-1",
            "title": "Sample: Re-Engagement in Human-Robot Interactions",
            "abstract": "Perceived interestingness and naturalness predict re-engagement.",
            "year": 2025,
            "venue": "CHI",
            "citationCount": 42,
            "externalIds": {"ArXiv": "2503.16449", "DOI": "10.1000/demo"},
            "url": "https://www.semanticscholar.org/paper/s2-1",
            "authors": [{"name": "Test Author"}, {"name": "Second Author"}],
        },
        {
            "paperId": "s2-2",
            "title": "A totally different paper about robots",
            "abstract": "Something else entirely.",
            "year": 2024,
            "venue": "HRI",
            "citationCount": 7,
            "externalIds": {},
            "url": "https://www.semanticscholar.org/paper/s2-2",
            "authors": [{"name": "Third Author"}],
        },
    ]
})


def _parse_arxiv_fixture(xml_text: str) -> list:
    root = ET.fromstring(xml_text)
    out = []
    for entry in root.findall(_ATOM + "entry"):
        aid = _arxiv_primary_id(entry)
        out.append({
            "source": "arXiv",
            "id": aid,
            "arxiv_id": aid,
            "doi": None,
            "title": " ".join((entry.findtext(_ATOM + "title") or "").split()),
            "authors": _arxiv_authors(entry),
            "published": _arxiv_published(entry),
            "venue": "arXiv preprint",
            "url": "https://arxiv.org/abs/%s" % aid,
            "abstract": _arxiv_summary(entry),
            "note": "",
            "citation_count": None,
            "query": "fixture",
        })
    return out


def _parse_s2_fixture(json_text: str) -> list:
    data = json.loads(json_text)
    out = []
    for rec in data.get("data") or []:
        ext = rec.get("externalIds") or {}
        out.append({
            "source": "Semantic Scholar",
            "id": rec.get("paperId") or "",
            "arxiv_id": ext.get("ArXiv") or "",
            "doi": ext.get("DOI") or "",
            "title": rec.get("title") or "",
            "authors": [a.get("name", "") for a in (rec.get("authors") or [])],
            "published": str(rec.get("year") or ""),
            "venue": rec.get("venue") or "",
            "url": rec.get("url") or "",
            "abstract": rec.get("abstract") or "",
            "note": "",
            "citation_count": rec.get("citationCount"),
            "query": "fixture",
        })
    return out


def self_test() -> int:
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 1) arXiv 解析
    ax = _parse_arxiv_fixture(FIXTURE_ARXIV)
    ok("arxiv 解析条数=2", len(ax) == 2, "got %d" % len(ax))
    ok("arxiv 去版本号", ax and ax[0]["id"] == "2503.16449", ax[0]["id"] if ax else "")
    ok("arxiv 多作者", ax and len(ax[0]["authors"]) == 2)
    ok("arxiv 日期截断到日", ax and ax[0]["published"] == "2025-02-18", ax[0]["published"] if ax else "")
    ok("arxiv 摘要压空白", ax and ax[1]["abstract"] == "Loneliness and anthropomorphism.")

    # 2) S2 解析
    s2 = _parse_s2_fixture(FIXTURE_S2)
    ok("s2 解析条数=2", len(s2) == 2, "got %d" % len(s2))
    ok("s2 引用数解析", s2 and s2[0]["citation_count"] == 42)
    ok("s2 arXiv ID 提取", s2 and s2[0]["arxiv_id"] == "2503.16449")

    # 3) 去重：同一篇（arXiv + S2）应合成 1 条
    merged = dedupe(ax + s2)
    ok("跨源去重 => 3 条", len(merged) == 3, "got %d" % len(merged))
    hit = [r for r in merged if "Re-Engagement" in r["title"]]
    ok("去重命中同篇", len(hit) == 1, "got %d" % len(hit))
    if hit:
        r = hit[0]
        ok("去重后保留引用数", r["citation_count"] == 42, str(r["citation_count"]))
        ok("去重后保留 DOI", r["doi"] == "10.1000/demo", str(r["doi"]))
        ok("去重后 venue 取更具体者(CHI > arXiv preprint)", r["venue"] == "CHI", str(r["venue"]))

    # 3b) venue 择优与「先到先得」无关：两种输入顺序结果必须一致
    rev = dedupe(s2 + ax)
    rev_hit = [r for r in rev if "Re-Engagement" in r["title"]]
    ok("去重顺序无关（venue 仍为 CHI）",
       rev_hit and rev_hit[0]["venue"] == "CHI",
       rev_hit[0]["venue"] if rev_hit else "")
    ok("venue 特异性评分：空 < preprint < 正式",
       _venue_specificity("") < _venue_specificity("arXiv preprint") < _venue_specificity("CHI"))

    # 4) 排序
    ranked = rank(merged)
    ok("排序：引用数高的在前", ranked and ranked[0]["citation_count"] == 42,
       str(ranked[0].get("citation_count")) if ranked else "")

    # 5) 转义
    ok("竖线被转义", "\\|" in _escape("a|b"), _escape("a|b"))
    ok("反斜杠被转义", _escape("a\\b") == "a\\\\b", _escape("a\\b"))
    ok("换行被压成空格", "\n" not in _escape("a\nb"))

    # 6) 渲染
    md = render_markdown({"llm-companion": merged},
                          {"title": "T", "out_hint": "x.md",
                           "generated_at": "2026-01-01 00:00:00"})
    ok("渲染非空", len(md) > 500, "len=%d" % len(md))
    ok("渲染含出处等级 T4", "T4" in md)
    ok("渲染含检索式", "search_query" not in md and "arXiv preprint" in md)
    ok("渲染含 arXiv ID", "2503.16449" in md)
    ok("渲染含免责声明", "不是 T1" in md)
    ok("渲染表格列数一致",
       all(line.count("|") >= 3 for line in md.splitlines()
           if line.startswith("| `") and line.endswith("|")))

    # 7) 主题表完整性
    ok("主题登记表非空", len(TOPICS) >= 6, "got %d" % len(TOPICS))
    for k, v in TOPICS.items():
        ok("主题 %s 有 title/why/arxiv/semantic" % k,
           all(x in v for x in ("title", "why", "arxiv", "semantic")))

    # 8) arXiv 引号短语坑的兜底变体（2026-10-25 实测 bug）
    vs = arxiv_query_variants('all:"social robot" AND all:"prosocial"')
    ok("变体原式排第一", vs and vs[0] == 'all:"social robot" AND all:"prosocial"')
    ok("变体含去引号拆分式",
       any(v != vs[0] and 'all:"social"' in v and 'all:"robot"' in v for v in vs),
       str(vs))
    ok("单词短语不产生多余变体",
       arxiv_query_variants('all:"robot"') == ['all:"robot"'],
       str(arxiv_query_variants('all:"robot"')))
    ok("无引号查询只有原式",
       arxiv_query_variants('all:robot AND all:prosocial') == ['all:robot AND all:prosocial'])

    # 9) 反向解析（留痕 → 结构）+ 跨次并集（2026-10-25 实测 S2 429 导致结果集互不包含）
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="lit-selftest-")
    try:
        pa = os.path.join(tmpdir, "a.md")
        _write_text(pa, render_markdown(
            {"llm-companion": merged},
            {"title": "T", "out_hint": "a.md", "generated_at": "2026-01-01 00:00:00"}))
        back, hdr = parse_markdown_groups(pa)
        ok("反向解析：主题数=1", list(back.keys()) == ["llm-companion"], str(list(back.keys())))
        b0 = back.get("llm-companion", [])
        ok("反向解析：条数往返一致", len(b0) == len(merged),
           "%d vs %d" % (len(b0), len(merged)))
        ok("反向解析：标题往返不变",
           bool(b0) and b0[0]["title"] == merged[0]["title"],
           b0[0]["title"] if b0 else "")
        ok("反向解析：arXiv ID 往返不变",
           bool(b0) and b0[0].get("arxiv_id") == merged[0].get("arxiv_id"),
           str(b0[0].get("arxiv_id")) if b0 else "")
        ok("反向解析：引用数往返不变",
           bool(b0) and b0[0].get("citation_count") == merged[0].get("citation_count"),
           str(b0[0].get("citation_count")) if b0 else "")
        ok("反向解析：摘要往返不变",
           bool(b0) and (b0[0].get("abstract") or "") == (merged[0].get("abstract") or ""))
        ok("反向解析：出处/venue 往返不变",
           bool(b0) and b0[0].get("venue") == merged[0].get("venue"),
           str(b0[0].get("venue")) if b0 else "")
        ok("反向解析：取证时间被读出",
           hdr.get("generated_at", "").startswith("2026-01-01"),
           hdr.get("generated_at", ""))

        # 第二份：同一条（字段更少）+ 一条全新的（标题里带竖线）
        dup = dict(merged[0])
        dup["citation_count"] = None
        dup["abstract"] = ""
        dup["note"] = ""
        extra = dict(merged[0])
        extra["arxiv_id"] = "9999.99999"
        extra["id"] = "9999.99999"
        extra["title"] = "A brand new paper | with pipe"
        extra["doi"] = ""
        pb = os.path.join(tmpdir, "b.md")
        _write_text(pb, render_markdown(
            {"llm-companion": [dup, extra]},
            {"title": "T", "out_hint": "b.md", "generated_at": "2026-02-02 00:00:00"}))
        mg, hs = merge_markdown_files([pa, pb])
        ok("合并：主题数=1", list(mg.keys()) == ["llm-companion"], str(list(mg.keys())))
        ok("合并：跨文件同 arXiv ID 去重 + 新增 1 条",
           len(mg.get("llm-companion", [])) == len(merged) + 1,
           "%d vs %d" % (len(mg.get("llm-companion", [])), len(merged) + 1))
        ok("合并：跨文件字段择优（引用数从缺的那份补回）",
           any(r.get("citation_count") == 42 for r in mg.get("llm-companion", [])))
        ok("合并：标题里的竖线往返不变",
           any(r.get("title") == "A brand new paper | with pipe" for r in mg.get("llm-companion", [])))
        ok("合并：headers 记录了来源与取证时间",
           len(hs) == 2 and hs[1]["generated_at"].startswith("2026-02-02"),
           str([h.get("generated_at") for h in hs]))

        # 合并产出的文件必须再能解析回来（幂等）
        pc = os.path.join(tmpdir, "c.md")
        _write_text(pc, render_markdown(
            mg, {"title": "T", "out_hint": "c.md",
                 "generated_at": "2026-03-03 00:00:00", "merge_sources": hs}))
        back2, _ = parse_markdown_groups(pc)
        ok("合并产物可再解析（幂等）",
           len(back2.get("llm-companion", [])) == len(mg.get("llm-companion", [])),
           "%d vs %d" % (len(back2.get("llm-companion", [])), len(mg.get("llm-companion", []))))
        md2 = render_markdown(
            mg, {"title": "T", "out_hint": "c.md",
                 "generated_at": "2026-03-03 00:00:00", "merge_sources": hs})
        ok("合并产物渲染出「取并集」说明", "取并集" in md2)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    passed = sum(1 for _, c, _ in checks if bool(c))
    failed = [c for c in checks if not c[1]]
    for name, cond, detail in checks:
        print("  %s %s%s" % ("PASS" if cond else "FAIL", name,
                             ("  (%s)" % detail) if detail and not cond else ""))
    print("\nSELF-TEST: %d/%d PASS" % (passed, len(checks)))
    if failed:
        print("FAILED: %s" % ", ".join(f[0] for f in failed))
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _write_text(path: str, text: str) -> None:
    """LF + UTF-8 无 BOM。用 io.open(newline="") 避免 Windows 把 \\n 翻成 \\r\\n。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _display_path(p: str) -> str:
    """把来源文件的绝对路径显示成**仓库内相对路径**；不在仓内的只留文件名。

    绝对路径不该进仓库文档 —— 它把文档绑死在某台机器上。
    """
    try:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ap_ = os.path.abspath(p)
        if ap_.lower().startswith(repo.lower() + os.sep):
            return os.path.relpath(ap_, repo).replace("\\", "/")
    except Exception:  # pragma: no cover
        pass
    return os.path.basename(p)


def _check_merge(groups: dict, committed_path: str) -> int:
    """比对「重算并集」与「已落盘的合并文件」是否漂移（不写盘）。

    判据用**规范化标题集合**而不是逐字节：
      * 落盘文件的头部带「取证时间」，重算必然不同 ⇒ 不能整体比；
      * 但**条目集合**必须一致 —— 少一条 = 有人删了证据，多一条 = 并集没重算。
    """
    if not committed_path or not os.path.isfile(committed_path):
        print("[lit] 漂移检查失败：已落盘的合并文件不存在：%s" % committed_path)
        return 1
    committed, _ = parse_markdown_groups(committed_path)
    drift = []
    for key in sorted(set(groups) | set(committed)):
        new_t = {_norm_title(r.get("title", "")) for r in groups.get(key, [])}
        old_t = {_norm_title(r.get("title", "")) for r in committed.get(key, [])}
        missing = new_t - old_t
        extra = old_t - new_t
        if missing or extra:
            drift.append((key, len(missing), len(extra)))
    if not drift:
        print("[lit] 漂移检查通过：并集与已落盘文件一致（%d 个主题）" % len(groups))
        return 0
    print("[lit] 漂移检查 FAIL：%d 个主题与已落盘文件不一致" % len(drift))
    for key, miss, extra in drift:
        print("       %-28s 少 %d 条 / 多 %d 条" % (key, miss, extra))
    print("       ⇒ 重新生成：py -3.12 tools/fetch_literature.py --merge <来源...> --out %s"
          % committed_path)
    return 1


def _run_merge(args) -> int:
    """跨次并集合并（不联网）。"""
    groups, headers = merge_markdown_files(args.merge)
    if not groups:
        print("[lit] 合并结果为空 —— 输入文件里没解析出任何条目")
        return 1
    for h in headers:
        h["display_path"] = _display_path(h.get("path", ""))
    total = sum(len(v) for v in groups.values())
    print("[lit] 合并 %d 份留痕 => 主题 %d 个，去重后 %d 条" % (
        len(args.merge), len(groups), total))
    for h in headers:
        print("       %s（取证时间 %s，本文件 %d 条，坏条目 %d）" % (
            h.get("display_path"), h.get("generated_at") or "?", h.get("count", 0),
            h.get("skipped", 0)))

    if args.check:
        return _check_merge(groups, args.out)

    if args.out:
        meta = {
            "title": "陪伴机器人 · 文献检索留痕",
            "out_hint": args.out,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "merge_sources": headers,
            "regen_cmd": "--merge %s --out %s" % (
                " ".join('"%s"' % p for p in args.merge), args.out),
        }
        _write_text(args.out, render_markdown(groups, meta))
        print("[lit] 已写出 %s" % args.out)
    else:
        print("[lit]（未指定 --out）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="陪伴机器人项目文献抓取器（arXiv + Semantic Scholar，可复现）")
    ap.add_argument("--list", action="store_true", help="列出全部主题与检索式")
    ap.add_argument("--all", action="store_true", help="抓取全部主题")
    ap.add_argument("--topics", default="", help="逗号分隔的主题键")
    ap.add_argument("--out", default="", help="输出 markdown 路径")
    ap.add_argument("--max-arxiv", type=int, default=12, help="每条 arXiv 检索式取几条")
    ap.add_argument("--max-s2", type=int, default=8, help="每条 S2 检索式取几条")
    ap.add_argument("--verify-ids", action="store_true", help="校验产出的 arXiv ID 是否仍可解析")
    ap.add_argument("--merge", nargs="+", default=[],
                    help="把已生成的留痕文件取并集后重新渲染（跨次累积用，不联网）")
    ap.add_argument("--check", action="store_true",
                    help="配合 --merge：只比对不写盘（并集与已落盘文件是否漂移）")
    ap.add_argument("--self-test", action="store_true", help="离线自检（不联网）")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args(argv)

    if args.version:
        print("fetch_literature.py %s" % __version__)
        return 0

    if args.self_test:
        return self_test()

    if args.list:
        print("主题登记表（%d 个）\n" % len(TOPICS))
        for key, meta in TOPICS.items():
            print("%-22s %s" % (key, meta["title"]))
            print("%-22s 理由：%s" % ("", meta["why"][:80]))
            for q in meta["arxiv"]:
                print("%-22s   arXiv: %s" % ("", q))
            for q in meta["semantic"]:
                print("%-22s   S2   : %s" % ("", q))
            print()
        return 0

    if args.merge:
        return _run_merge(args)

    if args.all:
        keys = list(TOPICS.keys())
    elif args.topics:
        keys = [k.strip() for k in args.topics.split(",") if k.strip()]
    else:
        ap.error("需要 --all 或 --topics 或 --list 或 --self-test")

    unknown = [k for k in keys if k not in TOPICS]
    if unknown:
        ap.error("未知主题：%s（用 --list 看清单）" % ", ".join(unknown))

    result = harvest(keys, max_arxiv=args.max_arxiv, max_s2=args.max_s2)

    if result["errors"]:
        print("\n[lit] 有 %d 条检索失败（已降级，不影响其余）：" % len(result["errors"]))
        for src, key, msg in result["errors"]:
            print("       %s / %s: %s" % (src, key, msg))

    groups = result["groups"]
    total = sum(len(v) for v in groups.values())
    print("\n[lit] 合计去重后 %d 条" % total)

    if args.verify_ids:
        ids = []
        for recs in groups.values():
            for r in recs:
                aid = r.get("arxiv_id") or (r.get("id") if r.get("source") == "arXiv" else "")
                if aid:
                    ids.append(aid)
        print("[lit] 校验 %d 个 arXiv ID ..." % len(set(ids)))
        res = verify_arxiv_ids(ids)
        print("[lit] 可解析 %d / 失效 %d" % (len(res["ok"]), len(res["missing"])))
        for m in res["missing"]:
            print("       MISSING %s" % m)

    if args.out:
        meta = {
            "title": "陪伴机器人 · 文献检索留痕",
            "out_hint": args.out,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _write_text(args.out, render_markdown(groups, meta))
        print("[lit] 已写出 %s" % args.out)
    else:
        print("[lit]（未指定 --out，只做检索不落盘）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
