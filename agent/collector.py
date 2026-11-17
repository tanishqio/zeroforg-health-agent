"""Collect machine stats for one sample: system, disks, network and processes.

Counters such as "bytes received" only ever grow, so a rate (bytes per second)
is the difference between two readings divided by the time between them.
"""

import logging
import time
from pathlib import Path

import psutil

log = logging.getLogger(__name__)

MB = 1024 * 1024  # bytes in one MiB, the unit `free -m` uses

# Class for calculating rates: we need per-second data,
# not totals counted from when the machine started.
class RateTracker:
    def __init__(self) -> None:
        # key -> (counter value, monotonic time it was read)
        self._last: dict[str, tuple[float, float]] = {}

    # Records new readings and returns a rate for every key that has a valid one.
    def update(self, counters: dict[str, float], now: float | None = None) -> dict[str, float]:
        if now is None:
            now = time.monotonic()

        rates: dict[str, float] = {}
        for key, value in counters.items():
            previous = self._last.get(key)
            self._last[key] = (value, now)
            if previous is None:
                continue  # first reading: nothing to compare with yet
            prev_val, prev_time = previous
            elapsed = now - prev_time
            delta = value - prev_val
            if elapsed <= 0 or delta < 0:
                continue  # clock did not move, or the counter reset
            rates[key] = delta / elapsed

        # Forget keys that vanished so memory stays flat.
        for key in self._last.keys() - counters.keys():
            del self._last[key]
        return rates

class Collector:
    def __init__(self) -> None:
        self._cpu_ready = False  # psutil's first CPU reading has no baseline
        self._disk_io_tracker = RateTracker()

    def collect_metrics(self) -> dict[str, float]:
        metrics: dict[str, float] = {}
        for read in (self._cpu, self._memory, self._load_and_uptime, self._disk_io_rates):
            try:
                metrics.update(read())
            except Exception:
                log.exception("collector: %s failed", read.__name__)
        return metrics

    def _cpu(self) -> dict[str, float]:
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        if not self._cpu_ready:
            self._cpu_ready = True
            return {}  # first call only sets the baseline
        metrics = {f"cpu.core{i}_pct": pct for i, pct in enumerate(per_core)}
        metrics["cpu.total_pct"] = sum(per_core) / len(per_core)
        return metrics

    def _memory(self) -> dict[str, float]:
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "mem.used_pct": ram.percent,
            "mem.available_mb": ram.available / MB,
            "swap.used_pct": swap.percent,
            "swap.used_mb": swap.used / MB,
        }

    def _load_and_uptime(self) -> dict[str, float]:
        load_1m, load_5m, load_15m = psutil.getloadavg()
        uptime_s = float(Path("/proc/uptime").read_text().split()[0])
        return {
            "load.1m": load_1m,
            "load.5m": load_5m,
            "load.15m": load_15m,
            "system.uptime_s": uptime_s,
        }

    def _disk_io_rates(self) -> dict[str, float]:
        io = psutil.disk_io_counters(perdisk=False, nowrap=False)
        if io is None:
            return {}
        return self._disk_io_tracker.update({
            "diskio.read_bytes_per_s": io.read_bytes,
            "diskio.write_bytes_per_s": io.write_bytes,
        })

if __name__ == "__main__":
    collector = Collector()
    collector.collect_metrics()  # first call sets the CPU and disk baselines
    time.sleep(5)
    for name, value in collector.collect_metrics().items():
        print(f"{name:28} {value:>14,.2f}")
