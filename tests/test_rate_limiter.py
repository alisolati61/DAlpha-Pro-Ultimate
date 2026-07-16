import time

from src.exchange.ratelimiter import RateLimiter

limiter = RateLimiter(requests_per_second=2)

for i in range(5):
    start = time.time()

    limiter.wait()

    print(f"Request {i+1} -> {time.time()-start:.3f} sec")