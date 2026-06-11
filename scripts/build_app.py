#!/usr/bin/env python3
"""Cross-platform build script for Network Monitor.

Usage:
    python scripts/build_app.py          # build for current platform
    python scripts/build_app.py --dmg    # macOS: also create DMG
"""
import os, sys, shutil, subprocess, platform

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_MAC = sys.platform == 'darwin'
IS_WIN = sys.platform == 'win32'
APP_NAME = 'Network Monitor'


def log(msg):
    """Print without emoji to avoid Windows encoding issues."""
    clean = msg.replace('\U0001f9f9', '[CLEAN]').replace('\U0001f4e6', '[PACK]') \
                .replace('\U0001f4c0', '[DMG]').replace('\u274c', '[FAIL]') \
                .replace('\u2705', '[OK]').replace('\u26a0\ufe0f', '[WARN]') \
                .replace('\U0001f3d7\ufe0f', '[BUILD]').replace('\u23f3', '[WAIT]')
    print(clean)


def clean():
    log("[CLEAN] Cleaning old builds...")
    for d in ['build', 'dist']:
        p = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(p):
            shutil.rmtree(p)
    spec = os.path.join(PROJECT_ROOT, f'{APP_NAME}.spec')
    if os.path.exists(spec):
        os.remove(spec)


def build_macos():
    log("[PACK] Building macOS .app...")
    icon = os.path.join(PROJECT_ROOT, 'NetworkMonitor.app', 'Contents', 'Resources', 'icon.icns')
    if not os.path.exists(icon):
        icon = os.path.join(PROJECT_ROOT, 'gui', 'static', 'd3.min.js')  # fallback

    cmd = [sys.executable, '-m', 'PyInstaller',
        '--name', APP_NAME, '--windowed', '--onedir',
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
        '-y', 'main.py']

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    if result.returncode != 0:
        log("[FAIL] macOS build failed")
        sys.exit(1)
    log("[OK] macOS build complete")


def build_dmg():
    log("[DMG] Creating DMG...")
    app_path = os.path.join(PROJECT_ROOT, 'dist', f'{APP_NAME}.app')
    if not os.path.exists(app_path):
        log("[FAIL] .app not found, build first")
        return

    dmg_name = f'{APP_NAME.replace(" ", "_")}_v1.0.dmg'
    dmg_path = os.path.join(PROJECT_ROOT, 'dist', dmg_name)

    tmp_dir = '/tmp/NetMonBuild'
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)

    shutil.copytree(app_path, os.path.join(tmp_dir, f'{APP_NAME}.app'),
                    symlinks=True, dirs_exist_ok=True)
    os.symlink('/Applications', os.path.join(tmp_dir, 'Applications'))

    subprocess.run(['hdiutil', 'create', '-volname', 'Network Monitor',
        '-srcfolder', tmp_dir, '-ov', '-format', 'UDZO', dmg_path], check=True)

    shutil.rmtree(tmp_dir)
    size = os.path.getsize(dmg_path) / 1024 / 1024
    log(f"[OK] DMG: {dmg_name} ({size:.0f}MB)")


def build_windows():
    log("[PACK] Building Windows .exe...")

    # Windows needs .ico icon, not .icns
    icon = os.path.join(PROJECT_ROOT, 'gui', 'static', 'icon.ico')
    if not os.path.exists(icon):
        icon = ''  # no icon, pyinstaller will use default

    cmd = [sys.executable, '-m', 'PyInstaller',
        '--name', APP_NAME, '--windowed', '--onedir',
        '--hide-console', 'hide-early']
    if icon:
        cmd.append(f'--icon={icon}')
    cmd += [
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
        '-y', 'main.py']

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    if result.returncode != 0:
        log("[FAIL] Windows build failed")
        sys.exit(1)

    exe_path = os.path.join(PROJECT_ROOT, 'dist', APP_NAME)
    log(f"[OK] Windows build complete: {exe_path}")


def main():
    log("[BUILD] Network Monitor Build Tool")
    log(f"  Platform: {platform.system()} {platform.machine()}")
    log(f"  Python: {sys.version.split()[0]}")
    log("")

    clean()

    if IS_MAC:
        build_macos()
        if '--dmg' in sys.argv:
            build_dmg()
        log(f"\n[OK] Output: {os.path.join(PROJECT_ROOT, 'dist', f'{APP_NAME}.app')}")
    elif IS_WIN:
        build_windows()
        log(f"\n[OK] Output: {os.path.join(PROJECT_ROOT, 'dist', APP_NAME)}")
    else:
        log("[WARN] Platform not supported for automated build")

    # Show size
    dist = os.path.join(PROJECT_ROOT, 'dist')
    if os.path.exists(dist):
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in
                   os.walk(dist) for f in fn) / 1024 / 1024
        log(f"  Total size: {size:.0f}MB")


if __name__ == '__main__':
    main()
