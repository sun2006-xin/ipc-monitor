"""Deterministic, non-blocking reconnect backoff for camera streams."""


class ReconnectPolicy:
    def __init__(self, initial_delay=0.5, max_delay=8.0):
        if initial_delay <= 0 or max_delay < initial_delay:
            raise ValueError("invalid reconnect delay bounds")
        self.initial_delay = float(initial_delay)
        self.max_delay = float(max_delay)
        self.attempts = 0
        self.delay = 0.0
        self.next_attempt_at = 0.0

    def reset(self, now):
        self.attempts = 0
        self.delay = 0.0
        self.next_attempt_at = float(now)

    def can_attempt(self, now):
        return float(now) >= self.next_attempt_at

    def failed(self, now):
        self.attempts += 1
        self.delay = min(self.initial_delay * (2 ** (self.attempts - 1)), self.max_delay)
        self.next_attempt_at = float(now) + self.delay
