# -*- coding: utf-8 -*-
"""意图题集探针：拿几段写死的中文对话跑一遍 analyze_intent，人工核对是否符合直觉。

    python tools/probe_intent.py                 # 跑内置样本，打印每题答案/置信度/耗时
    python tools/probe_intent.py --dump out.jsonl  # 另存 {state, questions, answers} 供将来微调

需要 WSL 里的 laya-serve 在线（见 deploy/laya-serve/run.sh）。默认连 127.0.0.1:8765。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import settings  # noqa: E402
from core import laya_client  # noqa: E402
from core.engine import analyze_intent  # noqa: E402
from core.intent_questions import INTENT_QUESTIONS, build_state  # noqa: E402

# (说明, 关系, [(from, text)])：覆盖四类意图与不同情绪，方便对照看题集偏没偏。
SAMPLES = [
    ("寒暄", "friends", [("her", "在吗"), ("me", "在的"), ("her", "没啥事，就随便问问")]),
    ("请求", "friends", [("her", "你明天上班顺路帮我带杯咖啡呗"), ("me", "行"), ("her", "少冰，谢谢")]),
    ("提问", "colleagues", [("her", "这个报表的公式怎么又错了？"), ("me", "我看看"), ("her", "急，下午要交")]),
    ("抱怨", "romantic partners", [("me", "今天加班可能回不去"), ("her", "你又加班"),
                                  ("her", "算了，你忙你的吧")]),
    ("关心", "romantic partners", [("her", "降温了记得多穿点，别又感冒")]),
    ("收尾", "friends", [("me", "那先这样"), ("her", "好，晚安")]),
    ("阴阳怪气", "friends", [("me", "周末我想在家躺着"), ("her", "行啊，你开心就好"),
                            ("her", "反正你一向很有想法")]),
    ("群里提问", "friends", [("her", "有人知道会议室怎么预约吗", "小李"),
                           ("me", "OA 里点会议"), ("her", "好的谢谢", "小李")]),
]


def _one(msgs, relationship, cfg, keep):
    state = build_state(msgs, relationship, keep=keep)
    t0 = time.perf_counter()
    result = analyze_intent(msgs, relationship, config=cfg, keep=keep)
    elapsed = (time.perf_counter() - t0) * 1000
    return state, result, elapsed


def _line(result):
    intent = result["intent"]
    flag = " 低置信" if intent.get("low_confidence") else ""
    return (f"意图 {intent.get('label', '—')}（{intent.get('choice')} "
            f"{intent.get('confidence', 0):.2f}{flag}）"
            f"｜情绪 {result['emotion'].get('label', '—')}"
            f"｜紧急度 {result['urgency'].get('label') or '—'}"
            f"｜等回复 {_p(result['expects_reply'])}"
            f"｜潜台词 {_p(result['subtext'])}")


def _p(node):
    p = node.get("noul")
    if p is None:
        return "—"
    return f"{p:.2f}{'?' if node.get('uncertain') else ''}"


def main():
    ap = argparse.ArgumentParser(description="中文意图题集探针")
    ap.add_argument("--host", default=None, help=f"Laya 服务地址（默认 {laya_client.DEFAULT_HOST}）")
    ap.add_argument("--port", type=int, default=None, help=f"默认 {laya_client.DEFAULT_PORT}")
    ap.add_argument("--model", default=None, help=f"默认 {laya_client.DEFAULT_MODEL}")
    ap.add_argument("--keep", type=int, default=None, help="喂模型的消息条数，默认取设置值")
    ap.add_argument("--dump", metavar="PATH", help="把每题的 {state, questions, answers} 写进 jsonl")
    args = ap.parse_args()

    cfg = settings.config()
    if args.host:
        cfg["laya_host"] = args.host
    if args.port:
        cfg["laya_port"] = args.port
    if args.model:
        cfg["laya_model"] = args.model
    keep = args.keep or settings.context()

    info = laya_client.health(cfg["laya_host"], int(cfg["laya_port"]))
    if not info:
        print(f"连不上 Laya 服务 {cfg['laya_host']}:{cfg['laya_port']}，先起 laya-serve。", file=sys.stderr)
        return 2
    print(f"Laya {info}\n")

    dump = open(args.dump, "w", encoding="utf-8") if args.dump else None
    try:
        for name, relationship, msgs in SAMPLES:
            try:
                state, result, elapsed = _one(msgs, relationship, cfg, keep)
            except laya_client.LayaError as e:
                print(f"[{name}] 失败：{e}", file=sys.stderr)
                continue
            print(f"[{name}] {_line(result)}")
            for who, text, *_ in [(m[0], m[1]) for m in msgs]:
                print(f"    {who}: {text}")
            print(f"    {elapsed:.0f} ms")
            if dump:
                dump.write(json.dumps({"sample": name, "state": state,
                                       "questions": INTENT_QUESTIONS,
                                       "answers": result["raw"]}, ensure_ascii=False) + "\n")
    finally:
        if dump:
            dump.close()
            print(f"\n已写入 {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())