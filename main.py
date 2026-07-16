from src.logger import app_logger
from src.config.settings import settings


def main():
    print("=" * 50)
    print(settings.APP_NAME)
    print(settings.VERSION)
    print(settings.ENVIRONMENT)
    print("=" * 50)


if __name__ == "__main__":
    main()
    app_logger.info("Alpha Pro UltimateX Started Successfully")