# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

# Spec is always run from the project directory
PROJECT_ROOT = os.getcwd()

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # Flask templates
        (os.path.join(PROJECT_ROOT, 'gui', 'templates'), 'gui/templates'),
        (os.path.join(PROJECT_ROOT, 'gui', 'static'), 'gui/static'),
        # Config
        (os.path.join(PROJECT_ROOT, 'config.yaml'), '.'),
    ],
    hiddenimports=[
        'flask',
        'webview',
        'webview.platforms.cocoa',
        'yaml',
        'PIL',
        'PIL._imaging',
        'scanner.arp_scanner',
        'scanner.ping_scanner',
        'scanner.oui_db',
        'scanner.network_stats',
        'tracker.device_db',
        'tracker.models',
        'gui.app',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'click',
        'markupsafe',
        'itsdangerous',
        'blinker',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'notebook',
        'jupyter',
        'test',
        'unittest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NetworkMonitor',
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

app = BUNDLE(
    exe,
    name='Network Monitor.app',
    icon=os.path.join(PROJECT_ROOT, 'NetworkMonitor.app', 'Contents', 'Resources', 'icon.icns'),
    bundle_identifier='com.local.network-monitor',
    info_plist={
        'CFBundleDisplayName': 'Network Monitor',
        'CFBundleName': 'Network Monitor',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': 'NetworkMonitor',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': '用于启动时弹出通知',
        'LSUIElement': False,
    },
)
