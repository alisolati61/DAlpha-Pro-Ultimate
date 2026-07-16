from dataclasses import dataclass


@dataclass
class HolderProfitLoss:
    average_cost: float
    current_price: float
    profit_percent: float
    in_profit: bool


class HolderProfitLossEngine:

    def analyze(
        self,
        average_cost: float,
        current_price: float,
    ) -> HolderProfitLoss:

        if average_cost == 0:
            profit = 0
        else:
            profit = (
                (current_price - average_cost)
                / average_cost
            ) * 100

        return HolderProfitLoss(
            average_cost=average_cost,
            current_price=current_price,
            profit_percent=round(profit, 2),
            in_profit=profit > 0,
        )