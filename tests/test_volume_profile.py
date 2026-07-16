from src.analysis.technical.volume_profile import VolumeProfileEngine

engine = VolumeProfileEngine()

result = engine.analyze(

    prices=[117000,117500,118000,118500,119000],

    volumes=[20,35,80,40,25]

)

print(result)