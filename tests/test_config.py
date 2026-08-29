import pytest

from ig_telegram_bot.config import ConfigurationError, Settings


def test_settings_require_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigurationError):
        Settings.from_environment()


def test_settings_load_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    for key in (
        "MAX_CONCURRENT_DOWNLOADS",
        "MAX_REQUESTS_PER_MINUTE",
        "MAX_UPLOAD_MB",
        "LOG_LEVEL",
        "INSTAGRAM_USERNAME",
        "INSTAGRAM_SESSIONID",
        "INSTAGRAM_CSRFTOKEN",
        "INSTAGRAM_DS_USER_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings.from_environment()

    assert settings.telegram_bot_token == "test-token"
    assert settings.max_concurrent_downloads == 2
    assert settings.max_requests_per_minute == 4
    assert settings.max_upload_mb == 49
    assert settings.story_session_configured is False


def test_story_session_settings_are_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_USERNAME", "owner")
    monkeypatch.setenv("INSTAGRAM_SESSIONID", "session-value")
    monkeypatch.setenv("INSTAGRAM_CSRFTOKEN", "csrf-value")
    monkeypatch.setenv("INSTAGRAM_DS_USER_ID", "1234")

    settings = Settings.from_environment()

    assert settings.story_session_configured is True
    assert settings.instagram_username == "owner"
    assert settings.instagram_sessionid == "session-value"
    assert settings.instagram_csrftoken == "csrf-value"
    assert settings.instagram_ds_user_id == "1234"


def test_upload_limit_cannot_exceed_cloud_bot_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("MAX_UPLOAD_MB", "50")
    with pytest.raises(ConfigurationError):
        Settings.from_environment()
