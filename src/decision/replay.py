"""Explicit synchronous recorded replay-to-decision coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from src.data.adapters.models import RecordedMarketDataPayload
from src.data.adapters.recorded import RecordedExchangeMarketDataAdapter
from src.data.service import MarketDataService
from src.decision.recorded import DecisionService, RecordedDecision
from src.strategy.service import StrategyService


@dataclass(frozen=True, slots=True)
class EvaluationPoint:
    sequence: int
    symbol: str
    exchange: str
    timeframe: str


@dataclass(frozen=True, slots=True)
class ReplayDecisionCheckpoint:
    replay_sequence: int | None
    pending_evaluation_sequence: int | None
    decision_ids: tuple[str, ...]


class RecordedDecisionPipelineError(Exception):
    """Sanitized failure raised when local evaluation cannot complete."""

    def __init__(self) -> None:
        super().__init__("Recorded decision evaluation failed.")


class RecordedDecisionCoordinator:
    """Replay validated events and evaluate only explicit checkpoints."""

    def __init__(
        self,
        adapter: RecordedExchangeMarketDataAdapter,
        market_data: MarketDataService,
        strategy: StrategyService,
        decision: DecisionService,
    ) -> None:
        self._adapter = adapter
        self._market_data = market_data
        self._strategy = strategy
        self._decision = decision
        self._decision_ids: list[str] = []
        self._pending_point: EvaluationPoint | None = None
        self._lock = RLock()

    @property
    def checkpoint(self) -> ReplayDecisionCheckpoint:
        with self._lock:
            return ReplayDecisionCheckpoint(
                self._adapter.last_sequence,
                (
                    None
                    if self._pending_point is None
                    else self._pending_point.sequence
                ),
                tuple(self._decision_ids),
            )

    def replay_and_decide(
        self,
        batch: tuple[RecordedMarketDataPayload, ...],
        evaluation_points: tuple[EvaluationPoint, ...],
    ) -> tuple[RecordedDecision, ...]:
        """Validate the complete batch before mutating canonical state.

        Successfully replayed events remain committed. The adapter cursor is
        the resumable checkpoint, and an exact retry skips committed events.
        """
        with self._lock:
            probe = RecordedExchangeMarketDataAdapter(
                MarketDataService(), batch
            )
            probe.initialize()
            points: dict[int, EvaluationPoint] = {}
            sequences = {payload.sequence for payload in batch}
            for evaluation_point in evaluation_points:
                if (
                    evaluation_point.sequence not in sequences
                    or evaluation_point.sequence in points
                ):
                    raise ValueError("Evaluation points are invalid.")
                points[evaluation_point.sequence] = evaluation_point
            cursor = self._adapter.last_sequence
            pending = tuple(
                payload
                for payload in batch
                if cursor is None or payload.sequence > cursor
            )
            decisions: list[RecordedDecision] = []
            if self._pending_point is not None:
                decisions.append(self._complete_pending())
            for payload in pending:
                self._adapter.replay((payload,))
                self._pending_point = points.get(payload.sequence)
                if self._pending_point is None:
                    continue
                decisions.append(self._complete_pending())
            return tuple(decisions)

    def _complete_pending(self) -> RecordedDecision:
        point = self._pending_point
        if point is None:
            raise RecordedDecisionPipelineError
        try:
            proposal = self._strategy.evaluate(
                symbol=point.symbol,
                exchange=point.exchange,
                timeframe=point.timeframe,
            )
            result = self._decision.evaluate(proposal)
        except Exception as error:
            raise RecordedDecisionPipelineError from error
        self._pending_point = None
        if result.decision_id not in self._decision_ids:
            self._decision_ids.append(result.decision_id)
        return result


__all__ = (
    "EvaluationPoint",
    "RecordedDecisionCoordinator",
    "RecordedDecisionPipelineError",
    "ReplayDecisionCheckpoint",
)
