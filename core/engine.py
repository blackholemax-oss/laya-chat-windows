# -*- coding: utf-8 -*-
"""意图识别内核：一次 Laya 前向 → 意图 / 情绪 / 紧急度 / 是否等回复 / 是否有潜台词。

只做判断，不做回复起草。Laya 零样本能力有限，所以对低置信结果不硬给结论：
intent 置信度低于 CONF_MIN、或 top1/top2 概率差低于 MARGIN_MIN → low_confidence；
noul 落在 NOUL_BAND 中间带 → uncertain。界面据此灰显「仅供参考」。
"""
from __future__ import annotations

from core import laya_client
from core.intent_questions import (CHOICE_LABELS, INTENT_QUESTIONS, URGENCY_LABELS,
                                   build_state)

CONF_MIN = 0.45            # intent 置信度下限
MARGIN_MIN = 0.12          # intent top1 - top2 概率差下限
NOUL_BAND = (0.40, 0.60)   # noul 落在这个区间算「不确定」


def _choice(ans, qid):
    ans = ans or {}
    choice = ans.get("choice")
    probs = ans.get("probabilities") or {}
    # laya-serve 的 confidence 是整体决策置信度，answer_confidence 才是选中项的概率；
    # 界面上要跟概率分布并排展示，用后者才对得上。
    conf = ans.get("answer_confidence")
    if conf is None:
        conf = ans.get("confidence")
    if conf is None:
        conf = probs.get(choice, 0.0)
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    top2 = sorted((float(v) for v in probs.values()), reverse=True)[:2]
    margin = (top2[0] - top2[1]) if len(top2) >= 2 else conf
    return {
        "choice": choice,
        "label": CHOICE_LABELS[qid].get(choice, choice or "—"),
        "confidence": conf,
        "probabilities": probs,
        "low_confidence": conf < CONF_MIN or margin < MARGIN_MIN,
    }


def _score(ans):
    ans = ans or {}
    score = ans.get("score")
    label = None
    try:
        i = int(round(float(score)))
        label = URGENCY_LABELS[max(0, min(len(URGENCY_LABELS) - 1, i))]
    except (TypeError, ValueError):
        pass
    return {"score": score, "max": ans.get("max"), "label": label}


def _noul(ans):
    ans = ans or {}
    p = ans.get("noul")
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        p = None
    else:
        p = float(p)
    return {"noul": p, "uncertain": p is not None and NOUL_BAND[0] <= p <= NOUL_BAND[1]}


def analyze_intent(messages: list, relationship: str = "friends", config: dict | None = None,
                   keep: int = 10) -> dict:
    """messages: [(from, text[, name])]，from ∈ her/me。返回结构化意图结果。"""
    cfg = config or {}
    state = build_state(messages, relationship, keep=keep)
    resp = laya_client.ask(
        state, INTENT_QUESTIONS,
        host=cfg.get("laya_host") or laya_client.DEFAULT_HOST,
        port=int(cfg.get("laya_port") or laya_client.DEFAULT_PORT),
        key=cfg.get("laya_api_key") or "",
        model=cfg.get("laya_model") or laya_client.DEFAULT_MODEL,
    )
    answers = resp.get("answers") or {}
    return {
        "intent": _choice(answers.get("intent"), "intent"),
        "emotion": _choice(answers.get("emotion"), "emotion"),
        "urgency": _score(answers.get("urgency")),
        "expects_reply": _noul(answers.get("expects_reply")),
        "subtext": _noul(answers.get("subtext")),
        "raw": answers,
        "usage": resp.get("usage"),
        "routing": resp.get("routing"),
    }