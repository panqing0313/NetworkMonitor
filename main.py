#!/usr/bin/env python3
"""Network Monitor - 局域网设备监测工具 (桌面版)

Usage:
    python main.py              # 启动桌面应用
    python main.py --cli        # CLI 模式
    python main.py --scan       # CLI 扫描一次
"""

import argparse
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime

# Support both source and PyInstaller-bundled runs
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    PROJECT_ROOT = sys._MEIPASS
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# Data directory — writable location outside the bundle
DATA_DIR = os.path.join(os.path.expanduser('~'), '.network-monitor', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

import yaml

from scanner.arp_scanner import scan_network, get_local_network
from scanner.ping_scanner import check_devices, check_device
from scanner.oui_db import lookup, is_random_mac
from tracker.device_db import init_db, get_all_devices, upsert_device
from tracker.models import Device


def load_config():
    config_path = os.path.join(PROJECT_ROOT, 'config.yaml')
    defaults = {
        'web_port': 5206,
        'scan_interval': 60,
        'ping_timeout': 2,
        'max_workers': 50,
        'auto_scan': True,
        'history_retention_days': 30,
    }
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        defaults.update(cfg.get('monitor', {}))
    return defaults


def run_scan(config):
    """Run a single scan and return results."""
    cidr, local_ip, _ = get_local_network()
    if not cidr:
        print("❌ 无法检测本地网络")
        return []

    # ARP scan + ping all known devices
    arp_devices = scan_network(cidr, fast=True)
    arp_ips = {d['ip'] for d in arp_devices}

    known_ips = set()
    for existing in get_all_devices():
        if existing.online or existing.ip not in arp_ips:
            known_ips.add(existing.ip)

    all_targets = list(arp_ips | known_ips)
    ping_results = check_devices(all_targets, timeout=config['ping_timeout']) if all_targets else {}
    found_ips = set()
    results = []

    for d in arp_devices:
        ip = d['ip']
        found_ips.add(ip)
        ping_info = ping_results.get(ip, {})
        vendor = lookup(d.get('mac', ''))
        rand_mac = is_random_mac(d.get('mac', ''))
        device = Device(
            ip=ip, mac=d.get('mac', ''), hostname=d.get('hostname', ''),
            vendor=vendor, interface=d.get('interface', ''),
            online=ping_info.get('online', True), rtt_ms=ping_info.get('rtt_ms'),
            is_random_mac=rand_mac,
        )
        device.device_type = _guess_device_type(device)
        upsert_device(device)
        results.append(device)

    # Check known-but-ARP-missed devices via ping
    for existing in get_all_devices():
        ip = existing.ip
        if ip in found_ips:
            continue
        ping_info = ping_results.get(ip, {})
        if ping_info.get('online', False):
            found_ips.add(ip)
            existing.online = True
            existing.rtt_ms = ping_info.get('rtt_ms')
            upsert_device(existing)
            results.append(existing)

    # Mark truly offline
    for existing in get_all_devices():
        if existing.ip not in found_ips and existing.online:
            existing.online = False
            existing.rtt_ms = None
            upsert_device(existing)

    return results


def _guess_device_type(device):
    vendor = device.vendor.lower()
    hostname = device.hostname.lower()
    if any(x in hostname for x in ['router', 'gateway', 'xiaomi']) or device.ip.endswith('.1'):
        return 'Router'
    if 'iphone' in hostname or 'ipad' in hostname or 'android' in hostname:
        return 'Phone'
    if vendor in ['apple', 'samsung', 'xiaomi', 'huawei', 'oppo', 'vivo'] and device.is_random_mac:
        return 'Phone'
    if any(x in hostname for x in ['mac', 'macbook', 'mini', 'desktop', 'laptop', 'pc']):
        return 'Computer'
    if any(x in vendor for x in ['intel', 'realtek', 'broadcom']):
        return 'Computer'
    return 'Unknown'


def cli_scan(config):
    init_db()
    results = run_scan(config)
    if not results:
        print("❌ 未发现设备")
        return
    print(f"\n📱 共发现 {len(results)} 个设备")
    for d in sorted(results, key=lambda x: (not x.online, x.ip)):
        status = '🟢' if d.online else '🔴'
        rtt = f" {d.rtt_ms}ms" if d.rtt_ms else ""
        mac = f" {d.mac}" if d.mac else ""
        print(f"  {status} {d.ip:15s} {d.hostname:20s}{mac} [{d.vendor}] {d.device_type}{rtt}")


def start_desktop(config):
    """Start the desktop application using pywebview."""
    init_db()

    # Import here (Flask + pywebview)
    from gui.app import create_app
    import webview

    app = create_app()
    port = config['web_port']

    # Flask server thread
    def run_flask():
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Wait for Flask to start
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/network', timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    # Auto-scan on startup
    scan_thread = threading.Thread(target=lambda: run_scan(config), daemon=True)
    scan_thread.start()

    # Create native window
    window = webview.create_window(
        title='Network Monitor - 局域网设备监测',
        url=f'http://127.0.0.1:{port}',
        width=1200,
        height=800,
        min_size=(800, 500),
        resizable=True,
        fullscreen=False,
        text_select=True,
    )

    webview.start(
        debug=False,
        http_server=False,  # We use our own Flask server
        private_mode=True,
        storage_path=os.path.join(PROJECT_ROOT, 'data'),
    )


def main():
    parser = argparse.ArgumentParser(
        description='📡 Network Monitor - 局域网设备监测工具'
    )
    parser.add_argument('--scan', action='store_true', help='CLI 扫描一次')
    parser.add_argument('--cli', action='store_true', help='CLI 模式 (持续监控)')
    args = parser.parse_args()
    config = load_config()

    if args.scan:
        cli_scan(config)
    elif args.cli:
        cli_scan(config)
    else:
        start_desktop(config)


if __name__ == '__main__':
    main()
