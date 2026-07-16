from src.analysis.smart_money.market_structure import MarketStructureEngine

engine = MarketStructureEngine()

result = engine.analyze(

    highs=[100,105,108,112],

    lows=[90,95,100,106]

)

print(result)