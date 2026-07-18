from __future__ import annotations

import asyncio


class ReconnectManager:
    """
    Handles automatic reconnection attempts.

    Features
    --------
    - Configurable retry count
    - Configurable delay
    - Async compatible
    """

    def __init__(
        self,
        retries: int = 5,
        delay: float = 1.0,
    ) -> None:

        if retries < 0:
            raise ValueError("retries must be >= 0")

        if delay < 0:
            raise ValueError("delay must be >= 0")

        self._retries = retries
        self._delay = delay

    # ------------------------------------------------

    @property
    def retries(self) -> int:
        return self._retries

    @property
    def delay(self) -> float:
        return self._delay

    # ------------------------------------------------

    async def run(
        self,
        connect_callback,
    ) -> bool:

        for _ in range(self._retries):

            try:

                result = await connect_callback()

                if result is not False:
                    return True

            except Exception:
                pass

            if self._delay > 0:
                await asyncio.sleep(self._delay)

        return False