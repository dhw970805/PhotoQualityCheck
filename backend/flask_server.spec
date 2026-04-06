# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Flask backend.

Build:  cd backend && pyinstaller flask_server.spec --distpath dist --workpath build --clean
Output: backend/dist/flask_server/
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# --- Collect native assets for heavy packages ---
# collect_all returns (datas, binaries, hiddenimports)
mediapipe_datas, mediapipe_bins, mediapipe_hids = collect_all('mediapipe')
rawpy_datas, rawpy_bins, rawpy_hids = collect_all('rawpy')
cv2_datas, cv2_bins, cv2_hids = collect_all('cv2')

# eventlet uses dynamic imports extensively; enumerate all submodules
eventlet_hids = collect_submodules('eventlet')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=mediapipe_bins + rawpy_bins + cv2_bins,
    datas=mediapipe_datas + rawpy_datas + cv2_datas,
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_socketio',
        'engineio.async_drivers.threading',
        'PIL',
        'PIL.Image',
        'PIL.ImageOps',
        'numpy',
        'requests',
    ] + eventlet_hids + mediapipe_hids + rawpy_hids + cv2_hids,
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
    name='flask_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # UPX corrupts native C++ DLLs from mediapipe/opencv/libraw
    console=False,   # No cmd window popup on Windows
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='flask_server',
)
