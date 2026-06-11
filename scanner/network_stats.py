"""Cross-platform network traffic monitoring.

macOS: `netstat -b` for per-interface byte counters.
Windows: `netstat -e` for aggregate interface stats.
"""

import subprocess
import time
import re
import sys
from threading import Lock
from .platform_utils import IS_WIN, IS_MAC


class TrafficMonitor:
    """Monitors network interface traffic with robust parsing."""

    def __init__(self):
        self._lock = Lock()
        self._prev = {}
        self._speeds = {}
        self._totals = {}
        self._active_iface = None
        self._column_map = None  # detected column positions

    def _detect_columns(self, header):
        """Detect which columns contain Ibytes and Obytes from netstat header."""
        parts = header.split()
        ib_col = ob_col = None
        for i, p in enumerate(parts):
            p = p.lower()
            if p in ('ibytes', 'in', 'i.pkts', 'ipkts', 'iaddr'):
                ib_col = i
            if p in ('obytes', 'out', 'o.pkts', 'opkts', 'oaddr'):
                ob_col = i
        return ib_col, ob_col

    def _get_active_interface(self):
        """Detect primary active network interface."""
        if IS_WIN:
            try:
                out = subprocess.check_output(
                    ["wmic", "nic", "where", "NetEnabled=true", "get", "NetConnectionID"],
                    text=True, stderr=subprocess.DEVNULL, timeout=3
                )
                for line in out.splitlines():
                    line = line.strip()
                    if line and line != 'NetConnectionID' and 'Wi-Fi' in line or 'Ethernet' in line:
                        return line
            except Exception:
                pass
            return '以太网'
        try:
            out = subprocess.check_output(
                ["route", "-n", "get", "default"],
                text=True, stderr=subprocess.DEVNULL, timeout=3
            )
            m = re.search(r'interface:\s+(\S+)', out)
            if m:
                return m.group(1)
        except Exception:
            pass
        return 'en0'

    def _get_interfaces(self):
        """Read traffic stats for all interfaces.

        Returns {iface: (ibytes, obytes)}
        """
        if IS_WIN:
            try:
                out = subprocess.check_output(
                    ["netstat", "-e"],
                    text=True, stderr=subprocess.DEVNULL, timeout=3
                )
                ibytes = obytes = 0
                for line in out.splitlines():
                    ls = line.strip().lower()
                    if ls.startswith('bytes') or 'received' in ls:
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                ibytes = int(parts[0].replace(',', ''))
                                obytes = int(parts[1].replace(',', ''))
                            except ValueError:
                                pass
                return {'interface': (ibytes, obytes)}
            except Exception:
                return {}

        # macOS: try different netstat flags
        for flags in [["-b"], ["-ib"], ["-i", "-b"]]:
            try:
                out = subprocess.check_output(
                    ["netstat"] + flags,
                    text=True, stderr=subprocess.DEVNULL, timeout=3
                )
                return self._parse_netstat(out)
            except Exception:
                continue
        return {}

    def _parse_netstat(self, output):
        """Parse netstat output, returning {iface: (ibytes, obytes)}."""
        result = {}
        lines = output.strip().splitlines()
        if not lines:
            return result

        # First line is header (Name Mtu Network Address Ibytes Ierrs ...)
        header = lines[0]
        ib_col, ob_col = self._detect_columns(header)
        if ib_col is None or ob_col is None:
            # Fallback: try common positions (6=Ibytes, 8=Obytes)
            ib_col, ob_col = 6, 8

        for line in lines[1:]:
            parts = line.split()
            if len(parts) <= max(ib_col, ob_col):
                continue
            name = parts[0]
            # Skip non-Ethernet interfaces
            if not name.startswith('en') or name == 'enX':
                continue
            try:
                ibytes = int(parts[ib_col])
                obytes = int(parts[ob_col])
                result[name] = (ibytes, obytes)
            except (ValueError, IndexError):
                continue

        return result

    def update(self):
        """Update traffic stats by reading fresh netstat data."""
        with self._lock:
            now = time.time()
            interfaces = self._get_interfaces()
            if not interfaces:
                return

            for name, (ibytes, obytes) in interfaces.items():
                if name in self._prev:
                    prev_ib, prev_ob, prev_ts = self._prev[name]
                    elapsed = now - prev_ts
                    if elapsed > 0.5:  # Skip unrealistically short intervals
                        down_bps = (ibytes - prev_ib) * 8 / elapsed
                        up_bps = (obytes - prev_ob) * 8 / elapsed
                        self._speeds[name] = {
                            'down_kbps': round(down_bps / 1000, 1),
                            'up_kbps': round(up_bps / 1000, 1),
                        }
                    self._totals[name] = {'ibytes': ibytes, 'obytes': obytes}
                self._prev[name] = (ibytes, obytes, now)

            self._active_iface = self._get_active_interface()

    def get_stats(self):
        """Get current traffic stats as a dict."""
        with self._lock:
            iface = self._active_iface or 'en0'
            result = {
                'active_interface': iface,
                'interfaces': {},
            }

            all_ifaces = set(list(self._speeds.keys()) + list(self._totals.keys()))
            if not all_ifaces:
                result['interfaces'][iface] = {
                    'down_kbps': 0, 'up_kbps': 0,
                    'down_mbps': 0, 'up_mbps': 0,
                    'total_mb_down': 0, 'total_mb_up': 0,
                }
                return result

            for name in sorted(all_ifaces):
                speed = self._speeds.get(name, {'down_kbps': 0, 'up_kbps': 0})
                total = self._totals.get(name, {'ibytes': 0, 'obytes': 0})
                result['interfaces'][name] = {
                    'down_kbps': speed['down_kbps'],
                    'up_kbps': speed['up_kbps'],
                    'down_mbps': round(speed['down_kbps'] / 1000, 1),
                    'up_mbps': round(speed['up_kbps'] / 1000, 1),
                    'total_mb_down': round(total['ibytes'] / (1024*1024), 1),
                    'total_mb_up': round(total['obytes'] / (1024*1024), 1),
                }
            return result


# Singleton
_monitor = TrafficMonitor()


def get_traffic_stats():
    """Thread-safe convenience to get current traffic stats."""
    try:
        _monitor.update()
        return _monitor.get_stats()
    except Exception:
        return {
            'active_interface': 'en0',
            'interfaces': {'en0': {
                'down_kbps': 0, 'up_kbps': 0,
                'down_mbps': 0, 'up_mbps': 0,
                'total_mb_down': 0, 'total_mb_up': 0,
            }},
            'error': 'Failed to read traffic stats',
        }


def format_speed(kbps):
    """Human-readable speed string."""
    try:
        if kbps >= 1000:
            return f"{kbps / 1000:.1f} Mbps"
        return f"{kbps:.0f} Kbps"
    except Exception:
        return "0 Kbps"
