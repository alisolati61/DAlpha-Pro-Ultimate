from src.analysis.intermarket.intermarket_engine import IntermarketEngine

engine = IntermarketEngine()

print(

    engine.analyze(

        dxy=98.5,

        gold=3370,

        sp500=6250,

        btc_dominance=61,

        usdt_dominance=4.7,

    )

)