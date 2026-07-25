"""Thread-safe validated in-memory asset balance tracking.

``AssetBalance`` remains a mutable transport model for compatibility with
exchange adapters. ``BalanceTracker`` stores and returns defensive copies so
external mutation cannot corrupt tracked state.

The legacy ``total_balance`` method is preserved even though it simply sums
numeric balances across assets without currency conversion.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from math import fsum, isfinite
from numbers import Real
from threading import RLock

_MAX_ASSET_LENGTH = 100


@dataclass(slots=True)
class AssetBalance:
    """Mutable transport snapshot for one asset balance."""

    asset: str
    free: float
    locked: float

    @property
    def total(self) -> float:
        """Return free plus locked balance."""

        return float(
            self.free + self.locked
        )

    @property
    def is_empty(self) -> bool:
        """Return whether both balance components are zero."""

        return (
            self.free == 0.0
            and self.locked == 0.0
        )


class BalanceTracker:
    """Thread-safe in-memory tracker for normalized asset balances."""

    __slots__ = (
        "_balances",
        "_lock",
    )

    def __init__(self) -> None:
        self._balances: dict[
            str,
            AssetBalance,
        ] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_asset(
        asset: object,
    ) -> str:
        if not isinstance(asset, str):
            raise TypeError(
                "asset must be a string."
            )

        normalized = asset.strip().upper()

        if not normalized:
            raise ValueError(
                "asset cannot be empty."
            )

        if len(normalized) > _MAX_ASSET_LENGTH:
            raise ValueError(
                "asset must not exceed "
                f"{_MAX_ASSET_LENGTH} characters."
            )

        return normalized

    @staticmethod
    def _validate_amount(
        value: object,
        name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{name} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{name} must be finite."
            )

        if normalized < 0.0:
            raise ValueError(
                f"{name} cannot be negative."
            )

        return normalized

    @classmethod
    def _validate_balance(
        cls,
        asset: object,
        free: object,
        locked: object,
    ) -> AssetBalance:
        normalized_asset = cls._validate_asset(
            asset
        )
        normalized_free = cls._validate_amount(
            free,
            "free",
        )
        normalized_locked = cls._validate_amount(
            locked,
            "locked",
        )

        total = normalized_free + normalized_locked

        if not isfinite(total):
            raise ValueError(
                "balance total must be finite."
            )

        return AssetBalance(
            asset=normalized_asset,
            free=normalized_free,
            locked=normalized_locked,
        )

    @classmethod
    def _normalize_balance(
        cls,
        balance: object,
    ) -> AssetBalance:
        if not isinstance(
            balance,
            AssetBalance,
        ):
            raise TypeError(
                "balance must be an AssetBalance."
            )

        return cls._validate_balance(
            balance.asset,
            balance.free,
            balance.locked,
        )

    @staticmethod
    def _normalize_balances_iterable(
        balances: object,
    ) -> tuple[AssetBalance, ...]:
        if (
            isinstance(
                balances,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not isinstance(
                balances,
                Iterable,
            )
        ):
            raise TypeError(
                "balances must be an iterable "
                "of AssetBalance objects."
            )

        normalized = tuple(
            BalanceTracker._normalize_balance(
                balance
            )
            for balance in balances
        )

        assets = tuple(
            balance.asset
            for balance in normalized
        )

        if len(assets) != len(set(assets)):
            raise ValueError(
                "Duplicate asset in balances."
            )

        return normalized

    def update(
        self,
        asset: str,
        free: float,
        locked: float,
    ) -> None:
        """Insert or replace one normalized asset balance."""

        balance = self._validate_balance(
            asset=asset,
            free=free,
            locked=locked,
        )

        with self._lock:
            self._balances[
                balance.asset
            ] = deepcopy(balance)

    def update_many(
        self,
        balances: Iterable[AssetBalance],
    ) -> int:
        """Atomically insert or replace multiple balances.

        Every balance is validated before internal state changes. Duplicate
        normalized assets inside the input batch are rejected.

        Returns:
            Number of balances processed.
        """

        normalized = (
            self._normalize_balances_iterable(
                balances
            )
        )

        with self._lock:
            for balance in normalized:
                self._balances[
                    balance.asset
                ] = deepcopy(balance)

        return len(normalized)

    def replace_all(
        self,
        balances: Iterable[AssetBalance],
    ) -> int:
        """Atomically replace the complete tracked balance snapshot."""

        normalized = (
            self._normalize_balances_iterable(
                balances
            )
        )
        replacement = {
            balance.asset: deepcopy(balance)
            for balance in normalized
        }

        with self._lock:
            self._balances = replacement

        return len(normalized)

    def get(
        self,
        asset: str,
    ) -> AssetBalance | None:
        """Return a defensive copy, or ``None`` when missing."""

        normalized_asset = self._validate_asset(
            asset
        )

        with self._lock:
            balance = self._balances.get(
                normalized_asset
            )

            if balance is None:
                return None

            return deepcopy(balance)

    def require(
        self,
        asset: str,
    ) -> AssetBalance:
        """Return one balance or raise ``KeyError`` when missing."""

        normalized_asset = self._validate_asset(
            asset
        )

        with self._lock:
            balance = self._balances.get(
                normalized_asset
            )

            if balance is None:
                raise KeyError(
                    f"Unknown asset: {normalized_asset}"
                )

            return deepcopy(balance)

    def exists(
        self,
        asset: str,
    ) -> bool:
        """Return whether a normalized asset is tracked."""

        normalized_asset = self._validate_asset(
            asset
        )

        with self._lock:
            return (
                normalized_asset
                in self._balances
            )

    def remove(
        self,
        asset: str,
    ) -> AssetBalance:
        """Remove and return one defensive balance copy."""

        normalized_asset = self._validate_asset(
            asset
        )

        with self._lock:
            try:
                balance = self._balances.pop(
                    normalized_asset
                )
            except KeyError as error:
                raise KeyError(
                    f"Unknown asset: {normalized_asset}"
                ) from error

            return deepcopy(balance)

    def total_balance(self) -> float:
        """Return the legacy numeric sum of all free and locked balances."""

        with self._lock:
            values = tuple(
                value
                for balance
                in self._balances.values()
                for value
                in (
                    balance.free,
                    balance.locked,
                )
            )

        try:
            total = fsum(values)
        except OverflowError as error:
            raise ValueError(
                "aggregate balance must be finite."
            ) from error

        if not isfinite(total):
            raise ValueError(
                "aggregate balance must be finite."
            )

        return float(total)

    def total_free(self) -> float:
        """Return the numeric sum of all free balances."""

        with self._lock:
            values = tuple(
                balance.free
                for balance
                in self._balances.values()
            )

        try:
            total = fsum(values)
        except OverflowError as error:
            raise ValueError(
                "aggregate free balance "
                "must be finite."
            ) from error

        if not isfinite(total):
            raise ValueError(
                "aggregate free balance "
                "must be finite."
            )

        return float(total)

    def total_locked(self) -> float:
        """Return the numeric sum of all locked balances."""

        with self._lock:
            values = tuple(
                balance.locked
                for balance
                in self._balances.values()
            )

        try:
            total = fsum(values)
        except OverflowError as error:
            raise ValueError(
                "aggregate locked balance "
                "must be finite."
            ) from error

        if not isfinite(total):
            raise ValueError(
                "aggregate locked balance "
                "must be finite."
            )

        return float(total)

    def all_balances(
        self,
    ) -> list[AssetBalance]:
        """Return insertion-ordered defensive copies."""

        with self._lock:
            return deepcopy(
                list(
                    self._balances.values()
                )
            )

    def snapshot(
        self,
    ) -> tuple[AssetBalance, ...]:
        """Return an independent tuple snapshot."""

        return tuple(
            self.all_balances()
        )

    def count(self) -> int:
        """Return the number of tracked assets."""

        return len(self)

    def clear(self) -> None:
        """Remove every tracked balance."""

        with self._lock:
            self._balances.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._balances)

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._balances)

    def __iter__(
        self,
    ) -> Iterator[AssetBalance]:
        return iter(self.snapshot())


__all__ = (
    "AssetBalance",
    "BalanceTracker",
)