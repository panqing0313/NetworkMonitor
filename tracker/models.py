"""Data models for network devices."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Device:
    """Represents a discovered network device."""
    ip: str
    mac: str = ""
    hostname: str = ""
    vendor: str = "Unknown"
    interface: str = ""
    online: bool = False
    rtt_ms: Optional[float] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_random_mac: bool = False
    device_type: str = "Unknown"  # Computer, Phone, Router, IoT, etc.
    notes: str = ""

    def to_dict(self):
        return {
            'ip': self.ip,
            'mac': self.mac,
            'hostname': self.hostname,
            'vendor': self.vendor,
            'interface': self.interface,
            'online': self.online,
            'rtt_ms': self.rtt_ms,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_random_mac': self.is_random_mac,
            'device_type': self.device_type,
            'notes': self.notes,
        }

    @staticmethod
    def from_dict(d):
        return Device(
            ip=d.get('ip', ''),
            mac=d.get('mac', ''),
            hostname=d.get('hostname', ''),
            vendor=d.get('vendor', 'Unknown'),
            interface=d.get('interface', ''),
            online=d.get('online', False),
            rtt_ms=d.get('rtt_ms'),
            first_seen=datetime.fromisoformat(d['first_seen']) if d.get('first_seen') else None,
            last_seen=datetime.fromisoformat(d['last_seen']) if d.get('last_seen') else None,
            is_random_mac=d.get('is_random_mac', False),
            device_type=d.get('device_type', 'Unknown'),
            notes=d.get('notes', ''),
        )
