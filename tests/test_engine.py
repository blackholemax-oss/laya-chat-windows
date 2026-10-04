# -*- coding: utf-8 -*-
"""engine 的解析与置信度门控单元测试：把 HTTP 层换成 stub，逻辑可确定断言。"""
from __future__ import annotations

import pytest

from core import engine


# ---------- _choice ----------
def test_choice_prefers_answer_confidence_over_overall():
    ans = {"choice": "chat", "probabilities": {"chat": 0.7, "need": 0.3},
           "confidence": 0.9, "answer_confidence": 0.71}
    out = engine._choice(ans, "intent")
    assert out["choice"] == "chat"
    assert out["label"] == "闲聊"
    assert out["confidence"] == pytest.approx(0.71)


def test_choice_falls_back_to_overall_then_probability():
    assert engine._choice({"choice": "need", "confidence": 0.5,
                           "probabilities": {"need": 0.5}}, "intent")["confidence"] == 0.5
    assert engine._choice({"choice": "need", "probabilities": {"need": 0.42}},
                          "intent")["confidence"] == pytest.approx(0.42)


def test_choice_low_confidence_on_low_probability():
    out = engine._choice({"choice": "need", "answer_confidence": 0.39,
                          "probabilities": {"need": 0.39, "chat": 0.61}}, "intent")
    assert out["low_confidence"] is True


def test_choice_low_confidence_on_narrow_margin():
    # 选中项概率够高，但 top1/top2 只差 0.04 < MARGIN_MIN
    out = engine._choice({"choice": "chat", "answer_confidence": 0.52,
                          "probabilities": {"chat": 0.52, "need": 0.48}}, "intent")
    assert out["confidence"] >= engine.CONF_MIN
    assert out["low_confidence"] is True


def test_choice_confident_when_wide_margin():
    out = engine._choice({"choice": "chat", "answer_confidence": 0.71,
                          "probabilities": {"chat": 0.71, "upset": 0.23, "warm": 0.04}},
                         "intent")
    assert out["low_confidence"] is False


def test_choice_unknown_choice_keeps_raw_code():
    assert engine._choice({"choice": "mystery", "answer_confidence": 0.9},
                          "intent")["label"] == "mystery"


def test_choice_none_answer_shows_dash_and_is_low_confidence():
    for ans in (None, {}):
        out = engine._choice(ans, "intent")
        assert out["label"] == "—"
        assert out["low_confidence"] is True


# ---------- _score ----------
@pytest.mark.parametrize("score,expected", [
    (0, "不急着回"), (1, "今天内回"), (2, "现在就该回"),
    (-3, "不急着回"), (99, "现在就该回"),
])
def test_score_maps_and_clamps(score, expected):
    assert engine._score({"score": score})["label"] == expected


def test_score_bad_value_yields_no_label():
    assert engine._score({"score": "abc"})["label"] is None
    assert engine._score(None)["label"] is None


# ---------- _noul ----------
@pytest.mark.parametrize("p,uncertain", [
    (0.10, False), (0.40, True), (0.50, True), (0.60, True), (0.68, False),
])
def test_noul_band(p, uncertain):
    assert engine._noul({"noul": p})["uncertain"] is uncertain


def test_noul_non_numeric_is_unknown():
    for bad in (None, True, False, "x"):
        out = engine._noul({"noul": bad})
        assert out["noul"] is None and out["uncertain"] is False


# ---------- analyze_intent ----------
def _stub_ask(monkeypatch, response, capture=None):
    def fake(state, questions, host=None, port=None, key="", model=None, timeout=60.0):
        if capture is not None:
            capture.update(state=state, questions=questions, host=host, port=port,
                           key=key, model=model)
        return response
    monkeypatch.setattr(engine.laya_client, "ask", fake)


def test_analyze_intent_builds_full_result_and_passes_config(monkeypatch):
    cap = {}
    _stub_ask(monkeypatch, {
        "answers": {
            "intent": {"choice": "need", "answer_confidence": 0.66,
                       "probabilities": {"need": 0.66, "chat": 0.34}},
            "emotion": {"choice": "neutral", "answer_confidence": 0.8,
                        "probabilities": {"neutral": 0.8}},
            "urgency": {"score": 2},
            "expects_reply": {"noul": 0.72},
            "subtext": {"noul": 0.55},
        },
        "usage": {"input_tokens": 10},
        "routing": {"model": "multilingual"},
    }, cap)

    out = engine.analyze_intent(
        [("her", "帮我带杯咖啡")], "friends",
        config={"laya_host": "h", "laya_port": 1234, "laya_model": "multilingual",
                "laya_api_key": ""}, keep=5)

    assert out["intent"]["label"] == "需要回应"
    assert out["intent"]["low_confidence"] is False
    assert out["emotion"]["label"] == "平静"
    assert out["urgency"]["label"] == "现在就该回"
    assert out["expects_reply"]["uncertain"] is False
    assert out["subtext"]["uncertain"] is True
    assert out["usage"] == {"input_tokens": 10}
    assert out["routing"] == {"model": "multilingual"}
    # 连接配置原样透传给客户端
    assert (cap["host"], cap["port"], cap["model"], cap["key"]) == ("h", 1234, "multilingual", "")
    # state 已按 keep 裁剪
    assert cap["state"]["chat"]["messages"] == [{"from": "her", "text": "帮我带杯咖啡"}]


def test_analyze_intent_defaults_when_config_empty(monkeypatch):
    cap = {}
    _stub_ask(monkeypatch, {"answers": {}}, cap)
    engine.analyze_intent([("her", "在吗")], config=None)
    assert (cap["host"], cap["port"], cap["model"], cap["key"]) == (
        engine.laya_client.DEFAULT_HOST, engine.laya_client.DEFAULT_PORT,
        engine.laya_client.DEFAULT_MODEL, "")


def test_analyze_intent_survives_missing_answers(monkeypatch):
    _stub_ask(monkeypatch, {"answers": {
        "intent": {"choice": "chat", "answer_confidence": 0.9,
                   "probabilities": {"chat": 0.9}}}})
    out = engine.analyze_intent([("her", "在吗")])
    assert out["intent"]["label"] == "闲聊"
    assert out["urgency"]["label"] is None
    assert out["expects_reply"]["noul"] is None