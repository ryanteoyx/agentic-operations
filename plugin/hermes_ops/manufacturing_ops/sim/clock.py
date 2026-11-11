from __future__ import annotations


class SimulatedClock:
    def __init__(self, hour: int = 0):
        self.hour = hour

    def advance(self, hours: int) -> int:
        if not isinstance(hours, int) or isinstance(hours, bool) or hours < 0:
            raise ValueError("advance hours must be a nonnegative whole number")
        self.hour += hours
        return self.hour
