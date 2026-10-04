# -*- coding: utf-8 -*-
"""置顶悬浮窗：显示当前会话、识别出的意图/情绪/紧急度/置信度，以及实时聊天记录与设置页。

只读自己电脑上自己有权查看的聊天窗口画面；识别结果仅供参考，低置信会灰显。
本程序不发送任何消息、不联网（除本地 WSL 的 Laya 服务）。截图只在内存里。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from app import settings
from core import laya_client

_LEVEL = {"info": "#3b6ea5", "warning": "#b7791f", "error": "#c53030", "ok": "#2f855a"}
_GREY = "#8a8a8a"


def ensure_app() -> QApplication:
    """QApplication 必须在任何 QWidget 之前建；单独跑 overlay 自测时也用得上。"""
    return QApplication.instance() or QApplication(sys.argv)


def _pct(p) -> str:
    return "—" if p is None else f"{p:.0%}"


def _yesno(node, positive: str, negative: str) -> str:
    p = node.get("noul")
    if p is None:
        return "—"
    if node.get("uncertain"):
        return "不确定"
    return positive if p >= 0.5 else negative


class Overlay(QWidget):
    def __init__(self, on_toggle_capture, on_toggle_debug=None, on_close=None):
        super().__init__()
        self._on_toggle_capture = on_toggle_capture
        self._on_toggle_debug = on_toggle_debug
        self._on_close = on_close
        self._chat = ""
        self._drag = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle("Laya 意图识别")
        self.resize(380, 540)
        self.setMinimumSize(320, 420)
        self.setStyleSheet(
            "QWidget{background:#20242b;color:#e6e6e6;}"
            "QFrame#card{background:#2a2f38;border-radius:8px;}"
            "QLabel#title{font-weight:600;}"
            "QLabel#intent{font-size:20px;font-weight:600;}"
            "QLineEdit,QSpinBox,QPlainTextEdit{background:#171a20;border:1px solid #3a4048;"
            "border-radius:6px;padding:4px;}"
            "QPushButton{background:#323841;border:1px solid #3a4048;border-radius:6px;padding:5px 10px;}"
            "QPushButton:hover{background:#3a414c;}"
        )
        self._build()

    # ---------- 界面 ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        title = QWidget()
        bar = QHBoxLayout(title)
        bar.setContentsMargins(2, 0, 2, 0)
        name = QLabel("Laya 意图识别")
        name.setObjectName("title")
        bar.addWidget(name)
        bar.addStretch(1)
        self.capture_box = QCheckBox("采集")
        self.capture_box.toggled.connect(lambda on: self._on_toggle_capture(bool(on)))
        bar.addWidget(self.capture_box)
        gear = QPushButton("设置")
        gear.clicked.connect(self.open_settings)
        bar.addWidget(gear)
        close_btn = QPushButton("✕")
        close_btn.setFixedWidth(30)
        close_btn.setToolTip("关闭程序")
        close_btn.clicked.connect(self._request_close)
        bar.addWidget(close_btn)
        root.addWidget(title)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.stack.addWidget(self._page_main())
        self.stack.addWidget(self._page_settings())

    def _page_main(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        self.chat_label = QLabel("当前会话：—")
        box.addWidget(self.chat_label)
        self.status_label = QLabel("等待对方的新消息…")
        self.status_label.setStyleSheet(f"color:{_LEVEL['info']};")
        box.addWidget(self.status_label)

        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(12, 10, 12, 10)
        c.setSpacing(4)
        self.intent_label = QLabel("意图：—")
        self.intent_label.setObjectName("intent")
        c.addWidget(self.intent_label)
        self.detail_label = QLabel("情绪 — ｜ 紧急度 —")
        c.addWidget(self.detail_label)
        self.noul_label = QLabel("等回复 — ｜ 潜台词 —")
        c.addWidget(self.noul_label)
        self.prob_label = QLabel("")
        self.prob_label.setWordWrap(True)
        c.addWidget(self.prob_label)
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet(f"color:{_GREY};")
        self.hint_label.setWordWrap(True)
        c.addWidget(self.hint_label)
        box.addWidget(card)

        self.last_label = QLabel("最后一条：—")
        self.last_label.setWordWrap(True)
        box.addWidget(self.last_label)

        self.log_btn = QPushButton("聊天记录")
        self.log_btn.setCheckable(True)
        self.log_btn.toggled.connect(self._toggle_log)
        box.addWidget(self.log_btn)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        self.log_view.setVisible(False)
        box.addWidget(self.log_view)
        box.addStretch(1)
        return page

    def _page_settings(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(6)

        box.addWidget(QLabel("Laya 服务（WSL 里常驻的 laya-serve）"))
        self.host_edit = self._row(box, "地址", settings.laya_host())
        self.port_edit = self._row(box, "端口", str(settings.laya_port()))
        self.model_edit = self._row(box, "模型", settings.laya_model())
        self.key_edit = self._row(box, "API Key", "", password=True)
        self.key_edit.setPlaceholderText("已配置时留空 = 保留")

        probe = QPushButton("检测连接")
        probe.clicked.connect(self._probe)
        box.addWidget(probe)

        box.addWidget(QLabel("识别设置"))
        self.relation_edit = self._row(box, "关系", settings.relationship())
        ctx = QHBoxLayout()
        ctx.addWidget(QLabel("参考上下文"))
        self.context_spin = QSpinBox()
        self.context_spin.setRange(3, 30)
        self.context_spin.setValue(settings.context())
        ctx.addWidget(self.context_spin)
        ctx.addStretch(1)
        box.addLayout(ctx)

        self.debug_box = QCheckBox("调试视图（实时画出识别框）")
        self.debug_box.setChecked(bool(settings.debug_view()))
        if self._on_toggle_debug is not None:
            self.debug_box.toggled.connect(lambda on: self._on_toggle_debug(bool(on)))
        box.addWidget(self.debug_box)

        save = QPushButton("保存")
        save.clicked.connect(self._save)
        box.addWidget(save)
        back = QPushButton("返回")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        box.addWidget(back)
        box.addStretch(1)
        return page

    def _row(self, box, label, value, password=False):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        edit = QLineEdit(str(value))
        if password:
            edit.setEchoMode(QLineEdit.Password)
        row.addWidget(edit, 1)
        box.addLayout(row)
        return edit

    # ---------- 交互 ----------
    def _toggle_log(self, on):
        self.log_view.setVisible(bool(on))

    def _probe(self):
        info = laya_client.health(self.host_edit.text().strip() or settings.laya_host(),
                                  int(self.port_edit.text() or settings.laya_port()))
        if info:
            self.set_status("连接正常：" + " ".join(f"{k}={v}" for k, v in list(info.items())[:3]), "ok")
        else:
            self.set_status("连不上 Laya 服务，检查 WSL 是否在跑 laya-serve", "error")

    def _save(self):
        try:
            port = int(self.port_edit.text())
        except ValueError:
            port = settings.laya_port()
        settings.save(host=self.host_edit.text(), port=port, model=self.model_edit.text(),
                      key_text=self.key_edit.text(), relationship_text=self.relation_edit.text(),
                      context_n=self.context_spin.value(), debug_view_on=self.debug_box.isChecked())
        self.key_edit.clear()
        self.set_status("设置已保存", "ok")
        self.stack.setCurrentIndex(0)

    def open_settings(self):
        self.stack.setCurrentIndex(1)

    def _request_close(self):
        """标题栏 ✕、Alt+F4 都走这里，统一交给 main 收尾（停子进程 + 退事件循环）。"""
        if self._on_close is not None:
            self._on_close()
        else:
            QApplication.quit()

    def closeEvent(self, event):
        self._request_close()
        event.accept()

    def after(self, ms, fn):
        QTimer.singleShot(ms, fn)

    # ---------- 供 main 调用 ----------
    def current_chat(self) -> str:
        return self._chat

    def set_chat(self, title: str):
        self._chat = title
        self.chat_label.setText(f"当前会话：{title or '—'}")

    def set_capture(self, on: bool, msg: str | None = None):
        self.capture_box.blockSignals(True)
        self.capture_box.setChecked(bool(on))
        self.capture_box.blockSignals(False)
        if msg:
            self.set_status(msg, "warning")

    def set_status(self, text: str, level: str = "info"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{_LEVEL.get(level, _LEVEL['info'])};")

    def set_busy(self, on: bool):
        if on:
            self.set_status("识别中…", "info")

    def invalidate_replies(self):
        self.intent_label.setText("意图：—")
        self.intent_label.setStyleSheet("")
        self.detail_label.setText("情绪 — ｜ 紧急度 —")
        self.noul_label.setText("等回复 — ｜ 潜台词 —")
        self.prob_label.setText("")
        self.hint_label.setText("")

    def show_result(self, result: dict):
        intent = result["intent"]
        low = intent.get("low_confidence")
        self.intent_label.setText(f"意图：{intent.get('label', '—')}")
        self.intent_label.setStyleSheet(f"color:{_GREY};" if low else "color:#7dd3a0;")
        self.detail_label.setText(
            f"情绪 {result['emotion'].get('label', '—')} ｜ 紧急度 {result['urgency'].get('label') or '—'}")
        self.noul_label.setText(
            f"等回复 {_yesno(result['expects_reply'], '是', '否')} ｜ "
            f"潜台词 {_yesno(result['subtext'], '是', '否')}")
        probs = intent.get("probabilities") or {}
        top = sorted(probs.items(), key=lambda kv: -kv[1])[:3]
        self.prob_label.setText("　".join(f"{k}={v:.2f}" for k, v in top))
        self.hint_label.setText(f"意图置信度 {_pct(intent.get('confidence'))}"
                                + ("，拿不准，仅供参考" if low else ""))

    def log_message(self, who: str, text: str, name=None, chat=None):
        tag = "我" if who == "me" else "对方"
        prefix = f"{name}: " if name else ""
        self.log_view.appendPlainText(f"[{tag}] {prefix}{text}")

    def log(self, text: str):
        self.log_view.appendPlainText(str(text))

    # ---------- 无边框窗口拖动 ----------
    def mousePressEvent(self, event):
        if event.position().y() <= 40:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        else:
            self._drag = None

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None