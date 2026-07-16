from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class DecisionInput:
    """
    Input scores collected from all analyzers.
    """

    technical_score: float = 0.0
    smart_money_score: float = 0.0
    orderflow_score: float = 0.0
    sentiment_score: float = 0.0
    onchain_score: float = 0.0
    risk_score: float = 100.0


@dataclass(slots=True)
class DecisionResult:
    """
    Final decision produced by Decision Engine.
    """

    action: str
    confidence: float
    final_score: float
    scores: Dict[str, float] = field(default_factory=dict)
    reason: str = ""