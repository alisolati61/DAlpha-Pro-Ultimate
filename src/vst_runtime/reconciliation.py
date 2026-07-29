"""Pure external reconciliation; this module never mutates remote state."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from .models import (
    ReconciliationResult,
    ReconciliationState,
    RemoteBalance,
    RemoteFill,
    RemoteOrder,
    RemotePosition,
    VstCheckpoint,
)


class VstReconciler:
    @staticmethod
    def reconcile(
        checkpoint: VstCheckpoint,
        *,
        orders: tuple[RemoteOrder, ...] | None,
        fills: tuple[RemoteFill, ...] | None,
        positions: tuple[RemotePosition, ...] | None,
        balance: RemoteBalance | None,
    ) -> ReconciliationResult:
        if orders is None or fills is None or positions is None or balance is None:
            return ReconciliationResult(
                ReconciliationState.UNKNOWN,
                ("remote_state_unavailable",),
                ("retry_read_only_reconciliation",),
            )
        reasons: set[str] = set()
        local_orders = {item.client_order_id: item for item in checkpoint.orders}
        remote_orders = {item.client_order_id: item for item in orders}
        if len(remote_orders) != len(orders):
            reasons.add("duplicate_remote_order")
        for _key in local_orders.keys() - remote_orders.keys():
            reasons.add("local_order_missing_remotely")
        for _key in remote_orders.keys() - local_orders.keys():
            reasons.add("orphan_remote_order")
        for key in local_orders.keys() & remote_orders.keys():
            local, remote = local_orders[key], remote_orders[key]
            if (
                local.order_id != remote.order_id
                or local.status != remote.status
                or local.original_quantity != remote.original_quantity
                or local.filled_quantity != remote.filled_quantity
                or local.remaining_quantity != remote.remaining_quantity
                or local.average_price != remote.average_price
            ):
                reasons.add("order_mismatch")
        local_fill_ids = Counter(item.fill_id for item in checkpoint.fills)
        remote_fill_ids = Counter(item.fill_id for item in fills)
        if any(count > 1 for count in remote_fill_ids.values()):
            reasons.add("duplicate_remote_fill")
        if local_fill_ids - remote_fill_ids:
            reasons.add("local_fill_missing_remotely")
        if remote_fill_ids - local_fill_ids:
            reasons.add("remote_fill_missing_locally")
        local_fills = {item.fill_id: item for item in checkpoint.fills}
        for fill in fills:
            local_fill = local_fills.get(fill.fill_id)
            if local_fill and (
                local_fill.quantity != fill.quantity
                or local_fill.price != fill.price
                or local_fill.fee != fill.fee
            ):
                reasons.add("fill_mismatch")
        local_positions = {
            (item.symbol, item.side): item for item in checkpoint.positions
        }
        remote_positions = {(item.symbol, item.side): item for item in positions}
        if remote_positions.keys() - local_positions.keys():
            reasons.add("orphan_remote_position")
        if local_positions.keys() - remote_positions.keys():
            reasons.add("local_position_missing_remotely")
        for position_key in local_positions.keys() & remote_positions.keys():
            local_position = local_positions[position_key]
            remote_position = remote_positions[position_key]
            if (
                local_position.quantity != remote_position.quantity
                or local_position.entry_price != remote_position.entry_price
            ):
                reasons.add("position_mismatch")
        if checkpoint.balance is not None and (
            checkpoint.balance.balance != balance.balance
            or checkpoint.balance.equity != balance.equity
            or checkpoint.balance.available_margin != balance.available_margin
        ):
            reasons.add("balance_mismatch")
        protected = {
            item.parent_client_order_id: item.original_quantity
            for item in orders
            if item.reduce_only and item.parent_client_order_id
        }
        for order in orders:
            if not order.reduce_only and order.filled_quantity > Decimal(0):
                position_quantity = sum(
                    (
                        item.quantity
                        for item in positions
                        if item.symbol == order.symbol
                    ),
                    Decimal(0),
                )
                if protected.get(order.client_order_id, Decimal(0)) > position_quantity:
                    reasons.add("protective_quantity_mismatch")
                if order.client_order_id not in protected:
                    reasons.add("protective_order_missing")
        if reasons:
            return ReconciliationResult(
                ReconciliationState.MISMATCH,
                tuple(reasons),
                ("activate_kill_switch", "inspect_remote_account"),
            )
        return ReconciliationResult(
            ReconciliationState.MATCHED, ("matched",), ("no_action",)
        )


__all__ = ("VstReconciler",)
