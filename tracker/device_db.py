"""SQLite database for persistent device tracking.

Tracks:
- Device list with metadata
- Online/offline history
- First seen / last seen timestamps
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional
from .models import Device

DB_DIR = os.path.join(os.path.expanduser('~'), '.network-monitor', 'data')
DB_PATH = os.path.join(DB_DIR, 'network_monitor.db')


def _get_connection():
    """Get database connection (creates DB if needed)."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                ip TEXT PRIMARY KEY,
                mac TEXT NOT NULL DEFAULT '',
                hostname TEXT NOT NULL DEFAULT '',
                vendor TEXT NOT NULL DEFAULT 'Unknown',
                interface TEXT NOT NULL DEFAULT '',
                online INTEGER NOT NULL DEFAULT 0,
                rtt_ms REAL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                is_random_mac INTEGER NOT NULL DEFAULT 0,
                device_type TEXT NOT NULL DEFAULT 'Unknown',
                notes TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS device_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                online INTEGER NOT NULL,
                rtt_ms REAL,
                hostname TEXT DEFAULT '',
                FOREIGN KEY (ip) REFERENCES devices(ip)
            );

            CREATE INDEX IF NOT EXISTS idx_history_ip ON device_history(ip);
            CREATE INDEX IF NOT EXISTS idx_history_ts ON device_history(timestamp);
        """)
        conn.commit()
    finally:
        conn.close()


def get_all_devices():
    """Get all tracked devices."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM devices ORDER BY online DESC, last_seen DESC"
        ).fetchall()
        return [_row_to_device(r) for r in rows]
    finally:
        conn.close()


def get_device(ip):
    """Get a single device by IP."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM devices WHERE ip = ?", (ip,)
        ).fetchone()
        return _row_to_device(row) if row else None
    finally:
        conn.close()


def _row_to_device(row):
    return Device(
        ip=row['ip'],
        mac=row['mac'],
        hostname=row['hostname'],
        vendor=row['vendor'],
        interface=row['interface'],
        online=bool(row['online']),
        rtt_ms=row['rtt_ms'],
        first_seen=datetime.fromisoformat(row['first_seen']),
        last_seen=datetime.fromisoformat(row['last_seen']),
        is_random_mac=bool(row['is_random_mac']),
        device_type=row['device_type'],
        notes=row['notes'],
    )


def upsert_device(device: Device):
    """Insert or update a device record.

    Returns True if online status changed (significant event).
    """
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT online, first_seen FROM devices WHERE ip = ?",
            (device.ip,)
        ).fetchone()

        now = datetime.now().isoformat()
        status_changed = False
        first_seen = now

        if existing:
            first_seen = existing['first_seen']
            was_online = bool(existing['online'])
            if was_online != device.online:
                status_changed = True

        conn.execute("""
            INSERT INTO devices (ip, mac, hostname, vendor, interface,
                                 online, rtt_ms, first_seen, last_seen,
                                 is_random_mac, device_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                mac = excluded.mac,
                hostname = excluded.hostname,
                vendor = excluded.vendor,
                interface = excluded.interface,
                online = excluded.online,
                rtt_ms = excluded.rtt_ms,
                last_seen = excluded.last_seen,
                is_random_mac = excluded.is_random_mac,
                device_type = excluded.device_type,
                notes = excluded.notes
        """, (
            device.ip, device.mac, device.hostname, device.vendor,
            device.interface, int(device.online), device.rtt_ms,
            first_seen, now,
            int(device.is_random_mac), device.device_type, device.notes,
        ))

        # Always log to history
        conn.execute("""
            INSERT INTO device_history (ip, timestamp, online, rtt_ms, hostname)
            VALUES (?, ?, ?, ?, ?)
        """, (device.ip, now, int(device.online), device.rtt_ms, device.hostname))

        conn.commit()
        return status_changed
    finally:
        conn.close()


def get_device_history(ip, limit=100):
    """Get online/offline history for a specific device.

    Returns list of {timestamp, online, rtt_ms, hostname}
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT timestamp, online, rtt_ms, hostname
               FROM device_history
               WHERE ip = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (ip, limit)
        ).fetchall()
        return [{
            'timestamp': r['timestamp'],
            'online': bool(r['online']),
            'rtt_ms': r['rtt_ms'],
            'hostname': r['hostname'],
        } for r in rows]
    finally:
        conn.close()


def get_online_devices():
    """Get currently online devices."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM devices WHERE online = 1 ORDER BY hostname"
        ).fetchall()
        return [_row_to_device(r) for r in rows]
    finally:
        conn.close()


def get_offline_devices():
    """Get currently offline devices."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM devices WHERE online = 0 ORDER BY last_seen DESC"
        ).fetchall()
        return [_row_to_device(r) for r in rows]
    finally:
        conn.close()


def get_stats():
    """Get database statistics."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        online = conn.execute("SELECT COUNT(*) FROM devices WHERE online = 1").fetchone()[0]
        new_today = conn.execute(
            "SELECT COUNT(*) FROM devices WHERE first_seen >= date('now')"
        ).fetchone()[0]
        events_24h = conn.execute(
            "SELECT COUNT(*) FROM device_history WHERE timestamp >= datetime('now', '-1 day')"
        ).fetchone()[0]
        return {
            'total_devices': total,
            'online_now': online,
            'new_today': new_today,
            'events_24h': events_24h,
            'db_path': DB_PATH,
        }
    finally:
        conn.close()


def get_timeline(hours=24):
    """Get timeline of online/offline events.

    Returns list of {timestamp, ip, hostname, event}
    where event is 'online' or 'offline'.
    """
    conn = _get_connection()
    try:
        # Get history entries with changes (compare consecutive records)
        rows = conn.execute("""
            SELECT h1.timestamp, h1.ip, h1.online, h1.hostname
            FROM device_history h1
            WHERE h1.timestamp >= datetime('now', ?)
            ORDER BY h1.timestamp DESC
            LIMIT 500
        """, (f'-{hours} hours',)).fetchall()

        events = []
        for r in rows:
            events.append({
                'timestamp': r['timestamp'],
                'ip': r['ip'],
                'hostname': r['hostname'],
                'event': 'online' if r['online'] else 'offline',
            })
        return events
    finally:
        conn.close()
