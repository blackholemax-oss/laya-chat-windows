# -*- coding: utf-8 -*-
"""端到端冒烟：一段写死的对话 → analyze_intent → 打印结构化结果。

只验证 Windows 程序配置层 → WSL laya-serve 这条链路（不含截图/OCR），用来确认
「地址/端口/key/模型」配得对、服务在跑、中文题集能拿到答案。

    python tools/demo.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import settings  # noqa: E402
from core import laya_client  # noqa: E402
from core.engine import analyze_intent  # noqa: E402

CONVERSATION = [
    ("me", "这周的项目进度发我一下"),
    ("her", "你怎么每次都催，昨天不是刚发过吗"),
    ("her", "算了，我再发一遍，你自己看吧"),
]


def main():
    cfg = settings.config()
    info = laya_client.health(cfg["laya_host"], int(cfg["laya_port"]))
    if not info:
        print(f"连不上 Laya 服务 {cfg['laya_host']}:{cfg['laya_port']}", file=sys.stderr)
        print("先在 WSL 里跑：bash ~/laya-serve/run.sh", file=sys.stderr)
        return 2
    print("Laya 服务：", info)
    print("对话：")
    for who, text in CONVERSATION:
        print(f"  {'对方' if who == 'her' else '我'}: {text}")
    try:
        result = analyze_intent(CONVERSATION, settings.relationship(), config=cfg,
                                keep=settings.context())
    except laya_client.LayaError as e:
        print("失败：", e, file=sys.stderr)
        return 1
    print("\n识别结果：")
    print(json.dumps({k: v for k, v in result.items() if k not in ("raw", "usage", "routing")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())