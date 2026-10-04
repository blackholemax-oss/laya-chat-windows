# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包定义：单文件 exe + UPX 压缩（排除 Qt6 / onnxruntime）。

    pyinstaller --noconfirm --clean --upx-dir .upx/upx-5.2.1-win64 laya-chat.spec

onefile：输出单个 dist\\laya-chat-windows.exe；UIP 每次启动会先解压到临时目录，首启慢几秒。
UPX 只压「压了没事」的部分：Qt6 的 DLL 和 onnxruntime 的 provider 是出了名的压完就崩，
所以列进 upx_exclude，其余（Python 扩展、OCR 模型外的二进制等）照压。
"""
from PyInstaller.utils.hooks import collect_all

NAME = "laya-chat-windows"

hiddenimports = [
    # spawn 出来的采集子进程按名字 import app.worker，再顺着它拉 capture/ocr；
    # 父进程这边 engine/debugwin 也是运行时才走到，静态分析扫不全，一并钉死。
    "app.worker", "app.capture", "app.ocr", "app.chatapps", "app.overlay",
    "app.settings", "app.i18n", "app.debugwin",
    "core.engine", "core.laya_client", "core.intent_questions",
    "windows_capture",  # 在 app/capture.py 的函数内 import，静态分析扫不到
]

datas, binaries = [], []
# 许可证随包分发：onefile 里会被解压到 _MEIPASS，满足署名/GPL 组件声明要求
datas += [("LICENSE", "."), ("NOTICE", "."), ("LICENSES", "LICENSES")]
for pkg in (
    "rapidocr_onnxruntime",  # .onnx 模型 + config.yaml 是包数据，不收就是启动即炸
    "onnxruntime",           # capi 下面那堆 DLL
    "qfluentwidgets",        # qss / 图标资源（debugwin 用 PlainTextEdit）
    "windows_capture",       # Rust 编译的 .pyd
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

excludes = [
    # 确认没人用：rapidocr 只用 cv2 / PIL / yaml / pyclipper / shapely（PIL 千万别排，读图要它）
    "tkinter", "matplotlib", "scipy", "pandas",
] + ["PySide6." + m for m in (
    # 留着 QtCore / QtGui / QtWidgets / QtSvg / QtSvgWidgets / QtXml —— import qfluentwidgets 实测就这六个
    "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtWebChannel",
    "QtMultimedia", "QtMultimediaWidgets", "QtCharts", "QtDataVisualization",
    "QtQuick", "QtQuick3D", "QtQuickControls2", "QtQuickWidgets", "QtQuickTest", "QtQml",
    "QtPdf", "QtPdfWidgets", "QtBluetooth", "QtNfc", "QtSensors", "QtSerialPort",
    "QtTest", "QtDesigner", "QtHelp", "QtRemoteObjects", "QtScxml", "QtStateMachine",
    "QtTextToSpeech", "QtPositioning", "QtLocation", "QtSql",
    "Qt3DCore", "Qt3DRender", "Qt3DInput", "Qt3DLogic", "Qt3DAnimation", "Qt3DExtras",
)]

# 压了容易崩的目标：Qt6 运行库 + PySide6 扩展模块 + onnxruntime 的 provider
UPX_EXCLUDE = [
    "Qt6*.dll", "Qt*.pyd", "shiboken6*.pyd",
    "onnxruntime*.dll", "*onnxruntime*.dll",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=UPX_EXCLUDE,
    runtime_tmpdir=None,
    console=False,  # 不要黑框；聊天内容不落日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)