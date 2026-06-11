#!/usr/bin/env python3
"""Cross-platform build script for Network Monitor.

Usage:
    python3 scripts/build_app.py        # build for current platform
    python3 scripts/build_app.py --dmg  # macOS: also create DMG
"""

import os
import sys
import shutil
import subprocess
import platform

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_MAC = sys.platform == 'darwin'
IS_WIN = sys.platform == 'win32'
APP_NAME = 'Network Monitor'


def clean():
    print("🧹 清理旧构建...")
    for d in ['build', 'dist']:
        p = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(p):
            shutil.rmtree(p)
    spec = os.path.join(PROJECT_ROOT, f'{APP_NAME}.spec')
    if os.path.exists(spec):
        os.remove(spec)


def build_macos():
    """Build macOS .app bundle using PyInstaller."""
    print(f"📦 构建 macOS .app...")

    icon = os.path.join(PROJECT_ROOT, 'NetworkMonitor.app', 'Contents', 'Resources', 'icon.icns')

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', APP_NAME,
        '--windowed', '--onedir',
        f'--icon={icon}',
        '--add-data', f'gui/templates{os.pathsep}templates',
        '--add-data', f'gui/static{os.pathsep}static',
        '--add-data', f'config.yaml{os.pathsep}.',
        '--hidden-import', 'scanner.arp_scanner',
        '--hidden-import', 'scanner.ping_scanner',
        '--hidden-import', 'scanner.oui_db',
        '--hidden-import', 'scanner.network_stats',
        '--hidden-import', 'scanner.connections',
        '--hidden-import', 'scanner.platform_utils',
        '--hidden-import', 'tracker.device_db',
        '--hidden-import', 'tracker.models',
        '--hidden-import', 'gui.app',
        '--hidden-import', 'webview',
        '--hidden-import', 'flask',
        '--hidden-import', 'yaml',
        '--collect-submodules', 'webview',
        '--collect-submodules', 'flask',
        '--collect-submodules', 'werkzeug',
        '--osx-bundle-identifier', 'com.local.network-monitor',
        '-y',
        'main.py',
    ]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    if result.returncode != 0:
        print("❌ 构建失败")
        sys.exit(1)
    print("✅ macOS 构建完成")


def build_dmg():
    """Create macOS DMG from built .app."""
    print("📀 创建 DMG...")
    app_path = os.path.join(PROJECT_ROOT, 'dist', f'{APP_NAME}.app')
    if not os.path.exists(app_path):
        print("❌ 未找到 .app，请先构建")
        return

    dmg_name = f'{APP_NAME.replace(" ", "_")}_v1.0.dmg'
    dmg_path = os.path.join(PROJECT_ROOT, 'dist', dmg_name)

    tmp_dir = '/tmp/NetMonBuild'
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)

    shutil.copytree(app_path, os.path.join(tmp_dir, f'{APP_NAME}.app'),
                    symlinks=True, dirs_exist_ok=True)

    # Create Applications shortcut
    os.symlink('/Applications', os.path.join(tmp_dir, 'Applications'))

    # README
    with open(os.path.join(tmp_dir, '说明.txt'), 'w') as f:
        f.write('Network Monitor v1.0\n拖入 Applications 文件夹即可安装\n')

    subprocess.run([
        'hdiutil', 'create', '-volname', 'Network Monitor',
        '-srcfolder', tmp_dir, '-ov', '-format', 'UDZO', dmg_path
    ], check=True)

    shutil.rmtree(tmp_dir)
    size = os.path.getsize(dmg_path) / 1024 / 1024
    print(f"✅ DMG: {dmg_name} ({size:.0f}MB)")


def build_windows():
    """Build Windows executable using PyInstaller."""
    print(f"📦 构建 Windows .exe...")

    icon = os.path.join(PROJECT_ROOT, 'gui', 'static', 'icon.ico')
    if not os.path.exists(icon):
        icon = os.path.join(PROJECT_ROOT, 'NetworkMonitor.app',
                            'Contents', 'Resources', 'icon.icns')

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', APP_NAME,
        '--windowed', '--onedir',
        f'--icon={icon}' if icon else '',
        '--add-data', f'gui/templates{os.pathsep}templates',
        '--add-data', f'gui/static{os.pathsep}static',
        '--add-data', f'config.yaml{os.pathsep}.',
        '--hidden-import', 'scanner.arp_scanner',
        '--hidden-import', 'scanner.ping_scanner',
        '--hidden-import', 'scanner.oui_db',
        '--hidden-import', 'scanner.network_stats',
        '--hidden-import', 'scanner.connections',
        '--hidden-import', 'scanner.platform_utils',
        '--hidden-import', 'tracker.device_db',
        '--hidden-import', 'tracker.models',
        '--hidden-import', 'gui.app',
        '--hidden-import', 'webview',
        '--hidden-import', 'flask',
        '--hidden-import', 'yaml',
        '--collect-submodules', 'webview',
        '--collect-submodules', 'flask',
        '--collect-submodules', 'werkzeug',
        '-y',
        'main.py',
    ]
    # Remove empty args
    cmd = [c for c in cmd if c]

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    if result.returncode != 0:
        print("❌ Windows 构建失败")
        sys.exit(1)

    exe_path = os.path.join(PROJECT_ROOT, 'dist', APP_NAME)
    print(f"✅ Windows 构建完成: {exe_path}")


def main():
    print(f"🏗️  Network Monitor 构建工具")
    print(f"   平台: {platform.system()} {platform.machine()}")
    print(f"   Python: {sys.version.split()[0]}")
    print()

    clean()

    if IS_MAC:
        build_macos()
        if '--dmg' in sys.argv:
            build_dmg()
        print(f"\n📦 产物: {os.path.join(PROJECT_ROOT, 'dist', f'{APP_NAME}.app')}")
    elif IS_WIN:
        build_windows()
        print(f"\n📦 产物: {os.path.join(PROJECT_ROOT, 'dist', APP_NAME)}")
    else:
        print("⚠️  当前平台暂不支持自动打包")

    # Show size
    dist = os.path.join(PROJECT_ROOT, 'dist')
    if os.path.exists(dist):
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in
                   os.walk(dist) for f in fn) / 1024 / 1024
        print(f"   总大小: {size:.0f}MB")


if __name__ == '__main__':
    main()
