"""Network activity monitor - packet capture and analysis.

Uses tcpdump (macOS) to capture live network packets and
provides a real-time view of ALL network activity on the LAN.

Falls back to netstat-based monitoring if tcpdump requires root.
"""

import subprocess
import re
import time
import os
import signal
import threading
from collections import defaultdict, Counter
from datetime import datetime
from .platform_utils import IS_MAC, IS_WIN


class ActivityMonitor:
    """Monitors all network activity on the local interface."""

    def __init__(self, max_entries=200):
        self._lock = threading.Lock()
        self._process = None
        self._entries = []
        self._max_entries = max_entries
        self._running = False
        self._stats = Counter()
        self._tcpdump_available = False
        self._thread = None

    def _check_tcpdump(self):
        """Check if tcpdump works (with or without sudo)."""
        # Try without sudo first
        try:
            r = subprocess.run(
                ['tcpdump', '-n', '-c', '1', '-t', '-q', '-i', 'lo0'],
                capture_output=True, text=True, timeout=3
            )
            self._tcpdump_available = r.returncode == 0
            return self._tcpdump_available
        except:
            pass

        # Try with sudo -n (non-interactive)
        try:
            r = subprocess.run(
                ['sudo', '-n', 'tcpdump', '-n', '-c', '1', '-t', '-q', '-i', 'lo0'],
                capture_output=True, text=True, timeout=3
            )
            self._tcpdump_available = r.returncode == 0
            return self._tcpdump_available
        except:
            self._tcpdump_available = False
            return False

    def _parse_packet_line(self, line):
        """Parse a single tcpdump output line into a structured entry."""
        # Skip non-data lines
        if not line or line.startswith('tcpdump:'):
            return None

        # Patterns for different packet types
        # ARP: ARP, Request who-has 192.168.1.1 tell 192.168.1.100, length 42
        # DNS: IP 192.168.1.100.54321 > 8.8.8.8.53: 12345+ A? google.com. (35)
        # TCP: IP 192.168.1.100.54321 > 93.184.216.34.80: Flags [S], seq ...
        # UDP: IP 192.168.1.100.54321 > 8.8.8.8.53: 12345+ A? ...

        entry = {
            'time': datetime.now().isoformat(),
            'src': '', 'dst': '', 'protocol': '',
            'info': '', 'size': 0, 'type': 'packet',
        }

        # ARP
        arp_m = re.search(r'ARP,\s*(Request|Reply)\s+([^,]+)', line)
        if arp_m:
            entry['protocol'] = 'ARP'
            entry['info'] = arp_m.group(0)
            # Extract IPs from ARP
            ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', line)
            if len(ips) >= 2:
                entry['src'], entry['dst'] = ips[0], ips[1]
            elif len(ips) == 1:
                entry['src'] = ips[0]
            return entry

        # IP packets: "IP src > dst: ..."
        ip_m = re.match(r'IP\s+(\S+)\s*>\s*(\S+):\s*(.*)', line)
        if ip_m:
            src_raw, dst_raw, rest = ip_m.group(1), ip_m.group(2), ip_m.group(3)
            entry['src'] = src_raw
            entry['dst'] = dst_raw

            # Detect protocol from port or content
            if '53:' in rest or '.53:' in rest:
                entry['protocol'] = 'DNS'
                dns_m = re.search(r'([A-Za-z0-9._-]+\.[A-Za-z]{2,})', rest)
                if dns_m:
                    entry['info'] = f'DNS Query: {dns_m.group(1)}'
                else:
                    entry['info'] = rest[:80]
            elif 'Flags [' in rest:
                flags = re.search(r'Flags\s+\[([^\]]+)\]', rest)
                flag_str = flags.group(1) if flags else ''
                entry['protocol'] = 'TCP'
                if 'S' in flag_str and 'A' not in flag_str:
                    entry['info'] = f'SYN → {"ESTABLISH" if "S." not in flag_str else ""}'
                elif 'F' in flag_str:
                    entry['info'] = 'FIN (CLOSE)'
                elif 'R' in flag_str:
                    entry['info'] = 'RST (RESET)'
                else:
                    entry['info'] = rest[:80]
            elif rest.strip().startswith('UDP'):
                entry['protocol'] = 'UDP'
                entry['info'] = rest[:80]
            else:
                entry['protocol'] = 'IP'
                entry['info'] = rest[:80]

            # Extract size
            size_m = re.search(r'length\s+(\d+)', rest)
            if size_m:
                entry['size'] = int(size_m.group(1))

            return entry

        # Non-IP (e.g. IPv6, ICMPv6)
        if re.match(r'ICMP|IGMP|IPv6', line):
            entry['protocol'] = line.split()[0]
            entry['info'] = line[:100]
            ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', line)
            if len(ips) >= 1:
                entry['src'] = ips[0]
            return entry

        return None

    def _capture_thread(self):
        """Background thread that runs tcpdump and captures packets."""
        if not self._tcpdump_available:
            return

        # Determine interface
        iface = 'en0'
        try:
            out = subprocess.check_output(
                ['route', '-n', 'get', 'default'], text=True, timeout=3
            )
            m = re.search(r'interface:\s+(\S+)', out)
            if m:
                iface = m.group(1)
        except:
            pass

        cmd = ['tcpdump', '-n', '-t', '-q', '-i', iface, '-l']  # -l = line buffered
        # Try sudo
        try:
            proc = subprocess.Popen(
                ['sudo', '-n'] + cmd,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1
            )
        except:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, bufsize=1
                )
            except:
                self._tcpdump_available = False
                return

        self._process = proc
        self._running = True

        try:
            for line in proc.stdout:
                if not self._running:
                    break
                entry = self._parse_packet_line(line.strip())
                if entry:
                    with self._lock:
                        self._entries.append(entry)
                        self._stats[entry['protocol']] += 1
                        # Trim
                        if len(self._entries) > self._max_entries:
                            self._entries = self._entries[-self._max_entries:]
        except (BrokenPipeError, OSError):
            pass
        finally:
            self._running = False

    def start(self):
        """Start capturing network activity."""
        if self._running:
            return

        self._check_tcpdump()
        if not self._tcpdump_available:
            # Fallback: use netstat polling
            self._start_netstat_fallback()
            return

        self._thread = threading.Thread(target=self._capture_thread, daemon=True)
        self._thread.start()

    def _start_netstat_fallback(self):
        """Fallback: poll netstat for new connections."""
        self._running = True
        known_conns = set()

        def poll():
            while self._running:
                try:
                    out = subprocess.check_output(
                        ['netstat', '-an', '-p', 'tcp'],
                        text=True, timeout=3, stderr=subprocess.DEVNULL
                    )
                    for line in out.splitlines():
                        if 'ESTABLISHED' in line and '127.0.0.1' not in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                key = parts[3] + '>' + parts[4]
                                if key not in known_conns:
                                    known_conns.add(key)
                                    entry = {
                                        'time': datetime.now().isoformat(),
                                        'src': parts[3], 'dst': parts[4],
                                        'protocol': 'TCP',
                                        'info': 'New Connection',
                                        'size': 0, 'type': 'connection',
                                    }
                                    with self._lock:
                                        self._entries.append(entry)
                                        self._stats['TCP'] += 1
                                        if len(self._entries) > self._max_entries:
                                            self._entries = self._entries[-self._max_entries:]
                except:
                    pass
                time.sleep(2)

        self._thread = threading.Thread(target=poll, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop capturing."""
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except:
                try:
                    self._process.kill()
                except:
                    pass

    def get_activity(self):
        """Get current activity data.

        Returns dict with entries, stats, and status.
        """
        with self._lock:
            entries = list(self._entries)
            stats = dict(self._stats)

        # Aggregate by protocol
        protocols = []
        for proto, count in stats.most_common():
            protocols.append({'protocol': proto, 'count': count})

        # Recent activity by type
        recent = entries[-50:] if entries else []

        return {
            'capturing': self._running,
            'tcpdump': self._tcpdump_available,
            'total_events': len(entries),
            'protocols': protocols,
            'recent': list(reversed(recent)),
            'method': 'tcpdump' if self._tcpdump_available else 'netstat',
        }


# Global singleton
_monitor = ActivityMonitor()


def get_activity():
    """Get current network activity (thread-safe)."""
    return _monitor.get_activity()


def start_monitoring():
    """Start the activity monitor."""
    _monitor.start()
