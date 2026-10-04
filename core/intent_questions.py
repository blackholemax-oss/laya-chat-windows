# -*- coding: utf-8 -*-
"""中文优先的意图识别题集（Laya typed decisions）。

Laya 的 base checkpoint 零样本能力有限（上游探针在 7 道难题上接近随机），所以这里
刻意保持「题少、选项少、中文短描述」：choice ≤6、score 3 档、两条 noul。
拿不准的兜底选项固定（intent 兜底 chat），再配合 engine 的置信度门控，避免硬猜。
"""
from __future__ import annotations

QUESTION_VERSION = "intent-zh-v2"   # 题集口径变了就改它，便于标注/微调对齐

INTENT_QUESTIONS: dict = {
    "intent": {
        "type": "choice",
        "instructions": (
            "对方最新这条消息主要想干什么？看整段对话和语气判断，不要只抠一个词。"
            "拿不准就选 chat。"
        ),
        # 6 类实测命中 2.5/8，4 类 3.5/8，且 upset/warm 的置信度更校准，故用 4 类。
        "criteria": {
            "chat": "闲聊、寒暄、分享日常、开玩笑，没有明确要求，也没有情绪。例：在吗、今天天气真好、哈哈",
            "need": "在提问、请你做事或邀约，等你回应或行动。例：这个怎么弄？帮我带杯咖啡、周六有空吗",
            "upset": "不满、抱怨、指责、讽刺、阴阳怪气、生气或受伤，情绪是重点。例：你怎么又这样、算了不用你了、行啊你开心就好",
            "warm": "关心、想念、亲密、道谢或告别。例：想你了、降温了多穿点、晚安、谢谢",
        },
    },
    "emotion": {
        "type": "choice",
        "instructions": "对方这条消息带着什么情绪？",
        "criteria": {
            "positive": "愉快、热情、开心",
            "neutral": "平静、没有明显情绪",
            "upset": "不满、烦躁、有点不高兴",
            "angry": "生气、发火",
            "hurt": "难过、受伤、委屈",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "这条消息需要多快回复？",
        "criteria": ["不急着回", "今天内回", "现在就该回"],
    },
    "expects_reply": {
        "type": "noul",
        "instructions": "对方这条是不是在等你回复或表态（提问、邀约、要求你答应等）？",
        # noul 的 criteria 不是可选题，而是两个选项本身的描述：没有它模型只看到
        # [MASK] true [MASK] false，答案会退化成常数。
        "criteria": {
            "true": "提问、邀约、要你答应或表态、抱怨后等你回应——都在等你回一句话",
            "false": "只是陈述、分享日常或平和地告别，不需要你回什么",
        },
    },
    "subtext": {
        "type": "noul",
        "instructions": "对方这条是不是话里有话（讽刺、试探、暗示、阴阳怪气），而不是字面意思？",
        "criteria": {
            "true": "话里有话：讽刺、试探、暗示、阴阳怪气，或把指责包装成一句问话",
            "false": "字面意思，直来直去，没有弦外之音",
        },
    },
}

# choice 类答案的中文说法，界面展示用。
CHOICE_LABELS: dict = {
    "intent": {
        "chat": "闲聊", "need": "需要回应", "upset": "情绪不满", "warm": "关心/亲密",
    },
    "emotion": {
        "positive": "愉快", "neutral": "平静", "upset": "不满",
        "angry": "生气", "hurt": "难过",
    },
}

# score 类的档位文字，顺序与 criteria 一致。
URGENCY_LABELS = ["不急着回", "今天内回", "现在就该回"]


def build_state(messages: list, relationship: str = "friends", keep: int = 10) -> dict:
    """messages: (from, text) / (from, text, name) / dict。from 只认 her/me。

    name = 群里的发言人；有 name 就当群聊。只取最近 keep 条。结构与参考项目同构，
    便于以后换回远程 Jev 时请求形状不变。
    """
    cleaned = []
    for item in messages:
        if isinstance(item, dict):
            who, text, name = item.get("from"), item.get("text"), item.get("name")
        else:
            who, text = item[0], item[1]
            name = item[2] if len(item) > 2 else None
        if who not in ("her", "me"):
            raise ValueError(f"message from must be 'her' or 'me', got {who!r}")
        message = {"from": who, "text": str(text)}
        if name:
            message["name"] = str(name)
        cleaned.append(message)
    cleaned = cleaned[-keep:]
    latest_from = cleaned[-1]["from"] if cleaned else "her"
    return {"chat": {
        "relationship": relationship,
        "messages": cleaned,
        "latest_from": latest_from,
        "is_group": any("name" in m for m in cleaned),
    }}