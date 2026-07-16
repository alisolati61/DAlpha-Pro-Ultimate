from datetime import datetime

from src.analysis.sentiment.economic_calendar import EconomicCalendarEngine

engine = EconomicCalendarEngine()

print(

    engine.analyze(

        name="CPI",

        currency="USD",

        event_time=datetime.now(),

    )

)

print(

    engine.analyze(

        name="Retail Sales",

        currency="USD",

        event_time=datetime.now(),

    )

)