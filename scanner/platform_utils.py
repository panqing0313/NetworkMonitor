"""Cross-platform utilities for network monitoring.

Handles macOS ↔ Windows command differences.
"""

import sys
import subprocess
import platform

IS_MAC = sys.platform == 'darwin'
IS_WIN = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

ARCH = platform.machine()


def run_cmd(cmd, mac_cmd=None, win_cmd=None, timeout=5, **kwargs):
    """Run a command with platform-specific overrides."""
    if IS_WIN and win_cmd:
        actual = win_cmd
    elif IS_MAC and mac_cmd:
        actual = mac_cmd
    else:
        actual = cmd

    if isinstance(actual, str):
        actual = actual.split()

    try:
        return subprocess.check_output(actual, text=True, timeout=timeout, **kwargs)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return ''


def get_local_ip_windows():
    """Get primary local IP on Windows using ipconfig."""
    out = run_cmd('ipconfig', timeout=3)
    for line in out.splitlines():
        if 'IPv4' in line and ':' in line:
            ip = line.split(':')[-1].strip()
            if ip and not ip.startswith('169.'):
                return ip
    return None


def get_gateway_windows():
    """Get default gateway on Windows."""
    out = run_cmd('route print 0.0.0.0', timeout=3)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == '0.0.0.0':
            return parts[2]
    return None


def parse_arp_windows(output):
    """Parse Windows `arp -a` output into list of {ip, mac, hostname}."""
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            ip = parts[0]
            mac = parts[1].replace('-', ':').lower()
            typ = parts[2] if len(parts) > 2 else ''
            # Filter: must look like an IP
            if ip.count('.') == 3 and mac.count(':') == 5:
                if not ip.startswith(('224.', '239.', '255.')):
                    octets = ip.split('.')
                    if octets[-1] not in ('0', '255'):
                        devices.append({
                            'ip': ip,
                            'mac': mac,
                            'hostname': ip,  # Windows ARP doesn't give hostnames
                            'interface': '',
                        })
    return devices
