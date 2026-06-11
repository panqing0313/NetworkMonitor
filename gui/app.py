"""Flask web dashboard for network device monitoring."""

import os
import sys
import threading
from datetime import datetime

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from flask import Flask, jsonify, render_template, request

from scanner.arp_scanner import scan_network, get_local_network
from scanner.ping_scanner import check_devices
from scanner.oui_db import lookup, is_random_mac
from scanner.network_stats import get_traffic_stats
from scanner.connections import get_connections, get_network_graph
from scanner.packet_monitor import get_activity, start_monitoring
from tracker.device_db import (
    init_db, get_all_devices, upsert_device, get_device_history,
    get_stats, get_timeline
)
from tracker.models import Device

_bundle_dir = getattr(sys, '_MEIPASS', None)

# Determine template/static paths (handle PyInstaller bundle vs dev)
if _bundle_dir and os.path.isdir(os.path.join(_bundle_dir, 'templates')):
    template_dir = os.path.join(_bundle_dir, 'templates')
    static_dir = os.path.join(_bundle_dir, 'static')
elif _bundle_dir and os.path.isdir(os.path.join(_bundle_dir, 'gui', 'templates')):
    template_dir = os.path.join(_bundle_dir, 'gui', 'templates')
    static_dir = os.path.join(_bundle_dir, 'gui', 'static')
else:
    template_dir = os.path.join(_project_root, 'gui', 'templates')
    static_dir = os.path.join(_project_root, 'gui', 'static')

app = Flask(__name__,
    template_folder=template_dir,
    static_folder=static_dir,
    static_url_path='/static')

# Global error handler - prevents any 500 response
@app.errorhandler(Exception)
def handle_error(error):
    return jsonify({'error': str(error), 'status': 'error'}), 200

# Scan state
_scan_lock = threading.Lock()
_last_scan_time = None
_scan_in_progress = False


def _guess_device_type(device):
    """Guess device type from hostname, vendor, and MAC."""
    vendor = device.vendor.lower()
    hostname = device.hostname.lower()
    if any(x in hostname for x in ['router', 'gateway', 'ap', 'wifi']):
        return 'Router'
    if device.ip.endswith('.1') or device.ip.endswith('.254'):
        return 'Router'
    if 'iphone' in hostname or 'ipad' in hostname or 'android' in hostname:
        return 'Phone'
    if vendor in ['apple', 'samsung', 'xiaomi', 'huawei'] and device.is_random_mac:
        return 'Phone'
    if any(x in hostname for x in ['mac', 'macbook', 'mini', 'desktop', 'laptop']):
        return 'Computer'
    if any(x in vendor for x in ['intel', 'realtek', 'broadcom']):
        return 'Computer'
    # Camera
    if any(x in hostname for x in ['camera', 'chuangmi', 'ipcam', 'webcam', 'cam']):
        return 'Camera'
    return 'Unknown'


def _do_scan():
    """Run a full network scan and save results."""
    global _last_scan_time, _scan_in_progress
    with _scan_lock:
        _scan_in_progress = True
    try:
        cidr, local_ip, _ = get_local_network()
        if not cidr:
            return

        # 1. Fast ARP scan
        devices = scan_network(cidr, fast=True)
        arp_ips = {d['ip'] for d in devices}

        # 2. Also ping all known devices from DB that ARP missed
        known_ips = set()
        for existing in get_all_devices():
            if existing.online or existing.ip not in arp_ips:
                known_ips.add(existing.ip)

        all_targets = list(arp_ips | known_ips)
        ping_results = check_devices(all_targets) if all_targets else {}
        found_ips = set()

        # 3. Process ARP-found devices
        for d in devices:
            ip = d['ip']
            found_ips.add(ip)
            ping = ping_results.get(ip, {})
            device = Device(
                ip=ip, mac=d.get('mac', ''),
                hostname=d.get('hostname', ''),
                vendor=lookup(d.get('mac', '')),
                interface=d.get('interface', ''),
                online=ping.get('online', True),
                rtt_ms=ping.get('rtt_ms'),
                is_random_mac=is_random_mac(d.get('mac', '')),
            )
            device.device_type = _guess_device_type(device)
            upsert_device(device)

        # 4. Check known-but-ARP-missed devices via ping
        for existing in get_all_devices():
            ip = existing.ip
            if ip in found_ips:
                continue
            ping = ping_results.get(ip, {})
            online = ping.get('online', False)
            if online:
                found_ips.add(ip)
                existing.online = True
                existing.rtt_ms = ping.get('rtt_ms')
                upsert_device(existing)

        # 5. Mark truly offline
        for existing in get_all_devices():
            if existing.ip not in found_ips and existing.online:
                existing.online = False
                existing.rtt_ms = None
                upsert_device(existing)

        _last_scan_time = datetime.now().isoformat()
    finally:
        with _scan_lock:
            _scan_in_progress = False


# ===== Routes =====

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/scan', methods=['POST'])
def api_scan():
    global _scan_in_progress
    if _scan_in_progress:
        return jsonify({'status': 'scan_in_progress'})
    t = threading.Thread(target=_do_scan, daemon=True)
    t.start()
    return jsonify({'status': 'started'})


@app.route('/api/devices')
def api_devices():
    devices = get_all_devices()
    return jsonify({
        'devices': [d.to_dict() for d in devices],
        'stats': get_stats(),
        'last_scan': _last_scan_time,
    })


@app.route('/api/device/<ip>')
def api_device(ip):
    for d in get_all_devices():
        if d.ip == ip:
            return jsonify({
                'device': d.to_dict(),
                'history': get_device_history(ip, limit=200),
            })
    return jsonify({'error': 'not found', 'device': None, 'history': []})


@app.route('/api/timeline')
def api_timeline():
    hours = request.args.get('hours', 24, type=int)
    return jsonify({'events': get_timeline(hours=hours), 'hours': hours})


@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())


@app.route('/api/network')
def api_network():
    cidr, ip, gw = get_local_network()
    return jsonify({
        'cidr': cidr, 'local_ip': ip, 'gateway': gw,
        'monitoring': _scan_in_progress,
        'last_scan': _last_scan_time,
    })


@app.route('/api/gateway')
def api_gateway():
    cidr, local_ip, gateway = get_local_network()
    gw_device = None
    if gateway:
        for d in get_all_devices():
            if d.ip == gateway:
                gw_device = d.to_dict()
                break
    return jsonify({
        'gateway_ip': gateway, 'local_ip': local_ip, 'cidr': cidr,
        'gateway_device': gw_device,
    })


@app.route('/api/traffic')
def api_traffic():
    return jsonify(get_traffic_stats())


@app.route('/api/connections')
def api_connections():
    """Get active network connections."""
    return jsonify(get_connections())


@app.route('/api/network-graph')
def api_network_graph():
    """Get network graph data for D3 visualization."""
    return jsonify(get_network_graph())


@app.route('/api/activity')
def api_activity():
    """Get real-time network activity data."""
    return jsonify(get_activity())


def create_app():
    init_db()
    start_monitoring()  # start network activity capture
    return app
