from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Sequence


@dataclass(slots=True)
class WalkForwardWindow:
    train_start: int
    train_end: int

    test_start: int
    test_end: int


class WalkForward:
    """
    Rolling Walk Forward window generator.
    """

    def generate(
        self,
        data: Sequence,
        train_size: float = 0.7,
        test_size: float = 0.2,
        step: float = 0.1,
    ) -> list[WalkForwardWindow]:

        total = len(data)

        if total == 0:
            return []

        train = max(1, floor(total * train_size))

        test = max(1, floor(total * test_size))

        stride = max(
            1,
            floor(total * step),
        )

        windows: list[WalkForwardWindow] = []

        start = 0

        while True:

            train_start = start
            train_end = train_start + train

            test_start = train_end
            test_end = test_start + test

            if test_end > total:
                break

            windows.append(
                WalkForwardWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            start += stride

        return windows