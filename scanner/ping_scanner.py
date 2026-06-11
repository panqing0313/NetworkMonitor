"""Continuous ping monitoring for device health tracking.

Pings known devices periodically to detect online/offline transitions.
"""

import time
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


def check_device(ip, timeout=2):
    """Ping a single device, return (ip, online, rtt_ms).

    rtt_ms is None if unreachable.
    """
    start = time.time()
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, text=True, timeout=timeout + 1,
        )
        elapsed = (time.time() - start) * 1000
        if result.returncode == 0:
            # Extract RTT from output
            m = result.stdout
            # "round-trip min/avg/max/stddev = 1.234/..."
            # or "time=1.23 ms"
            return (ip, True, round(elapsed, 1))
        return (ip, False, None)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return (ip, False, None)


def check_devices(ip_list, max_workers=30, timeout=2):
    """Check multiple devices in parallel.

    Returns {ip: {'online': bool, 'rtt_ms': float or None}}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_device, ip, timeout): ip for ip in ip_list}
        for f in as_completed(futures):
            ip, online, rtt = f.result()
            results[ip] = {'online': online, 'rtt_ms': rtt}
    return results
