from src.config.settings import settings


def test_settings():

    assert settings.APP_NAME == "Alpha Pro UltimateX"

    assert settings.VERSION == "1.0.0"

    assert settings.ENVIRONMENT == "development"