"""ARP-based device discovery.

Uses the system `arp -a` command to parse the local ARP table,
and sends ARP probes via ping to discover new devices on the subnet.
"""

import re
import subprocess
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from .platform_utils import IS_MAC, IS_WIN, run_cmd, get_local_ip_windows, get_gateway_windows, parse_arp_windows


def get_local_network():
    """Detect local network CIDR from active interfaces.

    Returns (cidr, local_ip, gateway) or (None, None, None).
    """
    if IS_WIN:
        return _get_local_network_windows()
    return _get_local_network_mac()


def _get_local_network_mac():
    """macOS: detect network from ifconfig + netstat."""
    try:
        ifconfig_out = subprocess.check_output(
            ["ifconfig"], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None, None

    active_iface = None
    local_ip = None
    cidr = None

    interfaces = re.split(r'\n(?=\w+:)', ifconfig_out)
    for iface in interfaces:
        if not iface.strip():
            continue
        name_match = re.match(r'(\w+):', iface)
        if not name_match:
            continue
        name = name_match.group(1)
        if name.startswith(('lo', 'awdl', 'llw', 'utun', 'bridge', 'gif', 'stf', 'anpi', 'ap', 'enX')):
            continue
        if 'UP' not in iface and 'RUNNING' not in iface:
            continue
        ip_m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', iface)
        netmask_m = re.search(r'netmask 0x([0-9a-fA-F]+)', iface)
        if ip_m and netmask_m:
            ip_str = ip_m.group(1)
            if ip_str.startswith('127.'):
                continue
            mask_hex = netmask_m.group(1)
            mask_bits = bin(int(mask_hex, 16)).count('1')
            cidr = f"{ip_str}/{mask_bits}"
            local_ip = ip_str
            active_iface = name
            break

    if not local_ip:
        return None, None, None
    gateway = _detect_gateway_mac(active_iface)
    return cidr, local_ip, gateway


def _detect_gateway_mac(iface=None):
    """macOS: detect default gateway via netstat."""
    try:
        out = subprocess.check_output(
            ["netstat", "-rn"], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        if not line.startswith('default'):
            continue
        parts = line.split()
        if len(parts) >= 2:
            gw = parts[1]
            if gw.startswith(('link#', '127.')):
                continue
            if iface and len(parts) >= 4 and parts[3] == iface:
                return gw
            return gw
    return None


def _get_local_network_windows():
    """Windows: detect network from ipconfig + route."""
    local_ip = get_local_ip_windows()
    if not local_ip:
        return None, None, None
    gateway = get_gateway_windows()
    # Assume /24 subnet
    octets = local_ip.split('.')
    octets[-1] = '0'
    cidr = f"{'.'.join(octets)}/24"
    return cidr, local_ip, gateway


def parse_arp_table():
    """Parse `arp -a` output into a list of device dicts.

    Returns [{ip, mac, hostname, iface}, ...]
    """
    if IS_WIN:
        out = run_cmd('arp -a', timeout=3)
        return parse_arp_windows(out)

    try:
        out = subprocess.check_output(
            ["arp", "-a"], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    devices = []
    # Pattern: hostname (ip) at mac on iface [ethernet]
    pattern = re.compile(
        r'(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+'
        r'([0-9a-fA-F:]+)\s+on\s+(\S+)'
    )
    for line in out.splitlines():
        m = pattern.search(line)
        if m:
            hostname, ip, mac, iface = m.groups()
            mac = mac.lower()
            # Skip multicast, broadcast, and network addresses
            if ip.startswith(('224.', '239.', '255.')):
                continue
            octets = ip.split('.')
            if octets[-1] in ('0', '255'):
                continue  # network or broadcast address
            devices.append({
                'ip': ip,
                'mac': mac,
                'hostname': hostname,
                'interface': iface,
            })
    return devices


def ping_host(ip, timeout=1):
    """Ping a single host, return True if reachable."""
    try:
        subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, timeout=timeout + 1,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def ping_sweep(network_cidr, max_workers=50, timeout=1):
    """Ping sweep an entire subnet to discover live hosts.

    Returns list of IP strings that responded.
    """
    try:
        net = ipaddress.ip_network(network_cidr, strict=False)
    except ValueError:
        return []

    # For /24 or smaller, scan all; for larger, skip the scan
    if net.prefixlen < 16:
        return []

    hosts = [str(h) for h in net.hosts()]

    live = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping_host, h, timeout): h for h in hosts}
        for f in as_completed(futures):
            if f.result():
                live.append(futures[f])
    return sorted(live, key=lambda x: [int(o) for o in x.split('.')])


def scan_network(network_cidr=None, fast=True):
    """Full network scan: ARP table + optional ping sweep.

    Args:
        network_cidr: e.g. "192.168.1.0/24". Auto-detect if None.
        fast: If True, only use ARP table (no ping sweep).

    Returns:
        list of device dicts with ip, mac, hostname, interface, online
    """
    if network_cidr is None:
        cidr, local_ip, _ = get_local_network()
        if cidr is None:
            return []
        network_cidr = cidr
    else:
        local_ip = None

    # ARP table gives us known devices
    arp_devices = parse_arp_table()

    # Build a dict by IP
    seen = {}
    for d in arp_devices:
        seen[d['ip']] = {
            'ip': d['ip'],
            'mac': d['mac'],
            'hostname': d['hostname'],
            'interface': d.get('interface', ''),
            'online': True,
        }

    # If fast mode, return what we have from ARP (already online)
    if fast:
        return list(seen.values())

    # Full mode: ping sweep to discover more
    live_ips = ping_sweep(network_cidr)
    for ip in live_ips:
        if ip not in seen:
            # New device found via ping but not in ARP table yet
            seen[ip] = {
                'ip': ip,
                'mac': '',
                'hostname': '',
                'interface': '',
                'online': True,
            }
        else:
            seen[ip]['online'] = True

    return list(seen.values())
