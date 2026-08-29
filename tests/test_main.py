import pytest

from ig_telegram_bot.config import ConfigurationError, Settings
from ig_telegram_bot.main import _webhook_security, build_application


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="123456:TEST_TOKEN_VALUE",
        max_concurrent_downloads=2,
        max_requests_per_minute=4,
        max_upload_mb=49,
        log_level="INFO",
        allowed_telegram_user_id=123456789,
    )


def test_application_builds_without_network_call() -> None:
    settings = _settings()

    application = build_application(settings)

    assert application.bot.token == settings.telegram_bot_token
    assert len(application.handlers[0]) == 6


def test_application_refuses_to_start_without_owner_id() -> None:
    settings = Settings(
        telegram_bot_token="123456:TEST_TOKEN_VALUE",
        max_concurrent_downloads=2,
        max_requests_per_minute=4,
        max_upload_mb=49,
        log_level="INFO",
    )

    with pytest.raises(ConfigurationError):
        build_application(settings)


def test_webhook_security_is_stable_and_does_not_expose_token(monkeypatch) -> None:
    monkeypatch.delenv("WEBHOOK_PATH", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET_TOKEN", raising=False)
    settings = _settings()

    path, secret = _webhook_security(settings)

    assert path.startswith("telegram-")
    assert settings.telegram_bot_token not in path
    assert settings.telegram_bot_token not in secret
    assert len(secret) == 64
