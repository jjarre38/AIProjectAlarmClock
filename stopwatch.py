"""Simple start/stop timer, independent of any vision code."""

import time


class Stopwatch:
    def __init__(self):
        self._start_time = None   # set while running
        self._elapsed = 0.0       # accumulated time from previous runs

    @property
    def running(self) -> bool:
        return self._start_time is not None

    def start(self):
        if not self.running:
            self._start_time = time.perf_counter()

    def stop(self):
        if self.running:
            self._elapsed += time.perf_counter() - self._start_time
            self._start_time = None

    def toggle(self):
        self.stop() if self.running else self.start()

    def reset(self):
        self._start_time = None
        self._elapsed = 0.0

    def elapsed(self) -> float:
        if self.running:
            return self._elapsed + (time.perf_counter() - self._start_time)
        return self._elapsed

    def formatted(self) -> str:
        total = self.elapsed()
        minutes, seconds = divmod(total, 60)
        return f"{int(minutes):02d}:{seconds:05.2f}"
