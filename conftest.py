# -*- coding: utf-8 -*-
"""pytest 根配置：保证能 import core/app；给真实服务测试加开关。

默认只跑离线单元测试。要跑需要 laya-serve 的集成测试：

    pytest --run-live -m live -s
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="跑需要本机 laya-serve 的集成测试（默认跳过）")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip = pytest.mark.skip(reason="需要 --run-live，且 WSL 里 laya-serve 在线")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)