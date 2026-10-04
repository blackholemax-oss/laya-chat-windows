# -*- coding: utf-8 -*-
"""真实识别集成测试：跑中文样本，核对意图是否符合直觉。需要 laya-serve 在线。

    pytest --run-live -m live -s
"""
from __future__ import annotations

import pytest

from app import settings
from core import laya_client
from core.engine import analyze_intent
from core.intent_questions import CHOICE_LABELS

# (说明, 关系, 对话, 人类直觉期望)。期望是标注参考，不是硬性真理——模型零样本能力有限。
SAMPLES = [
    ("寒暄", "friends", [("her", "在吗"), ("me", "在的"), ("her", "没啥事，就随便问问")], "chat"),
    ("请求", "friends", [("her", "你明天上班顺路帮我带杯咖啡呗"), ("me", "行"), ("her", "少冰，谢谢")], "need"),
    ("提问", "colleagues", [("her", "这个报表的公式怎么又错了？"), ("me", "我看看"), ("her", "急，下午要交")], "need"),
    ("抱怨", "romantic partners", [("me", "今天加班可能回不去"), ("her", "你又加班"),
                                  ("her", "算了，你忙你的吧")], "upset"),
    ("关心", "romantic partners", [("her", "降温了记得多穿点，别又感冒")], "warm"),
    ("收尾", "friends", [("me", "那先这样"), ("her", "好，晚安")], "warm"),
    ("阴阳怪气", "friends", [("me", "周末我想在家躺着"), ("her", "行啊，你开心就好"),
                            ("her", "反正你一向很有想法")], "upset"),
    ("群里提问", "friends", [("her", "有人知道会议室怎么预约吗", "小李"), ("me", "OA 里点会议"),
                            ("her", "好的谢谢", "小李")], "need"),
]

# 命中率下限。4 类题集在本组样本上实测约 3~4/8；设 2 是防「整体崩成常数/服务异常」的护栏，
# 而不是准确率目标。真要提高准确率得靠标注数据微调，不是调这个数。
MIN_HITS = 2


@pytest.fixture(scope="module")
def live_config():
    cfg = settings.config()
    info = laya_client.health(cfg["laya_host"], int(cfg["laya_port"]))
    if not info:
        pytest.skip(f"laya-serve 不在线（{cfg['laya_host']}:{cfg['laya_port']}）")
    return cfg


@pytest.mark.live
@pytest.mark.parametrize("name,relationship,messages,expected", SAMPLES,
                         ids=[s[0] for s in SAMPLES])
def test_live_intent_structure(name, relationship, messages, expected, live_config):
    """每个样本的返回结构都必须完整、可解释。"""
    result = analyze_intent(messages, relationship, config=live_config, keep=10)
    intent = result["intent"]
    assert intent["choice"] in CHOICE_LABELS["intent"]
    assert intent["label"] == CHOICE_LABELS["intent"][intent["choice"]]
    assert 0.0 <= intent["confidence"] <= 1.0
    probs = intent["probabilities"]
    if probs:
        assert abs(sum(probs.values()) - 1.0) < 0.05
        assert intent["choice"] in probs
    assert result["emotion"]["choice"] in CHOICE_LABELS["emotion"]
    assert result["urgency"]["label"] in ("不急着回", "今天内回", "现在就该回", None)
    for node in (result["expects_reply"], result["subtext"]):
        assert node["noul"] is None or 0.0 <= node["noul"] <= 1.0


@pytest.mark.live
def test_live_intent_report(live_config, capsys):
    """打印全部样本的识别结果与人类直觉对照，并统计命中率。"""
    hits = 0
    rows = []
    for name, relationship, messages, expected in SAMPLES:
        result = analyze_intent(messages, relationship, config=live_config, keep=10)
        got = result["intent"]
        hit = got["choice"] == expected
        hits += hit
        rows.append(
            f"{'OK ' if hit else 'MISS'} [{name}] 期望 {expected} 实际 {got['choice']}"
            f"（{got['label']} {got['confidence']:.2f}"
            f"{' 低置信' if got['low_confidence'] else ''}）"
            f" 情绪 {result['emotion']['label']}"
            f" 紧急 {result['urgency']['label']}"
            f" 等回复 {result['expects_reply']['noul']}")
    with capsys.disabled():
        print("\n" + "\n".join(rows))
        print(f"命中 {hits}/{len(SAMPLES)}")
    assert hits >= MIN_HITS, f"命中率塌了：{hits}/{len(SAMPLES)}"