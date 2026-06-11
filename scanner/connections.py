"""Active network connection monitoring.

Uses netstat to track active TCP connections and identifies
internal (LAN) vs external (internet) connections.
"""

import subprocess
import re
import ipaddress
from collections import defaultdict
from threading import Lock
from .platform_utils import IS_WIN, IS_MAC

# Common external services by IP range (simplified)
KNOWN_SERVICES = {
    "Google": ["74.125", "172.217", "142.250", "216.58", "142.251"],
    "Apple": ["17.0", "17.1", "17.2", "17.3", "17.4"],
    "Cloudflare": ["104.16", "104.17", "104.18", "104.19", "1.1.1"],
    "Amazon/AWS": ["52.0", "52.1", "52.2", "52.3", "54.0", "54.1", "54.2"],
    "Microsoft": ["13.64", "13.65", "13.66", "13.67", "40.0", "40.1"],
    "Tencent/WeChat": ["112.90", "113.96", "119.147", "175.24", "8.141"],
    "Alibaba": ["47.88", "47.89", "47.90", "8.141", "8.142"],
}

# Local network prefixes
LOCAL_PREFIXES = [
    "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "100.64.", "100.65.", "100.66.",
]


class ConnectionMonitor:
    """Monitors active network connections on the system."""

    def __init__(self):
        self._lock = Lock()
        self._local_ip = self._detect_local_ip()

    def _detect_local_ip(self):
        """Detect the primary local IP address."""
        if IS_WIN:
            from .platform_utils import get_local_ip_windows
            ip = get_local_ip_windows()
            return ip or '127.0.0.1'
        try:
            out = subprocess.check_output(
                ["ifconfig"], text=True, stderr=subprocess.DEVNULL
            )
            for m in re.finditer(r'inet (\d+\.\d+\.\d+\.\d+)', out):
                ip = m.group(1)
                if not ip.startswith('127.') and not ip.startswith('0.'):
                    return ip
        except:
            pass
        return "127.0.0.1"

    def _get_connections_windows(self):
        """Get connections on Windows using netstat -an."""
        connections = []
        try:
            out = subprocess.check_output(
                ["netstat", "-an"],
                text=True, stderr=subprocess.DEVNULL, timeout=3
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                if not parts[0].upper().startswith('TCP'):
                    continue
                local = parts[1]
                foreign = parts[2]
                state = parts[3]
                m = re.match(r'(\d+\.\d+\.\d+\.\d+):(\d+)', local)
                if not m:
                    continue
                local_ip, local_port = m.group(1), m.group(2)
                m2 = re.match(r'(\d+\.\d+\.\d+\.\d+):(\d+)', foreign)
                if not m2:
                    continue
                foreign_ip, foreign_port = m2.group(1), m2.group(2)
                if local_ip.startswith(('0.', '127.')) and foreign_ip.startswith(('0.', '127.')):
                    if state.upper() == 'LISTENING':
                        connections.append((local_ip, local_port, '*', '*', 'LISTEN'))
                    continue
                connections.append((local_ip, local_port, foreign_ip, foreign_port, state.upper()))
        except:
            pass
        return connections

    def _get_connections(self):
        """Get active TCP connections using netstat.

        Returns list of (local_ip, local_port, remote_ip, remote_port, state).
        """
        if IS_WIN:
            return self._get_connections_windows()
        connections = []
        try:
            out = subprocess.check_output(
                ["netstat", "-an", "-p", "tcp"],
                text=True, stderr=subprocess.DEVNULL, timeout=3
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                if not parts[0].startswith('tcp'):
                    continue

                local = parts[3]
                foreign = parts[4]
                state = parts[5] if len(parts) > 5 else ''

                # Parse local address
                local_match = re.match(r'\[?([^\]]+)\]?\.(\d+)', local)
                if not local_match:
                    continue
                local_ip = local_match.group(1).strip('[]')
                local_port = local_match.group(2)

                # Parse foreign address
                foreign_match = re.match(r'\[?([^\]]+)\]?\.(\d+)', foreign)
                if not foreign_match:
                    continue
                foreign_ip = foreign_match.group(1).strip('[]')
                foreign_port = foreign_match.group(2)

                # Skip IPv6 link-local for now
                if local_ip.startswith('fe80:') or foreign_ip.startswith('fe80:'):
                    continue

                connections.append((local_ip, local_port, foreign_ip, foreign_port, state))
        except:
            pass

        return connections

    def _guess_service(self, ip):
        """Guess the service name from an external IP."""
        for service, prefixes in KNOWN_SERVICES.items():
            for prefix in prefixes:
                if ip.startswith(prefix):
                    return service
        return None

    def _is_internal(self, ip):
        """Check if an IP is internal (LAN/local)."""
        if ip == '127.0.0.1' or ip == '::1':
            return True
        if ip.startswith('fe80:'):
            return True
        for prefix in LOCAL_PREFIXES:
            if ip.startswith(prefix):
                return True
        return False

    def get_connections(self):
        """Get all active connections categorized by type.

        Returns dict with internal, external, and listening connections.
        """
        with self._lock:
            raw = self._get_connections()

        internal = []
        external = []
        listening = []
        seen = set()

        for local_ip, local_port, remote_ip, remote_port, state in raw:
            # Skip localhost-only if not interesting
            if local_ip == '127.0.0.1' and remote_ip == '127.0.0.1':
                if state == 'LISTEN':
                    listening.append({
                        'local_ip': local_ip,
                        'port': local_port,
                        'state': 'LISTEN',
                    })
                continue

            # Detect connection type
            is_local_internal = self._is_internal(remote_ip)
            key = f"{remote_ip}:{remote_port}"

            if is_local_internal:
                if key not in seen:
                    seen.add(key)
                    internal.append({
                        'local_ip': local_ip,
                        'local_port': local_port,
                        'remote_ip': remote_ip,
                        'remote_port': remote_port,
                        'state': state,
                        'is_internal': True,
                    })
            elif remote_ip != '*':
                if key not in seen:
                    seen.add(key)
                    service = self._guess_service(remote_ip)
                    external.append({
                        'local_ip': local_ip,
                        'local_port': local_port,
                        'remote_ip': remote_ip,
                        'remote_port': remote_port,
                        'state': state,
                        'is_internal': False,
                        'service': service or 'Unknown',
                    })

        return {
            'local_ip': self._local_ip,
            'internal': internal,
            'external': external,
            'listening': listening,
            'total_connections': len(internal) + len(external),
            'internal_count': len(internal),
            'external_count': len(external),
        }

    def get_network_graph(self):
        """Build a force-directed graph data structure.

        Returns nodes and edges for D3.js visualization.
        Includes all known devices + active connections.
        """
        conns = self.get_connections()
        nodes = []
        edges = []
        node_map = {}
        node_id = 0

        def _add_node(ip, label, node_type, group, size=8, device=None):
            nonlocal node_id
            if ip not in node_map:
                entry = {
                    'id': node_id,
                    'ip': ip,
                    'label': label,
                    'type': node_type,
                    'group': group,
                    'size': size,
                }
                if device:
                    entry['vendor'] = device.get('vendor', '')
                    entry['device_type'] = device.get('device_type', '')
                    entry['hostname'] = device.get('hostname', '')
                    entry['online'] = device.get('online', False)
                    entry['rtt_ms'] = device.get('rtt_ms')
                node_map[ip] = entry
                nodes.append(entry)
                node_id += 1
            return node_map[ip]['id']

        # Device type → icon mapper
        def _device_icon(dtype, vendor=''):
            v = vendor.lower()
            if dtype == 'Router': return '🔀'
            if dtype == 'Camera': return '📷'
            if dtype == 'Phone': return '📱'
            if dtype == 'Computer': return '💻'
            if 'xiaomi' in v or 'mi' in v: return '📡'
            if dtype == 'IoT': return '💡'
            return '🔌'

        # Central node: this machine
        local_id = _add_node(
            self._local_ip,
            f"本机",
            'local', 'local', 22
        )

        # ── Add ALL known LAN devices from the database ──
        try:
            from tracker.device_db import get_all_devices
            lan_devices = get_all_devices()
            for dev in lan_devices:
                if dev.ip == self._local_ip or dev.ip == '127.0.0.1':
                    continue
                d = dev.to_dict()
                icon = _device_icon(d.get('device_type', ''), d.get('vendor', ''))
                label = d.get('hostname', '') or d.get('vendor', '') or d['ip']
                # Truncate long hostnames
                if len(label) > 12: label = label[:12] + '…'
                nid = _add_node(
                    d['ip'], f"{icon} {label}",
                    'lan', 'lan', 12,
                    device=d
                )
                # Edge from local to this device
                edges.append({
                    'source': local_id,
                    'target': nid,
                    'type': 'lan',
                    'label': f"{d.get('rtt_ms', '?')}ms" if d.get('online') else 'offline',
                    'active': d.get('online', False),
                    'count': 1,
                })
        except ImportError:
            pass

        # ── External connections (grouped by service) ──
        external_groups = defaultdict(list)
        for c in conns['external']:
            service = c.get('service', 'Unknown')
            external_groups[service].append(c)

        for service, conn_list in external_groups.items():
            service_id = _add_node(
                service, f"🌐 {service}",
                'external', 'wan',
                10 + min(len(conn_list), 6)
            )
            edges.append({
                'source': local_id,
                'target': service_id,
                'type': 'wan',
                'label': f"{len(conn_list)}连",
                'active': True,
                'count': len(conn_list),
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'local_ip': self._local_ip,
            'stats': {
                'lan': len(lan_devices) if 'lan_devices' in dir() else 0,
                'wan': len(external_groups),
            }
        }


# Global singleton
_monitor = ConnectionMonitor()


def get_connections():
    """Get active connections (thread-safe)."""
    return _monitor.get_connections()


def get_network_graph():
    """Get network graph data (thread-safe)."""
    return _monitor.get_network_graph()
