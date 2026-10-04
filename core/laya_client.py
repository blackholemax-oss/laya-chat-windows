# -*- coding: utf-8 -*-
"""本地 Laya 决策模型客户端。只依赖标准库，打 WSL 里常驻的 laya-serve。

接口形状跟远程 Jev 一致，方便以后换回去：
    请求 POST /v1/systemone  {"model", "state", "questions"}
    响应                    {"answers": {...}, "usage": {...}, "routing": {...}}

Laya 是 Apache-2.0 的非自回归 System 1 决策模型：一次前向返回 choice/score/noul
三类 typed decision，不生成自由文本。部署见 deploy/laya-serve/run.sh。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MODEL = "multilingual"   # 322M，含中文；英文场景可用 "english"

_TRUNC = 300


class LayaError(RuntimeError):
    """连不上 / 返回异常时抛出，消息里已经脱敏、可直接展示给用户。"""


def _safe(text) -> str:
    text = " ".join(str(text).split())
    return text[:_TRUNC] + ("…" if len(text) > _TRUNC else "")


def health(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 5.0):
    """GET /health；连不上返回 None（界面上「检测连接」按钮用它）。"""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def ask(state, questions, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, key: str = "",
        model: str = DEFAULT_MODEL, timeout: float = 60.0) -> dict:
    """一次前向。state 是 build_state() 的产物，questions 是题集 dict。"""
    body = json.dumps({"model": model, "state": state, "questions": questions},
                      ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"http://{host}:{port}/v1/systemone", data=body,
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = _safe(e.read().decode("utf-8", "replace"))
        raise LayaError(f"Laya 返回 {e.code}：{detail}") from None
    except urllib.error.URLError as e:
        raise LayaError(
            f"连不上本地 Laya 服务（{host}:{port}）：{_safe(e.reason)}。"
            "WSL 里的 laya-serve 起了吗？见 deploy/laya-serve/run.sh"
        ) from None
    except ValueError:
        raise LayaError("Laya 返回的不是合法 JSON") from None


if __name__ == "__main__":  # 自测：序列化 + 错误分支走 stub，不需要真的服务
    import io

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    seen = {}

    def _stub(req, timeout=None):
        seen["url"] = req.full_url
        seen["auth"] = req.headers.get("Authorization")
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(json.dumps({"answers": {"intent": {"choice": "chat"}}}).encode())

    real = urllib.request.urlopen
    urllib.request.urlopen = _stub
    try:
        out = ask({"chat": {}}, {"intent": {"type": "choice", "criteria": {"chat": "x"}}},
                  key="sk-test")
    finally:
        urllib.request.urlopen = real
    assert seen["url"].endswith("/v1/systemone") and seen["auth"] == "Bearer sk-test"
    assert seen["body"]["state"] == {"chat": {}} and seen["body"]["model"] == DEFAULT_MODEL
    assert out["answers"]["intent"]["choice"] == "chat"
    print("laya_client ok")