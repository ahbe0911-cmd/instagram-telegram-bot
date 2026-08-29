import asyncio
from pathlib import Path

from telegram.error import BadRequest

from ig_telegram_bot.advanced_service import AdvancedInstagramBotService
from ig_telegram_bot.config import Settings
from ig_telegram_bot.instagram import DownloadResult


class FakeMessage:
    def __init__(self, reject_group: bool = False, reject_video: bool = False) -> None:
        self.reject_group = reject_group
        self.reject_video = reject_video
        self.photos = 0
        self.videos = 0
        self.documents = 0
        self.groups = 0

    async def reply_media_group(self, media) -> None:
        del media
        self.groups += 1
        if self.reject_group:
            raise BadRequest("group rejected")

    async def reply_photo(self, photo, caption=None) -> None:
        del photo, caption
        self.photos += 1

    async def reply_video(self, video, caption=None, supports_streaming=True) -> None:
        del video, caption, supports_streaming
        self.videos += 1
        if self.reject_video:
            raise BadRequest("video rejected")

    async def reply_document(self, document, caption=None) -> None:
        del document, caption
        self.documents += 1


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="123456:TEST_TOKEN_VALUE",
        max_concurrent_downloads=2,
        max_requests_per_minute=4,
        max_upload_mb=49,
        log_level="INFO",
    )


def _result(paths: tuple[Path, ...]) -> DownloadResult:
    return DownloadResult(
        shortcode="ABCDEF",
        source_url="https://www.instagram.com/p/ABCDEF/",
        owner_username="example",
        caption="test",
        media_paths=paths,
    )


def test_large_photo_is_sent_as_document(tmp_path: Path) -> None:
    image = tmp_path / "large.jpg"
    image.write_bytes(b"x")
    image.write_bytes(b"\0" * (10 * 1024 * 1024 + 1))
    message = FakeMessage()
    service = AdvancedInstagramBotService(_settings())

    skipped = asyncio.run(service._send_result(message, _result((image,))))

    assert skipped == 0
    assert message.documents == 1
    assert message.photos == 0


def test_rejected_media_group_falls_back_to_individual_photos(tmp_path: Path) -> None:
    first = tmp_path / "1.jpg"
    second = tmp_path / "2.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    message = FakeMessage(reject_group=True)
    service = AdvancedInstagramBotService(_settings())

    skipped = asyncio.run(service._send_result(message, _result((first, second))))

    assert skipped == 0
    assert message.groups == 1
    assert message.photos == 2


def test_rejected_video_falls_back_to_document(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    message = FakeMessage(reject_video=True)
    service = AdvancedInstagramBotService(_settings())

    skipped = asyncio.run(service._send_result(message, _result((video,))))

    assert skipped == 0
    assert message.videos == 1
    assert message.documents == 1
