# -*- coding: utf-8 -*-
"""laya_client 的请求构造与错误分支单元测试：stub 掉 urllib，不联网。"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from core import laya_client


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch(monkeypatch, handler):
    monkeypatch.setattr(laya_client.urllib.request, "urlopen", handler)


def test_ask_sends_bearer_and_full_body(monkeypatch):
    seen = {}

    def handler(req, timeout=None):
        seen["url"] = req.full_url
        seen["auth"] = req.headers.get("Authorization")
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(b'{"answers": {}}')

    _patch(monkeypatch, handler)
    laya_client.ask({"chat": {}}, {"intent": {"type": "choice"}},
                    host="h", port=9, key="sk-1", model="multilingual")
    assert seen["url"] == "http://h:9/v1/systemone"
    assert seen["auth"] == "Bearer sk-1"
    assert seen["body"] == {"model": "multilingual", "state": {"chat": {}},
                            "questions": {"intent": {"type": "choice"}}}


def test_ask_omits_auth_header_without_key(monkeypatch):
    seen = {}

    def handler(req, timeout=None):
        seen["auth"] = req.headers.get("Authorization")
        return _Resp(b'{"answers": {}}')

    _patch(monkeypatch, handler)
    laya_client.ask({}, {}, key="")
    assert seen["auth"] is None


def test_health_returns_none_when_unreachable(monkeypatch):
    def boom(url, timeout=None):
        raise OSError("nope")

    _patch(monkeypatch, boom)
    assert laya_client.health() is None


def test_ask_http_error_becomes_laya_error(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b"bad key"))

    _patch(monkeypatch, handler)
    with pytest.raises(laya_client.LayaError) as ei:
        laya_client.ask({}, {}, key="wrong")
    assert "401" in str(ei.value)


def test_ask_connection_error_becomes_laya_error(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    _patch(monkeypatch, handler)
    with pytest.raises(laya_client.LayaError) as ei:
        laya_client.ask({}, {})
    assert "连不上" in str(ei.value)


def test_ask_bad_json_becomes_laya_error(monkeypatch):
    _patch(monkeypatch, lambda req, timeout=None: _Resp(b"not json"))
    with pytest.raises(laya_client.LayaError) as ei:
        laya_client.ask({}, {})
    assert "JSON" in str(ei.value)