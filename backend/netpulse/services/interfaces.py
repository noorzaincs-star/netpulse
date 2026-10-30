import time
from typing import Any

import psutil


class InterfaceSampler:
    def __init__(self) -> None:
        self._previous: dict[str, tuple[int, int, float]] = {}

    def snapshot(self) -> dict[str, Any]:
        sampled_at = time.monotonic()
        counters = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        interfaces: list[dict[str, Any]] = []
        current: dict[str, tuple[int, int, float]] = {}
        for name, counter in counters.items():
            sent = int(counter.bytes_sent)
            received = int(counter.bytes_recv)
            previous = self._previous.get(name)
            sent_rate = None
            received_rate = None
            reset = False
            if previous is not None:
                old_sent, old_received, old_sampled_at = previous
                elapsed = sampled_at - old_sampled_at
                if sent >= old_sent and received >= old_received and elapsed > 0:
                    sent_rate = (sent - old_sent) / elapsed
                    received_rate = (received - old_received) / elapsed
                else:
                    reset = True
            current[name] = (sent, received, sampled_at)
            interface_stats = stats.get(name)
            interfaces.append(
                {
                    "name": name,
                    "is_up": interface_stats.isup if interface_stats else None,
                    "speed_mbps": interface_stats.speed if interface_stats else None,
                    "mtu": interface_stats.mtu if interface_stats else None,
                    "bytes_sent": sent,
                    "bytes_received": received,
                    "bytes_sent_per_second": sent_rate,
                    "bytes_received_per_second": received_rate,
                    "counter_reset": reset,
                    "rate_available": sent_rate is not None and received_rate is not None,
                }
            )
        self._previous = current
        return {
            "scope": "local_host_interfaces",
            "sampled_at": time.time(),
            "note": "Counters and rates are for this host's interfaces, not per-device bandwidth.",
            "interfaces": interfaces,
        }
