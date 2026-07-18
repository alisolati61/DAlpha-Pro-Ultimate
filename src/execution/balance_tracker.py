from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass


@dataclass(slots=True)
class AssetBalance:

    asset: str

    free: float

    locked: float

    @property
    def total(
        self,
    ) -> float:

        return float(
            self.free + self.locked
        )


class BalanceTracker:

    def __init__(
        self,
    ) -> None:

        self._balances: dict[
            str,
            AssetBalance,
        ] = {}

    @staticmethod
    def _validate_asset(
        asset: str,
    ) -> str:

        if not isinstance(
            asset,
            str,
        ):

            raise TypeError(
                "asset must be a string."
            )

        asset = asset.strip().upper()

        if not asset:

            raise ValueError(
                "asset cannot be empty."
            )

        return asset

    @staticmethod
    def _validate_amount(
        value: float,
        name: str,
    ) -> float:

        if isinstance(
            value,
            bool,
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        value = float(value)

        if not math.isfinite(
            value
        ):

            raise ValueError(
                f"{name} must be finite."
            )

        if value < 0:

            raise ValueError(
                f"{name} cannot be negative."
            )

        return value

    @classmethod
    def _validate_balance(
        cls,
        asset: str,
        free: float,
        locked: float,
    ) -> AssetBalance:

        asset = cls._validate_asset(
            asset
        )

        free = cls._validate_amount(
            free,
            "free",
        )

        locked = cls._validate_amount(
            locked,
            "locked",
        )

        return AssetBalance(
            asset=asset,
            free=free,
            locked=locked,
        )

    def update(
        self,
        asset: str,
        free: float,
        locked: float,
    ) -> None:

        balance = self._validate_balance(
            asset=asset,
            free=free,
            locked=locked,
        )

        self._balances[
            balance.asset
        ] = balance

    def get(
        self,
        asset: str,
    ) -> AssetBalance | None:

        asset = self._validate_asset(
            asset
        )

        balance = self._balances.get(
            asset
        )

        if balance is None:

            return None

        return deepcopy(
            balance
        )

    def exists(
        self,
        asset: str,
    ) -> bool:

        asset = self._validate_asset(
            asset
        )

        return asset in self._balances

    def total_balance(
        self,
    ) -> float:

        return float(
            sum(
                balance.total
                for balance
                in self._balances.values()
            )
        )

    def all_balances(
        self,
    ) -> list[AssetBalance]:

        return [
            deepcopy(balance)
            for balance
            in self._balances.values()
        ]

    def count(
        self,
    ) -> int:

        return len(
            self._balances
        )

    def clear(
        self,
    ) -> None:

        self._balances.clear()