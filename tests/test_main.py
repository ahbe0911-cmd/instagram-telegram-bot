from ig_telegram_bot.config import Settings
from ig_telegram_bot.main import build_application


def test_application_builds_without_network_call() -> None:
    settings = Settings(
        telegram_bot_token="123456:TEST_TOKEN_VALUE",
        max_concurrent_downloads=2,
        max_requests_per_minute=4,
        max_upload_mb=49,
        log_level="INFO",
    )

    application = build_application(settings)

    assert application.bot.token == settings.telegram_bot_token
    assert len(application.handlers[0]) == 4
