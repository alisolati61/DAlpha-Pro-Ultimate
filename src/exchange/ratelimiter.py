import time


class RateLimiter:

    def __init__(self, requests_per_second: float = 5):
        self.requests_per_second = requests_per_second
        self.last_request = 0.0

    def wait(self):
        now = time.time()

        elapsed = now - self.last_request

        minimum_interval = 1 / self.requests_per_second

        if elapsed < minimum_interval:
            time.sleep(minimum_interval - elapsed)

        self.last_request = time.time()