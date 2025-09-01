# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for BindKit (Windows)

Produces an onedir distribution at dist/DesktopUtilityGUI/ with:
- Embedded Windows version resources (from version_info.py when present)
- Included resources: style.qss and scripts/ directory
- Hidden imports for common Windows + OCR deps
"""

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('style.qss', '.'),
        ('scripts', 'scripts'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        # Windows / pywin32 bits often needed in packaged apps
        'win32com',
        'win32com.client',
        'win32api',
        'win32con',
        'pythoncom',
        'pywintypes',
        # OCR / image / automation deps
        'easyocr',
        'PIL',
        'Pillow',
        'pyautogui',
        'numpy',
        'cv2',
    ] + collect_submodules('easyocr') + collect_submodules('torch'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BindKit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,  # GUI app
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    version='version_info.py' if os.path.exists('version_info.py') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BindKit',
)
