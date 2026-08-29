from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    """Raised when required environment configuration is invalid."""


def _read_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} باید یک عدد صحیح باشد.") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} باید بین {minimum} و {maximum} باشد.")
    return value


def _read_optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} باید یک عدد صحیح باشد.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} باید بزرگ‌تر از صفر باشد.")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    max_concurrent_downloads: int
    max_requests_per_minute: int
    max_upload_mb: int
    log_level: str
    soclip_api_key: str = ""
    instagram_username: str = ""
    instagram_sessionid: str = ""
    instagram_csrftoken: str = ""
    instagram_ds_user_id: str = ""
    allowed_telegram_user_id: int | None = None

    @property
    def story_api_configured(self) -> bool:
        return bool(self.soclip_api_key)

    @property
    def story_session_configured(self) -> bool:
        return bool(
            self.instagram_username
            and self.instagram_sessionid
            and self.instagram_csrftoken
        )

    @classmethod
    def from_environment(cls) -> Settings:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ConfigurationError(
                "متغیر TELEGRAM_BOT_TOKEN تنظیم نشده است. توکن BotFather را وارد کنید."
            )

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if log_level not in valid_levels:
            raise ConfigurationError("LOG_LEVEL معتبر نیست.")

        return cls(
            telegram_bot_token=token,
            max_concurrent_downloads=_read_int("MAX_CONCURRENT_DOWNLOADS", 2, 1, 8),
            max_requests_per_minute=_read_int("MAX_REQUESTS_PER_MINUTE", 4, 1, 30),
            max_upload_mb=_read_int("MAX_UPLOAD_MB", 49, 1, 49),
            log_level=log_level,
            soclip_api_key=os.getenv("SOCLIP_API_KEY", "").strip(),
            instagram_username=os.getenv("INSTAGRAM_USERNAME", "").strip(),
            instagram_sessionid=os.getenv("INSTAGRAM_SESSIONID", "").strip(),
            instagram_csrftoken=os.getenv("INSTAGRAM_CSRFTOKEN", "").strip(),
            instagram_ds_user_id=os.getenv("INSTAGRAM_DS_USER_ID", "").strip(),
            allowed_telegram_user_id=_read_optional_positive_int("ALLOWED_TELEGRAM_USER_ID"),
        )
