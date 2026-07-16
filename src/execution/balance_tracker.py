from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AssetBalance:

    asset: str

    free: float

    locked: float

    @property
    def total(self) -> float:

        return self.free + self.locked


class BalanceTracker:

    def __init__(self):

        self._balances: dict[str, AssetBalance] = {}

    def update(

        self,

        asset: str,

        free: float,

        locked: float,

    ) -> None:

        self._balances[asset] = AssetBalance(

            asset=asset,

            free=free,

            locked=locked,

        )

    def get(

        self,

        asset: str,

    ) -> AssetBalance | None:

        return self._balances.get(asset)

    def exists(

        self,

        asset: str,

    ) -> bool:

        return asset in self._balances

    def total_balance(self) -> float:

        return sum(

            balance.total

            for balance in self._balances.values()

        )

    def all_balances(self):

        return list(self._balances.values())