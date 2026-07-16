from dataclasses import dataclass


@dataclass
class BacktestResult:
    total_trades: int
    wins: int
    losses: int
    win_rate: float


class BacktestEngine:

    def evaluate(self, trades):

        total = len(trades)

        wins = len([t for t in trades if t > 0])

        losses = total - wins

        win_rate = (wins / total * 100) if total else 0

        return BacktestResult(
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 2),
        )