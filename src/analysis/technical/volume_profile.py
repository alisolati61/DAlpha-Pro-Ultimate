from dataclasses import dataclass
from typing import List


@dataclass
class VolumeNode:
    price: float
    volume: float


@dataclass
class VolumeProfile:
    poc: float
    vah: float
    val: float
    nodes: List[VolumeNode]


class VolumeProfileEngine:

    def analyze(self, prices, volumes):

        if not prices or not volumes:
            return VolumeProfile(
                poc=0,
                vah=0,
                val=0,
                nodes=[],
            )

        max_index = volumes.index(max(volumes))

        poc = prices[max_index]

        vah = max(prices)

        val = min(prices)

        nodes = [
            VolumeNode(price=p, volume=v)
            for p, v in zip(prices, volumes)
        ]

        return VolumeProfile(
            poc=poc,
            vah=vah,
            val=val,
            nodes=nodes,
        )