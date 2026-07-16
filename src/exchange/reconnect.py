import asyncio


class ReconnectManager:

    def __init__(self, retries=5, delay=3):
        self.retries = retries
        self.delay = delay

    async def retry(self, func, *args, **kwargs):

        for attempt in range(1, self.retries + 1):

            try:
                return await func(*args, **kwargs)

            except Exception as e:

                print(f"Reconnect Attempt {attempt}: {e}")

                await asyncio.sleep(self.delay)

        raise ConnectionError("Maximum reconnect attempts reached.")