# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import copy_metadata


a = Analysis(
    ['src\\app_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('src', 'src'), ('docs', 'docs'), ('requirements.txt', '.')] + copy_metadata('streamlit'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'easyocr', 'cv2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BackupOrganizerLite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BackupOrganizerLite',
)
