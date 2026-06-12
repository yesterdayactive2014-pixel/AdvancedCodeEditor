# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['code_editor.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('AlanTrain', 'AlanTrain'), ('index.html', '.')],
    hiddenimports=['PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebChannel', 'PyQt6.QtSerialPort'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CodeEditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
