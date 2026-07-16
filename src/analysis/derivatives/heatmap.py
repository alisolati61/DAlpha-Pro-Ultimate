from dataclasses import dataclass


@dataclass
class HeatmapResult:
    liquidity_level: float
    strong_wall: bool
    stop_hunt_risk: bool
    signal: str


class HeatmapEngine:

    def analyze(
        self,
        liquidity_level: float,
        average_liquidity: float,
    ) -> HeatmapResult:

        strong_wall = liquidity_level > average_liquidity * 2

        stop_hunt = liquidity_level > average_liquidity * 3

        if stop_hunt:
            signal = "STOP_HUNT_RISK"

        elif strong_wall:
            signal = "HIGH_LIQUIDITY"

        else:
            signal = "NORMAL"

        return HeatmapResult(
            liquidity_level=liquidity_level,
            strong_wall=strong_wall,
            stop_hunt_risk=stop_hunt,
            signal=signal,
        )