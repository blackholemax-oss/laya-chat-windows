# -*- coding: utf-8 -*-
"""题集契约 + build_state 的单元测试，不依赖 laya-serve。"""
from __future__ import annotations

import pytest

from core.intent_questions import (CHOICE_LABELS, INTENT_QUESTIONS, QUESTION_VERSION,
                                   URGENCY_LABELS, build_state)

EXPECTED_INTENTS = {"chat", "need", "upset", "warm"}
EXPECTED_EMOTIONS = {"positive", "neutral", "upset", "angry", "hurt"}


def test_question_version_pinned():
    assert QUESTION_VERSION == "intent-zh-v2"


def test_all_questions_declared():
    assert set(INTENT_QUESTIONS) == {"intent", "emotion", "urgency",
                                     "expects_reply", "subtext"}


def test_intent_is_four_way_emotion_is_five_way():
    assert set(INTENT_QUESTIONS["intent"]["criteria"]) == EXPECTED_INTENTS
    assert set(INTENT_QUESTIONS["emotion"]["criteria"]) == EXPECTED_EMOTIONS


@pytest.mark.parametrize("qid", ["intent", "emotion"])
def test_choice_labels_cover_every_criterion(qid):
    q = INTENT_QUESTIONS[qid]
    assert q["type"] == "choice"
    assert set(q["criteria"]) == set(CHOICE_LABELS[qid])
    assert q.get("instructions")


def test_urgency_score_bands_match_labels():
    q = INTENT_QUESTIONS["urgency"]
    assert q["type"] == "score"
    assert len(q["criteria"]) == len(URGENCY_LABELS) == 3


@pytest.mark.parametrize("qid", ["expects_reply", "subtext"])
def test_noul_questions_need_true_false_criteria(qid):
    """noul 缺 criteria 会让模型退化成常数（见题集注释），这里当回归护栏。"""
    q = INTENT_QUESTIONS[qid]
    assert q["type"] == "noul"
    assert set(q["criteria"]) == {"true", "false"}
    assert all(q["criteria"].values())


def test_build_state_keeps_only_recent():
    msgs = [("her", f"m{i}") for i in range(15)]
    state = build_state(msgs, keep=4)["chat"]
    assert [m["text"] for m in state["messages"]] == ["m11", "m12", "m13", "m14"]


def test_build_state_latest_from_and_group_flag():
    state = build_state([("me", "在吗"), ("her", "嗯", "小李")])["chat"]
    assert state["latest_from"] == "her"
    assert state["is_group"] is True
    assert state["messages"][1]["name"] == "小李"


def test_build_state_private_chat_is_not_group():
    state = build_state([("her", "在吗")])["chat"]
    assert state["is_group"] is False
    assert "name" not in state["messages"][0]


def test_build_state_accepts_dicts_and_stringifies_text():
    state = build_state([{"from": "her", "text": 123}])["chat"]
    assert state["messages"][0] == {"from": "her", "text": "123"}


def test_build_state_rejects_unknown_sender():
    with pytest.raises(ValueError):
        build_state([("system", "hi")])


def test_build_state_empty_defaults_latest_from_to_her():
    state = build_state([])["chat"]
    assert state["messages"] == []
    assert state["latest_from"] == "her"