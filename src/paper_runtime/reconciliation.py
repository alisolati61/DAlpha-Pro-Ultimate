"""Independent, read-only reconciliation of immutable paper reports."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from src.paper_runtime.models import (
    PaperEventType,
    PaperExecutionReport,
    PaperFill,
    PaperLedgerEvent,
    ReconciliationReason,
    ReconciliationResult,
    ReconciliationStatus,
)


class PaperReconciler:
    """Derive expected state from the immutable hash-chained local ledger."""

    def reconcile(self, report: PaperExecutionReport) -> ReconciliationResult:
        if not isinstance(report, PaperExecutionReport):
            raise TypeError("report must be a PaperExecutionReport")
        reasons: set[ReconciliationReason] = set()
        fills = tuple(report.fills)
        events = tuple(report.events)
        fill_ids = [item.fill_id for item in fills]
        if len(fill_ids) != len(set(fill_ids)):
            reasons.add(ReconciliationReason.DUPLICATE_FILL_ID)
        self._check_ledger_chain(events, reasons)

        accepted = tuple(
            item
            for item in events
            if item.event_type is PaperEventType.ORDER_ACCEPTED
            and item.order_id == report.order.order_id
        )
        accepted_quantity = self._single_decimal(
            accepted, "quantity", reasons
        )
        entry = tuple(item for item in fills if not item.protective)
        exits = tuple(item for item in fills if item.protective)
        entry_ledger = self._ledger_fills(
            entry, events, PaperEventType.ENTRY_FILL, reasons
        )
        exit_ledger = self._ledger_fills(
            exits, events, PaperEventType.PROTECTIVE_FILL, reasons
        )
        entry_quantity = sum(
            (quantity for _, quantity, _, _ in entry_ledger), Decimal(0)
        )
        exit_quantity = sum(
            (quantity for _, quantity, _, _ in exit_ledger), Decimal(0)
        )
        if entry_quantity != report.order.filled_quantity:
            reasons.add(ReconciliationReason.FILLED_QUANTITY_MISMATCH)
        expected_remaining = accepted_quantity - entry_quantity
        if expected_remaining != report.order.remaining_quantity:
            reasons.add(ReconciliationReason.REMAINING_QUANTITY_MISMATCH)
        expected_average = (
            Decimal(0)
            if entry_quantity == 0
            else sum(
                (quantity * price for _, quantity, price, _ in entry_ledger),
                Decimal(0),
            )
            / entry_quantity
        )
        if expected_average != report.order.average_fill_price:
            reasons.add(ReconciliationReason.AVERAGE_PRICE_MISMATCH)
        if (
            expected_position := max(
                Decimal(0), entry_quantity - exit_quantity
            )
        ) > 0 and report.position.average_entry_price != expected_average:
            reasons.add(ReconciliationReason.AVERAGE_PRICE_MISMATCH)
        entry_fees = sum(
            (fee for _, _, _, fee in entry_ledger), Decimal(0)
        )
        exit_fees = sum(
            (fee for _, _, _, fee in exit_ledger), Decimal(0)
        )
        if entry_fees != report.order.fees:
            reasons.add(ReconciliationReason.FEE_MISMATCH)
        protection_fees = sum(
            (item.fees for item in report.protections), Decimal(0)
        )
        if protection_fees != exit_fees:
            reasons.add(ReconciliationReason.FEE_MISMATCH)
        if exit_quantity > entry_quantity:
            reasons.add(ReconciliationReason.OVER_CLOSE)
        observed_entry_quantity = sum(
            (item.quantity for item in entry), Decimal(0)
        )
        observed_exit_quantity = sum(
            (item.quantity for item in exits), Decimal(0)
        )
        if observed_exit_quantity > observed_entry_quantity:
            reasons.add(ReconciliationReason.OVER_CLOSE)
        if expected_position != report.position.quantity:
            reasons.add(ReconciliationReason.POSITION_QUANTITY_MISMATCH)
        expected_side = (
            "FLAT"
            if expected_position == 0
            else "LONG" if report.order.side == "BUY" else "SHORT"
        )
        if report.position.side != expected_side:
            reasons.add(ReconciliationReason.POSITION_QUANTITY_MISMATCH)
        realized = Decimal(0)
        for _, quantity, price, _ in exit_ledger:
            if report.order.side == "BUY":
                realized += (price - expected_average) * quantity
            else:
                realized += (expected_average - price) * quantity
        if realized != report.position.realized_pnl:
            reasons.add(ReconciliationReason.REALIZED_PNL_MISMATCH)
        if realized != report.account.realized_pnl:
            reasons.add(ReconciliationReason.REALIZED_PNL_MISMATCH)
        expected_fees = entry_fees + exit_fees
        if expected_fees != report.account.fees_paid:
            reasons.add(ReconciliationReason.FEE_MISMATCH)
        expected_balance = (
            report.account.starting_balance
            + realized
            - expected_fees
        )
        if expected_balance != report.account.balance:
            reasons.add(ReconciliationReason.BALANCE_MISMATCH)
        expected_exposure = expected_position * report.order.average_fill_price
        if expected_exposure != report.account.exposure:
            reasons.add(ReconciliationReason.EXPOSURE_MISMATCH)
        protections = {
            item.protection_id: item for item in report.protections
        }
        if any(
            item.order_id not in protections
            or item.parent_order_id != report.order.order_id
            or protections[item.order_id].parent_order_id
            != report.order.order_id
            for item in exits
        ):
            reasons.add(ReconciliationReason.ORPHAN_PROTECTIVE_ORDER)
        if any(
            item.active_quantity != expected_position
            for item in report.protections
        ):
            reasons.add(ReconciliationReason.ORPHAN_PROTECTIVE_ORDER)
        if any(
            item.parent_order_id != report.order.order_id
            or item.sibling_id not in protections
            or protections[item.sibling_id].sibling_id
            != item.protection_id
            for item in report.protections
        ):
            reasons.add(ReconciliationReason.ORPHAN_PROTECTIVE_ORDER)
        if not reasons:
            return ReconciliationResult(
                ReconciliationStatus.MATCHED,
                (ReconciliationReason.MATCHED,),
            )
        return ReconciliationResult(
            ReconciliationStatus.MISMATCH, tuple(reasons)
        )

    @staticmethod
    def _payload(event: PaperLedgerEvent) -> dict[str, object]:
        value = json.loads(event.payload_json)
        if not isinstance(value, dict):
            raise ValueError
        return value

    @classmethod
    def _single_decimal(
        cls,
        events: tuple[PaperLedgerEvent, ...],
        field: str,
        reasons: set[ReconciliationReason],
    ) -> Decimal:
        if len(events) != 1:
            reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
            return Decimal(0)
        try:
            value = Decimal(str(cls._payload(events[0])[field]))
            if not value.is_finite() or value < 0:
                raise ValueError
            return value
        except (InvalidOperation, KeyError, ValueError):
            reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
            return Decimal(0)

    @classmethod
    def _ledger_fills(
        cls,
        fills: tuple[PaperFill, ...],
        events: tuple[PaperLedgerEvent, ...],
        event_type: PaperEventType,
        reasons: set[ReconciliationReason],
    ) -> tuple[tuple[PaperFill, Decimal, Decimal, Decimal], ...]:
        derived: list[tuple[PaperFill, Decimal, Decimal, Decimal]] = []
        market_by_sequence = {
            event.market_sequence: event
            for event in events
            if event.event_type is PaperEventType.MARKET_ACCEPTED
        }
        for fill in fills:
            matches = tuple(
                event
                for event in events
                if event.event_type is event_type
                and event.fill_id == fill.fill_id
                and event.order_id == fill.order_id
            )
            if len(matches) != 1:
                reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
                continue
            try:
                payload = cls._payload(matches[0])
                quantity = Decimal(str(payload["quantity"]))
                price = Decimal(str(payload["price"]))
                fee = Decimal(str(payload["fee"]))
                if (
                    not quantity.is_finite()
                    or quantity <= 0
                    or not price.is_finite()
                    or price <= 0
                    or not fee.is_finite()
                    or fee < 0
                ):
                    raise ValueError
            except (InvalidOperation, KeyError, ValueError):
                reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
                continue
            if (
                quantity != fill.quantity
                or price != fill.price
                or fee != fill.fee
                or matches[0].market_sequence != fill.market_sequence
            ):
                reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
            market_event = market_by_sequence.get(fill.market_sequence)
            if market_event is None:
                reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
            else:
                try:
                    timestamp = str(cls._payload(market_event)["timestamp"])
                except (KeyError, ValueError):
                    reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
                else:
                    expected_timestamp = fill.market_timestamp.isoformat().replace(
                        "+00:00", "Z"
                    )
                    if timestamp != expected_timestamp:
                        reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
            derived.append((fill, quantity, price, fee))
        return tuple(derived)

    @staticmethod
    def _check_ledger_chain(
        events: tuple[PaperLedgerEvent, ...],
        reasons: set[ReconciliationReason],
    ) -> None:
        identities = (
            [item.event_id for item in events],
            [item.digest for item in events],
            [item.ledger_sequence for item in events],
        )
        if any(len(values) != len(set(values)) for values in identities):
            reasons.add(ReconciliationReason.DUPLICATE_LEDGER_EVENT)
        previous = ""
        for expected_sequence, event in enumerate(events, start=1):
            if (
                event.ledger_sequence != expected_sequence
                or event.previous_digest != previous
            ):
                reasons.add(ReconciliationReason.MISSING_LEDGER_EVENT)
            previous = event.digest


__all__ = ("PaperReconciler",)
