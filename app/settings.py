# -*- coding: utf-8 -*-
"""设置持久化。Laya 的 API key 只进注册表（HKCU\\Environment），其余设置落 config.json。

key 读的时候先看进程环境，没有就直接读注册表——IDE 启动时把环境快照拿走了，只靠
os.environ 会「保存了下次打开还是没有」。其余字段每次现读 config.json，改设置不用重启。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys

from core.laya_client import DEFAULT_HOST, DEFAULT_MODEL, DEFAULT_PORT

# 打包后 __file__ 指向临时解包目录，config.json 得放在 exe 旁边才存得住
_ROOT = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
         else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CONFIG = os.path.join(_ROOT, "config.json")

_DEFAULT_RELATIONSHIP = "friends"
_DEFAULT_CONTEXT = 10
_LAYA_ENV = "LAYA_API_KEY"


def _read(name: str, default=None):
    """读 config.json 里的一个字段；每次都重新读文件，改设置不用重启进程。"""
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            value = json.load(f).get(name)
    except (OSError, ValueError):
        return default
    return default if value is None else value

def relationship() -> str:
    return str(_read("relationship") or _DEFAULT_RELATIONSHIP)

def context() -> int:
    """喂给模型的最近消息条数。3~30，缺失/脏数据一律退默认值。"""
    try:
        n = int(_read("context", _DEFAULT_CONTEXT))
    except (TypeError, ValueError):
        return _DEFAULT_CONTEXT
    return max(3, min(30, n))

def language() -> str:
    """界面语言；i18n 用它。默认中文。"""
    return str(_read("lang") or "zh").strip().lower()

def debug_view() -> bool:
    """调试视图：另开一个窗口实时画识别框。默认关。"""
    return bool(_read("debug_view", False))

def laya_host() -> str:
    return str(_read("laya_host") or DEFAULT_HOST).strip() or DEFAULT_HOST

def laya_port() -> int:
    try:
        port = int(_read("laya_port", DEFAULT_PORT))
    except (TypeError, ValueError):
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT

def laya_model() -> str:
    return str(_read("laya_model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _read_env(env_name: str) -> str:
    """进程环境优先；没有就读注册表并带进进程环境。"""
    v = os.environ.get(env_name, "").strip()
    if not v:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = str(winreg.QueryValueEx(k, env_name)[0]).strip()
        except Exception:  # 非 Windows / 没这个值
            v = ""
        if v:
            os.environ[env_name] = v
    return v

def _set_key(env_name: str, value: str) -> None:
    """只写进程环境 + HKCU\\Environment，不写任何文件。"""
    os.environ[env_name] = value
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, env_name, 0, winreg.REG_SZ, value)
    except Exception:
        pass  # 非 Windows 走不到，忽略


def _notify_env() -> None:
    """告诉别的进程环境变量变了。SendNotifyMessage 交出去就返回，不逐个窗口等回复。"""
    try:
        fn = ctypes.windll.user32.SendNotifyMessageW
        fn.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_wchar_p)
        fn.restype = ctypes.c_int
        fn(0xFFFF, 0x001A, 0, "Environment")  # HWND_BROADCAST, WM_SETTING_CHANGE
    except Exception:
        pass

def laya_key() -> str:
    """Laya 服务的 Bearer key；没设（服务也没设 key）就是空串。"""
    return _read_env(_LAYA_ENV)

def has_laya_key() -> bool:
    return bool(laya_key())


def config() -> dict:
    """engine.analyze_intent 需要的连接配置。"""
    return {"laya_host": laya_host(), "laya_port": laya_port(),
            "laya_model": laya_model(), "laya_api_key": laya_key()}


def save(host: str | None = None, port: int | None = None, model: str | None = None,
         key_text: str | None = None, relationship_text: str | None = None,
         context_n: int | None = None, debug_view_on: bool | None = None) -> None:
    """每个参数为空/None = 保留当前值。key 写进程环境 + HKCU\\Environment，不写文件。"""
    if key_text:
        _set_key(_LAYA_ENV, key_text.strip())
        _notify_env()
    n = context() if context_n is None else max(3, min(30, int(context_n)))
    keep = lambda new, name: _read(name) if new is None else str(new).strip()
    data = {
        "relationship": relationship_text or relationship(),
        "context": n,
        "laya_host": keep(host, "laya_host") or DEFAULT_HOST,
        "laya_port": port if port else laya_port(),
        "laya_model": keep(model, "laya_model") or DEFAULT_MODEL,
        "lang": _read("lang") or "zh",
        "debug_view": debug_view() if debug_view_on is None else bool(debug_view_on),
    }
    with open(_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)